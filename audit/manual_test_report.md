# Manual Test Report

## Сессия

- Дата: 2026-04-11
- Среда: Windows, Python 3.12.10, PySide6, SQLite, локальный Ollama
- Проект: `Exam_revision`
- Проверяющий: агент Codex

## Пройденные сценарии

| Сценарий | Что проверено | Результат | Статус | Доказательство |
| --- | --- | --- | --- | --- |
| Локальный Ollama | `ollama --version`, `ollama list`, `GET /api/tags`, `POST /api/generate` | Endpoint отвечает, `qwen3:8b` выбрана preferred-моделью, а diagnostic smoke допускает совместимую локальную `Qwen`-модель | PASS | `tests/test_ollama_integration.py`, `scripts/check_ollama.ps1` |
| Импорт DOCX/PDF | Импорт временных файлов через `DocumentImportService` | Оба формата реально разбираются и создают билеты | PASS | `tests/test_import_service.py` |
| UI error-paths | Unsupported import и невалидный Ollama URL | Пользователь получает понятную ошибку без ложного success | PASS | `tests/test_ui_handlers.py` |
| Реальный handoff после импорта | После успешного импорта доступны переходы в библиотеку, тренировку и статистику | Сценарий не обрывается | PASS | `tests/test_ui_handlers.py`, `audit/screens/gift-import.png` |
| Настройки секций | `Общие`, `Документы`, `Тренировка` сохраняют реальные значения | Новые поля попадают в `app_data/settings.json` | PASS | `tests/test_ui_handlers.py::test_settings_sections_persist_real_values` |
| Backup из настроек | Кнопка из раздела `Данные` создаёт копию SQLite | Создан файл `backups/exam_trainer-*.db` | PASS | `backups/exam_trainer-20260410-052755.db` |
| DLC `Тезис` | Paywall, активация, создание проекта, импорт материалов, logical gaps, role-aware mock и repair queue | DLC проходит через UI и сервисный слой как сильный локальный модуль с manual activation | PASS | `tests/test_defense_service.py`, `tests/test_defense_view.py`, `audit/ui_click_audit.md` |
| Режимы тренировки | Все 7 training cards открывают разные workspace и завершают разные сценарии, включая `state-exam-full` | Универсальный textarea-pane убран, режимы больше не притворяются разными | PASS | `tests/test_training_view_modes.py`, `audit/ui_click_audit.md`, `audit/screens/training-exe-smoke.png` |
| Responsive pass | Живой рендер на `1280x720`, `1366x768`, `1536x864` | Критических поломок layout нет | PASS | `audit/screens/library-1280.png`, `audit/screens/settings-1366.png`, `audit/screens/library-1536.png` |
| Large desktop pass | Живой рендер на `1600x960`, `1920x1080`, `2560x1440` | Критических поломок, ложной растяжки и развала композиции нет | PASS | `audit/screens/final_pass/library-1600.png`, `audit/screens/final_pass/library-1920.png`, `audit/screens/ultrawide/library-2560.png`, `audit/screens/ultrawide/settings-2560.png` |
| Финальный visual pass | Живой рендер `Библиотеки`, `Тренировки`, `Статистики`, `Настроек` после последних правок | Дефекты из оставшегося списка закрыты | PASS | `audit/screens/closeout-library.png`, `audit/screens/closeout-training.png`, `audit/screens/closeout-statistics.png`, `audit/screens/closeout-settings.png`, `audit/screens/closeout-settings-bottom.png` |
| Свежий Windows exe | Новый `dist\\Tezis\\Tezis.exe` и ярлык на рабочем столе запускаются и отвечают | Release и локальный ярлык указывают на актуальную сборку | PASS | smoke 2026-04-10: `Responding=True`, `MainWindowTitle=Тезис` |
| macOS code-path adaptation | Platform-aware пути, default models path, macOS helper scripts и docs | Логика выбрана корректно, unit-тесты проходят, Windows-only ветки больше не зашиты жёстко | PASS | `tests/test_platform_support.py`, `scripts/setup_ollama_macos.sh`, `scripts/check_ollama_macos.sh`, `scripts/build_mac_app.sh` |

## Автотесты

- `python -m compileall app application infrastructure ui tests` -> PASS
- `pytest -q` -> PASS, `53 passed, 5 skipped`
- `pytest -q --run-live-ollama` -> PASS, `58 passed`

## Вывод

- Остаток по текущему релизному объёму закрыт.
- Внутренние разделы настроек больше не являются фасадом.
- Документация обновлена свежими скриншотами, включая нижнюю зону `Настроек`.
- Отдельный большой desktop-pass тоже закрыт живым рендером на `2560x1440`.
- Для macOS выполнена кроссплатформенная адаптация по коду и документации, но ручной smoke-run на физическом Mac остаётся открытым QA-пунктом.

## Update 2026-04-10 06:40

- Асинхронный импорт `DOCX/PDF` внедрён на уровне UI shell.
- Импорт теперь идёт в background thread с отдельным SQLite connection.
- Живой Qt smoke подтвердил, что event loop не блокируется во время реального `DOCX` импорта.
- Доказательство: `TICKS=560`, `RESULT_OK=True`.
- Скрин после актуального запуска: `audit/screens/post-import-thread-library.png`.

## Update 2026-04-10 07:05

- В экран `Импорт документов` добавлен реальный stage-based progress bar.
- Во время импорта теперь показываются:
  - текущий этап
  - процент по фактически пройденным стадиям
  - прошедшее время
  - приблизительная оставшаяся длительность
- UI smoke с реальным рендером progress-состояния подтверждён.
- Доказательство: `audit/screens/import-progress-demo.png`.
- Полный `pytest -q` в этот момент не был полностью зелёным, потому что live Ollama integration test упёрся в недоступный локальный endpoint. Это относится к состоянию локального сервиса, а не к progress bar.

## Update 2026-04-10 07:55

- `SettingsView` перестал автоматически запускать Ollama diagnostics просто при открытии экрана.
- Qt teardown crash закрыт, `pytest tests/test_ui_handlers.py` выходит с кодом `0`.
- Базовый тестовый контур отделён от live Ollama integration через `--run-live-ollama`.
- Windows Ollama bridge теперь сначала уважает `OLLAMA_MODELS`, затем рабочий заполненный каталог моделей, а уже потом platform default.
- На проверочной Windows-машине `OLLAMA_MODELS` нормализован на фактически заполненный каталог `~/.ollama/models`, после чего `scripts/check_ollama.ps1` снова подтвердил живой endpoint, модель и generate smoke.

## Update 2026-04-10 10:45

- В продукт встроен профиль ответа `Госэкзамен`.
- Импорт теперь может сохранять билет как `Обычный билет` или `Госэкзамен`.
- Для профиля `Госэкзамен` строятся 6 блоков ответа, сохраняются block scores, criterion scores и профиль освоения по блокам.
- В тренировке добавлен отдельный режим `Полный госответ`.
- Карточка билета показывает структуру ответа по блокам, а статистика показывает отдельный профиль готовности к госэкзамену.
- Базовые проверки без live Ollama на этот момент: `pytest -q` -> `36 passed, 4 skipped`, `python -m compileall app application infrastructure ui tests` -> `PASS`.
- Быстрый menu-by-menu click-audit по всему UI не зелёный полностью: в `audit/ui_click_audit.md` остаётся `FAIL` по `training -> mode-specific scenarios`. Это вынесено в `audit/open_issues.md` как открытый QA-хвост, а не замаскировано.
## Update 2026-04-10 11:20

- Пересобран `dist\Tezis\Tezis.exe` и обновлён `dist\Tezis-windows.zip`.
- Ярлык на рабочем столе пересоздан и снова указывает на `dist\Tezis\Tezis.exe`.
- Smoke-запуск готовой сборки подтверждён: `HasExited=False`, `Responding=True`, `MainWindowTitle=Тезис`.
- Быстрый релизный аудит перед тегом подтверждает:
  - работает профиль `Госэкзамен` на уровне импорта, answer blocks, scoring, карточки билета и статистики;
  - базовый non-live контур зелёный: `pytest -q` -> `36 passed, 4 skipped`;
  - открытым остаётся один QA-хвост: `audit/ui_click_audit.md` всё ещё даёт `FAIL` по `training -> mode-specific scenarios`.

## Update 2026-04-11

- `scripts/ui_click_audit.py` переведён на надёжный критерий завершения training-сценариев: он проверяет реальную запись попытки и корректный mode-specific result, а не хрупкое ожидание старого label после `refresh_all_views()`.
- Windows click-audit теперь покрывает все 7 training workspace, включая `state-exam-full`, и завершается с `EXIT=0` без `FAIL`.
- `scripts/build_exe.ps1` фиксирует source-of-truth semantics: корневые `README/docs/scripts` копируются в packaged tree при сборке, а `dist` считается generated output.
- `scripts/clean_project.ps1` по умолчанию чистит только transient build/cache артефакты; удаление `dist` вынесено в `-FullClean`.
- packaged build теперь содержит `build_info.json`, а UI показывает версию и commit.
- для Windows release добавлен отдельный `scripts/release_smoke.ps1`.
- Для внешнего macOS smoke добавлен отдельный handoff checklist.
- Свежая верификация цикла:
  - `python -m pytest -q` -> `53 passed, 5 skipped`
  - `python -m pytest -q --run-live-ollama` -> `58 passed`
  - `powershell -ExecutionPolicy Bypass -File scripts/check_ollama.ps1` -> `PASS`
  - `powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1` -> `PASS`
  - packaged `dist\Tezis\Tezis.exe` сохранил `dist\Tezis\release-smoke.png`

## Update 2026-04-11 DLC

- `Защита DLC` усилен до strong paid local module with manual activation.
- После импорта материалов DLC теперь строит:
  - logical gaps
  - evidence-aware статус по ключевым блокам
  - role-aware rehearsal для `Научрук / Оппонент / Комиссия`
  - таймерную репетицию
  - repair queue
- `scripts/ui_click_audit.py` подтверждает новые DLC-сценарии:
  - `gap analysis`
  - `repair queue`
  - `timer controls`
  - `repair feedback`
