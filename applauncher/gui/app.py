"""Main application window."""
import os
import logging
from pathlib import Path

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
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QPixmap,
    QKeySequence,
    QShortcut,
    QCursor,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .dialogs import AddAppDialog, SettingsDialog
from .icon_service import IconService
from .layouts import FlowLayout
from .styles import TOKENS, apply_design_system, apply_shadow
from .widgets import (
    AppButton,
    AppListItem,
    ClipboardHistoryWidget,
    NotesWidget,
    TitleBar,
    Toast,
    UniversalSearchWidget,
)
from ..repository import DEFAULT_GROUP
from ..config import resolve_app_icon_path
from ..services.clipboard_service import ClipboardService
from ..services.file_transfer import copy_item
from ..services.hotkey_service import HotkeyService
from ..services.launch_service import LaunchService
from ..services.launcher_service import LauncherService
from ..services.search_service import SearchService
from ..services.validation import extract_shortcut_data, validate_app_data

logger = logging.getLogger(__name__)


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
        self._app_icon = self._resolve_app_icon()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("mainWindow")
        self.setMinimumSize(*TOKENS.sizes.window_min)
        self.resize(*TOKENS.sizes.window_min)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        self._tile_size = TOKENS.sizes.grid_button
        self._grid_columns = 0

        self.service = LauncherService()
        self.repository = self.service.repository
        self._last_render_state: tuple[str, str, str, str, int] | None = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._persist_config)
        self.launch_service = LaunchService()
        self.hotkey_service = HotkeyService(self)
        self.clipboard_service = ClipboardService(self)
        self.search_service = SearchService(self.repository)
        self.icon_service = IconService(self.repository)
        self.icon_service.iconUpdated.connect(self._on_icon_updated)
        self.universal_search = UniversalSearchWidget(self.search_service, self)
        self.universal_search.resultActivated.connect(self._launch_search_result)
        self.hotkey_service.hotkey_activated.connect(self._on_hotkey_activated)
        self.settings_dialog: SettingsDialog | None = None
        self.tray_icon: QSystemTrayIcon | None = None
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self._shown_via_hotkey = False
        self._tile_launch_should_hide = False
        if self.tray_available:
            self.create_tray_icon()
        else:
            logger.warning("Системный трей недоступен; окно будет закрываться напрямую.")

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

        settings_bar = QWidget()
        settings_layout = QHBoxLayout()
        settings_layout.setContentsMargins(
            TOKENS.layout.content_margins[0],
            TOKENS.spacing.xs,
            TOKENS.layout.content_margins[2],
            TOKENS.spacing.xs,
        )
        settings_layout.setSpacing(TOKENS.spacing.sm)
        settings_bar.setLayout(settings_layout)

        settings_button = QPushButton("⚙️ Настройки")
        settings_button.setProperty("variant", "secondary")
        settings_button.clicked.connect(self.show_settings)
        settings_layout.addStretch()
        settings_layout.addWidget(settings_button)
        main_layout.addWidget(settings_bar)

        section_container = QWidget()
        section_layout = QVBoxLayout()
        section_layout.setContentsMargins(*TOKENS.layout.content_margins)
        section_layout.setSpacing(TOKENS.layout.content_spacing)
        section_container.setLayout(section_layout)

        self.section_tabs = QTabBar()
        self.section_tabs.addTab("Приложения")
        self.section_tabs.addTab("Ссылки")
        self.section_tabs.addTab("Папки")
        self.section_tabs.addTab("Заметки")
        self.section_tabs.addTab("Clipboard")
        self.section_tabs.setMovable(False)
        self.section_tabs.setExpanding(False)
        self.section_tabs.currentChanged.connect(self.on_section_changed)
        section_layout.addWidget(self.section_tabs)

        main_layout.addWidget(section_container)

        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)

        launcher_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(*TOKENS.layout.content_margins)
        content_layout.setSpacing(TOKENS.layout.content_spacing)
        launcher_widget.setLayout(content_layout)

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
        self.tab_bar.setObjectName("groupTabs")
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

        self.add_btn = QPushButton("Добавить приложение")
        self.add_btn.setProperty("variant", "accent")
        self.add_btn.clicked.connect(self.add_item)
        apply_shadow(self.add_btn, TOKENS.shadows.raised)

        self.clear_btn = QPushButton("Удалить все")
        self.clear_btn.setProperty("variant", "danger")
        self.clear_btn.clicked.connect(self.clear_all_items)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
            TOKENS.spacing.none,
        )
        actions_layout.setSpacing(TOKENS.layout.content_spacing)
        actions_layout.addWidget(self.add_btn)
        actions_layout.addWidget(self.clear_btn)
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
        self.view_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view_stack.addWidget(self.grid_widget)
        self.view_stack.addWidget(self.list_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setWidget(self.view_stack)

        content_layout.addWidget(self.scroll_area)

        self.content_stack.addWidget(launcher_widget)
        self.notes_widget = NotesWidget(self.service)
        self.notes_widget.notesChanged.connect(self.schedule_save)
        self.content_stack.addWidget(self.notes_widget)
        self.clipboard_widget = ClipboardHistoryWidget(self.clipboard_service)
        self.content_stack.addWidget(self.clipboard_widget)

        self.size_grip = QSizeGrip(container)
        self.size_grip.setObjectName("sizeGrip")
        main_layout.addWidget(self.size_grip, alignment=Qt.AlignBottom | Qt.AlignRight)

        self.load_state()
        self.setWindowOpacity(self.service.window_opacity)
        self.setup_shortcuts()
        self.refresh_view()

    def create_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self)
        if self._app_icon is not None:
            self.tray_icon.setIcon(self._app_icon)
        else:
            pixmap = QPixmap(TOKENS.sizes.tray_icon, TOKENS.sizes.tray_icon)
            pixmap.fill(QColor(TOKENS.colors.accent))
            icon = QIcon(pixmap)
            self.tray_icon.setIcon(icon)

        tray_menu = QMenu()

        show_action = tray_menu.addAction("🚀 Показать")
        show_action.triggered.connect(self._show_from_tray)

        settings_action = tray_menu.addAction("⚙️ Настройки")
        settings_action.triggered.connect(self.show_settings)

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
                self._show_from_tray()

    def _show_from_tray(self) -> None:
        self._shown_via_hotkey = False
        self.show()
        self.raise_()
        self.activateWindow()

    def _minimize_to_tray(self, show_message: bool = False) -> None:
        if not self.tray_available or not self.tray_icon:
            return
        self.hide()
        self._shown_via_hotkey = False
        if show_message:
            self.tray_icon.showMessage(
                "Лаунчер",
                "Приложение свернуто в трей. Кликните на иконку для возврата.",
                QSystemTrayIcon.Information,
                2000,
            )

    def show_settings(self):
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(
                self.service.global_hotkey,
                self.service.window_opacity,
                self._tile_size,
                self,
            )
            self.settings_dialog.hotkey_widget.hotkeyChanged.connect(self.update_hotkey)
            self.settings_dialog.opacityChanged.connect(self.update_opacity)
            self.settings_dialog.tileSizeChanged.connect(self.update_tile_size)
        else:
            self.settings_dialog.hotkey_widget.set_hotkey(self.service.global_hotkey)
            self.settings_dialog.set_opacity(self.service.window_opacity)
            self.settings_dialog.set_tile_size(self._tile_size)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def closeEvent(self, event):
        if self.tray_available and self.tray_icon:
            event.ignore()
            self._minimize_to_tray(show_message=True)
            return
        response = QMessageBox.question(
            self,
            "Закрыть приложение",
            "Системный трей недоступен. Закрыть лаунчер?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        added = False
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            suffix = Path(file_path).suffix.lower()
            if os.path.isdir(file_path):
                if not self.is_folders_section:
                    logger.warning("Игнорирована папка при перетаскивании вне вкладки папок: %s", file_path)
                    continue
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
                self.service.add_app(app_data)
                added = True
                logger.info("Добавлена папка из перетаскивания: %s", file_path)
                continue

            if self.is_folders_section:
                logger.warning("Игнорирован файл при перетаскивании во вкладке папок: %s", file_path)
                continue

            if suffix in {".url", ".lnk"} and os.path.exists(file_path):
                shortcut_data = extract_shortcut_data(file_path)
                if shortcut_data:
                    name = Path(file_path).stem
                    app_data = {
                        "name": name,
                        "path": shortcut_data["path"],
                        "icon_path": shortcut_data.get("icon_path", ""),
                        "type": shortcut_data.get("type", "exe"),
                        "args": shortcut_data.get("args", []),
                        "group": self.current_group,
                        "usage_count": 0,
                        "source": "manual",
                    }
                    created = self.service.add_app(app_data)
                    self.icon_service.start_extraction(created)
                    added = True
                    logger.info(
                        "Добавлен ярлык из перетаскивания: %s -> %s",
                        file_path,
                        shortcut_data["path"],
                    )
                else:
                    logger.warning("Не удалось прочитать ярлык: %s", file_path)
                continue

            if suffix in {".exe", ".bat", ".cmd", ".py"} and os.path.exists(file_path):
                name = Path(file_path).stem
                app_data = {
                    "name": name,
                    "path": file_path,
                    "icon_path": "",
                    "type": "exe",
                    "group": self.current_group,
                    "usage_count": 0,
                    "source": "manual",
                }
                created = self.service.add_app(app_data)
                self.icon_service.start_extraction(created)
                added = True
                logger.info("Добавлено приложение из перетаскивания: %s", file_path)
            else:
                logger.warning("Игнорирован файл при перетаскивании: %s", file_path)
        if added:
            self.schedule_save()
            self.refresh_view()

    def add_item(self):
        if self.is_links_section:
            self.add_link()
        elif self.is_folders_section:
            self.add_folder()
        else:
            self.add_app()

    def clear_all_items(self):
        if self.is_links_section:
            self.clear_all_links()
        elif self.is_folders_section:
            self.clear_all_folders()
        else:
            self.clear_all_apps()

    def add_app(self):
        dialog = AddAppDialog(self, groups=self.groups)
        if dialog.exec():
            data, error = validate_app_data(dialog.get_data())
            if error:
                QMessageBox.warning(self, "Ошибка", error)
                return
            if not data:
                return
            data["custom_icon"] = bool(data.get("icon_path"))
            if data.get("group") not in self.groups:
                self.groups.append(data.get("group", DEFAULT_GROUP))
                self.setup_tabs()
            created = self.service.add_app(data)
            self.icon_service.start_extraction(created)
            self.schedule_save()
            self.refresh_view()
            logger.info("Добавлен элемент: %s", data["name"])

    def add_link(self):
        dialog = AddAppDialog(self, groups=self.groups, default_type="url")
        if dialog.exec():
            data, error = validate_app_data(dialog.get_data())
            if error:
                QMessageBox.warning(self, "Ошибка", error)
                return
            if not data:
                return
            data["custom_icon"] = bool(data.get("icon_path"))
            if data.get("group") not in self.groups:
                self.groups.append(data.get("group", DEFAULT_GROUP))
                self.setup_tabs()
            created = self.service.add_app(data)
            self.icon_service.start_extraction(created)
            self.schedule_save()
            self.refresh_view()
            logger.info("Добавлена ссылка: %s", data["name"])

    def add_folder(self):
        dialog = AddAppDialog(self, groups=self.groups, default_type="folder")
        if dialog.exec():
            data, error = validate_app_data(dialog.get_data())
            if error:
                QMessageBox.warning(self, "Ошибка", error)
                return
            if not data:
                return
            data["custom_icon"] = bool(data.get("icon_path"))
            if data.get("group") not in self.groups:
                self.groups.append(data.get("group", DEFAULT_GROUP))
                self.setup_tabs()
            created = self.service.add_app(data)
            if data.get("icon_path"):
                self.icon_service.start_extraction(created)
            self.schedule_save()
            self.refresh_view()
            logger.info("Добавлена папка: %s", data["name"])

    def edit_app(self, app_data: dict):
        for app in self.repository.apps:
            if app["path"] == app_data["path"]:
                dialog = AddAppDialog(self, edit_mode=True, app_data=app, groups=self.groups)
                if dialog.exec():
                    updated, error = validate_app_data(dialog.get_data())
                    if error:
                        QMessageBox.warning(self, "Ошибка", error)
                        return
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
                    stored = self.service.update_app(app["path"], updated)
                    new_icon = (stored or updated).get("icon_path")
                    if previous_icon and previous_icon != new_icon:
                        self.icon_service.cleanup_icon_cache(previous_icon)
                    self.icon_service.start_extraction(stored or updated)
                    self.schedule_save()
                    self.refresh_view()
                    logger.info("Изменен элемент: %s", updated["name"])
                break

    def delete_app(self, app_data: dict):
        if self.current_group != DEFAULT_GROUP:
            self.remove_app_from_group(app_data, self.current_group)
            return
        if self.service.delete_app(app_data["path"]):
            self.icon_service.cleanup_icon_cache(app_data.get("icon_path"))
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
            self.icon_service.cleanup_icon_cache(app.get("icon_path"))
        self.service.clear_apps()
        self.schedule_save()
        self.refresh_view()
        logger.info("Удалены все приложения")

    def clear_all_links(self):
        links = [app for app in self.repository.apps if app.get("type") == "url"]
        if not links:
            QMessageBox.information(self, "Удалить все", "Список ссылок уже пуст.")
            return
        confirm = QMessageBox.question(
            self,
            "Удалить все",
            "Удалить все ссылки из лаунчера?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        for app in links:
            self.icon_service.cleanup_icon_cache(app.get("icon_path"))
        self.service.clear_links()
        self.schedule_save()
        self.refresh_view()
        logger.info("Удалены все ссылки")

    def clear_all_folders(self):
        folders = [app for app in self.repository.apps if app.get("type") == "folder"]
        if not folders:
            QMessageBox.information(self, "Удалить все", "Список папок уже пуст.")
            return
        confirm = QMessageBox.question(
            self,
            "Удалить все",
            "Удалить все папки из лаунчера?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        for app in folders:
            self.icon_service.cleanup_icon_cache(app.get("icon_path"))
        self.service.clear_folders()
        self.schedule_save()
        self.refresh_view()
        logger.info("Удалены все папки")

    def toggle_favorite(self, app_data: dict):
        if not self.service.toggle_favorite(app_data["path"]):
            return
        self.schedule_save()
        self.refresh_view()

    def move_app_to_group(self, app_data: dict, group: str):
        if not self.service.move_app_to_group(app_data["path"], group):
            return
        self.schedule_save()
        self.refresh_view()

    def remove_app_from_group(self, app_data: dict, group: str):
        if not self.service.remove_app_from_group(app_data["path"], group):
            return
        self.schedule_save()
        self.refresh_view()

    def move_app_by_path(self, app_path: str, group: str):
        if self.service.move_app_to_group(app_path, group):
            self.schedule_save()
            self.refresh_view()

    def launch_item_from_tile(self, app_data: dict) -> None:
        should_hide = (
            self._shown_via_hotkey
            and self.tray_available
            and self.tray_icon is not None
        )
        self._tile_launch_should_hide = should_hide
        try:
            self.launch_app(app_data)
        finally:
            self._tile_launch_should_hide = False

    def launch_app(self, app_data: dict):
        success, error = self.launch_service.launch(app_data)
        if not success:
            if error:
                QMessageBox.warning(self, "Ошибка", error)
            return
        updated = self.service.increment_usage(app_data["path"]) or app_data
        app_data.update(updated)
        self.schedule_save()
        self.refresh_view()
        if app_data.get("type") == "folder":
            self._minimize_to_tray()
        elif self._tile_launch_should_hide:
            self._minimize_to_tray()

    def copy_dropped_to_folder(self, folder_data: dict, items: list, warnings: list) -> None:
        """Copy files/folders dropped onto a folder tile into that folder."""
        dest_dir = folder_data.get("path", "")
        if items and not os.path.isdir(dest_dir):
            QMessageBox.warning(self, "Ошибка", f"Папка не найдена:\n{dest_dir}")
            return

        copied: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []
        for item in items:
            status, name, message = copy_item(
                item,
                dest_dir,
                lambda conflict_name: self._resolve_copy_conflict(
                    conflict_name, folder_data.get("name", "")
                ),
            )
            if status == "copied":
                copied.append(name)
            elif status == "skipped":
                skipped.append(name)
                if message:
                    warnings = [*warnings, f"{name}: {message}"]
            else:
                errors.append(f"{name}: {message}" if message else name)

        if copied:
            if len(copied) == 1:
                Toast.show_message(self, f"✓ Скопировано: {copied[0]}")
            else:
                Toast.show_message(self, f"✓ Скопировано файлов: {len(copied)}")
        elif skipped and not errors and not warnings:
            Toast.show_message(self, "Копирование пропущено")

        if warnings:
            QMessageBox.information(self, "Копирование", "\n".join(warnings))
        if errors:
            QMessageBox.warning(
                self,
                "Ошибка копирования",
                "Не удалось скопировать:\n" + "\n".join(errors),
            )

    def _resolve_copy_conflict(self, name: str, folder_name: str) -> str:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Файл уже существует")
        dialog.setIcon(QMessageBox.Question)
        dialog.setText(f"В папке «{folder_name}» уже есть «{name}».")
        dialog.setInformativeText("Что сделать с этим файлом?")
        replace_btn = dialog.addButton("Заменить", QMessageBox.DestructiveRole)
        rename_btn = dialog.addButton("Сохранить копию", QMessageBox.AcceptRole)
        dialog.addButton("Пропустить", QMessageBox.RejectRole)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == replace_btn:
            return "overwrite"
        if clicked == rename_btn:
            return "rename"
        return "skip"

    def open_location(self, app_data: dict):
        success, error = self.launch_service.open_location(app_data)
        if not success and error:
            if error == "Для веб-ссылок нет локальной папки":
                QMessageBox.information(self, "Информация", error)
            else:
                QMessageBox.warning(self, "Ошибка", error)

    def copy_link(self, app_data: dict):
        link_value = app_data.get("raw_path") or app_data.get("path") or ""
        if not link_value:
            QMessageBox.information(self, "Информация", "Ссылка не указана.")
            return
        QApplication.clipboard().setText(link_value)

    def _filtered_items(self, query: str, group: str) -> list[dict]:
        if self.is_links_section:
            return [
                app
                for app in self.service.filtered_apps(query, group)
                if app.get("type") == "url"
            ]
        if self.is_folders_section:
            return [
                app
                for app in self.service.filtered_apps(query, group)
                if app.get("type") == "folder"
            ]
        return [
            app
            for app in self.service.filtered_apps(query, group)
            if app.get("type") not in {"url", "folder"}
        ]

    def refresh_view(self):
        if self.is_clipboard_section or self.is_notes_section:
            return
        current_group = self.current_group
        query = self.search_input.text()
        render_state = (self.current_section, self.view_mode, current_group, query, self.service.version)
        if self._last_render_state == render_state:
            return
        self._last_render_state = render_state

        filtered = self._filtered_items(query, current_group)
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

        self._update_grid_layout()
        current_group = self.current_group
        for app in apps:
            btn = AppButton(
                app,
                self.grid_widget,
                tile_size=self._tile_size,
                icon_size=self._grid_icon_size(),
                available_groups=self.groups,
                current_group=current_group,
                default_group=DEFAULT_GROUP,
            )
            btn.activated.connect(self.launch_item_from_tile)
            btn.editRequested.connect(self.edit_app)
            btn.deleteRequested.connect(self.delete_app)
            btn.openLocationRequested.connect(self.open_location)
            btn.copyLinkRequested.connect(self.copy_link)
            btn.favoriteToggled.connect(self.toggle_favorite)
            btn.moveRequested.connect(self.move_app_to_group)
            btn.copyDropRequested.connect(self.copy_dropped_to_folder)
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
                default_group=DEFAULT_GROUP,
            )
            item.activated.connect(self.launch_item_from_tile)
            item.editRequested.connect(self.edit_app)
            item.deleteRequested.connect(self.delete_app)
            item.openLocationRequested.connect(self.open_location)
            item.copyLinkRequested.connect(self.copy_link)
            item.favoriteToggled.connect(self.toggle_favorite)
            item.moveRequested.connect(self.move_app_to_group)
            item.copyDropRequested.connect(self.copy_dropped_to_folder)
            self.list_layout.addWidget(item)
        self.list_layout.addStretch()

    def launch_top_result(self):
        filtered = self._filtered_items(self.search_input.text(), self.current_group)
        if not filtered:
            return
        self.launch_app(filtered[0])

    def load_state(self):
        error = self.service.load_state()
        if error:
            QMessageBox.warning(self, "Ошибка конфигурации", error)
        self._tile_size = tuple(self.service.tile_size)
        self._grid_columns = 0
        self.setWindowOpacity(self.service.window_opacity)
        self.notes_widget.reload_notes()
        self.setup_tabs()
        self.sync_section_controls()
        self._last_render_state = None

    def update_opacity(self, value: float) -> None:
        self.service.window_opacity = value
        self.setWindowOpacity(value)
        self.schedule_save()

    def update_tile_size(self, tile_size: tuple[int, int]) -> None:
        if tuple(tile_size) == tuple(self._tile_size):
            return
        self._tile_size = tuple(tile_size)
        self.service.tile_size = tuple(tile_size)
        self._grid_columns = 0
        if self.view_mode == "grid":
            self._update_grid_layout()
            self._refresh_grid_tile_sizes()
            self.grid_layout.invalidate()
        self.schedule_save()

    def schedule_save(self):
        self._save_timer.start()

    def _persist_config(self):
        error = self.service.persist_config()
        if error:
            QMessageBox.warning(self, "Ошибка", error)

    @property
    def current_group(self) -> str:
        if self.is_clipboard_section or self.is_notes_section:
            return DEFAULT_GROUP
        return self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.count() else DEFAULT_GROUP

    @property
    def groups(self) -> list[str]:
        return self.service.groups

    @groups.setter
    def groups(self, value: list[str]) -> None:
        self.service.groups = value

    @property
    def current_section(self) -> str:
        if self.is_links_section:
            return "links"
        if self.is_folders_section:
            return "folders"
        return "apps"

    @property
    def view_mode(self) -> str:
        return self.service.view_mode

    @view_mode.setter
    def view_mode(self, value: str) -> None:
        self.service.view_mode = value

    def _on_icon_updated(self, _path: str, _icon_path: str) -> None:
        self.schedule_save()
        self.refresh_view()

    def on_section_changed(self, _index: int):
        if self.is_notes_section:
            self.content_stack.setCurrentWidget(self.notes_widget)
            return
        if self.is_clipboard_section:
            self.content_stack.setCurrentWidget(self.clipboard_widget)
            return
        self.content_stack.setCurrentIndex(0)
        self.setup_tabs()
        self.sync_section_controls()
        self._last_render_state = None
        self.refresh_view()

    def sync_section_controls(self):
        if self.is_links_section:
            self.search_input.setPlaceholderText("Поиск ссылок...")
            self.add_btn.setText("Добавить ссылку")
            self.clear_btn.setText("Удалить все ссылки")
        elif self.is_folders_section:
            self.search_input.setPlaceholderText("Поиск папок...")
            self.add_btn.setText("Добавить папку")
            self.clear_btn.setText("Удалить все папки")
        else:
            self.search_input.setPlaceholderText("Поиск приложений...")
            self.add_btn.setText("Добавить приложение")
            self.clear_btn.setText("Удалить все")
        self._sync_view_toggle()

    def setup_tabs(self):
        if self.is_clipboard_section or self.is_notes_section:
            return
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
        self.service.delete_group(group)
        self.setup_tabs()
        if self.current_group == group and self.groups:
            self.tabs.setCurrentIndex(0)
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
        if self.view_mode == "grid":
            if self._update_grid_layout():
                self._refresh_grid_tile_sizes()
            self.grid_layout.invalidate()

    def setup_shortcuts(self):
        shortcut = QShortcut(QKeySequence(self.service.global_hotkey), self)
        shortcut.setContext(Qt.ApplicationShortcut)
        shortcut.activated.connect(self._on_hotkey_activated)
        self.toggle_shortcut = shortcut
        self._register_hotkey()

    def _register_hotkey(self):
        if not self.hotkey_service.register_hotkey(self.service.global_hotkey):
            logger.warning("Глобальный хоткей не зарегистрирован")

    def update_hotkey(self, hotkey: str) -> None:
        if not hotkey:
            return
        self.service.global_hotkey = hotkey
        if self.toggle_shortcut:
            self.toggle_shortcut.setKey(QKeySequence(hotkey))
        self._register_hotkey()
        self.schedule_save()

    def _on_hotkey_activated(self):
        self._shown_via_hotkey = True
        self._show_on_active_screen()

    def _launch_search_result(self, result):
        success, error = self.launch_service.launch(result.payload)
        if not success:
            if error:
                QMessageBox.warning(self, "Ошибка", error)
            return
        updated = self.service.increment_usage(result.payload["path"]) or result.payload
        result.payload.update(updated)
        self.universal_search.hide()
        self.schedule_save()
        self.refresh_view()

    @property
    def is_links_section(self) -> bool:
        return self.section_tabs.currentIndex() == 1

    @property
    def is_folders_section(self) -> bool:
        return self.section_tabs.currentIndex() == 2

    @property
    def is_notes_section(self) -> bool:
        return self.section_tabs.currentIndex() == 3

    @property
    def is_clipboard_section(self) -> bool:
        return self.section_tabs.currentIndex() == 4

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self._show_on_active_screen()

    def _show_on_active_screen(self) -> None:
        screen = QApplication.screenAt(QCursor.pos())
        if screen is not None:
            available = screen.availableGeometry()
            new_x = available.x() + max(0, (available.width() - self.width()) // 2)
            new_y = available.y() + max(0, (available.height() - self.height()) // 2)
            self.move(new_x, new_y)
        self.show()
        self.raise_()
        self.activateWindow()

    def _update_grid_layout(self) -> bool:
        available_width = max(1, self.grid_widget.width())
        spacing = self.grid_layout.horizontalSpacing()
        margin = self.grid_layout.contentsMargins().left()
        usable_width = max(1, available_width - (margin * 2))
        tile_width = max(1, int(self._tile_size[0]))
        columns = max(1, int((usable_width + spacing) / (tile_width + spacing)))
        if columns == self._grid_columns:
            return False
        self._grid_columns = columns
        return True

    def _refresh_grid_tile_sizes(self) -> None:
        icon_size = self._grid_icon_size()
        for index in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(index)
            widget = item.widget() if item else None
            if isinstance(widget, AppButton):
                widget.set_tile_size(self._tile_size, icon_size)

    def _grid_icon_size(self) -> int:
        return max(24, int(self._tile_size[0] * 0.4))

    def _resolve_app_icon(self) -> QIcon | None:
        icon_path = resolve_app_icon_path()
        if icon_path and os.path.exists(icon_path):
            icon = QIcon(icon_path)
            if not icon.isNull():
                self.setWindowIcon(icon)
                return icon
        return None


def run_app():
    app = QApplication([])
    app_icon_path = resolve_app_icon_path()
    if app_icon_path and os.path.exists(app_icon_path):
        app_icon = QIcon(app_icon_path)
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)
    app.setStyle("Fusion")
    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    app.setQuitOnLastWindowClosed(not tray_available)
    apply_design_system(app)

    server_name = "applauncher_single_instance"
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(200):
        logger.info("Уже запущен экземпляр лаунчера, выход")
        return 0

    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    if server.listen(server_name):
        app._single_instance_server = server  # keep reference
    else:
        logger.warning(
            "Не удалось запустить single-instance сервер: %s",
            server.errorString(),
        )
        QMessageBox.warning(
            None,
            "AppLauncher",
            "Не удалось запустить single-instance сервер. "
            "Механизм единственного экземпляра отключен.",
        )

    window = AppLauncher()
    window.show()
    return app.exec()
