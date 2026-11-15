"""Logical captions, opt-in stacked OCR interpretation and safe presentation."""
from dataclasses import dataclass
from difflib import SequenceMatcher
import html
import re
import unicodedata

MAX_CAPTION = 8192
_START = re.compile(r"^\s*([A-Za-z][\w.'’ -]{1,32}?)\s*:\s*(.+)$",re.S)
_EXPLICIT = re.compile(r"^\s*([A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇçÜüÖö][\w.'’_-]{0,25}(?:\s+[A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇçÜüÖö][\w.'’_-]{0,25}){0,4})\s*:\s*(\S[\s\S]*)$")
_KNOWN = ('PRICE','GHOST','SOAP','GAZ','FARAH','ALEX','LASWELL','GRAVES','SHEPHERD',
          'MAKAROV','NIKOLAI','ALEJANDRO','RUDY','ROACH','YURI','KATE','KYLE',
          'CAPTAIN PRICE','SGT. GARRICK')
_LABEL = re.compile(r"(?<![\w])(?P<name>[A-Z][A-Z0-9.'’_-]{1,22}(?:\s+[A-Z][A-Z0-9.'’_-]{1,22}){0,3}|(?i:"
                    +'|'.join(re.escape(name).replace(r'\ ',r'\s+') for name in _KNOWN)+r"))\s*:\s*")


def compact(value):
    if not isinstance(value,str):
        raise TypeError('Altyazı metin olmalı.')
    if len(value)>MAX_CAPTION:
        raise ValueError('Altyazı 8192 karakter sınırını aşıyor.')
    return ' '.join(value.replace('\u200b','').split())


def caption_key(value):
    return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',value.casefold().replace('’',"'"))).strip()


@dataclass(frozen=True,slots=True)
class Caption:
    speaker: str = ''
    body: str = ''

    @property
    def full(self):
        return self.speaker+': '+self.body if self.speaker else self.body

    def as_dict(self):
        return dict(speaker=self.speaker,text=self.body)


def parse_caption(value):
    value=compact(value)
    match=_START.fullmatch(value)
    if match and len(match[1].split())<=4:
        return Caption(compact(match[1]),compact(match[2]))
    return Caption('',value)


def split_speaker(value):
    """Only explicit title-case/uppercase labels are speaker display labels."""
    match=_EXPLICIT.fullmatch(value.strip())
    if match:
        name=compact(match[1])
        if 2<=len(name)<=46 and (name.isupper() or all(part[0].isupper() for part in name.split())):
            return name,match[2].strip()
    return '',value


def ensure_speaker(source,translated):
    if not translated or split_speaker(translated)[0]:
        return translated
    speaker,_=split_speaker(source)
    return speaker+': '+translated if speaker else translated


def _additional_suffix(previous,combined):
    if not previous or len(combined)<=len(previous)+1 or not previous.endswith(('.', '!', '?')):
        return ''
    if combined.casefold().startswith(previous.casefold()):
        return combined[len(previous):].lstrip(' .!?:;,-')
    # Find a sentence boundary, preserving the next sentence's first letters.
    boundaries=[match.end() for match in re.finditer(r'[.!?]+(?=\s|$)',combined)
                if abs(match.end()-len(previous))<=3]
    for end in sorted(boundaries,key=lambda end:abs(end-len(previous))):
        if SequenceMatcher(None,caption_key(previous),caption_key(combined[:end])).ratio()>.89:
            return combined[end:].lstrip(' .!?:;,-')
    return ''


def newest_caption(raw,previous_accepted=''):
    raw=compact(raw)
    if not raw:
        return ''
    previous=parse_caption(previous_accepted)
    matches=list(_LABEL.finditer(raw))
    if matches:
        last=matches[-1]
        speaker,body=compact(last['name']),compact(raw[last.end():])
        if not caption_key(body):
            return ''
        if len(matches)==1 and previous.speaker and caption_key(previous.speaker)==caption_key(speaker):
            suffix=_additional_suffix(previous.body,body)
            if caption_key(suffix):
                return Caption(speaker,suffix).full
        return Caption(speaker,body).full
    named=parse_caption(raw)
    if named.speaker:
        return named.full
    suffix=_additional_suffix(previous.body,raw) if previous_accepted else ''
    return Caption(previous.speaker,suffix).full if caption_key(suffix) else raw


class CaptionSelector:
    """Own raw-to-current selection so periodic OCR cannot replay old history."""
    def __init__(self):
        self.raw_key=None
        self.selected=''

    def select(self,raw,previous):
        raw=compact(raw)
        key=caption_key(raw)
        if key!=self.raw_key:
            self.selected=newest_caption(raw,previous)
            self.raw_key=key
        return self.selected


class CaptionStack:
    def __init__(self):
        self.clear()

    def clear(self):
        self.previous=Caption()
        self.current=Caption()

    def add(self,text):
        incoming=parse_caption(text)
        if not incoming.body:
            return False
        if not self.current.body:
            self.current=incoming
            return True
        current,new=caption_key(self.current.full),caption_key(incoming.full)
        same_numbers = re.findall(r'\d+',current)==re.findall(r'\d+',new)
        if current==new or same_numbers and SequenceMatcher(None,current,new).ratio()>=.975:
            return False
        growing=(self.current.speaker==incoming.speaker and current and new.startswith(current)
                 and len(new)<=len(current)+40)
        if not growing:
            self.previous=self.current
        self.current=incoming
        return True

    def as_dict(self,show_previous=True):
        return dict(previous=(self.previous if show_previous else Caption()).as_dict(),current=self.current.as_dict())


def speaker_color(name):
    name=caption_key(name).upper()
    for part,color in (('PRICE','#26E6DC'),('GHOST','#80BEFA'),('SOAP','#FFD580'),('FARAH','#E6A0F5')):
        if part in name:
            return color
    return '#95F0A2' if name in ('GAZ','KYLE','KYLE GARRICK') else '#45D7E2'


def render_caption(caption,*,previous=False,font_size=None):
    prefix=(f'<span style="color:{speaker_color(caption.speaker)}">{html.escape(caption.speaker)}:</span> '
            if caption.speaker else '')
    body=html.escape(caption.body)
    if previous:
        body=f'<span style="color:#E9F8FF">{body}</span>'
    content=prefix+body
    if previous and font_size is not None:
        content=f'<span style="font-size:{max(14,font_size-3)}pt">{content}</span>'
    return content


def render_stack(stack,show_previous=True,font_size=None):
    lines=[]
    if show_previous and stack.previous.body:
        lines.append(render_caption(stack.previous,previous=True,font_size=font_size))
    if stack.current.body:
        lines.append(render_caption(stack.current))
    return '<br>'.join(lines)
