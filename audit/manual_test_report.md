# Manual Test Report

## Сессия

- Дата: 2026-04-10
- Среда: Windows, Python 3.12.10, PySide6, SQLite, локальный Ollama
- Проект: `Exam_revision`
- Проверяющий: агент Codex

## Пройденные сценарии

| Сценарий | Что проверено | Результат | Статус | Доказательство |
| --- | --- | --- | --- | --- |
| Локальный Ollama | `ollama --version`, `ollama list`, `GET /api/tags`, `POST /api/generate` | Endpoint отвечает, `mistral:instruct` доступна, реальный ответ модели получен | PASS | `tests/test_ollama_integration.py`, `scripts/check_ollama.ps1` |
| Импорт DOCX/PDF | Импорт временных файлов через `DocumentImportService` | Оба формата реально разбираются и создают билеты | PASS | `tests/test_import_service.py` |
| UI error-paths | Unsupported import и невалидный Ollama URL | Пользователь получает честную ошибку без ложного success | PASS | `tests/test_ui_handlers.py` |
| Реальный handoff после импорта | После успешного импорта доступны переходы в библиотеку, тренировку и статистику | Сценарий не обрывается | PASS | `tests/test_ui_handlers.py`, `audit/screens/gift-import.png` |
| Настройки секций | `Общие`, `Документы`, `Тренировка` сохраняют реальные значения | Новые поля попадают в `app_data/settings.json` | PASS | `tests/test_ui_handlers.py::test_settings_sections_persist_real_values` |
| Backup из настроек | Кнопка из раздела `Данные` создаёт копию SQLite | Создан файл `backups/exam_trainer-*.db` | PASS | `backups/exam_trainer-20260410-052755.db` |
| Responsive pass | Живой рендер на `1280x720`, `1366x768`, `1536x864` | Критических поломок layout нет | PASS | `audit/screens/library-1280.png`, `audit/screens/settings-1366.png`, `audit/screens/library-1536.png` |
| Large desktop pass | Живой рендер на `1600x960`, `1920x1080`, `2560x1440` | Критических поломок, ложной растяжки и развала композиции нет | PASS | `audit/screens/final_pass/library-1600.png`, `audit/screens/final_pass/library-1920.png`, `audit/screens/ultrawide/library-2560.png`, `audit/screens/ultrawide/settings-2560.png` |
| Финальный visual pass | Живой рендер `Библиотеки`, `Тренировки`, `Статистики`, `Настроек` после последних правок | Дефекты из честного остатка закрыты | PASS | `audit/screens/closeout-library.png`, `audit/screens/closeout-training.png`, `audit/screens/closeout-statistics.png`, `audit/screens/closeout-settings.png`, `audit/screens/closeout-settings-bottom.png` |
| macOS code-path adaptation | Platform-aware пути, default models path, macOS helper scripts и docs | Логика выбрана корректно, unit-тесты проходят, Windows-only ветки больше не зашиты жёстко | PASS | `tests/test_platform_support.py`, `scripts/setup_ollama_macos.sh`, `scripts/check_ollama_macos.sh`, `scripts/build_mac_app.sh` |

## Автотесты

- `python -m compileall app application infrastructure ui tests` -> PASS
- `pytest -q` -> PASS, `22 passed, 4 skipped`
- `pytest -q --run-live-ollama tests/test_ollama_integration.py` -> PASS, `4 passed`

## Вывод

- Честный остаток по текущему релизному объёму закрыт.
- Внутренние разделы настроек больше не являются фасадом.
- Документация обновлена свежими скриншотами, включая нижнюю зону `Настроек`.
- Отдельный большой desktop-pass тоже закрыт живым рендером на `2560x1440`.
- Для macOS выполнена честная кроссплатформенная адаптация по коду и документации, но ручной smoke-run на физическом Mac остаётся открытым QA-пунктом.

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
