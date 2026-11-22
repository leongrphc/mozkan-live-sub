"""Native presentation only. Window owns capture, settings and profile identity."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import html

from PySide6.QtCore import Qt, Signal, QEvent,QRectF,QPointF,QSize,QPropertyAnimation,QEasingCurve
from PySide6.QtGui import QPainter,QColor,QPixmap,QLinearGradient,QPen,QFont,QPainterPath,QFontMetricsF,QImageReader
from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QStackedWidget, QScrollArea, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView,QProgressBar,QBoxLayout,QLayout,QSizePolicy,
    QStyledItemDelegate,QStyle,QListView,QGraphicsOpacityEffect)
from presentation import NavigationSound,ResponsiveRow


_BUNDLED_GAMES={
    'mafia.svgame.sqlite':('Mafia','mafia','Diyalog'),
    'blackflag.svgame.sqlite':('Black Flag','blackflag','Resynced'),
    'mw4.svgame.sqlite':('Modern Warfare 4','mw4','Diyalog'),
    'rdr1.svgame.sqlite':('Red Dead Redemption','rdr1','Diyalog'),
    'rdr2.svgame.sqlite':('Red Dead Redemption 2','rdr2','Diyalog'),
}
_COVER_ORDER={value[1]:i for i,value in enumerate(_BUNDLED_GAMES.values())}


@dataclass(frozen=True)
class GameChoice:
    identity: str
    title: str
    available: bool
    error: str | None = None
    cover_key:str|None=None
    subtitle:str='Yerel profil'

    @classmethod
    def from_entry(cls,entry):
        known=_BUNDLED_GAMES.get(entry.path.name) if entry.kind=='bundled' else None
        return cls(entry.identity,known[0] if known else entry.title,entry.available,entry.error,
                   known[1] if known else None,known[2] if known else 'Yerel profil')

    @property
    def sort_key(self):return _COVER_ORDER.get(self.cover_key,len(_COVER_ORDER)),self.title.casefold(),self.identity

    @property
    def tooltip(self):return '<span>'+html.escape(self.error or self.title)+'</span>'


@dataclass(frozen=True)
class ConsoleState:
    context: str
    phase: str
    prompt: str
    can_change_source: bool
    can_navigate: bool
    preparing:bool=False
    running:bool=False


STYLE = '''
QMainWindow, QWidget#console, QDialog {background:#050813;color:#e5efff;}
QToolTip {background:#192b48;color:#e5efff;border:1px solid #597fb6;padding:6px;}
QWidget#workspace {background:#101b30;color:#e5efff;}
QWidget#choicePage {background:#050813;color:#e5efff;}
QLabel {color:#e5efff;background:transparent;}
QLabel#brand {font-size:18px;font-weight:600;letter-spacing:1px;}
QLabel#eyebrow {color:#91a7ca;font-size:12px;}
QLabel#heading {font-size:34px;font-weight:600;}
QLabel#context {font-size:20px;font-weight:600;}
QLabel#phase {color:#91a7ca;}
QLabel#prompt {background:#101b30;border:1px solid #243451;border-radius:16px;font-size:27px;padding:30px;}
QPushButton {background:#192b48;color:#e5efff;border:1px solid #304665;border-radius:9px;padding:10px 14px;font-weight:600;}
QPushButton:hover {background:#23406a;border-color:#597fb6;}
QPushButton:focus, QLineEdit:focus, QListWidget:focus {border:2px solid #80aaff;}
QPushButton:disabled {color:#758299;background:#111c2d;border-color:#263044;}
QPushButton#primary {background:#0047ff;border-color:#396fff;color:white;}
QPushButton#primary:hover {background:#225fff;}
QPushButton#primary:disabled {background:#111c2d;border-color:#263044;color:#758299;}
QPushButton#choice {text-align:left;padding:22px;font-size:20px;background:#101b30;}
QPushButton#quiet {background:transparent;border-color:transparent;color:#91a7ca;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox {background:#101b30;color:#e5efff;border:1px solid #304665;border-radius:6px;padding:6px;}
QComboBox QAbstractItemView {background:#192b48;color:#e5efff;selection-background-color:#0047ff;}
QCheckBox {color:#e5efff;spacing:7px;}
QCheckBox:disabled {color:#758299;}
QPlainTextEdit {background:#101b30;color:#e5efff;border:1px solid #243451;border-radius:12px;padding:20px;font-size:24px;}
QPlainTextEdit#source {font-size:15px;color:#91a7ca;padding:12px;}
QPlainTextEdit#caption,QLabel#prompt {background:transparent;}
QListWidget {background:#101b30;color:#e5efff;border:1px solid #243451;border-radius:12px;padding:8px;font-size:17px;}
QListWidget::item {padding:16px;border-bottom:1px solid #243451;}
QListWidget::item:selected {background:#193b7b;color:#e5efff;}
QScrollArea {background:transparent;border:0;}
QScrollBar:vertical {background:#101b30;width:12px;}
QScrollBar::handle:vertical {background:#304665;min-height:24px;border-radius:5px;}
QTabWidget::pane {border:1px solid #243451;border-radius:9px;}
QTabBar::tab {background:#101b30;color:#91a7ca;padding:12px 18px;}
QTabBar::tab:selected {background:#192b48;color:#e5efff;border-bottom:2px solid #80aaff;}
QTabBar::tab:focus {border:2px solid #80aaff;}
QLabel#connectionCode {font-family:Consolas;font-size:32px;font-weight:600;color:#a6c8ff;padding:12px;}
QLabel#connectionState {font-size:20px;font-weight:600;padding:12px;background:#192b48;border-radius:9px;}
'''


def label(text, name=None):
    result = QLabel(text)
    result.setTextFormat(Qt.PlainText)
    result.setWordWrap(True)
    if name:
        result.setObjectName(name)
    return result


class WorkCanvas(QStackedWidget):
    def __init__(self):
        super().__init__()
        self._preview=QPixmap()

    def set_preview(self,image=None):
        self._preview=(QPixmap.fromImage(image.scaled(960,260,Qt.KeepAspectRatio,Qt.SmoothTransformation))
                       if image is not None else QPixmap())
        self.update()

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.fillRect(self.rect(),QColor('#101b30'))
        if not self._preview.isNull():
            area=self.rect().adjusted(12,12,-12,-12)
            size=self._preview.size().scaled(area.size(),Qt.KeepAspectRatio)
            target=area.adjusted(0,0,0,0)
            target.setSize(size);target.moveCenter(area.center())
            painter.drawPixmap(target,self._preview,self._preview.rect())
            painter.fillRect(self.rect(),QColor(5,8,19,110))
        painter.end()


class ChoiceCard(QPushButton):
    """A painted choice retains native button focus, activation and accessibility."""
    def __init__(self,title,description,glyph):
        super().__init__(title+'\n'+description)
        self.glyph=glyph
        self.setMinimumSize(220,160)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.setMouseTracking(True)

    def sizeHint(self):return QSize(400,340)
    def minimumSizeHint(self):return QSize(220,160)

    def enterEvent(self,event):super().enterEvent(event);self.update()
    def leaveEvent(self,event):super().leaveEvent(event);self.update()
    def focusInEvent(self,event):super().focusInEvent(event);self.update()
    def focusOutEvent(self,event):super().focusOutEvent(event);self.update()

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():painter.setOpacity(.48)
        selected=self.hasFocus() or self.underMouse()
        rect=QRectF(self.rect()).adjusted(7,7,-7,-7)
        fill=QLinearGradient(rect.topLeft(),rect.bottomRight())
        fill.setColorAt(0,QColor('#214b94' if selected else '#1b2a46'))
        fill.setColorAt(1,QColor('#091c43' if selected else '#0a1225'))
        painter.setBrush(fill)
        painter.setPen(QPen(QColor('#81abff' if selected else '#304465'),1.5))
        painter.drawRoundedRect(rect,27,27)
        if self.hasFocus():
            painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor('#a6c8ff'),2))
            painter.drawRoundedRect(rect.adjusted(-5,-5,5,5),32,32)
        compact=self.height()<250
        title,description=self.text().rsplit('\n',1)
        painter.save()
        painter.translate(32 if compact else 42,30 if compact else 48)
        scale=.46 if compact else .9
        painter.scale(scale,scale)
        painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor('#d6e6ff' if selected else '#96afd6'),5,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
        if self.glyph=='games':
            path=QPainterPath(QPointF(20,30));path.cubicTo(26,10,94,10,100,30)
            path.lineTo(115,78);path.cubicTo(117,89,108,93,99,84)
            path.lineTo(82,68);path.lineTo(39,68);path.lineTo(22,84)
            path.cubicTo(13,93,4,89,6,78);path.closeSubpath();painter.drawPath(path)
            painter.drawLine(27,37,48,37);painter.drawLine(37,27,37,48)
            painter.drawEllipse(QPointF(84,34),2,2);painter.drawEllipse(QPointF(98,46),2,2)
        elif self.glyph=='movie':
            painter.drawRoundedRect(QRectF(5,10,110,72),9,9)
            path=QPainterPath(QPointF(49,28));path.lineTo(76,46);path.lineTo(49,64);path.closeSubpath();painter.drawPath(path)
        elif self.glyph=='dialogue':
            painter.drawRoundedRect(QRectF(2,4,82,45),9,9)
            painter.drawRoundedRect(QRectF(38,40,80,45),9,9)
            painter.drawLine(18,65,18,49);painter.drawLine(101,85,101,96)
        else:
            painter.drawLine(8,30,8,8);painter.drawLine(8,8,30,8)
            painter.drawLine(110,58,110,80);painter.drawLine(110,80,88,80)
            painter.drawLine(30,29,89,29);painter.drawLine(25,66,91,66)
            if self.glyph=='live':
                painter.drawLine(51,41,60,49);painter.drawLine(60,49,51,57)
        painter.restore()
        font=QFont('Segoe UI');font.setPixelSize(27 if compact else 43);font.setWeight(QFont.DemiBold)
        text_x=102 if compact else 40
        display_title=title.replace('\n',' ') if compact else title
        text_width=self.width()-text_x-55
        if compact:
            while font.pixelSize()>20 and QFontMetricsF(font).horizontalAdvance(display_title)>text_width:
                font.setPixelSize(font.pixelSize()-1)
        painter.setFont(font);painter.setPen(QColor('#f1f5ff'))
        compact_offset=max(0,(self.height()-120)/2)
        title_rect=QRectF(text_x,24+compact_offset if compact else self.height()-172,text_width,38 if compact else 114)
        painter.drawText(title_rect,Qt.AlignLeft|Qt.AlignVCenter,display_title)
        font.setPixelSize(13 if compact else 14);font.setWeight(QFont.Normal);painter.setFont(font)
        painter.setPen(QColor('#a6bbda'))
        painter.drawText(QRectF(text_x,72+compact_offset if compact else self.height()-49,text_width,32),Qt.AlignLeft|Qt.TextWordWrap,description)
        font.setPixelSize(23);painter.setFont(font)
        painter.drawText(QRectF(self.width()-53,self.height()-61,28,35),Qt.AlignCenter,'→')
        painter.end()


class ChoicePair(QWidget):
    def __init__(self,*buttons):
        super().__init__()
        self.buttons=buttons
        self._wide=None
        self.row=QBoxLayout(QBoxLayout.TopToBottom,self)
        self.row.setContentsMargins(0,0,0,0);self.row.setSpacing(22)
        for button in buttons:self.row.addWidget(button,1)

    def sizeHint(self):return QSize(900,370)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        wide=self.width()>=760
        if wide!=self._wide:
            self._wide=wide
            self.row.setDirection(QBoxLayout.LeftToRight if wide else QBoxLayout.TopToBottom)
            for button in self.buttons:button.setMinimumHeight(280 if wide else 160)


class PageStack(QStackedWidget):
    """Hidden work controls must not set the home page's minimum width."""
    def __init__(self):
        super().__init__()
        self.layout().setSizeConstraint(QLayout.SetNoConstraint)
        self.currentChanged.connect(lambda _:self.updateGeometry())
        self.reduced_motion = True
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1)
        self.setGraphicsEffect(self._effect)
        self._transition = QPropertyAnimation(self._effect, b'opacity', self)
        self._transition.setDuration(160)
        self._transition.setEasingCurve(QEasingCurve.OutCubic)
        self._transition.finished.connect(lambda:self._effect.setEnabled(False))
        self._effect.setEnabled(False)

    def finish_transition(self):
        self._transition.stop()
        self._effect.setOpacity(1)
        self._effect.setEnabled(False)

    def setCurrentWidget(self, widget):
        changed = widget is not self.currentWidget()
        self.finish_transition()
        super().setCurrentWidget(widget)
        if changed and not self.reduced_motion and self.isVisible():
            self._effect.setEnabled(True)
            self._transition.setStartValue(.35)
            self._transition.setEndValue(1.)
            self._transition.start()

    def minimumSizeHint(self):
        page=self.currentWidget()
        return page.minimumSizeHint() if page is not None else super().minimumSizeHint()

    def sizeHint(self):
        page=self.currentWidget()
        return page.sizeHint() if page is not None else super().sizeHint()

    def hasHeightForWidth(self):
        page=self.currentWidget()
        return page.hasHeightForWidth() if page is not None else False

    def heightForWidth(self,width):
        page=self.currentWidget()
        return page.heightForWidth(width) if page is not None else -1


class GameCardDelegate(QStyledItemDelegate):
    """Presentation resources are bounded and never determine profile identity."""
    def __init__(self,parent):
        super().__init__(parent)
        self._covers={}

    def cover(self,key):
        if key not in _COVER_ORDER:return None
        if key not in self._covers:
            reader=QImageReader(str(Path(__file__).with_name('art')/(key+'.jpg')))
            size=reader.size()
            image=None
            if size.isValid() and size.width()*size.height()<=8*1024*1024:
                reader.setScaledSize(size.scaled(QSize(480,620),Qt.KeepAspectRatio))
                decoded=reader.read()
                if not decoded.isNull():image=QPixmap.fromImage(decoded)
            self._covers[key]=image
        return self._covers[key]

    def sizeHint(self,option,index):return self.parent().gridSize()

    def paint(self,painter,option,index):
        painter.save();painter.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(option.rect).adjusted(17,7,-17,-7)
        path=QPainterPath();path.addRoundedRect(rect,22,22)
        painter.setClipPath(path)
        painter.fillRect(rect,QColor('#12203a'))
        cover=self.cover(index.data(Qt.UserRole+1))
        if cover is not None:
            source=QRectF(cover.rect())
            ratio=rect.width()/rect.height()
            if source.width()/source.height()>ratio:source.setWidth(source.height()*ratio)
            else:source.setHeight(source.width()/ratio)
            source.moveCenter(QRectF(cover.rect()).center())
            painter.drawPixmap(rect,cover,source)
        shade=QLinearGradient(rect.topLeft(),rect.bottomLeft())
        shade.setColorAt(0,QColor(5,8,19,8));shade.setColorAt(.4,QColor(5,8,19,25));shade.setColorAt(1,QColor(5,8,19,245))
        painter.fillRect(rect,shade)
        font=QFont('Segoe UI');font.setPixelSize(38 if rect.width()>=350 else 35);font.setWeight(QFont.DemiBold)
        painter.setFont(font);painter.setPen(QColor('#f1f5ff'))
        painter.drawText(rect.adjusted(17,rect.height()-112,-17,-27),Qt.AlignLeft|Qt.AlignBottom|Qt.TextWordWrap,index.data(Qt.DisplayRole))
        font.setPixelSize(12);font.setWeight(QFont.Normal);painter.setFont(font);painter.setPen(QColor('#a9bfdf'))
        painter.drawText(rect.adjusted(17,rect.height()-26,-17,-6),Qt.AlignLeft|Qt.AlignVCenter,index.data(Qt.UserRole+2))
        painter.setClipping(False)
        selected=bool(option.state & (QStyle.State_Selected|QStyle.State_HasFocus))
        painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor('#98bdff' if selected else '#304465'),2 if selected else 1))
        painter.drawRoundedRect(rect,22,22)
        if not option.state & QStyle.State_Enabled:painter.fillPath(path,QColor(5,8,19,150))
        painter.restore()


class GameList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setGridSize(QSize(340,300))
        self.setMaximumWidth(1100)
        self.setItemDelegate(GameCardDelegate(self))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        width=self.viewport().width()
        columns=2 if width>=700 else 1
        side=max(220,(width-20)//columns)
        grid=QSize(side,324 if columns==2 else 239)
        if grid!=self.gridSize():self.setGridSize(grid)


class ConsoleUI(QWidget):
    source_requested = Signal(str)
    game_requested = Signal(str)
    navigation_requested = Signal(str)
    preferences_opening = Signal()
    about_requested = Signal()
    appearance_requested = Signal()
    correction_requested = Signal()

    def __init__(self, owner, configuration, source, target, status, controls, version,game_import):
        super().__init__(owner)
        self.setObjectName('console')
        self._state = None
        self._can_navigate = True
        self._can_change_source = True
        self.home_choices = ()
        self.profile_choices = ()
        self.target = target
        self._owner = owner
        self.sound = NavigationSound(self)
        self.pages = PageStack()
        self.preferences = QDialog(owner)
        self.preferences.setObjectName('preferences')
        self.preferences.setWindowTitle('MOZKAN Live Sub · Ayarlar')
        self.preferences.setWindowModality(Qt.WindowModal)
        self.preferences.setAttribute(Qt.WA_QuitOnClose, False)
        available = owner.screen().availableGeometry()
        self.preferences.resize(min(960, available.width()-40), min(760, available.height()-60))
        preferences_layout = QVBoxLayout(self.preferences)
        preferences_layout.addWidget(configuration)
        self.preference_status = label('', 'eyebrow')
        self.preference_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        preferences_layout.addWidget(self.preference_status)
        close = QPushButton('Kapat')
        close.setAutoDefault(False)
        close.clicked.connect(self.preferences.reject)
        preferences_layout.addWidget(close)
        self.preferences.finished.connect(self.restore_settings_focus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 18)
        layout.setSpacing(18)
        header = ResponsiveRow(self)
        header.addWidget(label('MOZKAN LIVE SUB', 'brand'))
        header.addStretch()
        self.settings_button = QPushButton('Ayarlar')
        self.settings_button.clicked.connect(self.show_preferences)
        header.addWidget(self.settings_button)
        self.tv_button = QPushButton('TV’ye bağlan')
        self.tv_button.clicked.connect(lambda:self.show_preferences('tv'))
        header.addWidget(self.tv_button)
        layout.addLayout(header)
        layout.addWidget(self.pages, 1)

        self.home = QWidget()
        self.home.setObjectName('choicePage')
        home_layout = QVBoxLayout(self.home)
        home_layout.setContentsMargins(6, 24, 6, 12)
        home_layout.addStretch(1)
        self.live_choice = ChoiceCard('Canlı\nÇeviri','Tek replik veya diyalog','live')
        self.games_choice = ChoiceCard('Oyunlar','Yerel çeviri profilleri','games')
        self.movie_choice = ChoiceCard('Dizi ve film','Tarayıcıda veya video oynatıcıda','movie')
        self.movie_choice.setMinimumHeight(112);self.movie_choice.setMaximumHeight(112)
        self.home_choices = (self.live_choice, self.games_choice, self.movie_choice)
        for button in self.home_choices:
            button.setObjectName('choice')
            button.installEventFilter(self)
        self.home_pair=ChoicePair(self.live_choice,self.games_choice)
        home_layout.addWidget(self.home_pair,4)
        home_layout.addSpacing(12)
        home_layout.addWidget(self.movie_choice)
        self.live_choice.clicked.connect(lambda: self.navigation_requested.emit('profiles'))
        self.movie_choice.clicked.connect(lambda: self.source_requested.emit('movie'))
        self.games_choice.clicked.connect(lambda: self.navigation_requested.emit('games'))
        self.resume = QPushButton('Çalışma alanına dön')
        self.resume.clicked.connect(lambda: self.navigation_requested.emit('work'))
        home_layout.addWidget(self.resume)
        home_layout.addStretch(1)
        self.pages.addWidget(self.home)

        self.profiles = QWidget()
        self.profiles.setObjectName('choicePage')
        profiles_layout = QVBoxLayout(self.profiles)
        profiles_layout.setContentsMargins(0,24,0,20)
        profiles_layout.addWidget(label('Çeviri biçimi', 'context'),0,Qt.AlignHCenter)
        profiles_layout.addStretch(1)
        self.single_choice = ChoiceCard('Tek\nReplik','Ekrandaki güncel altyazı','single')
        self.dialogue_choice = ChoiceCard('Diyalog','Konuşmacı ve önceki replik','dialogue')
        self.profile_choices = (self.single_choice,self.dialogue_choice)
        for button, source_kind in zip(self.profile_choices,('single','dialogue')):
            button.setObjectName('choice')
            button.installEventFilter(self)
            button.clicked.connect(lambda checked=False,kind=source_kind:self.source_requested.emit(kind))
        self.profile_pair=ChoicePair(*self.profile_choices)
        profiles_layout.addWidget(self.profile_pair,4)
        profiles_layout.addStretch(1)
        self.pages.addWidget(self.profiles)

        self.games = QWidget()
        games_layout = QVBoxLayout(self.games)
        games_layout.setContentsMargins(0, 10, 0, 10)
        game_header=QHBoxLayout()
        game_header.addWidget(label('Oyun profilleri', 'heading'),1)
        game_import.setText('Profil ekle')
        game_header.addWidget(game_import)
        games_layout.addLayout(game_header)
        games_layout.addWidget(label('Kayıtlı Türkçe replikleri kullanır. Eşleşmeyen metin için model seçeneğini ayarlardan değiştirebilirsin.'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Oyun ara')
        self.search.setClearButtonEnabled(True)
        games_layout.addWidget(self.search)
        self.game_list = GameList()
        self.game_list.setSelectionMode(QAbstractItemView.SingleSelection)
        game_row=QHBoxLayout()
        game_row.addStretch();game_row.addWidget(self.game_list,1);game_row.addStretch()
        games_layout.addLayout(game_row,1)
        self.games_empty = label('')
        games_layout.addWidget(self.games_empty)
        self.use_game = QPushButton('Seçili oyunla devam et')
        self.use_game.setObjectName('primary')
        games_layout.addWidget(self.use_game)
        self.search.textChanged.connect(self.filter_games)
        self.game_list.currentItemChanged.connect(self.update_game_action)
        self.game_list.itemActivated.connect(lambda _: self.activate_game())
        self.game_list.itemClicked.connect(lambda _: self.activate_game())
        self.use_game.clicked.connect(self.activate_game)
        self.pages.addWidget(self.games)

        self.work = QWidget()
        work_layout = QVBoxLayout(self.work)
        work_layout.setContentsMargins(0, 4, 0, 0)
        context_row = QHBoxLayout()
        self.context = label('', 'context')
        self.phase = label('', 'phase')
        context_row.addWidget(self.context, 1)
        context_row.addWidget(self.phase)
        work_layout.addLayout(context_row)
        self.preparation=QProgressBar()
        self.preparation.setRange(0,0)
        self.preparation.setAccessibleName('Çeviri hazırlığı')
        self.preparation.hide()
        work_layout.addWidget(self.preparation)
        self.canvas = WorkCanvas()
        self.prompt = label('Alanı seç.\nSonra başlat.', 'prompt')
        self.prompt.setAlignment(Qt.AlignCenter)
        self.canvas.addWidget(self.prompt)
        target.setPlaceholderText('Türkçe çeviri burada görünecek.')
        target.setObjectName('caption')
        target.viewport().setAutoFillBackground(False)
        target.viewport().setAttribute(Qt.WA_TranslucentBackground)
        self.canvas.addWidget(target)
        work_layout.addWidget(self.canvas, 1)
        target.textChanged.connect(self.update_canvas)
        dock = QHBoxLayout()
        self.select, self.preview, self.start, self.pause, self.stop = controls
        self.start.setObjectName('primary')
        self.primary_action=QStackedWidget()
        self.primary_action.addWidget(self.start);self.primary_action.addWidget(self.stop)
        self.subtitle_settings = QPushButton('Altyazı')
        self.subtitle_settings.clicked.connect(lambda:self.appearance_requested.emit())
        for button in (self.select,self.start,self.stop,self.subtitle_settings):button.setMinimumHeight(64)
        dock.addWidget(self.select,1);dock.addWidget(self.primary_action,2);dock.addWidget(self.subtitle_settings,1)
        work_layout.addLayout(dock)
        secondary=QHBoxLayout()
        self.correct = QPushButton('Çeviriyi düzelt')
        self.correct.setToolTip('Son satırın Türkçesini düzeltin; aynı satır bir dahaki sefere sizin çevirinizle gösterilir.')
        self.correct.setEnabled(False)
        self.correct.clicked.connect(lambda:self.correction_requested.emit())
        secondary.addWidget(self.pause);secondary.addWidget(self.preview);secondary.addWidget(self.correct)
        work_layout.addLayout(secondary)
        self.details = QPushButton('Çeviri ayrıntısını göster')
        self.details.setCheckable(True)
        self.details.setObjectName('quiet')
        source.setObjectName('source')
        source.setMaximumHeight(120)
        source.hide()
        self.details.toggled.connect(source.setVisible)
        self.details.toggled.connect(lambda checked: self.details.setText('Çeviri ayrıntısını gizle' if checked else 'Çeviri ayrıntısını göster'))
        work_layout.addWidget(self.details)
        work_layout.addWidget(source)
        self.pages.addWidget(self.work)
        status.setObjectName('eyebrow')
        layout.addWidget(status)
        footer = ResponsiveRow(self)
        self.about_button=QPushButton('Yerel uygulama · '+version+' · Hakkında')
        self.about_button.setObjectName('quiet')
        self.about_button.clicked.connect(lambda:self.about_requested.emit())
        footer.addWidget(self.about_button)
        footer.addStretch()
        self.home_button = QPushButton('Ana ekran')
        self.home_button.setObjectName('quiet')
        self.home_button.clicked.connect(lambda: self.navigation_requested.emit('home'))
        footer.addWidget(self.home_button)
        self.back_button = QPushButton('Geri · Esc')
        self.back_button.setObjectName('quiet')
        self.back_button.clicked.connect(lambda:self.navigation_requested.emit('back'))
        footer.addWidget(self.back_button)
        self.back_button.hide()
        self.home_button.hide()
        layout.addLayout(footer)
        self.pages.setCurrentWidget(self.home)
        self.update_canvas()
        for button in self.findChildren(QPushButton):
            button.installEventFilter(self)
        self.game_list.installEventFilter(self)
        self.search.installEventFilter(self)
        self.live_choice.setFocus(Qt.OtherFocusReason)

    @property
    def page(self):
        return {getattr(self,name):name for name in ('home','profiles','games','work')}[self.pages.currentWidget()]

    def navigate(self, page):
        if page not in ('home', 'profiles', 'games', 'work'):
            raise ValueError('Bilinmeyen ekran.')
        if not self._can_navigate:
            return False
        changed = self.page != page
        self.pages.setCurrentWidget(getattr(self, page))
        self.back_button.setVisible(page != 'home')
        self.home_button.setVisible(page != 'home')
        if changed:self.sound.play()
        if page == 'home':
            (self.live_choice if self.live_choice.isEnabled() else self.resume).setFocus()
        elif page == 'games':
            self.search.setFocus()
        elif page == 'profiles':
            self.single_choice.setFocus()
        else:
            action=self.primary_action.currentWidget()
            (action if action.isEnabled() else self.select).setFocus()
        return True

    def restore_settings_focus(self, *_):
        if self.isVisible() and not self._owner.closing:
            self.settings_button.setFocus(Qt.OtherFocusReason)

    def show_preferences(self, section='general'):
        if not self.settings_button.isEnabled():
            return
        if not self._owner.prepare_capture_safe_dialog(self.preferences):
            return
        self.preferences_opening.emit()
        self.pages.finish_transition()
        self._owner.settings_tabs.setCurrentIndex(1 if section == 'tv' else 0)
        self.preferences.open()
        self._owner.settings_tabs.tabBar().setFocus(Qt.OtherFocusReason)
        self.preferences.raise_()
        self.preferences.activateWindow()

    def set_games(self, choices):
        selected = self.game_list.currentItem()
        identity = selected.data(Qt.UserRole) if selected else None
        self.game_list.clear()
        for choice in choices:
            item = QListWidgetItem(choice.title)
            item.setData(Qt.UserRole, choice.identity)
            item.setData(Qt.UserRole+1,choice.cover_key)
            item.setData(Qt.UserRole+2,choice.subtitle)
            item.setToolTip(choice.tooltip)
            if not choice.available:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable)
            self.game_list.addItem(item)
            if choice.identity == identity:
                self.game_list.setCurrentItem(item)
        self.filter_games(self.search.text())

    def filter_games(self, text):
        visible = []
        for index in range(self.game_list.count()):
            item = self.game_list.item(index)
            item.setHidden(text.casefold() not in item.text().casefold())
            if not item.isHidden() and item.flags() & Qt.ItemIsEnabled:
                visible.append(item)
        current = self.game_list.currentItem()
        if current not in visible:
            self.game_list.setCurrentItem(visible[0] if visible else None)
        self.games_empty.setText('' if visible else 'Sonuç bulunamadı. Başka bir ad ara veya ayarlardan bir profil aç.')
        self.update_game_action()

    def update_game_action(self, *args):
        item = self.game_list.currentItem()
        self.use_game.setEnabled(bool(self._can_change_source and item is not None
                                     and not item.isHidden() and item.flags() & Qt.ItemIsEnabled))

    def activate_game(self):
        if self.use_game.isEnabled():
            self.game_requested.emit(self.game_list.currentItem().data(Qt.UserRole))

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        self._can_navigate = state.can_navigate
        self._can_change_source = state.can_change_source
        self.context.setText(state.context)
        self.phase.setText(state.phase)
        self.prompt.setText(state.prompt)
        self.preparation.setVisible(state.preparing)
        previous_action=self.primary_action.currentWidget()
        transfer_focus=previous_action.hasFocus()
        action=self.stop if state.running else self.start
        self.primary_action.setCurrentWidget(action)
        if transfer_focus and action.isEnabled():action.setFocus(Qt.OtherFocusReason)
        self.about_button.setEnabled(state.can_navigate and not state.preparing)
        self.live_choice.setEnabled(state.can_change_source)
        self.movie_choice.setEnabled(state.can_change_source)
        self.single_choice.setEnabled(state.can_change_source)
        self.dialogue_choice.setEnabled(state.can_change_source)
        self.games_choice.setEnabled(state.can_navigate)
        self.home_button.setEnabled(state.can_navigate)
        self.resume.setEnabled(state.can_navigate)
        self.settings_button.setEnabled(state.can_navigate and not state.preparing)
        self.tv_button.setEnabled(state.can_navigate and not state.preparing)
        self.back_button.setEnabled(state.can_navigate)
        self.subtitle_settings.setEnabled(state.can_navigate and not state.preparing)
        self.update_game_action()

    def update_canvas(self):
        self.canvas.setCurrentWidget(self.prompt if self.target.document().isEmpty() else self.target)

    def eventFilter(self, watched, event):
        if event.type()==QEvent.KeyPress and watched in (self.search,self.game_list):
            if event.key()==Qt.Key_Down and watched is self.search and self.game_list.currentItem() is not None:
                self.game_list.setFocus(Qt.TabFocusReason)
                return True
            if event.key()==Qt.Key_Escape and watched is self.search and self.search.text():
                self.search.clear()
                return True
        if event.type()==QEvent.FocusIn and watched in self.home_choices+self.profile_choices:
            scroll=self.parentWidget()
            while scroll is not None and not isinstance(scroll,QScrollArea):scroll=scroll.parentWidget()
            if scroll is not None:scroll.ensureWidgetVisible(watched,12,12)
        if event.type()==QEvent.KeyPress and isinstance(watched,QPushButton) and event.key() in (Qt.Key_Return,Qt.Key_Enter):
            if not event.isAutoRepeat():watched.click()
            return True
        if event.type() == QEvent.KeyPress and watched in self.home_choices+self.profile_choices:
            if event.key() in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Right, Qt.Key_Down):
                group=self.home_choices if watched in self.home_choices else self.profile_choices
                choices = [button for button in group if button.isEnabled()]
                if watched in choices:
                    delta = -1 if event.key() in (Qt.Key_Left, Qt.Key_Up) else 1
                    choices[(choices.index(watched)+delta) % len(choices)].setFocus()
                    if not event.isAutoRepeat():self.sound.play()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.navigation_requested.emit('back')
            event.accept()
        else:
            super().keyPressEvent(event)
