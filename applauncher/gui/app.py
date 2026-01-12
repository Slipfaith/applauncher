"""Main application window."""
import os
import sys
import logging
import ctypes
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
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
from PySide6.QtCore import (
    QEvent,
    QAbstractAnimation,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QEasingCurve,
    QRect,
    QSettings,
    QTimer,
    QVariantAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QIcon,
    QPixmap,
    QKeySequence,
    QShortcut,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .dialogs import AddAppDialog, AddMacroDialog, SettingsDialog
from .icon_service import IconService
from .layouts import FlowLayout
from .styles import (
    TOKENS,
    apply_design_system,
    apply_shadow,
    build_theme_tokens,
    interpolate_color_tokens,
)
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
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setObjectName("mainWindow")
        self.setMinimumSize(*TOKENS.sizes.window_min)
        self.resize(600, 400)
        self.setAcceptDrops(True)

        self.service = LauncherService()
        self.repository = self.service.repository
        self.macro_repository = self.service.macro_repository
        self._last_render_state: tuple[str, str, str, str, int] | None = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._persist_config)
        self._entry_animations: list[QPropertyAnimation] = []
        self._theme_mode = "light"
        self._accent_color = QColor(TOKENS.colors.accent)
        self._theme_animation: QVariantAnimation | None = None
        self._open_animation: QParallelAnimationGroup | None = None
        self._close_animation: QParallelAnimationGroup | None = None
        self._closing = False
        self._search_pulse_animation: QPropertyAnimation | None = None
        self._search_glow_animation: QVariantAnimation | None = None
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
        apply_shadow(container, TOKENS.shadows.floating)

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
        self.search_input.installEventFilter(self)
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
        self._apply_system_theme(initial=True)
        self._setup_theme_timer()
        self._enable_backdrop_blur()
        self.setup_shortcuts()
        self.refresh_view()

    def create_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self)

        pixmap = QPixmap(TOKENS.sizes.tray_icon, TOKENS.sizes.tray_icon)
        pixmap.fill(self._accent_color)
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

    def _update_tray_icon(self) -> None:
        if not self.tray_icon:
            return
        pixmap = QPixmap(TOKENS.sizes.tray_icon, TOKENS.sizes.tray_icon)
        pixmap.fill(self._accent_color)
        self.tray_icon.setIcon(QIcon(pixmap))

    def _setup_theme_timer(self) -> None:
        timer = QTimer(self)
        timer.setInterval(1000)
        timer.timeout.connect(self._apply_system_theme)
        timer.start()
        self._theme_timer = timer

    def _apply_system_theme(self, initial: bool = False) -> None:
        mode, accent = self._detect_system_theme()
        if not initial and mode == self._theme_mode and accent == self._accent_color:
            return
        new_tokens = build_theme_tokens(mode, accent)
        if initial:
            self._theme_mode = mode
            self._accent_color = accent
            self._apply_theme_tokens(new_tokens)
            return
        self._animate_theme_transition(new_tokens, mode, accent)

    def _apply_theme_tokens(self, tokens) -> None:
        app = QApplication.instance()
        if app:
            apply_design_system(app, tokens)
        self._update_tray_icon()

    def _animate_theme_transition(self, target_tokens, mode: str, accent: QColor) -> None:
        if self._theme_animation:
            self._theme_animation.stop()
        start_tokens = build_theme_tokens(self._theme_mode, self._accent_color)
        self._theme_animation = QVariantAnimation(self)
        self._theme_animation.setDuration(300)
        self._theme_animation.setStartValue(0.0)
        self._theme_animation.setEndValue(1.0)
        self._theme_animation.setEasingCurve(QEasingCurve.OutCubic)

        def on_value_changed(value):
            progress = float(value)
            colors = interpolate_color_tokens(start_tokens.colors, target_tokens.colors, progress)
            interim = build_theme_tokens(mode, accent)
            interim = interim.__class__(
                colors=colors,
                typography=interim.typography,
                spacing=interim.spacing,
                radii=interim.radii,
                shadows=interim.shadows,
                sizes=interim.sizes,
                layout=interim.layout,
            )
            self._apply_theme_tokens(interim)

        def on_finished():
            self._theme_mode = mode
            self._accent_color = accent
            self._apply_theme_tokens(target_tokens)

        self._theme_animation.valueChanged.connect(on_value_changed)
        self._theme_animation.finished.connect(on_finished)
        self._theme_animation.start()

    def _detect_system_theme(self) -> tuple[str, QColor]:
        if sys.platform != "win32":
            return "light", QColor(TOKENS.colors.accent)
        personalize = QSettings(
            "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
            QSettings.NativeFormat,
        )
        apps_light = personalize.value("AppsUseLightTheme", 1)
        try:
            mode = "light" if int(apps_light) == 1 else "dark"
        except (TypeError, ValueError):
            mode = "light"

        accent = self._read_windows_accent_color()
        return mode, accent

    def _read_windows_accent_color(self) -> QColor:
        settings = QSettings(
            "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\DWM",
            QSettings.NativeFormat,
        )
        raw = settings.value("AccentColor") or settings.value("ColorizationColor")
        if raw is None:
            return QColor(TOKENS.colors.accent)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            try:
                value = int(str(raw), 0)
            except (TypeError, ValueError):
                return QColor(TOKENS.colors.accent)
        red = value & 0xFF
        green = (value >> 8) & 0xFF
        blue = (value >> 16) & 0xFF
        return QColor(red, green, blue)

    def _enable_backdrop_blur(self) -> None:
        if sys.platform != "win32":
            return
        hwnd = int(self.winId())
        try:
            self._set_windows_backdrop(hwnd)
        except (AttributeError, OSError):
            return

    @staticmethod
    def _set_windows_backdrop(hwnd: int) -> None:
        class AccentPolicy(ctypes.Structure):
            _fields_ = [
                ("accent_state", ctypes.c_int),
                ("accent_flags", ctypes.c_int),
                ("gradient_color", ctypes.c_int),
                ("animation_id", ctypes.c_int),
            ]

        class WindowCompositionAttributeData(ctypes.Structure):
            _fields_ = [
                ("attribute", ctypes.c_int),
                ("data", ctypes.c_void_p),
                ("size_of_data", ctypes.c_size_t),
            ]

        accent = AccentPolicy()
        accent.accent_state = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.accent_flags = 2
        accent.gradient_color = 0xCC000000

        data = WindowCompositionAttributeData()
        data.attribute = 19  # WCA_ACCENT_POLICY
        data.data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.size_of_data = ctypes.sizeof(accent)

        set_window_composition_attribute = ctypes.windll.user32.SetWindowCompositionAttribute
        set_window_composition_attribute(hwnd, ctypes.byref(data))

        dwmapi = ctypes.windll.dwmapi
        backdrop_type = ctypes.c_int(3)
        dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop_type), ctypes.sizeof(backdrop_type))

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
        if self._closing:
            event.accept()
            return
        if self.tray_available and self.tray_icon:
            event.ignore()
            self._animate_hide(self._hide_to_tray)
            return
        response = QMessageBox.question(
            self,
            "Закрыть приложение",
            "Системный трей недоступен. Закрыть лаунчер?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response == QMessageBox.Yes:
            event.ignore()
            self._animate_hide(self._final_close)
        else:
            event.ignore()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.isMaximized():
            self._center_on_active_screen()
        self._animate_show()

    def eventFilter(self, source, event):
        if source is self.search_input and event.type() == QEvent.KeyPress:
            self._trigger_search_pulse()
        return super().eventFilter(source, event)

    def _trigger_search_pulse(self) -> None:
        if self.search_input is None:
            return
        if not isinstance(self.search_input.graphicsEffect(), QGraphicsDropShadowEffect):
            effect = QGraphicsDropShadowEffect(self.search_input)
            effect.setBlurRadius(12)
            effect.setOffset(0, 0)
            effect.setColor(QColor(self._accent_color))
            self.search_input.setGraphicsEffect(effect)
        effect = self.search_input.graphicsEffect()
        if not isinstance(effect, QGraphicsDropShadowEffect):
            return
        if self._search_pulse_animation:
            self._search_pulse_animation.stop()
        if self._search_glow_animation:
            self._search_glow_animation.stop()

        self._search_pulse_animation = QPropertyAnimation(effect, b"blurRadius", self)
        self._search_pulse_animation.setDuration(100)
        self._search_pulse_animation.setStartValue(4.0)
        self._search_pulse_animation.setEndValue(16.0)
        self._search_pulse_animation.setEasingCurve(QEasingCurve.OutCubic)

        self._search_glow_animation = QVariantAnimation(self)
        self._search_glow_animation.setDuration(100)
        self._search_glow_animation.setStartValue(0.2)
        self._search_glow_animation.setEndValue(0.6)

        def update_glow(value):
            alpha = float(value)
            glow = QColor(self._accent_color)
            glow.setAlphaF(alpha)
            effect.setColor(glow)

        self._search_glow_animation.valueChanged.connect(update_glow)
        self._search_pulse_animation.start()
        self._search_glow_animation.start()

    def _center_on_active_screen(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geometry = screen.availableGeometry()
        target_rect = self.geometry()
        target_rect.moveCenter(geometry.center())
        self.move(target_rect.topLeft())

    def _animate_show(self) -> None:
        if self._open_animation and self._open_animation.state() == QAbstractAnimation.Running:
            return
        final_geometry = self.geometry()
        start_geometry = self._scaled_geometry(final_geometry, 0.9)
        self.setWindowOpacity(0.0)
        self.setGeometry(start_geometry)

        self._open_animation = QParallelAnimationGroup(self)
        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(240)
        opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(self.service.window_opacity)
        geometry_anim = QPropertyAnimation(self, b"geometry")
        geometry_anim.setDuration(240)
        geometry_anim.setEasingCurve(QEasingCurve.OutCubic)
        geometry_anim.setStartValue(start_geometry)
        geometry_anim.setEndValue(final_geometry)
        self._open_animation.addAnimation(opacity_anim)
        self._open_animation.addAnimation(geometry_anim)
        self._open_animation.start()

    def _animate_hide(self, callback) -> None:
        if self._close_animation and self._close_animation.state() == QAbstractAnimation.Running:
            return
        start_geometry = self.geometry()
        end_geometry = self._scaled_geometry(start_geometry, 0.9)

        self._close_animation = QParallelAnimationGroup(self)
        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(150)
        opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        opacity_anim.setStartValue(self.windowOpacity())
        opacity_anim.setEndValue(0.0)
        geometry_anim = QPropertyAnimation(self, b"geometry")
        geometry_anim.setDuration(150)
        geometry_anim.setEasingCurve(QEasingCurve.OutCubic)
        geometry_anim.setStartValue(start_geometry)
        geometry_anim.setEndValue(end_geometry)
        self._close_animation.addAnimation(opacity_anim)
        self._close_animation.addAnimation(geometry_anim)

        def finish():
            self._closing = True
            callback()
            self._closing = False
            self.setWindowOpacity(self.service.window_opacity)

        self._close_animation.finished.connect(finish)
        self._close_animation.start()

    def _hide_to_tray(self) -> None:
        self.hide()
        if self.tray_icon:
            self.tray_icon.showMessage(
                "Лаунчер",
                "Приложение свернуто в трей. Кликните на иконку для возврата.",
                QSystemTrayIcon.Information,
                2000,
            )

    def _final_close(self) -> None:
        self.close()

    @staticmethod
    def _scaled_geometry(rect, scale: float):
        center = rect.center()
        new_width = int(rect.width() * scale)
        new_height = int(rect.height() * scale)
        new_rect = QRect(rect)
        new_rect.setWidth(new_width)
        new_rect.setHeight(new_height)
        new_rect.moveCenter(center)
        return new_rect

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        added = False
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
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
        elif self.is_links_section:
            self.add_link()
        else:
            self.add_app()

    def clear_all_items(self):
        if self.is_macro_section:
            self.clear_all_macros()
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
        elif self.is_links_section:
            filtered = [
                app
                for app in self.service.filtered_apps(query, current_group)
                if app.get("type") == "url"
            ]
        else:
            filtered = self.service.filtered_apps(query, current_group)
        self._sync_view_toggle()

        if self.view_mode == "grid":
            self.view_stack.setCurrentWidget(self.grid_widget)
            self.populate_grid(filtered)
        else:
            self.view_stack.setCurrentWidget(self.list_container)
            self.populate_list(filtered)

    def populate_grid(self, apps: list[dict]):
        for animation in self._entry_animations:
            animation.stop()
        self._entry_animations.clear()
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
            self._animate_result_item(btn, len(self._entry_animations), restore_shadow=True)

    def populate_list(self, apps: list[dict]):
        for animation in self._entry_animations:
            animation.stop()
        self._entry_animations.clear()
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
            self._animate_result_item(item, len(self._entry_animations), restore_shadow=False)
        self.list_layout.addStretch()

    def _animate_result_item(self, widget: QWidget, index: int, restore_shadow: bool) -> None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)

        def finish():
            widget.setGraphicsEffect(None)
            if restore_shadow:
                apply_shadow(widget, TOKENS.shadows.raised)

        animation.finished.connect(finish)
        self._entry_animations.append(animation)
        QTimer.singleShot(index * 30, animation.start)

    def launch_top_result(self):
        current_group = self.current_group
        if self.is_macro_section:
            filtered = self.service.filtered_macros(self.search_input.text(), current_group)
        elif self.is_links_section:
            filtered = [
                app
                for app in self.service.filtered_apps(self.search_input.text(), current_group)
                if app.get("type") == "url"
            ]
        else:
            filtered = self.service.filtered_apps(self.search_input.text(), current_group)
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # FlowLayout automatically handles resizing

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
        self.show()
        self.activateWindow()

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
        return self.section_tabs.currentIndex() == 2

    @property
    def is_clipboard_section(self) -> bool:
        return self.section_tabs.currentIndex() == 3

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
            self.request_hide()
        else:
            self.show()
            self.activateWindow()

    def request_hide(self) -> None:
        if self.tray_available and self.tray_icon:
            self._animate_hide(self._hide_to_tray)
        else:
            self._animate_hide(self._final_close)


def run_app():
    QApplication.setAttribute(Qt.AA_UseDesktopOpenGL)
    app = QApplication([])
    app.setStyle("Fusion")
    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    app.setQuitOnLastWindowClosed(not tray_available)
    apply_design_system(app, build_theme_tokens("light", QColor(TOKENS.colors.accent)))

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
