import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import catalog
from catalog import Catalog, CatalogError
from profiles import normalize


def profile_file(path, title='Example game', translation='Merhaba'):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''CREATE TABLE metadata(name TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE lookup_entries(origin_key TEXT,en_text TEXT,tr_text TEXT,en_norm TEXT,kind TEXT);''')
        db.executemany('INSERT INTO metadata VALUES (?,?)', [
            ('format', 'duplay-game-memory-v1'), ('title', title), ('game_id', 'example')])
        db.execute('INSERT INTO lookup_entries VALUES (?,?,?,?,?)',
                   ('scene:1', 'Hello', translation, normalize('Hello'), 'full'))
        db.commit()


class CatalogTests(unittest.TestCase):
    def test_import_is_owned_and_survives_original_removal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source' / 'example.sqlite'
            profile_file(source)
            before = source.read_bytes()
            catalog = Catalog(root / 'bundle', root / 'data' / 'games')
            entry = catalog.import_profile(source)
            digest = hashlib.sha256(before).hexdigest()
            self.assertEqual(entry.identity, 'imported:' + digest)
            self.assertEqual(entry.title, 'Example game')
            self.assertEqual(source.read_bytes(), before)
            source.unlink()
            self.assertEqual(catalog.resolve(entry.identity).read_bytes(), before)
            restored = Catalog(root / 'different-bundle', root / 'data' / 'games')
            self.assertEqual(restored.entries[0].title, 'Example game')
            self.assertEqual(restored.entries[0].title_source, 'stored-import-metadata')
            self.assertEqual(restored.entries[0].count, 1)
            metadata = json.loads(entry.path.with_suffix('.json').read_text(encoding='utf-8'))
            self.assertEqual(metadata['origins'][0]['selected_path'], str(source))
            self.assertEqual(metadata['origins'][0]['sha256'], digest)

    def test_same_filename_different_contents_have_distinct_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first, second = root / 'a' / 'game.sqlite', root / 'b' / 'game.sqlite'
            profile_file(first, translation='Merhaba')
            profile_file(second, translation='Selam')
            catalog = Catalog(root / 'bundle', root / 'owned')
            one, two = catalog.import_profile(first), catalog.import_profile(second)
            self.assertNotEqual(one.identity, two.identity)
            self.assertEqual(len(catalog.entries), 2)
            again = catalog.import_profile(first)
            self.assertEqual(one.identity, again.identity)
            self.assertEqual(len(catalog.entries), 2)

    def test_builtin_selection_follows_new_bundle_and_missing_stays_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first, second = root / 'first', root / 'second'
            first.mkdir(); second.mkdir()
            (first / 'rdr2.svgame.sqlite').write_bytes(b'first')
            (second / 'rdr2.svgame.sqlite').write_bytes(b'second')
            with patch('catalog.GameProfile', side_effect=AssertionError('inventory loaded full DB')):
                original = Catalog(first, root / 'imports')
                identity = original.entries[0].identity
                relocated = Catalog(second, root / 'imports')
                self.assertEqual(relocated.resolve(identity), second / 'rdr2.svgame.sqlite')
            (second / 'rdr2.svgame.sqlite').unlink()
            with self.assertRaisesRegex(FileNotFoundError, 'otomatik'):
                relocated.resolve(identity)

    def test_legacy_external_path_is_never_reclassified_as_builtin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundled = root / 'bundle'
            bundled.mkdir()
            path = bundled / 'rdr2.svgame.sqlite'
            path.write_bytes(b'placeholder')
            catalog = Catalog(bundled, root / 'imports')
            legacy = catalog.legacy_external(path)
            self.assertEqual(legacy.kind, 'external')
            self.assertEqual(legacy.identity, 'external:' + str(path))
            self.assertEqual(catalog.resolve(legacy.identity), path)
            path.unlink()
            self.assertFalse(catalog.legacy_external(path).available)
            with self.assertRaises(FileNotFoundError):
                catalog.resolve(legacy.identity)

    def test_nonempty_wal_is_rejected_without_touching_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'game.sqlite'
            profile_file(source)
            before = source.read_bytes()
            wal = Path(str(source) + '-wal')
            wal.write_bytes(b'caller WAL evidence')
            catalog = Catalog(root / 'bundle', root / 'imports')
            with self.assertRaisesRegex(CatalogError, 'WAL'):
                catalog.import_profile(source)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(wal.read_bytes(), b'caller WAL evidence')
            self.assertFalse(catalog.imported_dir.exists())

    def test_malformed_profile_and_copy_change_clean_only_owned_temps(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'invalid.sqlite'
            source.write_bytes(b'not a database')
            catalog = Catalog(root / 'bundle', root / 'imports')
            caller_file = catalog.imported_dir / 'keep-me.txt'
            caller_file.parent.mkdir()
            caller_file.write_text('caller evidence', encoding='utf-8')
            with self.assertRaises(CatalogError):
                catalog.import_profile(source)
            self.assertEqual(source.read_bytes(), b'not a database')
            self.assertEqual(list(catalog.imported_dir.iterdir()), [caller_file])
            valid = root / 'valid.sqlite'
            profile_file(valid)
            real_fsync = __import__('os').fsync
            changed = [False]
            def change_source(fd):
                real_fsync(fd)
                if not changed[0]:
                    changed[0] = True
                    with valid.open('ab') as stream:
                        stream.write(b'changed during acquisition')
            with patch('catalog.os.fsync', side_effect=change_source):
                with self.assertRaisesRegex(CatalogError, 'değişti'):
                    catalog.import_profile(valid)
            self.assertEqual(list(catalog.imported_dir.iterdir()), [caller_file])

    def test_import_hash_is_of_validated_copy_not_later_mutated_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'game.sqlite'
            profile_file(source)
            before = source.read_bytes()
            actual_validator = catalog.GameProfile
            def validate_snapshot(path):
                result = actual_validator(path)
                source.write_bytes(b'source changed after copy')
                return result
            manager = Catalog(root / 'bundle', root / 'imports')
            with patch('catalog.GameProfile', side_effect=validate_snapshot):
                entry = manager.import_profile(source)
            self.assertEqual(entry.path.read_bytes(), before)
            self.assertEqual(entry.identity, 'imported:' + hashlib.sha256(before).hexdigest())

    def test_tampered_import_is_not_overwritten_or_silently_resolved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'game.sqlite'
            profile_file(source)
            catalog = Catalog(root / 'bundle', root / 'imports')
            entry = catalog.import_profile(source)
            entry.path.write_bytes(b'corrupted owned data')
            with self.assertRaisesRegex(CatalogError, 'bozulmuş'):
                catalog.resolve(entry.identity)
            with self.assertRaisesRegex(CatalogError, 'üzerine yazılmadı'):
                catalog.import_profile(source)
            self.assertEqual(entry.path.read_bytes(), b'corrupted owned data')

    def test_profile_path_escape_and_unknown_identity_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            catalog = Catalog(root / 'bundle', root / 'imports')
            for identity in ('bundled:../outside.sqlite', 'bundled:..\\outside.sqlite',
                             'imported:../outside', 'external:relative.sqlite', 'unknown:game'):
                with self.subTest(identity=identity), self.assertRaises(CatalogError):
                    catalog.resolve(identity)


if __name__ == '__main__':
    unittest.main()
