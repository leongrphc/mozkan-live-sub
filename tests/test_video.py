import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from stability import StableText, text_key
from recognition import Reading
from capture import ChangeGate
from video import subtitle_band, resolve_selection
import numpy as np


class VideoTests(unittest.TestCase):
    def test_subtitle_selection_is_not_cropped_a_second_time(self):
        selected = (120, 780, 900, 55)
        self.assertEqual(resolve_selection(selected), selected)
        self.assertEqual(resolve_selection(selected, 'subtitle', 30), selected)
        self.assertEqual(resolve_selection((100,100,960,540), 'video', 30),
                         (100,478,960,162))
        with self.assertRaises(ValueError):
            resolve_selection(selected, 'unknown')
    def test_band_stays_inside_video_on_negative_monitor(self):
        self.assertEqual(subtitle_band((-1920, 100, 1200, 600), 30),
                         (-1920, 520, 1200, 180))
        with self.assertRaises(ValueError):
            subtitle_band((0, 0, 1200, 600), 80)

    def test_punctuation_jitter_is_not_retranslated_but_word_changes_are(self):
        s = StableText(blank_timeout=.8)
        self.assertIsNone(s.observe('We need to leave.', 1))
        self.assertEqual(text_key(s.observe('WE NEED TO LEAVE!', 1.2)), 'we need to leave')
        self.assertIsNone(s.observe('We need to leave...', 1.4))
        self.assertIsNone(s.observe('We need to stay.', 1.6))
        self.assertEqual(s.observe('We need to stay.', 1.8), 'We need to stay.')
        self.assertIsNone(s.observe('', 2))
        self.assertEqual(s.observe('', 2.7), '')

    def test_periodic_refresh_examines_otherwise_unchanged_frame(self):
        class Reader:
            calls = 0
            def read(self, frame):
                self.calls += 1
                return Reading('Caption' if self.calls == 1 else '',1.0,'test',0.0)
        now = [0]
        gate = ChangeGate(refresh_seconds=.75, clock=lambda: now[0])
        reader = Reader()
        frame = np.zeros((80, 200, 3), dtype=np.uint8)
        self.assertEqual(gate.read(reader, frame).text, 'Caption')
        now[0] = .5
        self.assertEqual(gate.read(reader, frame).text, 'Caption')
        now[0] = .8
        self.assertEqual(gate.read(reader, frame).text, '')
        self.assertEqual(reader.calls, 2)
