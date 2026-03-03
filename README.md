# AppLauncher

Локальный desktop-лаунчер на `PySide6` для Windows: запуск приложений, папок, ссылок и быстрый поиск.

## Возможности

- Плитки и список для элементов в группах.
- Разделы: `Приложения`, `Папки`, `Ссылки`, `Заметки`.
- Глобальный хоткей и поиск (`Ctrl+K` / `Meta+K`).
- Single-instance режим (второй запуск передает аргументы в уже открытое окно).
- Работа через системный трей.
- Drag-and-drop файлов на плитки папок, включая перетаскивание из Outlook и других приложений с Windows MIME.

## Требования

- Windows
- Python 3.11+

## Установка и запуск

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

## Тесты

```powershell
python -m pytest -q
```

## Сборка (PyInstaller)

```powershell
pyinstaller main.spec
```

```powershell
pyinstaller main_onedir.spec
```

- `main.spec` -> onefile (один `exe`).
- `main_onedir.spec` -> onedir (папка с `exe` и зависимостями).

## Структура

- `main.py` - точка входа.
- `applauncher/gui/` - интерфейс.
- `applauncher/services/` - бизнес-логика (запуск, перенос файлов, поиск, хоткей).
- `tests/` - автотесты.
