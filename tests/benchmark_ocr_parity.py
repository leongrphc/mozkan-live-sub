"""Bounded OCR producer comparison. Does not import or launch the reference app.

Each provider runs in its own fresh child, without target bytecode writes or
network access. Timed workers themselves create no child processes. Only the
reference producer and current production engine are compared.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path(r'C:\Users\MOZKAN\AppData\Local\Programs\Duplay\app')
for name in ('OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'MKL_NUM_THREADS'):
    os.environ[name] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'


def peak_memory():
    class Memory(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
    value = Memory()
    value.cb = ctypes.sizeof(value)
    query = ctypes.windll.psapi.GetProcessMemoryInfo
    query.argtypes = [ctypes.c_void_p, ctypes.POINTER(Memory), ctypes.c_ulong]
    query.restype = ctypes.c_int
    if not query(ctypes.c_void_p(-1), ctypes.byref(value), value.cb):
        raise ctypes.WinError()
    return value.PeakWorkingSetSize


def fixtures():
    from PIL import Image, ImageDraw, ImageFont
    cases = [
        ('single', (950, 130), 32, (255,255,255), (0,0,0),
         ['We need to leave before the guards return.']),
        ('two_lines', (950, 180), 30, (255,255,255), (0,0,0),
         ['We need to leave before the guards return.', 'Take the gold and go.']),
        ('punctuation', (900, 110), 30, (255,255,255), (0,0,0),
         ["Don't move! There's no time."]),
        ('pale', (950, 130), 30, (240,240,240), (205,205,205),
         ['We need to leave before the guards return.']),
        ('small', (950, 55), 20, (255,255,255), (0,0,0),
         ['We need to leave before the guards return.']),
        ('blank', (950, 130), 30, (255,255,255), (0,0,0), []),
    ]
    result = []
    for name, dimensions, size, foreground, background, lines in cases:
        image = Image.new('RGB', dimensions, background)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', size)
        line_height = size + 12
        top = max(3, (dimensions[1] - len(lines)*line_height)//2)
        for index, line in enumerate(lines):
            draw.text((20, top+index*line_height), line, font=font, fill=foreground)
        result.append((name, image, ' '.join(lines)))
    return result


def normalized(text):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text.casefold()).split())


def construct(mode):
    if mode == 'reference':
        sys.path.insert(0, str(REFERENCE))
        from ocr_engine import RapidSubtitleOCR
        reader = RapidSubtitleOCR(threads=2, boost=False)
        return reader.read
    sys.path.insert(0, str(ROOT/'src'))
    from engine import Engine
    import numpy as np
    engine = Engine(ROOT/'models')
    def read(image):
        result = engine.read(np.asarray(image)[:, :, ::-1].copy())
        return result.text,result.confidence,result.method
    return read


def worker(mode, passes):
    images = fixtures()
    inputs = [dict(case=name, width=image.width, height=image.height,
                   rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest(), expected=expected)
              for name,image,expected in images]
    source_file = REFERENCE/'ocr_engine.py' if mode == 'reference' else ROOT/'src/engine.py'
    source_digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
    owners = [source_file,REFERENCE/'caption_noise.py' if mode=='reference' else ROOT/'src/recognition.py']
    if mode=='new':
        owners.append(ROOT/'src/dialogue.py')
    identities = {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in owners}
    init_wall, init_cpu = time.perf_counter(), time.process_time()
    read = construct(mode)
    init = dict(elapsed_seconds=time.perf_counter()-init_wall, cpu_seconds=time.process_time()-init_cpu)
    first_wall, first_cpu = time.perf_counter(), time.process_time()
    first_text,first_confidence,first_method = read(images[0][1])
    first = dict(output=first_text,confidence=first_confidence,method=first_method, elapsed_seconds=time.perf_counter()-first_wall,
                 cpu_seconds=time.process_time()-first_cpu, peak_working_set_bytes=peak_memory())
    rows = []
    warm_wall, warm_cpu = time.perf_counter(), time.process_time()
    for iteration in range(passes):
        for name, image, expected in images:
            started, cpu = time.perf_counter(), time.process_time()
            actual,confidence,method = read(image)
            rows.append(dict(iteration=iteration, case=name, expected=expected, output=actual,
                             confidence=confidence,method=method,
                             exact=actual==expected, normalized_equal=normalized(actual)==normalized(expected),
                             elapsed_seconds=time.perf_counter()-started, cpu_seconds=time.process_time()-cpu))
    warm = dict(elapsed_seconds=time.perf_counter()-warm_wall, cpu_seconds=time.process_time()-warm_cpu,
                peak_working_set_bytes=peak_memory(), calls=len(rows),
                normalized_correct=sum(row['normalized_equal'] for row in rows))
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in identities.items())
    return dict(mode=mode, source_path=str(source_file), source_sha256=source_digest,source_identities=identities,
                input_fixtures=inputs,
                initialization=init, first_ocr=first,
                cold_completed_single=dict(elapsed_seconds=init['elapsed_seconds']+first['elapsed_seconds'],
                                           cpu_seconds=init['cpu_seconds']+first['cpu_seconds']),
                warm=warm, rows=rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=['reference','new'])
    parser.add_argument('--passes', type=int, default=2)
    parser.add_argument('--output', type=Path, default=ROOT/'analysis/ocr-parity-results.json')
    args = parser.parse_args()
    if args.worker:
        print('OCR_PARITY_RESULT='+json.dumps(worker(args.worker,args.passes),ensure_ascii=True))
        return
    results = []
    for mode in ('reference','new'):
        process = subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',str(Path(__file__).resolve()),
                                  '--worker',mode,'--passes',str(args.passes)],
                                 cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=240)
        (ROOT/f'analysis/ocr-parity-{mode}-stderr.txt').write_text(process.stderr,encoding='utf-8')
        if process.returncode:
            raise RuntimeError(f'{mode}: {process.stderr[-3000:]}')
        lines = [line for line in process.stdout.splitlines() if line.startswith('OCR_PARITY_RESULT=')]
        if len(lines)!=1:
            raise RuntimeError(f'Missing worker result for {mode}: {process.stdout[-1000:]}')
        results.append(json.loads(lines[0].split('=',1)[1]))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(results=results,limits=[
        'Six generated subtitle images, not real game/browser footage.',
        'Fresh process per mode; OS file cache uncontrolled. One cold sample per mode.',
        'Cold task includes producer import/construction/first OCR, excludes Python startup and fixture generation.',
        'Warm phase follows first OCR but reference read can perform adaptive retries and keepalive.',
        'Peak memory is cumulative process working-set peak, not a phase-specific allocation delta.',
        'Timed worker creates no child processes. Thread CPU included; orchestration cost excluded.',
        'Token usage unmeasured. Experimental fixed640 path was superseded by production normalization.',
    ]),ensure_ascii=False,indent=2),encoding='utf-8')
    print(str(args.output))


if __name__ == '__main__':
    main()
