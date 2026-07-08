"""Clipboard history service with pinning and persistence."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from ..config import resolve_config_path

logger = logging.getLogger(__name__)

HISTORY_FILE = "clipboard_history.json"


class ClipboardService(QObject):
    """Monitors clipboard changes and stores recent history.

    Entries are dicts: {"text": str, "ts": iso-datetime, "pinned": bool}.
    Pinned entries survive clearing and never get trimmed.
    """

    history_changed = Signal()

    def __init__(self, parent: QObject | None = None, max_entries: int = 100) -> None:
        super().__init__(parent)
        self._entries: list[dict] = []
        self._max_entries = max_entries
        self._storage_path = resolve_config_path(HISTORY_FILE)
        self._clipboard = QApplication.clipboard()
        self._ignore_next_change = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save)
        self._load()
        self._clipboard.dataChanged.connect(self._on_data_changed)

    def get_history(self) -> list[dict]:
        """Return entries with pinned ones first, newest first within each part."""
        pinned = [dict(entry) for entry in self._entries if entry.get("pinned")]
        rest = [dict(entry) for entry in self._entries if not entry.get("pinned")]
        return pinned + rest

    def add_entry(self, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            return
        existing = next((entry for entry in self._entries if entry["text"] == cleaned), None)
        if existing is not None:
            self._entries.remove(existing)
            existing["ts"] = datetime.now().isoformat(timespec="seconds")
            self._entries.insert(0, existing)
        else:
            self._entries.insert(
                0,
                {"text": cleaned, "ts": datetime.now().isoformat(timespec="seconds"), "pinned": False},
            )
        self._trim()
        self._notify()

    def toggle_pin(self, text: str) -> None:
        for entry in self._entries:
            if entry["text"] == text:
                entry["pinned"] = not entry.get("pinned", False)
                self._notify()
                return

    def remove_entry(self, text: str) -> None:
        remaining = [entry for entry in self._entries if entry["text"] != text]
        if len(remaining) != len(self._entries):
            self._entries = remaining
            self._notify()

    def clear_history(self) -> None:
        """Remove all unpinned entries."""
        self._entries = [entry for entry in self._entries if entry.get("pinned")]
        self._notify()

    def copy_to_clipboard(self, text: str) -> None:
        if not text:
            return
        self._ignore_next_change = True
        self._clipboard.setText(text)

    def _trim(self) -> None:
        unpinned = [entry for entry in self._entries if not entry.get("pinned")]
        overflow = len(unpinned) - self._max_entries
        if overflow <= 0:
            return
        for entry in reversed(unpinned):
            if overflow <= 0:
                break
            self._entries.remove(entry)
            overflow -= 1

    def _notify(self) -> None:
        self.history_changed.emit()
        self._save_timer.start()

    def _on_data_changed(self) -> None:
        if self._ignore_next_change:
            self._ignore_next_change = False
            return
        self.add_entry(self._clipboard.text())

    def _load(self) -> None:
        if not os.path.exists(self._storage_path):
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError) as err:
            logger.warning("Не удалось загрузить историю буфера: %s", err)
            return
        if not isinstance(raw, list):
            return
        entries = []
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                entries.append(
                    {
                        "text": item["text"],
                        "ts": str(item.get("ts") or datetime.now().isoformat(timespec="seconds")),
                        "pinned": bool(item.get("pinned")),
                    }
                )
        self._entries = entries[: self._max_entries * 2]

    def _save(self) -> None:
        tmp_path = f"{self._storage_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(self._entries, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._storage_path)
        except OSError as err:
            logger.warning("Не удалось сохранить историю буфера: %s", err)
