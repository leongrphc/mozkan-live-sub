"""Capture lifecycle shared by subtitle and HUD channels."""
import queue
import threading
import time

from engine import Engine,InferenceCancelled
from stability import StableText
from profiles import GameProfile
from control import CaptureControl
from dialogue import CaptionSelector
from subtitle_ocr import valid_quality,valid_interval
from diagnostics import OcrObservation,TranslationObservation
from thread_priority import lower_current_thread
from startup import CaptureProgress,CaptureFailure


class ChangeGate:
    def __init__(self, refresh_seconds=2.0, clock=time.monotonic):
        self.previous = None
        self.reading = None
        self.fresh = False
        self.refresh_seconds = refresh_seconds
        self.clock = clock
        self.last_read = float('-inf')
        self.sample=0

    def read(self, engine, frame, *, force=False):
        import cv2
        summary = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (320, 48),interpolation=cv2.INTER_AREA)
        changed = force or self.previous is None or self.clock() - self.last_read >= self.refresh_seconds
        if not changed:
            delta=cv2.absdiff(summary,self.previous)
            # A short word, changed digit or faint caption may occupy too few
            # pixels to move the whole-strip mean. Preserve that local change.
            changed=float(delta.mean())>=1.2 or float(delta.reshape(6,8,40,8).mean(axis=(1,3)).max())>=1.2
        if changed:
            self.reading = engine.read(frame)
            self.previous = summary
            self.last_read = self.clock()
            self.sample+=1
        self.fresh = bool(changed)
        return self.reading


def run_capture(models, region, stop, output, status, error,
                profile_path='', fallback=True, interval=.15,
                engine_factory=Engine, frames=None, movie=False, control=None, ocr_kind='subtitle',stacked=False,
                quality='fast',diagnostics=None,ignore_speaker=True,prepare_model=False,
                progress=None,launch_gate=None,failure=None,dictionary=None,
                prefer_cpu=False,low_priority=False):
    """Return only after the translation child finishes, including on failures."""
    translator = None
    priority = None
    jobs = queue.Queue(maxsize=1)
    control = control if control is not None else CaptureControl()
    def stage(component,status):
        if progress is not None:progress(CaptureProgress(component,status))
    def failed(exc):
        if failure is not None:failure(CaptureFailure(type(exc).__name__,str(exc)))
        error(str(exc))
    try:
        if stop.is_set():
            return
        if (not valid_quality(quality) or not valid_interval(interval,minimum=0 if frames is not None else .08)
                or type(ignore_speaker) is not bool):
            raise ValueError('OCR kalitesi veya tarama aralığı geçersiz.')
        if type(prefer_cpu) is not bool or type(low_priority) is not bool:
            raise ValueError('Performans tercihi geçersiz.')
        if ocr_kind=='hud' or low_priority:
            priority=lower_current_thread()
        if ocr_kind=='hud':
            if stop.wait(1.2):return
        if profile_path:stage('profile','loading')
        profile = GameProfile(profile_path) if profile_path else None
        if profile is not None:stage('profile','ready')
        if stop.is_set():
            return
        stage('ocr','loading')
        engine = engine_factory(models, profile=profile, fallback=fallback, ocr_kind=ocr_kind,
                                cancelled=lambda:stop.is_set() or control.snapshot()[0],
                                quality=quality if ocr_kind=='subtitle' else 'fast',ignore_speaker=ignore_speaker)
        if dictionary is not None:
            engine.dictionary=dictionary
        if prefer_cpu:
            engine.prefer_cpu=True
        stage('ocr','ready')
        if movie or prepare_model and (profile is None or fallback):
            stage('translation','loading')
            while not stop.is_set():
                if control.snapshot()[0]:
                    stop.wait(.05)
                    continue
                try:
                    engine.prepare_translation()
                    stage('translation','ready')
                    break
                except InferenceCancelled:
                    stop.wait(.05)
        if stop.is_set():
            return
        stage('capture','ready')
        if launch_gate is not None:
            while not launch_gate.wait(.05):
                if stop.is_set():return
            if stop.is_set():return
        def translate():
            reported_backend=None
            translation_priority=None
            try:
                if ocr_kind=='hud' or low_priority:translation_priority=lower_current_thread()
                while not stop.is_set():
                    try:
                        revision, phrase = jobs.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if stop.is_set() or not control.current(revision):
                        continue
                    try:
                        result = engine.translate(phrase,can_infer=lambda:not stop.is_set() and control.current(revision))
                    except InferenceCancelled:
                        continue
                    info=getattr(engine,'last_translation',None)
                    device=info.device if info is not None and info.source=='model' else None
                    failure=info.fallback if info is not None else None
                    if device in ('cuda','cpu') and not info.cached and (device,failure)!=reported_backend:
                        reported_backend=(device,failure)
                        status('Çeviri motoru: NVIDIA CUDA (FP16).' if device=='cuda' else
                               ('CUDA kullanılamadı; çeviri CPU üzerinde sürüyor.' if failure else
                                'Çeviri motoru: CPU (INT8).'))
                    control.publish(revision, stop, output, phrase, result)
                    if diagnostics is not None and info is not None and not stop.is_set() and control.current(revision):
                        diagnostics(TranslationObservation(info,time.monotonic()),revision)
            except Exception as exc:
                failed(exc)
                stop.set()
            finally:
                if translation_priority is not None:translation_priority.restore()
        translator = threading.Thread(target=translate, daemon=False)
        translator.start()
        status('Çeviri açık. Durdurmak için paneli açın.')
        stable = StableText(blank_timeout=.8 if movie else 2.0)
        gate = ChangeGate(refresh_seconds=.75 if movie else 2.0)
        selector = CaptionSelector()
        last_text_at = time.monotonic()
        empty_notice = False
        observed_revision = control.snapshot()[1]
        def consume(frame):
            nonlocal last_text_at, empty_notice, stable, gate, selector, observed_revision
            paused, before_read = control.snapshot()
            if paused:
                return
            if before_read != observed_revision:
                stable = StableText(blank_timeout=.8 if movie else 2.0)
                gate = ChangeGate(refresh_seconds=.75 if movie else 2.0)
                selector = CaptionSelector()
                observed_revision = before_read
                last_text_at = time.monotonic()
                empty_notice = False
            try:
                reading = gate.read(engine, frame, force=stable.pending)
            except InferenceCancelled:
                return
            text = reading.text
            if stop.is_set() or not control.current(before_read):
                return
            if stacked and ocr_kind=='subtitle':
                text = selector.select(text,stable.accepted)
            now = time.monotonic()
            if text:
                last_text_at = now
                if empty_notice:
                    status('Altyazı yeniden okunuyor; çeviri açık.')
                empty_notice = False
            elif not empty_notice and now - last_text_at >= 8:
                status('Seçilen alanda yazı okunamıyor. Alanı önizleyin; İngilizce altyazı satırının çerçeve içinde kaldığını kontrol edin.')
                empty_notice = True
            phrase = stable.observe(text, now,reading.confidence,fresh=gate.fresh)
            if phrase is not None:
                revision = control.offer(before_read)
                if revision is None:
                    return
                observed_revision = revision
                if not phrase:
                    control.publish(revision, stop, output, '', '')
                else:
                    if movie:
                        # A confirmed new subtitle invalidates the old visible
                        # translation while its own translation is pending.
                        control.publish(revision, stop, output, phrase, '')
                    try:
                        jobs.get_nowait()
                    except queue.Empty:
                        pass
                    source=reading.text if ocr_kind=='hud' and ' '.join(reading.text.split())==phrase else phrase
                    jobs.put_nowait((revision, source))
            if diagnostics is not None and not stop.is_set() and control.current(observed_revision):
                diagnostics(OcrObservation(reading,gate.fresh,gate.sample,time.monotonic(),gate.last_read),observed_revision)
        if frames is not None:
            for frame in frames:
                if stop.is_set():
                    break
                consume(frame)
                stop.wait(interval)
        else:
            import mss
            import numpy as np
            x, y, w, h = region
            with mss.mss() as capture:
                while not stop.is_set():
                    if control.snapshot()[0]:
                        stop.wait(.05)
                        continue
                    started = time.monotonic()
                    shot = capture.grab(dict(left=x, top=y, width=w, height=h))
                    consume(np.asarray(shot)[:, :, :3].copy())
                    stop.wait(max(0, interval - (time.monotonic() - started)))
    except Exception as exc:
        failed(exc)
    finally:
        stop.set()
        try:
            if translator:translator.join()
        finally:
            if priority is not None:priority.restore()
