"""Centralized QSS style definitions for the launcher UI."""

# Layout metrics
WINDOW_MIN_SIZE = (640, 420)
CONTENT_MARGINS = (12, 12, 12, 12)
CONTENT_SPACING = 8
SEARCH_SPACING = 8
GRID_BUTTON_SIZE = (130, 110)
GRID_LAYOUT_MARGIN = 6
GRID_LAYOUT_SPACING = 12
LIST_SPACING = 8

# General container styles inspired by a clean, light overlay UI
WINDOW_STYLE = (
    "QMainWindow {"
    " background-color: rgba(255, 255, 255, 210);"
    " border: 1px solid rgba(180, 190, 200, 180);"
    " border-radius: 14px;"
    " }"
)
CONTAINER_STYLE = (
    "QWidget {"
    " background-color: rgba(255, 255, 255, 235);"
    " border-radius: 14px;"
    " }"
)
GRID_WIDGET_STYLE = "QWidget { background-color: transparent; }"
TABS_STYLE = """
QTabWidget::pane {
    border: none;
    margin-top: 4px;
}
QTabBar::tab {
    background: rgba(255, 255, 255, 210);
    color: #111827;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 8px 12px;
    margin-right: 6px;
    min-width: 78px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    letter-spacing: 0.05px;
}
QTabBar::tab:selected {
    background: #dbeafe;
    color: #0f172a;
    border-color: #93c5fd;
}
QTabBar::tab:hover {
    background: #e5e7eb;
}
"""

# Title bar
TITLE_BAR_STYLE = """
QWidget {
    background-color: rgba(255, 255, 255, 180);
    border-bottom: 1px solid rgba(200, 210, 220, 180);
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}
"""

TITLE_LABEL_STYLE = """
QLabel {
    color: #3b4a5a;
    font-size: 13px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    padding-left: 4px;
    letter-spacing: 0.1px;
}
"""

TITLE_BAR_BUTTON_STYLE = """
QPushButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 4px 8px;
    font-size: 14px;
    color: #4b5563;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: rgba(100, 116, 139, 50);
    border-color: rgba(148, 163, 184, 120);
    color: #111827;
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
    background-color: rgba(255, 255, 255, 200);
    color: #1f2937;
    border: 1px solid #d1d5db;
    border-radius: 12px;
    padding: 12px;
    font-size: 12px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    text-align: center;
    letter-spacing: 0.1px;
}
QPushButton:hover {
    background-color: rgba(229, 231, 235, 220);
    border: 1px solid #cfd5df;
}
QPushButton:pressed {
    background-color: rgba(209, 213, 219, 200);
}
"""

ADD_BUTTON_STYLE = """
QPushButton {
    background: rgba(59, 130, 246, 230);
    color: #f8fafc;
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    letter-spacing: 0.1px;
}
QPushButton:hover {
    background: rgba(37, 99, 235, 230);
}
QPushButton:pressed {
    background: rgba(59, 130, 246, 210);
}
"""

PRIMARY_BUTTON_STYLE = """
QPushButton {
    background: rgba(16, 185, 129, 230);
    color: #0f172a;
    border: none;
    border-radius: 11px;
    padding: 9px 16px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background: rgba(16, 185, 129, 255);
}
"""

SECONDARY_BUTTON_STYLE = """
QPushButton {
    background-color: #eef2ff;
    color: #1e293b;
    border: 1px solid #c7d2fe;
    border-radius: 11px;
    padding: 9px 16px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #e0e7ff;
}
"""

CANCEL_BUTTON_STYLE = """
QPushButton {
    background-color: #f3f4f6;
    color: #4b5563;
    border: 1px solid #e5e7eb;
    border-radius: 11px;
    padding: 9px 16px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #e5e7eb;
}
"""

SAVE_BUTTON_STYLE = """
QPushButton {
    background-color: #22c55e;
    color: #0b1120;
    border: none;
    border-radius: 11px;
    padding: 9px 16px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #16a34a;
}
"""

# Inputs
COMBO_BOX_STYLE = """
QComboBox {
    background-color: rgba(255, 255, 255, 230);
    color: #111827;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 7px 12px;
    font-size: 13px;
}
QComboBox:focus {
    border: 2px solid #93c5fd;
    padding: 6px 11px; /* compensate for border */
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
"""

LINE_EDIT_STYLE = """
QLineEdit {
    background-color: rgba(255, 255, 255, 230);
    color: #0f172a;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 8px 11px;
    font-size: 13px;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QLineEdit:focus {
    border: 2px solid #93c5fd;
    padding: 7px 10px; /* compensate for border */
}
"""

# Dialogs and menus
DIALOG_STYLE = """
QDialog {
    background-color: rgba(255, 255, 255, 240);
    color: #0f172a;
}
QLabel {
    font-size: 13px;
    font-weight: 600;
    color: #1f2937;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
"""

MENU_STYLE = """
QMenu {
    background-color: rgba(255, 255, 255, 245);
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 10px;
    border-radius: 8px;
    color: #111827;
}
QMenu::item:selected {
    background-color: #e5e7eb;
    color: #111827;
}
"""

CONTROL_BUTTON_STYLE = """
QPushButton {
    background-color: rgba(255, 255, 255, 220);
    color: #0f172a;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 8px 12px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    letter-spacing: 0.1px;
}
QPushButton:hover {
    background-color: rgba(229, 231, 235, 240);
    border-color: #cfd5df;
}
QPushButton:checked {
    background-color: #dbeafe;
    border-color: #93c5fd;
    color: #0f172a;
}
"""
