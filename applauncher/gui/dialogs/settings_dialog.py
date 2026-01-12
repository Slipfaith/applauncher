"""Settings dialog."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout

from ..styles import TOKENS
from ..widgets.hotkey_settings_widget import HotkeySettingsWidget


class SettingsDialog(QDialog):
    def __init__(self, current_hotkey: str, parent=None) -> None:
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
