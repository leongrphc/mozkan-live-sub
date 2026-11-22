from pathlib import Path
import sys
import tempfile
import json
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from app_log import AppLog


class AppLogTests(unittest.TestCase):
    def test_unique_files_preserve_prior_runs_and_only_named_metadata_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            a=AppLog(folder,'version','python');a.record('capture_error',session=2,role='subtitle',error_class='RuntimeError');a.close()
            before=a.path.read_bytes()
            b=AppLog(folder,'version','python')
            try:
                self.assertNotEqual(a.path,b.path)
                with self.assertRaises(ValueError):b.record('capture_error',session=2,role='subtitle',error_class='RuntimeError',subtitle='private')
                self.assertEqual(a.path.read_bytes(),before)
                rows=[json.loads(line) for line in before.splitlines()]
                self.assertEqual(rows[-1]['error_class'],'RuntimeError')
            finally:b.close()

    def test_ui_error_records_only_component_and_class(self):
        with tempfile.TemporaryDirectory() as folder:
            log=AppLog(folder,'version','python')
            try:
                log.record('ui_error',component='tv_start',error_class='OSError')
                with self.assertRaises(ValueError):
                    log.record('ui_error',component='tv_start',error_class='OSError',message='port in use')
            finally:log.close()
            row=json.loads(log.path.read_bytes().splitlines()[-1])
            self.assertEqual((row['event'],row['component'],row['error_class']),('ui_error','tv_start','OSError'))

    def test_utf8_byte_limit_keeps_file_bounded_and_marks_capacity(self):
        with tempfile.TemporaryDirectory() as folder:
            log=AppLog(folder,'test','python')
            log.MAX_BYTES=log.written+60
            try:
                log.record('capture_start',session=1,mode='ç'*30,profile='ö'*30)
                self.assertTrue(log.truncated)
                self.assertLessEqual(log.path.stat().st_size,log.MAX_BYTES)
            finally:log.close()

    def test_failed_close_retains_stream_until_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            log=AppLog(folder,'test','python');stream=log.stream
            class Failing:
                closed=False
                def close(self):raise OSError('known close failure')
            failing=Failing();log.stream=failing
            self.assertFalse(log.close())
            self.assertIs(log.stream,failing)
            log.stream=stream
            self.assertTrue(log.close())
            self.assertIsNone(log.stream)
