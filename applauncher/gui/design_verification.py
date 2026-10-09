"""Isolated design verification for the packaged executable, without user state."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontInfo, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from .glyphs import GlyphButton
from .fallback_icons import fallback_icon
from .dialogs.settings_dialog import SettingsDialog
from .styles import active_theme, apply_design_system, register_fonts
from .widgets import AppButton


def verify_design(arguments: list[str]) -> int:
    """Render both bundled themes and write a machine-readable resource result."""
    parser = argparse.ArgumentParser(description="Verify bundled fonts and themes without starting the launcher")
    parser.add_argument("output", type=Path)
    args = parser.parse_args(arguments)
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    warnings: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            warnings.append(record.getMessage())

    handler = Capture()
    logging.getLogger("applauncher.gui.styles").addHandler(handler)
    result = {"frozen": bool(getattr(sys, "frozen", False)), "platform": app.platformName(),
              "font_families": [], "themes": [], "warnings": warnings}
    try:
        icons = {kind: fallback_icon({"type": kind}) for kind in ("folder", "url", "exe")}
        settings = SettingsDialog("Ctrl+Alt+Space", 0.75)
        settings.themeChanged.connect(lambda mode: apply_design_system(app, theme=mode))
        settings.show()
        for theme in ("light", "dark"):
            settings.theme_combo.setCurrentIndex(settings.theme_combo.findData(theme))
            panel = QWidget()
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)
            label = QLabel("Onest — Проверка русского текста")
            layout.addWidget(label)
            mono = QLabel("Ctrl + Alt + Space")
            mono.setProperty("role", "hotkeyDisplay")
            layout.addWidget(mono)
            tile = AppButton({"name": "Очень длинное русское название с многоточием", "type": "url", "path": "https://example.com"})
            layout.addWidget(tile)
            button = GlyphButton("copy", tooltip="Скопировать")
            layout.addWidget(button)
            panel.resize(360, 300)
            panel.show()
            button.setFocus()
            app.processEvents()
            panel.grab().save(str(args.output / f"{theme}.png"))
            settings.grab().save(str(args.output / f"settings_{theme}.png"))
            for kind, icon in icons.items():
                icon.pixmap(QSize(64, 64), 1.0).save(str(args.output / f"icon_{kind}_{theme}.png"))
            result["themes"].append({"theme": active_theme(), "text": app.palette().color(QPalette.Text).name(),
                                     "ui_font": QFontInfo(label.font()).family(),
                                     "mono_font": QFontInfo(mono.font()).family(),
                                     "settings_mode": settings.theme_combo.currentData(),
                                     "settings_text": settings.palette().color(QPalette.Text).name(),
                                     "fallback_icons": [icon.name() for icon in icons.values()],
                                     "tile_elided": "…" in tile.text()})
            panel.close()
            panel.deleteLater()
        result["font_families"] = list(register_fonts())
        result["passed"] = (not warnings and {"Onest", "JetBrains Mono"} <= set(result["font_families"])
                            and all(item["ui_font"] == "Onest" and item["mono_font"] == "JetBrains Mono"
                                    and item["tile_elided"] and item["settings_mode"] == item["theme"]
                                    and item["fallback_icons"] == ["applauncher-line-folder", "applauncher-line-link", "applauncher-line-app"]
                                    and item["settings_text"] == item["text"] for item in result["themes"]))
        settings.close()
        settings.deleteLater()
    finally:
        logging.getLogger("applauncher.gui.styles").removeHandler(handler)
        (args.output / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result.get("passed") else 1
