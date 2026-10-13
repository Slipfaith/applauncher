"""Custom widgets for the launcher UI."""
import os

from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QMenu,
    QSystemTrayIcon,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
    QSizePolicy,
    QVBoxLayout,
)
from PySide6.QtCore import QEvent, Qt, QRect, QSize, QTimer, Signal, QMimeData, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QDrag, QFontMetrics, QIcon, QColor, QPalette, QTextLayout, QTextOption

from ..glyphs import GlyphButton, KeyboardButton, glyph_icon, paint_focus
from ..fallback_icons import ItemIconWidget, fallback_icon
from ..styles import TOKENS, active_colors, to_qcolor
from ...repository import DEFAULT_GROUP
from ..drop_payload import can_extract_dropped_files, extract_dropped_files
from ..tile_image.frame import default_icon_frame, render_framed_pixmap, resolve_icon_frame
from ..tile_image.utils import load_icon_file
from ...services.local_hotkeys import format_hotkey_for_display

from .clipboard_history_widget import ClipboardHistoryWidget  # noqa: E402
from .hotkey_settings_widget import HotkeySettingsWidget  # noqa: E402
from .notes_widget import NotesWidget  # noqa: E402
from .universal_search_widget import UniversalSearchWidget  # noqa: E402

def _set_state_property(widget: QWidget, name: str, value) -> None:
    """Set a dynamic property used by the stylesheet and re-polish so it applies."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class AppButton(KeyboardButton):
    """Button used in grid view to display an application."""

    activated = Signal(object)
    editRequested = Signal(object)
    deleteRequested = Signal(object)
    openLocationRequested = Signal(object)
    favoriteToggled = Signal(object)
    moveRequested = Signal(object, str)
    copyLinkRequested = Signal(object)
    assignHotkeyRequested = Signal(object)
    clearHotkeyRequested = Signal(object)
    filesDroppedToFolder = Signal(object, object)

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
        self.setProperty("role", "appTile")

        prefix = "★ " if self.show_favorite and app_data.get("favorite") else ""
        display_name = f"{prefix}{app_data['name']}"
        app_type = app_data.get("type", "exe")
        self._accept_external_files = app_type == "folder"
        self.setAcceptDrops(self._accept_external_files)
        icon_path = app_data.get("icon_path", "")
        pixmap = load_icon_file(icon_path) if icon_path and os.path.exists(icon_path) else None
        has_picture = pixmap is not None and not pixmap.isNull()
        has_custom_icon = bool(app_data.get("custom_icon") and has_picture)
        local_hotkey = (app_data.get("local_hotkey") or "").strip()
        tooltip_lines = [display_name]
        if local_hotkey:
            tooltip_lines.append(f"Горячая клавиша: {local_hotkey}")
        self.setToolTip("\n".join(tooltip_lines))
        self._display_label = "" if has_custom_icon else display_name
        self.setAccessibleName(display_name)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setText(self._wrap_text(self._display_label))
        if has_picture:
            if has_custom_icon:
                frame = resolve_icon_frame(app_data)
                fitted = render_framed_pixmap(pixmap, QSize(*TOKENS.sizes.grid_button), frame)
                self.setIcon(QIcon(fitted))
            else:
                self.setIcon(QIcon(pixmap))
        else:
            self.setIcon(fallback_icon(app_data))
        if has_custom_icon:
            self.setProperty("iconMode", "full")
            self._base_icon_size = QSize(*TOKENS.sizes.grid_button)
        else:
            self._base_icon_size = QSize(TOKENS.sizes.grid_icon, TOKENS.sizes.grid_icon)
        self.setIconSize(self._base_icon_size)
        self._pressed_icon_size = QSize(
            max(16, int(round(self._base_icon_size.width() * 0.94))),
            max(16, int(round(self._base_icon_size.height() * 0.94))),
        )
        # Fixed size for FlowLayout consistency
        self.setFixedSize(*TOKENS.sizes.grid_button)

        shadow = TOKENS.shadows.raised
        # Keep the complete hover shadow inside the grid's edge padding.
        self._shadow_base_blur = float(min(shadow.blur, TOKENS.layout.grid_layout_margin - abs(shadow.offset_y)))
        self._shadow_base_x = float(shadow.offset_x)
        self._shadow_base_y = float(shadow.offset_y)
        self._shadow_base_color = to_qcolor(shadow.color)

        self._shadow_effect = QGraphicsDropShadowEffect(self)
        self._shadow_effect.setBlurRadius(self._shadow_base_blur)
        self._shadow_effect.setXOffset(shadow.offset_x)
        self._shadow_effect.setYOffset(shadow.offset_y)
        self._shadow_effect.setColor(self._shadow_base_color)
        self.setGraphicsEffect(self._shadow_effect)
        # Tiles rest flat and lift on hover (design system: "quiet until touched").
        self._shadow_effect.setEnabled(False)
        self.setAttribute(Qt.WA_Hover, True)

        self._press_progress = 0.0
        self._press_animation = QVariantAnimation(self)
        self._press_animation.setDuration(90)
        self._press_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._press_animation.setStartValue(0.0)
        self._press_animation.setEndValue(0.0)
        self._press_animation.valueChanged.connect(self._apply_press_progress)

        self.clicked.connect(lambda: self.activated.emit(self.app_data))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self._copy_btn = None
        if app_type in {"url", "folder"}:
            btn = GlyphButton(
                "copy",
                self,
                glyph_size=14,
                tooltip="Скопировать ссылку" if app_type == "url" else "Скопировать путь",
            )
            btn.setProperty("role", "tileCopy")
            btn.setFixedSize(22, 22)
            btn.move(self.width() - 26, 4)
            btn.setVisible(False)
            btn.clicked.connect(self._on_copy_clicked)
            btn.installEventFilter(self)
            self._copy_btn = btn
        self.ensurePolished()
        self.setText(self._wrap_text(self._display_label))

    def _on_copy_clicked(self):
        self.copyLinkRequested.emit(self.app_data)
        btn = self._copy_btn
        if btn is None:
            return
        btn.set_glyph("check")
        _set_state_property(btn, "state", "done")
        QTimer.singleShot(800, self._reset_copy_btn)

    def _reset_copy_btn(self):
        btn = self._copy_btn
        if btn is None:
            return
        btn.set_glyph("copy")
        _set_state_property(btn, "state", None)
        self._sync_copy_visibility()

    def _sync_copy_visibility(self):
        if self._copy_btn is not None:
            visible = (self.underMouse() or self.hasFocus() or self._copy_btn.hasFocus()
                       or self._copy_btn.property("state") == "done")
            self._copy_btn.setVisible(visible)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._sync_copy_visibility()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        QTimer.singleShot(0, self._sync_copy_visibility)

    def eventFilter(self, obj, event):
        if obj is self._copy_btn and event.type() in (QEvent.FocusIn, QEvent.FocusOut):
            QTimer.singleShot(0, self._sync_copy_visibility)
        return super().eventFilter(obj, event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.StyleChange) and hasattr(self, "_display_label"):
            wrapped = self._wrap_text(self._display_label)
            if wrapped != self.text():
                self.setText(wrapped)

    def _apply_press_progress(self, value):
        progress = max(0.0, min(1.0, float(value)))
        self._press_progress = progress

        icon_w = int(round(self._base_icon_size.width() + (self._pressed_icon_size.width() - self._base_icon_size.width()) * progress))
        icon_h = int(round(self._base_icon_size.height() + (self._pressed_icon_size.height() - self._base_icon_size.height()) * progress))
        self.setIconSize(QSize(max(1, icon_w), max(1, icon_h)))

        blur = max(0.0, self._shadow_base_blur * (1.0 - 0.70 * progress))
        x_offset = self._shadow_base_x * (1.0 - progress)
        y_offset = self._shadow_base_y * (1.0 - progress)
        color = QColor(self._shadow_base_color)
        color.setAlpha(max(0, int(round(self._shadow_base_color.alpha() * (1.0 - 0.85 * progress)))))
        self._shadow_effect.setBlurRadius(blur)
        self._shadow_effect.setXOffset(x_offset)
        self._shadow_effect.setYOffset(y_offset)
        self._shadow_effect.setColor(color)

    def _animate_press(self, target: float, duration_ms: int) -> None:
        target = max(0.0, min(1.0, target))
        self._press_animation.stop()
        self._press_animation.setDuration(duration_ms)
        self._press_animation.setStartValue(self._press_progress)
        self._press_animation.setEndValue(target)
        self._press_animation.start()

    def set_available_groups(self, groups: list[str]) -> None:
        self.available_groups = list(groups)

    def set_current_group(self, group: str | None) -> None:
        self.current_group = group

    def paintEvent(self, _event):
        """Icon above, name below (design system Tile); the stylesheet draws the box."""
        painter = QStylePainter(self)
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        opt.text = ""
        opt.icon = QIcon()
        painter.drawControl(QStyle.CE_PushButtonBevel, opt)

        icon = self.icon()
        mode = QIcon.Normal if self.isEnabled() else QIcon.Disabled
        rect = self.rect()
        if self.property("iconMode") == "full":
            size = self.iconSize()
            target = QRect(0, 0, size.width(), size.height())
            target.moveCenter(rect.center())
            icon.paint(painter, target, Qt.AlignCenter, mode)
            paint_focus(painter, self)
            return

        text = self.text()
        metrics = QFontMetrics(self.font())
        lines = text.split("\n") if text else []
        text_h = metrics.lineSpacing() * len(lines)
        icon_size = self.iconSize() if not icon.isNull() else QSize(0, 0)
        gap = TOKENS.spacing.sm - 2 if (lines and not icon.isNull()) else 0
        block_h = icon_size.height() + gap + text_h
        top = rect.top() + max(0, (rect.height() - block_h) // 2)
        if not icon.isNull():
            icon_rect = QRect(0, 0, icon_size.width(), icon_size.height())
            icon_rect.moveTop(top)
            icon_rect.moveLeft(rect.center().x() - icon_size.width() // 2 + 1)
            icon.paint(painter, icon_rect, Qt.AlignCenter, mode)
        if lines:
            painter.setPen(opt.palette.color(QPalette.ButtonText))
            pad = TOKENS.spacing.xs
            text_rect = QRect(rect.left() + pad, top + icon_size.height() + gap, rect.width() - pad * 2, text_h)
            painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop, text)
        paint_focus(painter, self)

    def enterEvent(self, event):
        self._shadow_effect.setEnabled(True)
        if self._copy_btn is not None:
            self._copy_btn.setVisible(True)
        super().enterEvent(event)

    def _wrap_text(self, text: str, max_lines: int = 2) -> str:
        font = self.font()
        max_width = TOKENS.sizes.grid_button[0] - (TOKENS.spacing.md * 2)
        if max_width <= 0 or not text:
            return text
        key = (text, font.key(), max_width, max_lines)
        cache = getattr(self, "_wrap_cache", None)
        if cache is None:
            self._wrap_cache = cache = {}
        if key in cache:
            return cache[key]
        metrics = QFontMetrics(font)
        text = " ".join(text.split())
        encoded = text.encode("utf-16-le")
        layout = QTextLayout(text, font)
        options = QTextOption()
        options.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(options)
        lines = []
        layout.beginLayout()
        for index in range(max_lines):
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max_width)
            start = line.textStart() * 2
            end = start + line.textLength() * 2
            if index == max_lines - 1 and end < len(encoded):
                remaining = encoded[start:].decode("utf-16-le")
                lines.append(metrics.elidedText(remaining, Qt.ElideRight, max_width))
            else:
                lines.append(encoded[start:end].decode("utf-16-le").strip())
        layout.endLayout()
        wrapped = "\n".join(lines)
        # Style changes revisit the same few fonts; retain a bounded local cache.
        if len(cache) >= 8:
            cache.clear()
        cache[key] = wrapped
        return wrapped

    def show_context_menu(self, pos):
        menu = QMenu(self)
        edit_action = menu.addAction(glyph_icon("edit"), "Редактировать")
        open_folder_action = menu.addAction(glyph_icon("folder-open"), "Открыть расположение")
        current_hotkey = (self.app_data.get("local_hotkey") or "").strip()
        if current_hotkey:
            hotkey_action = menu.addAction(glyph_icon("keyboard"), f"Изменить горячую клавишу ({current_hotkey})")
        else:
            hotkey_action = menu.addAction(glyph_icon("keyboard"), "Назначить горячую клавишу")
        clear_hotkey_action = None
        if current_hotkey:
            clear_hotkey_action = menu.addAction(glyph_icon("close"), "Удалить горячую клавишу")
        copy_link_action = None
        if self.app_data.get("type") == "url":
            copy_link_action = menu.addAction(glyph_icon("link"), "Скопировать ссылку")
        favorite_action = None
        if self.show_favorite:
            favorite_action = menu.addAction(
                glyph_icon("star"),
                "Закрепить" if not self.app_data.get("favorite") else "Открепить",
            )
        delete_action = None
        trash_action = None
        if self.default_group and self.current_group == self.default_group:
            trash_action = menu.addAction(glyph_icon("trash", active_colors().danger), "В мусор")
        else:
            delete_action = menu.addAction(glyph_icon("trash", active_colors().danger), "Удалить")
        move_menu = menu.addMenu(glyph_icon("move"), "Переместить в")
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
        elif action == hotkey_action:
            self.assignHotkeyRequested.emit(self.app_data)
        elif clear_hotkey_action and action == clear_hotkey_action:
            self.clearHotkeyRequested.emit(self.app_data)
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
            self._animate_press(1.0, 80)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        self._animate_press(0.0, 90)
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-applauncher-app", self.app_data.get("id", self.app_data["path"]).encode("utf-8"))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.MoveAction)
        self._drag_start_pos = None

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._animate_press(0.0, 120)
            self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if not (QApplication.mouseButtons() & Qt.LeftButton):
            self._animate_press(0.0, 120)
        self._shadow_effect.setEnabled(False)
        self._sync_copy_visibility()
        super().leaveEvent(event)

    def dragEnterEvent(self, event):
        if self._accept_external_files and can_extract_dropped_files(event.mimeData()):
            _set_state_property(self, "dropTarget", True)
            event.acceptProposedAction()
            return
        _set_state_property(self, "dropTarget", None)
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        _set_state_property(self, "dropTarget", None)
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        if self._accept_external_files and can_extract_dropped_files(event.mimeData()):
            _set_state_property(self, "dropTarget", True)
            event.acceptProposedAction()
            return
        _set_state_property(self, "dropTarget", None)
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        _set_state_property(self, "dropTarget", None)
        if not self._accept_external_files:
            super().dropEvent(event)
            return
        dropped_files = extract_dropped_files(event.mimeData())
        if not dropped_files.paths:
            super().dropEvent(event)
            return
        payload = dropped_files.transfer()
        try:
            self.filesDroppedToFolder.emit(self.app_data, payload)
        finally:
            if not payload.claimed:
                payload.cleanup()
        event.acceptProposedAction()


class _ElidedLabel(QLabel):
    """Single line whose full value remains available to assistive tools."""

    def __init__(self, text: str):
        super().__init__(text)
        self._full_text = text
        self._elide_key = None
        self.setTextFormat(Qt.PlainText)
        self.setToolTip(text)
        self.setAccessibleName(text)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def _update_text(self):
        key = (self.contentsRect().width(), self.font().key())
        if key == self._elide_key:
            return
        self._elide_key = key
        text = self.fontMetrics().elidedText(self._full_text, Qt.ElideRight, max(0, key[0]))
        if text != self.text():
            self.setText(text)

    def paintEvent(self, event):
        # Font/style/layout events during construction can run several times.
        # Elide once with the final font and width, when the row is painted.
        self._update_text()
        super().paintEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.FontChange and hasattr(self, "_full_text"):
            self._elide_key = None
            self.update()


class AppListItem(QWidget):
    """Compact list entry for list mode."""

    activated = Signal(object)
    editRequested = Signal(object)
    deleteRequested = Signal(object)
    openLocationRequested = Signal(object)
    favoriteToggled = Signal(object)
    moveRequested = Signal(object, str)
    copyLinkRequested = Signal(object)
    assignHotkeyRequested = Signal(object)
    clearHotkeyRequested = Signal(object)
    filesDroppedToFolder = Signal(object, object)

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
        self._accept_external_files = app_data.get("type", "exe") == "folder"
        self.setAcceptDrops(self._accept_external_files)
        self.setProperty("role", "listItem")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(app_data.get("name", ""))
        self.setAttribute(Qt.WA_StyledBackground, True)
        local_hotkey = (app_data.get("local_hotkey") or "").strip()
        tooltip_lines = [app_data.get("name", "")]
        if local_hotkey:
            tooltip_lines.append(f"Горячая клавиша: {local_hotkey}")
        self.setToolTip("\n".join(line for line in tooltip_lines if line))

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout()
        layout.setContentsMargins(
            TOKENS.spacing.md,
            TOKENS.spacing.sm - 2,
            TOKENS.spacing.md,
            TOKENS.spacing.sm - 2,
        )
        layout.setSpacing(TOKENS.spacing.md)

        icon_label = ItemIconWidget(app_data, 32, self)
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        prefix = "★ " if self.show_favorite and app_data.get("favorite") else ""
        app_type = app_data.get("type", "exe")
        name_label = _ElidedLabel(f"{prefix}{app_data['name']}")
        name_label.setProperty("role", "listTitle")
        text_layout.addWidget(name_label)

        display_path = app_data.get("path", "")
        if app_type == "url":
            display_path = app_data.get("raw_path") or display_path
        path_label = _ElidedLabel(display_path)
        path_label.setProperty("role", "listSubtitle")
        text_layout.addWidget(path_label)
        layout.addLayout(text_layout, 1)

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

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.activated.emit(self.app_data)
            event.accept()
            return
        super().keyPressEvent(event)

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
        mime.setData("application/x-applauncher-app", self.app_data.get("id", self.app_data["path"]).encode("utf-8"))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.MoveAction)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self._dragging:
            self.activated.emit(self.app_data)
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if self._accept_external_files and can_extract_dropped_files(event.mimeData()):
            _set_state_property(self, "dropTarget", True)
            event.acceptProposedAction()
            return
        _set_state_property(self, "dropTarget", None)
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        _set_state_property(self, "dropTarget", None)
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        if self._accept_external_files and can_extract_dropped_files(event.mimeData()):
            _set_state_property(self, "dropTarget", True)
            event.acceptProposedAction()
            return
        _set_state_property(self, "dropTarget", None)
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        _set_state_property(self, "dropTarget", None)
        if not self._accept_external_files:
            super().dropEvent(event)
            return
        dropped_files = extract_dropped_files(event.mimeData())
        if not dropped_files.paths:
            super().dropEvent(event)
            return
        payload = dropped_files.transfer()
        try:
            self.filesDroppedToFolder.emit(self.app_data, payload)
        finally:
            if not payload.claimed:
                payload.cleanup()
        event.acceptProposedAction()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        edit_action = menu.addAction(glyph_icon("edit"), "Редактировать")
        open_folder_action = menu.addAction(glyph_icon("folder-open"), "Открыть расположение")
        current_hotkey = (self.app_data.get("local_hotkey") or "").strip()
        if current_hotkey:
            hotkey_action = menu.addAction(glyph_icon("keyboard"), f"Изменить горячую клавишу ({current_hotkey})")
        else:
            hotkey_action = menu.addAction(glyph_icon("keyboard"), "Назначить горячую клавишу")
        clear_hotkey_action = None
        if current_hotkey:
            clear_hotkey_action = menu.addAction(glyph_icon("close"), "Удалить горячую клавишу")
        copy_link_action = None
        if self.app_data.get("type") == "url":
            copy_link_action = menu.addAction(glyph_icon("link"), "Скопировать ссылку")
        favorite_action = None
        if self.show_favorite:
            favorite_action = menu.addAction(
                glyph_icon("star"),
                "Закрепить" if not self.app_data.get("favorite") else "Открепить",
            )
        delete_action = None
        trash_action = None
        if self.default_group and self.current_group == self.default_group:
            trash_action = menu.addAction(glyph_icon("trash", active_colors().danger), "В мусор")
        else:
            delete_action = menu.addAction(glyph_icon("trash", active_colors().danger), "Удалить")
        move_menu = menu.addMenu(glyph_icon("move"), "Переместить в")
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
        elif action == hotkey_action:
            self.assignHotkeyRequested.emit(self.app_data)
        elif clear_hotkey_action and action == clear_hotkey_action:
            self.clearHotkeyRequested.emit(self.app_data)
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


class HotkeySlotWidget(QWidget):
    """Single slot in the hotkey HUD: app icon with hotkey shown in tooltip."""

    clicked = Signal(dict)

    def __init__(self, app_data: dict, parent=None):
        super().__init__(parent)
        self.app_data = app_data
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("role", "hudSlot")
        self.setAttribute(Qt.WA_StyledBackground, True)
        hotkey_text = format_hotkey_for_display(app_data.get("local_hotkey", ""))
        self.setToolTip(f"{app_data.get('name', '')}\n{hotkey_text}")
        self.setAccessibleName(f"{app_data.get('name', '')} {hotkey_text}")
        self.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        icon_label = ItemIconWidget(app_data, 28, self)
        layout.addWidget(icon_label, 0, Qt.AlignHCenter)

        self.setLayout(layout)
        self.setFixedSize(40, 40)
        self._set_hovered(False)

    def _set_hovered(self, hovered: bool) -> None:
        _set_state_property(self, "hovered", True if hovered else None)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.app_data)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit(self.app_data)
            event.accept()
            return
        super().keyPressEvent(event)

    def enterEvent(self, event):
        self._set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._set_hovered(False)
        super().leaveEvent(event)


class HotkeyHudWidget(QWidget):
    """Strip of HotkeySlotWidgets for apps that have local_hotkey assigned."""

    slot_clicked = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("role", "hudStrip")
        layout = QHBoxLayout()
        layout.setContentsMargins(TOKENS.spacing.md, 2, TOKENS.spacing.md, 2)
        layout.setSpacing(TOKENS.spacing.xs)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setLayout(layout)
        self._slots: list[HotkeySlotWidget] = []
        self.setVisible(False)

    def update_slots(self, items: list[dict]) -> None:
        layout = self.layout()
        for slot in self._slots:
            layout.removeWidget(slot)
            slot.deleteLater()
        self._slots.clear()

        hotkey_items = [item for item in items if (item.get("local_hotkey") or "").strip()]
        for item in hotkey_items:
            slot = HotkeySlotWidget(item, self)
            slot.clicked.connect(self.slot_clicked)
            layout.addWidget(slot)
            self._slots.append(slot)

        self.setVisible(bool(hotkey_items))


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setObjectName("titleBar")
        self.setFixedHeight(TOKENS.sizes.title_bar_height)

        from PySide6.QtWidgets import QHBoxLayout  # lazy import to avoid circular deps

        layout = QHBoxLayout()
        layout.setContentsMargins(
            TOKENS.spacing.lg,
            TOKENS.spacing.none,
            TOKENS.spacing.sm,
            TOKENS.spacing.none,
        )
        layout.setSpacing(TOKENS.spacing.xs)

        self.mark_label = QLabel()
        self.mark_label.setFixedSize(18, 18)
        app = QApplication.instance()
        window_icon = parent.windowIcon() if not parent.windowIcon().isNull() else (
            app.windowIcon() if app is not None else QIcon()
        )
        if not window_icon.isNull():
            self.mark_label.setPixmap(window_icon.pixmap(18, 18))
        else:
            self.mark_label.setVisible(False)
        layout.addWidget(self.mark_label)
        layout.addSpacing(TOKENS.spacing.xs)

        title_label = QLabel("AppLauncher")
        title_label.setProperty("role", "windowTitle")
        layout.addWidget(title_label)
        layout.addStretch()

        # Header actions (Меню, Настройки) are inserted here by add_action().
        self._actions_index = layout.count()
        layout.addSpacing(TOKENS.spacing.sm)

        min_btn = GlyphButton("minus", tooltip="Свернуть")
        min_btn.setProperty("role", "titleButton")
        min_btn.setProperty("variant", "ghost")
        min_btn.clicked.connect(parent.showMinimized)
        layout.addWidget(min_btn)

        max_btn = GlyphButton("maximize", glyph_size=14, tooltip="Развернуть")
        max_btn.setProperty("role", "titleButton")
        max_btn.setProperty("variant", "ghost")
        max_btn.clicked.connect(self.toggle_maximize)
        layout.addWidget(max_btn)

        close_btn = GlyphButton("close", tooltip="Свернуть в трей")
        close_btn.setProperty("role", "titleButton")
        close_btn.setProperty("variant", "danger")
        close_btn.clicked.connect(self.close_to_tray)
        layout.addWidget(close_btn)

        self.min_button = min_btn
        self.max_button = max_btn
        self.close_button = close_btn
        parent.installEventFilter(self)
        self._sync_window_actions()

        self.setLayout(layout)
        self.start = None

    def add_action(self, widget: QWidget) -> None:
        """Place a header action (e.g. Меню, Настройки) to the left of the window buttons."""
        widget.setProperty("role", "titleAction")
        widget.setFocusPolicy(Qt.StrongFocus)
        if isinstance(widget, QPushButton):
            widget.setToolTip(widget.text())
            widget.setAccessibleName(widget.text())
        self.layout().insertWidget(self._actions_index, widget)
        self._actions_index += 1

    def _sync_window_actions(self):
        maximized = self.parent.isMaximized()
        text = "Восстановить" if maximized else "Развернуть"
        self.max_button.set_glyph("restore" if maximized else "maximize")
        self.max_button.setToolTip(text)
        self.max_button.setAccessibleName(text)
        has_tray = getattr(self.parent, "tray_available", False) and getattr(self.parent, "tray_icon", None)
        close_text = "Свернуть в трей" if has_tray else "Закрыть"
        self.close_button.setToolTip(close_text)
        self.close_button.setAccessibleName(close_text)

    def eventFilter(self, obj, event):
        if obj is self.parent and event.type() == QEvent.WindowStateChange:
            self._sync_window_actions()
        return super().eventFilter(obj, event)

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
