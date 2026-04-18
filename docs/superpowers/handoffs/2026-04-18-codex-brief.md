# Codex Handoff Brief: Cloud-LLM Seed Generation

**Audience:** Codex (OpenAI CLI / ChatGPT) — получает эту задачу как одноразовый batch-job.
**Date:** 2026-04-18
**Repo:** `D:\ticket-exam-trainer`
**Working directory:** `D:\ticket-exam-trainer-data` (git worktree на ветке `data-pipeline` от тэга `v1.2.0`)

---

## TL;DR для Codex

Нужно превратить PDF-конспект (208 экзаменационных билетов по госэкзамену) в структурированный JSON для последующей SQLite-seed сборки. Задача однократная, результат шипится пользователям как часть релиза приложения.

**Input:** `build/codex_input/raw_tickets.json` (208 билетов с извлечённым сырым текстом + метаданные раздела).
**Output:** `build/codex_output/structured_tickets.json` (тот же массив, но с обогащением согласно схеме ниже).
**Verification:** `scripts/verify_codex_output.py` (генерируется ниже) проверяет инварианты.

---

## Контекст проекта — коротко

**Проект:** «Тезис» — desktop-приложение на Python для подготовки к вузовским экзаменам.
- До сегодня: PySide6/Qt UI, локальная Ollama для всех LLM-задач (import + runtime).
- **Сегодня начата миграция на Flet** (Flutter engine через Python). Версия 2.0.
- Ship-дата: **10-12 мая 2026** для однокурсников (письменный госэкзамен 13 мая).

**Архитектурный сдвиг (сегодняшнее решение):**
- **One-time PDF → seed conversion** → cloud LLM (ты, Codex). Здесь нужно качество.
- **Runtime review student answer** → local Ollama (qwen3:1.7b или 4b). Здесь важна низкая hardware-планка для классмейтов.

Раньше всё было local Ollama. После валидации (`docs/superpowers/specs/2026-04-18-model-selection.md`) стало ясно: qwen3 не справляется с PDF → structured conversion на слабом железе. Переходим на cloud для seed-сборки.

**Твоя задача — генерация того самого seed один раз.** После этого ты не нужен. Приложение офлайн, локальная Ollama обрабатывает студенческие ответы, cравнивая их с твоими pre-generated reference theses.

## Git worktree структура

Три worktree-ветки от тэга `v1.2.0`:

| Путь | Ветка | Назначение |
|------|-------|-----------|
| `D:\ticket-exam-trainer` | `main` | Координатор + финальный merge |
| `D:\ticket-exam-trainer-data` | `data-pipeline` | **Твой рабочий каталог.** Pre-processing + твой output |
| `D:\ticket-exam-trainer-flet` | `flet-migration` | Новый UI-пакет `ui_flet/` (не твоё) |
| `D:\ticket-exam-trainer-installer` | `installer` | Windows wizard + flet pack (не твоё) |

Твои изменения коммитишь в `data-pipeline`. Координатор сделает merge в `main`.

## Референсные документы (в репозитории)

Перед работой прочитай:

1. **`docs/superpowers/specs/2026-04-18-flet-migration-design.md`** — полный дизайн-документ миграции. Часть 2 описывает data pipeline ожидания.
2. **`docs/superpowers/plans/2026-04-18-w1-data-pipeline.md`** — оригинальный план W1 (cloud-вариант упрощает его: задачи 6, 7 удаляются, см. изменение в этом brief).
3. **`domain/models.py`** — Python dataclasses для `SourceDocument`, `Section`, `Ticket`, `Atom`, `Skill`. Твой output должен mapping-иться сюда напрямую.
4. **`docs/superpowers/specs/2026-04-18-model-selection.md`** — R0 validation, объясняет почему cloud-LLM для seed.

## Что делать

### Шаг 1: Извлеки raw tickets

```powershell
cd D:\ticket-exam-trainer-data
python scripts/codex/extract_raw_tickets.py
```

Скрипт (будет подготовлен координатором) читает PDF `МДЭ_ГА_2024_Кол_Конспект_ГМУ_ГАРФ_18_02_2025_в_2.pdf`, применяет детерминированное preprocessing (byline strip, TOC skip, abbreviation-aware sentence split, title/section normalization) и выдаёт `build/codex_input/raw_tickets.json` формата:

```json
{
  "document": {
    "source_filename": "МДЭ_ГА_2024_Кол_Конспект_ГМУ_ГАРФ_18_02_2025_в_2.pdf",
    "display_title": "МДЭ ГА 2024. Конспект ГМУ ГАРФ. 18.02.2025, вариант 2"
  },
  "tickets": [
    {
      "ticket_number": 1,
      "raw_title": "Государственное устройство Российской Федерации и других государств",
      "raw_content": "[весь очищенный текст билета как он есть в PDF, уже без byline, со склеенными при аббревиатурах предложениями]",
      "section_raw": "Государственное управление и муниципальные услуги Иванов Иван Иванович ВШГА МГУ Доцент"
    },
    ...
  ]
}
```

### Шаг 2: Структурируй каждый билет

Для каждого билета в `raw_tickets.json["tickets"]` произведи structured object:

```json
{
  "ticket_number": 1,
  "title": "Государственное устройство Российской Федерации и других государств",
  "canonical_answer_summary": "[полный очищенный ответ студента-отличника по этому билету, в нормальном прозовом виде, без артефактов парсинга — 800-3000 chars]",
  "section": {
    "title": "Государственное управление и муниципальные услуги",
    "lecturer_name": "Иванов Иван Иванович",
    "department": "ВШГА МГУ",
    "position": "Доцент"
  },
  "atoms": [
    {
      "atom_type": "definition",
      "label": "Определение",
      "text": "Федеративное государство — форма государственного устройства, при которой составляющие его части имеют собственную государственность наряду с общефедеральной...",
      "keywords": ["федеративное", "устройство", "государственность"]
    },
    {
      "atom_type": "classification",
      "label": "Виды",
      "text": "Выделяют: 1) национально-территориальную федерацию; 2) административно-территориальную; 3) смешанную...",
      "keywords": ["национально-территориальная", "административно", "смешанная"]
    },
    {
      "atom_type": "features",
      "label": "Принципы",
      "text": "Конституционные принципы федеративного устройства РФ (ст. 5 Конституции): государственная целостность, единство системы государственной власти, разграничение предметов ведения...",
      "keywords": ["целостность", "единство", "разграничение"]
    },
    {
      "atom_type": "example",
      "label": "Примеры",
      "text": "Россия (смешанная федерация), США (административная федерация штатов), ФРГ (национально-территориальная), Швейцария (конфедеративные элементы)...",
      "keywords": ["Россия", "США", "ФРГ", "Швейцария"]
    }
  ],
  "answer_blocks": [
    {"label": "Введение", "text": "[1-2 абзаца контекста: почему вопрос важен, что будет раскрыто]"},
    {"label": "Определения", "text": "[ключевые термины билета с их определениями]"},
    {"label": "Классификация", "text": "[систематизация объектов/явлений по признакам]"},
    {"label": "Механизм", "text": "[как устроена / работает описываемая система]"},
    {"label": "Примеры", "text": "[конкретные иллюстрации из РФ и мировой практики]"},
    {"label": "Заключение", "text": "[синтез ключевых выводов, 3-5 предложений]"}
  ],
  "reference_theses": [
    {"label": "Понятие и признаки федерации", "text": "Федерация как форма государственного устройства характеризуется наличием собственной государственности у субъектов наряду с общефедеральной."},
    {"label": "Виды федераций", "text": "Различаются национально-территориальные, административно-территориальные и смешанные федерации."},
    {"label": "Принципы федеративного устройства РФ", "text": "Шесть конституционных принципов: государственная целостность, единство системы государственной власти, разграничение предметов ведения и полномочий, равноправие субъектов, национальное самоопределение, равноправие народов."},
    {"label": "Примеры из мировой практики", "text": "США — административная федерация штатов; ФРГ — национально-территориальная; Швейцария с конфедеративными элементами."}
  ],
  "difficulty": 4,
  "estimated_oral_time_sec": 420,
  "warnings": []
}
```

**Запиши результат в `build/codex_output/structured_tickets.json`.**

### Схема полей

| Field | Constraint | Notes |
|-------|-----------|-------|
| `ticket_number` | `int`, 1-208 | из input |
| `title` | str, < 200 chars | из input.raw_title |
| `canonical_answer_summary` | str, **800-3000 chars** | полный прозовый канонический ответ |
| `section.title` | str | предмет, например «Философия» |
| `section.lecturer_name` \| `department` \| `position` | str \| null | Null если эвристика не распарсила |
| `atoms[].atom_type` | enum | `"definition"` \| `"features"` \| `"classification"` \| `"example"` \| `"context"` \| `"mechanism"` \| `"consequence"` |
| `atoms[].label` | str, короткий (≤ 30 chars) | человеко-читаемое имя атома |
| `atoms[].text` | str, 100-1000 chars | содержание атома |
| `atoms[].keywords` | list[str], 3-7 элементов | ключевые слова для fallback-rule-based поиска |
| `answer_blocks` | **ровно 6 элементов** | labels фиксированные: Введение / Определения / Классификация / Механизм / Примеры / Заключение |
| `answer_blocks[].text` | str, 200-800 chars | может быть `""` если тема не требует этого блока (но тогда warn) |
| `reference_theses` | **3-5 элементов** | для runtime-рецензента; короткие, атомарные тезисы |
| `reference_theses[].label` | str, ≤ 50 chars | |
| `reference_theses[].text` | str, 80-300 chars | 1-2 предложения, квинтэссенция тезиса |
| `difficulty` | `int` 1-5 | субъективная оценка |
| `estimated_oral_time_sec` | `int` | ~300-600 |
| `warnings` | list[str] | пометки типа `"source_fragmented"`, `"low_quality_input"`, `"requires_expert_review"` |

### Качественные требования

1. **Byline strip verify:** ни одно поле не начинается со «(Фамилия» / «Автор:». Если в raw_content видишь подпись — игнорируй её.

2. **Abbreviation integrity:** предложения не должны быть разбиты на токене-аббревиатуре. Пример из seed v1: «Россия — федеративное государство (ст. 5 Конституции).» должно быть одним связным предложением, а не фрагментами «...государство (ст.» + «5 Конституции).»

3. **No garbage content:** если билет в raw_content имеет `● (5) 5` или подобный маркер-мусор — помечай `warnings: ["source_is_toc_artifact"]` и генерируй содержимое из title + контекста (при отсутствии полноценного source дай канонический учебный ответ по теме заголовка).

4. **No hallucinated законов/данных:** если не знаешь конкретной нормы — пишу общий принцип, не выдумываю номер ФЗ или дату.

5. **Русский язык.** Весь текстовый output — на русском. Названия labels по схеме выше (фиксированные).

6. **Консистентность.** Одинаковый стиль thesis-формулировок между билетами. Не смешивать «научно-формальный» и «ученический» регистры.

### Шаг 3: Verify

После генерации запусти:

```powershell
python scripts/codex/verify_codex_output.py
```

Выявит: слишком короткие summary (< 800 chars), отсутствующие answer_blocks, byline utечки в тексте, invalid atom_type, не-6 answer_blocks, < 3 references. Fix-ай найденное до того как коммитить.

### Шаг 4: Commit в `data-pipeline`

```bash
cd D:\ticket-exam-trainer-data
git add build/codex_output/ scripts/codex/
git commit -m "feat(seed): cloud-LLM structured output for 208 tickets

Generated via Codex over raw-tickets extract from PDF. Each ticket has
canonical_answer_summary, 4-8 atoms, 6 answer_blocks (госпрофиль),
3-5 reference_theses for runtime reviewer. Section metadata parsed.

Output: build/codex_output/structured_tickets.json (~X MB)
Verification passed: scripts/codex/verify_codex_output.py"
```

Координатор проверит и inкrement-но доведёт до SQLite seed (отдельным коммитом).

---

## Что НЕ делай

- **Не пиши в SQLite напрямую.** Только JSON. Координатор отдельно делает SQLite import.
- **Не переписывай** `infrastructure/importers/` код. Твоя работа — заменяет его LLM-refinement pass, но pre-processing (byline, tokenizer, TOC, normalizers) остаётся pure Python и обрабатывается separately — см. Task 1-5 плана W1.
- **Не трогай `ui/` и `ui_flet/`.** Чужая территория (W2 agent).
- **Не меняй `domain/models.py`** самостоятельно. Если нужен новый field — сначала договорись с координатором.

## Если застрял

- Какой-то билет в raw_content слишком короткий/битый → `warnings: ["source_fragmented"]`, generate best-effort от title
- Не понимаешь структуру раздела → пропиши только `section.title` из прямого парсинга, остальное null
- 208 билетов — большой объём, не хватает контекстного окна → обработай батчами по 10, каждый как отдельный call, merge результаты

## Вопросы координатору

Если после прочтения этого brief + исходного spec есть unclear points — не гадай, спрашивай через commit с `docs/superpowers/handoffs/codex-questions.md` и останавливайся. Координатор ответит и ты продолжишь.
