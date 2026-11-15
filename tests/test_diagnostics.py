import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from diagnostics import DiagnosticMailbox,DiagnosticUpdate,OcrObservation,TranslationObservation
from translation_info import TranslationInfo
from recognition import Reading,Scan
from capture import run_capture
from main import QApplication,Window
from settings import Settings


class DiagnosticsTests(unittest.TestCase):
    def test_accepted_export_facts_bound_context_across_pending_drains(self):
        mailbox=DiagnosticMailbox()
        new=DiagnosticUpdate(2,'subtitle',3,self.observation())
        old=DiagnosticUpdate(1,'subtitle',100,self.observation())
        mailbox.post(new)
        self.assertEqual(mailbox.drain(),(new,))
        mailbox.accept(new)
        mailbox.post(old)
        self.assertEqual(mailbox.drain(),())
        self.assertEqual(mailbox.snapshot(),(new,))
        with self.assertRaises(ValueError):mailbox.accept(DiagnosticUpdate(3,'unknown',0,self.observation()))
        mailbox.clear()
        self.assertEqual(mailbox.snapshot(),())

    def observation(self,*,fresh=True):
        now=time.monotonic()
        reading=Reading('Known private caption',.95,'subtitle/rows',12,variant='contrast',
                        scans=(Scan('plain',.6,5),Scan('contrast',.95,7)))
        return OcrObservation(reading,fresh,1,now,now-.5)

    def test_mailbox_coalesces_to_two_roles_and_rejects_older_context(self):
        mailbox=DiagnosticMailbox()
        observation=self.observation()
        for index in range(10000):
            mailbox.post(DiagnosticUpdate(2,'hud' if index%2 else 'subtitle',index,observation))
        mailbox.post(DiagnosticUpdate(1,'hud',99999,observation))
        updates=mailbox.drain()
        self.assertEqual(len(updates),2)
        self.assertEqual({u.revision for u in updates},{9998,9999})
        self.assertEqual(mailbox.drain(),())
        with self.assertRaises(ValueError):mailbox.post(DiagnosticUpdate(1,'other',0,observation))
        for role in ('subtitle','hud'):
            mailbox.post(DiagnosticUpdate(2,role,3,observation))
            mailbox.post(DiagnosticUpdate(2,role,3,TranslationObservation(TranslationInfo('model',5,device='cpu'),time.monotonic())))
        self.assertEqual(len(mailbox.drain()),4)

    def test_real_capture_gate_reports_fresh_samples_not_each_pass_as_a_vote(self):
        observations=[]
        counts=dict(reads=0)
        stop=threading.Event()
        class Reader:
            def __init__(self,*args,**kwargs):counts['quality']=kwargs['quality']
            def read(self,frame):
                counts['reads']+=1
                return Reading('We need to leave.',.95,'test',2,scans=(Scan('plain',.7,1),Scan('contrast',.95,1)))
            def translate(self,text,*,can_infer):return 'Gitmeliyiz.'
        def observed(observation,revision):
            observations.append((observation,revision))
            if len(observations)==6:stop.set()
        def frames():
            while not stop.is_set():yield np.zeros((65,200,3),dtype=np.uint8)
        errors=[]
        run_capture(Path('.'),(0,0,200,65),stop,lambda *args:None,lambda _:None,errors.append,
                    frames=frames(),engine_factory=Reader,interval=.01,quality='accurate',diagnostics=observed)
        self.assertEqual(errors,[])
        self.assertEqual(counts,dict(reads=2,quality='accurate'))
        self.assertEqual([o.fresh for o,_ in observations],[True,True,False,False,False,False])
        self.assertEqual([o.sample for o,_ in observations],[1,2,2,2,2,2])
        self.assertTrue(all(o.last_read_at<=o.observed_at for o,_ in observations))
        self.assertEqual(observations[1][1],1)


class DiagnosticWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_display_preserves_unknowns_cache_age_and_drops_stopped_or_paused_observations(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Path('models'),settings=Settings(Path(folder)/'settings.json'))
            release=threading.Event()
            worker=threading.Thread(target=lambda:release.wait(5))
            worker.start()
            window.worker=worker
            try:
                observation=DiagnosticsTests().observation(fresh=False)
                update=DiagnosticUpdate(window.session,'subtitle',0,observation)
                window.received_observation(update)
                self.assertIn('önbellek',window.ocr_info.text())
                self.assertIn('2 geçiş',window.ocr_info.text())
                self.assertNotIn(observation.reading.text,window.ocr_info.text()+window.ocr_info.toolTip())
                translated=TranslationObservation(TranslationInfo('profile',2,profile_kind='exact',match_percent=100),time.monotonic())
                window.received_observation(DiagnosticUpdate(window.session,'subtitle',0,translated))
                self.assertIn('oyun profili',window.translation_info.text())
                self.assertIn('%100',window.translation_info.text())
                self.assertNotIn('%10000',window.translation_info.text())
                window.toggle_pause()
                window.received_observation(update)
                self.assertIn('duraklatıldı',window.ocr_info.text())
                window.toggle_pause()
                window.received_observation(update)
                self.assertIn('bekleniyor',window.ocr_info.text())
                now=time.monotonic()
                unknown=OcrObservation(Reading('Known caption',None,'unknown',3),True,2,now,now)
                window.received_observation(DiagnosticUpdate(window.session,'subtitle',window.control.snapshot()[1],unknown))
                self.assertIn('güven ?',window.ocr_info.text())
                self.assertIn('? geçiş',window.ocr_info.text())
                window.halt()
                window.received_observation(update)
                self.assertIn('kapalı',window.ocr_info.text())
            finally:
                release.set();worker.join(3);window.close()

    def test_quality_and_interval_restore_and_each_channel_receives_its_own_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            settings=Settings(Path(folder)/'settings.json')
            window=Window(Path('models'),settings=settings)
            window.ocr_quality.setCurrentIndex(window.ocr_quality.findData('accurate'))
            window.ocr_interval.setValue(.25)
            window.ignore_speaker.setChecked(False)
            window.close()
            window=Window(Path('models'),settings=Settings(settings.path))
            self.assertEqual(window.ocr_quality.currentData(),'accurate')
            self.assertEqual(window.ocr_interval.value(),.25)
            self.assertFalse(window.ignore_speaker.isChecked())
            window.chosen((50,500,600,65))
            window.chosen_hud((50,100,600,130))
            received=[]
            release=threading.Event()
            def capture(*args,**kwargs):
                received.append((kwargs.get('ocr_kind','subtitle'),kwargs.get('quality','fast'),kwargs['interval'],kwargs.get('ignore_speaker',True)))
                release.wait(3)
            try:
                with patch('main.capture_region',side_effect=lambda region,screens:region),patch('main.run_capture',side_effect=capture):
                    window.begin()
                    worker=window.worker
                    self.assertFalse(window.ocr_quality.isEnabled())
                    release.set()
                    worker.join(3)
                self.assertCountEqual(received,[('subtitle','accurate',.25,False),('hud','fast',.55,True)])
            finally:
                release.set()
                if window.worker:window.worker.join(3)
                window.close()
