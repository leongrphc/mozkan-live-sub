"""Completed synthetic OCR→translation task; run each mode in a fresh process."""
import argparse
import ctypes
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from engine import Engine
from capture import ChangeGate

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['every-frame', 'change-gate'])
parser.add_argument('--models', type=Path, required=True)
args = parser.parse_args()
image = Image.new('RGB', (900, 130), 'black')
ImageDraw.Draw(image).text((20, 30), 'We need to leave before the guards return.',
                          font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 32), fill='white')
frame = np.array(image)[:, :, ::-1].copy()
started, cpu = time.perf_counter(), time.process_time()
engine = Engine(args.models)
gate = ChangeGate()
read = engine.read if args.mode == 'every-frame' else lambda f: gate.read(engine, f)
results = []
for index in range(12):
    source = read(frame).text
    results.append(engine.translate(source))
assert all(results) and len(set(results)) == 1
elapsed, cpu_used = time.perf_counter() - started, time.process_time() - cpu
class Memory(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
memory = Memory()
memory.cb = ctypes.sizeof(memory)
query_memory = ctypes.windll.psapi.GetProcessMemoryInfo
query_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(Memory), ctypes.c_ulong]
query_memory.restype = ctypes.c_int
if not query_memory(ctypes.c_void_p(-1), ctypes.byref(memory), memory.cb):
    raise ctypes.WinError()
print(json.dumps(dict(mode=args.mode, frames=12, elapsed_seconds=elapsed,
                      cpu_seconds=cpu_used, process_peak_working_set_bytes=memory.PeakWorkingSetSize,
                      translation=results[-1], source=source,
                      scope='fresh Python process; model cold start then repeated identical frames; no child processes',
                      token_usage='unmeasured'), ensure_ascii=True))
