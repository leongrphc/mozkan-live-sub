import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from collections import OrderedDict
from pathlib import Path
import sys
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QImage
from PySide6.QtCore import QRect
from hud import compose,translate_marked,render_html,BADGES
from recognition import Word,Badge,spatial_parts
from engine import Engine,InferenceCancelled
from overlay import HudOverlay
from stability import StableText
from capture import run_capture


class HudTests(unittest.TestCase):
    def test_compose_keeps_badge_reading_order_removes_edge_counter_and_duplicate(self):
        words=[Word('3',0,20,10,20),Word('Hold',50,20,45,20),Word('R8',110,20,25,20),
               Word('to',155,20,15,20),Word('open',180,20,40,20),Word('the',230,20,25,20),Word('door',265,20,40,20),
               Word('.',307,20,3,20)]
        self.assertEqual(compose(words,[Badge('RB',102,5,42,30)]),'Hold {{RB}} to open the door.')
        wrapped=[Word('Hold',50,20,45,20),Word('(LT)',110,20,25,20),Word('to open the door.',155,20,150,20)]
        self.assertEqual(compose(wrapped,[Badge('LT',102,5,42,30)]),'Hold {{LT}} to open the door.')
        self.assertEqual(compose([Word('A',0,20,15,20),Word('door',25,20,40,20)],[]),'A door')
        self.assertEqual(compose([Word('L1',0,20,20,20),Word('Open',30,20,40,20),Word('door',80,20,40,20)],[]),'{{L1}} Open door')
        self.assertEqual(compose([], [Badge('X',0,0,30,30)]),'')

    def test_translation_retains_missing_doubled_and_reordered_markers(self):
        for model in (lambda text:text.replace('Hold','Tut'),lambda text:'işaret kayboldu',lambda text:'[RB] [RB] iki kez'):
            calls=[]
            def translate(text):
                calls.append(text)
                return model(text)
            output=translate_marked(translate,'Hold {{RB}} to open the door.')
            self.assertEqual(output.count('{{RB}}'),1)
            self.assertNotIn('[RB]',output)
            self.assertTrue(calls)
        self.assertEqual(translate_marked(lambda text:'[A] sonra [B]', 'Press {{B}} then {{A}}.'),'{{A}} sonra {{B}}')

    def test_word_geometry_falls_back_whole_line_when_word_coverage_is_malformed(self):
        box=np.array([[10,10],[120,10],[120,30],[10,30]])
        output=SimpleNamespace(word_results=[('malformed',)],txts=['Open the door.'],scores=[.7],boxes=[box])
        words=spatial_parts(output,200,80)
        self.assertEqual(len(words),1)
        self.assertEqual(words[0].text,'Open the door.')
        self.assertEqual(words[0].level,'line')
        output.word_results=[(('Open',float('nan'),box),)]
        word=spatial_parts(output,200,80)[0]
        self.assertEqual(word.level,'word')
        self.assertIsNone(word.confidence)

    def test_changing_controller_button_is_not_typo_or_plain_article(self):
        stable=StableText()
        for index in range(2):
            stable.observe('Press {{A}} to continue.',index,.99)
        self.assertIsNone(stable.observe('Press {{B}} to continue.',2,.99))
        self.assertEqual(stable.observe('Press {{B}} to continue.',3,.99),'Press {{B}} to continue.')
        self.assertNotEqual(stable.key('A door'),stable.key('{{A}} door'))
        self.assertNotEqual(stable.key('controlbuttonA'),stable.key('{{A}}'))

    def test_cancelled_marker_recovery_does_not_start_second_inference_or_cache_partial_text(self):
        allowed=[True]
        engine=Engine.__new__(Engine)
        engine._translation_prepared=True
        engine.profile=None;engine.ocr_kind='hud';engine.cancelled=lambda:False;engine.cache=OrderedDict()
        tokenizer=SimpleNamespace(encode=lambda text,**kwargs:[text],convert_ids_to_tokens=lambda ids:ids,
                                  convert_tokens_to_ids=lambda words:words,decode=lambda words,**kwargs:' '.join(words))
        calls=[]
        def translate_batch(chunks,**kwargs):
            calls.append(chunks)
            allowed[0]=False
            return [SimpleNamespace(hypotheses=[['Dropped mark']])]
        engine.tokenizer=tokenizer;engine.translator=SimpleNamespace(translate_batch=translate_batch)
        with self.assertRaises(InferenceCancelled):
            engine.translate('Hold {{RB}} to open the door.',can_infer=lambda:allowed[0])
        self.assertEqual(len(calls),1)
        self.assertEqual(engine.cache,{})

    def test_stop_during_profile_load_prevents_engine_acquisition(self):
        stop=threading.Event()
        factory=Mock()
        def load(path):
            stop.set()
            return object()
        errors=[]
        with patch('capture.GameProfile',side_effect=load):
            run_capture(Path('.'),(0,0,100,50),stop,lambda *args:None,lambda _:None,errors.append,
                        profile_path='fixture.sqlite',engine_factory=factory,frames=[])
        factory.assert_not_called()
        self.assertEqual(errors,[])

    def test_stop_after_word_ocr_prevents_badge_recognition_inference(self):
        from hud_fixtures import fixtures
        image=next(image for name,image in fixtures() if name=='shoulder')
        frame=np.asarray(image)[:,:,::-1].copy()
        stopped=[False]
        calls=[]
        def box(x,w):
            return np.array([[x,42],[x+w,42],[x+w,82],[x,82]])
        output=SimpleNamespace(txts=['Hold RB to open the door.'],boxes=[box(20,500)],scores=[.99],
            word_results=[(('Hold',.99,box(20,65)),('RB',.99,box(110,48)),('to open the door.',.99,box(180,250)))])
        def ocr(*args,**kwargs):
            calls.append(kwargs)
            stopped[0]=True
            return output
        engine=Engine.__new__(Engine)
        engine._translation_prepared=True
        engine.ocr_kind='hud';engine.cancelled=lambda:stopped[0];engine.ocr=ocr
        with self.assertRaises(InferenceCancelled):
            engine.read(frame)
        self.assertEqual(len(calls),1)

    def test_fitted_word_boxes_map_back_to_original_source_pixels(self):
        box=np.array([[75,60],[105,60],[105,90],[75,90]])
        output=SimpleNamespace(txts=['Open door'],boxes=[box],scores=[.99],
                               word_results=[(('Open door',.99,box),)])
        engine=Engine.__new__(Engine)
        engine._translation_prepared=True
        engine.ocr_kind='hud';engine.cancelled=lambda:False;engine.ocr=lambda *args,**kwargs:output
        reading=engine.read(np.zeros((260,1280,3),dtype=np.uint8))
        self.assertEqual(reading.words[0].x,100)
        self.assertEqual(reading.words[0].y,100)
        self.assertEqual(reading.words[0].w,40)
        self.assertEqual(reading.words[0].h,40)
        self.assertEqual(reading.words[0].level,'word')

    def test_badge_html_keeps_unknown_marks_and_escapes_external_html(self):
        rendered=render_html('<img src=file:///secret> {{RB}} {{UNKNOWN}}',24)
        self.assertIn('&lt;img',rendered)
        self.assertIn('src="badge:RB"',rendered)
        self.assertIn('{{UNKNOWN}}',rendered)


class HudPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')

    def test_badges_render_locally_and_independent_offset_scale_stays_safe(self):
        overlay=HudOverlay()
        region=(100,250,400,60)
        try:
            self.assertTrue(overlay.present('Bas {{RB}} sonra {{SQR}} {{TRI}} {{CIR}} {{CRO}} {{VIEW}} {{MENU}}',region),overlay.last_error)
            image=overlay.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
            pixels=np.frombuffer(bytes(image.bits()),dtype='uint8').reshape(image.height(),image.bytesPerLine()//4,4)
            self.assertGreater(np.count_nonzero((pixels[:,:,0]>150)&(pixels[:,:,2]>120)&(pixels[:,:,3]>200)),5)
            first=overlay.geometry()
            with patch('overlay.try_capture_exclusion',return_value=True):
                overlay.configure_layout(x_offset=2,y_offset=1,scale=100)
            self.assertEqual(overlay.x(),first.x()+20)
            self.assertEqual(overlay.y(),first.y()-10)
            overlay.configure_layout(x_offset=0,y_offset=0,scale=150)
            self.assertGreater(overlay.width(),first.width())
            area=self.app.primaryScreen().availableGeometry()
            self.assertTrue(area.contains(overlay.geometry()))
            with self.assertRaises(ValueError):
                overlay.configure_layout(x_offset=0,y_offset=0,scale=151)
        finally:
            overlay.close()

    def test_hud_offset_cannot_overlap_capture_when_exclusion_is_unavailable(self):
        overlay=HudOverlay()
        try:
            with patch('overlay.try_capture_exclusion',return_value=False):
                self.assertTrue(overlay.present('Hold {{RB}}',(100,250,400,60)))
                overlay.configure_layout(x_offset=0,y_offset=1,scale=100)
                self.assertFalse(overlay.isVisible())
                self.assertIsNotNone(overlay.last_error)
        finally:
            overlay.close()

    def test_hud_cannot_feed_translated_text_into_other_subtitle_capture(self):
        overlay=HudOverlay()
        overlay.other_capture_regions=(QRect(100,316,400,100),)
        try:
            with patch('overlay.try_capture_exclusion',return_value=False):
                self.assertFalse(overlay.present('Hold {{RB}}',(100,250,400,60)))
                self.assertFalse(overlay.isVisible())
            with patch('overlay.try_capture_exclusion',return_value=True):
                self.assertTrue(overlay.present('Hold {{RB}}',(100,250,400,60)))
        finally:
            overlay.close()


if __name__=='__main__':
    unittest.main()
