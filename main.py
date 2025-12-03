import sys
import json
import os
import webbrowser
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout,
                               QPushButton, QFileDialog, QDialog, QVBoxLayout,
                               QHBoxLayout, QLineEdit, QLabel, QMessageBox,
                               QGraphicsDropShadowEffect, QSystemTrayIcon, QMenu,
                               QComboBox)
from PySide6.QtCore import Qt, QSize, QMimeData
from PySide6.QtGui import QIcon, QPixmap, QDragEnterEvent, QDropEvent, QColor

# Для извлечения иконок в Windows
try:
    import win32gui
    import win32ui
    import win32con
    import win32api

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class AppButton(QPushButton):
    def __init__(self, name, path, icon_path, app_type, parent=None):
        super().__init__(parent)
        self.name = name
        self.path = path
        self.icon_path = icon_path
        self.app_type = app_type  # 'exe' или 'url'

        self.setText(name)
        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        elif app_type == 'url':
            # Иконка для веб-ссылок
            self.setText(f"🌐 {name}")
        self.setIconSize(QSize(56, 56))
        self.setMinimumSize(140, 120)
        self.setStyleSheet("""
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
        """)

        # Тень
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        self.clicked.connect(self.launch_item)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def launch_item(self):
        if self.app_type == 'url':
            webbrowser.open(self.path)
        else:
            if os.path.exists(self.path):
                os.startfile(self.path)
            else:
                QMessageBox.warning(self, "Ошибка", f"Файл не найден:\n{self.path}")

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
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
        """)
        edit_action = menu.addAction("✏️ Редактировать")
        delete_action = menu.addAction("🗑️ Удалить")

        action = menu.exec(self.mapToGlobal(pos))
        if action == edit_action:
            main_window = self.window()
            main_window.edit_app(self)
        elif action == delete_action:
            main_window = self.window()
            main_window.delete_app(self)


class AddAppDialog(QDialog):
    def __init__(self, parent=None, edit_mode=False, app_data=None):
        super().__init__(parent)
        self.setWindowTitle("Редактировать" if edit_mode else "Добавить элемент")
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog { 
                background-color: #f8f9fa; 
                color: #2c3e50;
            }
            QLabel {
                font-size: 13px;
                font-weight: 500;
                color: #495057;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        # Тип элемента
        type_label = QLabel("Тип элемента")
        layout.addWidget(type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["💻 Приложение", "🌐 Веб-сайт"])
        self.type_combo.setStyleSheet("""
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
        """)
        if app_data and app_data.get('type') == 'url':
            self.type_combo.setCurrentIndex(1)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        layout.addWidget(self.type_combo)

        # Название
        name_label = QLabel("Название")
        layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setStyleSheet("""
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
        """)
        if app_data:
            self.name_input.setText(app_data.get('name', ''))
        layout.addWidget(self.name_input)

        # Путь к EXE или URL
        self.path_label = QLabel("Путь к исполняемому файлу")
        layout.addWidget(self.path_label)
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setStyleSheet("""
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
        """)
        if app_data:
            self.path_input.setText(app_data.get('path', ''))
        path_layout.addWidget(self.path_input)

        self.browse_btn = QPushButton("📁 Обзор")
        self.browse_btn.setStyleSheet("""
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
        """)
        self.browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)

        # Путь к иконке
        icon_label = QLabel("Иконка (необязательно)")
        layout.addWidget(icon_label)
        icon_layout = QHBoxLayout()
        self.icon_input = QLineEdit()
        self.icon_input.setStyleSheet("""
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
        """)
        if app_data:
            self.icon_input.setText(app_data.get('icon_path', ''))
        icon_layout.addWidget(self.icon_input)

        icon_btn = QPushButton("🖼️ Обзор")
        icon_btn.setStyleSheet("""
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
        """)
        icon_btn.clicked.connect(self.browse_icon)
        icon_layout.addWidget(icon_btn)
        layout.addLayout(icon_layout)

        layout.addStretch()

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet("""
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
        """)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("💾 Сохранить")
        save_btn.setStyleSheet("""
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
        """)
        save_btn.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.on_type_changed()

    def on_type_changed(self):
        is_url = self.type_combo.currentIndex() == 1
        if is_url:
            self.path_label.setText("URL адрес")
            self.browse_btn.setVisible(False)
            self.path_input.setPlaceholderText("https://example.com")
        else:
            self.path_label.setText("Путь к исполняемому файлу")
            self.browse_btn.setVisible(True)
            self.path_input.setPlaceholderText("")

    def browse_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите EXE файл", "", "Executable Files (*.exe)")
        if file_path:
            self.path_input.setText(file_path)
            if not self.name_input.text():
                self.name_input.setText(Path(file_path).stem)

            # Автоматическое извлечение иконки из exe
            if not self.icon_input.text():
                icon_path = self.extract_icon(file_path)
                if icon_path:
                    self.icon_input.setText(icon_path)

    def extract_icon(self, exe_path):
        """Извлечение иконки из .exe файла"""
        try:
            # Создаем папку для иконок если её нет
            icons_dir = Path("launcher_icons")
            icons_dir.mkdir(exist_ok=True)

            # Путь для сохранения иконки
            icon_path = icons_dir / f"{Path(exe_path).stem}.png"

            if HAS_WIN32:
                # Используем win32 для извлечения иконки
                ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
                ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)

                large, small = win32gui.ExtractIconEx(exe_path, 0)
                if large:
                    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                    hbmp = win32ui.CreateBitmap()
                    hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
                    hdc = hdc.CreateCompatibleDC()

                    hdc.SelectObject(hbmp)
                    hdc.DrawIcon((0, 0), large[0])

                    bmpstr = hbmp.GetBitmapBits(True)
                    img = QPixmap.fromImage(
                        QImage(bmpstr, ico_x, ico_y, QImage.Format_ARGB32)
                    )
                    img.save(str(icon_path))

                    win32gui.DestroyIcon(large[0])
                    return str(icon_path)
            else:
                # Альтернативный метод без win32
                from PIL import Image
                import struct

                # Простое чтение иконки из exe
                with open(exe_path, 'rb') as f:
                    data = f.read()
                    # Поиск PNG заголовка в exe
                    png_header = b'\x89PNG\r\n\x1a\n'
                    idx = data.find(png_header)
                    if idx != -1:
                        # Нашли PNG, сохраняем
                        with open(icon_path, 'wb') as icon_file:
                            icon_file.write(data[idx:idx + 5000])  # Примерный размер
                        return str(icon_path)
        except Exception as e:
            print(f"Не удалось извлечь иконку: {e}")
        return None

    def browse_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите иконку", "", "Images (*.png *.jpg *.ico)")
        if file_path:
            self.icon_input.setText(file_path)

    def get_data(self):
        return {
            'name': self.name_input.text(),
            'path': self.path_input.text(),
            'icon_path': self.icon_input.text(),
            'type': 'url' if self.type_combo.currentIndex() == 1 else 'exe'
        }


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(45)
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border-bottom: 1px solid #e9ecef;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(15, 0, 10, 0)
        layout.setSpacing(0)

        # Иконка и название
        title_label = QLabel("🚀 Лаунчер приложений")
        title_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        layout.addWidget(title_label)
        layout.addStretch()

        # Кнопки управления окном
        btn_style = """
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

        min_btn = QPushButton("−")
        min_btn.setStyleSheet(btn_style)
        min_btn.clicked.connect(parent.showMinimized)
        layout.addWidget(min_btn)

        max_btn = QPushButton("□")
        max_btn.setStyleSheet(btn_style)
        max_btn.clicked.connect(self.toggle_maximize)
        layout.addWidget(max_btn)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(btn_style + """
            QPushButton:hover {
                background-color: #e81123;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.close_to_tray)
        layout.addWidget(close_btn)

        self.setLayout(layout)

        self.start = None

    def close_to_tray(self):
        self.parent.hide()
        self.parent.tray_icon.showMessage(
            "Лаунчер",
            "Приложение свернуто в трей",
            QSystemTrayIcon.Information,
            2000
        )

    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.start:
            delta = event.position().toPoint() - self.start
            self.parent.move(self.parent.pos() + delta)

    def mouseReleaseEvent(self, event):
        self.start = None

    def mouseDoubleClickEvent(self, event):
        self.toggle_maximize()


class AppLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMinimumSize(700, 500)
        self.setStyleSheet("QMainWindow { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 10px; }")
        self.setAcceptDrops(True)

        self.config_file = "launcher_config.json"
        self.apps = []

        # Создание иконки в трее
        self.create_tray_icon()

        # Главный контейнер
        container = QWidget()
        container.setStyleSheet("QWidget { background-color: #f8f9fa; border-radius: 10px; }")
        self.setCentralWidget(container)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        container.setLayout(main_layout)

        # Кастомная титульная строка
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Контент
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        content_widget.setLayout(content_layout)

        # Кнопка добавления
        add_btn = QPushButton("➕ Добавить элемент")
        add_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #4a90e2, stop:1 #357abd);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 14px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #357abd, stop:1 #2868a8);
            }
            QPushButton:pressed {
                background: #2868a8;
            }
        """)
        add_btn.clicked.connect(self.add_app)

        # Тень для кнопки
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(QColor(74, 144, 226, 80))
        add_btn.setGraphicsEffect(shadow)

        content_layout.addWidget(add_btn)

        # Сетка приложений
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("QWidget { background-color: transparent; }")
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(20)
        self.grid_widget.setLayout(self.grid_layout)
        content_layout.addWidget(self.grid_widget)
        content_layout.addStretch()

        main_layout.addWidget(content_widget)

        self.load_config()
        self.refresh_grid()

    def create_tray_icon(self):
        """Создание иконки в системном трее"""
        self.tray_icon = QSystemTrayIcon(self)

        # Создаем простую иконку
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(74, 144, 226))
        icon = QIcon(pixmap)
        self.tray_icon.setIcon(icon)

        # Меню трея
        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
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
        """)

        show_action = tray_menu.addAction("🚀 Показать")
        show_action.triggered.connect(self.show)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("❌ Выход")
        quit_action.triggered.connect(QApplication.quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        """Обработка клика по иконке в трее"""
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()

    def closeEvent(self, event):
        """Переопределение закрытия окна - сворачивание в трей"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Лаунчер",
            "Приложение свернуто в трей. Кликните на иконку для возврата.",
            QSystemTrayIcon.Information,
            2000
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.endswith('.exe'):
                name = Path(file_path).stem

                # Автоматическое извлечение иконки
                icon_path = self.extract_icon_from_exe(file_path)

                self.apps.append({
                    'name': name,
                    'path': file_path,
                    'icon_path': icon_path or '',
                    'type': 'exe'
                })
        self.save_config()
        self.refresh_grid()

    def extract_icon_from_exe(self, exe_path):
        """Извлечение иконки из .exe файла"""
        try:
            icons_dir = Path("launcher_icons")
            icons_dir.mkdir(exist_ok=True)

            icon_path = icons_dir / f"{Path(exe_path).stem}.png"

            if HAS_WIN32:
                ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
                ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)

                large, small = win32gui.ExtractIconEx(exe_path, 0)
                if large:
                    from PySide6.QtGui import QImage
                    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                    hbmp = win32ui.CreateBitmap()
                    hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
                    hdc = hdc.CreateCompatibleDC()

                    hdc.SelectObject(hbmp)
                    hdc.DrawIcon((0, 0), large[0])

                    bmpstr = hbmp.GetBitmapBits(True)
                    img = QPixmap.fromImage(
                        QImage(bmpstr, ico_x, ico_y, QImage.Format_ARGB32)
                    )
                    img.save(str(icon_path))

                    win32gui.DestroyIcon(large[0])
                    return str(icon_path)
        except Exception as e:
            print(f"Не удалось извлечь иконку: {e}")
        return None

    def add_app(self):
        dialog = AddAppDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data['name'] and data['path']:
                self.apps.append(data)
                self.save_config()
                self.refresh_grid()

    def edit_app(self, button):
        for i, app in enumerate(self.apps):
            if app['path'] == button.path:
                dialog = AddAppDialog(self, edit_mode=True, app_data=app)
                if dialog.exec():
                    self.apps[i] = dialog.get_data()
                    self.save_config()
                    self.refresh_grid()
                break

    def delete_app(self, button):
        self.apps = [app for app in self.apps if app['path'] != button.path]
        self.save_config()
        self.refresh_grid()

    def refresh_grid(self):
        # Очистка сетки
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Добавление кнопок
        cols = 4
        for i, app in enumerate(self.apps):
            btn = AppButton(
                app['name'],
                app['path'],
                app.get('icon_path', ''),
                app.get('type', 'exe'),
                self.grid_widget
            )
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(btn, row, col)

    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.apps, f, ensure_ascii=False, indent=2)

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.apps = json.load(f)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Предотвращение полного закрытия при закрытии последнего окна
    app.setQuitOnLastWindowClosed(False)

    window = AppLauncher()
    window.show()
    sys.exit(app.exec())