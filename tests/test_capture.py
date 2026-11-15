import sys
import threading
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import numpy as np
from recognition import Reading
from capture import ChangeGate, run_capture,InferenceCancelled
from dialogue import Caption, render_caption, split_speaker
from control import CaptureControl


class CaptureTests(unittest.TestCase):
    def test_gate_detects_short_or_faint_text_without_waiting_for_periodic_refresh(self):
        from PIL import Image,ImageDraw,ImageFont
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
        class Reader:
            calls=0
            def read(self,frame):
                self.calls+=1
                return Reading('known',.99,'test',0)
        for background,fill,text in ((0,255,'No!'),(220,235,'We need to leave.')):
            blank=Image.new('RGB',(950,65),(background,)*3)
            caption=blank.copy()
            ImageDraw.Draw(caption).text((475,32),text,font=font,anchor='mm',fill=(fill,)*3)
            reader=Reader()
            gate=ChangeGate(clock=lambda:0)
            gate.read(reader,np.asarray(blank)[:,:,::-1].copy())
            gate.read(reader,np.asarray(caption)[:,:,::-1].copy())
            self.assertTrue(gate.fresh)
            self.assertEqual(reader.calls,2)

    def test_pause_during_movie_model_preparation_waits_then_resumes_same_engine(self):
        entered,prepared,stop=threading.Event(),threading.Event(),threading.Event()
        control=CaptureControl()
        counts={'engines':0,'prepare':0}
        errors=[]
        class Reader:
            def __init__(self,*args,**kwargs):
                counts['engines']+=1
            def prepare_translation(self):
                counts['prepare']+=1
                if counts['prepare']==1:
                    control.pause(True)
                    entered.set()
                    raise InferenceCancelled()
                prepared.set()
        worker=threading.Thread(target=run_capture,kwargs=dict(models=Path('.'),region=(0,0,200,80),
            stop=stop,output=lambda *args:None,status=lambda _:None,error=errors.append,
            frames=[],movie=True,engine_factory=Reader,control=control))
        worker.start()
        try:
            self.assertTrue(entered.wait(3))
            self.assertFalse(prepared.wait(.15))
            control.pause(False)
            worker.join(3)
            self.assertTrue(prepared.is_set())
        finally:
            stop.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors,[])
        self.assertEqual(counts,dict(engines=1,prepare=2))

    def test_pause_resume_keeps_model_and_discards_previous_revision(self):
        entered, release, stop = threading.Event(), threading.Event(), threading.Event()
        control = CaptureControl()
        outputs, errors, counts = [], [], {'models': 0, 'translation': 0, 'reads': 0}
        class Reader:
            def __init__(self, *args, **kwargs):
                counts['models'] += 1
            def read(self, frame):
                counts['reads'] += 1
                return Reading('Hello',1.0,'test',0.0)
            def translate(self, text, *, can_infer=None):
                counts['translation'] += 1
                if counts['translation'] == 1:
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError('missing release')
                    return 'Eski'
                return 'Yeni'
        frame = np.zeros((80,200,3),dtype=np.uint8)
        def frames():
            yield frame
            yield frame
            if not entered.wait(3):
                raise TimeoutError('inference did not start')
            control.pause(True)
            reads = counts['reads']
            yield frame
            if counts['reads'] != reads:
                raise AssertionError('OCR ran while paused')
            control.pause(False)
            yield frame
            yield frame
            release.set()
            for _ in range(300):
                yield frame
        def output(source,target):
            outputs.append((source,target))
            stop.set()
        worker = threading.Thread(target=run_capture,kwargs=dict(
            models=Path('.'),region=(0,0,200,80),stop=stop,output=output,
            status=lambda text:None,error=errors.append,frames=frames(),
            interval=.01,engine_factory=Reader,control=control))
        worker.start()
        try:
            worker.join(5)
        finally:
            stop.set(); release.set(); worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors,[])
        self.assertEqual(outputs,[('Hello','Yeni')])
        self.assertEqual(counts['models'],1)

    def test_movie_new_caption_discards_inflight_old_translation(self):
        entered, release, stop = threading.Event(), threading.Event(), threading.Event()
        outputs, errors = [], []
        class Reader:
            def __init__(self, *args, **kwargs):
                pass
            def prepare_translation(self):
                pass
            def read(self, frame):
                return Reading('First caption.' if frame.mean() == 0 else 'Second caption.',1.0,'test',0.0)
            def translate(self, text, *, can_infer=None):
                if text == 'First caption.':
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError('missing inference release')
                    return 'Eski çeviri'
                return 'Yeni çeviri'
        first = np.zeros((80, 200, 3), dtype=np.uint8)
        second = np.full_like(first, 255)
        def frames():
            yield first
            yield first
            if not entered.wait(3):
                raise TimeoutError('first inference did not start')
            yield second
            yield second
            release.set()
            for _ in range(300):
                yield second
        def output(source, target):
            outputs.append((source, target))
            if target == 'Yeni çeviri':
                stop.set()
        worker = threading.Thread(target=run_capture, kwargs=dict(
            models=Path('.'), region=(0,0,200,80), stop=stop, output=output,
            status=lambda message: None, error=errors.append, movie=True,
            frames=frames(), interval=.01, engine_factory=Reader))
        worker.start()
        try:
            worker.join(5)
        finally:
            stop.set(); release.set(); worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertIn(('Second caption.', ''), outputs)
        self.assertIn(('Second caption.', 'Yeni çeviri'), outputs)
        self.assertNotIn(('First caption.', 'Eski çeviri'), outputs)

    def test_cancel_during_model_initialization_does_not_start_capture(self):
        entered, release, stop = threading.Event(), threading.Event(), threading.Event()
        errors, outputs = [], []
        class LateEngine:
            def __init__(self, *args, **kwargs):
                entered.set()
                if not release.wait(5):
                    raise TimeoutError('initialization release missing')
            def read(self, frame):
                raise AssertionError('capture started after cancellation')
        worker = threading.Thread(target=run_capture, kwargs=dict(
            models=Path('.'), region=(0, 0, 100, 100), stop=stop,
            output=lambda *args: outputs.append(args), status=lambda message: None,
            error=errors.append, engine_factory=LateEngine, frames=[]))
        worker.start()
        try:
            self.assertTrue(entered.wait(3))
            stop.set()
            self.assertTrue(worker.is_alive())
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(outputs, [])
        self.assertEqual(errors, [])

    def test_static_frames_reuse_ocr_and_blank_changes_are_examined(self):
        class Reader:
            count = 0
            def read(self, frame):
                self.count += 1
                return Reading('Hello' if frame.mean() else '',1.0,'test',0.0)
        reader = Reader()
        gate = ChangeGate()
        bright = np.full((80, 200, 3), 200, dtype=np.uint8)
        self.assertEqual(gate.read(reader, bright).text, 'Hello')
        self.assertEqual(gate.read(reader, bright).text, 'Hello')
        self.assertEqual(reader.count, 1)
        self.assertEqual(gate.read(reader, np.zeros_like(bright)).text, '')
        self.assertEqual(reader.count, 2)

    def test_cancellation_retains_worker_until_inference_finishes(self):
        entered, release, stop = threading.Event(), threading.Event(), threading.Event()
        outputs, errors = [], []
        class FakeEngine:
            def __init__(self, *args, **kwargs):
                pass
            def read(self, frame):
                return Reading('Hello',1.0,'test',0.0)
            def translate(self, text, *, can_infer=None):
                entered.set()
                if not release.wait(5):
                    raise TimeoutError('test inference release missing')
                return 'Merhaba'
        frame = np.zeros((80, 200, 3), dtype=np.uint8)
        worker = threading.Thread(target=run_capture, kwargs=dict(
            models=Path('.'), region=(0, 0, 200, 80), stop=stop,
            output=lambda *args: outputs.append(args), status=lambda message: None,
            error=errors.append, engine_factory=FakeEngine,
            frames=(frame for _ in range(1000)), interval=.01))
        worker.start()
        try:
            self.assertTrue(entered.wait(3))
            stop.set()
            worker.join(.15)
            self.assertTrue(worker.is_alive())
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(outputs, [])
        self.assertEqual(errors, [])

    def test_dialogue_escapes_text_and_keeps_speaker(self):
        self.assertEqual(split_speaker('John: Leave now.'), ('John', 'Leave now.'))
        rendered = render_caption(Caption('John','<img src=x>'))
        self.assertIn('&lt;img', rendered)
        self.assertNotIn('<img', rendered)
