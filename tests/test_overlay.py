import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QFont, QImage, QFontDatabase
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from overlay import Overlay


class Screen:
    def __init__(self, area=QRect(0, 0, 1280, 720), ratio=1):
        self.area, self.ratio = area, ratio

    def geometry(self):
        return self.area

    def availableGeometry(self):
        return self.area

    def devicePixelRatio(self):
        return self.ratio


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/segoeui.ttf'
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))

    def setUp(self):
        self.overlay = Overlay()
        self.screen = Screen()
        self.monitor = patch.object(self.overlay, '_screen_for_region', return_value=self.screen)
        self.monitor.start()
        self.exclusion = patch('overlay.try_capture_exclusion', return_value=False)
        self.native_exclusion=self.exclusion.start()

    def tearDown(self):
        self.overlay.close()
        self.exclusion.stop()
        self.monitor.stop()

    def pixels(self):
        self.app.processEvents()
        image = self.overlay.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
        return np.frombuffer(bytes(image.bits()), dtype=np.uint8).reshape(
            image.height(), image.bytesPerLine() // 4, 4)[:, :image.width(), :]

    def test_auto_uses_region_monitor_and_stays_outside_capture(self):
        self.screen.area = QRect(-1920, 0, 1920, 1080)
        source = (-1800, 800, 900, 65)
        self.assertTrue(self.overlay.present('Merhaba dünya', source))
        self.assertTrue(self.screen.area.contains(self.overlay.geometry()))
        self.assertFalse(self.overlay.geometry().intersects(QRect(*source)))
        self.assertEqual(self.overlay.actual_position, 'above_region')

    def test_failed_exclusion_uses_safe_fallback_instead_of_reading_itself(self):
        self.overlay.configure(position='top')
        source = (0, 0, 1280, 200)
        self.assertTrue(self.overlay.present('Altyazı', source))
        self.assertFalse(self.overlay.geometry().intersects(QRect(*source)))
        self.assertEqual(self.overlay.actual_position, 'below_region')

    def test_no_safe_placement_returns_false_and_hides_previous_text(self):
        self.assertTrue(self.overlay.present('İlk metin', (100, 500, 800, 65)))
        self.assertFalse(self.overlay.present('Yeni metin', (0, 0, 1280, 720)))
        self.assertFalse(self.overlay.isVisible())
        self.assertIsNotNone(self.overlay.last_error)

    def test_confirmed_capture_exclusion_allows_screen_position_overlap(self):
        self.exclusion.stop()
        self.exclusion = patch('overlay.try_capture_exclusion', return_value=True)
        self.native_exclusion=self.exclusion.start()
        self.overlay.configure(position='top')
        source = (0, 0, 1280, 720)
        self.assertTrue(self.overlay.present('Altyazı', source))
        self.assertTrue(self.overlay.geometry().intersects(QRect(*source)))
        self.assertTrue(self.overlay.capture_excluded)

    def test_above_region_does_not_move_offscreen(self):
        self.overlay.configure(position='above_region')
        self.assertFalse(self.overlay.present('Altyazı', (100, 5, 900, 60)))
        self.assertFalse(self.overlay.isVisible())

    def test_background_opacity_does_not_make_text_transparent(self):
        self.overlay.configure(opacity=0, stroke=0)
        self.assertTrue(self.overlay.present('OPAQUE TEXT', (100, 500, 900, 65)))
        transparent = self.pixels()
        self.assertEqual(int(transparent[3, transparent.shape[1] // 2, 3]), 0)
        self.assertGreater(np.count_nonzero(transparent[:, :, 3] == 255), 20)
        self.overlay.configure(opacity=100)
        opaque = self.pixels()
        self.assertEqual(int(opaque[3, opaque.shape[1] // 2, 3]), 255)

    def test_outline_and_rich_speaker_colors_are_preserved(self):
        self.overlay.configure(color='#ff0000', opacity=0, stroke=0)
        text = '<span style="color:#00ff00">John:</span> Hello'
        self.assertTrue(self.overlay.present(text, (100, 500, 900, 65), rich=True))
        no_outline = self.pixels()
        red = (no_outline[:, :, 0] > 180) & (no_outline[:, :, 1] < 70) & (no_outline[:, :, 3] > 200)
        green = (no_outline[:, :, 1] > 180) & (no_outline[:, :, 0] < 70) & (no_outline[:, :, 3] > 200)
        self.assertGreater(np.count_nonzero(red), 10)
        self.assertGreater(np.count_nonzero(green), 10)
        for stroke in (1,2,5):
            with self.subTest(stroke=stroke):
                self.overlay.configure(stroke=stroke)
                outlined = self.pixels()
                dark = (outlined[:, :, :3].max(axis=2) < 30) & (outlined[:, :, 3] > 200)
                red = (outlined[:,:,0]>180)&(outlined[:,:,1]<70)&(outlined[:,:,3]>200)
                green = (outlined[:,:,1]>180)&(outlined[:,:,0]<70)&(outlined[:,:,3]>200)
                self.assertGreater(np.count_nonzero(dark),50)
                self.assertGreater(np.count_nonzero(red),10)
                self.assertGreater(np.count_nonzero(green),10)

    def test_long_text_wraps_without_truncation_or_unsafe_allocation(self):
        self.overlay.setFont(QFont('Segoe UI', 20))
        self.assertTrue(self.overlay.present('Bu cümle ekranda satırlara bölünerek gösterilir. ' * 4,
                                             (100, 500, 800, 65)))
        self.assertTrue(self.screen.area.contains(self.overlay.geometry()))
        self.assertFalse(self.overlay.present('uzun metin ' * 400, (100, 500, 800, 65)))
        self.assertIsNotNone(self.overlay.last_error)
        self.assertFalse(self.overlay.present('x' * (Overlay.MAX_TEXT_CHARACTERS + 1), (100, 500, 800, 65)))

    def test_pixel_expansion_is_checked_before_native_window_preparation(self):
        self.screen.ratio = 10
        native = self.native_exclusion
        self.assertFalse(self.overlay.present('Altyazı', (100, 500, 900, 65)))
        native.assert_not_called()
        self.assertIn('bellek', self.overlay.last_error)

    def test_partial_configuration_keeps_position_and_invalid_changes_are_atomic(self):
        self.overlay.configure(position='bottom', opacity=0, stroke=0)
        self.assertTrue(self.overlay.present('Altyazı', (100, 200, 900, 65)))
        bottom = self.overlay.geometry().top()
        self.overlay.configure(color='#33aaff')
        self.assertEqual(self.overlay.actual_position, 'bottom')
        self.assertEqual(self.overlay.geometry().top(), bottom)
        with self.assertRaises(ValueError):
            self.overlay.configure(position='top', opacity=101)
        self.assertTrue(self.overlay.present('Altyazı', (100, 200, 900, 65)))
        self.assertEqual(self.overlay.actual_position, 'bottom')
        self.overlay.configure(enabled=False)
        self.assertFalse(self.overlay.isVisible())
        self.assertFalse(self.overlay.present('Altyazı', (100, 200, 900, 65)))

    def test_vertical_offset_is_bounded_and_applied(self):
        self.overlay.configure(position='above_region', stroke=0)
        self.assertTrue(self.overlay.present('Altyazı', (100, 500, 900, 65)))
        top = self.overlay.geometry().top()
        self.overlay.configure(y_offset=2)
        self.assertEqual(self.overlay.geometry().top(), top - 20)
        self.overlay.configure(y_offset=-.5)
        self.assertEqual(self.overlay.geometry().top(), top + 5)
        self.overlay.configure(y_offset=-2.3)
        self.assertFalse(self.overlay.isVisible())
        for invalid in (-41, 41, True):
            with self.assertRaises(ValueError):
                self.overlay.configure(y_offset=invalid)

    def test_nonzero_offset_clamps_at_screen_edges_and_still_avoids_capture(self):
        self.screen.area=QRect(-1280,-720,1280,720)
        self.overlay.configure(position='top',y_offset=40)
        source=(-1100,-200,700,60)
        self.assertTrue(self.overlay.present('Altyazı',source))
        self.assertEqual(self.overlay.geometry().top(),-712)
        self.overlay.configure(position='bottom',y_offset=-40)
        self.assertEqual(self.overlay.geometry().bottom(),-9)
        self.assertFalse(self.overlay.geometry().intersects(QRect(*source)))
