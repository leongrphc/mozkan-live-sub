"""Production Engine using the selected installation's own runtime and models."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser()
parser.add_argument('--installation',type=Path,default=Path(__file__).resolve().parents[1])
parser.add_argument('--expect-device',choices=('cuda','cpu'))
args=parser.parse_args()
installation=args.installation.resolve()
sys.path.insert(0,str(installation/'src'))
import engine as module
import translation_backend

engine=module.Engine(installation/'models')
result=engine.translate('We need to leave before the guards return.')
assert result
backend=engine.translator
if args.expect_device:
    assert backend.device==args.expect_device,(backend.device,backend.cuda_failure)
assert Path(module.__file__).resolve().parent==installation/'src'
assert Path(translation_backend.__file__).resolve().parent==installation/'src'
print(json.dumps(dict(status='PASS',installation=str(installation),runtime=sys.executable,
    device=backend.device,cuda_failure=backend.cuda_failure,target=result,
    source_sha256={name:hashlib.sha256((installation/'src'/name).read_bytes()).hexdigest()
                   for name in ('engine.py','translation_backend.py')},
    scope='Actual selected production Engine, own OCR and translation models, real backend selection/inference. No capture or gameplay proof.')))
