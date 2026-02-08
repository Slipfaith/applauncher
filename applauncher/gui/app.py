"""Main application window."""
import os
import logging
import ctypes
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
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QEvent, QTimer, Qt, Signal, QPoint
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

from .dialogs import AddAppDialog, AddMacroDialog, SettingsDialog
from .icon_service import IconService
from .layouts import FlowLayout
from .styles import TOKENS, apply_design_system, apply_shadow
from .widgets import AppButton, AppListItem, ClipboardHistoryWidget, TitleBar, UniversalSearchWidget
from ..repository import DEFAULT_GROUP, DEFAULT_MACRO_GROUPS
from ..services.clipboard_service import ClipboardService
from ..services.hotkey_service import HotkeyService
from ..services.launch_service import LaunchService
from ..services.launcher_service import LauncherService
from ..services.search_service import SearchService
from ..services.validation import (
    extract_shortcut_data,
    validate_app_data,
    validate_macro_data,
)

logger = logging.getLogger(__name__)

WM_NCHITTEST = 0x0084
WM_NCLBUTTONDOWN = 0x00A1
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
WM_NCCALCSIZE = 0x0083
WS_THICKFRAME = 0x00040000
GWL_STYLE = -16


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

        self.service = LauncherService()
        self.repository = self.service.repository
        self.macro_repository = self.service.macro_repository
        self._last_render_state: tuple[str, str, str, str, int] | None = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._persist_config)
        self.launch_service = LaunchService()
        self.hotkey_service = HotkeyService(self)
        self.clipboard_service = ClipboardService(self)
        self.search_service = SearchService(self.repository, self.macro_repository)
        self.icon_service = IconService(self.repository)
        self.icon_service.iconUpdated.connect(self._on_icon_updated)
        self.universal_search = UniversalSearchWidget(self.search_service, self)
        self.universal_search.resultActivated.connect(self._launch_search_result)
        self.hotkey_service.hotkey_activated.connect(self._on_hotkey_activated)
        self.settings_dialog: SettingsDialog | None = None
        self.tray_icon: QSystemTrayIcon | None = None
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        if self.tray_available:
            self.create_tray_icon()
        else:
            logger.warning("Системный трей недоступен; окно будет закрываться напрямую.")

        container = QWidget()
        container.setObjectName("centralContainer")
        self.setCentralWidget(container)
        self._resize_border = 8
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.installEventFilter(self)

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
        self.section_tabs.addTab("Макросы")
        self.section_tabs.addTab("Папки")
        self.section_tabs.addTab("Ссылки")
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
        self.clipboard_widget = ClipboardHistoryWidget(self.clipboard_service)
        self.content_stack.addWidget(self.clipboard_widget)

        self.load_state()
        self.setWindowOpacity(self.service.window_opacity)
        self.setup_shortcuts()
        self.refresh_view()
        self._setup_native_resize()

    def _setup_native_resize(self):
        if os.name != "nt":
            return
        try:
            hwnd = int(self.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            style |= WS_THICKFRAME
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        except Exception:
            logger.warning("Не удалось установить WS_THICKFRAME для native resize")

    def create_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self)

        pixmap = QPixmap(TOKENS.sizes.tray_icon, TOKENS.sizes.tray_icon)
        pixmap.fill(QColor(TOKENS.colors.accent))
        icon = QIcon(pixmap)
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()

        show_action = tray_menu.addAction("🚀 Показать")
        show_action.triggered.connect(self.show)

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
                self.show()
                self.activateWindow()

    def show_settings(self):
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(
                self.service.global_hotkey,
                self.service.window_opacity,
                self,
            )
            self.settings_dialog.hotkey_widget.hotkeyChanged.connect(self.update_hotkey)
            self.settings_dialog.opacityChanged.connect(self.update_opacity)
        else:
            self.settings_dialog.hotkey_widget.set_hotkey(self.service.global_hotkey)
            self.settings_dialog.set_opacity(self.service.window_opacity)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def closeEvent(self, event):
        if self.tray_available and self.tray_icon:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "Лаунчер",
                "Приложение свернуто в трей. Кликните на иконку для возврата.",
                QSystemTrayIcon.Information,
                2000,
            )
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
            if os.name == "nt":
                file_path = os.path.normpath(file_path)
            suffix = Path(file_path).suffix.lower()

            if self.is_macro_section:
                if suffix in set(DEFAULT_MACRO_GROUPS) and os.path.exists(file_path):
                    name = Path(file_path).stem
                    macro_data = {
                        "name": name,
                        "path": file_path,
                        "description": "",
                        "group": suffix,
                    }
                    data, error = validate_macro_data(macro_data)
                    if error:
                        logger.warning("Не удалось добавить макрос: %s", error)
                        continue
                    created = self.service.add_macro(data)
                    added = True
                    logger.info("Добавлен макрос из перетаскивания: %s", created["path"])
                else:
                    logger.warning("Игнорирован файл при перетаскивании: %s", file_path)
                continue

            if self.is_folders_section:
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
                    self.service.add_app(app_data)
                    added = True
                    logger.info("Добавлена папка из перетаскивания: %s", file_path)
                else:
                    logger.warning("Игнорирован файл при перетаскивании: %s", file_path)
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
        if self.is_macro_section:
            self.add_macro()
        elif self.is_folders_section:
            self.add_folder()
        elif self.is_links_section:
            self.add_link()
        else:
            self.add_app()

    def clear_all_items(self):
        if self.is_macro_section:
            self.clear_all_macros()
        elif self.is_folders_section:
            self.clear_all_folders()
        elif self.is_links_section:
            self.clear_all_links()
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
                    path_changed = updated.get("path") != app.get("path")
                    updated["usage_count"] = app.get("usage_count", 0)
                    updated["source"] = app.get("source", "manual")
                    if updated.get("icon_path") != previous_icon:
                        updated["custom_icon"] = bool(updated.get("icon_path"))
                    else:
                        updated["custom_icon"] = previous_custom_icon
                    if path_changed and not updated.get("custom_icon", False):
                        # Reset auto icon when target path changes; new icon will be extracted.
                        updated["icon_path"] = ""
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

    def add_macro(self):
        dialog = AddMacroDialog(self, groups=self.groups)
        if dialog.exec():
            data, error = validate_macro_data(dialog.get_data())
            if error:
                QMessageBox.warning(self, "Ошибка", error)
                return
            if not data:
                return
            if data.get("group") not in self.groups:
                self.groups.append(data.get("group"))
                self.setup_tabs()
            self.service.add_macro(data)
            self.schedule_save()
            self.refresh_view()
            logger.info("Добавлен макрос: %s", data["name"])

    def edit_macro(self, macro_data: dict):
        for macro in self.macro_repository.apps:
            if macro["path"] == macro_data["path"]:
                dialog = AddMacroDialog(self, edit_mode=True, macro_data=macro, groups=self.groups)
                if dialog.exec():
                    updated, error = validate_macro_data(dialog.get_data())
                    if error:
                        QMessageBox.warning(self, "Ошибка", error)
                        return
                    if not updated:
                        return
                    updated["usage_count"] = macro.get("usage_count", 0)
                    updated["source"] = macro.get("source", "manual")
                    if updated.get("group") not in self.groups:
                        self.groups.append(updated.get("group"))
                        self.setup_tabs()
                    self.service.update_macro(macro["path"], updated)
                    self.schedule_save()
                    self.refresh_view()
                    logger.info("Изменен макрос: %s", updated["name"])
                break

    def delete_macro(self, macro_data: dict):
        if self.service.delete_macro(macro_data["path"]):
            logger.info("Удален макрос: %s", macro_data["name"])
            self.schedule_save()
            self.refresh_view()

    def clear_all_apps(self):
        apps = [
            app for app in self.repository.apps if app.get("type") not in {"url", "folder"}
        ]
        if not apps:
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
        for app in apps:
            self.icon_service.cleanup_icon_cache(app.get("icon_path"))
        self.service.clear_regular_apps()
        self.schedule_save()
        self.refresh_view()
        logger.info("Удалены все приложения")

    def clear_all_macros(self):
        if not self.macro_repository.apps:
            QMessageBox.information(self, "Удалить все", "Список макросов уже пуст.")
            return
        confirm = QMessageBox.question(
            self,
            "Удалить все",
            "Удалить все макросы из лаунчера?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.service.clear_macros()
        self.schedule_save()
        self.refresh_view()
        logger.info("Удалены все макросы")

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

    def toggle_macro_favorite(self, macro_data: dict):
        if not self.service.toggle_macro_favorite(macro_data["path"]):
            return
        self.schedule_save()
        self.refresh_view()

    def move_app_to_group(self, app_data: dict, group: str):
        if not self.service.move_app_to_group(app_data["path"], group):
            return
        self.schedule_save()
        self.refresh_view()

    def move_macro_to_group(self, macro_data: dict, group: str):
        if not self.service.move_macro_to_group(macro_data["path"], group):
            return
        self.schedule_save()
        self.refresh_view()

    def remove_app_from_group(self, app_data: dict, group: str):
        if not self.service.remove_app_from_group(app_data["path"], group):
            return
        self.schedule_save()
        self.refresh_view()

    def remove_macro_from_group(self, macro_data: dict, group: str):
        if not self.service.remove_macro_from_group(macro_data["path"], group):
            return
        self.schedule_save()
        self.refresh_view()

    def move_app_by_path(self, app_path: str, group: str):
        if self.is_macro_section:
            if self.service.move_macro_to_group(app_path, group):
                self.schedule_save()
                self.refresh_view()
            return
        if self.service.move_app_to_group(app_path, group):
            self.schedule_save()
            self.refresh_view()

    def launch_item(self, app_data: dict):
        if self.is_macro_section:
            self.launch_macro(app_data)
        else:
            self.launch_app(app_data)

    def launch_app(self, app_data: dict):
        success, error = self.launch_service.launch(app_data)
        if not success:
            if error:
                QMessageBox.warning(self, "Ошибка", error)
            return
        if self._should_collapse_after_app_launch(app_data):
            self._collapse_to_tray()
        updated = self.service.increment_usage(app_data["path"]) or app_data
        app_data.update(updated)
        self.schedule_save()
        self.refresh_view()

    def launch_macro(self, macro_data: dict):
        success, error = self.launch_service.launch(macro_data)
        if not success:
            if error:
                QMessageBox.warning(self, "Ошибка", error)
            return
        updated = self.service.increment_macro_usage(macro_data["path"]) or macro_data
        macro_data.update(updated)
        self.schedule_save()
        self.refresh_view()

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

    def refresh_view(self):
        if self.is_clipboard_section:
            return
        current_group = self.current_group
        query = self.search_input.text()
        version = self.service.macro_version if self.is_macro_section else self.service.version
        render_state = (self.current_section, self.view_mode, current_group, query, version)
        if self._last_render_state == render_state:
            return
        self._last_render_state = render_state

        if self.is_macro_section:
            filtered = self.service.filtered_macros(query, current_group)
        elif self.is_folders_section:
            filtered = [
                app
                for app in self.service.filtered_apps(query, current_group)
                if app.get("type") == "folder"
            ]
        elif self.is_links_section:
            filtered = [
                app
                for app in self.service.filtered_apps(query, current_group)
                if app.get("type") == "url"
            ]
        else:
            filtered = [
                app
                for app in self.service.filtered_apps(query, current_group)
                if app.get("type") not in {"url", "folder"}
            ]
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
                default_group=self.default_group,
                show_favorite=not self.is_macro_section,
            )
            btn.activated.connect(self.launch_item)
            btn.editRequested.connect(self.edit_item)
            btn.deleteRequested.connect(self.delete_item)
            btn.openLocationRequested.connect(self.open_location)
            btn.copyLinkRequested.connect(self.copy_link)
            if not self.is_macro_section:
                btn.favoriteToggled.connect(self.toggle_favorite)
            btn.moveRequested.connect(self.move_item_to_group)
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
                default_group=self.default_group,
                show_favorite=not self.is_macro_section,
            )
            item.activated.connect(self.launch_item)
            item.editRequested.connect(self.edit_item)
            item.deleteRequested.connect(self.delete_item)
            item.openLocationRequested.connect(self.open_location)
            item.copyLinkRequested.connect(self.copy_link)
            if not self.is_macro_section:
                item.favoriteToggled.connect(self.toggle_favorite)
            item.moveRequested.connect(self.move_item_to_group)
            self.list_layout.addWidget(item)
        self.list_layout.addStretch()

    def launch_top_result(self):
        current_group = self.current_group
        if self.is_macro_section:
            filtered = self.service.filtered_macros(self.search_input.text(), current_group)
        elif self.is_folders_section:
            filtered = [
                app
                for app in self.service.filtered_apps(self.search_input.text(), current_group)
                if app.get("type") == "folder"
            ]
        elif self.is_links_section:
            filtered = [
                app
                for app in self.service.filtered_apps(self.search_input.text(), current_group)
                if app.get("type") == "url"
            ]
        else:
            filtered = [
                app
                for app in self.service.filtered_apps(self.search_input.text(), current_group)
                if app.get("type") not in {"url", "folder"}
            ]
        if not filtered:
            return
        self.launch_item(filtered[0])

    def load_state(self):
        error = self.service.load_state()
        if error:
            QMessageBox.warning(self, "Ошибка конфигурации", error)
        self.setWindowOpacity(self.service.window_opacity)
        self.setup_tabs()
        self.sync_section_controls()
        self._last_render_state = None

    def update_opacity(self, value: float) -> None:
        self.service.window_opacity = value
        self.setWindowOpacity(value)
        self.schedule_save()

    def schedule_save(self):
        self._save_timer.start()

    def _persist_config(self):
        error = self.service.persist_config()
        if error:
            QMessageBox.warning(self, "Ошибка", error)

    @property
    def current_group(self) -> str:
        if self.is_clipboard_section:
            return DEFAULT_GROUP
        return self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.count() else DEFAULT_GROUP

    @property
    def groups(self) -> list[str]:
        if self.is_clipboard_section:
            return self.service.groups
        return self.service.macro_groups if self.is_macro_section else self.service.groups

    @groups.setter
    def groups(self, value: list[str]) -> None:
        if self.is_macro_section:
            self.service.macro_groups = value
        else:
            self.service.groups = value

    @property
    def current_section(self) -> str:
        if self.is_macro_section:
            return "macros"
        if self.is_folders_section:
            return "folders"
        if self.is_links_section:
            return "links"
        return "apps"

    @property
    def default_group(self) -> str | None:
        return DEFAULT_GROUP if not self.is_macro_section else None

    @property
    def view_mode(self) -> str:
        return self.service.macro_view_mode if self.is_macro_section else self.service.view_mode

    @view_mode.setter
    def view_mode(self, value: str) -> None:
        if self.is_macro_section:
            self.service.macro_view_mode = value
        else:
            self.service.view_mode = value

    def _on_icon_updated(self, _path: str, _icon_path: str) -> None:
        self.schedule_save()
        self.refresh_view()

    def on_section_changed(self, _index: int):
        if self.is_clipboard_section:
            self.content_stack.setCurrentWidget(self.clipboard_widget)
            return
        self.content_stack.setCurrentIndex(0)
        self.setup_tabs()
        self.sync_section_controls()
        self._last_render_state = None
        self.refresh_view()

    def sync_section_controls(self):
        if self.is_macro_section:
            self.search_input.setPlaceholderText("Поиск макросов...")
            self.add_btn.setText("Добавить макрос")
            self.clear_btn.setText("Удалить все макросы")
        elif self.is_folders_section:
            self.search_input.setPlaceholderText("Поиск папок...")
            self.add_btn.setText("Добавить папку")
            self.clear_btn.setText("Удалить все папки")
        elif self.is_links_section:
            self.search_input.setPlaceholderText("Поиск ссылок...")
            self.add_btn.setText("Добавить ссылку")
            self.clear_btn.setText("Удалить все ссылки")
        else:
            self.search_input.setPlaceholderText("Поиск приложений...")
            self.add_btn.setText("Добавить приложение")
            self.clear_btn.setText("Удалить все")
        self._sync_view_toggle()

    def setup_tabs(self):
        if self.is_clipboard_section:
            return
        self.tabs.clear()
        for group in self.groups:
            self.tabs.addTab(QWidget(), group)
        if not self.is_macro_section:
            self.tabs.addTab(QWidget(), "+")
        self._sync_view_toggle()
        if self.view_mode == "list":
            self.view_stack.setCurrentWidget(self.list_container)
        else:
            self.view_stack.setCurrentWidget(self.grid_widget)

    def on_tab_clicked(self, index: int):
        if self.is_macro_section:
            self.refresh_view()
            return
        if self.tabs.tabText(index) == "+":
            text, ok = QInputDialog.getText(self, "Новая группа", "Название группы:")
            target_index = 0
            if ok:
                group_name = text.strip()
                if not group_name:
                    QMessageBox.information(self, "Группа", "Название группы не может быть пустым.")
                elif group_name == "+":
                    QMessageBox.information(self, "Группа", "Имя '+' зарезервировано.")
                elif group_name in self.groups:
                    target_index = self.groups.index(group_name)
                else:
                    self.groups.append(group_name)
                    self.setup_tabs()
                    target_index = max(0, self.tabs.count() - 2)
                    self.schedule_save()
            self.tabs.setCurrentIndex(target_index)
            self.refresh_view()
            return
        self.refresh_view()

    def show_tab_context_menu(self, pos):
        tab_bar = self.tab_bar
        index = tab_bar.tabAt(pos)
        if index < 0 or tab_bar.tabText(index) == "+":
            return
        group = tab_bar.tabText(index)
        if self.default_group and group == self.default_group:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("🗑️ Удалить")
        if menu.exec(tab_bar.mapToGlobal(pos)) == delete_action:
            self.delete_group(group)

    def delete_group(self, group: str):
        if group not in self.groups:
            return
        if self.is_macro_section:
            self.service.delete_macro_group(group)
        else:
            if group == DEFAULT_GROUP:
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

    def _resize_edges_at(self, pos: QPoint) -> Qt.Edges:
        border = max(4, int(self._resize_border))
        x = pos.x()
        y = pos.y()
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return Qt.Edges()

        on_left = x <= border
        on_right = x >= w - border
        on_top = y <= border
        on_bottom = y >= h - border

        edges = Qt.Edges()
        if on_left:
            edges |= Qt.LeftEdge
        if on_right:
            edges |= Qt.RightEdge
        if on_top:
            edges |= Qt.TopEdge
        if on_bottom:
            edges |= Qt.BottomEdge
        return edges

    def _hit_test_resize(self, pos: QPoint) -> int | None:
        edges = self._resize_edges_at(pos)
        if (edges & Qt.TopEdge) and (edges & Qt.LeftEdge):
            return HTTOPLEFT
        if (edges & Qt.TopEdge) and (edges & Qt.RightEdge):
            return HTTOPRIGHT
        if (edges & Qt.BottomEdge) and (edges & Qt.LeftEdge):
            return HTBOTTOMLEFT
        if (edges & Qt.BottomEdge) and (edges & Qt.RightEdge):
            return HTBOTTOMRIGHT
        if edges & Qt.LeftEdge:
            return HTLEFT
        if edges & Qt.RightEdge:
            return HTRIGHT
        if edges & Qt.TopEdge:
            return HTTOP
        if edges & Qt.BottomEdge:
            return HTBOTTOM
        return None

    def _hit_test_resize_native(self, screen_x: int, screen_y: int) -> int | None:
        if os.name != "nt":
            return None
        rect = ctypes.wintypes.RECT()
        hwnd = int(self.winId())
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        handle = self.windowHandle()
        scale = float(handle.devicePixelRatio()) if handle is not None else 1.0
        border = max(4, int(round(self._resize_border * scale)))

        on_left = screen_x <= rect.left + border
        on_right = screen_x >= rect.right - border
        on_top = screen_y <= rect.top + border
        on_bottom = screen_y >= rect.bottom - border

        if on_top and on_left:
            return HTTOPLEFT
        if on_top and on_right:
            return HTTOPRIGHT
        if on_bottom and on_left:
            return HTBOTTOMLEFT
        if on_bottom and on_right:
            return HTBOTTOMRIGHT
        if on_left:
            return HTLEFT
        if on_right:
            return HTRIGHT
        if on_top:
            return HTTOP
        if on_bottom:
            return HTBOTTOM
        return None

    def _resize_cursor_for_edges(self, edges: Qt.Edges):
        if (edges & Qt.TopEdge) and (edges & Qt.LeftEdge):
            return Qt.SizeFDiagCursor
        if (edges & Qt.BottomEdge) and (edges & Qt.RightEdge):
            return Qt.SizeFDiagCursor
        if (edges & Qt.TopEdge) and (edges & Qt.RightEdge):
            return Qt.SizeBDiagCursor
        if (edges & Qt.BottomEdge) and (edges & Qt.LeftEdge):
            return Qt.SizeBDiagCursor
        if (edges & Qt.LeftEdge) or (edges & Qt.RightEdge):
            return Qt.SizeHorCursor
        if (edges & Qt.TopEdge) or (edges & Qt.BottomEdge):
            return Qt.SizeVerCursor
        return None

    def eventFilter(self, obj, event):
        if self.isMaximized():
            return super().eventFilter(obj, event)
        host_window = obj.window() if hasattr(obj, "window") else None
        if host_window is None or host_window != self:
            return super().eventFilter(obj, event)

        etype = event.type()
        if etype == QEvent.MouseMove:
            global_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            edges = self._resize_edges_at(self.mapFromGlobal(global_pos))
            cursor_shape = self._resize_cursor_for_edges(edges)
            if cursor_shape is None:
                if self.cursor().shape() in {
                    Qt.SizeHorCursor,
                    Qt.SizeVerCursor,
                    Qt.SizeFDiagCursor,
                    Qt.SizeBDiagCursor,
                }:
                    self.unsetCursor()
            else:
                self.setCursor(cursor_shape)
        elif etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            global_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            local_pos = self.mapFromGlobal(global_pos)
            edges = self._resize_edges_at(local_pos)
            if edges != Qt.Edges():
                window = self.windowHandle()
                if window is not None and window.startSystemResize(edges):
                    return True
                hit = self._hit_test_resize_native(global_pos.x(), global_pos.y())
                if hit is None:
                    hit = self._hit_test_resize(local_pos)
                if hit is not None and os.name == "nt":
                    ctypes.windll.user32.ReleaseCapture()
                    ctypes.windll.user32.SendMessageW(int(self.winId()), WM_NCLBUTTONDOWN, hit, 0)
                    return True
        return super().eventFilter(obj, event)

    def nativeEvent(self, eventType, message):
        if os.name == "nt":
            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
            except Exception:
                return super().nativeEvent(eventType, message)
            if msg.message == WM_NCCALCSIZE and msg.wParam:
                return True, 0
            if not self.isMaximized() and msg.message == WM_NCHITTEST:
                x = ctypes.c_short(msg.lParam & 0xFFFF).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                hit = self._hit_test_resize_native(x, y)
                if hit is not None:
                    return True, hit
        return super().nativeEvent(eventType, message)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # FlowLayout automatically handles resizing

    def setup_shortcuts(self):
        shortcut = QShortcut(QKeySequence(self.service.global_hotkey), self)
        shortcut.setContext(Qt.ApplicationShortcut)
        shortcut.activated.connect(self._on_hotkey_activated)
        self.toggle_shortcut = shortcut
        search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        search_shortcut.setContext(Qt.ApplicationShortcut)
        search_shortcut.activated.connect(self.universal_search.open_search)
        self.search_shortcut = search_shortcut
        search_shortcut_meta = QShortcut(QKeySequence("Meta+K"), self)
        search_shortcut_meta.setContext(Qt.ApplicationShortcut)
        search_shortcut_meta.activated.connect(self.universal_search.open_search)
        self.search_shortcut_meta = search_shortcut_meta
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
        self.show()
        self.activateWindow()

    def _should_collapse_after_app_launch(self, app_data: dict) -> bool:
        app_type = (app_data.get("type") or "exe").lower()
        return app_type in {"exe", "lnk", "folder", "url"}

    def _collapse_to_tray(self) -> None:
        if self.tray_available and self.tray_icon:
            self.hide()
            self.tray_icon.showMessage(
                "Лаунчер",
                "Элемент открыт, лаунчер свернут в трей.",
                QSystemTrayIcon.Information,
                1500,
            )

    def _launch_search_result(self, result):
        if result.item_type == "macro":
            success, error = self.launch_service.launch(result.payload)
            if not success:
                if error:
                    QMessageBox.warning(self, "Ошибка", error)
                return
            updated = self.service.increment_macro_usage(result.payload["path"]) or result.payload
            result.payload.update(updated)
        else:
            success, error = self.launch_service.launch(result.payload)
            if not success:
                if error:
                    QMessageBox.warning(self, "Ошибка", error)
                return
            if self._should_collapse_after_app_launch(result.payload):
                self._collapse_to_tray()
            updated = self.service.increment_usage(result.payload["path"]) or result.payload
            result.payload.update(updated)
        self.universal_search.hide()
        self.schedule_save()
        self.refresh_view()

    @property
    def is_macro_section(self) -> bool:
        return self.section_tabs.currentIndex() == 1

    @property
    def is_links_section(self) -> bool:
        return self.section_tabs.currentIndex() == 3

    @property
    def is_clipboard_section(self) -> bool:
        return self.section_tabs.currentIndex() == 4

    @property
    def is_folders_section(self) -> bool:
        return self.section_tabs.currentIndex() == 2

    def edit_item(self, item_data: dict):
        if self.is_macro_section:
            self.edit_macro(item_data)
        else:
            self.edit_app(item_data)

    def delete_item(self, item_data: dict):
        if self.is_macro_section:
            self.delete_macro(item_data)
        else:
            self.delete_app(item_data)

    def move_item_to_group(self, item_data: dict, group: str):
        if self.is_macro_section:
            self.move_macro_to_group(item_data, group)
        else:
            self.move_app_to_group(item_data, group)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()


def run_app():
    app = QApplication([])
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
