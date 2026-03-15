# AppLauncher

**v2.1** | [English](#english) | [Русский](#русский)

---

## Русский

Локальный desktop-лаунчер на `PySide6` для Windows: запуск приложений, папок, ссылок и быстрый поиск.

### Возможности

- Плитки и список для элементов в группах.
- Разделы: `Приложения`, `Папки`, `Ссылки`, `Заметки`.
- Глобальный хоткей и поиск (`Ctrl+K` / `Meta+K`).
- **Локальные горячие клавиши** — назначить хоткей на любое приложение/папку/ссылку через ПКМ; работает только внутри лаунчера.
- **HUD-панель** — полоса с иконками приложений, которым назначены горячие клавиши; tooltip при наведении показывает имя и комбинацию.
- **Сброс скролла** — при открытии лаунчера список плиток всегда прокручивается в начало.
- Single-instance режим (второй запуск передаёт аргументы в уже открытое окно).
- Работа через системный трей.
- Drag-and-drop файлов на плитки папок, включая перетаскивание из Outlook и других приложений с Windows MIME.

### Требования

- Windows
- Python 3.11+

### Установка и запуск

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

### Тесты

```powershell
python -m pytest -q
```

### Сборка (PyInstaller)

```powershell
pyinstaller main.spec
```

```powershell
pyinstaller main_onedir.spec
```

- `main.spec` → onefile (один `exe`).
- `main_onedir.spec` → onedir (папка с `exe` и зависимостями).

### Структура

- `main.py` — точка входа.
- `applauncher/gui/` — интерфейс.
- `applauncher/services/` — бизнес-логика (запуск, перенос файлов, поиск, хоткей).
- `tests/` — автотесты.

---

## English

A local desktop launcher built with `PySide6` for Windows: launch apps, folders, links, and search quickly.

### Features

- Grid and list view for items organized in groups.
- Sections: `Apps`, `Folders`, `Links`, `Notes`.
- Global hotkey and search (`Ctrl+K` / `Meta+K`).
- **Local hotkeys** — assign a keyboard shortcut to any app/folder/link via right-click menu; active only while the launcher window is focused.
- **HUD panel** — a strip of app icons for items with assigned hotkeys, shown between the title bar and section tabs; hover tooltip displays the app name and key combination.
- **Scroll reset** — the tile list always scrolls back to the top when the launcher is opened.
- Single-instance mode (a second launch passes arguments to the already-running window).
- System tray support.
- Drag-and-drop files onto folder tiles, including drops from Outlook and other apps using Windows MIME.

### Requirements

- Windows
- Python 3.11+

### Setup & Run

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

### Tests

```powershell
python -m pytest -q
```

### Build (PyInstaller)

```powershell
pyinstaller main.spec
```

```powershell
pyinstaller main_onedir.spec
```

- `main.spec` → onefile single `exe`.
- `main_onedir.spec` → onedir folder with `exe` and dependencies.

### Structure

- `main.py` — entry point.
- `applauncher/gui/` — UI layer.
- `applauncher/services/` — business logic (launch, file transfer, search, hotkeys).
- `tests/` — automated tests.
