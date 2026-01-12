"""Settings dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from ..styles import TOKENS
from ..widgets.hotkey_settings_widget import HotkeySettingsWidget


class SettingsDialog(QDialog):
    opacityChanged = Signal(float)

    def __init__(self, current_hotkey: str, current_opacity: float, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(TOKENS.sizes.dialog_min_width)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
        )
        layout.setSpacing(TOKENS.spacing.lg)

        opacity_label = QLabel("Прозрачность окна")
        layout.addWidget(opacity_label)

        opacity_row = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(50, 100)
        self.opacity_slider.setValue(self._opacity_to_percent(current_opacity))
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self.opacity_slider)

        self.opacity_value = QLabel(self._format_opacity(self.opacity_slider.value()))
        self.opacity_value.setFixedWidth(48)
        self.opacity_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        opacity_row.addWidget(self.opacity_value)
        layout.addLayout(opacity_row)

        self.hotkey_widget = HotkeySettingsWidget(current_hotkey, self)
        layout.addWidget(self.hotkey_widget)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Закрыть")
        close_btn.setProperty("variant", "secondary")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def set_opacity(self, value: float) -> None:
        percent = self._opacity_to_percent(value)
        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(percent)
        self.opacity_slider.blockSignals(False)
        self.opacity_value.setText(self._format_opacity(percent))

    def _on_opacity_changed(self, percent: int) -> None:
        self.opacity_value.setText(self._format_opacity(percent))
        self.opacityChanged.emit(percent / 100.0)

    def _format_opacity(self, percent: int) -> str:
        return f"{percent}%"

    def _opacity_to_percent(self, value: float) -> int:
        return max(50, min(100, round(value * 100)))
