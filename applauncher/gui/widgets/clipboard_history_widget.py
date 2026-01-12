"""Clipboard history widget."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QKeySequence, QShortcut

from ...services.clipboard_service import ClipboardService


class ClipboardHistoryWidget(QWidget):
    def __init__(self, clipboard_service: ClipboardService, parent=None) -> None:
        super().__init__(parent)
        self.clipboard_service = clipboard_service

        layout = QVBoxLayout()
        layout.setSpacing(8)

        header = QLabel("Clipboard")
        header.setProperty("role", "titleText")
        layout.addWidget(header)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по истории...")
        self.search_input.textChanged.connect(self._refresh_list)
        search_layout.addWidget(self.search_input)

        self.clear_button = QPushButton("Clear History")
        self.clear_button.setProperty("variant", "danger")
        self.clear_button.clicked.connect(self._clear_history)
        search_layout.addWidget(self.clear_button)
        layout.addLayout(search_layout)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._copy_item)
        layout.addWidget(self.list_widget)

        self.copy_shortcut = QShortcut(QKeySequence.Copy, self.list_widget)
        self.copy_shortcut.activated.connect(self._copy_selected)

        self.setLayout(layout)

        self.clipboard_service.history_changed.connect(self._refresh_list)
        self._refresh_list()

    def _refresh_list(self, *_args) -> None:
        query = (self.search_input.text() or "").lower()
        self.list_widget.clear()
        for text, timestamp in self.clipboard_service.get_history():
            if query and query not in text.lower():
                continue
            item = QListWidgetItem(self._format_item(text, timestamp))
            item.setData(Qt.UserRole, text)
            self.list_widget.addItem(item)

    def _format_item(self, text: str, timestamp: datetime) -> str:
        preview = text.replace("\n", " ")
        if len(preview) > 80:
            preview = f"{preview[:77]}..."
        return f"{timestamp.strftime('%H:%M:%S')} — {preview}"

    def _copy_item(self, item: QListWidgetItem) -> None:
        text = item.data(Qt.UserRole)
        if text:
            self.clipboard_service.copy_to_clipboard(text)

    def _copy_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item:
            self._copy_item(item)

    def _clear_history(self) -> None:
        self.clipboard_service.clear_history()
