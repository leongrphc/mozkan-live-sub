import sys
import threading
import unittest
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from engine import Engine,InferenceCancelled


class CompletionTests(unittest.TestCase):
    def test_waiting_for_other_tokenizer_load_can_be_canceled_before_acquisition(self):
        import engine as module
        reader=self.engine(lambda *args,**kwargs:None)
        reader.tokenizer=reader.translator=None
        reader._translation_prepared=False
        reader.model_path=Path('own-model')
        canceled=threading.Event();finished=threading.Event();failures=[]
        def prepare():
            try:reader.prepare_translation(can_infer=lambda:not canceled.is_set())
            except BaseException as error:failures.append(error)
            finally:finished.set()
        module._tokenizer_loading.acquire()
        task=threading.Thread(target=prepare)
        try:
            task.start();canceled.set()
            self.assertTrue(finished.wait(1),'Cancellation must not await the other model load')
            self.assertEqual(len(failures),1)
            self.assertIsInstance(failures[0],InferenceCancelled)
            self.assertIsNone(reader.translator)
        finally:module._tokenizer_loading.release();task.join(2)

    def test_cached_translation_retains_its_original_device_after_backend_fallback(self):
        calls=[]
        def translate(sources,**options):
            calls.append(sources)
            return [SimpleNamespace(hypotheses=[['çeviri','</s>']])]
        engine=self.engine(translate)
        engine.translator.device='cuda'
        engine.translator.cuda_failure=None
        self.assertEqual(engine.translate('Known input.'),'çeviri')
        self.assertEqual(engine.last_translation.device,'cuda')
        self.assertFalse(engine.last_translation.cached)
        engine.translator.device='cpu'
        engine.translator.cuda_failure='controlled failure'
        self.assertEqual(engine.translate('Known input.'),'çeviri')
        self.assertEqual(engine.last_translation.device,'cuda')
        self.assertTrue(engine.last_translation.cached)
        self.assertFalse(engine.last_translation.fallback)
        self.assertEqual(len(calls),1)

    def test_obsolete_caption_after_backend_acquisition_retains_model_for_current_caption(self):
        engine=self.engine(lambda *args,**kwargs:None)
        engine.translator=None
        engine._translation_prepared=False
        engine.model_path=Path('own-model')
        allowed=[True]
        inferences=[]
        def infer(sources,*,guard,**options):
            guard()
            inferences.append(sources)
            return [SimpleNamespace(hypotheses=[['güncel','</s>']])]
        backend=SimpleNamespace(device='cuda',translate_batch=infer)
        def acquired(*args,**kwargs):
            allowed[0]=False
            return backend
        with patch.dict(sys.modules,{'transformers':SimpleNamespace(AutoTokenizer=object())}),patch('engine.TranslationBackend',side_effect=acquired) as acquire:
            with self.assertRaises(InferenceCancelled):
                engine.prepare_translation(can_infer=lambda:allowed[0])
            self.assertIs(engine.translator,backend)
            self.assertFalse(inferences)
            allowed[0]=True
            self.assertEqual(engine.translate('Current input.',can_infer=lambda:allowed[0]),'güncel')
        self.assertEqual(acquire.call_count,1)
        self.assertEqual(len(inferences),2)

    def engine(self,callback):
        engine=Engine.__new__(Engine)
        engine._translation_prepared=True
        engine.profile=None
        engine.ocr_kind='subtitle'
        engine.cancelled=lambda:False
        engine.cache=OrderedDict()
        engine.tokenizer=SimpleNamespace(encode=lambda text,**kwargs:text.split(),
            convert_ids_to_tokens=lambda tokens:tokens,convert_tokens_to_ids=lambda tokens:tokens,
            decode=lambda tokens,**kwargs:' '.join(tokens))
        engine.translator=SimpleNamespace(translate_batch=callback)
        return engine

    def test_long_input_keeps_all_tokens_and_original_chunk_order(self):
        calls=[]
        def translate(sources,**options):
            calls.append((sources,options))
            return [SimpleNamespace(hypotheses=[source]) for source in sources]
        engine=self.engine(translate)
        text=' '.join('word'+str(index) for index in range(401))
        self.assertEqual(engine.translate(text),text)
        self.assertEqual([len(chunk) for chunk in calls[0][0]],[161,161,82])
        self.assertEqual(calls[0][1]['max_input_length'],0)
        self.assertTrue(calls[0][1]['return_end_token'])

    def test_only_unfinished_chunk_is_retried_and_original_order_is_restored(self):
        calls=[]
        def translate(sources,**options):
            calls.append((sources,options))
            if len(calls)==1:
                return [SimpleNamespace(hypotheses=[['bir','</s>']]),
                        SimpleNamespace(hypotheses=[['kesilmiş']])]
            return [SimpleNamespace(hypotheses=[['iki','</s>']])]
        engine=self.engine(translate)
        self.assertEqual(engine.translate('First sentence. Second sentence.'),'bir iki')
        self.assertEqual(calls[1][0],[calls[0][0][1]])
        self.assertEqual([options['max_decoding_length'] for _,options in calls],[256,512])

    def test_still_incomplete_output_is_not_returned_or_cached(self):
        calls=[]
        def translate(sources,**options):
            calls.append(sources)
            return [SimpleNamespace(hypotheses=[['unfinished']])]
        engine=self.engine(translate)
        with self.assertRaisesRegex(RuntimeError,'tamamlanamadı'):
            engine.translate('Known input.')
        self.assertEqual(len(calls),2)
        self.assertEqual(engine.cache,{})

    def test_canceled_retry_does_not_start_another_inference(self):
        allowed=[True]
        calls=[]
        def translate(sources,**options):
            calls.append(sources)
            allowed[0]=False
            return [SimpleNamespace(hypotheses=[['unfinished']])]
        engine=self.engine(translate)
        with self.assertRaises(InferenceCancelled):
            engine.translate('Known input.',can_infer=lambda:allowed[0])
        self.assertEqual(len(calls),1)
        self.assertEqual(engine.cache,{})

    def test_result_count_mismatch_is_explicit_failure(self):
        engine=self.engine(lambda *args,**kwargs:[])
        with self.assertRaisesRegex(RuntimeError,'eksik sonuç'):
            engine.translate('Known input.')
        self.assertEqual(engine.cache,{})

    def test_cancellation_after_tokenizer_loading_prevents_backend_acquisition(self):
        engine=self.engine(lambda *args,**kwargs:None)
        engine.translator=engine.tokenizer=None
        engine._translation_prepared=False
        engine.model_path=Path('own-model')
        allowed=[True]
        def load(*args,**kwargs):
            allowed[0]=False
            return object()
        module=SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=load))
        with patch.dict(sys.modules,{'transformers':module}),patch('engine.TranslationBackend') as backend:
            with self.assertRaises(InferenceCancelled):
                engine.prepare_translation(can_infer=lambda:allowed[0])
        backend.assert_not_called()

