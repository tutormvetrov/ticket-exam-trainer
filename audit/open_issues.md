# Open Issues

Статусы: `OPEN`, `DONE`

| ID | Проблема | Влияние на пользователя | Severity | Временный обход | Exit criteria | Статус | Доказательство |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MAC-REAL | macOS code-path подготовлен, но не прогнан вручную на реальном Mac | Возможны platform-specific нюансы bundle launch, Gatekeeper и локального Ollama | medium | Использовать `python3 main.py` и macOS scripts из репозитория | Собрать `.app` на Mac и пройти smoke `settings -> import -> training -> statistics` | OPEN | `tests/test_platform_support.py`, `scripts/setup_ollama_macos.sh`, `scripts/check_ollama_macos.sh`, `scripts/build_mac_app.sh`, `audit/mac_runtime_handoff.md` |
| TRAINING-REVIEW-AUDIT | `review` mode был не отражён в старых audit-артефактах | Документация занижала фактический набор режимов | medium | Не нужен | Держать test и click audit зелёными для `review` | DONE | `tests/test_training_view_modes.py`, `scripts/ui_click_audit.py`, `audit/ui_click_audit.md`, `audit/ui_click_audit_dark.md` |
| UI-WARM-STAGE1 | Warm-minimal stage 1 требовал manual visual gate и фиксации референсов | Без скриншотов было сложнее ловить регрессии стиля | low | Не нужен | Хранить комплект из 6 актуальных скриншотов | DONE | `docs/superpowers/screenshots/2026-04-17-warm-minimal/` |
