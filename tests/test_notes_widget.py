"""Regression checks for note sizing, formatting and mouse selection."""
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QMouseEvent, QTextCursor
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
def test_collapsed_note_folds_to_header_and_preserves_text(notes, initially_collapsed):
    text = "\n".join(f"Строка {i}" for i in range(12))
    card = add_card(notes, text, collapsed=initially_collapsed)
    if not initially_collapsed:
        expanded_height = card.height()
        card.toggle_collapsed()
        settle()
        assert card.height() < expanded_height
    assert not card.content.isVisible()
    assert card.title_input.isVisible() and card.delete_btn.isVisible()
    assert card.height() < card.title_input.height() + 30
    assert card.collapse_btn.glyph() == "chevron-right"
    assert card.content.toPlainText() == text
    saved = card.get_data()
    assert saved["collapsed"] is True
    card.toggle_collapsed()
    settle()
    assert card.content.isVisible()
    assert card.collapse_btn.glyph() == "chevron-down"
    assert card.content.isReadOnly()
    assert card.content.verticalScrollBar().maximum() == 0
    assert card.content.toPlainText() == text
    notes.set_notes([saved])
    settle()
    assert not notes._cards[0].content.isVisible()
    assert notes._cards[0].content.toPlainText() == text


def test_delete_button_is_trash_glyph(notes):
    card = add_card(notes, "text")
    assert card.delete_btn.glyph() == "trash"
    assert card.delete_btn.text() == ""
    QTest.mouseClick(card.delete_btn, Qt.LeftButton)
    settle()
    assert notes.get_notes() == []


def triple_click(widget, point):
    # QTest spaces clicks beyond the double-click interval, so send real timestamps.
    base = 10_000_000
    for event_type, offset in ((QEvent.MouseButtonPress, 0), (QEvent.MouseButtonRelease, 20),
                               (QEvent.MouseButtonPress, 120), (QEvent.MouseButtonDblClick, 120),
                               (QEvent.MouseButtonRelease, 140), (QEvent.MouseButtonPress, 240),
                               (QEvent.MouseButtonRelease, 260)):
        buttons = Qt.NoButton if event_type == QEvent.MouseButtonRelease else Qt.LeftButton
        event = QMouseEvent(event_type, QPointF(point), QPointF(widget.mapToGlobal(point)),
                            Qt.LeftButton, buttons, Qt.NoModifier)
        event.setTimestamp(base + offset)
        QApplication.sendEvent(widget, event)


def point_at(editor, position):
    cursor = QTextCursor(editor.document())
    cursor.setPosition(position)
    return editor.cursorRect(cursor).center()


def test_triple_click_in_preview_copies_line_without_opening_editor(notes):
    card = add_card(notes, "google\nlogin@example.com\npassword")
    select(card.content, 7, 12)
    card.content._mask_selection()
    QApplication.clipboard().clear()
    triple_click(card.content.viewport(), point_at(card.content, 9))
    QTest.qWait(QApplication.doubleClickInterval() + 50)
    assert QApplication.clipboard().text() == "login@example.com"
    assert card.content.textCursor().selectedText() == "login@example.com"
    assert card._editor is None


def test_triple_click_in_editor_copies_soft_broken_line(notes):
    card = add_card(notes, "")
    editor = card.open_editor()
    settle()
    editor.content.setHtml("<p>first line<br>second line</p><p>third</p>")
    QApplication.clipboard().clear()
    triple_click(editor.content.viewport(), point_at(editor.content, 14))
    assert QApplication.clipboard().text() == "second line"
    triple_click(editor.content.viewport(), point_at(editor.content, 26))
    assert QApplication.clipboard().text() == "third"


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
    assert editor.content.textCursor().selectedText() == "secret"
    assert editor.content.has_revealed_spoilers()
    saved = card.get_data()
    restored = SpoilerTextEdit()
    restored.setHtml(saved["content_html"])
    assert SpoilerTextEdit._is_hidden(char_format(restored, 1))
    assert char_format(restored, 1).fontWeight() == QFont.Bold
    assert editor.content.acceptRichText()
    restored.deleteLater()


def test_double_click_opens_editor_and_focus_loss_flushes_changes(notes):
    card = add_card(notes, "исходный текст")
    QTest.mouseDClick(card.content.viewport(), Qt.LeftButton)
    settle()
    assert card._editor is None
    QTest.qWait(QApplication.doubleClickInterval() + 50)
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
    assert card.get_data()["collapsed"] is False


def test_click_outside_editor_closes_and_saves(notes):
    card = add_card(notes, "before")
    editor = card.open_editor()
    settle()
    editor.content.setPlainText("saved on outside click")
    QTest.mouseClick(notes, Qt.LeftButton, pos=QPoint(notes.width() - 2, notes.height() - 2))
    assert card._editor is None
    assert card.content.toPlainText() == "saved on outside click"


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


@pytest.mark.parametrize("popup", [False, True])
def test_hide_via_real_context_menu_saves_and_keeps_editor_open(notes, popup):
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QContextMenuEvent
    from PySide6.QtWidgets import QMenu

    card = add_card(notes, "secret plain")
    content = card.open_editor().content if popup else card.content
    settle()
    select(content, 0, 6)
    changes = []
    notes.notesChanged.connect(lambda: changes.append(True))
    actions = []

    def choose_hide():
        menu = QApplication.activePopupWidget()
        if not isinstance(menu, QMenu):
            return
        actions.extend(action.text() for action in menu.actions())
        action = next((a for a in menu.actions() if a.text() == "Скрыть"), None)
        if action is None:
            menu.close()
            return
        # A submenu can extend outside the editor: this is not an outside click.
        if popup:
            editor = card._editor
            menu.move(editor.mapToGlobal(QPoint(editor.width() + 4, 0)))
            QApplication.sendEvent(editor, QEvent(QEvent.WindowDeactivate))
        QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(action).center())
        menu.close()

    QTimer.singleShot(20, choose_hide)
    point = point_at(content, 2)
    event = QContextMenuEvent(QContextMenuEvent.Mouse, point, content.viewport().mapToGlobal(point))
    QApplication.sendEvent(content.viewport(), event)
    settle()
    assert "Скрыть" in actions
    assert "Замаскировать" not in actions
    if popup:
        assert card._editor is not None and card._editor.isVisible()
        card._editor.flush_changes()
    assert SpoilerTextEdit._is_hidden(char_format(content, 2))
    assert changes
    saved = notes.get_notes()
    notes.set_notes(saved)
    settle()
    assert SpoilerTextEdit._is_hidden(char_format(notes._cards[0].content, 2))


@pytest.mark.parametrize("popup", [False, True])
def test_spoiler_single_click_reveals_and_hiding_view_remasks(notes, popup):
    card = add_card(notes, "secret plain")
    content = card.open_editor().content if popup else card.content
    settle()
    select(content, 0, 6)
    content._mask_selection()
    select(content, 9, 9)
    QTest.mouseClick(content.viewport(), Qt.LeftButton, pos=point_at(content, 2))
    assert content.has_revealed_spoilers()
    assert not SpoilerTextEdit._is_hidden(char_format(content, 2))
    if not popup:
        assert card._editor is None
    content.hide()
    content.show()
    settle()
    assert SpoilerTextEdit._is_hidden(char_format(content, 2))


@pytest.mark.parametrize("popup", [False, True])
@pytest.mark.parametrize("paste", [False, True])
def test_preformatted_email_wraps_without_clipping(notes, popup, paste):
    card = add_card(notes, "")
    content = card.open_editor().content if popup else card.content
    email = "long.email.address." * 12 + "@example.com"
    html = f'<p style="white-space:pre"><b>google</b><br><a href="mailto:{email}">{email}</a></p>'
    if paste:
        mime = QMimeData()
        mime.setHtml(html)
        target = content if popup else card.open_editor().content
        target.insertFromMimeData(mime)
        if not popup:
            card._editor.close()
    else:
        content.setHtml(html)
    settle()
    assert content.horizontalScrollBar().maximum() == 0
    assert content.document().size().width() <= content.viewport().width()
    assert email in content.toPlainText()
    if not popup:
        assert content.document().size().height() <= content.viewport().height()


def test_wrapped_spoiler_overlay_covers_last_character_on_each_line(notes):
    card = add_card(notes, "W" * 90 + "\nplain")
    content = card.content
    select(content, 0, 90)
    content._mask_selection()
    settle()
    block = content.document().firstBlock()
    layout = block.layout()
    assert layout.lineCount() > 1
    for i in range(layout.lineCount()):
        line = layout.lineAt(i)
        pos = line.textStart() + line.textLength() - 1
        point = point_at(content, pos) + QPoint(3, 0)
        assert any(rect.contains(point) for rect in content._spoiler_rects_cache)
    assert not any(rect.contains(point_at(content, 92)) for rect in content._spoiler_rects_cache)


@pytest.mark.parametrize("popup", [False, True])
def test_dragging_hidden_text_reveals_and_selects(notes, popup):
    card = add_card(notes, "secret plain")
    content = card.open_editor().content if popup else card.content
    settle()
    select(content, 0, 6)
    content._mask_selection()
    QTest.mousePress(content.viewport(), Qt.LeftButton, pos=point_at(content, 1))
    QTest.mouseMove(content.viewport(), point_at(content, 5))
    QTest.mouseRelease(content.viewport(), Qt.LeftButton, pos=point_at(content, 5))
    assert content.textCursor().selectedText() == "ecre"
    assert content.has_revealed_spoilers()
    content.copy()
    assert QApplication.clipboard().text() == "ecre"


def test_double_click_hidden_preview_does_not_open_editor(notes):
    card = add_card(notes, "secret plain")
    select(card.content, 0, 6)
    card.content._mask_selection()
    QTest.mouseDClick(card.content.viewport(), Qt.LeftButton, pos=point_at(card.content, 2))
    QTest.mouseRelease(card.content.viewport(), Qt.LeftButton, pos=point_at(card.content, 2))
    QTest.qWait(QApplication.doubleClickInterval() + 50)
    assert card._editor is None
    assert card.content.has_revealed_spoilers()


@pytest.mark.parametrize("popup", [False, True])
@pytest.mark.parametrize("destination", ["plain", "blank", "title", "outside"])
def test_click_away_remasks_revealed_text(notes, popup, destination):
    card = add_card(notes, "secret plain")
    editor = card.open_editor() if popup else None
    content = editor.content if popup else card.content
    settle()
    select(content, 0, 6)
    content._mask_selection()
    saved_html = content.persisted_html()
    QTest.mouseClick(content.viewport(), Qt.LeftButton, pos=point_at(content, 2))
    assert content.has_revealed_spoilers()
    changes = []
    content.textChanged.connect(lambda: changes.append(True))
    if destination == "plain":
        target, point = content.viewport(), point_at(content, 9)
    elif destination == "blank":
        target = content.viewport()
        point = QPoint(target.width() - 2, point_at(content, 2).y())
    elif destination == "title":
        target = editor.title_input if popup else card.title_input
        point = target.rect().center()
    else:
        target, point = notes, QPoint(notes.width() - 2, notes.height() - 2)
    QTest.mouseClick(target, Qt.LeftButton, pos=point)
    assert not content.has_revealed_spoilers()
    assert SpoilerTextEdit._is_hidden(char_format(content, 2))
    assert content.persisted_html() == saved_html
    assert changes == []


@pytest.mark.parametrize("popup", [False, True])
def test_click_on_revealed_text_keeps_it_readable(notes, popup):
    card = add_card(notes, "secret plain")
    content = card.open_editor().content if popup else card.content
    settle()
    select(content, 0, 6)
    content._mask_selection()
    for position in (2, 3):
        QTest.mouseClick(content.viewport(), Qt.LeftButton, pos=point_at(content, position))
        assert content.has_revealed_spoilers()


@pytest.mark.parametrize("popup", [False, True])
def test_unmask_selection_from_menu_is_permanent_and_preserves_styles(notes, popup):
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QContextMenuEvent
    from PySide6.QtWidgets import QMenu

    card = add_card(notes, "")
    card.content.setHtml('<p><b><span style="color:#ba459c">secret</span></b> plain</p>')
    content = card.open_editor().content if popup else card.content
    settle()
    select(content, 0, 6)
    content._mask_selection()
    QTest.mouseClick(content.viewport(), Qt.LeftButton, pos=point_at(content, 2))
    QTest.mouseDClick(content.viewport(), Qt.LeftButton, pos=point_at(content, 2))
    QTest.mouseRelease(content.viewport(), Qt.LeftButton, pos=point_at(content, 2))
    assert content.textCursor().selectedText() == "secret"
    assert content.has_revealed_spoilers()
    chosen = []

    def choose_unmask():
        menu = QApplication.activePopupWidget()
        if not isinstance(menu, QMenu):
            return
        action = next((a for a in menu.actions() if a.text() == "Раскрыть"), None)
        if action is not None:
            QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(action).center())
            chosen.append(True)
        menu.close()

    QTimer.singleShot(20, choose_unmask)
    point = point_at(content, 2)
    QApplication.sendEvent(content.viewport(), QContextMenuEvent(
        QContextMenuEvent.Mouse, point, content.viewport().mapToGlobal(point)))
    assert chosen
    QTest.mouseClick(content.viewport(), Qt.LeftButton, pos=point_at(content, 9))
    assert not SpoilerTextEdit._is_spoiler(char_format(content, 2))
    fmt = char_format(content, 2)
    assert fmt.fontWeight() == QFont.Bold
    assert fmt.foreground().color().name() == "#ba459c"
    saved = notes.get_notes()
    notes.set_notes(saved)
    settle()
    assert not SpoilerTextEdit._is_spoiler(char_format(notes._cards[0].content, 2))
    assert char_format(notes._cards[0].content, 2).foreground().color().name() == "#ba459c"


def test_unmask_only_selected_part_of_spoiler_and_support_undo(notes):
    card = add_card(notes, "secret plain")
    content = card.open_editor().content
    settle()
    select(content, 0, 6)
    content._mask_selection()
    select(content, 1, 4)
    content._unmask_selection()
    assert not SpoilerTextEdit._is_spoiler(char_format(content, 2))
    assert SpoilerTextEdit._is_hidden(char_format(content, 0))
    assert SpoilerTextEdit._is_hidden(char_format(content, 5))
    content.undo()
    assert SpoilerTextEdit._is_hidden(char_format(content, 2))


@pytest.mark.parametrize("popup", [False, True])
@pytest.mark.parametrize("interaction", ["hidden", "revealed", "dragged"])
def test_right_click_spoiler_offers_unmask_without_manual_selection(notes, popup, interaction):
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QContextMenuEvent
    from PySide6.QtWidgets import QMenu

    card = add_card(notes, "")
    # Legacy HTML with a link and a soft line break, as in an existing note.
    card.content.setHtml('<p><b>google</b><br><span style="color:#9ca3af; background-color:#9ca3af">'
                         'login@example.com<br>password</span></p><p>plain</p>')
    content = card.open_editor().content if popup else card.content
    settle()
    point = point_at(content, 9)
    if interaction == "revealed":
        QTest.mouseClick(content.viewport(), Qt.LeftButton, pos=point)
    elif interaction == "dragged":
        QTest.mousePress(content.viewport(), Qt.LeftButton, pos=point_at(content, 7))
        QTest.mouseMove(content.viewport(), point_at(content, 13))
        QTest.mouseRelease(content.viewport(), Qt.LeftButton, pos=point_at(content, 13))
        assert content.textCursor().selectedText() == "login@"
    selected_before = content.textCursor().selectedText()
    seen = []

    def choose_unmask():
        menu = QApplication.activePopupWidget()
        if not isinstance(menu, QMenu):
            return
        seen.extend(action.text() for action in menu.actions())
        action = next((a for a in menu.actions() if a.text() == "Раскрыть"), None)
        if action is not None:
            if interaction == "dragged":
                assert content.textCursor().selectedText() == selected_before
            QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(action).center())
        menu.close()

    # Include the right-button press/release, not only a synthetic context event.
    QTest.mouseClick(content.viewport(), Qt.RightButton, pos=point)
    QTimer.singleShot(20, choose_unmask)
    QApplication.sendEvent(content.viewport(), QContextMenuEvent(
        QContextMenuEvent.Mouse, point, content.viewport().mapToGlobal(point)))
    assert "Раскрыть" in seen
    assert not SpoilerTextEdit._is_spoiler(char_format(content, 9))
    if interaction == "dragged":
        assert SpoilerTextEdit._is_spoiler(char_format(content, 15))
    QTest.mouseClick(content.viewport(), Qt.LeftButton, pos=point_at(content, 35))
    saved = notes.get_notes()
    notes.set_notes(saved)
    settle()
    assert not SpoilerTextEdit._is_spoiler(char_format(notes._cards[0].content, 9))


@pytest.mark.parametrize("popup", [False, True])
@pytest.mark.parametrize("backwards", [False, True])
@pytest.mark.parametrize("wrapped", [False, True])
def test_drag_selects_whole_hidden_email(notes, popup, backwards, wrapped):
    email = "login.name+tag@example.co.uk"
    if wrapped:
        email = "very.long.email.address." * 4 + "name+tag@example.co.uk"
    card = add_card(notes, "")
    card.content.setHtml('<p><b>google</b><br><a href="mailto:' + email + '">'
                         '<span style="color:#9ca3af; background-color:#9ca3af">'
                         + email + '</span></a><br>password</p>')
    content = card.open_editor().content if popup else card.content
    settle()
    start = content.toPlainText().index(email)
    end = start + len(email)
    positions = (end, start) if backwards else (start, end)
    QTest.mousePress(content.viewport(), Qt.LeftButton, pos=point_at(content, positions[0]))
    QTest.mouseMove(content.viewport(), point_at(content, positions[1]))
    QTest.mouseRelease(content.viewport(), Qt.LeftButton, pos=point_at(content, positions[1]))
    assert content.textCursor().selectedText() == email
    assert content.has_revealed_spoilers()
    content.copy()
    assert QApplication.clipboard().text() == email


@pytest.mark.parametrize("popup", [False, True])
@pytest.mark.parametrize("revealed", [False, True])
def test_double_click_selects_complete_hidden_email(notes, popup, revealed):
    email = "login.name+tag@example.co.uk"
    card = add_card(notes, "")
    card.content.setHtml('<p>google<br><span style="color:#9ca3af; background-color:#9ca3af">'
                         + email + '</span><br>password</p>')
    content = card.open_editor().content if popup else card.content
    settle()
    point = point_at(content, content.toPlainText().index("example") + 2)
    if revealed:
        QTest.mouseClick(content.viewport(), Qt.LeftButton, pos=point)
    QTest.mouseDClick(content.viewport(), Qt.LeftButton, pos=point)
    QTest.mouseRelease(content.viewport(), Qt.LeftButton, pos=point)
    assert content.textCursor().selectedText() == email
    assert content.has_revealed_spoilers()
    content.copy()
    assert QApplication.clipboard().text() == email
    if not popup:
        assert not content._edit_timer.isActive()


@pytest.mark.parametrize("text", ["ordinary words", "login.name@example.co.uk"])
def test_preview_double_click_text_selects_without_opening_editor(notes, text):
    card = add_card(notes, text)
    QTest.mouseDClick(card.content.viewport(), Qt.LeftButton, pos=point_at(card.content, 3))
    QTest.mouseRelease(card.content.viewport(), Qt.LeftButton, pos=point_at(card.content, 3))
    QTest.qWait(QApplication.doubleClickInterval() + 50)
    assert card._editor is None
    assert card.content.textCursor().selectedText() == (text if "@" in text else "ordinary")


def test_preview_double_click_blank_space_opens_editor(notes):
    card = add_card(notes, "short")
    point = QPoint(card.content.viewport().width() - 3, point_at(card.content, 2).y())
    QTest.mouseDClick(card.content.viewport(), Qt.LeftButton, pos=point)
    QTest.mouseRelease(card.content.viewport(), Qt.LeftButton, pos=point)
    QTest.qWait(QApplication.doubleClickInterval() + 50)
    assert card._editor is not None and card._editor.isVisible()


def test_editor_hide_menu_keeps_original_selection_and_arrow_cursor(notes):
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QContextMenuEvent
    from PySide6.QtWidgets import QMenu

    card = add_card(notes, "password: 49371")
    editor = card.open_editor()
    content = editor.content
    settle()
    select(content, 10, 15)
    cursor_states = []
    had_override = QApplication.overrideCursor()

    def choose_hide():
        menu = QApplication.activePopupWidget()
        if not isinstance(menu, QMenu):
            return
        override = QApplication.overrideCursor()
        cursor_states.append(override.shape() if override else menu.cursor().shape())
        cursor_states.append(menu.testAttribute(Qt.WA_SetCursor))
        # Focus changes while a native popup is open must not lose its target.
        select(content, 0, 0)
        action = next(a for a in menu.actions() if a.text() == "Скрыть")
        QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(action).center())
        menu.close()

    QTimer.singleShot(20, choose_hide)
    point = point_at(content, 12)
    QApplication.sendEvent(content.viewport(), QContextMenuEvent(
        QContextMenuEvent.Mouse, point, content.viewport().mapToGlobal(point)))
    assert cursor_states == [Qt.ArrowCursor, True]
    assert QApplication.overrideCursor() is had_override
    assert editor.isVisible()
    assert SpoilerTextEdit._is_hidden(char_format(content, 12))
    assert not SpoilerTextEdit._is_spoiler(char_format(content, 2))
    QTest.qWait(350)
    assert SpoilerTextEdit._is_hidden(char_format(content, 12))
    assert SpoilerTextEdit._is_hidden(char_format(card.content, 12))



def test_double_click_title_text_selects_without_opening_editor(notes):
    card = add_card(notes, "body")
    card.title_input.setText("Title words")
    card.title_input.setCursorPosition(2)
    point = card.title_input.cursorRect().center()
    QTest.mouseDClick(card.title_input, Qt.LeftButton, pos=point)
    QTest.mouseRelease(card.title_input, Qt.LeftButton, pos=point)
    assert card.title_input.selectedText() == "Title"
    assert card._editor is None
