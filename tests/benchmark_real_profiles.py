"""Compare finite source-bound queries over each real bundled profile."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from benchmark_ocr_parity import peak_memory

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path(r'C:\Users\MOZKAN\AppData\Local\Programs\Duplay\app')


def run_worker(mode, path, samples):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    source = REFERENCE/'game_memory.py' if mode == 'reference' else ROOT/'src/profiles.py'
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    start, cpu = time.perf_counter(), time.process_time()
    if mode == 'reference':
        sys.path.insert(0,str(REFERENCE))
        from game_memory import GameMemory
        profile = GameMemory(path)
        rows = [(r[0],r[1],r[3]) for r in profile.entries]
        match = profile.find_dialogue
        source = REFERENCE/'game_memory.py'
    else:
        sys.path.insert(0,str(ROOT/'src'))
        from profiles import GameProfile
        profile = GameProfile(path)
        rows = [(r.key,r.source,r.normalized) for r in profile.rows]
        match = profile.match
        source = ROOT/'src/profiles.py'
    load = dict(elapsed=time.perf_counter()-start,cpu=time.process_time()-cpu)
    cases=[]
    for index in range(samples):
        ordinal = min(len(rows)-1,index*len(rows)//samples)
        key,text,norm=rows[ordinal]
        cases.extend([dict(ordinal=ordinal,kind='source',text=text,previous=None),
                      dict(ordinal=ordinal,kind='glued',text=text.replace(' ','',1),previous=None),
                      dict(ordinal=ordinal,kind='speaker',text='ARTHUR: '+text,previous=None)])
        words=norm.split()
        if len(words)>=10:
            cases.extend([dict(ordinal=ordinal,kind='prefix',text=' '.join(words[:len(words)//2]),previous=None),
                          dict(ordinal=ordinal,kind='tail',text=' '.join(words[len(words)//2:]),previous=key)])
    start,cpu=time.perf_counter(),time.process_time()
    def evaluate():
        results=[]
        for case in cases:
            hit=match(case['text'],case['previous'])
            results.append(dict(case=case,hit=asdict(hit) if hit else None))
        return results
    results=evaluate()
    cold=dict(elapsed=time.perf_counter()-start,cpu=time.process_time()-cpu)
    start,cpu=time.perf_counter(),time.process_time()
    warm_results=evaluate()
    warm=dict(elapsed=time.perf_counter()-start,cpu=time.process_time()-cpu)
    if warm_results!=results:
        raise AssertionError('Repeated queries changed within one loaded profile')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_digest, 'Producer changed during measurement'
    return dict(mode=mode,path=str(path),profile_sha256=digest,source_sha256=source_digest,
                rows=len(rows),load=load,cold_queries=cold,warm_queries=warm,peak_bytes=peak_memory(),results=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=['reference','new'])
    parser.add_argument('--profile',type=Path)
    parser.add_argument('--samples',type=int,default=20)
    args=parser.parse_args()
    if args.worker:
        print('RESULT='+json.dumps(run_worker(args.worker,args.profile,args.samples),ensure_ascii=True))
    else:
        reports=[]
        for path in sorted((ROOT/'game_profiles').glob('*.sqlite')):
            results=[]
            for mode in ('reference','new'):
                task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode,
                                     '--profile',str(path),'--samples',str(args.samples)],
                                    cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=240)
                if task.returncode:
                    raise RuntimeError(task.stderr[-3000:])
                results.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
            differences=[dict(reference=left,new=right) for left,right in zip(results[0]['results'],results[1]['results']) if left!=right]
            report=dict(name=path.name,queries=len(results[0]['results']),differences=differences,providers=results)
            reports.append(report)
            print(path.name,'queries',report['queries'],'differences',len(differences),flush=True)
            (ROOT/'analysis/real-profile-parity.json').write_text(json.dumps(dict(reports=reports,limits=[
                'Finite evenly spaced stored rows and derived queries, not game playback or OCR accuracy.',
                'Fresh child per provider/profile; timed worker itself creates no child.',
                'Cold query pass follows loaded index; warm pass repeats identical queries; peak is lifetime process peak.',
                'OS cache uncontrolled; one run per provider/profile; token usage unmeasured.']),ensure_ascii=False,indent=2),encoding='utf-8')
