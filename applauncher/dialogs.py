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
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from .styles import TOKENS
from .widgets import ICON_FOCUS_PRESETS, fit_pixmap_cropper

logger = logging.getLogger(__name__)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _clamp_range(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class IconCropPreview(QLabel):
    focusChanged = Signal(float, float)
    zoomChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._focus = (0.5, 0.5)
        self._zoom = 1.0
        self._drag_pos = None
        self.setCursor(Qt.OpenHandCursor)
        self.setAlignment(Qt.AlignCenter)

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._render()

    def clear_source(self) -> None:
        self._pixmap = QPixmap()
        self.clear()

    def set_focus(self, focus_x: float, focus_y: float) -> None:
        self._focus = (_clamp(focus_x), _clamp(focus_y))
        self._render()
        self.focusChanged.emit(*self._focus)

    def focus(self) -> tuple[float, float]:
        return self._focus

    def set_zoom(self, zoom: float) -> None:
        self._zoom = _clamp_range(float(zoom), 0.2, 4.0)
        self._render()
        self.zoomChanged.emit(self._zoom)

    def zoom(self) -> float:
        return self._zoom

    def reset_view(self) -> None:
        self._focus = (0.5, 0.5)
        self._zoom = 1.0
        self._render()
        self.focusChanged.emit(*self._focus)
        self.zoomChanged.emit(self._zoom)

    def _render(self) -> None:
        if self._pixmap.isNull():
            self.clear()
            return
        target_size = self.size()
        fitted = fit_pixmap_cropper(self._pixmap, target_size, self._focus, self._zoom)
        self.setPixmap(fitted)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is None or self._pixmap.isNull():
            super().mouseMoveEvent(event)
            return
        delta = event.position() - self._drag_pos
        target_size = self.size()
        if target_size.isEmpty():
            return
        base_scale = min(
            target_size.width() / self._pixmap.width(),
            target_size.height() / self._pixmap.height(),
        )
        scaled_width = self._pixmap.width() * base_scale * self._zoom
        scaled_height = self._pixmap.height() * base_scale * self._zoom
        focus_x, focus_y = self._focus
        if scaled_width > 0:
            focus_x = _clamp(focus_x - (delta.x() / scaled_width))
        if scaled_height > 0:
            focus_y = _clamp(focus_y - (delta.y() / scaled_height))
        self._drag_pos = event.position()
        self.set_focus(focus_x, focus_y)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
            self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        if self._pixmap.isNull():
            return
        steps = event.angleDelta().y() / 120.0
        if steps == 0:
            return
        zoom = self._zoom * (1.1 ** steps)
        self.set_zoom(zoom)
        event.accept()


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

        self.icon_preview = IconCropPreview()
        self.icon_preview.setObjectName("iconPreview")
        self.icon_preview.setFixedSize(*TOKENS.sizes.grid_button)
        layout.addWidget(self.icon_preview)

        focus_help = QLabel(
            "Перетаскивайте изображение мышью, чтобы выбрать область, и используйте колесо для масштаба."
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
        if app_data:
            focus = self._resolve_initial_focus(app_data)
            self.icon_preview.set_focus(*focus)
            zoom_value = app_data.get("icon_zoom", 1.0)
            if isinstance(zoom_value, (int, float)):
                self.icon_preview.set_zoom(zoom_value)
        self.icon_input.textChanged.connect(self.update_icon_preview)
        self.update_icon_preview()

    def _resolve_initial_focus(self, app_data: dict) -> tuple[float, float]:
        focus_x = app_data.get("icon_focus_x")
        focus_y = app_data.get("icon_focus_y")
        if isinstance(focus_x, (int, float)) and isinstance(focus_y, (int, float)):
            return (_clamp(float(focus_x)), _clamp(float(focus_y)))
        focus_value = app_data.get("icon_focus", "center")
        return ICON_FOCUS_PRESETS.get(focus_value, ICON_FOCUS_PRESETS["center"])

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
        if icon_path != self._last_icon_path:
            self.icon_preview.reset_view()
            self._last_icon_path = icon_path
        self.icon_preview.set_source_pixmap(pixmap)

    def get_data(self) -> dict:
        current_type = "exe"
        if self.type_combo.currentIndex() == 1:
            current_type = "url"
        elif self.type_combo.currentIndex() == 2:
            current_type = "folder"
        focus_x, focus_y = self.icon_preview.focus()
        return {
            "name": self.name_input.text(),
            "path": self.path_input.text(),
            "icon_path": self.icon_input.text(),
            "icon_focus": "manual",
            "icon_focus_x": focus_x,
            "icon_focus_y": focus_y,
            "icon_zoom": self.icon_preview.zoom(),
            "type": current_type,
            "group": self.group_input.currentText() or "Общее",
        }
