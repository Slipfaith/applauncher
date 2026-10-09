"""Scalable LINE 01 fallback icons, painted using the current theme colours."""
from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QIconEngine, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .styles import active_colors
from .tile_image.frame import render_framed_pixmap, resolve_icon_frame
from .tile_image.utils import load_icon_file

_GRID = 64.0
_STROKE = 3.7


def fallback_kind(item: dict) -> str:
    """Select one of the three approved silhouettes from an item's type."""
    return {"folder": "folder", "url": "link"}.get(item.get("type"), "app")


def _paths(kind: str) -> tuple[QPainterPath, QPainterPath]:
    main, accent = QPainterPath(), QPainterPath()
    if kind == "folder":
        main.addRoundedRect(QRectF(8, 29, 48, 28), 6, 6)
        accent.moveTo(8, 31)
        accent.lineTo(8, 20)
        accent.quadTo(8, 14, 14, 14)
        accent.lineTo(25, 14)
        accent.quadTo(28, 14, 31, 17)
        accent.lineTo(37, 23)
        accent.lineTo(50, 23)
        accent.quadTo(56, 23, 56, 29)
    elif kind == "link":
        main.moveTo(30, 47)
        main.lineTo(25, 52)
        main.cubicTo(20, 57, 13, 57, 8, 52)
        main.cubicTo(3, 47, 3, 40, 8, 35)
        main.lineTo(16, 27)
        main.cubicTo(21, 22, 28, 22, 33, 27)
        accent.moveTo(34, 17)
        accent.lineTo(39, 12)
        accent.cubicTo(44, 7, 51, 7, 55, 12)
        accent.cubicTo(60, 17, 60, 24, 55, 29)
        accent.lineTo(47, 37)
        accent.cubicTo(42, 42, 36, 42, 31, 37)
    else:
        main.addRoundedRect(QRectF(12, 8, 40, 48), 8, 8)
        main.moveTo(13, 21)
        main.lineTo(51, 21)
        for x, y in ((21, 30), (36, 30), (21, 43), (36, 43)):
            accent.addRoundedRect(QRectF(x, y, 7, 7), 1.6, 1.6)
    return main, accent


def paint_fallback_icon(painter: QPainter, rect: QRectF, kind: str, disabled: bool = False) -> None:
    """Draw rounded outlines with a restrained blue accent, at any DPI."""
    side = min(rect.width(), rect.height())
    if side <= 0:
        return
    colors = active_colors()
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.translate(rect.center().x() - side / 2, rect.center().y() - side / 2)
    painter.scale(side / _GRID, side / _GRID)
    painter.setBrush(Qt.NoBrush)
    if disabled:
        painter.setOpacity(painter.opacity() * 0.45)
    pen = QPen(QColor(colors.text_secondary))
    pen.setWidthF(max(_STROKE, _GRID / side * 1.2))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    main, accent = _paths(kind)
    painter.setPen(pen)
    painter.drawPath(main)
    gradient = QLinearGradient(8, 8, 56, 56)
    gradient.setColorAt(0, QColor(colors.accent))
    gradient.setColorAt(1, QColor(colors.sky))
    pen.setBrush(gradient)
    painter.setPen(pen)
    painter.drawPath(accent)
    painter.restore()


class _LineIconEngine(QIconEngine):
    """Resolve colours at paint time so existing QIcons switch theme in place."""

    def __init__(self, kind: str) -> None:
        super().__init__()
        self.kind = kind

    def clone(self) -> QIconEngine:
        return _LineIconEngine(self.kind)

    def isNull(self) -> bool:
        return False

    def iconName(self) -> str:
        return f"applauncher-line-{self.kind}"

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        paint_fallback_icon(painter, QRectF(rect), self.kind, mode == QIcon.Disabled)

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        return self.scaledPixmap(size, mode, state, 1.0)

    def scaledPixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float) -> QPixmap:
        pixmap = QPixmap(max(1, round(size.width() * scale)), max(1, round(size.height() * scale)))
        pixmap.setDevicePixelRatio(scale)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, QRect(0, 0, size.width(), size.height()), mode, state)
        painter.end()
        return pixmap


def fallback_icon(item: dict) -> QIcon:
    """Create a live vector fallback without adding files to the user's cache."""
    return QIcon(_LineIconEngine(fallback_kind(item)))


class ItemIconWidget(QWidget):
    """An existing picture or a theme-aware fallback for list rows and the HUD."""

    def __init__(self, item: dict, size: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setProperty("role", "itemIcon")
        path = item.get("icon_path") or ""
        pixmap = load_icon_file(path) if path else QPixmap()
        self.is_fallback = pixmap.isNull()
        if self.is_fallback:
            self.icon = fallback_icon(item)
        else:
            if item.get("custom_icon"):
                pixmap = render_framed_pixmap(pixmap, QSize(size, size), resolve_icon_frame(item))
            self.icon = QIcon(pixmap)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        mode = QIcon.Normal if self.isEnabled() else QIcon.Disabled
        self.icon.paint(painter, self.rect(), Qt.AlignCenter, mode)
