# Тезис

Локальное desktop-приложение на `Python 3.12+` и `Flet` для подготовки к письменному госэкзамену ГМУ. В сборку уже включены 208 билетов, приложение работает офлайн, прогресс хранится только на компьютере пользователя. `Ollama` подключается опционально для более содержательной рецензии.

## Что реально есть в приложении

- Онбординг с локальным профилем без регистрации.
- Дневник как стартовый экран: утро, день, итог дня и очередь на сегодня.
- Каталог из 208 билетов с поиском, фильтрами по разделу и сложности, карточкой билета и очередью повторений на широком экране.
- 6 режимов тренировки: `reading`, `plan`, `cloze`, `active-recall`, `state-exam-full`, `review`.
- Интервальные повторения FSRS и калибровка уверенности перед проверкой свободного ответа.
- Настройки темы, режима окна, шрифта и локального `Ollama`.

## Чего в текущем продукте нет

Этот репозиторий приведён к текущему состоянию приложения. Здесь больше нет старого Qt shell, archived audit-документов и описаний несуществующих экранов вроде импорта документов, диалога, статистики, карты знаний или модуля защиты.

Исторические материалы сохранены локально в `archive/legacy/`. Они не считаются частью актуального продукта и оставлены только как архив.

## Releases

Готовые сборки для Windows и macOS лежат в [Releases](https://github.com/tutormvetrov/ticket-exam-trainer/releases).

## Запуск из исходников

```powershell
python -m pip install -r requirements.txt
python -m ui_flet.main
```

При первом запуске приложение создаёт рабочую папку в `%LOCALAPPDATA%\Tezis\app_data\` на Windows или `~/Library/Application Support/Tezis/app_data/` на macOS и копирует туда seed-базу билетов.

## Опциональный Ollama

Без `Ollama` приложение работает в упрощённом режиме рецензии по ключевым словам. С `Ollama` появляются более детальные verdict и рекомендации.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_ollama_wizard.ps1
```

macOS:

```bash
bash scripts/setup_ollama_macos.sh
```

## Сборка

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_flet_exe.ps1
```

macOS:

```bash
bash scripts/build_mac_app.sh python3 data/state_exam_public_admin_demo.db
```

## Тесты

```powershell
python -m pytest -q
```

## Документация

- [Быстрый старт](docs/quickstart.md)
- [Архитектура](docs/architecture.md)
- [Инструкция для однокурсников](README_classmates.md)
- [Архив legacy-материалов](archive/README.md)
