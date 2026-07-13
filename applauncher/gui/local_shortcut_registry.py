"""Registry for launcher-local keyboard shortcuts."""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

from ..services.local_hotkeys import format_hotkey_for_display, normalize_hotkey_text

logger = logging.getLogger(__name__)


class LocalShortcutRegistry:
    """Keeps QShortcut objects in sync with launcher items."""

    def __init__(self, host: QWidget, activate_item: Callable[[dict], None]) -> None:
        self._host = host
        self._activate_item = activate_item
        self._shortcuts: list[QShortcut] = []

    def clear(self) -> None:
        while self._shortcuts:
            shortcut = self._shortcuts.pop()
            shortcut.setEnabled(False)
            shortcut.deleteLater()

    def rebuild(self, items: Iterable[dict]) -> None:
        self.clear()
        seen_hotkeys: set[str] = set()

        for item in items:
            if item.get("disabled") or item.get("invalid"):
                continue

            hotkey = format_hotkey_for_display(str(item.get("local_hotkey") or ""))
            normalized = normalize_hotkey_text(hotkey)
            if not normalized:
                continue
            if normalized in seen_hotkeys:
                logger.warning(
                    "Duplicate local hotkey skipped: %s for %s",
                    hotkey,
                    item.get("name") or item.get("path"),
                )
                continue

            sequence = QKeySequence.fromString(hotkey, QKeySequence.PortableText)
            if sequence.isEmpty():
                logger.warning(
                    "Failed to parse local hotkey '%s' for %s",
                    hotkey,
                    item.get("name") or item.get("path"),
                )
                continue

            shortcut = QShortcut(sequence, self._host)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(partial(self._activate_item, item))
            self._shortcuts.append(shortcut)
            seen_hotkeys.add(normalized)
