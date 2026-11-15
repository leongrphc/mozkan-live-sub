import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import Mock
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from capture import run_capture
from recognition import Reading


@unittest.skipUnless(os.name=='nt','Actual Windows thread scheduling')
class HudSchedulingTests(unittest.TestCase):
    @staticmethod
    def priority():
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.GetCurrentThread.argtypes=[];k.GetCurrentThread.restype=W.HANDLE
        k.GetThreadPriority.argtypes=[W.HANDLE];k.GetThreadPriority.restype=ctypes.c_int
        return k.GetThreadPriority(k.GetCurrentThread())

    def test_stop_during_startup_delay_does_not_acquire_model_and_restores_priority(self):
        stop=threading.Event()
        factory=Mock()
        before=self.priority()
        timer=threading.Timer(.03,stop.set)
        timer.start()
        try:run_capture(ROOT/'models',(0,0,100,30),stop,Mock(),Mock(),Mock(),ocr_kind='hud',engine_factory=factory,frames=[])
        finally:timer.join()
        factory.assert_not_called()
        self.assertEqual(self.priority(),before)

    def test_delay_and_below_normal_cover_both_owned_capture_and_translation_threads(self):
        stop=threading.Event()
        priorities={}
        before=self.priority()
        started=time.monotonic()
        class Reader:
            def __init__(inner,*args,**kwargs):
                priorities['load']=self.priority()
                priorities['at']=time.monotonic()-started
            def read(inner,frame):return Reading('Find the key.',.99,'hud',0)
            def translate(inner,text,*,can_infer):
                priorities['translate']=self.priority()
                return 'Anahtarı bul.'
        def frames():
            while not stop.is_set():yield np.zeros((60,200,3),dtype=np.uint8)
        errors=[]
        run_capture(ROOT/'models',(0,0,200,60),stop,lambda *args:stop.set(),lambda _:None,errors.append,
                    ocr_kind='hud',engine_factory=Reader,frames=frames(),interval=.02)
        self.assertEqual(errors,[])
        self.assertGreaterEqual(priorities['at'],1.18)
        self.assertEqual(priorities['load'],-1)
        self.assertEqual(priorities['translate'],-1)
        self.assertEqual(self.priority(),before)
