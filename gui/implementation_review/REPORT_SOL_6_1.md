# Внедрение редизайна AppLauncher

Актуальные дополнения: ручной переключатель темы — [THEME_SWITCH_REPORT.md](THEME_SWITCH_REPORT.md); выбранный набор иконок 01 LINE и текущая сборка — [LINE01_REPORT.md](LINE01_REPORT.md). Этот отчёт фиксирует основной этап переноса, включая хеш сборки до дополнений.

Дата: 9 октября 2026 года. Базовый Git HEAD: `90bc36b7926d8c71bae67d7d8b87fe5fb7cb93ff`.

## Результат

Дизайн из `gui/` перенесён в единственный рабочий пакет `applauncher.gui`. Исправлены подключение ресурсов, компактность, управление темой, клавиатурный доступ, усечение подписей, копирование, подсветка drop target и сохранение форматирования спойлеров. Существующие сервисы и схема конфигурации сохранены.

Полный автоматический прогон: **96 passed**. Baseline до переноса: **52 passed**. Собран свежий onefile EXE через `main.spec`; обе темы и семейства Onest / JetBrains Mono проверяются изолированным режимом `--verify-design`. Статусы и ограничения Windows-проверок перечислены ниже. Ручная приёмка внешнего drag-and-drop и реального системного масштаба 125% остаётся открытой.

Материалы Claude и план сохранены: SHA-256 всех **24 исходных файлов** совпал с первоначальным снимком. Доказательства: `source_sha256.json`, `source_integrity.json`, `final_integrity.json`. Пользовательское приложение обычным `main.py` для smoke не запускалось; проверки полного окна используют временные fixtures, заглушки запуска/переноса файлов/буфера и отключённые глобальные сочетания плиток.

## Изменённые файлы

Все пути в этой таблице указаны относительно `E:\PythonProjects\applauncher`.

| Файл | Что сделано |
| --- | --- |
| `applauncher/gui/styles.py` | Светлая/тёмная/auto тема; компактные метрики; pt-типографика; регистрация шрифтов один раз; fallback и предупреждения; отдельное состояние выбранного режима; focus-правила; контраст с учётом прозрачности |
| `applauncher/gui/glyphs.py` — новый | Контурные значки, Enter/Space, доступные имена и отрисовка фокуса |
| `applauncher/gui/fonts/` — новая папка | Два исходных TTF и соответствующие OFL-лицензии |
| `applauncher/gui/app.py` | Меню/настройки в TitleBar, вкладки и переключатель вида, Tab-порядок, доступные имена, размер по умолчанию `1000×620` и ограничение доступной областью экрана |
| `applauncher/gui/widgets/__init__.py` | Вертикальные плитки, HUD, список; усечение кириллицы/emoji/длинных слов; сохранённое полное имя; копирование при фокусе и после таймера; reset drop target; клавиатура списка/HUD; состояние кнопок окна; тень внутри отступов сетки |
| `applauncher/gui/widgets/notes_widget.py` | Компактный редактор; спойлер наследует цвет темы; сохранение пользовательских цветов и B/I/U при раскрытии, записи и загрузке |
| `applauncher/gui/widgets/clipboard_history_widget.py` | Семантические роли заголовка и опасного действия |
| `applauncher/gui/widgets/universal_search_widget.py` | QSS-идентификатор `universalSearch`; модель работы сохранена |
| `applauncher/gui/dialogs/hotkey_capture_dialog.py` | Роли для комбинации и ошибки |
| `applauncher/gui/dialogs/__init__.py` | Короткая подпись кадрирования; полная инструкция в tooltip, чтобы диалог не разрастался по ширине |
| `applauncher/gui/design_verification.py` — новый | Изолированная проверка шрифтов/тем и снимки без конфигурации, IPC, буфера и хоткеев |
| `applauncher/logger.py` | Запись предупреждений о дизайн-ресурсах в `design_warnings.log`, с ленивым открытием и ротацией |
| `main.py` | Дополнительный режим `--verify-design`; обычный запуск по-прежнему использует `applauncher.gui.app.run_app` |
| `main.spec` | Шрифты/лицензии в `datas`; контролируемый DLL search PATH на время Analysis |
| `requirements-dev.txt` — новый | Runtime-зависимости плюс pytest для разработки |
| `.github/workflows/release.yml` | Установка dev-зависимостей до тестов; offscreen для CI |
| `README.md` | Описание тем, шрифтов, пяти разделов, положения действий и запуска тестов; исправлена ссылка на отсутствовавший `main_onedir.spec` |
| `tests/test_design_system.py` — новый | Палитра, rgba, auto/explicit режим, повторные подключения, отсутствующие/повреждённые TTF, контраст |
| `tests/test_redesign_widgets.py` — новый | Клавиатура, Tab, accessible names, copy без launch, длинные подписи и resize, drop target, crop, HUD, размеры диалогов, границы тени |
| `tests/test_design_verification.py` — новый | Изоляция проверочной точки входа и запись fallback-предупреждений |
| `tests/test_notes_widget.py` | Новые проверки двух тем, пользовательских/смешанных цветов и неизменности legacy HTML при раскрытии |
| `tests/ui_fixture.py` — новый | Воспроизводимое полное окно с временной конфигурацией и заглушками внешних действий |

В `gui/implementation_review/` добавлены этот отчёт, логи, снимки, JSON-результаты, EXE и воспроизводимые скрипты `smoke_redesign.py`, `native_smoke.py`, `benchmark_redesign.py`. Временные fixtures и промежуточные файлы упаковки исключены из Git локальным `.gitignore`. Коммиты, теги, публикация и установка поверх пользовательского приложения не выполнялись.

## Адаптации дизайна Claude

- Layout-поля ограничены 12 px, интервалы — 8 px. Радиусы и пользовательское изображение `120×96` сохранены. Минимальное окно осталось `680×440`.
- Основная типографика задаётся в pt; дополнительный ручной DPI-множитель не применяется. При смене шрифта подписи плитки пересчитываются с фактическими метриками Qt.
- Палитры усилены для прозрачности 75% на светлом и тёмном фоне. `accent_text` отделён от цвета заливки акцентной кнопки. Проверяются текст/цветные подписи, hover-поверхности, границы и значок успешного копирования.
- Hover-тень плитки уменьшена до размера, полностью помещающегося в 12 px поля сетки. Автотест проверяет первую и последнюю плитки в минимальном окне.
- Усечение списка рассчитывается при отрисовке и кэшируется по ширине/шрифту; промежуточные font/style события при построении строки больше не вызывают повторную работу.
- Для новых спойлеров оригинальные цвета могут храниться в необязательном HTML `<meta name="applauncher-spoiler-styles">`. Поле `content_html` и схема JSON не изменены; миграция не нужна. Старые записи читаются, а раскрытие legacy-спойлера не меняет сохраняемый HTML. При редактировании новой записи старой версией приложения дополнительная метаинформация может быть потеряна.
- Отдельный переключатель темы и поле конфигурации не добавлялись. Обычный запуск использует auto; явные light/dark нужны для проверок.

Лицензии взяты из официальных дистрибутивов: [Onest / Google Fonts](https://github.com/google/fonts/blob/main/ofl/onest/OFL.txt), [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono/blob/master/OFL.txt).

## Проверки

| Проверка | Статус | Доказательство / предел проверки |
| --- | --- | --- |
| Baseline | passed | `baseline_tests_native.txt`: 52 passed |
| Полный итоговый suite | passed | `final_tests.txt`: 96 passed; включает прежние тесты запуска, поиска, конфигурации, резервных копий, файлов, MIME, хоткеев, clipboard и заметок |
| Темы, callback, rgba, оба шрифта, fallback без/с повреждённым TTF | passed | `test_design_system.py`, проверка реального лога в `test_design_verification.py` |
| Контраст на обоих фонах при 75%/100% | passed | Восемь комбинаций палитры/прозрачности/фона в полном suite; native композиции в снимках `*_opacity*.png` |
| Меню/настройки/вид/кнопки окна, Enter/Space, Tab, copy/focus/timer | passed | `test_redesign_widgets.py`; copy не активирует плитку |
| Длинные подписи, resize списка, crop, reset drop target, HUD | passed | `test_redesign_widgets.py`; существующие MIME/file-transfer тесты также зелёные |
| Rich text и заметки | passed | Полный `test_notes_widget.py`, включая light/dark, стандартные и явные цвета, смешанные фрагменты, legacy HTML |
| Light/dark при native Windows 100% | passed | Все пять разделов, grid/list, диалоги; снимки и `light_windows100_metrics.json`, `dark_windows100_metrics.json` |
| Масштаб Qt 125% на native Windows | passed | `QT_SCALE_FACTOR=1.25`; снимки/метрики `*_windows125_*` |
| Реальное переключение системного масштаба Windows на 125% | unverified | Настройка Windows не менялась; Qt scale factor не заменяет эту приёмку |
| Реальная смена системной темы Windows | unverified | Проверен Qt-сигнал смены схемы и открытые виджеты; системная настройка не переключалась |
| Native maximize/restore, программный resize, drag TitleBar синтетическими событиями | passed | `native_smoke.json`; сохранено перемещение на ожидаемое смещение |
| Закрытие в реальный доступный трей | passed | `native_smoke.json`: окно скрывается, значок остаётся; всплывающее уведомление заглушено |
| IPC передачи аргументов в обработчик окна | passed | Временный QLocalServer/QLocalSocket с уникальным именем; `native_smoke.json` |
| Полный запуск двух обычных экземпляров `run_app` | unverified | Пользовательский single-instance endpoint не занимался |
| Глобальный хоткей | passed частично | Регистрация временного `Ctrl+Alt+Shift+F10`, dispatch `WM_HOTKEY` в native filter и освобождение ресурса: passed |
| Физическое нажатие глобального хоткея | unverified | Синтетический dispatch не проверяет весь путь аппаратной клавиатуры |
| Перетаскивание краёв окна вручную | unverified | Программный resize не заменяет жест мышью по каждому краю |
| Drop из Проводника / Outlook | unverified | MIME извлечение и перенос тестовых файлов покрыты автоматикой; внешние приложения не использовались |
| Упаковка и проверка свежего EXE | passed | `pyinstaller_build.txt`, `bundle_verification/verification.json`, `bundle_native_verification/verification.json`, `exe_metadata.json` |
| Исходники Claude и содержимое ресурсов EXE | passed | `final_integrity.json`: исходники неизменны, два TTF и две лицензии встроены |

Системный экран проверки: `1366×768`, доступная область `1366×728`, logical DPI 96 и DPR 1. При Qt 125% доступная логическая область составляет примерно `1093×582`; запрос `1280×640` корректно ограничивается ею. Минимум `680×440` проверен отдельно. Снимки главного окна при 125% имеют физический размер `850×550` для этого минимума.

Снимки: `light_windows100_680x440_section0_grid.png`, `dark_windows125_680x440_section0_list.png`, `*_section3_grid.png` для заметок, `*_section4_grid.png` для clipboard, `*_dialog_*.png`, `*_opacity*.png`. Набор из четырёх вариантов содержит 96 финальных PNG; дополнительные baseline/offscreen снимки являются диагностическими.

## Производительность на 200 элементах

Отдельные процессы, одинаковые смешанные fixtures, native Windows 100%, окно `1000×620`, предварительный прогрев, три заполнения и 40 шагов прокрутки. Все 200 элементов помещались в измеряемый grid/list, независимо от фильтра раздела. Остальные собственные build/test процессы во время измерения не работали.

| Операция | Baseline, медиана с | Итоговый редизайн, медиана с |
| --- | ---: | ---: |
| Заполнение grid | 1.722 | 1.897 |
| 40 шагов прокрутки grid | 1.946 | 1.462 |
| Заполнение list | 1.329 | 1.348 |
| 40 шагов прокрутки list | 1.105 | 1.282 |

Первоначальное заполнение списка было медленнее, и повторный замер подтвердил проблему. Профилировщик показал 4800 вызовов `elidedText` на три заполнения/прокрутки; после исправления — 900, суммарное время этого расчёта уменьшилось с 0.636 до 0.111 с. Итоговое заполнение списка близко к baseline. Числа прокрутки/сетки имеют заметный разброс, включая единичные выбросы до 3.12 с; они не доказывают отсутствие любой регрессии на других машинах. Измеренная прокрутка списка примерно на 0.18 с дольше за 40 шагов.

Данные: `benchmark_baseline.json`, `benchmark_redesign_final.json`, повторные `benchmark_*_repeat.json`; профили до/после — `benchmark_redesign_profile.txt`, `benchmark_redesign_optimized.txt`. Оптимизация выполнена по найденному источнику затрат, без изменения сервисов и общего алгоритма заполнения.

## Устранённая ошибка упаковки

Первая сборка завершалась успешно, но EXE падал при импорте QtWidgets с сообщением о ненайденной процедуре. Анализ фактического состава CArchive и таблиц импортов установил:

1. В сборку попала `icuuc.dll` из стороннего Poppler в PATH; в ней отсутствуют импортируемые Qt6Core функции `ucnv_open`, `ucnv_close` и другие. Исходный Python-процесс использовал системную `C:\Windows\System32\icuuc.dll`.
2. Из стороннего libheif попали API-set DLL и `ucrtbase.dll`. В частности, `api-ms-win-core-synch-l1-2-0.dll` перенаправляла `WaitOnAddress` в `kernel32`, где такого экспорта на данной Windows нет; исходный процесс использовал системное API-set разрешение в KernelBase.

`main.spec` ограничивает PATH **на время Analysis** каталогами текущего Python/venv и Windows, затем восстанавливает исходное значение в процессе сборки. Зависимости внутри установленных Python-пакетов продолжают собираться обычными hooks. Установка/изменение системных DLL не выполнялись. Повторная сборка исключила чужие системные библиотеки и прошла запуск в native Windows и offscreen. Документы первой диагностики: `bundle_missing_imports.json`, `frozen_loaded_modules.json`, `bundle_dll_audit_before_path_fix.json`.

## Воспроизведение

Из корня проекта, в PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp gui\implementation_review\manual_test_temp
.\.venv\Scripts\python.exe main.py --verify-design gui\implementation_review\source_verification
.\.venv\Scripts\python.exe -m PyInstaller main.spec --distpath gui\implementation_review\exe --workpath gui\implementation_review\pyinstaller_work --noconfirm
.\gui\implementation_review\exe\applauncher.exe --verify-design gui\implementation_review\bundle_verification
```

Для native smoke и визуальной проверки:

```powershell
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
Remove-Item Env:QT_SCALE_FACTOR -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe gui\implementation_review\native_smoke.py
.\.venv\Scripts\python.exe gui\implementation_review\smoke_redesign.py --label manual_light --theme light --dialogs --opacity
$env:QT_SCALE_FACTOR = '1.25'
.\.venv\Scripts\python.exe gui\implementation_review\smoke_redesign.py --label manual_dark125 --theme dark --dialogs --opacity
```

Для осмотра изолированного полного окна есть `smoke_redesign.py --interactive --theme light` либо `--theme dark`. Он сохраняет временное состояние рядом с отчётом; реальные запуск приложений, перенос файлов и буфер подменены. Поэтому для финальной ручной проверки внешнего drop нужен отдельный контролируемый сценарий с тестовыми файлами и временной конфигурацией, а не этот интерактивный fixture.

В текущем окружении pytest изначально отсутствовал и был установлен в `.venv`; общий временный каталог pytest также выдал WinError 5. Итоговый прогон использует отдельный `--basetemp` и завершился с кодом 0. Ранние окруженческие ошибки сохранены как диагностические логи, они не являются текущими падениями suite.

## Оставшаяся ручная приёмка

Проверить на реальном Windows 125% и при системной смене темы; потянуть каждый край окна; нажать глобальный хоткей физической клавиатурой; запустить два экземпляра на отдельной тестовой конфигурации; перетащить тестовые файлы из Проводника и, если доступен, Outlook. До этих проверок статус соответствующих пунктов остаётся `unverified`, даже при зелёных автоматических тестах.
