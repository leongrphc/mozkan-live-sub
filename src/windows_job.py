"""Owned Windows job handle; completion is queried, never inferred from PIDs."""
import ctypes
from ctypes import wintypes as W
import uuid


class BasicLimits(ctypes.Structure):
    _fields_=[('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),('Flags',W.DWORD),
              ('MinWorkingSet',ctypes.c_size_t),('MaxWorkingSet',ctypes.c_size_t),
              ('ActiveLimit',W.DWORD),('Affinity',ctypes.c_size_t),('Priority',W.DWORD),('Scheduling',W.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_=[(name,ctypes.c_uint64) for name in ('ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes')]


class ExtendedLimits(ctypes.Structure):
    _fields_=[('Basic',BasicLimits),('Io',IoCounters),('ProcessMemory',ctypes.c_size_t),
              ('JobMemory',ctypes.c_size_t),('PeakProcess',ctypes.c_size_t),('PeakJob',ctypes.c_size_t)]


class Accounting(ctypes.Structure):
    _fields_=[('User',ctypes.c_int64),('Kernel',ctypes.c_int64),('PeriodUser',ctypes.c_int64),
              ('PeriodKernel',ctypes.c_int64),('Faults',W.DWORD),('Total',W.DWORD),
              ('Active',W.DWORD),('Terminated',W.DWORD)]


def api():
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    signatures={
        'CreateJobObjectW':([ctypes.c_void_p,W.LPCWSTR],W.HANDLE),
        'OpenJobObjectW':([W.DWORD,W.BOOL,W.LPCWSTR],W.HANDLE),
        'SetInformationJobObject':([W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD],W.BOOL),
        'QueryInformationJobObject':([W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD,ctypes.c_void_p],W.BOOL),
        'TerminateJobObject':([W.HANDLE,W.UINT],W.BOOL),
        'AssignProcessToJobObject':([W.HANDLE,W.HANDLE],W.BOOL),
        'GetCurrentProcess':([],W.HANDLE),'CloseHandle':([W.HANDLE],W.BOOL)}
    for name,(args,result) in signatures.items():
        fn=getattr(k,name);fn.argtypes=args;fn.restype=result
    return k


def checked(value):
    if not value:raise ctypes.WinError(ctypes.get_last_error())
    return value


class WindowsJob:
    def __init__(self):
        self.name='Local\\AltyaziAtolyesi-Samsung-'+uuid.uuid4().hex
        self._api=api()
        self.handle=checked(self._api.CreateJobObjectW(None,self.name))
        if ctypes.get_last_error()==183:
            checked(self._api.CloseHandle(self.handle));self.handle=None
            raise OSError('Yeni işlem grubu kimliği zaten kullanılıyor.')

    def configure(self):
        limits=ExtendedLimits();limits.Basic.Flags=0x2000  # KILL_ON_JOB_CLOSE; no breakaway.
        checked(self._api.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)))

    def metrics(self):
        result=Accounting();limits=ExtendedLimits()
        checked(self._api.QueryInformationJobObject(self.handle,1,ctypes.byref(result),ctypes.sizeof(result),None))
        checked(self._api.QueryInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits),None))
        return dict(cpu_seconds=(result.User+result.Kernel)/10_000_000,
                    total_processes=int(result.Total),peak_job_commit_bytes=int(limits.PeakJob))

    def active(self):
        if self.handle is None:raise RuntimeError('İşlem grubu artık açık değil.')
        result=Accounting()
        checked(self._api.QueryInformationJobObject(self.handle,1,ctypes.byref(result),ctypes.sizeof(result),None))
        return int(result.Active)

    def terminate(self):
        if self.handle is not None:checked(self._api.TerminateJobObject(self.handle,1))

    def close(self):
        if self.handle is None:return
        if self.active():raise OSError('İşlem grubu henüz boşalmadı.')
        checked(self._api.CloseHandle(self.handle))
        self.handle=None


def join_current_job(name):
    k=api()
    handle=checked(k.OpenJobObjectW(1,False,name))
    try:
        checked(k.AssignProcessToJobObject(handle,k.GetCurrentProcess()))
    finally:
        checked(k.CloseHandle(handle))
