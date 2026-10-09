"""Isolated full-window fixture: no real clipboard, global hotkeys or launches."""
from contextlib import ExitStack, contextmanager
import json
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from applauncher.repository import DEFAULT_GROUP
from applauncher.services.launcher_service import LauncherService


class MemoryClipboard(QObject):
    dataChanged = Signal()

    def __init__(self):
        super().__init__()
        self.value = ""

    def text(self):
        return self.value

    def setText(self, text):
        self.value = text
        self.dataChanged.emit()


class StubHotkeyService(QObject):
    hotkey_activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_hotkey = None
        self.last_error = None

    def register_hotkey(self, hotkey):
        self.current_hotkey = hotkey
        return True

    def unregister_hotkey(self):
        self.current_hotkey = None

    def ensure_hotkey_registered(self):
        return True


@contextmanager
def isolated_window(directory: Path, count: int = 200, tray: bool = False, theme: str | None = None):
    """Open the runtime window using only the supplied fixture directory."""
    import sys
    import applauncher.gui.app as runtime
    from applauncher.gui.styles import theme_mode

    app = QApplication.instance() or QApplication([])
    directory.mkdir(parents=True, exist_ok=True)
    icon = QPixmap(120, 96)
    icon.fill(QColor("#0a46d0"))
    icon_path = directory / "fixture.png"
    icon.save(str(icon_path))
    service = LauncherService(config_file=str(directory / "fixture.json"))
    service.theme_mode = theme if theme is not None else theme_mode()
    service.groups = [DEFAULT_GROUP] + [f"Группа {i}" for i in range(1, 16)]
    items = []
    for i in range(count):
        kind = ("exe", "folder", "url", "url")[i % 4]
        path = (sys.executable, str(directory), f"https://example.com/{i}", f"steam://run/{i}")[i % 4]
        items.append({
            "name": f"Очень длинное русское название элемента {i} 🚀",
            "path": path, "type": kind, "group": DEFAULT_GROUP,
            "favorite": i < 2, "local_hotkey": "Ctrl+1" if i == 0 else "",
            "icon_path": str(icon_path) if i % 3 == 0 else "",
            "custom_icon": i % 9 == 0,
        })
    service.repository.set_apps(items)
    service.notes = [{"id": "fixture", "title": "Заметка с форматированием",
                      "content_html": "<p><b>Жирный</b> <i>курсив</i> <u>подчёркнутый</u></p><p>" + "Строка заметки<br>" * 10 + "</p>",
                      "collapsed": False}]
    service.clipboard_history = [{"text": "Тестовая история буфера", "timestamp": "2026-10-09T12:00:00", "pinned": True}]
    Path(service.config_file).write_text(json.dumps(service.build_config_payload(), ensure_ascii=False), encoding="utf-8")
    clipboard = MemoryClipboard()
    with ExitStack() as stack:
        stack.enter_context(patch.object(runtime, "LauncherService", return_value=service))
        stack.enter_context(patch.object(service, "persist_config", return_value=None))
        stack.enter_context(patch.object(runtime, "HotkeyService", StubHotkeyService))
        stack.enter_context(patch.object(runtime.LocalShortcutRegistry, "_register_global_hotkey", return_value=False))
        stack.enter_context(patch.object(runtime, "LaunchService", return_value=Mock()))
        stack.enter_context(patch.object(runtime, "FileTransferService", return_value=Mock()))
        stack.enter_context(patch.object(QApplication, "clipboard", return_value=clipboard))
        stack.enter_context(patch.object(runtime.QSystemTrayIcon, "isSystemTrayAvailable", return_value=tray))
        stack.enter_context(patch.object(runtime.IconService, "cleanup_broken_png_cache", return_value=0))
        stack.enter_context(patch.object(runtime.IconService, "start_extraction"))
        window = runtime.AppLauncher()
        try:
            yield window
        finally:
            window._prepare_for_quit()
            window.tray_available = False
            with patch.object(runtime.QMessageBox, "question", return_value=runtime.QMessageBox.Yes):
                window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def settle():
    for _ in range(8):
        QApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
