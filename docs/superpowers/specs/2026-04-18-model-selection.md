# Review Engine Model Selection — R0 Validation Results

**Date:** 2026-04-18
**Models tested:** qwen3:0.6b, qwen3:1.7b, qwen3:8b (qwen3:4b недоступна локально, отложена)
**Corpus:** 5 билетов × 5 студенческих ответов (отличный → пустой)
**Raw data:** [2026-04-18-model-selection-raw.json](2026-04-18-model-selection-raw.json)
**Script:** `scripts/r0/validate_review_engine.py`
**Fixtures:** `tests/fixtures/review_validation/`

---

## TL;DR

**Default tier для установщика: qwen3:8b.** Единственная модель, которая реально различает качество ответа. Платим за это скоростью (50-130 сек/рецензия на CPU) и 2/5 failure rate (timeout + parse error).

**Fallback для слабого железа: qwen3:0.6b** с чётким labelом в UI: *«Упрощённая рецензия: проверяет структуру, но не глубину ответа».*

**qwen3:1.7b — не использовать.** Для текущего промпта возвращает `{}` — известный issue `format=json` на этой модели.

**Критичная follow-up задача для W1:** переписать `review_prompt()` — на русском, с few-shot, с chain-of-thought, разбить reference_theses на несколько тезисов. Ожидается, что после этого 1.7b и 4b станут viable как default, снизив требования к железу.

---

## Results summary

| Model | Size | OK rate | Avg latency | JSON valid | Quality discrimination |
|-------|------|---------|-------------|------------|----------------------|
| qwen3:0.6b | ~600 МБ | **5/5** | **18.5 sec** | 5/5 | ❌ Always «covered/100» |
| qwen3:1.7b | ~1.5 ГБ | 5/5 | 9.8 sec | 5/5 | ❌ Returns `{}` — нет содержания |
| qwen3:8b | ~5 ГБ | 3/5 | 96.7 sec | 3/5 | ✅ Реально оценивает |

---

## Detailed analysis

### qwen3:0.6b — too agreeable

JSON-структура идеальная. Поля `thesis_verdicts`, `overall_score`, `overall_comment` заполнены. Но:

```
Answer 1 (excellent): verdicts=['covered', 'covered', 'covered'], score=100
Answer 2 (good with gaps): verdicts=['covered'], score=100
Answer 3 (mediocre, half theses): verdicts=['covered'], score=100
Answer 4 (weak, 1-2 sentences): verdicts=['covered'], score=100
Answer 5 (1 line, essentially empty): verdicts=['covered'], score=100
```

Модель не различает качество. Всё — «covered», все — 100%. Классическая проблема маленьких моделей: они слишком «дружелюбные», не умеют жёстко критиковать. Ещё хуже — система-промпт на английском; 0.6b очень ограниченно переключает язык, и инструкция «be strict» теряется.

**Вердикт:** технически работает, но как educational tool бесполезен. Для UX — хуже чем ничего.

### qwen3:1.7b — broken format=json

```
Ticket 1: text = '{}'
Ticket 2: text = '{}'
Ticket 3: text = '{}'
Ticket 4: text = '{}'
Ticket 5: text = '{}'
```

Все 5 ответов — пустой объект. Это известный issue qwen3 на уровне 1.7B с `format=json`: модель трактует JSON-mode как «верни минимальный валидный JSON» и отдаёт `{}`.

**Диагноз:** требуется либо другой подход (без `format=json`, с парсингом JSON из response после instruct-prompt «Return only JSON object with ...»), либо прошивка 1.7b не подходит для нашего use case.

**Вердикт:** не использовать до редизайна промпта.

### qwen3:8b — slow but real

```
Ticket 1: FAIL (unterminated string, 79 sec) — JSON обрезан на 262 символе, парсится
Ticket 2: OK (2348 chars, 129 sec)
Ticket 3: FAIL (read timeout 180 sec)
Ticket 4: OK (742 chars, 49 sec)
Ticket 5: OK (612 chars, 43 sec)
```

Когда работает — реально оценивает качество:
- На ticket 2 (хороший ответ): подробная рецензия, разбор классификации доходов/расходов
- На более короткие ответы: более коротких рецензий (сам модель шкалирует глубину)

Проблемы:
- **2/5 failures.** Один timeout (просто не ответил за 180 сек на сложном запросе), один parse error (обрезал JSON).
- **Медленный.** Средне ~97 сек, медиана ~80 сек. На CPU — ощутимое ожидание.

**Вердикт:** единственная жизнеспособная опция для default, но с оговорками.

---

## Decision

### Default tier в установщике

**qwen3:8b** — только на машинах с RAM ≥ 16 ГБ и/или дискретной GPU. С dedicated NVIDIA 6+ ГБ VRAM: ~15-30 сек на рецензию.

### Тиры в установщике

| Тир | Модель | Условие | Время | UX-метка |
|-----|--------|---------|-------|----------|
| **Лёгкий** | qwen3:0.6b | RAM < 8 ГБ, CPU-only | ~20 сек | «Упрощённая рецензия — структура ответа, без глубокой оценки» |
| **Рекомендованный** | qwen3:8b | RAM 16+ ГБ, желательно GPU | 15-90 сек | «Полноценный рецензент» |
| **Полный** | qwen3:8b | RAM 16+ ГБ + dedicated GPU ≥ 8 ГБ VRAM | 10-25 сек | «Быстрый и полный рецензент» |

**qwen3:1.7b и qwen3:4b** — не предлагать в wizard-е до исправления промпта в W1.

### Обработка ошибок в клиенте

- Per-call timeout 180 сек (текущий).
- Retry на parse error — 1 раз с уменьшенной температурой (0.1 → 0.05).
- На повторный fail — показывать пользователю: «Рецензент не ответил на этот билет. Попробуйте повторить или упростите ответ.»

---

## Critical Follow-Up Work

### For W1 Agent (Data Pipeline Workstream)

**Новая задача W1 (добавить в план):** Rewrite `infrastructure/ollama/prompts.py::review_prompt()`:

1. Translate system prompt to Russian
2. Add 2 few-shot examples (one covered, one missing)
3. Add explicit chain-of-thought instruction: «Сначала опиши по порядку, какие тезисы раскрыты студентом; потом вынеси вердикт и только после этого — JSON»
4. Split reference_theses into multiple items (3-5 тезисов на билет) — требует интеграции с `application/answer_block_builder.py` или отдельной генерации theses LLM-ом до rewiev-вызова
5. Добавить explicit rubric: «`missing` — студент ни разу не упомянул эту концепцию. `partial` — упомянул но без глубины / без примеров / кратко.»

После rewrite — повторить R0 validation на том же корпусе. Ожидание: 1.7b и 4b станут viable default, 0.6b перестанет говорить «covered» на пустых ответах.

Это изменяет [frozen interface plan](../plans/2026-04-18-w1-data-pipeline.md) — добавьте Task 7.5 или расширьте Task 6 (Answer Blocks Generator) сценой «also regenerate reference theses for review».

### For W3 Agent (Installer Workstream)

Использовать качественную валидацию при installer-canary:
- После `ollama pull <model>`, вызвать review_answer на fixture из tests/fixtures/review_validation
- Если модель 0.6b → проверить валидный JSON + показать честный warning
- Если модель 8b → проверить валидный JSON + discrimination (ticket 1 excellent ≠ ticket 5 empty в overall_score)
- При несоответствии → пометить установку как "degraded" и подсказать upgrade до 8b

---

## Dataset Details

### Тикеты (v1 seed)

| # | Ticket Title | Content length |
|---|-------------|----------------|
| 1 | Системный анализ управленческих проблем | ~2500 chars |
| 2 | Бюджетное устройство РФ: классификация и процесс | ~3000 chars |
| 3 | Содержание и структура государственного бюджета | ~2800 chars |
| 4 | Национальный проект «Цифровая экономика» | ~2000 chars |
| 5 | Становление теории государственного управления | ~2600 chars |

### Ответы студентов

| # | Quality | Length | Descriptor |
|---|---------|--------|-----------|
| 1 | Отличный | ~1800 chars | Полный структурированный ответ с терминологией |
| 2 | Хороший с пропусками | ~1100 chars | Основные тезисы, поверхностно на деталях |
| 3 | Средний | ~450 chars | Половина тезисов, без примеров |
| 4 | Слабый | ~170 chars | 1 предложение, общие слова |
| 5 | Почти пустой | ~70 chars | 1 строка, фактически ни о чём |

---

## Status Log

- **2026-04-18:** R0 validation прогнан. qwen3:8b выбран default-ом с caveats. 1.7b помечен как broken для текущего промпта. W1 получает follow-up задачу на rewrite промпта + повторную валидацию.
