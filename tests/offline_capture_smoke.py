"""Actual OCR/MT/voting/clear lifecycle on generated frames; no desktop capture."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--movie',action='store_true')
parser.add_argument('--stacked',action='store_true')
parser.add_argument('--installation',type=Path,default=ROOT)
args=parser.parse_args()
if args.movie and args.stacked:
    parser.error('Film ve diyalog modu ayrı akışlardır.')
INSTALLATION=args.installation.resolve(strict=True)
sys.path.insert(0,str(INSTALLATION/'src'))
from benchmark_ocr_parity import fixtures, peak_memory
from capture import run_capture
import numpy as np

_,image,expected=fixtures()[0]
captions=[np.asarray(image)[:,:,::-1].copy()]
expected_sources=[expected]
if args.stacked:
    from PIL import Image,ImageDraw,ImageFont
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',32)
    captions=[]
    for lines in (['PRICE: Wait here.'],['PRICE: Wait here.','GHOST: Leave now.']):
        picture=Image.new('RGB',(950,130),(0,0,0))
        draw=ImageDraw.Draw(picture)
        for index,line in enumerate(lines):
            draw.text((20,10+index*45),line,font=font,fill='white')
        captions.append(np.asarray(picture)[:,:,::-1].copy())
    expected_sources=['PRICE: Wait here.','GHOST: Leave now.']
blank=np.zeros_like(captions[0])
phase=[0]
stop,translated=threading.Event(),threading.Event()
outputs,errors=[],[]
started,cpu=time.perf_counter(),time.process_time()
deadline=started+35
owners=['engine.py','recognition.py','stability.py','capture.py','dialogue.py']
identities={name:hashlib.sha256((INSTALLATION/'src'/name).read_bytes()).hexdigest() for name in owners}

def frames():
    while time.perf_counter()<deadline and not stop.is_set():
        yield blank if translated.is_set() else captions[phase[0]]
    if not stop.is_set():
        raise TimeoutError('Generated frame pipeline did not translate and clear within 35 seconds')

def output(source,target):
    outputs.append(dict(source=source,target=target,at_seconds=time.perf_counter()-started))
    if target:
        if phase[0]>=len(expected_sources) or source!=expected_sources[phase[0]]:
            errors.append('OCR source differs from generated caption')
        phase[0]+=1
        if phase[0]>=len(expected_sources):
            translated.set()
    elif not source and translated.is_set():
        stop.set()

run_capture(INSTALLATION/'models',(0,0,image.width,image.height),stop,output,lambda _:None,
            errors.append,frames=frames(),movie=args.movie,stacked=args.stacked,interval=.03)
assert translated.is_set(),outputs
assert outputs[-1]['source']==outputs[-1]['target']=='',outputs
assert not errors,errors
assert all(hashlib.sha256((INSTALLATION/'src'/name).read_bytes()).hexdigest()==digest for name,digest in identities.items())
print(json.dumps(dict(status='PASS',movie=args.movie,stacked=args.stacked,installation=str(INSTALLATION),outputs=outputs,
    elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
    peak_working_set_bytes=peak_memory(),source_identities=identities,
    scope='Generated frame injection through real production OCR/translation/voting/blank-clear; no desktop or real video capture.',
    limits='One cold task; process threads included, no children; OS cache uncontrolled; tokens unmeasured.'),ensure_ascii=True))
