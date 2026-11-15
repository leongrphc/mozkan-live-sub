import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from dialogue import (CaptionStack,CaptionSelector,Caption,newest_caption,render_stack,
                      ensure_speaker,split_speaker,parse_caption)


NEWEST_CASES = [
    ('empty','','',''),
    ('plain','Leave now.','','Leave now.'),
    ('two-speakers','PRICE: Stay here. GHOST: Follow me.','','GHOST: Follow me.'),
    ('known-title-case','Price: Stay here. Ghost: Follow me.','','Ghost: Follow me.'),
    ('unknown-uppercase','ROBOT: Stay here. PILOT: Follow me.','','PILOT: Follow me.'),
    ('same-speaker-append','PRICE: Stay here. Follow me.','PRICE: Stay here.','PRICE: Follow me.'),
    ('unlabelled-append','Stay here. Follow me.','Stay here.','Follow me.'),
    ('incomplete-growth','We need to leave before sunrise.','We need to leave','We need to leave before sunrise.'),
    ('no-suffix-for-different','Follow me.','Stay here.','Follow me.'),
    ('empty-label','PRICE:','',''),
    ('title-label','John: Stay here.','','John: Stay here.'),
    ('spaces','  PRICE:   Stay   here.  GHOST: Follow me.  ','','GHOST: Follow me.'),
    ('punctuation-suffix','Move now! Take cover.','Move now.','Take cover.'),
    ('named-punctuation-suffix','PRICE: Move now! Take cover.','PRICE: Move now.','PRICE: Take cover.'),
    ('short-command','PRICE: Go!','','PRICE: Go!'),
    ('short-appended-command','PRICE: Wait. Go!','PRICE: Wait.','PRICE: Go!'),
]
STACK_CASES = [
    ('two-speakers',['PRICE: Bekle.','GHOST: İlerle.']),
    ('duplicate',['PRICE: Bekle.','PRICE: BEKLE!']),
    ('growing',['PRICE: Burada bekle','PRICE: Burada bekle ve işaretimi izle.']),
    ('three-turns',['PRICE: Bekle.','GHOST: İlerle.','SOAP: Geliyorum.']),
    ('empty-between',['PRICE: Bekle.','','GHOST: İlerle.']),
    ('long-growth',['PRICE: Burada bekle','PRICE: Burada bekle ve yeni gelen birliklerin sokağın diğer ucuna ulaşmasını dikkatle izle.']),
    ('numbers',['PRICE: Collect exactly 120 coins before the guards return.','PRICE: Collect exactly 121 coins before the guards return.']),
]


class DialogueTests(unittest.TestCase):
    def test_newest_fixtures_include_short_commands_and_punctuation_recovery(self):
        for name,raw,previous,expected in NEWEST_CASES:
            with self.subTest(name=name):
                self.assertEqual(newest_caption(raw,previous),expected)

    def test_duplicate_and_growing_sentence_do_not_move_partial_line_to_previous(self):
        stack=CaptionStack()
        self.assertTrue(stack.add('PRICE: Burada bekle'))
        self.assertFalse(stack.add('PRICE: BURADA BEKLE!'))
        self.assertTrue(stack.add('PRICE: Burada bekle ve işaretimi izle.'))
        self.assertEqual(stack.previous,Caption())
        self.assertEqual(stack.current.body,'Burada bekle ve işaretimi izle.')
        self.assertTrue(stack.add('GHOST: İlerliyorum.'))
        self.assertEqual(stack.previous.body,'Burada bekle ve işaretimi izle.')
        self.assertEqual(stack.current.speaker,'GHOST')

    def test_meaningful_number_change_is_not_fuzzy_duplicate(self):
        stack=CaptionStack()
        old,new=STACK_CASES[-1][1]
        stack.add(old)
        self.assertTrue(stack.add(new))
        self.assertEqual(stack.previous.full,old)
        self.assertEqual(stack.current.full,new)

    def test_source_label_is_preserved_without_duplicate_or_guessed_speaker(self):
        self.assertEqual(ensure_speaker('PRICE: Wait.','Bekle.'),'PRICE: Bekle.')
        self.assertEqual(ensure_speaker('PRICE: Wait.','PRICE: Bekle.'),'PRICE: Bekle.')
        self.assertEqual(ensure_speaker('What if: we leave?','Ya gidersek?'),'Ya gidersek?')
        self.assertEqual(split_speaker('mission: start'),('','mission: start'))
        self.assertEqual(split_speaker('ED THATCH: Git.'),('ED THATCH','Git.'))

    def test_selector_does_not_replay_combined_caption_on_periodic_ocr(self):
        selector=CaptionSelector()
        self.assertEqual(selector.select('PRICE: Wait here.',''),'PRICE: Wait here.')
        self.assertEqual(selector.select('PRICE: Wait here. Move now.','PRICE: Wait here.'),'PRICE: Move now.')
        for _ in range(20):
            self.assertEqual(selector.select('PRICE: Wait here. Move now.','PRICE: Move now.'),'PRICE: Move now.')
        self.assertEqual(selector.select('','PRICE: Move now.'),'')
        self.assertEqual(selector.select('PRICE: Wait here.',''),'PRICE: Wait here.')

    def test_snapshot_and_rendering_share_owned_logical_captions(self):
        stack=CaptionStack()
        stack.add('PRICE: <img src=x>')
        stack.add('GHOST: Gel.')
        snapshot=stack.as_dict()
        snapshot['current']['text']='changed'
        self.assertEqual(stack.current.body,'Gel.')
        self.assertEqual(stack.as_dict(False)['previous'],dict(speaker='',text=''))
        rendered=render_stack(stack,True,24)
        self.assertIn('&lt;img src=x&gt;',rendered)
        self.assertNotIn('<img',rendered)
        self.assertIn('#26E6DC',rendered)
        self.assertIn('#80BEFA',rendered)
        self.assertIn('21pt',rendered)
        self.assertNotIn('img',render_stack(stack,False,24))
        stack.clear()
        self.assertEqual(render_stack(stack),'')

    def test_boundary_rejects_oversized_input_before_parsing(self):
        with self.assertRaises(ValueError):
            parse_caption('a'*8193)
        with self.assertRaises(ValueError):
            newest_caption('a'*8193)


if __name__=='__main__':
    unittest.main()
