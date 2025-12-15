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
    GRID_BUTTON_SIZE,
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
    favoriteToggled = Signal(object)

    def __init__(self, app_data: dict, parent=None):
        super().__init__(parent)
        self.app_data = app_data

        prefix = "★ " if app_data.get("favorite") else ""
        display_name = f"{prefix}{app_data['name']}"
        self.setText(display_name)
        icon_path = app_data.get("icon_path", "")
        app_type = app_data.get("type", "exe")
        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        elif app_type == "url":
            self.setText(f"🌐 {display_name}")
        self.setIconSize(QSize(56, 56))
        # Fixed size for FlowLayout consistency
        self.setFixedSize(*GRID_BUTTON_SIZE)
        self.setStyleSheet(APP_BUTTON_STYLE)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(14)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(QColor(15, 23, 42, 60))
        self.setGraphicsEffect(shadow)

        self.clicked.connect(lambda: self.activated.emit(self.app_data))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def enterEvent(self, event):
        super().enterEvent(event)
        effect = self.graphicsEffect()
        if effect:
            # Simple "animation" by step changes is effectively instant,
            # but creates a snappy feel.
            # For real animation we would need to subclass QGraphicsEffect or wrap it.
            # Here we just make it distinct.
            effect.setBlurRadius(18)
            effect.setYOffset(6)
            effect.setColor(QColor(59, 130, 246, 90))

    def leaveEvent(self, event):
        super().leaveEvent(event)
        effect = self.graphicsEffect()
        if effect:
            effect.setBlurRadius(14)
            effect.setYOffset(3)
            effect.setColor(QColor(15, 23, 42, 60))

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        edit_action = menu.addAction("✏️ Редактировать")
        delete_action = menu.addAction("🗑️ Удалить")
        open_folder_action = menu.addAction("📂 Открыть расположение")
        favorite_action = menu.addAction(
            "☆ Закрепить" if not self.app_data.get("favorite") else "★ Открепить"
        )

        action = menu.exec(self.mapToGlobal(pos))
        if action == edit_action:
            self.editRequested.emit(self.app_data)
        elif action == delete_action:
            self.deleteRequested.emit(self.app_data)
        elif action == open_folder_action:
            self.openLocationRequested.emit(self.app_data)
        elif action == favorite_action:
            self.favoriteToggled.emit(self.app_data)


class AppListItem(QWidget):
    """Compact list entry for list mode."""

    activated = Signal(object)
    editRequested = Signal(object)
    deleteRequested = Signal(object)
    openLocationRequested = Signal(object)
    favoriteToggled = Signal(object)

    def __init__(self, app_data: dict, parent=None):
        super().__init__(parent)
        self.app_data = app_data

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        icon_label = QLabel()
        icon_path = app_data.get("icon_path", "")
        if icon_path and os.path.exists(icon_path):
            icon_label.setPixmap(QIcon(icon_path).pixmap(32, 32))
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        prefix = "★ " if app_data.get("favorite") else ""
        name_label = QLabel(f"{prefix}{app_data['name']}")
        name_label.setStyleSheet("font-weight: 700; color: #0f172a;")
        text_layout.addWidget(name_label)

        path_label = QLabel(app_data["path"])
        path_label.setStyleSheet("color: #6b7280;")
        text_layout.addWidget(path_label)
        layout.addLayout(text_layout)

        layout.addStretch()

        self.setLayout(layout)
        self.setStyleSheet(
            "QWidget { background: rgba(255,255,255,0.9); border: 1px solid #e5e7eb; border-radius: 12px; }"
            "QWidget::hover { background: #f3f4f6; border-color: #d1d5db; }"
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
        favorite_action = menu.addAction(
            "☆ Закрепить" if not self.app_data.get("favorite") else "★ Открепить"
        )

        action = menu.exec(self.mapToGlobal(pos))
        if action == edit_action:
            self.editRequested.emit(self.app_data)
        elif action == delete_action:
            self.deleteRequested.emit(self.app_data)
        elif action == open_folder_action:
            self.openLocationRequested.emit(self.app_data)
        elif action == favorite_action:
            self.favoriteToggled.emit(self.app_data)


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(32)
        self.setStyleSheet(TITLE_BAR_STYLE)

        from PySide6.QtWidgets import QHBoxLayout  # lazy import to avoid circular deps

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        spacer = QLabel()
        spacer.setFixedWidth(6)
        layout.addWidget(spacer)
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
