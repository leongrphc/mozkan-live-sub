"""Window.begin -> real capture/control/queue -> GUI/overlay -> loopback TV."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from main import QApplication,Window
from capture import run_capture
from recognition import Reading
from settings import Settings
from tv import TV
from websockets.sync.client import connect


class DialogueFlowTests(unittest.TestCase):
    def test_current_selection_history_toggle_periodic_read_clear_and_tv(self):
        app=QApplication.instance() or QApplication([])
        advance,blank=threading.Event(),threading.Event()
        translations,errors=[],[]
        reads=[0]
        class Engine:
            def __init__(self,*args,**kwargs):
                self.hud=kwargs.get('ocr_kind')=='hud'
            def prepare_translation(self):pass
            def read(self,frame):
                if self.hud:
                    return Reading('Find key',.99,'test',0)
                reads[0]+=1
                value=int(frame[0,0,0])
                text= '' if value==100 else 'PRICE: Wait here.' if value==0 else 'PRICE: Wait here. GHOST: Move now.'
                return Reading(text,.99,'test',0)
            def translate(self,text,*,can_infer=None):
                if self.hud:
                    return 'Mavi anahtarı bul'
                translations.append(text)
                return {'PRICE: Wait here.':'Burada bekle.','GHOST: Move now.':'Şimdi ilerle.'}[text]
        frames_by_stage=[np.full((50,500,3),value,dtype=np.uint8) for value in (0,255,100)]
        def frames():
            while True:
                yield frames_by_stage[2 if blank.is_set() else 1 if advance.is_set() else 0]
        def pipeline(*args,**kwargs):
            kwargs.update(frames=frames(),engine_factory=Engine,interval=.01)
            return run_capture(*args,**kwargs)
        def until(predicate,timeout=5):
            deadline=time.monotonic()+timeout
            while not predicate() and time.monotonic()<deadline:
                app.processEvents()
                time.sleep(.005)
            self.assertTrue(predicate(),'GUI pipeline condition timed out')
        service=TV()
        service.start(host='127.0.0.1',ws_port=0,http_port=0)
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Path('models'),settings=Settings(Path(folder)/'settings.json'))
            window.events.error.connect(errors.append)
            window.caption_mode.setCurrentIndex(window.caption_mode.findData('dialogue'))
            window.dialogue.setChecked(True)
            screen=app.primaryScreen().availableGeometry()
            window.chosen((screen.x()+100,screen.y()+400,500,50))
            window.chosen_hud((screen.x()+100,screen.y()+200,200,50))
            def snapshot(include_hud=False):
                uri=f'ws://127.0.0.1:{service.ws.socket.getsockname()[1]}/?token={service.token}'
                with connect(uri) as client:
                    subtitle=json.loads(client.recv(timeout=3))
                    task=json.loads(client.recv(timeout=3))
                    return (subtitle,task) if include_hud else subtitle
            try:
                with patch('main.run_capture',side_effect=pipeline),patch('main.capture_region',side_effect=lambda region,screens:region):
                    window.begin()
                    until(lambda:window.target.toPlainText()=='PRICE: Burada bekle.' and window.current_hud=='Mavi anahtarı bul')
                    # Opening TV after the caption was accepted must publish
                    # current logical state without waiting for another caption.
                    with patch('main.TV',return_value=service),patch.object(service,'start'):
                        window.toggle_tv()
                    initial,task=snapshot(True)
                    self.assertEqual(initial['stack']['current']['speaker'],'PRICE')
                    self.assertEqual(task['text'],'Mavi anahtarı bul')
                    self.assertIsNotNone(task['box'])
                    self.assertTrue(all(0<=value<=1 for value in task['box'].values()))
                    clipboard=Mock()
                    with patch('main.QApplication.clipboard',return_value=clipboard):
                        window.copy_tv_code()
                        clipboard.setText.assert_called_with(service.token)
                        window.copy_tv_address()
                        clipboard.setText.assert_called_with(f'http://127.0.0.1:{service.connection_info().http_port}')
                    uri=f'ws://127.0.0.1:{service.connection_info().ws_port}/?token={service.token}'
                    with connect(uri) as client:
                        client.recv(timeout=3);client.recv(timeout=3)
                        window.poll()
                        self.assertTrue(window.tv_test.isEnabled())
                        window.test_tv_caption()
                        self.assertEqual(json.loads(client.recv(timeout=3))['text'],'Altyazı Atölyesi bağlantısı hazır.')
                        client.recv(timeout=3)
                    self.assertFalse(window.caption_mode.isEnabled())
                    advance.set()
                    until(lambda:window.target.toPlainText()=='GHOST: Şimdi ilerle.')
                    current=snapshot()
                    self.assertEqual(current['stack']['previous']['speaker'],'PRICE')
                    self.assertEqual(current['stack']['current']['text'],'Şimdi ilerle.')
                    self.assertEqual(window.captions.previous.full,'PRICE: Burada bekle.')
                    # A periodic real OCR of the same combined source must not
                    # translate the old sentence plus new sentence a second time.
                    before=reads[0]
                    until(lambda:reads[0]>before,timeout=3)
                    app.processEvents()
                    self.assertEqual(translations,['PRICE: Wait here.','GHOST: Move now.'])
                    window.dialogue.setChecked(False)
                    self.assertEqual(snapshot()['stack']['previous'],dict(speaker='',text=''))
                    self.assertEqual(window.captions.previous.full,'PRICE: Burada bekle.')
                    window.dialogue.setChecked(True)
                    self.assertEqual(snapshot()['stack']['previous']['speaker'],'PRICE')
                    blank.set()
                    until(lambda:window.target.toPlainText()=='',timeout=3)
                    self.assertEqual(window.captions.current.body,'')
                    self.assertEqual(snapshot()['type'],'clear')
                    self.assertFalse(window.overlay.isVisible())
                    self.assertEqual(errors,[])
                    window.halt()
                    window.worker.join(3)
                    self.assertFalse(window.worker.is_alive())
            finally:
                window.stop_event.set()
                if window.worker:
                    window.worker.join(5)
                window.tv=None
                service.close()
                window.close()


if __name__=='__main__':
    unittest.main()
