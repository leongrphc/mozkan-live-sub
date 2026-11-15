"""Actual models: brief local changes that an entire-strip average can miss."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from benchmark_ocr_parity import peak_memory

ROOT=Path(__file__).resolve().parents[1]


def worker(mode):
    baseline=None
    source=ROOT/'src'
    origin=str(source)
    if mode=='old':
        archive=ROOT/'releases/AltyaziAtolyesi-0.3.4-update.zip'
        baseline=tempfile.TemporaryDirectory(prefix='atolye-034-gate-')
        source=Path(baseline.name)
        with zipfile.ZipFile(archive) as snapshot:
            for item in snapshot.infolist():
                parts=Path(item.filename).parts
                if len(parts)==3 and parts[:2]==('AltyaziAtolyesi','src') and parts[2].endswith('.py'):
                    (source/parts[2]).write_bytes(snapshot.read(item))
        origin=dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    names=('capture.py','engine.py','recognition.py')+(('subtitle_ocr.py',) if mode=='new' else ())
    identities={str(source/name):hashlib.sha256((source/name).read_bytes()).hexdigest() for name in names}
    models={str(path.name):hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT/'models/ocr').glob('*.onnx')}
    inputs=[]
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
    for name,background,fill,text,before in (('short',0,255,'No!',''),('faint',220,235,'We need to leave.',''),('counter',0,255,'121','120')):
        blank=Image.new('RGB',(950,65),(background,)*3)
        caption=blank.copy()
        if before:ImageDraw.Draw(blank).text((475,32),before,font=font,anchor='mm',fill=(fill,)*3)
        ImageDraw.Draw(caption).text((475,32),text,font=font,anchor='mm',fill=(fill,)*3)
        inputs.append((name,np.asarray(blank)[:,:,::-1].copy(),np.asarray(caption)[:,:,::-1].copy(),text))
    pins=[dict(name=name,expected=text,blank_sha256=hashlib.sha256(blank.tobytes()).hexdigest(),caption_sha256=hashlib.sha256(caption.tobytes()).hexdigest()) for name,blank,caption,text in inputs]
    start,cpu=time.perf_counter(),time.process_time()
    sys.path.insert(0,str(source))
    from capture import ChangeGate
    from engine import Engine
    engine=Engine(ROOT/'models')
    def task():
        results=[]
        for name,blank,caption,text in inputs:
            class Reader:
                calls=0
                def read(self,image):
                    self.calls+=1
                    return engine.read(image)
            reader=Reader()
            now=[0.]
            gate=ChangeGate(clock=lambda:now[0])
            gate.read(reader,blank)
            now[0]=.1
            result=gate.read(reader,caption)
            results.append(dict(name=name,expected=text,gate_text=result.text,fresh=gate.fresh,calls=reader.calls,
                                direct_text=engine.read(caption).text))
        return results
    results=task()
    cold=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,peak_working_set_bytes=peak_memory())
    start,cpu=time.perf_counter(),time.process_time()
    warm_results=task()
    warm=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,peak_working_set_bytes=peak_memory())
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in identities.items())
    return dict(mode=mode,origin=origin,sources=identities,models=models,fixtures=pins,results=results,warm_results=warm_results,cold=cold,warm=warm)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=('old','new'))
    args=parser.parse_args()
    if args.worker:print('RESULT='+json.dumps(worker(args.worker)))
    else:
        providers=[]
        for mode in ('old','new'):
            task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode],cwd=ROOT,
                capture_output=True,text=True,encoding='utf-8',timeout=60)
            (ROOT/f'analysis/change-gate-{mode}-stderr.txt').write_text(task.stderr,encoding='utf-8')
            if task.returncode:raise RuntimeError(task.stderr[-2000:])
            providers.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
        assert providers[0]['fixtures']==providers[1]['fixtures'] and providers[0]['models']==providers[1]['models']
        result=dict(providers=providers,limits=[
            'Three known generated950x65strips. Blank/old counter then changed caption at virtual0.1s, before2s periodic refresh. Actual OCR models, no capture/MT/desktop/game.',
            'Direct read after each gated read proves whether the model can read the same pixels. Additional inference has a correctness purpose; not a speedup comparison.',
            'Cold import/models/two cases+direct probes; warm repeats with fresh gates. Fresh sequential workers, worker threadCPU/lifetimepeak, no worker child.',
            'Source/model/input hashes pinned, setup excluded, OS cache uncontrolled, tokens unmeasured. Not universal local-change/noise detection proof.'])
        (ROOT/'analysis/change-gate-comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps([dict(mode=p['mode'],results=p['results']) for p in providers]))
