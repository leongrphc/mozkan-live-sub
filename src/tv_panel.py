"""TV receiver and optional Samsung helper pages of the main window."""
import threading
import time

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
                               QComboBox, QLineEdit, QCheckBox, QProgressBar)

from presentation import ResponsiveRow
from tv import TV


class TVPanel:
    """Window mixin: owns TV/Samsung widgets, actions and status handlers.

    Shares Window state (self.tv, self.samsung, self.settings, self.poll ...).
    """
    def build_tv_pages(self):
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
        samsung_layout.addStretch()
        return tv_page, samsung_page

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
            self.record_ui_error('tv_start',exc)
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
                    self.events.tv_closed.emit(service, exc)
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
            self.record_ui_error('tv_stop',error)
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

    def poll_tv(self, tv_closing):
        """Refresh TV/Samsung widgets from the periodic window poll."""
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
