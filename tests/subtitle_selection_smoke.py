"""Exercise the real Start button workflow with only a subtitle line selected."""
import ctypes
import json
import sys
import time
import argparse
import tempfile
import hashlib
import os
from collections import deque
from unittest.mock import patch
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--pause-resume', action='store_true')
parser.add_argument('--offset',type=float,default=0)
parser.add_argument('--restart',action='store_true')
parser.add_argument('--mapping-change',action='store_true')
parser.add_argument('--selector',action='store_true')
parser.add_argument('--quality',choices=('fast','accurate'),default='fast')
parser.add_argument('--diagnostics',action='store_true')
parser.add_argument('--console',action='store_true')
parser.add_argument('--auto-start',action='store_true')
parser.add_argument('--manual-capture',action='store_true')
parser.add_argument('--installation',type=Path,default=Path(__file__).resolve().parents[1])
args = parser.parse_args()
if args.auto_start and (not args.selector or args.restart or args.manual_capture):
    parser.error('--auto-start requires --selector and excludes --restart/--manual-capture')
root=args.installation.resolve()
os.environ['QT_QPA_PLATFORM']='windows'
sys.path.insert(0,str(root/'src'))
from main import QApplication, QLabel, QFont, QTimer, Qt, Window
from settings import Settings
from app_log import AppLog
from live_preconditions import require_visible_desktop
from PySide6.QtCore import QEvent,QPoint,QPointF
from PySide6.QtGui import QMouseEvent,QKeyEvent
require_visible_desktop()
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
sources={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (root/'src').glob('*.py')}
app = QApplication([])
settings_folder = tempfile.TemporaryDirectory()
event_log=AppLog(Path(settings_folder.name)/'logs','native-smoke',sys.version.split()[0])
window = Window(root / 'models', settings=Settings(Path(settings_folder.name) / 'settings.json'),event_log=event_log)
window.show()
if args.console:
    ui=window.console
    assert ui.page=='home'
    ui.games_choice.click()
    assert ui.page=='games' and ui.game_list.count()>0
    ui.search.setText('generated-no-such-game-234')
    assert not ui.use_game.isEnabled()
    ui.search.clear()
    ui.use_game.click()
    assert ui.page=='work' and window.profile.currentData()
    app.sendEvent(ui,QKeyEvent(QEvent.KeyPress,Qt.Key_Escape,Qt.NoModifier))
    assert ui.page=='games'
    ui.home_button.click()
    app.sendEvent(ui.live_choice,QKeyEvent(QEvent.KeyPress,Qt.Key_Return,Qt.NoModifier))
    assert ui.page=='profiles'
    app.sendEvent(ui.dialogue_choice,QKeyEvent(QEvent.KeyPress,Qt.Key_Return,Qt.NoModifier))
    assert ui.page=='work' and window.caption_mode.currentData()=='dialogue'
    ui.home_button.click()
    ui.live_choice.click()
    ui.single_choice.click()
    assert window.caption_mode.currentData()=='single'
    ui.home_button.click()
    ui.movie_choice.click()
    assert ui.page=='work' and window.mode.currentData()=='movie'
label = QLabel('We need to leave before the guards return.')
label.setStyleSheet('background:black;color:white;padding:20px')
label.setFont(QFont('Arial', 24))
label.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
label.setGeometry(100,100,950,130)
label.show()
app.processEvents()
window.mode.setCurrentIndex(window.mode.findData('movie'))
window.selection_scope.setCurrentIndex(window.selection_scope.findData('subtitle'))
window.overlay_style['y_offset']=args.offset
window.overlay.configure(**window.overlay_style)
window.ocr_quality.setCurrentIndex(window.ocr_quality.findData(args.quality))
selection = (100, 142, 950, 65)
if args.selector:
    if args.auto_start:window.start.click()
    else:window.choose('subtitle')
    app.processEvents()
    selector=window.selector
    begin=QPoint(selection[0],selection[1])
    end=QPoint(selection[0]+selection[2]-1,selection[1]+selection[3]-1)
    for kind,point,button,buttons in ((QEvent.MouseButtonPress,begin,Qt.LeftButton,Qt.LeftButton),
                                     (QEvent.MouseMove,end,Qt.NoButton,Qt.LeftButton),
                                     (QEvent.MouseButtonRelease,end,Qt.LeftButton,Qt.NoButton)):
        event=QMouseEvent(kind,QPointF(selector.mapFromGlobal(point)),QPointF(point),button,buttons,Qt.NoModifier)
        app.sendEvent(selector,event)
    assert window.selector is None
    if not args.auto_start:
        window.choose('hud')
        pending=window.selector
        window.begin()
        assert window.worker is None and not window.start.isEnabled()
        app.sendEvent(pending,QKeyEvent(QEvent.KeyPress,Qt.Key_Escape,Qt.NoModifier))
        assert window.selector is None and window.hud_region is None
    label.raise_()
else:
    window.chosen(selection)
assert window.region == selection
if args.restart:
    window.appearance_changed()
    window.close()
    event_log=AppLog(Path(settings_folder.name)/'logs','native-smoke',sys.version.split()[0])
    window=Window(root/'models',settings=Settings(Path(settings_folder.name)/'settings.json'),event_log=event_log)
    window.show()
    label.show()
    label.raise_()
    assert window.region==selection
    assert window.mode.currentData()=='movie'
    assert window.worker is None
    if args.console:
        window.console.resume.click()
        assert window.console.page=='work'
outputs, errors, messages = [], [], []
manual={}
if args.manual_capture:
    from PySide6.QtGui import QImage
    label.raise_();app.processEvents();time.sleep(.1)
    baseline=window.capture_image()
    window.setWindowFlag(Qt.WindowStaysOnTopHint,True)
    window.resize(1100,300);window.move(80,70);window.show();window.raise_()
    app.processEvents();time.sleep(.1)
    covered=window.capture_image()
    def pixels(captured):
        image=captured.image.convertToFormat(QImage.Format_RGBA8888)
        return bytes(image.bits())
    assert pixels(baseline)==pixels(covered),'Owned console must not replace OCR source pixels'
    manual['console_capture_exclusion_changed_bytes']=0
    window.setWindowFlag(Qt.WindowStaysOnTopHint,False);window.show()
    label.raise_();app.processEvents();time.sleep(.1)
    window.preview()
    assert not window.console.canvas._preview.isNull()
    destination=Path(settings_folder.name)/'OCR test.png'
    with patch('main.QFileDialog.getSaveFileName',return_value=(str(destination),'PNG')):window.export_image()
    saved=QImage(str(destination))
    assert not saved.isNull() and saved.size()==baseline.image.size()
    manual['png']=dict(width=saved.width(),height=saved.height(),sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
observations=deque(maxlen=64)
if args.diagnostics:
    receive_observation=window.received_observation
    def observed(update):
        receive_observation(update)
        value=update.observation
        if hasattr(value,'reading'):
            reading=value.reading
            observations.append(dict(at=time.monotonic()-started,fresh=value.fresh,
                expected=reading.text=='We need to leave before the guards return.',characters=len(reading.text),
                confidence=reading.confidence,method=reading.method,variant=reading.variant))
    window.received_observation=observed
first_worker = None
window.events.error.connect(errors.append)
window.events.failure.connect(lambda session,role,failure:errors.append(f'{role}: {failure.error_class}: {failure.message}'))
window.events.capture_message.connect(lambda session,revision,text,error:messages.append(
    dict(session=session,revision=revision,text=text,error=error,at=time.monotonic()-started)))
def complete_output():
    global first_worker
    if args.diagnostics:
        window.poll()
        outputs[-1]['diagnostics']=dict(ocr=window.ocr_info.text(),translation=window.translation_info.text())
        if 'ms' not in window.ocr_info.text() or not any(name in window.translation_info.text() for name in ('CPU','NVIDIA CUDA')):
            errors.append('Actual OCR/translation observations were not displayed')
        if args.quality=='accurate' and '2 geçiş' not in window.ocr_info.text():
            errors.append('Accurate OCR did not report two passes')
    if args.manual_capture:
        destination=Path(settings_folder.name)/'diagnostic.json'
        window.export_text.setChecked(False)
        with patch('main.QFileDialog.getSaveFileName',return_value=(str(destination),'JSON')):window.export_diagnostics()
        snapshot=json.loads(destination.read_text(encoding='utf-8'))
        assert snapshot['observations'] and not snapshot['includes_text'] and 'captions' not in snapshot
        window.export_text.setChecked(True)
        with patch('main.QFileDialog.getSaveFileName',return_value=(str(destination),'JSON')):window.export_diagnostics()
        snapshot=json.loads(destination.read_text(encoding='utf-8'))
        assert snapshot['captions']['translation']==outputs[-1]['target']
        manual['json']=dict(observations=len(snapshot['observations']),text_opt_in=True,
                            sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    if args.offset:
        shifted=window.overlay.geometry().top()
        window.overlay.configure(y_offset=0)
        base=window.overlay.geometry().top()
        window.overlay.configure(y_offset=args.offset)
        outputs[-1]['offset_check']=dict(base=base,shifted=shifted,steps=args.offset)
        if not window.overlay.isVisible() or base-shifted!=round(args.offset*10):
            errors.append('Native subtitle offset was not applied as 10px up per step')
    if args.pause_resume and len(outputs) == 1:
        first_worker = window.worker
        window.toggle_pause()
        assert window.control.snapshot()[0]
        assert window.target.toPlainText() == ''
        def resume():
            assert window.worker is first_worker
            window.toggle_pause()
            assert not window.control.snapshot()[0]
        QTimer.singleShot(300, resume)
        return
    if args.pause_resume:
        assert window.worker is first_worker
    if args.mapping_change:
        before=window.session
        with patch('main.capture_region',return_value=(1,2,3,4)):
            changed=window.validate_areas(native=True)
        if changed or not window.stop_event.is_set() or window.region is not None or window.target.toPlainText():
            errors.append('Changed native mapping did not invalidate/stop/clear capture')
        outputs[-1]['mapping_change']=dict(simulated=True,session_invalidated=window.session>before,
                                           stopped=window.stop_event.is_set(),region_invalid=window.region is None,
                                           target_cleared=not window.target.toPlainText())
    window.halt()
    window.close()

def received(session,source,target,revision):
    if target:
        outputs.append(dict(source=source,target=target))
        if args.diagnostics:QTimer.singleShot(200,complete_output)
        else:complete_output()
window.events.output.connect(received)
started = time.monotonic()
def launch():
    if args.auto_start:pass
    elif args.console:app.sendEvent(window.start,QKeyEvent(QEvent.KeyPress,Qt.Key_Return,Qt.NoModifier))
    else:window.begin()
    label.show()
    label.raise_()
QTimer.singleShot(300, launch)
timer = QTimer()
def timeout():
    if time.monotonic() - started > (90 if args.diagnostics else 45):
        window.halt()
        window.close()
timer.timeout.connect(timeout)
timer.start(100)
app.exec()
window.halt()
if window.worker:
    window.worker.join(10)
    assert not window.worker.is_alive(),'Capture must end before hiding the opaque test source'
label.close()
window.close()
app.processEvents()
assert event_log.stream is None,'Owned application log must close with the window'
log_bytes=event_log.path.read_bytes()
log_rows=[json.loads(line) for line in log_bytes.splitlines()]
assert any(row['event']=='capture_start' for row in log_rows)
assert any(row['event']=='resource' and row['component']=='translation' and row['status']=='ready' for row in log_rows)
assert any(row['event']=='capture_end' for row in log_rows)
assert all(item['source'].encode('utf-8') not in log_bytes and item['target'].encode('utf-8') not in log_bytes for item in outputs)
app_log=dict(events=len(log_rows),bytes=len(log_bytes),sha256=hashlib.sha256(log_bytes).hexdigest(),
             closed=True,subtitle_stream_absent=True,records=log_rows)
assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in sources.items())
assert not errors, errors
assert outputs and outputs[0]['source']=='We need to leave before the guards return.',dict(outputs=outputs,messages=messages,observations=list(observations))
assert outputs[0]['target'], outputs
if args.pause_resume:
    assert len(outputs) == 2, outputs
print(json.dumps(dict(selection=selection, outputs=outputs,
                      elapsed_seconds=time.monotonic()-started,
                      pause_resume=args.pause_resume,
                      restored=args.restart,mapping_change=args.mapping_change,
                      selector=args.selector,quality=args.quality,diagnostics=args.diagnostics,
                      console=args.console,
                      auto_start=args.auto_start,manual_capture=manual,application_log=app_log,
                      installation=str(root),runtime=sys.executable,sources=sources,
                      capture_messages=messages,
                      observations=list(observations),
                      scope='actual Window.begin/MSS/MT; opaque owned subtitle source retained until worker completion. Optional selector uses Qt events addressed only to the owned widget, not OS input. Mapping-change fault is simulated.'),ensure_ascii=True))
settings_folder.cleanup()
