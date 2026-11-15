"""Synthetic frames through Window.begin, real OCR/MT, PC badges and loopback TV."""
import os
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from contextlib import ExitStack
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--installation',type=Path,default=ROOT)
parser.add_argument('--native',action='store_true')
args=parser.parse_args()
os.environ['QT_QPA_PLATFORM']='windows' if args.native else 'offscreen'
INSTALLATION=args.installation.resolve(strict=True)
sys.path.insert(0,str(INSTALLATION/'src'))
from main import QApplication,Window,QTimer,QLabel,QImage,QPixmap,Qt,capture_region
from settings import Settings
from capture import run_capture
from tv import TV
from hud import MARK
from hud_fixtures import fixtures
from benchmark_ocr_parity import peak_memory
from websockets.sync.client import connect

if args.native:
    from live_preconditions import require_visible_desktop
    require_visible_desktop()
    import ctypes
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
app=QApplication([])
temporary=tempfile.TemporaryDirectory()
window=Window(INSTALLATION/'models',settings=Settings(Path(temporary.name)/'settings.json'))
window.chosen((50,450,700,65))
window.chosen_hud((50,120,700,130))
service=TV()
window.tv=service
images=dict(fixtures())
frames=[np.asarray(images[name])[:,:,::-1].copy() for name in ('shoulder','colored','blank')]
blank=np.zeros((65,700,3),dtype=np.uint8)
labels=[]
baseline=None
exclusion=[]
checking=[False]
def show_frame(index):
    if args.native:
        rgb=np.asarray(images[('shoulder','colored','blank')[index]]).copy()
        image=QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QImage.Format_RGB888).copy()
        labels[0].setPixmap(QPixmap.fromImage(image))
if args.native:
    window.show()
    for region in (window.hud_region,window.region):
        label=QLabel()
        label.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        label.setGeometry(*region)
        label.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        label.setStyleSheet('background:black;padding:0px;margin:0px;border:0px')
        label.show()
        labels.append(label)
    show_frame(0)
    app.processEvents()
    import mss
    physical=capture_region(window.hud_region,app.screens())
    def grab_known_hud():
        x,y,w,h=physical
        with mss.mss() as screen:
            return np.asarray(screen.grab(dict(left=x,top=y,width=w,height=h))).copy()
    baseline=grab_known_hud()
try:
    service.start(host='127.0.0.1',ws_port=0,http_port=0)
    peer=connect(f'ws://127.0.0.1:{service.connection_info().ws_port}/?token={service.token}')
    peer.recv(timeout=3);peer.recv(timeout=3)
except BaseException:
    service.close()
    window.tv=None
    for label in labels:
        label.close()
    window.close()
    raise
phase=[0]
outputs=[]
errors=[]
started,cpu=time.perf_counter(),time.process_time()
sources={name:hashlib.sha256((INSTALLATION/'src'/name).read_bytes()).hexdigest()
         for name in ('main.py','engine.py','capture.py','recognition.py','hud.py','badge_image.py','overlay.py','stability.py')}

def generated(hud):
    while True:
        yield frames[min(phase[0],2)] if hud else blank

def pipeline(*args,**kwargs):
    kwargs.update(frames=generated(kwargs.get('ocr_kind')=='hud'),interval=.03)
    return run_capture(*args,**kwargs)

def tv_hud(expected):
    for _ in range(20):
        value=json.loads(peer.recv(timeout=3))
        if value['type']=='hud' and value['text']==expected:
            return value
    raise AssertionError('TV did not publish expected HUD state')

def observe(session,source,target,revision):
    if session!=window.session or not window.hud_control.current(revision):
        return
    if checking[0]:
        return
    try:
        if phase[0]<2 and target:
            expected=('RB','A')[phase[0]]
            assert MARK.findall(source)==[expected],source
            assert MARK.findall(target)==[expected],target
            assert window.current_hud==target
            assert window.hud_overlay.isVisible(),window.hud_overlay.last_error
            task=tv_hud(target)
            assert task['box'] is not None
            outputs.append(dict(source=source,target=target,tv=task,at_seconds=time.perf_counter()-started))
            window.hud_overlay.grab().save(str(ROOT/f'analysis/hud-{"native" if args.native else "pipeline"}-{expected}.png'))
            if args.native and phase[0]==0 and window.hud_overlay.capture_excluded:
                checking[0]=True
                window.hud_overlay.configure_layout(x_offset=0,y_offset=12,scale=100)
                def verify_exclusion():
                    try:
                        from PySide6.QtCore import QRect
                        assert window.hud_overlay.isVisible(),window.hud_overlay.last_error
                        assert window.hud_overlay.geometry().intersects(QRect(*window.hud_region))
                        current=grab_known_hud()
                        changed=int(np.count_nonzero(np.any(current[:,:,:3]!=baseline[:,:,:3],axis=2)))
                        exclusion.append(dict(verified=changed==0,changed_pixels=changed,physical_region=physical))
                        assert changed==0,'Excluded HUD changed known source pixels'
                        assert window.current_hud==target,'Unexpected OCR feedback during exclusion check'
                        window.hud_overlay.configure_layout(x_offset=0,y_offset=0,scale=100)
                        phase[0]=1
                        show_frame(1)
                    except Exception as exc:
                        errors.append(str(exc));window.halt()
                    finally:
                        checking[0]=False
                QTimer.singleShot(100,verify_exclusion)
                return
            if args.native and phase[0]==0:
                exclusion.append(dict(verified=False,reason='Capture exclusion unavailable; overlap test NOT_RUN'))
            phase[0]+=1
            if args.native:
                show_frame(phase[0])
        elif phase[0]==2 and not source and not target:
            assert not window.hud_overlay.isVisible()
            task=tv_hud('')
            assert task['box'] is None
            outputs.append(dict(source='',target='',tv=task,at_seconds=time.perf_counter()-started))
            phase[0]=3
            window.halt()
    except Exception as exc:
        errors.append(str(exc))
        window.halt()

window.events.hud.connect(observe)
window.events.error.connect(errors.append)
if hasattr(window.events,'failure'):
    window.events.failure.connect(lambda session,role,failure:errors.append(f'{role}: {failure.error_class}: {failure.message}'))
timer=QTimer()
def poll():
    if time.perf_counter()-started>40:
        errors.append('HUD pipeline did not complete within40seconds: '+json.dumps(
            dict(status=window.status.text(),phase=phase[0],hud_enabled=window.hud_enabled.isChecked(),
                 hud=window.hud_text.text(),startup=window.diagnostic_snapshot()['startup'],
                 ocr=window.hud_ocr_info.text(),translation=window.hud_translation_info.text()),ensure_ascii=True))
        window.halt()
        app.quit()
        return
    if errors:
        window.halt()
        app.quit()
        return
    if window.stop_event.is_set() or phase[0]==3:
        app.quit()
timer.timeout.connect(poll)
timer.start(50)
try:
    with ExitStack() as stack:
        if not args.native:
            stack.enter_context(patch('main.run_capture',side_effect=pipeline))
            stack.enter_context(patch('main.capture_region',side_effect=lambda region,screens:region))
        window.begin()
        app.exec()
finally:
    timer.stop()
    window.stop_event.set()
    if window.worker:
        window.worker.join(10)
        assert not window.worker.is_alive(),'Capture owner still active'
    for label in labels:
        label.close()
    peer.close()
    window.tv=None
    service.close()
    window.close()
assert not errors,dict(errors=errors,outputs=outputs)
assert phase[0]==3,outputs
assert all(hashlib.sha256((INSTALLATION/'src'/name).read_bytes()).hexdigest()==digest for name,digest in sources.items())
print(json.dumps(dict(status='PASS',native=args.native,exclusion=exclusion,installation=str(INSTALLATION),outputs=outputs,sources=sources,
    elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,peak_working_set_bytes=peak_memory(),
    scope='Window.begin; known generated image frames'+(' displayed in owned windows and captured with actual MSS.' if args.native else ' injected without desktop capture.')+' Actual independent OCR/MT, PC badge resources and real WS HUD/clear.',
    limits='No real game/physical controller/TV/other-monitor proof. Elapsed includes model loading and cleanup, excludes Qt/server setup. No worker children; thread CPU included; lifetime peak; tokens unmeasured.'),ensure_ascii=True))
