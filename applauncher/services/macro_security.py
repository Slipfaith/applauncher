"""Safety checks for macro execution."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _normalize_path(path: Path) -> Path:
    try:
        return path.resolve()
    except FileNotFoundError:
        return path.absolute()


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _system_dirs() -> list[Path]:
    if sys.platform.startswith("win"):
        return [
            Path(os.environ.get("SystemRoot", "C:\\Windows")),
            Path(os.environ.get("WINDIR", "C:\\Windows")),
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
            Path(os.environ.get("ProgramData", "C:\\ProgramData")),
        ]
    return [
        Path("/"),
        Path("/bin"),
        Path("/sbin"),
        Path("/usr"),
        Path("/lib"),
        Path("/lib64"),
        Path("/etc"),
        Path("/var"),
        Path("/System"),
        Path("/Library"),
    ]


def is_restricted_macro_path(input_path: str) -> tuple[bool, str | None]:
    """Check whether a macro input path is restricted for safety reasons."""
    if not input_path:
        return True, "Путь входных данных не указан."
    resolved = _normalize_path(Path(input_path))
    target = resolved if resolved.is_dir() else resolved.parent
    anchor = Path(target.anchor or "/")
    if _normalize_path(target) == _normalize_path(anchor):
        return True, "Запрещено выполнять макросы для корневых каталогов."
    for system_dir in _system_dirs():
        system_dir = _normalize_path(system_dir)
        if _is_relative_to(target, system_dir):
            return True, "Запрещено выполнять макросы для системных каталогов."
    return False, None
