"""Independent prototype engine. No imports from the investigated application."""
from __future__ import annotations

import re
import time
import threading
from collections import OrderedDict
from pathlib import Path
from dialogue import split_speaker,MAX_CAPTION
from recognition import Reading
from translation_backend import TranslationBackend,InferenceCancelled
from translation_info import TranslationInfo,CachedTranslation
from dataclasses import replace


def fit_subtitle(frame):
    """Bound detector work while preserving subtitle geometry and source pixels."""
    import cv2
    import numpy as np
    if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
        raise ValueError('OCR görüntüsü uint8 BGR olmalı.')
    height, width = frame.shape[:2]
    if not height or not width:
        raise ValueError('OCR görüntüsü boş olamaz.')
    scale = min(640 / width, 96 / height)
    resized = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))),
                         interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    canvas = np.zeros((96, 640, 3), dtype=np.uint8)
    y, x = (96 - resized.shape[0]) // 2, (640 - resized.shape[1]) // 2
    canvas[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return canvas




_tokenizer_loading=threading.Lock()


class Engine:
    def __init__(self, models: Path, profile=None, fallback=True, ocr_kind='subtitle',cancelled=lambda:False,quality='fast',ignore_speaker=True):
        if ocr_kind not in ('subtitle', 'hud'):
            raise ValueError('Bilinmeyen OCR görevi.')
        from subtitle_ocr import SubtitleReader
        self.subtitle_reader=SubtitleReader(quality)
        self.ocr_kind = ocr_kind
        self.cancelled = cancelled
        self.profile = profile
        if type(ignore_speaker) is not bool:raise ValueError('Konuşmacı eşleştirme tercihi geçersiz.')
        self.ignore_speaker=ignore_speaker
        self.previous = None
        self.previous_at = 0.0
        self.last_match = None
        self.fallback = fallback
        from rapidocr import RapidOCR

        ocr = models / 'ocr'
        mt = models / 'opus-mt-tc-big-en-tr-ct2'
        files = {'Det.model_path': ocr / 'PP-OCRv6_det_small.onnx',
                 'Rec.model_path': ocr / 'PP-OCRv6_rec_small.onnx',
                 'Cls.model_path': ocr / 'ch_ppocr_mobile_v2.0_cls_mobile.onnx'}
        for path in files.values():
            if not path.is_file():
                raise FileNotFoundError(f'Model bulunamadı: {path}')
        self.ocr = RapidOCR(params={
            'Global.model_root_dir': str(ocr),
            **{k: str(v) for k, v in files.items()},
            'Global.use_cls': False,
            'Global.use_vertical_padding': False,
            'Det.limit_type': 'max',
            'Det.limit_side_len': 640 if ocr_kind == 'subtitle' else 960,
            'Global.max_side_len': 640 if ocr_kind == 'subtitle' else 960,
            'EngineConfig.onnxruntime.intra_op_num_threads': 1 if ocr_kind=='hud' else 2,
            'EngineConfig.onnxruntime.inter_op_num_threads': 1,
        })
        self.model_path = mt
        self.tokenizer = self.translator = None
        self._translation_prepared=False
        self.cache: OrderedDict[str, CachedTranslation] = OrderedDict()
        self.last_translation=None
        # Optional glossary.UserDictionary; workers only read immutable snapshots.
        self.dictionary=None
        self._dictionary_version=None
        self._terms=None

    def prepare_translation(self,*,can_infer=lambda:True):
        if self._translation_prepared:
            return
        def guard():
            if self.cancelled() or not can_infer():
                raise InferenceCancelled()
        guard()
        mt = self.model_path
        if self.tokenizer is None:
            # Transformers resolves AutoTokenizer lazily. Its first attribute
            # lookup must not race between the independent subtitle/HUD engines.
            while not _tokenizer_loading.acquire(timeout=.05):guard()
            try:
                guard()
                from transformers import AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(str(mt), local_files_only=True,
                                                               use_fast=False)
            finally:_tokenizer_loading.release()
        guard()
        backend=self.translator
        if backend is None:
            # HUD always, subtitles on request ("game first"): leave the GPU to the game.
            cpu_only=self.ocr_kind=='hud' or getattr(self,'prefer_cpu',False)
            backend=TranslationBackend(mt,cpu_only=cpu_only,guard=guard)
        # Completed acquisition belongs to the engine even if the subtitle
        # changed during loading. Keep it; only obsolete inference is canceled.
        self.translator=backend
        if backend.device=='cuda':
            # Exercise lazy CUDA DLL loading before advertising GPU readiness.
            hello=self.tokenizer.convert_ids_to_tokens(self.tokenizer.encode('Hello.',add_special_tokens=True))
            backend.translate_batch([hello],guard=guard,beam_size=1,max_decoding_length=24)
        guard()
        self._translation_prepared=True

    def _read_ocr(self,*args,**kwargs):
        if self.cancelled():
            raise InferenceCancelled()
        return self.ocr(*args,**kwargs)

    def read(self, frame) -> Reading:
        started = time.perf_counter()
        if self.ocr_kind=='hud':
            from dataclasses import replace
            from recognition import Scan
            import numpy as np
            from hud import read_hud
            if frame.ndim!=3 or frame.shape[2]!=3 or frame.dtype!=np.uint8 or not frame.size:
                raise ValueError('HUD görüntüsü boş olmayan uint8 BGR olmalı.')
            reading=read_hud(self._read_ocr,frame,lambda:(time.perf_counter()-started)*1000)
            return replace(reading,variant='hud',scans=(Scan('hud',reading.confidence,reading.elapsed_ms),))
        return self.subtitle_reader.read(frame,fit_subtitle,self._read_ocr)

    def translate(self, text: str, *, can_infer=lambda:True) -> str:
        started=time.perf_counter()
        self.last_translation=None
        self.last_match = None
        dictionary=getattr(self,'dictionary',None)
        snapshot=dictionary.snapshot() if dictionary is not None else None
        self._terms=snapshot
        if snapshot is not None:
            if snapshot.version!=getattr(self,'_dictionary_version',None):
                self.cache.clear()
                self._dictionary_version=snapshot.version
            corrected=snapshot.correction(text)
            if corrected is not None:
                self.last_translation=TranslationInfo('user',(time.perf_counter()-started)*1000)
                return corrected
        if self.profile:
            if time.monotonic() - self.previous_at > 12:
                self.previous = None
            hit = self.profile.match(text,self.previous,ignore_speaker=self.ignore_speaker)
            if hit:
                self.previous = hit.key
                self.previous_at = time.monotonic()
                self.last_match = hit
                self.last_translation=TranslationInfo('profile',(time.perf_counter()-started)*1000,
                    profile_kind=hit.kind,match_percent=hit.confidence)
                return hit.translation
            if not self.fallback:
                self.last_translation=TranslationInfo('unmatched',(time.perf_counter()-started)*1000)
                return ''
        if text in self.cache:
            self.cache.move_to_end(text)
            cached=self.cache[text]
            self.last_translation=replace(cached.info,cached=True,elapsed_ms=(time.perf_counter()-started)*1000)
            return cached.text
        if self.ocr_kind=='hud':
            from hud import translate_marked
            translated=translate_marked(lambda part:self._translate_neural(part,can_infer),text)
        else:
            translated=self._translate_neural(text,can_infer)
        backend=self.translator
        self.last_translation=TranslationInfo('model',(time.perf_counter()-started)*1000,
            device=getattr(backend,'device',None),
            fallback=bool(backend.cuda_failure) if hasattr(backend,'cuda_failure') else None)
        if len(text)<=MAX_CAPTION and len(translated)<=MAX_CAPTION:
            self.cache[text] = CachedTranslation(translated,self.last_translation)
        if len(self.cache) > (40 if self.ocr_kind=='hud' else 120):
            self.cache.popitem(last=False)
        return translated

    def _translate_neural(self,text,can_infer):
        if self.cancelled() or not can_infer():
            raise InferenceCancelled()
        speaker,body=('',text) if self.ocr_kind=='hud' else split_speaker(text)
        terms=getattr(self,'_terms',None)
        if terms is not None:
            body=terms.apply_terms(body)
        self.prepare_translation(can_infer=can_infer)
        # Split long input explicitly, rather than silently truncating it.
        chunks = []
        for sentence in re.split(r'(?<=[.!?])\s+|\n+', body):
            ids = self.tokenizer.encode(sentence, add_special_tokens=False)
            for start in range(0, len(ids), 160):
                chunk = ids[start:start + 160]
                chunks.append(self.tokenizer.convert_ids_to_tokens(chunk) + ['</s>'])
        if self.cancelled() or not can_infer():
            raise InferenceCancelled()
        def guard():
            if self.cancelled() or not can_infer():
                raise InferenceCancelled()
        # A successful bounded decode must include EOS. A length-capped result
        # is not a complete translation, even when it looks like valid prose.
        pending=list(range(len(chunks)))
        completed={}
        for limit in (256,512):
            if not pending:
                break
            guard()
            results=self.translator.translate_batch([chunks[index] for index in pending],guard=guard,
                beam_size=1,max_decoding_length=limit,max_input_length=0,return_end_token=True)
            if len(results)!=len(pending):
                raise RuntimeError('Çeviri motoru eksik sonuç döndürdü; metin gösterilmedi.')
            remaining=[]
            for index,result in zip(pending,results,strict=True):
                if result.hypotheses and result.hypotheses[0] and result.hypotheses[0][-1]=='</s>':
                    completed[index]=result.hypotheses[0][:-1]
                else:
                    remaining.append(index)
            pending=remaining
        if pending:
            raise RuntimeError('Çeviri çıktı sınırında tamamlanamadı; kesilmiş metin gösterilmedi.')
        translated=' '.join(self.tokenizer.decode(self.tokenizer.convert_tokens_to_ids(completed[index]),
            skip_special_tokens=True).strip() for index in range(len(chunks)))
        if speaker:
            translated = speaker + ': ' + translated
        return translated
