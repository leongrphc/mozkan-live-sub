"""Actual Windows/MSS modal exclusion with an owned opaque source and positive control.

No OCR/model/real game is started. Only handles of this helper's own dialogs change.
"""
import ctypes
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='windows'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from main import QApplication,Window,Qt,QTimer,QPushButton,QDialog
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage
from settings import Settings
from capture_exclusion import try_capture_exclusion
from coordinates import capture_region
from live_preconditions import require_visible_desktop
import mss
import numpy as np
require_visible_desktop()
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
app=QApplication([])
folder=tempfile.TemporaryDirectory()
window=Window(ROOT/'models',settings=Settings(Path(folder.name)/'settings.json'))
window.show()
region=capture_region((100,142,950,65),app.screens())
user=ctypes.WinDLL('user32',use_last_error=True)
user.CreateWindowExW.argtypes=[W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.HWND,W.HMENU,W.HINSTANCE,ctypes.c_void_p]
user.CreateWindowExW.restype=W.HWND
user.SetWindowPos.argtypes=[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT]
user.SetWindowPos.restype=W.BOOL
user.UpdateWindow.argtypes=[W.HWND];user.UpdateWindow.restype=W.BOOL
user.DestroyWindow.argtypes=[W.HWND];user.DestroyWindow.restype=W.BOOL
user.WindowFromPoint.argtypes=[W.POINT];user.WindowFromPoint.restype=W.HWND
user.GetAncestor.argtypes=[W.HWND,W.UINT];user.GetAncestor.restype=W.HWND
# A native static window is outside QApplication's modal widget hierarchy.
# An owned QLabel from this same QApplication can be changed/disabled by a
# modal dialog, which is not representative of an external game's surface.
x,y,w,h=capture_region((100,100,950,130),app.screens())
source=user.CreateWindowExW(0x08000088,'STATIC','Owned fixed capture source',0x90000106,x,y,w,h,None,None,None,None)
assert source,ctypes.get_last_error()
assert user.SetWindowPos(source,W.HWND(-1),0,0,0,0,0x13)
user.UpdateWindow(source);QTest.qWait(100)
user.SetWindowDisplayAffinity.argtypes=[W.HWND,W.DWORD];user.SetWindowDisplayAffinity.restype=W.BOOL
user.GetWindowDisplayAffinity.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)];user.GetWindowDisplayAffinity.restype=W.BOOL
results=[];errors=[]
sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').glob('*.py')}

def grab():
    x,y,w,h=region
    with mss.MSS() as screen:return np.asarray(screen.grab(dict(left=x,top=y,width=w,height=h))).copy()
baseline=None

def verify(dialog,role):
    dialog.setGeometry(80,110,700,400);dialog.raise_();dialog.activateWindow();QTest.qWait(100)
    handle=int(dialog.winId())
    assert user.SetWindowPos(handle,W.HWND(-1),0,0,0,0,0x13)
    QTest.qWait(100)
    hit=user.WindowFromPoint(W.POINT(region[0]+region[2]//2,region[1]+region[3]//2))
    assert user.GetAncestor(hit,2)==handle,'Dialog is not visibly in front of the fixture source'
    affinity=W.DWORD()
    assert user.GetWindowDisplayAffinity(handle,ctypes.byref(affinity)) and affinity.value==0x11,'Production dialog was not excluded'
    actual=grab()
    assert QImage(actual.data,actual.shape[1],actual.shape[0],actual.strides[0],QImage.Format_ARGB32).copy().save(str(ROOT/f'analysis/{role}-source-excluded.png'))
    excluded=int(np.count_nonzero(np.any(actual[:,:,:3]!=baseline[:,:,:3],axis=2)))
    assert excluded==0,dict(role=role,excluded_changed_pixels=excluded,baseline_pixel=baseline[0,0].tolist(),actual_pixel=actual[0,0].tolist())
    try:
        assert user.SetWindowDisplayAffinity(handle,0)
        QTest.qWait(100)
        visible=int(np.count_nonzero(np.any(grab()[:,:,:3]!=baseline[:,:,:3],axis=2)))
        assert visible>0,'Positive control did not occlude the source'
    finally:assert try_capture_exclusion(dialog)
    QTest.qWait(100)
    restored=int(np.count_nonzero(np.any(grab()[:,:,:3]!=baseline[:,:,:3],axis=2)))
    assert restored==0
    results.append(dict(role=role,initial_changed_pixels=excluded,positive_changed_pixels=visible,restored_changed_pixels=restored))

def picker():
    dialog=app.activeModalWidget()
    try:verify(dialog,'color_picker')
    except Exception as error:errors.append(f'{type(error).__name__}: {error}')
    finally:
        if dialog is not None:dialog.reject()

def appearance():
    dialog=app.activeModalWidget()
    try:
        verify(dialog,'appearance')
        assert dialog.grab().save(str(ROOT/'analysis/appearance-0.4.0-dev-native.png'))
        QTimer.singleShot(20,picker)
        dialog.findChild(QPushButton,'appearanceColor').click()
    except Exception as error:errors.append(f'{type(error).__name__}: {error}')
    finally:
        if dialog is not None:dialog.reject()

def launch():
    QTimer.singleShot(20,appearance)
    actual=window.exec_capture_safe_dialog
    def topmost_fixture(dialog):
        dialog.setWindowFlag(Qt.WindowStaysOnTopHint,True)
        return actual(dialog)
    with patch.object(window,'exec_capture_safe_dialog',side_effect=topmost_fixture):window.edit_appearance()
    window.close();app.quit()

def abort():
    errors.append('Modal capture timeout')
    for dialog in window.findChildren(QDialog):dialog.reject()
    window.close();app.quit()

try:
    assert user.WindowFromPoint(W.POINT(region[0]+region[2]//2,region[1]+region[3]//2))==source,'Known source is not the foreground fixture'
    baseline=grab()
    user.GetSysColor.argtypes=[ctypes.c_int];user.GetSysColor.restype=W.DWORD
    color=user.GetSysColor(5)
    expected=[(color>>16)&255,(color>>8)&255,color&255]
    assert any(expected),'Fixture requires a nonblack window background'
    assert np.all(baseline[:,:,:3]==expected),'Known opaque source was not captured'
    assert QImage(baseline.data,baseline.shape[1],baseline.shape[0],baseline.strides[0],QImage.Format_ARGB32).copy().save(str(ROOT/'analysis/appearance-source-baseline.png'))
    QTimer.singleShot(100,launch);QTimer.singleShot(10000,abort)
    app.exec()
finally:
    window.close()
    assert user.DestroyWindow(source),ctypes.get_last_error()
    folder.cleanup()
assert not errors,errors
assert len(results)==2,results
assert all(hashlib.sha256((ROOT/'src'/p).read_bytes()).hexdigest()==d for p,d in sources.items())
print(json.dumps(dict(status='PASS',results=results,physical_region=region,sources=sources,
    scope='Actual own appearance and Qt color dialog, Win32 affinity query and MSS over own native static source outside Qt modal hierarchy. Source and dialogs are explicitly topmost for this fixture; foreground source checked with WindowFromPoint. Production dialog exclusion path unchanged. Positive control temporarily disables exclusion only on own HWND. No OCR/MT/game/physical TV/other-computer proof.')))
