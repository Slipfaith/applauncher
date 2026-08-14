"""Registry for launcher-local keyboard shortcuts."""
from __future__ import annotations

import importlib.util
import logging
from collections.abc import Callable, Iterable
from functools import partial

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

from ..services.local_hotkeys import format_hotkey_for_display, normalize_hotkey_text

logger = logging.getLogger(__name__)


class _ShortcutActivationBridge(QObject):
    """Move callbacks from the keyboard hook thread to Qt's GUI thread."""

    activated = Signal(object)


class LocalShortcutRegistry:
    """Keeps global item shortcuts in sync with launcher items."""

    def __init__(self, host: QWidget, activate_item: Callable[[dict], None]) -> None:
        self._host = host
        self._activate_item = activate_item
        self._shortcuts: list[QShortcut] = []
        self._global_hotkey_ids: list[object] = []
        self._keyboard_module = None
        self._bridge = _ShortcutActivationBridge(host)
        self._bridge.activated.connect(self._activate_item)
        if importlib.util.find_spec("keyboard") is not None:
            import keyboard  # type: ignore

            self._keyboard_module = keyboard

    def clear(self) -> None:
        if self._keyboard_module is not None:
            while self._global_hotkey_ids:
                hotkey_id = self._global_hotkey_ids.pop()
                try:
                    self._keyboard_module.remove_hotkey(hotkey_id)
                except Exception:
                    logger.debug("Failed to unregister item hotkey", exc_info=True)
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

            if not self._register_global_hotkey(hotkey, item):
                # Keep the shortcut usable in the application even on systems
                # where a global keyboard hook is unavailable.
                shortcut = QShortcut(sequence, self._host)
                shortcut.setContext(Qt.ApplicationShortcut)
                shortcut.setAutoRepeat(False)
                shortcut.activated.connect(partial(self._activate_item, item))
                self._shortcuts.append(shortcut)
            seen_hotkeys.add(normalized)

    def _register_global_hotkey(self, hotkey: str, item: dict) -> bool:
        if self._keyboard_module is None:
            return False
        key_combo = "+".join(
            part.strip().lower() for part in hotkey.split("+") if part.strip()
        )
        try:
            hotkey_id = self._keyboard_module.add_hotkey(
                key_combo,
                partial(self._bridge.activated.emit, item),
                suppress=False,
                trigger_on_release=True,
            )
        except Exception as err:
            logger.warning("Failed to register global item hotkey '%s': %s", hotkey, err)
            return False
        self._global_hotkey_ids.append(hotkey_id)
        logger.info(
            "Registered global item hotkey '%s' for %s",
            hotkey,
            item.get("name") or item.get("path"),
        )
        return True
