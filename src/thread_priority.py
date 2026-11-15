"""Best-effort priority for owned HUD threads, restored by that same thread."""
import ctypes
from ctypes import wintypes as W
from dataclasses import dataclass
import logging
import os
import threading


@dataclass
class ThreadPriority:
    api:object
    handle:int
    previous:int
    owner:int

    def restore(self):
        if threading.get_ident()!=self.owner:raise RuntimeError('İş parçacığı önceliğini yalnız sahibi geri yükleyebilir.')
        if not self.api.SetThreadPriority(self.handle,self.previous):
            logging.getLogger('atolye').warning('HUD thread priority restoration failed: %s',ctypes.get_last_error())


def lower_current_thread():
    if os.name!='nt':return None
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.GetCurrentThread.argtypes=[];k.GetCurrentThread.restype=W.HANDLE
    k.GetThreadPriority.argtypes=[W.HANDLE];k.GetThreadPriority.restype=ctypes.c_int
    k.SetThreadPriority.argtypes=[W.HANDLE,ctypes.c_int];k.SetThreadPriority.restype=W.BOOL
    handle=k.GetCurrentThread()
    previous=k.GetThreadPriority(handle)
    if previous==0x7fffffff or not k.SetThreadPriority(handle,-1):
        logging.getLogger('atolye').warning('HUD thread priority could not be lowered: %s',ctypes.get_last_error())
        return None
    return ThreadPriority(k,handle,previous,threading.get_ident())
