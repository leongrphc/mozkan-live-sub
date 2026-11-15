"""Typed Samsung helper state and owned process-family finalization."""
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
import sys
import uuid
from PySide6.QtCore import QObject,QProcess,QTimer,Signal
from samsung_protocol import SamsungState,parse_notice,ipv4,MAX_LINE
from windows_job import WindowsJob


class SamsungHelper(QObject):
    changed=Signal(object)
    status=Signal(str)
    MAX_LOG=1024*1024
    MAX_OUTPUT=8*1024*1024

    def __init__(self,directory,data,parent=None):
        super().__init__(parent)
        self.directory,self.data=Path(directory),Path(data)
        self.state=SamsungState()
        self.process=QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.started.connect(self.started)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.process_error)
        self.job=None
        self._log=None
        self.log_path=None
        self._log_bytes=0
        self._log_full=False
        self._output_bytes=0
        self._token=''
        self._buffers={QProcess.StandardOutput:bytearray(),QProcess.StandardError:bytearray()}
        self._root_done=True
        self._stopping=False
        self.last_metrics=None
        self._timer=QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.finalize)

    @property
    def busy(self):
        return self.job is not None or not self._root_done or self._log is not None

    def notify(self):
        self.changed.emit(self.state)
        self.status.emit(self.state.error or self.state.text or 'Samsung işlemi sürüyor…')

    def start(self,action,host='',token='',*,renew=False):
        if self.busy:raise ValueError('Önce devam eden Samsung işlemini bitirin.')
        if action not in ('scan','install'):raise ValueError('Bilinmeyen Samsung işlemi.')
        if type(renew) is not bool:raise ValueError('Oturum yenileme tercihi geçersiz.')
        executable=self.directory/'DuplaySamsung.exe'
        if not executable.is_file() or not (self.directory/'Duplay.wgt').is_file():
            raise FileNotFoundError('Samsung yardımcı dosyaları bulunamadı.')
        args=[action]
        if action=='install':
            host=ipv4(host)
            args+=['--host',host,'--preset-port','8765']
            if token:args+=['--preset-token',token]
            if renew:args.append('--renew')
        self.data.mkdir(parents=True,exist_ok=True)
        log_dir=self.data/'logs';log_dir.mkdir(exist_ok=True)
        log_path=log_dir/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S-')+uuid.uuid4().hex+'.log')
        self._log=log_path.open('xb')
        self.log_path=log_path
        try:
            self.job=WindowsJob()
            self.job.configure()
        except OSError as error:
            self.state=replace(self.state,error=str(error),code='start')
            self._timer.start()
            self.finalize()
            raise
        job=self.job
        self._log_bytes=0;self._log_full=False;self._token=token
        self._output_bytes=0
        for buffer in self._buffers.values():buffer.clear()
        self._root_done=False;self._stopping=False;self.last_metrics=None
        self.state=SamsungState(action=action,text='Başlatılıyor…',host=host if action=='install' else self.state.host,
                                tvs=() if action=='scan' else self.state.tvs)
        self.process.setWorkingDirectory(str(self.directory.resolve()))
        self.process.setStandardInputFile(QProcess.nullDevice())
        self.notify()
        self._timer.start()
        runner=Path(__file__).with_name('samsung_runner.py').resolve()
        self.process.start(sys.executable,['-B','-E','-s','-X','utf8',str(runner),job.name,'--',str(executable.resolve()),*args,'--data',str(self.data.resolve())])
        return self.state.host

    def started(self):
        if self._stopping:self.stop_family()

    def process_error(self,error):
        if error==QProcess.FailedToStart:
            self._root_done=True
            self.fail(self.process.errorString(),'start')
            self.finalize()
        elif error!=QProcess.Crashed and not self._stopping:
            self.fail(self.process.errorString(),'process')

    def fail(self,text,code):
        if not self.state.error:
            self.state=replace(self.state,error=text,code=code,url='',percent=None)
            self.notify()
        self._stopping=True
        self.stop_family()

    def write_log(self,raw,channel):
        if self._log is None or self._log_full:return
        text=raw.decode('utf-8','replace')
        if self._token:text=text.replace(self._token,'[TV eşleştirme kodu]')
        payload=(channel+': '+text+'\n').encode('utf-8')
        if self._log_bytes+len(payload)>self.MAX_LOG:
            payload=b'\n[Log capacity reached; further output omitted.]\n'[:max(0,self.MAX_LOG-self._log_bytes)]
            self._log_full=True
            self.state=replace(self.state,log_truncated=True)
        try:
            self._log.write(payload);self._log.flush();self._log_bytes+=len(payload)
        except OSError as error:
            self.fail(f'Samsung günlüğü yazılamadı: {error}','log')

    def consume(self,channel,chunk,*,final=False):
        buffer=self._buffers[channel]
        self._output_bytes+=len(chunk)
        if self._output_bytes>self.MAX_OUTPUT:
            self.fail('Samsung toplam çıktısı8MiB kapasitesini aştı.','capacity')
            buffer.clear();return
        buffer.extend(chunk)
        while b'\n' in buffer or (final and buffer):
            end=buffer.find(b'\n')
            if end<0:end=len(buffer)
            raw=bytes(buffer[:end]).rstrip(b'\r')
            del buffer[:min(end+1,len(buffer))]
            if len(raw)>MAX_LINE:
                self.fail('Samsung çıktı satırı kapasiteyi aştı.','capacity');buffer.clear();return
            if not raw:continue
            self.write_log(raw,'stderr' if channel==QProcess.StandardError else 'stdout')
            if channel==QProcess.StandardOutput and not self._stopping and raw.lstrip().startswith(b'{'):
                try:
                    event=parse_notice(raw)
                    if event is not None:
                        self.state=self.state.notice(event)
                        self.notify()
                except ValueError as error:self.fail(str(error),'protocol')
        if len(buffer)>MAX_LINE:
            self.fail('Samsung çıktı satırı kapasiteyi aştı.','capacity');buffer.clear()

    def read_channel(self,channel):
        previous=self.process.readChannel()
        self.process.setReadChannel(channel)
        try:
            while self.process.bytesAvailable():
                self.consume(channel,bytes(self.process.read(65536)))
        finally:self.process.setReadChannel(previous)

    def read(self):self.read_channel(QProcess.StandardOutput)
    def read_error(self):self.read_channel(QProcess.StandardError)

    def finished(self,code,status):
        self.read();self.read_error()
        for channel in self._buffers:self.consume(channel,b'',final=True)
        self._root_done=True
        self.state=replace(self.state,url='',percent=None)
        if not self.state.cancelled and not self.state.error:
            if code!=0 or status!=QProcess.NormalExit:
                self.state=replace(self.state,error=f'Samsung aracı beklenmedik şekilde kapandı (kod {code}).',code='crash')
            elif not (self.state.done or self.state.scanned):
                self.state=replace(self.state,error='Samsung aracı tamamlanma sonucu vermeden kapandı.',code='incomplete')
        self.notify()
        self.finalize()

    def stop_family(self):
        errors=[]
        if self.process.state()!=QProcess.NotRunning:self.process.kill()
        if self.job is not None:
            try:self.job.terminate()
            except OSError as error:errors.append(str(error))
        if errors:self.cleanup_error('; '.join(errors))

    def cleanup_error(self,message):
        if message!=self.state.cleanup_error:
            self.state=replace(self.state,cleanup_error=message)
            self.notify()

    def finalize(self):
        if self._stopping and not self._root_done:self.stop_family()
        if not self._root_done:return
        if self.job is not None:
            try:
                if self.job.active():
                    self.job.terminate()
                    return
                self.last_metrics=self.job.metrics()
                self.job.close()
                self.job=None
            except OSError as error:
                self.cleanup_error(str(error));return
        if self._log is not None:
            handle=self._log
            try:handle.close()
            except OSError as error:
                if handle.closed:self._log=None
                self.cleanup_error(str(error));return
            self._log=None
        self._timer.stop()
        self.state=replace(self.state,cleanup_error='',text='İptal edildi.' if self.state.cancelled else self.state.text)
        self.notify()

    def cancel(self):
        if not self.busy:return
        self._stopping=True
        self.state=replace(self.state,cancelled=True,text='İptal ediliyor…',error='',code='',hint='',url='',percent=None)
        self.notify()
        self.stop_family()
        self.finalize()
