"""Fresh old CPU/new auto/new HUD tasks with actual offline model bytes."""
import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import time
import tempfile
import zipfile
from pathlib import Path
from benchmark_ocr_parity import peak_memory

ROOT=Path(__file__).resolve().parents[1]
SOURCES=['Hello.','We need to leave before the guards return.',
         'Take the gold and go.','Open the door before sunrise.',
         'You have three minutes to reach the station.',
         'Please turn off the lights when you leave.',
         'I thought you said the bridge was safe.',
         'We will meet again. Stay here until I return.']


def worker(mode):
    baseline=None
    source=ROOT/'src'
    origin=dict(kind='working-source',path=str(source))
    if mode=='old-cpu':
        archive=ROOT/'releases/AltyaziAtolyesi-0.3.1-update.zip'
        baseline=tempfile.TemporaryDirectory(prefix='altyazi-031-source-')
        source=Path(baseline.name)
        with zipfile.ZipFile(archive) as snapshot:
            for item in snapshot.infolist():
                parts=Path(item.filename).parts
                if len(parts)==3 and parts[0]=='AltyaziAtolyesi' and parts[1]=='src' and parts[2].endswith('.py'):
                    (source/parts[2]).write_bytes(snapshot.read(item))
        origin=dict(kind='immutable-update',path=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    if mode=='reference-auto':
        source=Path('C:/Users/MOZKAN/AppData/Local/Programs/Duplay/app')
        origin=dict(kind='shipped-pure-module',path=str(source/'quality_engine.py'),model_override='own local identical-model bytes')
    paths=[source/name for name in (('quality_engine.py',) if mode=='reference-auto' else ('engine.py','dialogue.py'))]
    if mode not in ('old-cpu','reference-auto'):
        paths.append(source/'translation_backend.py')
    identities={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    models=ROOT/'models/opus-mt-tc-big-en-tr-ct2'
    digests={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(models.iterdir()) if path.is_file()}
    dependencies={name:importlib.metadata.version(name) for name in ('ctranslate2','transformers','sentencepiece')}
    start,cpu=time.perf_counter(),time.process_time()
    sys.path.insert(0,str(source))
    if mode=='reference-auto':
        import quality_engine
        quality_engine.QUALITY_MODEL_DIR=models
        engine=quality_engine.HighQualityTranslator(cpu_only=False)
        translate=engine.translate
    else:
        from engine import Engine
        engine=Engine.__new__(Engine)
        engine._translation_prepared=False
        engine.model_path=models
        engine.tokenizer=engine.translator=None
        engine.cancelled=lambda:False
        engine.ocr_kind='hud' if mode=='new-hud' else 'subtitle'
        if mode=='new-fallback':
            from transformers import AutoTokenizer
            from translation_backend import TranslationBackend
            engine.tokenizer=AutoTokenizer.from_pretrained(str(models),local_files_only=True,use_fast=False)
            engine.translator=TranslationBackend(models,cpu_only=False,guard=lambda:None,runtime_loader=lambda:None)
            assert engine.translator.device=='cuda','A real CUDA device is required for this failure probe'
        else:
            engine.prepare_translation()
        translate=lambda text:engine._translate_neural(text,lambda:True)
    results=[translate(text) for text in SOURCES]
    if mode=='new-fallback':
        assert engine.translator.device=='cpu' and engine.translator.cuda_failure,'Lazy CUDA failure was not reproduced'
    cold=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
              peak_working_set_bytes=peak_memory(),captions=len(SOURCES))
    start,cpu=time.perf_counter(),time.process_time()
    for _ in range(3):
        assert [translate(text) for text in SOURCES]==results
    warm=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
              peak_working_set_bytes=peak_memory(),captions=len(SOURCES)*3)
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in {**identities,**digests}.items())
    return dict(mode=mode,device=engine.translator.device,
                cuda_failure=getattr(engine.translator,'cuda_failure',None),
                cold=cold,warm=warm,sources=identities,source_origin=origin,models=digests,dependencies=dependencies,
                results=[dict(source=source,target=target) for source,target in zip(SOURCES,results,strict=True)])


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=('old-cpu','new-auto','new-hud','new-fallback','reference-auto'))
    args=parser.parse_args()
    if args.worker:
        print('RESULT='+json.dumps(worker(args.worker)))
    else:
        providers=[]
        for mode in ('old-cpu','new-auto','new-hud','new-fallback','reference-auto'):
            task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode],
                                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120)
            (ROOT/f'analysis/translation-device-{mode}-stderr.txt').write_text(task.stderr,encoding='utf-8')
            if task.returncode:
                raise RuntimeError(task.stderr[-2500:])
            providers.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
        assert all(item['models']==providers[0]['models'] and item['dependencies']==providers[0]['dependencies'] for item in providers)
        report=dict(status='PASS',providers=providers,matching_old=[dict(mode=item['mode'],same=sum(a==b for a,b in zip(item['results'],providers[0]['results'],strict=True)),total=len(SOURCES)) for item in providers[1:]],
            new_vs_reference=dict(same=sum(a==b for a,b in zip(providers[1]['results'],providers[-1]['results'],strict=True)),total=len(SOURCES)),
            limits=['Eight known English captions; repeated deterministic outputs, not broad translation quality proof.',
                    'Old immutable 0.3.1 update CPU source vs new auto GPU and CPU-only HUD. Same offline model/tokenizer/dependencies. New fallback deliberately omits DLL setup in a fresh worker to reproduce lazy CUBLAS failure.',
                    'Reference imports only shipped quality_engine.py with own local model override. No original GUI/licensing/network execution. Reference has two CUDA warmup sentences, new one; decoder limits differ, recorded in pinned source.',
                    'Cold includes source/import/tokenizer/model initialization, CUDA warmup when selected and first eight translations. Warm repeats eight captions three times without result cache.',
                    'Fresh worker per mode; no worker children, thread CPU included. Lifetime working-set peak; GPU VRAM and GPU compute time unmeasured.',
                    'OS/driver cache uncontrolled, tokens unmeasured, setup/digests and orchestration excluded. Single run, no real game contention.'])
        (ROOT/'analysis/translation-device-cost.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(dict(status=report['status'],matching_old=report['matching_old'],devices=[item['device'] for item in providers])))
