from types import SimpleNamespace

from applauncher.gui.local_shortcut_registry import LocalShortcutRegistry


class _SignalRecorder:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    def emit(self, item: dict) -> None:
        self.emitted.append(item)


class _KeyboardBackend:
    def __init__(self) -> None:
        self.registrations: list[tuple] = []
        self.removed: list[object] = []

    def add_hotkey(self, *args, **kwargs):
        self.registrations.append((args, kwargs))
        return "registration-id"

    def remove_hotkey(self, hotkey_id: object) -> None:
        self.removed.append(hotkey_id)


def test_item_hotkey_uses_global_keyboard_hook_and_gui_thread_bridge() -> None:
    backend = _KeyboardBackend()
    signal = _SignalRecorder()
    registry = LocalShortcutRegistry.__new__(LocalShortcutRegistry)
    registry._keyboard_module = backend
    registry._bridge = SimpleNamespace(activated=signal)
    registry._global_hotkey_ids = []
    item = {"name": "Editor", "path": "editor.exe"}

    assert registry._register_global_hotkey("Ctrl+Shift+E", item)

    args, kwargs = backend.registrations[0]
    assert args[0] == "ctrl+shift+e"
    assert kwargs == {"suppress": False, "trigger_on_release": True}
    args[1]()
    assert signal.emitted == [item]
    assert registry._global_hotkey_ids == ["registration-id"]


def test_clear_unregisters_global_item_hotkeys() -> None:
    backend = _KeyboardBackend()
    registry = LocalShortcutRegistry.__new__(LocalShortcutRegistry)
    registry._keyboard_module = backend
    registry._global_hotkey_ids = ["first", "second"]
    registry._shortcuts = []

    registry.clear()

    assert backend.removed == ["second", "first"]
    assert registry._global_hotkey_ids == []
