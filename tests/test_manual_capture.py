import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import json
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from main import Window
from settings import Settings
from manual_capture import CapturedImage,capture_image,save_image,save_json,MAX_CAPTURE_PIXELS
from diagnostics import DiagnosticUpdate,OcrObservation
from recognition import Reading


class ManualCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)
        self.window=Window(ROOT/'models',settings=Settings(self.path/'settings.json'))
        self.window.show();self.app.processEvents()
        image=QImage(192,32,QImage.Format_RGB888);image.fill(QColor('#26a2ed'))
        self.image=CapturedImage(image,(50,500,600,65),(50,500,600,65),time.monotonic())
        self.stack=ExitStack()
        self.capture=self.stack.enter_context(patch.object(self.window,'capture_image',return_value=self.image))
        self.stack.enter_context(patch('main.capture_region',side_effect=lambda rect,screens:rect))
        self.calls=[]
        def capture(*args,**kwargs):
            self.calls.append(args[1])
            args[2].wait(3)
        self.stack.enter_context(patch('main.run_capture',side_effect=capture))

    def tearDown(self):
        self.window.halt()
        if self.window.worker:self.window.worker.join(4)
        self.window.close();self.app.processEvents()
        self.stack.close();self.folder.cleanup()

    def until(self,predicate,timeout=2):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            self.app.processEvents()
            if predicate():return
            time.sleep(.005)
        self.fail('Owned UI transition did not complete')

    def test_start_without_area_selects_restores_and_starts_once(self):
        w=self.window
        w.open_source('single')
        w.start.click()
        self.assertIsNotNone(w.selector)
        self.assertFalse(w.isVisible())
        self.assertTrue(w.selector.isVisible())
        w.selector.selected.emit((50,500,600,65))
        self.assertIsNone(w.selector)
        self.until(lambda:len(self.calls)==1)
        self.assertEqual(self.calls,[(50,500,600,65)])
        self.capture.assert_called_once()

    def test_stop_and_new_source_cancel_queued_start_and_preview(self):
        w=self.window
        for action in (w.halt,lambda:w.open_source('movie'),w.console.show_preferences,w.export_diagnostics):
            w._areas.clear();w.region=None;w.poll()
            w.start.click()
            w.selector.selected.emit((50,500,600,65))
            with patch('main.QFileDialog.getSaveFileName',return_value=('','')):action()
            end=time.monotonic()+.16
            while time.monotonic()<end:self.app.processEvents();time.sleep(.005)
            self.assertIsNone(w.worker)
        self.capture.assert_not_called()
        self.assertEqual(self.calls,[])

    def test_escape_and_failed_selector_restore_owner_without_start(self):
        w=self.window
        w.start.click()
        w.selector.close()
        self.assertTrue(w.isVisible())
        self.assertIsNone(w.selector)
        self.assertIsNone(w.worker)
        with patch('main.Selector',side_effect=RuntimeError('known selector failure')):
            w.start.click()
        self.assertTrue(w.isVisible())
        self.assertIn('known selector failure',w.status.text())
        self.capture.assert_not_called()

    def test_preview_is_memory_only_and_new_geometry_clears_it(self):
        w=self.window
        w.chosen((50,500,600,65))
        before=set(self.path.iterdir())
        w.preview()
        self.assertFalse(w.console.canvas._preview.isNull())
        self.assertLessEqual(w.console.canvas._preview.width(),960)
        self.assertEqual(set(self.path.iterdir()),before)
        w.mode.setCurrentIndex(w.mode.findData('movie'))
        w.selection_scope.setCurrentIndex(w.selection_scope.findData('video'))
        self.assertTrue(w.console.canvas._preview.isNull())

    def test_manual_export_preserves_unknowns_and_text_requires_opt_in(self):
        w=self.window
        w.chosen((50,500,600,65));w.begin()
        now=time.monotonic()
        update=DiagnosticUpdate(w.session,'subtitle',0,OcrObservation(Reading('Known English',None,'known',4),True,1,now,now))
        w.received_observation(update)
        w.source.setPlainText('Known English');w.target.setPlainText('Bilinen Türkçe')
        destination=self.path/'tanılama.json'
        with patch('main.QFileDialog.getSaveFileName',return_value=(str(destination),'JSON')):w.export_diagnostics()
        data=json.loads(destination.read_text(encoding='utf-8'))
        self.assertNotIn('Known English',destination.read_text(encoding='utf-8'))
        self.assertFalse(data['includes_text'])
        self.assertIsNone(data['observations'][0]['confidence'])
        self.assertIsNone(data['observations'][0]['scans'])
        self.assertTrue(data['observations'][0]['current_context'])
        w.export_text.setChecked(True)
        with patch('main.QFileDialog.getSaveFileName',return_value=(str(destination),'JSON')):w.export_diagnostics()
        data=json.loads(destination.read_text(encoding='utf-8'))
        self.assertEqual(data['captions']['translation'],'Bilinen Türkçe')
        w.toggle_pause()
        self.assertEqual(w.diagnostic_snapshot()['observations'],[])

    def test_png_roundtrip_and_failed_json_commit_preserve_prior_file(self):
        image_path=self.path/'OCR görüntüsü.png'
        save_image(image_path,self.image)
        image=QImage(str(image_path))
        self.assertEqual(image.size(),self.image.image.size())
        self.assertEqual(image.pixelColor(0,0),QColor('#26a2ed'))
        destination=self.path/'existing.json';destination.write_bytes(b'original')
        before=set(self.path.iterdir())
        with patch('manual_capture.MAX_EXPORT_BYTES',8):
            with self.assertRaises(ValueError):save_json(destination,dict(text='too much text'))
        self.assertEqual(destination.read_bytes(),b'original')
        with patch('manual_capture.QSaveFile.commit',return_value=False):
            with self.assertRaises(OSError):save_json(destination,dict(ok=True))
        self.assertEqual(destination.read_bytes(),b'original')
        self.assertEqual(set(self.path.iterdir()),before)

    def test_image_capacity_rejected_before_desktop_acquisition(self):
        with patch('mss.mss') as native:
            with self.assertRaises(ValueError):capture_image((0,0,1,1),(0,0,MAX_CAPTURE_PIXELS+1,1))
        native.assert_not_called()
