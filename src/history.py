"""In-memory translation history for the running session. Never written to disk."""
from collections import deque
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

MAX_ENTRIES = 200


class TranslationHistory:
    def __init__(self, limit=MAX_ENTRIES):
        self.entries = deque(maxlen=limit)
        self.revision = 0

    def add(self, source, target, *, now=None):
        if not source or not target:
            return False
        if self.entries and self.entries[-1][1:] == (source, target):
            return False
        self.entries.append(((now or datetime.now()).strftime('%H:%M:%S'), source, target))
        self.revision += 1
        return True

    def clear(self):
        self.entries.clear()
        self.revision += 1

    def as_text(self):
        return '\n\n'.join(f'[{at}] {source}\n{target}' for at, source, target in self.entries)


class HistoryWindow(QDialog):
    """Non-modal reader; the owner decides whether it may be shown during capture."""

    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.history = history
        self.shown_revision = -1
        self.setWindowTitle('Çeviri geçmişi')
        self.setModal(False)
        self.resize(560, 520)
        layout = QVBoxLayout(self)
        hint = QLabel(f'Bu oturumdaki son {self.history.entries.maxlen} satır. Yalnız bellekte tutulur; '
                      'uygulama kapanınca silinir.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setAccessibleName('Çeviri geçmişi')
        self.view.setPlaceholderText('Henüz çevrilmiş satır yok.')
        layout.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.copy_button = QPushButton('Tümünü kopyala')
        self.clear_button = QPushButton('Geçmişi temizle')
        close = QPushButton('Kapat')
        self.copy_button.clicked.connect(self.copy_all)
        self.clear_button.clicked.connect(self.clear)
        close.clicked.connect(self.close)
        for button in (self.copy_button, self.clear_button):
            row.addWidget(button)
        row.addStretch()
        row.addWidget(close)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        if self.history.revision == self.shown_revision:
            return
        bar = self.view.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        self.view.setPlainText(self.history.as_text())
        if at_end:
            bar.setValue(bar.maximum())
        self.shown_revision = self.history.revision
        has_entries = bool(self.history.entries)
        self.copy_button.setEnabled(has_entries)
        self.clear_button.setEnabled(has_entries)

    def copy_all(self):
        QApplication.clipboard().setText(self.history.as_text())

    def clear(self):
        self.history.clear()
        self.refresh()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
