# Failure Cases

Статусы: `PASS`, `PARTIAL`, `FAIL`, `OPEN`

| Функция | Сценарий отказа | Шаги воспроизведения | Ожидаемое поведение | Фактическое поведение | Сообщение пользователю | Статус | Доказательство |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Ollama diagnostics | Недоступный endpoint | Указать `http://localhost:65500` | Endpoint должен считаться недоступным | `inspect()` возвращает `endpoint_ok=False` | Ошибка surfaced без ложного success | PASS | `tests/test_ollama_runtime.py`, `tests/test_ui_handlers.py` |
| Import UI | Битый или неподдерживаемый файл | Вызвать import с неверным путём или форматом | Показать понятную ошибку | `QMessageBox.critical` вызывается с объяснением | Человекочитаемая ошибка | PASS | `tests/test_ui_handlers.py` |
| Training review | Пустой ответ в `review` mode | Открыть `review` и нажать submit без текста | Не отправлять пустой answer | Workspace показывает требование ввести ответ | `Напишите ответ перед отправкой на рецензию.` | PASS | `ui/components/training_workspaces.py` |
| Dialogue | Ollama не готов | Открыть `Диалог` без валидной диагностики | Экран должен оставаться gated | Gate card остаётся видимой, body скрыт | Пользователь видит причину блокировки | PASS | `tests/test_dialogue_flow.py` |
| Defense activation | Неверный ключ активации | Подать ключ для другой установки или поддельную подпись | Модуль не должен открываться | License state остаётся неактивным | Ошибка surfaced через activation status | PASS | `tests/test_dlc_license_ed25519.py` |
