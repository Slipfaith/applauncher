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
    # ИЗМЕНЕНИЕ: всегда возвращаем полную картинку без автообрезки
    return (0.0, 0.0, 1.0, 1.0)


def render_framed_pixmap(
    pixmap: QPixmap,
    target_size: QSize,
    frame: tuple[float, float, float, float] | None = None,
) -> QPixmap:
    if pixmap.isNull() or target_size.isEmpty():
        return pixmap

    frame = frame or (0.0, 0.0, 1.0, 1.0)
    image_width = pixmap.width()
    image_height = pixmap.height()

    # Вычисляем frame rect
    frame_x = int(round(clamp(frame[0]) * image_width))
    frame_y = int(round(clamp(frame[1]) * image_height))
    frame_w = int(round(clamp(frame[2]) * image_width))
    frame_h = int(round(clamp(frame[3]) * image_height))

    if frame_w <= 0 or frame_h <= 0:
        frame_x, frame_y, frame_w, frame_h = 0, 0, image_width, image_height

    frame_rect = QRect(frame_x, frame_y, frame_w, frame_h).intersected(
        QRect(0, 0, image_width, image_height)
    )

    # Обрезаем согласно frame
    cropped = pixmap.copy(frame_rect)

    # ИСПРАВЛЕНИЕ: сохраняем пропорции при масштабировании
    # Масштабируем обрезанную часть с сохранением aspect ratio
    scaled = cropped.scaled(
        target_size,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation
    )

    # Создаем финальный pixmap с target_size
    target_pixmap = QPixmap(target_size)
    target_pixmap.fill(Qt.transparent)

    # Центруем масштабированную картинку
    painter = QPainter(target_pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    x = (target_size.width() - scaled.width()) // 2
    y = (target_size.height() - scaled.height()) // 2

    painter.drawPixmap(x, y, scaled)
    painter.end()

    return target_pixmap