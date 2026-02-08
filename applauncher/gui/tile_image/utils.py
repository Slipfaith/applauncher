"""Utility helpers for tile image calculations."""
from __future__ import annotations

import zlib

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _is_valid_png(filepath: str) -> bool:
    """Fast structural PNG check (signature + chunk bounds + CRC + IEND)."""
    try:
        with open(filepath, "rb") as handle:
            data = handle.read()
    except OSError:
        return False

    if len(data) < len(_PNG_SIGNATURE) + 12:
        return False
    if not data.startswith(_PNG_SIGNATURE):
        return False

    pos = len(_PNG_SIGNATURE)
    saw_iend = False
    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        pos += 4
        chunk_type = data[pos : pos + 4]
        pos += 4
        if pos + length + 4 > len(data):
            return False
        chunk_data = data[pos : pos + length]
        pos += length
        expected_crc = int.from_bytes(data[pos : pos + 4], "big")
        pos += 4
        actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            return False
        if chunk_type == b"IEND":
            saw_iend = True
            break
    return saw_iend


def is_valid_png_file(filepath: str) -> bool:
    """Public wrapper for PNG validation."""
    return _is_valid_png(filepath)


def load_icon_file(filepath: str, preferred_size: int = 256) -> QPixmap:
    """
    Load icon/image file and return a pixmap.

    For ICO files, picks the largest suitable size to avoid tiny icon variants.
    For PNG files, validates structure before loading to prevent libpng read errors.
    """
    if filepath.lower().endswith(".ico"):
        icon = QIcon(filepath)
        available_sizes = icon.availableSizes()

        if available_sizes:
            suitable_sizes = [s for s in available_sizes if s.width() >= preferred_size]
            if suitable_sizes:
                best_size = min(suitable_sizes, key=lambda s: s.width())
            else:
                best_size = max(available_sizes, key=lambda s: s.width() * s.height())
            pixmap = icon.pixmap(best_size)
        else:
            pixmap = icon.pixmap(QSize(preferred_size, preferred_size))

        if pixmap.isNull() or pixmap.width() < 32:
            pixmap = icon.pixmap(QSize(256, 256))
        return pixmap

    if filepath.lower().endswith(".png") and not _is_valid_png(filepath):
        return QPixmap()

    return QPixmap(filepath)
