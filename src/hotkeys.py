"""System-wide hotkeys (Win32 RegisterHotKey) so a game never needs Alt+Tab."""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
MODIFIERS = {'ctrl': MOD_CONTROL, 'alt': MOD_ALT, 'shift': MOD_SHIFT, 'meta': MOD_WIN, 'win': MOD_WIN}

# Ctrl+Alt is AltGr on Turkish layouts, so defaults use Ctrl+Shift.
ACTIONS = (
    ('toggle', 'Çeviriyi başlat / durdur', 'Ctrl+Shift+F5'),
    ('pause', 'Duraklat / devam et', 'Ctrl+Shift+F6'),
    ('overlay', 'PC altyazısını gizle / göster', 'Ctrl+Shift+F7'),
    ('reselect', 'Alanı yeniden seç', 'Ctrl+Shift+F8'),
)
DEFAULTS = {name: default for name, _, default in ACTIONS}
LABELS = {name: label for name, label, _ in ACTIONS}


def _virtual_key(name):
    name = name.upper()
    if len(name) == 1 and ('A' <= name <= 'Z' or '0' <= name <= '9'):
        return ord(name)
    if name.startswith('F') and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
        return 0x6F + int(name[1:])
    return {'PAUSE': 0x13, 'INS': 0x2D, 'INSERT': 0x2D, 'HOME': 0x24, 'END': 0x23,
            'PGUP': 0x21, 'PGDOWN': 0x22, 'SCROLLLOCK': 0x91}.get(name)


def parse(text):
    """'Ctrl+Shift+F5' -> (modifiers, virtual key). '' means disabled -> None."""
    if not isinstance(text, str) or len(text) > 64:
        raise ValueError('Kısayol metni geçersiz.')
    if not text:
        return None
    parts = [part.strip() for part in text.split('+')]
    *mods, key = parts
    flags = 0
    for mod in mods:
        flag = MODIFIERS.get(mod.lower())
        if flag is None or flags & flag:
            raise ValueError(f'Kısayol değiştiricisi geçersiz: {mod}')
        flags |= flag
    vk = _virtual_key(key)
    if vk is None:
        raise ValueError(f'Kısayol tuşu desteklenmiyor: {key}')
    function_key = 0x70 <= vk <= 0x87
    if not flags and not function_key:
        raise ValueError('Harf/rakam kısayolu Ctrl, Alt, Shift veya Win ile birlikte kullanılmalı.')
    return flags, vk


def valid_hotkey(value):
    try:
        parse(value)
    except ValueError:
        return False
    return True


class GlobalHotkeys(QAbstractNativeEventFilter):
    """Owns registrations for one window handle; unregisters everything on clear()."""
    BASE_ID = 0x4D4F  # application-defined id range

    def __init__(self, callback, user32=None):
        super().__init__()
        self.callback = callback
        self.user32 = user32 if user32 is not None else ctypes.windll.user32
        self.hwnd = None
        self.ids = {}

    def register(self, hwnd, bindings):
        """Replace registrations. Returns {action: reason} for bindings that failed."""
        self.clear()
        self.hwnd = hwnd
        failures = {}
        seen = {}
        for index, (action, text) in enumerate(bindings.items()):
            try:
                parsed = parse(text)
            except ValueError as exc:
                failures[action] = str(exc)
                continue
            if parsed is None:
                continue
            if parsed in seen:
                failures[action] = f'{LABELS.get(seen[parsed], seen[parsed])} ile aynı tuş.'
                continue
            seen[parsed] = action
            hotkey_id = self.BASE_ID + index
            if self.user32.RegisterHotKey(wintypes.HWND(hwnd), hotkey_id, parsed[0] | MOD_NOREPEAT, parsed[1]):
                self.ids[hotkey_id] = action
            else:
                failures[action] = 'Başka bir uygulama bu tuşu kullanıyor.'
        return failures

    def clear(self):
        for hotkey_id in tuple(self.ids):
            self.user32.UnregisterHotKey(wintypes.HWND(self.hwnd), hotkey_id)
        self.ids.clear()

    def nativeEventFilter(self, event_type, message):
        if self.ids and event_type == b'windows_generic_MSG':
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in self.ids:
                self.callback(self.ids[msg.wParam])
                return True, 0
        return False, 0
