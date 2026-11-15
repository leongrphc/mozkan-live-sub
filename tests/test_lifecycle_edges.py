"""Cancellation and cleanup regressions at the actual producer/server boundaries."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import queue
import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import numpy as np
from recognition import Reading
from capture import run_capture
from tv import TV
from main import QApplication, Window
from websockets.sync.server import ServerConnection


class CaptureCancellationEdges(unittest.TestCase):
    def test_stop_during_ocr_does_not_start_a_new_translation(self):
        waiting = threading.Event()
        stop = threading.Event()
        translations, errors = [], []

        class WaitingQueue(queue.Queue):
            def get(self, *args, **kwargs):
                waiting.set()
                return super().get(*args, **kwargs)

        class Reader:
            def __init__(self, *args, **kwargs):
                self.reads = 0

            def read(self, frame):
                if not waiting.wait(3):
                    raise TimeoutError('translation child did not enter its queue')
                self.reads += 1
                if self.reads == 2:
                    stop.set()
                return Reading('Hello',1.0,'test',0.0)

            def translate(self, text, *, can_infer=None):
                translations.append((text, stop.is_set()))
                return 'Merhaba'

        frames = [np.zeros((80, 200, 3), dtype=np.uint8),
                  np.full((80, 200, 3), 255, dtype=np.uint8)]
        with patch('capture.queue.Queue', WaitingQueue):
            run_capture(Path('.'), (0, 0, 200, 80), stop,
                        lambda *args: None, lambda text: None, errors.append,
                        engine_factory=Reader, frames=frames, interval=.01)
        self.assertEqual(errors, [])
        self.assertTrue(stop.is_set())
        self.assertEqual(translations, [])


class TVCleanupEdges(unittest.TestCase):
    def test_close_releases_a_websocket_still_waiting_for_handshake(self):
        entered = threading.Event()
        acquired_threads = []

        class ReadyConnection(ServerConnection):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                acquired_threads.append(threading.current_thread())
                entered.set()

        service = TV()
        close_thread = None
        client = None
        # Use the library's normal transport with a readiness handshake, rather
        # than timing the operating system's accept queue with a sleep.
        with patch('websockets.sync.server.ServerConnection', ReadyConnection):
            service.start(host='127.0.0.1', ws_port=0, http_port=0)
            try:
                client = socket.create_connection(
                    ('127.0.0.1', service.ws.socket.getsockname()[1]), timeout=3)
                self.assertTrue(entered.wait(3), 'WebSocket transport was not acquired')
                # No upgrade request is sent. It cannot enter TV.clients yet.
                self.assertFalse(service.clients)
                close_thread = threading.Thread(target=service.close, daemon=True)
                close_thread.start()
                close_thread.join(3)
                self.assertFalse(close_thread.is_alive(), 'TV.close did not finish pre-handshake cleanup')
                client.settimeout(.3)
                try:
                    self.assertEqual(client.recv(1), b'')
                except ConnectionResetError:
                    pass
            finally:
                if client:
                    client.close()
                for handler in acquired_threads:
                    handler.join(3)
                if close_thread:
                    close_thread.join(3)
                if close_thread is None or not close_thread.is_alive():
                    service.close()

    def test_close_releases_an_incomplete_http_request(self):
        service = TV()
        service.start(host='127.0.0.1', ws_port=0, http_port=0)
        entered = threading.Event()
        handlers = []
        original = service.http.process_request_thread

        def tracked(request, address):
            handlers.append(threading.current_thread())
            entered.set()
            return original(request, address)

        service.http.process_request_thread = tracked
        client = socket.create_connection(('127.0.0.1', service.http.server_address[1]), timeout=3)
        close_thread = None
        try:
            self.assertTrue(entered.wait(3), 'request handler was not acquired')
            # Deliberately send no HTTP headers: cleanup must own this accepted
            # socket as well as the listening socket.
            close_thread = threading.Thread(target=service.close, daemon=True)
            close_thread.start()
            close_thread.join(3)
            self.assertFalse(close_thread.is_alive(), 'TV.close did not complete')
            client.settimeout(.3)
            try:
                self.assertEqual(client.recv(1), b'')
            except ConnectionResetError:
                pass
            for handler in handlers:
                handler.join(.5)
                self.assertFalse(handler.is_alive(), 'HTTP request handler outlived TV.close')
        finally:
            client.close()
            if close_thread:
                close_thread.join(3)
            if close_thread is None or not close_thread.is_alive():
                service.close()


class TVCleanupOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for_cleanup(self, window):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.app.processEvents()
            thread = window.tv_cleanup
            if thread is None or not thread.is_alive():
                self.app.processEvents()
                return
            thread.join(.02)
        self.fail('TV cleanup did not settle')

    def test_failed_tv_close_keeps_owner_and_can_be_retried(self):
        class Service:
            attempts = 0

            def connection_info(self):
                return None

            def close(self):
                self.attempts += 1
                if self.attempts == 1:
                    raise OSError('test cleanup failure; listener still owned')

            def publish(self, *args):
                pass

            def publish_hud(self, *args):
                pass

        window = Window(Path('models'))
        service = Service()
        window.tv = service
        try:
            window.stop_tv()
            self.wait_for_cleanup(window)
            self.assertIs(window.tv, service, 'failed cleanup discarded its service owner')
            window.stop_tv()
            self.wait_for_cleanup(window)
            self.assertEqual(service.attempts, 2)
            self.assertIsNone(window.tv)
        finally:
            # The fake owns no sockets; avoid introducing a deliberate cleanup
            # failure into window shutdown if the assertion failed early.
            window.tv = None
            window.close()
