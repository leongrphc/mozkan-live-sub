import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from profiles import GameProfile, ProfileMatch
from settings import Settings
from engine import Engine
from unittest.mock import Mock, patch


class ProfilesTests(unittest.TestCase):
    def test_engine_passes_both_speaker_options_to_real_sqlite_matching(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'profile.sqlite'
            with closing(sqlite3.connect(path)) as db:
                db.executescript('CREATE TABLE metadata(name,value); CREATE TABLE lookup_entries(origin_key,en_text,tr_text,en_norm,kind);')
                db.execute('INSERT INTO metadata VALUES (?,?)',('format','duplay-game-memory-v1'))
                db.execute('INSERT INTO lookup_entries VALUES (?,?,?,?,?)',('a:1','Open northern gate','Kuzey kapısını aç','open northern gate','full'))
                db.commit()
            profile=GameProfile(path)
            for ignore,expected in [(True,'Kuzey kapısını aç'),(False,'')]:
                with patch('rapidocr.RapidOCR'):
                    engine=Engine(Path(__file__).resolve().parents[1]/'models',profile=profile,fallback=False,ignore_speaker=ignore)
                self.assertEqual(engine.translate('ARTHUR: Open northern gate'),expected)
                self.assertEqual(engine.last_translation.source,'profile' if ignore else 'unmatched')
                if ignore:self.assertEqual(engine.last_translation.match_percent,profile.match('ARTHUR: Open northern gate').confidence)

    def test_profile_view_is_rejected_as_a_stored_record_table(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'view.sqlite'
            with closing(sqlite3.connect(path)) as db:
                db.executescript("CREATE TABLE metadata(name,value); INSERT INTO metadata VALUES ('format','duplay-game-memory-v1'); CREATE VIEW lookup_entries AS SELECT 'a' origin_key,'Hello' en_text,'Merhaba' tr_text,'hello' en_norm,'full' kind;")
                db.commit()
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                GameProfile(path)
            self.assertEqual(path.read_bytes(),before)
    def test_old_scene_context_expires_before_lookup(self):
        engine = Engine.__new__(Engine)
        engine.profile = Mock()
        engine.ignore_speaker=True
        engine.previous = 'old:scene'
        engine.previous_at = 10
        engine.profile.match.return_value = ProfileMatch('new:scene', 'Hello', 'Merhaba', 100, 'full')
        with patch('engine.time.monotonic', return_value=23):
            self.assertEqual(engine.translate('Hello'), 'Merhaba')
        engine.profile.match.assert_called_once_with('Hello', None,ignore_speaker=True)
        self.assertEqual(engine.previous, 'new:scene')

    def test_scene_disambiguation_and_missing_short_line(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'game.sqlite'
            with closing(sqlite3.connect(path)) as db:
                db.executescript('CREATE TABLE metadata(name,value); CREATE TABLE lookup_entries(origin_key,en_text,tr_text,en_norm,kind);')
                db.execute('INSERT INTO metadata VALUES (?,?)', ('format', 'duplay-game-memory-v1'))
                db.executemany('INSERT INTO lookup_entries VALUES (?,?,?,?,?)', [
                    ('a:1', 'Hello!', 'Merhaba', 'hello', 'full'), ('b:1', 'Hello!', 'Selam', 'hello', 'full')])
                db.commit()
            before = path.read_bytes()
            profile = GameProfile(path)
            self.assertEqual(profile.match('HELLO', 'b:0').translation, 'Selam')
            self.assertIsNone(profile.match('Help'))
            self.assertEqual(before, path.read_bytes())

    def test_settings_keep_previous_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            settings = Settings(path)
            settings.save(font_size=24)
            first = path.read_bytes()
            settings.save(font_size=30)
            self.assertEqual(path.with_suffix('.json.bak').read_bytes(), first)
            self.assertEqual(Settings(path).values['font_size'], 30)

    def test_missing_stored_normalization_is_not_silently_invented(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'game.sqlite'
            with closing(sqlite3.connect(path)) as db:
                db.executescript('CREATE TABLE metadata(name,value); CREATE TABLE lookup_entries(origin_key,en_text,tr_text);')
                db.execute('INSERT INTO metadata VALUES (?,?)', ('format', 'duplay-game-memory-v1'))
                db.execute('INSERT INTO lookup_entries VALUES (?,?,?)', ('a:1','Hello','Merhaba'))
                db.commit()
            with self.assertRaises(ValueError):
                GameProfile(path)
