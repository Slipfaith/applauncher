"""Main application window."""
import json
import os
import logging
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QPixmap,
    QKeySequence,
    QShortcut,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .dialogs import AddAppDialog
from .icons import extract_icon_with_fallback
from .styles import (
    ADD_BUTTON_STYLE,
    CONTAINER_STYLE,
    GRID_WIDGET_STYLE,
    MENU_STYLE,
    WINDOW_STYLE,
)
from .widgets import AppButton, AppListItem, TitleBar

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
        self.groups: list[str] = ["Общее"]
        self.view_mode = "grid"

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
        content_layout.setSpacing(12)
        content_widget.setLayout(content_layout)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск приложений...")
        self.search_input.textChanged.connect(self.refresh_view)
        self.search_input.returnPressed.connect(self.launch_top_result)
        search_layout.addWidget(self.search_input)

        self.view_toggle = QPushButton("🔲 Сетка")
        self.view_toggle.setCheckable(True)
        self.view_toggle.setChecked(True)
        self.view_toggle.clicked.connect(self.toggle_view_mode)
        search_layout.addWidget(self.view_toggle)

        content_layout.addLayout(search_layout)

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

        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(False)
        self.tabs.tabBarClicked.connect(self.on_tab_clicked)
        self.tabs.currentChanged.connect(lambda _: self.refresh_view())
        content_layout.addWidget(self.tabs)

        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet(GRID_WIDGET_STYLE)
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(20)
        self.grid_widget.setLayout(self.grid_layout)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(10)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_container.setLayout(self.list_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(GRID_WIDGET_STYLE)
        self.scroll_area.setWidget(self.grid_widget)

        content_layout.addWidget(self.scroll_area)
        content_layout.addStretch()

        main_layout.addWidget(content_widget)

        self.load_config()
        self.setup_tabs()
        self.setup_shortcuts()
        self.refresh_view()

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
                        "group": self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.count() else "Общее",
                        "usage_count": 0,
                    }
                )
                logger.info("Добавлено приложение из перетаскивания: %s", file_path)
            else:
                logger.warning("Игнорирован файл при перетаскивании: %s", file_path)
        self.save_config()
        self.refresh_grid()

    def add_app(self):
        dialog = AddAppDialog(self, groups=self.groups)
        if dialog.exec():
            data = dialog.get_data()
            if data["name"] and data["path"]:
                data.setdefault("usage_count", 0)
                if data.get("group") not in self.groups:
                    self.groups.append(data.get("group", "Общее"))
                    self.setup_tabs()
                self.apps.append(data)
                self.save_config()
                self.refresh_view()
                logger.info("Добавлен элемент: %s", data["name"])

    def edit_app(self, app_data: dict):
        for i, app in enumerate(self.apps):
            if app["path"] == app_data["path"]:
                dialog = AddAppDialog(self, edit_mode=True, app_data=app, groups=self.groups)
                if dialog.exec():
                    updated = dialog.get_data()
                    updated.setdefault("usage_count", app.get("usage_count", 0))
                    self.apps[i] = updated
                    if updated.get("group") not in self.groups:
                        self.groups.append(updated.get("group", "Общее"))
                        self.setup_tabs()
                    self.save_config()
                    self.refresh_view()
                    logger.info("Изменен элемент: %s", self.apps[i]["name"])
                break

    def delete_app(self, app_data: dict):
        original_len = len(self.apps)
        self.apps = [app for app in self.apps if app["path"] != app_data["path"]]
        if len(self.apps) != original_len:
            logger.info("Удален элемент: %s", app_data["name"])
            self.save_config()
            self.refresh_view()

    def launch_app(self, app_data: dict):
        if app_data.get("type") == "url":
            webbrowser.open(app_data["path"])
            logger.info("Открыт сайт %s", app_data["path"])
        else:
            if os.path.exists(app_data["path"]):
                os.startfile(app_data["path"])
                logger.info("Запуск приложения %s", app_data["path"])
            else:
                QMessageBox.warning(self, "Ошибка", f"Файл не найден:\n{app_data['path']}")
                logger.warning("Файл не найден: %s", app_data["path"])
                return

        app_data["usage_count"] = app_data.get("usage_count", 0) + 1
        for item in self.apps:
            if item["path"] == app_data["path"]:
                item["usage_count"] = app_data["usage_count"]
                break
        self.save_config()
        self.refresh_view()

    def open_location(self, app_data: dict):
        if app_data.get("type") == "url":
            QMessageBox.information(self, "Информация", "Для веб-ссылок нет локальной папки")
            return
        folder = Path(app_data["path"]).parent
        if folder.exists():
            os.startfile(folder)
        else:
            QMessageBox.warning(self, "Ошибка", f"Папка не найдена:\n{folder}")

    def refresh_view(self):
        current_group = self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.count() else "Общее"
        text = self.search_input.text().lower()
        filtered = [
            app
            for app in self.apps
            if (app.get("group", "Общее") == current_group)
            and (text in app["name"].lower() or text in app["path"].lower())
        ]

        filtered.sort(key=lambda a: (-a.get("usage_count", 0), a["name"]))

        if self.view_mode == "grid":
            self.view_toggle.setText("🔲 Сетка")
            self.view_toggle.setChecked(True)
            self.scroll_area.setWidget(self.grid_widget)
            self.populate_grid(filtered)
        else:
            self.view_toggle.setText("📄 Список")
            self.view_toggle.setChecked(False)
            self.scroll_area.setWidget(self.list_container)
            self.populate_list(filtered)

    def populate_grid(self, apps: list[dict]):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        available_width = max(self.grid_widget.width(), 1)
        cols = max(1, available_width // 180)

        for i, app in enumerate(apps):
            btn = AppButton(app, self.grid_widget)
            btn.activated.connect(self.launch_app)
            btn.editRequested.connect(self.edit_app)
            btn.deleteRequested.connect(self.delete_app)
            btn.openLocationRequested.connect(self.open_location)
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(btn, row, col)

    def populate_list(self, apps: list[dict]):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for app in apps:
            item = AppListItem(app, self.list_container)
            item.activated.connect(self.launch_app)
            item.editRequested.connect(self.edit_app)
            item.deleteRequested.connect(self.delete_app)
            item.openLocationRequested.connect(self.open_location)
            self.list_layout.addWidget(item)
        self.list_layout.addStretch()

    def launch_top_result(self):
        current_group = self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.count() else "Общее"
        text = self.search_input.text().lower()
        filtered = [
            app
            for app in self.apps
            if (app.get("group", "Общее") == current_group)
            and (text in app["name"].lower() or text in app["path"].lower())
        ]
        if not filtered:
            return
        filtered.sort(key=lambda a: (-a.get("usage_count", 0), a["name"]))
        self.launch_app(filtered[0])

    def save_config(self):
        payload = {
            "apps": self.apps,
            "groups": self.groups,
            "view_mode": self.view_mode,
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("Конфигурация сохранена")

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.apps = data.get("apps", [])
                self.groups = data.get("groups", self.groups)
                self.view_mode = data.get("view_mode", self.view_mode)
            else:
                self.apps = data
            for app in self.apps:
                app.setdefault("usage_count", 0)
                app.setdefault("group", "Общее")
            logger.info("Конфигурация загружена")
        if not self.groups:
            self.groups = ["Общее"]

    def setup_tabs(self):
        self.tabs.clear()
        for group in self.groups:
            self.tabs.addTab(QWidget(), group)
        self.tabs.addTab(QWidget(), "+")
        if self.view_mode == "list":
            self.view_toggle.setText("📄 Список")
            self.view_toggle.setChecked(False)
            self.scroll_area.setWidget(self.list_container)
        else:
            self.view_toggle.setText("🔲 Сетка")
            self.view_toggle.setChecked(True)
            self.scroll_area.setWidget(self.grid_widget)

    def on_tab_clicked(self, index: int):
        if index == self.tabs.count() - 1:
            text, ok = QInputDialog.getText(self, "Новая группа", "Название группы:")
            if ok and text:
                self.groups.append(text)
                self.setup_tabs()
                self.tabs.setCurrentIndex(self.tabs.count() - 2)
                self.save_config()
        self.refresh_view()

    def toggle_view_mode(self):
        self.view_mode = "list" if self.view_mode == "grid" else "grid"
        self.save_config()
        self.refresh_view()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.view_mode == "grid":
            self.refresh_view()

    def setup_shortcuts(self):
        shortcut = QShortcut(QKeySequence("Ctrl+Alt+Space"), self)
        shortcut.setContext(Qt.ApplicationShortcut)
        shortcut.activated.connect(self.toggle_visibility)
        self.toggle_shortcut = shortcut

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()


def run_app():
    app = QApplication([])
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)

    server_name = "applauncher_single_instance"
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(200):
        logger.info("Уже запущен экземпляр лаунчера, выход")
        return 0

    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.listen(server_name)
    app._single_instance_server = server  # keep reference

    window = AppLauncher()
    window.show()
    return app.exec()
