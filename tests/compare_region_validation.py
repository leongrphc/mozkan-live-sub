"""Compare only the shipped pure saved-region validator; no reference GUI."""
import ast
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from regions import rectangle

root=Path(__file__).resolve().parents[1]
reference=Path('C:/Users/MOZKAN/AppData/Local/Programs/Duplay/app/console_bridge.py')
paths=[reference,root/'src/regions.py']
digests={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
node=next(node for node in ast.walk(ast.parse(reference.read_text(encoding='utf-8')))
          if isinstance(node,ast.FunctionDef) and node.name=='_valid_region')
node.decorator_list=[]
namespace={}
exec(compile(ast.Module(body=[node],type_ignores=[]),str(reference),'exec'),namespace)
cases=[None,False,'100,100,500,65',{},(100,100,500),(100,100,500,65,0),
       (100,100,500,65),[100,100,500,65],(-99999,-99999,40,18),
       (100000,100,500,65),(-100000,100,500,65),(100,100000,500,65),
       (100,100,39,65),(100,100,40,18),(100,100,500,17),(100,100,30000,20000),
       (100,100,30001,65),(100,100,500,20001),(True,100,500,65),(100,100,False,65),
       (100.,100,500,65),(100,100,500.,65),(100,100,500,0),(100,100,-1,65),
       (10**500,100,500,65),(100,100,500,float('nan'))]
observations=[]
for index,case in enumerate(cases):
    expected=namespace['_valid_region'](case)
    try:
        rectangle(case,selection=True)
        actual=True
    except ValueError:
        actual=False
    assert expected==actual,(index,repr(case),expected,actual)
    observations.append(dict(index=index,input_repr=repr(case),reference=expected,new=actual))
assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in digests.items())
print(json.dumps(dict(status='PASS',same=len(cases),total=len(cases),sources=digests,cases=observations,
    scope='Pure reference _valid_region vs new saved-selection scalar/shape bounds only.',
    limits='Reference saves logical/physical tuples without monitor metadata checks in _load (source-derived). New restore revalidates monitor configuration and recomputes physical mapping before start. Not whole UI/runtime equivalence or physical display-change proof. No cost measurement.')))
