import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from engine import Engine
from recognition import Reading, recognized_parts, reading_from_parts, readable_caption
from stability import StableText
from capture import ChangeGate


class RecognitionTests(unittest.TestCase):
    def test_boolean_text_and_nonreal_scores_are_not_fabricated_probabilities(self):
        from recognition import parse_confidence
        for value in (True,np.bool_(True),'0.9',complex(1,0),10**500):
            self.assertIsNone(parse_confidence(value))
        self.assertAlmostEqual(parse_confidence(np.float32(.9)),.9,places=6)
    def test_missing_nonfinite_and_out_of_range_scores_stay_unknown(self):
        output = SimpleNamespace(txts=['We need','to leave','right now'],scores=[float('nan'),1.1])
        parts = recognized_parts(output)
        self.assertEqual(parts,[('We need',None),('to leave',None),('right now',None)])
        result = reading_from_parts(parts,'test',12)
        self.assertEqual(result.text,'We need to leave right now')
        self.assertIsNone(result.confidence)

    def test_weak_words_are_retained_with_weighted_confidence(self):
        result = reading_from_parts([('We need to',.95),('leave',.3)],'test',12)
        self.assertEqual(result.text,'We need to leave')
        self.assertAlmostEqual(result.confidence,(10*.95+5*.3)/15)
        self.assertEqual(result.elapsed_ms,12)

    def test_engine_row_reader_preserves_scores_and_weak_words(self):
        box = np.array([[1,1],[150,1],[150,25],[1,25]])
        overlapping=np.array([[80,1],[190,1],[190,25],[80,25]])
        results = iter([SimpleNamespace(txts=['We need','need to leave'],boxes=[box,overlapping],scores=[.9,.9]),
                        SimpleNamespace(txts=['We need to','leave'],scores=[.95,.3])])
        engine = Engine.__new__(Engine)
        engine.ocr_kind = 'subtitle'
        from subtitle_ocr import SubtitleReader
        engine.subtitle_reader=SubtitleReader()
        engine.cancelled = lambda:False
        engine.ocr = lambda *args,**kwargs:next(results)
        frame=np.zeros((40,250,3),dtype=np.uint8)
        frame[5:25,10:140]=255
        reading = engine.read(frame)
        self.assertEqual(reading.text,'We need to leave')
        self.assertAlmostEqual(reading.confidence,(10*.95+5*.3)/15)
        self.assertGreaterEqual(reading.elapsed_ms,0)
        self.assertEqual(reading.method,'subtitle/rows')

    def test_whole_caption_filter_preserves_short_speech_and_numbers(self):
        for text in ('No!','HELP','Wait.','Hello','We need to leave.','120'):
            self.assertTrue(readable_caption(text),text)
        for text in ('xQz TTT zz','###','QR PL NX'):
            self.assertFalse(readable_caption(text),text)
        self.assertEqual(reading_from_parts([('xQz TTT zz',.99)],'test',0).text,'')
        self.assertEqual(reading_from_parts([('QR PL NX',.99)],'hud',0,subtitle=False).text,'QR PL NX')

    def test_cached_gate_sample_never_counts_as_an_independent_vote(self):
        class Reader:
            calls=0
            def read(self,frame):
                self.calls+=1
                return Reading('We need to leave.',.94,'test',0)
        reader=Reader()
        gate=ChangeGate(clock=lambda:0)
        stable=StableText()
        frame=np.zeros((40,250,3),dtype=np.uint8)
        first=gate.read(reader,frame)
        self.assertIsNone(stable.observe(first.text,0,first.confidence,fresh=gate.fresh))
        for index in range(10):
            cached=gate.read(reader,frame)
            self.assertFalse(gate.fresh)
            self.assertIsNone(stable.observe(cached.text,index/100,cached.confidence,fresh=gate.fresh))
        self.assertEqual(reader.calls,1)
        second=gate.read(reader,frame,force=stable.pending)
        self.assertEqual(stable.observe(second.text,.2,second.confidence,fresh=gate.fresh),'We need to leave.')
        self.assertEqual(reader.calls,2)

    def test_confidence_unknown_needs_three_real_reads(self):
        stable=StableText()
        self.assertIsNone(stable.observe('Leave now.',0,None))
        self.assertIsNone(stable.observe('Leave now.',.1,None))
        self.assertEqual(stable.observe('Leave now.',.2,None),'Leave now.')

    def test_six_read_history_tolerates_intervening_unrelated_error(self):
        stable=StableText()
        self.assertIsNone(stable.observe('Leave now.',0,.9))
        self.assertIsNone(stable.observe('Unrelated error.',.1,.9))
        self.assertEqual(stable.observe('Leave now.',.2,.9),'Leave now.')
        for index in range(20):
            stable.observe('Leave now.',index+1,.9)
        self.assertLessEqual(len(stable.recent),6)

    def test_word_vote_recovers_majority_spelling_without_cutting_a_word(self):
        stable=StableText()
        correct='We need to leave before the guards return.'
        self.assertIsNone(stable.observe('We need to leavo before the guards return.',0,.6))
        self.assertIsNone(stable.observe(correct,.1,.6))
        self.assertEqual(stable.observe(correct,.2,.6),correct)

    def test_cached_visible_caption_keeps_blank_expiry_relative_to_disappearance(self):
        stable=StableText(blank_timeout=.8)
        stable.observe('Leave now.',0,.9)
        stable.observe('Leave now.',.1,.9)
        stable.observe('Leave now.',10,.9,fresh=False)
        self.assertIsNone(stable.observe('',10.1,0))
        self.assertEqual(stable.observe('',10.9,0,fresh=False),'')

    def test_changing_number_is_meaningful_and_blank_cache_expires(self):
        stable=StableText(blank_timeout=.8)
        stable.observe('Collect 120 coins.',0,.9)
        self.assertEqual(stable.observe('Collect 120 coins.',.1,.9),'Collect 120 coins.')
        self.assertIsNone(stable.observe('Collect 121 coins.',.2,.9))
        self.assertEqual(stable.observe('Collect 121 coins.',.3,.9),'Collect 121 coins.')
        self.assertIsNone(stable.observe('',.4,0))
        self.assertEqual(stable.observe('',1.2,0,fresh=False),'')

    def test_similar_typo_needs_dominant_repeated_evidence(self):
        stable=StableText()
        for index in range(2):
            stable.observe('We need to leave before the guards return.',index,.99)
        typo='We need to leave before the guords return.'
        self.assertIsNone(stable.observe(typo,2,.9))
        self.assertIsNone(stable.observe(typo,3,.9))
        self.assertEqual(stable.accepted,'We need to leave before the guards return.')
        self.assertEqual(stable.observe(typo,4,.9),typo)


if __name__=='__main__':
    unittest.main()
