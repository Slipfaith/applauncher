# AppLauncher — Журнал изменений / Changelog

Новые записи добавляются сверху. Каждая запись описывает пользовательские изменения, проверки и связанную сборку.
Newest entries appear first. Each entry describes user-facing changes, verification, and the associated build.

## 2.3 — 2026-10-13

### Русский

- Исправлено скрытие текста в карточке заметки и отдельном редакторе. Команда «Замаскировать» переименована в «Скрыть»; выбранный фрагмент сохраняется при открытии контекстного меню, а действие применяется после его закрытия.
- Скрытый текст раскрывается по клику, доступен для выделения и копирования и снова скрывается при клике в сторону. «Раскрыть» снимает маскировку постоянно. Сохранение, отмена действий и исходное форматирование работают вместе с маскировкой.
- Исправлены обрезание адресов почты, перенос импортированного текста и границы маски на переносах строк. Адрес почты целиком выделяется двойным кликом; выделение перетаскиванием работает в обе стороны.
- Двойной клик по тексту выделяет его, а по свободному месту карточки открывает редактор. Тройной клик копирует строку целиком. Сворачивание оставляет только заголовок заметки.
- В контекстном меню редактора отображается обычная стрелка, в том числе после прокрутки; открытое меню больше не теряет выделение из-за смены фокуса.
- Контурные иконки заменили emoji в меню и диалогах. Исправлены загрузка иконки упакованного приложения и параметры значков ярлыков установщика.
- Удалены ненужные локальные промоматериалы и промежуточные сборки. Версия приложения и установщика обновлена до 2.3; инструкции в README актуализированы на двух языках.
- Проверки: **201 автотест**; готовый EXE проверен через `--verify-design` на обеих темах со встроенными шрифтами и иконками.
- Сборка: [applauncher.exe](gui/implementation_review/exe/applauncher.exe) · [SHA-256](gui/implementation_review/exe/SHA256SUMS).

### English

- Fixed text hiding in both note cards and the floating editor. Renamed «Замаскировать» to «Скрыть» (Hide); the selected range is retained while the context menu is open, and the action is applied after the menu closes.
- Hidden text can be revealed with a click, selected and copied, and is hidden again when clicking elsewhere. «Раскрыть» (Unhide) removes masking permanently. Saving, undo, and original formatting work with masked text.
- Fixed clipped email addresses, wrapping of imported text, and mask boundaries on wrapped lines. Double-click selects a complete email address; drag selection works in both directions.
- Double-clicking text selects it; double-clicking an empty card area opens the editor. Triple-click copies the whole line. Collapsing a note leaves only its header.
- The editor context menu now uses the arrow cursor, including after scrolling, and focus changes no longer discard the selection while the menu is open.
- Replaced emoji in menus and dialogs with outline icons. Fixed the bundled application icon and installer shortcut icon settings.
- Removed unused local promotional material and intermediate builds. Updated the application and installer version to 2.3 and refreshed the README in both languages.
- Verification: **201 automated tests**; the packaged EXE checked with `--verify-design` in both themes with bundled fonts and icons.
- Build: [applauncher.exe](gui/implementation_review/exe/applauncher.exe) · [SHA-256](gui/implementation_review/exe/SHA256SUMS).


## 2026-10-10 — Исправления ревью и обновлённая Windows-сборка

### Исправлено

- Повреждённая конфигурация больше не заменяется пустой при автосохранении; явный сброс сохраняет повреждённый оригинал. Восстановление учитывает ошибки UTF-8, а неверные типы записей не обрывают загрузку.
- Плитки получили постоянные ID: одинаковые пути могут иметь разные аргументы и группы; действия изменяют только выбранную запись.
- Редактирование сохраняет аргументы запуска, избранное, рабочую папку ярлыка и кадрирование картинки. Windows-аргументы разбираются без лишних буквальных кавычек.
- Поздняя автоиконка не заменяет пользовательскую. История буфера сохраняет исходные пробелы и переводы строк; обновление истории во время меню безопасно.
- Второй запуск показывает существующее окно даже без аргументов. Файловое копирование выполняется в фоне и сохраняет временные источники до завершения.
- Выход дожидается задач, продолжая обработку Qt-событий, и записывает последние заметки и историю буфера один раз.
- Установщик ограничен x64-совместимыми системами, закрывает приложение без принудительного завершения и поддерживает выбор исходного EXE при компиляции.
- Release workflow проверяет свежий frozen EXE перед упаковкой установщика. Временные результаты тестов и сборки очищены; локальные инструменты BMAD исключены из Git.

### Проверка и сборка

- На объединённой ветке прошли **151 тест**; готовый EXE прошёл проверку обеих тем, шрифтов и иконок через Windows и offscreen без предупреждений.
- [Текущий EXE](gui/implementation_review/exe/applauncher.exe) и [SHA-256](gui/implementation_review/exe/SHA256SUMS) обновлены из сборки основной ветки. Размер: 46 844 223 байта.
- [Отчёт проверки основной ветки](gui/implementation_review/MASTER_RELEASE_2026-10-10.md).

## 2026-10-10 — Редизайн, переключение темы и иконки LINE

Изменения относительно `90bc36b` (AppLauncher 2.2).

### Добавлено

- Компактный интерфейс с вертикальными плитками, обновлённым списком, панелью горячих клавиш и действиями «Меню»/«Настройки» в заголовке.
- «Настройки → Тема оформления»: автоматически, светлая, тёмная. Выбор применяется к существующим окнам без перезапуска и сохраняется между запусками.
- Набор контурных иконок **01 LINE** для папок, ссылок и программ без доступной собственной картинки. Используется в плитках, списке, HUD и поиске; подстраивается под тему и DPI.
- Шрифты Onest и JetBrains Mono с OFL-лицензиями.
- Изолированный режим `--verify-design` для проверки шрифтов, тем и иконок без запуска пользовательского лаунчера.
- `requirements-dev.txt`, регрессионные тесты интерфейса и сохранённая Windows-сборка в репозитории.

### Исправлено

- Перенос и усечение длинных русских названий и emoji, доступные имена элементов и управление кнопками с клавиатуры.
- Состояние кнопки копирования, подсветка папки при drag-and-drop и границы тени плитки.
- Цвета раскрытых спойлеров и сохранение пользовательского форматирования заметок.
- Пустая плитка при отсутствующей/повреждённой собственной картинке: теперь показываются LINE-иконка и название.
- Повторные расчёты подписей при смене темы; сохранение текста, выделения, истории отмены и прокрутки открытого редактора.
- Упаковка шрифтов и выбор Windows DLL при сборке PyInstaller; подготовка зависимостей и offscreen-тестирование в release workflow.

### Проверено

- **125 тестов прошли**; [результат](gui/implementation_review/line01_tests.txt).
- Сборка EXE проверена в Windows и offscreen, на обеих темах, со встроенными шрифтами и тремя типами LINE-иконок.
- Полное окно с 200 тестовыми элементами проверено при Windows 100% и масштабе Qt 125%. Системный масштаб Windows 125% вручную не переключался.
- Собственные картинки и параметры кадрирования сохранены. Все 24 предоставленных файла дизайна сохранили исходные хеши.

### Сборка и материалы

- [applauncher.exe](gui/implementation_review/exe/applauncher.exe) — 46 837 705 байт.
- SHA-256: `dd0fd36144301d3387fac8066c8e503cd92c009f9dad0efdeefea5f28798570e` ([файл проверки](gui/implementation_review/exe/SHA256SUMS)).
- [Отчёт о редизайне](gui/implementation_review/REPORT_SOL_6_1.md), [переключатель темы](gui/implementation_review/THEME_SWITCH_REPORT.md), [LINE](gui/implementation_review/LINE01_REPORT.md).
- [Фактический вид LINE](gui/implementation_review/icon_concepts/line01_implemented.png), [итоговая проверка](gui/implementation_review/final_integrity.json).

## Предыдущий этап — AppLauncher 2.2

Коммит `90bc36b`: отдельный редактор заметок с богатым форматированием и сохранением содержимого.
