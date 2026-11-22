import json
import sys
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from glossary import UserDictionary, normalize, FORMAT, MAX_TERMS
from engine import Engine


class DictionaryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'sozluk.json'

    def tearDown(self):
        self.folder.cleanup()

    def test_correction_lookup_ignores_case_spacing_punctuation_and_keeps_speaker(self):
        words = UserDictionary(self.path)
        words.set_correction('Get to the  horse!', 'Ata bin!')
        snap = words.snapshot()
        self.assertEqual(snap.correction('get to the horse'), 'Ata bin!')
        self.assertEqual(snap.correction('Arthur: Get to the horse.'), 'Arthur: Ata bin!')
        self.assertIsNone(snap.correction('Get to the horses'))
        self.assertEqual(normalize('  A  b?! '), 'a b')

    def test_persists_reloads_and_versions_change(self):
        words = UserDictionary(self.path)
        first = words.snapshot().version
        words.set_term('bounty', 'ödül')
        words.set_term('Arthur', '')
        words.set_correction('Hello there.', 'Selam.')
        self.assertGreater(words.snapshot().version, first)
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(stored['format'], FORMAT)
        again = UserDictionary(self.path)
        self.assertEqual(again.terms(), [('bounty', 'ödül'), ('Arthur', '')])
        self.assertEqual(again.corrections(), [('Hello there.', 'Selam.')])
        again.remove_term('BOUNTY')
        again.remove_correction('hello there')
        self.assertEqual(UserDictionary(self.path).terms(), [('Arthur', '')])
        self.assertEqual(UserDictionary(self.path).corrections(), [])

    def test_terms_match_whole_words_longest_first_case_insensitive(self):
        words = UserDictionary(self.path)
        words.set_term('Dutch', '')
        words.set_term('Dutch van der Linde', 'Dutch')
        words.set_term('bounty', 'ödül')
        snap = words.snapshot()
        self.assertEqual(snap.apply_terms('Dutch van der Linde has a Bounty.'), 'Dutch has a ödül.')
        self.assertEqual(snap.apply_terms('bounty-hunter bountyful'), 'ödül-hunter bountyful')

    def test_invalid_input_is_rejected_without_changing_state(self):
        words = UserDictionary(self.path)
        words.set_term('bounty', 'ödül')
        for source, target in (('', 'x'), ('...', 'x'), ('x' * 65, 'y')):
            with self.subTest(source=source), self.assertRaises(ValueError):
                words.set_term(source, target)
        with self.assertRaises(ValueError):
            words.set_correction('Hello', '   ')
        with patch('glossary.os.replace', side_effect=OSError('disk full')), self.assertRaises(OSError):
            words.set_term('horse', 'at')
        self.assertEqual(words.terms(), [('bounty', 'ödül')])
        self.assertEqual(words.snapshot().apply_terms('horse'), 'horse')

    def test_unreadable_file_is_kept_aside_before_first_save(self):
        self.path.write_bytes(b'{not json')
        words = UserDictionary(self.path)
        self.assertIn('okunamadı', words.warning)
        self.assertEqual(words.terms(), [])
        words.set_term('bounty', 'ödül')
        kept = list(Path(self.folder.name).glob('sozluk.okunamayan-*.json'))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_bytes(), b'{not json')
        self.assertEqual(UserDictionary(self.path).terms(), [('bounty', 'ödül')])

    def test_limits(self):
        words = UserDictionary(self.path)
        words._terms = [(f't{i}', '') for i in range(MAX_TERMS)]
        with self.assertRaises(ValueError):
            words.set_term('extra', '')
        self.assertEqual(len(words.terms()), MAX_TERMS)


class EngineDictionaryTests(unittest.TestCase):
    def engine(self, calls):
        engine = Engine.__new__(Engine)
        engine._translation_prepared = True
        engine.profile = None
        engine.ocr_kind = 'subtitle'
        engine.previous, engine.previous_at, engine.ignore_speaker = None, 0.0, True
        engine.cancelled = lambda: False
        engine.cache = OrderedDict()
        engine.tokenizer = SimpleNamespace(encode=lambda text, **kwargs: text.split(),
            convert_ids_to_tokens=lambda tokens: tokens, convert_tokens_to_ids=lambda tokens: tokens,
            decode=lambda tokens, **kwargs: ' '.join(tokens))
        def translate(sources, **options):
            calls.append(sources)
            return [SimpleNamespace(hypotheses=[list(source)]) for source in sources]
        engine.translator = SimpleNamespace(translate_batch=translate, device='cpu', cuda_failure=None)
        return engine

    def test_correction_wins_over_profile_and_model_terms_reach_model_and_cache_resets(self):
        with tempfile.TemporaryDirectory() as folder:
            words = UserDictionary(Path(folder) / 'sozluk.json')
            calls = []
            engine = self.engine(calls)
            engine.profile = SimpleNamespace(match=lambda *args, **kwargs: SimpleNamespace(
                key='k', kind='exact', confidence=100, translation='profil'))
            engine.dictionary = words
            words.set_correction('Known line.', 'Benim çevirim.')
            self.assertEqual(engine.translate('Arthur: known line'), 'Arthur: Benim çevirim.')
            self.assertEqual(engine.last_translation.source, 'user')
            self.assertEqual(engine.translate('Other line.'), 'profil')
            engine.profile = None
            words.set_term('bounty', 'ödül')
            self.assertEqual(engine.translate('A bounty here'), 'A ödül here')
            self.assertEqual(calls[-1], [['A', 'ödül', 'here', '</s>']])
            words.set_term('bounty', 'kelle parası')
            self.assertEqual(engine.translate('A bounty here'), 'A kelle parası here')
            self.assertFalse(engine.last_translation.cached)


if __name__ == '__main__':
    unittest.main()
