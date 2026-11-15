"""Bounded subtitle passes, adaptive pale-scene policy and owned scan facts."""
from collections import deque
from dataclasses import dataclass,replace,field
import time
import math
from recognition import Reading,Scan,quad_bounds,recognized_parts,reading_from_parts


def valid_quality(value):
    return isinstance(value,str) and value in ('fast','accurate')


def valid_interval(value,*,minimum=.08):
    try:return type(value) in (int,float) and math.isfinite(value) and 0<value and minimum<=value<=3
    except OverflowError:return False


def pale(frame):
    import cv2
    sample=frame[::4,::4]
    return bool(sample.size) and float(cv2.cvtColor(sample,cv2.COLOR_BGR2GRAY).mean())>=70


def transform(frame,variant):
    import cv2
    if variant=='light':
        plane=frame.min(axis=2)
        kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(15,15))
        strokes=cv2.morphologyEx(plane,cv2.MORPH_TOPHAT,kernel)
        return cv2.cvtColor(cv2.normalize(strokes,None,0,255,cv2.NORM_MINMAX),cv2.COLOR_GRAY2BGR)
    if variant=='contrast':
        lab=cv2.cvtColor(frame,cv2.COLOR_BGR2LAB)
        light,a,b=cv2.split(lab)
        light=cv2.createCLAHE(clipLimit=2.2,tileGridSize=(8,8)).apply(light)
        return cv2.cvtColor(cv2.merge((light,a,b)),cv2.COLOR_LAB2BGR)
    return frame


def choose(first,second,*,light=False):
    if not first.text:return second
    if not second.text:return first
    a,b=first.confidence,second.confidence
    if a is None or b is None:
        # Unknown confidence cannot establish a better or worse known score.
        return first
    if light:
        won=len(second.text)>len(first.text) if abs(a-b)<.01 else b>a
        return second if won else first
    if len(second.text)>=len(first.text)+5 and b>=max(.36,a-.17):return second
    if b>a+.08 and len(second.text)>=len(first.text)*.87:return second
    return first


@dataclass
class _Row:
    bounds: tuple
    members: list=field(default_factory=list)

    def add(self,bounds,part):
        left,top,right,bottom=self.bounds
        self.bounds=(min(left,bounds[0]),min(top,bounds[1]),max(right,bounds[2]),max(bottom,bounds[3]))
        self.members.append((bounds,part))

    def ordered(self):return sorted(self.members,key=lambda member:member[0][0])

    def overlaps(self):
        edge=float('-inf')
        for bounds,_ in self.ordered():
            if bounds[0]<edge:return True
            edge=max(edge,bounds[2])
        return False


def scan(ocr,frame,variant):
    started=time.perf_counter()
    result=ocr(frame,use_det=True,use_rec=True,use_cls=False,return_word_box=False)
    def finish(parts,method):
        reading=reading_from_parts(parts,method,(time.perf_counter()-started)*1000)
        return replace(reading,variant=variant)
    if result.txts is None:return finish([],'subtitle')
    if result.boxes is None:return finish(recognized_parts(result),'subtitle/unboxed')
    if len(result.boxes)>256:
        raise ValueError('OCR kutu kapasitesi aşıldı; alanı daraltın. Metin kesilmedi.')
    parts=recognized_parts(result)
    if len(result.txts)!=len(result.boxes) or len(parts)!=len(result.boxes):
        return finish(parts,'subtitle/unboxed-mismatch')
    boxes=[]
    invalid=False
    for box in result.boxes:
        try:boxes.append(quad_bounds(box))
        except (ValueError,TypeError,OverflowError):invalid=True
    if invalid:
        return finish(parts,'subtitle/unboxed-invalid')
    rows=[]
    for bounds,part in sorted(zip(boxes,parts,strict=True),key=lambda item:(item[0][1]+item[0][3])/2):
        left,top,right,bottom=bounds
        center=(top+bottom)/2
        row=next((r for r in rows if abs(center-(r.bounds[1]+r.bounds[3])/2)<=max(10,.6*max(bottom-top,r.bounds[3]-r.bounds[1]))),None)
        if row is None:
            row=_Row(bounds)
            rows.append(row)
        row.add(bounds,part)
    if len(rows)>8:
        raise ValueError('Altyazı alanında sekizden fazla satır var; alanı daraltın. Metin kesilmedi.')
    parts=[]
    height,width=frame.shape[:2]
    for row in rows:
        if not row.overlaps():
            parts.extend(part for _,part in row.ordered())
            continue
        left,top,right,bottom=row.bounds
        crop=frame[max(0,int(top)-3):min(height,int(bottom)+4),max(0,int(left)-3):min(width,int(right)+4)]
        if crop.size:
            parts.extend(recognized_parts(ocr(crop,use_det=False,use_rec=True,use_cls=False,return_word_box=False)))
    return finish(parts,'subtitle/rows')


class SubtitleReader:
    def __init__(self,quality='fast',clock=time.monotonic):
        if not valid_quality(quality):raise ValueError('OCR kalitesi geçersiz.')
        self.quality=quality
        self.clock=clock
        self.votes=deque(maxlen=8)
        self.blank_retry_at=float('-inf')

    def read(self,source,fit,ocr):
        started=time.perf_counter()
        # Source pixels determine scenery brightness; letterbox padding must
        # not make a pale scene look dark. Resize remains one bounded640x96 fit.
        frame=fit(source)
        if self.quality=='fast':
            import cv2
            _,deviation=cv2.meanStdDev(source)
            if not deviation.any():
                # Exact per-channel uniformity contains no visible glyphs.
                # Unlike a near-blank heuristic, faint nonuniform strokes pass.
                return Reading('',None,'subtitle/uniform',(time.perf_counter()-started)*1000,
                               variant='uniform',scans=())
        is_pale=self.quality=='fast' and pale(source)
        leading_light=is_pale and len(self.votes)>=2 and sum(self.votes)*2>len(self.votes)
        variant='light' if leading_light else 'plain'
        first=scan(ocr,transform(frame,variant),variant)
        attempts=[first]
        retry=self.quality=='accurate'
        if is_pale:
            if first.text:
                retry=first.confidence is None or first.confidence<.97
            else:
                now=self.clock()
                retry=now-self.blank_retry_at>=.3
                if retry:self.blank_retry_at=now
        elif self.quality=='fast' and first.text:
            strong=len(first.text)>=40 and len(first.text.split())>=7 and first.confidence is not None and first.confidence>=.87
            retry=not strong and (first.confidence is None or first.confidence<.62)
        best=first
        if retry:
            variant=('plain' if leading_light else 'light') if is_pale else 'contrast'
            second=scan(ocr,transform(frame,variant),variant)
            attempts.append(second)
            if is_pale:
                plain,light=(second,first) if leading_light else (first,second)
                best=choose(plain,light,light=True)
                if plain.text or light.text:self.votes.append(best is light)
            else:
                best=choose(first,second)
        return replace(best,elapsed_ms=(time.perf_counter()-started)*1000,
                       scans=tuple(Scan(item.variant,item.confidence,item.elapsed_ms) for item in attempts))
