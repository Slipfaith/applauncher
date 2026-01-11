"""Frame helpers for configuring application tile icons."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QRect
from PySide6.QtGui import QPainter, QPixmap

from .utils import clamp


def resolve_icon_frame(app_data: dict) -> tuple[float, float, float, float] | None:
    frame_x = app_data.get("icon_frame_x")
    frame_y = app_data.get("icon_frame_y")
    frame_w = app_data.get("icon_frame_w")
    frame_h = app_data.get("icon_frame_h")
    if frame_x is None or frame_y is None or frame_w is None or frame_h is None:
        return None
    try:
        return (
            clamp(float(frame_x)),
            clamp(float(frame_y)),
            clamp(float(frame_w)),
            clamp(float(frame_h)),
        )
    except (TypeError, ValueError):
        return None


def default_icon_frame(pixmap: QPixmap, target_size: QSize) -> tuple[float, float, float, float]:
    if pixmap.isNull() or target_size.isEmpty():
        return (0.0, 0.0, 1.0, 1.0)
    image_width = pixmap.width()
    image_height = pixmap.height()
    if image_width <= 0 or image_height <= 0:
        return (0.0, 0.0, 1.0, 1.0)
    image_aspect = image_width / image_height
    target_aspect = target_size.width() / target_size.height()
    if image_aspect >= target_aspect:
        frame_height = image_height
        frame_width = image_height * target_aspect
        frame_x = (image_width - frame_width) / 2
        frame_y = 0.0
    else:
        frame_width = image_width
        frame_height = image_width / target_aspect
        frame_x = 0.0
        frame_y = (image_height - frame_height) / 2
    return (
        frame_x / image_width,
        frame_y / image_height,
        frame_width / image_width,
        frame_height / image_height,
    )


def render_framed_pixmap(
    pixmap: QPixmap,
    target_size: QSize,
    frame: tuple[float, float, float, float] | None = None,
) -> QPixmap:
    if pixmap.isNull() or target_size.isEmpty():
        return pixmap
    frame = frame or default_icon_frame(pixmap, target_size)
    image_width = pixmap.width()
    image_height = pixmap.height()
    frame_x = int(round(clamp(frame[0]) * image_width))
    frame_y = int(round(clamp(frame[1]) * image_height))
    frame_w = int(round(clamp(frame[2]) * image_width))
    frame_h = int(round(clamp(frame[3]) * image_height))
    if frame_w <= 0 or frame_h <= 0:
        frame_x, frame_y, frame_w, frame_h = 0, 0, image_width, image_height
    frame_rect = QRect(frame_x, frame_y, frame_w, frame_h).intersected(
        QRect(0, 0, image_width, image_height)
    )
    cropped = pixmap.copy(frame_rect)
    target_pixmap = QPixmap(target_size)
    target_pixmap.fill(Qt.transparent)
    painter = QPainter(target_pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.drawPixmap(target_pixmap.rect(), cropped)
    painter.end()
    return target_pixmap
