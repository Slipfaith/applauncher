"""Design system and centralized styling for the launcher UI."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor
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
        background="#f8fafc",
        surface="#ffffff",
        surface_alt="#f1f5f9",
        surface_hover="#eef2f7",
        border="#d7dee7",
        border_soft="#e5eaf1",
        text_primary="#1f2937",
        text_secondary="#475569",
        text_muted="#64748b",
        accent="#2563eb",
        accent_soft="#dbeafe",
        accent_hover="#1d4ed8",
        danger="#dc2626",
    ),
    typography=TypographyTokens(
        font_family="'Inter', 'Segoe UI', sans-serif",
        font_size_sm=12,
        font_size_md=13,
        font_size_lg=15,
        weight_regular=400,
        weight_semibold=600,
        weight_bold=700,
        letter_spacing_sm=0.2,
    ),
    spacing=SpacingTokens(
        none=0,
        xs=4,
        sm=8,
        md=12,
        lg=16,
        xl=20,
        xxl=24,
    ),
    radii=RadiusTokens(
        sm=8,
        md=10,
        lg=12,
        xl=14,
    ),
    shadows=ShadowTokens(
        floating=ShadowToken(blur=18, offset_x=0, offset_y=6, color="rgba(15, 23, 42, 26)"),
        raised=ShadowToken(blur=12, offset_x=0, offset_y=4, color="rgba(15, 23, 42, 20)"),
    ),
    sizes=SizeTokens(
        window_min=(720, 480),
        grid_button=(140, 116),
        grid_icon=52,
        title_bar_height=36,
        dialog_min_width=480,
        tray_icon=64,
        tab_min_width=84,
        combo_drop_down=20,
    ),
    layout=LayoutTokens(
        content_margins=(16, 16, 16, 16),
        content_spacing=12,
        search_spacing=10,
        grid_layout_margin=8,
        grid_layout_spacing=12,
        list_spacing=10,
    ),
)


def build_stylesheet(tokens: DesignTokens = TOKENS) -> str:
    colors = tokens.colors
    spacing = tokens.spacing
    radii = tokens.radii
    typography = tokens.typography

    return f"""
    * {{
        font-family: {typography.font_family};
        font-size: {typography.font_size_md}px;
        color: {colors.text_primary};
    }}

    QMainWindow#mainWindow {{
        background-color: {colors.background};
        border: 1px solid {colors.border};
        border-radius: {radii.xl}px;
    }}

    QWidget#centralContainer {{
        background-color: {colors.surface};
        border-radius: {radii.xl}px;
    }}

    QTabWidget#mainTabs::pane {{
        border: none;
        margin-top: {spacing.xs}px;
    }}

    QTabBar::tab {{
        background: {colors.surface_alt};
        color: {colors.text_secondary};
        border: 1px solid {colors.border};
        border-radius: {radii.md}px;
        padding: {spacing.xs}px {spacing.md}px;
        margin-right: {spacing.sm}px;
        min-width: {tokens.sizes.tab_min_width}px;
        font-weight: {typography.weight_semibold};
    }}

    QTabBar::tab:selected {{
        background: {colors.accent_soft};
        color: {colors.text_primary};
        border-color: {colors.accent};
    }}

    QTabBar::tab:hover {{
        background: {colors.surface_hover};
    }}

    QWidget#titleBar {{
        background-color: {colors.surface};
        border-bottom: 1px solid {colors.border_soft};
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
        border: 1px solid {colors.border};
        border-radius: {radii.md}px;
        padding: {spacing.sm}px {spacing.md}px;
        font-weight: {typography.weight_semibold};
    }}

    QPushButton:hover {{
        background-color: {colors.surface_hover};
        border-color: {colors.border};
    }}

    QPushButton:pressed {{
        background-color: {colors.surface_alt};
    }}

    QPushButton[variant="accent"] {{
        background-color: {colors.accent};
        color: {colors.surface};
        border: 1px solid {colors.accent};
        font-weight: {typography.weight_bold};
    }}

    QPushButton[variant="accent"]:hover {{
        background-color: {colors.accent_hover};
    }}

    QPushButton[variant="control"] {{
        background-color: {colors.surface_alt};
        border-color: {colors.border_soft};
        font-weight: {typography.weight_semibold};
    }}

    QPushButton[variant="control"]:checked {{
        background-color: {colors.accent_soft};
        border-color: {colors.accent};
        color: {colors.text_primary};
    }}

    QPushButton[variant="secondary"] {{
        background-color: {colors.surface_alt};
        border-color: {colors.border};
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
    }}

    QPushButton[role="appTile"] {{
        background-color: {colors.surface};
        border-radius: {radii.lg}px;
        padding: {spacing.md}px;
        font-size: {typography.font_size_sm}px;
        font-weight: {typography.weight_bold};
        text-align: center;
        color: {colors.text_primary};
    }}

    QPushButton[role="appTile"]:hover {{
        background-color: {colors.surface_hover};
    }}

    QWidget[role="listItem"] {{
        background: {colors.surface};
        border: 1px solid {colors.border_soft};
        border-radius: {radii.lg}px;
    }}

    QWidget[role="listItem"]:hover {{
        background: {colors.surface_hover};
        border-color: {colors.border};
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
        border-radius: {radii.md}px;
        padding: {spacing.sm}px {spacing.md}px;
        font-size: {typography.font_size_md}px;
    }}

    QLineEdit:focus {{
        border: 2px solid {colors.accent};
        padding: {spacing.xs}px {spacing.md - 1}px;
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
        width: {tokens.sizes.combo_drop_down}px;
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
    """


def apply_design_system(app: QApplication, tokens: DesignTokens = TOKENS) -> None:
    app.setStyleSheet(build_stylesheet(tokens))


def apply_shadow(widget: QWidget, shadow: ShadowToken) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(shadow.blur)
    effect.setXOffset(shadow.offset_x)
    effect.setYOffset(shadow.offset_y)
    effect.setColor(QColor(shadow.color))
    widget.setGraphicsEffect(effect)
