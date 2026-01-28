"""Global hotkey service."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import importlib.util
import logging
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal

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
        self._native_filter: _WindowsHotkeyFilter | None = None
        self._native_filter_installed = False

        if importlib.util.find_spec("keyboard") is not None:
            import keyboard  # type: ignore

            self._keyboard_module = keyboard
        if importlib.util.find_spec("pynput") is not None:
            from pynput import keyboard as pynput_keyboard  # type: ignore

            self._pynput_keyboard = pynput_keyboard
        if sys.platform == "win32":
            self._native_filter = _WindowsHotkeyFilter(self._emit_hotkey)
            app = QCoreApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self._native_filter)
                self._native_filter_installed = True
        if not self._keyboard_module and not self._pynput_keyboard and sys.platform != "win32":
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
        if self._register_windows_hotkey(hotkey):
            return True
        if self._keyboard_module:
            key_combo = self._normalize_keyboard_hotkey(hotkey)
            try:
                self._hotkey_id = self._keyboard_module.add_hotkey(
                    key_combo, self.hotkey_activated.emit
                )
                self._backend = "keyboard"
                logger.info("Registered global hotkey via keyboard: %s", key_combo)
                return True
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Keyboard hotkey registration failed: %s", exc)
                self._hotkey_id = None
        if self._pynput_keyboard:
            key_combo = self._normalize_pynput_hotkey(hotkey)
            try:
                self._listener = self._pynput_keyboard.GlobalHotKeys({key_combo: self._emit_hotkey})
                self._listener.start()
                self._backend = "pynput"
                logger.info("Registered global hotkey via pynput: %s", key_combo)
                return True
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Pynput hotkey registration failed: %s", exc)
                self._listener = None
        logger.warning("Failed to register global hotkey: no backend available")
        return False

    def unregister_hotkey(self) -> None:
        if self._backend == "win32" and self._hotkey_id is not None:
            _unregister_windows_hotkey(int(self._hotkey_id))
            self._hotkey_id = None
        if self._keyboard_module and self._hotkey_id is not None:
            try:
                self._keyboard_module.remove_hotkey(self._hotkey_id)
            except KeyError:
                pass
            self._hotkey_id = None
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._backend = None

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

    def _register_windows_hotkey(self, hotkey: str) -> bool:
        if sys.platform != "win32":
            return False
        if self._native_filter is None:
            self._native_filter = _WindowsHotkeyFilter(self._emit_hotkey)
        app = QCoreApplication.instance()
        if app is not None and not self._native_filter_installed:
            app.installNativeEventFilter(self._native_filter)
            self._native_filter_installed = True
        parsed = _parse_windows_hotkey(hotkey)
        if parsed is None:
            return False
        modifiers, key = parsed
        if not _register_windows_hotkey(modifiers, key):
            logger.warning("Windows hotkey registration failed for %s", hotkey)
            return False
        self._hotkey_id = _WINDOWS_HOTKEY_ID
        self._backend = "win32"
        logger.info("Registered global hotkey via Windows API: %s", hotkey)
        return True


_WINDOWS_HOTKEY_ID = 0xA10C


class _WindowsHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback) -> None:
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        if event_type != "windows_generic_MSG":
            return False, 0
        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message == 0x0312 and msg.wParam == _WINDOWS_HOTKEY_ID:
            self._callback()
            return True, 0
        return False, 0


def _register_windows_hotkey(modifiers: int, key: int) -> bool:
    if sys.platform != "win32":
        return False
    result = ctypes.windll.user32.RegisterHotKey(None, _WINDOWS_HOTKEY_ID, modifiers, key)
    return bool(result)


def _unregister_windows_hotkey(hotkey_id: int) -> None:
    if sys.platform != "win32":
        return
    ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)


def _parse_windows_hotkey(hotkey: str) -> tuple[int, int] | None:
    parts = [part.strip() for part in hotkey.split("+") if part.strip()]
    if not parts:
        return None
    modifiers = 0
    key_part = None
    for part in parts:
        lowered = part.lower()
        if lowered in {"ctrl", "control"}:
            modifiers |= 0x0002
        elif lowered == "alt":
            modifiers |= 0x0001
        elif lowered == "shift":
            modifiers |= 0x0004
        elif lowered in {"meta", "win", "cmd", "command"}:
            modifiers |= 0x0008
        else:
            key_part = part
    if key_part is None:
        return None
    key = _key_name_to_vk(key_part)
    if key is None:
        return None
    return modifiers, key


def _key_name_to_vk(name: str) -> int | None:
    normalized = name.strip().lower().replace(" ", "")
    if normalized in {"space", "spacebar"}:
        return 0x20
    if normalized in {"tab"}:
        return 0x09
    if normalized in {"enter", "return"}:
        return 0x0D
    if normalized in {"esc", "escape"}:
        return 0x1B
    if normalized in {"backspace", "back"}:
        return 0x08
    if normalized in {"insert", "ins"}:
        return 0x2D
    if normalized in {"delete", "del"}:
        return 0x2E
    if normalized in {"home"}:
        return 0x24
    if normalized in {"end"}:
        return 0x23
    if normalized in {"pageup", "pgup"}:
        return 0x21
    if normalized in {"pagedown", "pgdn"}:
        return 0x22
    if normalized in {"left"}:
        return 0x25
    if normalized in {"up"}:
        return 0x26
    if normalized in {"right"}:
        return 0x27
    if normalized in {"down"}:
        return 0x28
    if len(normalized) == 1 and normalized.isalnum():
        return ord(normalized.upper())
    if normalized.startswith("f") and normalized[1:].isdigit():
        index = int(normalized[1:])
        if 1 <= index <= 24:
            return 0x70 + (index - 1)
    return None
