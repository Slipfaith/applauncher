"""Universal search widget."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from ...services.search_service import SearchResult, SearchService


class UniversalSearchWidget(QDialog):
    resultActivated = Signal(SearchResult)

    def __init__(self, search_service: SearchService, parent=None) -> None:
        super().__init__(parent)
        self.search_service = search_service
        self.setWindowTitle("Universal Search")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setModal(False)

        layout = QVBoxLayout()
        layout.setSpacing(8)

        header = QLabel("Универсальный поиск")
        header.setProperty("role", "titleText")
        layout.addWidget(header)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите запрос...")
        self.search_input.textChanged.connect(self._on_query_changed)
        self.search_input.returnPressed.connect(self._on_return_pressed)
        layout.addWidget(self.search_input)

        self.result_list = QListWidget()
        self.result_list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.result_list)

        self.setLayout(layout)
        self.resize(520, 320)

    def open_search(self) -> None:
        self.search_input.clear()
        self.result_list.clear()
        self.show()
        self.raise_()
        self.activateWindow()
        if self.parent() is not None and hasattr(self.parent(), "geometry"):
            parent_rect = self.parent().geometry()
            self.move(
                parent_rect.center().x() - self.width() // 2,
                parent_rect.center().y() - self.height() // 2,
            )
        self.search_input.setFocus()

    def _on_query_changed(self, text: str) -> None:
        self._populate_results(self.search_service.search(text))

    def _populate_results(self, results: list[SearchResult]) -> None:
        self.result_list.clear()
        for result in results:
            item = QListWidgetItem(self._format_label(result))
            icon = self._resolve_icon(result)
            if not icon.isNull():
                item.setIcon(icon)
            item.setData(Qt.UserRole, result)
            self.result_list.addItem(item)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)

    def _format_label(self, result: SearchResult) -> str:
        type_label = "Приложение" if result.item_type == "app" else "Макрос"
        return f"{result.name} — {type_label}"

    def _resolve_icon(self, result: SearchResult) -> QIcon:
        icon_path = result.payload.get("icon_path", "")
        if icon_path and os.path.exists(icon_path):
            return QIcon(icon_path)
        return QIcon()

    def _on_return_pressed(self) -> None:
        current = self.result_list.currentItem()
        if current:
            self._emit_result(current)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        self._emit_result(item)

    def _emit_result(self, item: QListWidgetItem) -> None:
        result = item.data(Qt.UserRole)
        if result:
            self.resultActivated.emit(result)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)
