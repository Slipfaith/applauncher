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

from .styles import TOKENS

logger = logging.getLogger(__name__)


class AddAppDialog(QDialog):
    def __init__(self, parent=None, edit_mode: bool = False, app_data: dict | None = None, groups: list[str] | None = None):
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
        self.type_combo.addItems(["💻 Приложение", "🌐 Веб-сайт"])
        if app_data and app_data.get("type") == "url":
            self.type_combo.setCurrentIndex(1)
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

    def on_type_changed(self):
        is_url = self.type_combo.currentIndex() == 1
        if is_url:
            self.path_label.setText("URL адрес")
            self.browse_btn.setVisible(False)
            self.path_input.setPlaceholderText("https://example.com")
        else:
            self.path_label.setText("Путь к файлу или ярлыку")
            self.browse_btn.setVisible(True)
            self.path_input.setPlaceholderText("")

    def browse_path(self):
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

    def get_data(self) -> dict:
        return {
            "name": self.name_input.text(),
            "path": self.path_input.text(),
            "icon_path": self.icon_input.text(),
            "type": "url" if self.type_combo.currentIndex() == 1 else "exe",
            "group": self.group_input.currentText() or "Общее",
        }
