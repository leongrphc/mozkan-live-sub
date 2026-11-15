"""Known local executable workload; never contacts a TV or vendor service."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

if '--child' in sys.argv:
    time.sleep(30)
    raise SystemExit(0)

parser=argparse.ArgumentParser()
parser.add_argument('action')
parser.add_argument('--data',type=Path,required=True)
parser.add_argument('--host');parser.add_argument('--preset-port');parser.add_argument('--preset-token')
parser.add_argument('--renew',action='store_true')
args=parser.parse_args()
mode=(args.data/'fixture-mode').read_text() if (args.data/'fixture-mode').exists() else 'normal'
def emit(**values):print(json.dumps(values,ensure_ascii=False),flush=True)
if mode in ('orphan','hang'):
    child=subprocess.Popen([sys.executable,'-B','-E','-s',__file__,'--child'],
                           stdin=subprocess.DEVNULL)
    (args.data/'child-pid').write_text(str(child.pid))
if mode=='hang':
    emit(event='step',step='connect',text='Bekliyor',percent=10)
    time.sleep(30)
if mode=='orphan':
    deadline=time.monotonic()+5
    while not (args.data/'allow-exit').exists() and time.monotonic()<deadline:time.sleep(.005)
if mode=='error':
    emit(event='error',code='known',text='Bilinen hata',hint='Geliştirici modunu açın.')
    raise SystemExit(2)
if mode=='malformed':
    print('{"event":"step","text":{}}',flush=True);time.sleep(30)
if mode=='capacity':
    print('x'*100000,flush=True);time.sleep(30)
if mode=='flood':
    while True:emit(event='step',step='wait',text='known progress line')
if mode=='exit0':raise SystemExit(0)
fragment=(json.dumps(dict(event='tv',ip='192.168.1.80',name='İlk TV',model='M80',devMode=True),ensure_ascii=False)+'\n').encode('utf-8')
split=fragment.index('İ'.encode('utf-8'))+1
sys.stdout.buffer.write(fragment[:split]);sys.stdout.buffer.flush();time.sleep(.03)
sys.stdout.buffer.write(fragment[split:]);sys.stdout.buffer.flush()
emit(event='tv',ip='192.168.1.20',name='İkinci TV',model='M20')
emit(event='tv',ip='192.168.1.80',name='Güncel TV',model='M80',devMode=False)
if args.action=='install':
    emit(event='step',step='login',text='Samsung oturumu',url='https://account.samsung.com/known-local-fixture',percent=20)
emit(event='step',step='install',text='Kuruluyor',percent=60)
emit(event='device',tizen='7.0')
print('known stderr '+(args.preset_token or '')+' renew='+str(args.renew),file=sys.stderr,flush=True)
# A final JSON line need not end in LF.
sys.stdout.write(json.dumps(dict(event='done',text='Bilinen tamamlanma'),ensure_ascii=False));sys.stdout.flush()
