"""Notes widget with sticky-note cards and Telegram-style spoiler support."""
from __future__ import annotations

from collections.abc import Callable
import base64
import json
from math import ceil
import random
import re
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
    QToolTip,
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
    QTextOption,
    QTransform,
    QWheelEvent,
)

from ..glyphs import GlyphButton
from ..styles import TOKENS

SPOILER_LEGACY_FG = QColor("#d1d5db")
SPOILER_BG = QColor("#9ca3af")
SPOILER_FG = QColor(SPOILER_BG)
SPOILER_META_PROP = int(QTextFormat.UserProperty) + 1
SPOILER_FOREGROUND_PROP = SPOILER_META_PROP + 1
SPOILER_BACKGROUND_PROP = SPOILER_META_PROP + 2
NOTE_MIN_WIDTH = 280
LINE_SEPARATOR = "\u2028"
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
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self._spoiler_rects_cache: list[QRect] = []
        self._overlay = _SpoilerOverlay(self)
        self.textChanged.connect(self._schedule_refresh)
        self.verticalScrollBar().valueChanged.connect(self._schedule_refresh)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(0)
        self._refresh_timer.timeout.connect(self._refresh_overlay)
        self._last_double_click: tuple[int, QPoint] | None = None
        self._context_menu_open = False

    def setHtml(self, text: str) -> None:
        """Load old notes and optional colour metadata within the same HTML field."""
        super().setHtml(text)
        self._enable_line_wrapping()
        match = re.search(r'<meta name="applauncher-spoiler-styles" content="([\w=-]+)"\s*/?>', text)
        if not match:
            return
        try:
            records = json.loads(base64.urlsafe_b64decode(match.group(1)))
            if not isinstance(records, list):
                return
            blocker = QSignalBlocker(self)
            for record in records:
                start, length, foreground, background = record
                if not isinstance(start, int) or not isinstance(length, int):
                    continue
                if start < 0 or length <= 0 or start + length >= self.document().characterCount():
                    continue
                if not all(value == "none" or QColor(value).isValid() for value in (foreground, background)):
                    continue
                cursor = QTextCursor(self.document())
                cursor.setPosition(start)
                cursor.setPosition(start + length, QTextCursor.KeepAnchor)
                if not self._is_hidden(cursor.charFormat()):
                    continue
                fmt = QTextCharFormat()
                fmt.setProperty(SPOILER_FOREGROUND_PROP, foreground)
                fmt.setProperty(SPOILER_BACKGROUND_PROP, background)
                fmt.setProperty(SPOILER_META_PROP, True)
                cursor.mergeCharFormat(fmt)
            del blocker
        except (ValueError, TypeError, KeyError):
            return

    def _enable_line_wrapping(self):
        # Pasted HTML can carry white-space:pre, overriding QTextEdit's wrap mode.
        block = self.document().begin()
        while block.isValid():
            fmt = block.blockFormat()
            if fmt.nonBreakableLines():
                fmt.setNonBreakableLines(False)
                QTextCursor(block).setBlockFormat(fmt)
            block = block.next()

    def insertFromMimeData(self, source):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        super().insertFromMimeData(source)
        self._enable_line_wrapping()
        cursor.endEditBlock()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self.viewport().rect())
        self.refresh_overlay_now()

    def showEvent(self, event):
        super().showEvent(event)
        QApplication.instance().installEventFilter(self)
        self.refresh_overlay_now()

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        self.remask_revealed_spoilers()
        super().hideEvent(event)
        self._refresh_timer.stop()
        self._overlay.stop()

    def eventFilter(self, obj, event):
        # Listen at application level: clicking blank space or another card may
        # leave keyboard focus in this text edit, so focusOutEvent is not enough.
        if event.type() == QEvent.MouseButtonPress and self.isVisible() and self.has_revealed_spoilers():
            position = None
            if obj is self.viewport() or obj is self:
                point = self.viewport().mapFromGlobal(event.globalPosition().toPoint())
                position = self._spoiler_position_at(point)
            if position is not None:
                cursor = QTextCursor(self.document())
                cursor.setPosition(position)
                cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
                if not self._is_hidden(cursor.charFormat()):
                    return super().eventFilter(obj, event)
            self.remask_revealed_spoilers()
        elif event.type() == QEvent.ApplicationDeactivate and self.isVisible():
            self.remask_revealed_spoilers()
        return super().eventFilter(obj, event)

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

    def _create_context_menu(self):
        menu = self.createStandardContextMenu()
        menu.setCursor(Qt.ArrowCursor)
        cursor = self.textCursor()
        if cursor.hasSelection():
            menu.addSeparator()
            mask_action = menu.addAction("Скрыть")
            mask_action.setData("note-hide")
            if self._selected_spoiler_ranges():
                menu.addAction("Раскрыть").setData("note-unhide")
        return menu

    def contextMenuEvent(self, event):
        # A right click does not select text in QTextEdit. Offer spoiler actions
        # for the fragment under the pointer even without a prior selection.
        cursor = self.textCursor()
        if not cursor.hasSelection():
            point = event.pos() if event.reason() == QContextMenuEvent.Mouse else self.cursorRect().center()
            position = self._spoiler_position_at(point)
            if position is not None:
                start, end = self._spoiler_range_at(position)
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                self.setTextCursor(cursor)
        selection = QTextCursor(self.textCursor())
        menu = self._create_context_menu()
        self._context_menu_open = True
        # Windows can retain the viewport's I-beam while a nested popup has the
        # mouse grab. Push/pop an override rather than inheriting that cursor.
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        try:
            action = menu.exec(event.globalPos())
            # Apply formatting after the native menu has released focus/mouse
            # capture, using the selection that the user opened the menu for.
            if action is not None and action.data() in ("note-hide", "note-unhide"):
                self.setTextCursor(selection)
                if action.data() == "note-hide":
                    self._mask_selection()
                else:
                    self._unmask_selection()
        finally:
            QApplication.restoreOverrideCursor()
            self._context_menu_open = False
            menu.deleteLater()

    def _mask_selection(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        self._apply_spoiler_state(cursor.selectionStart(), cursor.selectionEnd(), hidden=True, emit_signal=True)
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.refresh_overlay_now()

    def _selected_spoiler_ranges(self, *, hidden_only=False):
        selection = self.textCursor()
        start, end = selection.selectionStart(), selection.selectionEnd()
        ranges = []
        block = self.document().findBlock(start)
        while block.isValid() and block.position() < end:
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and (self._is_hidden(fragment.charFormat()) if hidden_only else self._is_spoiler(fragment.charFormat())):
                    left = max(start, fragment.position())
                    right = min(end, fragment.position() + fragment.length())
                    if left < right:
                        ranges.append((left, right))
                iterator += 1
            block = block.next()
        return ranges

    def _unmask_selection(self):
        # Restore the original character styles and remove the spoiler marker.
        # Unlike a temporary reveal, this remains visible after clicking away.
        ranges = self._selected_spoiler_ranges()
        if not ranges:
            return
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        for start, end in ranges:
            self._apply_spoiler_state(start, end, hidden=False, emit_signal=False)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            fmt = cursor.charFormat()
            for prop in (SPOILER_META_PROP, SPOILER_FOREGROUND_PROP, SPOILER_BACKGROUND_PROP):
                fmt.clearProperty(prop)
            cursor.setCharFormat(fmt)
        cursor.endEditBlock()
        self.refresh_overlay_now()

    def mousePressEvent(self, event):
        if self._context_menu_open:
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._is_triple_click(event):
            self._last_double_click = None
            self.copy_line_at(event.position().toPoint())
            event.accept()
            return
        position = None
        if event.button() == Qt.LeftButton:
            position = self._spoiler_position_at(event.position().toPoint(), hidden_only=True)
        super().mousePressEvent(event)
        # Reveal on press, preserving Qt's selection anchor for dragging.
        if position is not None:
            self._reveal_at(position)

    def _reveal_selected_spoilers(self):
        # A drag can begin just beyond the hidden text (for example at the end
        # of an email). Reveal what the selection reaches, not only its origin.
        for start, _ in self._selected_spoiler_ranges(hidden_only=True):
            self._reveal_at(start)

    def mouseMoveEvent(self, event):
        if self._context_menu_open:
            event.accept()
            return
        super().mouseMoveEvent(event)
        if event.buttons() & Qt.LeftButton:
            self._reveal_selected_spoilers()

    def mouseReleaseEvent(self, event):
        if self._context_menu_open:
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self._reveal_selected_spoilers()

    def _spoiler_position_at(self, point: QPoint, *, hidden_only=False) -> int | None:
        # Hit the text itself, not the closest cursor on an adjacent line.
        block = self.document().begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    fmt = fragment.charFormat()
                    matches = self._is_hidden(fmt) if hidden_only else self._is_spoiler(fmt)
                    if matches and any(rect.contains(point) for rect in self._frag_rects(fragment.position(), fragment.length())):
                        position = self.cursorForPosition(point).position()
                        return max(fragment.position(), min(position, fragment.position() + fragment.length() - 1))
                iterator += 1
            block = block.next()
        return None

    def _remember_double_click(self, event: QMouseEvent) -> None:
        self._last_double_click = (event.timestamp(), event.position().toPoint())

    def _is_triple_click(self, event: QMouseEvent) -> bool:
        if self._last_double_click is None:
            return False
        stamp, pos = self._last_double_click
        if event.timestamp() - stamp > QApplication.doubleClickInterval():
            return False
        return (event.position().toPoint() - pos).manhattanLength() <= QApplication.startDragDistance()

    def copy_line_at(self, point: QPoint) -> str:
        """Select and copy the whole line under ``point``, spoilers included."""
        cursor = self.cursorForPosition(point)
        block = cursor.block()
        text = block.text()
        offset = cursor.position() - block.position()
        # Shift+Enter breaks stay inside one block as U+2028; each is its own line.
        start = text.rfind(LINE_SEPARATOR, 0, offset) + 1
        end = text.find(LINE_SEPARATOR, offset)
        if end < 0:
            end = len(text)
        line = text[start:end].replace("\u00a0", " ")
        if not line.strip():
            return ""
        cursor.setPosition(block.position() + start)
        cursor.setPosition(block.position() + end, QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)
        QApplication.clipboard().setText(line)
        QToolTip.showText(self.viewport().mapToGlobal(point), "Строка скопирована", self)
        return line

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._remember_double_click(event)
            cursor = self.cursorForPosition(event.position().toPoint())
            self.setFocus(Qt.MouseFocusReason)
            position = self._spoiler_position_at(event.position().toPoint())
            if position is not None:
                self._reveal_at(position)
            # A fresh cursor discards any anchor left on another line. Spoilers
            # use the same word selection as ordinary text after revealing.
            self._select_word_or_email(cursor)
            self.setTextCursor(cursor)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    @staticmethod
    def _select_word_or_email(cursor: QTextCursor):
        block = cursor.block()
        text = block.text()
        for match in re.finditer(r"[\w.+-]+@[\w.-]+", text):
            # QTextCursor positions count UTF-16 code units, not Python chars.
            start = block.position() + len(text[:match.start()].encode("utf-16-le")) // 2
            end = start + len(match.group().encode("utf-16-le")) // 2
            if start <= cursor.position() <= end:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                return
        cursor.select(QTextCursor.WordUnderCursor)

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
        color_records = []
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and self._is_spoiler(fragment.charFormat()):
                    ranges.append((fragment.position(), fragment.length()))
                    fmt = fragment.charFormat()
                    if fmt.hasProperty(SPOILER_FOREGROUND_PROP):
                        color_records.append([fragment.position(), fragment.length(),
                                              fmt.property(SPOILER_FOREGROUND_PROP),
                                              fmt.property(SPOILER_BACKGROUND_PROP)])
                iterator += 1
            block = block.next()
        for start, length in ranges:
            cursor = QTextCursor(document)
            cursor.setPosition(start)
            cursor.setPosition(start + length, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(self._spoiler_format(hidden=True))
        html = document.toHtml()
        if color_records:
            metadata = base64.urlsafe_b64encode(json.dumps(color_records).encode("utf-8")).decode("ascii")
            html = html.replace("</head>", f'<meta name="applauncher-spoiler-styles" content="{metadata}" /></head>', 1)
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
            # No explicit colour: revealed text follows the theme's text colour.
            fmt.setForeground(QBrush(Qt.NoBrush))
            fmt.setBackground(QBrush(Qt.NoBrush))
        return fmt

    def _apply_spoiler_state(self, start: int, end: int, *, hidden: bool, emit_signal: bool):
        if start >= end:
            return
        blocker = None if emit_signal else QSignalBlocker(self)
        segments = []
        block = self.document().findBlock(start)
        while block.isValid() and block.position() < end:
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                left = max(start, fragment.position())
                right = min(end, fragment.position() + fragment.length())
                if fragment.isValid() and left < right:
                    segments.append((left, right, fragment.charFormat()))
                iterator += 1
            block = block.next()
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        for left, right, original in segments:
            fmt = self._spoiler_format(hidden=hidden)
            legacy_hidden = self._is_hidden(original) and not original.hasProperty(SPOILER_FOREGROUND_PROP)
            for prop, brush in ((SPOILER_FOREGROUND_PROP, original.foreground()),
                                (SPOILER_BACKGROUND_PROP, original.background())):
                saved = original.property(prop)
                if saved is None:
                    saved = "none" if self._is_hidden(original) or brush.style() == Qt.NoBrush else brush.color().name(QColor.HexArgb)
                if not legacy_hidden:
                    fmt.setProperty(prop, saved)
                if not hidden:
                    restored = QBrush(Qt.NoBrush) if saved == "none" else QBrush(QColor(saved))
                    if prop == SPOILER_FOREGROUND_PROP:
                        fmt.setForeground(restored)
                    else:
                        fmt.setBackground(restored)
            cursor.setPosition(left)
            cursor.setPosition(right, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(fmt)
        cursor.endEditBlock()
        del blocker

    def _spoiler_range_at(self, pos: int) -> tuple[int, int]:
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

        return start, end

    def _reveal_at(self, pos: int):
        start, end = self._spoiler_range_at(pos)
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
        # Cursor rectangles jump to the next line at a wrap boundary. Use the
        # actual text layout so the final glyph is covered and adjacent lines
        # never acquire a stray mask rectangle.
        block = self.document().findBlock(start)
        layout = block.layout()
        bounds = self.document().documentLayout().blockBoundingRect(block)
        first = start - block.position()
        last = first + length
        rects = []
        for index in range(layout.lineCount()):
            line = layout.lineAt(index)
            left = max(first, line.textStart())
            right = min(last, line.textStart() + line.textLength())
            if left >= right:
                continue
            x1, _ = line.cursorToX(left)
            x2, _ = line.cursorToX(right)
            rect = QRectF(
                bounds.left() + min(x1, x2) - self.horizontalScrollBar().value(),
                bounds.top() + line.y() - self.verticalScrollBar().value(),
                abs(x2 - x1), line.height(),
            ).toAlignedRect()
            if not rect.isEmpty():
                rects.append(rect)
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
        self.setToolTip("Двойной клик по тексту — выделить; по пустому месту — редактировать; тройной — скопировать строку")
        self.setAccessibleName("Текст заметки")
        # The editor opens only once a third click (copy line) can no longer follow.
        self._edit_position = 0
        self._edit_timer = QTimer(self)
        self._edit_timer.setSingleShot(True)
        self._edit_timer.timeout.connect(lambda: self.editRequested.emit(self._edit_position))

    def sizeHint(self) -> QSize:
        return QSize(NOTE_MIN_WIDTH, self._display_height)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self._display_height)

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._is_triple_click(event):
            self._edit_timer.stop()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            point = event.position() + QPointF(self.horizontalScrollBar().value(), self.verticalScrollBar().value())
            if self.document().documentLayout().hitTest(point, Qt.ExactHit) >= 0:
                self._edit_timer.stop()
                super().mouseDoubleClickEvent(event)
                return
            self._remember_double_click(event)
            self._edit_position = self.cursorForPosition(event.position().toPoint()).position()
            self._edit_timer.start(QApplication.doubleClickInterval())
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _create_context_menu(self):
        self._edit_timer.stop()
        menu = super()._create_context_menu()
        menu.addSeparator()
        menu.addAction("Редактировать заметку", lambda: self.editRequested.emit(0))
        return menu


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
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

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
        close_button = GlyphButton("close", tooltip="Закрыть и сохранить")
        close_button.setProperty("variant", "ghost")
        close_button.setProperty("role", "iconButton")
        close_button.setFixedSize(28, 28)
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
            if self.content._context_menu_open:
                return super().event(event)
            active = QApplication.activePopupWidget()
            if active is None or active is self or not self._owns_widget(active):
                self.close()
        return super().event(event)

    def _owns_widget(self, widget: QObject) -> bool:
        # QWidget.isAncestorOf stops at popup windows, including our own QMenu.
        while widget is not None:
            if widget is self:
                return True
            widget = widget.parent()
        return False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if self.isVisible() and event.type() == QEvent.MouseButtonPress:
            inside = self.rect().contains(self.mapFromGlobal(event.globalPosition().toPoint()))
            child = self._owns_widget(obj)
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
    """Content-sized note that folds down to its header, with a popup editor."""

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
        layout.setSpacing(4)
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
        self.content.textChanged.connect(lambda: self.changed.emit(self.note_id))
        self.content.document().documentLayout().documentSizeChanged.connect(self._schedule_content_height)
        self._apply_collapsed()
        self._schedule_content_height()
        self._edit_shortcut = QShortcut(QKeySequence("F2"), self)
        self._edit_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._edit_shortcut.activated.connect(self.open_editor)


    def _build_header(self, note_data: dict) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(3)
        self.collapse_btn = GlyphButton("chevron-down", glyph_size=14)
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.setProperty("variant", "ghost")
        self.collapse_btn.setProperty("role", "iconButton")
        self.collapse_btn.clicked.connect(self.toggle_collapsed)
        header.addWidget(self.collapse_btn)

        self.title_input = QLineEdit(note_data.get("title", ""))
        self.title_input.setReadOnly(True)
        self.title_input.setPlaceholderText("Без заголовка")
        self.title_input.setMinimumWidth(0)
        self.title_input.setProperty("role", "noteTitleInput")
        self.title_input.setToolTip("Двойной клик по тексту — выделить; по пустому месту — редактировать")
        self.title_input.setAccessibleName("Заголовок заметки")
        self.title_input.installEventFilter(self)
        header.addWidget(self.title_input, 1)

        self.delete_btn = GlyphButton("trash", glyph_size=16, tooltip="Удалить заметку")
        self.delete_btn.setFixedSize(24, 24)
        self.delete_btn.setProperty("variant", "danger")
        self.delete_btn.setProperty("role", "iconButton")
        self.delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self.note_id))
        header.addWidget(self.delete_btn)
        return header

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.title_input and event.type() == QEvent.MouseButtonDblClick:
            if event.button() == Qt.LeftButton:
                text = self.title_input.text()
                caret = self.title_input.cursorRect()
                prefix = text.encode("utf-16-le")[:self.title_input.cursorPosition() * 2].decode("utf-16-le", errors="ignore")
                metrics = self.title_input.fontMetrics()
                left = caret.left() - metrics.horizontalAdvance(prefix)
                bounds = QRect(left, caret.top(), metrics.horizontalAdvance(text), caret.height())
                if text and bounds.contains(event.position().toPoint()):
                    return False  # Let QLineEdit select the title text normally.
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
        self._apply_collapsed()
        self._sync_content_height()
        self.updateGeometry()
        self.layoutChanged.emit()
        self.changed.emit(self.note_id)

    def _apply_collapsed(self) -> None:
        """A folded note keeps only its header row."""
        self.content.setVisible(not self._collapsed)
        self.layout().setContentsMargins(10, 8, 12, 8 if self._collapsed else 12)
        self.collapse_btn.set_glyph("chevron-right" if self._collapsed else "chevron-down")
        label = "Развернуть заметку" if self._collapsed else "Свернуть заметку"
        self.collapse_btn.setToolTip(label)
        self.collapse_btn.setAccessibleName(label)

    def _schedule_content_height(self, _size: QSizeF | None = None) -> None:
        self._height_timer.start(0)

    def _target_content_height(self) -> int:
        height = self.content.document().size().height()
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
        content_blocker = QSignalBlocker(self.content)
        self.title_input.setText(title)
        self.content.setHtml(content_html)
        del content_blocker
        del title_blocker
        self.content.refresh_overlay_now()
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
