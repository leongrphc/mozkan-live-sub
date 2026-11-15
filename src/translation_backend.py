"""Own device choice and GPU failure recovery for the local CTranslate2 model."""
import os
import sys
import threading
from pathlib import Path


class InferenceCancelled(Exception):
    pass


_runtime_lock=threading.Lock()
_runtime_directories={}


def enable_cuda_runtime():
    """Add bundled DLL search directories once for this application process only.

    CT2's native LoadLibrary requires PATH as well as Python's DLL directories.
    Handles remain owned here for process lifetime; nothing is installed or
    written to the user's environment/configuration.
    """
    if os.name!='nt':
        return
    with _runtime_lock:
        root=Path(sys.prefix)/'Lib/site-packages/nvidia'
        for name in ('cublas','cuda_runtime','cuda_nvrtc'):
            folder=root/name/'bin'
            identity=os.path.normcase(str(folder))
            if not folder.is_dir():
                continue
            if identity not in _runtime_directories:
                handle=os.add_dll_directory(str(folder))
                _runtime_directories[identity]=handle
            entries=os.environ.get('PATH','').split(os.pathsep)
            if identity not in {os.path.normcase(entry) for entry in entries}:
                os.environ['PATH']=str(folder)+os.pathsep+os.environ.get('PATH','')


class TranslationBackend:
    def __init__(self,model_path,*,cpu_only,guard,runtime=None,runtime_loader=enable_cuda_runtime):
        if runtime is None:
            import ctranslate2 as runtime
        self.runtime=runtime
        self.model_path=str(model_path)
        self.cpu_only=cpu_only
        self.device='cpu'
        self.cuda_failure=None
        self.fallback_count=0
        self.translator=None
        guard()
        if not cpu_only:
            try:
                if runtime.get_cuda_device_count()>0:
                    runtime_loader()
                    guard()
                    self.translator=runtime.Translator(self.model_path,device='cuda',compute_type='float16')
                    self.device='cuda'
            except (RuntimeError,OSError) as exc:
                self.cuda_failure=f'{type(exc).__name__}: {exc}'
                self.fallback_count+=1
        if self.translator is None:
            self._cpu(guard)

    def _cpu(self,guard):
        guard()
        replacement=self.runtime.Translator(self.model_path,device='cpu',compute_type='int8',
            inter_threads=1,intra_threads=1 if self.cpu_only else 2)
        self.translator=replacement
        self.device='cpu'

    def translate_batch(self,sources,*,guard=lambda:None,**options):
        guard()
        try:
            return self.translator.translate_batch(sources,**options)
        except (RuntimeError,OSError) as exc:
            if self.device!='cuda':
                raise
            self.cuda_failure=f'{type(exc).__name__}: {exc}'
            # A canceled GPU failure must not acquire a CPU model or retry.
            self._cpu(guard)
            self.fallback_count+=1
            guard()
            return self.translator.translate_batch(sources,**options)
