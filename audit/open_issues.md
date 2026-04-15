# Open Issues

Статусы: `OPEN`, `IN_PROGRESS`, `BLOCKED`, `DONE`

На 11 апреля 2026 основной Windows-релизный сценарий по билетам закрыт.
По DLC `Тезис` цикл усиления до strong paid local module закрыт: logical gaps, role-aware rehearsal, таймер и repair queue уже встроены.
Отдельно всё ещё остаётся внешний QA-пункт по реальному macOS smoke-run.

| ID | Проблема | Влияние на пользователя | Severity | Временный обход | Exit criteria | Статус | Доказательство |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DLC-SCOPE | DLC `Тезис` теперь покрывает paywall, проекты, импорт, dossier, outline, storyboard, logical gaps, role-aware rehearsal, таймер и repair queue | В рамках текущего продуктового объёма DLC можно считать закрытым как сильный локальный модуль с manual activation | medium | Не нужен | Держать DLC menu-by-menu audit зелёным и не путать модуль с billing-продуктом | DONE | `ui/views/defense_view.py`, `application/defense_service.py`, `tests/test_defense_service.py`, `audit/ui_click_audit.md` |
| QA-ULTRA | Отдельный visual-pass на большом desktop был не завершён | Риск композиционных отличий на очень широком экране | low | Не требовался | Снять живые скриншоты и пройти human visual audit на `2560x1440` | DONE | `audit/screens/ultrawide/library-2560.png`, `audit/screens/ultrawide/training-2560.png`, `audit/screens/ultrawide/statistics-2560.png`, `audit/screens/ultrawide/settings-2560.png` |
| UI-FREEZE | Окно зависало во время тяжёлого импорта `DOCX/PDF` | Главный пользовательский сценарий выглядел сломанным | critical | Не использовать | Перенести импорт и Ollama diagnostics в background threads, подтвердить живым Qt smoke | DONE | `audit/manual_test_report.md`, `audit/visual_defects.md`, `audit/screens/post-import-thread-library.png` |
| TRAINING-AUDIT | Windows click-audit теперь подтверждает menu-by-menu прохождение всех 7 mode-specific training сценариев без ложного `FAIL` | Релизный training flow можно считать закрытым на уровне Windows beta | medium | Не нужен | Держать `scripts/ui_click_audit.py` зелёным при следующих UI-изменениях | DONE | `audit/ui_click_audit.md`, `tests/test_training_view_modes.py` |
| TEST-LIVE-OLLAMA | Live Ollama интеграция теперь отделена от базового `pytest -q` | Базовый контур больше не выглядит сломанным без локальной модели, при этом live проверка не исчезла | medium | Базовый прогон: `pytest -q`, live прогон: `pytest -q --run-live-ollama` | Подтвердить оба режима реальным запуском | DONE | `pytest.ini`, `tests/conftest.py`, `tests/test_ollama_integration.py`, прогоны 2026-04-10 `22 passed, 4 skipped` и `4 passed` |
| MAC-REAL | macOS-ветка адаптирована по коду, скриптам и инструкции, но не прогнана руками на реальном Mac | Возможны platform-specific нюансы Gatekeeper, Terminal launch и `.app` bundle, которые нельзя подтвердить из Windows-среды | medium | Использовать `python3 main.py` и следовать разделу macOS в `README.md` | Собрать `.app` на реальном Mac, пройти `setup/check` Ollama и smoke `import -> training -> statistics` | OPEN | `tests/test_platform_support.py`, `scripts/setup_ollama_macos.sh`, `scripts/check_ollama_macos.sh`, `scripts/build_mac_app.sh`, `audit/mac_runtime_handoff.md` |
