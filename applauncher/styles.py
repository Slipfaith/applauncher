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

# General container styles inspired by the dark, moody reference UI
WINDOW_STYLE = (
    "QMainWindow {"
    " background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
    " stop:0 #0f1526, stop:0.5 #131c30, stop:1 #0f1626);"
    " border: 1px solid #1f2942;"
    " border-radius: 16px;"
    " }"
)
CONTAINER_STYLE = (
    "QWidget {"
    " background-color: #11192b;"
    " border-radius: 16px;"
    " }"
)
GRID_WIDGET_STYLE = "QWidget { background-color: transparent; }"
TABS_STYLE = """
QTabWidget::pane {
    border: none;
    margin-top: 6px;
}
QTabBar::tab {
    background: #1a2337;
    color: #e8edf7;
    border: 1px solid #222f47;
    border-radius: 12px;
    padding: 9px 16px;
    margin-right: 8px;
    min-width: 90px;
    font-weight: 600;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    letter-spacing: 0.1px;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #26344f, stop:1 #30476f);
    color: #f8fafc;
    border-color: #3b4f74;
}
QTabBar::tab:hover {
    background: #212d44;
}
"""

# Title bar
TITLE_BAR_STYLE = """
QWidget {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #121a2b, stop:1 #162239);
    border-bottom: 1px solid #1e2840;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
}
"""

TITLE_LABEL_STYLE = """
QLabel {
    color: #e8edf7;
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
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 6px 10px;
    font-size: 16px;
    color: #cfd7e6;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #1f2a40;
    border-color: #2b3a57;
    color: #ffffff;
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
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1c273b, stop:1 #1f2f49);
    color: #e8edf7;
    border: 1px solid #2a3854;
    border-radius: 16px;
    padding: 16px;
    font-size: 13px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    text-align: center;
    letter-spacing: 0.15px;
}
QPushButton:hover {
    background-color: #24324d;
    border: 1px solid #36486b;
}
QPushButton:pressed {
    background-color: #1d2841;
}
"""

ADD_BUTTON_STYLE = """
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f97316, stop:1 #fb923c);
    color: #0c0f16;
    border: none;
    border-radius: 14px;
    padding: 14px 24px;
    font-size: 14px;
    font-weight: 800;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    letter-spacing: 0.15px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fb923c, stop:1 #fbbf24);
}
QPushButton:pressed {
    background: #f97316;
}
"""

PRIMARY_BUTTON_STYLE = """
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f7cff, stop:1 #3b6adc);
    color: #0b1020;
    border: none;
    border-radius: 12px;
    padding: 10px 20px;
    font-weight: 800;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6a8cff, stop:1 #4f7cff);
}
"""

SECONDARY_BUTTON_STYLE = """
QPushButton {
    background-color: #1d273a;
    color: #e2e8f0;
    border: 1px solid #2f3c57;
    border-radius: 12px;
    padding: 10px 18px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #26344f;
}
"""

CANCEL_BUTTON_STYLE = """
QPushButton {
    background-color: #1a2337;
    color: #cfd7e6;
    border: 1px solid #26334d;
    border-radius: 12px;
    padding: 10px 20px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #212d44;
}
"""

SAVE_BUTTON_STYLE = """
QPushButton {
    background-color: #0ea774;
    color: #0c121f;
    border: none;
    border-radius: 12px;
    padding: 10px 20px;
    font-weight: 800;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background-color: #11c489;
}
"""

# Inputs
COMBO_BOX_STYLE = """
QComboBox {
    background-color: #141d2f;
    color: #e2e8f0;
    border: 1px solid #2d3a56;
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 14px;
}
QComboBox:focus {
    border: 2px solid #4f7cff;
    padding: 7px 11px; /* compensate for border */
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
"""

LINE_EDIT_STYLE = """
QLineEdit {
    background-color: #141d2f;
    color: #e2e8f0;
    border: 1px solid #2d3a56;
    border-radius: 12px;
    padding: 9px 12px;
    font-size: 14px;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QLineEdit:focus {
    border: 2px solid #4f7cff;
    padding: 8px 11px; /* compensate for border */
}
"""

# Dialogs and menus
DIALOG_STYLE = """
QDialog {
    background-color: #0f1626;
    color: #e2e8f0;
}
QLabel {
    font-size: 14px;
    font-weight: 700;
    color: #e8edf7;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
"""

MENU_STYLE = """
QMenu {
    background-color: #141d2f;
    border: 1px solid #22334f;
    border-radius: 12px;
    padding: 6px;
}
QMenu::item {
    padding: 8px 12px;
    border-radius: 8px;
    color: #e2e8f0;
}
QMenu::item:selected {
    background-color: #1f2a40;
    color: #f8fafc;
}
"""

CONTROL_BUTTON_STYLE = """
QPushButton {
    background-color: #1c2436;
    color: #e2e8f0;
    border: 1px solid #2b3a57;
    border-radius: 12px;
    padding: 10px 14px;
    font-weight: 700;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    letter-spacing: 0.1px;
}
QPushButton:hover {
    background-color: #222d45;
    border-color: #36486b;
}
QPushButton:checked {
    background-color: #2f3f61;
    border-color: #4f7cff;
    color: #ffffff;
}
"""
