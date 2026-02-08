"""Notes widget with sticky-note cards and Telegram-style spoiler support."""
import random
import uuid

from PySide6.QtWidgets import (
    QApplication,
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
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
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
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QTransform,
    QMouseEvent,
)

from ..styles import TOKENS

SPOILER_LEGACY_FG = QColor("#d1d5db")
SPOILER_BG = QColor("#9ca3af")
SPOILER_FG = QColor(SPOILER_BG)
SPOILER_META_PROP = int(QTextFormat.UserProperty) + 1
NOTE_WIDTH = TOKENS.sizes.grid_button[0] * 2 + TOKENS.layout.grid_layout_spacing
NOTE_CONTENT_MIN_HEIGHT = 60
NOTE_CONTENT_MAX_HEIGHT = 300
NOTE_TOGGLE_DURATION_MS = 180

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

        item_width = max(item.sizeHint().width() for item in items)
        avail = max(0, effective.width())

        if item_width <= 0:
            num_cols = 1
        else:
            num_cols = max(1, (avail + self._h_spacing) // (item_width + self._h_spacing))

        if num_cols > 1:
            remaining = max(0, avail - item_width * num_cols)
            spacing_x = max(float(self._h_spacing), remaining / float(num_cols - 1))
        else:
            spacing_x = 0.0

        col_y = [float(effective.y())] * num_cols

        for idx, item in enumerate(items):
            col = idx % num_cols
            hint = item.sizeHint()
            x = effective.x() + col * (item_width + spacing_x)
            y = col_y[col]

            if not test_only:
                item.setGeometry(QRect(QPoint(int(round(x)), int(round(y))), hint))

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
        self.setAcceptRichText(False)
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
            cursor = self.cursorForPosition(event.pos())
            if self._is_spoiler(cursor.charFormat()):
                self._reveal_at(cursor.position())
                return
        super().mouseDoubleClickEvent(event)

    @staticmethod
    def _is_spoiler(fmt: QTextCharFormat) -> bool:
        return bool(fmt.property(SPOILER_META_PROP)) or (
            fmt.foreground().color() == SPOILER_LEGACY_FG and fmt.background().color() == SPOILER_BG
        )

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


class NoteCard(QWidget):
    """Collapsible sticky-note card with title and spoiler-enabled content."""

    changed = Signal(str)
    layoutChanged = Signal()
    deleteRequested = Signal(str)

    def __init__(self, note_data: dict, parent=None):
        super().__init__(parent)
        self.note_id = note_data.get("id", str(uuid.uuid4()))
        self._collapsed = note_data.get("collapsed", False)
        self._app = QApplication.instance()
        self.setProperty("role", "noteCard")
        self.setFixedWidth(NOTE_WIDTH)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            TOKENS.spacing.sm,
            TOKENS.spacing.sm,
            TOKENS.spacing.sm,
            TOKENS.spacing.sm,
        )
        layout.setSpacing(TOKENS.spacing.xs)

        header = QHBoxLayout()
        header.setSpacing(TOKENS.spacing.xs)

        self.collapse_btn = QPushButton("\u25be" if not self._collapsed else "\u25b8")
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.setProperty("variant", "ghost")
        self.collapse_btn.setCursor(Qt.PointingHandCursor)
        self.collapse_btn.clicked.connect(self.toggle_collapsed)
        header.addWidget(self.collapse_btn)

        self.title_input = QLineEdit()
        self.title_input.setText(note_data.get("title", ""))
        self.title_input.setPlaceholderText("Заголовок...")
        self.title_input.setProperty("role", "noteTitleInput")
        self.title_input.textChanged.connect(self._on_changed)
        header.addWidget(self.title_input)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedSize(24, 24)
        self.delete_btn.setProperty("variant", "danger")
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setToolTip("Удалить заметку")
        self.delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self.note_id))
        header.addWidget(self.delete_btn)

        layout.addLayout(header)

        self.content = SpoilerTextEdit()
        self.content.setPlaceholderText("Текст заметки...")
        self.content.setMinimumHeight(0)
        self.content.setMaximumHeight(NOTE_CONTENT_MAX_HEIGHT)
        self.content.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._content_v_scroll_policy = Qt.ScrollBarAsNeeded
        self.content.setVerticalScrollBarPolicy(self._content_v_scroll_policy)
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        content_html = note_data.get("content_html", "")
        if content_html:
            self.content.setHtml(content_html)
        self.content.textChanged.connect(self._on_changed)
        layout.addWidget(self.content)

        self.setLayout(layout)

        self._change_timer = QTimer(self)
        self._change_timer.setSingleShot(True)
        self._change_timer.setInterval(500)
        self._change_timer.timeout.connect(lambda: self.changed.emit(self.note_id))

        self._toggle_animation = QPropertyAnimation(self.content, b"maximumHeight", self)
        self._toggle_animation.setDuration(NOTE_TOGGLE_DURATION_MS)
        self._toggle_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._toggle_animation.valueChanged.connect(self._on_toggle_step)
        self._toggle_animation.finished.connect(self._on_toggle_finished)
        if self._app is not None:
            self._app.installEventFilter(self)

        if self._collapsed:
            self.content.setMaximumHeight(0)
            self.content.hide()
        else:
            QTimer.singleShot(0, self._sync_content_height)

    def closeEvent(self, event):
        if self._app is not None:
            self._app.removeEventFilter(self)
        super().closeEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and isinstance(event, QMouseEvent):
            if self.content.has_revealed_spoilers():
                local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                if not self.rect().contains(local_pos):
                    self.content.remask_revealed_spoilers()
        elif event.type() == QEvent.WindowDeactivate and self.content.has_revealed_spoilers():
            self.content.remask_revealed_spoilers()
        return super().eventFilter(obj, event)

    def _on_changed(self):
        if not self._collapsed and self._toggle_animation.state() != QAbstractAnimation.Running:
            self._sync_content_height()
        self._change_timer.start()

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self.collapse_btn.setText("\u25b8" if self._collapsed else "\u25be")
        self._start_toggle_animation()
        self.changed.emit(self.note_id)

    def _target_content_height(self) -> int:
        doc_height = int(round(self.content.document().size().height()))
        chrome_height = self.content.frameWidth() * 2 + TOKENS.spacing.md
        target = doc_height + chrome_height
        return max(NOTE_CONTENT_MIN_HEIGHT, min(NOTE_CONTENT_MAX_HEIGHT, target))

    def _sync_content_height(self):
        if self._collapsed:
            return
        target = self._target_content_height()
        if self.content.maximumHeight() != target:
            self.content.setMaximumHeight(target)
            self.adjustSize()
            self.updateGeometry()
            self.layoutChanged.emit()

    def _start_toggle_animation(self):
        self._toggle_animation.stop()
        self._set_content_scrollbars(visible=False)
        if self._collapsed:
            if not self.content.isVisible():
                self.content.show()
            start = max(0, self.content.height())
            if start == 0:
                start = self._target_content_height()
            end = 0
        else:
            self.content.show()
            start = max(0, self.content.maximumHeight())
            end = self._target_content_height()
            self.content.refresh_overlay_now()
        self.content.setMaximumHeight(start)
        self._toggle_animation.setStartValue(start)
        self._toggle_animation.setEndValue(end)
        self._toggle_animation.start()

    def _on_toggle_step(self, _value):
        self.adjustSize()
        self.updateGeometry()
        self.layoutChanged.emit()

    def _on_toggle_finished(self):
        if self._collapsed:
            self.content.setMaximumHeight(0)
            self.content.hide()
            self._set_content_scrollbars(visible=False)
        else:
            self.content.show()
            self._sync_content_height()
            self._set_content_scrollbars(visible=True)
        self.adjustSize()
        self.updateGeometry()
        self.layoutChanged.emit()

    def _set_content_scrollbars(self, visible: bool):
        self.content.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        if visible:
            self.content.setVerticalScrollBarPolicy(self._content_v_scroll_policy)
        else:
            self.content.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def get_data(self) -> dict:
        self.content.remask_revealed_spoilers()
        return {
            "id": self.note_id,
            "title": self.title_input.text(),
            "content_html": self.content.toHtml(),
            "collapsed": self._collapsed,
        }


class NotesWidget(QWidget):
    """Main container for the Notes section with masonry column layout."""

    notesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: list[NoteCard] = []

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
        card.title_input.setFocus()
        self.notesChanged.emit()

    def _create_card(self, note_data: dict) -> NoteCard:
        card = NoteCard(note_data, self.cards_container)
        card.changed.connect(self._on_card_changed)
        card.layoutChanged.connect(self._reflow_cards)
        card.deleteRequested.connect(self._delete_note)
        self._cards.append(card)
        self.cards_layout.addWidget(card)
        return card

    def _on_card_changed(self, _note_id: str):
        self._reflow_cards()
        self.notesChanged.emit()

    def _reflow_cards(self):
        self.cards_layout.invalidate()
        self.cards_layout.activate()
        self.cards_container.adjustSize()
        self.cards_container.updateGeometry()

    def _delete_note(self, note_id: str):
        for card in self._cards:
            if card.note_id == note_id:
                self._cards.remove(card)
                self.cards_layout.removeWidget(card)
                card.deleteLater()
                self._reflow_cards()
                self.notesChanged.emit()
                break

    def _clear_cards(self):
        for card in self._cards:
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._reflow_cards()

