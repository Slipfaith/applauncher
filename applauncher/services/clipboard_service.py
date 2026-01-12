"""Clipboard history service."""
from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


class ClipboardService(QObject):
    """Monitors clipboard changes and stores recent history."""

    history_changed = Signal(list)

    def __init__(self, parent: QObject | None = None, max_entries: int = 20) -> None:
        super().__init__(parent)
        self._history: List[Tuple[str, datetime]] = []
        self._max_entries = max_entries
        self._clipboard = QApplication.clipboard()
        self._ignore_next_change = False
        self._clipboard.dataChanged.connect(self._on_data_changed)

    def get_history(self) -> List[Tuple[str, datetime]]:
        return list(self._history)

    def add_entry(self, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            return
        if any(entry_text == cleaned for entry_text, _ in self._history):
            return
        self._history.insert(0, (cleaned, datetime.now()))
        if len(self._history) > self._max_entries:
            self._history = self._history[: self._max_entries]
        self.history_changed.emit(self.get_history())

    def clear_history(self) -> None:
        self._history = []
        self.history_changed.emit(self.get_history())

    def copy_to_clipboard(self, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            return
        self._ignore_next_change = True
        self._clipboard.setText(cleaned)

    def _on_data_changed(self) -> None:
        if self._ignore_next_change:
            self._ignore_next_change = False
            return
        self.add_entry(self._clipboard.text())
