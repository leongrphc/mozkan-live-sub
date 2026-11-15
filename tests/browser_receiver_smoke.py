"""Real HTTP/WS receiver in offscreen Chromium; never capture the desktop."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_OPENGL']='software'
os.environ['QTWEBENGINE_CHROMIUM_FLAGS']='--disable-gpu'
import hashlib
import argparse
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--installation',type=Path,default=ROOT)
parser.add_argument('--screenshot',type=Path,default=ROOT/'analysis/tv-receiver-current-offscreen.png')
args=parser.parse_args()
INSTALLATION=args.installation.resolve(strict=True)
sys.path.insert(0,str(INSTALLATION/'src'))
from PySide6.QtCore import QUrl,QTimer,Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from tv import TV
from coordinates import NormalizedBox

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
app=QApplication([])
view=QWebEngineView()
view.resize(1280,720)
view.show()
service=TV()
service.start(host='127.0.0.1',ws_port=0,http_port=0)
info=service.connection_info()
sources={name:hashlib.sha256((INSTALLATION/'src'/name).read_bytes()).hexdigest() for name in ('tv.py','coordinates.py')}
text='Türkçe altyazı kesilmeden korunuyor. '*20
task="{{RB}} ile kapıyı aç. <img id='injected'>"
task_display="RB ile kapıyı aç. <img id='injected'>"
loaded=[False]
phase=[0]
query_busy=[False]
observations=[]
errors=[]
started=time.perf_counter()
script="""JSON.stringify((()=>{const h=document.querySelector('#hud'),c=document.querySelector('#caption');const r=h.getBoundingClientRect();return {text:c.textContent,hud:h.textContent,badges:Array.from(h.querySelectorAll('.badge')).map(b=>b.title),display:getComputedStyle(h).display,pair:getComputedStyle(document.querySelector('#pair')).display,width:innerWidth,height:innerHeight,box:{left:r.left,top:r.top,right:r.right,bottom:r.bottom},injected:!!document.querySelector('#injected')}})())"""

def connect_browser():
    view.page().runJavaScript("document.querySelector('#token').value="+json.dumps(service.token)+";document.querySelector('#connect').click()")

def on_loaded(ok):
    if not ok:
        errors.append('Receiver HTTP load failed')
        app.quit()
        return
    loaded[0]=True
    # The actual receiver fetches its owned /duplay.json and connects itself.

def inspect(value):
    query_busy[0]=False
    try:
        state=json.loads(value)
        if phase[0] in (1,2) and state['text']==text and state['hud']==task_display and state['display']=='block':
            expected_width=1280 if phase[0]==1 else 800
            if state['width']!=expected_width:
                return
            box=state['box']
            assert box['left']>=-1 and box['top']>=-1,state
            assert box['right']<=state['width']+1 and box['bottom']<=state['height']+1,state
            assert not state['injected'],state
            assert state['badges']==['RB'],state
            assert state['pair']=='none',state
            observations.append(dict(phase='initial' if phase[0]==1 else 'resize',state=state))
            if phase[0]==1:
                view.grab().save(str(args.screenshot))
                view.resize(800,450)
                phase[0]=2
            else:
                service.publish('')
                service.publish_hud('')
                phase[0]=3
        elif phase[0]==3 and state['text']==state['hud']=='' and state['display']=='none':
            observations.append(dict(phase='clear',state=state))
            view.page().runJavaScript("document.querySelector('#edit').click()")
            phase[0]=4
        elif phase[0]==5 and service.connection_info().clients==1 and state['text']==state['hud']=='' and state['pair']=='none':
            observations.append(dict(phase='reconnect',state=state))
            phase[0]=6
            app.quit()
    except Exception as exc:
        errors.append(str(exc))
        app.quit()

def poll():
    if time.perf_counter()-started>25:
        errors.append('Offscreen Chromium receiver did not complete within 25 seconds')
        app.quit()
        return
    if not loaded[0]:
        return
    if phase[0]==0 and service.connection_info().clients==1:
        service.publish(text)
        service.publish_hud(task,NormalizedBox(.8,.9,.2,.1))
        phase[0]=1
    if phase[0]==4 and service.connection_info().clients==0:
        connect_browser()
        phase[0]=5
    if not query_busy[0]:
        query_busy[0]=True
        view.page().runJavaScript(script,inspect)

view.loadFinished.connect(on_loaded)
view.load(QUrl(f'http://127.0.0.1:{info.http_port}/'))
timer=QTimer()
timer.timeout.connect(poll)
timer.start(50)
try:
    app.exec()
finally:
    timer.stop()
    view.close()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    service.close()
assert not errors,errors
assert phase[0]==6,phase
assert all(hashlib.sha256((INSTALLATION/'src'/name).read_bytes()).hexdigest()==digest for name,digest in sources.items())
print(json.dumps(dict(status='PASS',installation=str(INSTALLATION),elapsed_seconds=time.perf_counter()-started,observations=observations,
    sources=sources,screenshot=str(args.screenshot),
    scope='Actual local HTTP/WebSocket + offscreen Chromium DOM/geometry/resize/clear/reconnect; no physical TV or desktop capture.',
    costs='Interaction sequence+cleanup elapsed; Qt imports/browser/server setup excluded. Process-family CPU/peak memory and token usage unmeasured.'),ensure_ascii=True))
