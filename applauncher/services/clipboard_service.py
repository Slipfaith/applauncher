"""Clipboard history service."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Tuple

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication


class ClipboardService(QObject):
    """Monitors clipboard changes and stores recent history."""

    history_changed = Signal(list)

    def __init__(self, parent: QObject | None = None, max_entries: int = 20) -> None:
        super().__init__(parent)
        self._history: List[Tuple[str, datetime, bool]] = []
        self._max_entries = max_entries
        self._clipboard = QApplication.clipboard()
        self._ignore_next_change = False
        self._clipboard.dataChanged.connect(self._on_data_changed)

    def get_history(self) -> List[Tuple[str, datetime, bool]]:
        return list(self._history)

    def add_entry(self, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            return
        if any(entry_text == cleaned for entry_text, _, _ in self._history):
            return
        self._history.append((cleaned, datetime.now(), False))
        self._sort_and_trim()
        self.history_changed.emit(self.get_history())

    def set_history(self, entries: Iterable[dict]) -> None:
        """Restore validated history entries from the application config."""
        restored: List[Tuple[str, datetime, bool]] = []
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text") or "").strip()
            if not text or text in seen:
                continue
            try:
                timestamp = datetime.fromisoformat(str(entry.get("timestamp") or ""))
            except (TypeError, ValueError):
                timestamp = datetime.now()
            if timestamp.tzinfo is not None:
                timestamp = timestamp.astimezone().replace(tzinfo=None)
            restored.append((text, timestamp, bool(entry.get("pinned", False))))
            seen.add(text)
        self._history = restored
        self._sort_and_trim()
        self.history_changed.emit(self.get_history())

    def serialize_history(self) -> list[dict]:
        return [
            {"text": text, "timestamp": timestamp.isoformat(), "pinned": pinned}
            for text, timestamp, pinned in self._history
        ]

    def toggle_pinned(self, text: str) -> None:
        for index, (entry_text, timestamp, pinned) in enumerate(self._history):
            if entry_text == text:
                self._history[index] = (entry_text, timestamp, not pinned)
                self._sort_and_trim()
                self.history_changed.emit(self.get_history())
                return

    def _sort_and_trim(self) -> None:
        self._history.sort(key=lambda entry: (entry[2], entry[1]), reverse=True)
        self._history = self._history[: self._max_entries]

    def clear_history(self) -> None:
        self._history = []
        self.history_changed.emit(self.get_history())

    def copy_to_clipboard(self, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            return
        self._ignore_next_change = True
        self._clipboard.setText(cleaned)
        # Some clipboard backends do not emit dataChanged when the text is
        # unchanged. Do not let that suppress the next genuine external copy.
        QTimer.singleShot(0, self._clear_ignore_flag)

    def _clear_ignore_flag(self) -> None:
        self._ignore_next_change = False

    def _on_data_changed(self) -> None:
        if self._ignore_next_change:
            self._ignore_next_change = False
            return
        self.add_entry(self._clipboard.text())
