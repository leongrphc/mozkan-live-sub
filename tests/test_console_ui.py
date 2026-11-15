import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from PySide6.QtCore import Qt,QEvent,QTimer
from PySide6.QtGui import QKeyEvent,QColor,QTextDocument
from PySide6.QtWidgets import QApplication,QLabel,QSpinBox,QPushButton,QColorDialog
from PySide6.QtTest import QTest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from main import Window
from settings import Settings
from console_ui import GameChoice
from catalog import CatalogEntry


class ConsoleWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.window=Window(ROOT/'models',settings=Settings(Path(self.folder.name)/'settings.json'))
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.folder.cleanup()

    def key(self,widget,key):
        self.app.sendEvent(widget,QKeyEvent(QEvent.KeyPress,key,Qt.NoModifier))
        self.app.processEvents()

    def test_small_home_uses_current_page_bounds_and_scrolls_keyboard_focus_into_view(self):
        w=self.window;ui=w.console
        w.resize(480,400)
        for _ in range(3):self.app.processEvents()
        self.assertEqual(w.centralWidget().horizontalScrollBar().maximum(),0)
        self.assertGreater(w.centralWidget().verticalScrollBar().maximum(),0)
        self.assertFalse(ui.home_pair._wide)
        ui.live_choice.setFocus()
        self.key(ui.live_choice,Qt.Key_Right)
        self.key(ui.games_choice,Qt.Key_Right)
        self.assertTrue(ui.movie_choice.hasFocus())
        viewport=w.centralWidget().viewport()
        center=ui.movie_choice.mapTo(viewport,ui.movie_choice.rect().center())
        self.assertTrue(viewport.rect().contains(center))
        self.key(ui.movie_choice,Qt.Key_Return)
        self.assertEqual(ui.page,'work')
        self.assertEqual(w.mode.currentData(),'movie')

    def test_game_art_uses_bundled_identity_and_grid_enter_opens_exact_profile(self):
        entry=CatalogEntry('imported:'+'a'*64,'Mafia <img src=data:,>',Path('mafia.svgame.sqlite'),'imported',True,'stored-import-metadata')
        choice=GameChoice.from_entry(entry)
        self.assertIsNone(choice.cover_key)
        tooltip=QTextDocument();tooltip.setHtml(choice.tooltip)
        self.assertEqual(tooltip.toPlainText(),entry.title)
        self.assertEqual(self.window.status.textFormat(),Qt.PlainText)
        ui=self.window.console
        ui.games_choice.click();ui.search.setText('Red Dead Redemption 2')
        selected=ui.game_list.currentItem()
        self.assertEqual(selected.data(Qt.UserRole),'bundled:rdr2.svgame.sqlite')
        self.assertEqual(selected.data(Qt.UserRole+1),'rdr2')
        delegate=ui.game_list.itemDelegate()
        cover=delegate.cover('rdr2')
        self.assertIsNotNone(cover)
        self.assertLessEqual(cover.width()*cover.height(),480*620)
        self.assertIsNone(delegate.cover('Mafia'))
        ui.game_list.setFocus()
        self.key(ui.game_list,Qt.Key_Return)
        self.assertEqual(ui.page,'work')
        self.assertEqual(self.window.profile.currentData(),'bundled:rdr2.svgame.sqlite')
        ui.home_button.click();ui.games_choice.click();ui.search.setText('Mafia')
        self.app.processEvents()
        rect=ui.game_list.visualItemRect(ui.game_list.currentItem())
        QTest.mouseClick(ui.game_list.viewport(),Qt.LeftButton,Qt.NoModifier,rect.center())
        self.assertEqual(ui.page,'work')
        self.assertEqual(self.window.profile.currentData(),'bundled:mafia.svgame.sqlite')

    def test_appearance_preview_applies_controls_immediately_and_close_keeps_values(self):
        w=self.window
        observed=[]
        def edit():
            dialog=self.app.activeModalWidget()
            try:
                font=dialog.findChild(QSpinBox,'appearanceFont')
                opacity=dialog.findChild(QSpinBox,'appearanceOpacity')
                sample=dialog.findChild(QLabel,'appearanceSample')
                font.setValue(40);opacity.setValue(20)
                observed.append(sample.font().pixelSize()==34 and 'rgba(3,7,15,51)' in sample.styleSheet())
                def color():
                    picker=self.app.activeModalWidget()
                    if isinstance(picker,QColorDialog):picker.setCurrentColor(QColor('#12abef'));picker.accept()
                    elif picker is not None:picker.reject()
                QTimer.singleShot(0,color)
                dialog.findChild(QPushButton,'appearanceColor').click()
                observed.append('#12abef' in sample.styleSheet())
                observed.append(w.font_size.value()==40 and w.settings.values['overlay_opacity']==20)
            except Exception as error:observed.append(f'{type(error).__name__}: {error}')
            finally:
                if dialog is not None:dialog.reject()
        QTimer.singleShot(0,edit)
        w.console.subtitle_settings.click()
        self.assertEqual(observed,[True,True,True])
        self.assertEqual(w.font_size.value(),40)
        self.assertEqual(w.overlay_style['color'],'#12abef')
        self.assertEqual(w.settings.values['overlay_opacity'],20)

    def test_appearance_dialog_cannot_enter_live_capture_when_exclusion_is_unknown(self):
        w=self.window;before=dict(w.overlay_style)
        with patch.object(w,'capture_active',return_value=True),patch('main.try_capture_exclusion',return_value=False):
            w.edit_appearance()
        self.assertIsNone(self.app.activeModalWidget())
        self.assertEqual(w.overlay_style,before)
        self.assertIn('yakalamadan dışlanamadı',w.status.text())

    def test_primary_action_stays_stop_until_capture_owner_retires(self):
        w=self.window;ui=w.console
        w.chosen((50,500,600,65));release=threading.Event()
        def pipeline(*args,**kwargs):release.wait(5)
        try:
            with patch('main.capture_region',side_effect=lambda rect,screens:rect),patch('main.run_capture',side_effect=pipeline):
                w.begin()
                self.assertIs(ui.primary_action.currentWidget(),w.stop)
                self.assertFalse(ui.subtitle_settings.isEnabled())
                w.halt();w.poll()
                self.assertIs(ui.primary_action.currentWidget(),w.stop)
                self.assertFalse(w.stop.isEnabled())
                release.set();w.worker.join(3);w.poll()
                self.assertIs(ui.primary_action.currentWidget(),w.start)
        finally:
            release.set()
            if w.worker:w.worker.join(3)
            w.close()

    def test_actual_choice_keys_profile_identity_and_plain_canvas(self):
        w=self.window
        ui=w.console
        self.assertEqual(ui.page,'home')
        ui.live_choice.setFocus()
        self.key(ui.live_choice,Qt.Key_Right)
        self.assertTrue(ui.games_choice.hasFocus())
        self.key(ui.live_choice,Qt.Key_Return)
        self.assertEqual(ui.page,'profiles')
        ui.dialogue_choice.click()
        self.assertEqual(ui.page,'work')
        self.assertEqual(w.caption_mode.currentData(),'dialogue')
        self.assertTrue(w.dialogue.isChecked())
        self.assertEqual(w.profile.currentData(),'')
        self.assertEqual(w.settings.values['caption_mode'],'dialogue')
        w.target.setPlainText('<b>Bilinen düz metin</b>')
        self.assertIs(ui.canvas.currentWidget(),w.target)
        self.assertEqual(w.target.toPlainText(),'<b>Bilinen düz metin</b>')
        self.key(w.target,Qt.Key_Escape)
        self.assertEqual(ui.page,'profiles')
        ui.single_choice.click()
        self.assertEqual(w.caption_mode.currentData(),'single')
        self.assertTrue(w.dialogue.isChecked())
        self.assertTrue(w.target.document().isEmpty())
        self.assertIs(ui.canvas.currentWidget(),ui.prompt)
        w.dialogue.setChecked(False)
        ui.home_button.click();ui.live_choice.click();ui.dialogue_choice.click()
        self.assertFalse(w.dialogue.isChecked())

    def test_game_search_uses_owner_identity_and_returns_to_games(self):
        w=self.window
        ui=w.console
        self.assertTrue(w._game_choices)
        choice=next(c for c in w._game_choices if c.available)
        w.open_source('dialogue')
        ui.home_button.click()
        ui.games_choice.click()
        self.assertEqual(ui.page,'games')
        ui.search.setText('no-such-generated-game-81234')
        self.assertFalse(ui.use_game.isEnabled())
        ui.activate_game()
        self.assertEqual(w.profile.currentData(),'')
        ui.search.clear()
        item=next(ui.game_list.item(i) for i in range(ui.game_list.count())
                  if ui.game_list.item(i).data(Qt.UserRole)==choice.identity)
        ui.game_list.setCurrentItem(item)
        self.key(ui.game_list,Qt.Key_Return)
        self.assertEqual(ui.page,'work')
        self.assertEqual(w.profile.currentData(),choice.identity)
        self.assertEqual(w.settings.values['profile'],choice.identity)
        self.assertEqual(w.mode.currentData(),'screen')
        self.assertFalse(w.stacked_mode())
        self.assertEqual(w.caption_mode.currentData(),'dialogue')
        self.assertFalse(w.caption_mode.isEnabled())
        self.key(ui,Qt.Key_Escape)
        self.assertEqual(ui.page,'games')
        before=w.profile.currentData()
        w.open_game('absent:profile')
        self.assertEqual(w.profile.currentData(),before)
        ui.home_button.click();ui.live_choice.click();ui.dialogue_choice.click()
        self.assertTrue(w.stacked_mode())

    def test_navigation_waits_for_capture_owner_and_blocks_late_source_change(self):
        w=self.window
        ui=w.console
        w.open_source('single')
        release=threading.Event()
        worker=threading.Thread(target=lambda:release.wait(5))
        worker.start()
        w.worker=worker
        old_session=w.session
        try:
            w.poll()
            ui.home_button.click()
            self.assertEqual(ui.page,'work')
            self.assertTrue(w.stop_event.is_set())
            self.assertGreater(w.session,old_session)
            self.assertEqual(w._navigation_pending,'home')
            w.open_source('movie')
            self.assertEqual(w.mode.currentData(),'screen')
            self.assertFalse(ui.home_button.isEnabled())
            release.set();worker.join(3)
            w.poll()
            self.assertEqual(ui.page,'home')
            self.assertIsNone(w.worker)
            self.assertIsNone(w._navigation_pending)
            ui.movie_choice.click()
            self.assertEqual(ui.page,'work')
            self.assertEqual(w.mode.currentData(),'movie')
            self.assertEqual(w.settings.values['mode'],'movie')
        finally:
            release.set();worker.join(3)

    def test_settings_dialog_reuses_controls_and_selection_hides_it(self):
        w=self.window
        ui=w.console
        ui.settings_button.click()
        self.app.processEvents()
        self.assertTrue(ui.preferences.isVisible())
        self.assertTrue(ui.preferences.isAncestorOf(w.profile))
        self.assertTrue(ui.preferences.isAncestorOf(w.ocr_quality))
        w.choose()
        self.assertFalse(ui.preferences.isVisible())
        self.assertEqual(ui.page,'work')
        self.assertIsNotNone(w.selector)
        ui.navigation_requested.emit('home')
        self.assertEqual(ui.page,'work')
        self.key(w.selector,Qt.Key_Escape)
        self.assertIsNone(w.selector)
        ui.settings_button.click()
        self.app.processEvents()
        self.assertTrue(ui.preferences.isVisible())
        w.close()
        self.assertFalse(ui.preferences.isVisible())
