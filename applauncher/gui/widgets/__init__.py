"""Custom widgets for the launcher UI."""
import os
import logging

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QWidget,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, QSize, Signal, QMimeData
from PySide6.QtGui import QDrag, QFontMetrics, QIcon

from ..styles import TOKENS, apply_shadow
from ...repository import DEFAULT_GROUP
from ...services.file_transfer import extract_drop_items, has_virtual_files
from ..tile_image.frame import default_icon_frame, render_framed_pixmap, resolve_icon_frame
from ..tile_image.utils import load_icon_file

logger = logging.getLogger(__name__)

from .clipboard_history_widget import ClipboardHistoryWidget  # noqa: E402
from .hotkey_settings_widget import HotkeySettingsWidget  # noqa: E402
from .notes_widget import NotesWidget  # noqa: E402
from .toast import Toast  # noqa: E402
from .universal_search_widget import UniversalSearchWidget  # noqa: E402


def _mime_has_copyable_payload(mime) -> bool:
    """True when the drag carries files copyable into a folder tile."""
    if mime.hasFormat("application/x-applauncher-app"):
        return False
    if mime.hasUrls() and any(url.toLocalFile() for url in mime.urls()):
        return True
    return has_virtual_files(mime)


class AppButton(QPushButton):
    """Button used in grid view to display an application."""

    activated = Signal(object)
    editRequested = Signal(object)
    deleteRequested = Signal(object)
    openLocationRequested = Signal(object)
    favoriteToggled = Signal(object)
    moveRequested = Signal(object, str)
    copyLinkRequested = Signal(object)
    copyDropRequested = Signal(object, list, list)

    def __init__(
        self,
        app_data: dict,
        parent=None,
        tile_size: tuple[int, int] | None = None,
        icon_size: int | None = None,
        available_groups: list[str] | None = None,
        current_group: str | None = None,
        default_group: str | None = DEFAULT_GROUP,
        show_favorite: bool = True,
    ):
        super().__init__(parent)
        self.app_data = app_data
        self.available_groups = available_groups or []
        self.current_group = current_group or app_data.get("group")
        self.default_group = default_group
        self.show_favorite = show_favorite
        self._drag_start_pos = None
        self._accepts_file_drop = (
            app_data.get("type") == "folder" and not app_data.get("disabled")
        )
        self.setProperty("role", "appTile")
        self.setAcceptDrops(self._accepts_file_drop)

        self.tile_size = tile_size or TOKENS.sizes.grid_button
        self.icon_size = icon_size or TOKENS.sizes.grid_icon

        prefix = "★ " if self.show_favorite and app_data.get("favorite") else ""
        display_name = f"{prefix}{app_data['name']}"
        app_type = app_data.get("type", "exe")
        display_label = display_name
        icon_path = app_data.get("icon_path", "")
        has_custom_icon = bool(app_data.get("custom_icon"))
        if app_type == "url" and not (icon_path and os.path.exists(icon_path)):
            if app_data.get("path", "").lower().startswith("steam://"):
                display_label = f"🎮 {display_name}"
            else:
                display_label = f"🌐 {display_name}"
        elif app_type == "folder" and not (icon_path and os.path.exists(icon_path)):
            display_label = f"📁 {display_name}"
        tooltip = display_name
        if self._accepts_file_drop:
            tooltip = f"{display_name}\nПеретащите файл или папку сюда, чтобы скопировать"
        self.setToolTip(tooltip)
        self._display_label = display_label
        self._has_custom_icon = has_custom_icon
        self._sync_text()
        if icon_path and os.path.exists(icon_path):
            if has_custom_icon:
                pixmap = load_icon_file(icon_path)
                if not pixmap.isNull():
                    frame = resolve_icon_frame(app_data)
                    fitted = render_framed_pixmap(pixmap, QSize(*self.tile_size), frame)
                    self.setIcon(QIcon(fitted))
                else:
                    self.setIcon(QIcon(icon_path))
            else:
                self.setIcon(QIcon(icon_path))
        if has_custom_icon:
            self.setProperty("iconMode", "full")
            self.setIconSize(QSize(*self.tile_size))
        else:
            self.setIconSize(QSize(self.icon_size, self.icon_size))
        # Fixed size for FlowLayout consistency
        self.setFixedSize(*self.tile_size)
        apply_shadow(self, TOKENS.shadows.raised)

        self.clicked.connect(lambda: self.activated.emit(self.app_data))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_available_groups(self, groups: list[str]) -> None:
        self.available_groups = list(groups)

    def set_current_group(self, group: str | None) -> None:
        self.current_group = group

    def _wrap_text(self, text: str, max_lines: int = 3) -> str:
        metrics = QFontMetrics(self.font())
        max_width = self.tile_size[0] - (TOKENS.spacing.md * 2)
        if max_width <= 0 or not text:
            return text

        def wrap_line(line: str) -> list[str]:
            words = line.split()
            if not words:
                return [line]
            wrapped: list[str] = []
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if metrics.horizontalAdvance(candidate) <= max_width or not current:
                    current = candidate
                else:
                    wrapped.append(current)
                    current = word
            if current:
                wrapped.append(current)
            return wrapped

        raw_lines = text.splitlines() or [text]
        lines: list[str] = []
        total_segments = 0
        for raw in raw_lines:
            wrapped_segments = wrap_line(raw)
            total_segments += len(wrapped_segments)
            for segment in wrapped_segments:
                lines.append(segment)
                if len(lines) >= max_lines:
                    break
            if len(lines) >= max_lines:
                break

        if not lines:
            return ""

        truncated = total_segments > max_lines

        if truncated or metrics.horizontalAdvance(lines[-1]) > max_width:
            lines[-1] = metrics.elidedText(lines[-1], Qt.ElideRight, max_width)

        return "\n".join(lines)

    def set_tile_size(self, tile_size: tuple[int, int], icon_size: int) -> None:
        self.tile_size = tile_size
        self.icon_size = icon_size
        if self._has_custom_icon:
            self.setIconSize(QSize(*self.tile_size))
        else:
            self.setIconSize(QSize(self.icon_size, self.icon_size))
        self.setFixedSize(*self.tile_size)
        self._sync_text()

    def _sync_text(self) -> None:
        if self._has_custom_icon:
            self.setText("")
        else:
            self.setText(self._wrap_text(self._display_label))

    def _set_drop_active(self, active: bool) -> None:
        if self.property("dropActive") == active:
            return
        self.setProperty("dropActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        edit_action = menu.addAction("✏️ Редактировать")
        open_folder_action = menu.addAction("📂 Открыть расположение")
        copy_link_action = None
        if self.app_data.get("type") == "url":
            copy_link_action = menu.addAction("🔗 Скопировать ссылку")
        favorite_action = None
        if self.show_favorite:
            favorite_action = menu.addAction(
                "☆ Закрепить" if not self.app_data.get("favorite") else "★ Открепить"
            )
        delete_action = None
        trash_action = None
        if self.default_group and self.current_group == self.default_group:
            trash_action = menu.addAction("🗑️ В мусор")
        else:
            delete_action = menu.addAction("🗑️ Удалить")
        move_menu = menu.addMenu("📁 Переместить в")
        move_action_map = {}
        for group in self.available_groups:
            if group == self.current_group:
                continue
            action = move_menu.addAction(group)
            move_action_map[action] = group
        if not move_action_map:
            empty_action = move_menu.addAction("Нет других вкладок")
            empty_action.setEnabled(False)

        action = menu.exec(self.mapToGlobal(pos))
        if action is None:
            return
        if action == edit_action:
            self.editRequested.emit(self.app_data)
        elif action == delete_action:
            self.deleteRequested.emit(self.app_data)
        elif action == trash_action:
            self.deleteRequested.emit(self.app_data)
        elif action == open_folder_action:
            self.openLocationRequested.emit(self.app_data)
        elif copy_link_action and action == copy_link_action:
            self.copyLinkRequested.emit(self.app_data)
        elif favorite_action and action == favorite_action:
            self.favoriteToggled.emit(self.app_data)
        elif action in move_action_map:
            self.moveRequested.emit(self.app_data, move_action_map[action])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-applauncher-app", self.app_data["path"].encode("utf-8"))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if self._accepts_file_drop and _mime_has_copyable_payload(event.mimeData()):
            self._set_drop_active(True)
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._accepts_file_drop and _mime_has_copyable_payload(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._set_drop_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._set_drop_active(False)
        if not (self._accepts_file_drop and _mime_has_copyable_payload(event.mimeData())):
            super().dropEvent(event)
            return
        items, warnings = extract_drop_items(event.mimeData())
        if items or warnings:
            event.acceptProposedAction()
            self.copyDropRequested.emit(self.app_data, items, warnings)
        else:
            super().dropEvent(event)


class AppListItem(QWidget):
    """Compact list entry for list mode."""

    activated = Signal(object)
    editRequested = Signal(object)
    deleteRequested = Signal(object)
    openLocationRequested = Signal(object)
    favoriteToggled = Signal(object)
    moveRequested = Signal(object, str)
    copyLinkRequested = Signal(object)
    copyDropRequested = Signal(object, list, list)

    def __init__(
        self,
        app_data: dict,
        parent=None,
        available_groups: list[str] | None = None,
        current_group: str | None = None,
        default_group: str | None = DEFAULT_GROUP,
        show_favorite: bool = True,
    ):
        super().__init__(parent)
        self.app_data = app_data
        self.available_groups = available_groups or []
        self.current_group = current_group or app_data.get("group")
        self.default_group = default_group
        self.show_favorite = show_favorite
        self._drag_start_pos = None
        self._dragging = False
        self._accepts_file_drop = (
            app_data.get("type") == "folder" and not app_data.get("disabled")
        )
        self.setProperty("role", "listItem")
        self.setAcceptDrops(self._accepts_file_drop)

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout()
        layout.setContentsMargins(
            TOKENS.spacing.sm,
            TOKENS.spacing.xs,
            TOKENS.spacing.sm,
            TOKENS.spacing.xs,
        )
        layout.setSpacing(TOKENS.spacing.sm)

        icon_label = QLabel()
        icon_path = app_data.get("icon_path", "")
        if icon_path and os.path.exists(icon_path):
            if app_data.get("custom_icon"):
                pixmap = load_icon_file(icon_path)
                if not pixmap.isNull():
                    frame = resolve_icon_frame(app_data)
                    icon_label.setPixmap(render_framed_pixmap(pixmap, QSize(32, 32), frame))
                else:
                    icon_label.setPixmap(QIcon(icon_path).pixmap(32, 32))
            else:
                icon_label.setPixmap(QIcon(icon_path).pixmap(32, 32))
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        prefix = "★ " if self.show_favorite and app_data.get("favorite") else ""
        app_type = app_data.get("type", "exe")
        if app_type == "url":
            if app_data.get("path", "").lower().startswith("steam://"):
                name_label = QLabel(f"🎮 {prefix}{app_data['name']}")
            else:
                name_label = QLabel(f"🌐 {prefix}{app_data['name']}")
        elif app_type == "folder":
            name_label = QLabel(f"📁 {prefix}{app_data['name']}")
        else:
            name_label = QLabel(f"{prefix}{app_data['name']}")
        name_label.setProperty("role", "listTitle")
        text_layout.addWidget(name_label)

        display_path = app_data.get("path", "")
        if app_type == "url":
            display_path = app_data.get("raw_path") or display_path
        path_label = QLabel(display_path)
        path_label.setProperty("role", "listSubtitle")
        text_layout.addWidget(path_label)
        layout.addLayout(text_layout)

        layout.addStretch()

        self.setLayout(layout)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_available_groups(self, groups: list[str]) -> None:
        self.available_groups = list(groups)

    def set_current_group(self, group: str | None) -> None:
        self.current_group = group

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        self._dragging = True
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-applauncher-app", self.app_data["path"].encode("utf-8"))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.MoveAction)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self._dragging:
            self.activated.emit(self.app_data)
        super().mouseReleaseEvent(event)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        edit_action = menu.addAction("✏️ Редактировать")
        open_folder_action = menu.addAction("📂 Открыть расположение")
        copy_link_action = None
        if self.app_data.get("type") == "url":
            copy_link_action = menu.addAction("🔗 Скопировать ссылку")
        favorite_action = None
        if self.show_favorite:
            favorite_action = menu.addAction(
                "☆ Закрепить" if not self.app_data.get("favorite") else "★ Открепить"
            )
        delete_action = None
        trash_action = None
        if self.default_group and self.current_group == self.default_group:
            trash_action = menu.addAction("🗑️ В мусор")
        else:
            delete_action = menu.addAction("🗑️ Удалить")
        move_menu = menu.addMenu("📁 Переместить в")
        move_action_map = {}
        for group in self.available_groups:
            if group == self.current_group:
                continue
            action = move_menu.addAction(group)
            move_action_map[action] = group
        if not move_action_map:
            empty_action = move_menu.addAction("Нет других вкладок")
            empty_action.setEnabled(False)

        action = menu.exec(self.mapToGlobal(pos))
        if action is None:
            return
        if action == edit_action:
            self.editRequested.emit(self.app_data)
        elif action == delete_action:
            self.deleteRequested.emit(self.app_data)
        elif action == trash_action:
            self.deleteRequested.emit(self.app_data)
        elif action == open_folder_action:
            self.openLocationRequested.emit(self.app_data)
        elif copy_link_action and action == copy_link_action:
            self.copyLinkRequested.emit(self.app_data)
        elif favorite_action and action == favorite_action:
            self.favoriteToggled.emit(self.app_data)
        elif action in move_action_map:
            self.moveRequested.emit(self.app_data, move_action_map[action])

    def _set_drop_active(self, active: bool) -> None:
        if self.property("dropActive") == active:
            return
        self.setProperty("dropActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        if self._accepts_file_drop and _mime_has_copyable_payload(event.mimeData()):
            self._set_drop_active(True)
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._accepts_file_drop and _mime_has_copyable_payload(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._set_drop_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._set_drop_active(False)
        if not (self._accepts_file_drop and _mime_has_copyable_payload(event.mimeData())):
            super().dropEvent(event)
            return
        items, warnings = extract_drop_items(event.mimeData())
        if items or warnings:
            event.acceptProposedAction()
            self.copyDropRequested.emit(self.app_data, items, warnings)
        else:
            super().dropEvent(event)


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setObjectName("titleBar")
        self.setFixedHeight(TOKENS.sizes.title_bar_height)

        from PySide6.QtWidgets import QHBoxLayout  # lazy import to avoid circular deps

        layout = QHBoxLayout()
        layout.setContentsMargins(
            TOKENS.spacing.sm,
            TOKENS.spacing.none,
            TOKENS.spacing.sm,
            TOKENS.spacing.none,
        )
        layout.setSpacing(TOKENS.spacing.xs)

        spacer = QLabel()
        spacer.setFixedWidth(TOKENS.spacing.sm)
        layout.addWidget(spacer)

        title_label = QLabel("Лаунчер")
        title_label.setProperty("role", "titleText")
        layout.addWidget(title_label)
        layout.addStretch()

        min_btn = QPushButton("−")
        min_btn.setProperty("role", "titleButton")
        min_btn.setProperty("variant", "ghost")
        min_btn.clicked.connect(parent.showMinimized)
        layout.addWidget(min_btn)

        max_btn = QPushButton("□")
        max_btn.setProperty("role", "titleButton")
        max_btn.setProperty("variant", "ghost")
        max_btn.clicked.connect(self.toggle_maximize)
        layout.addWidget(max_btn)

        close_btn = QPushButton("✕")
        close_btn.setProperty("role", "titleButton")
        close_btn.setProperty("variant", "danger")
        close_btn.clicked.connect(self.close_to_tray)
        layout.addWidget(close_btn)

        self.setLayout(layout)
        self.start = None

    def close_to_tray(self):
        if not getattr(self.parent, "tray_available", False) or not self.parent.tray_icon:
            self.parent.close()
            return
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
