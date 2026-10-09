"""Design system and centralized styling for the launcher UI.

Values come from the AppLauncher design system (tokens.json). Two colour
themes, light and dark; ``apply_design_system(app, theme="auto")`` follows the
Windows app theme and re-applies itself when it changes.
"""

from __future__ import annotations

import logging
import re
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ColorTokens:
    # Original field names are kept so every existing import keeps working.
    background: str  # design token: surface (window ground)
    surface: str  # surface-raised (tiles on hover, cards, menus, dialogs)
    surface_alt: str  # surface-sunken (inputs, tab track, pressed)
    surface_hover: str  # hover fill for ghost controls
    border: str  # line-strong (control borders that must be seen)
    border_soft: str  # line (hairlines, card edges)
    text_primary: str  # ink
    text_secondary: str  # ink-muted
    text_muted: str  # ink-subtle (placeholders, disabled)
    accent: str  # brand
    accent_soft: str  # brand-soft (selection)
    accent_hover: str  # brand-hover
    danger: str
    # Added by the design system
    on_accent: str = "#ffffff"
    danger_soft: str = "#fde6ea"
    success: str = "#137a3f"
    success_soft: str = "#e2f6ea"
    warning: str = "#9a5800"
    warning_soft: str = "#fff1d6"
    brand_deep: str = "#00269c"
    sky: str = "#1fa9fb"
    sky_soft: str = "#dff3ff"
    tooltip_bg: str = "#0a1330"
    tooltip_text: str = "#ffffff"
    accent_text: str = ""  # Text may need a stronger contrast than accent fills.


@dataclass(frozen=True)
class TypographyTokens:
    font_family: str
    font_size_sm: float
    font_size_md: float
    font_size_lg: float
    weight_regular: int
    weight_semibold: int
    weight_bold: int
    letter_spacing_sm: float
    font_family_mono: str = "'JetBrains Mono', 'Cascadia Mono', Consolas, monospace"
    font_size_body: float = 10.5


@dataclass(frozen=True)
class SpacingTokens:
    none: int
    xs: int
    sm: int
    md: int
    lg: int
    xl: int
    xxl: int


@dataclass(frozen=True)
class RadiusTokens:
    sm: int
    md: int
    lg: int
    xl: int


@dataclass(frozen=True)
class ShadowToken:
    blur: int
    offset_x: int
    offset_y: int
    color: str


@dataclass(frozen=True)
class ShadowTokens:
    floating: ShadowToken
    raised: ShadowToken


@dataclass(frozen=True)
class SizeTokens:
    window_min: tuple[int, int]
    grid_button: tuple[int, int]
    grid_icon: int
    title_bar_height: int
    dialog_min_width: int
    tray_icon: int
    tab_min_width: int
    combo_drop_down: int


@dataclass(frozen=True)
class LayoutTokens:
    content_margins: tuple[int, int, int, int]
    content_spacing: int
    search_spacing: int
    grid_layout_margin: int
    grid_layout_spacing: int
    list_spacing: int


@dataclass(frozen=True)
class DesignTokens:
    colors: ColorTokens
    typography: TypographyTokens
    spacing: SpacingTokens
    radii: RadiusTokens
    shadows: ShadowTokens
    sizes: SizeTokens
    layout: LayoutTokens


LIGHT_COLORS = ColorTokens(
    background="#f3f5fa",
    surface="#ffffff",
    surface_alt="#e8ecf5",
    surface_hover="#e8ecf5",
    border="#57647c",
    border_soft="#dbe1ec",
    text_primary="#0a1330",
    text_secondary="#2d3953",
    text_muted="#303c56",
    accent="#0839b5",
    accent_soft="#e4ecff",
    accent_hover="#0838a8",
    danger="#94112c",
    on_accent="#ffffff",
    danger_soft="#fde6ea",
    success="#064920",
    success_soft="#e2f6ea",
    warning="#5f3000",
    warning_soft="#fff1d6",
    brand_deep="#00269c",
    sky="#1fa9fb",
    sky_soft="#dff3ff",
    tooltip_bg="#0a1330",
    tooltip_text="#ffffff",
    accent_text="#0734ab",
)

DARK_COLORS = ColorTokens(
    background="#0b1020",
    surface="#141b2e",
    surface_alt="#070b17",
    surface_hover="#1c2540",
    border="#8593b0",
    border_soft="#232c44",
    text_primary="#edf1fa",
    text_secondary="#c6cee3",
    text_muted="#bdc7de",
    accent="#629aff",
    accent_soft="#13265a",
    accent_hover="#7eacff",
    danger="#ffb6c4",
    on_accent="#000000",
    danger_soft="#3a0f18",
    success="#4fd88a",
    success_soft="#0e2e1d",
    warning="#f9c656",
    warning_soft="#33240a",
    brand_deep="#00269c",
    sky="#3cb8ff",
    sky_soft="#0b2b45",
    tooltip_bg="#edf1fa",
    tooltip_text="#0a1330",
    accent_text="#b0ccff",
)


TOKENS = DesignTokens(
    colors=LIGHT_COLORS,
    typography=TypographyTokens(
        font_family="'Onest', 'Segoe UI Variable Text', 'Segoe UI', sans-serif",
        font_size_sm=9,  # points; Qt handles display scaling
        font_size_md=9.75,
        font_size_lg=11.25,
        weight_regular=400,
        weight_semibold=600,
        weight_bold=650,
        letter_spacing_sm=0.0,
    ),
    spacing=SpacingTokens(
        none=0,
        xs=4,
        sm=6,
        md=8,
        lg=8,
        xl=12,
        xxl=12,
    ),
    radii=RadiusTokens(
        sm=6,  # menu items, title buttons, kbd
        md=8,  # buttons, inputs, list rows, window corners
        lg=12,  # tiles, tab track, menus
        xl=16,  # note cards, popups
    ),
    shadows=ShadowTokens(
        floating=ShadowToken(blur=32, offset_x=0, offset_y=8, color="rgba(10, 19, 48, 46)"),
        raised=ShadowToken(blur=18, offset_x=0, offset_y=4, color="rgba(10, 19, 48, 34)"),
    ),
    sizes=SizeTokens(
        window_min=(680, 440),
        grid_button=(120, 96),  # kept: custom tile images are cropped to this ratio
        grid_icon=40,
        title_bar_height=44,
        dialog_min_width=420,
        tray_icon=56,
        tab_min_width=48,
        combo_drop_down=24,
    ),
    layout=LayoutTokens(
        content_margins=(12, 8, 12, 8),
        content_spacing=8,
        search_spacing=8,
        grid_layout_margin=12,
        grid_layout_spacing=8,
        list_spacing=2,
    ),
)

_STATE: dict = {"colors": LIGHT_COLORS, "theme": "light", "mode": "auto"}


def active_colors() -> ColorTokens:
    """Colours of the theme currently applied (use for anything painted in Python)."""
    return _STATE["colors"]


def active_theme() -> str:
    return _STATE["theme"]


def theme_mode() -> str:
    """Requested mode, independent of the resolved light/dark palette."""
    return _STATE["mode"]


def to_qcolor(value: str) -> QColor:
    """QColor from '#rrggbb' or 'rgba(r, g, b, a)' with a 0-255 alpha."""
    match = re.fullmatch(r"\s*rgba?\(([^)]*)\)\s*", value)
    if match:
        parts = [float(p) for p in match.group(1).split(",")]
        r, g, b = (int(p) for p in parts[:3])
        a = parts[3] if len(parts) > 3 else 255
        if a <= 1.0 and "." in match.group(1).split(",")[-1]:
            a = a * 255
        return QColor(r, g, b, int(a))
    return QColor(value)


def _font_dirs() -> list[Path]:
    dirs = [Path(__file__).resolve().parent / "fonts"]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        dirs.append(Path(bundle) / "applauncher" / "gui" / "fonts")
        dirs.append(Path(bundle) / "fonts")
    return dirs


def register_fonts() -> tuple[str, ...]:
    """Register the bundled Onest and JetBrains Mono faces (falls back to Segoe UI)."""
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("Font registration requires QApplication")
    cached = getattr(app, "_applauncher_font_families", None)
    if cached is not None:
        return cached
    families: list[str] = []
    for filename in ("Onest-Variable.ttf", "JetBrainsMono-Variable.ttf"):
        for directory in _font_dirs():
            path = directory / filename
            if not path.is_file():
                continue
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id >= 0:
                families.extend(QFontDatabase.applicationFontFamilies(font_id))
                break
            logger.warning("Не удалось загрузить шрифт %s; используется резервный шрифт", path)
        else:
            logger.warning("Шрифт %s недоступен; используется системный шрифт", filename)
    app._applauncher_font_families = tuple(dict.fromkeys(families))
    return app._applauncher_font_families


def _chevron_image(color: str) -> str:
    """Render the combo-box chevron once per colour; returns a QSS-safe file path."""
    path = Path(tempfile.gettempdir()) / f"applauncher-chevron-{color.lstrip('#')}.png"
    if not path.exists():
        image = QImage(32, 32, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(color), 3.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        chevron = QPainterPath()
        chevron.moveTo(9, 13)
        chevron.lineTo(16, 20)
        chevron.lineTo(23, 13)
        painter.drawPath(chevron)
        painter.end()
        image.save(str(path))
    return path.as_posix()


def _resolve_theme(app: QApplication, theme: str) -> str:
    if theme in ("light", "dark"):
        return theme
    try:
        scheme = app.styleHints().colorScheme()
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"
    except AttributeError:  # Qt < 6.5
        return "light"


def build_palette(colors: ColorTokens) -> QPalette:
    pal = QPalette()
    roles = {
        QPalette.Window: colors.background,
        QPalette.WindowText: colors.text_primary,
        QPalette.Base: colors.surface,
        QPalette.AlternateBase: colors.surface_alt,
        QPalette.Text: colors.text_primary,
        QPalette.Button: colors.surface,
        QPalette.ButtonText: colors.text_primary,
        QPalette.Highlight: colors.accent,
        QPalette.HighlightedText: colors.on_accent,
        QPalette.ToolTipBase: colors.tooltip_bg,
        QPalette.ToolTipText: colors.tooltip_text,
        QPalette.PlaceholderText: colors.text_muted,
        QPalette.Link: colors.accent_text or colors.accent,
        QPalette.Mid: colors.border_soft,
    }
    for role, value in roles.items():
        pal.setColor(role, QColor(value))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(colors.text_muted))
    return pal


def build_stylesheet(tokens: DesignTokens = TOKENS) -> str:
    c = tokens.colors
    accent_text = c.accent_text or c.accent
    s = tokens.spacing
    r = tokens.radii
    t = tokens.typography
    z = tokens.sizes

    return f"""
    * {{
        font-family: {t.font_family};
        font-size: {t.font_size_md}pt;
        color: {c.text_primary};
        selection-background-color: {c.accent};
        selection-color: {c.on_accent};
    }}

    /* ---------- Window shell ---------- */
    QMainWindow#mainWindow, QWidget#centralContainer {{ background-color: transparent; }}

    QWidget#windowSurface {{
        background-color: {c.background};
        border: 1px solid {c.border_soft};
        border-radius: {r.md}px;
    }}

    QWidget#titleBar {{
        background-color: transparent;
        border: none;
    }}

    QLabel[role="windowTitle"] {{
        font-size: {t.font_size_md}pt;
        font-weight: {t.weight_semibold};
        color: {c.text_primary};
    }}

    QLabel[role="titleText"] {{
        font-size: {t.font_size_lg}pt;
        font-weight: {t.weight_semibold};
        color: {c.text_primary};
    }}

    QLabel[role="subtitleText"] {{ color: {c.text_secondary}; }}

    QLabel[role="errorText"] {{
        color: {c.warning};
        font-size: {t.font_size_sm}pt;
    }}

    QLabel[role="hotkeyDisplay"] {{
        font-family: {t.font_family_mono};
        font-size: 13.5pt;
        font-weight: 500;
        color: {c.text_primary};
        background: {c.surface_alt};
        border: 1px solid {c.border_soft};
        border-radius: {r.md}px;
        padding: {s.md}px;
    }}

    QWidget[role="hudStrip"] {{ background: transparent; }}

    QWidget[role="hudSlot"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: {r.md}px;
    }}

    QWidget[role="hudSlot"][hovered="true"] {{
        background: {c.surface};
        border-color: {c.border_soft};
    }}

    /* ---------- Section tabs: segmented control ---------- */
    QTabBar#sectionTabs {{
        background: {c.surface_alt};
        border-radius: {r.lg - 2}px;
    }}

    QTabBar#sectionTabs::tab {{
        background: transparent;
        color: {c.text_secondary};
        border: 1px solid transparent;
        border-radius: {r.md}px;
        padding: 5px {s.md}px;
        margin: 3px 1px;
        font-weight: 500;
    }}

    QTabBar#sectionTabs::tab:first {{ margin-left: 3px; }}
    QTabBar#sectionTabs::tab:last {{ margin-right: 3px; }}
    QTabBar#sectionTabs::tab:hover {{ color: {c.text_primary}; }}

    QTabBar#sectionTabs::tab:selected {{
        background: {c.surface};
        color: {c.text_primary};
        border-color: {c.border_soft};
    }}

    /* ---------- Group tabs: underline, one level below sections ---------- */
    QTabWidget#mainTabs::pane {{ border: none; margin: 0; }}
    QTabWidget#mainTabs::tab-bar {{ left: 0; }}

    QTabBar#groupTabs {{
        background: transparent;
        border-bottom: 1px solid {c.border_soft};
    }}

    QTabBar#groupTabs::tab {{
        background: transparent;
        color: {c.text_secondary};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 6px {s.md - 2}px 7px {s.md - 2}px;
        margin-right: 2px;
        min-width: {z.tab_min_width}px;
        max-width: 160px;
        font-weight: 500;
    }}

    QTabBar#groupTabs::tab:hover {{ color: {c.text_primary}; }}

    QTabBar#groupTabs::tab:selected {{
        color: {c.text_primary};
        border-bottom-color: {c.accent};
    }}

    QTabBar QToolButton {{
        background: {c.background};
        border: none;
        border-radius: {r.sm}px;
    }}

    /* ---------- Buttons ---------- */
    QPushButton {{
        background-color: {c.surface};
        color: {c.text_primary};
        border: 1px solid {c.border_soft};
        border-radius: {r.md}px;
        padding: 7px {s.md}px;
        font-weight: 500;
    }}

    QPushButton:hover {{ border-color: {c.border}; }}
    QPushButton:pressed {{ background-color: {c.surface_alt}; }}
    QPushButton:focus {{ border-color: {c.accent}; }}

    QPushButton:disabled {{
        background-color: {c.surface_alt};
        color: {c.text_muted};
        border-color: transparent;
    }}

    QPushButton[variant="accent"] {{
        background-color: {c.accent};
        color: {c.on_accent};
        border: 1px solid {c.accent};
        font-weight: {t.weight_semibold};
    }}

    QPushButton[variant="accent"]:hover {{
        background-color: {c.accent_hover};
        border-color: {c.accent_hover};
    }}

    QPushButton[variant="accent"]:disabled {{
        background-color: {c.surface_alt};
        color: {c.text_muted};
        border-color: transparent;
    }}

    QPushButton[variant="secondary"] {{
        background-color: {c.surface};
        border-color: {c.border_soft};
    }}

    QPushButton[variant="control"], QPushButton[variant="ghost"] {{
        background-color: transparent;
        border-color: transparent;
        color: {c.text_secondary};
    }}

    QPushButton[variant="control"]:hover, QPushButton[variant="ghost"]:hover {{
        background-color: {c.surface_hover};
        color: {c.text_primary};
    }}

    QPushButton[variant="control"]:checked {{
        background-color: {c.accent_soft};
        color: {accent_text};
    }}

    QPushButton[variant="danger"] {{
        background-color: transparent;
        border-color: transparent;
        color: {c.danger};
    }}

    QPushButton[variant="danger"]:hover {{
        background-color: {c.danger_soft};
        border-color: transparent;
    }}

    QPushButton[variant="danger"][role="iconButton"] {{ color: {c.text_muted}; }}
    QPushButton[variant="danger"][role="iconButton"]:hover {{ color: {c.danger}; }}

    QPushButton[role="viewToggle"] {{
        padding: 0;
        min-width: 34px;
        max-width: 34px;
        min-height: 34px;
        max-height: 34px;
    }}

    QPushButton[role="titleButton"] {{
        background: transparent;
        border: none;
        border-radius: {r.sm}px;
        padding: 0;
        min-width: 36px;
        max-width: 36px;
        min-height: 28px;
        max-height: 28px;
    }}

    QPushButton[role="titleButton"]:hover {{ background: {c.surface_hover}; }}
    QPushButton[role="titleButton"][variant="danger"]:hover {{ background: {c.danger}; }}

    QPushButton[role="titleAction"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {c.text_secondary};
        padding: 5px {s.md - 2}px;
    }}

    QPushButton[role="titleAction"]:hover {{
        background: {c.surface_hover};
        color: {c.text_primary};
    }}

    QPushButton[role="iconButton"] {{ padding: 0px; }}

    /* ---------- Tiles ---------- */
    QPushButton[role="appTile"] {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: {r.lg}px;
        padding: {s.sm}px;
        font-size: {t.font_size_sm}pt;
        font-weight: 500;
        color: {c.text_primary};
    }}

    QPushButton[role="appTile"][iconMode="full"] {{ padding: 0px; }}

    QPushButton[role="appTile"]:hover {{
        background-color: {c.surface};
        border-color: {c.border_soft};
    }}

    QPushButton[role="appTile"]:pressed {{
        background-color: {c.surface_alt};
        border-color: {c.border_soft};
    }}

    QPushButton[role="appTile"]:focus {{ border-color: {c.accent}; }}

    QPushButton[role="appTile"][dropTarget="true"] {{
        background-color: {c.sky_soft};
        border: 1px dashed {c.accent};
    }}

    QPushButton[role="tileCopy"] {{
        background: {c.surface_alt};
        border: none;
        border-radius: {r.sm}px;
        padding: 0;
        min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px;
    }}

    QPushButton[role="tileCopy"]:hover {{ background: {c.border_soft}; }}
    QPushButton[role="tileCopy"][state="done"] {{ background: {c.success_soft}; }}

    /* ---------- List rows ---------- */
    QWidget[role="listItem"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: {r.md}px;
    }}

    QWidget[role="listItem"]:hover {{
        background: {c.surface};
        border-color: {c.border_soft};
    }}

    QWidget[role="listItem"][dropTarget="true"] {{
        background: {c.sky_soft};
        border: 1px dashed {c.accent};
    }}

    QLabel[role="listTitle"] {{
        font-size: {t.font_size_body}pt;
        font-weight: 500;
        color: {c.text_primary};
        background: transparent;
    }}

    QLabel[role="listSubtitle"] {{
        font-family: {t.font_family_mono};
        font-size: {t.font_size_sm}pt;
        color: {c.text_secondary};
        background: transparent;
    }}

    /* ---------- Inputs ---------- */
    QLineEdit, QComboBox, QSpinBox {{
        background-color: {c.surface_alt};
        color: {c.text_primary};
        border: 1px solid transparent;
        border-radius: {r.md}px;
        padding: 7px {s.md - 2}px;
        font-size: {t.font_size_md}pt;
    }}

    QLineEdit:hover, QComboBox:hover {{ border-color: {c.border_soft}; }}

    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
        background-color: {c.surface};
        border-color: {c.accent};
    }}

    QLineEdit:read-only {{ color: {c.text_secondary}; }}

    QDialog QLineEdit, QDialog QComboBox {{ border-color: {c.border_soft}; }}

    QComboBox::drop-down {{
        border: none;
        width: {z.combo_drop_down}px;
    }}

    QComboBox::down-arrow {{
        image: url("{_chevron_image(c.text_secondary)}");
        width: 14px;
        height: 14px;
    }}

    QComboBox QAbstractItemView {{
        background: {c.surface};
        border: 1px solid {c.border_soft};
        border-radius: {r.md}px;
        padding: {s.xs}px;
        outline: none;
        selection-background-color: {c.accent_soft};
        selection-color: {c.text_primary};
    }}

    QCheckBox {{ spacing: {s.sm}px; }}

    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {c.border};
        border-radius: 4px;
        background: {c.surface};
    }}

    QCheckBox::indicator:checked {{
        background: {c.accent};
        border-color: {c.accent};
    }}

    QSlider::groove:horizontal {{
        height: 4px;
        background: {c.surface_alt};
        border-radius: 2px;
    }}

    QSlider::sub-page:horizontal {{
        background: {c.accent};
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        width: 16px; height: 16px;
        margin: -7px 0;
        border-radius: 8px;
        background: {c.surface};
        border: 1px solid {c.border};
    }}

    /* ---------- Dialogs, menus, tooltips ---------- */
    QDialog {{ background-color: {c.surface}; }}

    QDialog QLabel {{
        font-size: {t.font_size_md}pt;
        font-weight: 500;
        color: {c.text_primary};
    }}

    QLabel#iconPreview {{
        background: {c.surface_alt};
        border: 1px dashed {c.border_soft};
        border-radius: {r.lg}px;
    }}

    QMenu {{
        background-color: {c.surface};
        border: 1px solid {c.border_soft};
        border-radius: {r.md}px;
        padding: {s.xs}px;
    }}

    QMenu::item {{
        padding: 7px {s.md}px 7px {s.sm + 2}px;
        border-radius: {r.sm}px;
        color: {c.text_primary};
        background: transparent;
    }}

    QMenu::item:selected {{
        background-color: {c.surface_hover};
        color: {c.text_primary};
    }}

    QMenu::item:disabled {{ color: {c.text_muted}; }}

    QMenu::separator {{
        height: 1px;
        background: {c.border_soft};
        margin: {s.xs}px 6px;
    }}

    QToolTip {{
        background-color: {c.tooltip_bg};
        color: {c.tooltip_text};
        border: none;
        border-radius: {r.sm}px;
        padding: 5px {s.sm}px;
        font-size: {t.font_size_sm}pt;
    }}

    QMessageBox QLabel {{ font-weight: 400; }}

    /* ---------- Lists (clipboard, universal search) ---------- */
    QListWidget {{
        background: {c.surface};
        border: 1px solid {c.border_soft};
        border-radius: {r.lg}px;
        padding: {s.xs}px;
        outline: none;
    }}

    QListWidget::item {{
        padding: {s.sm}px {s.sm + 2}px;
        border-radius: {r.sm}px;
        color: {c.text_primary};
    }}

    QListWidget::item:hover {{ background: {c.surface_hover}; }}

    QListWidget::item:selected {{
        background: {c.accent_soft};
        color: {c.text_primary};
    }}

    QDialog#universalSearch {{
        background: {c.surface};
        border: 1px solid {c.border};
    }}

    /* ---------- Scrolling ---------- */
    QScrollArea {{
        background: transparent;
        border: none;
    }}

    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QWidget#qt_scrollarea_viewport {{ background: transparent; }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        background: {c.border_soft};
        border-radius: 3px;
        min-height: 32px;
    }}

    QScrollBar::handle:vertical:hover {{ background: {c.border}; }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 2px;
    }}

    QScrollBar::handle:horizontal {{
        background: {c.border_soft};
        border-radius: 3px;
        min-width: 32px;
    }}

    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* ---------- Notes ---------- */
    QDialog#noteEditorPopup {{
        background: {c.surface};
        border: 1px solid {c.border};
        border-radius: {r.xl}px;
    }}

    QDialog#noteEditorPopup QLineEdit {{
        font-size: {t.font_size_lg}pt;
        font-weight: {t.weight_semibold};
        background: transparent;
        border-color: transparent;
    }}

    QDialog#noteEditorPopup QLineEdit:focus {{
        background: {c.surface_alt};
        border-color: transparent;
    }}

    QDialog#noteEditorPopup QTextEdit {{
        background: {c.surface};
        border: 1px solid {c.border_soft};
        border-radius: {r.md}px;
        padding: {s.xs}px;
        font-size: {t.font_size_body}pt;
    }}

    QPushButton[role="noteFormatButton"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: {r.sm}px;
        padding: 0px;
        color: {c.text_secondary};
    }}

    QPushButton[role="noteFormatButton"]:hover {{
        background: {c.surface_hover};
        color: {c.text_primary};
    }}

    QPushButton[role="noteFormatButton"]:checked {{
        background: {c.accent_soft};
        color: {accent_text};
    }}

    QWidget[role="noteCard"] {{
        background: {c.surface};
        border: 1px solid {c.border_soft};
        border-radius: {r.xl}px;
    }}

    QWidget[role="noteCard"]:hover {{ border-color: {c.border}; }}

    QLineEdit[role="noteTitleInput"] {{
        border: 1px solid transparent;
        background: transparent;
        border-radius: {r.sm}px;
        font-weight: {t.weight_semibold};
        font-size: {t.font_size_lg}pt;
        padding: 2px {s.xs}px;
        color: {c.text_primary};
    }}

    QLineEdit[role="noteTitleInput"]:focus {{
        border: 1px solid transparent;
        background: {c.surface_alt};
    }}

    QWidget[role="noteCard"] QTextEdit {{
        border: none;
        background: transparent;
        font-size: {t.font_size_body}pt;
    }}

    QPushButton[role="titleAction"]:focus,
    QPushButton[role="titleButton"]:focus,
    QPushButton[role="iconButton"]:focus,
    QPushButton[role="viewToggle"]:focus,
    QPushButton[role="tileCopy"]:focus,
    QPushButton[role="noteFormatButton"]:focus {{
        border: 1px solid {c.accent};
    }}

    QWidget[role="listItem"]:focus, QWidget[role="hudSlot"]:focus {{
        border: 1px solid {c.accent};
    }}

    QTabBar QToolButton:focus {{ border: 1px solid {c.accent}; }}
    """


def _apply_theme(app: QApplication, tokens: DesignTokens, name: str) -> None:
    colors = DARK_COLORS if name == "dark" else LIGHT_COLORS
    if tokens is not TOKENS and name == "light":
        colors = tokens.colors
    _STATE["colors"] = colors
    _STATE["theme"] = name
    themed = replace(tokens, colors=colors)
    app.setPalette(build_palette(colors))
    stylesheet = build_stylesheet(themed)
    if app.styleSheet() != stylesheet:
        app.setStyleSheet(stylesheet)
    # Custom-painted children use active_colors(), including hidden tabs/popups.
    for widget in app.allWidgets():
        widget.update()


def apply_design_system(
    app: QApplication, tokens: DesignTokens = TOKENS, theme: str = "auto"
) -> None:
    """Apply fonts and theme; retain one system callback per QApplication."""
    if theme not in {"auto", "light", "dark"}:
        raise ValueError(f"Unknown theme: {theme}")
    families = register_fonts()
    font = QFont("Onest" if "Onest" in families else "Segoe UI")
    font.setPointSizeF(tokens.typography.font_size_md)
    app.setFont(font)
    app._applauncher_theme_mode = theme
    app._applauncher_design_tokens = tokens
    _STATE["mode"] = theme
    hints = app.styleHints()
    # Qt >= 6.8 also applies the choice to native window decorations and dialogs.
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme({"auto": Qt.ColorScheme.Unknown,
                              "light": Qt.ColorScheme.Light,
                              "dark": Qt.ColorScheme.Dark}[theme])
    if not hasattr(app, "_applauncher_theme_callback"):
        def on_scheme_changed(scheme: Qt.ColorScheme) -> None:
            if app._applauncher_theme_mode == "auto":
                name = "dark" if scheme == Qt.ColorScheme.Dark else "light"
                _apply_theme(app, app._applauncher_design_tokens, name)
        app.styleHints().colorSchemeChanged.connect(on_scheme_changed)
        app._applauncher_theme_callback = on_scheme_changed
    _apply_theme(app, tokens, _resolve_theme(app, theme))


def apply_shadow(widget: QWidget, shadow: ShadowToken) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(shadow.blur)
    effect.setXOffset(shadow.offset_x)
    effect.setYOffset(shadow.offset_y)
    effect.setColor(to_qcolor(shadow.color))
    widget.setGraphicsEffect(effect)
