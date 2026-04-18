# Review Engine — Model Research (январь 2026)

**Дата:** 2026-04-19
**Статус:** research-документ, входные данные для spec update и W1-rewrite промпта.
**Автор:** research pass по состоянию Ollama-каталога на январь 2026.
**Предыдущий артефакт:** `2026-04-18-model-selection.md` (R0 по qwen3 family).

> Все оценки явно маркированы:
> - **[empirical]** — подтверждено R0 или публичной замеренной бенчмаркой на CPU.
> - **[benchmarks]** — по отчётам MERA / MT-Bench / RuMTEB / RussianSuperGLUE / авторские README.
> - **[предположение]** — экстраполяция из размера, архитектуры, соседних моделей.
> - **[неуверенно]** — данных мало, стоит валидировать вручную.

---

## 1. Топ-5 кандидатов

Контекст задачи: **review_answer** — прочитать 2-6 абзацев русского текста + ≤5 reference-тезисов, выдать structured JSON с verdicts и overall_score 0-100. Главные критерии: (a) реально различает качество ответов (не всё «covered/100»), (b) держит structured JSON на Ollama с `format=json`, (c) русский на уровне instruct, (d) укладывается в 5 GB RAM и <60 сек на 8-core CPU.

| # | Модель (Ollama tag) | Размер (диск / RAM) | RU-качество | JSON надёжность | CPU speed (400 tok) | Дискриминация | Слабые места |
|---|---|---|---|---|---|---|---|
| 1 | **`qwen2.5:7b-instruct-q4_K_M`** | 4.7 GB / ~5.5 GB | Хороший **[benchmarks]** — MERA tier выше llama3.1-8b; качественный instruction-following на RU. | Надёжный с `format=json`; структурирует по схеме лучше qwen3-4b/8b **[benchmarks]** | ~25-45 сек **[предположение]** — 7B q4 на i5 gen11 даёт 6-9 tok/sec | Хорошая **[предположение]** — 7B instruct обычно разделяет qualitites; требует явной рубрики в промпте. | Русский слабее чем у Vikhr; JSON иногда лишние поля если промпт неплотный. |
| 2 | **`vikhr-nemo:12b-instruct-q4_K_M`** (Vikhrmodels/Vikhr-Nemo-12B-Instruct-R-21-09-24) | ~7 GB / ~8.5 GB | **Лучший RU** в классе **[benchmarks]** — MERA top-3 для open-source <14B; специально тюнен для русского reasoning. | Хорошая **[benchmarks]** — тренированы на structured outputs; JSON-mode стабильный. | ~35-60 сек **[предположение]** — 12B q4 на 8-core CPU даёт 4-6 tok/sec, на edge бюджета. | **Ожидается сильная [предположение]** — тюнен на RU-рубриках; корректно работает с few-shot. | Выходит за RAM budget ≤5 GB — подходит только Premium тиру. Ollama-tag доступен, но проверить: `ollama pull vikhr-nemo-12b-instruct-r` или `evilfreelancer/vikhr-nemo-12b-instruct`. |
| 3 | **`qwen3:4b-instruct-q4_K_M`** (или `qwen3:4b` instruct режим) | ~2.6 GB / ~3.5 GB | Средне-хороший **[benchmarks]** — qwen3 multilingual, но 4B просаживается на nuanced RU critique. | Ожидается улучшение vs 1.7b **[предположение]** — 4B обычно не коллапсирует в `{}` при `format=json`. **Не тестировалось локально**. | ~15-30 сек **[предположение]** — 4B q4 даёт 10-14 tok/sec. | Ожидается умеренная **[неуверенно]** — при русском промпте + few-shot должна различать; при английском промпте — риск повторить паттерн 0.6b («covered/100»). | Не тестирована локально; риск «too agreeable» как у 0.6b при английском промпте. **Обязательно валидировать после W1 rewrite промпта.** |
| 4 | **`gemma3:4b-it-q4_K_M`** | ~3 GB / ~4 GB | Средний RU **[benchmarks]** — Gemma3 сильнее Gemma2 на RU, но уступает qwen2.5 и Vikhr. | **Слабое место [benchmarks]** — Gemma family известна тем, что хуже держит strict JSON, чаще добавляет markdown/префиксы. | ~18-35 сек **[предположение]** — 4B q4 sweet spot. | Средне **[предположение]** — 4B обычно не даёт честной дискриминации без CoT. | Основной риск — JSON форматирование; надо явно тестировать `format=json` совместимость. |
| 5 | **`t-lite:7b-instruct`** (T-Bank T-lite — или `saiga-mistral:7b` как RU-fallback) | ~4.5 GB / ~5.5 GB | **Отличный RU [benchmarks]** — T-lite MERA top-5, Saiga — специфический RU-тюн Mistral. | Умеренная **[неуверенно]** — оба не специально тренированы на JSON; нужен явный instruct. | ~25-45 сек **[предположение]** — 7B q4. | Ожидается хорошая на critique **[предположение]** — RU-тюны обычно чувствительнее к nuance. | Доступность в Ollama неоднозначная: T-lite публиковался как GGUF через HuggingFace, Ollama-tag может потребовать `ollama pull evilfreelancer/t-lite-instruct-0.1:q4_K_M` или ручной import. Saiga — по тому же паттерну. **Проверить доступность pull-ом на чистом Ollama 0.x до комита.** |

### Кандидаты, которые я бы **исключил**

- **`qwen3:0.6b` / `qwen3:1.7b`** — R0 доказал непригодность **[empirical]**: слишком маленькие, не критикуют или коллапсируют в `{}`.
- **`llama3.2:3b-instruct`** — слабый RU **[benchmarks]**, плюс известные проблемы с JSON после 3B уровня. Использовать только если ничего другого не помещается.
- **`llama3.1:8b-instruct`** — средний RU **[benchmarks]**, 8B без spec-тюна проигрывает qwen2.5:7b на RU. Излишен если есть qwen2.5:7b.
- **`mistral:7b-instruct` (v0.3 / Nemo 12B stock)** — RU средний **[benchmarks]**, на EXAM-review будет уступать Vikhr-Nemo (это и есть его RU-тюн).
- **`phi4:14b`** — отличный reasoning **[benchmarks]**, но ~9 GB RAM и 60-120 сек на CPU → выходит за budget. Premium-only, но Vikhr-Nemo-12B даёт лучший RU за тот же price point.
- **`yi:9b`** — RU слабый **[benchmarks]**, оптимизирован под китайский/английский.
- **`gemma3:12b-instruct`** — альтернатива Vikhr-Nemo, но RU слабее и JSON риск.

---

## 2. Рекомендация по тирам установщика

### Light (4-8 GB RAM, CPU-only, ≤20 сек) — **не делать полноценный review**

**Честная рекомендация:** на этом железе structured review от LLM будет либо бесполезен (0.6b/1.7b), либо слишком медленным (4b на слабом CPU может дать 40+ сек). **Отказаться от LLM-review на Light-тире.**

Вместо этого:
- **Keyword-fallback** (детерминированный, без LLM): для каждого reference-тезиса проверить keywords из `thesis.keywords` в answer — отметить `covered`/`missing`. `partial` не поддерживать (нет сигнала).
- Overall score = доля covered × 100.
- В UI метка: **«Базовая проверка тезисов (без LLM). Для полной рецензии установите Recommended модель.»**
- Можно параллельно держать **`qwen3:4b-instruct-q4_K_M`** как опциональный add-on для пользователей, готовых ждать 30-40 сек — но не по умолчанию.

### Recommended default (8-16 GB RAM, CPU-only, ≤60 сек) — **`qwen2.5:7b-instruct-q4_K_M`**

**Обоснование [benchmarks + предположение]:**
- RU на уровне MERA-top, инструкт-качество выше llama3.1:8b и qwen3:4b.
- q4_K_M — ~4.7 GB диска, ~5-5.5 GB RAM в работе — в budget.
- 25-45 сек на 400-токенный review на i5 gen11 — укладывается в UX-бюджет.
- Structured JSON с `format=json` держит надёжно (есть публичные кейсы).
- **Ключевая замена для qwen3:8b как default** — быстрее в 2-3 раза, в 2 раза меньше по RAM, при сравнимом (или лучшем) RU-качестве.

Fallback внутри тира: **`qwen3:4b-instruct`** как «lite default» если qwen2.5:7b не влезает (RAM < 8 GB measured).

### Premium (16+ GB RAM, GPU 8+ GB VRAM или сильный CPU) — **`vikhr-nemo:12b-instruct-q4_K_M`**

**Обоснование [benchmarks]:**
- Лучший доступный RU в open-source на январь 2026 в классе до 14B.
- Специализирован под русский critique и structured output.
- На GPU 8+ GB — 10-20 сек. На сильном CPU (Ryzen 7 7000 / i7 13-го поколения) — 30-50 сек.
- Если Vikhr-Nemo Ollama-tag не доступен сразу — fallback на **`qwen2.5:14b-instruct-q4_K_M`** (~8 GB). Не так хорош на RU, но официальный и стабильный.

---

## 3. Промпт-паттерн для усиления дискриминации (для 4-7B)

**Главный принцип:** 4-7B модели по умолчанию too agreeable. Нужно явно заставить их **искать плохое**.

Рекомендую **комбинацию трёх приёмов** в одном промпте:

1. **Русский system-промпт с explicit rubric**. Английский system вместе с русским user сбивает 4B-модели (см. R0 qwen3:0.6b). Рубрика должна быть жёсткая:
   - `missing` — тезис не упомянут или упомянут термином без раскрытия.
   - `partial` — упомянут концептуально, но без примеров / без определения / в одном предложении.
   - `covered` — раскрыт минимум на 2-3 предложения с примером или определением.
   - Score rubric: 90-100 только при всех covered + структурой; 60-80 средне; <50 если 2+ missing.

2. **Few-shot: один excellent + один weak**. Даёт модели calibration. Без него 4B тянет всё к «covered». Примеры должны быть короткие (~300 chars answer + 150 chars expected verdict JSON) чтобы не раздувать контекст.

3. **Chain-of-thought до JSON** — **в одном проходе**, не в двух. Два прохода на CPU удваивают latency. Паттерн:
   ```
   Сначала внутри тэгов <reasoning>...</reasoning> кратко (3-5 предложений)
   перечисли, что из reference theses реально есть в ответе и чего нет.
   После </reasoning> верни ТОЛЬКО валидный JSON-объект.
   ```
   При `format=json` в Ollama теги `<reasoning>` уйдут в «thinking» область, а на выходе будет чистый JSON. **[неуверенно]** — поведение `format=json` с pre-JSON reasoning зависит от версии Ollama (0.3.x+ терпят, 0.2.x могут обрезать). **Валидировать.**

4. **Анти-паттерн, которого избегать:** просить `format=json` + «be strict» без few-shot. R0 показал, что 0.6b/1.7b игнорируют «strict» — только примеры их сбивают.

---

## 4. Минимальный testplan до коммита на модель

**Корпус:** existing R0 fixtures (5 билетов × 5 answers: excellent / good / mediocre / weak / empty) — уже в `tests/fixtures/review_validation/`. Расширить до 5 × 6, добавив **«wrong answer»** (ответ не по теме билета — проверка false-covered).

**Шаги:**

1. **Прогнать 4 модели × 30 ответов × 3 прогона** = 360 вызовов: `qwen2.5:7b-instruct`, `qwen3:4b-instruct`, `gemma3:4b-it`, `vikhr-nemo:12b-instruct` (если доступна). 3 прогона — чтобы поймать нестабильность (температура 0.1).
2. **Измерить по 4 метрикам**: (a) JSON-valid rate, (b) schema-valid rate (все обязательные поля), (c) latency p50/p95, (d) **discrimination score** = `|overall_score(excellent) − overall_score(empty)|` — цель ≥50 пунктов.
3. **Качественная рубрика вручную** на 30 ответах: для каждого verdict — «согласен / не согласен» (inter-rater с одним ревьюером достаточно для R0). Цель: ≥70% agreement с human judge на 7b+ моделях.
4. **Отдельный sanity-тест: «wrong answer»**. Модель должна вернуть overall_score ≤30 и хотя бы 2 `missing` verdicts. Это ловит too-agreeable failure mode.
5. **RAM и диск**: замерить pull-size (Ollama) и peak RSS во время review через `psutil`. Записать в таблицу.
6. **Прогон на референсном ноуте классмейта** (i5 gen11, 8 GB RAM, без GPU) минимум на top-2 кандидатах — синтетика на разработческой машине врёт в 1.5-2 раза.
7. **Опционально: canary после pull в установщике.** Один fixture-вызов review_answer на свежеустановленной модели, проверка (a) JSON valid, (b) discrimination между excellent и empty ответом. Если не проходит — отметить установку degraded.

---

## Вывод одной фразой

**Отказаться от qwen3:8b как default.** Перейти на `qwen2.5:7b-instruct-q4_K_M` (default) + `vikhr-nemo:12b-instruct` (premium) + keyword-fallback без LLM (light). Параллельно в W1 переписать промпт (русский system, rubric, 1+1 few-shot, single-pass CoT), без этого ни одна 4-7B модель нормальную дискриминацию не даст.
