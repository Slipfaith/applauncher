"""Centralized QSS style definitions for the launcher UI."""

# Layout metrics
WINDOW_MIN_SIZE = (760, 520)
CONTENT_MARGINS = (18, 18, 18, 18)
CONTENT_SPACING = 10
SEARCH_SPACING = 10
GRID_BUTTON_SIZE = (150, 130)
GRID_LAYOUT_MARGIN = 8
GRID_LAYOUT_SPACING = 16
LIST_SPACING = 12

# General container styles
WINDOW_STYLE = (
    "QMainWindow { background-color: #f7f8fb; border: 1px solid #e5e7ef; border-radius: 14px; }"
)
CONTAINER_STYLE = "QWidget { background-color: #f7f8fb; border-radius: 14px; }"
GRID_WIDGET_STYLE = "QWidget { background-color: transparent; }"
TABS_STYLE = """
QTabWidget::pane {
    border: none;
    margin-top: 6px;
}
QTabBar::tab {
    background: #ffffff;
    color: #1f2933;
    border: 1px solid #e5e7ef;
    border-radius: 12px;
    padding: 9px 16px;
    margin-right: 8px;
    min-width: 90px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    letter-spacing: 0.1px;
}
QTabBar::tab:selected {
    background: #e9edff;
    color: #1d4ed8;
    border-color: #cdd6ff;
}
QTabBar::tab:hover {
    background: #f6f7fb;
}
"""

# Title bar
TITLE_BAR_STYLE = """
QWidget {
    background-color: #ffffff;
    border-bottom: 1px solid #e5e7ef;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}
"""

TITLE_LABEL_STYLE = """
QLabel {
    color: #0f172a;
    font-size: 15px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    padding-left: 6px;
    letter-spacing: 0.15px;
}
"""

TITLE_BAR_BUTTON_STYLE = """
QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 16px;
    color: #4b5563;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #eef1f8;
    color: #0f172a;
}
"""

TITLE_BAR_CLOSE_STYLE = TITLE_BAR_BUTTON_STYLE + """
QPushButton:hover {
    background-color: #ef4444;
    color: white;
}
"""

# Buttons
APP_BUTTON_STYLE = """
QPushButton {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #e5e7ef;
    border-radius: 14px;
    padding: 16px;
    font-size: 13px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    text-align: center;
    letter-spacing: 0.1px;
}
QPushButton:hover {
    background-color: #f9fafe;
    border: 1px solid #cfd4e3;
}
QPushButton:pressed {
    background-color: #eef1f8;
}
"""

ADD_BUTTON_STYLE = """
QPushButton {
    background: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 12px;
    padding: 14px 24px;
    font-size: 14px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    letter-spacing: 0.15px;
}
QPushButton:hover {
    background: #1d4ed8;
}
QPushButton:pressed {
    background: #1e3a8a;
}
"""

PRIMARY_BUTTON_STYLE = """
QPushButton {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #1d4ed8;
}
"""

SECONDARY_BUTTON_STYLE = """
QPushButton {
    background-color: #f1f3f7;
    color: #111827;
    border: 1px solid #d8dce6;
    border-radius: 10px;
    padding: 10px 18px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #e6e9f2;
}
"""

CANCEL_BUTTON_STYLE = """
QPushButton {
    background-color: #f5f6f9;
    color: #1f2937;
    border: 1px solid #e0e4ed;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #eef1f8;
}
"""

SAVE_BUTTON_STYLE = """
QPushButton {
    background-color: #10b981;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #0f9a74;
}
"""

# Inputs
COMBO_BOX_STYLE = """
QComboBox {
    background-color: white;
    color: #1f2937;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
}
QComboBox:focus {
    border: 2px solid #3b82f6;
    padding: 7px 11px; /* compensate for border */
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
"""

LINE_EDIT_STYLE = """
QLineEdit {
    background-color: #ffffff;
    color: #111827;
    border: 1px solid #d8dce6;
    border-radius: 10px;
    padding: 9px 12px;
    font-size: 14px;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QLineEdit:focus {
    border: 2px solid #2563eb;
    padding: 8px 11px; /* compensate for border */
}
"""

# Dialogs and menus
DIALOG_STYLE = """
QDialog {
    background-color: #ffffff;
    color: #111827;
}
QLabel {
    font-size: 14px;
    font-weight: 600;
    color: #1f2937;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
"""

MENU_STYLE = """
QMenu {
    background-color: white;
    border: 1px solid #e5e7ef;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 8px 12px;
    border-radius: 8px;
    color: #111827;
}
QMenu::item:selected {
    background-color: #eef1f8;
    color: #0f172a;
}
"""

CONTROL_BUTTON_STYLE = """
QPushButton {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #e5e7ef;
    border-radius: 10px;
    padding: 10px 14px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    letter-spacing: 0.1px;
}
QPushButton:hover {
    background-color: #f3f5fb;
    border-color: #cfd4e3;
}
QPushButton:checked {
    background-color: #e9edff;
    border-color: #cdd6ff;
    color: #1d4ed8;
}
"""
