"""Validation and normalization helpers for launcher data."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from ..repository import DEFAULT_GROUP


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)
    if parsed.scheme == "steam":
        if parsed.netloc or parsed.path:
            return url
        return ""
    if not parsed.netloc:
        return ""
    return url


def read_url_shortcut(file_path: str) -> str:
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1251", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding) as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if line.lower().startswith("url="):
                        return line[4:].strip()
        except UnicodeError:
            continue
        except OSError:
            break
    return ""


def validate_app_data(data: dict | None) -> tuple[dict | None, str | None]:
    if not data:
        return None, None
    name = (data.get("name") or "").strip()
    if not name:
        return None, "Укажите название элемента"
    path_value = (data.get("path") or "").strip()
    data["name"] = name
    data["path"] = path_value
    item_type = data.get("type", "exe")
    args = data.get("args") or []
    if isinstance(args, str):
        args = [args]
    data["args"] = args
    if item_type == "url":
        normalized = normalize_url(path_value)
        if not normalized:
            return None, "Введите корректный URL (пример: https://example.com или steam://rungameid/550)"
        data["path"] = normalized
    elif item_type == "folder":
        if not path_value:
            return None, "Укажите путь к папке"
        if not os.path.isdir(path_value):
            return None, f"Папка не найдена:\n{path_value}"
        data["type"] = "folder"
    else:
        if not path_value:
            return None, "Укажите путь к исполняемому файлу"
        if not os.path.exists(path_value):
            return None, f"Файл не найден:\n{path_value}"
        suffix = Path(path_value).suffix.lower()
        data["type"] = "lnk" if suffix == ".lnk" else "exe"
    data.setdefault("group", DEFAULT_GROUP)
    data.setdefault("usage_count", 0)
    data.setdefault("favorite", False)
    data.setdefault("args", [])
    data.setdefault("source", "manual")
    return data, None
