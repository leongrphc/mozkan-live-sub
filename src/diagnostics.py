"""Bounded latest OCR observations; no screenshots, serialization or disk writes."""
from dataclasses import dataclass,asdict
import threading
from recognition import Reading
from translation_info import TranslationInfo


@dataclass(frozen=True,slots=True)
class OcrObservation:
    reading: Reading
    fresh: bool
    sample: int
    observed_at: float
    last_read_at: float


@dataclass(frozen=True,slots=True)
class TranslationObservation:
    info: TranslationInfo
    observed_at: float


@dataclass(frozen=True,slots=True)
class DiagnosticUpdate:
    session: int
    role: str
    revision: int
    observation: OcrObservation | TranslationObservation


class DiagnosticMailbox:
    def __init__(self):
        self._lock=threading.Lock()
        self._latest={}
        self._accepted={}

    @staticmethod
    def key(update):
        if (not isinstance(update,DiagnosticUpdate) or update.role not in ('subtitle','hud')
                or type(update.observation) not in (OcrObservation,TranslationObservation)):
            raise ValueError('OCR gözlem kanalı geçersiz.')
        return update.role,type(update.observation)

    @staticmethod
    def order(item):return item.session,item.revision,item.observation.observed_at

    def post(self,update):
        key=self.key(update)
        with self._lock:
            previous=self._latest.get(key) or self._accepted.get(key)
            if previous is None or self.order(update)>=self.order(previous):
                self._latest[key]=update

    def drain(self):
        with self._lock:
            values=tuple(self._latest.values())
            self._latest.clear()
            return values

    def clear(self):
        with self._lock:
            self._latest.clear()
            self._accepted.clear()

    def accept(self,update):
        key=self.key(update)
        with self._lock:
            previous=self._accepted.get(key)
            if previous is None or self.order(update)>=self.order(previous):self._accepted[key]=update

    def snapshot(self):
        with self._lock:return tuple(self._accepted.values())


def diagnostic_record(update,now,*,include_text=False):
    observation=update.observation
    age=now-observation.observed_at
    value=dict(role=update.role,session=update.session,revision=update.revision,
               observed_monotonic=observation.observed_at,age_seconds=age if age>=0 else None)
    if isinstance(observation,TranslationObservation):
        value.update(kind='translation',info=asdict(observation.info))
    else:
        reading=observation.reading
        value.update(kind='ocr',fresh=observation.fresh,sample=observation.sample,
                     last_read_monotonic=observation.last_read_at,
                     confidence=reading.confidence,method=reading.method,variant=reading.variant,
                     elapsed_ms=reading.elapsed_ms,
                     scans=[asdict(scan) for scan in reading.scans] if reading.scans is not None else None,
                     word_count=len(reading.words),badge_count=len(reading.badges))
        if include_text:value['text']=reading.text
    return value
