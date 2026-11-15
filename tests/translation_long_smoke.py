"""Actual long unpunctuated local model input; verify chunk coverage and EOS."""
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from engine import Engine

root=Path(__file__).resolve().parents[1]
text=('We need to leave before the guards return and take the gold through the old railway station '
      'while the others wait beside the bridge and keep the door open ')*16
engine=Engine.__new__(Engine)
engine._translation_prepared=False
engine.model_path=root/'models/opus-mt-tc-big-en-tr-ct2'
engine.tokenizer=engine.translator=None
engine.cancelled=lambda:False
engine.ocr_kind='subtitle'
start=time.perf_counter()
engine.prepare_translation()
backend=engine.translator
facts=[]
class Observe:
    def translate_batch(self,sources,**options):
        results=backend.translate_batch(sources,**options)
        facts.append(dict(sources=sources,limit=options['max_decoding_length'],
            input_limit=options['max_input_length'],
            outputs=[item.hypotheses for item in results]))
        return results
engine.translator=Observe()
target=engine._translate_neural(text,lambda:True)
encoded=engine.tokenizer.convert_ids_to_tokens(engine.tokenizer.encode(text,add_special_tokens=False))
observed=[token for chunk in facts[0]['sources'] for token in chunk[:-1]]
assert observed==encoded and len(encoded)>160
assert all(chunk[-1]=='</s>' and len(chunk)<=161 for chunk in facts[0]['sources'])
assert target and all(hypotheses and hypotheses[0][-1]=='</s>' for hypotheses in facts[-1]['outputs'])
print(json.dumps(dict(status='PASS',source_chars=len(text),source_tokens=len(encoded),
    chunks=len(facts[0]['sources']),device=backend.device,elapsed_seconds=time.perf_counter()-start,
    source_sha256=hashlib.sha256(text.encode()).hexdigest(),target=target,calls=facts,
    production_sources={name:hashlib.sha256((root/'src'/name).read_bytes()).hexdigest() for name in ('engine.py','translation_backend.py')},
    scope='Known repeated English prose, actual offline tokenizer/CT2, exact input-token coverage and successful EOS. No silent input truncation.',
    limits='EOS does not prove semantic completeness or translation quality. No game/native capture. Elapsed only, CPU/VRAM/memory/tokens unmeasured.')))
