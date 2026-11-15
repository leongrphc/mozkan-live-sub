"""Same native choice workflow against immutable039 and current source."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile
from benchmark_ocr_parity import peak_memory

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--worker',choices=('old','new'))
parser.add_argument('--label',default='cards')
args=parser.parse_args()

def worker(mode):
    os.environ['QT_QPA_PLATFORM']='windows'
    snapshot=tempfile.TemporaryDirectory()
    source=ROOT/'src'
    origin=str(source)
    if mode=='old':
        archive=ROOT/'releases/AltyaziAtolyesi-0.3.9-update.zip'
        source=Path(snapshot.name)
        with zipfile.ZipFile(archive) as package:
            for entry in package.infolist():
                parts=Path(entry.filename).parts
                if len(parts)==3 and parts[:2]==('AltyaziAtolyesi','src') and parts[-1].endswith('.py'):
                    (source/parts[-1]).write_bytes(package.read(entry))
        origin=dict(path=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*')
             if p.is_file() and p.suffix in ('.py','.jpg') and '__pycache__' not in p.parts}
    started,cpu=time.perf_counter(),time.process_time()
    sys.path.insert(0,str(source))
    from main import QApplication,Window,QTimer
    from settings import Settings
    from PySide6.QtCore import Qt,QEvent
    from PySide6.QtGui import QKeyEvent
    app=QApplication([])
    with tempfile.TemporaryDirectory() as folder:
        window=Window(ROOT/'models',settings=Settings(Path(folder)/'settings.json'))
        window.resize(1280,900);window.show();app.processEvents()
        ui=window.console
        cold=dict(elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,peak_working_set_bytes=peak_memory())
        pages=[]
        def tick():
            i=len(pages)
            if i==20:window.resize(480,400)
            if i==28:window.resize(1280,900)
            if i%4==0:
                ui.home_button.click();ui.live_choice.setFocus()
                for button in (ui.live_choice,ui.games_choice):
                    app.sendEvent(button,QKeyEvent(QEvent.KeyPress,Qt.Key_Right,Qt.NoModifier))
                assert ui.movie_choice.hasFocus()
            elif i%4==1:ui.live_choice.click()
            elif i%4==2:ui.dialogue_choice.click()
            else:ui.home_button.click();ui.games_choice.click()
            pages.append(ui.page)
            if len(pages)==40:timer.stop();app.quit()
        timer=QTimer();timer.timeout.connect(tick);timer.start(50)
        QTimer.singleShot(10000,app.quit)
        started,cpu=time.perf_counter(),time.process_time()
        app.exec()
        warm=dict(elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,peak_working_set_bytes=peak_memory())
        window.close()
        assert pages==['home','profiles','work','games']*10,pages
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==d for p,d in sources.items())
    snapshot.cleanup()
    return dict(mode=mode,origin=origin,sources=sources,cold=cold,warm=warm,pages=pages)

if args.worker:print('RESULT='+json.dumps(worker(args.worker)))
else:
    results=[]
    for mode in ('old','new'):
        task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode],cwd=ROOT,
            capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        (ROOT/f'analysis/choices-cost-{args.label}-{mode}-stderr.txt').write_text(task.stderr,encoding='utf-8')
        assert task.returncode==0,task.stderr[-2500:]
        results.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
    report=dict(status='PASS',results=results,scope='Native Qt choices:40transitions home/profiles/work/games, keyboard focus to movie,1280x900 and480x400.',
        limits=['Fresh worker per version; cold imports/settings/catalog/widget construction/first event processing; warm excludes cleanup.',
                'No OCR/MT/MSS/network/real game. Process CPU includes Qt threads, no worker child processes intentionally started.',
                'Peak lifetime working set; GPU/external desktop processes/tokens unmeasured; single run, OS/cache/background uncontrolled.',
                'New painted cards versus old plain buttons; not a pixel equality or speedup claim.'])
    (ROOT/f'analysis/choices-0.4.0-dev-{args.label}-cost.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(status='PASS',results=[dict(mode=r['mode'],cold=r['cold'],warm=r['warm']) for r in results])))
