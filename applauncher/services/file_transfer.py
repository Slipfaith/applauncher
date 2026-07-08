"""Helpers for copying dropped files and folders into a target folder.

Supports two drop sources:
- Windows Explorer (local file URLs);
- Outlook and other apps that expose virtual files via the
  ``FileGroupDescriptorW``/``FileContents`` OLE formats.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

FILE_ATTRIBUTE_DIRECTORY = 0x10
FD_ATTRIBUTES = 0x04

# FILEGROUPDESCRIPTOR layout: UINT cItems + FILEDESCRIPTOR entries.
_DESCRIPTOR_ENTRY_SIZE_W = 592
_DESCRIPTOR_ENTRY_SIZE_A = 332
_DESCRIPTOR_FLAGS_OFFSET = 0
_DESCRIPTOR_ATTRS_OFFSET = 36
_DESCRIPTOR_NAME_OFFSET = 72

_INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

OUTLOOK_CONTENT_UNAVAILABLE = (
    "Не удалось получить содержимое файла из перетаскивания. "
    "Сохраните файл на диск и перетащите его из Проводника."
)
OUTLOOK_SINGLE_FILE_ONLY = (
    "За раз можно перетащить только один файл из Outlook — скопирован первый."
)


@dataclass
class DropItem:
    """One droppable entity: either a local path or in-memory content."""

    name: str
    path: str | None = None
    data: bytes | None = None


def sanitize_file_name(name: str) -> str:
    cleaned = _INVALID_NAME_CHARS.sub("_", (name or "").strip())
    return cleaned.strip(". ") or "Без названия"


def _find_format(formats: list[str], marker: str) -> str | None:
    marker = marker.lower()
    for fmt in formats:
        if marker in fmt.lower():
            return fmt
    return None


def has_virtual_files(mime) -> bool:
    """Check whether the mime data carries virtual files (Outlook-style)."""
    return _find_format(list(mime.formats()), "FileGroupDescriptor") is not None


def _parse_group_descriptor(raw: bytes, wide: bool) -> list[tuple[str, bool]]:
    """Return (file name, is_directory) pairs from FILEGROUPDESCRIPTOR bytes."""
    if len(raw) < 4:
        return []
    count = struct.unpack_from("<I", raw, 0)[0]
    entry_size = _DESCRIPTOR_ENTRY_SIZE_W if wide else _DESCRIPTOR_ENTRY_SIZE_A
    name_size = 520 if wide else 260
    entries: list[tuple[str, bool]] = []
    for index in range(count):
        base = 4 + index * entry_size
        if base + entry_size > len(raw):
            break
        flags = struct.unpack_from("<I", raw, base + _DESCRIPTOR_FLAGS_OFFSET)[0]
        attrs = struct.unpack_from("<I", raw, base + _DESCRIPTOR_ATTRS_OFFSET)[0]
        name_raw = raw[base + _DESCRIPTOR_NAME_OFFSET : base + _DESCRIPTOR_NAME_OFFSET + name_size]
        if wide:
            name = name_raw.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]
        else:
            name = name_raw.decode("mbcs", errors="ignore").split("\x00", 1)[0]
        is_dir = bool(flags & FD_ATTRIBUTES) and bool(attrs & FILE_ATTRIBUTE_DIRECTORY)
        if name:
            entries.append((name, is_dir))
    return entries


def extract_drop_items(mime) -> tuple[list[DropItem], list[str]]:
    """Extract droppable items from QMimeData.

    Must be called inside dropEvent while the source data object is alive.
    Returns items to copy plus human-readable warnings.
    """
    items: list[DropItem] = []
    warnings: list[str] = []

    if mime.hasUrls():
        for url in mime.urls():
            local = url.toLocalFile()
            if local and os.path.exists(local):
                items.append(DropItem(name=os.path.basename(os.path.normpath(local)), path=local))
        if items:
            return items, warnings

    formats = list(mime.formats())
    descriptor_fmt = _find_format(formats, "FileGroupDescriptorW")
    wide = descriptor_fmt is not None
    if descriptor_fmt is None:
        descriptor_fmt = _find_format(formats, "FileGroupDescriptor")
    if descriptor_fmt is None:
        return items, warnings

    entries = _parse_group_descriptor(bytes(mime.data(descriptor_fmt)), wide)
    entries = [(name, is_dir) for name, is_dir in entries if not is_dir]
    if not entries:
        return items, warnings

    contents_fmt = _find_format(formats, "FileContents")
    payload = bytes(mime.data(contents_fmt)) if contents_fmt else b""
    if payload:
        items.append(DropItem(name=sanitize_file_name(entries[0][0]), data=payload))
        if len(entries) > 1:
            warnings.append(OUTLOOK_SINGLE_FILE_ONLY)
    else:
        warnings.append(OUTLOOK_CONTENT_UNAVAILABLE)
    return items, warnings


def unique_name(dest_dir: Path, name: str) -> str:
    """Build a non-conflicting "name (2).ext" style file name."""
    stem, suffix = os.path.splitext(name)
    counter = 2
    candidate = name
    while (dest_dir / candidate).exists():
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


def copy_item(item: DropItem, dest_dir: str, resolve_conflict) -> tuple[str, str, str | None]:
    """Copy one DropItem into dest_dir.

    ``resolve_conflict(name)`` is called when the target already exists and
    must return one of ``"overwrite"``, ``"rename"``, ``"skip"``.
    Returns (status, final name, error message) with status in
    {"copied", "skipped", "error"}.
    """
    dest = Path(dest_dir)
    name = item.name
    target = dest / name

    if item.path:
        src = Path(item.path)
        try:
            if target.exists() and src.resolve() == target.resolve():
                return "skipped", name, "Элемент уже находится в этой папке"
            if src.is_dir() and dest.resolve().is_relative_to(src.resolve()):
                return "error", name, "Нельзя скопировать папку внутрь самой себя"
        except OSError:
            pass

    if target.exists():
        decision = resolve_conflict(name)
        if decision == "rename":
            name = unique_name(dest, name)
            target = dest / name
        elif decision != "overwrite":
            return "skipped", name, None

    try:
        if item.path:
            src = Path(item.path)
            if src.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(src, target)
            else:
                shutil.copy2(src, target)
        else:
            target.write_bytes(item.data or b"")
        logger.info("Скопировано в %s: %s", dest_dir, name)
        return "copied", name, None
    except OSError as err:
        logger.warning("Ошибка копирования %s в %s: %s", item.name, dest_dir, err)
        return "error", name, str(err)
