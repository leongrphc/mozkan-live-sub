"""Owned, byte-bounded metadata log. No subtitle stream or ambient environment."""
from datetime import datetime,timezone
import json
from pathlib import Path
import threading
import uuid

FIELDS={
    'app_start':{'version','python'},'capture_start':{'session','mode','profile'},
    'stop_requested':{'session'},'capture_end':{'session'},'resource':{'session','component','status'},
    'capture_error':{'session','role','error_class'},'close_requested':set(),
}


class AppLog:
    MAX_BYTES=1024*1024

    def __init__(self,directory,version,python_version):
        self.owner=threading.get_ident()
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/(datetime.now(timezone.utc).strftime('app-%Y%m%dT%H%M%S-')+uuid.uuid4().hex+'.jsonl')
        self.stream=self.path.open('xb',buffering=0)
        self.written=0
        self.error=''
        self.truncated=False
        self.record('app_start',version=version,python=python_version)

    def check_owner(self):
        if threading.get_ident()!=self.owner:raise RuntimeError('Günlüğü yalnız sahibi kullanabilir.')

    def record(self,event,**fields):
        self.check_owner()
        if event not in FIELDS or set(fields)!=FIELDS[event]:raise ValueError('Geçersiz günlük olayı.')
        if any(value is not None and type(value) not in (str,int,bool) for value in fields.values()):
            raise ValueError('Geçersiz günlük alanı.')
        if self.stream is None or self.error or self.truncated:return False
        data=dict(time=datetime.now(timezone.utc).isoformat(),event=event,**fields)
        payload=(json.dumps(data,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
        if self.written+len(payload)>self.MAX_BYTES:
            self.truncated=True
            payload=b'{"event":"log_capacity"}\n'
            if self.written+len(payload)>self.MAX_BYTES:return False
        try:
            count=self.stream.write(payload)
            self.written+=count
            if count!=len(payload):raise OSError('Günlük satırı tam yazılamadı.')
            return True
        except OSError as error:
            self.error=str(error)
            return False

    def close(self):
        self.check_owner()
        if self.stream is None:return True
        try:self.stream.close()
        except OSError as error:
            self.error=str(error)
            if not self.stream.closed:return False
        self.stream=None
        return True
