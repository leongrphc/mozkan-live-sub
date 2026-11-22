import ctypes
import sys
import unittest
from ctypes import wintypes
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import hotkeys
from hotkeys import GlobalHotkeys, parse, valid_hotkey, DEFAULTS, WM_HOTKEY, MOD_NOREPEAT


class FakeUser32:
    def __init__(self, taken=()):
        self.taken = set(taken)
        self.registered = {}

    def RegisterHotKey(self, hwnd, hotkey_id, modifiers, vk):
        if (modifiers & ~MOD_NOREPEAT, vk) in self.taken:
            return 0
        self.registered[hotkey_id] = (modifiers, vk)
        return 1

    def UnregisterHotKey(self, hwnd, hotkey_id):
        return 1 if self.registered.pop(hotkey_id, None) else 0


class HotkeyParseTests(unittest.TestCase):
    def test_defaults_parse_and_avoid_altgr(self):
        for text in DEFAULTS.values():
            flags, _ = parse(text)
            self.assertFalse(flags & hotkeys.MOD_ALT and flags & hotkeys.MOD_CONTROL)

    def test_accepted_and_rejected_forms(self):
        self.assertEqual(parse('Ctrl+Shift+F5'), (hotkeys.MOD_CONTROL | hotkeys.MOD_SHIFT, 0x74))
        self.assertEqual(parse('F9'), (0, 0x78))
        self.assertEqual(parse('Meta+K'), (hotkeys.MOD_WIN, ord('K')))
        self.assertIsNone(parse(''))
        for text in ('K', 'Ctrl+Ctrl+K', 'Hyper+K', 'Ctrl+Space', 'Ctrl+F25', None, 'x' * 65):
            with self.subTest(text=text):
                self.assertFalse(valid_hotkey(text))


class GlobalHotkeyTests(unittest.TestCase):
    def test_register_reports_conflicts_duplicates_and_clear_unregisters(self):
        user32 = FakeUser32(taken={parse('Ctrl+Shift+F6')})
        keys = GlobalHotkeys(lambda action: None, user32=user32)
        failures = keys.register(1, dict(toggle='Ctrl+Shift+F5', pause='Ctrl+Shift+F6',
                                         overlay='Ctrl+Shift+F5', reselect=''))
        self.assertEqual(set(failures), {'pause', 'overlay'})
        self.assertEqual(list(keys.ids.values()), ['toggle'])
        self.assertTrue(all(mods & MOD_NOREPEAT for mods, _ in user32.registered.values()))
        keys.clear()
        self.assertFalse(user32.registered)
        self.assertFalse(keys.ids)

    def test_native_filter_dispatches_only_owned_hotkeys(self):
        pressed = []
        keys = GlobalHotkeys(pressed.append, user32=FakeUser32())
        keys.register(1, dict(toggle='Ctrl+Shift+F5'))
        (owned_id,) = keys.ids
        msg = wintypes.MSG()
        msg.message, msg.wParam = WM_HOTKEY, owned_id
        self.assertEqual(keys.nativeEventFilter(b'windows_generic_MSG', ctypes.addressof(msg)), (True, 0))
        msg.wParam = owned_id + 100
        self.assertEqual(keys.nativeEventFilter(b'windows_generic_MSG', ctypes.addressof(msg)), (False, 0))
        msg.message, msg.wParam = 0x0100, owned_id
        self.assertEqual(keys.nativeEventFilter(b'windows_generic_MSG', ctypes.addressof(msg)), (False, 0))
        self.assertEqual(pressed, ['toggle'])


if __name__ == '__main__':
    unittest.main()
