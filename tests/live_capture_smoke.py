"""Render a known test window and capture only that window's text rectangle."""
import ctypes
import json
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from main import QApplication, QLabel, QFont, QTimer, Qt, capture_region
from capture import run_capture
from live_preconditions import require_visible_desktop

require_visible_desktop()

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
app = QApplication([])
label = QLabel('We need to leave before the guards return.')
label.setStyleSheet('background:black;color:white;padding:20px')
label.setFont(QFont('Arial', 24))
label.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
label.setGeometry(100, 100, 950, 130)
label.show()
app.processEvents()
region = capture_region((100, 100, 950, 130), app.screens())
stop = threading.Event()
outputs, errors = [], []
def received(source, target):
    outputs.append(dict(source=source, target=target))
    stop.set()
worker = threading.Thread(target=run_capture, kwargs=dict(
    models=Path(__file__).resolve().parents[1] / 'models',
    region=region, stop=stop, output=received,
    status=lambda text: None, error=errors.append))
worker.start()
started = time.monotonic()
timer = QTimer()
def poll():
    if time.monotonic() - started > 45:
        stop.set()
    if not worker.is_alive():
        app.quit()
timer.timeout.connect(poll)
timer.start(100)
app.exec()
worker.join()
assert not errors, errors
assert outputs and outputs[0]['source'] == 'We need to leave before the guards return.', outputs
assert outputs[0]['target'], outputs
print(json.dumps(dict(outputs=outputs, elapsed_seconds=time.monotonic()-started,
                      physical_region=region), ensure_ascii=True))
