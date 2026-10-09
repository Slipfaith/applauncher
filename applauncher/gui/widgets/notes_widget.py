"""Notes widget with sticky-note cards and Telegram-style spoiler support."""
from __future__ import annotations

from collections.abc import Callable
from math import ceil
import random
import uuid

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QSizeF,
    QSignalBlocker,
    Qt,
    Signal,
    QTimer,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPixmap,
    QFont,
    QContextMenuEvent,
    QHideEvent,
    QMouseEvent,
    QKeySequence,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QTransform,
    QWheelEvent,
)

from ..styles import TOKENS

SPOILER_LEGACY_FG = QColor("#d1d5db")
SPOILER_BG = QColor("#9ca3af")
SPOILER_FG = QColor(SPOILER_BG)
SPOILER_META_PROP = int(QTextFormat.UserProperty) + 1
NOTE_MIN_WIDTH = 280
NOTE_PREVIEW_LINES = 5
NOTE_EDITOR_SIZE = QSize(560, 400)

_NOISE_PIXMAP = None


class _MasonryLayout(QLayout):
    """Column-based masonry layout where each column flows independently."""

    def __init__(self, parent=None, margin=0, h_spacing=8, v_spacing=8):
        super().__init__(parent)
        if margin >= 0:
            self.setContentsMargins(margin, margin, margin, margin)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def removeWidget(self, widget):
        for index, item in enumerate(self._item_list):
            if item.widget() is widget:
                self.takeAt(index)
                return

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(+left, +top, -right, -bottom)
        items = self._item_list
        if not items:
            return top + bottom

        avail = max(0, effective.width())
        num_cols = max(1, (avail + self._h_spacing) // (NOTE_MIN_WIDTH + self._h_spacing))
        item_width = max(1, (avail - self._h_spacing * (num_cols - 1)) // num_cols)

        col_y = [float(effective.y())] * num_cols

        for idx, item in enumerate(items):
            col = idx % num_cols
            hint = item.sizeHint()
            x = effective.x() + col * (item_width + self._h_spacing)
            y = col_y[col]

            if not test_only:
                item.setGeometry(QRect(int(x), int(round(y)), item_width, hint.height()))

            col_y[col] = y + hint.height() + self._v_spacing

        max_h = max(col_y) - self._v_spacing if items else 0.0
        return int(max_h) - effective.y() + top + bottom


def _get_noise():
    global _NOISE_PIXMAP
    if _NOISE_PIXMAP is None:
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor("#d4d4d4"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        rng = random.Random(42)
        for _ in range(size * size // 5):
            x = rng.random() * size
            y = rng.random() * size
            r = rng.uniform(0.5, 1.3)
            alpha = rng.randint(90, 210)
            painter.setBrush(QColor(107, 114, 128, alpha))
            painter.drawEllipse(QPointF(x, y), r, r)
        painter.end()
        _NOISE_PIXMAP = pixmap
    return _NOISE_PIXMAP


class _SpoilerOverlay(QWidget):
    """Transparent overlay that draws animated noise over spoiler regions."""

    def __init__(self, text_edit: "SpoilerTextEdit"):
        super().__init__(text_edit.viewport())
        self._text_edit = text_edit
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self):
        if not self._timer.isActive():
            self._timer.start(80)
            self.show()
            self.raise_()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._offset = (self._offset + 1) % 64
        self.update()

    def paintEvent(self, event):
        rects = self._text_edit._spoiler_rects_cache
        if not rects:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        noise = _get_noise()
        brush = QBrush(noise)
        t = QTransform()
        t.translate(self._offset, self._offset * 0.7)
        brush.setTransform(t)
        for rect in rects:
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), 3, 3)
            painter.fillPath(path, brush)
        painter.end()


class SpoilerTextEdit(QTextEdit):
    """QTextEdit with Telegram-style animated spoiler support."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(True)
        self._spoiler_rects_cache: list[QRect] = []
        self._overlay = _SpoilerOverlay(self)
        self.textChanged.connect(self._schedule_refresh)
        self.verticalScrollBar().valueChanged.connect(self._schedule_refresh)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(0)
        self._refresh_timer.timeout.connect(self._refresh_overlay)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self.viewport().rect())
        self.refresh_overlay_now()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_overlay_now()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._refresh_timer.stop()
        self._overlay.stop()

    def _schedule_refresh(self):
        self._refresh_timer.start()

    def refresh_overlay_now(self):
        self._refresh_timer.stop()
        self._refresh_overlay()

    def _refresh_overlay(self):
        if not self.isVisible():
            self._overlay.stop()
            return
        self._overlay.setGeometry(self.viewport().rect())
        self._spoiler_rects_cache = self._compute_spoiler_rects()
        if self._spoiler_rects_cache:
            self._overlay.start()
            self._overlay.update()
        else:
            self._overlay.stop()

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        cursor = self.textCursor()
        if cursor.hasSelection():
            menu.addSeparator()
            mask_action = menu.addAction("Замаскировать")
            mask_action.triggered.connect(self._mask_selection)
        menu.exec(event.globalPos())
        menu.deleteLater()

    def _mask_selection(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        cursor.mergeCharFormat(self._spoiler_format(hidden=True))
        self.refresh_overlay_now()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.position().toPoint())
            self.setFocus(Qt.MouseFocusReason)
            if self._is_spoiler(cursor.charFormat()):
                self.setTextCursor(cursor)
                self._reveal_at(cursor.position())
            else:
                # A fresh cursor discards any anchor left on another line.
                cursor.select(QTextCursor.WordUnderCursor)
                self.setTextCursor(cursor)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    @staticmethod
    def _is_spoiler(fmt: QTextCharFormat) -> bool:
        return bool(fmt.property(SPOILER_META_PROP)) or (
            fmt.foreground().color() in (SPOILER_LEGACY_FG, SPOILER_FG)
            and fmt.background().color() == SPOILER_BG
        )

    def persisted_html(self) -> str:
        """Save spoilers hidden without changing the live cursor or undo history."""
        document = self.document().clone()
        block = document.begin()
        ranges = []
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and self._is_spoiler(fragment.charFormat()):
                    ranges.append((fragment.position(), fragment.length()))
                iterator += 1
            block = block.next()
        for start, length in ranges:
            cursor = QTextCursor(document)
            cursor.setPosition(start)
            cursor.setPosition(start + length, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(self._spoiler_format(hidden=True))
        html = document.toHtml()
        document.deleteLater()
        return html

    @classmethod
    def _is_hidden(cls, fmt: QTextCharFormat) -> bool:
        is_new_hidden = fmt.foreground().color() == SPOILER_FG and fmt.background().color() == SPOILER_BG
        is_legacy_hidden = fmt.foreground().color() == SPOILER_LEGACY_FG and fmt.background().color() == SPOILER_BG
        return (
            cls._is_spoiler(fmt)
            and (is_new_hidden or is_legacy_hidden)
        )

    @staticmethod
    def _spoiler_format(hidden: bool) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setProperty(SPOILER_META_PROP, True)
        if hidden:
            fmt.setForeground(SPOILER_FG)
            fmt.setBackground(SPOILER_BG)
        else:
            fmt.setForeground(QColor(TOKENS.colors.text_primary))
            fmt.setBackground(QBrush(Qt.NoBrush))
        return fmt

    def _apply_spoiler_state(self, start: int, end: int, *, hidden: bool, emit_signal: bool):
        if start >= end:
            return
        blocker = None if emit_signal else QSignalBlocker(self)
        cursor = QTextCursor(self.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(self._spoiler_format(hidden=hidden))
        del blocker

    def _reveal_at(self, pos: int):
        doc = self.document()
        total = doc.characterCount()
        start, end = pos, pos

        while start > 0:
            c = QTextCursor(doc)
            c.setPosition(start - 1)
            c.setPosition(start, QTextCursor.KeepAnchor)
            if not self._is_spoiler(c.charFormat()):
                break
            start -= 1

        while end < total - 1:
            c = QTextCursor(doc)
            c.setPosition(end)
            c.setPosition(end + 1, QTextCursor.KeepAnchor)
            if not self._is_spoiler(c.charFormat()):
                break
            end += 1

        if start == end:
            return
        self._apply_spoiler_state(start, end, hidden=False, emit_signal=False)
        self.refresh_overlay_now()

    def has_revealed_spoilers(self) -> bool:
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and self._is_spoiler(frag.charFormat()) and not self._is_hidden(frag.charFormat()):
                    return True
                it += 1
            block = block.next()
        return False

    def remask_revealed_spoilers(self):
        ranges: list[tuple[int, int]] = []
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and self._is_spoiler(frag.charFormat()) and not self._is_hidden(frag.charFormat()):
                    ranges.append((frag.position(), frag.position() + frag.length()))
                it += 1
            block = block.next()

        if not ranges:
            return
        for start, end in ranges:
            self._apply_spoiler_state(start, end, hidden=True, emit_signal=False)
        self.refresh_overlay_now()

    def _compute_spoiler_rects(self) -> list[QRect]:
        rects: list[QRect] = []
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and self._is_hidden(frag.charFormat()):
                    rects.extend(self._frag_rects(frag.position(), frag.length()))
                it += 1
            block = block.next()
        vp = self.viewport().rect()
        return [r for r in rects if vp.intersects(r)]

    def _frag_rects(self, start: int, length: int) -> list[QRect]:
        rects: list[QRect] = []
        cursor = QTextCursor(self.document())
        cursor.setPosition(start)
        prev = self.cursorRect(cursor)
        line_left = prev.left()
        cur_y = prev.top()
        cur_h = prev.height()
        last_right = prev.right()

        for i in range(1, length + 1):
            cursor.setPosition(start + i)
            r = self.cursorRect(cursor)
            if r.top() != cur_y:
                rects.append(QRect(line_left, cur_y, last_right - line_left, cur_h))
                line_left = r.left()
                cur_y = r.top()
                cur_h = r.height()
            last_right = r.right()

        if last_right > line_left:
            rects.append(QRect(line_left, cur_y, last_right - line_left, cur_h))
        return rects


class NotePreviewTextEdit(SpoilerTextEdit):
    """Read-only preview; the tab owns scrolling and double-click opens editing."""

    editRequested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._display_height = 60
        self.setReadOnly(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setToolTip("Двойной клик — редактировать заметку")
        self.setAccessibleName("Текст заметки")

    def sizeHint(self) -> QSize:
        return QSize(NOTE_MIN_WIDTH, self._display_height)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self._display_height)

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.editRequested.emit(self.cursorForPosition(event.position().toPoint()).position())
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction("Редактировать заметку", lambda: self.editRequested.emit(0))
        menu.exec(event.globalPos())
        menu.deleteLater()


class NoteEditorPopup(QDialog):
    """Floating rich-text editor that flushes changes before closing."""

    edited = Signal(str, str)
    dismissed = Signal()

    def __init__(self, note_data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Popup)
        self.setWindowTitle("Редактировать заметку")
        self.setObjectName("noteEditorPopup")
        self.setMinimumSize(360, 260)
        self.resize(NOTE_EDITOR_SIZE)
        self._last_payload = None
        self._dismissed = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        layout.addLayout(self._build_header(note_data))

        self.content = SpoilerTextEdit()
        self.content.setAccessibleName("Редактор заметки")
        self.content.setPlaceholderText("Текст заметки…")
        self.content.setHtml(note_data.get("content_html", ""))
        layout.addLayout(self._build_toolbar())
        layout.addWidget(self.content, 1)
        self._shortcuts = []
        for sequence, callback in (
            ("Ctrl+B", self.toggle_bold),
            ("Ctrl+I", self.toggle_italic),
            ("Ctrl+U", self.toggle_underline),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self.content)
            shortcut.setContext(Qt.WidgetShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)
        self.content.currentCharFormatChanged.connect(self._sync_format_buttons)
        self._sync_format_buttons()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self.flush_changes)
        self.content.textChanged.connect(self._save_timer.start)
        self.title_input.textChanged.connect(self._schedule_save)
        self._last_payload = (self.title_input.text(), self.content.persisted_html())
        self._app = QApplication.instance()
        if self._app is not None:
            self._app.installEventFilter(self)


    def _build_header(self, note_data: dict) -> QHBoxLayout:
        header = QHBoxLayout()
        self.title_input = QLineEdit(note_data.get("title", ""))
        self.title_input.setPlaceholderText("Заголовок заметки")
        self.title_input.setAccessibleName("Заголовок заметки")
        header.addWidget(self.title_input, 1)
        close_button = QPushButton("✕")
        close_button.setProperty("role", "iconButton")
        close_button.setFixedSize(28, 28)
        close_button.setToolTip("Закрыть и сохранить")
        close_button.setAccessibleName("Закрыть и сохранить")
        close_button.clicked.connect(self.close)
        header.addWidget(close_button)
        return header


    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        self.bold_button = self._format_button("B", "Жирный (Ctrl+B)", self.toggle_bold)
        self.italic_button = self._format_button("I", "Курсив (Ctrl+I)", self.toggle_italic)
        self.underline_button = self._format_button("U", "Подчёркнутый (Ctrl+U)", self.toggle_underline)
        for button in (self.bold_button, self.italic_button, self.underline_button):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        return toolbar

    def _schedule_save(self, _text: str) -> None:
        self._save_timer.start()

    def _format_button(self, label: str, tooltip: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(label)
        button.setProperty("role", "noteFormatButton")
        button.setFixedSize(30, 28)
        button.setCheckable(True)
        button.setFocusPolicy(Qt.NoFocus)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        font = button.font()
        font.setBold(label == "B")
        font.setItalic(label == "I")
        font.setUnderline(label == "U")
        button.setFont(font)
        button.clicked.connect(callback)
        return button

    def toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Normal if self.content.fontWeight() >= QFont.Bold else QFont.Bold)
        self._apply_format(fmt)

    def toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.content.fontItalic())
        self._apply_format(fmt)

    def toggle_underline(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.content.fontUnderline())
        self._apply_format(fmt)

    def _apply_format(self, fmt: QTextCharFormat) -> None:
        self.content.mergeCurrentCharFormat(fmt)
        self.content.setFocus(Qt.OtherFocusReason)
        self._sync_format_buttons()

    def _sync_format_buttons(self, _format: QTextCharFormat | None = None) -> None:
        self.bold_button.setChecked(self.content.fontWeight() >= QFont.Bold)
        self.italic_button.setChecked(self.content.fontItalic())
        self.underline_button.setChecked(self.content.fontUnderline())

    def flush_changes(self) -> None:
        self._save_timer.stop()
        payload = (self.title_input.text(), self.content.persisted_html())
        if payload != self._last_payload:
            self._last_payload = payload
            self.edited.emit(*payload)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.WindowDeactivate and self.isVisible():
            active = QApplication.activePopupWidget()
            if active is None or active is self or not self.isAncestorOf(active):
                self.close()
        return super().event(event)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if self.isVisible() and event.type() == QEvent.MouseButtonPress:
            inside = self.rect().contains(self.mapFromGlobal(event.globalPosition().toPoint()))
            child = isinstance(obj, QWidget) and self.isAncestorOf(obj)
            if not inside and not child:
                self.close()
        return super().eventFilter(obj, event)

    def hideEvent(self, event: QHideEvent) -> None:
        self.flush_changes()
        if self._app is not None:
            self._app.removeEventFilter(self)
        super().hideEvent(event)
        if not self._dismissed:
            self._dismissed = True
            self.dismissed.emit()


class NoteCard(QWidget):
    """Content-sized note with an optional five-line preview and popup editor."""

    changed = Signal(str)
    layoutChanged = Signal()
    deleteRequested = Signal(str)

    def __init__(self, note_data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.note_id = note_data.get("id", str(uuid.uuid4()))
        self._collapsed = bool(note_data.get("collapsed", False))
        self._editor: NoteEditorPopup | None = None
        self.setProperty("role", "noteCard")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setMinimumWidth(NOTE_MIN_WIDTH)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        layout.addLayout(self._build_header(note_data))

        self.content = NotePreviewTextEdit()
        self.content.setPlaceholderText("Двойной клик — добавить текст")
        self.content.setHtml(note_data.get("content_html", ""))
        self.content.editRequested.connect(self.open_editor)
        layout.addWidget(self.content)
        self._height_timer = QTimer(self)
        self._height_timer.setSingleShot(True)
        self._height_timer.timeout.connect(self._sync_content_height)
        self.content.textChanged.connect(self._schedule_content_height)
        self.content.document().documentLayout().documentSizeChanged.connect(self._schedule_content_height)
        self._update_collapse_button()
        self._schedule_content_height()
        self._edit_shortcut = QShortcut(QKeySequence("F2"), self)
        self._edit_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._edit_shortcut.activated.connect(self.open_editor)


    def _build_header(self, note_data: dict) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(3)
        self.collapse_btn = QPushButton()
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.setProperty("variant", "ghost")
        self.collapse_btn.setProperty("role", "iconButton")
        self.collapse_btn.setCursor(Qt.PointingHandCursor)
        self.collapse_btn.clicked.connect(self.toggle_collapsed)
        header.addWidget(self.collapse_btn)

        self.title_input = QLineEdit(note_data.get("title", ""))
        self.title_input.setReadOnly(True)
        self.title_input.setPlaceholderText("Без заголовка")
        self.title_input.setMinimumWidth(0)
        self.title_input.setProperty("role", "noteTitleInput")
        self.title_input.setToolTip("Двойной клик — редактировать заметку")
        self.title_input.setAccessibleName("Заголовок заметки")
        self.title_input.installEventFilter(self)
        header.addWidget(self.title_input, 1)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedSize(24, 24)
        self.delete_btn.setProperty("variant", "danger")
        self.delete_btn.setProperty("role", "iconButton")
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setToolTip("Удалить заметку")
        self.delete_btn.setAccessibleName("Удалить заметку")
        self.delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self.note_id))
        header.addWidget(self.delete_btn)
        return header

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.title_input and event.type() == QEvent.MouseButtonDblClick:
            if event.button() == Qt.LeftButton:
                self.open_editor()
                return True
        return super().eventFilter(obj, event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.open_editor()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self._update_collapse_button()
        cursor = self.content.textCursor()
        cursor.setPosition(0)
        self.content.setTextCursor(cursor)
        self.content.verticalScrollBar().setValue(0)
        self._sync_content_height()
        self.changed.emit(self.note_id)

    def _update_collapse_button(self) -> None:
        self.collapse_btn.setText("▸" if self._collapsed else "▾")
        label = "Развернуть полностью" if self._collapsed else "Свернуть до 5 строк"
        self.collapse_btn.setToolTip(label)
        self.collapse_btn.setAccessibleName(label)

    def _schedule_content_height(self, _size: QSizeF | None = None) -> None:
        self._height_timer.start(0)

    def _target_content_height(self) -> int:
        document = self.content.document()
        height = document.size().height()
        if self._collapsed:
            remaining = NOTE_PREVIEW_LINES
            block = document.begin()
            while block.isValid():
                text_layout = block.layout()
                count = text_layout.lineCount()
                if count >= remaining:
                    line = text_layout.lineAt(remaining - 1)
                    bounds = document.documentLayout().blockBoundingRect(block)
                    height = min(height, bounds.top() + line.y() + line.height())
                    break
                remaining -= count
                block = block.next()
        chrome = self.content.height() - self.content.viewport().height()
        return max(self.content.fontMetrics().height() + 8, ceil(height) + chrome)

    def _sync_content_height(self) -> None:
        target = self._target_content_height()
        if self.content._display_height != target:
            self.content._display_height = target
            self.content.setMinimumHeight(target)
            self.content.updateGeometry()
            self.updateGeometry()
            self.layoutChanged.emit()
        if self._collapsed:
            self.content.verticalScrollBar().setValue(0)

    def open_editor(self, position: int = 0) -> NoteEditorPopup:
        if self._editor is not None:
            self._editor.raise_()
            self._editor.content.setFocus()
            return self._editor
        active = QApplication.activePopupWidget()
        if isinstance(active, NoteEditorPopup):
            active.close()
        editor = NoteEditorPopup(self.get_data(), self)
        self._editor = editor
        editor.edited.connect(self._on_editor_edited)
        editor.dismissed.connect(self._on_editor_dismissed)
        screen = self.screen().availableGeometry()
        origin = self.mapToGlobal(QPoint(0, 0))
        x = max(screen.left(), min(origin.x(), screen.right() - editor.width() + 1))
        y = max(screen.top(), min(origin.y(), screen.bottom() - editor.height() + 1))
        editor.move(x, y)
        editor.show()
        cursor = editor.content.textCursor()
        cursor.setPosition(min(position, editor.content.document().characterCount() - 1))
        editor.content.setTextCursor(cursor)
        editor.content.setFocus()
        return editor

    def _on_editor_edited(self, title: str, content_html: str) -> None:
        title_blocker = QSignalBlocker(self.title_input)
        self.title_input.setText(title)
        self.content.setHtml(content_html)
        del title_blocker
        self._sync_content_height()
        self.changed.emit(self.note_id)

    def _on_editor_dismissed(self) -> None:
        editor = self._editor
        self._editor = None
        if editor is not None:
            editor.deleteLater()

    def get_data(self) -> dict:
        if self._editor is not None:
            self._editor.flush_changes()
        return {
            "id": self.note_id,
            "title": self.title_input.text(),
            "content_html": self.content.persisted_html(),
            "collapsed": self._collapsed,
        }


class NotesWidget(QWidget):
    """Main container for the Notes section with masonry column layout."""

    notesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: list[NoteCard] = []
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.timeout.connect(self._reflow_cards)

        layout = QVBoxLayout()
        layout.setContentsMargins(*TOKENS.layout.content_margins)
        layout.setSpacing(TOKENS.layout.content_spacing)

        controls = QHBoxLayout()
        controls.setSpacing(TOKENS.spacing.sm)

        add_btn = QPushButton("Добавить заметку")
        add_btn.setProperty("variant", "accent")
        add_btn.clicked.connect(self._add_note)
        controls.addWidget(add_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.cards_container = QWidget()
        self.cards_layout = _MasonryLayout(
            self.cards_container,
            margin=0,
            h_spacing=TOKENS.layout.grid_layout_spacing,
            v_spacing=TOKENS.layout.grid_layout_spacing,
        )
        self.cards_container.setLayout(self.cards_layout)
        self.scroll_area.setWidget(self.cards_container)

        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

    def set_notes(self, notes: list[dict]):
        self._clear_cards()
        for note in notes:
            self._create_card(note)
        self._reflow_cards()

    def get_notes(self) -> list[dict]:
        return [card.get_data() for card in self._cards]

    def _add_note(self):
        note_data = {
            "id": str(uuid.uuid4()),
            "title": "",
            "content_html": "",
            "collapsed": False,
        }
        card = self._create_card(note_data)
        card.open_editor().title_input.setFocus()
        self.notesChanged.emit()

    def _create_card(self, note_data: dict) -> NoteCard:
        card = NoteCard(note_data, self.cards_container)
        card.changed.connect(self._on_card_changed)
        card.layoutChanged.connect(self._schedule_reflow)
        card.deleteRequested.connect(self._delete_note)
        self._cards.append(card)
        self.cards_layout.addWidget(card)
        return card

    def _on_card_changed(self, _note_id: str):
        self._schedule_reflow()
        self.notesChanged.emit()

    def _schedule_reflow(self) -> None:
        self._reflow_timer.start(0)

    def _reflow_cards(self):
        self._reflow_timer.stop()
        self.cards_layout.invalidate()
        self.cards_layout.activate()
        viewport_width = max(1, self.scroll_area.viewport().width())
        self.cards_container.setMinimumHeight(self.cards_layout.heightForWidth(viewport_width))
        self.cards_container.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_reflow()

    def _delete_note(self, note_id: str):
        for card in self._cards:
            if card.note_id == note_id:
                if card._editor is not None:
                    card._editor.close()
                self._cards.remove(card)
                self.cards_layout.removeWidget(card)
                card.deleteLater()
                self._reflow_cards()
                self.notesChanged.emit()
                break

    def _clear_cards(self):
        for card in self._cards:
            if card._editor is not None:
                card._editor.close()
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._reflow_cards()
