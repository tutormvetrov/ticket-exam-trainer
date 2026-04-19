# Dispatch Prompts для Parallel Worktree Sessions

> Copy-paste prompts для трёх отдельных Claude Code сессий. Каждая сессия — отдельный workstream, работает в своём worktree, контролируется через superpowers:subagent-driven-development skill.

**Prerequisites (должно быть выполнено до запуска):**
- ✅ main закоммичен на v1.2.0 (tag существует)
- ✅ Три worktree созданы: `D:\ticket-exam-trainer-data`, `D:\ticket-exam-trainer-flet`, `D:\ticket-exam-trainer-installer`
- ✅ R0 validation завершён, default-модель выбрана в `docs/superpowers/specs/2026-04-18-model-selection.md`
- ✅ Spec и планы в git на main

**Как использовать:**
1. Откройте три окна Claude Code
2. В каждом — `cd` в соответствующий worktree-каталог
3. Скопируйте соответствующий prompt ниже в окно
4. Сессия прочитает свой plan и начнёт dispatch implementer subagent-ов

---

## W1: Data Pipeline — session 1

**Worktree:** `D:\ticket-exam-trainer-data`
**Ветка:** `data-pipeline` (от v1.2.0)
**Plan:** `docs/superpowers/plans/2026-04-18-w1-data-pipeline.md`

### Prompt:

```
Ты — контроллер workstream W1 (Data Pipeline Overhaul) для миграции приложения «Тезис» на Flet v2.0.

Рабочий каталог: D:\ticket-exam-trainer-data (ветка data-pipeline от тэга v1.2.0)

План исполнения: docs/superpowers/plans/2026-04-18-w1-data-pipeline.md
Спецификация (контекст): docs/superpowers/specs/2026-04-18-flet-migration-design.md (Часть 2)

Используй superpowers:subagent-driven-development skill для исполнения. Прочитай план один раз, извлеки все 9 задач с полным текстом, создай TodoWrite со всеми задачами, и диспетчи по одному implementer subagent на задачу. После каждого implementer — spec reviewer, потом code quality reviewer.

КРИТИЧНО — Frozen interface:
- application/facade.py (public API класса AppFacade)
- application/ui_data.py (формы dataclass-ов)
- domain/models.py — НО! Task 4 и Task 5 плана W1 намеренно расширяют SourceDocument и Section новыми опциональными полями. Это запланированный breaking change для W2/W3. После коммита этих задач необходимо:
  1. Сделать pause
  2. Написать в координирующую сессию (главный Claude Code) что frozen interface изменён
  3. Дождаться подтверждения sync в другие worktree перед продолжением
  Если координатор недоступен — пометь задачу DONE_WITH_CONCERNS и двигайся дальше

После всех 9 задач — финальный code-review всего workstream, затем workstream готов к merge в main (координатор делает merge).

Начинай с Task 1 (Byline Stripper).
```

---

## W2: Flet UI — session 2

**Worktree:** `D:\ticket-exam-trainer-flet`
**Ветка:** `flet-migration` (от v1.2.0)
**Plan:** `docs/superpowers/plans/2026-04-18-w2-flet-ui.md`

### Prompt:

```
Ты — контроллер workstream W2 (Flet UI Migration) для приложения «Тезис» v2.0.

Рабочий каталог: D:\ticket-exam-trainer-flet (ветка flet-migration от тэга v1.2.0)

План исполнения: docs/superpowers/plans/2026-04-18-w2-flet-ui.md
Спецификация (контекст): docs/superpowers/specs/2026-04-18-flet-migration-design.md (Часть 3)

Используй superpowers:subagent-driven-development skill. Прочитай план один раз, извлеки все 29 задач, создай TodoWrite, и диспетчи implementer subagent по одной. После каждого implementer — spec reviewer + code quality reviewer.

КРИТИЧНО:
- НЕ модифицируй ничего вне ui_flet/ и requirements.txt / pyproject.toml
- НЕ меняй application/, domain/, infrastructure/ — это frozen contract, приходящий от W1
- Ты потребляешь AppFacade через `from application.facade import AppFacade`, вся работа с данными только через его методы
- Если нужен метод facade, которого нет — НЕ добавляй его; эскалируй BLOCKED

Выбор default модели для Settings view — возьми из docs/superpowers/specs/2026-04-18-model-selection.md (R0 результат).

После Task 4 (Card component) и Task 5 (Sidebar) — визуально проверь storybook (`python -m ui_flet._dev.storybook`) перед движением дальше. Это catch точка для visual regressions.

После всех 29 задач — финальный code-review.

Начинай с Task 1 (Setup Flet dependency).
```

---

## W3: Installer & Packaging — session 3

**Worktree:** `D:\ticket-exam-trainer-installer`
**Ветка:** `installer` (от v1.2.0)
**Plan:** `docs/superpowers/plans/2026-04-18-w3-installer-packaging.md`

### Prompt:

```
Ты — контроллер workstream W3 (Installer & Packaging) для «Тезис» v2.0.

Рабочий каталог: D:\ticket-exam-trainer-installer (ветка installer от тэга v1.2.0)

План исполнения: docs/superpowers/plans/2026-04-18-w3-installer-packaging.md
Спецификация (контекст): docs/superpowers/specs/2026-04-18-flet-migration-design.md (Часть 5, 6)

Используй superpowers:subagent-driven-development skill. 7 задач, dispatch implementer subagent per task.

Фактический default-тир модели для wizard — из docs/superpowers/specs/2026-04-18-model-selection.md (R0 результат).

КРИТИЧНО:
- Task 3 (flet pack) и Task 5 (VM smoke) зависят от готовности ui_flet/main.py из W2. Если к моменту старта Task 3 W2 ещё не смержен в этот worktree — делай build scripts с placeholder ui_flet/main.py (минимальное "Hello" Flet-окно), чтобы подтвердить работоспособность самого flet pack. Реальный сontent появится после merge.
- Hardware detection (Task 1) и Ollama wizard (Task 2) — независимы от W1/W2, выполняются немедленно.

После всех 7 задач — финальный code-review. VM smoke-report (Task 5) — обязательный deliverable.

Начинай с Task 1 (Hardware Detection).
```

---

## Координация (главная сессия)

Пока три workstream работают параллельно, главная координирующая сессия держит:

### Daily reconcile

Раз в рабочий день (или при нотификации от workstream):

```powershell
# Проверить прогресс всех трёх
foreach ($dir in @("D:\ticket-exam-trainer-data", "D:\ticket-exam-trainer-flet", "D:\ticket-exam-trainer-installer")) {
    Write-Host "=== $dir ===" -ForegroundColor Cyan
    cd $dir
    git log --oneline -5
    python -m pytest -q --tb=no 2>&1 | Select-Object -Last 3
}
```

### Frozen interface sync

Когда W1 сообщает об изменении `domain/models.py` (Task 4 или Task 5):

```powershell
cd D:\ticket-exam-trainer-data
git log -1 --format=%H domain/models.py
# → получить commit SHA

cd D:\ticket-exam-trainer-flet
git cherry-pick <SHA>
python -m pytest tests/test_flet_*.py -q  # verify

cd D:\ticket-exam-trainer-installer
git cherry-pick <SHA>
```

### Final merge sequence

Когда все три workstream зелёные:

```powershell
cd D:\ticket-exam-trainer

# 1. W1 first (data changes feed into others)
git merge --no-ff data-pipeline -m "Merge W1 data-pipeline"
python -m pytest -q

# 2. W3 (scripts depend on seed from W1)
git merge --no-ff installer -m "Merge W3 installer"
python -m pytest -q

# 3. W2 last (UI consumes v2 seed through facade)
git merge --no-ff flet-migration -m "Merge W2 Flet UI"
python -m pytest -q

# 4. Tag v2.0.0
git tag -a v2.0.0 -m "Flet migration complete: state-exam focus, tiered Ollama installer"
git push origin main v2.0.0

# 5. Build final release
powershell -ExecutionPolicy Bypass -File scripts\build_flet_exe.ps1
powershell -ExecutionPolicy Bypass -File scripts\package_release.ps1

# 6. Smoke на VM + рассылка классмейтам
```
