> **Политика evidence для скриншотов (2026-04-15):**
> `audit/screens/` — локальная рабочая папка и находится в `.gitignore`.
> Канонические скриншоты для публичной документации живут в `docs/screenshots/`.
> Строки ниже, которые ссылаются на `audit/screens/…`, отражают реальные прогоны на машине проверяющего и не обязательно доступны в чужом клоне репозитория.
> Для внешнего читателя authoritative evidence — `tests/*` и `docs/screenshots/*`.

# Screen by Screen Checklist

Проверенные desktop-размеры: `1280x720`, `1366x768`, `1536x864`, `1600x960`, `1920x1080`, `2560x1440`
Статусы: `PASS`, `PARTIAL`, `FAIL`, `OPEN`

| Экран | Что проверено | Статус | Доказательство | Комментарий |
| --- | --- | --- | --- | --- |
| Sidebar и навигация | Активный раздел, переключение stacked views, честный Ollama status | PASS | `audit/screens/closeout-library.png`, `audit/screens/closeout-settings.png` | Навигация не декоративная |
| Библиотека | Список документов, detail panel, правая статистика, режимы тренировки | PASS | `audit/screens/closeout-library.png` | Правая колонка больше не ломается |
| Предметы | Читаемость summary и карточек | PASS | `audit/screens/subjects.png` | Пустой wide-layout убран |
| Разделы | Список без пустого фасада, фильтрация | PASS | `audit/screens/sections.png` | Огромная пустая карта устранена |
| Билеты | Карта билета, микронавыки, weak areas | PASS | `audit/screens/tickets.png` | Экран рабочий и читаемый |
| Импорт документов | Выбор файла, summary, handoff в следующие разделы | PASS | `audit/screens/gift-import.png`, `tests/test_ui_handlers.py` | Сценарий не обрывается |
| Тренировка | Карточная adaptive queue, editor, проверка ответа | PASS | `audit/screens/closeout-training.png` | Очередь стала нормально читаемой |
| Статистика | Общая статистика, recent sessions, weak areas | PASS | `audit/screens/closeout-statistics.png` | Критичных visual-дефектов не осталось |
| Настройки / Ollama | Верхняя форма, нижняя диагностика, action panel, honest status | PASS | `audit/screens/closeout-settings.png`, `audit/screens/closeout-settings-bottom.png` | Экран собран и читаем |
| Настройки / Общие | Тема, стартовый экран, автопроверка, DLC teaser | PASS | `ui/views/settings_view.py`, `tests/test_ui_handlers.py::test_settings_sections_persist_real_values` | Реальные persisted controls |
| Настройки / Документы | Папка импорта, формат, LLM assist | PASS | `ui/views/settings_view.py`, `tests/test_ui_handlers.py::test_settings_sections_persist_real_values` | Реальные persisted controls |
| Настройки / Тренировка | Режим по умолчанию, review mode, размер очереди | PASS | `ui/views/settings_view.py`, `tests/test_ui_handlers.py::test_settings_sections_persist_real_values` | Реальные persisted controls |
| Настройки / Данные | Пути к базе, backup, открытие каталогов | PASS | `ui/views/settings_view.py`, `backups/exam_trainer-20260410-052755.db` | Backup реально создаётся |
| Настройки / Продвинутые | Доступ к docs/audit и запуск `check_ollama.ps1` | PASS | `ui/views/settings_view.py` | Реальные сервисные действия |

Неблокирующий остаток:
- отсутствует
