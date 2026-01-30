"""Notes widget for managing text notes with masked fragments."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..layouts import FlowLayout
from ..styles import TOKENS
from ...services.launcher_service import LauncherService


@dataclass(frozen=True)
class MaskedRange:
    start: int
    end: int


class NoteTextEdit(QTextEdit):
    """Text editor with masked spoiler ranges."""

    maskedRangesChanged = Signal(list)
    textEdited = Signal(str)

    def __init__(self, text: str, masked_ranges: Iterable[dict], parent=None) -> None:
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setProperty("role", "noteText")
        self._masked_ranges = self._normalize_ranges(masked_ranges)
        self._revealed_ranges: set[tuple[int, int]] = set()
        self._suspend_range_updates = True
        self.setPlainText(text)
        self._suspend_range_updates = False
        self._masked_ranges = self._clamp_ranges(self._masked_ranges)
        self.document().contentsChange.connect(self._on_contents_change)
        self.textChanged.connect(self._on_text_changed)
        self.verticalScrollBar().valueChanged.connect(self._reset_revealed)
        self._apply_mask_format()

    @property
    def masked_ranges(self) -> list[dict]:
        return [{"start": item.start, "end": item.end} for item in self._masked_ranges]

    def contextMenuEvent(self, event) -> None:
        menu = self.createStandardContextMenu()
        if self.textCursor().hasSelection():
            mask_action = menu.addAction("Замаскировать")
            mask_action.triggered.connect(self._mask_selection)
        menu.exec(event.globalPos())

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._reset_revealed()

    def mouseDoubleClickEvent(self, event) -> None:
        cursor = self.cursorForPosition(event.position().toPoint())
        position = cursor.position()
        target = self._range_at(position)
        if target is None:
            super().mouseDoubleClickEvent(event)
            return
        key = (target.start, target.end)
        if key in self._revealed_ranges:
            self._revealed_ranges.remove(key)
        else:
            self._revealed_ranges.add(key)
        self._apply_mask_format()

    def wheelEvent(self, event) -> None:
        self._reset_revealed()
        super().wheelEvent(event)

    def _mask_selection(self) -> None:
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        if end <= start:
            return
        self._masked_ranges = self._merge_ranges(
            [*self._masked_ranges, MaskedRange(start=start, end=end)]
        )
        self._revealed_ranges.clear()
        self._apply_mask_format()
        self.maskedRangesChanged.emit(self.masked_ranges)

    def _on_text_changed(self) -> None:
        self.textEdited.emit(self.toPlainText())

    def _on_contents_change(self, position: int, chars_removed: int, chars_added: int) -> None:
        if self._suspend_range_updates:
            return
        if not self._masked_ranges:
            return
        self._masked_ranges = self._clamp_ranges(
            self._adjust_ranges(self._masked_ranges, position, chars_removed, chars_added)
        )
        self._revealed_ranges.clear()
        self._apply_mask_format()
        self.maskedRangesChanged.emit(self.masked_ranges)

    def _adjust_ranges(
        self, ranges: list[MaskedRange], position: int, chars_removed: int, chars_added: int
    ) -> list[MaskedRange]:
        delta = chars_added - chars_removed
        change_end = position + chars_removed
        adjusted: list[MaskedRange] = []
        for item in ranges:
            start = item.start
            end = item.end
            if end <= position:
                adjusted.append(item)
                continue
            if start >= change_end:
                adjusted.append(MaskedRange(start=start + delta, end=end + delta))
                continue
            new_start = start
            if start >= position:
                new_start = position + chars_added
            new_end = end + delta
            if new_end < new_start:
                new_end = new_start
            if new_end > new_start:
                adjusted.append(MaskedRange(start=new_start, end=new_end))
        return self._merge_ranges(adjusted)

    def _apply_mask_format(self) -> None:
        selections = []
        mask_dot_color = QColor(170, 170, 170)
        mask_text_color = QColor(0, 0, 0, 0)
        mask_brush = QBrush(mask_dot_color, Qt.Dense6Pattern)
        for item in self._masked_ranges:
            key = (item.start, item.end)
            if key in self._revealed_ranges:
                continue
            cursor = self.textCursor()
            cursor.setPosition(item.start)
            cursor.setPosition(item.end, QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setBackground(mask_brush)
            fmt.setForeground(mask_text_color)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = fmt
            selections.append(selection)
        self.setExtraSelections(selections)

    def _reset_revealed(self) -> None:
        if not self._revealed_ranges:
            return
        self._revealed_ranges.clear()
        self._apply_mask_format()

    def _range_at(self, position: int) -> MaskedRange | None:
        for item in self._masked_ranges:
            if item.start <= position < item.end:
                return item
        return None

    def _normalize_ranges(self, ranges: Iterable[dict]) -> list[MaskedRange]:
        normalized: list[MaskedRange] = []
        for entry in ranges or []:
            if not isinstance(entry, dict):
                continue
            try:
                start = int(entry.get("start", 0))
                end = int(entry.get("end", 0))
            except (TypeError, ValueError):
                continue
            if end <= start or start < 0:
                continue
            normalized.append(MaskedRange(start=start, end=end))
        return self._merge_ranges(normalized)

    def _merge_ranges(self, ranges: list[MaskedRange]) -> list[MaskedRange]:
        if not ranges:
            return []
        ordered = sorted(ranges, key=lambda item: (item.start, item.end))
        merged = [ordered[0]]
        for item in ordered[1:]:
            last = merged[-1]
            if item.start <= last.end:
                merged[-1] = MaskedRange(start=last.start, end=max(last.end, item.end))
            else:
                merged.append(item)
        return merged

    def _clamp_ranges(self, ranges: list[MaskedRange]) -> list[MaskedRange]:
        text_length = len(self.toPlainText())
        clamped: list[MaskedRange] = []
        for item in ranges:
            start = max(0, min(item.start, text_length))
            end = max(0, min(item.end, text_length))
            if end > start:
                clamped.append(MaskedRange(start=start, end=end))
        return self._merge_ranges(clamped)


class NoteTile(QWidget):
    """Single note tile with editable text and delete control."""

    deleteRequested = Signal(str)
    noteUpdated = Signal(str, dict)

    def __init__(self, note_data: dict, parent=None) -> None:
        super().__init__(parent)
        self.note_id = note_data["id"]
        self._collapsed = bool(note_data.get("collapsed", False))
        self.setProperty("role", "noteTile")
        self.setMinimumSize(220, 170)
        self.setMaximumWidth(320)

        layout = QVBoxLayout()
        layout.setContentsMargins(TOKENS.spacing.md, TOKENS.spacing.md, TOKENS.spacing.md, TOKENS.spacing.md)
        layout.setSpacing(TOKENS.spacing.sm)
        self.setLayout(layout)

        header = QHBoxLayout()
        toggle_btn = QToolButton()
        toggle_btn.setCheckable(True)
        toggle_btn.setChecked(not self._collapsed)
        toggle_btn.setProperty("role", "noteToggle")
        toggle_btn.toggled.connect(self._toggle_collapsed)
        self._update_toggle_icon(toggle_btn, not self._collapsed)

        title = QLineEdit(note_data.get("title", ""))
        title.setPlaceholderText("Название заметки")
        title.setProperty("role", "noteTitleInput")
        title.textChanged.connect(self._emit_update)
        delete_btn = QToolButton()
        delete_btn.setText("✕")
        delete_btn.setProperty("role", "noteDelete")
        delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self.note_id))
        header.addWidget(toggle_btn)
        header.addWidget(title, 1)
        header.addWidget(delete_btn)
        layout.addLayout(header)

        self.text_edit = NoteTextEdit(note_data.get("text", ""), note_data.get("masked_ranges", []))
        self.text_edit.textEdited.connect(self._emit_update)
        self.text_edit.maskedRangesChanged.connect(self._emit_update)
        self.text_edit.setVisible(not self._collapsed)
        layout.addWidget(self.text_edit)
        self._title_input = title
        self._toggle_btn = toggle_btn

    def _emit_update(self, *_args) -> None:
        payload = {
            "id": self.note_id,
            "title": self._title_input.text().strip(),
            "text": self.text_edit.toPlainText(),
            "masked_ranges": self.text_edit.masked_ranges,
            "collapsed": self._collapsed,
        }
        self.noteUpdated.emit(self.note_id, payload)

    def _toggle_collapsed(self, expanded: bool) -> None:
        self._collapsed = not expanded
        self.text_edit.setVisible(expanded)
        self._update_toggle_icon(self._toggle_btn, expanded)
        self._emit_update()

    def _update_toggle_icon(self, button: QToolButton, expanded: bool) -> None:
        button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)


class NotesWidget(QWidget):
    """Widget that manages a collection of notes."""

    notesChanged = Signal()

    def __init__(self, service: LauncherService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.setObjectName("notesWidget")

        layout = QVBoxLayout()
        layout.setContentsMargins(*TOKENS.layout.content_margins)
        layout.setSpacing(TOKENS.layout.content_spacing)
        self.setLayout(layout)

        header_layout = QHBoxLayout()
        title = QLabel("Заметки")
        title.setProperty("role", "sectionTitle")
        add_btn = QPushButton("Добавить заметку")
        add_btn.setProperty("variant", "accent")
        add_btn.clicked.connect(self.add_note)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(add_btn)
        layout.addLayout(header_layout)

        self.tiles_container = QWidget()
        self.tiles_layout = FlowLayout(
            self.tiles_container,
            margin=TOKENS.layout.grid_layout_margin,
            h_spacing=TOKENS.layout.grid_layout_spacing,
            v_spacing=TOKENS.layout.grid_layout_spacing,
        )
        self.tiles_container.setLayout(self.tiles_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.tiles_container)
        layout.addWidget(self.scroll_area)

        self.reload_notes()

    def reload_notes(self) -> None:
        self._clear_tiles()
        for note in self.service.notes_repository.notes:
            self._add_tile(note)

    def add_note(self) -> None:
        note = self.service.add_note({"title": "", "text": "", "masked_ranges": [], "collapsed": False})
        self._add_tile(note)
        self.notesChanged.emit()

    def delete_note(self, note_id: str) -> None:
        self.service.delete_note(note_id)
        self._remove_tile(note_id)
        self.notesChanged.emit()

    def update_note(self, note_id: str, note_data: dict) -> None:
        self.service.update_note(note_id, note_data)
        self.notesChanged.emit()

    def _add_tile(self, note: dict) -> None:
        tile = NoteTile(note)
        tile.deleteRequested.connect(self.delete_note)
        tile.noteUpdated.connect(self.update_note)
        self.tiles_layout.addWidget(tile)

    def _remove_tile(self, note_id: str) -> None:
        for index in range(self.tiles_layout.count()):
            item = self.tiles_layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, NoteTile) and widget.note_id == note_id:
                removed = self.tiles_layout.takeAt(index)
                if removed:
                    removed.widget().deleteLater()
                return

    def _clear_tiles(self) -> None:
        while self.tiles_layout.count():
            item = self.tiles_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
