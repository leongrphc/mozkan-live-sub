"""User dictionary: exact-line corrections and best-effort term hints.

Local JSON only. Corrections are reliable (whole line lookup, checked before
game profiles and the model). Term hints are substituted into the English
input before the neural model runs; OPUS-MT may still inflect or rewrite
them, so they are a hint, not a guarantee.
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from dialogue import MAX_CAPTION, split_speaker

FORMAT = 'mozkan-live-sub/dictionary-v1'
MAX_BYTES = 1024 * 1024
MAX_CORRECTIONS = 5000
MAX_TERMS = 500
MAX_TERM = 64


def normalize(text):
    """Lookup key: case/whitespace-insensitive, ignores trailing sentence punctuation."""
    if not isinstance(text, str):
        raise ValueError('Sözlük metni geçersiz.')
    return re.sub(r'\s+', ' ', text).strip().rstrip('.!?…').strip().casefold()


def _clean(value, limit, name, *, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} metin olmalı.')
    value = re.sub(r'\s+', ' ', value).strip()
    if (not value and not allow_empty) or len(value) > limit:
        raise ValueError(f'{name} 1-{limit} karakter olmalı.' if not allow_empty else f'{name} en fazla {limit} karakter olmalı.')
    return value


@dataclass(frozen=True)
class Snapshot:
    """Immutable view handed to worker threads."""
    version: int = 0
    corrections: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))
    terms: tuple = ()
    _pattern: re.Pattern | None = None
    _targets: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))

    def correction(self, text):
        """Return the user's Turkish line for this English line, or None."""
        if not self.corrections or not isinstance(text, str):
            return None
        hit = self.corrections.get(normalize(text))
        if hit is not None:
            return hit
        speaker, body = split_speaker(text)
        if speaker:
            hit = self.corrections.get(normalize(body))
            if hit is not None:
                return speaker + ': ' + hit
        return None

    def apply_terms(self, text):
        if self._pattern is None:
            return text
        return self._pattern.sub(lambda match: self._targets[match.group(0).casefold()], text)


def _snapshot(version, corrections, terms):
    pattern = None
    targets = {}
    if terms:
        for source, target in terms:
            targets[source.casefold()] = target or source
        alternatives = sorted(targets, key=len, reverse=True)
        pattern = re.compile(r'(?<!\w)(' + '|'.join(re.escape(term) for term in alternatives) + r')(?!\w)',
                             re.IGNORECASE)
    return Snapshot(version, MappingProxyType(dict(corrections)), tuple(terms), pattern, MappingProxyType(targets))


class UserDictionary:
    """Owned by the UI thread; workers only call snapshot()."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.warning = ''
        self._unreadable = False
        self._corrections = {}
        self._sources = {}
        self._terms = []
        self._snapshot = Snapshot()
        if self.path.is_file():
            try:
                self._load(self.path.read_bytes())
            except (OSError, ValueError) as exc:
                self.warning = f'Sözlük okunamadı; dosya korunuyor, boş sözlük kullanılıyor: {exc}'
                self._unreadable = True
                self._corrections, self._sources, self._terms = {}, {}, []
        self._publish()

    def _load(self, data):
        if len(data) > MAX_BYTES:
            raise ValueError('Sözlük 1 MiB sınırını aşıyor.')
        try:
            value = json.loads(data.decode('utf-8-sig'))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError('JSON geçersiz.') from exc
        if not isinstance(value, dict) or value.get('format') != FORMAT:
            raise ValueError('Biçim tanınmadı.')
        corrections, terms = value.get('corrections', []), value.get('terms', [])
        if not isinstance(corrections, list) or not isinstance(terms, list):
            raise ValueError('Liste alanları geçersiz.')
        if len(corrections) > MAX_CORRECTIONS or len(terms) > MAX_TERMS:
            raise ValueError('Kayıt sayısı sınırı aşıldı.')
        for row in corrections:
            if not isinstance(row, dict):
                raise ValueError('Düzeltme kaydı geçersiz.')
            self._set_correction(row.get('source'), row.get('target'))
        for row in terms:
            if not isinstance(row, dict):
                raise ValueError('Terim kaydı geçersiz.')
            self._set_term(row.get('source'), row.get('target', ''))

    def _publish(self):
        with self.lock:
            self._snapshot = _snapshot(self._snapshot.version + 1, self._corrections, self._terms)

    def snapshot(self):
        with self.lock:
            return self._snapshot

    # --- corrections -----------------------------------------------------
    def _set_correction(self, source, target):
        source = _clean(source, MAX_CAPTION, 'İngilizce satır')
        target = _clean(target, MAX_CAPTION, 'Türkçe karşılık')
        key = normalize(source)
        if not key:
            raise ValueError('İngilizce satır yalnız noktalama olamaz.')
        if key not in self._corrections and len(self._corrections) >= MAX_CORRECTIONS:
            raise ValueError(f'En fazla {MAX_CORRECTIONS} düzeltme saklanabilir.')
        self._corrections[key] = target
        self._sources[key] = source

    def corrections(self):
        return [(self._sources[key], target) for key, target in self._corrections.items()]

    def _mutate(self, change):
        """Apply and persist one change; restore the previous state if either step fails."""
        saved = dict(self._corrections), dict(self._sources), list(self._terms)
        try:
            change()
            self._save()
        except BaseException:
            self._corrections, self._sources, self._terms = saved
            raise

    def set_correction(self, source, target):
        self._mutate(lambda: self._set_correction(source, target))

    def remove_correction(self, source):
        key = normalize(source)
        def change():
            self._corrections.pop(key, None)
            self._sources.pop(key, None)
        self._mutate(change)

    # --- terms -----------------------------------------------------------
    def _set_term(self, source, target):
        source = _clean(source, MAX_TERM, 'Terim')
        target = _clean(target, MAX_TERM, 'Terim karşılığı', allow_empty=True)
        if not re.search(r'\w', source):
            raise ValueError('Terim en az bir harf veya rakam içermeli.')
        self._terms = [row for row in self._terms if row[0].casefold() != source.casefold()]
        if len(self._terms) >= MAX_TERMS:
            raise ValueError(f'En fazla {MAX_TERMS} terim saklanabilir.')
        self._terms.append((source, target))

    def terms(self):
        return list(self._terms)

    def set_term(self, source, target=''):
        self._mutate(lambda: self._set_term(source, target))

    def remove_term(self, source):
        def change():
            self._terms = [row for row in self._terms if row[0].casefold() != str(source).casefold()]
        self._mutate(change)

    # --- persistence -----------------------------------------------------
    def _save(self):
        data = json.dumps(dict(format=FORMAT,
                               corrections=[dict(source=s, target=t) for s, t in self.corrections()],
                               terms=[dict(source=s, target=t) for s, t in self._terms]),
                          ensure_ascii=False, indent=1).encode('utf-8')
        if len(data) > MAX_BYTES:
            raise ValueError('Sözlük 1 MiB sınırını aşacaktı; kaydedilmedi.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self._unreadable and self.path.exists():
            # Never overwrite a file we could not read; keep it beside the new one.
            for index in range(1, 1000):
                keep = self.path.with_name(f'{self.path.stem}.okunamayan-{index}{self.path.suffix}')
                if not keep.exists():
                    os.replace(self.path, keep)
                    break
            else:
                raise OSError('Okunamayan sözlük dosyası yedeklenemedi; kaydedilmedi.')
        self._unreadable = False
        temporary = self.path.with_name(self.path.name + '.tmp')
        with temporary.open('wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)
        self.warning = ''
        self._publish()
