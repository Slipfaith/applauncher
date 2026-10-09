"""Regression checks for note sizing, formatting and mouse selection."""
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QMimeData, QPoint, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from applauncher.gui.styles import apply_design_system
from applauncher.gui.widgets.notes_widget import NoteEditorPopup, NotesWidget, SpoilerTextEdit
from applauncher.services.launcher_service import LauncherService


@pytest.fixture
def notes():
    app = QApplication.instance() or QApplication([])
    # The Windows offscreen plugin does not discover system fonts itself.
    if not QFontDatabase.families():
        font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"):
            if (font_dir / name).exists():
                QFontDatabase.addApplicationFont(str(font_dir / name))
    app.setStyle("Fusion")
    apply_design_system(app)
    widget = NotesWidget()
    widget.resize(680, 440)
    widget.show()
    yield widget
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def settle():
    for _ in range(8):
        QApplication.processEvents()


def add_card(notes, text, *, collapsed=False):
    notes.set_notes([{"id": "note", "title": "Заметка", "collapsed": collapsed}])
    card = notes._cards[0]
    card.content.setPlainText(text)
    settle()
    return card


def select(editor, start, end):
    cursor = editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.KeepAnchor)
    editor.setTextCursor(cursor)
    return cursor


def char_format(editor, position):
    cursor = QTextCursor(editor.document())
    cursor.setPosition(position)
    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
    return cursor.charFormat()


def test_expanded_note_fits_all_text_without_inner_scrollbar(notes):
    card = add_card(notes, "\n".join(f"Строка {i}" for i in range(50)))
    assert card.content.height() > 300
    assert card.content.document().size().height() <= card.content.viewport().height()
    assert card.content.verticalScrollBar().maximum() == 0
    assert notes.scroll_area.verticalScrollBar().maximum() > 0


@pytest.mark.parametrize("initially_collapsed", [False, True])
def test_collapsed_note_shows_first_five_lines_and_preserves_text(notes, initially_collapsed):
    text = "\n".join(f"Строка {i}" for i in range(12))
    card = add_card(notes, text, collapsed=initially_collapsed)
    if not initially_collapsed:
        card.toggle_collapsed()
        settle()
    assert card.content.isVisible()
    fifth = card.content.document().findBlockByNumber(4)
    sixth = fifth.next()
    cursor = QTextCursor(fifth)
    assert card.content.cursorRect(cursor).bottom() < card.content.viewport().height()
    cursor = QTextCursor(sixth)
    assert card.content.cursorRect(cursor).top() >= card.content.viewport().height() - 2
    assert card.content.verticalScrollBar().value() == 0
    assert card.content.toPlainText() == text
    saved = card.get_data()
    assert saved["collapsed"] is True
    card.toggle_collapsed()
    settle()
    assert card.content.isReadOnly()
    assert card.content.verticalScrollBar().maximum() == 0
    assert card.content.toPlainText() == text
    notes.set_notes([saved])
    settle()
    assert notes._cards[0].content.isVisible()
    assert notes._cards[0].content.toPlainText() == text


def test_note_reflows_after_wrapping_and_editing_without_overlap(notes):
    notes.resize(980, 440)
    notes.set_notes([
        {"id": str(i), "content_html": "<p>" + "длинная заметка " * 30 + "</p>"}
        for i in range(6)
    ])
    settle()
    notes.resize(580, 440)
    settle()
    card = notes._cards[0]
    assert card.content.document().size().height() <= card.content.viewport().height()
    old_height = card.height()
    card.content.append("\n".join("Добавленная строка" for _ in range(15)))
    settle()
    assert card.height() > old_height
    for i, first in enumerate(notes._cards):
        for second in notes._cards[i + 1:]:
            assert not first.geometry().intersects(second.geometry())
    card.content.setPlainText("Короткий текст")
    settle()
    assert card.height() < old_height


def test_formatting_buttons_preserve_selection_and_survive_save(notes):
    card = add_card(notes, "выделено обычный")
    editor = card.open_editor()
    settle()
    cursor = select(editor.content, 0, 8)
    for button in (editor.bold_button, editor.italic_button, editor.underline_button):
        QTest.mouseClick(button, Qt.LeftButton)
        assert editor.content.textCursor().selectionStart() == cursor.selectionStart()
        assert editor.content.textCursor().selectionEnd() == cursor.selectionEnd()
    fmt = char_format(editor.content, 2)
    assert fmt.fontWeight() == QFont.Bold
    assert fmt.fontItalic() and fmt.fontUnderline()
    plain = char_format(editor.content, 11)
    assert plain.fontWeight() < QFont.Bold
    assert not plain.fontItalic() and not plain.fontUnderline()
    saved = notes.get_notes()
    notes.set_notes(saved)
    settle()
    restored = char_format(notes._cards[0].content, 2)
    assert restored.fontWeight() == QFont.Bold
    assert restored.fontItalic() and restored.fontUnderline()


def test_formatting_shortcuts_apply_to_new_text_and_support_undo(notes):
    card = add_card(notes, "")
    editor = card.open_editor()
    settle()
    for key in (Qt.Key_B, Qt.Key_I, Qt.Key_U):
        QTest.keyClick(editor.content, key, Qt.ControlModifier)
    QTest.keyClicks(editor.content, "new")
    fmt = char_format(editor.content, 1)
    assert fmt.fontWeight() == QFont.Bold
    assert fmt.fontItalic() and fmt.fontUnderline()
    editor.content.undo()
    assert editor.content.toPlainText() == ""
    editor.content.redo()
    assert editor.content.toPlainText() == "new"


def test_double_click_replaces_previous_selection_on_another_line(notes):
    card = add_card(notes, "верхняя строка\nнижняя цель здесь")
    editor = card.open_editor()
    settle()
    for start, expected in [(0, "верхняя"), (22, "цель"), (0, "верхняя"), (22, "цель")]:
        cursor = QTextCursor(editor.content.document())
        cursor.setPosition(start + 1)
        point = editor.content.cursorRect(cursor).center()
        QTest.mouseDClick(editor.content.viewport(), Qt.LeftButton, pos=point)
        QTest.mouseRelease(editor.content.viewport(), Qt.LeftButton, pos=point)
        assert editor.content.textCursor().selectedText() == expected


def test_rich_text_paste_and_spoilers_keep_character_styles(notes):
    card = add_card(notes, "secret plain")
    editor = card.open_editor()
    settle()
    select(editor.content, 0, 6)
    editor.content.setFontWeight(QFont.Bold)
    editor.content._mask_selection()
    assert SpoilerTextEdit._is_hidden(char_format(editor.content, 1))
    select(editor.content, 7, 12)
    cursor = QTextCursor(editor.content.document())
    cursor.setPosition(2)
    point = editor.content.cursorRect(cursor).center()
    QTest.mouseDClick(editor.content.viewport(), Qt.LeftButton, pos=point)
    QTest.mouseRelease(editor.content.viewport(), Qt.LeftButton, pos=point)
    assert not editor.content.textCursor().hasSelection()
    assert editor.content.has_revealed_spoilers()
    saved = card.get_data()
    restored = SpoilerTextEdit()
    restored.setHtml(saved["content_html"])
    assert SpoilerTextEdit._is_hidden(char_format(restored, 1))
    assert char_format(restored, 1).fontWeight() == QFont.Bold
    assert editor.content.acceptRichText()
    restored.deleteLater()


def test_double_click_opens_editor_and_focus_loss_flushes_changes(notes):
    card = add_card(notes, "исходный текст", collapsed=True)
    QTest.mouseDClick(card.content.viewport(), Qt.LeftButton)
    settle()
    editor = card._editor
    assert isinstance(editor, NoteEditorPopup)
    assert editor.isVisible()
    assert card.open_editor() is editor
    editor.title_input.setText("Новый заголовок")
    editor.content.setPlainText("Изменение перед закрытием")
    QApplication.sendEvent(editor, QEvent(QEvent.WindowDeactivate))
    assert not editor.isVisible()
    assert card._editor is None
    assert card.title_input.text() == "Новый заголовок"
    assert card.content.toPlainText() == "Изменение перед закрытием"
    assert card.get_data()["collapsed"] is True


def test_click_outside_editor_closes_and_saves(notes):
    card = add_card(notes, "before")
    editor = card.open_editor()
    settle()
    editor.content.setPlainText("saved on outside click")
    QTest.mouseClick(notes, Qt.LeftButton, pos=QPoint(notes.width() - 2, notes.height() - 2))
    assert card._editor is None
    assert card.content.toPlainText() == "saved on outside click"


def test_preview_counts_wrapped_visual_lines(notes):
    card = add_card(notes, "перенос строки " * 60, collapsed=True)
    block = card.content.document().begin()
    text_layout = block.layout()
    assert text_layout.lineCount() > 5
    cursor = QTextCursor(card.content.document())
    cursor.setPosition(text_layout.lineAt(4).textStart())
    assert card.content.cursorRect(cursor).bottom() < card.content.viewport().height()
    cursor.setPosition(text_layout.lineAt(5).textStart())
    assert card.content.cursorRect(cursor).top() >= card.content.viewport().height() - 1


def test_html_paste_preserves_bold_italic_and_underline(notes):
    card = add_card(notes, "")
    editor = card.open_editor()
    settle()
    mime_data = QMimeData()
    mime_data.setHtml("<p><b>bold</b> <i>italic</i> <u>underlined</u></p>")
    editor.content.insertFromMimeData(mime_data)
    editor.close()
    assert card.content.toPlainText() == "bold italic underlined"
    assert char_format(card.content, 1).fontWeight() == QFont.Bold
    assert char_format(card.content, 6).fontItalic()
    assert char_format(card.content, 14).fontUnderline()


def test_autosave_does_not_change_live_selection_or_revealed_spoilers(notes):
    card = add_card(notes, "secret plain")
    editor = card.open_editor()
    settle()
    select(editor.content, 0, 6)
    editor.content._mask_selection()
    editor.content._reveal_at(2)
    cursor = select(editor.content, 7, 12)
    editor.flush_changes()
    assert editor.content.has_revealed_spoilers()
    assert editor.content.textCursor().selectionStart() == cursor.selectionStart()
    assert editor.content.textCursor().selectionEnd() == cursor.selectionEnd()
    assert SpoilerTextEdit._is_hidden(char_format(card.content, 1))


def test_editor_changes_roundtrip_through_config(notes, tmp_path):
    card = add_card(notes, "original", collapsed=True)
    editor = card.open_editor()
    editor.title_input.setText("Saved title")
    editor.content.setHtml("<p><b>saved</b> <i>text</i></p>")
    service = LauncherService(config_file=str(tmp_path / "notes.json"))
    service.notes = notes.get_notes()
    assert service.persist_config() is None
    restored = LauncherService(config_file=str(tmp_path / "notes.json"))
    assert restored.load_state() is None
    notes.set_notes(restored.notes)
    settle()
    card = notes._cards[0]
    assert card.note_id == "note"
    assert card.title_input.text() == "Saved title"
    assert card.content.toPlainText() == "saved text"
    assert card._collapsed is True
    assert char_format(card.content, 1).fontWeight() == QFont.Bold
    assert char_format(card.content, 7).fontItalic()


@pytest.mark.parametrize("use_keyboard", [True, False])
def test_keyboard_and_header_open_editor(notes, use_keyboard):
    card = add_card(notes, "note")
    card.title_input.setFocus()
    settle()
    if use_keyboard:
        QTest.keyClick(card.title_input, Qt.Key_F2)
    else:
        QTest.mouseDClick(card.title_input, Qt.LeftButton)
    assert isinstance(card._editor, NoteEditorPopup)


def test_switching_editors_saves_previous_note(notes):
    notes.set_notes([{"id": "first"}, {"id": "second"}])
    settle()
    first, second = notes._cards
    editor = first.open_editor()
    editor.content.setPlainText("last edit")
    second.open_editor()
    assert first._editor is None
    assert first.content.toPlainText() == "last edit"
    assert second._editor.isVisible()


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("custom_color", [False, True])
def test_spoiler_theme_and_user_colors_survive_reveal_save_reload(notes, theme, custom_color):
    app = QApplication.instance()
    apply_design_system(app, theme=theme)
    card = add_card(notes, "secret plain")
    editor = card.open_editor().content
    select(editor, 0, 6)
    editor.setFontWeight(QFont.Bold)
    editor.setFontItalic(True)
    editor.setFontUnderline(True)
    if custom_color:
        editor.setTextColor(QColor("#ba459c"))
        editor.setTextBackgroundColor(QColor("#ffdd55"))
    editor._mask_selection()
    hidden_html = editor.persisted_html()
    editor._reveal_at(2)
    fmt = char_format(editor, 2)
    assert fmt.fontWeight() == QFont.Bold
    assert fmt.fontItalic() and fmt.fontUnderline()
    if custom_color:
        assert fmt.foreground().color().name() == "#ba459c"
        assert fmt.background().color().name() == "#ffdd55"
    else:
        assert fmt.foreground().style() == Qt.NoBrush
    assert editor.persisted_html() == hidden_html
    apply_design_system(app, theme="dark" if theme == "light" else "light")
    assert editor.toPlainText() == "secret plain"
    restored = SpoilerTextEdit()
    restored.setHtml(editor.persisted_html())
    assert SpoilerTextEdit._is_hidden(char_format(restored, 2))
    restored._reveal_at(2)
    fmt = char_format(restored, 2)
    assert fmt.fontWeight() == QFont.Bold
    assert fmt.fontItalic() and fmt.fontUnderline()
    if custom_color:
        assert fmt.foreground().color().name() == "#ba459c"
        assert fmt.background().color().name() == "#ffdd55"
    else:
        assert fmt.foreground().style() == Qt.NoBrush
    restored.deleteLater()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_legacy_spoiler_reveal_does_not_change_saved_html(notes, theme):
    apply_design_system(QApplication.instance(), theme=theme)
    card = add_card(notes, "")
    card.content.setHtml('<p><b><span style="color:#9ca3af; background-color:#9ca3af">secret</span></b> plain</p>')
    before = card.content.persisted_html()
    card.content._reveal_at(2)
    assert card.content.toPlainText() == "secret plain"
    assert card.content.persisted_html() == before


def test_spoiler_restores_mixed_colors_within_same_selection(notes):
    card = add_card(notes, "")
    content = card.open_editor().content
    content.setHtml('<p><span style="color:#c93434">red</span><span style="color:#349d61">green</span> plain</p>')
    select(content, 0, 8)
    content._mask_selection()
    restored = SpoilerTextEdit()
    restored.setHtml(content.persisted_html())
    restored._reveal_at(1)
    assert restored.toPlainText() == "redgreen plain"
    assert char_format(restored, 1).foreground().color().name() == "#c93434"
    assert char_format(restored, 5).foreground().color().name() == "#349d61"
    restored.deleteLater()
