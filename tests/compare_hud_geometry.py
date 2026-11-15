"""Isolated shipped _hud_fraction AST vs owned region geometry, no app launch."""
import ast
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtCore import QPoint,QRect
from coordinates import normalized_region
from test_coordinates import Screen

reference=Path(r'C:\Users\MOZKAN\AppData\Local\Programs\Duplay\app\console_bridge.py')
source=reference.read_bytes()
tree=ast.parse(source.decode('utf-8-sig'))
methods=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='_hud_fraction']
assert len(methods)==1
method=methods[0]
screens=[]
class Application:
    @staticmethod
    def screenAt(point):
        return next((screen for screen in screens if screen.geometry().contains(point)),None)
    @staticmethod
    def primaryScreen():
        return screens[0] if screens else None
namespace=dict(QApplication=Application,QPoint=QPoint)
exec(compile(ast.Module(body=[method],type_ignores=[]),str(reference),'exec'),namespace)

fixtures=[
    ('primary',(192,216,384,108),[(0,0,1920,1080)]),
    ('negative-origin',(-1728,316,384,108),[(-1920,100,1920,1080),(0,0,2560,1440)]),
    ('second-screen',(256,288,512,144),[(-1920,100,1920,1080),(0,0,2560,1440)]),
    ('negative-y',(456,-1152,512,144),[(0,0,1920,1080),(200,-1440,2560,1440)]),
    ('full-screen',(0,0,1920,1080),[(0,0,1920,1080)]),
    ('bottom-right',(1820,1030,100,50),[(0,0,1920,1080)]),
    ('outside-rejected',(90000,90000,200,50),[(0,0,1920,1080)]),
    ('cross-monitor-rejected',(-20,100,100,50),[(-1920,0,1920,1080),(0,0,1920,1080)]),
    ('ambiguous-rejected',(100,100,200,50),[(0,0,1920,1080),(0,0,1920,1080)]),
]
results=[]
for name,region,monitors in fixtures:
    screens[:]=[Screen(rect) for rect in monitors]
    owner=type('FixtureOwner',(),{})()
    owner._hud_logical=region
    old=namespace['_hud_fraction'](owner)
    try:
        new=normalized_region(region,screens).as_dict()
    except ValueError as exc:
        new=dict(rejected=str(exc))
    results.append(dict(name=name,region=region,monitors=monitors,reference=old,new=new,equal=old==new))
assert all(item['equal'] for item in results[:6])
assert all('rejected' in item['new'] for item in results[6:])
assert hashlib.sha256(reference.read_bytes()).hexdigest()==hashlib.sha256(source).hexdigest()
report=dict(results=results,valid_matches=6,valid_cases=6,rejected_invalid_cases=3,
            source_path=str(reference),source_sha256=hashlib.sha256(source).hexdigest(),
            new_sha256=hashlib.sha256((ROOT/'src/coordinates.py').read_bytes()).hexdigest(),limits=[
    'Only shipped _hud_fraction AST executed with generated QRect/QPoint screen fixtures; no original app imports or execution.',
    'Six valid monitor-relative outputs equal. New code rejects outside/spanning/ambiguous ownership instead of primary-screen fallback/clamping.',
    'Not actual multi-monitor, mixed-DPI, physical TV or browser evidence. Runtime cost not measured; token usage unmeasured.'
])
(ROOT/'analysis/hud-geometry-parity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('6/6 valid geometries match; 3 invalid ownership cases explicitly rejected')
