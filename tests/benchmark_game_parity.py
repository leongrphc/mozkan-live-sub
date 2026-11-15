"""Finite game producer parity: fresh reference/new workers and explicit cases."""
from __future__ import annotations

from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from test_game_parity import CASES, ROWS, write_fixture
from benchmark_ocr_parity import peak_memory

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path(r'C:\Users\MOZKAN\AppData\Local\Programs\Duplay\app')


def worker(mode, repeats):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'fixture.sqlite'
        write_fixture(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source_path=REFERENCE/'game_memory.py' if mode=='reference' else ROOT/'src/profiles.py'
        source_digest=hashlib.sha256(source_path.read_bytes()).hexdigest()
        started,cpu=time.perf_counter(),time.process_time()
        if mode=='reference':
            sys.path.insert(0,str(REFERENCE))
            from game_memory import GameMemory
            profile=GameMemory(path)
            match=profile.find_dialogue
            source_path=REFERENCE/'game_memory.py'
        else:
            sys.path.insert(0,str(ROOT/'src'))
            from profiles import GameProfile
            profile=GameProfile(path)
            match=profile.match
            source_path=ROOT/'src/profiles.py'
        def evaluate():
            output=[]
            for case in CASES:
                value=match(case['text'],case.get('previous'),case.get('ignore_speaker',True))
                output.append(dict(name=case['name'],hit=asdict(value) if value is not None else None))
            return output
        result=evaluate()
        cold=dict(elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
                  peak_working_set_bytes=peak_memory(),queries=len(CASES))
        started,cpu=time.perf_counter(),time.process_time()
        for _ in range(repeats):
            repeated=evaluate()
            if repeated!=result:
                raise AssertionError('Non-deterministic producer result within repeated task')
        warm=dict(elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
                  peak_working_set_bytes=peak_memory(),queries=len(CASES)*repeats)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise AssertionError('Producer mutated fixture database')
        if hashlib.sha256(source_path.read_bytes()).hexdigest()!=source_digest:
            raise AssertionError('Producer changed during measurement')
        return dict(mode=mode,source_path=str(source_path),source_sha256=source_digest,
                    fixture_sha256=digest,cold=cold,warm=warm,cases=result)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=['reference','new'])
    parser.add_argument('--repeats',type=int,default=100)
    parser.add_argument('--output',type=Path,default=ROOT/'analysis/game-parity-results.json')
    args=parser.parse_args()
    if args.worker:
        print('GAME_PARITY_RESULT='+json.dumps(worker(args.worker,args.repeats),ensure_ascii=True))
        return
    results=[]
    for mode in ('reference','new'):
        task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',str(Path(__file__).resolve()),
                             '--worker',mode,'--repeats',str(args.repeats)],
                            cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120)
        (ROOT/f'analysis/game-parity-{mode}-stderr.txt').write_text(task.stderr,encoding='utf-8')
        if task.returncode:
            raise RuntimeError(mode+': '+task.stderr[-3000:])
        marker=[line for line in task.stdout.splitlines() if line.startswith('GAME_PARITY_RESULT=')]
        if len(marker)!=1:
            raise RuntimeError('Worker output missing: '+mode)
        results.append(json.loads(marker[0].split('=',1)[1]))
    reference,new=results
    comparisons=[dict(name=left['name'],equal=left['hit']==right['hit'],reference=left['hit'],new=right['hit'])
                 for left,right in zip(reference['cases'],new['cases'])]
    report=dict(results=results,comparisons=comparisons,matched=sum(row['equal'] for row in comparisons),
                total=len(comparisons),fixture_rows=ROWS,fixture_cases=CASES,limits=[
        'Finite generated schema-valid SQLite fixture; no real game or OCR runtime evidence.',
        'Reference GameMemory.find_dialogue only; no original app, launcher or network execution.',
        'Fresh process per provider; cold task includes import, construction and first full query set.',
        'Warm phase uses the same profile for the declared repeated query task.',
        'Timed workers create no children; CPU includes their threads; orchestrator excluded.',
        'Peak working set is cumulative process lifetime, not allocation delta.',
        'Token usage unmeasured; OS file cache uncontrolled; one run per provider.',
        'Parity is limited to the listed key/source/translation/confidence/kind observations.'
    ])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"{report['matched']}/{report['total']} equal; {args.output}")


if __name__=='__main__':
    main()
