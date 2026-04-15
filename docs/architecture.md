# Architecture

## Layers

- `app`
  composition root, запуск приложения и platform-aware entrypoint
- `application`
  use cases: import, scoring, adaptive review, concept linking, settings, defense flow
- `domain`
  сущности и инварианты модели знаний и defense-модуля
- `infrastructure`
  SQLite, файловые importers, локальный Ollama API, runtime bridge
- `ui`
  PySide6 views, widgets и mode-specific workspace

## End-to-End Chains

### Exam Import Chain

`UI import action -> application.import_service / application.facade -> infrastructure.importers -> domain ticket model -> infrastructure.db.repository -> UI refresh`

Что важно сейчас:

- основной import path относится к `DOCX` и `PDF`
- import идёт в фоне и обновляет progress по этапам
- частичный результат может быть сохранён и потом локально добит через resume flow
- отдельного `import preview` перед стартом импорта пока нет

### Training Chain

`UI training workspace -> application.facade.evaluate_answer -> application.scoring -> domain mastery / weak areas -> infrastructure.db.repository -> adaptive queue + statistics -> UI refresh`

Что важно сейчас:

- training UI разделён на 7 реальных workspace
- внутренняя taxonomy упражнений шире, чем текущий UI mode set
- `Госэкзамен` использует отдельный answer profile и block-level scoring

### Adaptive Review Chain

`attempt history + mastery profile + weak areas + ticket difficulty -> application.adaptive_review -> spaced_review_queue -> UI schedule`

### Ollama Chain

`UI settings / import / training / defense action -> infrastructure.ollama.service -> infrastructure.ollama.client -> local Ollama API -> parsed response -> application/domain usage -> UI diagnostics or result`

Что важно сейчас:

- Ollama вызывается только локально
- `qwen3:8b` теперь является preferred default
- при diagnostic smoke допускается fallback на совместимую локальную `Qwen`-модель того же семейства
- rule-based fallback обязателен там, где LLM недоступен или вернул пустой результат

### DLC Defense Chain

`UI defense workspace -> application.defense_service -> defense importers / Ollama / SQLite -> dossier + outlines + slides + questions + mock evaluation -> UI refresh`

Сейчас defense-flow уже покрывает:

- paywall и локальную активацию
- проекты защиты
- импорт `DOCX/PDF/PPTX/TXT/MD`
- dossier
- outline
- storyboard
- вопросы комиссии
- mock defense

## Persistence

SQLite хранит:

- import results
- structured tickets
- atoms
- skills
- exercise templates
- attempts
- weak areas
- mastery profiles
- adaptive review queue
- cross-ticket concepts
- answer blocks и block mastery для `Госэкзамен`
- defense projects, sources, claims, outlines, slides, questions, scores

## Current Product Boundaries

1. Основной подтверждённый release path сейчас относится к Windows desktop.
2. macOS code-path подготовлен, но runtime smoke на реальном Mac остаётся внешним QA-пунктом.
3. DLC уже является рабочей вертикалью, но не полностью завершённым коммерческим модулем.
4. Root `README.md`, `docs`, `scripts`, код и тесты являются source-of-truth; packaged-копии в `dist` считаются generated output.
5. Документация должна различать:
   - что доступно пользователю как отдельный UI workflow
   - что существует только как внутренняя доменная или exercise taxonomy
