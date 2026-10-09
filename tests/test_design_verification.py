"""The verification entrypoint must not start ordinary launcher side effects."""
import json
import subprocess
import sys

from PySide6.QtWidgets import QApplication


def test_verification_entrypoint_is_isolated(monkeypatch, tmp_path):
    import main
    import applauncher.config as config

    def forbidden(*args, **kwargs):
        raise AssertionError("ordinary application state accessed")

    monkeypatch.setattr(main, "run_app", forbidden)
    monkeypatch.setattr(main, "setup_logging", forbidden)
    monkeypatch.setattr(config, "resolve_config_path", forbidden)
    monkeypatch.setattr(QApplication, "clipboard", forbidden)
    monkeypatch.setattr(sys, "argv", ["applauncher", "--verify-design", str(tmp_path)])
    assert main.main() == 0
    result = json.loads((tmp_path / "verification.json").read_text(encoding="utf-8"))
    assert result["passed"] is True
    assert [item["theme"] for item in result["themes"]] == ["light", "dark"]
    assert all(item["settings_mode"] == item["theme"] for item in result["themes"])
    assert (tmp_path / "settings_light.png").is_file() and (tmp_path / "settings_dark.png").is_file()
    for theme in ("light", "dark"):
        for kind in ("folder", "url", "exe"):
            assert (tmp_path / f"icon_{kind}_{theme}.png").is_file()
    assert (tmp_path / "light.png").is_file() and (tmp_path / "dark.png").is_file()


def test_font_fallback_warning_is_retained_by_normal_logging(tmp_path):
    script = """
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
import applauncher.config as config
from applauncher.logger import setup_logging
from applauncher.gui import styles
config.resolve_config_path = lambda: str(Path(sys.argv[1]) / 'fixture.json')
setup_logging()
app = QApplication([])
styles._font_dirs = lambda: []
styles.apply_design_system(app, theme='light')
assert styles.register_fonts() == ()
"""
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=True, timeout=20)
    warnings = (tmp_path / "design_warnings.log").read_text(encoding="utf-8")
    assert "Onest-Variable.ttf" in warnings
    assert "JetBrainsMono-Variable.ttf" in warnings
