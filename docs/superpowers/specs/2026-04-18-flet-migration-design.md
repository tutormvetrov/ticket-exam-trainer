# Flet Migration Design — v2.0 (Flet-only, обновление 2026-04-19)

> Status: scope сужен после завершения data-pipeline. Актуальный план — миграция на Flet, 3 экрана, 6 evidence-based тренировочных режимов. Установщик Ollama и macOS-сборка вынесены в secondary.

**Дата создания:** 2026-04-18
**Последнее обновление:** 2026-04-19 — сокращён scope (см. Status Log внизу)
**Цель:** заменить PySide6/Qt UI на Flet (Flutter engine), сохранив весь `application/infrastructure/domain` слой без изменений. Уменьшить UI до минимума, необходимого для реальной подготовки к письменному госэкзамену ГМУ.

---

## 1. Motivation

Data-слой закрыт на ветке `data-pipeline` (коммиты `c277286`, `fcd7d8a`): все 208 билетов имеют структурированный контент (159 из PDF, 49 сгенерированы по шаблону «отлично» с нормативной базой), собрана seed DB `build/demo_seed/state_exam_public_admin_demo.db`, `scripts/verify_state_exam_seed.py` проходит end-to-end (training snapshot + attempts + block scores + review verdict persist). Миграция базы или расширение схемы не требуется.

Остаётся UI-задача: Qt v1.2.x работает, но:
- кастомный QSS-набор («folio/atelier/paper») дорог в поддержке;
- dark theme отсутствует;
- responsive требует ручного `resizeEvent`;
- QPainter custom-drawings дают warning storms.

Переход на Flet упрощает поддержку (Material 3 defaults + warm tokens), даёт готовую dark theme и responsive без ручной работы. Одновременно режем scope до 3 экранов — для письменного экзамена не нужны Library, Import, Knowledge Map, Dialogue, Defense DLC, Statistics как отдельный экран.

## 2. Decisions

| Параметр | Выбор | Отклонённые варианты и почему |
|---|---|---|
| UI-стек | **Flet (Flutter engine), Python 3.12** | PySide6 (оставляем как fallback до финальной приёмки), web-фреймворк (нет офлайн desktop-feel) |
| Scope экранов | **3** — Tickets, Training, Settings | 6 из v1.2.x (Library/Import/Statistics/Dialogue/Knowledge Map) — режем, т.к. seed финальный, второго не предвидится |
| Тренировочные режимы | **6 evidence-based** — `reading` → `plan` → `cloze` → `active-recall` → `state-exam-full` → `review` (см. часть 4) | 8 режимов из v1.2.x (matching, mini-exam, dialogue) — режем, дублируют существующие или неприменимы к письменному экзамену |
| LLM-стратегия | **Локальная Ollama, опциональная** | Cloud — запрещён product spec; обязательная Ollama — создаёт барьер входа для классмейтов со слабым железом |
| Рецензент-движок | **qwen2.5:7b-instruct как default, vikhr-nemo:12b как premium, keyword-fallback для слабых машин и без Ollama** (обновлено 2026-04-19 после research в `docs/superpowers/specs/2026-04-19-review-model-research.md`) | qwen3:8b слишком медленный на CPU (50-130с, 2/5 timeout), qwen3:1.7b returns `{}`, qwen3:0.6b всем ставит «covered/100» (честнее keyword-fallback). Требует промпт-rewrite (RU + few-shot + CoT). |
| Визуал | **Warm tokens + Material 3**, light+dark, responsive 1024-3840+ | Minimum (Material 3 defaults) — пользователь запретил; премиум storybook — не окупается за 3 недели |
| Data pipeline | **Закрыт, merge в main после UI-приёмки** | Переход к W1 заново не требуется — база готова |
| Установщик Ollama | **Secondary**: ручная инструкция в README + опциональный wizard если время остаётся | Обязательный wizard как в v1 — тянет +15 часов, не критичен (app работает на fallback без LLM) |
| Ship-дата | **10-12 мая 2026** — для классмейтов к письменному госэкзамену 13 мая | без дедлайна — отказ от обязательства перед однокурсниками |

## 3. Strategy

W1 (data) закрыт. Остаются W2 (Flet UI, primary) и W3 (packaging + optional installer, secondary). Работают последовательно в ветке `flet-migration` от тэга `v1.2.0`.

Параллелизма больше не требуется: один разработчик, 21-23 рабочих дня до ship-даты.

Frozen interface между слоями сохраняется: `application/facade.py`, `application/ui_data.py`, `domain/models.py`, `infrastructure/db/schema.py`. Flet-слой потребляет только эти контракты.

Fallback-план: если `flet pack` не собирает exe за 3 дня — собираем Qt v1.2.x с обновлённой seed DB как promise-minimum для классмейтов, Flet-версия остаётся в dev.

---

## Часть 1: Архитектура и границы

### 1.1 Layered architecture (без изменений)

```
app/              bootstrap, paths, platform
application/      use cases, facade, services       ← frozen
domain/           entities, value objects            ← frozen
infrastructure/   SQLite, Ollama, importers          ← frozen
ui/               PySide6 (legacy, fallback)         ← заморожен, удаляется после приёмки v2.0
ui_flet/          Flet (new)                         ← создаётся
scripts/          build, setup, packaging            ← меняется минимально (build_flet_exe)
```

### 1.2 Workstreams (упрощены)

| Stream | Branch | Фокус | Основные файлы |
|--------|--------|-------|----------------|
| **W1: Data pipeline** ✅ DONE | `data-pipeline` → будет merge в main | снапшот в Часть 2 | `scripts/codex/`, `build/codex_output/structured_tickets.json`, `build/demo_seed/state_exam_public_admin_demo.db` |
| **W2: Flet UI** (primary) | `flet-migration` | новый пакет `ui_flet/`, 3 экрана, 6 training workspaces, компоненты, темы | `ui_flet/`, `pyproject.toml`, `requirements.txt` |
| **W3: Packaging & (опционально) installer** | `flet-migration` (совмещается с W2) | `flet pack`, zip-дистрибутив, README; Ollama-wizard только если остаётся время | `scripts/build_flet_exe.ps1`, `scripts/package_release.ps1`, `scripts/install_ollama_wizard.ps1` (опц.) |

### 1.3 Frozen interface

Не меняется без явного согласования:

- `application/facade.py` — публичный `AppFacade`
- `application/ui_data.py` — dataclass-формы `Ticket`, `Atom`, `AnswerBlock`, `TrainingEvaluationResult`, `ReviewVerdict`, `ThesisVerdict`
- `application/ui_query_service.py` — read-only проекции
- `domain/models.py`, `domain/answer_profile.py`, `domain/knowledge.py`
- `infrastructure/db/schema.py` — only add-column миграции

### 1.4 Branch strategy (обновлено)

```
main (v1.2.0)  ← base для всех работ
  └─ data-pipeline  (W1)  → merge в main после приёмки UI
  └─ flet-migration (W2+W3) → merge в main → tag v2.0.0
```

Worktree `D:\ticket-exam-trainer-data` (для data) остаётся до финального merge. Worktree для `flet-migration` создаётся при старте W2.

---

## Часть 2: Data Pipeline — DONE (snapshot)

Ниже — зафиксированное состояние. Возврат к этой части не планируется.

### 2.1 Сделанные правки

1. **Полный PDF-экстрактор** (`scripts/codex/extract_pdf_tickets.py`) — парсит 208 маркеров `● (N) M. Title` из `МДЭ_ГА_2024_Кол_Конспект_ГМУ_ГАРФ_18_02_2025_в_2.pdf`, 839K символов содержания, 26 подразделов с ФИО преподавателей. Заменил лоссовую seed-v1 экстракцию.
2. **Упаковщик PDF-контента** (`scripts/codex/package_pdf_tickets.py`) — byline strip (включая `(ИЗ ПРЕЗЕНТАЦИИ)` и паттерны без закрывающей скобки), page-number strip, split по абзацам в атомы, извлечение тезисов по границам предложений.
3. **Генерация ненаписанных билетов** — 49 билетов, для которых в оригинальном коллективном конспекте студенты не дописали ответы, сгенерированы по структуре «отлично на МДЭ ГМУ» (Введение / Теория / Практика / Навыки / Заключение / Дополнительные). Нормативная база проставлена: Конституция РФ (ст. 5/7/12), ФЗ № 131, № 79, № 248, № 273 и др.
4. **Merge + verify** — `scripts/codex/merge_batches.py` собирает `build/codex_output/structured_tickets.json` (208 tickets, 3.7 MB), `scripts/codex/verify_codex_output.py` проверяет инварианты (byline, atom enum, 6 answer_blocks, 3-5 theses 80-300 chars) — 208/208 pass.
5. **Import в SQLite** (`scripts/codex/import_to_seed_db.py`) — JSON → `build/demo_seed/state_exam_public_admin_demo.db` (8.2 MB). Все 208 билетов с `answer_profile_code = state_exam_public_admin`. Для PDF-билетов атомы распределены по 6 блокам по типу (definition/features → theory, mechanism → practice, classification → skills, example → extra, consequence/context → intro/conclusion) — это гарантирует не-пустой `_extract_reference_theses` в scoring.
6. **End-to-end verify** — `scripts/verify_state_exam_seed.py`: загрузка ticket maps → training snapshot → evaluate_answer в режимах active-recall, plan, state-exam-full → review verdict + block scores + persist attempts. Все зелёные.

### 2.2 Артефакты

- `build/codex_input/raw_tickets.json` (1.6 MB) — PDF extract
- `build/codex_output/structured_tickets.json` (3.7 MB) — структурированные билеты
- `build/demo_seed/state_exam_public_admin_demo.db` (8.2 MB) — seed DB для дистрибутива
- `scripts/codex/*.py` — одноразовые CLI-скрипты (не runtime)

Эти артефакты коммичены в `data-pipeline`, будут merge в main после приёмки UI.

---

## Часть 3: Flet UI (W2) — упрощённый скоуп

### 3.1 Структура пакета

```
ui_flet/
  __init__.py
  main.py                        # python -m ui_flet.main
  state.py                       # AppState, breakpoint signal, theme signal
  router.py                      # page.on_route_change — 3 роута
  theme/
    tokens.py                    # COLOR, TYPE, SPACE, RADIUS (warm tokens)
    fonts.py                     # Lora, Golos Text, JetBrains Mono (TTF bundled)
    theme.py                     # build_theme(brightness) -> ft.ThemeData
    fonts/                       # bundled TTF
  components/
    top_bar.py                   # серифный заголовок + chip-навигация + theme switcher
    ticket_card.py
    chip.py
    ollama_status_badge.py
    review_verdict_widget.py     # per-thesis verdict display
    training_workspace_base.py   # база для 6 режимов
    empty_state.py
    timer_widget.py              # для state-exam-full + active-recall
  views/
    tickets_view.py              # каталог 208 билетов, фильтры, выбор
    training_view.py             # хост для 6 workspace-ов, контекст билета
    settings_view.py             # тема, шрифт, модель Ollama
  workspaces/
    reading_workspace.py
    plan_workspace.py
    cloze_workspace.py
    active_recall_workspace.py
    state_exam_full_workspace.py
    review_workspace.py
  i18n/
    ru.py
  _dev/
    storybook.py
```

**Уменьшения по сравнению с v1 scope:**
- `library_view.py`, `import_view.py`, `statistics_view.py` — удалены. Библиотека не нужна (один seed). Импорт не нужен (финальный контент). Статистика — встроена как правая панель в `tickets_view.py` (прогресс по билетам, overall readiness gauge).
- `sidebar.py` как тяжёлый компонент не нужен: 3 экрана → chip-навигация в TopBar.

### 3.2 Theme tokens (без изменений от v1 спека)

Warm palette для Material 3 адаптации:

```python
# ui_flet/theme/tokens.py
COLOR_LIGHT = {
    "bg_base":        "#F3E8D2",  # sand paper
    "bg_surface":     "#FBF4E4",  # parchment
    "bg_elevated":    "#FFFBF0",
    "accent":         "#A94434",  # rust
    "accent_soft":    "#E8C9BF",
    "text_primary":   "#2B1F17",
    "text_secondary": "#6B5A4A",
    "border_soft":    "#E3D4B5",
    "success":        "#5B8A3A",  # moss
    "warning":        "#C68B2E",
    "danger":         "#A94434",
}
COLOR_DARK = {
    "bg_base":        "#241811",  # dark cognac
    "bg_surface":     "#2E1F16",
    "bg_elevated":    "#3A2A1E",
    "accent":         "#D9735E",  # desaturated rust
    "accent_soft":    "#4A2820",
    "text_primary":   "#F3E8D2",
    "text_secondary": "#C9B68F",
    "border_soft":    "#3D2C1F",
    "success":        "#8EB266",
    "warning":        "#D9A857",
    "danger":         "#D9735E",
}

TYPE = {
    "display":     {"family": "Lora", "size": 32, "weight": "w600"},
    "h1":          {"family": "Lora", "size": 26, "weight": "w600"},
    "h2":          {"family": "Lora", "size": 20, "weight": "w600"},
    "h3":          {"family": "Golos Text", "size": 16, "weight": "w600"},
    "body":        {"family": "Golos Text", "size": 14, "weight": "w400"},
    "body_strong": {"family": "Golos Text", "size": 14, "weight": "w600"},
    "caption":     {"family": "Golos Text", "size": 12, "weight": "w400"},
    "mono":        {"family": "JetBrains Mono", "size": 12, "weight": "w400"},
}

SPACE  = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 48}
RADIUS = {"sm": 6, "md": 10, "lg": 14, "xl": 20, "pill": 999}
```

### 3.3 Responsive behavior (обновлено 2026-04-19)

**Fullscreen-first.** Приложение открывается в **полноэкранном режиме** по умолчанию (`page.window.full_screen = True`). В Settings → «Режим окна» — переключатель «Полноэкранный / Оконный». Для полноэкранного скрывать window chrome (в рамках возможностей Flet + Windows). Выход из fullscreen — кнопка выхода в TopBar или `Esc` (стандартный хоткей).

**Целевые разрешения ноутбуков и ПК** (должны выглядеть без обрезаний / двойного скролла):

| Класс | Ширина | Примеры устройств | Layout |
|---|---|---|---|
| laptop-small | 1366×768 | бюджетные ноутбуки, старые 14" | 1 колонка + chip-навигация → popup-меню |
| laptop-standard | 1440×900 — 1536×864 | MacBook Air 13" (1440×900), многие 15" (1536×864) | 2 колонки (список 40% / деталь 60%) |
| laptop-hd | 1600×900 — 1920×1080 | 15-17" Windows ноуты, FullHD-мониторы | 2 колонки (35/65) + расширенный hero-блок деталей |
| desktop-wide | 2560×1440 | 27" QHD | 3 колонки (список / деталь / правая статистика) |
| 4k | 3840×2160+ | 4K мониторы | 3 колонки + `page.scale = 1.25` |

```python
BREAKPOINTS = {
    "laptop_small":    (0, 1400),      # 1366×768 и ниже
    "laptop_standard": (1400, 1700),   # 1440×900, 1536×864
    "laptop_hd":       (1700, 2200),   # 1600×900, 1920×1080
    "desktop_wide":    (2200, 3200),   # 2560×1440
    "4k":              (3200, None),   # 3840×2160+
}
```

Нижний порог — **1366×768** (ни один классмейтский ноут не должен оказаться вне scope). На `laptop_small` приоритет — читаемость полного текста билета при ответе: «Теория» и прочие многострочные поля раскрываются во всю ширину, сайдбар сворачивается в bottom sheet. На `desktop_wide+` появляется правая колонка с прогрессом, очередью повторений (FSRS) и mastery-картой.

**Acceptance для адаптива:** интерфейс снимается без обрезаний и двойных скроллов на каждом из 5 классов на реальной или VM-машине. `scripts/run_resolution_matrix.ps1` (если успеваем) делает серию скриншотов в offscreen-режиме для визуальной проверки.

### 3.4 Facade integration

Один instance `AppFacade` создаётся в `ui_flet/main.py`, передаётся во все views через `AppState`. Views делают только `state.facade.method(...)` — прямых обращений к `infrastructure/` нет.

### 3.5 Theme switching

`page.theme_mode = ft.ThemeMode.LIGHT / DARK` — переключатель в Settings. Все компоненты читают токены через `page.theme.color_scheme.*` — переключение без рестарта.

### 3.5a Window mode (обновлено 2026-04-19)

По умолчанию — `page.window.full_screen = True`. В Settings → «Режим окна»:
- **Полноэкранный** (по умолчанию) — приложение открывается во весь экран. Выход через кнопку в TopBar или `Esc`.
- **Оконный** — сохраняются размеры (`window.width/height/left/top`) в `settings.json` между запусками.

Сброс в полноэкранный — кнопка «Открыть на весь экран» в TopBar.

### 3.6 Deliverable W2

- Пакет `ui_flet/` с 8 компонентами, 3 views, 6 workspaces
- Light + Dark темы работают
- Responsive 1024-3840+ проверен на 3 breakpoints вручную
- Все UI-строки из `ui_flet/i18n/ru.py`
- Storybook `python -m ui_flet._dev.storybook`
- `python -m ui_flet.main` открывает приложение с seed DB из `build/demo_seed/`

---

## Часть 4: Тренировочные режимы (evidence-based research)

**Обоснование выбора.** Подбор режимов основан на:
- Dunlosky et al. 2013 «Improving Students' Learning With Effective Learning Techniques» (meta-review 10 методик с рейтингами high/moderate/low).
- Roediger & Karpicke 2006 «The Power of Testing Memory» (testing effect).
- Bjork «Desirable Difficulties» (transfer-appropriate processing).
- Bereiter & Scardamalia «Knowledge-transforming» (writing-to-learn).

**Критерий:** транзитивность методики к формату экзамена. Письменный экзамен требует написать развёрнутый ответ из памяти за ограниченное время — значит тренировки с максимально близким профилем (free recall, timed writing) имеют приоритет.

### 4.1 6 режимов в порядке знакомство → симуляция

| # | Mode key | Назначение | Input студента | Evidence (Dunlosky/Bjork) | Отображение эталона |
|---|---|---|---|---|---|
| 1 | `reading` | Первое знакомство с билетом | — (просмотр) | **Low** (Dunlosky) — но необходим как entry-point для нового билета | Полный `canonical_answer_summary` с разметкой атомов |
| 2 | `plan` | Восстановление 6-блочной структуры | Drag-to-order блоков и их тезисов | **Moderate** — тренирует macro-structure (Bereiter & Scardamalia) | После ответа: правильная структура |
| 3 | `cloze` | Закрепление формулировок, норм, дат | Fill-in-the-blank | **Moderate** для точных формулировок | Бинарная проверка по пропускам |
| 4 | `active-recall` | Cued retrieval с самопроверкой | Короткий свободный ответ (1-3 абзаца) по одному блоку или билету целиком | **High** (Dunlosky #1) — practice testing | Score + weak points + (опц.) LLM-review |
| 5 | `state-exam-full` | Полная симуляция экзамена | Текст в 6 полях по блокам, таймер 20-40 мин | **High** — максимальный transfer-appropriate processing | Block scores + criterion scores + thesis-level review verdict |
| 6 | `review` | Рецензирование готового ответа | Полный текст (свой прошлый ответ или чужой) | **High** — self-explanation по результатам retrieval | Per-thesis verdict (covered / partial / missing) + strengths + recommendations + overall score |

**Прогрессия:** студент проходит билет снизу-вверх по списку: `reading` → `plan` → `cloze` → `active-recall` → `state-exam-full` → `review`. Приложение предлагает следующий режим после успешного прохождения предыдущего (adaptive queue в Tickets view).

### 4.2 Интервальные повторения — ключевая фича v2.0 (обновлено 2026-04-19)

**Было в v1:** SM-2 в `application/adaptive_review.py` как фоновый механизм, без явной визуализации.

**Стало в v2.0:** FSRS (Free Spaced Repetition Scheduler) — первоклассная фича. По нашим оценкам это самая сильная сторона приложения для подготовки за 3-4 недели до экзамена: без него пользователь тренируется хаотично, с ним — идёт по оптимальному графику повторений с учётом собственных успехов.

**Почему FSRS, а не SM-2.** FSRS — современный ML-калиброванный алгоритм (Jarrett Ye, 2022+), открытый код, свободно используется Anki. На одинаковых логах показывает retention на 10-20% лучше SM-2 при той же нагрузке. Вход — три параметра на повторение: `grade (Again/Hard/Good/Easy)`, `time_elapsed`, `past_history`. Выход — `next_review_at`.

**Скоуп v2.0:**

1. **Миграция `application/adaptive_review.py` на FSRS.** Реализация `py-fsrs` (PyPI `fsrs`) в существующий `ReviewScheduler`. Контракт `next_review_at` остаётся, но формула меняется. Тесты `test_adaptive_review_edge_cases.py` обновить под новые интервалы.
2. **Mapping attempt → grade.** Из `TrainingEvaluationResult.score_percent`:
   - `state-exam-full`: ≥80 → Easy, 60-79 → Good, 40-59 → Hard, <40 → Again.
   - `active-recall`: ≥75 → Good, 50-74 → Hard, <50 → Again (нет Easy — слишком короткий формат).
   - `review` / `reading` / `cloze` / `plan` — не меняют интервалы (пассивные или вспомогательные режимы).
3. **Очередь повторений в Tickets view.** Правая панель на `laptop_hd+`: «Сегодня: N билетов», прогресс-бар по completion, список из 5-10 ближайших билетов с due-time. Клик открывает ticket + рекомендует следующий режим.
4. **Dashboard в Tickets view:** вверху слева plot «retention за 7/30 дней» + счётчик «билетов в активной ротации». На `laptop_small` — скрываемая секция, раскрывается по кнопке «Прогресс».
5. **Adaptive scheduling в меню билета:** кнопка «Начать тренировку» по умолчанию дёргает режим, который соответствует текущему состоянию билета по правилу:
   - новый билет → `reading`
   - был `reading`, но не было retention → `plan`
   - был `plan` → `cloze`
   - был `cloze` → `active-recall`
   - был `active-recall` с score ≥60 → `state-exam-full`
   - после `state-exam-full` — `review` при желании
   - после N дней без взаимодействия — FSRS отправляет в «overdue» с пометкой

**Interleaving** — параметр построения очереди дня: билеты мешаются из разных разделов (не «8 билетов подряд из Философии»).

**Out of scope v2.0:**
- Настройка параметров FSRS вручную (stability/difficulty) — используем рекомендованные defaults из `fsrs` пакета.
- Экспорт/импорт истории из Anki.

### 4.3 Отброшенные режимы

- `matching` — дублирует `cloze` без добавленной ценности
- `mini-exam` — дублирует `state-exam-full` без 6-блочной структуры
- `dialogue` — устный формат, не соответствует письменному экзамену (сохранён как Deferred v2.1)

### 4.4 Review engine — выбор модели (обновлено 2026-04-19)

R0 на qwen3-семействе показал: 0.6b всем ставит «covered/100», 1.7b возвращает `{}`, 8b реально различает но 50-130 сек на CPU и 2/5 таймаутят (см. `docs/superpowers/specs/2026-04-18-model-selection.md`). Второй раунд research (январь 2026, `docs/superpowers/specs/2026-04-19-review-model-research.md`) дал альтернативы на других семействах.

**Новая карта моделей для v2.0:**

| Тир | Модель | RAM | Диск | CPU 400 tok | RU | JSON | Назначение |
|---|---|---|---|---|---|---|---|
| Light | — (keyword fallback) | 0 | 0 | <1 сек | — | — | машины 4-8 GB RAM без GPU. Честное поведение: не ставим `qwen3:0.6b` c false-covered, а используем рулбейс по `thesis.keywords`. UI-метка: «Базовая проверка тезисов, без LLM». |
| Default | `qwen2.5:7b-instruct-q4_K_M` | ~5.5 GB | ~4.7 GB | 25-45 сек | хороший | надёжный | 8-16 GB RAM CPU-only. Основной путь. В 2-3× быстрее qwen3:8b, в 2× меньше RAM, сопоставимое RU-качество. |
| Premium | `vikhr-nemo-12b-instruct-r-21-09-24:q4_K_M` | ~8.5 GB | ~7 GB | 35-60 сек | **лучший в классе** (RU fine-tune Mistral Nemo) | хороший | 16+ GB или GPU 8+. Если tag недоступен в Ollama registry к дню установки — fallback на `qwen2.5:14b-instruct-q4_K_M`. |

**qwen3:8b не рекомендуется как default** — по скорости на CPU проигрывает qwen2.5:7b, RU-качество сопоставимое, JSON-надёжность хуже (2/5 parse-errors в R0).

**Без Ollama** — keyword-matching fallback в `scoring.build_review_verdict_fallback`. UX-индикатор «рецензия в упрощённом режиме (Ollama не запущена)».

**Промпт-rewrite (блокер качества на 4-7B).** Текущий `infrastructure/ollama/prompts.py::review_prompt()` написан на английском — малые модели игнорируют "be strict" и всем ставят covered. В W2 перед R1-валидацией переписать:

1. Русский system-prompt с явной рубрикой `missing/partial/covered` и числовыми диапазонами (score ≥90 только при всех covered, <50 при 2+ missing).
2. Few-shot из 2 реалистичных примеров (excellent + weak) ~300 и ~150 символов.
3. Single-pass CoT: `<reasoning>3-5 предложений почему такая оценка</reasoning>` перед JSON. Не два прохода — удваивает latency.
4. Избегать `format=json` без few-shot — малые модели трактуют его как «минимальный валидный JSON» и отдают `{}`.

**R1-валидация (дни 9-14).** На финальном промпте прогнать 3 топ-кандидата (`qwen2.5:7b`, `qwen3:4b`, `vikhr-nemo:12b`) × 5 билетов × 6 ответов (5 из R0 + «wrong answer»). Метрики: JSON-valid rate, schema-valid rate, latency p50/p95, discrimination `|score(excellent) − score(empty)|` (цель ≥50), human-agreement на 30 ответах (цель ≥70%), peak RSS. Запуск на референсном ноуте классмейта (i5 gen11 / 8 GB / без GPU) для top-2 — dev-машина врёт в 1.5-2×.

Все тренировочные режимы работают без Ollama (кроме LLM-review, который тогда fallback на keyword) — приложение не имеет hard dependency на наличие Ollama.

---

## Часть 5: Packaging (W3, упрощённый)

### 5.1 Build EXE

`scripts/build_flet_exe.ps1`:
- `flet pack ui_flet/main.py --name Tezis --icon assets/icon.ico`
- bundled TTF в `ui_flet/theme/fonts/` (no-network fallback)
- включаемые ресурсы: `assets/icon.ico`, `build/demo_seed/state_exam_public_admin_demo.db`
- output: `dist/Tezis.exe` (~100-150 MB, Flet тяжёлый)

### 5.2 Distribution zip

```
Tezis-v2.0-windows.zip
├── Tezis.exe
├── data/state_exam_public_admin_demo.db
├── scripts/
│   ├── install_ollama_wizard.ps1    # optional, если W3-wizard успевает
│   └── check_ollama.ps1              # диагностика
├── assets/icon.ico
├── README.txt                        # 10 шагов для однокурсника
└── LICENSE.txt
```

`scripts/package_release.ps1` собирает zip, проверяет checksum, генерирует CHANGELOG.

### 5.3 Ollama installer (опционально)

Если время остаётся после W2 — восстанавливаем `scripts/install_ollama_wizard.ps1` из v1 спека (hardware detection + tiered model + canary test). Иначе — README содержит 3-строчную ручную инструкцию: `winget install Ollama.Ollama` → `ollama pull qwen3:8b` → открыть Tezis.

**Acceptance без wizard-а:** приложение работает с fallback-review без Ollama, классмейт получает value даже если модель не скачана.

### 5.4 macOS сборка

Отложена в Deferred v2.1 (после 13 мая).

---

## Часть 6: Testing Strategy

### 6.1 Переносимые тесты (~180 шт)

Service/domain/infrastructure тесты не зависят от UI-фреймворка:
- `test_import_service.py`, `test_scoring.py`, `test_adaptive_review.py`, `test_state_exam_scoring.py`
- `test_ollama_runtime.py`, `test_ollama_service.py`
- `test_delete_document.py`, `test_release_seed.py`
- `scripts/verify_state_exam_seed.py` (end-to-end cycle)
- `scripts/codex/verify_codex_output.py` (JSON invariants)

### 6.2 Qt-специфичные тесты (удаляем после приёмки v2.0)

Сохраняются в `tests/qt_legacy/` до финальной приёмки, потом удаляются вместе с `ui/`:
- `test_painter_warnings.py`, `test_theme_palette.py`, `test_theme_typography.py`, `test_materiality.py`, `test_logo_mark.py`, `test_responsive_layouts.py`

### 6.3 Новые тесты W2

- `tests/test_flet_state.py` — breakpoint logic, theme switching, facade wiring
- `tests/test_flet_theme_tokens.py` — токены не хардкодятся в компонентах
- `tests/test_flet_i18n.py` — все строки из `ui_flet/i18n/ru.py`
- `tests/test_flet_router.py` — 3 роута (tickets, training, settings) работают
- `tests/test_flet_training_modes.py` — 6 workspace-ов корректно диспатчят evaluate_answer на facade

UI-smoke через Flet testing API (если стабильно) или через `QT_QPA_PLATFORM=offscreen`-аналог для Flet (не уверен что есть — fallback на pyautogui скриншотирование).

### 6.4 Acceptance v2.0

1. `pytest -q` зелёный
2. `flet pack` собирает `Tezis.exe`, запускается на Windows 10 + 11 VM
3. На открытом билете:
   - `reading` показывает полный ответ с разметкой
   - `plan` позволяет drag-to-order и возвращает оценку
   - `cloze` проверяет пропуски
   - `active-recall` оценивает короткий ответ с (опц.) LLM-review
   - `state-exam-full` таймер работает, возвращает block scores + review verdict
   - `review` — per-thesis verdict
4. Без Ollama все 6 режимов работают (review использует keyword-fallback)
5. С Ollama qwen3:8b — review выдаёт per-thesis verdict за < 60 сек
6. Light/Dark переключаются из Settings без багов
7. На 1024×768 — chip-навигация сворачивается; на 1920×1200 — 2-колон; на 2560×1440 — 3-колон
8. Однокурсник: распаковать zip → запустить exe → открыть билет → пройти `state-exam-full` → увидеть review
9. README понятен не-программисту

---

## Часть 7: Execution Sequence

**2026-04-19 (сегодня):** scope frozen, spec обновлён. Создание worktree `flet-migration`, установка Flet (`pip install flet`).

**Дни 1-3 (19-21 апреля):**
- Bootstrap `ui_flet/main.py`, `state.py`, `router.py`, `theme/tokens.py + theme.py`
- TopBar, TicketCard, EmptyState компоненты
- Tickets view (список + фильтр + карточки билетов), подключение к facade
- Packaging smoke: `flet pack` собирается без ошибок на dev-машине (ранний сигнал про кириллицу/шрифты)

**Дни 4-8 (22-26 апреля):**
- Training view (хост workspace-ов)
- Reading + Plan workspace (drag-to-order) + Cloze workspace (fill-in-the-blank)
- Active-recall workspace + timer_widget
- State-exam-full workspace (6 полей + таймер 20-40 мин)
- Review workspace (per-thesis verdict display)

**Дни 9-14 (27 апреля — 2 мая):**
- Settings view (тема, шрифт, модель Ollama, window-mode toggle, test connection)
- **FSRS миграция** `application/adaptive_review.py` — py-fsrs, mapping score→grade, обновлённые тесты
- **Очередь повторений в Tickets view** — правая панель на laptop_hd+, mini-dashboard
- Dark theme polish, адаптив на 5 разрешениях (1366×768, 1440×900, 1536×864, 1920×1080, 2560×1440)
- **Fullscreen-first** — `page.window.full_screen = True` при старте, переключатель в Settings
- Ollama integration + error states — быстрый connect-probe чтобы не висеть 60с при offline
- R1 валидация review-модели на финальном промпте (3 кандидата × 5 ответов)
- Smoke на 2 VM (Windows 10 + 11)

**Дни 15-21 (3-9 мая):**
- Финальный polish, bug-bash (особенно FSRS edge-cases: новые билеты, долгий перерыв, массовое Again)
- README для однокурсников, финальный zip
- Rollout внутренний (2-3 классмейта на тест)

**Дни 22-23 (10-11 мая):** рассылка zip всем классмейтам.

**Буфер 12-13 мая:** багрепорты, hot-fixes перед экзаменом 13 мая.

### 7.1 Cut order

Если не успеваем — режем в порядке (первое — с минимумом потерь):
1. Dark theme — только Light в релизе
2. 4K (>2560) multi-panel — только 2-колон на `laptop_hd`/`desktop_wide`
3. Ollama wizard — README-инструкция вместо него
4. R1-валидация премиум-модели (vikhr-nemo) — оставить только default-тир qwen2.5:7b
5. FSRS dashboard plot retention — оставить просто список ближайших билетов (очередь обязательна, plot опционален)
6. `review` workspace как отдельный — embedded в state-exam-full
7. Timer в active-recall — без таймера

---

## Часть 8: Files Affected

| Файл / Каталог | Stream | Тип | Описание |
|---|---|---|---|
| `ui_flet/` | W2 | **new pkg** | весь пакет |
| `pyproject.toml` | W2 | modify | добавить `flet>=0.27,<0.28`, `fsrs>=4.0` |
| `requirements.txt` | W2 | modify | pinned versions |
| `application/adaptive_review.py` | W2 | **rewrite** | миграция SM-2 → FSRS (py-fsrs), mapping score→grade |
| `infrastructure/ollama/prompts.py` | W2 | modify | `review_prompt()` — RU system + few-shot + single-pass CoT |
| `tests/test_flet_*.py` | W2 | **new** | 4-5 файлов (часть уже в 7bec85c) |
| `tests/test_fsrs_scheduler.py` | W2 | **new** | интервалы, cold-start, score→grade |
| `tests/qt_legacy/` | W2 | **new dir** | перенос Qt-тестов |
| `scripts/run_resolution_matrix.ps1` | W2 | **new** | snapshot-прогон на 5 разрешениях |
| `scripts/r1_review_validation.py` | W2 | **new** | R1: 3 модели × 5 билетов × 6 ответов |
| `scripts/build_flet_exe.ps1` | W3 | **new** | flet pack wrapper |
| `scripts/package_release.ps1` | W3 | **new** | zip builder |
| `scripts/install_ollama_wizard.ps1` | W3 | **new** (опц.) | если успеваем |
| `ui/` | W2 | **delete** (после приёмки) | удаляем весь Qt-пакет |
| `docs/superpowers/specs/2026-04-19-review-model-research.md` | coord | **new** | текущий research (создан) |
| `docs/product_spec.md` | coord | modify | scope v2.0 (3 экрана, 6 режимов, FSRS) |
| `docs/architecture.md` | coord | modify | Flet-слой |
| `README.md` | coord | modify | v2.0 инструкции |
| `CHANGELOG.md` | coord | **new** | |

Удаления не касаются data-pipeline артефактов — они финальные.

---

## Часть 9: Scope Boundaries

### In scope (v2.0)

- **Flet UI**: 3 экрана (Tickets, Training, Settings), 8 компонентов, 6 training workspaces
- **6 evidence-based тренировочных режимов** (reading, plan, cloze, active-recall, state-exam-full, review)
- **FSRS spaced-repetition** — first-class фича (часть 4.2): миграция `adaptive_review.py`, очередь в Tickets view, dashboard retention, adaptive mode suggestion
- **Warm-minimal visual language** в Material 3 адаптации, light + dark
- **Fullscreen-first** window behavior + windowed toggle в Settings (часть 3.5a)
- **Адаптивность** на 5 классах разрешений — 1366×768 … 3840×2160+ (часть 3.3)
- **Pre-baked seed DB** `state_exam_public_admin_demo.db` (готов, не пересобираем)
- **Review engine** (часть 4.4): tier model system — keyword-fallback / qwen2.5:7b / vikhr-nemo:12b + rewrite промпта (RU + few-shot + CoT)
- **Windows-дистрибутив** (zip, exe); Ollama wizard — опционально
- **Fallback без Ollama** (keyword-matching review)

### Out of scope (v2.0) — архив v1.2.x-general-exam

- Dialogue mode (устная репетиция)
- Knowledge Map view
- Subjects view, Sections view (section metadata — часть ticket detail)
- Defense DLC (подготовка к защите)
- Training modes: matching, mini-exam
- Import view (seed финальный)
- Library view (один документ — не нужна)
- Statistics как отдельный экран (встроена как панель в Tickets)
- Cloud LLM
- Web/browser версия
- macOS сборка

### Deferred to v2.1 (после 13 мая)

- macOS полноценная сборка
- Dialogue mode на Flet (если нужен)
- Knowledge Map на Flet
- Visual polish на 4K
- Ollama wizard если не успел

---

## Часть 10: Risks & Mitigations

| Риск | Вероятность | Воздействие | Митигация |
|---|---|---|---|
| `flet pack` падает на Windows (кириллица в путях / шрифты) | Средняя | Критическое | Packaging smoke на день 3; fallback на PyInstaller; худший сценарий — Qt v1.2.x + новая seed для классмейтов |
| Flet dnd (drag-and-drop) для plan workspace ненадёжен на Windows | Средняя | Среднее | Fallback — numbered-list reorder через кнопки ↑/↓ |
| Flet timer widget не обновляется в фоне при fullscreen-writing | Низкая | Среднее | Ручной таймер через `page.on_interval` |
| Классмейт не ставит Ollama — думает что приложение сломано | Высокая | Среднее | Явный UX-индикатор «рецензия в упрощённом режиме», README-инструкция по установке, fallback review всё равно работает |
| TTF шрифты не грузятся у классмейта | Низкая | Низкое | Bundled в `ui_flet/theme/fonts/`, no-network fallback |
| 1366×768 ноутбук — chip-навигация не помещается | Низкая | Среднее | Explicit `laptop_small` breakpoint c popup-меню; snapshot-прогон на 5 разрешениях до release |
| Flet API несовместимые изменения между минорными версиями | Низкая | Высокое | Pin `flet==0.27.x` в requirements |
| py-fsrs возвращает странные интервалы на малом истории (1-2 attempts) | Средняя | Среднее | Cold-start rule: первые 3 повторения — линейная лестница 1д/3д/7д, потом FSRS |
| qwen2.5:7b не пулл'ится (network / диск) | Низкая | Среднее | Fallback в install-wizard на qwen3:4b, явный UX если нет ни одной модели → keyword-only |
| Fullscreen не отпускает мышь на dual-monitor (Flet на Windows) | Средняя | Низкое | `Esc` hotkey + кнопка выхода из fullscreen в TopBar |

---

## Часть 11: Acceptance Criteria (обобщение)

1. `pytest -q` зелёный
2. `flet pack` собирает `Tezis.exe`, запускается на Windows 10 + 11 VM
3. Все 6 тренировочных режимов работают на любом билете (с и без Ollama)
4. Seed DB `state_exam_public_admin_demo.db` подключается автоматически при первом запуске
5. **Адаптивность:** интерфейс снимается без наложений/обрезаний на 5 контрольных разрешениях — 1366×768, 1440×900, 1536×864, 1920×1080, 2560×1440. Проверка через скриншоты на VM или снапшот-прогон.
6. **Полноэкранный режим:** приложение стартует в fullscreen; переключатель «Полноэкранный/Оконный» в Settings работает; размеры окна сохраняются между запусками.
7. Light + Dark переключаются без багов.
8. **FSRS:** после серии attempts в `state-exam-full` и `active-recall` очередь повторений на завтра / послезавтра меняется адекватно; правая панель показывает «Сегодня: N билетов»; dashboard retention отрисовывается.
9. README понятен не-программисту (10 шагов от скачивания до первого ответа на билет).
10. Однокурсник: exe → open ticket → `state-exam-full` 20 мин → review verdict → завтра открывает — видит свой билет в очереди повторений.

---

## Часть 12: Open Items / Future Considerations

- После 13 мая — решение по возвращению Dialogue / Knowledge Map
- Потенциальная web-версия через `flet --web` — офлайн-first
- Контент-пак для других предметов
- Ручная настройка FSRS-параметров (retention target, stability min/max) для продвинутых пользователей
- Экспорт/импорт истории повторений из Anki / в Anki

---

## Status Log

- **2026-04-18** — design created, scope: 3 workstreams, 6 экранов, 6 тренировочных режимов, обязательный Ollama wizard, установщик как первоклассный scope.
- **2026-04-19 (1st update)** — W1 (data pipeline) закрыт, seed DB финальный (см. Часть 2). Экраны сокращены с 6 до 3. Тренировочные режимы пересмотрены через evidence-based research. Ollama wizard — secondary. macOS — v2.1.
- **2026-04-19 (2nd update)** — правки по замечаниям пользователя:
  1. **Адаптивность** переписана (часть 3.3): вместо одного порога 1280×800 — таргет на 5 классов ноутбуков и мониторов (1366×768, 1440×900, 1536×864, 1920×1080, 2560×1440). Добавлен `scripts/run_resolution_matrix.ps1` в Files Affected.
  2. **Fullscreen-first** (новая часть 3.5a): приложение стартует в полноэкранном, переключатель «Полноэкранный/Оконный» в Settings, сохранение window-size между запусками.
  3. **FSRS** повышен из Deferred в первоклассный scope v2.0 (часть 4.2): миграция `application/adaptive_review.py` с SM-2 на FSRS (py-fsrs), mapping score→grade, очередь повторений в Tickets view, retention dashboard, adaptive mode suggestion.
  4. **Review engine rewriten** (часть 4.4): после research (`2026-04-19-review-model-research.md`) дефолт — `qwen2.5:7b-instruct-q4_K_M` (2-3× быстрее qwen3:8b, сопоставимое RU). Premium — `vikhr-nemo:12b-instruct` (лучший RU). Light — keyword-fallback без LLM (qwen3:0.6b исключён: false-covered хуже чем честное отсутствие LLM). Промпт rewrite блокирует R1 validation (дни 9-14).
  5. Acceptance criteria обновлены под новые требования (адаптивность, fullscreen, FSRS). Cut order перераспределён. Risks дополнены 3 новыми (FSRS cold-start, qwen2.5 pull failure, fullscreen dual-monitor).
