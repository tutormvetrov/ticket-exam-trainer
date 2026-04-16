# Тренажёр билетов к вузовским экзаменам

Локальное desktop-приложение на `Python 3.12+` и `PySide6` для подготовки к обычным экзаменам и госэкзамену. Проект не использует облачные LLM. LLM-функции работают только через локальный `Ollama`; preferred default-моделью теперь является `qwen3:8b`, но диагностический smoke допускает совместимую локальную `Qwen`-модель из того же семейства.

Репозиторий содержит исходники, сборочные скрипты, пользовательскую документацию, тесты и audit-артефакты. Основной подтверждённый пользовательский путь сейчас относится к Windows desktop release.

## Что реально реализовано

- основной Windows workflow `настройка Ollama -> импорт -> библиотека -> тренировка -> статистика`
- импорт учебных материалов из `DOCX` и `PDF` в основном продукте
- асинхронный импорт с progress bar, понятными warning и возможностью локально добить частичный хвост
- структурирование текста в билеты, атомы знаний, навыки, шаблоны упражнений и adaptive queue
- 7 реальных training modes в UI:
  - `reading`
  - `active-recall`
  - `cloze`
  - `matching`
  - `plan`
  - `mini-exam`
  - `state-exam-full`
- профиль ответа `Госэкзамен` с 6 answer blocks, criterion scores и отдельной статистикой
- локальная диагностика `Ollama`, автонастройка, backup SQLite и update-check
- DLC `Защита DLC` как сильный локальный модуль: paywall, локальная активация по ключу, проекты, импорт материалов, dossier, outline, storyboard, logical gaps, role-aware вопросы комиссии, таймерная репетиция и mock defense
- Windows-сборка `Tezis.exe`

## Что не стоит обещать без оговорки

- macOS-путь подготовлен по коду, скриптам и документации, но финальный runtime smoke на реальном Mac остаётся отдельным QA-пунктом
- DLC уже является сильным локальным модулем подготовки, но это не полноценный billing-продукт
- отдельного `import preview` перед запуском импорта сейчас нет
- не все внутренние `exercise types` выведены в UI как отдельные пользовательские режимы
- root `README.md`, `docs`, `scripts`, код и тесты являются source-of-truth; содержимое `dist/Tezis/*` считается generated output сборки, а не местом ручного редактирования

## Основной пользовательский сценарий

1. Запустить готовый `Tezis.exe` или `python main.py`.
2. Открыть `Настройки -> Ollama`.
3. Проверить локальный `Ollama`.
4. Импортировать один большой `DOCX` или `PDF`.
5. Проверить результат в `Библиотеке`.
6. Перейти в `Тренировку`.
7. Смотреть динамику в `Статистике`.

## Требования

Для запуска из исходников:
- `Python 3.12+`
- зависимости из `requirements.txt`

Для LLM-функций:
- локально установленный `Ollama`
- доступный endpoint `http://localhost:11434`
- локально загруженная `qwen3:8b` или совместимая локальная `Qwen`-модель для diagnostic smoke

## Документация

- [Быстрый старт](docs/quickstart.md)
- [Быстрый старт: госэкзамен](docs/quickstart_state_exam.md)
- [Подробное руководство пользователя](docs/user_guide.md)
- [Архитектура](docs/architecture.md)
- [Спецификация продукта](docs/product_spec.md)
- [Roadmap](docs/roadmap.md)

## Запуск

### Вариант 1. Готовый Windows release

1. Скачать архив релиза из GitHub Releases.
2. Распаковать папку релиза.
3. Запустить `Tezis.exe`.
4. Открыть `Настройки -> Ollama`.
5. Нажать `Проверить соединение`.

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
python main.py --view defense
```

## Ollama и Qwen

Целевая конфигурация по умолчанию:
- API URL: `http://localhost:11434`
- preferred-модель: `qwen3:8b`
- models path выбирается так:
  - `OLLAMA_MODELS`, если переменная уже задана
  - `D:\OllamaModels` на Windows, если диск `D:` существует
  - `~/.ollama/models` на Windows без диска `D:`
  - `~/.ollama` на macOS

### Автонастройка из интерфейса

1. Откройте `Настройки -> Ollama`.
2. Нажмите `Автонастройка Ollama`.
3. После завершения снова нажмите `Проверить соединение`.

### Скрипты Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_ollama_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\check_ollama.ps1
```

### Как понять, что интеграция живая

Опираться нужно на совокупность признаков:
- в `Настройках -> Ollama` endpoint отвечает
- найдена `qwen3:8b` или совместимая локальная `Qwen`-модель
- показано время отклика
- `scripts/check_ollama.ps1` проходит без ошибки
- LLM-assisted действия в UI явно помечаются

## Импорт документов

Основной сценарий релиза:
- один большой `DOCX` со сборником билетов

Также поддерживается:
- `PDF`

Что делает импорт:
- извлекает и нормализует текст
- ищет разделы и кандидаты в билеты
- строит карту знаний
- создаёт шаблоны упражнений
- сохраняет результат в `SQLite`
- показывает progress по этапам и summary после завершения

Что важно оговаривать заранее:
- отдельного `import preview` перед стартом импорта сейчас нет
- приложение показывает warning, если структура документа распознана слабо
- частично неудачный импорт не маскируется под полный success

### DLC import path

В `Защита DLC` поддерживаются дополнительные типы материалов:
- `DOCX`
- `PDF`
- `PPTX`
- `TXT`
- `MD`

Этот расширенный import относится к defense-ветке, а не к обычному exam-import в основном продукте.

## Тренировка и статистика

В текущем UI доступны 7 отдельных режимов:
- `reading`
- `active-recall`
- `cloze`
- `matching`
- `plan`
- `mini-exam`
- `state-exam-full`

Что происходит после проверки ответа:
- обновляется score
- сохраняются weak areas
- пересчитывается adaptive queue
- обновляется статистика по микронавыкам
- для билетов `Госэкзамен` сохраняются block scores и criterion scores

Что важно понимать:
- в движке есть более широкая внутренняя taxonomy упражнений, чем в UI
- `odd thesis`, `examiner follow-up`, `weak area repeat`, `cross-ticket repeat`, `oral short` существуют как backend exercise types, но не все выведены как отдельные пользовательские workspace

## DLC `Тезис`

В приложении уже есть отдельный paywalled workspace:
- `Защита DLC`

Что в нём сейчас реально доступно:
- локальная активация по ключу
- создание проекта защиты
- импорт материалов защиты
- построение `defense dossier`
- outline доклада на 5, 7 и 10 минут
- storyboard слайдов
- logical gaps с evidence-aware разбором
- role-aware вопросы комиссии: `Научрук`, `Оппонент`, `Комиссия`
- таймерная репетиция и mock defense с очередью доработок

Что важно оговаривать заранее:
- оплата в приложении не встроена; используется manual activation code
- DLC закрыт paywall и без активации недоступен
- это strong paid local module with manual activation, а не завершённый billing-продукт
- editor/export-heavy слой и внешний license server в этот цикл не входят

## Тесты

Базовый запуск:

```powershell
python -m pip install -r requirements.txt
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

Если зависимости из `requirements.txt` установлены, но `PySide6` недоступен, UI-тесты будут пропущены, а не сломают весь запуск при collection.

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

Важно:
- из Windows-среды нельзя полноценно подтвердить ручной runtime smoke на реальном Mac
- поэтому macOS-путь подготовлен на уровне кода и инструкций, но финальная проверка должна выполняться на macOS отдельно

Базовый путь на macOS:

```bash
python3 main.py
bash scripts/setup_ollama_macos.sh
bash scripts/check_ollama_macos.sh
bash scripts/build_mac_app.sh
```

Если macOS блокирует unsigned build:

```bash
xattr -dr com.apple.quarantine dist/Tezis.app
```

## GitHub Releases

Для публикации лучше держать отдельные артефакты:
- Windows: zip с папкой релиза или готовым `Tezis.exe`
- macOS: zip с `Tezis.app`, собранным и проверенным на реальном Mac

При этом важно соблюдать repo hygiene:
- редактировать только корневые исходники и документацию
- считать `build` временным артефактом
- считать `dist` финальным output, который каждый раз пересобирается из актуального корня
- packaged build теперь содержит `build_info.json`, а UI показывает текущую версию и commit
- релиз по умолчанию не должен включать живую `exam_trainer.db` из workspace или машины сборщика
- если для внутреннего smoke нужен seed, его можно подложить только явно: `powershell -File scripts\build_exe.ps1 -SeedDatabasePath C:\path\to\seed.db`

Быстрый smoke для готового Windows release:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\release_smoke.ps1
```

В release notes стоит отдельно писать:
- что Windows-сборка приложена
- что macOS-сценарий требует проверки на реальном Mac
- что DLC уже доступен как сильный локальный модуль с manual activation, но не как завершённый billing-продукт
