"""Custom widgets for the launcher UI."""
import os
import webbrowser
import logging

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QWidget,
    QMessageBox,
    QMenu,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QColor

from .styles import (
    APP_BUTTON_STYLE,
    MENU_STYLE,
    TITLE_BAR_STYLE,
    TITLE_LABEL_STYLE,
    TITLE_BAR_BUTTON_STYLE,
    TITLE_BAR_CLOSE_STYLE,
)

logger = logging.getLogger(__name__)


class AppButton(QPushButton):
    def __init__(self, name: str, path: str, icon_path: str, app_type: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.path = path
        self.icon_path = icon_path
        self.app_type = app_type

        self.setText(name)
        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        elif app_type == "url":
            self.setText(f"🌐 {name}")
        self.setIconSize(QSize(56, 56))
        self.setMinimumSize(140, 120)
        self.setStyleSheet(APP_BUTTON_STYLE)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        self.clicked.connect(self.launch_item)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def launch_item(self):
        if self.app_type == "url":
            webbrowser.open(self.path)
            logger.info("Открыт сайт %s", self.path)
        else:
            if os.path.exists(self.path):
                os.startfile(self.path)
                logger.info("Запуск приложения %s", self.path)
            else:
                QMessageBox.warning(self, "Ошибка", f"Файл не найден:\n{self.path}")
                logger.warning("Файл не найден: %s", self.path)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        edit_action = menu.addAction("✏️ Редактировать")
        delete_action = menu.addAction("🗑️ Удалить")

        action = menu.exec(self.mapToGlobal(pos))
        if action == edit_action:
            main_window = self.window()
            main_window.edit_app(self)
        elif action == delete_action:
            main_window = self.window()
            main_window.delete_app(self)


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(45)
        self.setStyleSheet(TITLE_BAR_STYLE)

        from PySide6.QtWidgets import QHBoxLayout  # lazy import to avoid circular deps

        layout = QHBoxLayout()
        layout.setContentsMargins(15, 0, 10, 0)
        layout.setSpacing(0)

        title_label = QLabel("🚀 Лаунчер приложений")
        title_label.setStyleSheet(TITLE_LABEL_STYLE)
        layout.addWidget(title_label)
        layout.addStretch()

        min_btn = QPushButton("−")
        min_btn.setStyleSheet(TITLE_BAR_BUTTON_STYLE)
        min_btn.clicked.connect(parent.showMinimized)
        layout.addWidget(min_btn)

        max_btn = QPushButton("□")
        max_btn.setStyleSheet(TITLE_BAR_BUTTON_STYLE)
        max_btn.clicked.connect(self.toggle_maximize)
        layout.addWidget(max_btn)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(TITLE_BAR_CLOSE_STYLE)
        close_btn.clicked.connect(self.close_to_tray)
        layout.addWidget(close_btn)

        self.setLayout(layout)
        self.start = None

    def close_to_tray(self):
        self.parent.hide()
        self.parent.tray_icon.showMessage(
            "Лаунчер",
            "Приложение свернуто в трей",
            self.parent.tray_icon.Information,
            2000,
        )

    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.start:
            delta = event.position().toPoint() - self.start
            self.parent.move(self.parent.pos() + delta)

    def mouseReleaseEvent(self, event):
        self.start = None

    def mouseDoubleClickEvent(self, event):
        self.toggle_maximize()
