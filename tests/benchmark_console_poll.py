"""Native common GUI task, immutable035 versus native console presentation."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile
import faulthandler
from benchmark_ocr_parity import peak_memory

ROOT=Path(__file__).resolve().parents[1]


def worker(mode):
    faulthandler.dump_traceback_later(15,repeat=False)
    os.environ['QT_QPA_PLATFORM']='windows'
    baseline=None
    source=ROOT/'src'
    origin=str(source)
    if mode=='old':
        archive=ROOT/'releases/AltyaziAtolyesi-0.3.5-update.zip'
        baseline=tempfile.TemporaryDirectory(prefix='altyazi-035-poll-')
        source=Path(baseline.name)
        with zipfile.ZipFile(archive) as snapshot:
            for item in snapshot.infolist():
                parts=Path(item.filename).parts
                if len(parts)==3 and parts[:2]==('AltyaziAtolyesi','src') and parts[2].endswith('.py'):
                    (source/parts[2]).write_bytes(snapshot.read(item))
        origin=dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    digests={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in source.glob('*.py')}
    started,cpu=time.perf_counter(),time.process_time()
    sys.path.insert(0,str(source))
    import main
    from settings import Settings
    app=main.QApplication([])
    folder=tempfile.TemporaryDirectory()
    window=main.Window(ROOT/'models',settings=Settings(Path(folder.name)/'settings.json'))
    window.mode.setCurrentIndex(window.mode.findData('movie'))
    window.mode.setCurrentIndex(window.mode.findData('screen'))
    geometry=app.primaryScreen().geometry()
    subtitle=(geometry.x()+50,geometry.y()+500,600,65)
    hud=(geometry.x()+50,geometry.y()+100,600,130)
    window.chosen(subtitle)
    window.chosen_hud(hud)
    from regions import CapturePlan
    window._capture_plan=CapturePlan.create(subtitle,hud,app.screens(),main.capture_region)
    window._topology_check_at=0
    window.resize(1080,860)
    window.show()
    window.source.setPlainText('Known generated English caption.')
    window.target.setPlainText('Bilinen Türkçe altyazı.')
    if mode=='new':window.console.navigate('work')
    cold=dict(elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
              peak_working_set_bytes=peak_memory())
    class ActiveWorker:
        def is_alive(self):return True
    window.worker=ActiveWorker()
    counts=dict(polls=0,native_probes=0)
    mapper=main.capture_region
    def observed(region,screens):
        counts['native_probes']+=1
        return mapper(region,screens)
    main.capture_region=observed
    window.timer.timeout.disconnect(window.poll)
    finished={}
    def tick():
        window.poll()
        counts['polls']+=1
        if counts['polls']>=40:
            assert not window.stop_event.is_set()
            finished.update(elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
                            peak_working_set_bytes=peak_memory(),**counts)
            window.worker=None
            app.quit()
    window.timer.timeout.connect(tick)
    window.timer.start(100)
    def abort():
        window.worker=None
        app.quit()
    main.QTimer.singleShot(7000,abort)
    started,cpu=time.perf_counter(),time.process_time()
    try:
        app.exec()
        warm=finished
        assert counts['polls']==40 and finished
        assert counts['native_probes']>=6
    finally:
        window.worker=None
        window.close()
        folder.cleanup()
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in digests.items())
    faulthandler.cancel_dump_traceback_later()
    return dict(mode=mode,cold=cold,warm=warm,origin=origin,sources=digests,
                dependencies=dict(PySide6=importlib.metadata.version('PySide6')),
                logical_regions=[subtitle,hud],screens=[list(screen.geometry().getRect()) for screen in app.screens()])


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=('old','new'))
    args=parser.parse_args()
    if args.worker:
        print('RESULT='+json.dumps(worker(args.worker)))
    else:
        providers=[]
        for mode in ('old','new'):
            task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode],
                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=60)
            (ROOT/f'analysis/console-poll-{mode}-stderr.txt').write_text(task.stderr,encoding='utf-8')
            if task.returncode:raise RuntimeError(task.stderr[-2000:])
            providers.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
        assert providers[0]['logical_regions']==providers[1]['logical_regions'] and providers[0]['screens']==providers[1]['screens']
        result=dict(status='PASS',providers=providers,limits=[
            'Completed GUI task: construct native Window, switch movie then screen, select same two areas, prepare physical coordinates, show1080x860known source/translation; new console work page; then40Qt timer polls configured100ms.',
            'Active worker is a controlled is_alive stand-in. No OCR/MT/MSS frame capture or real-game/device performance proof.',
            'Both tasks perform actual private QWindow/Win32 physical mapping probes once per second. No display settings were changed.',
            'Cold includes imports/Qt/window/selections/binding/first paint; warm excludes setup/cleanup. Source snapshots/digests prepared before timing.',
            'Fresh workers sequentially. CPU/peak are worker-process metrics with Qt threads; no worker child intentionally started; external process-family costs unmeasured.',
            'Lifetime working-set peak; single run; OS/background/cache uncontrolled; tokens unmeasured. Not a speedup claim.'])
        (ROOT/'analysis/console-poll-cost.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(dict(status='PASS',tasks=[dict(mode=p['mode'],warm=p['warm']) for p in providers])))
