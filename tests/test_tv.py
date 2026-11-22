import json
import sys
import unittest
import socket
from urllib.request import urlopen
from urllib.parse import quote
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tv import TV,MAX_WIRE_BYTES
from coordinates import NormalizedBox
from dialogue import MAX_CAPTION
from websockets.sync.client import connect
from websockets.exceptions import InvalidStatus


class TVTests(unittest.TestCase):
    def test_non_ascii_wrong_pairing_code_is_rejected_without_server_error(self):
        service=TV()
        service.start(host='127.0.0.1',ws_port=0,http_port=0)
        try:
            port=service.connection_info().ws_port
            for token in ('wrong','yanlış-ö','😀'):
                with self.subTest(token=token),self.assertRaises(InvalidStatus) as failure:
                    connect(f'ws://127.0.0.1:{port}/?token={quote(token)}')
                self.assertEqual(failure.exception.response.status_code,403)
            with connect(f'ws://127.0.0.1:{port}/?token={service.token}') as client:
                self.assertEqual(self.snapshot(client)[0]['type'],'clear')
        finally:
            service.close()

    def test_hud_geometry_long_text_test_caption_and_connection_state(self):
        service=TV()
        self.assertIsNone(service.connection_info())
        with self.assertRaises(ValueError):
            service.test_caption()
        service.start(host='127.0.0.1',ws_port=0,http_port=0)
        try:
            info=service.connection_info()
            self.assertEqual(info.clients,0)
            self.assertEqual(info.host,'127.0.0.1')
            with self.assertRaises(ValueError):
                service.test_caption()
            caption='Bu uzun altyazı kesilmeden korunmalıdır. '*30
            hud='Görevi tamamlamak için kapıyı aç. '*40
            box=NormalizedBox(.1,.2,.3,.1)
            service.publish(caption)
            service.publish_hud(hud,box)
            with connect(f'ws://127.0.0.1:{info.ws_port}/?token={service.token}') as client:
                subtitle,task=self.snapshot(client)
                self.assertEqual(subtitle['text'],caption)
                self.assertEqual(task['text'],hud)
                self.assertEqual(task['box'],box.as_dict())
                self.assertEqual(service.connection_info().clients,1)
                service.test_caption()
                subtitle,task=self.snapshot(client)
                self.assertEqual(subtitle['text'],'MOZKAN Live Sub bağlantısı hazır.')
                self.assertEqual(task['box'],box.as_dict())
                service.publish_hud('')
                _,task=self.snapshot(client)
                self.assertEqual(task['text'],'')
                self.assertIsNone(task['box'])
        finally:
            service.close()
        self.assertIsNone(service.connection_info())

    def test_invalid_publication_does_not_partially_replace_current_state(self):
        service=TV()
        service.start(host='127.0.0.1',ws_port=0,http_port=0)
        service.publish('Geçerli altyazı')
        service.publish_hud('Geçerli görev',NormalizedBox(.1,.2,.3,.1))
        try:
            invalid=[lambda:service.publish('x'*(MAX_CAPTION+1)),
                     lambda:service.publish('\ud800'),
                     lambda:service.publish('Geçerli altyazı',dict(current=dict(text='Başka satır'))),
                     lambda:service.publish('Geçerli altyazı',dict(current=dict(text='Geçerli altyazı'),unexpected=[])),
                     lambda:service.publish_hud('x'*(MAX_CAPTION+1)),
                     lambda:service.publish_hud('Yeni görev',dict(x=.1,y=.2,w=.3,h=.1))]
            for operation in invalid:
                with self.assertRaises(ValueError):
                    operation()
            info=service.connection_info()
            with connect(f'ws://127.0.0.1:{info.ws_port}/?token={service.token}') as client:
                subtitle,task=self.snapshot(client)
            self.assertEqual(subtitle['text'],'Geçerli altyazı')
            self.assertEqual(task['text'],'Geçerli görev')
            self.assertEqual(task['box'],dict(x=.1,y=.2,w=.3,h=.1))
        finally:
            service.close()

    def test_maximum_json_expansion_is_bounded_and_never_truncated(self):
        text='\x01'*MAX_CAPTION
        stack=dict(current=dict(speaker='',text=text),previous=dict(speaker='S'*46,text=text))
        service=TV()
        service.publish(text,stack)
        stack['current']['text']='external mutation'
        service.start(host='127.0.0.1',ws_port=0,http_port=0)
        try:
            info=service.connection_info()
            with connect(f'ws://127.0.0.1:{info.ws_port}/?token={service.token}') as client:
                raw=client.recv(timeout=3)
                client.recv(timeout=3)
            self.assertLessEqual(len(raw.encode('utf-8')),MAX_WIRE_BYTES)
            payload=json.loads(raw)
            self.assertEqual(payload['text'],text)
            self.assertEqual(payload['stack']['current']['text'],text)
            self.assertEqual(payload['stack']['previous']['text'],text)
        finally:
            service.close()

    def test_failed_bind_releases_http_socket(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            service = TV()
            with self.assertRaises(OSError):
                service.start(host='127.0.0.1', ws_port=occupied.getsockname()[1], http_port=0)
            self.assertEqual(service.http.socket.fileno(), -1)
            self.assertFalse(service.threads)
            service.close()

    @staticmethod
    def snapshot(client):
        subtitle = json.loads(client.recv(timeout=3))
        hud = json.loads(client.recv(timeout=3))
        return subtitle, hud

    def test_auth_subtitle_clear_and_cleanup(self):
        service = TV()
        service.start(host='127.0.0.1', ws_port=0, http_port=0)
        port = service.ws.socket.getsockname()[1]
        try:
            http_port = service.http.server_address[1]
            with urlopen(f'http://127.0.0.1:{http_port}/duplay.json', timeout=3) as response:
                discovery = json.load(response)
            self.assertEqual(discovery['token'], service.token)
            self.assertEqual(discovery['port'], port)
            with self.assertRaises(InvalidStatus):
                connect(f'ws://127.0.0.1:{port}/?token=wrong')
            with connect(f'ws://127.0.0.1:{port}/?token={service.token}') as client:
                initial, _ = self.snapshot(client)
                self.assertEqual(initial['type'], 'clear')
                service.publish('Merhaba')
                message, _ = self.snapshot(client)
                self.assertEqual(message['text'], 'Merhaba')
                service.publish('')
                self.assertEqual(self.snapshot(client)[0]['type'], 'clear')
                service.publish_hud('Anahtarı bul')
                _, hud = self.snapshot(client)
                self.assertEqual(hud['type'], 'hud')
                self.assertEqual(hud['text'], 'Anahtarı bul')
        finally:
            service.close()
        self.assertFalse(service.threads)

    def test_discovery_hides_pairing_code_outside_pairing_window(self):
        now = [100.0]
        service = TV(clock=lambda: now[0])
        service.start(host='127.0.0.1', ws_port=0, http_port=0)
        url = f'http://127.0.0.1:{service.http.server_address[1]}/duplay.json'
        def discover():
            with urlopen(url, timeout=3) as response:
                return json.load(response)
        try:
            self.assertEqual(discover()['token'], service.token)
            now[0] += 121
            self.assertNotIn('token', discover())
            self.assertEqual(service.pairing_remaining(), 0)
            service.open_pairing(30)
            self.assertEqual(discover()['token'], service.token)
            service.close_pairing()
            closed = discover()
            self.assertNotIn('token', closed)
            self.assertEqual(closed['port'], service.ws.socket.getsockname()[1])
            with urlopen(f'http://127.0.0.1:{service.http.server_address[1]}/', timeout=3) as response:
                self.assertIsNone(response.headers.get('Access-Control-Allow-Origin'))
            with self.assertRaises(ValueError):
                service.open_pairing(0)
        finally:
            service.close()

    def test_reconnect_preserves_dialogue_hud_and_remaining_ttl(self):
        now = [100.0]
        service = TV(clock=lambda: now[0])
        stack = dict(current=dict(speaker='John', text='Merhaba'), previous={})
        service.publish('John: Merhaba', stack)
        service.publish_hud('Kapıyı aç')
        stack['current']['text'] = 'external mutation'
        service.start(host='127.0.0.1', ws_port=0, http_port=0)
        uri = f'ws://127.0.0.1:{service.ws.socket.getsockname()[1]}/?token={service.token}'
        try:
            now[0] = 105
            with connect(uri) as client:
                subtitle, hud = self.snapshot(client)
                self.assertEqual(subtitle['ttl_ms'], 6000)
                self.assertEqual(subtitle['stack']['current']['text'], 'Merhaba')
                self.assertEqual(hud['text'], 'Kapıyı aç')
            now[0] = 112
            with connect(uri) as client:
                subtitle, hud = self.snapshot(client)
                self.assertEqual(subtitle['type'], 'clear')
                self.assertNotIn('stack', subtitle)
                self.assertEqual(hud['text'], 'Kapıyı aç')
        finally:
            service.close()
        self.assertFalse(service.clients)
