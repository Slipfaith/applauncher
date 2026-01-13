"""Design system and centralized styling for the launcher UI."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget


@dataclass(frozen=True)
class ColorTokens:
    background: str
    surface: str
    surface_alt: str
    surface_hover: str
    border: str
    border_soft: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_soft: str
    accent_hover: str
    accent_pressed: str
    focus_ring: str
    tooltip_background: str
    tooltip_text: str
    danger: str


@dataclass(frozen=True)
class TypographyTokens:
    font_family: str
    font_size_sm: int
    font_size_md: int
    font_size_lg: int
    weight_regular: int
    weight_semibold: int
    weight_bold: int
    letter_spacing_sm: float


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


TOKENS = DesignTokens(
    colors=ColorTokens(
        background="#fafafa",
        surface="#ffffff",
        surface_alt="#f5f5f5",
        surface_hover="#f5f5f5",
        border="#e0e0e0",
        border_soft="#ededed",
        text_primary="#1a1a1a",
        text_secondary="#6b6b6b",
        text_muted="#999999",
        accent="#0078d4",
        accent_soft="rgba(0, 120, 212, 0.12)",
        accent_hover="#0067b3",
        accent_pressed="#005a9c",
        focus_ring="rgba(0, 120, 212, 0.2)",
        tooltip_background="#2d2d2d",
        tooltip_text="#ffffff",
        danger="#c62828",
    ),
    typography=TypographyTokens(
        font_family="'Inter', 'Segoe UI', sans-serif",
        font_size_sm=12,
        font_size_md=14,
        font_size_lg=15,
        weight_regular=400,
        weight_semibold=600,
        weight_bold=700,
        letter_spacing_sm=0.2,
    ),
    spacing=SpacingTokens(
        none=0,
        xs=8,
        sm=12,
        md=16,
        lg=24,
        xl=32,
        xxl=40,
    ),
    radii=RadiusTokens(
        sm=4,
        md=6,
        lg=8,
        xl=12,
    ),
    shadows=ShadowTokens(
        floating=ShadowToken(blur=16, offset_x=0, offset_y=6, color="rgba(0, 0, 0, 0.12)"),
        raised=ShadowToken(blur=8, offset_x=0, offset_y=2, color="rgba(0, 0, 0, 0.08)"),
    ),
    sizes=SizeTokens(
        window_min=(680, 440),
        grid_button=(140, 140),
        grid_icon=48,
        title_bar_height=44,
        dialog_min_width=420,
        tray_icon=56,
        tab_min_width=88,
        combo_drop_down=22,
    ),
    layout=LayoutTokens(
        content_margins=(24, 24, 24, 24),
        content_spacing=16,
        search_spacing=8,
        grid_layout_margin=0,
        grid_layout_spacing=12,
        list_spacing=8,
    ),
)

def _rgba(color: QColor, alpha: float) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"


def _accent_variant(accent: QColor, factor: int) -> str:
    return accent.darker(factor).name(QColor.HexRgb)


def _search_icon(color: str) -> str:
    hex_color = color.lstrip("#")
    return (
        "data:image/svg+xml;utf8,"
        "<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24'>"
        f"<path fill='%23{hex_color}' d='M15.5 14h-.79l-.28-.27A6.5 6.5 0 1 0 14 15.5l.27.28v.79L20 21.5 21.5 20zM10 15a5 5 0 1 1 0-10 5 5 0 0 1 0 10'/>"
        "</svg>"
    )


def _build_color_tokens(accent: QColor, is_dark: bool) -> ColorTokens:
    if is_dark:
        base_background = "#1e1e1e"
        base_surface = "#2d2d2d"
        base_surface_alt = "#2a2a2a"
        base_surface_hover = "#2a2a2a"
        base_border = "#3a3a3a"
        base_border_soft = "#333333"
        base_text_primary = "#ffffff"
        base_text_secondary = "#b0b0b0"
        base_text_muted = "#8f8f8f"
        tooltip_background = "#f5f5f5"
        tooltip_text = "#1e1e1e"
        accent_color = accent.lighter(115)
    else:
        base_background = "#fafafa"
        base_surface = "#ffffff"
        base_surface_alt = "#f5f5f5"
        base_surface_hover = "#f5f5f5"
        base_border = "#e0e0e0"
        base_border_soft = "#ededed"
        base_text_primary = "#1a1a1a"
        base_text_secondary = "#6b6b6b"
        base_text_muted = "#999999"
        tooltip_background = "#2d2d2d"
        tooltip_text = "#ffffff"
        accent_color = accent

    accent_hex = accent_color.name(QColor.HexRgb)
    accent_soft = _rgba(accent_color, 0.12)
    focus_ring = _rgba(accent_color, 0.2)

    return ColorTokens(
        background=base_background,
        surface=base_surface,
        surface_alt=base_surface_alt,
        surface_hover=base_surface_hover,
        border=base_border,
        border_soft=base_border_soft,
        text_primary=base_text_primary,
        text_secondary=base_text_secondary,
        text_muted=base_text_muted,
        accent=accent_hex,
        accent_soft=accent_soft,
        accent_hover=_accent_variant(accent_color, 110),
        accent_pressed=_accent_variant(accent_color, 120),
        focus_ring=focus_ring,
        tooltip_background=tooltip_background,
        tooltip_text=tooltip_text,
        danger="#c62828",
    )


def resolve_tokens(app: QApplication, tokens: DesignTokens = TOKENS) -> DesignTokens:
    palette = app.palette()
    window_color = palette.color(QPalette.Window)
    is_dark = window_color.lightness() < 128
    accent_color = palette.color(QPalette.Highlight)
    if not accent_color.isValid():
        accent_color = QColor(tokens.colors.accent)
    colors = _build_color_tokens(accent_color, is_dark)
    return replace(tokens, colors=colors)


def build_stylesheet(tokens: DesignTokens = TOKENS) -> str:
    colors = tokens.colors
    spacing = tokens.spacing
    radii = tokens.radii
    typography = tokens.typography
    sizes = tokens.sizes
    separator = _rgba(QColor(colors.text_primary), 0.2)
    accent_half = _rgba(QColor(colors.accent), 0.5)
    accent_strong = _rgba(QColor(colors.accent), 0.8)
    search_icon = _search_icon(colors.text_muted)

    return f"""
    * {{
        font-family: {typography.font_family};
        font-size: {typography.font_size_md}px;
        color: {colors.text_primary};
    }}

    QMainWindow#mainWindow {{
        background-color: {colors.background};
        border-radius: {radii.xl}px;
    }}

    QWidget#centralContainer {{
        background-color: {colors.background};
        border-radius: {radii.xl}px;
    }}

    QTabWidget#mainTabs::pane {{
        border: none;
        margin-top: 0;
    }}

    QTabBar {{
        background-color: transparent;
        padding: 0;
    }}

    QTabBar::tab {{
        background: transparent;
        color: {colors.text_secondary};
        border: none;
        padding: 0 {spacing.sm}px;
        margin-right: {spacing.sm}px;
        min-width: {sizes.tab_min_width}px;
        height: 44px;
        font-weight: {typography.weight_regular};
    }}

    QTabBar::tab:selected {{
        color: {colors.text_primary};
        font-weight: {typography.weight_bold};
        border-bottom: 3px solid {colors.accent};
        padding-bottom: 9px;
    }}

    QTabBar::tab:hover {{
        background: {colors.surface_hover};
    }}

    QTabBar::tab:!selected {{
        border-bottom: 3px solid transparent;
        padding-bottom: 9px;
    }}

    QTabBar#groupTabs::tab:last {{
        background: transparent;
        color: {colors.text_secondary};
        min-width: 44px;
        max-width: 44px;
    }}

    QTabBar#groupTabs::tab:last:hover {{
        background: {colors.surface_hover};
    }}

    QWidget#titleBar {{
        background-color: {colors.background};
        border-bottom: 1px solid {colors.border};
        border-top-left-radius: {radii.xl}px;
        border-top-right-radius: {radii.xl}px;
    }}

    QLabel[role="titleText"] {{
        color: {colors.text_secondary};
        font-size: {typography.font_size_sm}px;
        font-weight: {typography.weight_semibold};
        letter-spacing: {typography.letter_spacing_sm}px;
    }}

    QPushButton {{
        background-color: {colors.surface};
        color: {colors.text_primary};
        border: none;
        border-radius: {radii.md}px;
        padding: {spacing.sm}px {spacing.lg}px;
        font-weight: {typography.weight_semibold};
        min-height: 44px;
        min-width: 44px;
    }}

    QPushButton:hover {{
        background-color: {colors.surface_hover};
    }}

    QPushButton:pressed {{
        background-color: {colors.surface_alt};
    }}

    QPushButton:focus {{
        border: 2px solid {colors.accent};
    }}

    QPushButton[variant="accent"] {{
        background-color: {colors.accent};
        color: #ffffff;
        border: none;
        font-size: {typography.font_size_md}px;
        font-weight: {typography.weight_semibold};
    }}

    QPushButton[variant="accent"]:hover {{
        background-color: {colors.accent_hover};
    }}

    QPushButton[variant="accent"]:pressed {{
        background-color: {colors.accent_pressed};
    }}

    QPushButton[variant="control"] {{
        background-color: {colors.surface_alt};
        border: none;
        font-weight: {typography.weight_semibold};
    }}

    QPushButton[variant="control"]:checked {{
        background-color: {colors.accent_soft};
        color: {colors.text_primary};
    }}

    QPushButton[role="viewToggle"] {{
        padding: {spacing.xs}px {spacing.sm}px;
        min-width: {sizes.combo_drop_down}px;
        font-size: {typography.font_size_md}px;
    }}

    QPushButton[variant="secondary"] {{
        background-color: transparent;
        color: {colors.accent};
        border: none;
    }}

    QPushButton[variant="secondary"]:hover {{
        background-color: {colors.accent_soft};
    }}

    QPushButton[variant="secondary"]:pressed {{
        background-color: {colors.accent_soft};
    }}

    QPushButton[variant="ghost"] {{
        background-color: transparent;
        border-color: transparent;
        color: {colors.text_secondary};
    }}

    QPushButton[variant="ghost"]:hover {{
        background-color: {colors.surface_hover};
        border-color: {colors.border_soft};
    }}

    QPushButton[variant="danger"] {{
        background-color: transparent;
        border-color: transparent;
        color: {colors.text_secondary};
    }}

    QPushButton[variant="danger"]:hover {{
        background-color: {colors.danger};
        border-color: {colors.danger};
        color: {colors.surface};
    }}

    QPushButton[role="titleButton"] {{
        border-radius: {radii.sm}px;
        padding: {spacing.xs}px {spacing.sm}px;
        font-size: {typography.font_size_md}px;
        min-height: 44px;
        min-width: 44px;
    }}

    QPushButton[role="appTile"] {{
        background-color: {colors.surface};
        border-radius: {radii.lg}px;
        padding: {spacing.md}px;
        font-size: {typography.font_size_sm}px;
        font-weight: {typography.weight_semibold};
        text-align: center;
        color: {colors.text_primary};
    }}

    QPushButton[role="appTile"][iconMode="full"] {{
        padding: 0px;
    }}

    QPushButton[role="appTile"]:hover {{
        background-color: {colors.surface_hover};
    }}

    QWidget[role="listItem"] {{
        background: {colors.surface};
        border: none;
        border-radius: {radii.lg}px;
    }}

    QWidget[role="listItem"]:hover {{
        background: {colors.surface_hover};
    }}

    QLabel[role="listTitle"] {{
        font-weight: {typography.weight_semibold};
        color: {colors.text_primary};
    }}

    QLabel[role="listSubtitle"] {{
        color: {colors.text_muted};
        font-size: {typography.font_size_sm}px;
    }}

    QLineEdit {{
        background-color: {colors.surface};
        color: {colors.text_primary};
        border: 1px solid {colors.border};
        border-radius: {radii.lg}px;
        padding: 12px 16px;
        font-size: 15px;
        min-height: 44px;
    }}

    QLineEdit:focus {{
        border: 2px solid {colors.accent};
        padding: 11px 15px;
    }}

    QLineEdit::placeholder {{
        color: {colors.text_muted};
        font-size: 15px;
    }}

    QComboBox {{
        background-color: {colors.surface};
        color: {colors.text_primary};
        border: 1px solid {colors.border};
        border-radius: {radii.md}px;
        padding: {spacing.xs}px {spacing.md}px;
    }}

    QComboBox:focus {{
        border: 2px solid {colors.accent};
        padding: {spacing.xs - 1}px {spacing.md - 1}px;
    }}

    QComboBox::drop-down {{
        border: none;
        width: {sizes.combo_drop_down}px;
    }}

    QDialog {{
        background-color: {colors.surface};
    }}

    QDialog QLabel {{
        font-size: {typography.font_size_md}px;
        font-weight: {typography.weight_semibold};
        color: {colors.text_primary};
    }}

    QMenu {{
        background-color: {colors.surface};
        border: 1px solid {colors.border_soft};
        border-radius: {radii.md}px;
        padding: {spacing.xs}px;
    }}

    QMenu::item {{
        padding: {spacing.xs}px {spacing.md}px;
        border-radius: {radii.sm}px;
        color: {colors.text_primary};
    }}

    QMenu::item:selected {{
        background-color: {colors.surface_hover};
        color: {colors.text_primary};
    }}

    QScrollArea {{
        background: transparent;
        border: none;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px 0 2px 0;
    }}

    QScrollBar::handle:vertical {{
        background: {accent_half};
        min-height: 24px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {accent_strong};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
        width: 0px;
    }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 0 2px 0 2px;
    }}

    QScrollBar::handle:horizontal {{
        background: {accent_half};
        min-width: 24px;
        border-radius: 4px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background: {accent_strong};
    }}

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0px;
        height: 0px;
    }}

    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    QToolTip {{
        background-color: {colors.tooltip_background};
        color: {colors.tooltip_text};
        border-radius: {radii.sm}px;
        padding: 6px 10px;
    }}

    QToolButton {{
        background: transparent;
        border: none;
        border-radius: {radii.md}px;
        min-width: 44px;
        min-height: 44px;
    }}

    QToolButton:hover {{
        background-color: {colors.surface_hover};
    }}

    QToolButton:focus {{
        border: 2px solid {colors.accent};
    }}

    [role="iconButton"] {{
        min-width: 32px;
        min-height: 32px;
        border-radius: 16px;
        padding: 0px;
    }}

    [role="iconButton"]:hover {{
        background-color: {colors.surface_hover};
    }}

    QLineEdit#searchInput {{
        padding-left: 44px;
        background-image: url("{search_icon}");
        background-repeat: no-repeat;
        background-position: 16px center;
    }}

    QWidget[role="appTile"] {{
        min-width: 140px;
        min-height: 140px;
    }}

    QWidget[role="separator"] {{
        background-color: {separator};
    }}
    """


def apply_design_system(app: QApplication, tokens: DesignTokens = TOKENS) -> None:
    resolved = resolve_tokens(app, tokens)
    app.setStyleSheet(build_stylesheet(resolved))


def apply_shadow(widget: QWidget, shadow: ShadowToken) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(shadow.blur)
    effect.setXOffset(shadow.offset_x)
    effect.setYOffset(shadow.offset_y)
    effect.setColor(QColor(shadow.color))
    widget.setGraphicsEffect(effect)
