# Как продолжить разработку на другой машине (Windows 11)

Короткая шпаргалка, чтобы взять проект с нуля.

## 1. Клонировать и настроить окружение

```powershell
git clone https://github.com/tutormvetrov/ticket-exam-trainer.git
cd ticket-exam-trainer

# Python 3.12+ обязателен
python --version

python -m pip install -r requirements.txt
```

Из зависимостей ключевые: `PySide6`, `cryptography` (для DLC-подписи), `pytest`,
`pyinstaller`, `python-docx`, `pypdf`, `reportlab`, `requests`.

## 2. Проверить, что всё собирается

```powershell
python -m pytest -q
```

Ожидание: **165 passed, 5 skipped** на `main`. На `feature/logo-refresh` —
то же число.

## 3. Запустить приложение

```powershell
python main.py
# или сразу на конкретный экран
python main.py --view library --theme light
python main.py --view library --theme dark
```

LLM-функции (диалоги, рецензии, структурирование) работают только при
живом локальном `Ollama` на `http://localhost:11434` с загруженной
моделью `qwen3:8b` или совместимой. Без Ollama UI запустится, но LLM-
режимы будут недоступны.

Чтобы поднять Ollama локально:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_ollama_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\check_ollama.ps1
```

## 4. Ветки и состояние

| Ветка | Что в ней |
|-------|-----------|
| `main` | Базовое приложение + три очереди хардинга (security / reliability / visual) + спек и план логотипа. Тесты: 165 passed. |
| `feature/logo-refresh` | Рефреш логотипа (академический медальон, SVG-шаблоны, адаптивные варианты) + русификация оставшихся английских строк UI. Не смёржен, ждёт визуального одобрения. |

Переключиться на работу с логотипом:
```powershell
git fetch origin
git checkout feature/logo-refresh
git pull
```

После визуального одобрения смёржить в main:
```powershell
git checkout main
git merge --no-ff feature/logo-refresh
git push origin main
```

## 5. Что ещё в работе / план на будущее

- **Премиальный визуальный пасс** — типографика (Inter/Manrope), воздух,
  слои поверхностей, тонкие hairline-границы, микро-анимации на hover,
  изумрудно-золотые акценты вместо плоского синего. План согласован,
  будет в отдельной ветке `feature/premium-visual-pass`. Объём — как все
  три очереди хардинга вместе.
- **DLC Ed25519 rotation** — до релиза надо сгенерировать свою пару ключей
  через `python local_tools/dlc_issuer.py generate --out <path>` и
  подставить публичный ключ в `application/dlc_license.py` →
  `DEFAULT_DLC_PUBLIC_KEY_PEM`. Приватный — **только вне репо**.
- **macOS smoke** (пункт `MAC-REAL` в `audit/open_issues.md`) — не прогонялся
  руками на реальном Mac, по-прежнему open.

## 6. Документация

- Спеки и планы: `docs/superpowers/specs/`, `docs/superpowers/plans/`
- Последний спек: `2026-04-16-logo-refresh-design.md`
- Последний план: `2026-04-16-logo-refresh.md`
- Audit с честным списком известных проблем: `audit/open_issues.md`

## 7. Worktrees

В этом проекте используются git worktrees через `.worktrees/<branch>`
(игнорируется). Если хочешь работать над двумя ветками параллельно:

```powershell
git worktree add .worktrees/premium-visual -b feature/premium-visual-pass
cd .worktrees/premium-visual
```

Список активных worktree: `git worktree list`.
