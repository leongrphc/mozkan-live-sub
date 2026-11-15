"""Equivalent completed 8-client loopback delivery before/after TV changes."""
import argparse
from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile
from websockets.sync.client import connect
from benchmark_ocr_parity import peak_memory
ROOT=Path(__file__).resolve().parents[1]


def worker(mode,updates):
    sys.path.insert(0,str(ROOT/'src'))
    with tempfile.TemporaryDirectory() as folder:
        if mode=='before':
            with zipfile.ZipFile(ROOT/'releases/AltyaziAtolyesi-0.2.7-update.zip') as archive:
                payload=archive.read('AltyaziAtolyesi/src/tv.py')
            source=Path(folder)/'tv.py'
            source.write_bytes(payload)
        else:
            source=ROOT/'src/tv.py'
            payload=source.read_bytes()
        digest=hashlib.sha256(payload).hexdigest()
        dependencies={name:hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest()
                      for name in ('coordinates.py','dialogue.py')} if mode=='new' else {}
        start,cpu=time.perf_counter(),time.process_time()
        spec=importlib.util.spec_from_file_location('measured_tv',source)
        module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=module
        spec.loader.exec_module(module)
        service=module.TV()
        service.publish('Başlangıç')
        service.publish_hud('Kapıyı aç')
        service.start(host='127.0.0.1',ws_port=0,http_port=0)
        def receive(client,expected):
            subtitle=json.loads(client.recv(timeout=3))
            hud=json.loads(client.recv(timeout=3))
            assert subtitle['text']==expected and subtitle['type']=='subtitle'
            assert 0<subtitle['ttl_ms']<=11000
            assert hud==dict(type='hud',text='Kapıyı aç',box=None,ttl_ms=0)
        try:
            with ExitStack() as stack:
                clients=[stack.enter_context(connect(f'ws://127.0.0.1:{service.ws.socket.getsockname()[1]}/?token={service.token}')) for _ in range(8)]
                for client in clients:
                    receive(client,'Başlangıç')
                cold=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
                          peak_working_set_bytes=peak_memory(),client_snapshots=8)
                warm_start,warm_cpu=time.perf_counter(),time.process_time()
                for index in range(updates):
                    text=f'Türkçe altyazı {index}: gardiyanlar dönmeden önce gitmeliyiz.'
                    service.publish(text)
                    for client in clients:
                        receive(client,text)
                warm=dict(elapsed_seconds=time.perf_counter()-warm_start,cpu_seconds=time.process_time()-warm_cpu,
                          peak_working_set_bytes=peak_memory(),updates=updates,client_snapshots=8*updates,
                          websocket_messages=16*updates)
                cleanup_start,cleanup_cpu=time.perf_counter(),time.process_time()
        finally:
            service.close()
        cleanup=dict(elapsed_seconds=time.perf_counter()-cleanup_start,cpu_seconds=time.process_time()-cleanup_cpu)
        total=dict(elapsed_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
                   peak_working_set_bytes=peak_memory())
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
        assert all(hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest()==value for name,value in dependencies.items())
        return dict(mode=mode,source_sha256=digest,dependencies=dependencies,cold=cold,warm=warm,cleanup=cleanup,total=total)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=['before','new'])
    parser.add_argument('--updates',type=int,default=100)
    parser.add_argument('--output',type=Path,default=ROOT/'analysis/tv-delivery-cost.json')
    args=parser.parse_args()
    if args.worker:
        print('RESULT='+json.dumps(worker(args.worker,args.updates)))
    else:
        results=[]
        for mode in ('before','new'):
            task=subprocess.run([sys.executable,'-B','-E','-s','-X','utf8',__file__,'--worker',mode,'--updates',str(args.updates)],
                                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=90)
            if task.returncode:
                raise RuntimeError(task.stderr[-2000:])
            results.append(json.loads(next(line[7:] for line in task.stdout.splitlines() if line.startswith('RESULT='))))
        args.output.write_text(json.dumps(dict(results=results,limits=[
            'Same short caption/HUD payloads supported by both versions; all8 clients receive every published update and HUD snapshot.',
            'Before source is immutable0.2.7 update; new production source. No original Duplay or physical TV execution.',
            'Cold producer import/server start/8 handshakes/initial snapshots; warm100 publications and800 full snapshots.',
            'Cleanup closes every client and owned listener/handler; total task includes cleanup.',
            'Fresh worker/provider; timed workers create threads but no children. CPU includes threads, peak is lifetime working set.',
            'Qt GUI/network enumeration, browser costs and larger new-capacity messages excluded; those outputs are not equivalent to the old truncated output.',
            'Token usage unmeasured, OS cache uncontrolled, one run/provider; orchestrator/preparation excluded.'
        ]),indent=2),encoding='utf-8')
        print(json.dumps(results))
