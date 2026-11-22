import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import threading
import unittest
import tempfile
from unittest.mock import patch, Mock
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from main import QApplication, Window
from settings import Settings
from tv import TVInfo


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.defaults=tempfile.TemporaryDirectory()
        self.default_settings=patch('main.Settings',side_effect=lambda:Settings(Path(self.defaults.name)/'settings.json'))
        self.default_settings.start()

    def tearDown(self):
        self.default_settings.stop()
        self.defaults.cleanup()

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_imported_profile_selection_survives_source_removal_and_restart(self):
        from test_catalog import profile_file
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'selected.sqlite'
            profile_file(source, title='Imported game')
            settings = Settings(root/'data/settings.json')
            window = Window(root/'bundle/models', settings=settings)
            with patch('main.QFileDialog.getOpenFileName', return_value=(str(source),'')):
                window.open_profile()
            window.import_worker.join(5)
            self.app.processEvents()
            self.assertFalse(window.import_busy)
            identity = window.profile.currentData()
            self.assertTrue(identity.startswith('imported:'))
            source.unlink()
            self.assertTrue(window.catalog.resolve(identity).exists())
            window.close()
            restored = Window(root/'moved-bundle/models', settings=Settings(settings.path))
            self.assertEqual(restored.profile.currentData(), identity)
            self.assertTrue(restored.catalog.resolve(identity).exists())
            restored.close()

    def test_legacy_previous_option_restores_dialogue_mode_and_movie_keeps_choice(self):
        with tempfile.TemporaryDirectory() as folder:
            settings=Settings(Path(folder)/'settings.json')
            settings.save(dialogue=True)
            window=Window(Path('models'),settings=settings)
            self.assertEqual(window.caption_mode.currentData(),'dialogue')
            self.assertTrue(window.dialogue.isChecked())
            window.mode.setCurrentIndex(window.mode.findData('movie'))
            self.assertFalse(window.stacked_mode())
            self.assertFalse(window.caption_mode.isEnabled())
            self.assertEqual(window.caption_mode.currentData(),'dialogue')
            window.mode.setCurrentIndex(window.mode.findData('screen'))
            self.assertTrue(window.stacked_mode())
            window.caption_mode.setCurrentIndex(window.caption_mode.findData('single'))
            self.assertFalse(window.dialogue.isEnabled())
            window.close()
            restored=Window(Path('models'),settings=Settings(settings.path))
            self.assertEqual(restored.caption_mode.currentData(),'single')
            self.assertTrue(restored.dialogue.isChecked())
            restored.close()

    def test_hud_layout_preferences_restore_and_ui_never_exposes_internal_marks_or_html(self):
        with tempfile.TemporaryDirectory() as folder:
            settings=Settings(Path(folder)/'settings.json')
            window=Window(Path('models'),settings=settings)
            window.hud_layout=dict(x_offset=2,y_offset=-1,scale=130)
            window.hud_overlay.configure_layout(**window.hud_layout)
            window.appearance_changed()
            window.received_hud(window.session,'Hold RB','Bas {{RB}} <img src=file:///secret>')
            self.assertNotIn('{{RB}}',window.hud_text.text())
            self.assertIn('RB',window.hud_text.text())
            self.assertIn('&lt;img',window.hud_text.toolTip())
            window.close()
            restored=Window(Path('models'),settings=Settings(settings.path))
            self.assertEqual(restored.hud_layout,dict(x_offset=2,y_offset=-1,scale=130))
            self.assertEqual(restored.hud_overlay.hud_layout,restored.hud_layout)
            restored.close()

    def test_oversized_translation_reports_capacity_without_stale_overlay(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Path('models'),settings=Settings(Path(folder)/'settings.json'))
            window.tv=Mock(connection_info=lambda:None)
            window.received(window.session,'PRICE: Wait.','x'*8193)
            self.assertEqual(window.target.toPlainText(),'')
            self.assertEqual(window.captions.current.body,'')
            self.assertIn('8192',window.status.text())
            window.tv.publish.assert_called_with('')
            self.assertFalse(window.overlay.isVisible())
            window.tv=None
            window.close()

    def test_disappearing_tv_address_keeps_explicit_selection_and_does_not_copy_another(self):
        from PySide6.QtNetwork import QNetworkInterface,QHostAddress
        from PySide6.QtCore import Qt
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Path('models'),settings=Settings(Path(folder)/'settings.json'))
            info=TVInfo('0.0.0.0',8766,8765,0)
            entry=Mock(ip=lambda:QHostAddress('192.168.1.20'))
            interface=Mock(flags=lambda:QNetworkInterface.IsUp|QNetworkInterface.IsRunning,
                           addressEntries=lambda:[entry])
            with patch.object(QNetworkInterface,'allInterfaces',return_value=[interface]):
                window.update_tv_addresses(info)
            self.assertEqual(window.tv_urls.currentData(),'http://192.168.1.20:8766')
            window.tv=Mock(connection_info=lambda:info)
            with patch.object(QNetworkInterface,'allInterfaces',return_value=[]),patch('main.QApplication.clipboard') as clipboard:
                window.copy_tv_address()
                clipboard.assert_not_called()
                self.assertEqual(window.tv_urls.currentData(),'http://192.168.1.20:8766')
                self.assertFalse(window.tv_urls.currentData(Qt.UserRole+1))
                self.assertIn('artık etkin değil',window.status.text())
            window.tv=None
            window.close()

    def test_invalid_hud_monitor_clears_tv_placement_and_reports_why(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Path('models'),settings=Settings(Path(folder)/'settings.json'))
            window.chosen_hud((100,100,200,50))
            release=threading.Event()
            worker=threading.Thread(target=lambda:release.wait(5))
            window.worker=worker
            worker.start()
            window.tv=Mock(connection_info=lambda:None)
            try:
                with patch('main.normalized_region',side_effect=ValueError('Monitör artık bulunamıyor')):
                    window.received_hud(window.session,'Find key','Anahtarı bul')
                window.tv.publish_hud.assert_called_with('')
                self.assertIn('TV görev alanı gönderilemedi',window.status.text())
            finally:
                release.set();worker.join(3)
                window.tv=None
                window.close()

    def test_appearance_persists_and_pc_toggle_does_not_stop_tv(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(Path(folder)/'settings.json')
            window = Window(Path('models'),settings=settings)
            service = Mock(connection_info=lambda:None)
            window.tv = service
            window.overlay_style.update(position='top',color='#12abcd',opacity=30,stroke=4,enabled=False,y_offset=10)
            window.overlay.configure(**window.overlay_style)
            window.font_size.setValue(60)
            self.assertIs(window.tv,service)
            self.assertFalse(window.overlay.isVisible())
            loaded = Settings(settings.path)
            self.assertEqual(loaded.values['font_size'],60)
            self.assertEqual(loaded.values['overlay_color'],'#12abcd')
            self.assertFalse(loaded.values['overlay_enabled'])
            window.tv = None
            window.close()

    def test_render_toggle_restores_current_hud_and_stop_cannot_resurrect_text(self):
        with tempfile.TemporaryDirectory() as folder:
            window = Window(Path('models'),settings=Settings(Path(folder)/'settings.json'))
            screen = self.app.primaryScreen().availableGeometry()
            window.chosen((screen.x()+100,screen.y()+400,600,80))
            window.chosen_hud((screen.x()+100,screen.y()+180,200,50))
            release = threading.Event()
            worker = threading.Thread(target=lambda:release.wait(5))
            window.worker = worker
            worker.start()
            try:
                window.received(window.session,'Hello','Merhaba')
                window.received_hud(window.session,'Find key','Anahtarı bul')
                self.assertTrue(window.overlay.isVisible())
                self.assertTrue(window.hud_overlay.isVisible())
                window.overlay.configure(enabled=False)
                window.hud_overlay.configure(enabled=False)
                window.refresh_overlay()
                self.assertFalse(window.overlay.isVisible())
                self.assertFalse(window.hud_overlay.isVisible())
                window.overlay.configure(enabled=True)
                window.hud_overlay.configure(enabled=True)
                window.refresh_overlay()
                self.assertTrue(window.overlay.isVisible())
                self.assertTrue(window.hud_overlay.isVisible())
                window.halt()
                window.appearance_changed()
                self.assertFalse(window.overlay.isVisible())
                self.assertFalse(window.hud_overlay.isVisible())
            finally:
                release.set();worker.join(3);window.close()

    def test_missing_profile_does_not_fall_back_to_live_translation(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(Path(folder)/'settings.json')
            settings.save(profile='bundled:missing.sqlite',mode='screen')
            window = Window(Path(folder)/'models',settings=settings)
            window.chosen((100,100,500,80))
            with patch('main.capture_region',side_effect=lambda region,screens:region):
                window.begin()
            self.assertIsNone(window.worker)
            self.assertEqual(window.profile.currentData(),'bundled:missing.sqlite')
            self.assertIn('Seçili profil kullanılamıyor',window.status.text())
            window.close()

    def test_reselect_waits_until_previous_worker_finishes(self):
        window = Window(Path('models'))
        release = threading.Event()
        worker = threading.Thread(target=lambda: release.wait(5))
        worker.start()
        window.worker = worker
        chosen = []
        window.choose = lambda: chosen.append(True)
        try:
            window.reselect()
            window.poll()
            self.app.processEvents()
            self.assertTrue(window.reselect_pending)
            self.assertEqual(chosen, [])
            release.set()
            worker.join(3)
            window.poll()
            self.app.processEvents()
            self.assertEqual(chosen, [True])
            self.assertIsNone(window.worker)
        finally:
            release.set()
            worker.join(3)
            window.close()

    def test_queued_translation_before_pause_cannot_reappear_after_resume(self):
        window = Window(Path('models'))
        window.chosen((100, 100, 900, 65))
        old_revision = window.control.snapshot()[1]
        window.control.pause(True)
        window.control.pause(False)
        window.received(window.session, 'old source', 'old translation', old_revision)
        self.assertEqual(window.target.toPlainText(), '')
        window.close()

    def test_queued_status_cannot_override_pause_or_stopped_session(self):
        window = Window(Path('models'))
        old_revision = window.control.snapshot()[1]
        worker = threading.Thread(target=lambda: window.events.capture_message.emit(
            window.session, old_revision, 'Çeviri açık.', False))
        worker.start(); worker.join()
        window.control.pause(True)
        window.status.setText('Duraklatıldı')
        self.app.processEvents()
        self.assertEqual(window.status.text(), 'Duraklatıldı')
        previous_session = window.session
        window.halt()
        window.capture_message(previous_session, old_revision, 'Old failure', True)
        self.assertEqual(window.status.text(), 'Çeviri kapalı.')
        window.close()

    def test_failed_start_retains_cleanup_owner_until_retry_succeeds(self):
        class FailingService:
            calls = 0
            def connection_info(self):return None
            def start(self):
                raise OSError('start failed with owned resource')
            def close(self):
                self.calls += 1
                if self.calls == 1:
                    raise OSError('cleanup failed')
        service = FailingService()
        window = Window(Path('models'))
        try:
            with patch('tv_panel.TV', return_value=service):
                window.toggle_tv()
            window.tv_cleanup.join(3)
            self.app.processEvents()
            self.assertIs(window.tv, service)
            self.assertIsNotNone(window.tv_stop_error)
            window.poll()
            self.assertFalse(window.tv_urls.isEnabled())
            self.assertTrue(window.tv_button.isEnabled())
            window.stop_tv()
            window.tv_cleanup.join(3)
            self.app.processEvents()
            self.assertIsNone(window.tv)
        finally:
            if window.tv is not None:window.stop_tv()
            if window.tv_cleanup:window.tv_cleanup.join(3)
            self.app.processEvents()
            window.close()


class HotkeyWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_hotkeys_persist_mirror_buttons_and_hide_only_pc_overlay(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(Path(folder)/'settings.json')
            window = Window(Path(folder)/'models', settings=settings)
            try:
                # Offscreen platform: nothing is registered with Windows.
                self.assertIsNone(window.hotkeys)
                window.hotkey_edits['pause'].setKeySequence('Ctrl+Shift+F9')
                window.hotkeys_changed()
                self.assertEqual(Settings(Path(folder)/'settings.json').values['hotkey_pause'], 'Ctrl+Shift+F9')
                window.hotkey_edits['pause'].setKeySequence('Ctrl+Space')
                window.hotkeys_changed()
                self.assertIn('Desteklenmeyen', window.hotkey_info.text())
                self.assertEqual(Settings(Path(folder)/'settings.json').values['hotkey_pause'], 'Ctrl+Shift+F9')
                with patch.object(window, 'halt') as halt, patch.object(window, 'request_start') as start:
                    window.hotkey_pressed('toggle')  # idle and not on work page: nothing
                    halt.assert_not_called()
                    start.assert_not_called()
                window.hotkey_pressed('overlay')
                self.assertTrue(window.overlay_suppressed)
                self.assertFalse(window.overlay.isVisible())
                window.hotkey_pressed('overlay')
                self.assertFalse(window.overlay_suppressed)
            finally:
                window.close()


class DictionaryWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_correction_dialog_saves_body_and_dictionary_dialog_manages_terms(self):
        from PySide6.QtWidgets import QDialog, QPlainTextEdit
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(Path(folder)/'settings.json')
            window = Window(Path(folder)/'models', settings=settings)
            try:
                self.assertFalse(window.console.correct.isEnabled())
                window.received(window.session, 'Arthur: Get to the horse.', 'Arthur: Ata git.')
                window.poll()
                self.assertTrue(window.console.correct.isEnabled())
                def accept(dialog):
                    english, turkish = dialog.findChildren(QPlainTextEdit)
                    self.assertEqual(english.toPlainText(), 'Get to the horse.')
                    self.assertEqual(turkish.toPlainText(), 'Ata git.')
                    turkish.setPlainText('Ata bin.')
                    return QDialog.Accepted
                with patch.object(window, 'exec_capture_safe_dialog', side_effect=accept):
                    window.edit_correction()
                self.assertEqual(window.dictionary.corrections(), [('Get to the horse.', 'Ata bin.')])
                self.assertEqual(window.dictionary.snapshot().correction('Arthur: get to the horse'), 'Arthur: Ata bin.')
                def manage(dialog):
                    ui = window.dictionary_dialog
                    self.assertEqual(ui['corrections'].rowCount(), 1)
                    ui['term_source'].setText('bounty'); ui['term_target'].setText('ödül'); ui['add'].click()
                    ui['term_source'].setText(''); ui['add'].click()
                    self.assertIn('Kaydedilemedi', ui['info'].text())
                    self.assertEqual(ui['terms'].rowCount(), 1)
                    ui['corrections'].selectRow(0); ui['remove_correction'].click()
                    self.assertEqual(ui['corrections'].rowCount(), 0)
                    return QDialog.Rejected
                with patch.object(window, 'exec_capture_safe_dialog', side_effect=manage):
                    window.edit_dictionary()
                self.assertEqual(window.dictionary.terms(), [('bounty', 'ödül')])
                self.assertEqual(window.dictionary.corrections(), [])
                self.assertIsNone(window.dictionary_dialog)
            finally:
                window.close()
