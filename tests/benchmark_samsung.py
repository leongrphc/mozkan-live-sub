"""Same controlled executable workload through old/new actual Qt adapters/jobs."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import zipfile
ROOT=Path(__file__).resolve().parents[1]


def worker(mode):
    baseline=None
    source=ROOT/'src'
    origin=str(source)
    if mode=='old':
        baseline=tempfile.TemporaryDirectory()
        source=Path(baseline.name)
        archive=ROOT/'releases/AltyaziAtolyesi-0.3.6-update.zip'
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                if item.filename.startswith('AltyaziAtolyesi/src/') and item.filename.endswith('.py'):
                    (source/Path(item.filename).name).write_bytes(z.read(item))
        origin=dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')}
    start,cpu=time.perf_counter(),time.process_time()
    sys.path.insert(0,str(source))
    from PySide6.QtCore import QCoreApplication
    from samsung import SamsungHelper
    app=QCoreApplication([])
    folder=tempfile.TemporaryDirectory()
    helper=SamsungHelper(ROOT/'samsung',Path(folder.name))
    launch=helper.process.start
    events=[]
    if mode=='old':helper.event.connect(events.append)
    else:helper.changed.connect(lambda state:events.append(asdict(state)))
    def fixture(program,args):
        command=[sys.executable,'-B','-E','-s','-X','utf8',str(ROOT/'tests/samsung_fixture.py')]
        if mode=='new':
            split=args.index('--')
            launch(program,args[:split+1]+command+args[split+2:])
        else:launch(command[0],command[1:]+args)
    def task():
        events.clear()
        helper.start('install','192.168.1.20','benchmark-token')
        deadline=time.monotonic()+10
        while helper.busy:
            app.processEvents()
            if time.monotonic()>deadline:
                helper.cancel()
                raise RuntimeError('Controlled helper did not complete')
            time.sleep(.002)
        return dict(observed_events=len(events),done=any(event.get('done') is True or event.get('event')=='done' for event in events))
    with patch.object(helper.process,'start',side_effect=fixture):
        first=task()
        cold=dict(elapsed_seconds=time.perf_counter()-start,parent_cpu_seconds=time.process_time()-cpu,result=first)
        start,cpu=time.perf_counter(),time.process_time()
        second=task()
        warm=dict(elapsed_seconds=time.perf_counter()-start,parent_cpu_seconds=time.process_time()-cpu,result=second)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in pins.items())
    folder.cleanup()
    return dict(mode=mode,origin=origin,sources=pins,cold=cold,warm=warm,
                fixture_sha256=hashlib.sha256((ROOT/'tests/samsung_fixture.py').read_bytes()).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=('old','new'))
    args=parser.parse_args()
    if args.worker:print('RESULT='+json.dumps(worker(args.worker)))
    else:
        sys.path.insert(0,str(ROOT/'src'))
        from windows_job import WindowsJob
        providers=[]
        for mode in ('old','new'):
            job=WindowsJob();job.configure()
            start=time.perf_counter()
            try:
                result=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',str(ROOT/'src/samsung_runner.py'),job.name,'--',
                    sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode],
                    capture_output=True,text=True,encoding='utf-8',timeout=15,cwd=ROOT)
                if result.returncode:raise RuntimeError(result.stderr[-2000:])
                completed=json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith('RESULT=')))
                completed['family_total']=job.metrics()
                completed['family_elapsed_seconds']=time.perf_counter()-start
                providers.append(completed)
            finally:
                if job.active():job.terminate()
                deadline=time.monotonic()+5
                while job.active() and time.monotonic()<deadline:time.sleep(.01)
                job.close()
        report=dict(providers=providers,limits=[
            'Controlled executable fixture through actual Qt process pipes. No original helper/TV/vendor/network work. Cold includes imports/QCoreApplication/first workload; warm repeats in same worker.',
            'Outer non-breakaway job contains benchmark runner, worker and all helper descendants for BOTH modes; resource containment is harness support, not an old-adapter ownership claim.',
            'Family total CPU and peak committed memory cover whole two-task job, including common outer runner. Parent CPU per phase excludes helper children; family phase split unmeasured.',
            'Fresh sequential workers, fixture/source pinned, peak job commit is not working set/VRAM. Setup extraction/orchestrator excluded, OS/cache uncontrolled, tokens unmeasured.',
            'New adapter persists bounded redacted logs and structured state; old discards final non-newline done. Workloads same but outcomes/features differ; no speedup claim.'])
        (ROOT/'analysis/samsung-cost-0.3.7.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps([dict(mode=p['mode'],cold=p['cold'],warm=p['warm'],family=p['family_total']) for p in providers]))
