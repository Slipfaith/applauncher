"""Live theme selection, persistence and preservation of open editor state."""
from copy import deepcopy
import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from applauncher.config import load_config
from applauncher.gui import styles
from applauncher.gui.dialogs import AddAppDialog, SettingsDialog
from applauncher.gui.widgets.notes_widget import NoteEditorPopup
from applauncher.services.launcher_service import LauncherService
from ui_fixture import isolated_window, settle


@pytest.fixture
def app():
    application = QApplication.instance() or QApplication([])
    application.setStyle("Fusion")
    styles.apply_design_system(application, theme="light")
    yield application
    styles.apply_design_system(application, theme="auto")
    settle()


@pytest.mark.parametrize("payload", [[], {}, {"theme_mode": None}, {"theme_mode": 1},
                                    {"theme_mode": ["dark"]}, {"theme_mode": "unknown"}])
def test_legacy_or_invalid_theme_defaults_to_auto(tmp_path, payload):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_config(str(path))["theme_mode"] == "auto"
    assert load_config(str(tmp_path / "missing.json"))["theme_mode"] == "auto"


@pytest.mark.parametrize("mode", ["auto", "light", "dark"])
def test_selected_theme_survives_service_reload_and_reset(tmp_path, mode):
    service = LauncherService(config_file=str(tmp_path / "config.json"))
    service.theme_mode = mode
    assert service.persist_config() is None
    restored = LauncherService(config_file=service.config_file)
    assert restored.load_state() is None
    assert restored.theme_mode == mode
    assert restored.reset_to_defaults() is None
    assert load_config(service.config_file)["theme_mode"] == "auto"


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_startup_applies_saved_theme_before_showing_window(app, tmp_path, mode):
    styles.apply_design_system(app, theme="dark" if mode == "light" else "light")
    with isolated_window(tmp_path, count=4, theme=mode) as window:
        assert styles.theme_mode() == styles.active_theme() == mode
        window.show_settings()
        assert window.settings_dialog.theme_combo.currentData() == mode


def test_theme_combo_keyboard_and_silent_synchronization(app):
    dialog = SettingsDialog("Ctrl+Space", 0.75, current_theme="auto")
    changes = []
    dialog.themeChanged.connect(changes.append)
    dialog.show()
    dialog.theme_combo.setFocus()
    settle()
    QTest.keyClick(dialog.theme_combo, Qt.Key_End)
    assert changes == ["dark"]
    dialog.set_theme("light")
    assert changes == ["dark"]
    assert dialog.theme_combo.currentData() == "light"
    dialog.close()
    dialog.deleteLater()
    settle()


def test_live_theme_updates_existing_windows_and_preserves_editing(app, tmp_path):
    with isolated_window(tmp_path, count=12, theme="light") as window:
        window.show()
        window.search_input.setText("Очень")
        window.show_settings()
        settle()
        settings = window.settings_dialog
        add_dialog = AddAppDialog(window, groups=window.groups)
        add_dialog.show()
        editor = NoteEditorPopup(window.service.notes[0], window)
        # Keep the editor visible alongside Settings for this controlled test.
        editor.setWindowFlags(Qt.Tool)
        editor.show()
        cursor = editor.content.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(" Несохранённая правка")
        cursor.setPosition(2)
        cursor.setPosition(8, QTextCursor.KeepAnchor)
        editor.content.setTextCursor(cursor)
        editor._save_timer.stop()
        settle()
        original_html = editor.content.persisted_html()
        original_selection = (cursor.anchor(), cursor.position())
        original_items = deepcopy(window.repository.apps)
        tile = window.grid_layout.itemAt(0).widget()
        scroll = window.scroll_area.verticalScrollBar()
        scroll.setValue(min(20, scroll.maximum()))
        original_scroll = scroll.value()
        glyph_light = window.title_bar.min_button._glyph_color().name()
        for mode, colors in (("dark", styles.DARK_COLORS), ("light", styles.LIGHT_COLORS)):
            settings.theme_combo.setCurrentIndex(settings.theme_combo.findData(mode))
            # Application state changes synchronously, before event processing.
            assert styles.active_theme() == window.service.theme_mode == mode
            assert app.palette().color(QPalette.Text).name() == colors.text_primary
            settle()
            for widget in (settings, add_dialog, editor, editor.content, window.search_input,
                           window.universal_search, window.clipboard_widget):
                assert widget.palette().color(QPalette.Text).name() == colors.text_primary
            assert tile is window.grid_layout.itemAt(0).widget()
            assert window.repository.apps == original_items
            assert window.search_input.text() == "Очень"
            assert scroll.value() == original_scroll
            assert editor.isVisible() and editor.content.document().isUndoAvailable()
            assert editor.content.persisted_html() == original_html
            current = editor.content.textCursor()
            assert (current.anchor(), current.position()) == original_selection
            if mode == "dark":
                assert window.title_bar.min_button._glyph_color().name() != glyph_light
                app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
                assert styles.active_theme() == "dark"
        settings.theme_combo.setCurrentIndex(settings.theme_combo.findData("auto"))
        app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        assert styles.theme_mode() == window.service.theme_mode == "auto"
        assert styles.active_theme() == "dark"
        settle()
        assert editor.content.palette().color(QPalette.Text).name() == styles.DARK_COLORS.text_primary
        # Exercise the real save, rather than the fixture's mock persistence.
        assert LauncherService.persist_config(window.service) is None
        restored = LauncherService(config_file=window.service.config_file)
        assert restored.load_state() is None
        assert restored.theme_mode == "auto"
        editor.close()
        add_dialog.close()
        editor.deleteLater()
        add_dialog.deleteLater()
        settle()


def test_settings_reset_applies_auto_and_resynchronizes_selector(app, tmp_path, monkeypatch):
    import applauncher.gui.app as runtime
    with isolated_window(tmp_path, count=4, theme="dark") as window:
        window.show_settings()
        monkeypatch.setattr(runtime.QMessageBox, "question", lambda *args: runtime.QMessageBox.Yes)
        monkeypatch.setattr(runtime.QMessageBox, "information", lambda *args: None)
        monkeypatch.setattr(window.icon_service, "clear_cache", lambda: 0)
        monkeypatch.setattr(window.service, "persist_config", lambda: LauncherService.persist_config(window.service))
        window._on_reset_settings_requested()
        assert window.service.theme_mode == styles.theme_mode() == "auto"
        assert window.settings_dialog.theme_combo.currentData() == "auto"
        assert styles.active_theme() == styles._resolve_theme(app, "auto")
