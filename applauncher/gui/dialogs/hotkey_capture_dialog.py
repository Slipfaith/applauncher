"""Dialog for capturing a hotkey combination."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout

from ..styles import TOKENS

FORBIDDEN_COMBOS = {
    "alt+tab",
    "alt+f4",
    "ctrl+alt+del",
    "ctrl+alt+delete",
    "ctrl+shift+esc",
    "ctrl+esc",
    "cmd+space",
}


class HotkeyCaptureDialog(QDialog):
    def __init__(self, parent=None, current_hotkey: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Изменить хоткей")
        self.setMinimumWidth(TOKENS.sizes.dialog_min_width)
        self._current_hotkey = current_hotkey
        self.selected_hotkey: str | None = None

        layout = QVBoxLayout()
        layout.setContentsMargins(
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
        )
        layout.setSpacing(TOKENS.spacing.lg)

        self.info_label = QLabel("Нажмите комбинацию клавиш")
        self.info_label.setProperty("role", "titleText")
        layout.addWidget(self.info_label)

        self.hotkey_label = QLabel(current_hotkey or "")
        self.hotkey_label.setAlignment(Qt.AlignCenter)
        self.hotkey_label.setStyleSheet("font-size: 18px; padding: 12px;")
        layout.addWidget(self.hotkey_label)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ff6b6b;")
        layout.addWidget(self.error_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setProperty("variant", "secondary")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setProperty("variant", "accent")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        modifiers = event.modifiers()
        key = event.key()
        if key in {Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta}:
            self._update_display(modifiers, None)
            return
        key_name = QKeySequence(key).toString()
        hotkey = self._format_hotkey(modifiers, key_name)
        self._update_hotkey(hotkey)

    def _update_display(self, modifiers, key_name: str | None) -> None:
        hotkey = self._format_hotkey(modifiers, key_name) if key_name else self._format_hotkey(modifiers, None)
        self.hotkey_label.setText(hotkey)
        self.save_btn.setEnabled(False)

    def _update_hotkey(self, hotkey: str) -> None:
        self.hotkey_label.setText(hotkey)
        if not hotkey or hotkey.lower() in FORBIDDEN_COMBOS:
            self.error_label.setText("Эта комбинация занята системой")
            self.save_btn.setEnabled(False)
            return
        if "+" not in hotkey:
            self.error_label.setText("Добавьте модификатор (Ctrl, Alt, Shift)")
            self.save_btn.setEnabled(False)
            return
        self.error_label.setText("")
        self.selected_hotkey = hotkey
        self.save_btn.setEnabled(True)

    def _format_hotkey(self, modifiers, key_name: str | None) -> str:
        parts: list[str] = []
        if modifiers & Qt.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.MetaModifier:
            parts.append("Meta")
        if key_name:
            parts.append(key_name)
        return "+".join(parts)
