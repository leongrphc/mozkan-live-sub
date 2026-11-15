"""Locally painted inline controller resources; never load files or URLs."""
from PySide6.QtCore import Qt,QRectF,QLineF
from PySide6.QtGui import QImage,QPainter,QPen,QColor,QFont,QFontMetrics
from hud import BADGES


def badge_image(name,font):
    info=BADGES[name]
    height=max(16,QFontMetrics(font).height())
    width=round(height*(1.6 if info['shape']=='plate' else 1.1))
    image=QImage(width,height,QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter=QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor('#252a31'))
    painter.setPen(QPen(QColor('#a3adb9'),max(1,height*.035)))
    rect=QRectF(1,1,width-2,height-2)
    painter.drawRoundedRect(rect,height*(.17 if info['shape']=='plate' else .45),height*.45)
    painter.setPen(QPen(QColor(info['color']),max(2,height*.07),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
    center=rect.center()
    side=height*.4
    if name=='SQR':
        painter.drawRect(QRectF(center.x()-side/2,center.y()-side/2,side,side))
    elif name=='CIR':
        painter.drawEllipse(QRectF(center.x()-side/2,center.y()-side/2,side,side))
    elif name=='TRI':
        from PySide6.QtGui import QPainterPath
        path=QPainterPath();path.moveTo(center.x(),center.y()-side*.6)
        path.lineTo(center.x()-side*.6,center.y()+side*.5)
        path.lineTo(center.x()+side*.6,center.y()+side*.5);path.closeSubpath()
        painter.setBrush(Qt.NoBrush);painter.drawPath(path)
    elif name=='CRO':
        painter.drawLine(QLineF(center.x()-side/2,center.y()-side/2,center.x()+side/2,center.y()+side/2))
        painter.drawLine(QLineF(center.x()+side/2,center.y()-side/2,center.x()-side/2,center.y()+side/2))
    elif name=='VIEW':
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(center.x()-side*.65,center.y()-side*.65,side,side))
        painter.setBrush(QColor('#252a31'))
        painter.drawRect(QRectF(center.x()-side*.15,center.y()-side*.15,side,side))
    elif name=='MENU':
        for shift in (-.4,0,.4):
            painter.drawLine(QLineF(center.x()-side*.6,center.y()+shift*side,center.x()+side*.6,center.y()+shift*side))
    else:
        label=QFont(font)
        label.setPixelSize(round(height*.53))
        label.setBold(True)
        painter.setFont(label)
        painter.drawText(rect,Qt.AlignCenter,info['label'])
    painter.end()
    return image
