"""Apply and query capture exclusion only for a caller-owned Qt widget."""
import ctypes
from ctypes import wintypes as W
import os
from PySide6.QtGui import QGuiApplication


def try_capture_exclusion(widget):
    if os.name!='nt' or QGuiApplication.platformName().lower()!='windows':return False
    try:
        user=ctypes.WinDLL('user32',use_last_error=True)
        user.SetWindowDisplayAffinity.argtypes=[W.HWND,W.DWORD]
        user.SetWindowDisplayAffinity.restype=W.BOOL
        user.GetWindowDisplayAffinity.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
        user.GetWindowDisplayAffinity.restype=W.BOOL
        handle=int(widget.winId())
        affinity=W.DWORD()
        return bool(user.SetWindowDisplayAffinity(handle,0x11)
                    and user.GetWindowDisplayAffinity(handle,ctypes.byref(affinity)) and affinity.value==0x11)
    except (OSError,AttributeError,RuntimeError):return False
