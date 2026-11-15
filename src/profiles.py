"""Parsed game-profile facts and the reference-derived matching policy."""
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path
import re
import sqlite3
import unicodedata
from rapidfuzz.fuzz import ratio


def normalize(text):
    text = re.sub(r'<[^>]*>', ' ', unicodedata.normalize('NFKC', text)).casefold()
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


@dataclass(frozen=True, slots=True)
class ProfileEntry:
    key: str
    source: str
    translation: str
    normalized: str
    kind: str


@dataclass(frozen=True, slots=True)
class ProfileMatch:
    key: str
    source: str
    translation: str
    confidence: float
    kind: str


class GameProfile:
    MAX_BYTES = 256 * 1024 * 1024
    MAX_ROWS = 250000

    def __init__(self, path):
        self.path = Path(path).resolve()
        if not self.path.is_file() or self.path.stat().st_size > self.MAX_BYTES:
            raise ValueError('Oyun profili bulunamadı veya 256 MiB sınırını aşıyor.')
        self.rows = []
        self.exact = defaultdict(list)
        self.squash = defaultdict(list)
        self.words = defaultdict(set)
        self.prefix = defaultdict(list)
        self.by_key = defaultdict(list)
        self.full_prefix = defaultdict(list)
        try:
            with closing(sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)) as db:
                db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 16 * 1024 * 1024)
                for name in ('metadata','lookup_entries'):
                    table = db.execute("SELECT type FROM pragma_table_list WHERE schema='main' AND name=?", (name,)).fetchone()
                    if table is None or table[0] != 'table':
                        raise ValueError('Profil alanı normal bir SQLite tablosu olmalı: ' + name)
                metadata, metadata_bytes = {}, 0
                for count, (key,value) in enumerate(db.execute('SELECT name,value FROM metadata'), 1):
                    if not isinstance(key,str) or not isinstance(value,str):
                        raise ValueError('Oyun profili metadata alanları metin olmalı.')
                    metadata_bytes += len(key.encode('utf-8')) + len(value.encode('utf-8'))
                    if count > 4096 or metadata_bytes > 1024 * 1024:
                        raise ValueError('Oyun profili metadata kaynak sınırlarını aşıyor.')
                    metadata[key] = value
                if metadata.get('format') not in ('duplay-game-memory-v1', 'subvori-game-memory-v1'):
                    raise ValueError('Desteklenmeyen oyun profili.')
                self.title = metadata.get('title', self.path.stem)
                self.game_id = metadata.get('game_id', '')
                cursor = db.execute('SELECT origin_key,en_text,tr_text,en_norm,kind FROM lookup_entries')
                for examined, values in enumerate(cursor, 1):
                    if examined > self.MAX_ROWS:
                        raise ValueError('Oyun profili 250.000 kayıt sınırını aşıyor.')
                    if not all(isinstance(value, str) for value in values):
                        raise ValueError('Oyun profilinde geçersiz kayıt.')
                    key, source, target, norm, kind = values
                    if not norm or not target.strip():
                        continue
                    index = len(self.rows)
                    self.rows.append(ProfileEntry(key, source, target, norm, kind))
                    self.exact[norm].append(index)
                    self.by_key[key].append(index)
                    tokens = norm.split()
                    if len(tokens) >= 8:
                        self.prefix[tuple(tokens[:2])].append(index)
                    for word in set(tokens):
                        if len(word) >= 3:
                            self.words[word].add(index)
                    if kind == 'full':
                        compact = norm.replace(' ', '')
                        if len(compact) >= 12:
                            self.squash[compact].append(index)
                        if len(compact) >= 28:
                            self.full_prefix[compact[:4]].append(index)
        except sqlite3.DatabaseError as exc:
            raise ValueError('Geçerli v1 SQLite oyun profili değil: ' + str(exc)) from exc
        if not self.rows:
            raise ValueError('Profilde eşleştirilmiş İngilizce/Türkçe kayıt yok.')

    def _choose(self, candidates, previous):
        if not candidates:
            return None
        if previous:
            scene = previous.split(':', 1)[0] + ':'
            same = [i for i in candidates if self.rows[i].key.startswith(scene)]
            candidates = same or candidates
        counts = Counter(self.rows[i].translation.casefold() for i in candidates)
        return max(candidates, key=lambda i: counts[self.rows[i].translation.casefold()])

    def _hit(self, index, confidence, kind=None, translation=None):
        row = self.rows[index]
        return ProfileMatch(row.key, row.source, row.translation if translation is None else translation,
                            round(confidence, 1), kind or row.kind)

    def _direct(self, query, previous):
        if not 3 <= len(query) <= 500:
            return None
        chosen = self._choose(self.exact.get(query, ()), previous)
        if chosen is not None:
            return self._hit(chosen, 100)
        compact = query.replace(' ', '')
        if len(compact) >= 12:
            chosen = self._choose(self.squash.get(compact, ()), previous)
            if chosen is not None:
                score = ratio(query, self.rows[chosen].normalized)
                if score >= 86:
                    return self._hit(chosen, score)
        tokens = query.split()
        if len(tokens) >= 3 and tokens[0] == tokens[1]:
            chosen = self._choose(self.exact.get(' '.join(tokens[1:]), ()), previous)
            if chosen is not None:
                return self._hit(chosen, 100)
        if len(query) < 19:
            return None
        terms = {w for w in tokens if len(w) >= 3}
        available = sorted((w for w in terms if w in self.words), key=lambda w: len(self.words[w]))
        votes = Counter()
        for word in available[:6]:
            if len(self.words[word]) <= 1500:
                votes.update(self.words[word])
        scored = []
        for index, _ in votes.most_common(350):
            row = self.rows[index]
            if not len(query) * .76 <= len(row.normalized) <= len(query) * 1.28:
                continue
            overlap = len(terms & set(row.normalized.split())) / max(1, len(terms))
            score = ratio(query, row.normalized)
            if overlap >= .55 and score >= 88:
                scored.append((score, overlap, index))
        scored.sort(reverse=True)
        minimum = 96 if len(query) < 32 else 94 if len(query) < 56 else 91
        if not scored or scored[0][0] < minimum:
            return None
        best = scored[0][0]
        chosen = self._choose([i for score, _, i in scored if score >= best - .5], previous)
        if chosen is None:
            return None
        if any(self.rows[i].normalized != self.rows[chosen].normalized and best - score < 3
               for score, _, i in scored):
            return None
        return self._hit(chosen, best)

    def _joined(self, query, previous):
        compact = query.replace(' ', '')
        if len(compact) < 40 or len(query.split()) < 8:
            return None
        candidates = set()
        # A >=28-char exact span necessarily exposes its first four characters
        # in the query. Index selection preserves the full-record scan's order.
        for start in range(max(0, len(compact) - 27)):
            candidates.update(self.full_prefix.get(compact[start:start + 4], ()))
        groups = defaultdict(list)
        for index in sorted(candidates):
            piece = self.rows[index].normalized.replace(' ', '')
            at = compact.find(piece)
            if at >= 0:
                groups[(at, at + len(piece))].append(index)
        chosen, cursor = [], -1
        for start, end in sorted(groups, key=lambda span: (span[0], -(span[1] - span[0]))):
            if start < cursor:
                continue
            index = self._choose(groups[(start, end)], previous)
            if index is not None:
                chosen.append((start, end, index))
                cursor = end
        if not chosen or sum(end - start for start, end, _ in chosen) < len(compact) * .68:
            return None
        translations = []
        for _, _, index in chosen:
            text = self.rows[index].translation
            if not translations or translations[-1] != text:
                translations.append(text)
        return ProfileMatch(self.rows[chosen[0][2]].key, query, ' '.join(translations), 97, 'joined')

    def _prefix(self, query, previous):
        words = query.split()
        if len(words) < 5 or not 28 <= len(query) <= 350:
            return None
        scored = []
        for index in self.prefix.get(tuple(words[:2]), ()):
            row = self.rows[index]
            if len(row.normalized) <= len(query) + 5 or len(query) < len(row.normalized) * .30:
                continue
            tokens = row.normalized.split()
            score = max((ratio(query, ' '.join(tokens[:n])) for n in
                         (len(words) - 1, len(words), len(words) + 1) if 1 <= n <= len(tokens)), default=0)
            if score >= 96 and len(set(words[-4:]) & set(tokens[:len(words) + 2])) >= 3:
                scored.append((score, index))
        if not scored:
            return None
        best = max(score for score, _ in scored)
        contenders = [i for score, i in scored if score >= best - 1]
        if len({self.rows[i].key for i in contenders}) > 1:
            same = [i for i in contenders if previous and self.rows[i].key.split(':',1)[0] == previous.split(':',1)[0]]
            if previous and len({self.rows[i].key for i in same}) == 1:
                contenders = same
            elif len({self.rows[i].translation.casefold() for i in contenders}) > 1:
                return None
        chosen = min(contenders, key=lambda i: (len(self.rows[i].normalized), self.rows[i].kind == 'full'))
        row, translated = self.rows[chosen], self.rows[chosen].translation
        if row.source.count(',') == 1 and translated.count(',') == 1:
            if normalize(row.source.split(',',1)[0]) == query:
                candidate = translated.split(',',1)[0].strip()
                if len(candidate) >= 12:
                    translated = candidate
        return self._hit(chosen, best, 'partial-prefix', translated)

    def _continuation(self, query, previous):
        if not previous or len(query) < 19 or len(query.split()) < 4:
            return None
        for index in self.by_key.get(previous, ()):
            row = self.rows[index]
            if (' ' + row.normalized + ' ').find(' ' + query + ' ') <= 1:
                continue
            translated = row.translation
            if row.source.count(',') == 1 and translated.count(',') == 1:
                if query == normalize(row.source.split(',',1)[1]):
                    translated = translated.split(',',1)[1].strip()
            return self._hit(index, 99, 'continuation', translated)
        return None

    def _middle(self, query, previous):
        words = query.split()
        if len(words) < 6 or not 35 <= len(query) <= 350:
            return None
        terms = sorted({w for w in words if len(w) >= 4 and w in self.words}, key=lambda w: len(self.words[w]))
        candidates = set()
        for word in terms[:4]:
            if len(self.words[word]) < 700:
                candidates.update(self.words[word])
        if not candidates or len(candidates) > 800:
            return None
        matches = [i for i in candidates if len(self.rows[i].normalized) > len(query) + 5
                   and len(query) >= len(self.rows[i].normalized) * .30
                   and (' ' + self.rows[i].normalized + ' ').find(' ' + query + ' ') > 1]
        if not matches:
            return None
        if len({self.rows[i].key for i in matches}) > 1:
            same = [i for i in matches if self.rows[i].key == previous]
            if same:
                matches = same
            elif len({self.rows[i].translation.casefold() for i in matches}) > 1:
                return None
        chosen = min(matches, key=lambda i: len(self.rows[i].normalized))
        return self._hit(chosen, 99, 'partial-middle')

    def _body(self, query, previous):
        return (self._direct(query, previous) or self._joined(query, previous)
                or self._prefix(query, previous) or self._continuation(query, previous)
                or self._middle(query, previous))

    def _speaker_body(self, query, previous, allow_fuzzy):
        index = self._choose(self.exact.get(query, ()), previous)
        if index is not None:
            return self._hit(index, 100, 'speaker-filtered')
        if allow_fuzzy and len(query) >= 22 and len(query.split()) >= 4:
            hit = self._direct(query, previous)
            if hit and hit.confidence >= 97:
                return replace(hit, kind='speaker-filtered')
        hit = self._prefix(query, previous)
        if hit:
            return replace(hit, kind='speaker-prefix')
        hit = self._continuation(query, previous) or self._middle(query, previous)
        return replace(hit, kind='speaker-partial') if hit else None

    def match(self, text, previous=None, ignore_speaker=True):
        query = normalize(text)
        hit = self._body(query, previous)
        if hit or not ignore_speaker:
            return hit
        explicit = re.match(r"^\s*[\[(]?([A-Za-z][A-Za-z .'-]{0,45})[\])]?\s*[:：]\s*(.+)$", text.strip(), re.S)
        if explicit:
            body = normalize(explicit.group(2))
            if len(body) >= 3:
                hit = self._speaker_body(body, previous, True)
                if hit:
                    return hit
        tokens = query.split()
        words = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", text)
        if len(tokens) < 3 or len(words) < 3:
            return None
        blocked = {'i','we','you','he','she','they','it','what','where','why','when','who','how',
                   'there','here','this','that','these','those','a','an','the','and','but','if',
                   'because','well','please','look','listen','yes','no'}
        for count in range(1, min(5, len(tokens) - 2)):
            label = words[:count]
            if len(label) != count or label[0].casefold() in blocked:
                continue
            if not all(w[0].isupper() or w.lower() in {'de','van','von','the'} for w in label):
                continue
            if count == 1 and not (label[0].isupper() and len(label[0]) >= 4):
                continue
            body = ' '.join(tokens[count:])
            if len(body) < 3:
                continue
            chosen = self._choose(self.exact.get(body, ()), previous)
            if chosen is not None:
                return self._hit(chosen, 100, 'speaker-filtered')
            if len(body) >= 24 and len(body.split()) >= 4:
                hit = self._speaker_body(body, previous, count >= 2)
                if hit:
                    return hit
        return None
