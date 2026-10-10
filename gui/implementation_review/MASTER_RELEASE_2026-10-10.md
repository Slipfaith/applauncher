# AppLauncher: объединение в master и проверка сборки

Дата: 10 октября 2026. По выбору пользователя целевая ветка — `master`, основная ветка репозитория; ветки `main` нет.

## Объединение

- Исходная основная ветка: `d38b982f74113f610f96fba82e72cbb39fea8d27`, уже содержит новый дизайн, живые темы и иконки LINE.
- Исправления ревью, тесты и установщик: `2f648913295b97c5067e2a363b161db95a7d1249`.
- Merge-коммит: `05c2c9a1b1be9629b8eb8151950474713124b08d`. Конфликтов не было.
- Сохранены постоянные ID плиток, защита повреждённого JSON, параметры запуска и кадрирование, точный clipboard, передача пустого запроса IPC и отзывчивое ожидание фоновых copy/icon задач при выходе.

## Тесты на объединённой ветке

**151 passed in 76.17s, 0 failed, 0 skipped**. [Полный лог](master-release-tests-20261010.txt).

```powershell
New-Item -ItemType Directory -Path build -Force
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider -o faulthandler_timeout=30 --basetemp build/master-tests-20261010
```

Первый повторный прогон не создал fixtures, потому что после очистки отсутствовал родительский каталог `build`. Каталог создан, полный прогон выполнен повторно и прошёл.

## Готовый EXE

Собран из merge-коммита `05c2c9a1b1be9629b8eb8151950474713124b08d` командой:

```powershell
.venv/Scripts/python.exe -m PyInstaller main.spec --distpath dist --workpath build/master-release-20261010 --noconfirm
```

- [EXE в репозитории](exe/applauncher.exe); локальная копия: `dist/applauncher.exe`. Хеши обеих копий совпадают.
- Размер: **46 844 223 байта**.
- SHA-256: `371a6bc8b78ac664cb4a362ff4b7af14454340db80d12c63cf0c7f978de1f496`.
- [Успешный лог сборки](master-release-build-retry-20261010.txt).

Первая упаковка остановилась на Windows `EndUpdateResourceW`, код 110, при записи манифеста. Повтор той же команды с уже собранными модулями завершился успешно; исходники не менялись.

Готовый EXE запущен с `--verify-design` через два Qt backend: [offscreen](master-release-offscreen-20261010/verification.json) и [windows](master-release-windows-20261010/verification.json). Оба запуска завершились с кодом 0, `frozen=true`, `passed=true`, `warnings=[]`. Проверены Onest и JetBrains Mono, светлая и тёмная темы, согласованная тема настроек, иконки LINE и многоточие в длинном названии плитки. Проверка изолирована от пользовательской конфигурации; ручная проверка DPI в эту верификацию не входит.

## Очистка

По предварительному списку удалены **1699 файлов, 169 554 463 байта** (161,7 МиБ): старые PyInstaller/test outputs, fixtures, дублирующие скриншоты и метрики, pytest/Python caches, пустой временный каталог и остаток неудачного BMAD setup.

Все цели проверены на нахождение внутри `E:/PythonProjects/applauncher`, отсутствие отслеживаемых файлов и reparse points. Хеши **82 сохраняемых файлов** совпали до и после удаления. Настройки и backup, исходники, `.venv`, IDE, EXE/установщики, BMAD и новая папка `promo` сохранены. Локальные BMAD snapshots и навыки исключены из Git без удаления.

После сборки и проверок удалены только новые временные каталоги `build/master-tests-20261010` и `build/master-release-20261010`: ещё **176 файлов, 50 752 955 байт**. Хеши 73 сохраняемых исходников, настроек, установщиков и свежего EXE совпали до и после этого удаления. Итог: **1875 файлов, 220 307 418 байт (210,1 МиБ)**. [Результат финальной очистки](MASTER_CLEANUP_RESULT_2026-10-10.json).
