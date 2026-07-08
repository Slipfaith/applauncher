"""Clipboard history widget."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...services.clipboard_service import ClipboardService
from ..styles import TOKENS
from .toast import Toast

PREVIEW_LIMIT = 120
TOOLTIP_LIMIT = 800


class _ClipboardRow(QWidget):
    """Single history entry: preview, meta line, and action buttons."""

    def __init__(self, entry: dict, widget: "ClipboardHistoryWidget", parent=None) -> None:
        super().__init__(parent)
        self.setProperty("role", "listItem")
        text = entry["text"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            TOKENS.spacing.md,
            TOKENS.spacing.sm,
            TOKENS.spacing.sm,
            TOKENS.spacing.sm,
        )
        layout.setSpacing(TOKENS.spacing.sm)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(TOKENS.spacing.xs)

        preview = text.replace("\n", " ").strip()
        if len(preview) > PREVIEW_LIMIT:
            preview = f"{preview[:PREVIEW_LIMIT - 1]}…"
        title = QLabel(("📌 " if entry.get("pinned") else "") + preview)
        title.setProperty("role", "listTitle")
        text_layout.addWidget(title)

        meta = QLabel(self._build_meta(entry))
        meta.setProperty("role", "listSubtitle")
        text_layout.addWidget(meta)
        layout.addLayout(text_layout, stretch=1)

        pin_btn = QToolButton()
        pin_btn.setProperty("role", "clipAction")
        pin_btn.setText("📌")
        pin_btn.setToolTip("Открепить" if entry.get("pinned") else "Закрепить")
        pin_btn.clicked.connect(lambda: widget.toggle_pin(text))
        layout.addWidget(pin_btn)

        copy_btn = QToolButton()
        copy_btn.setProperty("role", "clipAction")
        copy_btn.setText("📋")
        copy_btn.setToolTip("Скопировать")
        copy_btn.clicked.connect(lambda: widget.copy_text(text))
        layout.addWidget(copy_btn)

        delete_btn = QToolButton()
        delete_btn.setProperty("role", "clipAction")
        delete_btn.setText("✕")
        delete_btn.setToolTip("Удалить из истории")
        delete_btn.clicked.connect(lambda: widget.remove_text(text))
        layout.addWidget(delete_btn)

    @staticmethod
    def _build_meta(entry: dict) -> str:
        parts = [_format_timestamp(entry.get("ts", ""))]
        lines = entry["text"].count("\n") + 1
        if lines > 1:
            parts.append(f"строк: {lines}")
        parts.append(f"символов: {len(entry['text'])}")
        return " • ".join(part for part in parts if part)


def _format_timestamp(raw: str) -> str:
    try:
        moment = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return ""
    if moment.date() == datetime.now().date():
        return moment.strftime("%H:%M")
    return moment.strftime("%d.%m %H:%M")


class ClipboardHistoryWidget(QWidget):
    def __init__(self, clipboard_service: ClipboardService, parent=None) -> None:
        super().__init__(parent)
        self.clipboard_service = clipboard_service

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TOKENS.layout.content_margins)
        layout.setSpacing(TOKENS.layout.content_spacing)

        header_layout = QHBoxLayout()
        header = QLabel("История буфера обмена")
        header.setProperty("role", "titleText")
        header_layout.addWidget(header)
        self.counter_label = QLabel("")
        self.counter_label.setProperty("role", "listSubtitle")
        header_layout.addWidget(self.counter_label)
        header_layout.addStretch()

        self.clear_button = QPushButton("Очистить историю")
        self.clear_button.setProperty("variant", "danger")
        self.clear_button.clicked.connect(self._clear_history)
        header_layout.addWidget(self.clear_button)
        layout.addLayout(header_layout)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по истории...")
        self.search_input.textChanged.connect(self._refresh_list)
        layout.addWidget(self.search_input)

        hint = QLabel("Клик по записи копирует её в буфер. Закреплённые записи не удаляются при очистке.")
        hint.setProperty("role", "listSubtitle")
        layout.addWidget(hint)

        self.empty_label = QLabel("История пуста.\nСкопируйте что-нибудь — оно появится здесь.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setProperty("role", "listSubtitle")
        layout.addWidget(self.empty_label, stretch=1)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("clipboardList")
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.list_widget, stretch=1)

        self.copy_shortcut = QShortcut(QKeySequence.Copy, self.list_widget)
        self.copy_shortcut.activated.connect(self._copy_selected)
        self.delete_shortcut = QShortcut(QKeySequence.Delete, self.list_widget)
        self.delete_shortcut.activated.connect(self._delete_selected)

        self.clipboard_service.history_changed.connect(self._refresh_list)
        self._refresh_list()

    def copy_text(self, text: str) -> None:
        self.clipboard_service.copy_to_clipboard(text)
        Toast.show_message(self.window(), "✓ Скопировано в буфер")

    def toggle_pin(self, text: str) -> None:
        self.clipboard_service.toggle_pin(text)

    def remove_text(self, text: str) -> None:
        self.clipboard_service.remove_entry(text)

    def _refresh_list(self, *_args) -> None:
        query = (self.search_input.text() or "").strip().lower()
        entries = self.clipboard_service.get_history()
        if query:
            entries = [entry for entry in entries if query in entry["text"].lower()]

        self.list_widget.clear()
        for entry in entries:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, entry["text"])
            tooltip = entry["text"]
            if len(tooltip) > TOOLTIP_LIMIT:
                tooltip = f"{tooltip[:TOOLTIP_LIMIT]}…"
            item.setToolTip(tooltip)
            row = _ClipboardRow(entry, self)
            item.setSizeHint(QSize(0, row.sizeHint().height() + TOKENS.spacing.xs))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

        total = len(self.clipboard_service.get_history())
        shown = self.list_widget.count()
        if query:
            self.counter_label.setText(f"найдено: {shown} из {total}")
        else:
            self.counter_label.setText(f"записей: {total}" if total else "")
        has_items = shown > 0
        self.list_widget.setVisible(has_items)
        self.empty_label.setVisible(not has_items)
        if not has_items and query:
            self.empty_label.setText("Ничего не найдено по запросу.")
        elif not has_items:
            self.empty_label.setText("История пуста.\nСкопируйте что-нибудь — оно появится здесь.")

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        text = item.data(Qt.UserRole)
        if text:
            self.copy_text(text)

    def _copy_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item and item.data(Qt.UserRole):
            self.copy_text(item.data(Qt.UserRole))

    def _delete_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item and item.data(Qt.UserRole):
            self.remove_text(item.data(Qt.UserRole))

    def _show_context_menu(self, pos) -> None:
        item = self.list_widget.itemAt(pos)
        if item is None:
            return
        text = item.data(Qt.UserRole)
        if not text:
            return
        pinned = any(
            entry.get("pinned") for entry in self.clipboard_service.get_history() if entry["text"] == text
        )
        menu = QMenu(self)
        copy_action = menu.addAction("📋 Скопировать")
        pin_action = menu.addAction("📌 Открепить" if pinned else "📌 Закрепить")
        delete_action = menu.addAction("🗑️ Удалить")
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == copy_action:
            self.copy_text(text)
        elif action == pin_action:
            self.toggle_pin(text)
        elif action == delete_action:
            self.remove_text(text)

    def _clear_history(self) -> None:
        entries = self.clipboard_service.get_history()
        if not any(not entry.get("pinned") for entry in entries):
            Toast.show_message(self.window(), "Нечего очищать")
            return
        confirm = QMessageBox.question(
            self,
            "Очистить историю",
            "Удалить все незакреплённые записи из истории буфера?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.clipboard_service.clear_history()
