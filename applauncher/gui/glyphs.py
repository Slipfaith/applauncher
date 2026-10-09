"""Outline UI glyphs (24-unit grid, 1.75 stroke, round caps) drawn with QPainter.

No icon files and no QtSvg dependency: every glyph is a few path commands, so
it stays crisp at any DPI and takes its colour from the active theme.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton, QStyle, QStyleOptionButton, QStylePainter

from .styles import TOKENS, active_colors


def _path(name: str) -> QPainterPath:
    p = QPainterPath()
    if name == "grid":
        for x, y in ((4, 4), (14, 4), (4, 14), (14, 14)):
            p.addRoundedRect(QRectF(x, y, 6, 6), 1.5, 1.5)
    elif name == "list":
        for y in (6, 12, 18):
            p.moveTo(9, y)
            p.lineTo(20, y)
            p.addEllipse(QPointF(4.5, y), 0.6, 0.6)
    elif name == "plus":
        p.moveTo(12, 5); p.lineTo(12, 19)
        p.moveTo(5, 12); p.lineTo(19, 12)
    elif name == "minus":
        p.moveTo(6, 12); p.lineTo(18, 12)
    elif name == "maximize":
        p.addRoundedRect(QRectF(6, 6, 12, 12), 2, 2)
    elif name == "restore":
        p.addRoundedRect(QRectF(5, 9, 10, 10), 1.5, 1.5)
        p.moveTo(9, 9); p.lineTo(9, 5); p.lineTo(19, 5); p.lineTo(19, 15); p.lineTo(15, 15)
    elif name == "close":
        p.moveTo(6.5, 6.5); p.lineTo(17.5, 17.5)
        p.moveTo(17.5, 6.5); p.lineTo(6.5, 17.5)
    elif name == "copy":
        p.addRoundedRect(QRectF(8.5, 8.5, 11, 11), 2, 2)
        p.moveTo(15.5, 8.5); p.lineTo(15.5, 6.5)
        p.quadTo(15.5, 4.5, 13.5, 4.5); p.lineTo(6.5, 4.5)
        p.quadTo(4.5, 4.5, 4.5, 6.5); p.lineTo(4.5, 13.5)
        p.quadTo(4.5, 15.5, 6.5, 15.5); p.lineTo(8.5, 15.5)
    elif name == "check":
        p.moveTo(5, 12.5); p.lineTo(9.5, 17); p.lineTo(19, 7.5)
    elif name == "chevron-down":
        p.moveTo(6, 9); p.lineTo(12, 15); p.lineTo(18, 9)
    elif name == "chevron-right":
        p.moveTo(9, 6); p.lineTo(15, 12); p.lineTo(9, 18)
    elif name == "menu":
        for y in (7, 12, 17):
            p.moveTo(5, y); p.lineTo(19, y)
    elif name == "settings":
        p.addEllipse(QPointF(12, 12), 3, 3)
        p.addEllipse(QPointF(12, 12), 8, 8)
    elif name == "trash":
        p.moveTo(4.5, 7); p.lineTo(19.5, 7)
        p.moveTo(6.5, 7); p.lineTo(7.5, 19.5); p.lineTo(16.5, 19.5); p.lineTo(17.5, 7)
        p.moveTo(9.5, 7); p.lineTo(9.5, 4.5); p.lineTo(14.5, 4.5); p.lineTo(14.5, 7)
    return p


def paint_glyph(painter: QPainter, rect: QRectF, name: str, color: QColor, stroke: float = 1.75) -> None:
    scale = min(rect.width(), rect.height()) / 24.0
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.translate(rect.center().x() - 12 * scale, rect.center().y() - 12 * scale)
    painter.scale(scale, scale)
    pen = QPen(color, stroke)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(_path(name))
    painter.restore()


def paint_focus(painter: QPainter, widget: QPushButton) -> None:
    """Visible focus even when custom painting omits the native button label."""
    if not widget.hasFocus():
        return
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QPen(QColor(active_colors().accent), 1.5))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(QRectF(widget.rect()).adjusted(2, 2, -2, -2), TOKENS.radii.sm, TOKENS.radii.sm)
    painter.restore()


class KeyboardButton(QPushButton):
    """Ordinary button with Enter activation outside a QDialog as well."""

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.isAutoRepeat():
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)


class GlyphButton(KeyboardButton):
    """QPushButton that paints a glyph instead of text; colour follows state and theme.

    The stylesheet still draws the background and border (variant/role properties),
    so these buttons look like every other button.
    """

    def __init__(self, glyph: str, parent=None, glyph_size: int = 16, tooltip: str = "") -> None:
        super().__init__(parent)
        self._glyph = glyph
        self._glyph_size = glyph_size
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        if tooltip:
            self.setToolTip(tooltip)
            self.setAccessibleName(tooltip)

    def set_glyph(self, glyph: str) -> None:
        self._glyph = glyph
        self.update()

    def glyph(self) -> str:
        return self._glyph

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        side = max(self._glyph_size + 12, 28)
        return QSize(max(hint.width(), side), max(hint.height(), side))

    def _glyph_color(self) -> QColor:
        c = active_colors()
        variant = self.property("variant")
        role = self.property("role")
        if not self.isEnabled():
            return QColor(c.text_muted)
        if self.property("state") == "done":
            return QColor(c.success)
        if self.isCheckable() and self.isChecked():
            return QColor(c.accent)
        hovered = self.underMouse()
        if variant == "danger":
            if role == "titleButton":
                return QColor(c.on_accent if hovered else c.text_secondary)
            return QColor(c.danger)
        if variant == "accent":
            return QColor(c.on_accent)
        return QColor(c.text_primary if hovered else c.text_secondary)

    def paintEvent(self, _event) -> None:
        painter = QStylePainter(self)
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        opt.text = ""
        painter.drawControl(QStyle.CE_PushButtonBevel, opt)
        size = self._glyph_size
        rect = QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size)
        paint_glyph(painter, rect, self._glyph, self._glyph_color())
        paint_focus(painter, self)

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)
