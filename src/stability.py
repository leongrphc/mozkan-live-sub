"""Bounded OCR voting over independent observations, including blank expiry."""
from collections import deque
from difflib import SequenceMatcher
import math
import re


def text_key(text):
    pieces=re.split(r'(\{\{[A-Z0-9]+\}\})',text)
    keys=[]
    for index,piece in enumerate(pieces):
        if index%2:
            keys.append('⟦'+piece[2:-2].casefold()+'⟧')
        else:
            key=re.sub(r'[^\w]+',' ',piece.casefold().replace('’',"'").replace('‘',"'")).strip()
            if key:
                keys.append(key)
    return ' '.join(keys)


def _semantic(key):
    return re.findall(r'\d+',key),re.findall(r'⟦([a-z0-9]+)⟧',key)


def _similar(left,right):
    return SequenceMatcher(None,left.casefold(),right.casefold(),autojunk=False).ratio()


def vote(group):
    closeness = [sum(_similar(entry[0],other[0]) for other in group) for entry in group]
    base_at = max(range(len(group)),key=lambda i:(round(closeness[i],3),group[i][2]))
    base = group[base_at][1].split()
    keys = [text_key(word) for word in base]
    slots = [{key:[1,word]} for key,word in zip(keys,base)]
    for at,(_,text,_) in enumerate(group):
        if at==base_at:
            continue
        words = text.split()
        other_keys = [text_key(word) for word in words]
        for tag,i1,i2,j1,j2 in SequenceMatcher(None,keys,other_keys,autojunk=False).get_opcodes():
            if tag not in ('equal','replace') or i2-i1!=j2-j1:
                continue
            for offset in range(i2-i1):
                item = slots[i1+offset].setdefault(other_keys[j1+offset],[0,words[j1+offset]])
                item[0]+=1
    result=[]
    for key,word,slot in zip(keys,base,slots):
        winner = max(slot,key=lambda candidate:(slot[candidate][0],candidate==key))
        spelling = slot[winner][1]
        punctuation = re.search(r'[.,!?;:…]+$',word)
        if punctuation and not re.search(r'[.,!?;:…]+$',spelling):
            spelling += punctuation[0]
        result.append(spelling)
    return ' '.join(result)


class StableText:
    def __init__(self,required=2,blank_timeout=2.0):
        self.required = required
        self.blank_timeout = blank_timeout
        self.accepted = ''
        self.last_seen = 0.0
        self.recent = deque(maxlen=6)
        self.pending = False

    def key(self,text):
        return text_key(text)

    def observe(self,text,now,confidence=1.0,*,fresh=True):
        text = ' '.join(text.split())
        if len(text)>8192:
            raise ValueError('Altyazı kararlılık sınırını aşıyor.')
        if not text:
            self.pending = False
            if fresh:
                self.recent.clear()
            if self.accepted and now-self.last_seen>=self.blank_timeout:
                self.accepted = ''
                self.recent.clear()
                return ''
            return None
        self.last_seen = now
        if not fresh:
            return None
        score = confidence if confidence is not None and math.isfinite(confidence) else 0.0
        key = self.key(text)
        self.recent.append((key,text,score))
        current = self.key(self.accepted)
        if key==current:
            self.pending = False
            return None
        self.pending = True
        need = max(self.required,3 if score<.7 else 2)
        # Similar OCR typos require stronger evidence than a new sentence.
        # A changing score/number is meaningful even when the rest is identical.
        similar = (bool(current) and _similar(current,key)>=.86
                   and _semantic(current)==_semantic(key))
        if similar:
            count = sum(entry[0]==key for entry in self.recent)
            shown = sum(entry[0]==current for entry in self.recent)
            if count<need+1 or count<=shown:
                return None
            accepted = text
        else:
            group = [entry for entry in self.recent
                     if entry[0]==key or (_similar(entry[0],key)>=.86
                         and _semantic(entry[0])==_semantic(key))]
            sure = sum(entry[0]==key and entry[2]>=.97 for entry in group)
            if len(group)<need and not (need>2 and sure>=2):
                return None
            accepted = vote(group)
        self.accepted = accepted
        self.pending = False
        accepted_key = self.key(accepted)
        self.recent = deque((entry for entry in self.recent if entry[0]==accepted_key),maxlen=6)
        return accepted
