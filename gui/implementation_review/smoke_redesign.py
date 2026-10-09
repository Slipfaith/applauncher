"""Run from the project root; all state and screenshots stay beside the plan."""
import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget
from applauncher.gui.styles import apply_design_system
from ui_fixture import isolated_window, settle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="redesign")
    parser.add_argument("--theme", choices=["auto", "light", "dark"], default="auto")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--dialogs", action="store_true")
    parser.add_argument("--opacity", action="store_true")
    args = parser.parse_args()
    global apply_design_system
    if args.baseline:
        # Load the recorded Git baseline in this verification process only.
        import importlib
        import subprocess
        for name, filename in [
            ("applauncher.gui.styles", "applauncher/gui/styles.py"),
            ("applauncher.gui.widgets.notes_widget", "applauncher/gui/widgets/notes_widget.py"),
            ("applauncher.gui.widgets", "applauncher/gui/widgets/__init__.py"),
            ("applauncher.gui.app", "applauncher/gui/app.py"),
        ]:
            module = importlib.import_module(name)
            source = subprocess.check_output(["git", "show", f"90bc36b:{filename}"], cwd=ROOT)
            exec(compile(source, filename, "exec"), module.__dict__)
        from applauncher.gui.styles import apply_design_system
    app = QApplication.instance() or QApplication([])
    if app.platformName() == "offscreen":
        # Windows offscreen does not enumerate system fallback faces (emoji too).
        import os
        from PySide6.QtGui import QFontDatabase
        font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf", "seguiemj.ttf"):
            if (font_dir / filename).exists():
                QFontDatabase.addApplicationFont(str(font_dir / filename))
    app.setStyle("Fusion")
    try:
        apply_design_system(app, theme=args.theme)
    except TypeError:  # baseline runtime had no theme argument
        apply_design_system(app)
    output = Path(__file__).resolve().parent
    with isolated_window(output / ("fixture_" + args.label)) as window:
        window.resize(1000, 620)
        window.show()
        settle()
        if args.interactive:
            return app.exec()
        result = {"platform": app.platformName(), "scale": window.devicePixelRatioF(), "runs": [],
                  "screens": [{"geometry": [screen.geometry().width(), screen.geometry().height()],
                               "available": [screen.availableGeometry().width(), screen.availableGeometry().height()],
                               "logical_dpi": screen.logicalDotsPerInch(), "device_ratio": screen.devicePixelRatio()}
                              for screen in app.screens()]}
        for width, height in [(1280, 640), (680, 440)]:
            available = window.screen().availableGeometry()
            actual_width = min(width, available.width()) if app.platformName() == "windows" else width
            actual_height = min(height, available.height()) if app.platformName() == "windows" else height
            window.resize(actual_width, actual_height)
            for section in range(5):
                window.section_tabs.setCurrentIndex(section)
                for mode in (["grid", "list"] if section < 3 else ["grid"]):
                    start = perf_counter()
                    if section < 3:
                        window.set_view_mode(mode)
                    settle()
                    elapsed = perf_counter() - start
                    window.grab().save(str(output / f"{args.label}_{width}x{height}_section{section}_{mode}.png"))
                    result["runs"].append({"requested_size": [width, height], "size": [window.width(), window.height()], "section": section,
                                           "mode": mode, "seconds": elapsed,
                                           "scroll_max": window.scroll_area.verticalScrollBar().maximum()})
        if args.dialogs:
            from unittest.mock import patch
            from applauncher.gui.dialogs import AddAppDialog, HotkeyCaptureDialog, SettingsDialog
            from applauncher.gui.widgets.notes_widget import NoteEditorPopup
            result["dialogs"] = []
            dialogs = [
                ("settings", SettingsDialog("Ctrl+Space", 0.75, window)),
                ("add", AddAppDialog(window, groups=window.groups)),
                ("hotkey", HotkeyCaptureDialog(window, current_hotkey="Ctrl+Alt+Space")),
                ("note", NoteEditorPopup(window.service.notes[0], window)),
            ]
            for name, dialog in dialogs:
                with patch.object(dialog, "grabKeyboard"), patch.object(dialog, "releaseKeyboard"):
                    dialog.show()
                    settle()
                    dialog.grab().save(str(output / f"{args.label}_dialog_{name}.png"))
                    result["dialogs"].append({"name": name, "size": [dialog.width(), dialog.height()]})
                    dialog.close()
            settle()
        if args.opacity and app.platformName() == "windows":
            from PySide6.QtTest import QTest
            window.section_tabs.setCurrentIndex(0)
            window.set_view_mode("grid")
            window.resize(680, 440)
            window.move(100, 100)
            result["opacity"] = []
            backdrop = QWidget()
            backdrop.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
            backdrop.setGeometry(window.geometry())
            for color in ("#ffffff", "#101010"):
                backdrop.setStyleSheet(f"background-color: {color}")
                backdrop.show()
                for opacity in (0.75, 1.0):
                    window.setWindowOpacity(opacity)
                    window.raise_()
                    window.activateWindow()
                    settle()
                    QTest.qWait(200)
                    rect = window.geometry()
                    shot = window.screen().grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
                    filename = f"{args.label}_opacity{int(opacity*100)}_bg{color[1:]}.png"
                    shot.save(str(output / filename))
                    result["opacity"].append({"opacity": opacity, "background": color, "captured": not shot.isNull(), "file": filename})
            backdrop.close()
            backdrop.deleteLater()
            window.setWindowOpacity(window.service.window_opacity)
        (output / f"{args.label}_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
