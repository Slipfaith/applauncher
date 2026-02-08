"""Validation and normalization helpers for launcher data."""
from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from ..repository import DEFAULT_GROUP, DEFAULT_MACRO_GROUPS

logger = logging.getLogger(__name__)


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


def is_unc_path(path_value: str) -> bool:
    """Return True for UNC paths like \\\\server\\share\\folder."""
    value = (path_value or "").strip()
    if not value:
        return False
    normalized = value.replace("/", "\\")
    if not normalized.startswith("\\\\"):
        return False
    tail = normalized[2:]
    parts = [part for part in tail.split("\\") if part]
    return len(parts) >= 2


def read_url_shortcut(file_path: str) -> str:
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1251", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding) as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith("["):
                        continue
                    key, separator, value = line.partition("=")
                    if separator and key.strip().lower() == "url":
                        return value.strip().strip('"')
        except UnicodeError:
            continue
        except OSError:
            break
    return ""


def read_lnk_shortcut(file_path: str) -> dict | None:
    if sys.platform != "win32":
        return None
    if not os.path.exists(file_path):
        return None
    escaped_path = file_path.replace("'", "''")
    script = (
        "$ErrorActionPreference='Stop';"
        "$shell=New-Object -ComObject WScript.Shell;"
        f"$shortcut=$shell.CreateShortcut('{escaped_path}');"
        "$obj=[PSCustomObject]@{"
        "target=$shortcut.TargetPath;"
        "arguments=$shortcut.Arguments;"
        "icon=$shortcut.IconLocation;"
        "working_dir=$shortcut.WorkingDirectory"
        "};"
        "$obj | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error("PowerShell превысил время ожидания при чтении .lnk: %s", exc)
        return None
    except (OSError, subprocess.CalledProcessError) as exc:
        logger.error("Не удалось прочитать .lnk через PowerShell: %s", exc)
        return None
    raw_output = result.stdout.strip()
    if not raw_output:
        return None
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "target": (payload.get("target") or "").strip(),
        "arguments": (payload.get("arguments") or "").strip(),
        "icon": (payload.get("icon") or "").strip(),
        "working_dir": (payload.get("working_dir") or "").strip(),
    }


def _split_arguments(argument_line: str) -> list[str]:
    if not argument_line:
        return []
    try:
        return shlex.split(argument_line, posix=False)
    except ValueError:
        return [argument_line]


def _normalize_if_url(value: str) -> str:
    if not value:
        return ""
    candidate = value.strip().strip('"')
    lowered = candidate.lower()
    if lowered.startswith(("http://", "https://", "steam://")):
        return normalize_url(candidate)
    return ""


def _extract_icon_path(icon_location: str) -> str:
    if not icon_location:
        return ""
    path_part = icon_location.split(",", 1)[0].strip().strip('"')
    if path_part and os.path.exists(path_part):
        return path_part
    return ""


def extract_shortcut_data(file_path: str) -> dict | None:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".url":
        target_url = read_url_shortcut(file_path)
        normalized = normalize_url(target_url)
        if normalized:
            return {"type": "url", "path": normalized, "args": [], "icon_path": ""}
        return None
    if suffix == ".lnk":
        lnk_data = read_lnk_shortcut(file_path)
        if not lnk_data:
            return None
        target = lnk_data.get("target", "")
        arguments = lnk_data.get("arguments", "")
        url_value = _normalize_if_url(target) or _normalize_if_url(arguments)
        if url_value:
            return {"type": "url", "path": url_value, "args": [], "icon_path": ""}
        if target:
            return {
                "type": "exe",
                "path": target,
                "args": _split_arguments(arguments),
                "icon_path": _extract_icon_path(lnk_data.get("icon", "")),
            }
    return None


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
        data["raw_path"] = path_value
        normalized = normalize_url(path_value)
        if not normalized:
            return None, "Введите корректный URL (пример: https://example.com или steam://rungameid/550)"
        data["path"] = normalized
    elif item_type == "folder":
        data["raw_path"] = ""
        if not path_value:
            return None, "Укажите путь к папке"
        if not os.path.isdir(path_value) and not is_unc_path(path_value):
            return None, f"Папка не найдена:\n{path_value}"
        data["type"] = "folder"
    else:
        data["raw_path"] = ""
        if not path_value:
            return None, "Укажите путь к исполняемому файлу"
        if not os.path.exists(path_value):
            return None, f"Файл не найден:\n{path_value}"
        suffix = Path(path_value).suffix.lower()
        data["type"] = "lnk" if suffix == ".lnk" else "exe"
    group = (data.get("group") or "").strip()
    data["group"] = group or DEFAULT_GROUP
    data.setdefault("usage_count", 0)
    data.setdefault("favorite", False)
    data.setdefault("args", [])
    data.setdefault("source", "manual")
    data.setdefault("disabled", False)
    data.setdefault("disabled_reason", "")
    data.setdefault("invalid", False)
    data.setdefault("invalid_reason", "")
    return data, None


def validate_macro_data(data: dict | None) -> tuple[dict | None, str | None]:
    if not data:
        return None, None
    name = (data.get("name") or "").strip()
    if not name:
        return None, "Укажите название макроса"
    path_value = (data.get("path") or "").strip()
    if not path_value:
        return None, "Укажите путь к файлу макроса"
    if not os.path.exists(path_value):
        return None, f"Файл не найден:\n{path_value}"
    suffix = Path(path_value).suffix.lower()
    if suffix not in set(DEFAULT_MACRO_GROUPS):
        return None, "Выберите файл макроса с расширением .vbs, .vba или .py"
    selected_group = (data.get("group") or "").strip().lower()
    if selected_group and selected_group != suffix:
        return None, "Тип макроса не совпадает с расширением выбранного файла"
    description = (data.get("description") or "").strip()
    data["name"] = name
    data["path"] = path_value
    data["description"] = description
    data["type"] = suffix.lstrip(".")
    data["group"] = suffix
    data.setdefault("usage_count", 0)
    data.setdefault("favorite", False)
    data.setdefault("args", [])
    data.setdefault("source", "manual")
    data.setdefault("disabled", False)
    data.setdefault("disabled_reason", "")
    data.setdefault("invalid", False)
    data.setdefault("invalid_reason", "")
    return data, None


def soft_validate_app_data(data: dict | None) -> dict | None:
    if not data:
        return None
    validated, error = validate_app_data(dict(data))
    if not error and validated:
        validated["invalid"] = False
        validated["invalid_reason"] = ""
        if validated.get("type") == "url":
            validated.setdefault("raw_path", data.get("raw_path") or validated.get("path", ""))
        return validated
    fallback = dict(data)
    name = (fallback.get("name") or "").strip()
    path_value = (fallback.get("path") or "").strip()
    if not name:
        name = path_value or "Без названия"
    fallback["name"] = name
    fallback["path"] = path_value
    args = fallback.get("args") or []
    if isinstance(args, str):
        args = [args]
    fallback["args"] = args
    fallback.setdefault("type", "exe")
    fallback.setdefault("group", DEFAULT_GROUP)
    fallback.setdefault("usage_count", 0)
    fallback.setdefault("favorite", False)
    fallback.setdefault("source", "manual")
    if fallback.get("type") == "url":
        fallback.setdefault("raw_path", fallback.get("raw_path") or path_value)
    fallback["invalid"] = True
    fallback["invalid_reason"] = error or "Некорректные данные"
    fallback["disabled"] = True
    fallback["disabled_reason"] = fallback["invalid_reason"]
    return fallback


def soft_validate_macro_data(data: dict | None) -> dict | None:
    if not data:
        return None
    validated, error = validate_macro_data(dict(data))
    if not error and validated:
        validated["invalid"] = False
        validated["invalid_reason"] = ""
        return validated
    fallback = dict(data)
    name = (fallback.get("name") or "").strip()
    path_value = (fallback.get("path") or "").strip()
    if not name:
        name = path_value or "Без названия"
    fallback["name"] = name
    fallback["path"] = path_value
    fallback.setdefault("description", (fallback.get("description") or "").strip())
    fallback.setdefault("type", (fallback.get("type") or "").strip())
    fallback.setdefault("group", (fallback.get("group") or DEFAULT_GROUP))
    fallback.setdefault("usage_count", 0)
    fallback.setdefault("favorite", False)
    fallback.setdefault("source", "manual")
    fallback["invalid"] = True
    fallback["invalid_reason"] = error or "Некорректные данные"
    fallback["disabled"] = True
    fallback["disabled_reason"] = fallback["invalid_reason"]
    return fallback
