"""Actual file workflows against immutable0.3.3 and current settings owner."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import zipfile
from benchmark_ocr_parity import peak_memory

ROOT=Path(__file__).resolve().parents[1]


def worker(mode):
    baseline=None
    source=ROOT/'src'
    origin=str(source)
    if mode=='old':
        archive=ROOT/'releases/AltyaziAtolyesi-0.3.3-update.zip'
        baseline=tempfile.TemporaryDirectory(prefix='altyazi-033-settings-')
        source=Path(baseline.name)
        with zipfile.ZipFile(archive) as snapshot:
            for item in snapshot.infolist():
                parts=Path(item.filename).parts
                if len(parts)==3 and parts[:2]==('AltyaziAtolyesi','src') and parts[2].endswith('.py'):
                    (source/parts[2]).write_bytes(snapshot.read(item))
        origin=dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    sources={str(source/name):hashlib.sha256((source/name).read_bytes()).hexdigest()
             for name in ('settings.py','regions.py','coordinates.py','appearance.py')}
    folder=tempfile.TemporaryDirectory()
    root=Path(folder.name)
    start,cpu=time.perf_counter(),time.process_time()
    sys.path.insert(0,str(source))
    import settings as module
    def workflows(phase):
        directory=root/phase
        directory.mkdir()
        raw=b'{"font_size":24,"regions":{"version":99,"subtitle":null,"hud":null}}'
        path=directory/'malformed.json'
        path.write_bytes(raw)
        settings=module.Settings(path)
        settings.save(font_size=30)
        settings.save(regions=dict(version=1,subtitle=None,hud=None))
        settings.save(font_size=32)
        original_survives=any(file.read_bytes()==raw for file in directory.glob('*.json*'))
        path=directory/'mutation.json'
        settings=module.Settings(path)
        value=dict(version=1,subtitle=None,hud=None)
        extra=dict(items=['original'])
        settings.save(regions=value,extra=extra)
        value['version']=99
        extra['items'][0]='mutated'
        settings.save(font_size=30)
        caller_result=json.loads(path.read_bytes())
        path=directory/'foreign.json'
        settings=module.Settings(path)
        foreign=b'{"font_size":40,"mode":"movie"}'
        replace=module.os.replace
        def intervene(source,destination):
            replace(source,destination)
            Path(destination).write_bytes(foreign)
        with patch.object(module.os,'replace',side_effect=intervene):
            settings.save(font_size=30)
        adopted=settings.loaded_bytes==foreign
        blocked=False
        reason=None
        try:
            settings.save(dialogue=True)
        except OSError as exc:
            blocked=True
            reason=str(exc)
        return dict(original_malformed_source_survives=original_survives,
                    caller_region_version_persisted=caller_result['regions']['version'],
                    caller_extra_persisted=caller_result['extra'],
                    adopted_foreign_snapshot=adopted,followup_blocked=blocked,
                    foreign_preserved=path.read_bytes()==foreign,followup_reason=reason)
    observed=workflows('cold')
    cold=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,peak_working_set_bytes=peak_memory())
    start,cpu=time.perf_counter(),time.process_time()
    assert workflows('warm')==observed
    warm=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,peak_working_set_bytes=peak_memory())
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in sources.items())
    folder.cleanup()
    return dict(mode=mode,sources=sources,origin=origin,results=observed,cold=cold,warm=warm)


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
            (ROOT/f'analysis/settings-owner-{mode}-stderr.txt').write_text(task.stderr,encoding='utf-8')
            if task.returncode:raise RuntimeError(task.stderr[-2000:])
            providers.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
        old,new=[p['results'] for p in providers]
        assert not old['original_malformed_source_survives'] and old['adopted_foreign_snapshot'] and not old['foreign_preserved']
        assert new['original_malformed_source_survives'] and not new['adopted_foreign_snapshot'] and new['foreign_preserved'] and new['followup_blocked']
        assert old['caller_extra_persisted']==dict(items=['mutated']) and new['caller_extra_persisted']==dict(items=['original'])
        result=dict(status='PASS',providers=providers,limits=[
            'Actual tempfile I/O on three known workflows: malformed region source then explicit repair and independent font save, caller mutation, intervening writer immediately after commit.',
            'Intervening writer is a deterministic os.replace boundary hook that performs a real write, not an uncontrolled multiprocess race. No cross-process transaction lock established.',
            'Fresh sequential workers, immutable0.3.3 vs current source. Cold includes module import+three workflows; warm repeats all three with new files, no import.',
            'Worker CPU/lifetime peak; no child started in workers, orchestration excluded. OS cache uncontrolled, token usage unmeasured, single run.',
            'Small typical settings fixtures only;1MiB worst-case save cost unmeasured. Corrected outcomes differ; no speedup claim.'])
        (ROOT/'analysis/settings-owner-comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(dict(status='PASS',results=[dict(mode=p['mode'],**p['results']) for p in providers])))
