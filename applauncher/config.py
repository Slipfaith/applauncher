"""Configuration helpers for the application launcher."""
from __future__ import annotations

import json
import os
import shutil
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: Dict[str, Any] = {
    "apps": [],
    "groups": ["Общее"],
    "view_mode": "grid",
}


class ConfigError(Exception):
    """Raised when configuration operations fail."""


def _normalize_loaded(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "apps": data or [],
            "groups": DEFAULT_CONFIG["groups"].copy(),
            "view_mode": DEFAULT_CONFIG["view_mode"],
        }
    apps = data.get("apps", [])
    groups = data.get("groups", DEFAULT_CONFIG["groups"].copy())
    view_mode = data.get("view_mode", DEFAULT_CONFIG["view_mode"])
    return {"apps": apps, "groups": groups, "view_mode": view_mode}


def load_config(path: str) -> Dict[str, Any]:
    """Load configuration from JSON with validation."""
    if not os.path.exists(path):
        return DEFAULT_CONFIG.copy()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError("Поврежден файл конфигурации") from exc
    except OSError as exc:  # pragma: no cover - filesystem dependent
        raise ConfigError("Не удалось прочитать конфигурацию") from exc

    return _normalize_loaded(data)


def save_config(path: str, payload: Dict[str, Any], backup: bool = True) -> None:
    """Persist configuration atomically with optional backup."""
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
