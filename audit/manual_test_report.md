# Manual Test Report

## Сессия

- Дата: 2026-04-17
- Среда: Windows 11, Python 3.12, PySide6, SQLite
- Ветка: `main`
- Проверяющий: Codex

## Что реально перепроверено

| Сценарий | Что проверено | Статус | Доказательство |
| --- | --- | --- | --- |
| Базовый тестовый контур | `python -m pytest -q` | PASS | `186 passed, 5 skipped` |
| Training modes | Все 8 режимов открывают отдельные workspace, включая `review` | PASS | `tests/test_training_view_modes.py`, `audit/ui_click_audit.md`, `audit/ui_click_audit_dark.md` |
| TopBar section meta | Заголовок и subtitle меняются при `switch_view()` | PASS | `ui/components/topbar.py`, `scripts/ui_click_audit.py`, `audit/ui_click_audit.md` |
| Light click audit | Навигация, import handoff, training, defense и settings | PASS | `audit/ui_click_audit.md` |
| Dark click audit | Те же сценарии на тёмной палитре | PASS | `audit/ui_click_audit_dark.md` |
| Warm-minimal visual gate | `Library`, `Tickets`, `Training` в light и dark | PASS | `docs/superpowers/screenshots/2026-04-17-warm-minimal/` |
| Sidebar visual cleanup | Активная иконка, шапка бренда и тон логознака | PASS | `ui/components/sidebar.py`, `ui/theme/palette.py`, human visual check 2026-04-17 |
| Dialogue gate | Экран блокируется без готового Ollama и открывается при валидном ticket-flow | PASS | `tests/test_dialogue_flow.py` |
| Defense DLC | paywall, активация, проект, импорт, gap analysis, repair queue, mock defense | PASS | `tests/test_defense_service.py`, `tests/test_defense_view.py`, `audit/ui_click_audit.md` |
| QPainter regression | Переключение вкладок без nested-effect warning storm | PASS | `tests/test_painter_warnings.py` |

## Что не перепроверялось в этой сессии

- live Ollama integration с реальной локальной моделью;
- runtime smoke на реальном macOS-устройстве;
- отдельный ручной visual pass для всех вторичных экранов за пределами `Library`, `Tickets`, `Training`.

## Вывод

- Документация синхронизирована с текущим `main`.
- Warm-minimal stage 1 закрыт и зафиксирован скриншотами.
- Training truth-source теперь 8 режимов, а не 7.
- Основной открытый QA-хвост остаётся прежним: реальный macOS smoke-run.
