"""Map Qt logical coordinates to Windows monitor pixel coordinates."""
import ctypes
import os
import math
from ctypes import wintypes
from dataclasses import dataclass


def screen_for_region(region,screens):
    if (not isinstance(region,(tuple,list)) or len(region)!=4
            or any(type(value) is not int for value in region)
            or region[2]<=0 or region[3]<=0):
        raise ValueError('Ekran bölgesinin koordinatları geçersiz.')
    x,y,w,h=region
    matches=[s for s in screens if s.geometry().contains(x,y)
             and s.geometry().contains(x+w-1,y+h-1)]
    if not matches:
        raise ValueError('Bölgeyi tek bir görünür monitörün içinde seçin.')
    if len(matches)!=1:
        raise ValueError('Bölgenin hangi monitöre ait olduğu belirlenemedi.')
    return matches[0]


@dataclass(frozen=True,slots=True)
class NormalizedBox:
    x: float
    y: float
    w: float
    h: float

    def __post_init__(self):
        values=(self.x,self.y,self.w,self.h)
        try:
            finite=all(type(value) in (int,float) and math.isfinite(value) for value in values)
        except OverflowError:
            finite=False
        if (not finite
                or not 0<=self.x<=1 or not 0<=self.y<=1 or not 0<self.w<=1 or not 0<self.h<=1
                or self.x+self.w>1.0001 or self.y+self.h>1.0001):
            raise ValueError('TV alanı sonlu, pozitif ve monitör sınırları içinde olmalı.')

    @classmethod
    def from_wire(cls,value):
        if not isinstance(value,dict) or len(value)!=4 or set(value)!=set(('x','y','w','h')):
            raise ValueError('TV alanı x/y/w/h sayılarından oluşmalı.')
        return cls(**value)

    def as_dict(self):
        return dict(x=self.x,y=self.y,w=self.w,h=self.h)


def normalized_region(region,screens):
    """Use the region's owning monitor, never virtual-desktop coordinates."""
    geometry=screen_for_region(region,screens).geometry()
    if geometry.width()<=0 or geometry.height()<=0:
        raise ValueError('Monitör boyutu belirlenemedi.')
    x,y,w,h=region
    return NormalizedBox(round((x-geometry.x())/geometry.width(),4),
                         round((y-geometry.y())/geometry.height(),4),
                         round(w/geometry.width(),4),round(h/geometry.height(),4))


def capture_region(region, screens):
    screen = screen_for_region(region,screens)
    x, y, w, h = region
    geometry = screen.geometry()
    if os.name != 'nt':
        ratio = screen.devicePixelRatio()
        return (round(x * ratio), round(y * ratio), round(w * ratio), round(h * ratio))
    class MonitorInfo(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                    ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD),
                    ('szDevice', wintypes.WCHAR * 32)]
    # Qt may expose an EDID friendly name while Win32 exposes DISPLAY1.
    # Bind a private native Qt window to the chosen screen and ask Windows
    # which monitor owns that exact window; display strings aren't identity.
    from PySide6.QtGui import QWindow
    probe = QWindow()
    try:
        probe.setScreen(screen)
        probe.setGeometry(geometry.x() + 20, geometry.y() + 20, 1, 1)
        handle = int(probe.winId())
        monitor_from_window = ctypes.windll.user32.MonitorFromWindow
        monitor_from_window.argtypes = [wintypes.HWND, wintypes.DWORD]
        monitor_from_window.restype = wintypes.HMONITOR
        monitor = monitor_from_window(handle, 0)
        get_info = ctypes.windll.user32.GetMonitorInfoW
        get_info.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MonitorInfo)]
        get_info.restype = wintypes.BOOL
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        if not monitor or not get_info(monitor, ctypes.byref(info)):
            raise OSError('Seçilen Qt ekranının Windows monitörü bulunamadı.')
        r = info.rcMonitor
        px, py, pw, ph = r.left, r.top, r.right - r.left, r.bottom - r.top
    finally:
        probe.destroy()
    sx, sy = pw / geometry.width(), ph / geometry.height()
    return (px + round((x - geometry.x()) * sx),
            py + round((y - geometry.y()) * sy), round(w * sx), round(h * sy))
