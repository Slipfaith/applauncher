"""Exercise the real Settings selector without user config, launches or clipboard."""
import json
import cProfile
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
from applauncher.gui import styles
from applauncher.services.launcher_service import LauncherService
from ui_fixture import isolated_window, settle


def main():
    output = Path(__file__).resolve().parent
    app = QApplication([])
    app.setStyle("Fusion")
    result = {"platform": app.platformName(), "samples": []}
    profiler = cProfile.Profile()
    with isolated_window(output / "fixture_theme_switch", count=200, theme="auto") as window:
        window.setWindowOpacity(1.0)
        window.show()
        window.show_settings()
        settle()
        settings = window.settings_dialog
        tile = window.grid_layout.itemAt(0).widget()
        for mode in ("dark", "light", "auto"):
            started = perf_counter()
            if "--profile" in sys.argv:
                profiler.enable()
            settings.theme_combo.setCurrentIndex(settings.theme_combo.findData(mode))
            if "--profile" in sys.argv:
                profiler.disable()
            synchronous_ms = (perf_counter() - started) * 1000
            settle()
            painted_ms = (perf_counter() - started) * 1000
            colors = styles.active_colors()
            assert window.service.theme_mode == mode
            assert styles.theme_mode() == mode
            assert settings.palette().color(QPalette.Text).name() == colors.text_primary
            assert tile is window.grid_layout.itemAt(0).widget()
            assert LauncherService.persist_config(window.service) is None
            restored = LauncherService(config_file=window.service.config_file)
            assert restored.load_state() is None and restored.theme_mode == mode
            window.grab().save(str(output / f"theme_switch_{mode}_window.png"))
            settings.grab().save(str(output / f"theme_switch_{mode}_settings.png"))
            result["samples"].append({"mode": mode, "resolved": styles.active_theme(),
                                      "synchronous_ms": round(synchronous_ms, 2),
                                      "painted_ms": round(painted_ms, 2),
                                      "dialog_size": [settings.width(), settings.height()],
                                      "persisted": restored.theme_mode})
        result["passed"] = True
    if "--profile" in sys.argv:
        profiler.dump_stats(str(output / "theme_switch.pstats"))
    (output / "theme_switch_smoke.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
