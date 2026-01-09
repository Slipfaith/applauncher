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
from PySide6.QtCore import Qt, QSize, Signal, QMimeData, QRect
from PySide6.QtGui import QDrag, QFontMetrics, QIcon, QPainter, QPixmap

from .styles import TOKENS, apply_shadow
from .repository import DEFAULT_GROUP

logger = logging.getLogger(__name__)

def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _resolve_icon_frame(app_data: dict) -> tuple[float, float, float, float] | None:
    frame_x = app_data.get("icon_frame_x")
    frame_y = app_data.get("icon_frame_y")
    frame_w = app_data.get("icon_frame_w")
    frame_h = app_data.get("icon_frame_h")
    if not all(isinstance(value, (int, float)) for value in (frame_x, frame_y, frame_w, frame_h)):
        return None
    frame_w = float(frame_w)
    frame_h = float(frame_h)
    if frame_w <= 0 or frame_h <= 0:
        return None
    return (
        _clamp(float(frame_x)),
        _clamp(float(frame_y)),
        _clamp(float(frame_w)),
        _clamp(float(frame_h)),
    )


def default_icon_frame(pixmap: QPixmap, target_size: QSize) -> tuple[float, float, float, float]:
    if pixmap.isNull() or target_size.isEmpty():
        return (0.0, 0.0, 1.0, 1.0)
    image_width = pixmap.width()
    image_height = pixmap.height()
    if image_width <= 0 or image_height <= 0:
        return (0.0, 0.0, 1.0, 1.0)
    target_aspect = target_size.width() / target_size.height()
    image_aspect = image_width / image_height
    if image_aspect >= target_aspect:
        frame_height = image_height
        frame_width = frame_height * target_aspect
        frame_x = (image_width - frame_width) / 2
        frame_y = 0
    else:
        frame_width = image_width
        frame_height = frame_width / target_aspect
        frame_x = 0
        frame_y = (image_height - frame_height) / 2
    return (
        frame_x / image_width,
        frame_y / image_height,
        frame_width / image_width,
        frame_height / image_height,
    )


def render_framed_pixmap(
    pixmap: QPixmap,
    target_size: QSize,
    frame: tuple[float, float, float, float] | None = None,
) -> QPixmap:
    if pixmap.isNull() or target_size.isEmpty():
        return pixmap
    frame = frame or default_icon_frame(pixmap, target_size)
    image_width = pixmap.width()
    image_height = pixmap.height()
    frame_x = int(round(_clamp(frame[0]) * image_width))
    frame_y = int(round(_clamp(frame[1]) * image_height))
    frame_w = int(round(_clamp(frame[2]) * image_width))
    frame_h = int(round(_clamp(frame[3]) * image_height))
    if frame_w <= 0 or frame_h <= 0:
        frame_x, frame_y, frame_w, frame_h = 0, 0, image_width, image_height
    frame_rect = QRect(frame_x, frame_y, frame_w, frame_h).intersected(
        QRect(0, 0, image_width, image_height)
    )
    cropped = pixmap.copy(frame_rect)
    scaled = cropped.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    target_pixmap = QPixmap(target_size)
    target_pixmap.fill(Qt.transparent)
    painter = QPainter(target_pixmap)
    offset_x = int(round((target_size.width() - scaled.width()) / 2))
    offset_y = int(round((target_size.height() - scaled.height()) / 2))
    painter.drawPixmap(offset_x, offset_y, scaled)
    painter.end()
    return target_pixmap


class AppButton(QPushButton):
    """Button used in grid view to display an application."""

    activated = Signal(object)
    editRequested = Signal(object)
    deleteRequested = Signal(object)
    openLocationRequested = Signal(object)
    favoriteToggled = Signal(object)
    moveRequested = Signal(object, str)

    def __init__(
        self,
        app_data: dict,
        parent=None,
        available_groups: list[str] | None = None,
        current_group: str | None = None,
    ):
        super().__init__(parent)
        self.app_data = app_data
        self.available_groups = available_groups or []
        self.current_group = current_group or app_data.get("group")
        self._drag_start_pos = None
        self.setProperty("role", "appTile")

        prefix = "★ " if app_data.get("favorite") else ""
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
        self.setToolTip(display_name)
        self.setText("" if has_custom_icon else self._wrap_text(display_label))
        if icon_path and os.path.exists(icon_path):
            if has_custom_icon:
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    frame = _resolve_icon_frame(app_data)
                    fitted = render_framed_pixmap(pixmap, QSize(*TOKENS.sizes.grid_button), frame)
                    self.setIcon(QIcon(fitted))
                else:
                    self.setIcon(QIcon(icon_path))
            else:
                self.setIcon(QIcon(icon_path))
        if has_custom_icon:
            self.setProperty("iconMode", "full")
            self.setIconSize(QSize(*TOKENS.sizes.grid_button))
        else:
            self.setIconSize(QSize(TOKENS.sizes.grid_icon, TOKENS.sizes.grid_icon))
        # Fixed size for FlowLayout consistency
        self.setFixedSize(*TOKENS.sizes.grid_button)
        apply_shadow(self, TOKENS.shadows.raised)

        self.clicked.connect(lambda: self.activated.emit(self.app_data))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_available_groups(self, groups: list[str]) -> None:
        self.available_groups = list(groups)

    def set_current_group(self, group: str | None) -> None:
        self.current_group = group

    def _wrap_text(self, text: str, max_lines: int = 2) -> str:
        metrics = QFontMetrics(self.font())
        max_width = TOKENS.sizes.grid_button[0] - (TOKENS.spacing.md * 2)
        if max_width <= 0 or not text:
            return text
        words = text.split()
        if not words:
            return text

        lines = []
        current = ""
        word_index = 0
        for idx, word in enumerate(words):
            candidate = f"{current} {word}".strip()
            if metrics.horizontalAdvance(candidate) <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
                if len(lines) == max_lines - 1:
                    word_index = idx
                    break
            word_index = idx + 1

        if current and len(lines) < max_lines:
            lines.append(current)

        truncated = word_index < len(words)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True

        if lines and (truncated or metrics.horizontalAdvance(lines[-1]) > max_width):
            lines[-1] = metrics.elidedText(lines[-1], Qt.ElideRight, max_width)

        return "\n".join(lines)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        edit_action = menu.addAction("✏️ Редактировать")
        open_folder_action = menu.addAction("📂 Открыть расположение")
        favorite_action = menu.addAction(
            "☆ Закрепить" if not self.app_data.get("favorite") else "★ Открепить"
        )
        delete_action = None
        trash_action = None
        if self.current_group == DEFAULT_GROUP:
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
        if action == edit_action:
            self.editRequested.emit(self.app_data)
        elif action == delete_action:
            self.deleteRequested.emit(self.app_data)
        elif action == trash_action:
            self.deleteRequested.emit(self.app_data)
        elif action == open_folder_action:
            self.openLocationRequested.emit(self.app_data)
        elif action == favorite_action:
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


class AppListItem(QWidget):
    """Compact list entry for list mode."""

    activated = Signal(object)
    editRequested = Signal(object)
    deleteRequested = Signal(object)
    openLocationRequested = Signal(object)
    favoriteToggled = Signal(object)
    moveRequested = Signal(object, str)

    def __init__(
        self,
        app_data: dict,
        parent=None,
        available_groups: list[str] | None = None,
        current_group: str | None = None,
    ):
        super().__init__(parent)
        self.app_data = app_data
        self.available_groups = available_groups or []
        self.current_group = current_group or app_data.get("group")
        self._drag_start_pos = None
        self._dragging = False
        self.setProperty("role", "listItem")

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
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    frame = _resolve_icon_frame(app_data)
                    icon_label.setPixmap(render_framed_pixmap(pixmap, QSize(32, 32), frame))
                else:
                    icon_label.setPixmap(QIcon(icon_path).pixmap(32, 32))
            else:
                icon_label.setPixmap(QIcon(icon_path).pixmap(32, 32))
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        prefix = "★ " if app_data.get("favorite") else ""
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

        path_label = QLabel(app_data["path"])
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
        favorite_action = menu.addAction(
            "☆ Закрепить" if not self.app_data.get("favorite") else "★ Открепить"
        )
        delete_action = None
        trash_action = None
        if self.current_group == DEFAULT_GROUP:
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
        if action == edit_action:
            self.editRequested.emit(self.app_data)
        elif action == delete_action:
            self.deleteRequested.emit(self.app_data)
        elif action == trash_action:
            self.deleteRequested.emit(self.app_data)
        elif action == open_folder_action:
            self.openLocationRequested.emit(self.app_data)
        elif action == favorite_action:
            self.favoriteToggled.emit(self.app_data)
        elif action in move_action_map:
            self.moveRequested.emit(self.app_data, move_action_map[action])


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
