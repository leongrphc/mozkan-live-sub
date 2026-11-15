"""Quest word ordering, visual badge recognition and lossless control markers."""
from collections import Counter
from dataclasses import replace
import html
import re
from recognition import Badge,Word,Reading,readable_caption,recognized_parts,spatial_parts,reading_from_parts
from dialogue import MAX_CAPTION

MARK=re.compile(r'\{\{([A-Z0-9]+)\}\}')
SHOULDERS=frozenset('R1 R2 R3 L1 L2 L3 LB RB LT RT LS RS'.split())
BADGES={name:dict(label=name,color='#ffffff',shape='plate') for name in sorted(SHOULDERS)}
BADGES.update({name:dict(label=name,color=color,shape='round') for name,color in
               (('A','#58d469'),('B','#ef6461'),('X','#7ea6f2'),('Y','#e8d26a'))})
BADGES.update({name:dict(label=glyph,color=color,shape='round') for name,glyph,color in
               (('SQR','□','#e58ac0'),('TRI','△','#3ec7a7'),('CIR','○','#ef6461'),
                ('CRO','✕','#7ea6f2'),('VIEW','⧉','#ffffff'),('MENU','≡','#ffffff'))})
SYMBOLS={'□':'SQR','■':'SQR','△':'TRI','▲':'TRI','○':'CIR','◯':'CIR','×':'CRO','✕':'CRO'}
ALIASES=dict(zip('L8 R8 IB 1B LE RE LI RI LL RL L| R| LZ RZ L7 R7 IT 1T LT1 RT1 K R5 L5 RSS LSS R$ L$ OPTIONS START SELECT BACK SHARE CREATE'.split(),
                 'LB RB LB LB LB RB L1 R1 L1 R1 L1 R1 L2 R2 LT RT LT LT LT RT X RS LS RS LS RS LS MENU MENU VIEW VIEW VIEW VIEW'.split()))
SHAPES={'口':'SQR','□':'SQR','■':'SQR','▢':'SQR','囗':'SQR','Δ':'TRI','△':'TRI','▲':'TRI','∆':'TRI',
        '0':'CIR','O':'CIR','o':'CIR','○':'CIR','〇':'CIR','◯':'CIR','●':'CIR','Q':'CIR','×':'X','✕':'X','x':'X'}


def _overlap(a,b):
    return min(a.x+a.w,b.x+b.w)>max(a.x,b.x) and min(a.y+a.h,b.y+b.h)>max(a.y,b.y)


def compose(words,badges):
    items=[]
    for word in words:
        text=word.text.strip()
        token=text.upper().replace(' ','')
        covered=any(max(0,min(word.x+word.w,b.x+b.w)-max(word.x,b.x))*
                    max(0,min(word.y+word.h/2,b.y+b.h)-max(word.y-word.h/2,b.y))>=.45*word.w*word.h for b in badges)
        if len(token.strip('()[]{}.,!?;:'))<=3 and covered:
            continue
        if token in ('A','B','X','Y') and any(b.name==token and word.x-8<=b.cx<=word.x+word.w+8
                                               and abs(word.y-b.cy)<=word.h/2+8 for b in badges):
            continue
        mark=SYMBOLS.get(token) or (token if token in SHOULDERS else None)
        items.append((word.x,word.y,word.w,word.h,'{{'+mark+'}}' if mark else text,bool(mark)))
    for badge in badges:
        mark='{{'+badge.name+'}}'
        if not any(item[4]==mark and abs(item[0]-badge.cx)<48 and abs(item[1]-badge.cy)<36 for item in items):
            items.append((badge.x,badge.cy,badge.w,badge.h,mark,True))
    rows=[]
    for item in sorted(items,key=lambda value:(value[1],value[0])):
        if rows and abs(item[1]-rows[-1][0][1])<=max(14,item[3]*.7):
            rows[-1].append(item)
        else:
            rows.append([item])
    result=[]
    prose=[]
    for row in rows:
        row.sort(key=lambda value:value[0])
        def number(item):
            return not item[5] and any(c.isdigit() for c in item[4]) and not any(c.isalpha() for c in item[4])
        while len(row)>1 and number(row[0]) and row[1][0]-row[0][0]-row[0][2]>.9*row[0][3]:
            row.pop(0)
        while len(row)>1 and number(row[-1]) and row[-1][0]-row[-2][0]-row[-2][2]>.9*row[-1][3]:
            row.pop()
        if not any(not item[5] and any(c.isalpha() for c in item[4]) for item in row):
            continue
        line=''
        for item in row:
            bit=item[4]
            line+=('' if not line or re.fullmatch(r'[.,!?;:)\]]+',bit) else ' ')+bit
            if not item[5]:
                prose.append(bit)
        result.append(line)
    if sum(len(line) for line in result)+max(0,len(result)-1)>MAX_CAPTION:
        raise ValueError('İşaretli görev metni kapasiteyi aşıyor.')
    return '\n'.join(result) if readable_caption(' '.join(prose)) else ''


def _paragraphs(text):
    paragraphs=[]
    for line in text.splitlines():
        line=line.strip()
        if not line:
            continue
        if paragraphs and not (paragraphs[-1].endswith(('.', '!', '?', ':')) and line[:1].isupper()):
            paragraphs[-1]+=' '+line
        else:
            paragraphs.append(line)
    return [part for paragraph in paragraphs for part in re.split(r'(?<=[.!?])\s+(?=[A-Z{])',paragraph) if part.strip()]


def translate_marked(translate,text):
    result=[]
    for paragraph in _paragraphs(text):
        names=MARK.findall(paragraph)
        if not names:
            value=translate(paragraph) or paragraph
            result.append(MARK.sub(lambda m:m[1] if m[1] in BADGES else m[0],value))
            continue
        translated=translate(MARK.sub(lambda m:'['+m[1]+']',paragraph)) or ''
        if Counter(re.findall(r'\[([A-Z0-9]+)\]',translated))==Counter(names):
            result.append(re.sub(r'\[([A-Z0-9]+)\]',lambda m:'{{'+m[1]+'}}',translated).strip())
            continue
        pieces=[]
        for index,part in enumerate(MARK.split(paragraph)):
            part=part.strip()
            if not part:
                continue
            if index%2:
                pieces.append('{{'+part+'}}')
            elif re.fullmatch(r'[.,!?;:]+',part):
                pieces.append(part)
            else:
                match=re.fullmatch(r'(.*?)([.,!?;:]+)',part)
                body,tail=(match[1].strip(),match[2]) if match and match[1].strip() else (part,'')
                value=translate(body) or body
                # A failed placeholder attempt must not invent extra badges
                # while translating the surrounding plain pieces. Preserve
                # genuine literal brackets already present in that source.
                value=MARK.sub(lambda m:m[1] if m[1] in BADGES else m[0],value)
                literal=Counter(re.findall(r'\[([A-Z0-9]+)\]',body))
                def keep(match):
                    if match[1] not in names:
                        return match[0]
                    if literal[match[1]]:
                        literal[match[1]]-=1
                        return match[0]
                    return ''
                value=re.sub(r'\[([A-Z0-9]+)\]',keep,value)
                pieces.append(value.strip()+tail)
        built=''
        for part in pieces:
            built+=('' if not built or part[:1] in '.,!?;:' else ' ')+part
        result.append(built)
    return '\n'.join(part.strip() for part in result if part.strip())


def render_html(text,size):
    result=[]
    last=0
    for mark in MARK.finditer(text):
        result.append(html.escape(text[last:mark.start()]).replace('\n','<br>'))
        name=mark[1]
        if name in BADGES:
            height=max(16,round(size))
            width=round(height*(1.6 if BADGES[name]['shape']=='plate' else 1.1))
            result.append(f'<img src="badge:{name}" width="{width}" height="{height}">')
        else:
            result.append(html.escape(mark[0]))
        last=mark.end()
    result.append(html.escape(text[last:]).replace('\n','<br>'))
    return ''.join(result)


def display_text(text):
    return MARK.sub(lambda mark:BADGES[mark[1]]['label'] if mark[1] in BADGES else mark[0],text)


def _shape(ink):
    import cv2
    import numpy as np
    ys,xs=np.nonzero(ink)
    if len(xs)<6:
        return ''
    crop=ink[ys.min():ys.max()+1,xs.min():xs.max()+1]
    h,w=crop.shape
    if not .6<=w/max(1,h)<=1.7 or crop.mean()>=.7:
        return ''
    cy,cx=h//2,w//2
    if .75<=w/h<=1.33 and not crop[max(0,cy-h//7):cy+h//7+1,max(0,cx-w//7):cx+w//7+1].any():
        contours,_=cv2.findContours(crop.astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        contour=max(contours,key=cv2.contourArea)
        if len(cv2.approxPolyDP(contour,.03*cv2.arcLength(contour,True),True))>=6:
            return 'CIR'
    size=32
    glyph=cv2.resize(crop.astype('uint8'),(size,size),interpolation=cv2.INTER_NEAREST)>0
    templates={}
    for name in ('SQR','TRI','X','MENU','VIEW'):
        canvas=np.zeros((size,size),np.uint8)
        if name=='SQR':
            cv2.rectangle(canvas,(4,4),(28,28),255,3)
        elif name=='TRI':
            cv2.polylines(canvas,[np.array([[16,3],[3,28],[28,28]],np.int32)],True,255,3)
        elif name=='X':
            cv2.line(canvas,(4,4),(28,28),255,4);cv2.line(canvas,(28,4),(4,28),255,4)
        elif name=='MENU':
            for y in (7,16,25):
                cv2.line(canvas,(4,y),(28,y),255,4)
        else:
            cv2.rectangle(canvas,(3,3),(20,20),255,3)
            cv2.rectangle(canvas,(12,12),(29,29),255,-1)
            cv2.rectangle(canvas,(16,16),(25,25),0,-1)
        templates[name]=canvas>0
    kernel=np.ones((5,5),np.uint8)
    near=cv2.dilate(glyph.astype('uint8'),kernel)>0
    scores=[]
    for name,template in templates.items():
        ty,tx=np.nonzero(template)
        template=cv2.resize(template[ty.min():ty.max()+1,tx.min():tx.max()+1].astype('uint8'),
                            (size,size),interpolation=cv2.INTER_NEAREST)>0
        tolerant=cv2.dilate(template.astype('uint8'),kernel)>0
        score=float((glyph&tolerant).sum())/max(1,glyph.sum())*float((template&near).sum())/max(1,template.sum())
        scores.append((score,name))
    scores.sort(reverse=True)
    return scores[0][1] if scores[0][0]>=.62 and scores[0][0]-scores[1][0]>=.08 else ''


def find_badges(frame,words,recognize):
    """Bounded plate detection, then REC-only label decoding; no DET per plate."""
    import cv2
    import numpy as np
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    heights=sorted(word.h for word in words if word.h>4)
    line_h=heights[len(heights)//2] if heights else max(10,frame.shape[0]*.1)
    candidates=[]
    for mask in (cv2.inRange(hsv,(0,110,90),(180,255,255)),cv2.threshold(gray,165,255,cv2.THRESH_BINARY)[1]):
        contours,hierarchy=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            continue
        for index,contour in enumerate(contours):
            if hierarchy[0][index][3]!=-1:
                continue
            x,y,w,h=cv2.boundingRect(contour)
            if h<max(7,line_h*.36) or h>max(line_h*2,14) or not .6<=w/h<=3.6 or w*h<60:
                continue
            badge=Badge('',x,y,w,h)
            if any(_overlap(badge,existing[0]) for existing in candidates):
                continue
            inside=np.zeros((h,w),np.uint8)
            cv2.drawContours(inside,[contour],-1,255,-1,offset=(-x,-y))
            filled=(inside>0).sum()/(w*h)
            if filled<.7:
                if filled<.38:
                    continue
                inside[:]=0
                cv2.drawContours(inside,[cv2.convexHull(contour)],-1,255,-1,offset=(-x,-y))
                if (inside>0).mean()<.82:
                    continue
            plate=(mask[y:y+h,x:x+w]>0)&(inside>0)
            ink=(cv2.erode(inside,np.ones((3,3),np.uint8))>0)&~plate
            if not .07<=ink.sum()/max(1,(inside>0).sum())<=.6:
                continue
            ys,xs=np.nonzero(ink)
            if not len(xs) or xs.max()-xs.min()+1<w*.28 or ys.max()-ys.min()+1<h*.35:
                continue
            host=next((word for word in words if word.x<=badge.cx<=word.x+word.w and abs(word.y-badge.cy)<=word.h/2),None)
            if host:
                token=re.sub(r'[^A-Za-z0-9]','',host.text).upper()
                token=ALIASES.get(token,token)
                if len(token)>=2 and token not in BADGES or w<h*.85:
                    continue
            symbol_host=host is not None and not any(char.isascii() and char.isalpha() for char in host.text)
            candidates.append((badge,gray[y:y+h,x:x+w],inside>0,plate,ink,host is None or symbol_host))
    result=[]
    for badge,crop,inside,plate,ink,gap in sorted(candidates,key=lambda c:(not c[-1],c[0].y,c[0].x))[:10]:
        if not ink.any() or not plate.any():
            continue
        span=float(np.median(crop[plate]))-float(np.median(crop[ink]))
        if abs(span)<25:
            continue
        norm=np.clip((crop.astype('float32')-float(np.median(crop[ink])))*255/span,0,255)
        norm[~inside]=255
        ys,xs=np.nonzero(ink)
        label=norm[max(0,ys.min()-1):ys.max()+2,max(0,xs.min()-1):xs.max()+2].astype('uint8')
        scale=40/label.shape[0]
        label=cv2.resize(label,(max(8,round(label.shape[1]*scale)),40),interpolation=cv2.INTER_CUBIC)
        label=cv2.copyMakeBorder(label,14,14,24,24,cv2.BORDER_CONSTANT,value=255)
        raw,score=recognize(cv2.cvtColor(label,cv2.COLOR_GRAY2BGR))
        name=''
        method='label-ocr'
        label_text=raw
        if score is not None and score>=.45:
            raw=raw.strip()
            if raw in SHAPES:
                name=SHAPES[raw]
                if name=='CIR' and _shape(ink)!='CIR' and _shape(plate)!='CIR':
                    name=''
            else:
                token=re.sub(r'[^A-Za-z0-9|$]','',raw).upper()
                token=ALIASES.get(token,token)
                name=token if token in BADGES else ''
        if not name and gap:
            name=_shape(ink)
            method='shape-template'
        if name:
            result.append(replace(badge,name=name,method=method,label=label_text,
                                  confidence=score if method=='label-ocr' else None))
    return tuple(sorted(result,key=lambda badge:(badge.cy,badge.cx)))


def read_hud(ocr,frame,elapsed):
    import cv2
    height,width=frame.shape[:2]
    scale=min(1,960/max(width,height))
    fitted=(cv2.resize(frame,(max(1,round(width*scale)),max(1,round(height*scale))),interpolation=cv2.INTER_AREA)
            if scale<1 else frame)
    fh,fw=fitted.shape[:2]
    output=ocr(fitted,use_det=True,use_cls=False,use_rec=True,return_word_box=True)
    if getattr(output,'txts',None) is not None and len(output.txts)>256:
        raise ValueError('HUD OCR satır kapasitesi aşıldı.')
    words=spatial_parts(output,fw,fh)
    def label(image):
        parts=recognized_parts(ocr(image,use_det=False,use_cls=False,use_rec=True,return_word_box=False))
        return parts[0] if parts else ('',None)
    detailed=bool(words) and all(word.level=='word' for word in words)
    badges=find_badges(fitted,words,label) if detailed else ()
    text=compose(words,badges) if detailed else ' '.join(text for text,_ in recognized_parts(output))
    base=reading_from_parts([(word.text,word.confidence) for word in words] if words else recognized_parts(output),
                             'hud/words' if detailed else 'hud/line-fallback',elapsed(),subtitle=False)
    sx,sy=width/fw,height/fh
    return Reading(text,base.confidence,base.method,elapsed(),
                   tuple(replace(word,x=word.x*sx,y=word.y*sy,w=word.w*sx,h=word.h*sy) for word in words),
                   tuple(replace(badge,x=badge.x*sx,y=badge.y*sy,w=badge.w*sx,h=badge.h*sy) for badge in badges))
