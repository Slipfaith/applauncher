"""Editor widget for selecting a framed icon region."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel

from ..styles import TOKENS
from .frame import default_icon_frame
from .utils import clamp, load_icon_file


class IconFrameEditor(QLabel):
    frameChanged = Signal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._frame = (0.0, 0.0, 1.0, 1.0)
        self._drag_mode = None
        self._drag_start = None
        self._drag_frame = None
        self._resize_anchor = None
        self._handle_size = 10
        self._aspect_ratio = TOKENS.sizes.grid_button[0] / TOKENS.sizes.grid_button[1]
        self._lock_aspect = False  # НОВОЕ: опция блокировки пропорций
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        # ИЗМЕНЕНИЕ: устанавливаем полный фрейм (вся картинка) вместо автообрезки
        self._frame = (0.0, 0.0, 1.0, 1.0)
        self.update()
        self.frameChanged.emit(*self._frame)

    def set_source_from_file(self, filepath: str) -> None:
        """Загружает иконку из файла с правильной обработкой ICO."""
        pixmap = load_icon_file(filepath)
        self.set_source_pixmap(pixmap)

    def clear_source(self) -> None:
        self._pixmap = QPixmap()
        self.update()

    def set_frame(self, frame_x: float, frame_y: float, frame_w: float, frame_h: float) -> None:
        self._frame = (
            clamp(frame_x),
            clamp(frame_y),
            clamp(frame_w),
            clamp(frame_h),
        )
        self.update()
        self.frameChanged.emit(*self._frame)

    def frame(self) -> tuple[float, float, float, float]:
        return self._frame

    def reset_frame(self) -> None:
        # ИЗМЕНЕНИЕ: сброс теперь возвращает всю картинку, а не автообрезку
        self._frame = (0.0, 0.0, 1.0, 1.0)
        self.update()
        self.frameChanged.emit(*self._frame)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            handle = self._handle_at(event.position())
            if handle:
                self._drag_mode = handle
            elif self._frame_rect_in_widget().contains(event.position()):
                self._drag_mode = "move"
            else:
                self._drag_mode = None
            if self._drag_mode:
                self._drag_start = event.position()
                self._drag_frame = self._frame_rect_in_image()
                if self._drag_mode != "move":
                    self._resize_anchor = self._resize_anchor_point(self._drag_frame, self._drag_mode)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pixmap.isNull():
            super().mouseMoveEvent(event)
            return
        if not self._drag_mode:
            self._update_hover_cursor(event.position())
            super().mouseMoveEvent(event)
            return
        image_point = self._widget_to_image(event.position())
        if image_point is None or self._drag_frame is None:
            return
        image_width = self._pixmap.width()
        image_height = self._pixmap.height()
        if self._drag_mode == "move":
            start_point = self._widget_to_image(self._drag_start)
            if start_point is None:
                return
            delta = image_point - start_point
            new_rect = QRectF(self._drag_frame)
            new_rect.translate(delta)
            new_rect.moveLeft(max(0.0, min(new_rect.left(), image_width - new_rect.width())))
            new_rect.moveTop(max(0.0, min(new_rect.top(), image_height - new_rect.height())))
        else:
            new_rect = self._resize_frame(self._drag_mode, self._resize_anchor, image_point)
        self._apply_frame_rect(new_rect)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_mode = None
            self._drag_start = None
            self._drag_frame = None
            self._resize_anchor = None
            self._update_hover_cursor(event.position())
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._pixmap.isNull():
            painter.end()
            return
        image_rect = self._image_rect()
        scaled = self._pixmap.scaled(
            image_rect.size().toSize(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        painter.drawPixmap(image_rect.topLeft(), scaled)
        frame_rect = self._frame_rect_in_widget()
        overlay_color = QColor(0, 0, 0, 120)
        painter.fillRect(image_rect.x(), image_rect.y(), image_rect.width(), frame_rect.top() - image_rect.y(), overlay_color)
        painter.fillRect(
            image_rect.x(),
            frame_rect.bottom(),
            image_rect.width(),
            image_rect.bottom() - frame_rect.bottom(),
            overlay_color,
        )
        painter.fillRect(
            image_rect.x(),
            frame_rect.top(),
            frame_rect.left() - image_rect.x(),
            frame_rect.height(),
            overlay_color,
        )
        painter.fillRect(
            frame_rect.right(),
            frame_rect.top(),
            image_rect.right() - frame_rect.right(),
            frame_rect.height(),
            overlay_color,
        )
        pen = QPen(QColor(255, 255, 255), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(frame_rect)
        painter.setBrush(QColor(255, 255, 255))
        for handle_rect in self._handle_rects(frame_rect).values():
            painter.drawRect(handle_rect)
        painter.end()

    def _image_rect(self) -> QRectF:
        if self._pixmap.isNull():
            return QRectF()
        image_width = self._pixmap.width()
        image_height = self._pixmap.height()
        scale = min(self.width() / image_width, self.height() / image_height)
        draw_width = image_width * scale
        draw_height = image_height * scale
        x = (self.width() - draw_width) / 2
        y = (self.height() - draw_height) / 2
        return QRectF(x, y, draw_width, draw_height)

    def _frame_rect_in_image(self) -> QRectF:
        if self._pixmap.isNull():
            return QRectF()
        image_width = self._pixmap.width()
        image_height = self._pixmap.height()
        return QRectF(
            clamp(self._frame[0]) * image_width,
            clamp(self._frame[1]) * image_height,
            clamp(self._frame[2]) * image_width,
            clamp(self._frame[3]) * image_height,
        )

    def _frame_rect_in_widget(self) -> QRectF:
        image_rect = self._image_rect()
        if image_rect.isNull():
            return QRectF()
        frame_rect = self._frame_rect_in_image()
        scale = image_rect.width() / self._pixmap.width()
        return QRectF(
            image_rect.x() + frame_rect.x() * scale,
            image_rect.y() + frame_rect.y() * scale,
            frame_rect.width() * scale,
            frame_rect.height() * scale,
        )

    def _widget_to_image(self, pos: QPointF) -> QPointF | None:
        image_rect = self._image_rect()
        if image_rect.isNull():
            return None
        x = (pos.x() - image_rect.x()) / image_rect.width()
        y = (pos.y() - image_rect.y()) / image_rect.height()
        return QPointF(
            clamp(x) * self._pixmap.width(),
            clamp(y) * self._pixmap.height(),
        )

    def _handle_rects(self, frame_rect: QRectF) -> dict[str, QRectF]:
        size = self._handle_size
        half = size / 2
        return {
            "top_left": QRectF(frame_rect.left() - half, frame_rect.top() - half, size, size),
            "top_right": QRectF(frame_rect.right() - half, frame_rect.top() - half, size, size),
            "bottom_left": QRectF(frame_rect.left() - half, frame_rect.bottom() - half, size, size),
            "bottom_right": QRectF(frame_rect.right() - half, frame_rect.bottom() - half, size, size),
            # НОВОЕ: добавляем хендлы по сторонам для свободного ресайза
            "top": QRectF(frame_rect.center().x() - half, frame_rect.top() - half, size, size),
            "bottom": QRectF(frame_rect.center().x() - half, frame_rect.bottom() - half, size, size),
            "left": QRectF(frame_rect.left() - half, frame_rect.center().y() - half, size, size),
            "right": QRectF(frame_rect.right() - half, frame_rect.center().y() - half, size, size),
        }

    def _handle_at(self, pos: QPointF) -> str | None:
        frame_rect = self._frame_rect_in_widget()
        if frame_rect.isNull():
            return None
        for name, rect in self._handle_rects(frame_rect).items():
            if rect.contains(pos):
                return name
        return None

    def _update_hover_cursor(self, pos: QPointF) -> None:
        handle = self._handle_at(pos)
        if handle in {"top_left", "bottom_right"}:
            self.setCursor(Qt.SizeFDiagCursor)
        elif handle in {"top_right", "bottom_left"}:
            self.setCursor(Qt.SizeBDiagCursor)
        elif handle in {"top", "bottom"}:
            self.setCursor(Qt.SizeVerCursor)
        elif handle in {"left", "right"}:
            self.setCursor(Qt.SizeHorCursor)
        elif self._frame_rect_in_widget().contains(pos):
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def _resize_anchor_point(self, frame_rect: QRectF, handle: str) -> QPointF:
        if handle == "top_left":
            return QPointF(frame_rect.right(), frame_rect.bottom())
        if handle == "top_right":
            return QPointF(frame_rect.left(), frame_rect.bottom())
        if handle == "bottom_left":
            return QPointF(frame_rect.right(), frame_rect.top())
        if handle == "bottom_right":
            return QPointF(frame_rect.left(), frame_rect.top())
        # НОВОЕ: якоря для боковых хендлов
        if handle == "top":
            return QPointF(frame_rect.center().x(), frame_rect.bottom())
        if handle == "bottom":
            return QPointF(frame_rect.center().x(), frame_rect.top())
        if handle == "left":
            return QPointF(frame_rect.right(), frame_rect.center().y())
        if handle == "right":
            return QPointF(frame_rect.left(), frame_rect.center().y())
        return QPointF(frame_rect.center())

    def _resize_frame(self, handle: str, anchor: QPointF, cursor: QPointF) -> QRectF:
        if self._pixmap.isNull():
            return QRectF()
        image_width = self._pixmap.width()
        image_height = self._pixmap.height()

        # ИСПРАВЛЕНИЕ: свободный ресайз без жесткой блокировки пропорций
        if handle in {"top_left", "top_right", "bottom_left", "bottom_right"}:
            # Угловые хендлы - с сохранением пропорций только если нужно
            if self._lock_aspect:
                # Старая логика с пропорциями
                width_limit = anchor.x() if handle in {"top_left", "bottom_left"} else image_width - anchor.x()
                height_limit = anchor.y() if handle in {"top_left", "top_right"} else image_height - anchor.y()
                max_width = min(width_limit, height_limit * self._aspect_ratio)
                width_from_dx = abs(anchor.x() - cursor.x())
                height_from_dy = abs(anchor.y() - cursor.y())
                width = min(width_from_dx, height_from_dy * self._aspect_ratio, max_width)
                min_frame = min(max(24.0, min(image_width, image_height) * 0.1), min(image_width, image_height))
                width = max(width, min_frame)
                height = width / self._aspect_ratio
            else:
                # НОВОЕ: свободный ресайз без блокировки пропорций
                width = abs(cursor.x() - anchor.x())
                height = abs(cursor.y() - anchor.y())
                width = max(24.0, min(width, image_width))
                height = max(24.0, min(height, image_height))

            if handle == "top_left":
                return QRectF(anchor.x() - width, anchor.y() - height, width, height)
            if handle == "top_right":
                return QRectF(anchor.x(), anchor.y() - height, width, height)
            if handle == "bottom_left":
                return QRectF(anchor.x() - width, anchor.y(), width, height)
            return QRectF(anchor.x(), anchor.y(), width, height)

        # НОВОЕ: боковые хендлы - только один размер меняется
        elif handle in {"top", "bottom", "left", "right"}:
            current_rect = self._drag_frame

            if handle == "top":
                new_top = max(0.0, min(cursor.y(), anchor.y() - 24.0))
                return QRectF(current_rect.left(), new_top, current_rect.width(), anchor.y() - new_top)
            elif handle == "bottom":
                new_bottom = max(anchor.y() + 24.0, min(cursor.y(), image_height))
                return QRectF(current_rect.left(), anchor.y(), current_rect.width(), new_bottom - anchor.y())
            elif handle == "left":
                new_left = max(0.0, min(cursor.x(), anchor.x() - 24.0))
                return QRectF(new_left, current_rect.top(), anchor.x() - new_left, current_rect.height())
            elif handle == "right":
                new_right = max(anchor.x() + 24.0, min(cursor.x(), image_width))
                return QRectF(anchor.x(), current_rect.top(), new_right - anchor.x(), current_rect.height())

        return QRectF()

    def _apply_frame_rect(self, rect: QRectF) -> None:
        if self._pixmap.isNull():
            return
        image_width = self._pixmap.width()
        image_height = self._pixmap.height()
        rect = rect.intersected(QRectF(0, 0, image_width, image_height))
        if rect.width() <= 0 or rect.height() <= 0:
            return
        self._frame = (
            rect.x() / image_width,
            rect.y() / image_height,
            rect.width() / image_width,
            rect.height() / image_height,  # ИСПРАВЛЕНИЕ: было image_width, должно быть image_height
        )
        self.update()
        self.frameChanged.emit(*self._frame)