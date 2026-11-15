import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from stability import StableText


class StabilityTests(unittest.TestCase):
    def test_repeat_and_blank_expiry(self):
        s = StableText()
        self.assertIsNone(s.observe('Hello', 1))
        self.assertEqual(s.observe('Hello', 1.2), 'Hello')
        self.assertIsNone(s.observe('', 2))
        self.assertEqual(s.observe('', 3.3), '')
        self.assertIsNone(s.observe('', 4))

    def test_flicker_does_not_replace_caption(self):
        s = StableText()
        s.observe('Hello', 1)
        s.observe('Hello', 2)
        self.assertIsNone(s.observe('Noise', 3))
        self.assertIsNone(s.observe('Hello', 4))
        self.assertEqual(s.accepted, 'Hello')


if __name__ == '__main__':
    unittest.main()
