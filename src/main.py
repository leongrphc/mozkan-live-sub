from __future__ import annotations

import argparse
import ctypes
import os
import logging
import threading
import time
import html
from datetime import datetime,timezone
import sys
from pathlib import Path

for key in ('OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'MKL_NUM_THREADS'):
    os.environ[key] = '2'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

from PySide6.QtCore import Qt, QRect, Signal, QObject, QTimer, QUrl, QLockFile,QCoreApplication,QEvent,QSignalBlocker
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QFontDatabase, QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QFileDialog, QLineEdit, QDialog, QFormLayout,
    QDialogButtonBox, QColorDialog,QScrollArea,QProgressBar,QTabWidget)
from settings import Settings
from tv import TV
from coordinates import capture_region, normalized_region
from capture import run_capture
from dialogue import CaptionStack, Caption, render_stack, render_caption, split_speaker, ensure_speaker,MAX_CAPTION
from samsung import SamsungHelper
from video import resolve_selection
from control import CaptureControl
from catalog import Catalog
from overlay import Overlay,HudOverlay
from appearance import STYLE_DEFAULTS,HUD_LAYOUT_DEFAULTS,DEFAULT_FONT_SIZE,BACKGROUND_RGB
from hud import display_text
from diagnostics import DiagnosticMailbox,DiagnosticUpdate,TranslationObservation,diagnostic_record
from regions import SelectedArea,CapturePlan,CaptureBindingChanged,save_areas,desktop_signature,AREA_LABELS
from console_ui import ConsoleUI,ConsoleState,GameChoice,STYLE as CONSOLE_STYLE
from capture_exclusion import try_capture_exclusion
from manual_capture import capture_image as grab_image,save_image,save_json
from startup import Startup,CaptureProgress,CaptureFailure,ChildStop
from app_log import AppLog
from presentation import ResponsiveRow,system_reduced_motion

APP_VERSION='0.4.1'


class Events(QObject):
    output = Signal(int, str, str, int)
    hud = Signal(int, str, str, int)
    error = Signal(str)
    capture_message = Signal(int, int, str, bool)
    tv_closed = Signal(object, object)
    profile_imported = Signal(object, object)
    progress = Signal(int,object)
    failure = Signal(int,str,object)


class Selector(QWidget):
    selected = Signal(tuple)
    finished = Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_QuitOnClose,False)
        self._finished=False
        self.first = self.last = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.first = self.last = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        self.last = event.globalPosition().toPoint()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button()!=Qt.LeftButton or self.first is None:
            return
        r = QRect(self.first, event.globalPosition().toPoint()).normalized()
        if r.width() >= 40 and r.height() >= 20:
            self.selected.emit((r.x(), r.y(), r.width(), r.height()))
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self,event):
        if not self._finished:
            self._finished=True
            self.finished.emit()
        event.accept()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(20, 30, 50, 120))
        if self.first and self.last:
            p.setPen(QPen(QColor('#5ed8ee'), 3))
            p.drawRect(QRect(self.mapFromGlobal(self.first),
                             self.mapFromGlobal(self.last)).normalized())


class Window(QMainWindow):
    def __init__(self, models, settings=None,event_log=None):
        super().__init__()
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'segoeui.ttf'
        if font_path.is_file():
            QFontDatabase.addApplicationFont(str(font_path))
        QApplication.instance().setFont(QFont('Segoe UI', 10))
        self.models, self.region = models, None
        self.event_log=event_log
        self.startup=None
        self._hud_stop=None
        self.last_capture_error=''
        self._cleanup_failed=False
        self._areas={}
        self._stale_areas=set()
        self.selector=None
        self._selection_generation=0
        self._selection_context=None
        self._selection_restore=None
        self._capture_plan=None
        self._topology_check_at=0.0
        self.diagnostics=DiagnosticMailbox()
        self._screen_connections={}
        self._application_connections=[]
        self.settings = settings if settings is not None else Settings()
        self.catalog = Catalog(models.parent / 'game_profiles', self.settings.path.parent / 'games')
        self.import_worker = None
        self.import_busy = False
        self.samsung = SamsungHelper(models.parent / 'samsung', self.settings.path.parent / 'samsung', self)
        self.samsung.status.connect(lambda text: self.status.setText(text))
        self.samsung.changed.connect(self.samsung_changed)
        self.captions = CaptionStack()
        self.current_hud = ''
        self.tv = None
        self.tv_cleanup = None
        self.tv_closing = False
        self.tv_stop_error = None
        self.tv_address_refresh_at = 0.0
        self.stop_event = threading.Event()
        self.worker = None
        self.control = CaptureControl()
        self.hud_control = CaptureControl()
        self.reselect_pending = False
        self._navigation_pending = None
        self.session = 0
        self.closing = False
        self.events = Events()
        self.events.output.connect(self.received)
        self.events.hud.connect(self.received_hud)
        self.events.error.connect(lambda s: self.status.setText('Hata: ' + s))
        self.events.capture_message.connect(self.capture_message)
        self.events.tv_closed.connect(self.tv_closed)
        self.events.profile_imported.connect(self.profile_imported)
        self.events.progress.connect(self.capture_progress)
        self.events.failure.connect(self.capture_failure)
        self.overlay = Overlay()
        self.hud_overlay = HudOverlay()
        self.hud_layout={key:self.settings.values.get('hud_'+key,value) for key,value in HUD_LAYOUT_DEFAULTS.items()}
        self.hud_overlay.configure_layout(**self.hud_layout)
        self.overlay_style = {key: self.settings.values.get('overlay_' + key, default)
                              for key, default in STYLE_DEFAULTS.items()}
        self.overlay.configure(**self.overlay_style)
        self.hud_overlay.configure(**{key:self.overlay_style[key] for key in ('color','opacity','stroke','enabled')})
        self.setWindowTitle('MOZKAN Live Sub · '+APP_VERSION)
        available=QApplication.primaryScreen().availableGeometry()
        self.resize(min(1080,max(480,available.width()-40)),min(900,max(400,available.height()-60)))
        self.setMinimumSize(480, 400)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(32, 28, 32, 28)
        title = QLabel('Çeviri ayarları')
        title.setStyleSheet('font-size:26px;font-weight:600')
        layout.addWidget(title)
        layout.addWidget(QLabel('Altyazı bölgesini seç. Çeviriyi ekranın üzerinde gör.'))
        mode_row = ResponsiveRow(root)
        self.mode = QComboBox()
        self.mode.addItem('Oyun / ekran', 'screen')
        self.mode.addItem('Dizi / film · Tarayıcı videosu', 'movie')
        self.mode.setCurrentIndex(max(0, self.mode.findData(self.settings.values.get('mode', 'screen'))))
        self.selection_scope = QComboBox()
        self.selection_scope.addItem('Yalnızca altyazı satırını seçeceğim', 'subtitle')
        self.selection_scope.addItem('Videonun tamamını seçeceğim', 'video')
        self.selection_scope.setCurrentIndex(max(0, self.selection_scope.findData(self.settings.values.get('selection_scope', 'subtitle'))))
        self.band = QSpinBox()
        self.band.setRange(15, 50)
        self.band.setSuffix(' %')
        self.band.setValue(self.settings.values.get('video_band', 30))
        self.band_label = QLabel('Videonun alt kısmını tara')
        self.video_hint = QLabel()
        self.video_hint.setWordWrap(True)
        mode_row.addWidget(self.mode)
        mode_row.addWidget(self.selection_scope)
        mode_row.addWidget(self.band_label)
        mode_row.addWidget(self.band)
        layout.addLayout(mode_row)
        layout.addWidget(self.video_hint)
        self.select = QPushButton('Bölge seç')
        self.start = QPushButton('Çeviriyi başlat')
        self.stop = QPushButton('Durdur')
        self.preview_button = QPushButton('Alanı önizle')
        self.preview_button.clicked.connect(self.preview)
        self.pause_button = QPushButton('Duraklat')
        self.pause_button.clicked.connect(self.toggle_pause)
        self.reselect_button = QPushButton('Alanı yeniden seç')
        self.reselect_button.clicked.connect(self.reselect)
        layout.addWidget(self.reselect_button)
        options = ResponsiveRow(root)
        self.profile = QComboBox()
        self.profile.setMinimumContentsLength(24)
        self.profile.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        saved_profile = self.settings.values.get('profile', '')
        self.refresh_profiles(saved_profile)
        self.profile.activated.connect(self.save_profile_selection)
        self.import_profile = QPushButton('Profil aç')
        self.import_profile.clicked.connect(self.open_profile)
        self.fallback = QCheckBox('Eşleşmeyeni modelle çevir')
        self.fallback.setChecked(self.settings.values.get('fallback', True))
        self.dialogue = QCheckBox('Önceki altyazıyı göster')
        self.dialogue.setChecked(self.settings.values.get('dialogue', True))
        options.addWidget(self.profile)
        options.addWidget(self.import_profile)
        options.addWidget(self.fallback)
        layout.addLayout(options)
        self.ignore_speaker=QCheckBox('Eşleştirmede konuşmacı adlarını yok say')
        self.ignore_speaker.setChecked(self.settings.values.get('ignore_speaker',True))
        layout.addWidget(self.ignore_speaker)
        ocr_options=ResponsiveRow(root)
        ocr_options.addWidget(QLabel('Altyazı OCR'))
        self.ocr_quality=QComboBox()
        self.ocr_quality.addItem('Hızlı · uyarlamalı','fast')
        self.ocr_quality.addItem('Ayrıntılı · iki geçiş','accurate')
        self.ocr_quality.setCurrentIndex(self.ocr_quality.findData(self.settings.values.get('ocr_quality','fast')))
        self.ocr_quality.setToolTip('Ayrıntılı mod normal ve kontrast görüntüyü karşılaştırır; daha fazla işlemci süresi kullanır. Görev OCR kanalı bağımsızdır.')
        ocr_options.addWidget(self.ocr_quality)
        ocr_options.addWidget(QLabel('Tarama aralığı'))
        self.ocr_interval=QDoubleSpinBox()
        self.ocr_interval.setDecimals(2)
        self.ocr_interval.setRange(.08,3)
        self.ocr_interval.setSingleStep(.05)
        self.ocr_interval.setSuffix(' s')
        self.ocr_interval.setValue(self.settings.values.get('ocr_interval',.35))
        self.ocr_interval.setToolTip('Altyazı yakalamaları arasındaki en az süre. OCR daha uzun sürerse çevrim de uzar.')
        ocr_options.addWidget(self.ocr_interval)
        ocr_options.addStretch()
        layout.addLayout(ocr_options)
        observation_row=ResponsiveRow(root)
        self.ocr_info=QLabel('Altyazı OCR: kapalı')
        self.hud_ocr_info=QLabel('Görev OCR: kapalı')
        for label in (self.ocr_info,self.hud_ocr_info):
            label.setTextFormat(Qt.PlainText)
            label.setWordWrap(True)
            observation_row.addWidget(label,1)
        layout.addLayout(observation_row)
        translation_row=ResponsiveRow(root)
        self.translation_info=QLabel('Altyazı çevirisi: kapalı')
        self.hud_translation_info=QLabel('Görev çevirisi: kapalı')
        for label in (self.translation_info,self.hud_translation_info):
            label.setTextFormat(Qt.PlainText)
            label.setWordWrap(True)
            translation_row.addWidget(label,1)
        layout.addLayout(translation_row)
        appearance = ResponsiveRow(root)
        self.caption_mode = QComboBox()
        self.caption_mode.addItem('Tek altyazı','single')
        self.caption_mode.addItem('Diyalog · son konuşmacı','dialogue')
        saved_caption_mode = self.settings.values.get('caption_mode',
                            'dialogue' if self.settings.values.get('dialogue',False) else 'single')
        self.caption_mode.setCurrentIndex(self.caption_mode.findData(saved_caption_mode))
        self.caption_mode.setToolTip('Diyalog modunda üstte kalan eski İngilizce satırlar ayrılır; son konuşmacı çevrilir.')
        appearance.addWidget(self.caption_mode)
        appearance.addWidget(self.dialogue)
        appearance.addWidget(QLabel('Yazı boyutu'))
        self.font_size = QSpinBox()
        self.font_size.setRange(14, 64)
        self.font_size.setValue(self.settings.values.get('font_size',DEFAULT_FONT_SIZE))
        appearance.addWidget(self.font_size)
        self.appearance_button = QPushButton('Altyazı görünümü')
        self.appearance_button.clicked.connect(self.edit_appearance)
        appearance.addWidget(self.appearance_button)
        appearance.addStretch()
        layout.addLayout(appearance)
        hud_row = ResponsiveRow(root)
        self.hud_enabled = QCheckBox('Görev / HUD çevirisi')
        self.hud_select = QPushButton('HUD bölgesi seç')
        self.hud_select.clicked.connect(lambda: self.choose('hud'))
        self.hud_text = QLabel('İsteğe bağlı ikinci ekran bölgesi')
        self.hud_text.setTextFormat(Qt.PlainText)
        self.hud_text.setWordWrap(True)
        self.hud_text.setMaximumHeight(56)
        hud_row.addWidget(self.hud_enabled)
        hud_row.addWidget(self.hud_select)
        self.hud_appearance=QPushButton('Görev görünümü')
        self.hud_appearance.clicked.connect(self.edit_hud_appearance)
        hud_row.addWidget(self.hud_appearance)
        hud_row.addWidget(self.hud_text)
        layout.addLayout(hud_row)
        tv_page = QWidget()
        tv_layout = QVBoxLayout(tv_page)
        tv_title = QLabel('TV’ye bağlan')
        tv_title.setObjectName('heading')
        tv_layout.addWidget(tv_title)
        tv_hint = QLabel('Bilgisayar ve TV aynı yerel ağda olmalı. TV tarayıcısını açarak bağlanabilirsiniz.')
        tv_hint.setWordWrap(True)
        tv_layout.addWidget(tv_hint)
        self.tv_state = QLabel('Yayın kapalı')
        self.tv_state.setObjectName('connectionState')
        self.tv_state.setTextFormat(Qt.PlainText)
        tv_layout.addWidget(self.tv_state)
        tv_layout.addWidget(QLabel('1 · Yerel altyazı yayınını açın'))
        tv_row = ResponsiveRow(tv_page)
        self.tv_button = QPushButton('TV yayınını aç')
        self.tv_button.clicked.connect(self.toggle_tv)
        self.tv_info = QLabel('TV ve bilgisayar aynı ağda olmalı.')
        self.tv_info.setWordWrap(True)
        self.tv_info.setTextFormat(Qt.PlainText)
        tv_row.addWidget(self.tv_button)
        tv_row.addWidget(self.tv_info)
        tv_layout.addLayout(tv_row)
        tv_tools = ResponsiveRow(tv_page)
        self.tv_urls = QComboBox()
        self.tv_urls.setMinimumContentsLength(12)
        self.tv_urls.setAccessibleName('TV alıcı adresi')
        self.tv_urls.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.tv_copy_url = QPushButton('Adresi kopyala')
        self.tv_copy_code = QPushButton('Kodu kopyala')
        self.tv_test = QPushButton('Test altyazısı')
        self.tv_pairing = QPushButton('Otomatik eşleştirmeyi aç')
        self.tv_pairing.setToolTip('Aynı ağdaki alıcılar kodu 2 dakika boyunca otomatik alabilir.')
        self.tv_pairing.clicked.connect(self.toggle_tv_pairing)
        self.tv_clients = QLabel('Bağlı alıcı: 0')
        self.tv_copy_url.clicked.connect(self.copy_tv_address)
        self.tv_copy_code.clicked.connect(self.copy_tv_code)
        self.tv_test.clicked.connect(self.test_tv_caption)
        self.tv_urls.setMinimumWidth(0)
        tv_layout.addWidget(QLabel('2 · TV tarayıcısında bu adresi açın'))
        tv_layout.addWidget(self.tv_urls)
        self.tv_code = QLabel('—')
        self.tv_code.setTextFormat(Qt.PlainText)
        self.tv_code.setObjectName('connectionCode')
        self.tv_code.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.tv_code.setAccessibleName('Eşleştirme kodu')
        tv_layout.addWidget(QLabel('3 · Alıcı isterse eşleştirme kodunu girin'))
        tv_layout.addWidget(self.tv_code)
        for item in (self.tv_copy_url,self.tv_copy_code,self.tv_pairing,self.tv_test):
            tv_tools.addWidget(item)
        tv_layout.addLayout(tv_tools)
        tv_layout.addWidget(self.tv_clients)
        self.tv_feedback = QLabel('Yalnız altyazı metni gönderilir. Oyun veya video görüntüsü TV’ye aktarılmaz.')
        self.tv_feedback.setWordWrap(True)
        self.tv_feedback.setTextFormat(Qt.PlainText)
        tv_layout.addWidget(self.tv_feedback)
        tv_layout.addStretch()
        samsung_page = QWidget()
        samsung_layout = QVBoxLayout(samsung_page)
        samsung_title = QLabel('Samsung TV kurulumu · isteğe bağlı')
        samsung_title.setObjectName('context')
        samsung_layout.addWidget(samsung_title)
        samsung_hint = QLabel('TV tarayıcısı ile bağlantı için kurulum gerekmez. Bu bölüm mevcut Samsung yardımcı aracını kullanır; fiziksel TV kurulumu henüz doğrulanmadı.')
        samsung_hint.setWordWrap(True)
        samsung_layout.addWidget(samsung_hint)
        samsung_row = ResponsiveRow(samsung_page)
        self.tv_host = QLineEdit()
        self.tv_host.setPlaceholderText('Samsung TV IP adresi')
        self.tv_host.setText(self.settings.values.get('samsung_host',''))
        self.samsung_scan = QPushButton('Samsung TV ara')
        self.samsung_install = QPushButton('TV’ye kur')
        self.samsung_cancel = QPushButton('İptal')
        self.samsung_login = QPushButton('Samsung hesabını aç')
        self.samsung_login.setEnabled(False)
        self.samsung_login.clicked.connect(self.open_samsung_login)
        self.samsung_scan.clicked.connect(lambda: self.samsung_start('scan'))
        self.samsung_install.clicked.connect(lambda: self.samsung_start('install'))
        self.samsung_cancel.clicked.connect(self.samsung.cancel)
        for widget in (self.tv_host, self.samsung_scan, self.samsung_install, self.samsung_cancel, self.samsung_login):
            samsung_row.addWidget(widget)
        samsung_layout.addLayout(samsung_row)
        samsung_options=ResponsiveRow(samsung_page)
        self.samsung_devices=QComboBox()
        self.samsung_devices.addItem('Bulunan TV’yi seç','')
        self.samsung_devices.activated.connect(lambda index:self.tv_host.setText(self.samsung_devices.itemData(index)) if index>0 else None)
        self.samsung_renew=QCheckBox('Samsung oturumunu yenile')
        self.samsung_log=QPushButton('Samsung günlüğü')
        self.samsung_log.clicked.connect(self.open_samsung_log)
        for widget in (self.samsung_devices,self.samsung_renew,self.samsung_log):samsung_options.addWidget(widget)
        samsung_layout.addLayout(samsung_options)
        self.samsung_progress=QProgressBar()
        self.samsung_progress.setRange(0,100)
        self.samsung_progress.hide()
        samsung_layout.addWidget(self.samsung_progress)
        self.samsung_detail=QLabel('')
        self.samsung_detail.setTextFormat(Qt.PlainText)
        self.samsung_detail.setWordWrap(True)
        samsung_layout.addWidget(self.samsung_detail)
        diagnostic_tools=ResponsiveRow(root)
        self.screenshot_button=QPushButton('OCR görüntüsünü kaydet')
        self.screenshot_button.clicked.connect(self.export_image)
        self.diagnostics_button=QPushButton('Tanılamayı kaydet')
        self.diagnostics_button.clicked.connect(self.export_diagnostics)
        self.open_logs_button=QPushButton('Günlük klasörünü aç')
        self.open_logs_button.clicked.connect(self.open_logs)
        for button in (self.screenshot_button,self.diagnostics_button,self.open_logs_button):diagnostic_tools.addWidget(button)
        layout.addLayout(diagnostic_tools)
        self.export_text=QCheckBox('Tanılama kaydına okunan metni de ekle')
        self.export_text.setToolTip('JSON dosyasına İngilizce OCR metni ve Türkçe çeviriyi ekler; görüntü eklemez.')
        layout.addWidget(self.export_text)
        self.ui_sounds = QCheckBox('Menü sesleri')
        self.ui_sounds.setChecked(self.settings.values.get('ui_sounds',False))
        self.ui_sounds.setToolTip('Ekran değiştirirken kısa ve düşük sesli bir bildirim çalar.')
        self.reduced_motion = QCheckBox('Ekran geçişlerinde hareketi azalt')
        self.reduced_motion.setChecked(self.settings.values.get('reduced_motion',system_reduced_motion()))
        layout.addWidget(self.ui_sounds)
        layout.addWidget(self.reduced_motion)
        self.status = QLabel('Önce ekrandaki İngilizce altyazı bölgesini seçin.')
        self.status.setTextFormat(Qt.PlainText)
        if self.settings.warnings:
            self.status.setText(' '.join(self.settings.warnings))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        self.target = QPlainTextEdit()
        self.target.setReadOnly(True)
        root.setObjectName('workspace')
        layout.addStretch()
        samsung_layout.addStretch()
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setAccessibleName('Ayar bölümleri')
        for page, title in ((root,'Çeviri'),(tv_page,'TV bağlantısı'),(samsung_page,'Samsung')):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.settings_tabs.addTab(scroll,title)
        self.console=ConsoleUI(self,self.settings_tabs,self.source,self.target,self.status,
                               (self.select,self.preview_button,self.start,self.pause_button,self.stop),APP_VERSION,self.import_profile)
        self.console.sound.set_enabled(self.ui_sounds.isChecked())
        self.console.pages.reduced_motion = self.reduced_motion.isChecked()
        self.ui_sounds.toggled.connect(self.presentation_changed)
        self.reduced_motion.toggled.connect(self.presentation_changed)
        self.console.set_games(self._game_choices)
        self.console.source_requested.connect(self.open_source)
        self.console.game_requested.connect(self.open_game)
        self.console.navigation_requested.connect(self.navigate_console)
        self.console.preferences_opening.connect(self.cancel_selection)
        self.console.about_requested.connect(self.show_about)
        self.console.appearance_requested.connect(self.edit_appearance)
        console_scroll=QScrollArea()
        console_scroll.setWidgetResizable(True)
        console_scroll.setFrameShape(QScrollArea.NoFrame)
        console_scroll.setWidget(self.console)
        self.setCentralWidget(console_scroll)
        self.setStyleSheet(CONSOLE_STYLE)
        self.select.clicked.connect(lambda: self.choose())
        self.start.clicked.connect(self.request_start)
        self.stop.clicked.connect(self.halt)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.selection_scope.currentIndexChanged.connect(self.mode_changed)
        self.band.valueChanged.connect(self.mode_changed)
        self.font_size.valueChanged.connect(self.appearance_changed)
        self.dialogue.toggled.connect(self.appearance_changed)
        self.caption_mode.currentIndexChanged.connect(self.appearance_changed)
        self.ocr_quality.currentIndexChanged.connect(self.ocr_options_changed)
        self.ocr_interval.valueChanged.connect(self.ocr_options_changed)
        self.fallback.toggled.connect(self.worker_options_changed)
        self.ignore_speaker.toggled.connect(self.worker_options_changed)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)
        restore_issues=self.restore_areas()
        self.hud_enabled.clicked.connect(self.save_hud_preference)
        self._application_connections.append(QApplication.instance().screenAdded.connect(self.screen_added))
        self._application_connections.append(QApplication.instance().screenRemoved.connect(self.screen_removed))
        for screen in QApplication.screens():
            self.watch_screen(screen)
        self.update_mode()
        self.poll()
        if restore_issues:
            self.status.setText(' '.join(restore_issues))

    def presentation_changed(self):
        self.console.sound.set_enabled(self.ui_sounds.isChecked())
        self.console.pages.reduced_motion = self.reduced_motion.isChecked()
        if self.reduced_motion.isChecked():self.console.pages.finish_transition()
        try:
            self.settings.save(ui_sounds=self.ui_sounds.isChecked(),reduced_motion=self.reduced_motion.isChecked())
        except (OSError,ValueError) as exc:
            self.status.setText('Arayüz tercihi kaydedilemedi: '+str(exc))

    def source_change_allowed(self):
        return not (self.closing or self._cleanup_failed or self.selector is not None or self.import_busy
                    or self._navigation_pending is not None or self.reselect_pending
                    or (self.worker and self.worker.is_alive()))

    def navigate_console(self,page):
        if page not in ('home','profiles','games','work','back'):
            raise ValueError('Bilinmeyen ekran.')
        if self.closing or self.selector is not None or self._navigation_pending is not None:return
        if page=='back' and self.startup is not None and not self.startup.gate.is_set() and self.worker and self.worker.is_alive():
            self.halt();self.poll();return
        if page=='back':
            if self.console.page=='work':
                page='home' if self.mode.currentData()=='movie' else 'games' if self.profile.currentData() else 'profiles'
            else:
                page='home'
        if self.worker and self.worker.is_alive():
            if self.stop_event.is_set():return
            self._navigation_pending=page
            self.halt()
            self.poll()
        else:
            if page!='work':self.cancel_selection()
            self.console.navigate(page)

    def open_source(self,source):
        if source not in ('single','dialogue','movie'):
            raise ValueError('Bilinmeyen çeviri kaynağı.')
        if not self.source_change_allowed():return
        self.cancel_selection()
        self.console.canvas.set_preview()
        self.mode.setCurrentIndex(self.mode.findData('movie' if source=='movie' else 'screen'))
        if source!='movie':
            self.profile.setCurrentIndex(0)
            self.save_profile_selection()
            self.caption_mode.setCurrentIndex(self.caption_mode.findData(source))
        self.source.clear()
        self.target.clear()
        self.console.navigate('work')
        self.poll()

    def open_game(self,identity):
        if not self.source_change_allowed():return
        self.cancel_selection()
        self.console.canvas.set_preview()
        index=self.profile.findData(identity)
        if index<1 or not any(choice.identity==identity and choice.available for choice in self._game_choices):
            self.status.setText('Bu oyun profili listede bulunamadı; ayarlardan yeniden açın.')
            return
        self.mode.setCurrentIndex(self.mode.findData('screen'))
        self.profile.setCurrentIndex(index)
        self.save_profile_selection()
        self.source.clear()
        self.target.clear()
        self.console.navigate('work')
        self.poll()

    @property
    def selection(self):
        area=self._areas.get('subtitle')
        return area.logical if area is not None and 'subtitle' not in self._stale_areas else None

    @property
    def hud_region(self):
        area=self._areas.get('hud')
        return area.logical if area is not None and 'hud' not in self._stale_areas else None

    def update_mode(self):
        if self.worker and self.worker.is_alive():
            self.halt()
        movie = self.mode.currentData() == 'movie'
        full_video = movie and self.selection_scope.currentData() == 'video'
        self.selection_scope.setVisible(movie)
        self.band.setEnabled(full_video)
        self.band_label.setVisible(full_video)
        self.band.setVisible(full_video)
        self.select.setText('Video alanını seç' if full_video else 'Altyazı alanını seç')
        self.video_hint.setText(('Videonun tamamını seçin. Alt bant okunacak.' if full_video else
                               'İngilizce altyazı satırını çevreleyen alanı seçin. Seçtiğiniz alanın tamamı okunacak.') if movie else '')
        self.update_region()
        self.poll()

    def mode_changed(self):
        if self.closing:
            return
        self.cancel_selection()
        self.update_mode()
        try:
            self.settings.save(mode=self.mode.currentData(),selection_scope=self.selection_scope.currentData(),
                               video_band=self.band.value())
        except (ValueError,OSError) as exc:
            self.status.setText(f'Mod tercihi kaydedilemedi: {exc}')

    def ocr_options_changed(self):
        if self.closing:return
        self.cancel_selection()
        if self.worker and self.worker.is_alive():self.halt()
        try:
            self.settings.save(ocr_quality=self.ocr_quality.currentData(),ocr_interval=self.ocr_interval.value())
        except (ValueError,OSError) as exc:
            self.status.setText(f'OCR tercihi kaydedilemedi: {exc}')
        self.poll()

    def worker_options_changed(self):
        if self.closing:return
        self.cancel_selection()
        if self.worker and self.worker.is_alive():self.halt()
        try:self.settings.save(fallback=self.fallback.isChecked(),ignore_speaker=self.ignore_speaker.isChecked())
        except (ValueError,OSError) as exc:self.status.setText(f'Eşleştirme tercihi kaydedilemedi: {exc}')
        self.poll()

    def clear_diagnostics(self,state='kapalı'):
        self.diagnostics.clear()
        self.ocr_info.setText('Altyazı OCR: '+state)
        self.hud_ocr_info.setText('Görev OCR: '+(state if self.hud_enabled.isChecked() and self.mode.currentData()!='movie' else 'kapalı'))
        self.ocr_info.setToolTip('')
        self.hud_ocr_info.setToolTip('')
        self.translation_info.setText('Altyazı çevirisi: '+state)
        self.hud_translation_info.setText('Görev çevirisi: '+(state if self.hud_enabled.isChecked() and self.mode.currentData()!='movie' else 'kapalı'))
        self.translation_info.setToolTip('')
        self.hud_translation_info.setToolTip('')

    def received_observation(self,update):
        control=self.hud_control if update.role=='hud' else self.control
        if update.session!=self.session or not self.capture_active(control) or not control.current(update.revision):return
        self.diagnostics.accept(update)
        if isinstance(update.observation,TranslationObservation):
            info=update.observation.info
            label=self.hud_translation_info if update.role=='hud' else self.translation_info
            title='Görev' if update.role=='hud' else 'Altyazı'
            source={'profile':'oyun profili','model':{'cuda':'NVIDIA CUDA','cpu':'CPU'}.get(info.device,'model · cihaz ?'),
                    'unmatched':'profilde eşleşme yok'}.get(info.source,'kaynak ?')
            detail=f' · eşleşme %{info.match_percent:g}' if info.match_percent is not None else ''
            label.setText(f'{title} çevirisi · {source}{detail} · {info.elapsed_ms:.0f} ms'+(' · önbellek' if info.cached else ''))
            label.setToolTip('<p>'+html.escape(info.profile_kind or info.source)+('<br>CUDA kullanılamadığı için CPU kullanıldı.' if info.fallback else '')+'</p>')
            return
        reading=update.observation.reading
        label=self.hud_ocr_info if update.role=='hud' else self.ocr_info
        title='Görev' if update.role=='hud' else 'Altyazı'
        confidence=f'%{reading.confidence*100:.0f}' if reading.confidence is not None else 'güven ?'
        variant={'plain':'normal','light':'açık zemin','contrast':'kontrast','hud':'görev','uniform':'tek renkli yakalama'}.get(reading.variant,'yöntem ?')
        passes=str(len(reading.scans)) if reading.scans is not None else '?'
        freshness='yeni okuma' if update.observation.fresh else f'önbellek · {max(0,time.monotonic()-update.observation.last_read_at):.1f} s'
        label.setText(f'{title} OCR · {confidence} · {reading.elapsed_ms:.0f} ms · {variant} · {passes} geçiş · {freshness}'+(' · sonuç boş' if not reading.text else ''))
        label.setToolTip('<p>'+html.escape(reading.method)+'<br>Güven OCR modelinin tahminidir; çeviri doğruluğu oranı değildir. Süre son gerçek okumanındır.</p>')

    def update_region(self):
        previous=self.region
        if self.selection:
            scope = self.selection_scope.currentData() if self.mode.currentData() == 'movie' else 'subtitle'
            try:
                if self._areas['subtitle'].purpose!=scope:
                    raise ValueError('Seçili alan türü bu modla uyuşmuyor; bu mod için alanı yeniden seçin.')
                self.region = resolve_selection(self.selection, scope, self.band.value())
                self.status.setText(f'Okunacak alan hazır: {self.region}')
            except ValueError as exc:
                self.region = None
                self.status.setText(str(exc))
        else:
            self.region=None
        if self.region!=previous and hasattr(self,'console'):self.console.canvas.set_preview()

    def restore_areas(self):
        self._areas=dict(self.settings.regions)
        issues=list(self.settings.region_issues)
        for role,area in self._areas.items():
            try:
                area.resolve(QApplication.screens())
            except (ValueError,RuntimeError) as exc:
                self._stale_areas.add(role)
                issues.append(f'Kayıtlı {AREA_LABELS[role]} alanı kullanılamıyor: {exc}')
                continue
            if role=='hud':
                self.hud_text.setText(f'HUD: {area.logical}')
        self.hud_enabled.setChecked(bool(self.hud_region) and self.settings.values.get('hud_enabled',False))
        return issues

    def watch_screen(self,screen):
        if screen in self._screen_connections:
            return
        connections=self._screen_connections[screen]=[]
        for signal in (screen.geometryChanged,screen.logicalDotsPerInchChanged,screen.physicalDotsPerInchChanged):
            connections.append(signal.connect(self.topology_changed))

    def save_hud_preference(self):
        if self.closing:
            return
        try:
            self.settings.save(hud_enabled=self.hud_enabled.isChecked())
        except (ValueError,OSError) as exc:
            self.status.setText(f'HUD tercihi kaydedilemedi: {exc}')

    def screen_added(self,screen):
        if self.closing:
            return
        self.watch_screen(screen)
        self.topology_changed()

    def screen_removed(self,screen):
        try:
            self.unwatch_screen(screen)
        finally:
            self.topology_changed()

    @staticmethod
    def disconnect_connections(connections):
        for connection in tuple(connections):
            if not connection or QObject.disconnect(connection) or not connection:
                connections.remove(connection)
        return not connections

    def unwatch_screen(self,screen):
        if screen not in self._screen_connections:
            return True
        if self.disconnect_connections(self._screen_connections[screen]):
            del self._screen_connections[screen]
            return True
        return False

    def topology_changed(self,*args):
        if self.closing:
            return
        self.cancel_selection()
        self.validate_areas(native=True)

    def validate_areas(self,*,native=False):
        screens=QApplication.screens()
        issues=[]
        for role,area in self._areas.items():
            if role in self._stale_areas:
                continue
            try:
                area.resolve(screens)
            except (ValueError,RuntimeError) as exc:
                self.invalidate_area(role)
                issues.append(f'{AREA_LABELS[role]}: {exc}')
        if not issues and self.worker and self.worker.is_alive() and self._capture_plan is not None:
            try:
                self._capture_plan.validate(screens,capture_region if native else None)
            except CaptureBindingChanged as exc:
                self.invalidate_area(exc.role)
                issues.append(str(exc))
        if issues:
            self.cancel_selection()
            if self.worker and self.worker.is_alive():
                self.halt()
            self.overlay.hide()
            self.hud_overlay.hide()
            self.target.clear()
            self.source.clear()
            self.status.setText('Ekran alanı değişti. ' + ' '.join(issues))
        return not issues

    def invalidate_area(self,role):
        self._stale_areas.add(role)
        if role=='subtitle':
            self.region=None
            self.console.canvas.set_preview()
        else:
            self.hud_enabled.setChecked(False)

    def appearance_changed(self):
        try:
            self.settings.save(font_size=self.font_size.value(), dialogue=self.dialogue.isChecked(),
                               overlay_offset_version=1,
                               caption_mode=self.caption_mode.currentData(),
                               **{'hud_'+key:value for key,value in self.hud_layout.items()},
                               **{'overlay_'+key:value for key,value in self.overlay_style.items()})
        except (ValueError, OSError) as exc:
            self.status.setText(f'Görünüm ayarı kaydedilemedi: {exc}')
        self.refresh_overlay()
        self.publish_caption()
        self.poll()

    def edit_hud_appearance(self):
        dialog=QDialog(self)
        dialog.setWindowTitle('Görev görünümü')
        form=QFormLayout(dialog)
        fields={}
        for key,title,low,high in (('x_offset','Yatay · + sağa (10px)',-40,40),
                                   ('y_offset','Dikey · + yukarı (10px)',-40,40),('scale','Ölçek (%)',70,150)):
            control=QSpinBox()
            control.setRange(low,high)
            control.setValue(self.hud_layout[key])
            fields[key]=control
            form.addRow(title,control)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('Kaydet')
        buttons.button(QDialogButtonBox.Cancel).setText('Vazgeç')
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if self.exec_capture_safe_dialog(dialog)==QDialog.Accepted:
            self.hud_layout={key:control.value() for key,control in fields.items()}
            self.hud_overlay.configure_layout(**self.hud_layout)
            self.appearance_changed()

    def edit_appearance(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Altyazı')
        form = QFormLayout(dialog)
        sample=QLabel('Hikâyede kal.')
        sample.setObjectName('appearanceSample')
        sample.setTextFormat(Qt.PlainText);sample.setAlignment(Qt.AlignCenter)
        sample.setMinimumHeight(110)
        form.addRow(sample)
        font_size=QSpinBox()
        font_size.setObjectName('appearanceFont')
        font_size.setRange(14,64);font_size.setValue(self.font_size.value())
        form.addRow('Yazı boyutu',font_size)
        position = QComboBox()
        for title, value in (('Otomatik güvenli konum','auto'),('Altyazı alanının üstü','above_region'),
                             ('Ekranın üstü','top'),('Ekranın altı','bottom')):
            position.addItem(title,value)
        position.setCurrentIndex(position.findData(self.overlay_style['position']))
        form.addRow('Konum', position)
        spins = {}
        for key,title,low,high in (('opacity','Arka plan opaklığı (%)',0,100),
                                   ('stroke','Yazı konturu',0,5),('y_offset','Dikey · + yukarı (10px)',-40,40)):
            spin = QDoubleSpinBox() if key=='y_offset' else QSpinBox()
            if key=='y_offset':
                spin.setDecimals(1)
                spin.setSingleStep(1)
            spin.setRange(low,high)
            spin.setObjectName('appearance'+key.title())
            spin.setValue(self.overlay_style[key])
            spins[key] = spin
            form.addRow(title,spin)
        color = [self.overlay_style['color']]
        color_button = QPushButton(color[0])
        color_button.setObjectName('appearanceColor')
        def update_sample():
            font=QFont('Segoe UI');font.setPixelSize(min(34,font_size.value()));font.setBold(True)
            sample.setFont(font)
            r,g,b=BACKGROUND_RGB
            sample.setStyleSheet(f'QLabel {{color:{color[0]};background:rgba({r},{g},{b},{round(255*spins["opacity"].value()/100)});border-radius:12px;padding:18px;}}')
        def pick_color():
            picker=QColorDialog(QColor(color[0]),dialog)
            picker.setOption(QColorDialog.DontUseNativeDialog,True)
            picker.setWindowTitle('Yazı rengini seç')
            if self.exec_capture_safe_dialog(picker)==QDialog.Accepted:
                color[0] = picker.currentColor().name()
                color_button.setText(color[0])
                apply_appearance()
        color_button.clicked.connect(pick_color)
        form.addRow('Yazı rengi',color_button)
        enabled = QCheckBox('Bilgisayarda altyazıyı göster')
        enabled.setChecked(self.overlay_style['enabled'])
        form.addRow(enabled)
        form.addRow(QLabel('Bilgisayar görünümünü kapatmak TV yayınını durdurmaz.'))
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText('Kapat')
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        def apply_appearance():
            if self.closing or self._cleanup_failed:return
            update_sample()
            candidate=dict(position=position.currentData(),color=color[0],enabled=enabled.isChecked(),
                           **{key:spin.value() for key,spin in spins.items()})
            if candidate==self.overlay_style and font_size.value()==self.font_size.value():return
            self.overlay.configure(**candidate)
            self.hud_overlay.configure(**{key:candidate[key] for key in ('color','opacity','stroke','enabled')})
            self.overlay_style=candidate
            with QSignalBlocker(self.font_size):self.font_size.setValue(font_size.value())
            self.appearance_changed()
        font_size.valueChanged.connect(apply_appearance)
        position.currentIndexChanged.connect(apply_appearance)
        enabled.toggled.connect(apply_appearance)
        for spin in spins.values():spin.valueChanged.connect(apply_appearance)
        update_sample()
        self.exec_capture_safe_dialog(dialog)

    def prepare_capture_safe_dialog(self,dialog):
        if self.closing or self._cleanup_failed:return False
        if self.startup is not None and not self.startup.gate.is_set() and not self.control.snapshot()[0]:
            self.status.setText('Modeller hazırlanıyor; hazır olunca ayarları açabilirsiniz.')
            return False
        self.cancel_selection()
        excluded=try_capture_exclusion(dialog)
        if self.capture_active() and not excluded:
            self.status.setText('Bu pencereyi açmak için önce çeviriyi durdurun; yakalamadan dışlanamadı.')
            return False
        return True

    def exec_capture_safe_dialog(self,dialog):
        """Run a one-shot dialog; dispose it after the caller reads its fields."""
        previous=QApplication.focusWidget()
        try:
            if not self.prepare_capture_safe_dialog(dialog):return QDialog.Rejected
            self.console.pages.finish_transition()
            return dialog.exec()
        finally:
            dialog.deleteLater()
            if previous is not None and not self.closing:
                try:
                    if previous.isVisible() and previous.isEnabled():previous.setFocus(Qt.OtherFocusReason)
                except RuntimeError:
                    pass  # The owning window may have closed during the modal event loop.

    def refresh_overlay(self):
        if not self.region or not self.capture_active():
            self.overlay.hide()
            self.hud_overlay.hide()
            return
        font = QFont('Segoe UI', self.font_size.value(), QFont.Bold)
        self.overlay.other_capture_regions=(QRect(*self.hud_region),) if self.hud_region and self.hud_enabled.isChecked() and self.mode.currentData()!='movie' else ()
        if self.overlay.font() != font:
            self.overlay.setFont(font)
        target = self.target.toPlainText()
        speaker,body = split_speaker(target)
        stacked = self.stacked_mode()
        rich = stacked or bool(speaker)
        text = (render_stack(self.captions,self.dialogue.isChecked(),self.font_size.value())
                if stacked and target else render_caption(Caption(speaker,body)) if speaker else target)
        if not self.overlay.present(text,self.region,rich=rich) and target and self.overlay.last_error:
            self.status.setText(self.overlay.last_error)
        self.refresh_hud()

    def refresh_hud(self):
        if not self.hud_region or not self.capture_active(self.hud_control):
            self.hud_overlay.hide()
            return
        self.hud_overlay.other_capture_regions=(QRect(*self.region),) if self.region else ()
        if not self.hud_overlay.present(self.current_hud,self.hud_region) and self.current_hud and self.hud_overlay.last_error:
            self.status.setText(self.hud_overlay.last_error)

    def open_profile(self):
        if not self.source_change_allowed():return
        path, _ = QFileDialog.getOpenFileName(self, 'Oyun profili seç', '', 'Oyun profili (*.sqlite)')
        if not path or self.import_busy:
            return
        self.import_busy = True
        self.status.setText('Profil kopyalanıyor ve tüm kayıtları doğrulanıyor…')
        def import_profile():
            try:
                entry = self.catalog.import_profile(path)
            except Exception as exc:
                self.events.profile_imported.emit(None, str(exc))
            else:
                self.events.profile_imported.emit(entry, None)
        self.import_worker = threading.Thread(target=import_profile, daemon=False)
        try:
            self.import_worker.start()
        except Exception as exc:
            self.import_busy = False
            self.status.setText(f'İçe aktarma başlatılamadı: {exc}')
        self.poll()

    def refresh_profiles(self, selected=''):
        self.profile.clear()
        self.profile.addItem('Canlı çeviri', '')
        choices=sorted((GameChoice.from_entry(entry) for entry in self.catalog.entries),key=lambda choice:choice.sort_key)
        for choice in choices:
            self.profile.addItem(choice.title, choice.identity)
            if choice.error:
                self.profile.setItemData(self.profile.count()-1, choice.tooltip, Qt.ToolTipRole)
        found = self.profile.findData(selected)
        if selected and found < 0:
            if not selected.startswith(('bundled:', 'imported:', 'external:')):
                try:
                    entry = self.catalog.legacy_external(selected)
                    selected = entry.identity
                    title = entry.title
                except (ValueError, OSError):
                    title = 'Önceki profil erişilemiyor: ' + selected
            else:
                title = 'Seçili profil bulunamadı: ' + selected
            self.profile.addItem(title, selected)
            found = self.profile.count() - 1
        self.profile.setCurrentIndex(max(0, found))
        self._game_choices=tuple(choices)
        if hasattr(self,'console'):
            self.console.set_games(self._game_choices)

    def profile_imported(self, entry, error):
        self.import_busy = False
        if self.import_worker and not self.import_worker.is_alive():
            self.import_worker.join()
            self.import_worker = None
        if error is not None:
            self.status.setText(f'Profil içe aktarılamadı: {error}')
        elif not self.closing:
            self.refresh_profiles(entry.identity)
            if self.save_profile_selection():
                self.status.setText(f'Profil hazır: {entry.title} · {entry.count} kayıt')
        self.poll()

    def save_profile_selection(self):
        try:
            self.settings.save(profile=self.profile.currentData())
        except (ValueError,OSError) as exc:
            self.status.setText(f'Profil seçimi kaydedilemedi: {exc}')
            return False
        return True

    def samsung_start(self, action):
        try:
            host=self.samsung.start(action,self.tv_host.text().strip(),self.tv.token if self.tv else '',
                                    renew=self.samsung_renew.isChecked())
            if action=='install':self.settings.save(samsung_host=host)
        except (ValueError,OSError) as exc:
            self.status.setText(str(exc))
        self.poll()

    def samsung_changed(self,state):
        selected=self.samsung_devices.currentData()
        self.samsung_devices.clear()
        self.samsung_devices.addItem('Bulunan TV’yi seç','')
        for tv in state.tvs:
            self.samsung_devices.addItem(f'{tv.name} · {tv.ip}',tv.ip)
            index=self.samsung_devices.count()-1
            self.samsung_devices.setItemData(index,f'{tv.model} · Geliştirici modu: '+('açık' if tv.dev_mode else 'kapalı' if tv.dev_mode is False else 'bilinmiyor'),Qt.ToolTipRole)
        self.samsung_devices.setCurrentIndex(max(0,self.samsung_devices.findData(selected)))
        details=[text for text in (state.error or state.text,state.hint,
                 ('Kapatma tamamlanamadı; iptali tekrar deneyin: '+state.cleanup_error) if state.cleanup_error else '',
                 'Günlük kapasitesi doldu; sonraki satırlar dosyaya yazılmadı.' if state.log_truncated else '',
                 ('Tizen '+state.tizen) if state.tizen else '') if text]
        self.samsung_detail.setText('\n'.join(details))
        self.samsung_progress.setVisible(self.samsung.busy and not state.cancelled and not state.error)
        if state.percent is None:self.samsung_progress.setRange(0,0)
        else:
            self.samsung_progress.setRange(0,100)
            self.samsung_progress.setValue(state.percent)
        self.samsung_login.setEnabled(bool(self.samsung.busy and state.url and not state.cancelled))

    def open_samsung_login(self):
        if not self.samsung.busy or not self.samsung.state.url:return
        if not QDesktopServices.openUrl(QUrl(self.samsung.state.url)):
            self.status.setText('Samsung giriş bağlantısı açılamadı; varsayılan tarayıcıyı kontrol edin.')

    def open_samsung_log(self):
        path=self.samsung.log_path
        if path is not None and path.is_file():
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                self.status.setText('Samsung günlüğü açılamadı: '+str(path))

    def toggle_tv(self):
        if self.tv:
            self.stop_tv()
            return
        if self.tv_cleanup and self.tv_cleanup.is_alive():
            return
        service = TV()
        self.tv = service
        try:
            service.start()
        except Exception as exc:
            self.tv_message(f'TV yayını açılamadı: {exc}')
            self.stop_tv()
            return
        self.tv_button.setText('TV yayınını kapat')
        self.tv_info.setText(f'TV tarayıcısında seçili adresi açın. Eşleştirme kodu: {service.token}')
        self.update_tv_addresses(service.connection_info())
        self.publish_caption()
        self.publish_current_hud()
        self.poll()

    def update_tv_addresses(self,info):
        if info is None:
            return
        import ipaddress
        addresses=set()
        if info.host=='0.0.0.0':
            from PySide6.QtNetwork import QNetworkInterface,QAbstractSocket
            for interface in QNetworkInterface.allInterfaces():
                flags=interface.flags()
                if not flags&QNetworkInterface.IsUp or not flags&QNetworkInterface.IsRunning:
                    continue
                for entry in interface.addressEntries():
                    address=entry.ip()
                    if address.protocol()!=QAbstractSocket.IPv4Protocol:
                        continue
                    value=ipaddress.IPv4Address(address.toString())
                    if not (value.is_loopback or value.is_unspecified or value.is_multicast):
                        addresses.add(str(value))
        else:
            addresses.add(info.host)
        addresses=sorted(addresses,key=ipaddress.IPv4Address)
        if info.host=='0.0.0.0':
            addresses.append('127.0.0.1')
        selected=self.tv_urls.currentData()
        self.tv_urls.clear()
        available=[]
        for host in addresses:
            url=f'http://{host}:{info.http_port}'
            label=('Bu bilgisayar · ' if ipaddress.IPv4Address(host).is_loopback else '')+url
            self.tv_urls.addItem(label,url)
            self.tv_urls.setItemData(self.tv_urls.count()-1,True,Qt.UserRole+1)
            available.append(url)
        if selected and selected not in available:
            self.tv_urls.addItem('Adres artık etkin değil · '+selected,selected)
            self.tv_urls.setItemData(self.tv_urls.count()-1,False,Qt.UserRole+1)
        if selected:
            self.tv_urls.setCurrentIndex(self.tv_urls.findData(selected))
        self.tv_address_refresh_at=time.monotonic()+10

    def tv_message(self,text):
        self.status.setText(text)
        self.tv_feedback.setText(text)

    def copy_tv_code(self):
        if not self.tv or self.tv_closing or self.tv.connection_info() is None:
            self.tv_message('Önce TV yayınını açın.')
            return
        QApplication.clipboard().setText(self.tv.token)
        self.tv_message('Eşleştirme kodu kopyalandı.')

    def copy_tv_address(self):
        info=self.tv.connection_info() if self.tv and not self.tv_closing else None
        if info is None:
            self.tv_message('Önce TV yayınını açın.')
            return
        self.update_tv_addresses(info)
        if not self.tv_urls.currentData(Qt.UserRole+1):
            self.tv_message('Seçili adres artık etkin değil; listeden TV ile aynı ağdaki adresi seçin.')
            return
        QApplication.clipboard().setText(self.tv_urls.currentData())
        self.tv_message('TV alıcı adresi kopyalandı. TV ve bilgisayar aynı ağda olmalı.')

    def toggle_tv_pairing(self):
        if not self.tv or self.tv_closing or self.tv.connection_info() is None:
            self.tv_message('Önce TV yayınını açın.')
            return
        if self.tv.pairing_remaining()>0:
            self.tv.close_pairing()
            self.tv_message('Otomatik eşleştirme kapatıldı; yeni alıcılar kodu elle girmeli.')
        else:
            self.tv.open_pairing()
            self.tv_message('Otomatik eşleştirme 2 dakika açık. Aynı ağdaki alıcılar kodu kendiliğinden alabilir.')
        self.poll()

    def test_tv_caption(self):
        try:
            if not self.tv or self.tv_closing:
                raise ValueError('Önce TV yayınını açın.')
            self.tv.test_caption()
        except ValueError as exc:
            self.tv_message(str(exc))
        else:
            self.tv_message('Test altyazısı bağlı cihazlara yayınlandı.')

    def stop_tv(self):
        if self.tv and not self.tv_closing:
            service = self.tv
            self.tv_closing = True
            self.tv_stop_error = None
            def close():
                try:
                    service.close()
                except Exception as exc:
                    self.events.tv_closed.emit(service, str(exc))
                else:
                    self.events.tv_closed.emit(service, None)
            self.tv_cleanup = threading.Thread(target=close, daemon=False)
            try:
                self.tv_cleanup.start()
            except Exception as exc:
                self.tv_closed(service, str(exc))
                return
            self.tv_info.setText('TV yayını kapanıyor…')

    def tv_closed(self, service, error):
        if self.tv is not service:
            return
        self.tv_closing = False
        if error is not None:
            self.tv_stop_error = error
            self.closing = False
            self.tv_info.setText(f'TV tamamen kapanamadı: {error}')
            self.tv_button.setText('Kapatmayı tekrar dene')
        else:
            self.tv = None
            self.tv_stop_error = None
            self.tv_info.setText('TV yayını kapalı.')
            self.tv_button.setText('TV yayınını aç')
            self.tv_urls.clear()

    def choose(self, channel='subtitle',*,start_after=False):
        if channel not in ('subtitle','hud'):
            raise ValueError('Bilinmeyen alan seçimi.')
        if type(start_after) is not bool or start_after and channel!='subtitle':
            raise ValueError('Alan seçimi başlatma tercihi geçersiz.')
        if self.closing or (self.worker and self.worker.is_alive()):
            return
        self.console.preferences.hide()
        self.console.navigate('work')
        self.cancel_selection()
        self._selection_restore=(self.isVisible(),self.windowState())
        if self.isVisible():self.hide()
        self._selection_generation+=1
        context=(self._selection_generation,channel,self.session,desktop_signature(QApplication.screens()),start_after)
        try:selector=Selector()
        except Exception as exc:
            self.cancel_selection()
            self.status.setText(f'Alan seçimi açılamadı: {exc}')
            return
        self.selector=selector
        self._selection_context=context
        selector.selected.connect(lambda region:self.selection_result(context,region))
        selector.finished.connect(lambda:self.selection_finished(context))
        selector.show()
        selector.raise_()
        selector.activateWindow()
        self.poll()

    def cancel_selection(self):
        selector=self.selector
        self.selector=None
        self._selection_context=None
        self._selection_generation+=1
        if selector is not None:
            selector.close()
        restore,self._selection_restore=self._selection_restore,None
        if restore is not None and restore[0] and not self.closing:
            self.setWindowState(restore[1])
            self.show()

    def selection_finished(self,context):
        if self._selection_context==context:
            self.cancel_selection()
            self.poll()

    def selection_result(self,context,region):
        if self._selection_context!=context:
            return
        eligible=(not self.closing and not (self.worker and self.worker.is_alive())
                  and context[2]==self.session and context[3]==desktop_signature(QApplication.screens()))
        self.cancel_selection()
        if eligible:
            accepted=self.accept_area(context[1],region)
            if accepted and context[1]=='subtitle':
                generation=self._selection_generation
                QTimer.singleShot(100,self,lambda:self.complete_selection(generation,context[2],context[3],context[4]))
        else:
            self.status.setText('Eski alan seçimi kullanılmadı; alanı yeniden seçin.')
        self.poll()

    def complete_selection(self,generation,session,desktop,start_after):
        if (self.closing or generation!=self._selection_generation or session!=self.session
                or desktop!=desktop_signature(QApplication.screens()) or not self.source_change_allowed()):return
        self.preview(cancel_pending=False)
        if start_after:self.begin()

    def request_start(self):
        if not self.source_change_allowed():return
        if self.region is None:self.choose(start_after=True)
        else:self.begin()

    def accept_area(self,role,region):
        if role not in ('subtitle','hud'):
            raise ValueError('Bilinmeyen alan seçimi.')
        if self.closing or (self.worker and self.worker.is_alive()) or self.selector is not None:
            return False
        try:
            purpose=role
            if role=='subtitle' and self.mode.currentData()=='movie':
                purpose=self.selection_scope.currentData()
            area=SelectedArea.create(region,QApplication.screens(),purpose=purpose)
        except (ValueError,RuntimeError) as exc:
            self.status.setText(str(exc))
            return False
        self._areas[role]=area
        self._stale_areas.discard(role)
        if role=='subtitle':
            self.console.canvas.set_preview()
            self.update_region()
        else:
            self.hud_text.setText(f'HUD: {area.logical}')
            self.hud_enabled.setChecked(True)
        try:
            self.settings.save(regions=save_areas(self._areas),hud_enabled=self.hud_enabled.isChecked(),
                               mode=self.mode.currentData(),selection_scope=self.selection_scope.currentData(),
                               video_band=self.band.value())
        except (ValueError,OSError) as exc:
            self.status.setText(f'Alan bu oturumda hazır, fakat kaydedilemedi: {exc}')
        self.poll()
        return True

    def chosen_hud(self, region):
        return self.accept_area('hud',region)

    def chosen(self, region):
        return self.accept_area('subtitle',region)

    def showEvent(self,event):
        super().showEvent(event)
        try_capture_exclusion(self)

    def capture_image(self):
        if self.closing or self._cleanup_failed or self.selector is not None or self.region is None:
            raise ValueError('Önce geçerli bir altyazı alanı seçin.')
        if not self.validate_areas(native=True):raise ValueError('Ekran alanı değişti; yeniden seçin.')
        logical=self.region
        signature=desktop_signature(QApplication.screens())
        physical=capture_region(logical,QApplication.screens())
        capture=QRect(*logical)
        for widget in QApplication.topLevelWidgets():
            owned=widget is self or self.isAncestorOf(widget) or widget in (self.overlay,self.hud_overlay)
            if owned and widget.isVisible() and not widget.isMinimized() and widget.frameGeometry().intersects(capture):
                if not try_capture_exclusion(widget):
                    raise OSError('Önizleme için uygulama penceresini seçili alanın dışına taşıyın; ekran yakalama dışlaması doğrulanamadı.')
        captured=grab_image(logical,physical)
        if (self.region!=logical or signature!=desktop_signature(QApplication.screens())
                or capture_region(logical,QApplication.screens())!=physical):
            raise OSError('Görüntü alınırken ekran eşlemesi değişti; görüntü kullanılmadı.')
        return captured

    def preview(self,*,cancel_pending=True):
        if cancel_pending:self.cancel_selection()
        if self.worker and self.worker.is_alive():return
        try:
            captured=self.capture_image()
            self.console.canvas.set_preview(captured.image)
            self.console.navigate('work')
            self.status.setText('Son önizleme: OCR bu alanı okuyacak. Görüntü yalnız bellekte tutuluyor.')
        except (ValueError,OSError,RuntimeError) as exc:
            self.console.canvas.set_preview()
            self.status.setText(f'Alan önizlenemedi: {exc}')

    def diagnostic_snapshot(self,*,include_text=False):
        now=time.monotonic()
        observations=[]
        for update in self.diagnostics.snapshot():
            value=diagnostic_record(update,now,include_text=include_text)
            control=self.hud_control if update.role=='hud' else self.control
            value['current_context']=bool(update.session==self.session and self.capture_active(control)
                                          and control.current(update.revision))
            observations.append(value)
        result=dict(format='altyazi-atolyesi/diagnostics-v2',app_version=APP_VERSION,
                    generated_utc=datetime.now(timezone.utc).isoformat(),python_version=sys.version.split()[0],
                    session=self.session,running=self.capture_active(),paused=self.control.snapshot()[0],
                    mode=self.mode.currentData(),profile=self.profile.currentData(),ignore_speaker=self.ignore_speaker.isChecked(),
                    ocr_quality=self.ocr_quality.currentData(),interval_seconds=self.ocr_interval.value(),
                    logical_ocr_region=self.region,saved_areas=save_areas(self._areas),observations=observations,
                    includes_text=include_text,includes_image=False)
        result['startup']=(dict(components=dict(self.startup.components),capture_released=self.startup.gate.is_set())
                           if self.startup is not None else None)
        result['capture_error_present']=bool(self.last_capture_error)
        result['application_log']=(dict(path=str(self.event_log.path),stream_owned=self.event_log.stream is not None,
                                       confirmed_written_bytes=self.event_log.written,
                                       truncated=self.event_log.truncated,error_present=bool(self.event_log.error))
                                   if self.event_log is not None else None)
        if include_text:
            texts=dict(source=self.source.toPlainText(),translation=self.target.toPlainText())
            if any(len(text)>MAX_CAPTION for text in texts.values()):raise ValueError('Metin dışa aktarma kapasitesini aşıyor.')
            result['captions']=texts
            result['capture_error_text']=self.last_capture_error
        return result

    def export_image(self):
        self.cancel_selection()
        try:
            captured=self.capture_image()
            filename,_=QFileDialog.getSaveFileName(self,'OCR görüntüsünü kaydet',
                         str(self.settings.path.parent/'ocr_debug.png'),'PNG görüntüsü (*.png)')
            if not filename:return
            save_image(filename,captured)
            self.status.setText('OCR görüntüsü kaydedildi: '+filename)
        except (ValueError,OSError,RuntimeError) as exc:self.status.setText(f'Görüntü kaydedilemedi: {exc}')

    def export_diagnostics(self):
        self.cancel_selection()
        try:
            snapshot=self.diagnostic_snapshot(include_text=self.export_text.isChecked())
            filename,_=QFileDialog.getSaveFileName(self,'Tanılamayı kaydet',
                         str(self.settings.path.parent/'diagnostics.json'),'JSON kaydı (*.json)')
            if not filename:return
            save_json(filename,snapshot)
            self.status.setText('Tanılama kaydedildi: '+filename)
        except (ValueError,OSError,RuntimeError) as exc:self.status.setText(f'Tanılama kaydedilemedi: {exc}')

    def open_logs(self):
        self.cancel_selection()
        try:
            folder=self.settings.path.parent/'logs'
            folder.mkdir(parents=True,exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve()))):
                raise OSError('Dosya yöneticisi açılamadı: '+str(folder))
        except OSError as exc:self.status.setText(str(exc))

    def record_event(self,event,**fields):
        if self.event_log is not None:self.event_log.record(event,**fields)

    def show_about(self):
        if self.closing or self._cleanup_failed:return
        if self.startup is not None and not self.startup.gate.is_set() and self.worker and self.worker.is_alive():return
        self.cancel_selection()
        dialog=QDialog(self)
        dialog.setWindowTitle('MOZKAN Live Sub hakkında')
        layout=QVBoxLayout(dialog)
        texts=[f'MOZKAN Live Sub {APP_VERSION}',
               'Canlı OCR, çevrimdışı İngilizce–Türkçe çeviri ve yerel oyun profilleri.',
               'Tek replik güncel altyazıyı gösterir. Diyalog konuşmacı ve önceki repliği birlikte gösterir. Oyun profilleri canlı diyalog ayarından bağımsızdır.',
               'Uygulama hesabı veya lisans sunucusu gerekmez. TV yayını yerel ağdadır; isteğe bağlı Samsung kurulumu kendi cihaz hizmetini kullanır.',
               'Uygulama günlüğü yalnız sürüm, oturum, yükleme adımları ve hata türlerini tutar. Metinler ve görüntüler yalnız elle dışa aktarılır.']
        if self.event_log is not None:
            texts.append('Günlük: '+str(self.event_log.path))
            if self.event_log.error:texts.append('Günlük yazılamadı: '+self.event_log.error)
            if self.event_log.truncated:texts.append('Bu çalışma günlüğünün kapasitesi doldu.')
        else:texts.append('Bu oturumda uygulama dosya günlüğü etkin değil.')
        for text in texts:
            label=QLabel(text);label.setTextFormat(Qt.PlainText);label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(label)
        row=QHBoxLayout()
        for title,action in [('Günlükleri aç',self.open_logs),('OCR görüntüsü',self.export_image),('Tanılamayı kaydet',self.export_diagnostics)]:
            button=QPushButton(title);button.clicked.connect(action);row.addWidget(button)
        layout.addLayout(row)
        buttons=QDialogButtonBox(QDialogButtonBox.Close);buttons.rejected.connect(dialog.reject)
        buttons.button(QDialogButtonBox.Close).setText('Kapat')
        layout.addWidget(buttons)
        dialog.resize(620,520)
        dialog.setModal(True)
        self.exec_capture_safe_dialog(dialog)

    def capture_progress(self,session,progress):
        if (session!=self.session or self.stop_event.is_set() or self.startup is None
                or self.startup.session!=session):return
        if not isinstance(progress,CaptureProgress):
            self.halt();self.status.setText('Geçersiz hazırlık bildirimi; çeviri durduruldu.');return
        self.startup.observe(progress)
        self.record_event('resource',session=session,component=progress.component,status=progress.status)
        if self.startup.ready:QTimer.singleShot(0,self,lambda:self.finish_launch(session))
        self.poll()

    def capture_failure(self,session,role,failure):
        if not isinstance(failure,CaptureFailure):return
        kind=failure.error_class
        self.record_event('capture_error',session=session,role=role,error_class=kind if len(kind)<=128 and kind.isidentifier() else None)
        if session!=self.session:return
        self.last_capture_error=('Görev: ' if role=='hud' else '')+failure.message
        self.status.setText('Hata: '+self.last_capture_error)
        if role=='hud':
            self.hud_control.pause(True)
            self.current_hud=''
            self.hud_overlay.hide()
            self.hud_text.setText('Görev kanalı durdu; ana altyazı devam ediyor.')
            self.hud_ocr_info.setText('Görev OCR: hata')
            self.hud_translation_info.setText('Görev çevirisi: durduruldu')
            self.hud_translation_info.setToolTip('')
            if self.tv:self.tv.publish_hud('')

    def prepare_capture_visibility(self):
        self.console.preferences.hide()
        if self.region is not None and self.isVisible() and self.frameGeometry().intersects(QRect(*self.region)):
            self.showMinimized()

    def finish_launch(self,session):
        if (session!=self.session or self.closing or self.stop_event.is_set() or self.startup is None
                or self.startup.session!=session or not self.startup.ready or self.control.snapshot()[0]):return
        self.prepare_capture_visibility()
        self.startup.gate.set()
        self.poll()

    def begin(self):
        if not self.source_change_allowed() or self.region is None:
            return
        if not self.validate_areas(native=True):
            return
        movie = self.mode.currentData() == 'movie'
        try:
            if self.hud_enabled.isChecked() and not movie:
                if not self.hud_region:
                    raise ValueError('Önce HUD bölgesini seçin.')
            plan=CapturePlan.create(self.region,self.hud_region if self.hud_enabled.isChecked() and not movie else None,
                                    QApplication.screens(),capture_region)
            physical_region=plan.subtitle.physical
            physical_hud=plan.hud.physical if plan.hud is not None else None
        except (ValueError, OSError,RuntimeError) as exc:
            self.status.setText(str(exc))
            return
        self.session += 1
        logging.getLogger('atolye').info('capture_start session=%s scope=%s logical=%s physical=%s movie=%s',
                                       self.session, self.selection_scope.currentData(), self.region, physical_region, movie)
        self.captions.clear()
        profile_identity = self.profile.currentData()
        profile_path = ''
        selected_fallback = self.fallback.isChecked()
        fallback = selected_fallback
        if movie:
            fallback, physical_hud = True, None
        elif profile_identity:
            try:
                profile_path = str(self.catalog.resolve(profile_identity))
            except (ValueError, OSError) as exc:
                self.status.setText(f'Seçili profil kullanılamıyor: {exc}')
                return
        try:
            self.settings.save(profile=profile_identity, fallback=selected_fallback,
                               ignore_speaker=self.ignore_speaker.isChecked(),
                               dialogue=self.dialogue.isChecked(), font_size=self.font_size.value(),
                               caption_mode=self.caption_mode.currentData(),
                               mode=self.mode.currentData(), video_band=self.band.value(),
                               hud_enabled=self.hud_enabled.isChecked(),
                               selection_scope=self.selection_scope.currentData())
        except (ValueError, OSError) as exc:
            self.status.setText(f'Ayarlar kaydedilemedi: {exc}')
            return
        self.stop_event = threading.Event()
        self.startup=Startup(self.session)
        self._hud_stop=ChildStop(self.stop_event) if physical_hud is not None else None
        self.last_capture_error=''
        self.record_event('capture_start',session=self.session,mode=self.mode.currentData(),profile=profile_identity)
        self._capture_plan=plan
        self.clear_diagnostics('bekleniyor')
        self.source.clear()
        self.target.clear()
        self.current_hud = ''
        self.control = CaptureControl()
        self.hud_control = CaptureControl()
        self.worker = threading.Thread(target=self.run, args=(self.session, physical_region,
                                                              self.stop_event, profile_path, fallback, physical_hud, movie,self.stacked_mode(),
                                                              self.ocr_quality.currentData(),self.ocr_interval.value(),self.ignore_speaker.isChecked(),self.startup,self._hud_stop), daemon=False)
        self.worker.start()
        self.console.preferences.hide()
        self.console.navigate('work')
        self.poll()

    def halt(self):
        if self.worker is not None and self.worker.is_alive():
            self.record_event('stop_requested',session=self.startup.session if self.startup is not None else self.session)
        self.cancel_selection()
        self.clear_diagnostics()
        self.session += 1
        self.stop_event.set()
        self.status.setText('Çeviri durduruluyor…' if self.worker and self.worker.is_alive() else 'Çeviri kapalı.')
        self.overlay.hide()
        self.hud_overlay.hide()
        self.current_hud = ''
        self.captions.clear()
        if self.tv:
            self.tv.publish('')
            self.tv.publish_hud('')

    def toggle_pause(self):
        if not self.worker or not self.worker.is_alive() or self.stop_event.is_set():
            return
        paused = not self.control.snapshot()[0]
        if not paused and self.startup is not None and self.startup.ready:self.prepare_capture_visibility()
        self.control.pause(paused)
        self.hud_control.pause(paused)
        self.clear_diagnostics('duraklatıldı' if paused else 'bekleniyor')
        self.overlay.hide()
        self.hud_overlay.hide()
        self.captions.clear()
        self.current_hud = ''
        self.target.clear()
        if self.tv:
            self.tv.publish('')
            self.tv.publish_hud('')
        self.status.setText('Çeviri duraklatıldı. Devam et ile aynı alandan sürdürebilirsiniz.' if paused else 'Çeviri devam ediyor; altyazı bekleniyor.')
        if not paused and self.startup is not None and self.startup.ready:self.finish_launch(self.session)
        self.poll()

    def reselect(self):
        if self.worker and self.worker.is_alive():
            self.reselect_pending = True
            self.halt()
            self.status.setText('Son işlem tamamlanınca yeni alan seçimi açılacak…')
        else:
            self.choose()

    def run(self, session, region, stop, profile_path='', fallback=True, hud_region=None, movie=False,stacked=False,
            quality='fast',interval=.15,ignore_speaker=True,startup=None,hud_stop=None):
        hud_worker = None
        def status(text):
            self.events.capture_message.emit(session, self.control.snapshot()[1], text, False)
        try:
            status('OCR ve çeviri modelleri hazırlanıyor…')
            if hud_region:
                hud_worker = threading.Thread(target=run_capture, kwargs=dict(
                    models=self.models, region=hud_region, stop=hud_stop if hud_stop is not None else ChildStop(stop),
                    output=lambda source, target: self.events.hud.emit(session, source, target, self.hud_control.snapshot()[1]),
                    status=lambda message: None, error=lambda _:None,
                    failure=lambda failure:self.events.failure.emit(session,'hud',failure),
                    interval=.55, control=self.hud_control, ocr_kind='hud',
                    prepare_model=True,
                    diagnostics=lambda observation,revision:self.diagnostics.post(DiagnosticUpdate(session,'hud',revision,observation))), daemon=False)
                hud_worker.start()
            run_capture(self.models, region, stop,
                        lambda source, target: self.events.output.emit(session, source, target, self.control.snapshot()[1]),
                        status, lambda _:None, profile_path, fallback,
                        movie=movie, control=self.control,stacked=stacked,quality=quality,interval=interval,
                        ignore_speaker=ignore_speaker,
                        prepare_model=True,progress=lambda update:self.events.progress.emit(session,update),
                        launch_gate=startup.gate if startup is not None else None,
                        failure=lambda failure:self.events.failure.emit(session,'subtitle',failure),
                        diagnostics=lambda observation,revision:self.diagnostics.post(DiagnosticUpdate(session,'subtitle',revision,observation)))
        finally:
            stop.set()
            if hud_worker:
                hud_worker.join()

    def capture_message(self, session, revision, text, error):
        if session != self.session:
            return
        if error:
            self.last_capture_error=text
            self.events.error.emit(text)
        elif not self.stop_event.is_set() and self.control.current(revision):
            self.status.setText(text)

    def received(self, session, source, target, revision=None):
        if session != self.session or self.stop_event.is_set():
            return
        if revision is not None and not self.control.current(revision):
            return
        self.source.setPlainText(source)
        try:
            target = ensure_speaker(source,target)
            if target:
                self.captions.add(target)
                if self.stacked_mode():
                    target = self.captions.current.full
            else:
                self.captions.clear()
        except (TypeError,ValueError) as exc:
            self.target.clear()
            self.captions.clear()
            self.overlay.hide()
            if self.tv:
                self.tv.publish('')
            self.status.setText(f'Altyazı gösterilemedi: {exc}')
            return
        self.target.setPlainText(target)
        self.refresh_overlay()
        self.publish_caption()

    def stacked_mode(self):
        return (self.mode.currentData()=='screen' and not self.profile.currentData()
                and self.caption_mode.currentData()=='dialogue')

    def capture_active(self,control=None):
        control = self.control if control is None else control
        if control is self.hud_control and self._hud_stop is not None and self._hud_stop.is_set():return False
        return bool(self.worker is not None and self.worker.is_alive() and not self.stop_event.is_set()
                    and not control.snapshot()[0])

    def publish_caption(self):
        if self.tv:
            target = self.target.toPlainText() if self.capture_active() else ''
            stack = self.captions.as_dict(self.dialogue.isChecked()) if target and self.stacked_mode() else None
            self.tv.publish(target, stack)

    def received_hud(self, session, source, target, revision=None):
        if session != self.session or self.stop_event.is_set():
            return
        if self._hud_stop is not None and self._hud_stop.is_set():return
        if revision is not None and not self.hud_control.current(revision):
            return
        if not isinstance(target,str) or len(target)>MAX_CAPTION:
            self.current_hud=''
            self.hud_text.setText('Görev metni görüntülenemedi.')
            self.hud_text.setToolTip('')
            self.hud_overlay.hide()
            if self.tv:
                self.tv.publish_hud('')
            self.status.setText(f'Görev çevirisi en fazla {MAX_CAPTION} karakter olmalı.')
            return
        self.current_hud = target
        visible=display_text(target)
        self.hud_text.setText(visible or 'HUD metni temizlendi')
        self.hud_text.setToolTip('<p>'+html.escape(visible).replace('\n','<br>')+'</p>' if visible else '')
        self.refresh_hud()
        self.publish_current_hud()

    def publish_current_hud(self):
        if not self.tv:
            return
        target=self.current_hud if self.capture_active(self.hud_control) else ''
        try:
            box=normalized_region(self.hud_region,QApplication.screens()) if target else None
            self.tv.publish_hud(target,box)
        except (ValueError,TypeError) as exc:
            self.tv.publish_hud('')
            self.status.setText(f'TV görev alanı gönderilemedi: {exc}')

    def retire_capture(self):
        if self.worker is None or self.worker.is_alive():return
        self.worker.join()
        self.record_event('capture_end',session=self.startup.session if self.startup is not None else self.session)
        self.worker = None
        self.startup=None
        self._hud_stop=None
        self._capture_plan=None
        self.clear_diagnostics()
        self.overlay.hide()
        self.hud_overlay.hide()
        if self.tv:
            self.tv.publish('')
            self.tv.publish_hud('')

    def poll(self):
        previous_primary=self.console.primary_action.currentWidget()
        primary_had_focus=previous_primary.hasFocus()
        completed_navigation=None
        if time.monotonic()>=self._topology_check_at:
            self._topology_check_at=time.monotonic()+1
            self.validate_areas(native=True)
        active = bool(self.worker and self.worker.is_alive())
        import_active = bool(self.import_worker and self.import_worker.is_alive())
        if self.import_worker is not None and not import_active:
            self.import_worker.join()
            self.import_worker = None
        self.retire_capture()
        if not active and self._navigation_pending is not None and not self.closing:
            completed_navigation,self._navigation_pending=self._navigation_pending,None
        for update in self.diagnostics.drain():self.received_observation(update)
        selecting=self.selector is not None
        self.ocr_quality.setEnabled(not active and not selecting and not self.closing)
        self.ocr_interval.setEnabled(not active and not selecting and not self.closing)
        self.start.setEnabled(self.source_change_allowed())
        self.start.setText('Alan seç ve başlat' if self.region is None else 'Çeviriyi başlat')
        self.screenshot_button.setEnabled(not selecting and not self.closing and self.region is not None)
        self.diagnostics_button.setEnabled(not self.closing)
        self.select.setEnabled(not active and not selecting)
        self.preview_button.setEnabled(not active and not selecting and self.region is not None)
        self.hud_select.setEnabled(not active)
        self.hud_enabled.setEnabled(not active)
        movie = self.mode.currentData() == 'movie'
        self.hud_select.setEnabled(not active and not selecting and not movie)
        self.hud_enabled.setEnabled(not active and not selecting and not movie)
        self.hud_appearance.setEnabled(not movie)
        self.mode.setEnabled(not active and not selecting)
        self.selection_scope.setEnabled(not active and not selecting)
        self.band.setEnabled(movie and self.selection_scope.currentData() == 'video' and not active and not selecting)
        self.profile.setEnabled(not active and not movie)
        self.import_profile.setEnabled(self.source_change_allowed() and (not movie or self.console.page=='games'))
        self.fallback.setEnabled(not active and not movie)
        self.ignore_speaker.setVisible(not movie and bool(self.profile.currentData()))
        self.ignore_speaker.setEnabled(not active and not selecting)
        live=not movie and not self.profile.currentData()
        self.caption_mode.setVisible(live)
        self.dialogue.setVisible(live and self.stacked_mode())
        self.caption_mode.setEnabled(not active and live)
        self.dialogue.setEnabled(not movie and self.stacked_mode())
        self.stop.setEnabled(active and not self.stop_event.is_set())
        self.stop.setText('Durduruluyor…' if active and self.stop_event.is_set() else 'Durdur')
        self.pause_button.setEnabled(active and not self.stop_event.is_set())
        self.pause_button.setText('Devam et' if active and self.control.snapshot()[0] else 'Duraklat')
        self.reselect_button.setEnabled(not self.closing)
        tv_closing = self.tv_closing
        self.tv_button.setEnabled(not tv_closing)
        info=self.tv.connection_info() if self.tv and not tv_closing else None
        ready=info is not None
        self.tv_state.setText('Kapatma tamamlanamadı' if self.tv_stop_error else
                              'Yayın kapanıyor…' if tv_closing else
                              'Alıcı bağlı' if ready and info.clients else
                              'TV bağlantısı bekleniyor' if ready else
                              'Yayın hazırlanıyor' if self.tv else 'Yayın kapalı')
        self.tv_code.setText(self.tv.token if ready else '—')
        self.tv_urls.setEnabled(ready)
        self.tv_copy_url.setEnabled(ready)
        self.tv_copy_code.setEnabled(ready)
        self.tv_test.setEnabled(ready and info.clients>0)
        pairing=self.tv.pairing_remaining() if ready else 0
        self.tv_pairing.setEnabled(ready)
        self.tv_pairing.setText('Otomatik eşleştirmeyi kapat' if pairing>0 else 'Otomatik eşleştirmeyi aç')
        self.tv_clients.setText(f'Bağlı alıcı: {info.clients}'
                               +(f' · Otomatik eşleştirme {int(pairing)//60}:{int(pairing)%60:02d}' if pairing>0 else '') if ready else
                               'Bağlantılar kapanıyor…' if tv_closing else
                               'Bağlantı durumu bilinmiyor' if self.tv else 'Bağlı alıcı: 0')
        if ready and time.monotonic()>=self.tv_address_refresh_at:
            self.update_tv_addresses(info)
        self.samsung_scan.setEnabled(not self.samsung.busy)
        self.samsung_install.setEnabled(not self.samsung.busy)
        self.samsung_cancel.setEnabled(self.samsung.busy)
        self.tv_host.setEnabled(not self.samsung.busy)
        self.samsung_renew.setEnabled(not self.samsung.busy)
        self.samsung_devices.setEnabled(not self.samsung.busy)
        self.samsung_log.setEnabled(self.samsung.log_path is not None)
        if not self.samsung.busy:
            self.samsung_login.setEnabled(False)
        paused=active and self.control.snapshot()[0]
        stopping=active and self.stop_event.is_set()
        preparing=bool(active and not stopping and not paused and self.startup is not None and not self.startup.gate.is_set())
        context=('Dizi ve film' if movie else self.profile.currentText() if self.profile.currentData()
                 else 'Diyalog' if self.stacked_mode() else 'Tek replik')
        if self.closing or self._cleanup_failed:
            phase,prompt='Kapanıyor','Son işlemler tamamlanıyor…'
        elif selecting:
            phase,prompt='Alan seçiliyor','Ekrandaki altyazıyı seç.\nEsc ile vazgeçebilirsin.'
        elif stopping:
            phase,prompt='Durduruluyor','Çeviri durduruluyor…'
        elif paused:
            phase,prompt='Duraklatıldı','Hazır olduğunda devam et.'
        elif preparing:
            phase,prompt='Hazırlanıyor',self.startup.message if not self.startup.ready else 'Çeviri başlatılıyor…'
        elif active:
            phase,prompt='Çalışıyor','Altyazı bekleniyor.'
        elif self.region is not None:
            phase,prompt='Alan hazır','Alan hazır.\nÇeviriyi başlat.'
        else:
            phase,prompt='Alan bekleniyor','Alanı seç.\nSonra başlat.'
        self.console.set_state(ConsoleState(context,phase,prompt,self.source_change_allowed(),
                                            not selecting and not stopping and not self.closing and not self._cleanup_failed,preparing,bool(active)))
        primary=self.console.primary_action.currentWidget()
        if primary_had_focus and primary is not previous_primary and primary.isEnabled():
            primary.setFocus(Qt.OtherFocusReason)
        if self.console.preferences.isVisible():
            self.console.preference_status.setText(self.status.text())
        if completed_navigation is not None:self.console.navigate(completed_navigation)
        if self.closing and not active and not self.import_busy and not import_active and self.tv is None and not tv_closing and not self.samsung.busy:
            if self.close():
                QApplication.instance().quit()
        elif self.reselect_pending and not active and not self.closing:
            self.reselect_pending = False
            QTimer.singleShot(0, self.choose)

    def closeEvent(self, event):
        self.record_event('close_requested')
        self.closing = True
        self._navigation_pending=None
        self.console.preferences.hide()
        self.halt()
        self.stop_tv()
        self.samsung.cancel()
        if (self.worker and self.worker.is_alive()) or self.import_busy or (self.import_worker and self.import_worker.is_alive()) or self.tv is not None or self.tv_closing or self.samsung.busy:
            event.ignore()
            self.status.setText('Son işlem tamamlanıyor; ardından kapanacak…')
        else:
            self.retire_capture()
            QCoreApplication.sendPostedEvents(self,QEvent.MetaCall)
            if self.event_log is not None:
                if not self.event_log.close():
                    self.closing=False
                    self._cleanup_failed=True
                    self.status.setText('Günlük kapanamadı; kapatmayı tekrar deneyin: '+self.event_log.error)
                    event.ignore();return
            self.timer.stop()
            try:
                self.disconnect_connections(self._application_connections)
                for screen in tuple(self._screen_connections):
                    self.unwatch_screen(screen)
                if self._application_connections or self._screen_connections:
                    raise RuntimeError('Ekran gözlem bağlantıları henüz kapanmadı.')
            except RuntimeError as exc:
                self.closing=False
                self._cleanup_failed=True
                self.timer.start(100)
                self.status.setText(f'Kapatma tamamlanamadı; tekrar kapatmayı deneyin: {exc}')
                event.ignore()
                return
            self._cleanup_failed=False
            event.accept()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--self-test', action='store_true', help='Panel açılışını doğrular ve otomatik kapanır.')
    args = parser.parse_args()
    if os.name == 'nt':
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    app = QApplication([])
    settings = Settings()
    lock_path = settings.path.parent / 'desktop.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(lock_path))
    if not args.self_test and not lock.tryLock(100):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None, 'MOZKAN Live Sub', 'Uygulama zaten açık.')
        raise SystemExit(0)
    event_log=None
    log_error=''
    try:event_log=AppLog(settings.path.parent/'logs',APP_VERSION,sys.version.split()[0])
    except OSError as exc:log_error=str(exc)
    try:
        window=Window(args.models,settings=settings,event_log=event_log)
        if log_error:window.status.setText('Uygulama günlüğü açılamadı: '+log_error)
        window.show()
        if args.self_test:QTimer.singleShot(500,window.close)
        exit_code=app.exec()
    finally:
        if event_log is not None:event_log.close()
    raise SystemExit(exit_code)
