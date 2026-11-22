"""Local-network subtitle stream and browser receiver."""
import json
import ipaddress
import secrets
import threading
import time
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from websockets.protocol import State
from dataclasses import dataclass
from coordinates import NormalizedBox
from dialogue import MAX_CAPTION
from hud import BADGES

# Three caption strings (plain/current/previous), two short speaker labels,
# JSON keys and punctuation. Every Unicode/control character needs <=6 UTF-8
# bytes under ensure_ascii=False JSON encoding. No unbounded deep-copy input.
MAX_WIRE_BYTES=3*MAX_CAPTION*6+1024
# Automatic discovery hands the pairing code to any LAN peer that asks, so it
# is only answered inside a short, user-opened pairing window.
PAIRING_SECONDS=120


def _text(value,limit=MAX_CAPTION):
    if not isinstance(value,str) or len(value)>limit:
        raise ValueError(f'TV metni en fazla {limit} karakter olmalı.')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as exc:
        raise ValueError('TV metni geçerli Unicode olmalı.') from exc
    return value


def _stack(value,text):
    if value is None:
        return None
    if not isinstance(value,dict) or len(value)>2 or set(value)-{'previous','current'}:
        raise ValueError('TV diyalog yükü previous/current alanlarından oluşmalı.')
    result={}
    for slot in ('previous','current'):
        fields=value.get(slot,{})
        if not isinstance(fields,dict) or len(fields)>2 or set(fields)-{'speaker','text'}:
            raise ValueError('TV diyalog satırı speaker/text alanlarından oluşmalı.')
        result[slot]=dict(speaker=_text(fields.get('speaker',''),46),text=_text(fields.get('text','')))
    current=result['current']
    full=(current['speaker']+': ' if current['speaker'] else '')+current['text']
    if not text or full!=text:
        raise ValueError('TV düz metni güncel diyalog satırıyla aynı olmalı.')
    return result


@dataclass(frozen=True,slots=True)
class TVInfo:
    host: str
    http_port: int
    ws_port: int
    clients: int


class OwnedHTTPServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, *args, **kwargs):
        self.connections = set()
        self.connections_lock = threading.Lock()
        self.closing = False
        super().__init__(*args, **kwargs)

    def process_request(self, request, address):
        with self.connections_lock:
            rejected = self.closing or len(self.connections) >= 16
            if not rejected:
                self.connections.add(request)
        if rejected:
            self.shutdown_request(request)
            return
        try:
            request.settimeout(2)
            super().process_request(request, address)
        except BaseException:
            with self.connections_lock:
                self.connections.discard(request)
            self.shutdown_request(request)
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            with self.connections_lock:
                self.connections.discard(request)

    def close_connections(self):
        with self.connections_lock:
            self.closing = True
            requests = tuple(self.connections)
        for request in requests:
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # Already closed/unconnected sockets still get close().
            request.close()

PAGE = r'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MOZKAN Live Sub · TV</title>
<style>body{margin:0;background:#101d2d;color:white;font:32px system-ui;text-align:center}
#surface{position:fixed;left:0;right:0;top:0;bottom:0;overflow:hidden}#caption{position:absolute;bottom:10%;left:5%;width:90%;max-height:42%;overflow:auto;white-space:pre-line;word-wrap:break-word;overflow-wrap:anywhere}
#hud{position:absolute;display:none;box-sizing:border-box;background:rgba(0,0,0,.92);border-radius:.4em;padding:.55em .8em;text-align:left;font-size:24px;font-size:clamp(13px,2.1vw,26px);line-height:1.45;font-weight:700;overflow-wrap:anywhere;white-space:pre-line;overflow:auto}
.badge{display:inline-block;position:relative;min-width:1.05em;height:1.05em;line-height:1.05em;padding:.12em .18em;margin:0 .12em;border:.06em solid #a3adb9;border-radius:.5em;background:#252a31;text-align:center;vertical-align:middle;font-size:.9em}.badge.plate{border-radius:.2em;min-width:1.7em}.badge.view{text-indent:-9999px;overflow:hidden;width:1.25em}.badge.view:before,.badge.view:after{content:'';position:absolute;width:.48em;height:.48em;border:.1em solid white;left:.2em;top:.16em}.badge.view:after{left:.52em;top:.42em;background:#252a31}
#pair{position:relative;z-index:2;margin-top:8vh}input,button{font:20px system-ui;padding:10px}#status{position:fixed;top:8px;left:15%;width:70%;font:14px system-ui;pointer-events:none}#edit{display:none;position:fixed;top:8px;right:8px;font:14px system-ui}</style>
<div id="surface"><div id="caption" tabindex="0" aria-label="Altyazı"></div><div id="hud" tabindex="0" aria-label="Görev metni"></div></div><div id="pair"><h2>MOZKAN Live Sub</h2><input id="token" placeholder="Eşleştirme kodu" autocomplete="off" spellcheck="false"><button id="connect">Bağlan</button></div><p id="status"></p><button id="edit">Kodu değiştir</button>
<script>
let socket,timer,retry,attempt=0,generation=0,captionRevision=0,hudBox=null;
const caption=document.querySelector('#caption'),hud=document.querySelector('#hud'),surface=document.querySelector('#surface');
const status=document.querySelector('#status'),pair=document.querySelector('#pair'),edit=document.querySelector('#edit');
const badgeCatalog=__BADGES__;
function renderHudText(text){
 hud.textContent='';
 for(const part of text.split(/(\{\{[A-Z0-9]+\}\})/g)){
  const match=/^\{\{([A-Z0-9]+)\}\}$/.exec(part),spec=match&&badgeCatalog[match[1]];
  if(!spec){hud.appendChild(document.createTextNode(part));continue}
  const badge=document.createElement('span');badge.className='badge '+spec.shape+(match[1]==='VIEW'?' view':'');
  badge.textContent=spec.label;badge.style.color=spec.color;badge.title=match[1];badge.setAttribute('role','img');badge.setAttribute('aria-label',match[1]);hud.appendChild(badge);
 }
}
function validText(value){return typeof value==='string'&&value.length<=2*__MAX_TEXT__&&Array.from(value).length<=__MAX_TEXT__}
function validBox(box){return box&&['x','y','w','h'].every(k=>typeof box[k]==='number'&&Number.isFinite(box[k])&&box[k]>=0&&box[k]<=1)&&box.w>0&&box.h>0&&box.x+box.w<=1.0001&&box.y+box.h<=1.0001}
function layoutHud(){
 if(!hud.textContent)return;
 const width=surface.clientWidth,height=surface.clientHeight;
 if(width<24||height<24){hud.style.display='none';return}
 const box=hudBox||{x:.55,y:.1,w:.4,h:.04};
 const pixels=Math.min(width-12,Math.max(.3,box.w)*width);
 hud.style.width=pixels+'px';hud.style.maxHeight=(height-12)+'px';
 hud.style.left=Math.max(6,Math.min(box.x*width,width-pixels-6))+'px';
 hud.style.display='block';
 const measured=hud.offsetHeight,below=(box.y+box.h)*height+6;
 const top=below+measured<=height-6?below:box.y*height-6-measured;
 hud.style.top=Math.max(6,Math.min(top,height-measured-6))+'px';
}
function clearCaption(){captionRevision++;clearTimeout(timer);caption.textContent=''}
function clearHud(){hud.textContent='';hud.style.display='none';hudBox=null}
function openSocket(id){
 if(id!==generation)return;
 let code;try{code=encodeURIComponent(document.querySelector('#token').value)}catch{status.textContent='Eşleştirme kodu geçersiz.';return}
 const connection=new WebSocket('ws://'+location.hostname+':__WS_PORT__/?token='+code);socket=connection;
 const current=()=>id===generation&&socket===connection;
 connection.onopen=()=>{if(!current())return;attempt=0;status.textContent='Bağlandı';pair.style.display='none';edit.style.display='block'};
 connection.onclose=()=>{if(!current())return;status.textContent='Bağlantı kapandı';clearCaption();clearHud();if(attempt<5){retry=setTimeout(()=>openSocket(id),Math.min(10000,1000*2**attempt));attempt++}else{pair.style.display='block'}};
 connection.onmessage=e=>{
  if(!current()||typeof e.data!=='string'||e.data.length>__MAX_MESSAGE__)return;
  let m;try{m=JSON.parse(e.data)}catch{return}if(!m||typeof m!=='object')return;
  if(m.type==='hud'){
   if(!validText(m.text)||!m.text||(m.box!=null&&!validBox(m.box))){clearHud();return}
   renderHudText(m.text);hudBox=m.box||null;layoutHud();return;
  }
  if(m.type==='clear'){clearCaption();return}
  if(m.type!=='subtitle'||!validText(m.text))return;
  clearCaption();
  const ttl=typeof m.ttl_ms==='number'&&Number.isFinite(m.ttl_ms)?Math.max(0,Math.min(11000,m.ttl_ms)):11000;
  if(!ttl)return;
  let text=m.text;
  if(m.stack&&typeof m.stack==='object'){
   const rows=[m.stack.previous,m.stack.current];
   if(rows.every(x=>x&&validText(x.text)&&validText(x.speaker)))text=rows.filter(x=>x.text).map(x=>(x.speaker?x.speaker+': ':'')+x.text).join('\n');
  }
  caption.textContent=text;
  caption.scrollTop=caption.scrollHeight;
  const revision=captionRevision;
  timer=setTimeout(()=>{if(current()&&revision===captionRevision)clearCaption()},ttl);
 };
}
document.querySelector('#connect').onclick=()=>{
 const token=document.querySelector('#token').value;
 if(!token||token.length>128){status.textContent='Eşleştirme kodunu girin.';return}
 generation++;attempt=0;clearTimeout(retry);clearCaption();clearHud();if(socket)socket.close();openSocket(generation);
};
edit.onclick=()=>{generation++;clearTimeout(retry);clearCaption();clearHud();if(socket)socket.close();socket=null;pair.style.display='block';edit.style.display='none';status.textContent='Eşleştirme kodunu girin.'};
window.addEventListener('resize',layoutHud);
const linkCode=/^#kod=([0-9a-f]{8})$/.exec(typeof location.hash==='string'?location.hash:'');
if(linkCode){
 // QR/link pairing: the code stays in the fragment (never sent to the server) and is removed after use.
 try{history.replaceState(null,'',location.pathname)}catch{}
 document.querySelector('#token').value=linkCode[1];document.querySelector('#connect').onclick();
}else if(typeof fetch==='function')fetch('/duplay.json',{cache:'no-store'}).then(response=>{
 if(!response.ok)throw new Error('Discovery unavailable');return response.json();
}).then(data=>{
 if(generation!==0)return;
 if(data&&data.name==='Duplay'&&typeof data.token==='string'&&data.token.length>0&&data.token.length<=128){
  document.querySelector('#token').value=data.token;document.querySelector('#connect').onclick();
 }else status.textContent='Eşleştirme kodunu girerek bağlanabilirsiniz.';
}).catch(()=>{if(generation===0)status.textContent='Eşleştirme kodunu girerek bağlanabilirsiniz.'});
</script>'''.replace('__MAX_TEXT__',str(MAX_CAPTION)).replace('__MAX_MESSAGE__',str(MAX_WIRE_BYTES)).replace('__BADGES__',json.dumps(BADGES,ensure_ascii=False))


class TV:
    def __init__(self, clock=time.monotonic):
        self.token = secrets.token_hex(4)
        self.clients = set()
        self.lock = threading.Lock()
        self.ws = self.http = None
        self.threads = []
        self.latest = ('', 0)
        self.condition = threading.Condition(self.lock)
        self.revision = 0
        self.clock = clock
        self.stopped = False
        self.hud = ''
        self.hud_box = None
        self.stack = None
        self.start_attempted = False
        self.http_started = False
        self.ws_raw = {}
        self.pairing_until = None

    def open_pairing(self, seconds=PAIRING_SECONDS):
        """Let LAN receivers fetch the pairing code for a limited time."""
        if not isinstance(seconds,(int,float)) or not 0<seconds<=600:
            raise ValueError('Eşleştirme süresi 1-600 saniye olmalı.')
        with self.condition:
            self.pairing_until = self.clock()+seconds

    def close_pairing(self):
        with self.condition:
            self.pairing_until = None

    def pairing_remaining(self):
        with self.condition:
            if self.pairing_until is None:
                return 0
            remaining = self.pairing_until-self.clock()
            if remaining <= 0:
                self.pairing_until = None
                return 0
            return remaining

    def _running(self):
        return (not self.stopped and self.http_started and self.ws is not None
                and len(self.threads)==2 and all(thread.is_alive() for thread in self.threads)
                and self.http.socket.fileno()!=-1 and self.ws.socket.fileno()!=-1)

    def connection_info(self):
        with self.condition:
            if not self._running():
                return None
            host,port=self.http.server_address[:2]
            return TVInfo(host,port,self.ws.socket.getsockname()[1],
                          sum(client.state==State.OPEN for client in self.clients))

    def serve_websockets(self):
        # websockets.sync.Server doesn't own accepted pre-handshake sockets.
        # Admit and track each socket before starting any protocol thread.
        self.ws.socket.settimeout(.25)
        while not self.stopped:
            try:
                request, address = self.ws.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                if self.stopped:
                    return
                raise
            with self.condition:
                self.ws_raw = {sock: thread for sock, thread in self.ws_raw.items()
                               if thread.is_alive() or sock.fileno() != -1}
                if self.stopped or len(self.ws_raw) >= 8:
                    request.close()
                    continue
                worker = threading.Thread(target=self.handle_websocket, args=(request, address), daemon=False)
                self.ws_raw[request] = worker
                try:
                    worker.start()
                except Exception:
                    request.close()
                    del self.ws_raw[request]
                    raise

    def handle_websocket(self, request, address):
        try:
            if not self.stopped:
                self.ws.handler(request, address)
        finally:
            request.close()
            with self.condition:
                self.condition.notify_all()

    def start(self, host='0.0.0.0', ws_port=8765, http_port=8766):
        if self.start_attempted:
            raise RuntimeError('Bu TV oturumu zaten başlatıldı; yeni bir oturum oluşturun.')
        self.start_attempted = True
        from websockets.sync.server import serve
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlsplit(self.path).path
                if path == '/duplay.json':
                    peer = ipaddress.ip_address(self.client_address[0])
                    if not (peer.is_private or peer.is_loopback or peer.is_link_local):
                        self.send_error(403)
                        return
                    info = dict(name='Duplay', port=owner.ws.socket.getsockname()[1])
                    if owner.pairing_remaining() > 0:
                        info['token'] = owner.token
                    body = json.dumps(info).encode('utf-8')
                elif path == '/':
                    body = PAGE.replace('__WS_PORT__', str(owner.ws.socket.getsockname()[1])).encode('utf-8')
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/json' if path == '/duplay.json' else 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                if path == '/duplay.json':
                    # Samsung receiver probes cross-origin; the page needs no CORS.
                    self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        def authorize(conn, request):
            value = parse_qs(urlsplit(request.path).query).get('token', [''])[0]
            if not secrets.compare_digest(value.encode('utf-8'), owner.token.encode('utf-8')):
                return conn.respond(403, 'Eşleştirme kodu geçersiz')
        def connected(conn):
            with owner.condition:
                rejected = owner.stopped or len(owner.clients) >= 8
                if not rejected:
                    owner.clients.add(conn)
            if rejected:
                conn.close(code=1013, reason='TV bağlantı kapasitesi dolu')
                return
            revision = -1
            try:
                while True:
                    with owner.condition:
                        owner.condition.wait_for(lambda: owner.stopped or owner.revision != revision, timeout=1)
                        if owner.stopped:
                            return
                        if conn.state == State.CLOSED:
                            return
                        if owner.revision == revision:
                            continue
                        revision = owner.revision
                        messages = owner._snapshot()
                    for message in messages:
                        conn.send(json.dumps(message, ensure_ascii=False))
            except Exception:
                pass
            finally:
                with owner.condition:
                    owner.clients.discard(conn)
                    owner.condition.notify_all()
        try:
            self.http = OwnedHTTPServer((host, http_port), Handler)
            self.ws = serve(connected, host, ws_port, process_request=authorize,
                            max_size=1024, max_queue=4, ping_interval=3,
                            open_timeout=2, close_timeout=1)
            for target in (self.http.serve_forever, self.serve_websockets):
                thread = threading.Thread(target=target, daemon=False)
                thread.start()
                self.threads.append(thread)
                if target == self.http.serve_forever:
                    self.http_started = True
            self.open_pairing()
        except Exception:
            self.close()
            raise

    def _snapshot(self):
        # Caller owns the state lock. Every client gets a single ordered
        # snapshot, so joining and live publication cannot race each other.
        import math
        text, at = self.latest
        remaining = max(0, 11 - (self.clock() - at))
        text = text if remaining > 0 else ''
        subtitle = dict(type='subtitle' if text else 'clear', text=text,
                        ttl_ms=math.ceil(remaining * 1000) if text else 0)
        if self.stack and text:
            subtitle.update(duplay_style='cod_stack_v1', stack=self.stack)
        return [subtitle, dict(type='hud', text=self.hud, box=self.hud_box.as_dict() if self.hud_box else None, ttl_ms=0)]

    def publish(self, text, stack=None):
        text=_text(text)
        stack=_stack(stack,text)
        with self.condition:
            self._publish(text,stack)

    def _publish(self,text,stack):
        self.latest = text,self.clock()
        self.stack = stack
        self.revision += 1
        self.condition.notify_all()

    def test_caption(self):
        with self.condition:
            if not self._running():
                raise ValueError('Önce TV yayınını açın.')
            if not any(client.state==State.OPEN for client in self.clients):
                raise ValueError('Henüz bağlı bir alıcı yok; TV tarayıcısından bağlanın.')
            self._publish('MOZKAN Live Sub bağlantısı hazır.',None)

    def publish_hud(self, text,box=None):
        text=_text(text)
        if box is not None and not isinstance(box,NormalizedBox):
            raise ValueError('TV HUD alanı doğrulanmış NormalizedBox olmalı.')
        with self.condition:
            self.hud = text
            self.hud_box = box if text else None
            self.revision += 1
            self.condition.notify_all()

    def close(self):
        failures = []
        def attempt(operation):
            try:
                operation()
            except Exception as exc:
                failures.append(str(exc))
        with self.condition:
            self.stopped = True
            self.condition.notify_all()
        if self.ws:
            attempt(self.ws.shutdown)
        with self.lock:
            clients = tuple(self.clients)
        with self.condition:
            raw = tuple(self.ws_raw.items())
        # A peer that stops reading can hold the protocol writer mutex in
        # sendall. Interrupt the owned transport before protocol finalization;
        # calling conn.close first can wait forever for that writer mutex.
        for request, _ in raw:
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            attempt(request.close)
        for conn in clients:
            attempt(conn.close)
        if self.http:
            if self.http_started:
                attempt(self.http.shutdown)
            attempt(self.http.close_connections)
            attempt(self.http.server_close)
        for thread in self.threads:
            attempt(lambda thread=thread: thread.join(3))
        self.threads = [thread for thread in self.threads if thread.is_alive()]
        if self.threads:
            failures.append('TV sunucu iş parçacıkları henüz kapanmadı.')
        for _, worker in raw:
            attempt(lambda worker=worker: worker.join(3))
        with self.condition:
            self.ws_raw = {request: worker for request, worker in self.ws_raw.items()
                           if worker.is_alive() or request.fileno() != -1}
            if self.ws_raw:
                failures.append('TV WebSocket bağlantıları henüz kapanmadı.')
            if not self.condition.wait_for(lambda: not self.clients, timeout=3):
                failures.append('TV istemcileri henüz kapanmadı.')
        if failures:
            raise RuntimeError('; '.join(failures))
