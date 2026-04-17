# Architecture

## Слои

- `app`: bootstrap, пути, build info, platform-aware entrypoints.
- `application`: use cases, import, scoring, adaptive review, dialogue, defense flow, settings.
- `domain`: сущности билетов, карты знаний, mastery, answer profiles, defense-модель.
- `infrastructure`: SQLite, importers, local Ollama API, repository, update bridge.
- `ui`: PySide6 shell, views, widgets, theme package и runtime wiring.

## UI shell

Текущий shell состоит из:

- `ui/components/sidebar.py`
- `ui/components/topbar.py`
- `ui/main_window.py`

`MainWindow` держит `Sidebar`, `TopBar` и `QStackedWidget` с основными экранами. Навигационные ключи совпадают с view ids:

- `library`
- `subjects`
- `sections`
- `tickets`
- `import`
- `training`
- `dialogue`
- `statistics`
- `knowledge-map`
- `defense`
- `settings`

## Theme system

Тема уже разделена на пакет `ui/theme/`:

- `palette.py`
- `typography.py`
- `spacing.py`
- `materiality.py`
- `stylesheet.py`

Пакет сохраняет backward compatibility через `ui/theme/__init__.py`. Сейчас в продукте используется warm-minimal palette:

- light: sand / parchment / rust / moss
- dark: cognac / brass / warm ink

## Основные цепочки

### Exam import

`ImportView -> MainWindow.open_import_dialog -> AppFacade.import_document_with_progress -> import_service -> repository -> refresh views`

Сейчас подтверждены:

- `DOCX` и `PDF`;
- stage-based progress;
- summary и handoff;
- сохранение результатов в SQLite.

### Training

`TrainingView -> AppFacade.evaluate_answer -> scoring -> mastery/weak areas -> repository -> adaptive queue/statistics -> UI refresh`

Сейчас в UI доступны 8 отдельных режимов, включая `state-exam-full` и `review`.

### Dialogue

`DialogueView -> AppFacade.start_dialogue_session / submit_dialogue_turn -> Ollama dialogue service -> repository -> transcript/result`

Dialogue использует ticket-grounded prompts и хранит сессии в локальной БД.

### Defense DLC

`DefenseView -> MainWindow -> AppFacade.defense_* -> defense_service -> repository/Ollama -> workspace snapshot`

Этот поток включает:

- локальную активацию;
- проекты;
- импорт материалов;
- dossier, outline, storyboard;
- logical gaps;
- mock defense и repair queue.

## Persistence

SQLite хранит:

- source documents;
- tickets;
- sections;
- atoms;
- skills;
- exercise templates;
- attempts;
- mastery profiles;
- weak areas;
- review queue;
- dialogue sessions and turns;
- defense projects, claims, slides, questions, scores и license state.

## QA hooks

Ключевые проверочные точки:

- `python -m pytest -q`
- `tests/test_painter_warnings.py`
- `scripts/ui_click_audit.py`
- `docs/superpowers/screenshots/2026-04-17-warm-minimal/`

На 2026-04-17 базовый ориентир репозитория:

- `186 passed, 5 skipped`

## Границы продукта

1. Основной подтверждённый release path относится к Windows desktop.
2. macOS code-path подготовлен, но реальный smoke на Mac остаётся открытым.
3. Никаких облачных LLM.
4. `dist/` считается generated output.
