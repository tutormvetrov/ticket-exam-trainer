# Тренажёр билетов к вузовским экзаменам

Локальное desktop-приложение на `Python 3.12+` и `PySide6` для подготовки к обычным экзаменам, письменному госэкзамену и защите выпускной работы. Облачные LLM не используются. Все LLM-функции работают только через локальный `Ollama`.

## Текущее состояние

- Основной Windows desktop flow подтверждён.
- Warm Minimal visual refresh завершён для shell, `Библиотеки`, `Билетов` и `Тренировки`.
- В навигации доступны экраны: `Библиотека`, `Предметы`, `Разделы`, `Билеты`, `Импорт`, `Тренировка`, `Диалог`, `Статистика`, `Карта знаний`, `Подготовка к защите`, `Настройки`.
- В `Тренировке` доступны 8 отдельных режимов:
  - `reading`
  - `active-recall`
  - `cloze`
  - `matching`
  - `plan`
  - `mini-exam`
  - `state-exam-full`
  - `review`
- Поддержан профиль ответа `Госэкзамен` с 6 answer blocks, block scores и criterion scores.
- Отдельный DLC workspace `Подготовка к защите` уже рабочий: paywall, локальная активация, проекты, импорт материалов, dossier, outline, storyboard, logical gaps, mock defense и repair queue.
- Базовый тестовый контур на 2026-04-17: `python -m pytest -q` -> `186 passed, 5 skipped`.

## Основные сценарии

### 1. Базовый exam flow

1. Запустить приложение.
2. Открыть `Настройки -> Ollama`.
3. Проверить локальный endpoint и модель.
4. Импортировать `DOCX` или `PDF`.
5. Проверить результат в `Библиотеке` и `Билетах`.
6. Перейти в `Тренировку`.
7. Смотреть динамику в `Статистике`.

### 2. Устная репетиция

Экран `Диалог` запускает ticket-grounded диалоговую сессию по выбранному билету и сохраняет историю сессий и итоговый результат.

### 3. Подготовка к защите

Экран `Подготовка к защите` даёт отдельный workflow для защиты: активация DLC, проект, импорт материалов, карта аргументов, вопросы комиссии и mock defense.

## Что важно заранее

- Никаких облачных LLM. Только локальный `Ollama`.
- Основной exam import path поддерживает `DOCX` и `PDF`.
- Для defense flow дополнительно поддерживаются `PPTX`, `TXT`, `MD`.
- Отдельного `import preview` перед стартом импорта пока нет.
- `dist/` считается generated output, а не местом ручного редактирования.
- macOS code-path подготовлен, но ручной runtime smoke на реальном Mac остаётся открытым QA-пунктом.

## Требования

Для запуска из исходников:

- `Python 3.12+`
- зависимости из `requirements.txt`

Для LLM-функций:

- локально установленный `Ollama`
- доступный endpoint `http://localhost:11434`
- локально загруженная `qwen3:8b` или совместимая локальная `Qwen`-модель

## Запуск

### Готовый Windows release

1. Скачать архив релиза из GitHub Releases.
2. Распаковать каталог релиза.
3. Запустить `Tezis.exe`.
4. Открыть `Настройки -> Ollama`.
5. Нажать `Проверить соединение`.

### Запуск из исходников

```powershell
python -m pip install -r requirements.txt
python main.py
```

Полезные варианты:

```powershell
python main.py --view library
python main.py --view training
python main.py --view dialogue
python main.py --view defense
python main.py --theme dark
```

## Ollama

Рекомендуемая конфигурация:

- API URL: `http://localhost:11434`
- preferred-модель: `qwen3:8b`

Подготовка на Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_ollama_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\check_ollama.ps1
```

Подготовка на macOS:

```bash
bash scripts/setup_ollama_macos.sh
bash scripts/check_ollama_macos.sh
```

## Документация

- [Быстрый старт](docs/quickstart.md)
- [Быстрый старт для госэкзамена](docs/quickstart_state_exam.md)
- [Руководство пользователя](docs/user_guide.md)
- [Архитектура](docs/architecture.md)
- [Спецификация продукта](docs/product_spec.md)
- [Roadmap](docs/roadmap.md)
- [Handoff для разработки](PICKUP.md)

## QA и визуальные артефакты

- Visual gate warm-minimal pass: `docs/superpowers/screenshots/2026-04-17-warm-minimal/`
- Click audit light: `audit/ui_click_audit.md`
- Click audit dark: `audit/ui_click_audit_dark.md`
- Manual test report: `audit/manual_test_report.md`

## Тесты

Базовый прогон:

```powershell
python -m pytest -q
```

Live Ollama integration:

```powershell
python -m pytest -q --run-live-ollama
```

UI click audit:

```powershell
python scripts/ui_click_audit.py --theme light --report audit/ui_click_audit.md
python scripts/ui_click_audit.py --theme dark --report audit/ui_click_audit_dark.md
```
