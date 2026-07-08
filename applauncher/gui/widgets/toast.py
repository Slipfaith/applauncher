"""Small auto-dismissing toast notification."""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..styles import TOKENS


class Toast(QWidget):
    """Frameless notification shown near the bottom of the parent window."""

    FADE_MS = 160

    def __init__(self, parent: QWidget, text: str) -> None:
        super().__init__(parent, Qt.FramelessWindowHint | Qt.ToolTip)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setObjectName("toastLabel")
        label.setStyleSheet(
            f"""
            QLabel#toastLabel {{
                background-color: rgba(31, 42, 55, 235);
                color: #f6f6f3;
                border-radius: {TOKENS.radii.lg}px;
                padding: {TOKENS.spacing.md}px {TOKENS.spacing.xl}px;
                font-size: {TOKENS.typography.font_size_md}px;
                font-weight: {TOKENS.typography.weight_semibold};
            }}
            """
        )
        layout.addWidget(label)

        self._animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._animation.setDuration(self.FADE_MS)

    @staticmethod
    def show_message(parent: QWidget, text: str, duration_ms: int = 2400) -> None:
        """Show a toast over the parent window, replacing any active one."""
        if parent is None:
            return
        previous = getattr(parent, "_active_toast", None)
        if previous is not None:
            try:
                previous.close()
            except RuntimeError:
                pass
        toast = Toast(parent, text)
        parent._active_toast = toast
        toast.adjustSize()
        geo = parent.geometry()
        toast.move(
            geo.x() + (geo.width() - toast.width()) // 2,
            geo.y() + geo.height() - toast.height() - 56,
        )
        toast.setWindowOpacity(0.0)
        toast.show()
        toast._fade(0.0, 1.0)
        QTimer.singleShot(duration_ms, toast._dismiss)

    def _fade(self, start: float, end: float, on_done=None) -> None:
        self._animation.stop()
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        if on_done is not None:
            self._animation.finished.connect(on_done)
        self._animation.start()

    def _dismiss(self) -> None:
        self._fade(self.windowOpacity(), 0.0, self.close)
