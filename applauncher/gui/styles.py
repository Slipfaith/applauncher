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
        background="#f5f5f4",
        surface="#ffffff",
        surface_alt="#f3f4f6",
        surface_hover="#eceff1",
        border="#d1d5db",
        border_soft="#e5e7eb",
        text_primary="#1f2933",
        text_secondary="#4b5563",
        text_muted="#6b7280",
        accent="#6b7280",
        accent_soft="#e5e7eb",
        accent_hover="#4b5563",
        danger="#b91c1c",
    ),
    typography=TypographyTokens(
        font_family="'Inter', 'Segoe UI', sans-serif",
        font_size_sm=11,
        font_size_md=12,
        font_size_lg=14,
        weight_regular=400,
        weight_semibold=600,
        weight_bold=700,
        letter_spacing_sm=0.2,
    ),
    spacing=SpacingTokens(
        none=0,
        xs=3,
        sm=6,
        md=10,
        lg=12,
        xl=16,
        xxl=20,
    ),
    radii=RadiusTokens(
        sm=6,
        md=8,
        lg=10,
        xl=12,
    ),
    shadows=ShadowTokens(
        floating=ShadowToken(blur=12, offset_x=0, offset_y=4, color="rgba(15, 23, 42, 18)"),
        raised=ShadowToken(blur=8, offset_x=0, offset_y=3, color="rgba(15, 23, 42, 14)"),
    ),
    sizes=SizeTokens(
        window_min=(600, 400),
        grid_button=(120, 96),
        grid_icon=44,
        title_bar_height=30,
        dialog_min_width=420,
        tray_icon=56,
        tab_min_width=72,
        combo_drop_down=18,
    ),
    layout=LayoutTokens(
        content_margins=(12, 12, 12, 12),
        content_spacing=8,
        search_spacing=6,
        grid_layout_margin=6,
        grid_layout_spacing=8,
        list_spacing=6,
    ),
)


def _rgba(color: QColor, alpha: float | None = None) -> str:
    target = QColor(color)
    if alpha is not None:
        target.setAlphaF(alpha)
    return f"rgba({target.red()}, {target.green()}, {target.blue()}, {target.alphaF():.2f})"


def build_theme_tokens(mode: str, accent: QColor, opacity: float = 0.78) -> DesignTokens:
    mode_key = mode.lower()
    base = TOKENS
    accent_color = QColor(accent)
    accent_color.setAlphaF(1.0)
    accent_hover = accent_color.darker(115)
    accent_soft_alpha = 0.18 if mode_key == "light" else 0.28
    accent_soft = QColor(accent_color)
    accent_soft.setAlphaF(accent_soft_alpha)

    if mode_key == "dark":
        colors = ColorTokens(
            background=_rgba(QColor("#111827"), opacity),
            surface=_rgba(QColor("#1f2937"), opacity),
            surface_alt=_rgba(QColor("#374151"), opacity),
            surface_hover=_rgba(QColor("#475569"), min(opacity + 0.08, 0.9)),
            border=_rgba(QColor("#94a3b8"), 0.35),
            border_soft=_rgba(QColor("#94a3b8"), 0.2),
            text_primary="#f9fafb",
            text_secondary="#e5e7eb",
            text_muted="#cbd5e1",
            accent=accent_color.name(),
            accent_soft=_rgba(accent_soft),
            accent_hover=accent_hover.name(),
            danger="#f87171",
        )
    else:
        colors = ColorTokens(
            background=_rgba(QColor("#f5f5f4"), opacity),
            surface=_rgba(QColor("#ffffff"), opacity),
            surface_alt=_rgba(QColor("#f3f4f6"), opacity),
            surface_hover=_rgba(QColor("#e2e8f0"), min(opacity + 0.08, 0.9)),
            border=_rgba(QColor("#d1d5db"), 0.6),
            border_soft=_rgba(QColor("#e5e7eb"), 0.5),
            text_primary="#1f2933",
            text_secondary="#4b5563",
            text_muted="#6b7280",
            accent=accent_color.name(),
            accent_soft=_rgba(accent_soft),
            accent_hover=accent_hover.name(),
            danger="#b91c1c",
        )

    return DesignTokens(
        colors=colors,
        typography=base.typography,
        spacing=base.spacing,
        radii=base.radii,
        shadows=base.shadows,
        sizes=base.sizes,
        layout=base.layout,
    )


def interpolate_color_tokens(start: ColorTokens, end: ColorTokens, progress: float) -> ColorTokens:
    def lerp_color(a: str, b: str) -> str:
        start_color = QColor(a)
        end_color = QColor(b)
        red = start_color.red() + (end_color.red() - start_color.red()) * progress
        green = start_color.green() + (end_color.green() - start_color.green()) * progress
        blue = start_color.blue() + (end_color.blue() - start_color.blue()) * progress
        alpha = start_color.alphaF() + (end_color.alphaF() - start_color.alphaF()) * progress
        blended = QColor(int(red), int(green), int(blue))
        blended.setAlphaF(alpha)
        return _rgba(blended)

    return ColorTokens(
        background=lerp_color(start.background, end.background),
        surface=lerp_color(start.surface, end.surface),
        surface_alt=lerp_color(start.surface_alt, end.surface_alt),
        surface_hover=lerp_color(start.surface_hover, end.surface_hover),
        border=lerp_color(start.border, end.border),
        border_soft=lerp_color(start.border_soft, end.border_soft),
        text_primary=lerp_color(start.text_primary, end.text_primary),
        text_secondary=lerp_color(start.text_secondary, end.text_secondary),
        text_muted=lerp_color(start.text_muted, end.text_muted),
        accent=lerp_color(start.accent, end.accent),
        accent_soft=lerp_color(start.accent_soft, end.accent_soft),
        accent_hover=lerp_color(start.accent_hover, end.accent_hover),
        danger=lerp_color(start.danger, end.danger),
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
        border: none;
        border-radius: {radii.xl}px;
    }}

    QWidget#centralContainer {{
        background-color: {colors.surface};
        border: none;
        border-radius: {radii.xl}px;
    }}

    QTabWidget#mainTabs::pane {{
        border: none;
        margin-top: 0;
    }}

    QTabBar {{
        background-color: transparent;
        border-radius: {radii.lg}px;
        padding: 0;
    }}

    QTabBar::tab {{
        background: {colors.surface};
        color: {colors.text_secondary};
        border: 1px solid {colors.border_soft};
        border-radius: {radii.lg}px;
        padding: {spacing.xs}px {spacing.lg}px;
        margin-right: {spacing.xs}px;
        min-width: {tokens.sizes.tab_min_width}px;
        max-width: {tokens.sizes.tab_min_width}px;
        font-weight: {typography.weight_semibold};
    }}

    QTabBar::tab:selected {{
        background: {colors.accent_soft};
        color: {colors.text_primary};
        border-color: {colors.accent};
    }}

    QTabBar::tab:hover {{
        background: {colors.surface_hover};
        border-color: {colors.border};
    }}

    QTabBar#groupTabs::tab:last {{
        background: {colors.accent};
        color: {colors.surface};
        border-color: {colors.accent};
        min-width: 32px;
        max-width: 32px;
        padding: {spacing.xs}px {spacing.sm}px;
    }}

    QTabBar#groupTabs::tab:last:hover {{
        background: {colors.accent_hover};
        border-color: {colors.accent_hover};
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

    QPushButton[role="viewToggle"] {{
        padding: {spacing.xs}px {spacing.sm}px;
        min-width: {tokens.sizes.combo_drop_down}px;
        font-size: {typography.font_size_md}px;
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

    QPushButton[role="appTile"][iconMode="full"] {{
        padding: 0px;
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
