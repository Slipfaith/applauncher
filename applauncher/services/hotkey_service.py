"""Global hotkey service."""
from __future__ import annotations

import ctypes
import importlib.util
import logging
import os
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
ERROR_INVALID_HOTKEY = 1422


class _WindowsHotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self, service: "HotkeyService") -> None:
        super().__init__()
        self._service = service

    def nativeEventFilter(self, _event_type, message):  # pragma: no cover - platform specific
        if os.name != "nt":
            return False, 0
        try:
            msg = wintypes.MSG.from_address(int(message))
        except Exception:
            return False, 0
        if msg.message == WM_HOTKEY:
            self._service._on_windows_hotkey(int(msg.wParam))
            return True, 0
        return False, 0


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
        self._native_filter: _WindowsHotkeyEventFilter | None = None
        self._native_filter_installed = False
        self._windows_hotkey_id_counter = 1
        self._windows_modifiers: int | None = None
        self._windows_key_code: int | None = None
        self._last_error: str | None = None

        if os.name == "nt" and self._setup_windows_backend():
            self._backend = "windows"
        elif importlib.util.find_spec("keyboard") is not None:
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

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def register_hotkey(self, hotkey: str) -> bool:
        """Register a global hotkey string like "Ctrl+Space"."""
        if not hotkey:
            self._last_error = "Не указана комбинация клавиш."
            return False
        self._last_error = None
        self.unregister_hotkey()
        self._current_hotkey = hotkey
        if self._backend == "windows":
            parsed = self._parse_windows_hotkey(hotkey)
            if parsed is None:
                self._last_error = (
                    f"Не удалось разобрать комбинацию: '{hotkey}'. "
                    "Проверьте формат вида Ctrl+Alt+Space."
                )
                logger.warning("Failed to parse windows hotkey '%s'", hotkey)
                return False
            modifiers, key_code = parsed
            hotkey_id = self._next_windows_hotkey_id()
            try:
                ctypes.set_last_error(0)
                registered = bool(
                    ctypes.windll.user32.RegisterHotKey(None, hotkey_id, modifiers, key_code)
                )
                win_error = ctypes.get_last_error()
            except Exception as err:  # pragma: no cover - backend dependent
                logger.warning("Failed to register windows hotkey '%s': %s", hotkey, err)
                registered = False
                win_error = None
            if not registered:
                logger.warning("Failed to register windows hotkey '%s'", hotkey)
                self._hotkey_id = None
                self._windows_modifiers = None
                self._windows_key_code = None
                if win_error == ERROR_HOTKEY_ALREADY_REGISTERED:
                    self._last_error = (
                        "Комбинация уже занята другим приложением или системой."
                    )
                elif win_error == ERROR_INVALID_HOTKEY:
                    self._last_error = (
                        "Комбинация не поддерживается системой."
                    )
                elif win_error:
                    self._last_error = (
                        f"Ошибка Windows при регистрации хоткея (код {win_error})."
                    )
                else:
                    self._last_error = "Не удалось зарегистрировать хоткей."
                return False
            self._hotkey_id = hotkey_id
            self._windows_modifiers = modifiers
            self._windows_key_code = key_code
            logger.info("Registered global hotkey via windows API: %s", hotkey)
            return True
        if self._backend == "keyboard" and self._keyboard_module:
            key_combo = self._normalize_keyboard_hotkey(hotkey)
            try:
                self._hotkey_id = self._keyboard_module.add_hotkey(
                    key_combo, self.hotkey_activated.emit
                )
                logger.info("Registered global hotkey via keyboard: %s", key_combo)
                return True
            except Exception as err:  # pragma: no cover - backend dependent
                logger.warning("Failed to register keyboard hotkey '%s': %s", key_combo, err)
                self._hotkey_id = None
                self._last_error = f"Не удалось зарегистрировать через backend keyboard: {err}"
                return False
        if self._backend == "pynput" and self._pynput_keyboard:
            key_combo = self._normalize_pynput_hotkey(hotkey)
            try:
                self._listener = self._pynput_keyboard.GlobalHotKeys(
                    {key_combo: self._emit_hotkey}
                )
                self._listener.start()
                logger.info("Registered global hotkey via pynput: %s", key_combo)
                return True
            except Exception as err:  # pragma: no cover - backend dependent
                logger.warning("Failed to register pynput hotkey '%s': %s", key_combo, err)
                self._listener = None
                self._last_error = f"Не удалось зарегистрировать через backend pynput: {err}"
                return False
        self._last_error = "Не найден backend для глобальных горячих клавиш."
        logger.warning("Failed to register global hotkey: no backend")
        return False

    def unregister_hotkey(self) -> None:
        if self._backend == "windows" and self._hotkey_id is not None:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, int(self._hotkey_id))
            except Exception:  # pragma: no cover - backend dependent
                logger.debug("Failed to unregister windows hotkey", exc_info=True)
            self._hotkey_id = None
            self._windows_modifiers = None
            self._windows_key_code = None
        if self._backend == "keyboard" and self._keyboard_module and self._hotkey_id is not None:
            try:
                self._keyboard_module.remove_hotkey(self._hotkey_id)
            except Exception:  # pragma: no cover - backend dependent
                logger.debug("Failed to unregister keyboard hotkey", exc_info=True)
            self._hotkey_id = None
        if self._backend == "pynput" and self._listener is not None:
            try:
                self._listener.stop()
            except Exception:  # pragma: no cover - backend dependent
                logger.debug("Failed to stop pynput listener", exc_info=True)
            self._listener = None

    def ensure_hotkey_registered(self) -> bool:
        """Best-effort self-healing registration for long-running sessions."""
        if not self._current_hotkey:
            return False

        if self._backend == "windows":
            if self._hotkey_id is None:
                return self.register_hotkey(self._current_hotkey)
            if self._windows_modifiers is None or self._windows_key_code is None:
                return self.register_hotkey(self._current_hotkey)
            try:
                # If registration was lost (sleep/session change), this restores it.
                ctypes.set_last_error(0)
                ok = ctypes.windll.user32.RegisterHotKey(
                    None,
                    int(self._hotkey_id),
                    int(self._windows_modifiers),
                    int(self._windows_key_code),
                )
                if not ok:
                    win_error = ctypes.get_last_error()
                    if win_error == ERROR_HOTKEY_ALREADY_REGISTERED:
                        return True
                    return self.register_hotkey(self._current_hotkey)
            except Exception:  # pragma: no cover - backend dependent
                logger.debug("Failed to probe windows hotkey registration", exc_info=True)
                return False
            return True

        if self._backend == "keyboard":
            return self._hotkey_id is not None or self.register_hotkey(self._current_hotkey)
        if self._backend == "pynput":
            return self._listener is not None or self.register_hotkey(self._current_hotkey)
        return False

    def _emit_hotkey(self) -> None:
        self.hotkey_activated.emit()

    def _setup_windows_backend(self) -> bool:
        if os.name != "nt":
            return False
        app = QCoreApplication.instance()
        if app is None:
            return False
        try:
            self._native_filter = _WindowsHotkeyEventFilter(self)
            app.installNativeEventFilter(self._native_filter)
            self._native_filter_installed = True
            return True
        except Exception as err:  # pragma: no cover - backend dependent
            logger.warning("Failed to install windows hotkey event filter: %s", err)
            self._native_filter = None
            self._native_filter_installed = False
            return False

    def _next_windows_hotkey_id(self) -> int:
        hotkey_id = self._windows_hotkey_id_counter
        self._windows_hotkey_id_counter += 1
        if self._windows_hotkey_id_counter > 0xBFFF:
            self._windows_hotkey_id_counter = 1
        return hotkey_id

    def _parse_windows_hotkey(self, hotkey: str) -> tuple[int, int] | None:
        parts = [part.strip().lower() for part in hotkey.split("+") if part.strip()]
        if len(parts) < 2:
            return None
        key_name = parts[-1]
        modifiers = 0
        for modifier in parts[:-1]:
            if modifier in {"ctrl", "control"}:
                modifiers |= MOD_CONTROL
            elif modifier == "alt":
                modifiers |= MOD_ALT
            elif modifier == "shift":
                modifiers |= MOD_SHIFT
            elif modifier in {"meta", "win", "cmd", "command"}:
                modifiers |= MOD_WIN
            else:
                return None
        if modifiers == 0:
            return None
        key_code = self._windows_key_to_vk(key_name)
        if key_code is None:
            return None
        return modifiers | MOD_NOREPEAT, key_code

    def _windows_key_to_vk(self, key_name: str) -> int | None:
        normalized_key = key_name.strip().lower().replace(" ", "")
        key_aliases = {
            "del": "delete",
            "ins": "insert",
            "pgup": "pageup",
            "pgdn": "pagedown",
            "pgdown": "pagedown",
            "return": "enter",
            "spacebar": "space",
            "\u043f\u0440\u043e\u0431\u0435\u043b": "space",  # "??????"
            "\u0443\u0434\u0430\u043b\u0438\u0442\u044c": "delete",  # "???????"
            "\u0432\u0441\u0442\u0430\u0432\u043a\u0430": "insert",  # "???????"
            "\u0441\u0442\u0440\u0432\u0432\u0435\u0440\u0445": "pageup",  # "????????"
            "\u0441\u0442\u0440\u0432\u043d\u0438\u0437": "pagedown",  # "???????"
        }
        normalized_key = key_aliases.get(normalized_key, normalized_key)

        if len(normalized_key) == 1:
            if "a" <= normalized_key <= "z" or "0" <= normalized_key <= "9":
                return ord(normalized_key.upper())
        if normalized_key.startswith("f") and normalized_key[1:].isdigit():
            value = int(normalized_key[1:])
            if 1 <= value <= 24:
                return 0x6F + value
        key_map = {
            "space": VK_SPACE,
            "tab": 0x09,
            "enter": 0x0D,
            "esc": 0x1B,
            "escape": 0x1B,
            "up": 0x26,
            "down": 0x28,
            "left": 0x25,
            "right": 0x27,
            "insert": 0x2D,
            "delete": 0x2E,
            "home": 0x24,
            "end": 0x23,
            "pageup": 0x21,
            "pagedown": 0x22,
            "plus": 0xBB,
            "=": 0xBB,
            "minus": 0xBD,
            "-": 0xBD,
            ",": 0xBC,
            ".": 0xBE,
            "/": 0xBF,
            "\\": 0xDC,
            ";": 0xBA,
            "'": 0xDE,
            "[": 0xDB,
            "]": 0xDD,
            "`": 0xC0,
        }
        return key_map.get(normalized_key)

    def _on_windows_hotkey(self, hotkey_id: int) -> None:
        if self._backend != "windows":
            return
        if self._hotkey_id is None:
            return
        if int(self._hotkey_id) != hotkey_id:
            return
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
