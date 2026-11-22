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
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QLabel,QDialog
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from capture import run_capture
from startup import CaptureProgress,ChildStop,CaptureFailure
from main import Window
from settings import Settings
from app_log import AppLog


class StartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def until(self,predicate,timeout=3):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            self.app.processEvents()
            if predicate():return
            time.sleep(.005)
        self.fail('Startup transition did not complete')

    def test_resource_ready_is_not_capture_permission_and_stop_cancels_handoff(self):
        stop=threading.Event();gate=threading.Event();ready=threading.Event()
        calls=[];progress=[];errors=[]
        class Reader:
            def __init__(self,*args,**kwargs):calls.append('ocr')
            def prepare_translation(self):calls.append('model')
        def lazy_frames():
            calls.append('grab')
            yield np.zeros((30,100,3),dtype=np.uint8)
        def stages(value):
            progress.append(value)
            if value.component=='capture':ready.set()
        worker=threading.Thread(target=run_capture,kwargs=dict(models=ROOT/'models',region=(0,0,100,30),stop=stop,
            output=lambda *args:None,status=lambda _:None,error=errors.append,engine_factory=Reader,
            frames=lazy_frames(),prepare_model=True,progress=stages,launch_gate=gate))
        worker.start()
        try:
            self.assertTrue(ready.wait(2))
            self.assertEqual(calls,['ocr','model'])
            stop.set();worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertNotIn('grab',calls)
            self.assertEqual(errors,[])
            self.assertIn(CaptureProgress('translation','ready'),progress)
        finally:stop.set();gate.set();worker.join(2)

    def test_window_acknowledges_real_pipeline_readiness_and_logs_only_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            log=AppLog(root/'logs','test','3.11')
            window=Window(ROOT/'models',settings=Settings(root/'settings.json'),event_log=log)
            window.show();window.chosen((50,500,600,65))
            release=threading.Event();frames_started=threading.Event()
            class Reader:
                def __init__(self,*args,**kwargs):pass
                def prepare_translation(self):release.wait(2)
                def read(self,frame):raise RuntimeError('Known private subtitle text')
            from capture import run_capture as actual
            def pipeline(*args,**kwargs):
                def frames():
                    frames_started.set()
                    yield np.zeros((65,600,3),dtype=np.uint8)
                return actual(*args,**kwargs,frames=frames(),engine_factory=Reader)
            try:
                with patch('main.capture_region',side_effect=lambda rect,screens:rect),patch('main.run_capture',side_effect=pipeline):
                    window.begin()
                    self.until(lambda:window.startup.components.get('translation')=='loading')
                    self.assertFalse(window.isMinimized())
                    self.assertFalse(frames_started.is_set())
                    self.assertFalse(window.console.preparation.isHidden())
                    self.assertEqual(window.console.phase.text(),'Hazırlanıyor')
                    self.assertFalse(window.console.settings_button.isEnabled())
                    self.assertFalse(window.console.subtitle_settings.isEnabled())
                    with patch.object(QDialog,'exec',return_value=QDialog.Accepted) as execute:
                        window.edit_appearance()
                    execute.assert_not_called()
                    self.assertFalse(window.isMinimized())
                    release.set()
                    self.until(frames_started.is_set)
                    self.until(lambda:window.worker is None)
                contents=log.path.read_text(encoding='utf-8')
                self.assertIn('RuntimeError',contents)
                self.assertNotIn('Known private subtitle text',contents)
                self.assertTrue(window.isMinimized())
                self.assertTrue(window.diagnostic_snapshot()['capture_error_present'])
                self.assertNotIn('capture_error_text',window.diagnostic_snapshot())
                self.assertEqual(window.diagnostic_snapshot(include_text=True)['capture_error_text'],'Known private subtitle text')
            finally:
                release.set();window.halt()
                if window.worker:window.worker.join(3)
                window.close()

    def test_late_ready_from_retired_session_cannot_minimize_or_release(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(ROOT/'models',settings=Settings(Path(folder)/'settings.json'))
            window.show();window.chosen((50,500,600,65))
            release=threading.Event()
            def pipeline(*args,**kwargs):release.wait(2)
            try:
                with patch('main.capture_region',side_effect=lambda rect,screens:rect),patch('main.run_capture',side_effect=pipeline):
                    window.begin()
                    old=window.startup;session=window.session
                    window.halt()
                    window.capture_progress(session,CaptureProgress('capture','ready'))
                    window.finish_launch(session)
                    self.assertFalse(old.gate.is_set())
                    self.assertFalse(window.isMinimized())
                    release.set();window.worker.join(3);window.poll()
            finally:
                release.set()
                if window.worker:window.worker.join(3)
                window.close()

    def test_log_cleanup_failure_keeps_window_owned_and_blocks_capture_until_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            log=AppLog(Path(folder)/'logs','test','python')
            window=Window(ROOT/'models',settings=Settings(Path(folder)/'settings.json'),event_log=log)
            window.show()
            stream=log.stream
            class Failing:
                closed=False
                def close(self):raise OSError('known close failure')
                def write(self,data):return stream.write(data)
            failing=Failing();log.stream=failing
            try:
                self.assertFalse(window.close())
                self.assertIs(log.stream,failing)
                self.assertTrue(window.isVisible())
                self.assertFalse(window.source_change_allowed())
                snapshot=window.diagnostic_snapshot()['application_log']
                self.assertTrue(snapshot['stream_owned'])
                self.assertTrue(snapshot['error_present'])
                log.stream=stream
                self.assertTrue(window.close())
                self.assertIsNone(log.stream)
            finally:
                log.stream=stream if not stream.closed else None
                window.close()

    def test_queued_terminal_failure_is_recorded_before_close_releases_log(self):
        with tempfile.TemporaryDirectory() as folder:
            log=AppLog(Path(folder)/'logs','test','python')
            window=Window(ROOT/'models',settings=Settings(Path(folder)/'settings.json'),event_log=log)
            worker=threading.Thread(target=lambda:window.events.failure.emit(window.session,'subtitle',CaptureFailure('RuntimeError','private text')))
            worker.start();worker.join(2)
            window.close()
            self.assertIsNone(log.stream)
            contents=log.path.read_text(encoding='utf-8')
            self.assertIn('RuntimeError',contents)
            self.assertNotIn('private text',contents)

    def test_optional_hud_failure_does_not_cancel_primary_and_parent_stop_joins_both(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(ROOT/'models',settings=Settings(Path(folder)/'settings.json'))
            parent=threading.Event();child=ChildStop(parent)
            primary_running=threading.Event();hud_failed=threading.Event()
            def pipeline(*args,**kwargs):
                if kwargs.get('ocr_kind')=='hud':
                    try:kwargs['failure'](CaptureFailure('RuntimeError','known HUD failure'))
                    finally:kwargs['stop'].set();hud_failed.set()
                else:
                    primary_running.set()
                    args[2].wait(3)
            worker=threading.Thread(target=window.run,args=(window.session,(0,0,100,30),parent),
                kwargs=dict(hud_region=(0,40,100,30),hud_stop=child))
            try:
                with patch('main.run_capture',side_effect=pipeline):
                    worker.start()
                    self.assertTrue(primary_running.wait(2))
                    self.assertTrue(hud_failed.wait(2))
                    self.app.processEvents()
                    self.assertTrue(child.is_set())
                    self.assertFalse(parent.is_set())
                    self.assertTrue(worker.is_alive())
                    self.assertIn('ana altyazı devam ediyor',window.hud_text.text())
                    parent.set();worker.join(2)
                    self.assertFalse(worker.is_alive())
            finally:parent.set();worker.join(3);window.close()

    def test_about_button_opens_owned_plain_text_dialog_and_returns(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(ROOT/'models',settings=Settings(Path(folder)/'settings.json'))
            window.show()
            observed=[]
            def close_dialog():
                dialog=self.app.activeModalWidget()
                observed.append(dialog.windowTitle() if dialog else '')
                if dialog:
                    observed.extend(label.text() for label in dialog.findChildren(QLabel))
                    dialog.reject()
            try:
                QTimer.singleShot(30,close_dialog)
                window.console.about_button.click()
                self.assertIn('MOZKAN Live Sub hakkında',observed)
                self.assertTrue(any('lisans sunucusu' in text for text in observed))
            finally:window.close()
