# Daily Journal, Ritual & Calibration — дизайн

> Status: approved for planning, 2026-04-19.
> Author: совместно с Claude (superpowers:brainstorming).
> Scope: ~2 часа вечерней имплементации на ветке `flet-migration` (до рассылки classmates 10–11 мая).

## 1. Motivation

Текущий UX приложения — тренажёр в чистом виде: открыл, долбил, закрыл. Пользователь сформулировал это как «ощущается как совершенно банальная рутина». Конкретные царапины:

1. **Нет ощущения прогресса.** Непонятно, сколько закрыл, где слабые места, куда движешься.
2. **Нет драйва внутри сессии.** Ответил → «сохранено», и всё. Нет сравнения с прошлой попыткой, нет микро-награды.
3. **Нет auth / персонализации.** Приложение «сухое», не «моё».
4. **Нет момента завершения дня.** Непонятно, когда остановиться — можно бесконечно грызть очередь.
5. **Не все билеты одинаково хорошо распознаются** по скелету плана ответа на «отлично» (качество seed-данных).

Цель — превратить «тренажёр» в **ежедневный ритуал**: утро-день-вечер как связная арка, с человеческим голосом и осмысленной обратной связью. Не добавить N разрозненных фич, а дать одну объединяющую метафору (дневник) + две точечные механики (calibration, skeleton-маркер).

## 2. Decisions

| Параметр | Выбор | Отклонённые варианты |
|---|---|---|
| Подход | **Глубина — «Дневник дня» как новая смысловая ось** | Ширина (6 мелких фич везде — выглядит недоделанно), Эмоция (только feedback-петля — не даёт ощущения пути) |
| Auth-модель | **Один локальный профиль** (имя + emoji-аватар) в `profile.json` | Таблица `users` в SQLite (overkill), мультипрофиль (незачем), облачный auth (outside scope) |
| Размещение calibration | **Только free-text режимы** (active-recall, review, state-exam-full) | Все режимы (в `reading` бессмысленно), только state-exam-full (слишком редко) |
| Skeleton-маркер | **Эвристика по длине плана** (число блоков + средний размер) | Пересмотр seed-pipeline (отдельный project), ручная разметка (не масштабируется) |
| Navigation default | **Journal становится root-роутом** после auth | Tickets как root (оставляет Journal незаметным), отдельная кнопка «Дневник» (не создаёт ритуала) |
| Language-контракт | **Тест-assertion на весь `ui_flet/`** — user-facing строки обязаны содержать кириллицу | Линтер-warning (не блокирует регрессии), ручной review (не масштабируется) |

## 3. Architecture

### 3.1 Навигация

```
Первый запуск → /onboarding (auth)
           → profile.json создан → /journal (default)

/journal   ← НОВЫЙ, root-route
/tickets   ← существует
/training/{ticket_id}/{mode} ← существует
/settings  ← существует
```

Sidebar-пункты: `Дневник` (новая первая строка) / `Билеты` / `Настройки`. `Training` остаётся доступным только через `Tickets → карточка → Тренировать`.

### 3.2 Три состояния Journal

Состояние выводится из данных, не хранится явно:

| Состояние | Условие | Содержимое |
|---|---|---|
| **Morning** | `MAX(attempts.created_at)` по today нет | Приветствие «С добрым утром, {name} {avatar}». Карточка «Сегодня: N повторений + M новых ≈ T минут». Опционально — строка «Вчера ты разобрал X билетов» (если вчерашняя сессия была). Кнопка `Начать` → `/training/{first-queue-ticket}/{suggested-mode}`. |
| **During day** | Есть ≥1 attempt today, флаг `day_closed_at` не проставлен | Лента карточек попыток (chronological, newest first): билет, режим, балл, дельта vs прошлая попытка этого билета («+15», «−8», «первый раз»). CTA `Продолжить` → следующий FSRS-топ. Subtle ссылка `Хватит на сегодня` внизу. |
| **Evening** | Клик `Хватит на сегодня` ИЛИ день имеет attempts и `day_closed_at` проставлен | Сводка: разобрано, закрыто в FSRS-зелёное, лучший момент дня (attempt с max баллом → карточка билета с баллом), превью завтрашней очереди. Одна строка voice на ночь. |

Переход morning → during-day автоматический, после первого attempt. Переход during-day → evening ручной (click `Хватит на сегодня`) или автоматический на следующий календарный день.

### 3.3 Components

Новые файлы:
- `ui_flet/views/journal_view.py` — routing state + 3 layout-ветки
- `ui_flet/views/onboarding_view.py` — экран auth (имя + аватар)
- `ui_flet/components/attempt_card.py` — карточка попытки в ленте дня
- `ui_flet/components/calibration_chips.py` — 3-chip виджет уверенности
- `ui_flet/components/skeleton_warning.py` — полоса-предупреждение для plan-mode
- `application/daily_digest.py` — агрегатор «что было сегодня» (attempts → сводка)
- `application/user_profile.py` — read/write `profile.json`, единая точка доступа к имени/аватару
- `application/ticket_quality.py` — эвристика skeleton-weakness, кешируется при bootstrap

Правки существующих:
- `ui_flet/router.py` — добавить `/journal`, `/onboarding`, сменить default
- `ui_flet/main.py` — gate: если профиля нет → onboarding, иначе → journal
- `ui_flet/components/top_bar.py` — показать имя + аватар справа
- `ui_flet/views/training_view.py` — вставить calibration-chips перед «Проверить» в free-text режимах, показать отклик после
- `ui_flet/components/ticket_card.py` — показать 🔶 для `plan_skeleton_weak`
- Все строки пользовательских сообщений — переписать под voice-контракт (см. §6)

### 3.4 Data model — дельта

**Новый файл:** `app_data/profile.json`
```json
{"name": "Миша", "avatar_emoji": "🦉", "created_at": "2026-04-19T22:10:00Z"}
```

**Миграция SQLite:** `attempts.confidence TEXT NULL` — значения `'guess' | 'idea' | 'sure' | NULL`. Nullable обязателен: все существующие записи совместимы.

**Вычисляемо в памяти (НЕ в БД):**
- `plan_skeleton_weak` для билета → считается из `canonical_plan` при bootstrap, держится в `TicketQualityCache` (dict `ticket_id → bool`). Пересчёт при импорте новых билетов.
- Daily digest → агрегат `SELECT * FROM attempts WHERE DATE(created_at) = DATE('now')` на каждом рендере Journal (208 билетов × десятки попыток в день — дёшево, без индекса).

**Новый флаг в settings / app_data:** `day_closed_at: ISO-datetime | null` — когда пользователь нажал «Хватит на сегодня». Сбрасывается автоматически при открытии приложения на следующий календарный день.

## 4. Calibration

**Placement:** между полем ответа и кнопкой `Проверить` в режимах `active-recall`, `review`, `state-exam-full`.

**UI:** 3 chip'а в ряд, один обязателен к выбору перед активацией `Проверить`:
- 🤷 `угадываю`
- 🤔 `есть идеи`
- 💡 `точно знаю`

**Отклик** (после `Проверить`, одна строка над баллом):
| confidence | score | Строка |
|---|---|---|
| `sure` | ≥ 75 | «Ты был уверен — и оказался прав.» |
| `sure` | < 75 | «Был уверен, а это {score}%. Калибровка важнее уверенности.» |
| `idea` | ≥ 75 | «Ты сомневался, а зря — знаешь лучше, чем думаешь.» |
| `idea` | < 75 | «Ожидания совпали с реальностью. Это нормально — дай мозгу время.» |
| `guess` | ≥ 75 | «Неожиданный успех. Не записывай в «знаю» — повтори через день.» |
| `guess` | < 75 | «Честная самооценка. Возвращайся к этому билету завтра.» |

**Storage:** `attempts.confidence` — заполняется для новых попыток, NULL для старых. В Journal-карточках попыток показывается маленькой иконкой уверенности рядом с баллом.

**Не делаем сейчас:** aggregate calibration dashboard («твоя калибровка: 73%»). Это логичное следующее улучшение, но за 2 часа не влезает.

## 5. Skeleton-маркер

**Эвристика** (`application/ticket_quality.py`):

```python
def is_plan_skeleton_weak(ticket) -> bool:
    plan = ticket.canonical_plan or []
    if len(plan) < 4:
        return True
    avg_words_per_block = mean(len(block.split()) for block in plan)
    if avg_words_per_block < 15:
        return True
    return False
```

**UI:**
- `TicketCard` (в `/tickets`): иконка 🔶 справа от заголовка, tooltip «Эталонный план у этого билета короткий — сверяй смысл, не структуру.»
- `plan`-режим: полоса-warning наверху — «У этого билета эталонный скелет неточный — ориентируйся на смысл ответа, не на количество блоков.»

**Когда считается:** один раз при bootstrap приложения (после загрузки tickets из БД), результат в `TicketQualityCache`. Пересчёт — при импорте новых билетов или при явном вызове `/settings → обновить кеш` (не делаем сейчас, но API предусматривает).

## 6. Voice contract

**Правила тона** (обязательны для всех user-facing строк в Journal + onboarding + calibration-отклике):
1. На «ты», не на «Вы».
2. С именем пользователя, где уместно. В onboarding имени ещё нет → обезличенно.
3. Без геймификации в стиле «Level up! +10 XP!». Без капса, восклицательных знаков в avalanche.
4. Короткие фразы (≤ 80 символов в строке идеала, ≤ 120 максимум).
5. Человеческий тон: «Крепкий заход», «Без пафоса — просто молодец», «До завтра». Не «Задание выполнено», не «Сессия сохранена».
6. Никаких эмодзи, кроме: аватар пользователя, 🔶 (skeleton-маркер), иконки confidence-chips, и те что уже в TopBar/IconBadge.

**Примеры (canon):**
- Morning: «С добрым утром, {name} {avatar}. Сегодня очередь небольшая — {N} повторений. Справишься за {T} минут.»
- Morning (без очереди): «С добрым утром, {name} {avatar}. Свежая неделя — можно начать с нового билета.»
- Attempt-карточка лучшая за день: «Лучший момент: {ticket_title} — {score}%.»
- Evening: «Разобрал {N} билетов, {K} легли в долговременную память. {best_line} До завтра, {name}.»
- Evening (пустой день, если юзер просто открыл): «Сегодня ты не занимался. Бывает. Очередь подождёт до завтра.»
- Streak ≥ 3 дня (если реализуем — опционально): «{N}-й день подряд. Без пафоса — просто молодец.»

## 7. Language contract test

**Требование пользователя:** тест, проверяющий, что во всём приложении соблюдён русский язык как строгое правило дизайн-кода.

**Реализация:** `tests/test_language_contract.py`.

**Что проверяется:**
- Обходим все `.py` файлы в `ui_flet/` (view, components) и все copy-файлы, если появятся.
- Для каждого string-literal, передаваемого в text-rendering (Text, ElevatedButton, TextButton, TextField.label, .hint, SnackBar, AlertDialog.title и подобные) — строка должна содержать ≥ 1 кириллический символ ИЛИ быть в whitelist.

**Whitelist** (технические термины + безопасные не-кириллические строки):
- Пустая строка `""`.
- Строки из одних пробелов, знаков препинания, цифр, emoji.
- Технические токены в whitelist: `FSRS`, `Ollama`, `SQLite`, `JSON`, `PDF`, `Tezis`, `active-recall`, `state-exam-full`, `reading`, `plan`, `cloze`, `review`, режимы тренировки как идентификаторы.
- URL-ы и файловые пути (детектятся по `.`, `/`, `http`).
- Single-character строки.

**Что НЕ проверяется** (out of scope теста):
- Docstring'и, комментарии.
- Identifier'ы, keys словарей.
- Ключи в локализационных файлах (их нет сейчас, но если появятся — whitelist класса `I18N_KEY`).
- Строки в `tests/`, `scripts/`, `docs/`.

**Техника:** AST-walk через `ast.parse`, визитор ищет вызовы `ft.Text(...)`, `ft.ElevatedButton(text=...)`, `ft.TextField(label=..., hint_text=...)` и т.п. Для каждого constant string literal — проверка. Список проверяемых callable'ов держится в коде теста как tuple, расширяется по мере добавления новых UI-виджетов.

**Exit criteria:** `pytest tests/test_language_contract.py` → зелёное на весь `ui_flet/` current state + любых новых строк этой сессии.

**Осознанно в теста НЕ лезем:** f-string части, которые собираются во время runtime (например, `f"Score: {score}%"` — тут `Score: ` был бы нарушением, но этот конкретный случай не встретится, потому что voice-контракт запрещает такие конструкции, и тест поймает). Если окажется, что у нас таких много — это сигнал, что voice-контракт ещё не везде применён, и это правильный signal.

## 8. Scope & time budget (≈ 2 ч 10 мин)

| Блок | Мин |
|---|---|
| `profile.json` + `user_profile.py` + onboarding view | 20 |
| Journal view (3 состояния) + `daily_digest.py` + attempt-card компонент | 40 |
| Calibration chips widget + wiring в 3 режима + миграция `attempts.confidence` | 25 |
| Skeleton-маркер + `ticket_quality.py` + warning-полоса | 15 |
| Voice-sweep по канон-строкам (morning, evening, attempt-отклик, confidence-отклик) | 10 |
| Language contract test | 10 |
| Sanity-проверка — ручной прогон onboarding → journal → training → evening | 10 |

**Буфер:** нет. Если поплывёт — первым резать **evening best-moment** (оставить «разобрал N билетов»), вторым — **streak-счётчик**, который в каноне 6 не заявлен и добавляется опционально.

## 9. Out of scope (осознанно)

- **Aggregate calibration dashboard** — «твоя калибровка 73%» за неделю. Логичное v+1.
- **Streak-счётчик и heatmap по разделам** — добавляется тривиально позже.
- **Полный фикс seed-pipeline для skeleton-проблемы** — отдельная сессия с пересмотром конспект → план pipeline.
- **Мультипрофиль / sync / auth с паролем** — один пользователь на установку, локально.
- **Перевод статистики на уровень разделов** — карта знаний по разделам как v+2.
- **Анимации, звуки, тактильные эффекты** — warm-minimal сознательно тихий.

## 10. Open risks

| Риск | Митигация |
|---|---|
| Воткнуть calibration в 3 режима и сломать существующие training-views | Отдельный компонент, интеграция через опциональный prop `show_calibration=True`. Старые тесты `test_flet_tickets_view.py`, `test_facade_review_fastfail.py` должны остаться зелёными. |
| Journal state misjudged (day_closed_at не сбросился) → пользователь утром попадает в evening | Проверка: при открытии приложения если `day_closed_at` ≠ today → сбросить и пересчитать состояние. Unit test на переход суток. |
| Skeleton-эвристика false-positives на валидных коротких билетах | Эвристика консервативная (len < 4 OR avg < 15 слов), маркер — мягкий tooltip/warning, не блокирует использование. Можно точнее настроить после baseline. |
| Language contract test ломает CI на legitimate latin-string (напр. «Tezis» в TopBar) | Whitelist явно описан в тесте, расширяется по факту регрессии. Тест — guardrail, не догма. |
| Voice-контракт не везде применён после 2 часов | Language contract test поймает latin-strings; voice-тон самих русских строк не автоматизируется — остаётся человеческим правилом. Приоритет sweep'а — Journal, auth, calibration. |

---

## Acceptance

После 2 часов имплементации и sanity-прогона:
1. `profile.json` создаётся при первом запуске, имя и аватар сохраняются.
2. `/journal` — root, показывает morning на чистом дне, during-day после первого attempt, evening после click «Хватит на сегодня».
3. Calibration-chips обязательны в 3 free-text режимах; отклик появляется после проверки.
4. Skeleton-маркер виден на Ticket-карточках (для билетов с weak-планом) и в plan-mode warning.
5. `pytest tests/test_language_contract.py` → green.
6. `pytest -q` → 313 passed (+ новые тесты) 5 skipped, 0 failed.
7. Пользователь проходит путь «onboarding → journal → training → calibration → вечерняя сводка» и говорит «да, это уже не рутина».
