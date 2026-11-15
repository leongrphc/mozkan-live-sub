import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from subtitle_ocr import SubtitleReader,choose,scan
from recognition import Reading
from engine import fit_subtitle,InferenceCancelled


class SubtitleOCRTests(unittest.TestCase):
    def source(self,pale=False,blank=False):
        frame=np.full((65,950,3),200 if pale else 0,dtype=np.uint8)
        if not blank:frame[20:40,400:410]=255
        return frame
    def reader(self,outputs,calls):
        outputs=iter(outputs)
        def read(frame,**flags):
            calls.append((frame.shape,flags))
            text,score=next(outputs)
            return SimpleNamespace(txts=[text] if text else None,scores=[score],boxes=None)
        return read

    def test_fast_dark_blank_and_confident_text_use_one_pass(self):
        for text in ('','We need to leave.'):
            calls=[]
            result=SubtitleReader().read(self.source(blank=not text),fit_subtitle,self.reader([(text,.95)],calls))
            self.assertEqual(result.text,text)
            self.assertEqual(len(calls),1 if text else 0)
            if text:self.assertEqual(calls[0][0],(96,640,3))
            self.assertEqual(result.variant,'plain' if text else 'uniform')
            self.assertEqual(len(result.scans),1 if text else 0)

    def test_accurate_always_compares_contrast_and_keeps_full_winning_caption(self):
        calls=[]
        result=SubtitleReader('accurate').read(self.source(),fit_subtitle,
            self.reader([('We need to',.8),('We need to leave before the guards return.',.9)],calls))
        self.assertEqual(result.text,'We need to leave before the guards return.')
        self.assertEqual(result.variant,'contrast')
        self.assertEqual([s.variant for s in result.scans],['plain','contrast'])
        self.assertGreaterEqual(result.elapsed_ms,sum(s.elapsed_ms for s in result.scans))

    def test_pale_blank_recovery_is_throttled_but_does_not_vote_for_empty_frames(self):
        now=[0.]
        policy=SubtitleReader(clock=lambda:now[0])
        calls=[]
        ocr=self.reader([('',None)]*5,calls)
        for value in (0,.1,.31):
            now[0]=value
            policy.read(self.source(True),fit_subtitle,ocr)
        self.assertEqual(len(calls),5)
        self.assertEqual(len(policy.votes),0)

    def test_pale_votes_lead_with_light_only_after_two_successful_comparisons(self):
        policy=SubtitleReader()
        calls=[]
        ocr=self.reader([('We need to go.',.7),('We need to leave.',.95)]*2+[('We need to leave.',.99)],calls)
        for _ in range(2):policy.read(self.source(True),fit_subtitle,ocr)
        third=policy.read(self.source(True),fit_subtitle,ocr)
        self.assertEqual(third.variant,'light')
        self.assertEqual(len(third.scans),1)
        self.assertEqual(list(policy.votes),[True,True])

    def test_unknown_confidence_remains_unknown_and_not_a_synthetic_score(self):
        first=Reading('We need to leave.',None,'test',0)
        second=Reading('We need to leave right now.',.9,'test',0)
        self.assertIs(choose(first,second),first)
        self.assertIsNone(choose(first,second).confidence)

    def test_cancel_before_recovery_starts_no_second_model_call(self):
        calls=[]
        def read(frame,**flags):
            if calls:raise InferenceCancelled()
            calls.append(frame.shape)
            return SimpleNamespace(txts=['We need to'],scores=[.5],boxes=None)
        with self.assertRaises(InferenceCancelled):
            SubtitleReader('accurate').read(self.source(),fit_subtitle,read)
        self.assertEqual(len(calls),1)

    def test_more_than_eight_rows_fails_explicitly_instead_of_silent_truncation(self):
        boxes=[[[0,i*11],[80,i*11],[80,i*11+4],[0,i*11+4]] for i in range(9)]
        calls=[]
        def read(frame,**flags):
            calls.append(flags)
            return SimpleNamespace(txts=['row']*9,scores=[.9]*9,boxes=boxes)
        with self.assertRaisesRegex(ValueError,'sekizden fazla'):
            scan(read,np.zeros((96,640,3),dtype=np.uint8),'plain')
        self.assertEqual(len(calls),1)

    def test_malformed_geometry_keeps_whole_line_facts_instead_of_dropping_words(self):
        output=SimpleNamespace(txts=['We need to','leave now.'],scores=[.95,.9],
            boxes=[[[0,0],[80,0],[80,10],[0,10]],[[0,20]]])
        reading=scan(lambda *args,**kwargs:output,np.zeros((96,640,3),dtype=np.uint8),'plain')
        self.assertEqual(reading.text,'We need to leave now.')
        self.assertEqual(reading.method,'subtitle/unboxed-invalid')

    def test_single_or_disjoint_box_uses_validated_recognition_without_rerecognizing_crop(self):
        boxes=[[[0,0],[80,0],[80,15],[0,15]],[[90,0],[170,0],[170,15],[90,15]]]
        calls=[]
        def read(frame,**options):
            calls.append(options)
            return SimpleNamespace(txts=['We need to','leave now.'],scores=[.95,.9],boxes=boxes)
        reading=scan(read,np.zeros((96,640,3),dtype=np.uint8),'plain')
        self.assertEqual(reading.text,'We need to leave now.')
        self.assertEqual(len(calls),1)
