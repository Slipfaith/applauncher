"""Configuration helpers for the application launcher."""
from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

APP_NAME = "AppLauncher"

DEFAULT_CONFIG: Dict[str, Any] = {
    "apps": [],
    "groups": ["Общее"],
    "view_mode": "grid",
    "macros": [],
    "macro_groups": [".vbs", ".vba", ".py"],
    "macro_view_mode": "grid",
    "global_hotkey": "Ctrl+Alt+Space",
    "window_opacity": 0.75,
    "notes": [],
}


class ConfigError(Exception):
    """Raised when configuration operations fail."""


def _normalize_loaded(data: Any) -> Dict[str, Any]:
    def normalize_list(value: Any, default: list) -> list:
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return list(value.values())
        return default.copy()

    def normalize_groups(value: Any, default: list) -> list:
        if isinstance(value, list) and value:
            return value
        return default.copy()

    if not isinstance(data, dict):
        return {
            "apps": normalize_list(data, []),
            "groups": DEFAULT_CONFIG["groups"].copy(),
            "view_mode": DEFAULT_CONFIG["view_mode"],
            "macros": [],
            "macro_groups": DEFAULT_CONFIG["macro_groups"].copy(),
            "macro_view_mode": DEFAULT_CONFIG["macro_view_mode"],
            "global_hotkey": DEFAULT_CONFIG["global_hotkey"],
            "window_opacity": DEFAULT_CONFIG["window_opacity"],
            "notes": [],
        }
    apps = normalize_list(data.get("apps"), [])
    groups = normalize_groups(data.get("groups"), DEFAULT_CONFIG["groups"])
    view_mode = data.get("view_mode", DEFAULT_CONFIG["view_mode"])
    macros = normalize_list(data.get("macros"), [])
    macro_groups = normalize_groups(data.get("macro_groups"), DEFAULT_CONFIG["macro_groups"])
    macro_view_mode = data.get("macro_view_mode", DEFAULT_CONFIG["macro_view_mode"])
    global_hotkey = data.get("global_hotkey", DEFAULT_CONFIG["global_hotkey"])
    window_opacity = data.get("window_opacity", DEFAULT_CONFIG["window_opacity"])
    notes = normalize_list(data.get("notes"), [])
    return {
        "apps": apps,
        "groups": groups,
        "view_mode": view_mode,
        "macros": macros,
        "macro_groups": macro_groups,
        "macro_view_mode": macro_view_mode,
        "global_hotkey": global_hotkey,
        "window_opacity": window_opacity,
        "notes": notes,
    }


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_config(path: str) -> Dict[str, Any]:
    """Load configuration from JSON with validation."""
    if not os.path.exists(path):
        return DEFAULT_CONFIG.copy()

    try:
        data = _load_json(path)
    except json.JSONDecodeError as exc:
        backup_path = f"{path}.bak"
        if os.path.exists(backup_path):
            try:
                backup_data = _load_json(backup_path)
            except (json.JSONDecodeError, OSError):
                raise ConfigError("Поврежден файл конфигурации") from exc
            restored = _normalize_loaded(backup_data)
            logger.warning("Конфигурация восстановлена из бэкапа: %s", backup_path)
            try:
                save_config(path, restored, backup=False)
            except ConfigError as save_exc:
                logger.warning("Не удалось сохранить восстановленную конфигурацию: %s", save_exc)
            return restored
        raise ConfigError("Поврежден файл конфигурации") from exc
    except OSError as exc:  # pragma: no cover - filesystem dependent
        raise ConfigError("Не удалось прочитать конфигурацию") from exc

    return _normalize_loaded(data)


def resolve_config_path(filename: str = "launcher_config.json") -> str:
    """Resolve a per-user configuration path for the launcher."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        base_dir = Path(appdata)
    else:
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            base_dir = Path(xdg_config_home)
        else:
            base_dir = Path.home() / ".config"
    config_dir = base_dir / APP_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return str(config_dir / filename)


def resolve_icons_cache_dir(folder_name: str = "launcher_icons") -> str:
    """Resolve a per-user cache directory for extracted icons."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        base_dir = Path(appdata)
    else:
        xdg_cache_home = os.environ.get("XDG_CACHE_HOME") or os.environ.get("XDG_CONFIG_HOME")
        if xdg_cache_home:
            base_dir = Path(xdg_cache_home)
        else:
            base_dir = Path.home() / ".cache"
    cache_dir = base_dir / APP_NAME / folder_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    return str(cache_dir)


def save_config(path: str, payload: Dict[str, Any], backup: bool = True) -> None:
    """Persist configuration atomically with optional backup."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if backup and os.path.exists(path):
        backup_path = f"{path}.bak"
        try:
            shutil.copyfile(path, backup_path)
        except OSError as exc:  # pragma: no cover - filesystem dependent
            logger.warning("Не удалось создать бэкап конфигурации: %s", exc)

    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except OSError as exc:  # pragma: no cover - filesystem dependent
        raise ConfigError("Не удалось сохранить конфигурацию") from exc
