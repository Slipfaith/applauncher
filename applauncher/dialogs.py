"""Application dialogs."""
from pathlib import Path
import logging

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, Signal, QSize, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen

from .styles import TOKENS
from .widgets import default_icon_frame

logger = logging.getLogger(__name__)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


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
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def clear_source(self) -> None:
        self._pixmap = QPixmap()
        self.update()

    def set_frame(self, frame_x: float, frame_y: float, frame_w: float, frame_h: float) -> None:
        self._frame = (
            _clamp(frame_x),
            _clamp(frame_y),
            _clamp(frame_w),
            _clamp(frame_h),
        )
        self.update()
        self.frameChanged.emit(*self._frame)

    def frame(self) -> tuple[float, float, float, float]:
        return self._frame

    def reset_frame(self) -> None:
        if self._pixmap.isNull():
            self._frame = (0.0, 0.0, 1.0, 1.0)
        else:
            self._frame = default_icon_frame(self._pixmap, QSize(*TOKENS.sizes.grid_button))
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
            _clamp(self._frame[0]) * image_width,
            _clamp(self._frame[1]) * image_height,
            _clamp(self._frame[2]) * image_width,
            _clamp(self._frame[3]) * image_height,
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
            _clamp(x) * self._pixmap.width(),
            _clamp(y) * self._pixmap.height(),
        )

    def _handle_rects(self, frame_rect: QRectF) -> dict[str, QRectF]:
        size = self._handle_size
        half = size / 2
        return {
            "top_left": QRectF(frame_rect.left() - half, frame_rect.top() - half, size, size),
            "top_right": QRectF(frame_rect.right() - half, frame_rect.top() - half, size, size),
            "bottom_left": QRectF(frame_rect.left() - half, frame_rect.bottom() - half, size, size),
            "bottom_right": QRectF(frame_rect.right() - half, frame_rect.bottom() - half, size, size),
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
        return QPointF(frame_rect.left(), frame_rect.top())

    def _resize_frame(self, handle: str, anchor: QPointF, cursor: QPointF) -> QRectF:
        if self._pixmap.isNull():
            return QRectF()
        image_width = self._pixmap.width()
        image_height = self._pixmap.height()
        width_limit = anchor.x() if handle in {"top_left", "bottom_left"} else image_width - anchor.x()
        height_limit = anchor.y() if handle in {"top_left", "top_right"} else image_height - anchor.y()
        max_width = min(width_limit, height_limit * self._aspect_ratio)
        width_from_dx = abs(anchor.x() - cursor.x())
        height_from_dy = abs(anchor.y() - cursor.y())
        width = min(width_from_dx, height_from_dy * self._aspect_ratio, max_width)
        min_frame = min(max(24.0, min(image_width, image_height) * 0.1), min(image_width, image_height))
        width = max(width, min_frame)
        height = width / self._aspect_ratio
        if handle == "top_left":
            return QRectF(anchor.x() - width, anchor.y() - height, width, height)
        if handle == "top_right":
            return QRectF(anchor.x(), anchor.y() - height, width, height)
        if handle == "bottom_left":
            return QRectF(anchor.x() - width, anchor.y(), width, height)
        return QRectF(anchor.x(), anchor.y(), width, height)

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
            rect.height() / image_height,
        )
        self.update()
        self.frameChanged.emit(*self._frame)


class AddAppDialog(QDialog):
    def __init__(
        self,
        parent=None,
        edit_mode: bool = False,
        app_data: dict | None = None,
        groups: list[str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Редактировать" if edit_mode else "Добавить элемент")
        self.setMinimumWidth(TOKENS.sizes.dialog_min_width)
        groups = groups or ["Общее"]

        layout = QVBoxLayout()
        layout.setSpacing(TOKENS.spacing.lg)
        layout.setContentsMargins(
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
        )

        type_label = QLabel("Тип элемента")
        layout.addWidget(type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["💻 Приложение", "🌐 Веб-сайт", "📁 Папка"])
        if app_data:
            if app_data.get("type") == "url":
                self.type_combo.setCurrentIndex(1)
            elif app_data.get("type") == "folder":
                self.type_combo.setCurrentIndex(2)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        layout.addWidget(self.type_combo)

        name_label = QLabel("Название")
        layout.addWidget(name_label)
        self.name_input = QLineEdit()
        if app_data:
            self.name_input.setText(app_data.get("name", ""))
        layout.addWidget(self.name_input)

        self.path_label = QLabel("Путь к исполняемому файлу")
        layout.addWidget(self.path_label)
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        if app_data:
            self.path_input.setText(app_data.get("path", ""))
        path_layout.addWidget(self.path_input)

        self.browse_btn = QPushButton("📁 Обзор")
        self.browse_btn.setProperty("variant", "accent")
        self.browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)

        icon_label = QLabel("Иконка (необязательно)")
        layout.addWidget(icon_label)
        icon_layout = QHBoxLayout()
        self.icon_input = QLineEdit()
        if app_data:
            self.icon_input.setText(app_data.get("icon_path", ""))
        icon_layout.addWidget(self.icon_input)

        icon_btn = QPushButton("🖼️ Обзор")
        icon_btn.setProperty("variant", "secondary")
        icon_btn.clicked.connect(self.browse_icon)
        icon_layout.addWidget(icon_btn)
        layout.addLayout(icon_layout)

        self.icon_preview = IconFrameEditor()
        self.icon_preview.setObjectName("iconPreview")
        self.icon_preview.setFixedSize(*TOKENS.sizes.grid_button)
        layout.addWidget(self.icon_preview)

        focus_help = QLabel(
            "Перетаскивайте рамку, чтобы выбрать область, и используйте угловые маркеры для изменения размера."
        )
        layout.addWidget(focus_help)

        group_label = QLabel("Группа")
        layout.addWidget(group_label)
        self.group_input = QComboBox()
        self.group_input.setEditable(True)
        self.group_input.addItems(groups)
        if app_data:
            existing_group = app_data.get("group", "Общее")
            if existing_group not in groups:
                self.group_input.addItem(existing_group)
            self.group_input.setCurrentText(existing_group)
        layout.addWidget(self.group_input)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(TOKENS.spacing.sm)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setProperty("variant", "secondary")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("💾 Сохранить")
        save_btn.setProperty("variant", "accent")
        save_btn.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.on_type_changed()
        self._last_icon_path = self.icon_input.text().strip()
        self._frame_initialized = False
        if app_data:
            has_frame = self._has_frame_data(app_data)
            frame = self._resolve_initial_frame(app_data)
            self.icon_preview.set_frame(*frame)
            self._frame_initialized = has_frame
        self.icon_input.textChanged.connect(self.update_icon_preview)
        self.update_icon_preview()

    def _resolve_initial_frame(self, app_data: dict) -> tuple[float, float, float, float]:
        if self._has_frame_data(app_data):
            return (
                _clamp(float(app_data["icon_frame_x"])),
                _clamp(float(app_data["icon_frame_y"])),
                _clamp(float(app_data["icon_frame_w"])),
                _clamp(float(app_data["icon_frame_h"])),
            )
        pixmap = self.icon_preview._pixmap
        return default_icon_frame(pixmap, QSize(*TOKENS.sizes.grid_button))

    def _has_frame_data(self, app_data: dict) -> bool:
        frame_values = (
            app_data.get("icon_frame_x"),
            app_data.get("icon_frame_y"),
            app_data.get("icon_frame_w"),
            app_data.get("icon_frame_h"),
        )
        if not all(isinstance(value, (int, float)) for value in frame_values):
            return False
        return frame_values[2] > 0 and frame_values[3] > 0

    def on_type_changed(self):
        current_index = self.type_combo.currentIndex()
        is_url = current_index == 1
        is_folder = current_index == 2
        if is_url:
            self.path_label.setText("URL адрес")
            self.browse_btn.setVisible(False)
            self.path_input.setPlaceholderText("https://example.com или steam://rungameid/550")
        elif is_folder:
            self.path_label.setText("Путь к папке")
            self.browse_btn.setVisible(True)
            self.path_input.setPlaceholderText("")
        else:
            self.path_label.setText("Путь к файлу или ярлыку")
            self.browse_btn.setVisible(True)
            self.path_input.setPlaceholderText("")

    def browse_path(self):
        if self.type_combo.currentIndex() == 2:
            folder_path = QFileDialog.getExistingDirectory(self, "Выберите папку", "")
            if folder_path:
                self.path_input.setText(folder_path)
                if not self.name_input.text():
                    self.name_input.setText(Path(folder_path).name)
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл приложения",
            "",
            "Executable Files (*.exe *.lnk *.bat *.cmd *.py)",
        )
        if file_path:
            self.path_input.setText(file_path)
            if not self.name_input.text():
                self.name_input.setText(Path(file_path).stem)

    def browse_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите иконку", "", "Images (*.png *.jpg *.ico)")
        if file_path:
            self.icon_input.setText(file_path)

    def update_icon_preview(self) -> None:
        icon_path = self.icon_input.text().strip()
        if not icon_path or not Path(icon_path).exists():
            self.icon_preview.clear_source()
            self._last_icon_path = ""
            return
        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            self.icon_preview.clear_source()
            return
        self.icon_preview.set_source_pixmap(pixmap)
        if icon_path != self._last_icon_path:
            self.icon_preview.reset_frame()
            self._last_icon_path = icon_path
            self._frame_initialized = True
        elif not self._frame_initialized:
            self.icon_preview.reset_frame()
            self._frame_initialized = True

    def get_data(self) -> dict:
        current_type = "exe"
        if self.type_combo.currentIndex() == 1:
            current_type = "url"
        elif self.type_combo.currentIndex() == 2:
            current_type = "folder"
        frame_x, frame_y, frame_w, frame_h = self.icon_preview.frame()
        return {
            "name": self.name_input.text(),
            "path": self.path_input.text(),
            "icon_path": self.icon_input.text(),
            "icon_frame_x": frame_x,
            "icon_frame_y": frame_y,
            "icon_frame_w": frame_w,
            "icon_frame_h": frame_h,
            "type": current_type,
            "group": self.group_input.currentText() or "Общее",
        }
