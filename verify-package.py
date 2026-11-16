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
    roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
    if len(roots) != 1 or not roots <= {'MOZKANLiveSub', 'AltyaziAtolyesi'}:
        raise SystemExit('Geçersiz paket kökü.')
    package_root = roots.pop()
    for entry in entries:
        path = PurePosixPath(entry.filename)
        if path.is_absolute() or '\\' in entry.filename or ':' in entry.filename or '..' in path.parts or not path.parts or path.parts[0] != package_root:
            raise SystemExit('Geçersiz paket yolu: ' + entry.filename)
        if stat.S_ISLNK(entry.external_attr >> 16):
            raise SystemExit('Paket sembolik bağlantı içeriyor.')
    manifest_name = package_root + '/package-manifest.json'
    if archive.getinfo(manifest_name).file_size > 16 * 1024 * 1024:
        raise SystemExit('Manifest çok büyük.')
    manifest = json.loads(archive.read(manifest_name))
    expected = {manifest_name}
    update_name = package_root + '/update-manifest.json'
    if update_name in names:
        if archive.getinfo(update_name).file_size > 16 * 1024 * 1024:
            raise SystemExit('Güncelleme manifesti çok büyük.')
        update = json.loads(archive.read(update_name))
        if update.get('version') != '0.4.1' or update.get('files') != manifest or update.get('from_versions') != ['0.4.0']:
            raise SystemExit('Güncelleme manifesti paket kapsamıyla farklı.')
        expected.add(update_name)
    for record in manifest:
        name = package_root + '/' + record['path']
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
