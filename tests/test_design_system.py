"""Behaviour checks for palettes, automatic mode and font fallbacks."""
import logging

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from applauncher.gui import styles


@pytest.fixture
def app():
    application = QApplication.instance() or QApplication([])
    application.setStyle("Fusion")
    yield application
    styles.apply_design_system(application, theme="auto")


@pytest.mark.parametrize("theme, colors", [("light", styles.LIGHT_COLORS), ("dark", styles.DARK_COLORS)])
def test_applied_palette_and_active_python_colors(app, theme, colors):
    styles.apply_design_system(app, theme=theme)
    assert styles.active_colors() == colors
    assert styles.active_theme() == theme
    assert app.palette().color(QPalette.Window).name() == colors.background
    assert app.palette().color(QPalette.Text).name() == colors.text_primary
    assert app.font().pointSizeF() > 0


@pytest.mark.parametrize("value, rgba", [
    ("rgba(10, 19, 48, 46)", (10, 19, 48, 46)),
    ("rgba(10, 19, 48, 34)", (10, 19, 48, 34)),
    ("rgba(10, 19, 48, 0.5)", (10, 19, 48, 127)),
    ("#0a1330", (10, 19, 48, 255)),
])
def test_shadow_color_channels(value, rgba):
    assert styles.to_qcolor(value).getRgb() == rgba


def test_explicit_mode_survives_system_signal_and_auto_has_one_callback(app, monkeypatch):
    styles.apply_design_system(app, theme="auto")
    calls = []
    original = styles._apply_theme

    def track(application, tokens, name):
        calls.append(name)
        return original(application, tokens, name)

    monkeypatch.setattr(styles, "_apply_theme", track)
    for _ in range(3):
        styles.apply_design_system(app, theme="auto")
    calls.clear()
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert calls == ["dark"]
    assert styles.active_theme() == "dark"
    styles.apply_design_system(app, theme="light")
    calls.clear()
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert calls == []
    assert styles.theme_mode() == "light"
    assert styles.active_theme() == "light"
    styles.apply_design_system(app, theme="auto")
    calls.clear()
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
    assert calls == ["light"]


def test_bundled_font_families_register_once(app, monkeypatch):
    assert {"Onest", "JetBrains Mono"} <= set(styles.register_fonts())
    monkeypatch.setattr(styles.QFontDatabase, "addApplicationFont", lambda _: pytest.fail("registered twice"))
    styles.apply_design_system(app, theme="dark")


@pytest.mark.parametrize("corrupt", [False, True])
def test_missing_or_corrupt_fonts_fall_back_without_crash(app, monkeypatch, tmp_path, caplog, corrupt):
    monkeypatch.delattr(app, "_applauncher_font_families", raising=False)
    monkeypatch.setattr(styles, "_font_dirs", lambda: [tmp_path])
    if corrupt:
        for name in ("Onest-Variable.ttf", "JetBrainsMono-Variable.ttf"):
            (tmp_path / name).write_bytes(b"not a font")
    with caplog.at_level(logging.WARNING):
        styles.apply_design_system(app, theme="light")
    assert styles.register_fonts() == ()
    assert app.font().family() == "Segoe UI"
    assert "Onest-Variable.ttf" in caplog.text
    assert "JetBrainsMono-Variable.ttf" in caplog.text
    del app._applauncher_font_families


def _composited_luminance(color, backdrop, opacity):
    from PySide6.QtGui import QColor
    foreground, background = QColor(color), QColor(backdrop)
    values = [(opacity * fg + (1 - opacity) * bg) / 255
              for fg, bg in zip(foreground.getRgb()[:3], background.getRgb()[:3])]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


@pytest.mark.parametrize("colors", [styles.LIGHT_COLORS, styles.DARK_COLORS])
@pytest.mark.parametrize("opacity", [0.75, 1.0])
@pytest.mark.parametrize("backdrop", ["#ffffff", "#101010"])
def test_text_and_control_contrast_at_supported_opacity(colors, opacity, backdrop):
    def ratio(foreground, background):
        first, second = sorted([_composited_luminance(foreground, backdrop, opacity),
                                _composited_luminance(background, backdrop, opacity)])
        return (second + 0.05) / (first + 0.05)

    backgrounds = (colors.background, colors.surface, colors.surface_alt, colors.surface_hover)
    for background in backgrounds:
        for foreground in (colors.text_primary, colors.text_secondary, colors.text_muted):
            assert ratio(foreground, background) >= 4.5
        assert ratio(colors.border, background) >= 3.0
    assert ratio(colors.on_accent, colors.accent) >= 4.5
    for foreground, soft in ((colors.accent_text or colors.accent, colors.accent_soft),
                             (colors.danger, colors.danger_soft)):
        for background in (*backgrounds, soft):
            assert ratio(foreground, background) >= 4.5
    for background in backgrounds:
        assert ratio(colors.warning, background) >= 4.5
    for background in (*backgrounds, colors.success_soft):
        assert ratio(colors.success, background) >= 3.0  # Copy-confirmation glyph.
