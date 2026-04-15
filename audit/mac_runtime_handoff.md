# macOS Runtime Handoff

Этот чеклист нужен внешнему исполнителю, который будет подтверждать macOS runtime path на реальном устройстве. Из Windows-среды этот этап не закрывается и не должен помечаться как `DONE` без живого прогона.

## Что подготовить заранее

- актуальный commit или release build
- установленный `Python 3.12+`, если запуск идёт из исходников
- локальный `Ollama`
- локально загруженную `qwen3:8b` или совместимую локальную `Qwen`-модель

## Последовательность smoke-run

1. Запустить `bash scripts/setup_ollama_macos.sh`.
2. Запустить `bash scripts/check_ollama_macos.sh`.
3. Запустить приложение через `python3 main.py`.
4. При необходимости собрать `.app` через `bash scripts/build_mac_app.sh`.
5. Если macOS блокирует unsigned build, отдельно зафиксировать это и попробовать:

```bash
xattr -dr com.apple.quarantine dist/Tezis.app
```

## Что проверить в приложении

1. `launch -> library/startup status`
2. `import -> handoff`
3. `training`
4. `statistics`
5. DLC smoke:
   - экран открывается
   - paywall виден до активации
   - после локальной активации открывается workspace

## Какой smoke считается достаточным

- импортировать один `DOCX` или `PDF`
- перейти в `Тренировку`
- пройти хотя бы один mode-specific сценарий
- открыть `Статистику` и убедиться, что попытка появилась
- открыть `Защита DLC` и подтвердить корректный paywall

## Какие доказательства собрать

- скриншот стартового окна
- скриншот `Настройки -> Ollama` после успешной проверки
- скриншот после успешного импорта
- скриншот `Тренировки`
- скриншот `Статистики`
- скриншот DLC paywall
- commit hash или версия сборки
- результат `scripts/check_ollama_macos.sh`
- любые проблемы с Gatekeeper, Terminal launch или `.app` bundle
