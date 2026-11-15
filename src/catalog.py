"""Portable profile identities and owned, validated imports.

Inventory is deliberately cheaper than profile validation. A builtin inventory
title is filename-derived; an imported title is bound to bytes validated at import.
resolve() checks current imported bytes before returning a usable path.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sqlite3
import tempfile
import threading

from profiles import GameProfile

MAX_PROFILE_BYTES = GameProfile.MAX_BYTES
MAX_METADATA_BYTES = 64 * 1024
_DIGEST = re.compile(r'[0-9a-f]{64}')
_METADATA_LOCK = threading.RLock()


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class CatalogEntry:
    identity: str
    title: str
    path: Path
    kind: str
    available: bool
    title_source: str
    error: str | None = None
    count: int | None = None


def _wal_exists(path):
    wal = Path(str(path) + '-wal')
    return wal.exists() and wal.stat().st_size > 0


def _stamp(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_PROFILE_BYTES:
            raise CatalogError('Profil normal bir dosya olmalı ve 256 MiB sınırını aşmamalı.')
        size = 0
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_PROFILE_BYTES:
                raise CatalogError('Profil okuma sırasında 256 MiB sınırını aştı.')
            digest.update(chunk)
        if _stamp(before) != _stamp(os.fstat(source.fileno())):
            raise CatalogError('Profil okunurken değişti; kapalı veya dışa aktarılmış bir kopya seçin.')
    return digest.hexdigest()


class Catalog:
    def __init__(self, bundled_dir, imported_dir):
        self.bundled_dir = Path(bundled_dir).resolve()
        self.imported_dir = Path(imported_dir).resolve()

    def _metadata(self, digest):
        path = self.imported_dir / (digest + '.json')
        if not path.exists():
            return None
        try:
            with path.open('rb') as source:
                data = source.read(MAX_METADATA_BYTES + 1)
            if len(data) > MAX_METADATA_BYTES:
                raise CatalogError('İçe aktarma metadata dosyası 64 KiB sınırını aşıyor.')
            value = json.loads(data.decode('utf-8'))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise CatalogError('İçe aktarma metadata dosyası okunamadı: ' + str(path)) from exc
        if (not isinstance(value, dict) or value.get('sha256') != digest
                or not isinstance(value.get('title'), str)
                or not isinstance(value.get('origins'), list)
                or any(not isinstance(origin, dict) for origin in value['origins'])):
            raise CatalogError('İçe aktarma metadata kimliği veya biçimi geçersiz: ' + str(path))
        return value

    @property
    def entries(self):
        result = []
        for path in sorted(self.bundled_dir.glob('*.sqlite')):
            available = path.is_file() and path.resolve().parent == self.bundled_dir
            result.append(CatalogEntry('bundled:' + path.name, path.stem, path, 'bundled',
                                       available, 'filename', None if available else 'Paket profili erişilemiyor.'))
        for path in sorted(self.imported_dir.glob('*.sqlite')):
            digest = path.stem
            if not _DIGEST.fullmatch(digest):
                continue  # Unowned/legacy filenames are never silently assigned an identity.
            error, metadata = None, None
            try:
                metadata = self._metadata(digest)
            except (CatalogError, OSError) as exc:
                error = str(exc)
            title = metadata['title'] if metadata else 'İçe aktarılan profil ' + digest[:12]
            count = metadata.get('count') if metadata else None
            result.append(CatalogEntry('imported:' + digest, title, path, 'imported',
                                       path.is_file() and path.resolve().parent == self.imported_dir,
                                       'stored-import-metadata' if metadata else 'filename', error,
                                       count if type(count) is int else None))
        return tuple(result)

    def resolve(self, identity):
        if not isinstance(identity, str):
            raise CatalogError('Profil kimliği metin olmalı.')
        if identity.startswith('bundled:'):
            name = identity[len('bundled:'):]
            if not name or '/' in name or '\\' in name or ':' in name or Path(name).suffix.lower() != '.sqlite':
                raise CatalogError('Paket profil kimliği geçersiz.')
            path = self.bundled_dir / name
            if path.resolve().parent != self.bundled_dir:
                raise CatalogError('Profil paket klasörünün dışına çıkıyor.')
        elif identity.startswith('imported:'):
            digest = identity[len('imported:'):]
            if not _DIGEST.fullmatch(digest):
                raise CatalogError('İçe aktarılan profil kimliği geçersiz.')
            path = self.imported_dir / (digest + '.sqlite')
            if path.resolve().parent != self.imported_dir:
                raise CatalogError('Profil içe aktarma klasörünün dışına çıkıyor.')
            if not path.is_file():
                raise FileNotFoundError('Seçili içe aktarılmış profil bulunamadı: ' + identity)
            if _wal_exists(path):
                raise CatalogError('İçe aktarılmış profilin WAL verisi var; dosya kimliği doğrulanamıyor.')
            if _hash_file(path) != digest:
                raise CatalogError('İçe aktarılmış profil değiştirilmiş veya bozulmuş: ' + identity)
        elif identity.startswith('external:'):
            path = Path(identity[len('external:'):])
            if not path.is_absolute():
                raise CatalogError('Harici profil yolu mutlak olmalı.')
        else:
            raise CatalogError('Bilinmeyen profil kimliği; önceki harici yolu açıkça seçin veya profili içe aktarın.')
        if not path.is_file():
            raise FileNotFoundError('Seçili profil bulunamadı; başka profile otomatik geçilmedi: ' + str(path))
        return path

    def legacy_external(self, path):
        """Expose a previous caller-selected path without relabeling its origin."""
        path = Path(path)
        if not path.is_absolute():
            raise CatalogError('Önceki harici profil yolu mutlak olmalı.')
        return CatalogEntry('external:' + str(path), path.name + ' (harici)', path,
                            'external', path.is_file(), 'filename',
                            None if path.is_file() else 'Önceki harici profil artık bulunamıyor.')

    def import_profile(self, source):
        selected = os.fspath(source)
        source = Path(source).resolve()
        if _wal_exists(source):
            raise CatalogError('Profilin etkin WAL verisi var. Kaynak uygulamayı kapatın veya dışa aktarılmış kapalı bir profil seçin.')
        self.imported_dir.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix='.import-', suffix='.sqlite', dir=self.imported_dir)
        temporary = Path(temporary_name)
        try:
            digest, size = hashlib.sha256(), 0
            with os.fdopen(fd, 'wb') as output, source.open('rb') as input_file:
                before = os.fstat(input_file.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_PROFILE_BYTES:
                    raise CatalogError('Profil normal bir dosya olmalı ve 256 MiB sınırını aşmamalı.')
                while chunk := input_file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_PROFILE_BYTES:
                        raise CatalogError('Profil kopyalanırken 256 MiB sınırını aştı.')
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
                if _stamp(before) != _stamp(os.fstat(input_file.fileno())) or _wal_exists(source):
                    raise CatalogError('Kaynak profil kopyalanırken değişti; kapalı veya dışa aktarılmış bir kopya seçin.')
            copied_digest = digest.hexdigest()
            try:
                profile = GameProfile(temporary)
            except (ValueError, sqlite3.DatabaseError) as exc:
                raise CatalogError('Profil kopyası doğrulanamadı: ' + str(exc)) from exc
            if not profile.rows:
                raise CatalogError('Profil kullanılabilir İngilizce/Türkçe eşleşme içermiyor.')
            if not isinstance(profile.title, str):
                raise CatalogError('Profil başlığı metin olmalı.')
            title, count = profile.title, len(profile.rows)
            del profile
            if _hash_file(temporary) != copied_digest:
                raise CatalogError('Doğrulanan profil kopyasının kimliği değişti.')
            destination = self.imported_dir / (copied_digest + '.sqlite')
            if destination.resolve().parent != self.imported_dir:
                raise CatalogError('İçe aktarma hedefi sahip olunan klasörün dışına çıkıyor.')
            # Hard-link publication is atomic and refuses an existing filename.
            # Both files live on the same filesystem; the private name is removed below.
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if _hash_file(destination) != copied_digest:
                    raise CatalogError('Aynı kimlikteki içe aktarılmış dosya bozulmuş; üzerine yazılmadı.')
            origin = dict(selected_path=selected, resolved_path=str(source), sha256=copied_digest,
                          bytes=size, source_identity=dict(device=before.st_dev, inode=before.st_ino,
                          modified_ns=before.st_mtime_ns, changed_ns=before.st_ctime_ns))
            self._save_metadata(copied_digest, title, count, origin)
            return CatalogEntry('imported:' + copied_digest, title, destination, 'imported',
                                True, 'import-validation', count=count)
        finally:
            # Only names created from this unique owned temp are eligible for cleanup.
            for owned in (temporary, Path(str(temporary) + '-wal'), Path(str(temporary) + '-shm')):
                owned.unlink(missing_ok=True)

    def _save_metadata(self, digest, title, count, origin):
        with _METADATA_LOCK:
            previous = self._metadata(digest)
            origins = list(previous['origins']) if previous else []
            if origin not in origins:
                origins.append(origin)
            record = dict(sha256=digest, title=title, count=count, origins=origins)
            encoded = bytearray()
            try:
                for chunk in json.JSONEncoder(ensure_ascii=False, indent=2).iterencode(record):
                    data = chunk.encode('utf-8')
                    if len(encoded) + len(data) > MAX_METADATA_BYTES:
                        raise CatalogError('İçe aktarma metadata dosyası 64 KiB sınırını aşıyor; doğrulanmış profil kopyası korundu.')
                    encoded.extend(data)
            except RecursionError as exc:
                raise CatalogError('İçe aktarma metadata yapısı çok derin; profil kopyası korundu.') from exc
            fd, name = tempfile.mkstemp(prefix='.metadata-', suffix='.json', dir=self.imported_dir)
            temporary = Path(name)
            try:
                with os.fdopen(fd, 'wb') as output:
                    output.write(encoded)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.imported_dir / (digest + '.json'))
            finally:
                temporary.unlink(missing_ok=True)
