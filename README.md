# Тренажёр билетов к вузовским экзаменам

Локальное desktop-приложение на `Python 3.12+` и `PySide6` для подготовки к экзаменам и госэкзамену без облачных LLM.

Главный сценарий релиза:
- запустить `exe` или `python main.py`
- проверить локальный `Ollama + mistral:instruct`
- импортировать один большой `DOCX` или `PDF`
- сразу перейти к тренировке и статистике

## Что уже умеет приложение

- импорт `DOCX` и `PDF`
- разбор текста в билеты и карту знаний
- генерация упражнений по билетам
- adaptive repeat и слабые места
- локальная интеграция `mistral:instruct` через Ollama
- честная диагностика endpoint и модели
- рабочие разделы настроек для запуска, импорта, тренировки, данных и сервисных действий
- создание резервной копии SQLite из экрана `Настройки -> Данные`
- responsive desktop UI под `1280x720`, `1366x768`, `1536x864`
- сборка `exe`

## Быстрый старт

Подробные инструкции:
- [Быстрый старт](/Users/tutor/OneDrive/Документы/Exam_revision/docs/quickstart.md)
- [Подробное руководство со скриншотами](/Users/tutor/OneDrive/Документы/Exam_revision/docs/user_guide.md)

### Вариант 1. Готовый exe

1. Откройте `dist\TicketExamTrainer\TicketExamTrainer.exe`
2. Перейдите в `Настройки -> Ollama`
3. Нажмите `Проверить соединение`
4. Если Ollama ещё не готов, нажмите `Автонастройка Ollama` или используйте скрипты ниже
5. Перейдите в `Импорт документов` и загрузите большой `DOCX` или `PDF`
6. Откройте `Библиотеку` или `Тренировку`

### Вариант 2. Запуск из исходников

```powershell
python main.py
```

Можно сразу открыть конкретный экран:

```powershell
python main.py --view settings
python main.py --view import
python main.py --view training
```

## Ollama и Mistral

Целевая конфигурация:
- API URL: `http://localhost:11434`
- модель: `mistral:instruct`
- папка моделей: `D:\OllamaModels`

### Автонастройка

Из интерфейса:
- откройте `Настройки -> Ollama`
- нажмите `Автонастройка Ollama`
- после завершения вернитесь в приложение и нажмите `Проверить соединение`

Из PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_ollama_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\check_ollama.ps1
```

### Как понять, что всё реально подключено

Признаки живой интеграции:
- в `Настройках -> Ollama` статус показывает `Подключено`
- `Endpoint` в диагностике отвечает
- модель `mistral:instruct` найдена
- видно время отклика
- после импорта в summary может появляться `LLM assist: да`
- follow-up вопросы в тренировке приходят не как заглушка

### Ручная проверка

```powershell
$env:Path += ';C:\Users\tutor\AppData\Local\Programs\Ollama'
ollama --version
ollama list
Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/tags
```

## Импорт документов

Основной сценарий релиза:
- один большой `DOCX` со сборником билетов

Поддерживается также:
- `PDF`

После импорта приложение:
- извлекает текст
- нормализует его
- выделяет кандидатов в билеты
- строит атомы знаний и навыки
- генерирует упражнения
- сохраняет всё в `SQLite`

Если структура распознана слабо:
- приложение показывает warning
- включает fallback
- не делает вид, что распознало всё идеально

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

## Документация со скриншотами

Скриншоты лежат в:
- [docs/screenshots](/Users/tutor/OneDrive/Документы/Exam_revision/docs/screenshots)

Основное руководство:
- [docs/user_guide.md](/Users/tutor/OneDrive/Документы/Exam_revision/docs/user_guide.md)

## Структура проекта

- `app` запуск приложения и пути
- `application` facade, import, scoring, adaptive logic
- `domain` модель билетов и знаний
- `infrastructure/db` SQLite
- `infrastructure/importers` импорт DOCX/PDF
- `infrastructure/ollama` локальный клиент и сервисы Ollama
- `ui` views и components
- `docs` инструкции и скриншоты
- `scripts` setup/build/check
- `audit` артефакты ручного и визуального аудита
- `tests` smoke и integration tests

## Сборка exe

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

Готовая папка релиза:

```text
dist\TicketExamTrainer\
```

Внутри должны лежать:
- `TicketExamTrainer.exe`
- `README.md`
- `docs\`
- `scripts\`
- `app_data\`

## Тесты

Полный прогон:

```powershell
pytest -q
```

## DLC teaser

В UI уже есть честный teaser будущего модуля:
- `DLC: Подготовка к защите магистерской`

Он пока не реализован как рабочий сценарий.
Сейчас это только аккуратный анонс будущего расширения.

## Внутренний стандарт аудита

Проект использует обязательный стандарт из [skills.md](/Users/tutor/OneDrive/Документы/Exam_revision/skills.md).

Это означает:
- нельзя верить статусам без проверки
- нельзя считать экран готовым без живого визуального аудита
- нельзя выдавать заглушки за реальную функцию
- после заметных UI-изменений обновляются `audit/*`

## macOS

Поддержка macOS теперь доведена до комфортного кроссплатформенного уровня:
- дефолтный путь моделей выбирается под платформу
- экран `Настройки -> Ollama` запускает macOS-скрипты вместо Windows-only PowerShell
- внутренние кнопки окна не дублируют macOS window controls
- добавлен отдельный скрипт сборки `.app`

Что важно понимать честно:
- из этой Windows-среды я не могу физически прогнать живой запуск на реальном Mac
- поэтому поддержка адаптирована по коду, скриптам и инструкции, но не заявляется как вручную проверенная на macOS машинах

Базовый запуск на macOS:

```bash
python3 main.py
```

Скрипты под macOS:

```bash
bash scripts/setup_ollama_macos.sh
bash scripts/check_ollama_macos.sh
```

Сборка `.app`:

```bash
bash scripts/build_mac_app.sh
```

Если macOS блокирует запуск unsigned build, используйте стандартный путь:
- `Open` из контекстного меню Finder
- или снимите quarantine-атрибут вручную:

```bash
xattr -dr com.apple.quarantine dist/TicketExamTrainer.app
```

По официальной документации Ollama на macOS файлы и модели хранятся в `~/.ollama`.
Источник: [Ollama macOS docs](https://docs.ollama.com/macos)

## GitHub Releases

Для GitHub Releases теперь разумно держать два артефакта:
- Windows: `TicketExamTrainer.exe` или zip с папкой `dist/TicketExamTrainer`
- macOS: zip с `TicketExamTrainer.app` после сборки на реальном Mac

В release notes стоит отдельно писать:
- что Windows-сборка приложена готовой
- что macOS-сборку лучше собирать или перепроверять на Mac перед публикацией
- как запускать локальный Ollama и где лежат модели на каждой платформе
