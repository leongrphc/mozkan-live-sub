"""Render shipped HTML with an explicit fake bridge and deny external requests.

This observes the original frontend, not its engine/account/device behavior.
Never imports the reference Python application or sends real native commands.
"""
import ast
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QTWEBENGINE_CHROMIUM_FLAGS']='--disable-gpu'
from PySide6.QtCore import QObject,Signal,Slot,QTimer,QUrl,Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile,QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=Path(r'C:\Users\MOZKAN\AppData\Local\Programs\Duplay\app')
HTML=REFERENCE/'web/index.html'
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=ROOT/'analysis/reference-ui-render-039-complete')
args=parser.parse_args()
OUTPUT=args.output.resolve()
OUTPUT.mkdir(exist_ok=False)
tree=ast.parse((REFERENCE/'console_bridge.py').read_text(encoding='utf-8'))
defaults=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id=='DEFAULT_SETTINGS' for t in n.targets))
state=dict(version='1.0.13',native=True,mode='live',profile='single',gameId='mafia',settings=defaults,
    capture=dict(running=False,starting=False,stopping=False,selecting=False,hasRegion=False,region=None,
        source='',text='',previous='',speaker='',method='',latency='',error='',preview='',hasHud=False,hudText='',selectionKind=''),
    games=[dict(id=k,title=t,subtitle='Diyalog',artKey=k,count=0) for k,t in
           [('mafia','Mafia'),('blackflag','Black Flag'),('mw4','Modern Warfare 4'),('rdr1','Red Dead Redemption'),('rdr2','Red Dead Redemption 2')]],
    tv=dict(running=False,connected=False,clients=0,ip='127.0.0.1',port=8765,previewPort=8766,token='',error='',
            samsung=dict(busy=False,action='',step='',text='',tvs=[])),status='Hazır',subscription='Fixture · çevrimdışı')
commands=[];blocked=[];shots=[];errors=[]

class Bridge(QObject):
    stateChanged=Signal(str)
    notification=Signal(str)
    @Slot(result=str)
    def getState(self):return json.dumps(state,ensure_ascii=False)
    @Slot(str,result=str)
    def command(self,serialized):
        request=json.loads(serialized);commands.append(request)
        if request['action']=='configure':
            payload=request.get('payload',{})
            for key in ('mode','profile','gameId','settings'):
                if key in payload:state[key]=payload[key]
        else:return json.dumps(dict(ok=False,error='Controlled frontend fixture: action unavailable',state=state))
        return json.dumps(dict(ok=True,state=state))

class DenyExternal(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self,info):
        url=info.requestUrl()
        allowed=url.scheme() in ('data','qrc','about') or (url.scheme()=='file' and Path(url.toLocalFile())==HTML)
        if not allowed:blocked.append(url.toString());info.block(True)

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
app=QApplication([])
view=QWebEngineView();view.resize(1280,900)
profile=QWebEngineProfile(view)
interceptor=DenyExternal(profile);profile.setUrlRequestInterceptor(interceptor)
page=QWebEnginePage(profile,view);view.setPage(page)
channel=QWebChannel(page);bridge=Bridge(channel);channel.registerObject('duplay',bridge);page.setWebChannel(channel)
view.setWindowTitle('Reference frontend fixture; no original engine')
view.show()
steps=[('home',None),('profiles',"document.querySelectorAll('.console-choice')[0].click()"),
       ('work',"document.querySelectorAll('.console-choice')[0].click()"),
       ('settings',"document.querySelector('#subtitleSettings').click()"),
       ('about',"document.querySelector('.sheet-heading button').click(); setTimeout(()=>[...document.querySelectorAll('button')].find(b=>b.innerText.startsWith('Console ')).click(),500)"),
       ('tv',"document.querySelector('.sheet-heading button').click(); setTimeout(()=>document.querySelector('.tv-trigger').click(),500)"),
       ('games',"document.querySelector('.sheet-heading button').click(); setTimeout(()=>document.querySelector('.home-link').click(),500);setTimeout(()=>{const timer=setInterval(()=>{const button=[...document.querySelectorAll('.console-choice')].find(b=>b.innerText.includes('Oyunlar'));if(button){clearInterval(timer);button.click()}},100)},700)")]

def step(index=0):
    if index==len(steps):app.quit();return
    name,action=steps[index]
    def capture():
        path=OUTPUT/(name+'.png')
        script="JSON.stringify({text:document.body.innerText,buttons:[...document.querySelectorAll('button')].map(b=>({text:b.innerText,aria:b.getAttribute('aria-label'),className:b.className,opacity:getComputedStyle(b).opacity,box:{width:b.getBoundingClientRect().width,height:b.getBoundingClientRect().height}})),dialogs:[...document.querySelectorAll('[role=dialog]')].map(d=>d.getAttribute('aria-label'))})"
        def record(value):
            facts=json.loads(value)
            expected={'settings':'Altyazı','about':'Duplay Console','tv':'TV’ye bağlan'}.get(name)
            if expected and expected not in facts['dialogs']:errors.append(f'{name}: expected dialog not rendered: {facts["dialogs"]}')
            if name=='profiles' and 'Çeviri biçimi' not in facts['text']:errors.append('Profile page missing')
            if name=='games' and 'Mafia' not in facts['text']:errors.append('Game cards missing')
            def save():
                assert view.grab().save(str(path))
                shots.append(dict(name=name,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),**facts))
                QTimer.singleShot(0,lambda:step(index+1))
            QTimer.singleShot(500,save)
        page.runJavaScript(script,record)
    if action:page.runJavaScript(action)
    QTimer.singleShot(3500 if name=='games' else 1800,capture)

page.loadFinished.connect(lambda ok:QTimer.singleShot(1800,step) if ok else (errors.append('HTML load failed'),app.quit()))
page.load(QUrl.fromLocalFile(str(HTML)))
QTimer.singleShot(35000,lambda:(errors.append('Render timeout'),app.quit()))
app.exec()
view.close()
report=dict(reference=str(HTML),sha256=hashlib.sha256(HTML.read_bytes()).hexdigest(),
    authority='controlled replay of shipped frontend with explicit fake native bridge; not original engine/device/account runtime',
    viewport=[1280,900],fixture_state=state,commands=commands,blocked_requests=blocked,shots=shots,errors=errors)
(OUTPUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert not errors,errors
assert len(shots)==len(steps)
print(json.dumps(dict(output=str(OUTPUT),screens=len(shots),blocked_requests=len(blocked))))
