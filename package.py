"""Build a local portable archive from the prepared runtime. No downloads."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent
destination = args.output.resolve()
if destination.exists():
    raise SystemExit('Paket hedefi zaten var; yeni bir dosya adı seçin.')
for required in ('MOZKANLiveSub.exe', 'python/pythonw.exe', 'models/opus-mt-tc-big-en-tr-ct2/model.bin'):
    if not (root / required).is_file():
        raise SystemExit('Eksik paket girdisi: ' + required)
files = [root / name for name in ('MOZKANLiveSub.exe', 'start.ps1', 'README.md', 'TESLIM.md', 'REBRAND.md', 'requirements.txt')]
files.extend(root.glob('UPDATE-*.md'))
for folder in ('src', 'python', 'models', 'game_profiles', 'samsung'):
    files.extend(p for p in (root / folder).rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts and p.suffix != '.pyc')
destination.parent.mkdir(parents=True, exist_ok=True)
manifest = []
try:
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as archive:
        for path in sorted(files):
            relative = path.relative_to(root).as_posix()
            digest = hashlib.sha256()
            with path.open('rb') as source, archive.open('MOZKANLiveSub/' + relative, 'w', force_zip64=True) as output:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
            manifest.append(dict(path=relative, bytes=path.stat().st_size, sha256=digest.hexdigest()))
        archive.writestr('MOZKANLiveSub/package-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
except BaseException:
    destination.unlink(missing_ok=True)
    raise
print(json.dumps(dict(path=str(destination), files=len(manifest), archive_bytes=destination.stat().st_size,
                      source_bytes=sum(item['bytes'] for item in manifest))))
