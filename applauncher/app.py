"""Main application window."""
import os
import logging
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QFileSystemWatcher, QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, QUrl
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QDesktopServices,
    QIcon,
    QPixmap,
    QKeySequence,
    QShortcut,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .config import ConfigError, DEFAULT_CONFIG, load_config, save_config
from .dialogs import AddAppDialog
from .icons import extract_icon_with_fallback
from .layouts import FlowLayout
from .styles import TOKENS, apply_design_system, apply_shadow
from .repository import AppRepository, DEFAULT_GROUP
from .widgets import AppButton, AppListItem, TitleBar

logger = logging.getLogger(__name__)


class IconExtractionSignals(QObject):
    finished = Signal(str, str)


class IconExtractionWorker(QRunnable):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = IconExtractionSignals()

    def run(self):  # pragma: no cover - visual side effects
        icon_path = extract_icon_with_fallback(self.path)
        self.signals.finished.emit(self.path, icon_path or "")


class GroupTabBar(QTabBar):
    appDropRequested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setElideMode(Qt.ElideRight)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-applauncher-app"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-applauncher-app"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasFormat("application/x-applauncher-app"):
            super().dropEvent(event)
            return
        index = self.tabAt(event.position().toPoint())
        if index < 0:
            return
        group = self.tabText(index)
        if group == "+":
            return
        payload = bytes(event.mimeData().data("application/x-applauncher-app")).decode("utf-8")
        if payload:
            self.appDropRequested.emit(payload, group)
            self.setCurrentIndex(index)
            event.acceptProposedAction()


class AppLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("mainWindow")
        self.setMinimumSize(*TOKENS.sizes.window_min)
        self.setAcceptDrops(True)

        self.config_file = "launcher_config.json"
        self.repository = AppRepository()
        self.groups: list[str] = [DEFAULT_GROUP]
        self.view_mode = "grid"
        self._last_render_state: tuple[str, str, str, int] | None = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._persist_config)
        self.thread_pool = QThreadPool.globalInstance()
        self._icon_tasks: list[IconExtractionWorker] = []
        self.shortcut_watcher = QFileSystemWatcher(self)
        self.shortcut_scan_timer = QTimer(self)
        self.shortcut_scan_timer.setSingleShot(True)
        self.shortcut_scan_timer.setInterval(500)
        self.shortcut_scan_timer.timeout.connect(self._rescan_shortcuts)
        self.shortcut_roots: list[Path] = []
        self.launch_handlers = {
            "url": self._launch_url,
            "exe": self._launch_executable,
            "lnk": self._launch_shortcut,
            "folder": self._launch_folder,
        }

        self.create_tray_icon()

        container = QWidget()
        container.setObjectName("centralContainer")
        self.setCentralWidget(container)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
        )
        main_layout.setSpacing(TOKENS.spacing.none)
        container.setLayout(main_layout)

        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(*TOKENS.layout.content_margins)
        content_layout.setSpacing(TOKENS.layout.content_spacing)
        content_widget.setLayout(content_layout)

        controls_layout = QVBoxLayout()
        controls_layout.setContentsMargins(
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
        )
        controls_layout.setSpacing(TOKENS.layout.content_spacing)

        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(False)
        self.tabs.setDocumentMode(True)
        self.tabs.setObjectName("mainTabs")
        self.tab_bar = GroupTabBar(self)
        self.tab_bar.appDropRequested.connect(self.move_app_by_path)
        self.tabs.setTabBar(self.tab_bar)
        self.tabs.tabBarClicked.connect(self.on_tab_clicked)
        self.tabs.currentChanged.connect(lambda _: self.refresh_view())
        self.tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self.show_tab_context_menu)
        controls_layout.addWidget(self.tabs)

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
        )
        search_layout.setSpacing(TOKENS.layout.search_spacing)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск приложений...")
        self.search_input.setObjectName("searchInput")
        self.search_input.textChanged.connect(self.refresh_view)
        self.search_input.returnPressed.connect(self.launch_top_result)
        search_layout.addWidget(self.search_input)

        self.view_toggle = QPushButton()
        self.view_toggle.setProperty("variant", "control")
        self.view_toggle.setProperty("role", "viewToggle")
        self.view_toggle.clicked.connect(self.toggle_view_mode)
        search_layout.addWidget(self.view_toggle)

        controls_layout.addLayout(search_layout)
        content_layout.addLayout(controls_layout)

        add_btn = QPushButton("Добавить приложение")
        add_btn.setProperty("variant", "accent")
        add_btn.clicked.connect(self.add_app)
        apply_shadow(add_btn, TOKENS.shadows.raised)

        clear_btn = QPushButton("Удалить все")
        clear_btn.setProperty("variant", "danger")
        clear_btn.clicked.connect(self.clear_all_apps)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
        )
        actions_layout.setSpacing(TOKENS.layout.content_spacing)
        actions_layout.addWidget(add_btn)
        actions_layout.addWidget(clear_btn)
        actions_layout.addStretch()

        content_layout.addLayout(actions_layout)

        self.grid_widget = QWidget()
        self.grid_layout = FlowLayout(
            self.grid_widget,
            margin=TOKENS.layout.grid_layout_margin,
            h_spacing=TOKENS.layout.grid_layout_spacing,
            v_spacing=TOKENS.layout.grid_layout_spacing,
        )
        self.grid_widget.setLayout(self.grid_layout)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(TOKENS.layout.list_spacing)
        self.list_layout.setContentsMargins(
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
        )
        self.list_container.setLayout(self.list_layout)

        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self.grid_widget)
        self.view_stack.addWidget(self.list_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.view_stack)

        content_layout.addWidget(self.scroll_area)
        content_layout.addStretch()

        main_layout.addWidget(content_widget)

        self.load_state()
        self.setup_shortcuts()
        self.refresh_view()

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)

        pixmap = QPixmap(TOKENS.sizes.tray_icon, TOKENS.sizes.tray_icon)
        pixmap.fill(QColor(TOKENS.colors.accent))
        icon = QIcon(pixmap)
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()

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
        added = False
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            suffix = Path(file_path).suffix.lower()

            if os.path.isdir(file_path):
                name = Path(file_path).name
                app_data = {
                    "name": name,
                    "path": file_path,
                    "icon_path": "",
                    "type": "folder",
                    "group": self.current_group,
                    "usage_count": 0,
                    "source": "manual",
                }
                self.repository.add_app(app_data)
                added = True
                logger.info("Добавлена папка из перетаскивания: %s", file_path)
                continue

            if suffix == ".url" and os.path.exists(file_path):
                target_url = self._read_url_shortcut(file_path)
                normalized = self._normalize_url(target_url)
                if normalized:
                    name = Path(file_path).stem
                    app_data = {
                        "name": name,
                        "path": normalized,
                        "icon_path": "",
                        "type": "url",
                        "group": self.current_group,
                        "usage_count": 0,
                        "source": "manual",
                    }
                    self.repository.add_app(app_data)
                    added = True
                    logger.info("Добавлена ссылка из ярлыка: %s -> %s", file_path, normalized)
                else:
                    logger.warning("Не удалось прочитать ссылку из ярлыка: %s", file_path)
                continue

            if suffix in {".exe", ".lnk", ".bat", ".cmd", ".py"} and os.path.exists(file_path):
                name = Path(file_path).stem
                app_data = {
                    "name": name,
                    "path": file_path,
                    "icon_path": "",
                    "type": "lnk" if suffix == ".lnk" else "exe",
                    "group": self.current_group,
                    "usage_count": 0,
                    "source": "manual",
                }
                self.repository.add_app(app_data)
                self._start_icon_extraction(app_data)
                added = True
                logger.info("Добавлено приложение из перетаскивания: %s", file_path)
            else:
                logger.warning("Игнорирован файл при перетаскивании: %s", file_path)
        if added:
            self.schedule_save()
            self.refresh_view()

    def add_app(self):
        dialog = AddAppDialog(self, groups=self.groups)
        if dialog.exec():
            data = self._validate_app_data(dialog.get_data())
            if not data:
                return
            data["custom_icon"] = bool(data.get("icon_path"))
            if data.get("group") not in self.groups:
                self.groups.append(data.get("group", DEFAULT_GROUP))
                self.setup_tabs()
            created = self.repository.add_app(data)
            self._start_icon_extraction(created)
            self.schedule_save()
            self.refresh_view()
            logger.info("Добавлен элемент: %s", data["name"])

    def edit_app(self, app_data: dict):
        for app in self.repository.apps:
            if app["path"] == app_data["path"]:
                dialog = AddAppDialog(self, edit_mode=True, app_data=app, groups=self.groups)
                if dialog.exec():
                    updated = self._validate_app_data(dialog.get_data())
                    if not updated:
                        return
                    previous_icon = app.get("icon_path")
                    previous_custom_icon = app.get("custom_icon", False)
                    updated["usage_count"] = app.get("usage_count", 0)
                    updated["source"] = app.get("source", "manual")
                    if updated.get("icon_path") != previous_icon:
                        updated["custom_icon"] = bool(updated.get("icon_path"))
                    else:
                        updated["custom_icon"] = previous_custom_icon
                    if updated.get("group") not in self.groups:
                        self.groups.append(updated.get("group", DEFAULT_GROUP))
                        self.setup_tabs()
                    stored = self.repository.update_app(app["path"], updated)
                    new_icon = (stored or updated).get("icon_path")
                    if previous_icon and previous_icon != new_icon:
                        self._cleanup_icon_cache(previous_icon)
                    self._start_icon_extraction(stored or updated)
                    self.schedule_save()
                    self.refresh_view()
                    logger.info("Изменен элемент: %s", updated["name"])
                break

    def delete_app(self, app_data: dict):
        if self.current_group != DEFAULT_GROUP:
            self.remove_app_from_group(app_data, self.current_group)
            return
        if self.repository.delete_app(app_data["path"]):
            self._cleanup_icon_cache(app_data.get("icon_path"))
            logger.info("Удален элемент: %s", app_data["name"])
            self.schedule_save()
            self.refresh_view()

    def clear_all_apps(self):
        if not self.repository.apps:
            QMessageBox.information(self, "Удалить все", "Список приложений уже пуст.")
            return
        confirm = QMessageBox.question(
            self,
            "Удалить все",
            "Удалить все приложения из лаунчера?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        for app in list(self.repository.apps):
            self._cleanup_icon_cache(app.get("icon_path"))
        self.repository.clear_apps()
        self.schedule_save()
        self.refresh_view()
        logger.info("Удалены все приложения")

    def toggle_favorite(self, app_data: dict):
        target = next((item for item in self.repository.apps if item["path"] == app_data["path"]), None)
        if not target:
            return
        updated = dict(target)
        updated["favorite"] = not target.get("favorite", False)
        self.repository.update_app(target["path"], updated)
        self.schedule_save()
        self.refresh_view()

    def move_app_to_group(self, app_data: dict, group: str):
        if group not in self.groups:
            return
        target = next((item for item in self.repository.apps if item["path"] == app_data["path"]), None)
        if not target:
            return
        updated = dict(target)
        updated["group"] = group
        self.repository.update_app(target["path"], updated)
        self.schedule_save()
        self.refresh_view()

    def remove_app_from_group(self, app_data: dict, group: str):
        if group == DEFAULT_GROUP:
            return
        target = next((item for item in self.repository.apps if item["path"] == app_data["path"]), None)
        if not target:
            return
        if target.get("group", DEFAULT_GROUP) != group:
            return
        updated = dict(target)
        updated["group"] = DEFAULT_GROUP
        self.repository.update_app(target["path"], updated)
        self.schedule_save()
        self.refresh_view()

    def move_app_by_path(self, app_path: str, group: str):
        target = next((item for item in self.repository.apps if item["path"] == app_path), None)
        if not target:
            return
        self.move_app_to_group(target, group)

    def launch_app(self, app_data: dict):
        handler = self.launch_handlers.get(app_data.get("type", "exe"), self._launch_executable)
        success = handler(app_data)
        if success:
            updated = self.repository.increment_usage(app_data["path"]) or app_data
            app_data.update(updated)
            self.schedule_save()
            self.refresh_view()

    def open_location(self, app_data: dict):
        if app_data.get("type") == "url":
            QMessageBox.information(self, "Информация", "Для веб-ссылок нет локальной папки")
            return
        if app_data.get("type") == "folder":
            folder = Path(app_data["path"])
        else:
            folder = Path(app_data["path"]).parent
        if folder.exists():
            try:
                os.startfile(folder)
            except OSError as err:  # pragma: no cover - system dependent
                QMessageBox.warning(self, "Ошибка", f"Не удалось открыть папку:\n{err}")
        else:
            QMessageBox.warning(self, "Ошибка", f"Папка не найдена:\n{folder}")

    def refresh_view(self):
        current_group = self.current_group
        query = self.search_input.text()
        render_state = (self.view_mode, current_group, query, self.repository.version)
        if self._last_render_state == render_state:
            return
        self._last_render_state = render_state

        filtered = self.repository.get_filtered_apps(query, current_group)
        self._sync_view_toggle()

        if self.view_mode == "grid":
            self.view_stack.setCurrentWidget(self.grid_widget)
            self.populate_grid(filtered)
        else:
            self.view_stack.setCurrentWidget(self.list_container)
            self.populate_list(filtered)

    def populate_grid(self, apps: list[dict]):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current_group = self.current_group
        for app in apps:
            btn = AppButton(
                app,
                self.grid_widget,
                available_groups=self.groups,
                current_group=current_group,
            )
            btn.activated.connect(self.launch_app)
            btn.editRequested.connect(self.edit_app)
            btn.deleteRequested.connect(self.delete_app)
            btn.openLocationRequested.connect(self.open_location)
            btn.favoriteToggled.connect(self.toggle_favorite)
            btn.moveRequested.connect(self.move_app_to_group)
            self.grid_layout.addWidget(btn)

    def populate_list(self, apps: list[dict]):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current_group = self.current_group
        for app in apps:
            item = AppListItem(
                app,
                self.list_container,
                available_groups=self.groups,
                current_group=current_group,
            )
            item.activated.connect(self.launch_app)
            item.editRequested.connect(self.edit_app)
            item.deleteRequested.connect(self.delete_app)
            item.openLocationRequested.connect(self.open_location)
            item.favoriteToggled.connect(self.toggle_favorite)
            item.moveRequested.connect(self.move_app_to_group)
            self.list_layout.addWidget(item)
        self.list_layout.addStretch()

    def launch_top_result(self):
        current_group = self.current_group
        filtered = self.repository.get_filtered_apps(self.search_input.text(), current_group)
        if not filtered:
            return
        self.launch_app(filtered[0])

    def load_state(self):
        try:
            data = load_config(self.config_file)
        except ConfigError as err:
            QMessageBox.warning(self, "Ошибка конфигурации", str(err))
            logger.warning("Ошибка загрузки конфигурации: %s", err)
            data = DEFAULT_CONFIG.copy()

        apps = [app for app in data.get("apps", []) if app.get("source") != "auto"]
        self.repository.set_apps(apps)
        self.groups = data.get("groups", self.groups) or [DEFAULT_GROUP]
        self.view_mode = data.get("view_mode", self.view_mode)
        for app in self.repository.apps:
            group_name = app.get("group", DEFAULT_GROUP)
            if group_name not in self.groups:
                self.groups.append(group_name)
        self.setup_tabs()
        self._last_render_state = None

    def schedule_save(self):
        self._save_timer.start()

    def _persist_config(self):
        payload = {
            "apps": self.repository.apps,
            "groups": self.groups or [DEFAULT_GROUP],
            "view_mode": self.view_mode,
        }
        try:
            save_config(self.config_file, payload)
            logger.info("Конфигурация сохранена")
        except ConfigError as err:
            QMessageBox.warning(self, "Ошибка", str(err))
            logger.warning("Ошибка сохранения конфигурации: %s", err)

    @property
    def current_group(self) -> str:
        return self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.count() else DEFAULT_GROUP

    def _validate_app_data(self, data: dict | None) -> dict | None:
        if not data:
            return None
        name = (data.get("name") or "").strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Укажите название элемента")
            return None
        path_value = (data.get("path") or "").strip()
        data["name"] = name
        data["path"] = path_value
        item_type = data.get("type", "exe")
        args = data.get("args") or []
        if isinstance(args, str):
            args = [args]
        data["args"] = args
        if item_type == "url":
            normalized = self._normalize_url(path_value)
            if not normalized:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Введите корректный URL (пример: https://example.com или steam://rungameid/550)",
                )
                return None
            data["path"] = normalized
        elif item_type == "folder":
            if not path_value:
                QMessageBox.warning(self, "Ошибка", "Укажите путь к папке")
                return None
            if not os.path.isdir(path_value):
                QMessageBox.warning(self, "Ошибка", f"Папка не найдена:\n{path_value}")
                return None
            data["type"] = "folder"
        else:
            if not path_value:
                QMessageBox.warning(self, "Ошибка", "Укажите путь к исполняемому файлу")
                return None
            if not os.path.exists(path_value):
                QMessageBox.warning(self, "Ошибка", f"Файл не найден:\n{path_value}")
                return None
            suffix = Path(path_value).suffix.lower()
            data["type"] = "lnk" if suffix == ".lnk" else "exe"
        data.setdefault("group", DEFAULT_GROUP)
        data.setdefault("usage_count", 0)
        data.setdefault("favorite", False)
        data.setdefault("args", [])
        data.setdefault("source", "manual")
        return data

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"https://{url}"
            parsed = urlparse(url)
        if parsed.scheme == "steam":
            if parsed.netloc or parsed.path:
                return url
            return ""
        if not parsed.netloc:
            return ""
        return url

    def _read_url_shortcut(self, file_path: str) -> str:
        for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1251", "latin-1"):
            try:
                with open(file_path, "r", encoding=encoding) as handle:
                    for raw_line in handle:
                        line = raw_line.strip()
                        if line.lower().startswith("url="):
                            return line[4:].strip()
            except UnicodeError:
                continue
            except OSError:
                break
        return ""

    def _launch_url(self, app_data: dict) -> bool:
        normalized = self._normalize_url(app_data.get("path", ""))
        if not normalized:
            QMessageBox.warning(self, "Ошибка", "Некорректный URL")
            return False
        try:
            if QDesktopServices.openUrl(QUrl(normalized)):
                logger.info("Открыт адрес %s", normalized)
                return True
            opened = bool(webbrowser.open(normalized))
            if not opened:
                QMessageBox.warning(self, "Ошибка", "Не удалось открыть ссылку")
                return False
            logger.info("Открыт адрес %s", normalized)
            return True
        except Exception as err:  # pragma: no cover - system/browser dependent
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть ссылку:\n{err}")
            logger.exception("Ошибка открытия URL %s", normalized)
            return False

    def _launch_executable(self, app_data: dict) -> bool:
        path_value = app_data.get("path", "")
        if not os.path.exists(path_value):
            QMessageBox.warning(self, "Ошибка", f"Файл не найден:\n{path_value}")
            logger.warning("Файл не найден: %s", path_value)
            return False
        try:
            args = app_data.get("args") or []
            if args:
                subprocess.Popen([path_value, *args])
            else:
                os.startfile(path_value)
            logger.info("Запуск приложения %s", path_value)
            return True
        except OSError as err:  # pragma: no cover - system dependent
            QMessageBox.warning(self, "Ошибка", f"Не удалось запустить файл:\n{err}")
            logger.warning("Ошибка запуска %s: %s", path_value, err)
            return False

    def _launch_shortcut(self, app_data: dict) -> bool:
        path_value = app_data.get("path", "")
        if not os.path.exists(path_value):
            QMessageBox.warning(self, "Ошибка", f"Файл не найден:\n{path_value}")
            logger.warning("Файл не найден: %s", path_value)
            return False
        try:
            os.startfile(path_value)
            logger.info("Запуск ярлыка %s", path_value)
            return True
        except OSError as err:  # pragma: no cover - system dependent
            QMessageBox.warning(self, "Ошибка", f"Не удалось запустить ярлык:\n{err}")
            logger.warning("Ошибка запуска ярлыка %s: %s", path_value, err)
            return False

    def _launch_folder(self, app_data: dict) -> bool:
        path_value = app_data.get("path", "")
        if not os.path.isdir(path_value):
            QMessageBox.warning(self, "Ошибка", f"Папка не найдена:\n{path_value}")
            logger.warning("Папка не найдена: %s", path_value)
            return False
        try:
            os.startfile(path_value)
            logger.info("Открыта папка %s", path_value)
            return True
        except OSError as err:  # pragma: no cover - system dependent
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть папку:\n{err}")
            logger.warning("Ошибка открытия папки %s: %s", path_value, err)
            return False

    def _start_icon_extraction(self, app_data: dict | None):
        if not app_data or app_data.get("icon_path"):
            return
        if app_data.get("type") == "lnk":
            if self.repository.update_icon(app_data["path"], app_data["path"]):
                self.schedule_save()
                self.refresh_view()
            return
        if app_data.get("type") != "exe":
            return
        worker = IconExtractionWorker(app_data["path"])
        worker.signals.finished.connect(
            lambda path, icon, w=worker: self._on_icon_extracted(path, icon, w)
        )
        self._icon_tasks.append(worker)
        self.thread_pool.start(worker)

    def _setup_shortcut_discovery(self) -> None:
        self.shortcut_watcher.directoryChanged.connect(self._schedule_shortcut_rescan)
        self.shortcut_roots = self._get_shortcut_roots()
        self._refresh_shortcut_watcher()
        self._sync_shortcuts()

    def _schedule_shortcut_rescan(self, _path: str) -> None:
        self.shortcut_scan_timer.start()

    def _rescan_shortcuts(self) -> None:
        self.shortcut_roots = self._get_shortcut_roots()
        self._refresh_shortcut_watcher()
        self._sync_shortcuts()

    def _refresh_shortcut_watcher(self) -> None:
        watched = self.shortcut_watcher.directories()
        if watched:
            self.shortcut_watcher.removePaths(watched)
        directories: list[str] = []
        for root in self.shortcut_roots:
            if not root.exists():
                continue
            directories.append(str(root))
            for dirpath, dirnames, _ in os.walk(root):
                for dirname in dirnames:
                    directories.append(str(Path(dirpath) / dirname))
        if directories:
            self.shortcut_watcher.addPaths(directories)

    def _get_shortcut_roots(self) -> list[Path]:
        roots: list[Path] = []
        appdata = os.environ.get("APPDATA")
        programdata = os.environ.get("PROGRAMDATA")
        if appdata:
            roots.append(
                Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            )
        if programdata:
            roots.append(
                Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            )
        home = Path.home()
        roots.extend([home / "Desktop", home / "Documents", home / "Downloads"])
        return [root for root in roots if root.exists()]

    def _sync_shortcuts(self) -> None:
        shortcut_paths = self._collect_shortcut_paths()
        normalized_shortcuts = {
            os.path.normcase(os.path.abspath(path)): path for path in shortcut_paths
        }
        manual_paths = {
            os.path.normcase(os.path.abspath(app["path"]))
            for app in self.repository.apps
            if app.get("source") != "auto"
        }
        auto_apps = [
            app for app in list(self.repository.apps) if app.get("source") == "auto"
        ]
        auto_paths = {
            os.path.normcase(os.path.abspath(app["path"])): app for app in auto_apps
        }
        changed = False

        for app in auto_apps:
            normalized = os.path.normcase(os.path.abspath(app["path"]))
            if normalized not in normalized_shortcuts:
                self.repository.delete_app(app["path"])
                changed = True
                logger.info("Удален ярлык из списка: %s", app["path"])

        for normalized, path_value in normalized_shortcuts.items():
            if normalized in manual_paths:
                continue
            if normalized in auto_paths:
                auto_app = auto_paths[normalized]
                if not auto_app.get("icon_path"):
                    self.repository.update_icon(auto_app["path"], auto_app["path"])
                    changed = True
                continue
            new_app = {
                "name": Path(path_value).stem,
                "path": path_value,
                "icon_path": path_value,
                "type": "lnk",
                "group": DEFAULT_GROUP,
                "usage_count": 0,
                "source": "auto",
            }
            self.repository.add_app(new_app)
            changed = True
            logger.info("Добавлен ярлык из системы: %s", path_value)

        if changed:
            self.schedule_save()
            self.refresh_view()

    def _collect_shortcut_paths(self) -> list[str]:
        shortcuts: list[str] = []
        for root in self.shortcut_roots:
            if not root.exists():
                continue
            for dirpath, _, filenames in os.walk(root):
                for filename in filenames:
                    if filename.lower().endswith(".lnk"):
                        shortcuts.append(str(Path(dirpath) / filename))
        return shortcuts

    def _on_icon_extracted(
        self, path: str, icon_path: str, worker: IconExtractionWorker | None = None
    ):
        if worker and worker in self._icon_tasks:
            self._icon_tasks.remove(worker)
        if icon_path and self.repository.update_icon(path, icon_path):
            self.schedule_save()
            self.refresh_view()

    def _cleanup_icon_cache(self, icon_path: str | None) -> None:
        if not icon_path:
            return
        try:
            icon_file = Path(icon_path).resolve()
            icons_dir = Path("launcher_icons").resolve()
        except Exception:
            return
        if icon_file.exists() and icons_dir in icon_file.parents:
            try:
                icon_file.unlink()
            except OSError as err:  # pragma: no cover - filesystem dependent
                logger.warning("Не удалось удалить иконку %s: %s", icon_file, err)

    def setup_tabs(self):
        self.tabs.clear()
        for group in self.groups:
            self.tabs.addTab(QWidget(), group)
        self.tabs.addTab(QWidget(), "+")
        self._sync_view_toggle()
        if self.view_mode == "list":
            self.view_stack.setCurrentWidget(self.list_container)
        else:
            self.view_stack.setCurrentWidget(self.grid_widget)

    def on_tab_clicked(self, index: int):
        if self.tabs.tabText(index) == "+":
            text, ok = QInputDialog.getText(self, "Новая группа", "Название группы:")
            if ok and text:
                self.groups.append(text)
                self.setup_tabs()
                self.tabs.setCurrentIndex(self.tabs.count() - 2)
                self.schedule_save()
        self.refresh_view()

    def show_tab_context_menu(self, pos):
        tab_bar = self.tab_bar
        index = tab_bar.tabAt(pos)
        if index < 0 or tab_bar.tabText(index) == "+":
            return
        group = tab_bar.tabText(index)
        if group == DEFAULT_GROUP:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("🗑️ Удалить")
        if menu.exec(tab_bar.mapToGlobal(pos)) == delete_action:
            self.delete_group(group)

    def delete_group(self, group: str):
        if group == DEFAULT_GROUP or group not in self.groups:
            return
        for app in list(self.repository.apps):
            if app.get("group", DEFAULT_GROUP) == group:
                updated = dict(app)
                updated["group"] = DEFAULT_GROUP
                self.repository.update_app(app["path"], updated)
        self.groups = [name for name in self.groups if name != group]
        self.setup_tabs()
        if self.current_group == group:
            self.tabs.setCurrentIndex(self.groups.index(DEFAULT_GROUP))
        self._last_render_state = None
        self.schedule_save()
        self.refresh_view()

    def set_view_mode(self, mode: str):
        if mode not in {"grid", "list"} or self.view_mode == mode:
            self._sync_view_toggle()
            return
        self.view_mode = mode
        self._last_render_state = None
        self.schedule_save()
        self.refresh_view()

    def toggle_view_mode(self):
        target_mode = "list" if self.view_mode == "grid" else "grid"
        self.set_view_mode(target_mode)

    def _sync_view_toggle(self):
        is_grid = self.view_mode == "grid"
        if is_grid:
            self.view_toggle.setText("☰")
            self.view_toggle.setToolTip("Список")
        else:
            self.view_toggle.setText("⧉")
            self.view_toggle.setToolTip("Сетка")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # FlowLayout automatically handles resizing

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
    apply_design_system(app)

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
