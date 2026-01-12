"""Global hotkey service."""
from __future__ import annotations

import importlib.util
import logging

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class HotkeyService(QObject):
    """Registers and listens to a global hotkey."""

    hotkey_activated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._backend: str | None = None
        self._hotkey_id: object | None = None
        self._listener = None
        self._keyboard_module = None
        self._pynput_keyboard = None
        self._current_hotkey: str | None = None

        if importlib.util.find_spec("keyboard") is not None:
            import keyboard  # type: ignore

            self._keyboard_module = keyboard
            self._backend = "keyboard"
        elif importlib.util.find_spec("pynput") is not None:
            from pynput import keyboard as pynput_keyboard  # type: ignore

            self._pynput_keyboard = pynput_keyboard
            self._backend = "pynput"
        else:
            logger.warning("Hotkey backend unavailable (install keyboard or pynput).")

    @property
    def current_hotkey(self) -> str | None:
        return self._current_hotkey

    def register_hotkey(self, hotkey: str) -> bool:
        """Register a global hotkey string like "Ctrl+Space"."""
        if not hotkey:
            return False
        self.unregister_hotkey()
        self._current_hotkey = hotkey
        if self._backend == "keyboard" and self._keyboard_module:
            key_combo = self._normalize_keyboard_hotkey(hotkey)
            self._hotkey_id = self._keyboard_module.add_hotkey(key_combo, self.hotkey_activated.emit)
            logger.info("Registered global hotkey via keyboard: %s", key_combo)
            return True
        if self._backend == "pynput" and self._pynput_keyboard:
            key_combo = self._normalize_pynput_hotkey(hotkey)
            self._listener = self._pynput_keyboard.GlobalHotKeys({key_combo: self._emit_hotkey})
            self._listener.start()
            logger.info("Registered global hotkey via pynput: %s", key_combo)
            return True
        logger.warning("Failed to register global hotkey: no backend")
        return False

    def unregister_hotkey(self) -> None:
        if self._backend == "keyboard" and self._keyboard_module and self._hotkey_id is not None:
            try:
                self._keyboard_module.remove_hotkey(self._hotkey_id)
            except KeyError:
                pass
            self._hotkey_id = None
        if self._backend == "pynput" and self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _emit_hotkey(self) -> None:
        self.hotkey_activated.emit()

    def _normalize_keyboard_hotkey(self, hotkey: str) -> str:
        return "+".join(part.strip().lower() for part in hotkey.split("+") if part.strip())

    def _normalize_pynput_hotkey(self, hotkey: str) -> str:
        parts = []
        for part in hotkey.split("+"):
            key = part.strip().lower()
            if not key:
                continue
            if key in {"ctrl", "control"}:
                parts.append("<ctrl>")
            elif key == "alt":
                parts.append("<alt>")
            elif key == "shift":
                parts.append("<shift>")
            elif key in {"meta", "win", "cmd", "command"}:
                parts.append("<cmd>")
            else:
                parts.append(key)
        return "+".join(parts)
