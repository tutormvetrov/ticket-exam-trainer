# Архитектура

Репозиторий отражает только актуальную Flet-версию приложения.

## Слои

- `domain/`
  Чистые модели предметной области.
- `application/`
  Сервисы приложения, scoring, FSRS, профиль пользователя, дневная сводка.
- `infrastructure/`
  SQLite, локальный Ollama HTTP-клиент и прикладные адаптеры.
- `ui_flet/`
  Все пользовательские экраны, роутинг, state holder, компоненты и темы.
- `app/`
  Общие runtime-утилиты: пути, build info, release seed, логирование.

## Точки входа

- `main.py`
  Тонкая обёртка, которая запускает Flet entrypoint.
- `ui_flet/main.py`
  Главная точка запуска приложения.

`ui_flet/main.py` делает четыре вещи:

1. Готовит рабочую папку и seed-базу билетов.
2. Собирает `AppFacade`.
3. Создаёт `AppState`.
4. Подключает router и Flet page chrome.

## Маршруты

Публичные пользовательские маршруты:

- `/onboarding`
- `/journal`
- `/tickets`
- `/training/<ticket_id>/<mode>`
- `/settings`

Корневой путь перенаправляется в `/onboarding`, если профиля ещё нет, иначе в `/journal`.

## Тренировочные режимы

В `ui_flet/workspaces/` есть ровно шесть рабочих режимов:

- `reading`
- `plan`
- `cloze`
- `active-recall`
- `state-exam-full`
- `review`

Именно их нужно считать актуальным продуктовым набором.

## Хранение данных

Локально сохраняются:

- `exam_trainer.db`
- `settings.json`
- `profile.json`
- runtime logs

Рабочая папка создаётся в `%LOCALAPPDATA%\Tezis\app_data\` на Windows и в `~/Library/Application Support/Tezis/app_data/` на macOS.

## Сборка и релизы

- `scripts/build_flet_exe.ps1`
  Локальная Windows-сборка через `flet pack`.
- `scripts/build_mac_app.sh`
  Локальная macOS-сборка через `flet pack`.
- `.github/workflows/release.yml`
  Релизный workflow по тегам `v*`.

## Тестовый контур

Основной smoke-контур:

```powershell
python -m pytest -q
```

Live Ollama тесты запускаются только с флагом `--run-live-ollama`.
