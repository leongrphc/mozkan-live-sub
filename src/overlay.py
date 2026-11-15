"""Bounded subtitle presentation with explicit capture-overlap safety."""
from __future__ import annotations

import math
import re

from PySide6.QtCore import Qt, QRect, QRectF,QUrl
from PySide6.QtGui import (QColor, QFont, QPainter, QPen, QTextBlockFormat,
                          QTextCharFormat, QTextCursor, QTextDocument, QTextOption,
                          QAbstractTextDocumentLayout)
from PySide6.QtWidgets import QApplication, QWidget
from capture_exclusion import try_capture_exclusion
from appearance import validate_style,STYLE_DEFAULTS,DEFAULT_FONT_SIZE,BACKGROUND_RGB
from coordinates import screen_for_region

_UNSET = object()


class _LocalTextDocument(QTextDocument):
    def loadResource(self, kind, url):
        # Rich content consists of escaped text and colored speaker spans.
        # Never let a document cause file or network resource acquisition.
        return None


class Overlay(QWidget):
    alignment=Qt.AlignHCenter
    MAX_TEXT_CHARACTERS = 32768
    MAX_RENDER_PIXELS = 4 * 1024 * 1024

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.Tool | Qt.WindowTransparentForInput |
                            Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        super().setFont(QFont('Segoe UI',DEFAULT_FONT_SIZE,QFont.Bold))
        self._position = STYLE_DEFAULTS['position']
        self._color = QColor(STYLE_DEFAULTS['color'])
        self._opacity = STYLE_DEFAULTS['opacity']
        self._stroke = STYLE_DEFAULTS['stroke']
        self._enabled = STYLE_DEFAULTS['enabled']
        self._y_offset = STYLE_DEFAULTS['y_offset']
        self._document = None
        self._padding = 14
        self._last_text = ''
        self._last_region = None
        self._last_rich = False
        self.last_error = None
        self.capture_excluded = False
        self.actual_position = None
        self.other_capture_regions=()

    def configure(self, *, position=_UNSET, color=_UNSET, opacity=_UNSET,
                  stroke=_UNSET, enabled=_UNSET, y_offset=_UNSET):
        """Apply supplied style fields atomically; reflow only visible text."""
        position = self._position if position is _UNSET else position
        color = self._color.name() if color is _UNSET else color
        opacity = self._opacity if opacity is _UNSET else opacity
        stroke = self._stroke if stroke is _UNSET else stroke
        enabled = self._enabled if enabled is _UNSET else enabled
        y_offset = self._y_offset if y_offset is _UNSET else y_offset
        validate_style(dict(position=position,color=color,opacity=opacity,stroke=stroke,
                            enabled=enabled,y_offset=y_offset))
        visible = self.isVisible()
        self._position, self._color, self._opacity = position, QColor(color), opacity
        self._stroke, self._enabled, self._y_offset = stroke, enabled, y_offset
        if not enabled:
            self.hide()
        elif visible and self._last_region is not None:
            self.present(self._last_text, self._last_region, self._last_rich)

    def setFont(self, font):
        super().setFont(font)
        if self.isVisible() and self._last_region is not None:
            self.present(self._last_text, self._last_region, self._last_rich)

    def _screen_for_region(self, region):
        try:
            return screen_for_region((region.x(),region.y(),region.width(),region.height()),QApplication.screens())
        except ValueError:
            return None

    def _make_document(self, text, width, rich):
        document = _LocalTextDocument()
        document.setDocumentMargin(0)
        document.setDefaultFont(self.font())
        option = QTextOption()
        option.setAlignment(self.alignment)
        option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        document.setDefaultTextOption(option)
        if rich:
            from hud import BADGES
            from badge_image import badge_image
            for name in set(re.findall(r'<img src="badge:([A-Z0-9]+)"',text))&BADGES.keys():
                document.addResource(QTextDocument.ImageResource,QUrl('badge:'+name),badge_image(name,self.font()))
            document.setHtml(f'<div style="color:{self._color.name()};">{text}</div>')
        else:
            document.setPlainText(text)
        cursor = QTextCursor(document)
        cursor.select(QTextCursor.Document)
        block = QTextBlockFormat()
        block.setAlignment(self.alignment)
        cursor.mergeBlockFormat(block)
        character = QTextCharFormat()
        if not rich:
            character.setForeground(self._color)
        # Keep the colored fill intact. Qt's TextOutline replaces glyph fill;
        # stroke is a separate paint selection over this same shaped document.
        cursor.mergeCharFormat(character)
        document.setTextWidth(width)
        return document

    def _prepare_font(self,screen):
        pass

    def _format_text(self,text,rich):
        return text,rich

    def _layout_width(self,area,source):
        if self._position in ('top','bottom'):
            return min(area.width()-24,max(120,area.width()-100))
        return min(area.width()-24,max(520,source.width()+100))

    def _placement(self, area, source, width, height, excluded):
        margin, gap = 12, 12
        centered = max(area.left() + margin,
                       min(source.center().x() - width // 2,
                           area.right() + 1 - margin - width))
        screen_center = area.left() + (area.width() - width) // 2
        positions = {
            'above_region': (centered, source.top() - gap - height),
            'below_region': (centered, source.bottom() + 1 + gap),
            'top': (screen_center, area.top() + 35),
            'bottom': (screen_center, area.bottom() + 1 - height - 60),
        }
        if self._position == 'auto':
            order = ('above_region', 'below_region', 'top', 'bottom')
        elif self._position == 'above_region':
            order = ('above_region',)
        else:
            other = 'bottom' if self._position == 'top' else 'top'
            order = (self._position, 'above_region', 'below_region', other)
        for name in order:
            left, top = positions[name]
            if self._y_offset:
                low=area.top()+8
                high=max(low,area.bottom()+1-height-8)
                top=min(max(top-round(self._y_offset*10),low),high)
            rect = QRect(left, top, width, height)
            if not area.contains(rect):
                continue
            if not excluded and self._intersects_capture(rect,source):
                continue
            return rect, name
        return None, None

    def _intersects_capture(self,rect,source):
        return rect.intersects(source) or any(rect.intersects(other) for other in self.other_capture_regions)

    def _fail(self, message):
        self.hide()
        self.last_error = message
        self.actual_position = None
        return False

    def present(self, text, region, rich=False):
        """Return false when hidden, oversized, or no safe placement exists."""
        self.last_error = None
        if not isinstance(text, str):
            return self._fail('Altyazı metni geçersiz.')
        self._last_text, self._last_rich = text, bool(rich)
        if not text or not self._enabled:
            self.hide()
            self.actual_position = None
            return False
        if len(text) > self.MAX_TEXT_CHARACTERS:
            return self._fail('Altyazı metni görüntüleme sınırını aşıyor.')
        if (not isinstance(region, (tuple, list)) or len(region) != 4 or
                any(type(value) is not int for value in region) or
                region[2] <= 0 or region[3] <= 0):
            return self._fail('Altyazı alanının koordinatları geçersiz.')
        self._last_region = tuple(region)
        source = QRect(*region)
        screen = self._screen_for_region(source)
        if screen is None:
            return self._fail('Altyazı alanı tek bir görünür monitörde olmalı.')
        area = screen.availableGeometry()
        ratio = float(screen.devicePixelRatio())
        if not math.isfinite(ratio) or ratio <= 0:
            return self._fail('Monitörün piksel ölçeği belirlenemedi.')
        maximum_width = area.width() - 24
        if maximum_width < 60:
            return self._fail('Monitörde altyazı için yeterli alan yok.')
        width=self._layout_width(area,source)
        self._prepare_font(screen)
        text,rich=self._format_text(text,rich)
        if len(text)>self.MAX_TEXT_CHARACTERS:
            return self._fail('Biçimlendirilmiş altyazı görüntüleme sınırını aşıyor.')
        self._padding = 12 + self._stroke
        content_width = width - self._padding * 2
        if content_width < 32:
            return self._fail('Altyazı metni için yeterli genişlik yok.')
        document = self._make_document(text, content_width, bool(rich))
        document_height = document.size().height()
        if not math.isfinite(document_height):
            return self._fail('Altyazı boyutu hesaplanamadı.')
        height = max(40, math.ceil(document_height) + self._padding * 2)
        if height > math.floor(area.height() * .42):
            return self._fail('Altyazı bu yazı boyutuyla ekrana sığmıyor.')
        if math.ceil(width * ratio) * math.ceil(height * ratio) > self.MAX_RENDER_PIXELS:
            return self._fail('Altyazı görüntüsü bellek sınırını aşıyor.')
        excluded = try_capture_exclusion(self)
        rect, actual = self._placement(area, source, width, height, excluded)
        if rect is None:
            return self._fail('Altyazı için güvenli yer yok; alanı veya konumu değiştirin.')
        self.capture_excluded = excluded
        self.actual_position = actual
        self._document = document
        self.setGeometry(rect)
        self.show()
        self.update()
        return True

    def paintEvent(self, event):
        if self._document is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._opacity:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(*BACKGROUND_RGB, round(255 * self._opacity / 100)))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
        painter.translate(self._padding, self._padding)
        if self._stroke:
            selection = QAbstractTextDocumentLayout.Selection()
            selection.cursor = QTextCursor(self._document)
            selection.cursor.select(QTextCursor.Document)
            selection.format.setForeground(QColor('#020305'))
            selection.format.setTextOutline(QPen(QColor('#020305'),self._stroke*2,
                                                Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
            context = QAbstractTextDocumentLayout.PaintContext()
            context.selections = [selection]
            self._document.documentLayout().draw(painter,context)
        self._document.drawContents(painter)
        painter.end()


class HudOverlay(Overlay):
    alignment=Qt.AlignLeft

    def __init__(self,parent=None):
        super().__init__(parent)
        from appearance import HUD_LAYOUT_DEFAULTS
        self.hud_layout=dict(HUD_LAYOUT_DEFAULTS)

    def configure_layout(self,**values):
        from appearance import HUD_LAYOUT_RULES
        if set(values)!=set(HUD_LAYOUT_RULES) or any(not HUD_LAYOUT_RULES[key](value) for key,value in values.items()):
            raise ValueError('Görev görünümü ayarları geçersiz.')
        self.hud_layout=dict(values)
        if self.isVisible() and self._last_region:
            self.present(self._last_text,self._last_region)

    def _prepare_font(self,screen):
        font=QFont('Segoe UI',10,QFont.Bold)
        font.setPixelSize(max(13,min(40,round(screen.geometry().height()/1080*19*self.hud_layout['scale']/100))))
        if self.font()!=font:
            QWidget.setFont(self,font)

    def _format_text(self,text,rich):
        from hud import render_html
        return render_html(text,self.fontMetrics().height()),True

    def _layout_width(self,area,source):
        return round(min(max(source.width(),320)*self.hud_layout['scale']/100,area.width()-24))

    def _placement(self,area,source,width,height,excluded):
        left=source.x()+self.hud_layout['x_offset']*10
        top=source.bottom()+1+6-self.hud_layout['y_offset']*10
        if top+height>area.bottom()+1-6 and self.hud_layout['y_offset']==0:
            top=source.top()-6-height
        left=max(area.left()+6,min(left,area.right()+1-width-6))
        top=max(area.top()+6,min(top,area.bottom()+1-height-6))
        rect=QRect(left,top,width,height)
        if not area.contains(rect) or not excluded and self._intersects_capture(rect,source):
            return None,None
        return rect,'hud'
