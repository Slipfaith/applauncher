"""Custom widgets for the launcher UI."""
import os
import logging

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QWidget,
    QMenu,
    QGraphicsDropShadowEffect,
    QSystemTrayIcon,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, QSize, Signal
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
    """Button used in grid view to display an application."""

    activated = Signal(object)
    editRequested = Signal(object)
    deleteRequested = Signal(object)
    openLocationRequested = Signal(object)

    def __init__(self, app_data: dict, parent=None):
        super().__init__(parent)
        self.app_data = app_data

        self.setText(app_data["name"])
        icon_path = app_data.get("icon_path", "")
        app_type = app_data.get("type", "exe")
        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        elif app_type == "url":
            self.setText(f"🌐 {app_data['name']}")
        self.setIconSize(QSize(56, 56))
        self.setMinimumSize(140, 120)
        self.setStyleSheet(APP_BUTTON_STYLE)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        self.clicked.connect(lambda: self.activated.emit(self.app_data))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        edit_action = menu.addAction("✏️ Редактировать")
        delete_action = menu.addAction("🗑️ Удалить")
        open_folder_action = menu.addAction("📂 Открыть расположение")

        action = menu.exec(self.mapToGlobal(pos))
        if action == edit_action:
            self.editRequested.emit(self.app_data)
        elif action == delete_action:
            self.deleteRequested.emit(self.app_data)
        elif action == open_folder_action:
            self.openLocationRequested.emit(self.app_data)


class AppListItem(QWidget):
    """Compact list entry for list mode."""

    activated = Signal(object)
    editRequested = Signal(object)
    deleteRequested = Signal(object)
    openLocationRequested = Signal(object)

    def __init__(self, app_data: dict, parent=None):
        super().__init__(parent)
        self.app_data = app_data

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_path = app_data.get("icon_path", "")
        if icon_path and os.path.exists(icon_path):
            icon_label.setPixmap(QIcon(icon_path).pixmap(32, 32))
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        name_label = QLabel(app_data["name"])
        name_label.setStyleSheet("font-weight: 600;")
        text_layout.addWidget(name_label)

        path_label = QLabel(app_data["path"])
        path_label.setStyleSheet("color: #666;")
        text_layout.addWidget(path_label)
        layout.addLayout(text_layout)

        layout.addStretch()

        self.setLayout(layout)
        self.setStyleSheet(
            "QWidget { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; }"
            "QWidget::hover { background: #f5f6ff; }"
        )

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.app_data)
        super().mousePressEvent(event)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        edit_action = menu.addAction("✏️ Редактировать")
        delete_action = menu.addAction("🗑️ Удалить")
        open_folder_action = menu.addAction("📂 Открыть расположение")

        action = menu.exec(self.mapToGlobal(pos))
        if action == edit_action:
            self.editRequested.emit(self.app_data)
        elif action == delete_action:
            self.deleteRequested.emit(self.app_data)
        elif action == open_folder_action:
            self.openLocationRequested.emit(self.app_data)


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
            QSystemTrayIcon.Information,
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
