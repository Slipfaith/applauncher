"""Windows lifecycle and IPC smoke on an isolated window, with bounded hotkey use."""
import ctypes
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from PySide6.QtCore import QPoint, Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from applauncher.gui.styles import apply_design_system
from applauncher.services.hotkey_service import HotkeyService, WM_HOTKEY
from ui_fixture import isolated_window, settle


def main():
    app = QApplication([])
    app.setStyle("Fusion")
    apply_design_system(app)
    output = Path(__file__).resolve().parent
    result = {"platform": app.platformName(), "tray_available": QSystemTrayIcon.isSystemTrayAvailable()}
    with isolated_window(output / "native_fixture", count=4, tray=result["tray_available"]) as window:
        window.show()
        window.activateWindow()
        settle()
        window.resize(900, 520)
        settle()
        assert (window.width(), window.height()) == (900, 520)
        result["resize_programmatic"] = "passed"
        QTest.keyClick(window.title_bar.max_button, Qt.Key_Return)
        settle()
        assert window.isMaximized() and window.title_bar.max_button.accessibleName() == "Восстановить"
        QTest.keyClick(window.title_bar.max_button, Qt.Key_Space)
        settle()
        assert not window.isMaximized()
        result["maximize_restore_native"] = "passed"
        old_position = window.pos()
        bar = window.title_bar
        bar.start = None
        QTest.mousePress(bar, Qt.LeftButton, pos=QPoint(180, 20))
        QTest.mouseMove(bar, QPoint(200, 30))
        QTest.mouseRelease(bar, Qt.LeftButton, pos=QPoint(200, 30))
        settle()
        assert window.pos() == old_position + QPoint(20, 10)
        result["title_drag_synthetic"] = "passed"
        if window.tray_icon:
            with patch.object(window.tray_icon, "showMessage"):
                QTest.keyClick(bar.close_button, Qt.Key_Return)
            assert not window.isVisible() and window.tray_icon.isVisible()
            window.show()
            result["tray_close_hide"] = "passed"
        else:
            result["tray_close_hide"] = "unverified"

        server = QLocalServer()
        assert server.listen(f"applauncher_redesign_smoke_{os.getpid()}")
        app._single_instance_server = server
        received = Mock()
        window.handle_external_paths = received
        window.bind_single_instance_server(server)
        client = QLocalSocket()
        client.connectToServer(server.serverName())
        assert client.waitForConnected(2000)
        client.write(json.dumps({"args": [str(output / "native_fixture")]}).encode("utf-8") + b"\n")
        client.flush()
        QTest.qWait(200)
        settle()
        received.assert_called_once_with([str(output / "native_fixture")])
        client.disconnectFromServer()
        server.close()
        result["isolated_ipc_argument_delivery"] = "passed"

    hotkeys = HotkeyService()
    activation = []
    hotkeys.hotkey_activated.connect(lambda: activation.append(True))
    try:
        registered = hotkeys.register_hotkey("Ctrl+Alt+Shift+F10")
        result["global_hotkey_registration"] = "passed" if registered else "unverified"
        result["hotkey_error"] = hotkeys.last_error
        if registered and hotkeys._backend == "windows":
            # Exercise Qt's native event filter without injecting keyboard input.
            thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
            ctypes.windll.user32.PostThreadMessageW(thread_id, WM_HOTKEY, hotkeys._hotkey_id, 0)
            QTest.qWait(100)
            settle()
            assert activation == [True]
            result["global_hotkey_synthetic_dispatch"] = "passed"
    finally:
        hotkeys.unregister_hotkey()
        result["global_hotkey_released"] = hotkeys._hotkey_id is None
    result["manual_edge_drag"] = "unverified"
    result["physical_global_keypress"] = "unverified"
    result["explorer_outlook_drop"] = "unverified"
    (output / "native_smoke.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
