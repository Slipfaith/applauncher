"""Interaction regressions for the redesigned runtime widgets."""
import pytest
from pathlib import Path
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent, QEnterEvent, QFont, QFontMetrics
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from applauncher.gui.styles import apply_design_system
from applauncher.gui.widgets import AppButton, AppListItem, HotkeySlotWidget, TitleBar
from ui_fixture import isolated_window, settle


@pytest.fixture
def app():
    application = QApplication.instance() or QApplication([])
    application.setStyle("Fusion")
    apply_design_system(application, theme="light")
    return application


@pytest.fixture
def window(app, tmp_path):
    with isolated_window(tmp_path, count=12) as widget:
        widget.show()
        widget.activateWindow()
        settle()
        yield widget


@pytest.mark.parametrize("key", [Qt.Key_Return, Qt.Key_Space])
def test_header_actions_activate_from_keyboard(app, tmp_path, monkeypatch, key):
    from applauncher.gui.app import AppLauncher
    calls = []
    monkeypatch.setattr(AppLauncher, "show_top_menu", lambda _: calls.append("menu"))
    monkeypatch.setattr(AppLauncher, "show_settings", lambda _: calls.append("settings"))
    with isolated_window(tmp_path, count=4) as window:
        window.show()
        window.activateWindow()
        for button in (window.menu_button, window.settings_button):
            assert button.focusPolicy() == Qt.StrongFocus
            assert button.accessibleName() == button.toolTip() == button.text()
            button.setFocus()
            settle()
            QTest.keyClick(button, key)
        assert calls == ["menu", "settings"]


def test_navigation_view_glyph_and_accessible_name_follow_target(window):
    assert window.view_mode == "grid"
    assert window.view_toggle.glyph() == "list"
    assert window.view_toggle.accessibleName() == "Список"
    QTest.keyClick(window.view_toggle, Qt.Key_Return)
    assert window.view_mode == "list"
    assert window.view_toggle.glyph() == "grid"
    assert window.view_toggle.accessibleName() == "Сетка"
    QTest.keyClick(window.view_toggle, Qt.Key_Space)
    assert window.view_mode == "grid"


def test_header_tab_order_is_logical(window):
    window.menu_button.setFocus()
    settle()
    for button in (window.settings_button, window.title_bar.min_button,
                   window.title_bar.max_button, window.title_bar.close_button):
        QTest.keyClick(QApplication.focusWidget(), Qt.Key_Tab)
        settle()
        assert button.hasFocus()


def test_hover_shadow_fits_grid_edges_at_minimum_size(window):
    window.resize(680, 440)
    settle()
    tiles = [window.grid_layout.itemAt(i).widget() for i in range(window.grid_layout.count())]
    viewport = window.scroll_area.viewport()
    for tile in (tiles[0], tiles[-1]):
        QApplication.sendEvent(tile, QEnterEvent(QPointF(), QPointF(), QPointF()))
        settle()
        bounds = tile.graphicsEffect().boundingRectFor(QRectF(tile.rect()))
        bounds.translate(tile.mapTo(viewport, QPoint()))
        assert QRectF(viewport.rect()).contains(bounds)
        QApplication.sendEvent(tile, QEvent(QEvent.Leave))


def test_window_buttons_track_maximize_and_no_tray(window):
    bar = window.title_bar
    assert bar.close_button.accessibleName() == "Закрыть"
    assert all(button.focusPolicy() == Qt.StrongFocus for button in (bar.min_button, bar.max_button, bar.close_button))
    QTest.keyClick(bar.max_button, Qt.Key_Return)
    settle()
    assert window.isMaximized()
    assert bar.max_button.accessibleName() == "Восстановить"
    assert bar.max_button.glyph() == "restore"
    QTest.keyClick(bar.max_button, Qt.Key_Space)
    settle()
    assert not window.isMaximized()
    assert bar.max_button.accessibleName() == "Развернуть"


@pytest.mark.parametrize("name", [
    "Очень длинное русское название папки с несколькими словами",
    "Непрерывноедлинноеслово" * 6,
    "📁🚀 Очень длинное название с emoji 🚀 и продолжением" * 3,
])
def test_long_tile_label_elides_and_reflows_on_font_change(app, name):
    button = AppButton({"name": name, "path": "https://example.com", "type": "url"})
    assert "…" in button.text()
    assert len(button.text().splitlines()) <= 2
    assert button.accessibleName() == name
    assert name in button.toolTip()
    font = QFont(button.font())
    font.setPointSizeF(13)
    button.setFont(font)
    metrics = QFontMetrics(button.font())
    assert "…" in button.text()
    assert all(metrics.horizontalAdvance(line) <= 104 for line in button.text().splitlines())
    button.deleteLater()
    settle()


def test_copy_focus_and_success_timer_do_not_activate_tile(app):
    button = AppButton({"name": "Ссылка", "path": "https://example.com", "type": "url"})
    copied, activated = [], []
    button.copyLinkRequested.connect(copied.append)
    button.activated.connect(activated.append)
    button.show()
    button.activateWindow()
    button.setFocus()
    settle()
    assert button._copy_btn.isVisible()
    QTest.keyClick(button, Qt.Key_Tab)
    settle()
    assert button._copy_btn.hasFocus()
    QTest.keyClick(button._copy_btn, Qt.Key_Space)
    QTest.qWait(850)
    assert len(copied) == 1
    assert activated == []
    assert button._copy_btn.isVisible() and button._copy_btn.hasFocus()
    button.close()
    button.deleteLater()
    settle()


@pytest.mark.parametrize("widget_type", [AppButton, AppListItem])
def test_folder_drop_highlight_resets_after_invalid_leave_and_drop(app, tmp_path, widget_type):
    target = widget_type({"name": "Папка", "type": "folder", "path": str(tmp_path)})
    source = tmp_path / "source.txt"
    source.write_text("test", encoding="utf-8")
    valid = QMimeData()
    valid.setUrls([QUrl.fromLocalFile(str(source))])
    invalid = QMimeData()
    invalid.setText("unsupported")
    target.dragEnterEvent(QDragEnterEvent(QPoint(4, 4), Qt.CopyAction, valid, Qt.LeftButton, Qt.NoModifier))
    assert target.property("dropTarget") is True
    target.dragMoveEvent(QDragMoveEvent(QPoint(4, 4), Qt.CopyAction, invalid, Qt.LeftButton, Qt.NoModifier))
    assert not target.property("dropTarget")
    target.dragEnterEvent(QDragEnterEvent(QPoint(4, 4), Qt.CopyAction, valid, Qt.LeftButton, Qt.NoModifier))
    target.dragEnterEvent(QDragEnterEvent(QPoint(4, 4), Qt.CopyAction, invalid, Qt.LeftButton, Qt.NoModifier))
    assert not target.property("dropTarget")
    target.dragEnterEvent(QDragEnterEvent(QPoint(4, 4), Qt.CopyAction, valid, Qt.LeftButton, Qt.NoModifier))
    target.dragLeaveEvent(QDragLeaveEvent())
    assert not target.property("dropTarget")
    drops = []
    target.filesDroppedToFolder.connect(lambda item, files: drops.append(files))
    target.dragEnterEvent(QDragEnterEvent(QPoint(4, 4), Qt.CopyAction, valid, Qt.LeftButton, Qt.NoModifier))
    target.dropEvent(QDropEvent(QPointF(4, 4), Qt.CopyAction, valid, Qt.LeftButton, Qt.NoModifier))
    assert len(drops) == 1 and [Path(path) for path in drops[0]] == [source]
    assert not target.property("dropTarget")
    target.deleteLater()
    settle()


def test_full_custom_image_keeps_saved_crop_and_dimensions(app, tmp_path):
    from PySide6.QtGui import QPixmap
    pixmap = QPixmap(300, 200)
    pixmap.fill(Qt.blue)
    path = tmp_path / "image.png"
    pixmap.save(str(path))
    data = {"name": "Изображение", "path": "https://example.com", "type": "url",
            "custom_icon": True, "icon_path": str(path), "icon_frame": [0, 0, 1, 1]}
    original = data.copy()
    tile = AppButton(data)
    assert (tile.width(), tile.height()) == (120, 96)
    assert tile.property("iconMode") == "full"
    assert not tile.icon().isNull()
    assert data == original
    tile.deleteLater()
    settle()


def test_hud_slot_can_activate_with_keyboard(app):
    data = {"name": "Элемент", "path": "https://example.com", "type": "url", "local_hotkey": "Ctrl+1"}
    slot = HotkeySlotWidget(data)
    activated = []
    slot.clicked.connect(activated.append)
    QTest.keyClick(slot, Qt.Key_Return)
    assert activated == [data]
    assert "Элемент" in slot.accessibleName()
    slot.deleteLater()
    settle()


def test_list_row_elides_long_path_and_activates_from_keyboard(app):
    from PySide6.QtWidgets import QLabel
    name = "Длинное русское название " * 20
    path = "https://example.com/" + "long-path/" * 50
    row = AppListItem({"name": name, "path": path, "type": "url"})
    row.resize(500, 60)
    row.show()
    settle()
    labels = {label.property("role"): label for label in row.findChildren(QLabel)}
    assert "…" in labels["listTitle"].text()
    assert "…" in labels["listSubtitle"].text()
    assert labels["listSubtitle"].toolTip() == path
    assert row.accessibleName() == name
    narrow = labels["listTitle"].text()
    row.resize(900, 60)
    settle()
    assert len(labels["listTitle"].text()) > len(narrow)
    row.resize(500, 60)
    settle()
    assert labels["listTitle"].text() == narrow
    activated = []
    row.activated.connect(activated.append)
    QTest.keyClick(row, Qt.Key_Return)
    assert activated == [row.app_data]
    row.close()
    row.deleteLater()
    settle()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_dialog_layouts_fit_screen_budget_without_editing_data(app, window, theme):
    from copy import deepcopy
    from unittest.mock import patch
    from applauncher.gui.dialogs import AddAppDialog, SettingsDialog, HotkeyCaptureDialog
    from applauncher.gui.widgets.notes_widget import NoteEditorPopup
    apply_design_system(app, theme=theme)
    data = deepcopy(window.service.repository.apps[0])
    original = deepcopy(data)
    dialogs = [AddAppDialog(window, edit_mode=True, app_data=data, groups=window.groups),
               SettingsDialog("Ctrl+Space", 0.75, window),
               HotkeyCaptureDialog(window, current_hotkey="Ctrl+Alt+Space"),
               NoteEditorPopup(window.service.notes[0], window)]
    for dialog in dialogs:
        with patch.object(dialog, "grabKeyboard"), patch.object(dialog, "releaseKeyboard"):
            dialog.show()
            settle()
            assert dialog.width() <= 1280 and dialog.height() <= 640
            dialog.close()
        dialog.deleteLater()
    assert data == original
    settle()
