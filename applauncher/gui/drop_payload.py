"""Helpers for extracting file payloads from drag-and-drop mime data."""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QMimeData

logger = logging.getLogger(__name__)

FILE_GROUP_DESCRIPTOR_W = 'application/x-qt-windows-mime;value="FileGroupDescriptorW"'
FILE_GROUP_DESCRIPTOR_A = 'application/x-qt-windows-mime;value="FileGroupDescriptor"'
FILE_CONTENTS_PATTERN = re.compile(
    r'^application/x-qt-windows-mime;value="FileContents"(?:;index=(\d+))?$',
    re.IGNORECASE,
)
WINDOWS_FILE_DESCRIPTOR_NAME_OFFSET = 72
WINDOWS_FILE_DESCRIPTOR_W_SIZE = 592
WINDOWS_FILE_DESCRIPTOR_A_SIZE = 332
WINDOWS_FILE_DESCRIPTOR_W_NAME_SIZE = 520
WINDOWS_FILE_DESCRIPTOR_A_NAME_SIZE = 260


@dataclass(slots=True)
class ExtractedDropFiles:
    paths: list[str] = field(default_factory=list)
    temp_dirs: list[str] = field(default_factory=list)

    def cleanup(self) -> None:
        for temp_dir in self.temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _normalize_mime_format(value: str) -> str:
    return "".join((value or "").lower().split())


def extract_local_paths(mime_data: QMimeData) -> list[str]:
    if not mime_data.hasUrls():
        return []
    local_paths: list[str] = []
    for url in mime_data.urls():
        if not url.isLocalFile():
            continue
        local_path = (url.toLocalFile() or "").strip()
        if local_path:
            local_paths.append(local_path)
    return local_paths


def _find_windows_descriptor_format(mime_data: QMimeData) -> tuple[str | None, bool]:
    descriptor_map = {
        _normalize_mime_format(FILE_GROUP_DESCRIPTOR_W): (FILE_GROUP_DESCRIPTOR_W, True),
        _normalize_mime_format(FILE_GROUP_DESCRIPTOR_A): (FILE_GROUP_DESCRIPTOR_A, False),
    }
    for fmt in mime_data.formats():
        mapped = descriptor_map.get(_normalize_mime_format(fmt))
        if mapped is None:
            continue
        _canonical, is_wide = mapped
        return fmt, is_wide
    return None, False


def _collect_windows_file_contents_formats(mime_data: QMimeData) -> list[tuple[int, str]]:
    indexed_formats: list[tuple[int, str]] = []
    fallback_format: str | None = None
    for fmt in mime_data.formats():
        match = FILE_CONTENTS_PATTERN.match((fmt or "").strip())
        if match is None:
            continue
        raw_index = match.group(1)
        if raw_index is None:
            if fallback_format is None:
                fallback_format = fmt
            continue
        try:
            index = int(raw_index)
        except ValueError:
            continue
        indexed_formats.append((index, fmt))
    if indexed_formats:
        indexed_formats.sort(key=lambda item: item[0])
        return indexed_formats
    if fallback_format is not None:
        return [(0, fallback_format)]
    return []


def parse_windows_file_group_descriptor(descriptor_data: bytes, is_wide: bool) -> list[str]:
    if len(descriptor_data) < 4:
        return []
    declared_count = int.from_bytes(descriptor_data[:4], byteorder="little", signed=False)
    if declared_count <= 0:
        return []

    entry_size = WINDOWS_FILE_DESCRIPTOR_W_SIZE if is_wide else WINDOWS_FILE_DESCRIPTOR_A_SIZE
    name_size = WINDOWS_FILE_DESCRIPTOR_W_NAME_SIZE if is_wide else WINDOWS_FILE_DESCRIPTOR_A_NAME_SIZE
    names: list[str] = []
    payload_offset = 4

    for index in range(declared_count):
        entry_start = payload_offset + (index * entry_size)
        entry_end = entry_start + entry_size
        if entry_end > len(descriptor_data):
            break
        raw_name = descriptor_data[
            entry_start
            + WINDOWS_FILE_DESCRIPTOR_NAME_OFFSET : entry_start
            + WINDOWS_FILE_DESCRIPTOR_NAME_OFFSET
            + name_size
        ]
        if is_wide:
            decoded_name = raw_name.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]
        else:
            raw_name = raw_name.split(b"\x00", 1)[0]
            codec = "mbcs" if os.name == "nt" else "latin-1"
            decoded_name = raw_name.decode(codec, errors="replace")
        cleaned_name = (decoded_name or "").strip()
        names.append(cleaned_name)
    return names


def _sanitize_drop_filename(filename: str, index: int) -> str:
    base_name = Path((filename or "").strip()).name
    if not base_name:
        base_name = f"attachment-{index + 1}"
    invalid_chars = '<>:"/\\|?*'
    safe_name = "".join("_" if char in invalid_chars or ord(char) < 32 else char for char in base_name)
    safe_name = safe_name.rstrip(" .")
    if not safe_name:
        safe_name = f"attachment-{index + 1}"
    return safe_name


def _resolve_unique_temp_path(base_dir: Path, file_name: str) -> Path:
    candidate = base_dir / file_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem or "attachment"
    suffix = candidate.suffix
    attempt = 1
    while True:
        numbered = base_dir / f"{stem} ({attempt}){suffix}"
        if not numbered.exists():
            return numbered
        attempt += 1


def _create_drop_temp_dir() -> Path | None:
    try:
        return Path(tempfile.mkdtemp(prefix="applauncher-drop-"))
    except OSError as err:
        logger.debug("Failed to create drop temp dir in default temp location: %s", err)
        pass
    try:
        return Path(tempfile.mkdtemp(prefix="applauncher-drop-", dir=str(Path.cwd())))
    except OSError:
        logger.warning("Failed to create drop temp dir for virtual files", exc_info=True)
        return None


def _extract_windows_virtual_files(mime_data: QMimeData) -> ExtractedDropFiles:
    descriptor_format, is_wide = _find_windows_descriptor_format(mime_data)
    if descriptor_format is None:
        return ExtractedDropFiles()
    content_formats = _collect_windows_file_contents_formats(mime_data)
    if not content_formats:
        return ExtractedDropFiles()

    descriptor_data = bytes(mime_data.data(descriptor_format))
    names = parse_windows_file_group_descriptor(descriptor_data, is_wide) if descriptor_data else []

    temp_dir = _create_drop_temp_dir()
    if temp_dir is None:
        return ExtractedDropFiles()
    temp_paths: list[str] = []
    try:
        for fallback_index, (content_index, format_name) in enumerate(content_formats):
            blob = bytes(mime_data.data(format_name))
            source_index = content_index if content_index >= 0 else fallback_index
            source_name = names[source_index] if source_index < len(names) else f"attachment-{fallback_index + 1}"
            safe_name = _sanitize_drop_filename(source_name, fallback_index)
            temp_path = _resolve_unique_temp_path(temp_dir, safe_name)
            temp_path.write_bytes(blob)
            temp_paths.append(str(temp_path))
    except OSError:
        logger.warning("Failed to materialize dropped virtual files", exc_info=True)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return ExtractedDropFiles()

    if not temp_paths:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return ExtractedDropFiles()
    return ExtractedDropFiles(paths=temp_paths, temp_dirs=[str(temp_dir)])


def extract_dropped_files(mime_data: QMimeData) -> ExtractedDropFiles:
    local_paths = extract_local_paths(mime_data)
    if local_paths:
        return ExtractedDropFiles(paths=local_paths)
    if os.name != "nt":
        return ExtractedDropFiles()
    return _extract_windows_virtual_files(mime_data)


def can_extract_dropped_files(mime_data: QMimeData) -> bool:
    if mime_data.hasUrls():
        return bool(extract_local_paths(mime_data))
    if os.name != "nt":
        return False
    descriptor_format, _is_wide = _find_windows_descriptor_format(mime_data)
    if descriptor_format is None:
        return False
    return bool(_collect_windows_file_contents_formats(mime_data))
