# Architecture

## Layers

- `app`
  composition root и запуск приложения
- `application`
  use cases: import, scoring, adaptive review, concept linking
- `domain`
  сущности и инварианты модели знаний
- `infrastructure`
  SQLite, файловые importers, локальный Ollama API
- `ui`
  PySide6 views и widgets

## End-to-End Function Chains

### Import Chain

`UI import action -> application.import_service -> infrastructure.importers -> domain ticket model -> infrastructure.db.repository -> UI refresh`

### Ollama Chain

`UI settings / training action -> infrastructure.ollama.service -> infrastructure.ollama.client -> local Ollama API -> parsed response -> application/domain usage -> UI diagnostics/result`

### Scoring Chain

`training attempt -> application.scoring -> domain mastery profile/weak areas -> infrastructure.db.repository -> statistics and repeat queue`

### Adaptive Review Chain

`attempt history + mastery profile + weak areas + ticket difficulty -> application.adaptive_review -> spaced_review_queue -> UI schedule`

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

## LLM Integration Rules

1. Ollama вызывается только локально.
2. `mistral:instruct` является дефолтной моделью.
3. LLM не должен придумывать новые факты.
4. Rule-based fallback обязателен.
5. Каждый LLM-assisted результат должен быть отличим от pure rule-based результата.
