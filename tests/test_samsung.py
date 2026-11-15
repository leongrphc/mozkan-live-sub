import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import ctypes
from ctypes import wintypes as W
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from samsung_protocol import parse_notice,SamsungState,valid_saved_host,MAX_LINE
from samsung import SamsungHelper
from PySide6.QtWidgets import QApplication


class SamsungProtocolTests(unittest.TestCase):
    def test_owner_preserves_unknown_confidence_and_rejects_host_and_url_confusion(self):
        self.assertTrue(valid_saved_host('192.168.1.5'))
        self.assertFalse(valid_saved_host(True))
        for url in ('https://account.samsung.com.evil.test/x','https://user@account.samsung.com/x',
                    'http://account.samsung.com/x','https://account.samsung.com:444/x'):
            event=parse_notice(json.dumps(dict(event='step',step='login',url=url,percent=True)).encode())
            self.assertEqual(event.url,'')
            self.assertIsNone(event.percent)
        event=parse_notice(b'{"event":"step","step":"login","url":"https://account.samsung.com/x","percent":50}')
        self.assertEqual(event.percent,50)
        self.assertTrue(event.url)
        with self.assertRaises(ValueError):parse_notice(b'{"event":"tv","ip":"224.0.0.1"}')
        with self.assertRaises(ValueError):parse_notice(b'{"event":"step","text":{}}')
        with self.assertRaises(ValueError):parse_notice(b'x'*(MAX_LINE+1))

    def test_tv_identity_order_replacement_and_error_facts_survive_done(self):
        state=SamsungState(action='scan')
        for ip,name in [('192.168.1.80','A'),('192.168.1.20','B'),('192.168.1.80','C')]:
            state=state.notice(parse_notice(json.dumps(dict(event='tv',ip=ip,name=name)).encode()))
        self.assertEqual([(tv.ip,tv.name) for tv in state.tvs],[('192.168.1.20','B'),('192.168.1.80','C')])
        self.assertIsNone(state.tvs[0].dev_mode)
        state=state.notice(parse_notice(b'{"event":"error","code":"x","text":"failed","hint":"try"}'))
        state=state.notice(parse_notice(b'{"event":"done"}'))
        self.assertTrue(state.scanned)
        self.assertEqual(state.error,'failed')
        self.assertEqual(state.hint,'try')


@unittest.skipUnless(os.name=='nt','Actual Windows job/process lifecycle')
class SamsungLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.data=Path(self.folder.name)
        self.helper=SamsungHelper(ROOT/'samsung',self.data)
        self.launch=self.helper.process.start
        def fixture(program,args):
            split=args.index('--')
            args=args[:split+1]+[sys.executable,'-B','-E','-s','-X','utf8',str(ROOT/'tests/samsung_fixture.py')]+args[split+2:]
            self.launch(program,args)
        self.patcher=patch.object(self.helper.process,'start',side_effect=fixture)
        self.patcher.start()

    def tearDown(self):
        self.helper.cancel()
        self.until(lambda:not self.helper.busy)
        self.patcher.stop()
        self.folder.cleanup()

    def until(self,predicate,timeout=8):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            self.app.processEvents()
            if predicate():return
            time.sleep(.005)
        self.fail('Owned helper did not reach requested lifecycle state: '+str(self.helper.state))

    def mode(self,value):(self.data/'fixture-mode').write_text(value)

    def child_handle(self):
        self.until(lambda:(self.data/'child-pid').exists())
        pid=int((self.data/'child-pid').read_text())
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
        handle=k.OpenProcess(0x100000|0x1000,False,pid)
        self.assertTrue(handle)
        k.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,ctypes.POINTER(W.BOOL)];k.IsProcessInJob.restype=W.BOOL
        inside=W.BOOL()
        self.assertTrue(k.IsProcessInJob(handle,self.helper.job.handle,ctypes.byref(inside)))
        self.assertTrue(inside.value,'Child handle must be a member of the owned job')
        k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.WaitForSingleObject.restype=W.DWORD
        k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
        return k,handle

    def test_real_runner_scans_fragmented_lines_and_records_redacted_log(self):
        self.helper.start('install','192.168.1.20','known-transport-token',renew=True)
        self.until(lambda:not self.helper.busy)
        state=self.helper.state
        self.assertTrue(state.done,state)
        self.assertFalse(state.error,state)
        self.assertEqual([tv.name for tv in state.tvs],['İkinci TV','Güncel TV'])
        self.assertEqual(state.tizen,'7.0')
        self.assertEqual(state.url,'')
        log=self.helper.log_path.read_text(encoding='utf-8')
        self.assertNotIn('known-transport-token',log)
        self.assertIn('renew=True',log)
        self.assertIn('Bilinen tamamlanma',log)

    def test_cancel_before_late_started_signal_keeps_ownership_until_terminal(self):
        self.mode('hang')
        self.helper.start('scan')
        self.helper.cancel()
        self.assertTrue(self.helper.busy)
        self.until(lambda:not self.helper.busy)
        self.assertTrue(self.helper.state.cancelled)
        self.assertEqual(self.helper.state.text,'İptal edildi.')

    def test_actual_descendant_is_owned_and_cancelled_without_pid_kill(self):
        self.mode('hang')
        self.helper.start('scan')
        k,handle=self.child_handle()
        try:
            self.assertGreaterEqual(self.helper.job.active(),3)
            self.helper.cancel()
            self.until(lambda:not self.helper.busy)
            self.assertEqual(k.WaitForSingleObject(handle,0),0)
        finally:k.CloseHandle(handle)

    def test_normal_root_exit_also_drains_lingering_child(self):
        self.mode('orphan')
        # Open the descendant handle as soon as fixture creates it, before root exits.
        self.helper.start('scan')
        k,handle=self.child_handle()
        try:
            (self.data/'allow-exit').touch()
            self.until(lambda:not self.helper.busy)
            self.assertTrue(self.helper.state.scanned)
            self.assertEqual(k.WaitForSingleObject(handle,0),0)
        finally:k.CloseHandle(handle)

    def test_error_incomplete_and_capacity_are_distinct_and_retry_uses_new_job(self):
        names=set()
        for mode,code in [('error','known'),('exit0','incomplete'),('malformed','protocol'),('capacity','capacity')]:
            self.mode(mode)
            self.helper.start('scan')
            names.add(self.helper.job.name)
            self.until(lambda:not self.helper.busy)
            self.assertEqual(self.helper.state.code,code,self.helper.state)
            self.assertTrue(self.helper.state.error)
        self.assertEqual(len(names),4)

    def test_cleanup_failure_retains_job_and_cancel_retries_finalization(self):
        self.helper.start('scan')
        job=self.helper.job
        close=job.close
        allow=[False]
        def failed():
            if not allow[0]:raise OSError('known cleanup failure')
            close()
        with patch.object(job,'close',side_effect=failed):
            self.until(lambda:'known cleanup failure' in self.helper.state.cleanup_error)
            self.assertTrue(self.helper.busy)
            self.assertIs(self.helper.job,job)
            self.assertEqual(job.active(),0)
            self.helper.cancel()
            allow[0]=True
            self.until(lambda:not self.helper.busy)
            self.assertIsNone(job.handle)

    def test_failed_root_start_releases_empty_job_and_open_log(self):
        with patch.object(self.helper.process,'start',side_effect=lambda program,args:self.launch(str(self.data/'missing-runner.exe'),args)):
            self.helper.start('scan')
            self.until(lambda:not self.helper.busy)
        self.assertEqual(self.helper.state.code,'start')
        self.assertIsNone(self.helper.job)
        self.assertIsNone(self.helper._log)

    def test_job_configuration_failure_retains_owner_until_retry(self):
        from windows_job import WindowsJob
        with patch.object(WindowsJob,'configure',side_effect=OSError('configuration refused')):
            with self.assertRaises(OSError):self.helper.start('scan')
        self.until(lambda:not self.helper.busy)
        self.assertEqual(self.helper.state.code,'start')

    def test_log_limit_does_not_cut_state_or_exceed_advertised_file_capacity(self):
        self.helper.MAX_LOG=128
        self.helper.start('scan')
        self.until(lambda:not self.helper.busy)
        self.assertTrue(self.helper.state.scanned)
        self.assertTrue(self.helper.state.log_truncated)
        self.assertLessEqual(self.helper.log_path.stat().st_size,128)

    def test_many_valid_small_lines_still_obey_total_output_capacity(self):
        self.mode('flood')
        self.helper.MAX_OUTPUT=2048
        self.helper.start('scan')
        self.until(lambda:not self.helper.busy)
        self.assertEqual(self.helper.state.code,'capacity')

    def test_actual_window_consumes_typed_progress_and_never_replaces_entered_host(self):
        from main import Window
        from settings import Settings
        with patch('main.SamsungHelper',return_value=self.helper):
            window=Window(ROOT/'models',settings=Settings(self.data/'settings.json'))
        login_enabled=[]
        self.helper.changed.connect(lambda state:login_enabled.append(window.samsung_login.isEnabled()) if state.url else None)
        try:
            window.tv_host.setText('192.168.1.99')
            window.samsung_renew.setChecked(True)
            window.samsung_start('install')
            self.assertFalse(window.samsung_install.isEnabled())
            self.until(lambda:not self.helper.busy)
            window.poll()
            self.assertEqual(window.tv_host.text(),'192.168.1.99')
            self.assertEqual(window.settings.values['samsung_host'],'192.168.1.99')
            self.assertEqual(window.samsung_devices.count(),3)
            self.assertIn(True,login_enabled)
            self.assertFalse(window.samsung_login.isEnabled())
            self.assertTrue(window.samsung_progress.isHidden())
            self.assertIn('Bilinen tamamlanma',window.samsung_detail.text())
            window.samsung_devices.activated.emit(1)
            self.assertEqual(window.tv_host.text(),'192.168.1.20')
        finally:
            self.helper.cancel()
            self.until(lambda:not self.helper.busy)
            window.close()
