"""Helpers for extracting icons from executables."""
import os
import hashlib
import zlib
from pathlib import Path
import logging

from PySide6.QtGui import QPixmap, QImage

from ..config import resolve_icons_cache_dir

try:
    import win32gui
    import win32ui
    import win32con
    import win32api

    HAS_WIN32 = True
except ImportError:  # pragma: no cover - platform specific
    HAS_WIN32 = False

logger = logging.getLogger(__name__)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _extract_complete_png(data: bytes) -> bytes | None:
    """Extract the first structurally valid PNG blob from arbitrary bytes."""
    search_from = 0
    while True:
        start = data.find(_PNG_SIGNATURE, search_from)
        if start < 0:
            return None
        pos = start + len(_PNG_SIGNATURE)
        try:
            while True:
                if pos + 12 > len(data):
                    raise ValueError("truncated chunk header")
                length = int.from_bytes(data[pos : pos + 4], "big")
                pos += 4
                chunk_type = data[pos : pos + 4]
                pos += 4
                if pos + length + 4 > len(data):
                    raise ValueError("truncated chunk data")
                chunk_data = data[pos : pos + length]
                pos += length
                expected_crc = int.from_bytes(data[pos : pos + 4], "big")
                actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
                if expected_crc != actual_crc:
                    raise ValueError("bad chunk crc")
                pos += 4
                if chunk_type == b"IEND":
                    return data[start:pos]
        except ValueError:
            search_from = start + len(_PNG_SIGNATURE)
            continue


def extract_icon_from_exe(exe_path: str) -> str | None:
    """Extract an icon from an executable and return the stored path."""
    try:
        icons_dir = Path(resolve_icons_cache_dir())
        resolved_path = str(Path(exe_path).resolve())
        digest = hashlib.sha1(resolved_path.lower().encode("utf-8", errors="ignore")).hexdigest()[:12]
        icon_path = icons_dir / f"{Path(exe_path).stem}_{digest}.png"

        if HAS_WIN32:
            ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
            ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)

            large, _ = win32gui.ExtractIconEx(exe_path, 0)
            if large:
                hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
                hdc = hdc.CreateCompatibleDC()

                hdc.SelectObject(hbmp)
                hdc.DrawIcon((0, 0), large[0])

                bmpstr = hbmp.GetBitmapBits(True)
                img = QPixmap.fromImage(QImage(bmpstr, ico_x, ico_y, QImage.Format_ARGB32))
                img.save(str(icon_path))

                win32gui.DestroyIcon(large[0])
                return str(icon_path)
        else:
            with open(exe_path, "rb") as f:
                data = f.read()
                png_blob = _extract_complete_png(data)
                if png_blob:
                    with open(icon_path, "wb") as icon_file:
                        icon_file.write(png_blob)
                    return str(icon_path)
    except Exception as err:  # pragma: no cover - visual/log side effects
        logger.warning("Не удалось извлечь иконку: %s", err)
    return None


def extract_icon_with_fallback(path_value: str) -> str:
    """Extract an icon and return an empty string if extraction fails."""
    if not path_value or not os.path.exists(path_value):
        return ""
    return extract_icon_from_exe(path_value) or ""
