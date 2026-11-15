"""Known generated subtitle strips; no desktop/user media is sampled."""
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont


def fixtures():
    text='We need to leave before the guards return.'
    font=ImageFont.truetype(str(Path('C:/Windows/Fonts/arial.ttf')),30)
    result=[]
    def picture(name,background,fill,*,stroke=0,noise=0,caption=text,size=30,opacity=1,gradient=False):
        h,w=80,950
        pixels=np.empty((h,w,3),dtype=np.uint8)
        pixels[:]=background
        if gradient:
            y,x=np.mgrid[:h,:w]
            waves=(18*np.sin(x/35+y/8)+12*np.cos(x/90-y/12))[:,:,None]
            pixels=np.clip(pixels.astype(float)+waves*np.array([1,.6,.3]),0,255).astype(np.uint8)
        if noise:
            rng=np.random.default_rng(517)
            variation=rng.normal(0,noise,(h,w,1))
            pixels=np.clip(pixels.astype(float)+variation,0,255).astype(np.uint8)
        image=Image.fromarray(pixels)
        base=image.copy()
        draw=ImageDraw.Draw(image)
        selected_font=font if size==30 else ImageFont.truetype(str(Path('C:/Windows/Fonts/arial.ttf')),size)
        draw.text((w//2,h//2),caption,font=selected_font,anchor='mm',fill=fill,
                  stroke_width=stroke,stroke_fill=(20,20,20))
        if opacity!=1:image=Image.blend(base,image,opacity)
        result.append((name,image,caption))
    picture('dark-white',(0,0,0),(255,255,255))
    picture('dark-gray',(12,12,12),(95,95,95))
    picture('gray-white',(170,170,170),(245,245,245))
    picture('sand-white',(205,185,135),(245,245,245),noise=6)
    picture('sky-white',(160,205,230),(245,245,245),noise=4)
    picture('snow-white',(220,220,220),(250,250,250),noise=3)
    picture('snow-thin-white',(235,235,235),(246,246,246))
    picture('white-black',(240,240,240),(12,12,12))
    picture('bright-outline',(210,210,200),(250,250,250),stroke=1,noise=10)
    picture('busy-gray',(110,110,110),(235,235,235),noise=35)
    picture('dark-blank',(0,0,0),(255,255,255),caption='')
    picture('pale-blank',(225,225,225),(255,255,255),caption='')
    picture('pale-noise-blank',(225,220,210),(255,255,255),noise=8,caption='')
    picture('small-sand',(205,185,135),(250,250,250),size=18,opacity=.35,gradient=True)
    picture('faint-sky',(160,205,230),(250,250,250),size=22,opacity=.25,gradient=True)
    picture('small-snow',(220,220,220),(250,250,250),size=18,opacity=.3,noise=2)
    picture('small-gray-outline',(190,190,190),(245,245,245),size=18,stroke=1,noise=15,gradient=True)
    picture('faint-dark',(10,10,10),(180,180,180),size=20,opacity=.15,noise=2)
    picture('uneven-blank',(205,185,135),(250,250,250),caption='',gradient=True,noise=3)
    return result
