"""Optional local UI feedback; independent of capture and translation workers."""
import ctypes
import os
from pathlib import Path

from PySide6.QtCore import QObject, QEvent, QUrl, QSize
from PySide6.QtWidgets import QBoxLayout


def system_reduced_motion():
    if os.name == 'nt':
        enabled = ctypes.c_int(1)
        try:
            if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
                return not bool(enabled.value)
        except (OSError, AttributeError):
            pass
    return False


class ResponsiveRow(QBoxLayout):
    """Stack a form row when its containing page is narrow."""
    def __init__(self, host):
        super().__init__(QBoxLayout.TopToBottom)
        host.installEventFilter(self)

    def minimumSize(self):
        size = super().minimumSize()
        # A horizontal row must still allow its host to shrink and trigger wrapping.
        width = max((self.itemAt(i).minimumSize().width() for i in range(self.count())), default=0)
        margins = self.contentsMargins()
        return QSize(width + margins.left() + margins.right(), size.height())

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Resize, QEvent.Show):
            margins = watched.contentsMargins()
            required = sum(self.itemAt(i).minimumSize().width() for i in range(self.count()))
            required += max(0, self.count()-1) * max(0, self.spacing())
            available = watched.width()-margins.left()-margins.right()-64
            direction = self.LeftToRight if available >= max(700, required) else self.TopToBottom
            if self.direction() != direction:
                self.setDirection(direction)
        return super().eventFilter(watched, event)


class NavigationSound(QObject):
    """Load Qt Multimedia only after the user explicitly enables sounds."""
    def __init__(self, parent):
        super().__init__(parent)
        self.enabled = False
        self.effect = None

    def set_enabled(self, enabled):
        self.enabled = enabled
        if not enabled and self.effect is not None:
            self.effect.stop()

    def play(self):
        if not self.enabled:
            return
        if self.effect is None:
            try:
                from PySide6.QtMultimedia import QSoundEffect
                self.effect = QSoundEffect(self)
                self.effect.setVolume(.12)
                self.effect.setSource(QUrl.fromLocalFile(str(Path(__file__).parent / 'audio' / 'navigate.wav')))
            except (ImportError, OSError, RuntimeError):
                self.enabled = False
                return
        self.effect.play()
