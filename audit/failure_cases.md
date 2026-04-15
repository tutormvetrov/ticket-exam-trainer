# Failure Cases

Статусы: `PASS`, `PARTIAL`, `FAIL`, `OPEN`

Правила:

- каждый кейс должен иметь воспроизводимые шаги
- `PASS` означает, что отказ обработан корректно
- `FAIL` означает, что найден пользовательский дефект
- если кейс не проигран руками или тестом, статус не выше `OPEN`

| функция | сценарий отказа | шаги воспроизведения | ожидаемое поведение | фактическое поведение | сообщение пользователю | статус | доказательство |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Ollama diagnostics | недоступный endpoint | использовать `http://localhost:65500` | endpoint должен считаться недоступным | `inspect()` вернул `endpoint_ok=False` | диагностика должна показать недоступность сервиса | PASS | `tests/test_ollama_integration.py` |
| Import fallback | структура билета плохо распознана | подать слабо структурированный текст | должен включиться fallback на единый chunk | service добавляет warning и собирает единый кандидат | warning фиксируется в результате | PASS | `application/import_service.py` |
| Библиотека / Import UI | импортируемый файл повреждён или формат не поддерживается | вызвать `open_import_dialog()` с неподдерживаемым путём | должен появиться понятный error dialog без ложного успеха | `QMessageBox.critical` вызван с текстом об unsupported format | человекочитаемая ошибка surfaced | PASS | `tests/test_ui_handlers.py` |
| Settings / Ollama | endpoint недоступен после сохранения параметров | вызвать `save_settings()` с `http://localhost:65500` | статус не должен оставаться зелёным | `status_pill` переходит в `Недоступно`, `error_label` заполнен, settings сохраняются | ошибка surfaced без false success | PASS | `tests/test_ui_handlers.py` |
