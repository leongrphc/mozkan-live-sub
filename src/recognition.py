"""Owned OCR facts and whole-caption validation; never remove individual words."""
from dataclasses import dataclass
import math
import re
from numbers import Real


def parse_confidence(raw):
    if isinstance(raw,bool) or not isinstance(raw,Real):return None
    try:
        value=float(raw)
        return value if math.isfinite(value) and 0<=value<=1 else None
    except (ValueError,TypeError,OverflowError):return None


@dataclass(frozen=True,slots=True)
class Word:
    text: str
    x: float
    y: float
    w: float
    h: float
    confidence: float | None = None
    level: str = 'word'


@dataclass(frozen=True,slots=True)
class Badge:
    name: str
    x: float
    y: float
    w: float
    h: float
    method: str = 'unknown'
    confidence: float | None = None
    label: str | None = None

    @property
    def cx(self):
        return self.x+self.w/2

    @property
    def cy(self):
        return self.y+self.h/2


@dataclass(frozen=True, slots=True)
class Scan:
    variant: str
    confidence: float | None
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class Reading:
    text: str
    confidence: float | None
    method: str
    elapsed_ms: float
    words: tuple[Word,...] = ()
    badges: tuple[Badge,...] = ()
    variant: str | None = None
    scans: tuple[Scan,...] | None = None


def quad_bounds(box):
    import numpy as np
    if isinstance(box,np.ndarray):
        if box.shape!=(4,2):
            raise ValueError('OCR kutusu dört noktadan oluşmalı.')
    elif (not isinstance(box,(tuple,list)) or len(box)!=4
          or any(not isinstance(point,(tuple,list)) or len(point)!=2 for point in box)):
        raise ValueError('OCR kutusu dört noktadan oluşmalı.')
    points=np.asarray(box,dtype=float)
    if not np.isfinite(points).all():
        raise ValueError('OCR kutusu sonlu olmalı.')
    left,top=points.min(axis=0)
    right,bottom=points.max(axis=0)
    if left>=right or top>=bottom:
        raise ValueError('OCR kutusu pozitif olmalı.')
    return float(left),float(top),float(right),float(bottom)


def spatial_parts(output,width,height):
    """Parse word boxes once; malformed word coverage falls back to line facts."""
    def parse(text,score,box,level):
        if not isinstance(text,str) or not text.strip():
            raise ValueError('OCR sözcüğü boş.')
        if len(text)>8192:
            raise ValueError('OCR sözcüğü fazla uzun.')
        left,top,right,bottom=quad_bounds(box)
        if not (0<=left<right<=width+1 and 0<=top<bottom<=height+1):
            raise ValueError('OCR kutusu görüntü dışında.')
        score=parse_confidence(score)
        return Word(' '.join(text.split()),float(left),float((top+bottom)/2),
                    float(right-left),float(bottom-top),score,level)
    lines=getattr(output,'word_results',None)
    if lines is not None:
        words=[]
        characters=0
        try:
            if len(lines)>256:
                raise ValueError('OCR kutu kapasitesi aşıldı.')
            for line in lines:
                if not isinstance(line,(tuple,list)) or len(line)+len(words)>256:
                    raise ValueError('OCR sözcük kapsaması geçersiz.')
                for item in line:
                    word=parse(item[0],item[1],item[2],'word')
                    characters+=len(word.text)
                    if characters>8192:
                        raise ValueError('OCR sözcük kapasitesi aşıldı.')
                    words.append(word)
            if words:
                return tuple(sorted(words,key=lambda word:(word.y,word.x)))
        except (TypeError,ValueError,IndexError,KeyError,OverflowError):
            pass
    texts=getattr(output,'txts',None)
    boxes=getattr(output,'boxes',None)
    scores=getattr(output,'scores',None)
    if texts is None or boxes is None or len(texts)!=len(boxes) or len(texts)>256:
        return ()
    try:
        result=[parse(text,scores[i] if scores is not None and i<len(scores) else None,boxes[i],'line')
                for i,text in enumerate(texts)]
    except (TypeError,ValueError,IndexError,OverflowError):
        return ()
    return tuple(sorted(result,key=lambda word:(word.y,word.x)))


def recognized_parts(output):
    texts = getattr(output, 'txts', None)
    scores = getattr(output, 'scores', None)
    if texts is None:
        return []
    parts = []
    for index, raw in enumerate(texts):
        if not isinstance(raw, str):
            continue
        text = ' '.join(raw.split())
        if not text:
            continue
        score = None
        try:
            score=parse_confidence(scores[index])
        except (TypeError, ValueError, IndexError, OverflowError):
            pass
        parts.append((text, score))
    return parts


def reading_from_parts(parts, method, elapsed_ms, subtitle=True):
    if sum(len(text) for text,_ in parts)+max(0,len(parts)-1)>8192:
        raise ValueError('OCR metni 8192 karakter sınırını aşıyor.')
    text = ' '.join(text for text, _ in parts)
    known = bool(parts) and all(score is not None for _,score in parts)
    confidence = (sum(len(text)*score for text,score in parts)/sum(len(text) for text,_ in parts)
                  if known else None)
    if subtitle and text and (not readable_caption(text) or confidence is not None and confidence < .27):
        return Reading('', confidence, method + '/noise', elapsed_ms)
    return Reading(text,confidence,method,elapsed_ms)


_WORDS = frozenset('''a i am an as at be by do go he hi if in is it me my no of oh ok on or so to up us we
ah all and are but can for get god got her hey him his how its let man not now one our
out run say see she sir the too two was who why yes you back been come dead door down
fire first from give gold have help here hold into just keep kill know left like look
make move need open over press right some stay stop take than that them then they this
time wait want were what when where which will with your about after again before could
cross guards leave other return should their there these those under until world would
brother soldier weapon mission quest enemy attack defend follow inside outside nothing
someone something another already always around because between through without
sorry please thanks thank hello yeah okay bye friend guys check coming going'''.split())
_SHORT = frozenset('ok no yes go wait help stop look run hey'.split())
_VOWELS = frozenset('aeıioöuüy')
_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇçÜüÖö']+")


def _plausible(word):
    letters = ''.join(c for c in word if c.isalpha())
    low = letters.casefold()
    if low in _WORDS:
        return True
    if len(letters)<4 or not (letters.isupper() or letters.islower() or letters.istitle()):
        return False
    if letters.isupper() and len(letters)<=5 or not any(c in _VOWELS for c in low):
        return False
    return not re.search(r'[^aeıioöuüy]{4}',low)


def readable_caption(text):
    words = _WORD.findall(text)
    if not words:
        return bool(re.search(r'\d',text))
    plausible = [word for word in words if _plausible(word)]
    if len(plausible)>=2:
        return True
    if not plausible:
        return False
    letters = ''.join(c for c in plausible[0] if c.isalpha())
    return (letters.casefold() in _SHORT or letters.casefold() in _WORDS and len(letters)>=4
            or len(letters)>=6 and not letters.isupper())
