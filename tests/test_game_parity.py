"""Finite source-derived game-memory contract cases using the shipped schema."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unittest
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


def norm(text):
    text = re.sub(r'<[^>]*>', ' ', unicodedata.normalize('NFKC', text)).casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text).split())


# (origin key, English source, verified Turkish, stored normalized source, kind)
ROWS = [
    ('short:1', 'Open northern gate', 'Kuzey kapısını aç.', None, 'full'),
    ('fuzzy:1', 'We need to leave before the guards return.', 'Gardiyanlar dönmeden gitmeliyiz.', None, 'full'),
    ('glued:1', 'We need to be quiet before the guards return.', 'Gardiyanlar dönmeden sessiz olmalıyız.', None, 'full'),
    ('repeat:1', 'Listen to me carefully.', 'Beni dikkatle dinle.', None, 'full'),
    ('prefix:1', 'When the northern bridge collapses, take the hidden passage beneath the old mill.',
     'Kuzeydeki köprü yıkıldığında, eski değirmenin altındaki gizli geçidi kullan.', None, 'full'),
    ('ambiga:1', 'Before the northern army arrives, hide the weapons under the bridge.',
     'Kuzey ordusu gelmeden önce, silahları köprünün altına sakla.', None, 'full'),
    ('ambigb:1', 'Before the northern army arrives, leave the village through the mountains.',
     'Kuzey ordusu gelmeden evvel, dağlardan köyü terk et.', None, 'full'),
    ('continue:1', 'Before the ancient fortress collapses, take your wounded friend home.',
     'Kadim kale yıkılmadan önce, yaralı arkadaşını eve götür.', None, 'full'),
    ('middle:1', 'Our scout discovered the hidden tunnel beneath the northern fortress before sunrise.',
     'İzcimiz gün doğmadan kuzey kalesinin altındaki gizli tüneli keşfetti.', None, 'full'),
    ('mida:1', 'Our captain discovered the ancient passage beneath the southern fortress before sunrise.',
     'Kaptanımız güney kalesinin altındaki kadim geçidi gün doğmadan keşfetti.', None, 'full'),
    ('midb:1', 'Your captain found the ancient passage beneath the southern fortress during the storm.',
     'Kaptanınız güney kalesinin altındaki kadim geçidi fırtınada buldu.', None, 'full'),
    ('joined:2', 'Take the silver lantern through the eastern gate.', 'Gümüş feneri doğu kapısından geçir.', None, 'full'),
    ('span:1', 'There is no time to explain the plan.', 'Planı açıklamak için zaman yok.', None, 'span'),
    ('stored:1', 'Stored source display differs.', 'Saklanan normalizasyon kullanıldı.', 'canonical lookup phrase', 'sentence'),
]


CASES = [
    dict(name='exact_short', text='Open northern gate', key='short:1', kind='full'),
    dict(name='fuzzy_transposition', text='We need to leave before the gurads return.', key='fuzzy:1', kind='full', confidence=97.6),
    dict(name='glued_words', text='We need tobe quiet before the guards return.', key='glued:1', kind='full', confidence=98.9),
    dict(name='repeated_opener', text='Listen listen to me carefully.', key='repeat:1', kind='full'),
    dict(name='prefix_comma', text='When the northern bridge collapses', key='prefix:1', kind='partial-prefix',
         translation='Kuzeydeki köprü yıkıldığında'),
    dict(name='ambiguous_prefix_without_context', text='Before the northern army arrives', missing=True),
    dict(name='ambiguous_prefix_with_scene', text='Before the northern army arrives', previous='ambigb:9',
         key='ambigb:1', kind='partial-prefix', translation='Kuzey ordusu gelmeden evvel'),
    dict(name='continuation_in_origin', text='take your wounded friend home', previous='continue:1',
         key='continue:1', kind='continuation', translation='yaralı arkadaşını eve götür.'),
    dict(name='continuation_no_origin', text='take your wounded friend home', missing=True),
    dict(name='continuation_wrong_origin', text='take your wounded friend home', previous='unrelated:1', missing=True),
    dict(name='distinctive_middle', text='the hidden tunnel beneath the northern fortress', key='middle:1', kind='partial-middle'),
    dict(name='ambiguous_middle_without_context', text='the ancient passage beneath the southern fortress', missing=True),
    dict(name='ambiguous_middle_with_origin', text='the ancient passage beneath the southern fortress', previous='midb:1',
         key='midb:1', kind='continuation'),
    dict(name='joined_with_minor_unmatched_text', text='ARTHUR We need toleave before the guards return. Take the silverlantern through the eastern gate. now',
         key='fuzzy:1', kind='joined', translation='Gardiyanlar dönmeden gitmeliyiz. Gümüş feneri doğu kapısından geçir.'),
    dict(name='joined_insufficient_coverage', text='We need toleave before the guards return. Completely irrelevant additional words about another unknown situation beyond this scene and many other people who never appeared in this dialogue.', missing=True),
    dict(name='explicit_speaker', text='ARTHUR: Open northern gate', key='short:1', kind='speaker-filtered'),
    dict(name='speaker_without_colon', text='ARTHUR Open northern gate', key='short:1', kind='speaker-filtered'),
    dict(name='two_word_speaker', text='John Marston Open northern gate', key='short:1', kind='speaker-filtered'),
    dict(name='speaker_filter_disabled', text='ARTHUR: Open northern gate', ignore_speaker=False, missing=True),
    dict(name='ordinary_opener_not_speaker', text='We Open northern gate', missing=True),
    dict(name='title_word_not_single_speaker', text='Arthur Open northern gate', missing=True),
    dict(name='stored_span_kind', text='There is no time to explain the plan.', key='span:1', kind='span'),
    dict(name='stored_norm_is_authority', text='canonical lookup phrase', key='stored:1', kind='sentence'),
]


def write_fixture(path):
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''CREATE TABLE metadata(name TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE lookup_entries(origin_key TEXT,en_text TEXT,tr_text TEXT,en_norm TEXT,kind TEXT);''')
        db.executemany('INSERT INTO metadata VALUES (?,?)', [
            ('format','duplay-game-memory-v1'), ('title','Finite game parity fixture'),
            ('game_id','parity-fixture'), ('origin','generated'), ('shared_keys',str(len(ROWS)))])
        db.executemany('INSERT INTO lookup_entries VALUES (?,?,?,?,?)',
                       [(key,en,tr,stored if stored is not None else norm(en),kind)
                        for key,en,tr,stored,kind in ROWS])
        db.commit()


class GameParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from profiles import GameProfile
        cls.folder = tempfile.TemporaryDirectory()
        cls.path = Path(cls.folder.name)/'fixture.sqlite'
        write_fixture(cls.path)
        cls.original_bytes = cls.path.read_bytes()
        cls.profile = GameProfile(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.profile = None
        cls.folder.cleanup()

    def test_finite_reference_contract_cases(self):
        for case in CASES:
            with self.subTest(case=case['name']):
                result = self.profile.match(case['text'],case.get('previous'),case.get('ignore_speaker',True))
                if case.get('missing'):
                    self.assertIsNone(result)
                else:
                    self.assertIsNotNone(result)
                    self.assertEqual(result.key,case['key'])
                    self.assertEqual(result.kind,case['kind'])
                    row=next(row for row in ROWS if row[0]==case['key'])
                    self.assertEqual(result.translation,case.get('translation',row[2]))
                    expected_source=norm(case['text']) if case['kind']=='joined' else row[1]
                    self.assertEqual(result.source,expected_source)
                    defaults={'continuation':99.0,'partial-middle':99.0,'joined':97.0}
                    self.assertEqual(result.confidence,case.get('confidence',defaults.get(case['kind'],100.0)))
        self.assertEqual(self.path.read_bytes(),self.original_bytes)


if __name__ == '__main__':
    unittest.main()
