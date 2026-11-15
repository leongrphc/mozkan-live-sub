"""Fresh-process comparison of shipped pure caption semantics, no app execution."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from benchmark_ocr_parity import peak_memory

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=Path(r'C:\Users\MOZKAN\AppData\Local\Programs\Duplay\app')


def cases():
    tree=ast.parse((ROOT/'tests/test_dialogue.py').read_text(encoding='utf-8'))
    return {node.targets[0].id:ast.literal_eval(node.value) for node in tree.body
            if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)
            and node.targets[0].id in ('NEWEST_CASES','STACK_CASES')}


def worker(mode,repeats):
    fixtures=cases()
    source=REFERENCE/'cod_text.py' if mode=='reference' else ROOT/'src/dialogue.py'
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    start,cpu=time.perf_counter(),time.process_time()
    if mode=='reference':
        sys.path.insert(0,str(REFERENCE))
        import cod_text as producer
    else:
        sys.path.insert(0,str(ROOT/'src'))
        import dialogue as producer
    def evaluate():
        result=[]
        for name,raw,previous,_ in fixtures['NEWEST_CASES']:
            result.append(dict(name='newest/'+name,value=producer.newest_caption(raw,previous)))
        for name,sequence in fixtures['STACK_CASES']:
            stack=producer.CaptionStack()
            for index,text in enumerate(sequence):
                changed=stack.add(text)
                result.append(dict(name=f'stack/{name}/{index}',value=dict(changed=changed,stack=stack.as_dict())))
        return result
    results=evaluate()
    cold=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
              peak_working_set_bytes=peak_memory(),operations=len(results))
    start,cpu=time.perf_counter(),time.process_time()
    for _ in range(repeats):
        assert evaluate()==results
    warm=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
              peak_working_set_bytes=peak_memory(),operations=len(results)*repeats)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    return dict(mode=mode,source_path=str(source),source_sha256=digest,cold=cold,warm=warm,results=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=['reference','new'])
    parser.add_argument('--repeats',type=int,default=1000)
    args=parser.parse_args()
    if args.worker:
        print('RESULT='+json.dumps(worker(args.worker,args.repeats),ensure_ascii=True))
    else:
        providers=[]
        for mode in ('reference','new'):
            task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode,
                                 '--repeats',str(args.repeats)],cwd=ROOT,capture_output=True,
                                text=True,encoding='utf-8',timeout=90)
            if task.returncode:
                raise RuntimeError(task.stderr[-2000:])
            providers.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
        comparison=[dict(name=left['name'],equal=left['value']==right['value'],reference=left['value'],new=right['value'])
                    for left,right in zip(providers[0]['results'],providers[1]['results'],strict=True)]
        report=dict(providers=providers,comparison=comparison,matched=sum(item['equal'] for item in comparison),total=len(comparison),
                    fixtures_sha256=hashlib.sha256((ROOT/'tests/test_dialogue.py').read_bytes()).hexdigest(),limits=[
            'Finite pure caption fixtures; no OCR, GUI, game playback or TV runtime proof.',
            'Shipped cod_text module only; no original app, launcher or network execution.',
            'Fresh process/provider. Cold task includes producer import, first newest and stack fixture pass.',
            'Warm repeats identical operations with a fresh logical stack per sequence; process reuse.',
            'Process CPU includes threads; no worker children. Peak is lifetime working set.',
            'Orchestrator and fixture parsing excluded; OS cache uncontrolled; tokens unmeasured.'
        ])
        output=ROOT/'analysis/dialogue-parity.json'
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f"{report['matched']}/{report['total']} equal")
        for item in comparison:
            if not item['equal']:
                print(json.dumps(item,ensure_ascii=True))
