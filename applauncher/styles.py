"""Centralized QSS style definitions for the launcher UI."""

# General container styles
WINDOW_STYLE = "QMainWindow { background-color: #f0f2f5; border: 1px solid #d1d5db; border-radius: 12px; }"
CONTAINER_STYLE = "QWidget { background-color: #f0f2f5; border-radius: 12px; }"
GRID_WIDGET_STYLE = "QWidget { background-color: transparent; }"
TABS_STYLE = """
QTabWidget::pane {
    border: none;
}
QTabBar::tab {
    background: #ffffff;
    color: #4b5563;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 10px 16px;
    margin-right: 8px;
    min-width: 90px;
    font-weight: 600;
    font-family: 'Segoe UI', sans-serif;
}
QTabBar::tab:selected {
    background: #e0f2fe;
    color: #0369a1;
    border-color: #7dd3fc;
}
QTabBar::tab:hover {
    background: #f9fafb;
}
"""

# Title bar
TITLE_BAR_STYLE = """
QWidget {
    background-color: #ffffff;
    border-bottom: 1px solid #e5e7eb;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}
"""

TITLE_LABEL_STYLE = """
QLabel {
    color: #111827;
    font-size: 15px;
    font-weight: 700;
    font-family: 'Segoe UI', sans-serif;
    padding-left: 8px;
}
"""

TITLE_BAR_BUTTON_STYLE = """
QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 16px;
    color: #4b5563;
}
QPushButton:hover {
    background-color: #f3f4f6;
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
    background-color: #ffffff;
    color: #374151;
    border: 1px solid #f3f4f6;
    border-radius: 16px;
    padding: 15px;
    font-size: 13px;
    font-weight: 600;
    font-family: 'Segoe UI', sans-serif;
    text-align: center;
}
QPushButton:hover {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
}
QPushButton:pressed {
    background-color: #f9fafb;
}
"""

ADD_BUTTON_STYLE = """
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 600;
    font-family: 'Segoe UI', sans-serif;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
}
QPushButton:pressed {
    background: #1e40af;
}
"""

PRIMARY_BUTTON_STYLE = """
QPushButton {
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2563eb;
}
"""

SECONDARY_BUTTON_STYLE = """
QPushButton {
    background-color: #6b7280;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #4b5563;
}
"""

CANCEL_BUTTON_STYLE = """
QPushButton {
    background-color: #e5e7eb;
    color: #374151;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #d1d5db;
}
"""

SAVE_BUTTON_STYLE = """
QPushButton {
    background-color: #10b981;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #059669;
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
    background-color: white;
    color: #1f2937;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
}
QLineEdit:focus {
    border: 2px solid #3b82f6;
    padding: 7px 11px; /* compensate for border */
}
"""

# Dialogs and menus
DIALOG_STYLE = """
QDialog {
    background-color: #ffffff;
    color: #1f2937;
}
QLabel {
    font-size: 14px;
    font-weight: 500;
    color: #374151;
}
"""

MENU_STYLE = """
QMenu {
    background-color: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 12px;
    border-radius: 6px;
    color: #374151;
}
QMenu::item:selected {
    background-color: #f3f4f6;
    color: #111827;
}
"""
