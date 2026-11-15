"""Real blocked WebSocket write: shutdown must interrupt its owned socket."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--observe',action='store_true')
parser.add_argument('--installation',type=Path,default=ROOT)
args=parser.parse_args()
INSTALLATION=args.installation.resolve(strict=True)
sys.path.insert(0,str(INSTALLATION/'src'))
from tv import TV
from dialogue import MAX_CAPTION
from websockets.sync.server import ServerConnection
source_digest=hashlib.sha256((INSTALLATION/'src/tv.py').read_bytes()).hexdigest()
entered,finished=threading.Event(),threading.Event()
progress=threading.Condition()
writes=[0,0]
errors=[]
send_errors=[]
class TrackedConnection(ServerConnection):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,4096)
    def send(self,message,*args,**kwargs):
        if len(message)>100000:
            entered.set()
        with progress:
            writes[0]+=1
            progress.notify_all()
        try:
            return super().send(message,*args,**kwargs)
        except Exception as exc:
            send_errors.append(repr(exc))
            raise
        finally:
            finished.set()
            with progress:
                writes[1]+=1
                progress.notify_all()

service=TV()
text='\x01'*MAX_CAPTION
service.publish(text,dict(current=dict(speaker='',text=text),previous=dict(speaker='',text=text)))
client=socket.socket()
client.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024)
client.settimeout(3)
closer=None
blocked=False
started=time.perf_counter()
with patch('websockets.sync.server.ServerConnection',TrackedConnection):
    try:
        service.start(host='127.0.0.1',ws_port=0,http_port=0)
        info=service.connection_info()
        client.connect(('127.0.0.1',info.ws_port))
        key=base64.b64encode(os.urandom(16)).decode('ascii')
        # No compression extension: exercise the full bounded JSON expansion.
        request=(f'GET /?token={service.token} HTTP/1.1\r\nHost: 127.0.0.1:{info.ws_port}\r\n'
                 f'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n')
        client.sendall(request.encode('ascii'))
        response=b''
        while not response.endswith(b'\r\n\r\n') and len(response)<4096:
            response+=client.recv(1)
        assert response.startswith(b'HTTP/1.1 101 '),response
        assert entered.wait(3),'Large frame write did not start'
        pressured=False
        # Windows loopback may acknowledge a full bounded message into a large
        # kernel receive queue. Feed at most128 completed frames (~19MiB) until
        # a real send remains pending; publication itself never queues frames.
        for _ in range(128):
            with progress:
                expected=writes[0]
                if not progress.wait_for(lambda:writes[1]>=expected,timeout=.1):
                    pressured=True
                    break
            service.publish(text,dict(current=dict(speaker='',text=text),previous=dict(speaker='',text=text)))
            with progress:
                assert progress.wait_for(lambda:writes[0]>expected,timeout=3),('Next large frame did not start',writes,send_errors,service.connection_info())
        assert pressured,'Test transport did not create backpressure within128 bounded frames'
        def close():
            try:
                service.close()
            except Exception as exc:
                errors.append(str(exc))
        closer=threading.Thread(target=close,daemon=True)
        close_started=time.perf_counter()
        closer.start()
        closer.join(3)
        elapsed=time.perf_counter()-close_started
        blocked=closer.is_alive()
    finally:
        # Always recover this test's own connection, including the known-bad
        # baseline, so an observation never leaves a background server behind.
        client.close()
        with service.condition:
            owned=tuple(service.ws_raw)
        for request in owned:
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if closer:
            closer.join(5)
            assert not closer.is_alive(),'Test cleanup did not finish'
        service.close()
assert hashlib.sha256((INSTALLATION/'src/tv.py').read_bytes()).hexdigest()==source_digest
report=dict(status='BLOCKED' if blocked else 'PASS',installation=str(INSTALLATION),close_seconds=elapsed,
            total_seconds=time.perf_counter()-started,close_errors=errors,write_finished=finished.is_set(),
            remaining_server_threads=len(service.threads),remaining_socket_owners=len(service.ws_raw),
            writes_started=writes[0],writes_finished=writes[1],
            source_sha256=source_digest,
            scope='Actual loopback uncompressed WebSocket/TCP backpressure, bounded full-size caption frame; no physical device.',
            costs='Elapsed only; CPU, peak process-family memory and tokens unmeasured.')
print(json.dumps(report))
if not args.observe:
    assert not blocked and not errors,report
