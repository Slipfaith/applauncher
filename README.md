# AppLauncher

**v2.3** | [English](#english) | [Русский](#русский)

---

## Русский

Локальный desktop-лаунчер на `PySide6` для Windows: запуск приложений, папок, ссылок и быстрый поиск.

Готовая сборка: [applauncher.exe](gui/implementation_review/exe/applauncher.exe) · [SHA-256](gui/implementation_review/exe/SHA256SUMS) · [Журнал изменений](CHANGELOG.md).

### Возможности

- Плитки и список для элементов в группах.
- Контурные иконки LINE для папок, ссылок и программ без собственной картинки; они подстраиваются под тему и масштаб экрана.
- Разделы: `Приложения`, `Папки`, `Ссылки`, `Заметки`, `Буфер обмена`.
- В «Настройки → Тема оформления» доступны автоматическая, светлая и тёмная темы. Выбор сразу меняет все окна и сохраняется между запусками; автоматический режим следует теме Windows. Прозрачность окна также сохраняется. Шрифты Onest и JetBrains Mono включены в пакет.
- Кнопки «Меню» и «Настройки» находятся в заголовке окна. Кнопки заголовка, переключения вида и копирования доступны с клавиатуры.
- Заметки показывают весь текст; кнопка ▾ сворачивает заметку до заголовка. Двойной клик по свободному месту карточки или F2 открывает отдельный редактор. Клик вне редактора закрывает его с автосохранением.
- Двойной клик по тексту выделяет слово, а по адресу почты — весь адрес. Тройной клик копирует строку целиком, включая её переносы по ширине карточки.
- «Скрыть» в контекстном меню маскирует выделенный текст в карточке и редакторе. Клик по скрытому фрагменту временно раскрывает его для выделения и копирования; клик в сторону снова скрывает. «Раскрыть» снимает маскировку постоянно. Форматирование сохраняется. Длинные строки и адреса почты переносятся по ширине заметки.
- В редакторе заметок доступны жирный, курсив и подчёркивание: кнопки B/I/U или `Ctrl+B` / `Ctrl+I` / `Ctrl+U`. Форматирование сохраняется между запусками.
- Глобальный хоткей и поиск (`Ctrl+K` / `Meta+K`).
- **Горячие клавиши элементов** — назначить глобальный хоткей на любое приложение/папку/ссылку через ПКМ; работает, даже когда окно лаунчера скрыто или неактивно.
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
python -m pip install -r requirements-dev.txt
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest tests -q
```

### Сборка (PyInstaller)

```powershell
pyinstaller main.spec
```

- `main.spec` → onefile (один `exe`).
- Спецификация включает шрифты и их лицензии из `applauncher/gui/fonts/`.

### Установщик (Inno Setup)

Требуется [Inno Setup 6](https://jrsoftware.org/isinfo.php).

```powershell
pyinstaller main.spec
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\applauncher.iss
```

Готовый установщик появится в `installer\Output\`.

### Структура

- `main.py` — точка входа.
- `applauncher/gui/` — интерфейс.
- `applauncher/services/` — бизнес-логика (запуск, перенос файлов, поиск, хоткей).
- `tests/` — автотесты.

---

## English

A local desktop launcher built with `PySide6` for Windows: launch apps, folders, links, and search quickly.

Windows build: [applauncher.exe](gui/implementation_review/exe/applauncher.exe) · [SHA-256](gui/implementation_review/exe/SHA256SUMS) · [Changelog](CHANGELOG.md).

### Features

- Grid and list view for items organized in groups.
- Scalable LINE icons for folders, links and apps without their own picture, with colours that follow the selected theme.
- Sections: `Apps`, `Folders`, `Links`, `Notes`, `Clipboard`.
- Settings → Theme offers automatic, light and dark modes. Changes apply immediately to every window and persist between sessions; automatic mode follows Windows. Window opacity remains configurable. Onest and JetBrains Mono are bundled.
- Menu and Settings are in the title bar. Header, view and copy buttons support keyboard navigation.
- Notes show their full text; ▾ collapses a note to its header. Double-click an empty area of the card or press F2 to open its floating editor. Clicking outside closes it and saves changes automatically.
- Double-click text to select a word, or an email address to select the entire address. Triple-click to copy the whole line, including any portions wrapped across the card.
- The context-menu action «Скрыть» (Hide) masks selected text in both the card and editor. Click a hidden fragment to reveal it temporarily for selection and copying; clicking elsewhere hides it again. «Раскрыть» (Unhide) removes masking permanently. Formatting is preserved, and long lines and email addresses wrap to fit the note.
- The note editor supports bold, italic and underline with B/I/U buttons or `Ctrl+B` / `Ctrl+I` / `Ctrl+U`. Formatting persists between sessions.
- Global hotkey and search (`Ctrl+K` / `Meta+K`).
- **Item hotkeys** — assign a global keyboard shortcut to any app/folder/link via the right-click menu; it works even while the launcher window is hidden or inactive.
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
python -m pip install -r requirements-dev.txt
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest tests -q
```

### Build (PyInstaller)

```powershell
pyinstaller main.spec
```

- `main.spec` → onefile single `exe`.
- The spec includes fonts and their licences from `applauncher/gui/fonts/`.

### Installer (Inno Setup)

Requires [Inno Setup 6](https://jrsoftware.org/isinfo.php).

```powershell
pyinstaller main.spec
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\applauncher.iss
```

The compiled installer is written to `installer\Output\`.

### Structure

- `main.py` — entry point.
- `applauncher/gui/` — UI layer.
- `applauncher/services/` — business logic (launch, file transfer, search, hotkeys).
- `tests/` — automated tests.
