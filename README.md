# Тренажёр билетов к вузовским экзаменам

Локальное desktop-приложение на `Python 3.12+` и `PySide6` для подготовки к экзаменам и госэкзамену. Проект не использует облачные LLM. LLM-функции работают только через локальный `Ollama` и модель `mistral:instruct`.

Репозиторий содержит исходники, скрипты сборки, пользовательскую документацию и audit-артефакты. Готовый `exe` нужно брать из GitHub Releases или собирать локально.

## Что реально подтверждено

- импорт `DOCX` и `PDF`
- разбор текста в билеты и внутреннюю карту знаний
- генерация упражнений и повторной очереди
- локальная диагностика `Ollama` и `mistral:instruct`
- хранение данных в `SQLite`
- desktop UI на `PySide6`
- Windows-сборка `exe`

Что не стоит обещать без оговорки:
- запуск из исходников требует установленного `PySide6`
- LLM-сценарии требуют локального `Ollama`
- macOS-код и скрипты подготовлены, но ручной smoke-run на реальном Mac должен быть проверен отдельно

## Основной пользовательский сценарий

1. Запустить готовый `exe` или `python main.py`
2. Открыть `Настройки -> Ollama`
3. Проверить локальный `Ollama + mistral:instruct`
4. Импортировать один большой `DOCX` или `PDF`
5. Перейти в библиотеку, тренировку и статистику

## Требования

Для запуска из исходников:
- `Python 3.12+`
- `pip install -r requirements.txt` поставит `PySide6`, `requests`, `python-docx`, `pypdf`

Для разработки и сборки:
- `pip install -r requirements-dev.txt` добавляет `pytest` и `pyinstaller`

Для LLM-функций:
- локально установленный `Ollama`
- доступный endpoint `http://localhost:11434`
- локально загруженная модель `mistral:instruct`

## Документация

- [Быстрый старт](docs/quickstart.md)
- [Подробное руководство пользователя](docs/user_guide.md)
- [Архитектура](docs/architecture.md)
- [Спецификация продукта](docs/product_spec.md)
- [Roadmap](docs/roadmap.md)

## Запуск

### Вариант 1. Готовый release

1. Скачайте архив релиза с GitHub Releases.
2. Распакуйте папку релиза.
3. Запустите `Tezis.exe`.
4. Перейдите в `Настройки -> Ollama`.
5. Нажмите `Проверить соединение`.

### Вариант 2. Запуск из исходников

```powershell
python -m pip install -r requirements.txt
python main.py
```

Можно сразу открыть конкретный экран:

```powershell
python main.py --view settings
python main.py --view import
python main.py --view training
```

## Ollama и Mistral

Целевая конфигурация по умолчанию:
- API URL: `http://localhost:11434`
- модель: `mistral:instruct`
- models path выбирается так:
  - `OLLAMA_MODELS`, если переменная уже задана
  - `D:\OllamaModels` на Windows, если диск `D:` существует
  - `~/.ollama/models` на Windows без диска `D:`
  - `~/.ollama` на macOS

### Автонастройка из интерфейса

1. Откройте `Настройки -> Ollama`
2. Нажмите `Автонастройка Ollama`
3. После завершения снова нажмите `Проверить соединение`

### Скрипты Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_ollama_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\check_ollama.ps1
```

### Ручная проверка

```powershell
ollama --version
ollama list
Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/tags
```

Если `ollama` не найден в `PATH`, сначала откройте новую консоль после установки Ollama или укажите полный путь до бинарника вручную. Приложение и `check_ollama.ps1` дополнительно пытаются использовать уже заполненный каталог моделей, даже если в настройках указан другой путь.

### Как честно понять, что интеграция живая

Опираться нужно не на один зелёный индикатор, а на совокупность признаков:
- в `Настройках -> Ollama` endpoint отвечает
- модель `mistral:instruct` найдена
- показано время отклика
- `scripts/check_ollama.ps1` проходит без ошибки
- LLM-assisted действия в UI явно помечаются

## Импорт документов

Основной сценарий:
- один большой `DOCX` со сборником билетов

Поддерживается также:
- `PDF`

После импорта приложение:
- извлекает текст
- нормализует его
- выделяет кандидатов в билеты
- строит карту знаний
- генерирует упражнения
- сохраняет результат в `SQLite`

Если структура распознана слабо:
- приложение показывает warning
- включает fallback
- не маскирует слабое распознавание под идеальный результат

## Тренировка и статистика

В текущем релизе доступны:
- чтение билета
- active recall
- cloze deletion
- сопоставление
- сбор плана ответа
- мини-экзамен

После проверки ответа обновляются:
- score
- слабые места
- adaptive queue
- статистика по микронавыкам

## Скриншоты

- [Каталог скриншотов](docs/screenshots)
- [Подробное руководство](docs/user_guide.md)

## Структура проекта

- `app` запуск приложения и platform-aware пути
- `application` use cases и фасад
- `domain` модель билетов и знаний
- `infrastructure/db` SQLite
- `infrastructure/importers` импорт DOCX/PDF
- `infrastructure/ollama` локальный клиент и сервисы Ollama
- `ui` views и components
- `docs` пользовательские и технические документы
- `scripts` setup, build и проверочные скрипты
- `audit` артефакты ручного и визуального аудита
- `tests` unit, UI и integration tests

## Сборка Windows exe

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

Ожидаемый результат:

```text
dist\Tezis\
```

## Тесты

Базовый запуск:

```powershell
pytest -q
```

Что входит в базовый прогон:
- pure logic и database smoke tests
- runtime tests для bridge вокруг путей Ollama
- UI tests, если в среде доступен `PySide6`

Что не входит в базовый прогон:
- live integration tests с реальным локальным `Ollama`

Запуск live integration tests:

```powershell
pytest -q --run-live-ollama
```

Если `PySide6` не установлен, UI-тесты будут пропущены честно, а не сломают весь запуск при collection.

## DLC `Тезис`

В приложении уже есть отдельный paywalled workspace:
- `Защита DLC`

Что в нём сейчас реально доступно:
- локальная активация по ключу
- создание проекта защиты
- импорт материалов защиты
- построение `defense dossier`
- outline доклада, storyboard слайдов и вопросы комиссии
- mock-защита с оценкой слабых мест

Что важно оговаривать честно:
- DLC закрыт paywall и без активации недоступен
- сценарий рассчитан на локальный `Ollama`
- это первая рабочая версия DLC, а не полностью завершённый коммерческий модуль

## Внутренний стандарт аудита

Проект использует обязательный стандарт из [skills.md](skills.md).

Это означает:
- нельзя верить статусам без проверки
- нельзя считать экран готовым без живого визуального аудита
- нельзя выдавать заглушки за готовую функцию
- после заметных UI-изменений обновляются `audit/*`

## macOS

В репозитории есть platform-aware код и отдельные macOS-скрипты:
- `scripts/setup_ollama_macos.sh`
- `scripts/check_ollama_macos.sh`
- `scripts/build_mac_app.sh`

Честная оговорка:
- из Windows-среды нельзя полноценно подтвердить ручной runtime smoke на реальном Mac
- поэтому macOS-путь подготовлен на уровне кода и инструкций, но финальная проверка должна выполняться на macOS отдельно

Базовый запуск на macOS:

```bash
python3 main.py
```

Подготовка Ollama:

```bash
bash scripts/setup_ollama_macos.sh
bash scripts/check_ollama_macos.sh
```

Сборка `.app`:

```bash
bash scripts/build_mac_app.sh
```

Если macOS блокирует unsigned build:

```bash
xattr -dr com.apple.quarantine dist/Tezis.app
```

По официальной документации Ollama на macOS модели и данные хранятся в `~/.ollama`.
Источник: [Ollama macOS docs](https://docs.ollama.com/macos)

## GitHub Releases

Для публикации лучше держать отдельные артефакты:
- Windows: zip с папкой релиза или готовым `Tezis.exe`
- macOS: zip с `Tezis.app`, собранным и проверенным на реальном Mac

В release notes стоит отдельно писать:
- что Windows-сборка приложена
- что macOS-сценарий требует проверки на реальном Mac
- как поднять локальный `Ollama`
