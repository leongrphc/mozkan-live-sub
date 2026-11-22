import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from main import QApplication, Window
from settings import Settings
from history import TranslationHistory, HistoryWindow


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_bounded_deduplicated_and_clearable(self):
        history = TranslationHistory(limit=3)
        at = datetime(2026, 1, 1, 12, 0, 5)
        self.assertFalse(history.add('', 'x', now=at))
        for index in range(5):
            self.assertTrue(history.add(f'line {index}', f'satır {index}', now=at))
        self.assertFalse(history.add('line 4', 'satır 4', now=at))
        self.assertEqual([entry[1] for entry in history.entries], ['line 2', 'line 3', 'line 4'])
        self.assertTrue(history.as_text().startswith('[12:00:05] line 2\nsatır 2'))
        window = HistoryWindow(history)
        self.assertIn('line 4', window.view.toPlainText())
        window.clear()
        self.assertEqual(window.view.toPlainText(), '')
        self.assertFalse(window.copy_button.isEnabled())
        window.deleteLater()

    def test_window_collects_live_lines_and_closes_when_capture_cannot_exclude_it(self):
        with tempfile.TemporaryDirectory() as folder:
            window = Window(Path(folder)/'models', settings=Settings(Path(folder)/'settings.json'))
            try:
                window.received(window.session, 'Hello.', 'Merhaba.')
                window.open_history()
                panel = window.history_window
                self.assertIsNotNone(panel)
                self.assertIn('Merhaba.', panel.view.toPlainText())
                window.received(window.session, 'Bye.', 'Hoşça kal.')
                window.poll()
                self.assertIn('Hoşça kal.', panel.view.toPlainText())
                with patch.object(window, 'capture_active', return_value=True):
                    window.poll()
                self.assertIsNone(window.history_window)
                self.assertIn('dışlanamadığı', window.status.text())
                with patch.object(window, 'capture_active', return_value=True):
                    window.open_history()
                self.assertIsNone(window.history_window)
            finally:
                window.close()


if __name__ == '__main__':
    unittest.main()
