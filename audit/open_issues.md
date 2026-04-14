# Open Issues

Статусы: `OPEN`, `IN_PROGRESS`, `BLOCKED`, `DONE`

На 10 апреля 2026 основной Windows-релизный сценарий по билетам закрыт.
По DLC `Тезис` сейчас есть первая рабочая вертикаль, но не полный объём запланированного модуля.
Отдельно всё ещё остаётся внешний QA-пункт по реальному macOS smoke-run.

| ID | Проблема | Влияние на пользователя | Severity | Временный обход | Exit criteria | Статус | Доказательство |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DLC-SCOPE | DLC `Тезис` сейчас закрывает paywall, проекты, импорт, dossier, outline и mock-защиту, но ещё не покрывает весь ранее согласованный объём | Нельзя честно называть DLC завершённым коммерческим модулем | medium | Использовать текущую версию как первую рабочую итерацию | Добавить остальной согласованный объём DLC и повторить menu-by-menu audit | OPEN | `ui/views/defense_view.py`, `tests/test_defense_service.py`, `audit/ui_click_audit.md` |
| QA-ULTRA | Отдельный visual-pass на большом desktop был не завершён | Риск композиционных отличий на очень широком экране | low | Не требовался | Снять живые скриншоты и пройти human visual audit на `2560x1440` | DONE | `audit/screens/ultrawide/library-2560.png`, `audit/screens/ultrawide/training-2560.png`, `audit/screens/ultrawide/statistics-2560.png`, `audit/screens/ultrawide/settings-2560.png` |
| UI-FREEZE | Окно зависало во время тяжёлого импорта `DOCX/PDF` | Главный пользовательский сценарий выглядел сломанным | critical | Не использовать | Перенести импорт и Ollama diagnostics в background threads, подтвердить живым Qt smoke | DONE | `audit/manual_test_report.md`, `audit/visual_defects.md`, `audit/screens/post-import-thread-library.png` |
| TRAINING-AUDIT | Быстрый click-audit всё ещё не подтвердил завершение всех mode-specific сценариев в тренировке, хотя unit/UI тесты по режимам проходят | Нельзя честно заявлять, что вся тренировка закрыта end-to-end человеческим автопрокликом | medium | Использовать режимы вручную или опираться на `tests/test_training_view_modes.py` до добивки click-audit | Довести `scripts/ui_click_audit.py` до реального прохождения сценариев `reading`, `active-recall`, `cloze`, `matching`, `plan`, `mini-exam`, `state-exam-full` без ложного `FAIL` | OPEN | `audit/ui_click_audit.md`, `tests/test_training_view_modes.py` |
| MAC-REAL | macOS-ветка адаптирована по коду, скриптам и инструкции, но не прогнана руками на реальном Mac | Возможны platform-specific нюансы Gatekeeper, Terminal launch и `.app` bundle, которые нельзя честно подтвердить из Windows-среды | medium | Использовать `python3 main.py` и следовать разделу macOS в `README.md` | Собрать `.app` на реальном Mac, пройти `setup/check` Ollama и smoke `import -> training -> statistics` | OPEN | `tests/test_platform_support.py`, `scripts/setup_ollama_macos.sh`, `scripts/check_ollama_macos.sh`, `scripts/build_mac_app.sh` |

## Added 2026-04-15

| ID | Проблема | Влияние | Severity | Workaround | Exit criteria | Статус | Доказательство |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TEST-ENV-HYGIENE | `tests/test_ollama_runtime.py` мог падать на машине с выставленным `OLLAMA_MODELS` | Блокировал `pytest -q` на любом dev-окружении с уже настроенным Ollama | high | Использовать `monkeypatch.delenv` в каждом тесте | Проход `pytest -q` на машине с непустым `OLLAMA_MODELS` | DONE | `tests/test_ollama_runtime.py`, прогон 2026-04-15 `40 passed, 4 skipped` |
| DEP-PINNING | Отсутствовал `requirements.txt`, README обещал его | Невоспроизводимая установка для однокурсников | high | Ставить зависимости руками | `pip install -r requirements.txt` в чистом venv | DONE | `requirements.txt`, `requirements-dev.txt`, `tests/test_dependencies.py` |
