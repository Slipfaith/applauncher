"""Centralized QSS style definitions for the launcher UI."""

# General container styles
WINDOW_STYLE = "QMainWindow { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 10px; }"
CONTAINER_STYLE = "QWidget { background-color: #f8f9fa; border-radius: 10px; }"
GRID_WIDGET_STYLE = "QWidget { background-color: transparent; }"
TABS_STYLE = """
QTabWidget::pane {
    border: none;
}
QTabBar::tab {
    background: #ffffff;
    color: #2c3e50;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    padding: 8px 14px;
    margin-right: 6px;
    min-width: 80px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #e7f3ff;
    border-color: #4a90e2;
}
QTabBar::tab:hover {
    background: #f1f5ff;
}
"""

# Title bar
TITLE_BAR_STYLE = """
QWidget {
    background-color: white;
    border-bottom: 1px solid #e9ecef;
}
"""

TITLE_LABEL_STYLE = """
QLabel {
    color: #2c3e50;
    font-size: 14px;
    font-weight: 600;
}
"""

TITLE_BAR_BUTTON_STYLE = """
QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 16px;
}
QPushButton:hover {
    background-color: #f0f0f0;
}
"""

TITLE_BAR_CLOSE_STYLE = TITLE_BAR_BUTTON_STYLE + """
QPushButton:hover {
    background-color: #e81123;
    color: white;
}
"""

# Buttons
APP_BUTTON_STYLE = """
QPushButton {
    background-color: white;
    color: #2c3e50;
    border: none;
    border-radius: 12px;
    padding: 15px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #f8f9fa;
}
QPushButton:pressed {
    background-color: #e9ecef;
}
"""

ADD_BUTTON_STYLE = """
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4a90e2, stop:1 #357abd);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 14px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #357abd, stop:1 #2868a8);
}
QPushButton:pressed {
    background: #2868a8;
}
"""

PRIMARY_BUTTON_STYLE = """
QPushButton {
    background-color: #4a90e2;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #357abd;
}
"""

SECONDARY_BUTTON_STYLE = """
QPushButton {
    background-color: #6c757d;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #5a6268;
}
"""

CANCEL_BUTTON_STYLE = """
QPushButton {
    background-color: #e9ecef;
    color: #495057;
    border: none;
    border-radius: 8px;
    padding: 12px 25px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #dee2e6;
}
"""

SAVE_BUTTON_STYLE = """
QPushButton {
    background-color: #28a745;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px 25px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #218838;
}
"""

# Inputs
COMBO_BOX_STYLE = """
QComboBox {
    background-color: white;
    color: #2c3e50;
    border: 2px solid #e9ecef;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
}
QComboBox:focus {
    border: 2px solid #4a90e2;
}
QComboBox::drop-down {
    border: none;
}
"""

LINE_EDIT_STYLE = """
QLineEdit {
    background-color: white;
    color: #2c3e50;
    border: 2px solid #e9ecef;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
}
QLineEdit:focus {
    border: 2px solid #4a90e2;
}
"""

# Dialogs and menus
DIALOG_STYLE = """
QDialog {
    background-color: #f8f9fa;
    color: #2c3e50;
}
QLabel {
    font-size: 13px;
    font-weight: 500;
    color: #495057;
}
"""

MENU_STYLE = """
QMenu {
    background-color: white;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    padding: 8px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #e7f3ff;
}
"""
