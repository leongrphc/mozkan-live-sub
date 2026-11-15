import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import tempfile
import threading
import unittest
import json
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from main import QApplication,Window
from settings import Settings
from regions import CapturePlan
from video import resolve_selection


class FakeSelector(QObject):
    selected=Signal(tuple)
    finished=Signal()
    def __init__(self,parent=None):
        super().__init__(parent)
        self.closed=False
    def show(self):pass
    def raise_(self):pass
    def activateWindow(self):pass
    def close(self):
        if self.closed:return
        self.closed=True
        self.finished.emit()


class RegionWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/'settings.json'
        self.window=Window(Path('models'),settings=Settings(self.path))
        self.selector_patch=patch('main.Selector',FakeSelector)
        self.selector_patch.start()

    def tearDown(self):
        self.window.close()
        self.selector_patch.stop()
        self.app.processEvents()
        self.folder.cleanup()

    def test_subtitle_and_hud_restore_without_starting_capture_or_touching_file(self):
        self.assertTrue(self.window.chosen((50,500,600,65)))
        self.assertTrue(self.window.chosen_hud((50,100,600,130)))
        raw=self.path.read_bytes()
        self.window.close()
        self.window=Window(Path('models'),settings=Settings(self.path))
        self.assertEqual(self.window.region,(50,500,600,65))
        self.assertEqual(self.window.hud_region,(50,100,600,130))
        self.assertTrue(self.window.hud_enabled.isChecked())
        self.assertTrue(self.window.start.isEnabled())
        self.assertIsNone(self.window.worker)
        self.assertEqual(self.path.read_bytes(),raw)

    def test_full_video_selection_restores_once_and_uses_saved_band(self):
        self.window.mode.setCurrentIndex(self.window.mode.findData('movie'))
        self.window.selection_scope.setCurrentIndex(self.window.selection_scope.findData('video'))
        self.window.band.setValue(35)
        self.window.chosen((50,50,640,600))
        self.window.close()
        self.window=Window(Path('models'),settings=Settings(self.path))
        self.assertEqual(self.window.selection,(50,50,640,600))
        self.assertEqual(self.window.region,resolve_selection((50,50,640,600),'video',35))
        self.window.mode.setCurrentIndex(self.window.mode.findData('screen'))
        self.assertIsNone(self.window.region)
        self.assertTrue(self.window.start.isEnabled())
        self.window.start.click()
        self.assertIsNotNone(self.window.selector)
        self.assertIsNone(self.window.worker)
        self.window.selector.close()
        self.window.mode.setCurrentIndex(self.window.mode.findData('movie'))
        self.assertEqual(self.window.region,resolve_selection((50,50,640,600),'video',35))

    def test_replaced_selector_and_stop_reject_late_results(self):
        self.window.chosen((50,500,600,65))
        self.window.choose('hud')
        old=self.window.selector
        self.window.choose('subtitle')
        current=self.window.selector
        self.assertTrue(old.closed)
        old.selected.emit((50,100,600,130))
        self.assertIsNone(self.window.hud_region)
        self.assertIs(self.window.selector,current)
        self.window.halt()
        current.selected.emit((50,200,600,65))
        self.assertEqual(self.window.selection,(50,500,600,65))
        self.assertIsNone(self.window.selector)

    def test_start_waits_for_selection_then_accepts_only_current_role(self):
        self.window.chosen((50,500,600,65))
        self.window.choose('hud')
        selector=self.window.selector
        with patch('main.capture_region') as mapper:
            self.window.begin()
        mapper.assert_not_called()
        self.assertFalse(self.window.start.isEnabled())
        selector.selected.emit((50,100,600,130))
        self.assertEqual(self.window.hud_region,(50,100,600,130))
        self.assertEqual(self.window.selection,(50,500,600,65))
        self.assertTrue(self.window.start.isEnabled())

    def test_selection_snapshot_change_or_escape_rejects_pending_result(self):
        self.window.chosen((50,500,600,65))
        self.window.choose('hud')
        selector=self.window.selector
        with patch('main.desktop_signature',return_value=('changed topology',)):
            selector.selected.emit((50,100,600,130))
        self.assertIsNone(self.window.hud_region)
        self.window.choose('hud')
        selector=self.window.selector
        selector.close()
        selector.selected.emit((50,100,600,130))
        self.assertIsNone(self.window.hud_region)
        self.assertTrue(self.window.start.isEnabled())

    def test_mode_change_cancels_pending_selection_and_persists_even_before_start(self):
        self.window.chosen((50,500,600,65))
        self.window.choose('hud')
        selector=self.window.selector
        self.window.mode.setCurrentIndex(self.window.mode.findData('movie'))
        selector.selected.emit((50,100,600,130))
        self.assertIsNone(self.window.hud_region)
        self.assertIsNone(self.window.selector)
        self.window.close()
        self.window=Window(Path('models'),settings=Settings(self.path))
        self.assertEqual(self.window.mode.currentData(),'movie')
        self.assertEqual(self.window.region,(50,500,600,65))
        self.assertIsNone(self.window.worker)

    def test_running_capture_rejects_direct_and_queued_selection_and_mapping_change_stops_it(self):
        self.window.chosen((50,500,600,65))
        self.window.choose('hud')
        selector=self.window.selector
        release=threading.Event()
        worker=threading.Thread(target=lambda:release.wait(5))
        worker.start()
        self.window.worker=worker
        self.window._capture_plan=CapturePlan.create(self.window.region,None,QApplication.screens(),lambda region,screens:region)
        old_session=self.window.session
        try:
            self.assertFalse(self.window.chosen((50,300,600,65)))
            selector.selected.emit((50,100,600,130))
            self.assertIsNone(self.window.hud_region)
            self.window.target.setPlainText('old target')
            with patch('main.capture_region',return_value=(1,2,3,4)):
                self.assertFalse(self.window.validate_areas(native=True))
            self.assertTrue(self.window.stop_event.is_set())
            self.assertGreater(self.window.session,old_session)
            self.assertEqual(self.window.target.toPlainText(),'')
            self.assertIsNone(self.window.region)
            self.window.received(old_session,'old','old target')
            self.assertEqual(self.window.target.toPlainText(),'')
        finally:
            release.set()
            worker.join(3)

    def test_close_cancels_selection_and_does_not_open_pending_reselect(self):
        self.window.choose()
        selector=self.window.selector
        self.window.reselect_pending=True
        self.window.close()
        self.window.poll()
        self.app.processEvents()
        self.assertTrue(selector.closed)
        self.assertIsNone(self.window.selector)

    def test_save_failure_keeps_valid_current_choice_and_reports_unsaved_state(self):
        with patch.object(self.window.settings,'save',side_effect=OSError('test write failure')):
            self.assertTrue(self.window.chosen((50,500,600,65)))
        self.assertEqual(self.window.region,(50,500,600,65))
        self.assertIn('kaydedilemedi',self.window.status.text())
        self.assertFalse(self.path.exists())

    def test_changed_saved_monitor_blocks_only_affected_role_and_preserves_disk(self):
        self.window.chosen((50,500,600,65))
        self.window.chosen_hud((50,100,600,130))
        self.window.close()
        value=json.loads(self.path.read_text(encoding='utf-8'))
        value['regions']['subtitle']['monitor']['serial']='different-known-serial'
        raw=json.dumps(value).encode()
        self.path.write_bytes(raw)
        self.window=Window(Path('models'),settings=Settings(self.path))
        self.assertIsNone(self.window.region)
        self.assertEqual(self.window.hud_region,(50,100,600,130))
        self.assertTrue(self.window.start.isEnabled())
        self.assertIn('Kayıtlı altyazı',self.window.status.text())
        self.assertEqual(self.path.read_bytes(),raw)

    def test_close_retains_failed_signal_cleanup_and_retry_disconnects_remaining_owners(self):
        disconnect=self.window.disconnect_connections
        def fail_application_once(connections):
            if connections is self.window._application_connections:
                return False
            return disconnect(connections)
        with patch.object(self.window,'disconnect_connections',side_effect=fail_application_once):
            self.window.close()
        self.assertFalse(self.window.closing)
        self.assertFalse(self.window.source_change_allowed())
        self.assertTrue(self.window.timer.isActive())
        self.assertTrue(self.window._application_connections)
        self.assertFalse(self.window._screen_connections)
        self.window.close()
        self.assertFalse(self.window._application_connections)
        self.assertFalse(self.window._screen_connections)
        self.assertFalse(self.window.timer.isActive())

    def test_close_waits_for_worker_then_disconnects_observers_before_quit(self):
        release=threading.Event()
        worker=threading.Thread(target=lambda:release.wait(5))
        worker.start()
        self.window.worker=worker
        try:
            self.window.close()
            self.assertTrue(self.window.closing)
            self.assertTrue(self.window._application_connections)
            release.set()
            worker.join(3)
            self.window.poll()
            self.assertFalse(self.window._application_connections)
            self.assertFalse(self.window._screen_connections)
            self.assertFalse(self.window.timer.isActive())
        finally:
            release.set()
            worker.join(3)
