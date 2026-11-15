from PIL import Image,ImageDraw,ImageFont


def fixtures():
    result=[]
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',28)
    label=ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf',23)
    cases=[('plain',None,None,700),('shoulder','RB','white',700),
           ('colored','A','#54a550',700),('wide','L1','white',1280)]
    cases.extend(('face-'+name,name,color,700) for name,color in [('B','#b64940'),('X','#3274b0'),('Y','#ddb42d')])
    cases.extend(('plate-'+name,name,'white',700) for name in ('R1','R2','R3','L2','L3','LB','LT','RT','LS','RS'))
    for name,button,color,width in cases:
        image=Image.new('RGB',(width,130),'#1b2430')
        draw=ImageDraw.Draw(image)
        if button:
            draw.text((20,42),'Hold' if len(button)>1 else 'Press',font=font,fill='white')
            box=(105,43,165,81) if len(button)>1 else (115,43,153,81)
            draw.rounded_rectangle(box,radius=9 if len(button)>1 else 19,fill=color)
            draw.text(((box[0]+box[2])/2,(box[1]+box[3])/2),button,font=label,
                      fill='black' if color=='white' else 'white',anchor='mm')
            draw.text((180,42),'to open the door.' if len(button)>1 else 'to continue.',font=font,fill='white')
        else:
            draw.text((20,42),'Open the door before the guards return.',font=font,fill='white')
        result.append((name,image))
    result.append(('blank',Image.new('RGB',(700,130),'#1b2430')))
    for code in ('SQR','TRI','CIR','CRO','MENU','VIEW'):
        image=Image.new('RGB',(700,130),'#1b2430')
        draw=ImageDraw.Draw(image)
        draw.text((20,42),'Press',font=font,fill='white')
        draw.rounded_rectangle((115,42,157,84),radius=13,fill='white')
        if code=='SQR':
            draw.rectangle((127,54,145,72),outline='black',width=3)
        elif code=='TRI':
            draw.line([(136,52),(124,74),(148,74),(136,52)],fill='black',width=3)
        elif code=='CIR':
            draw.ellipse((126,53,146,73),outline='black',width=3)
        elif code=='CRO':
            draw.line((127,54,145,72),fill='black',width=3)
            draw.line((145,54,127,72),fill='black',width=3)
        elif code=='MENU':
            for y in (54,63,72):
                draw.line((125,y,147,y),fill='black',width=3)
        else:
            draw.rectangle((125,52,140,67),outline='black',width=3)
            draw.rectangle((132,59,147,74),fill='white',outline='black',width=3)
        draw.text((180,42),'to continue.',font=font,fill='white')
        result.append((code,image))
    return result
