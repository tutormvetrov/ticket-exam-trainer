# Visual Polish — Onboarding & Journal final pass

> Status: approved 2026-04-19.
> Author: совместно с Claude (superpowers:brainstorming).
> Scope: ~60-70 мин, последний visual-pass перед рассылкой classmates.

## 1. Motivation

Journal и Onboarding собраны функционально корректно, но визуально **отстают от** warm-minimal-уровня, заданного tickets/training. Конкретно:

- `display` token (Lora 32px) не используется в новых экранах
- Elevated-кнопки — Flet-material-default, а не rust
- Нет ornaments/brand в церемониальных моментах
- Best-moment и greeting сидят как body-строки, не выделены
- Attempt-card функциональна, но без warm-акцентов

Цель: одна сессия, три экрана (onboarding, journal morning, journal evening) + мелкие правки attempt-card и calibration-chips, чтобы визуальная планка совпала с остальным приложением.

## 2. Decisions

| Параметр | Выбор | Отклонено |
|---|---|---|
| Глубина правки | **C — полная переозвучка** | A (минимум tone, оставляет утилитарный фил), B (ритуальная плотность — хорошо, но не закрывает Button + elevation) |
| Новые tokens | **ELEVATION + SHADOW** в `ui_flet/theme/elevation.py` | Inline shadow-значения в каждом Container (дублирование) |
| Button styling | **`primary_button()` / `ghost_button()` helpers** в `ui_flet/theme/buttons.py` | Кастомизация inline в каждом view, кастомные `ft.ElevatedButton` subclasses |
| Ornaments | **Один компонент `OrnamentalDivider`** с двумя variants | Ad-hoc HorizontalLines везде |
| Анимации | **Fade-in 200ms через `animate_opacity`** на внешнем Container onboarding/journal | Slide/scale анимации (дороже, риск на Flet 0.27), CSS-like keyframes |
| LogoMark SVG | **Не делаем** — только текстовый brand-mark в display | Асинхронная загрузка SVG (отдельная сессия) |
| Hover-эффекты | **Не делаем** — нестабильны на Flet 0.27 | Container ink=True/on_hover |

## 3. Architecture

### 3.1 Новые файлы

- `ui_flet/theme/elevation.py` — 3-level shadow tokens + `apply_elevation(container, level, is_dark)` helper.
- `ui_flet/theme/buttons.py` — `primary_button(is_dark)` и `ghost_button(is_dark)` возвращают `ft.ButtonStyle`.
- `ui_flet/components/ornamental_divider.py` — `OrnamentalDivider(variant="ornamental"|"light")`. По дефолту — dots «• • •».

### 3.2 Переработанные файлы

- `ui_flet/views/onboarding_view.py` — brand-mark + display welcome + divider + primary_button + elevation, fade-in.
- `ui_flet/views/journal_view.py` — три состояния (morning/during/evening), каждое использует elevation вместо border + display + dividers + fade-in.
- `ui_flet/components/attempt_card.py` — accent tint на левой кромке, score ≥75 в rust-цвет, delta с стрелкой-иконкой.
- `ui_flet/components/calibration_chips.py` — h3-heading вместо caption, padding-lg, SPACE-md между chip'ами, выразительный selected.

### 3.3 Data flow

Всё — презентационный слой. Никакой новой data.
Единственное изменение в логике: дата в morning-greeting берётся через `datetime.date.today()` + ru-locale weekday.

## 4. Components — детали

### 4.1 `theme/elevation.py`

```python
SHADOW_LEVELS = {
    "flat":     {"blur": 0, "spread": 0, "offset_y": 0, "alpha": 0.00},
    "raised":   {"blur": 8, "spread": 0, "offset_y": 2, "alpha": 0.06},
    "floating": {"blur": 16, "spread": 0, "offset_y": 4, "alpha": 0.10},
}

def apply_elevation(level: str, is_dark: bool) -> ft.BoxShadow | None:
    """Возвращает BoxShadow или None (для 'flat')."""
```

- Shadow color — warm-tinted: light → `#2B1F17` с alpha; dark → `#000000` с alpha (дарк-шадоу контрастнее, чем на парче).
- Предназначено для прямой подстановки: `Container(..., shadow=apply_elevation("raised", is_dark))`.

### 4.2 `theme/buttons.py`

```python
def primary_button(is_dark: bool) -> ft.ButtonStyle:
    """rust bgcolor, parchment fg, Lora-body, RADIUS-md, SPACE-xl padding."""

def ghost_button(is_dark: bool) -> ft.ButtonStyle:
    """transparent, text_primary, no border, SPACE-md padding."""
```

- Использовать через `ft.ElevatedButton(text="...", style=primary_button(state.is_dark))`.
- Text-weight — W_600 (strong body).

### 4.3 `components/ornamental_divider.py`

- Row из 3 частей: fading line (Container с gradient) → Text("• • •") в text_muted → fading line.
- Высота: SPACE-xl (24px total row height).
- Параметр `variant="light"` — просто `Divider(color=border_soft, thickness=1)`. Используется реже.
- Не принимает text overrides — строго «• • •», одна штука на весь app.

### 4.4 Onboarding layout (итоговый порядок)

```
┌─────────────────────────────────┐
│       Тезис (display)           │ brand-mark
│  caption-muted subtitle         │
│                                 │
│         • • •                   │ ornamental divider
│                                 │
│ Привет. Давай познакомимся.     │ welcome (display)
│ body subtitle (3 строки макс)   │
│                                 │
│ [ Как к тебе обращаться? ____ ] │ name field
│                                 │
│ Выбери аватар (h3)              │
│ caption-muted hint              │
│                                 │
│ 🦉 🐺 🦊 🐻 🦁 🐢               │ row 1 (6)
│ 🦅 🐉 🌲 🌊 🔥 ⚡                │ row 2 (6)
│                                 │
│         [ Начнём ]              │ primary_button
└─────────────────────────────────┘
```

Card: `bg_surface`, elevation=`raised`, padding-2xl, width=560, centered, fade-in.

### 4.5 Journal morning

```
      пятница, 19 апреля        (caption-muted-italic)

С добрым утром, Миша 🦉         (display)

         • • •                   (divider)

• 7 повторений                   (body + rust bullet)
• 3 новых                        (body + rust bullet)
• ≈ 22 минуты                    (body + rust bullet)

         [ Начать ]              (primary_button)
```

Card: `bg_surface`, elevation=`flat` (то есть нет shadow) — «открытая страница», not floating. Padding-2xl. Width=560.

### 4.6 Journal evening

```
Итог дня                         (display)

• 5 билетов разобрано            (body + bullet)
• 3 легли в долговременную память (body + bullet)

┌─────────────────────────────┐
│ Лучший момент               │ (caption-muted)
│ Бюджетная система РФ        │ (h3)
│                       90%   │ (display, rust, right)
└─────────────────────────────┘    best-moment tile

Завтра: 6 повторений, 3 новых    (body)

         • • •                   (divider)

     До завтра, Миша             (display, italic, centered)

    [ Открыть дневник заново ]   (ghost_button)
```

Card: `bg_surface`, elevation=`flat`. Padding-2xl.

### 4.7 Attempt card polish

- Левая кромка 3px accent color.
- Score ≥ 75 → accent color + Lora-h3 weight. < 75 → text_secondary, regular body.
- Delta: `↑ 15` в success, `↓ 8` в danger, `~` в text_muted (ранее `+15`/`−8`/`±0`).
- Padding: `horizontal=md, vertical=sm` → `horizontal=lg, vertical=md`.

### 4.8 Calibration chips polish

- Вместо inline caption prompt — heading `ft.Text(..., style=text_style("h3"))`.
- Chips: padding `symmetric(horizontal=md, vertical=xs)` → `symmetric(horizontal=lg, vertical=sm)`.
- Selected state: 2px accent border + bgcolor accent_soft (уже есть, добавить ещё визуальный вес через FontWeight.W_600 на chip-тексте).
- Gap между chips: SPACE-sm → SPACE-md.
- Reply-container после проверки — bg-цвет `accent_soft` вместо `bg_elevated`, border accent-1px.

## 5. Accessibility / responsive

- Fade-in только если `state.breakpoint != "compact"` — на маленьких экранах анимация ощущается как лаг. (Простой if-check.)
- Fonts не меняются. `display` = 32px — читаемо на 1366×768.
- Color-contrast: accent (rust #A94434) на parchment (#FBF4E4) — contrast 5.8 (AA passes). Dark-mode: desaturated rust на cognac — contrast 4.5+.

## 6. Testing

- `tests/test_language_contract.py` — должен остаться зелёным (строки не меняем).
- `tests/test_flet_router.py` — должен остаться зелёным (роуты не меняем).
- Новые тесты **не добавляем** — визуальная работа, golden-screenshot подход вне бюджета.
- Manual check: после имплементации — запустить приложение (не проверяю через preview, user проверит сам).

## 7. Out of scope

- LogoMark SVG asset-pipeline.
- Gradient backgrounds.
- Hover states на карточках.
- Новые анимационные примитивы (slide/scale/stagger).
- Dark-mode-specific iconography overrides.
- Visual regression auto-tests.

## 8. Time budget

| Блок | Мин |
|---|---|
| `theme/elevation.py` + `theme/buttons.py` | 10 |
| `components/ornamental_divider.py` | 7 |
| Onboarding полная переработка | 12 |
| Journal morning | 10 |
| Journal evening + best-moment tile | 12 |
| Attempt card polish | 5 |
| Calibration chips polish | 5 |
| Sanity прогон тестов + commit | 7 |

**≈68 мин.** Буфер нулевой. Если поплывёт — режем в обратном порядке (сначала fade-in, потом calibration polish, потом attempt-card kromka).

## 9. Acceptance

После имплементации:
1. Onboarding: brand-mark + display welcome + ornamental divider + primary-button.
2. Journal morning: дата-строка + display greeting + divider + bulleted queue + primary-button.
3. Journal evening: display title + best-moment tile + divider + display farewell + ghost-button.
4. Attempt-card: accent-kromка + color-coded score + arrow delta.
5. Calibration: h3 heading + большие chips + выразительный reply.
6. Все существующие тесты остаются зелёными (313 + language-contract + user_profile + daily_digest + ticket_quality + block_derivation + router = 395 passed).
