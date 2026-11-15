"""Compare only the shipped pure nudge function; never import the reference app."""
import ast
import hashlib
import json
import os
import sys
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication
from overlay import Overlay

root=Path(__file__).resolve().parents[1]
reference=Path('C:/Users/MOZKAN/AppData/Local/Programs/Duplay/app/cod_overlay.py')
paths=[reference,root/'src/overlay.py',root/'src/appearance.py']
def identities():
    return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
before=identities()
node=next(node for node in ast.parse(reference.read_text(encoding='utf-8')).body
          if isinstance(node,ast.FunctionDef) and node.name=='_nudge_rect')
namespace={'QRect':QRect}
exec(compile(ast.Module(body=[node],type_ignores=[]),str(reference),'exec'),namespace)
app=QApplication([])
overlay=Overlay()
observations=[]
for area in (QRect(0,0,1920,1080),QRect(-1920,-200,1920,1080),QRect(0,-720,1280,720)):
    source=QRect(area.left()+100,area.top()+500,900,65)
    width,height=600,80
    for position in ('top','bottom','above_region'):
        overlay.configure(position=position,y_offset=0)
        base,actual=overlay._placement(area,source,width,height,True)
        assert base is not None and actual==position
        for steps in (-40,-2,0,2,40):
            overlay.configure(y_offset=steps)
            observed,actual=overlay._placement(area,source,width,height,True)
            expected=namespace['_nudge_rect'](base,steps,area)
            assert observed==expected,(area,position,steps,observed,expected)
            observations.append(dict(screen=list(area.getRect()),position=position,steps=steps,
                                     reference=list(expected.getRect()),new=list(observed.getRect())))
overlay.close()
assert before==identities()
print(json.dumps(dict(status='PASS',same=len(observations),sources=before,cases=observations,
    scope='Pure shipped nudge vs production placement; generated valid base rectangles. Integer steps, three screen origins, top/bottom/above. Capture exclusion confirmed in model.',
    limits='Not whole target_rect/layout equivalence or actual multimonitor/DPI/runtime proof. No timing or token measurement.')))
