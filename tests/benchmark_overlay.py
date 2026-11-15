"""Compare identical caption-render tasks before/after the fill fix, offscreen."""
import argparse
import hashlib
import importlib.util
import json
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import zipfile
from benchmark_ocr_parity import peak_memory

ROOT=Path(__file__).resolve().parents[1]


def worker(mode,repeats):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage,QFontDatabase,QFont
    import numpy as np
    sys.path.insert(0,str(ROOT/'src'))
    with tempfile.TemporaryDirectory() as folder:
        if mode=='before':
            with zipfile.ZipFile(ROOT/'releases/AltyaziAtolyesi-0.2.6-update.zip') as archive:
                payload=archive.read('AltyaziAtolyesi/src/overlay.py')
            source=Path(folder)/'overlay.py'
            source.write_bytes(payload)
        else:
            source=ROOT/'src/overlay.py'
            payload=source.read_bytes()
        digest=hashlib.sha256(payload).hexdigest()
        app=QApplication([])
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
        app.setFont(QFont('Segoe UI',10))
        start,cpu=time.perf_counter(),time.process_time()
        spec=importlib.util.spec_from_file_location('measured_overlay',source)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        overlay=module.Overlay()
        source_text='<span style="color:#26E6DC">PRICE:</span> Burada bekle.<br><span style="color:#80BEFA">GHOST:</span> Şimdi git.'
        with (patch.object(overlay,'_try_capture_exclusion',return_value=False) if hasattr(overlay,'_try_capture_exclusion') else patch.object(module,'try_capture_exclusion',return_value=False)):
            assert overlay.present(source_text,(100,400,600,70),rich=True),overlay.last_error
            first=overlay.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
            cold=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
                      peak_working_set_bytes=peak_memory(),renders=1)
            start,cpu=time.perf_counter(),time.process_time()
            for _ in range(repeats):
                final=overlay.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
            warm=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
                      peak_working_set_bytes=peak_memory(),renders=repeats)
        pixels=np.frombuffer(bytes(final.bits()),dtype=np.uint8).reshape(final.height(),final.bytesPerLine()//4,4)[:,:final.width()]
        filled=((pixels[:,:,:3].max(axis=2)>180)&(pixels[:,:,3]>200))
        final.save(str(ROOT/f'analysis/overlay-fill-{mode}.png'))
        overlay.close()
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
        return dict(mode=mode,source_sha256=digest,cold=cold,warm=warm,
                    colored_or_white_fill_pixels=int(np.count_nonzero(filled)))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=['before','new'])
    parser.add_argument('--repeats',type=int,default=500)
    args=parser.parse_args()
    if args.worker:
        print('RESULT='+json.dumps(worker(args.worker,args.repeats)))
    else:
        results=[]
        for mode in ('before','new'):
            task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode,'--repeats',str(args.repeats)],
                                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=60)
            if task.returncode:
                raise RuntimeError(task.stderr[-2000:])
            results.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
        report=dict(results=results,limits=[
            'Identical fixed two-line rich caption, font24/stroke2/default background, Qt offscreen; no desktop or gameplay claim.',
            'Before source is from immutable 0.2.6 update archive; new is production source.',
            'Before visibly loses fill, so output correctness differs; this is cost of the fix, not an equivalent-quality speedup claim.',
            'Cold includes Overlay import/construction/first render, excludes Qt/numpy import, QApplication startup and production font registration.',
            'Warm repeats grab+RGBA conversion of same shaped document; no reflow or native window acquisition.',
            'Fresh worker/provider, no children; CPU includes threads, peak is lifetime process working set.',
            'Token usage unmeasured, OS cache uncontrolled, one run/provider; orchestrator excluded.'
        ])
        (ROOT/'analysis/overlay-fill-cost.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(results))
