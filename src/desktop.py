"""Read-only Windows session visibility; never switch or unlock a desktop."""
from dataclasses import dataclass
import os
import sys


@dataclass(frozen=True)
class DesktopState:
    state: str
    reason: str
    session_id: int | None = None
    native_state: int | None = None
    native_flags: int | None = None


def desktop_state():
    if os.name != 'nt' or sys.getwindowsversion().major < 10:
        return DesktopState('unknown', 'Windows 10+ oturum gözlemi kullanılamıyor.')
    import ctypes
    from ctypes import wintypes
    class Level1(ctypes.Structure):
        _fields_ = [('session', wintypes.ULONG), ('state', ctypes.c_int), ('flags', wintypes.LONG),
                    ('station', wintypes.WCHAR*33), ('user', wintypes.WCHAR*21),
                    ('domain', wintypes.WCHAR*18), ('times', ctypes.c_longlong*5),
                    ('counters', wintypes.DWORD*6)]
    class Data(ctypes.Union):
        _fields_ = [('level1', Level1)]
    class Info(ctypes.Structure):
        _fields_ = [('level', wintypes.DWORD), ('data', Data)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    get_session = kernel.ProcessIdToSessionId
    get_session.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    get_session.restype = wintypes.BOOL
    session = wintypes.DWORD()
    if not get_session(os.getpid(), ctypes.byref(session)):
        return DesktopState('unknown', 'İşlemin Windows oturumu okunamadı.')
    api = ctypes.WinDLL('wtsapi32', use_last_error=True)
    query = api.WTSQuerySessionInformationW
    query.argtypes = [wintypes.HANDLE,wintypes.DWORD,ctypes.c_int,
                      ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(wintypes.DWORD)]
    query.restype = wintypes.BOOL
    buffer, size = ctypes.c_void_p(), wintypes.DWORD()
    if not query(None, session.value, 25, ctypes.byref(buffer), ctypes.byref(size)):
        return DesktopState('unknown', 'Windows oturum durumu sorgulanamadı.', session.value)
    try:
        if size.value < ctypes.sizeof(Info):
            return DesktopState('unknown', 'Windows oturum kaydı eksik.', session.value)
        info = ctypes.cast(buffer, ctypes.POINTER(Info)).contents
        if info.level != 1 or info.data.level1.session != session.value:
            return DesktopState('unknown', 'Windows oturum kaydının kimliği uyuşmuyor.', session.value)
        native = info.data.level1
        if native.flags == 0:
            state, reason = 'locked', 'Windows oturumu kilitli; gerçek ekran testi yapılamaz.'
        elif native.flags == 1 and native.state == 0:
            state, reason = 'unlocked', 'Windows oturumu açık ve etkin.'
        else:
            state, reason = 'unknown', 'Windows oturumu görünürlüğü doğrulanamadı.'
        return DesktopState(state, reason, session.value, native.state, native.flags)
    finally:
        api.WTSFreeMemory.argtypes = [ctypes.c_void_p]
        api.WTSFreeMemory(buffer)
