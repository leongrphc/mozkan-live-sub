import json
import tempfile
import os
import hashlib
from unittest.mock import patch
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from settings import Settings


class SettingsTests(unittest.TestCase):
    def test_malformed_region_source_survives_later_independent_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            raw=b'{"font_size":24,"regions":{"version":99,"subtitle":null,"hud":null}}'
            path.write_bytes(raw)
            settings=Settings(path)
            self.assertTrue(settings.region_issues)
            self.assertFalse(settings.primary_valid)
            self.assertEqual(settings.values['font_size'],24)
            settings.save(font_size=30)
            settings.save(regions=dict(version=1,subtitle=None,hud=None))
            settings.save(font_size=32)
            preserved=path.with_name('settings.invalid-'+hashlib.sha256(raw).hexdigest()+'.json')
            self.assertEqual(preserved.read_bytes(),raw)
            self.assertEqual(settings.values['regions']['version'],1)
            self.assertFalse(settings.region_issues)
            with self.assertRaises(ValueError):
                settings.save(regions=dict(version=100,subtitle=None,hud=None))

    def test_committed_snapshot_detaches_mutable_input_and_exposes_readonly_regions(self):
        with tempfile.TemporaryDirectory() as folder:
            settings=Settings(Path(folder)/'settings.json')
            value=dict(version=1,subtitle=None,hud=None)
            extra=dict(items=['original'])
            settings.save(regions=value,extra=extra)
            value['version']=99
            extra['items'][0]='mutated'
            self.assertEqual(settings.values['regions']['version'],1)
            self.assertEqual(settings.values['extra']['items'],['original'])
            with self.assertRaises(TypeError):
                settings.regions['subtitle']=None
            settings.save(font_size=30)
            self.assertEqual(json.loads(settings.path.read_bytes())['extra']['items'],['original'])

    def test_writer_after_commit_is_not_adopted_as_our_loaded_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            settings=Settings(path)
            replace=os.replace
            foreign=b'{"font_size":40,"mode":"movie"}'
            def intervene(source,destination):
                replace(source,destination)
                Path(destination).write_bytes(foreign)
            with patch('settings.os.replace',side_effect=intervene):
                settings.save(font_size=30)
            self.assertEqual(settings.values['font_size'],30)
            self.assertNotEqual(settings.loaded_bytes,foreign)
            with self.assertRaises(OSError):
                settings.save(dialogue=True)
            self.assertEqual(path.read_bytes(),foreign)

    def test_legacy_pixel_offset_migrates_exactly_once_without_writing_on_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            raw=b'{"overlay_y_offset":23,"mode":"movie"}'
            path.write_bytes(raw)
            settings=Settings(path)
            self.assertEqual(settings.values['overlay_y_offset'],-2.3)
            self.assertEqual(path.read_bytes(),raw)
            settings.save(font_size=30)
            self.assertEqual(path.with_suffix('.json.bak').read_bytes(),raw)
            self.assertEqual(Settings(path).values['overlay_y_offset'],-2.3)
            self.assertEqual(Settings(path).values['mode'],'movie')

    def test_new_offset_persists_units_and_unknown_units_do_not_move_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            settings=Settings(path)
            settings.save(overlay_y_offset=8)
            self.assertEqual(Settings(path).values['overlay_y_offset'],8)
            path.write_text('{"overlay_y_offset":8,"overlay_offset_version":9}',encoding='utf-8')
            settings=Settings(path)
            self.assertNotIn('overlay_y_offset',settings.values)
            self.assertTrue(settings.warnings)

    def test_save_cannot_create_a_file_larger_than_its_read_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            settings = Settings(path)
            with self.assertRaises(ValueError):
                settings.save(extra='x' * (Settings.MAX_BYTES + 1))
            self.assertFalse(path.exists())

    def test_oversized_settings_are_bounded_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            contents = b' ' * (Settings.MAX_BYTES + 20)
            path.write_bytes(contents)
            settings = Settings(path)
            self.assertLessEqual(len(settings.loaded_bytes), Settings.MAX_BYTES + 1)
            self.assertTrue(settings.warnings)
            with self.assertRaises(OSError):
                settings.save(font_size=30)
            self.assertEqual(path.read_bytes(), contents)

    def test_invalid_primary_recovers_backup_and_preserves_both(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            bad = b'{unfinished'
            backup = b'{"font_size":30,"mode":"movie"}'
            path.write_bytes(bad)
            path.with_suffix('.json.bak').write_bytes(backup)
            settings = Settings(path)
            self.assertEqual(settings.values['font_size'], 30)
            self.assertTrue(settings.warnings)
            self.assertEqual(path.read_bytes(), bad)
            settings.save(dialogue=True)
            self.assertEqual(path.with_suffix('.json.bak').read_bytes(), backup)
            self.assertEqual(next(Path(folder).glob('settings.invalid-*.json')).read_bytes(), bad)
            self.assertTrue(json.loads(path.read_bytes())['dialogue'])

    def test_invalid_fields_do_not_discard_independent_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text('{"font_size":true,"video_band":"bad","mode":"movie","dialogue":true,"caption_mode":42}',encoding='utf-8')
            settings = Settings(path)
            self.assertNotIn('font_size', settings.values)
            self.assertNotIn('video_band', settings.values)
            self.assertNotIn('caption_mode', settings.values)
            self.assertEqual(settings.values['mode'], 'movie')
            self.assertTrue(settings.values['dialogue'])

    def test_stale_writer_cannot_replace_newer_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            first, stale = Settings(path), Settings(path)
            first.save(font_size=30)
            with self.assertRaises(OSError):
                stale.save(font_size=40)
            self.assertEqual(Settings(path).values['font_size'], 30)
