"""Helpers for extracting icons from executables."""
import os
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


def extract_icon_from_exe(exe_path: str) -> str | None:
    """Extract an icon from an executable and return the stored path."""
    try:
        icons_dir = Path(resolve_icons_cache_dir())
        icon_path = icons_dir / f"{Path(exe_path).stem}.png"

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
                png_header = b"\x89PNG\r\n\x1a\n"
                idx = data.find(png_header)
                if idx != -1:
                    with open(icon_path, "wb") as icon_file:
                        icon_file.write(data[idx : idx + 5000])
                    return str(icon_path)
    except Exception as err:  # pragma: no cover - visual/log side effects
        logger.warning("Не удалось извлечь иконку: %s", err)
    return None


def extract_icon_with_fallback(path_value: str) -> str:
    """Extract an icon and return an empty string if extraction fails."""
    if not path_value or not os.path.exists(path_value):
        return ""
    return extract_icon_from_exe(path_value) or ""
