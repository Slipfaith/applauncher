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
        floating=ShadowToken(blur=18, offset_x=0, offset_y=8, color="rgba(0, 0, 0, 80)"),
        raised=ShadowToken(blur=12, offset_x=0, offset_y=4, color="rgba(0, 0, 0, 60)"),
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


def _clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _to_rgba(color: QColor, alpha_override: int | None = None) -> str:
    alpha = color.alpha() if alpha_override is None else alpha_override
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"


def _blend_colors(start: QColor, end: QColor, progress: float) -> QColor:
    return QColor(
        _clamp_channel(start.red() + (end.red() - start.red()) * progress),
        _clamp_channel(start.green() + (end.green() - start.green()) * progress),
        _clamp_channel(start.blue() + (end.blue() - start.blue()) * progress),
        _clamp_channel(start.alpha() + (end.alpha() - start.alpha()) * progress),
    )


def _shift_color(color: QColor, shift: int) -> QColor:
    return QColor(
        _clamp_channel(color.red() + shift),
        _clamp_channel(color.green() + shift),
        _clamp_channel(color.blue() + shift),
        color.alpha(),
    )


def build_theme_tokens(
    *,
    is_light: bool,
    accent: QColor,
    opacity: float = 0.78,
    tokens: DesignTokens = TOKENS,
) -> DesignTokens:
    alpha = _clamp_channel(255 * opacity)
    if is_light:
        background = QColor(248, 248, 249, alpha)
        surface = QColor(255, 255, 255, alpha)
        surface_alt = QColor(243, 244, 246, alpha)
        surface_hover = QColor(236, 239, 241, alpha)
        border = QColor(210, 214, 220, 180)
        border_soft = QColor(229, 231, 235, 140)
        text_primary = QColor(29, 30, 34)
        text_secondary = QColor(59, 63, 71)
        text_muted = QColor(107, 114, 128)
    else:
        background = QColor(22, 23, 26, alpha)
        surface = QColor(30, 31, 35, alpha)
        surface_alt = QColor(38, 40, 45, alpha)
        surface_hover = QColor(45, 48, 54, alpha)
        border = QColor(68, 70, 76, 180)
        border_soft = QColor(58, 60, 66, 140)
        text_primary = QColor(244, 245, 247)
        text_secondary = QColor(200, 202, 207)
        text_muted = QColor(148, 153, 160)

    accent_color = QColor(accent)
    accent_hover = _shift_color(accent_color, -20 if is_light else 25)
    accent_soft = QColor(accent_color)
    accent_soft.setAlpha(_clamp_channel(255 * 0.24))

    colors = ColorTokens(
        background=_to_rgba(background),
        surface=_to_rgba(surface),
        surface_alt=_to_rgba(surface_alt),
        surface_hover=_to_rgba(surface_hover),
        border=_to_rgba(border),
        border_soft=_to_rgba(border_soft),
        text_primary=_to_rgba(text_primary),
        text_secondary=_to_rgba(text_secondary),
        text_muted=_to_rgba(text_muted),
        accent=_to_rgba(accent_color),
        accent_soft=_to_rgba(accent_soft),
        accent_hover=_to_rgba(accent_hover),
        danger=_to_rgba(QColor(220, 38, 38)),
    )
    return DesignTokens(
        colors=colors,
        typography=tokens.typography,
        spacing=tokens.spacing,
        radii=tokens.radii,
        shadows=tokens.shadows,
        sizes=tokens.sizes,
        layout=tokens.layout,
    )


def interpolate_tokens(start: DesignTokens, end: DesignTokens, progress: float) -> DesignTokens:
    def blend_channel(start_value: str, end_value: str) -> str:
        return _to_rgba(
            _blend_colors(QColor(start_value), QColor(end_value), progress)
        )

    colors = ColorTokens(
        background=blend_channel(start.colors.background, end.colors.background),
        surface=blend_channel(start.colors.surface, end.colors.surface),
        surface_alt=blend_channel(start.colors.surface_alt, end.colors.surface_alt),
        surface_hover=blend_channel(start.colors.surface_hover, end.colors.surface_hover),
        border=blend_channel(start.colors.border, end.colors.border),
        border_soft=blend_channel(start.colors.border_soft, end.colors.border_soft),
        text_primary=blend_channel(start.colors.text_primary, end.colors.text_primary),
        text_secondary=blend_channel(start.colors.text_secondary, end.colors.text_secondary),
        text_muted=blend_channel(start.colors.text_muted, end.colors.text_muted),
        accent=blend_channel(start.colors.accent, end.colors.accent),
        accent_soft=blend_channel(start.colors.accent_soft, end.colors.accent_soft),
        accent_hover=blend_channel(start.colors.accent_hover, end.colors.accent_hover),
        danger=blend_channel(start.colors.danger, end.colors.danger),
    )
    return DesignTokens(
        colors=colors,
        typography=start.typography,
        spacing=start.spacing,
        radii=start.radii,
        shadows=start.shadows,
        sizes=start.sizes,
        layout=start.layout,
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

    QWidget[role="listItem"][hovered="true"],
    QPushButton[role="appTile"][hovered="true"] {{
        background-color: {colors.surface_hover};
    }}

    QLineEdit#searchInput[pulse="true"] {{
        border: 2px solid {colors.accent};
        padding: {spacing.xs}px {spacing.md - 1}px;
        background-color: {colors.surface_alt};
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
