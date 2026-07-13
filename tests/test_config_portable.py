from pathlib import Path
import builtins

import applauncher.config as config_module


def test_resolve_config_path_uses_portable_marker(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / config_module.PORTABLE_MARKER).write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    resolved = Path(config_module.resolve_config_path("portable_config.json"))

    assert resolved == tmp_path / "portable_config.json"


def test_resolve_icons_cache_dir_uses_portable_marker(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / config_module.PORTABLE_MARKER).write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    resolved = Path(config_module.resolve_icons_cache_dir("icon_cache"))

    assert resolved == tmp_path / "icon_cache"
    assert resolved.exists()


def test_resolve_config_path_falls_back_if_portable_dir_not_writable(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / config_module.PORTABLE_MARKER).write_text("", encoding="utf-8")
    fallback_appdata = tmp_path / "appdata"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APPDATA", str(fallback_appdata))
    original_open = builtins.open
    probe_name = f".{config_module.APP_NAME.lower()}_portable_write_check.tmp"

    def failing_open(file, mode="r", *args, **kwargs):
        if Path(file).name == probe_name and "w" in mode:
            raise OSError("no write permissions")
        return original_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", failing_open)

    resolved = Path(config_module.resolve_config_path("launcher_config.json"))

    assert resolved == fallback_appdata / config_module.APP_NAME / "launcher_config.json"
