"""Actual independent OCR tasks with known pale/blank fixtures and source pins."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile
from benchmark_ocr_parity import peak_memory
from ocr_quality_fixtures import fixtures

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=Path('C:/Users/MOZKAN/AppData/Local/Programs/Duplay/app')


def worker(mode):
    source=ROOT/'src'
    baseline=None
    origin=str(source)
    if mode=='old':
        archive=ROOT/'releases/AltyaziAtolyesi-0.3.4-update.zip'
        baseline=tempfile.TemporaryDirectory(prefix='atolye-034-ocr-')
        source=Path(baseline.name)
        with zipfile.ZipFile(archive) as snapshot:
            for item in snapshot.infolist():
                parts=Path(item.filename).parts
                if len(parts)==3 and parts[:2]==('AltyaziAtolyesi','src') and parts[2].endswith('.py'):
                    (source/parts[2]).write_bytes(snapshot.read(item))
        origin=dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    if mode.startswith('reference'):
        source=REFERENCE
        origin=str(source)
        names=('ocr_engine.py','caption_noise.py')
    else:
        names=('engine.py','recognition.py')+(('subtitle_ocr.py',) if mode!='old' else ())
    identities={str(source/name):hashlib.sha256((source/name).read_bytes()).hexdigest() for name in names}
    model_root=(REFERENCE if mode.startswith('reference') else ROOT)/'models/ocr'
    models={str(path.name):hashlib.sha256(path.read_bytes()).hexdigest() for path in model_root.glob('*.onnx')}
    images=fixtures()
    virtual=[0.]
    fixture_pins=[dict(name=name,expected=expected,size=image.size,rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest()) for name,image,expected in images]
    started,cpu=time.perf_counter(),time.process_time()
    sys.path.insert(0,str(source))
    if mode.startswith('reference'):
        from ocr_engine import RapidSubtitleOCR
        import ocr_engine
        from types import SimpleNamespace
        ocr_engine.time=SimpleNamespace(monotonic=lambda:virtual[0],perf_counter=time.perf_counter)
        reader=RapidSubtitleOCR(threads=2,boost=False)
        def read(image):
            text,confidence,method=reader.read(image,accurate=mode=='reference-accurate',scene_mode='auto')
            return dict(text=text,confidence=confidence,method=method)
    else:
        import numpy as np
        from engine import Engine
        reader=Engine(ROOT/'models',**({} if mode=='old' else dict(quality='accurate' if mode=='accurate' else 'fast')))
        if mode!='old':reader.subtitle_reader.clock=lambda:virtual[0]
        def read(image):
            reading=reader.read(np.asarray(image)[:,:,::-1].copy())
            return dict(text=reading.text,confidence=reading.confidence,method=reading.method,
                        variant=getattr(reading,'variant',None),passes=1 if mode=='old' else len(reading.scans))
    def run():
        results=[]
        for name,image,expected in images:
            results.append(dict(name=name,expected=expected,**read(image)))
            virtual[0]+=.2
        return results
    results=run()
    cold=dict(elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,peak_working_set_bytes=peak_memory(),images=len(images))
    started,cpu=time.perf_counter(),time.process_time()
    warm_results=run()
    warm=dict(elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,peak_working_set_bytes=peak_memory(),images=len(images))
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in identities.items())
    assert all(hashlib.sha256(path.read_bytes()).hexdigest()==models[path.name] for path in model_root.glob('*.onnx'))
    return dict(mode=mode,origin=origin,sources=identities,models=models,fixtures=fixture_pins,
                cold=cold,warm=warm,results=results,warm_results=warm_results,
                dependencies={name:importlib.metadata.version(name) for name in ('rapidocr','onnxruntime','numpy','opencv-python-headless')})


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=('old','fast','accurate','reference-fast','reference-accurate'))
    args=parser.parse_args()
    if args.worker:
        print('RESULT='+json.dumps(worker(args.worker)))
    else:
        providers=[]
        for mode in ('old','fast','accurate','reference-fast','reference-accurate'):
            task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode],cwd=ROOT,
                capture_output=True,text=True,encoding='utf-8',timeout=120)
            (ROOT/f'analysis/ocr-quality-{mode}-stderr.txt').write_text(task.stderr,encoding='utf-8')
            if task.returncode:raise RuntimeError(task.stderr[-2500:])
            providers.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
        assert all(p['fixtures']==providers[0]['fixtures'] and p['models']==providers[0]['models'] for p in providers)
        normalize=lambda text:' '.join(text.casefold().split())
        summary=[dict(mode=p['mode'],exact=sum(normalize(r['text'])==normalize(r['expected']) for r in p['results']),total=len(p['results']),
                      mismatches=[r for r in p['results'] if normalize(r['text'])!=normalize(r['expected'])]) for p in providers]
        report=dict(providers=providers,summary=summary,limits=[
            'Known generated single-line/blank strips only; no gameplay/streaming/display or universal OCR quality proof.',
            'Fresh sequential workers, source/model/input/dependencies pinned. Reference pure OCR producer only, boostFalse; no original GUI/license/network execution.',
            'Cold import/models/first fixture pass; warm second fixture pass with temporal adaptive state retained. Adaptive/keepalive clock advances virtual0.2s/frame equally; elapsed measures real work, not waits.',
            'CPU includes threads, lifetime worker peak; workers create no child. Setup/pins/orchestration excluded. OS cache uncontrolled; tokens unmeasured.',
            'Reference/new preprocessing/row grouping/confidence/noise policies differ; exact ground-truth results alone do not prove all behavior parity.'])
        (ROOT/'analysis/ocr-quality-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(summary))
