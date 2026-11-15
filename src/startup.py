"""Resource readiness and the GUI-to-capture handoff are separate facts."""
from dataclasses import dataclass,field
import threading
import time


@dataclass(frozen=True,slots=True)
class CaptureFailure:
    error_class:str
    message:str


class ChildStop:
    """A failed optional child can stop itself without stopping its parent."""
    def __init__(self,parent):
        self.parent=parent
        self.local=threading.Event()

    def is_set(self):return self.local.is_set() or self.parent.is_set()
    def set(self):self.local.set()
    def wait(self,timeout):
        end=time.monotonic()+timeout
        while not self.is_set():
            remaining=end-time.monotonic()
            if remaining<=0:return False
            self.local.wait(min(.05,remaining))
        return True


@dataclass(frozen=True,slots=True)
class CaptureProgress:
    component:str
    status:str

    def __post_init__(self):
        if self.component not in ('profile','ocr','translation','capture') or self.status not in ('loading','ready'):
            raise ValueError('Geçersiz hazırlık bildirimi.')


@dataclass
class Startup:
    session:int
    gate:threading.Event=field(default_factory=threading.Event)
    components:dict=field(default_factory=dict)
    loading:str|None=None

    def observe(self,progress):
        if not isinstance(progress,CaptureProgress):raise ValueError('Geçersiz hazırlık bildirimi.')
        self.components[progress.component]=progress.status
        if progress.status=='loading':self.loading=progress.component
        elif self.loading==progress.component:self.loading=None

    @property
    def ready(self):return self.components.get('capture')=='ready'

    @property
    def message(self):
        return {'profile':'Oyun profili yükleniyor…','ocr':'OCR hazırlanıyor…',
                'translation':'Çeviri modeli hazırlanıyor…'}.get(self.loading,'Çeviri hazırlanıyor…')
