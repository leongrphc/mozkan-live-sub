"""Real Chromium <video> → MSS → OCR → translation → subtitle disappearance."""
import ctypes
import json
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from main import QApplication, QTimer, Qt, QObject, Signal, capture_region
from PySide6.QtWebEngineWidgets import QWebEngineView
from capture import run_capture
from video import subtitle_band
from live_preconditions import require_visible_desktop

require_visible_desktop()

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
app = QApplication([])
view = QWebEngineView()
view.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
view.setGeometry(100, 100, 960, 540)
view.show()
html = '''<html><body style="margin:0;background:black"><video autoplay muted playsinline width="960" height="540"></video><script>
const canvas=document.createElement('canvas');canvas.width=960;canvas.height=540;const c=canvas.getContext('2d');
window.caption='We need to leave before the guards return.';
setInterval(()=>{c.fillStyle='#182b43';c.fillRect(0,0,960,540);c.fillStyle='white';c.textAlign='center';
c.font='20px Arial';c.fillText('NAVIGATION OUTSIDE SUBTITLE BAND',480,80);c.font='30px Arial';c.fillText(window.caption,480,470)},100);
document.querySelector('video').srcObject=canvas.captureStream(10);</script></body></html>'''
stop = threading.Event()
outputs, errors = [], []
worker = None
started = time.monotonic()
class Bridge(QObject):
    translated = Signal(str, str)
bridge = Bridge()
def received(source, target):
    outputs.append(dict(source=source, target=target))
    if target:
        view.page().runJavaScript("window.caption='' ")
    elif not source and any(item['target'] for item in outputs):
        stop.set()
bridge.translated.connect(received)
def launch(success):
    global worker
    if not success:
        errors.append('HTML load failed'); app.quit(); return
    region = capture_region(subtitle_band((100,100,960,540),30), app.screens())
    worker = threading.Thread(target=run_capture, kwargs=dict(
        models=Path(__file__).resolve().parents[1] / 'models',
        region=region, stop=stop, output=bridge.translated.emit,
        status=lambda message: None, error=errors.append, movie=True))
    worker.start()
view.loadFinished.connect(launch)
view.setHtml(html)
timer = QTimer()
def poll():
    if time.monotonic()-started > 45:
        stop.set()
    if worker and not worker.is_alive():
        app.quit()
timer.timeout.connect(poll)
timer.start(100)
app.exec()
stop.set()
if worker:
    worker.join()
assert not errors, errors
translations = [item for item in outputs if item['target']]
assert translations and translations[0]['source']=='We need to leave before the guards return.', outputs
assert outputs[-1] == dict(source='',target=''), outputs
print(json.dumps(dict(outputs=outputs, elapsed_seconds=time.monotonic()-started,
                      scope='local canvas stream in Chromium video element; no external website or DRM tested'), ensure_ascii=True))
