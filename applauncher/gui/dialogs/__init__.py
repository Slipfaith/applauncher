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
    QTextEdit,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, QSize

from ..styles import TOKENS
from ..tile_image import IconFrameEditor, clamp, default_icon_frame
from ...repository import DEFAULT_MACRO_GROUPS

logger = logging.getLogger(__name__)

from .hotkey_capture_dialog import HotkeyCaptureDialog  # noqa: E402
from .settings_dialog import SettingsDialog  # noqa: E402


class AddAppDialog(QDialog):
    def __init__(
        self,
        parent=None,
        edit_mode: bool = False,
        app_data: dict | None = None,
        groups: list[str] | None = None,
        default_type: str | None = None,
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
        elif default_type == "url":
            self.type_combo.setCurrentIndex(1)
        elif default_type == "folder":
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
            if app_data.get("type") == "url":
                self.path_input.setText(app_data.get("raw_path") or app_data.get("path", ""))
            else:
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
                clamp(float(app_data["icon_frame_x"])),
                clamp(float(app_data["icon_frame_y"])),
                clamp(float(app_data["icon_frame_w"])),
                clamp(float(app_data["icon_frame_h"])),
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
        self.icon_preview.set_source_from_file(icon_path)
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


class AddMacroDialog(QDialog):
    def __init__(
        self,
        parent=None,
        edit_mode: bool = False,
        macro_data: dict | None = None,
        groups: list[str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Редактировать макрос" if edit_mode else "Добавить макрос")
        self.setMinimumWidth(TOKENS.sizes.dialog_min_width)
        base_groups = groups or []
        self.available_groups = list(dict.fromkeys([*DEFAULT_MACRO_GROUPS, *base_groups]))

        layout = QVBoxLayout()
        layout.setSpacing(TOKENS.spacing.lg)
        layout.setContentsMargins(
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
            TOKENS.spacing.xl,
        )

        type_label = QLabel("Группа")
        layout.addWidget(type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(self.available_groups)
        layout.addWidget(self.type_combo)

        name_label = QLabel("Название")
        layout.addWidget(name_label)
        self.name_input = QLineEdit()
        if macro_data:
            self.name_input.setText(macro_data.get("name", ""))
        layout.addWidget(self.name_input)

        self.path_label = QLabel("Путь к файлу макроса")
        layout.addWidget(self.path_label)
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        if macro_data:
            self.path_input.setText(macro_data.get("path", ""))
        path_layout.addWidget(self.path_input)

        self.browse_btn = QPushButton("📁 Обзор")
        self.browse_btn.setProperty("variant", "accent")
        self.browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)

        input_type_label = QLabel("Тип входа")
        layout.addWidget(input_type_label)
        self.input_type_combo = QComboBox()
        self.input_type_combo.addItem("Файл", userData="file")
        self.input_type_combo.addItem("Папка", userData="folder")
        layout.addWidget(self.input_type_combo)

        description_label = QLabel("Описание")
        layout.addWidget(description_label)
        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(84)
        if macro_data:
            self.description_input.setPlainText(macro_data.get("description", ""))
        layout.addWidget(self.description_input)

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

        if macro_data:
            group = macro_data.get("group")
            if group and group in self.available_groups:
                self.type_combo.setCurrentText(group)
            input_type = macro_data.get("input_type")
            if input_type:
                index = self.input_type_combo.findData(input_type)
                if index >= 0:
                    self.input_type_combo.setCurrentIndex(index)

    def browse_path(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл макроса",
            "",
            "Все файлы (*.*)",
        )
        if file_path:
            self.path_input.setText(file_path)
            if not self.name_input.text():
                self.name_input.setText(Path(file_path).stem)

    def get_data(self) -> dict:
        return {
            "name": self.name_input.text(),
            "path": self.path_input.text(),
            "description": self.description_input.toPlainText(),
            "group": self.type_combo.currentText(),
            "input_type": self.input_type_combo.currentData(),
        }
