"""Actual word OCR/visual badges against shipped quest producer; no app launch."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from benchmark_ocr_parity import peak_memory
from hud_fixtures import fixtures
ROOT=Path(__file__).resolve().parents[1]
REFERENCE=Path(r'C:\Users\MOZKAN\AppData\Local\Programs\Duplay\app')


def worker(mode,passes):
    import cv2
    import numpy as np
    cv2.setNumThreads(1)
    images=fixtures()
    paths=([REFERENCE/name for name in ('ocr_engine.py','button_marks.py','caption_noise.py')]
           if mode=='reference' else [ROOT/'src'/name for name in ('engine.py','recognition.py','hud.py','dialogue.py')])
    identities={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    model_root=(REFERENCE if mode=='reference' else ROOT)/'models/ocr'
    models={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(model_root.glob('*.onnx'))}
    started,cpu=time.perf_counter(),time.process_time()
    if mode=='reference':
        sys.path.insert(0,str(REFERENCE))
        from ocr_engine import RapidSubtitleOCR
        from button_marks import compose,find_buttons
        reader=RapidSubtitleOCR(threads=1,boost=False)
        def read(image):
            words=reader.read_quest(image)
            badges=find_buttons(image,words,reader.read_label)
            return dict(text=compose(words,badges),badges=badges,words=words)
    else:
        sys.path.insert(0,str(ROOT/'src'))
        from engine import Engine
        reader=Engine(ROOT/'models',ocr_kind='hud')
        def read(image):
            result=reader.read(np.asarray(image)[:,:,::-1].copy())
            return dict(text=result.text,badges=[asdict(badge) for badge in result.badges],
                        words=[asdict(word) for word in result.words],method=result.method)
    observations=[dict(name=name,**read(image)) for name,image in images]
    cold=dict(elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
              peak_working_set_bytes=peak_memory(),images=len(images))
    started,cpu=time.perf_counter(),time.process_time()
    for _ in range(passes):
        repeated=[dict(name=name,**read(image)) for name,image in images]
        assert repeated==observations,'Non-deterministic repeated HUD result'
    warm=dict(elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
              peak_working_set_bytes=peak_memory(),images=len(images)*passes)
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in identities.items())
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in models.items())
    return dict(mode=mode,identities=identities,cold=cold,warm=warm,results=observations,
                models=models,configuration=dict(detector_max_side=640 if mode=='reference' else 960,word_frame_max_side=960,onnx_threads=1),
                fixtures=[dict(name=name,size=image.size,rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest()) for name,image in images])


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=['reference','new'])
    parser.add_argument('--passes',type=int,default=2)
    args=parser.parse_args()
    if args.worker:
        print('RESULT='+json.dumps(worker(args.worker,args.passes),ensure_ascii=True))
    else:
        providers=[]
        for mode in ('reference','new'):
            task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode,'--passes',str(args.passes)],
                                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120)
            (ROOT/f'analysis/hud-parity-{mode}-stderr.txt').write_text(task.stderr,encoding='utf-8')
            if task.returncode:
                raise RuntimeError(task.stderr[-2000:])
            providers.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
        assert providers[0]['fixtures']==providers[1]['fixtures']
        comparison=[dict(name=left['name'],text_equal=left['text']==right['text'],reference=left['text'],new=right['text'],
                         reference_badges=[b['name'] for b in left['badges']],new_badges=[b['name'] for b in right['badges']])
                    for left,right in zip(providers[0]['results'],providers[1]['results'],strict=True)]
        report=dict(providers=providers,comparison=comparison,matched=sum(row['text_equal'] for row in comparison),total=len(comparison),limits=[
            f'{len(comparison)} generated English HUD crops with drawn badges; no game/physical controller/native desktop evidence.',
            'Shipped OCR/read_quest/button_marks only, boost disabled; no original app/launcher/licensing/network execution.',
            'Fresh worker/provider, no worker children; CPU includes threads, peak is lifetime working set.',
            'Cold includes producer import/construction and first fixture pass; warm repeats declared passes after cold.',
            'Reference constructor has a subtitle warmup; new HUD instance loads on first actual crop.',
            'Source/dependencies/model/fixture bytes pinned; preparation/hash validation excluded from timed phases. OS cache uncontrolled; tokens unmeasured; orchestration excluded.',
            'Word geometry levels and visual badge facts retained inline; matching text alone does not establish geometry equality.'
        ])
        (ROOT/'analysis/hud-parity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f"{report['matched']}/{report['total']} same text")
        print(json.dumps(comparison,ensure_ascii=True))
