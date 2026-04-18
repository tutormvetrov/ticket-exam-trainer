# Flet Migration & Data Quality Overhaul — дизайн v2.0

> Status on 2026-04-18: pending implementation.
>
> Reference artifacts:
> - current base (Qt v1.2.x): `186 passed, 5 skipped` on 2026-04-17
> - seed DB baseline audit: `build/demo_seed/state_exam_public_admin_demo.db` — 35% билетов с деградированным контентом, LLM refinement не прогонялся
> - target ship: v2.0 Flet build для однокурсников к 10-12 мая 2026, письменный госэкзамен 13 мая

**Дата:** 2026-04-18
**Автор:** совместно с Claude (superpowers:brainstorming)
**Цель:** мигрировать UI-слой с PySide6/Qt на Flet (Flutter engine), одновременно починить data pipeline до уровня пригодности к реальной подготовке к госэкзамену. Сохранить warm-minimal визуальный язык в новой стек-адаптации. Держать domain/application/infrastructure неизменными.

---

## 1. Motivation

Текущее приложение v1.2.x на PySide6 имеет две независимые проблемы, которые нельзя решить в одном слое:

1. **Data-слой**: из 208 билетов текущего seed-ядра 36 (17%) содержат мусорный контент (`● (5) 5` вместо ответа), 73 (35%) имеют summary менее 200 символов. Атомы разорваны по аббревиатурам (`ст.` интерпретирован как конец предложения → «5 Конституции)» как отдельная единица знания). Answer_blocks таблица пуста — `state-exam-full` режим не функционален. LLM refinement на 0% билетов.

2. **UI-стек**: PySide6 решает задачу, но стек громоздкий для развития. Кастомный QSS-набор («folio/atelier/paper») поддерживать долго, dark theme отсутствует, responsive требует ручной обработки `resizeEvent`, QPainter custom-drawings создают warning storms.

Цель v2.0 — приложение, пригодное для реальной подготовки к письменному госэкзамену: каждый билет содержит осмысленный полный ответ, рецензент выдаёт содержательную обратную связь по тезисам, UI работает на любом мониторе от 13" ноутбука до 4K.

## 2. Decisions

| Параметр | Выбор | Отклонённые варианты и почему |
|---|---|---|
| UI-стек | **Flet (Flutter engine), Python 3.12** | PySide6 (оставляем как fallback до финальной приёмки, потом удаляем), web-фреймворк (нет офлайн-desktop-feel) |
| Стратегия сценариев | **C (радикальная переоценка)** — только письменный госэкзамен | A (паритет 1:1, тащит неиспользуемое), B (частичный скоуп без ясных границ) |
| Ship-дата | **S2** — Flet v2.0 сразу однокурсникам к 10-12 мая | S1 (Qt v1.3 к 27 апр + Flet после — комфортнее, но раздваивает внимание), S3 (без классмейтского дедлайна — отказ от обязательства) |
| Параллелизм | **P2 с тремя workstream-ами** (data / Flet UI / installer) | P1 (последовательно — не влезает в сроки), P2 с двумя stream-ами (установщик разбавляет оба) |
| LLM-стратегия | **Локальная Ollama с tiered-моделями** (0.6b/1.7b/4b/8b) + hardware-aware установщик | Cloud-LLM (запрещён product spec), только 8b (многие машины не тянут), rule-based без LLM (рецензент деградирует до keyword-matching) |
| Рецензент-движок | **R0** — эмпирическая валидация на qwen3:1.7b и 8b на 5 реальных билетах до коммита на модель | R1 (порт 1:1 без валидации — риск), R2 (переделать сразу — +15ч), R3 (новый формат — нет времени) |
| Тренировочные режимы | **M2** — 6 режимов: reading, active-recall, cloze, plan, state-exam-full, review | M0 (только review+state-exam — тренировка запоминания страдает), M1 (без active-recall — теряем формативный режим), M3 (всё 8 — matching/mini-exam не окупаются) |
| Импорт | **I1** — предзагруженный seed + минимальный Import view | I0 (только seed — нет гибкости), I2 (полный импорт с preview — +15-25ч) |
| Визуал | **«Нормальный»** — warm tokens, light+dark, responsive 1024-3840+, компонентная библиотека 10 штук | Минимум (Material 3 defaults без tokens — пользователь запретил), премиум (3 размера × 2 темы × 10 экранов × storybook — +30ч) |
| Экраны | **6** — Library, Import, Tickets, Training, Statistics, Settings | Добавить Dialogue/Knowledge Map/Defense DLC/Subjects/Sections (все в архив v1.2.x-general-exam) |

## 3. Strategy

Три параллельных workstream-а с frozen interface между ними. Контракт: facade, ui_data dataclasses, domain models, SQLite schema не меняются без синхронизации через координатора. Координатор — автор (Claude в последующих сессиях), синхронизирует через review PR-ов и sync-коммиты.

Ship-план S2: классмейты получают Flet v2.0 напрямую, без промежуточного Qt v1.3. Риск — уперлись в `flet pack` / шрифты / Ollama setup на чужой машине в последние дни. Митигация: packaging-check на день 3-5, не на день 18; smoke-тесты на 2-3 VM заранее; готовый fallback «Qt v1.3 с новым seed» если Flet не взлетает (не отдельная разработка, а просто собрать текущий Qt с v2-seed).

---

## Часть 1: Архитектура и границы workstream-ов

### 1.1 Layered architecture (без изменений)

```
app/              bootstrap, paths, platform
application/      use cases, facade, services       ← frozen interface для W2
domain/           entities, value objects            ← frozen для всех
infrastructure/   SQLite, Ollama, importers          ← активно меняется W1
ui/               PySide6 (legacy, fallback)         ← заморожен
ui_flet/          Flet (new)                         ← создаётся W2
scripts/          build, setup, packaging            ← активно меняется W3
```

### 1.2 Три workstream-а

| Stream | Worktree ветка | Базируется от | Фокус | Основные файлы |
|--------|---------------|---------------|-------|----------------|
| **W1: Data pipeline** | `data-pipeline` | `v1.2.0` tag | Починка PDF-импорта, атомы, answer_blocks, нормализация, LLM refinement | `infrastructure/importers/`, `application/import_service.py`, `scripts/build_state_exam_seed.py`, `tests/test_pdf_*` |
| **W2: Flet UI** | `flet-migration` | `v1.2.0` tag | Новый пакет `ui_flet/`, 6 экранов, 6 workspaces, компоненты, темы | `ui_flet/`, `pyproject.toml`, `requirements.txt` (добавляет flet) |
| **W3: Installer & packaging** | `installer` | `v1.2.0` tag | Мастер установки Ollama, hardware detection, `flet pack` сборка, zip дистрибуция | `scripts/install_ollama_wizard.ps1`, `scripts/build_flet_exe.ps1`, `scripts/package_release.ps1`, `scripts/install_ollama_macos.sh` |

### 1.3 Frozen interface

Эти артефакты **не меняются без координации**:

- `application/facade.py` — публичный API класса `AppFacade`
- `application/ui_data.py` — формы dataclass-ов `Ticket`, `Atom`, `AnswerBlock`, `TrainingEvaluationResult`, `ReviewVerdict`, `ThesisVerdict`
- `application/ui_query_service.py` — read-only projection shapes
- `domain/models.py` — сущности `SourceDocument`, `Section`, `Exam`, `Ticket`, `Atom`, `Skill`
- `infrastructure/db/schema.sql` — SQLite schema (только add-column миграции; не rename, не drop без синхронизации)

Если W1 требует изменения формы (например, добавить `Atom.byline_suppressed`) — делается через sync-коммит в main с update документации для W2/W3. W2 потребляет только публичные формы из `application/ui_data.py`.

### 1.4 Branch & tag strategy

```
main (before)       ─── 40+ WIP files, uncommitted
main (after day 0)  ─── commit WIP (3-5 logical commits) ─── tag v1.2.0 ─── [base for all 3 worktrees]
main (after merge)  ─── merge W1 → merge W2 → merge W3 → tag v2.0.0
```

Worktree-ы создаются через `git worktree add ../ticket-exam-trainer-data data-pipeline` и параллельные для Flet UI и installer. Это избавляет от постоянного `git checkout` между ветками и позволяет агентам независимо работать в изолированных каталогах.

---

## Часть 2: Data Pipeline Overhaul (W1)

7 конкретных правок с acceptance тестами. После W1 seed-DB `state_exam_public_admin_demo_v2.db` должен проходить все тесты.

### 2.1 Byline-stripper

**Проблема**: атом 1 билета 1 начинается с `"( Абдулаева Екатерина) \n\n\nРоссия — федеративное..."`. Имена студентов, которые писали конспект, попадают в атомы как «определения».

**Реализация**: regex + heuristic в `infrastructure/importers/common.py`:
- Распознать шаблоны `(Фамилия Имя)`, `Автор: …`, `Выполнил(а): …`, одиночная строка из 2-3 заглавных русских слов в начале блока
- Удалить из content, но сохранить как `atom.metadata["author"]` если понадобится в будущем

**Acceptance**: 0 атомов начинаются с `(` или известного ФИО-паттерна. Тест `test_byline_stripped_from_atoms`.

### 2.2 Abbreviation-aware tokenizer

**Проблема**: `"Россия — федеративное государство (ст. 5 Конституции)."` разбивается на два атома: `"...государство (ст."` и `"5 Конституции)."`. Токенайзер не знает, что `ст.` — не конец предложения.

**Реализация**: `infrastructure/importers/ru_tokenizer.py` — список русских аббревиатур:
```
ст. гл. п. пп. т.е. т.к. т.н. и т.д. и т.п. см. др.
стр. абз. ч. ФЗ КРФ ГК УК РФ ЗАО ОАО ООО ГМУ ВУЗ
млн. млрд. тыс. руб. долл. евро ок. прим. рис. табл.
№ § и пр.
```
Плюс pattern-based: инициалы (`А.Н.`, `А. Н. Иванов`), десятичные (`5.5`), URL/email.

**Acceptance**: атомы билета 1 содержат «Россия — федеративное государство (ст. 5 Конституции)» как один связный элемент. Тест `test_abbreviation_tokenizer`.

### 2.3 TOC-detector

**Проблема**: билеты 4, 5, 6, 7, 8 содержат `● (N) N` вместо ответа. Парсер взял оглавление конспекта (где перечислены билеты) и принял bullet-list как содержание билетов.

**Реализация**: `infrastructure/importers/toc_detector.py`:
- Эвристика на блок-уровне: если > 80% строк блока — короткие (< 80 символов), начинаются с цифры/маркера, содержат title-case заголовки → это TOC
- Либо обратная: если блок < 100 символов и не содержит полного предложения с глаголом → skip как имитация контента
- TOC блоки помечаются `content_chunk.metadata["is_toc"] = True` и не становятся билетами

**Acceptance**: билеты 4-8 либо содержат реальный текст (если он есть в PDF), либо помечены `status="insufficient_content"` и не попадают в финальный seed. Тест `test_toc_not_imported_as_tickets`.

### 2.4 Title normalizer

**Проблема**: `МДЭ ГА 2024 Кол Конспект ГМУ ГАРФ 18 02 2025 в 2` — результат naive `.title()` от имени файла. Аббревиатуры сохранились случайно (уже были в capsах), но «Кол» должно быть `Кол.` (сокращение), даты должны склеиваться через точки.

**Реализация**: `infrastructure/importers/title_normalizer.py`:
- Детектировать 2-4-буквенные капс-последовательности как аббревиатуры (сохранить)
- Детектировать паттерны `DD MM YYYY` и склеивать в `DD.MM.YYYY`
- Детектировать словарные сокращения (`Кол` → `Кол.`, `в N` → `, вариант N`)
- Возвращать normalized form как `Document.display_title`, сохранять оригинальное имя файла в `Document.source_filename`

**Схема изменения**: добавить колонки `display_title TEXT` и `source_filename TEXT` в `source_documents` через миграцию. Поле `title` становится legacy — заполняется = `display_title` для совместимости.

**Acceptance**: `МДЭ ГА 2024. Конспект ГМУ ГАРФ. 18.02.2025, вариант 2` — ожидаемый вывод для текущего PDF. Тест `test_title_normalizer_known_patterns` с 10 известными примерами.

### 2.5 Section metadata parser

**Проблема**: `Философия Седых Татьяна Николаевна ВШГА МГУ Доцент` — один слипшийся string в `sections.title`. Раздел, ФИО, департамент, должность смешаны.

**Реализация**: `infrastructure/importers/section_metadata_parser.py`:
- Шаблон ФИО: три слова с заглавной буквы подряд, из которых 1-е — известное русское имя/фамилия (список топ-3000)
- Словарь департаментов: `ВШГА`, `МГУ`, `МГИМО`, `ВШЭ` и их комбинации
- Словарь должностей: `Доцент`, `Профессор`, `Ст. преподаватель`, `Ассистент`, `Доктор наук`, `Кандидат наук`, `Заведующий кафедрой`
- Если все компоненты распознаны → делим на `title`, `lecturer_name`, `department`, `position`; если эвристика не сработала → `title` = исходная строка, остальные None

**Схема изменения**: добавить `lecturer_name TEXT NULL`, `department TEXT NULL`, `position TEXT NULL` в `sections` через миграцию.

**Acceptance**: для 10 известных заголовков парсер извлекает корректные поля. Fallback в `title` сохраняется при неудаче. Тест `test_section_metadata_parser`.

### 2.6 Answer_blocks generator

**Проблема**: таблица `answer_blocks` пустая. Без неё `state-exam-full` mode не работает, рецензент не имеет reference theses для государственного профиля.

**Реализация**: `application/answer_block_builder.py` уже существует — подключить его в pipeline. Для каждого билета LLM-prompt:
> «Разбей канонический ответ на 6 блоков структуры письменного госэкзамена: Введение, Определения, Классификация, Механизм/Анализ, Примеры, Заключение. Верни JSON.»

Если билет слишком короткий (< 500 символов) → генерируем только `Определения` и `Заключение`, остальные пометим `status="insufficient_source"`.

**Acceptance**: для 80 билетов с «reasonable» content в v1-seed после прогона появляется 6 answer blocks. Тест `test_answer_blocks_generated_for_full_ticket`.

### 2.7 LLM refinement pass

**Проблема**: 0 из 208 билетов прошли LLM-refinement. Reference theses для рецензента — это просто первичные атомы, часто битые.

**Реализация**: уже написанный `scripts/build_state_exam_seed.py` с параллельными workers, но с:
- Таймаутом 120 секунд на билет (не бесконечность)
- Retry 2 раза при таймауте, потом пропустить с пометкой `llm_error="timeout"`
- Рекомендуемая модель qwen3:1.7b (валидация R0 может изменить на 4b/8b)
- `--max-resume-passes 1` или 2 — обновляем атомы, генерируем answer_blocks, генерируем reference theses для review mode

Бюджет: 208 билетов × ~30-60 сек/билет на 4-workers = 25-50 минут на одну passe. Две passes (атомы + review theses) = 1-2 часа машинного времени.

**Acceptance**: 200+ из 208 билетов имеют `llm_status="succeeded"`. < 10 с `llm_error="timeout"` или `llm_error="parse_error"`. Тест `test_seed_v2_llm_coverage`.

### 2.8 Deliverable W1

- Файл `build/demo_seed/state_exam_public_admin_demo_v2.db`
- Manifest в `build/demo_seed/state_exam_public_admin_demo_v2.manifest.json` с checksum
- Verify-script `scripts/verify_state_exam_seed.py` зелёный на новом seed
- Все 7 acceptance тестов зелёные

---

## Часть 3: Flet UI (W2)

### 3.1 Структура пакета

```
ui_flet/
  __init__.py
  main.py                       # entry: python -m ui_flet.main
  state.py                      # AppState, breakpoint signal, theme signal
  router.py                     # page.on_route_change
  theme/
    tokens.py                   # COLOR, TYPE, SPACE, RADIUS
    fonts.py                    # Lora, Golos Text, JetBrains Mono
    theme.py                    # build_theme(brightness) -> ft.ThemeData
    fonts/                      # local TTF fallbacks
  components/
    card.py                     # Card (base)
    sidebar.py                  # Sidebar (collapsible on compact)
    top_bar.py                  # TopBar (serif title + subtitle + actions)
    stat_card.py
    ticket_card.py
    chip.py
    ollama_status_badge.py      # live status indicator
    review_verdict_widget.py    # per-thesis verdict display
    training_workspace_base.py  # base for mode workspaces
    empty_state.py
  views/
    library_view.py
    import_view.py
    tickets_view.py
    training_view.py
    statistics_view.py
    settings_view.py
  workspaces/
    reading_workspace.py
    active_recall_workspace.py
    cloze_workspace.py
    plan_workspace.py
    state_exam_full_workspace.py
    review_workspace.py
  i18n/
    ru.py                       # все UI-строки
  _dev/
    storybook.py                # облегчённая галерея компонентов
```

### 3.2 Theme tokens

Дизайн-токены адаптируют warm-minimal палитру из v1.2.x для Material 3:

```python
# ui_flet/theme/tokens.py

COLOR_LIGHT = {
    "bg_base":        "#F3E8D2",   # sand paper
    "bg_surface":     "#FBF4E4",   # parchment
    "bg_elevated":    "#FFFBF0",
    "bg_sidebar":     "#F7EDD6",
    "accent":         "#A94434",   # rust
    "accent_hover":   "#8F3528",
    "accent_soft":    "#E8C9BF",
    "text_primary":   "#2B1F17",
    "text_secondary": "#6B5A4A",
    "text_muted":     "#9B8874",
    "border_soft":    "#E3D4B5",
    "border_medium":  "#C9B68F",
    "success":        "#5B8A3A",   # moss
    "warning":        "#C68B2E",
    "danger":         "#A94434",
}

COLOR_DARK = {
    "bg_base":        "#241811",   # dark cognac
    "bg_surface":     "#2E1F16",
    "bg_elevated":    "#3A2A1E",
    "bg_sidebar":     "#1F140E",
    "accent":         "#D9735E",   # desaturated rust
    "accent_hover":   "#E88670",
    "accent_soft":    "#4A2820",
    "text_primary":   "#F3E8D2",
    "text_secondary": "#C9B68F",
    "text_muted":     "#8F7D63",
    "border_soft":    "#3D2C1F",
    "border_medium":  "#553F2C",
    "success":        "#8EB266",
    "warning":        "#D9A857",
    "danger":         "#D9735E",
}

TYPE = {
    "display":     {"family": "Lora",        "size": 32, "weight": "w600"},
    "h1":          {"family": "Lora",        "size": 26, "weight": "w600"},
    "h2":          {"family": "Lora",        "size": 20, "weight": "w600"},
    "h3":          {"family": "Golos Text",  "size": 16, "weight": "w600"},
    "body":        {"family": "Golos Text",  "size": 14, "weight": "w400"},
    "body_strong": {"family": "Golos Text",  "size": 14, "weight": "w600"},
    "caption":     {"family": "Golos Text",  "size": 12, "weight": "w400"},
    "mono":        {"family": "JetBrains Mono", "size": 12, "weight": "w400"},
}

SPACE  = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 48}
RADIUS = {"sm": 6, "md": 10, "lg": 14, "xl": 20, "pill": 999}
```

Dark palette — desaturated warm, не черный. Сохраняется эмоциональная связь со светлой версией (cognac leather вместо ink black).

### 3.3 Responsive breakpoints

```python
# ui_flet/state.py

BREAKPOINTS = {
    "compact":    (0, 1280),      # sidebar drawer, 1-col
    "standard":   (1280, 1920),   # sidebar open, 2-col
    "wide":       (1920, 2560),   # 2-col with max-width reading
    "ultrawide":  (2560, 3840),   # 3-col multi-panel
    "huge_4k":    (3840, None),   # 3-col + UI scale 1.25x
}
```

Multi-panel layouts на `ultrawide+`:
- `Tickets`: список | деталь | related/weak-areas (3 колонки)
- `Training` (active-recall/review workspace): context | workspace input | result/rubric
- `Library`: документы | деталь с табами | правая статистика

На `huge_4k` дополнительно `page.scale = 1.25` чтобы кнопки и текст не были микроскопическими на 27".

### 3.4 Facade integration

Один instance `AppFacade` создаётся в `ui_flet/main.py` и передаётся во все views через `AppState`. Views делают только `state.facade.method(...)` — никаких прямых обращений к `infrastructure/`.

### 3.5 Theme switching

`page.theme_mode = ft.ThemeMode.LIGHT / DARK` — переключатель в `Settings`. Все компоненты используют `page.theme.color_scheme.*` через tokens — при переключении UI обновляется без рестарта.

### 3.6 Import view — минимальный скоуп

`ImportView` — один dropzone для PDF/DOCX, кнопка «Импортировать», progress indicator с этапами (parsing → atoms → answer_blocks → LLM refinement). Без preview, без детальной настройки, без выбора секций. По завершении — редирект в Library.

Если пользователь не импортирует ничего — использует pre-baked seed. Import view доступен из sidebar, но не является основной точкой входа. Акцент в onboarding — на pre-baked seed.

### 3.7 Deliverable W2

- Пакет `ui_flet/` с 10 компонентами, 6 views, 6 workspaces
- Обе темы функциональны
- Responsive breakpoints работают при ресайзе окна
- Все UI-строки из `ui_flet/i18n/ru.py`, никакого хардкода
- Storybook запускается через `python -m ui_flet._dev.storybook`, даёт визуальный отчёт
- `python -m ui_flet.main` открывает приложение и подключается к seed-DB

---

## Часть 4: Тренировочные режимы M2

6 режимов, каждый со своим workspace. Логика скоринга — существующая `application/scoring.py` без изменений.

| Mode | Назначение | Input | Feedback |
|------|-----------|-------|----------|
| `reading` | Знакомство с билетом | — | Показ эталонного ответа с разметкой атомов |
| `active-recall` | Быстрое воспроизведение по памяти | Короткий свободный ответ (1-3 абзаца) | Score + weak points + thesis-level review (если LLM доступна) |
| `cloze` | Заучивание формулировок | Fill-in-the-blank | Бинарно правильно/неправильно по пропускам |
| `plan` | Структурная память | Drag-to-order точек плана | Бинарно правильный/неправильный порядок |
| `state-exam-full` | Полный письменный ответ по госпрофилю (6 answer blocks) | Текст в 6 полях по блокам | Block scores + criterion scores + thesis-level review |
| `review` | Рецензент: глубокий разбор тезисов | Полный письменный ответ | Per-thesis verdict (covered/partial/missing) + strengths + recommendations + overall score |

**Исключены**: `matching` (дублирует cloze без добавленной ценности), `mini-exam` (дублирует state-exam-full без answer blocks).

### 4.1 Review engine (R0 validation gate)

Перед началом работы W2 на `review` workspace — валидационный прогон. Выполняет координатор (я) на день 0, до запуска агентов.

1. Выбрать 5 билетов из v1-seed с «reasonable» content (500+ символов)
2. Координатор вручную пишет 5 реалистичных студенческих ответов: 1 отличный, 2 средних (с пропусками тезисов), 2 слабых (поверхностные или с ошибками) — приближённо к реальному разбросу
3. Прогнать `review_answer()` на qwen3:1.7b, qwen3:4b, qwen3:8b (если доступна) через существующий `infrastructure/ollama/service.py`
4. Оценить по рубрике:
   - Корректный JSON в 5/5 случаев (без парс-ошибок)?
   - Per-thesis verdicts соответствуют реальности эксперта?
   - Recommendations конкретны (включают action-verb) или водянисты?
   - Время ответа приемлемо (< 60 сек на 1.7b CPU-only)?
5. Зафиксировать выбор default-модели в `docs/superpowers/specs/2026-04-18-model-selection.md` с прикреплёнными примерами input/output
6. Результат: рекомендованная модель для установщика (default tier), граничные условия (требуется ли для review mode обязательно 4b+?)

Если 1.7b проваливается — default повышается до 4b. Если 4b проваливается — `review` mode помечается `requires_model=["qwen3:8b"]` и UI предупреждает пользователей со слабым железом.

---

## Часть 5: Ollama Installer (W3)

### 5.1 Hardware detection

`scripts/install_ollama_wizard.ps1`:
```powershell
$ram_gb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$cpu_cores = (Get-CimInstance Win32_Processor | Select-Object -ExpandProperty NumberOfCores)
# Выбираем GPU с наибольшим VRAM (дискретная карта обычно имеет больше памяти чем встроенная)
$gpu = Get-CimInstance Win32_VideoController |
    Where-Object { $_.AdapterRAM -gt 0 } |
    Sort-Object AdapterRAM -Descending |
    Select-Object -First 1
$vram_gb = if ($gpu) { [math]::Round($gpu.AdapterRAM / 1GB, 1) } else { 0 }
```

> Замечание: `Win32_VideoController.AdapterRAM` — 32-битное поле, на картах с 4+ ГБ VRAM может показывать некорректные значения. Для 4+ ГБ использовать `dxdiag /t` вывод или `nvidia-smi` если установлен. Fallback для W3 — пользователь может override тир вручную.

### 5.2 Tiered рекомендация

| Тир | Модель | RAM | VRAM | Время ответа рецензента | Скачивание |
|-----|--------|-----|------|------------------------|------------|
| Лёгкий | qwen3:0.6b | 4 GB | — | 10-20 сек CPU | ~600 МБ |
| Рекомендованный (default) | qwen3:1.7b | 8 GB | — | 20-40 сек CPU | ~1.5 ГБ |
| Продвинутый | qwen3:4b | 16 GB | 6 GB+ | 10-25 сек с GPU | ~3 ГБ |
| Полный | qwen3:8b | 16+ GB | 8+ GB | 5-15 сек с GPU | ~5 ГБ |

Wizard делает:
1. Детект железа → показать рекомендацию («У вас 16ГБ RAM и GTX 1660 6ГБ — рекомендую qwen3:4b, рецензент будет отвечать за 10-25 секунд»)
2. Пользователь может override: кнопки «Быстрее» (-1 тир) / «Качественнее» (+1 тир)
3. Установить Ollama если не стоит — запуск `OllamaSetup.exe` с тихим флагом. Проверить актуальный flag в документации Ollama перед коммитом (кандидаты: `/SILENT`, `/VERYSILENT`, `/S`; зависит от installer framework, который Ollama использует на момент сборки)
4. `ollama pull <tier>` с прогресс-баром
5. Canary request → рецензент-prompt на тестовом билете → валидация JSON → success/fail
6. Записать выбор в `app_data/settings.json`

### 5.3 macOS mirror

`scripts/install_ollama_macos.sh` — аналогичная логика через `sysctl hw.memsize`, `system_profiler SPDisplaysDataType`. Вторичный приоритет — делаем после Windows-пути, если время остаётся.

### 5.4 Deliverable W3

- Работающий wizard на Windows, протестирован на 2 машинах (ноут 8ГБ и ПК 32ГБ+GPU)
- Canary test проходит на обеих
- `scripts/build_flet_exe.ps1` собирает exe через `flet pack`
- `scripts/package_release.ps1` создаёт zip: `Tezis-v2.0-windows.zip` с exe + wizard + seed DB + README
- Smoke-тест: распаковать zip на чистой VM → запустить wizard → запустить exe → открыть билет → написать ответ → получить рецензию

---

## Часть 6: Distribution Bundle

Структура финального zip:

```
Tezis-v2.0-windows.zip
├── Tezis.exe                               # собранный flet pack
├── data/
│   └── state_exam_public_admin_demo.db     # v2 seed
├── scripts/
│   ├── install_ollama_wizard.ps1           # мастер установки
│   └── check_ollama.ps1                    # утилита диагностики
├── assets/
│   └── icon.ico
├── README.txt                              # для однокурсников — краткая инструкция
└── LICENSE.txt
```

README.txt: 10 шагов на русском, от «скачать» до «первый билет». Включает скриншоты окон wizard-а и главного экрана.

---

## Часть 7: Data Migration Strategy

### 7.1 SQLite schema

**Добавления** (через миграцию, не breaking):
- `source_documents.display_title TEXT`
- `source_documents.source_filename TEXT`
- `sections.lecturer_name TEXT NULL`
- `sections.department TEXT NULL`
- `sections.position TEXT NULL`
- `atoms.metadata_json TEXT NULL` (для `author` и других полей без отдельных колонок)

**Существующий seed**: v1 seed заменяется v2 seed целиком. У классмейтов v1 никогда не было — установка v2 с нуля. У автора v1 остаётся в `build/demo_seed/state_exam_public_admin_demo.db` как бэкап.

**Пользовательские данные**: если классмейт импортировал свой PDF и накопил tracking данные, эти данные в их локальной БД (`app_data/exam_trainer.db`). Миграционный скрипт при первом запуске v2 applies schema migrations поверх существующей БД. Данные сохраняются.

### 7.2 Миграция

`infrastructure/db/migrations/` — новый подкаталог. Каждая миграция — SQL-скрипт с версией:
- `001_add_document_normalized_fields.sql`
- `002_add_section_metadata_fields.sql`
- `003_add_atom_metadata.sql`

Таблица `schema_versions` отслеживает применённые. При запуске приложения — проверка и применение pending миграций.

---

## Часть 8: Testing Strategy

### 8.1 Переносимые тесты (не меняются)

Service/domain/infrastructure тесты (~150 шт) работают без изменений, т.к. они не завязаны на UI-фреймворк:
- `test_import_service.py`, `test_scoring.py`, `test_adaptive_review.py`, `test_state_exam_scoring.py`
- `test_ollama_runtime.py`, `test_ollama_service.py`
- `test_pdf_*` (новые после W1)
- `test_delete_document.py`, `test_release_seed.py`

### 8.2 Удаляемые тесты

Qt-специфичные, не имеют аналога в Flet:
- `test_painter_warnings.py` — QPainter нет в Flet
- `test_theme_palette.py`, `test_theme_typography.py`, `test_materiality.py`, `test_logo_mark.py` — привязаны к QPalette/QFont
- `test_responsive_layouts.py` — привязан к QResizeEvent

Сохраняются в `tests/qt_legacy/` до финальной приёмки v2.0, потом удаляются вместе с `ui/` пакетом.

### 8.3 Новые тесты W2

- `tests/test_flet_state.py` — breakpoint logic, theme switching, facade wiring
- `tests/test_flet_theme_tokens.py` — токены не хардкодятся в компонентах
- `tests/test_flet_i18n.py` — все строки из `ui_flet/i18n/ru.py`
- `tests/test_flet_router.py` — роуты работают

UI-smoke тесты через Flet testing API (если стабильно на день 10) или через pyautogui скриншотирование и visual diff.

### 8.4 Acceptance для всего v2.0

- Все pytest зелёные (`pytest -q`)
- `flet pack` собирает exe без ошибок
- Exe запускается на 2 тестовых Windows VM (чистая Windows 10 + Windows 11)
- Wizard устанавливает Ollama + модель без участия пользователя кроме click «Далее»
- На открытом билете рецензент выдаёт per-thesis verdict за < 60 секунд на рекомендованной модели
- v2 seed: 0 билетов с garbage content, все с LLM refinement

---

## Часть 9: Execution Sequence (calendar)

> Пользователь указал, что сроки переоценены. Оставляю консервативные оценки как потолок; ускоряемся по факту продвижения.

**День 0 (18 апреля, сегодня):**
- Я: commit WIP в main (3-5 логических commits), tag `v1.2.0`, создание трёх worktree-веток
- Я: R0 валидация рецензента на 5 билетах × 3 моделях → выбор default
- Я: запуск трёх агентов параллельно с prompt-ами по workstream-ам

**Дни 1-3 (19-21 апреля, hackathon):**
- W1 (data agent): byline stripper + abbrev tokenizer + TOC detector + title normalizer (дни 1-2), запуск LLM refinement pass на ночь (день 2-3)
- W2 (Flet agent): theme tokens + shell + 3 простых view (Library, Tickets, Settings) + компонентная база (дни 1-3)
- W3 (installer agent): hardware detection + Ollama install + canary test (день 1-2), packaging build (день 3)
- Вы: ежедневное ревью PR-ов от агентов, эскалация мне

**Дни 4-10 (22-28 апреля):**
- W1: answer_blocks generator + section metadata parser + финальный LLM refinement pass; W1 closes
- W2: Import view + Training view + Statistics view + 6 training workspaces; integration с v2 seed
- W3: macOS mirror (если время), smoke на 2 VM
- Вы: промежуточные тесты, feedback по визуалу

**Дни 11-18 (29 апреля — 6 мая):**
- W2: dark theme polish + responsive на 2560+ + 4K scale + bug fixes
- W3: финальная сборка, release notes, README для однокурсников
- Весь стек: pytest зелёный, flet pack стабилен, wizard на 2 VM smoke

**Дни 19-22 (7-10 мая):**
- Финальный polish, проверка на ещё одной VM, документация
- Рассылка zip однокурсникам 10-12 мая

**Буфер 11-13 мая:** реакция на багрепорты от классмейтов перед экзаменом 13 мая.

### 9.1 Cut order

Если за срок не успеваем, режется в таком порядке (первый — самый ценный для cut-а, минимум потерь):
1. Dark theme (полный skip; Light-only в релизе)
2. 4K multi-panel (оставляем только 3-колоночный ultrawide)
3. `Import` view (оставляем только seed; удаляем возможность загрузки своего PDF)
4. `Statistics` view (заменить на минимальную панель внутри Library)
5. macOS сборка (полный skip; только Windows)

---

## Часть 10: Files Affected

| Файл / Каталог | Stream | Тип | Описание |
|----------------|--------|-----|----------|
| `infrastructure/importers/common.py` | W1 | modify | byline stripper |
| `infrastructure/importers/pdf_importer.py` | W1 | modify | интеграция новых парсеров |
| `infrastructure/importers/ru_tokenizer.py` | W1 | **new** | abbreviation-aware tokenizer |
| `infrastructure/importers/toc_detector.py` | W1 | **new** | TOC-block detection |
| `infrastructure/importers/title_normalizer.py` | W1 | **new** | title normalization |
| `infrastructure/importers/section_metadata_parser.py` | W1 | **new** | section metadata extraction |
| `infrastructure/db/migrations/` | W1 | **new dir** | SQL migrations |
| `application/answer_block_builder.py` | W1 | modify | подключение в pipeline |
| `application/import_service.py` | W1 | modify | использование новых парсеров |
| `scripts/build_state_exam_seed.py` | W1 | modify | LLM refinement + retry |
| `scripts/verify_state_exam_seed.py` | W1 | modify | новые acceptance checks |
| `tests/test_byline_stripper.py` | W1 | **new** | |
| `tests/test_abbreviation_tokenizer.py` | W1 | **new** | |
| `tests/test_toc_detector.py` | W1 | **new** | |
| `tests/test_title_normalizer.py` | W1 | **new** | |
| `tests/test_section_metadata_parser.py` | W1 | **new** | |
| `tests/test_answer_blocks_generator.py` | W1 | **new** | |
| `tests/test_seed_v2_quality.py` | W1 | **new** | acceptance |
| `ui_flet/` | W2 | **new pkg** | весь пакет новый |
| `pyproject.toml` | W2 | modify | добавить `flet`, `flet[desktop]` |
| `requirements.txt` | W2 | modify | pinned versions |
| `tests/test_flet_*` | W2 | **new** | |
| `scripts/install_ollama_wizard.ps1` | W3 | **new** | |
| `scripts/build_flet_exe.ps1` | W3 | **new** | |
| `scripts/package_release.ps1` | W3 | **new** | |
| `scripts/install_ollama_macos.sh` | W3 | **new** | optional |
| `docs/architecture.md` | coord | modify | обновить после merge |
| `docs/product_spec.md` | coord | modify | scope v2.0 |
| `docs/roadmap.md` | coord | modify | перенести general-exam features в архив |
| `README.md` | coord | modify | v2.0 instructions |
| `CHANGELOG.md` | coord | **new** | |

---

## Часть 11: Scope Boundaries

**In scope (v2.0):**
- Flet UI (6 views, 6 training workspaces)
- Data pipeline fixes (7 правок)
- Ollama installer с hardware detection и tiered models
- Warm-minimal visual language в Material 3 адаптации, light + dark
- Responsive от 1024 до 3840+
- Pre-baked seed DB для госэкзамена ГМУ ГАРФ
- Windows-дистрибутив (zip, exe, wizard)

**Out of scope (v2.0) — архив v1.2.x-general-exam:**
- Dialogue mode (устная репетиция)
- Knowledge Map view
- Subjects view
- Sections view (как отдельный экран; section metadata — часть ticket detail)
- Defense DLC (подготовка к защите)
- Training modes: matching, mini-exam
- Import preview
- Cloud LLM
- Web/browser версия
- macOS сборка (вторичный приоритет, если остаётся время)

**Deferred to v2.1 (после 13 мая):**
- macOS полноценная сборка и smoke
- Dialogue mode на Flet (если нужен)
- Knowledge Map на Flet
- Visual polish на 4K
- Import preview

---

## Часть 12: Risks & Mitigations

| Риск | Вероятность | Воздействие | Митигация |
|------|-------------|-------------|-----------|
| `flet pack` падает на Windows из-за кириллицы в путях / шрифтах | Средняя | Критическое (нет exe) | Packaging smoke на день 3, не на день 18; fallback на PyInstaller с Flet через wheels если flet pack ломается |
| Рецензент на qwen3:1.7b даёт мусорные JSON | Средняя | Высокое (основная фича проседает) | R0 валидация на день 0; откат на 4b или 8b с предупреждением в UI |
| Agent W1 ломает dataclass shape, W2 не компилируется | Низкая | Среднее | Frozen interface + daily reconcile + автотесты на форму dataclass-ов |
| Ollama не устанавливается на чужой Windows (права, антивирус) | Средняя | Критическое для UX | Fallback инструкция в README на ручную установку; canary test с ясной ошибкой |
| LLM refinement pass не завершается за ночь (208 билетов × 2 passes) | Низкая | Среднее | `--max-resume-passes 1` на минимуме; partial_llm статус допустим для fallback |
| Шрифты Lora/Golos Text не загружаются через Google Fonts у классмейта (корпоративный firewall) | Низкая | Среднее | Bundling TTF в `ui_flet/theme/fonts/`, no-network fallback |
| Однокурсник откроет на 13" ноутбуке 1366x768 и всё разломается | Низкая | Среднее | Explicit compact breakpoint с sidebar-drawer; smoke на VM с 1366x768 |
| Классмейт не поставит Ollama и не поймёт как запустить без LLM | Средняя | Среднее | Wizard + clear error UI в приложении; fallback rule-based режим с дисклеймером |

---

## Часть 13: Acceptance Criteria

1. `pytest -q` зелёный (все переносимые тесты + новые W1/W2)
2. `flet pack` собирает `Tezis.exe`, запускается на 2 тестовых Windows VM (10 + 11)
3. `scripts/install_ollama_wizard.ps1` устанавливает Ollama + рекомендованную модель на обеих VM
4. Wizard canary test проходит: рецензент отвечает валидным JSON за < 60 сек на рекомендованной модели
5. Seed DB v2: 0 билетов с garbage content (≥ 500 символов в `canonical_answer_summary` или явный `status="insufficient_content"`), ≥ 200/208 билетов с `llm_status="succeeded"`
6. Все 6 экранов работают на 1280x800 без наложений / обрезаний текста
7. Responsive: на 1024x768 sidebar свёрнут, на 2560x1440 multi-panel активен
8. Light + Dark переключаются из Settings без визуальных багов
9. Однокурсник может: запустить exe → открыть билет → написать ответ → получить рецензию → увидеть статистику
10. README.txt понятен не-программисту

---

## Часть 14: Open Items / Future Considerations

- После 13 мая — обзор, какие фичи из «архива v1.2.x» возвращать в v2.x (Dialogue? Knowledge Map? Defense DLC?)
- Потенциальная web-версия через `flet --web` — офлайн-first, но с возможностью локального запуска в браузере
- Интеграция spaced-repetition алгоритма в Statistics / Review queue (SM-2 или FSRS)
- Sync между устройствами (но без cloud-LLM — только данные, шифрованно)
- Контент-пак для других предметов (не только ГМУ госэкзамен)

---

## Status Log

- **2026-04-18:** design created, pending implementation. Next step — `writing-plans` skill → executable plan → parallel agent dispatch.
