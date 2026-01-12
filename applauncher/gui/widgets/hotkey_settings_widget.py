"""Settings widget for global hotkeys."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ..dialogs.hotkey_capture_dialog import HotkeyCaptureDialog


class HotkeySettingsWidget(QWidget):
    hotkeyChanged = Signal(str)

    def __init__(self, current_hotkey: str, parent=None) -> None:
        super().__init__(parent)
        self._current_hotkey = current_hotkey

        layout = QVBoxLayout()
        layout.setSpacing(8)

        title = QLabel("Глобальный хоткей")
        title.setProperty("role", "titleText")
        layout.addWidget(title)

        self.hotkey_label = QLabel(self._current_hotkey)
        self.hotkey_label.setProperty("role", "subtitleText")
        layout.addWidget(self.hotkey_label)

        self.change_button = QPushButton("Change Hotkey")
        self.change_button.setProperty("variant", "accent")
        self.change_button.clicked.connect(self._on_change_clicked)
        layout.addWidget(self.change_button)

        layout.addStretch()
        self.setLayout(layout)

    def set_hotkey(self, hotkey: str) -> None:
        self._current_hotkey = hotkey
        self.hotkey_label.setText(hotkey)

    def _on_change_clicked(self) -> None:
        dialog = HotkeyCaptureDialog(self, current_hotkey=self._current_hotkey)
        if dialog.exec() and dialog.selected_hotkey:
            self.set_hotkey(dialog.selected_hotkey)
            self.hotkeyChanged.emit(dialog.selected_hotkey)
