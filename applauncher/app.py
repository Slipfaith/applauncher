"""Main application window."""
import json
import json
import os
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QIcon, QPixmap

from .dialogs import AddAppDialog
from .icons import extract_icon_with_fallback
from .styles import (
    ADD_BUTTON_STYLE,
    CONTAINER_STYLE,
    GRID_WIDGET_STYLE,
    MENU_STYLE,
    WINDOW_STYLE,
)
from .widgets import AppButton, TitleBar

logger = logging.getLogger(__name__)


class AppLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMinimumSize(700, 500)
        self.setStyleSheet(WINDOW_STYLE)
        self.setAcceptDrops(True)

        self.config_file = "launcher_config.json"
        self.apps: list[dict] = []

        self.create_tray_icon()

        container = QWidget()
        container.setStyleSheet(CONTAINER_STYLE)
        self.setCentralWidget(container)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        container.setLayout(main_layout)

        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        content_widget.setLayout(content_layout)

        add_btn = QPushButton("➕ Добавить элемент")
        add_btn.setStyleSheet(ADD_BUTTON_STYLE)
        add_btn.clicked.connect(self.add_app)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(QColor(74, 144, 226, 80))
        add_btn.setGraphicsEffect(shadow)

        content_layout.addWidget(add_btn)

        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet(GRID_WIDGET_STYLE)
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(20)
        self.grid_widget.setLayout(self.grid_layout)
        content_layout.addWidget(self.grid_widget)
        content_layout.addStretch()

        main_layout.addWidget(content_widget)

        self.load_config()
        self.refresh_grid()

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)

        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(74, 144, 226))
        icon = QIcon(pixmap)
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()
        tray_menu.setStyleSheet(MENU_STYLE)

        show_action = tray_menu.addAction("🚀 Показать")
        show_action.triggered.connect(self.show)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("❌ Выход")
        quit_action.triggered.connect(QApplication.quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Лаунчер",
            "Приложение свернуто в трей. Кликните на иконку для возврата.",
            QSystemTrayIcon.Information,
            2000,
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            suffix = Path(file_path).suffix.lower()

            if suffix in {".exe", ".lnk"}:
                name = Path(file_path).stem
                icon_path = extract_icon_with_fallback(file_path) if suffix == ".exe" else ""

                self.apps.append(
                    {
                        "name": name,
                        "path": file_path,
                        "icon_path": icon_path,
                        "type": suffix.lstrip("."),
                    }
                )
                logger.info("Добавлено приложение из перетаскивания: %s", file_path)
            else:
                logger.warning("Игнорирован файл при перетаскивании: %s", file_path)
        self.save_config()
        self.refresh_grid()

    def add_app(self):
        dialog = AddAppDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data["name"] and data["path"]:
                self.apps.append(data)
                self.save_config()
                self.refresh_grid()
                logger.info("Добавлен элемент: %s", data["name"])

    def edit_app(self, button: AppButton):
        for i, app in enumerate(self.apps):
            if app["path"] == button.path:
                dialog = AddAppDialog(self, edit_mode=True, app_data=app)
                if dialog.exec():
                    self.apps[i] = dialog.get_data()
                    self.save_config()
                    self.refresh_grid()
                    logger.info("Изменен элемент: %s", self.apps[i]["name"])
                break

    def delete_app(self, button: AppButton):
        original_len = len(self.apps)
        self.apps = [app for app in self.apps if app["path"] != button.path]
        if len(self.apps) != original_len:
            logger.info("Удален элемент: %s", button.name)
            self.save_config()
            self.refresh_grid()

    def refresh_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 4
        for i, app in enumerate(self.apps):
            btn = AppButton(
                app["name"],
                app["path"],
                app.get("icon_path", ""),
                app.get("type", "exe"),
                self.grid_widget,
            )
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(btn, row, col)

    def save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.apps, f, ensure_ascii=False, indent=2)
        logger.info("Конфигурация сохранена")

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.apps = json.load(f)
            logger.info("Конфигурация загружена")


def run_app():
    app = QApplication([])
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)

    window = AppLauncher()
    window.show()
    return app.exec()
