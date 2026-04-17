# Screen by Screen Checklist

Статусы: `PASS`, `PARTIAL`, `OPEN`

| Экран | Что проверено | Статус | Доказательство | Комментарий |
| --- | --- | --- | --- | --- |
| Sidebar | Все пункты навигации, активный раздел, warm accent-state | PASS | `audit/ui_click_audit.md`, `audit/ui_click_audit_dark.md` | Навигация и визуальная индикация совпадают |
| TopBar | Кнопка настроек, page title и subtitle по текущему разделу | PASS | `audit/ui_click_audit.md` | Runtime drift заголовка закрыт |
| Библиотека | Список документов, detail tabs, training CTA, DLC teaser, импорт из библиотеки | PASS | `audit/ui_click_audit.md`, `docs/superpowers/screenshots/2026-04-17-warm-minimal/library-light.png` | Ключевой экран visual refresh |
| Предметы | Рендер summary и поиск по списку | PASS | `audit/ui_click_audit.md` | Theme inheritance достаточна |
| Разделы | Фильтр и базовый render | PASS | `audit/ui_click_audit.md` | Theme inheritance достаточна |
| Билеты | Выбор билета, ticket map, warm-minimal folio cards | PASS | `audit/ui_click_audit.md`, `docs/superpowers/screenshots/2026-04-17-warm-minimal/tickets-light.png` | Ключевой экран visual refresh |
| Импорт | Запуск, summary, handoff в библиотеку, тренировку и статистику | PASS | `audit/ui_click_audit.md`, `tests/test_ui_handlers.py` | Основной import flow подтверждён |
| Тренировка | Adaptive queue, 8 mode-specific workspaces, реальные результаты | PASS | `audit/ui_click_audit.md`, `audit/ui_click_audit_dark.md`, `tests/test_training_view_modes.py` | `review` теперь тоже покрыт |
| Диалог | Gate до готовности Ollama, открытие ticket-bound session | PASS | `tests/test_dialogue_flow.py` | Screen flow проверен тестами и navigation audit |
| Статистика | Snapshot и реальные попытки после training | PASS | `audit/ui_click_audit.md` | Блок статистики не fake |
| Карта знаний | Базовый render и загрузка данных | PARTIAL | `tests/test_responsive_layouts.py`, `tests/test_ui_handlers.py` | Нужен отдельный ручной user-flow pass |
| Подготовка к защите | paywall, активация, проект, импорт, gap analysis, mock defense | PASS | `audit/ui_click_audit.md`, `tests/test_defense_service.py`, `tests/test_defense_view.py` | DLC flow живой |
| Настройки | Навигация секций, Ollama diagnostics, save/reset, backup и сервисные действия | PASS | `audit/ui_click_audit.md`, `audit/ui_click_audit_dark.md`, `tests/test_ui_handlers.py` | Экран не фасад |

Неблокирующий остаток:

- `Карта знаний` требует отдельного ручного сценарного аудита beyond render/responsive checks;
- вторичные экраны ещё не проходили персональный warm-minimal redesign.
