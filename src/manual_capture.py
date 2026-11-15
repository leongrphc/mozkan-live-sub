"""Detached, explicitly requested OCR image and bounded atomic local exports."""
from dataclasses import dataclass
import json
from pathlib import Path
import time
from PySide6.QtCore import QSaveFile,QIODevice
from PySide6.QtGui import QImage

MAX_CAPTURE_PIXELS=50_000_000  # <=1GiB at a conservative20bytes/pixel transient budget.
MAX_EXPORT_BYTES=2*1024*1024
MAX_PNG_BYTES=256*1024*1024


@dataclass(frozen=True)
class CapturedImage:
    image:QImage
    logical:tuple
    physical:tuple
    captured_at:float


def capture_image(logical,physical):
    import mss
    x,y,w,h=physical
    if w<=0 or h<=0 or w*h>MAX_CAPTURE_PIXELS:
        raise ValueError('OCR görüntüsü yakalama kapasitesini aşıyor.')
    try:
        with mss.mss() as source:
            shot=source.grab(dict(left=x,top=y,width=w,height=h))
            image=QImage(shot.rgb,shot.width,shot.height,shot.width*3,QImage.Format_RGB888).copy()
    except MemoryError as error:raise OSError('OCR görüntüsü için yeterli bellek yok.') from error
    if image.isNull():raise OSError('OCR görüntüsü oluşturulamadı.')
    return CapturedImage(image,tuple(logical),tuple(physical),time.monotonic())


def write_export(path,writer):
    destination=QSaveFile(str(Path(path)))
    if not destination.open(QIODevice.WriteOnly):raise OSError(destination.errorString())
    try:
        writer(destination)
        if not destination.commit():raise OSError(destination.errorString())
    except BaseException:
        destination.cancelWriting()
        raise


def save_json(path,value):
    def write(destination):
        total=0
        for part in json.JSONEncoder(ensure_ascii=False,allow_nan=False,indent=2).iterencode(value):
            payload=part.encode('utf-8');total+=len(payload)
            if total>MAX_EXPORT_BYTES:raise ValueError('Tanılama kaydı2MiB kapasitesini aşıyor.')
            if destination.write(payload)!=len(payload):raise OSError(destination.errorString())
    write_export(path,write)


def save_image(path,captured):
    def write(destination):
        if not captured.image.save(destination,'PNG'):raise OSError('OCR görüntüsü PNG olarak yazılamadı.')
        if destination.pos()>MAX_PNG_BYTES:raise ValueError('PNG dosyası256MiB kapasitesini aşıyor.')
    write_export(path,write)
