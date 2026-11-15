"""Verify and optionally unpack a portable build into a new directory."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('archive', type=Path)
parser.add_argument('--extract-to', type=Path)
args = parser.parse_args()
if args.extract_to and args.extract_to.exists():
    raise SystemExit('Çıkarma hedefi yeni bir klasör olmalı.')
with zipfile.ZipFile(args.archive) as archive:
    entries = archive.infolist()
    if len(entries) > 25000 or sum(item.file_size for item in entries) > 8 * 1024**3:
        raise SystemExit('Paket kaynak sınırlarını aşıyor.')
    names = [entry.filename for entry in entries]
    if len(set(name.casefold() for name in names)) != len(names):
        raise SystemExit('Paket çakışan dosya adları içeriyor.')
    for entry in entries:
        path = PurePosixPath(entry.filename)
        if path.is_absolute() or '\\' in entry.filename or ':' in entry.filename or '..' in path.parts or path.parts[0] != 'AltyaziAtolyesi':
            raise SystemExit('Geçersiz paket yolu: ' + entry.filename)
        if stat.S_ISLNK(entry.external_attr >> 16):
            raise SystemExit('Paket sembolik bağlantı içeriyor.')
    manifest_name = 'AltyaziAtolyesi/package-manifest.json'
    if archive.getinfo(manifest_name).file_size > 16 * 1024 * 1024:
        raise SystemExit('Manifest çok büyük.')
    manifest = json.loads(archive.read(manifest_name))
    expected = {manifest_name}
    for record in manifest:
        name = 'AltyaziAtolyesi/' + record['path']
        if name in expected:
            raise SystemExit('Tekrarlanan manifest girdisi.')
        expected.add(name)
        digest, size = hashlib.sha256(), 0
        with archive.open(name) as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        if size != record['bytes'] or digest.hexdigest() != record['sha256']:
            raise SystemExit('Dosya doğrulanamadı: ' + name)
    if expected != set(names):
        raise SystemExit('Arşiv ve manifest kapsamları farklı.')
    if args.extract_to:
        args.extract_to.mkdir(parents=True)
        archive.extractall(args.extract_to)
digest = hashlib.sha256()
with args.archive.open('rb') as source:
    while chunk := source.read(1024 * 1024):
        digest.update(chunk)
print(json.dumps(dict(files_verified=len(manifest), archive_sha256=digest.hexdigest(),
                      extracted_to=str(args.extract_to) if args.extract_to else None)))
