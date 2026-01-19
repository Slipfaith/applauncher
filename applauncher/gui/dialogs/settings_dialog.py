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
    tileSizeChanged = Signal(tuple)

    def __init__(
        self,
        current_hotkey: str,
        current_opacity: float,
        current_tile_size: tuple[int, int],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(TOKENS.sizes.dialog_min_width)
        self._tile_ratio = self._resolve_ratio(current_tile_size)

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

        tile_label = QLabel("Размер плиток")
        layout.addWidget(tile_label)

        tile_row = QHBoxLayout()
        self.tile_slider = QSlider(Qt.Horizontal)
        self.tile_slider.setRange(80, 200)
        self.tile_slider.setValue(self._resolve_tile_width(current_tile_size))
        self.tile_slider.valueChanged.connect(self._on_tile_size_changed)
        tile_row.addWidget(self.tile_slider)

        self.tile_value = QLabel(self._format_tile_size(self.tile_slider.value()))
        self.tile_value.setFixedWidth(72)
        self.tile_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tile_row.addWidget(self.tile_value)
        layout.addLayout(tile_row)

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

    def set_tile_size(self, tile_size: tuple[int, int]) -> None:
        width = self._resolve_tile_width(tile_size)
        self.tile_slider.blockSignals(True)
        self.tile_slider.setValue(width)
        self.tile_slider.blockSignals(False)
        self.tile_value.setText(self._format_tile_size(width))

    def _on_opacity_changed(self, percent: int) -> None:
        self.opacity_value.setText(self._format_opacity(percent))
        self.opacityChanged.emit(percent / 100.0)

    def _on_tile_size_changed(self, width: int) -> None:
        self.tile_value.setText(self._format_tile_size(width))
        height = max(1, round(width * self._tile_ratio))
        self.tileSizeChanged.emit((width, height))

    def _format_opacity(self, percent: int) -> str:
        return f"{percent}%"

    def _format_tile_size(self, width: int) -> str:
        height = max(1, round(width * self._tile_ratio))
        return f"{width}×{height}"

    def _opacity_to_percent(self, value: float) -> int:
        return max(50, min(100, round(value * 100)))

    def _resolve_ratio(self, tile_size: tuple[int, int]) -> float:
        width, height = tile_size
        if width > 0 and height > 0:
            return height / width
        return TOKENS.sizes.grid_button[1] / TOKENS.sizes.grid_button[0]

    def _resolve_tile_width(self, tile_size: tuple[int, int]) -> int:
        width = tile_size[0] if tile_size else TOKENS.sizes.grid_button[0]
        return max(80, min(200, int(width)))
