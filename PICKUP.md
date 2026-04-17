# Как продолжить разработку на другой машине

Короткий handoff по текущему состоянию `main`.

## 1. Быстрый старт

```powershell
git clone https://github.com/tutormvetrov/ticket-exam-trainer.git
cd ticket-exam-trainer
python -m pip install -r requirements.txt
python -m pytest -q
python main.py
```

Ориентир по тестам на 2026-04-17:

- `186 passed, 5 skipped`

## 2. Что сейчас важно знать

- Основная ветка: `main`
- Warm-minimal visual refresh этапа 1 уже влит.
- `TopBar`, `Sidebar`, `Library`, `Tickets`, `Training` и `LogoMark` уже на новом дизайне.
- В `Тренировке` уже 8 режимов, включая `review`.
- Click audit обновлён для light и dark.

## 3. Полезные команды

```powershell
python main.py --view library
python main.py --view training --theme dark
python main.py --view dialogue
python scripts/ui_click_audit.py --theme light --report audit/ui_click_audit.md
python scripts/ui_click_audit.py --theme dark --report audit/ui_click_audit_dark.md
```

Если нужен локальный Ollama:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_ollama_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\check_ollama.ps1
```

## 4. Где смотреть актуальные документы

- корневой обзор: `README.md`
- пользовательские документы: `docs/`
- активный визуальный spec: `docs/superpowers/specs/2026-04-17-warm-minimal-visual-refresh-design.md`
- активный visual plan: `docs/superpowers/plans/2026-04-17-warm-minimal-visual-refresh.md`
- visual gate screenshots: `docs/superpowers/screenshots/2026-04-17-warm-minimal/`
- audit: `audit/`

## 5. Текущий остаток

- главный открытый продуктовый QA-хвост: реальный macOS smoke-run;
- `import preview` ещё не реализован;
- вторичные экраны не проходили персональный warm-minimal redesign, только theme inheritance.

## 6. Repo truth

- редактируемые исходники: корень репозитория, `docs`, `audit`, `scripts`, код, тесты;
- `build` это временные build-артефакты;
- `dist` это generated output;
- packaged docs внутри релиза не редактируются вручную.
