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
    QMenu,
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

        header = QLabel("Буфер обмена")
        header.setProperty("role", "titleText")
        layout.addWidget(header)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по истории...")
        self.search_input.textChanged.connect(self._refresh_list)
        search_layout.addWidget(self.search_input)

        self.clear_button = QPushButton("Очистить историю")
        self.clear_button.setProperty("variant", "danger")
        self.clear_button.clicked.connect(self._clear_history)
        search_layout.addWidget(self.clear_button)
        layout.addLayout(search_layout)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._copy_item)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.list_widget)

        self.copy_shortcut = QShortcut(QKeySequence.Copy, self.list_widget)
        self.copy_shortcut.activated.connect(self._copy_selected)

        self.setLayout(layout)

        self.clipboard_service.history_changed.connect(self._refresh_list)
        self._refresh_list()

    def _refresh_list(self, *_args) -> None:
        query = (self.search_input.text() or "").lower()
        self.list_widget.clear()
        for text, timestamp, pinned in self.clipboard_service.get_history():
            if query and query not in text.lower():
                continue
            item = QListWidgetItem(self._format_item(text, timestamp, pinned))
            item.setData(Qt.UserRole, text)
            item.setData(Qt.UserRole + 1, pinned)
            item.setToolTip(text)
            self.list_widget.addItem(item)

    def _format_item(self, text: str, timestamp: datetime, pinned: bool) -> str:
        preview = text.replace("\n", " ")
        if len(preview) > 80:
            preview = f"{preview[:77]}..."
        marker = "📌 " if pinned else ""
        return f"{marker}{timestamp.strftime('%H:%M:%S')} — {preview}"

    def _show_context_menu(self, pos) -> None:
        item = self.list_widget.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        pinned = bool(item.data(Qt.UserRole + 1))
        pin_action = menu.addAction("Открепить" if pinned else "Закрепить наверху")
        copy_action = menu.addAction("Копировать")
        selected = menu.exec(self.list_widget.viewport().mapToGlobal(pos))
        if selected == pin_action:
            self.clipboard_service.toggle_pinned(item.data(Qt.UserRole))
        elif selected == copy_action:
            self._copy_item(item)

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
