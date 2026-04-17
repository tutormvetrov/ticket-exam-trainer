# Warm Minimal — визуальный рефреш UI (этап 1)

**Дата:** 2026-04-17
**Автор:** совместно с Claude (superpowers:brainstorming)
**Цель:** поднять визуальный тон приложения с нейтрально-системного до выразительного «warm editorial» — ощутимая роскошь, вкус, цельность. На этом этапе закладываем дизайн-систему и применяем её к shell'у + трём самым видимым вьюхам.

---

## 1. Motivation

Текущий интерфейс — функционально корректный нейтральный light/dark (белое/серое + синий акцент). Он универсален, но не передаёт характера автора и не вызывает эмоции. Пользователь хочет, чтобы каждый миллиметр дизайна был «стильным, роскошным, вкусным, эстетичным». В терминах бренда — это сдвиг от «офисного tool'а» к «студии/библиотеке с личным голосом».

## 2. Decisions (выбранные направления)

| Параметр | Выбор | Отклонённые варианты и почему |
|---|---|---|
| Эстетика | **Warm Minimal** — кремово-песочная бумага, терракот/ржавчина, лесной зелёный | Academic Editorial (слишком формально), Swiss Modernist (холодно), Dark Luxury (не подходит для long-reading) |
| Палитры | **Light (sand+rust+moss) + тёплая Dark (cognac leather)** — обе в одной редакции | Light-only (дороже для вечерних сценариев), Light + холодная Dark (две разных «продукта») |
| Плотность | **Studio-level** — умеренный воздух, чуть больше чем сейчас, но без максимума editorial | Editorial air max (конфликт с folio-материальностью), Dense как сейчас (не даёт роскоши) |
| Типографика | **Гибрид serif + sans** — серифный корпус (Georgia с fallback'ами), микро-UI в гротеске (Inter-stack), tabular-nums для цифр | All-serif (плохо в плотных UI), all-sans (теряет editorial-голос) |
| Акцент | **Rust (#A04A22) + Moss (#3D4E2A)** — «керамическая мастерская» | Dusty rose + Sage (слишком мягко), Ochre + Ink (слишком графично), Terracotta + Forest (пробник для рефренса) |
| Материальность | **Leather Folio** — иерархически: L1 folio для ключевых карточек, L2 atelier для вторичных, L3 paper для inline-блоков | Plain Paper (не даёт тактильной роскоши), Atelier везде (без тактильного контраста) |
| Scope этапа 1 | **Дизайн-система + sidebar/topbar/splash + library/tickets/training** | Only design-system (виден только в 2 вьюхах), All views at once (риск растянуть и не доделать) |
| Реализация | **Инкрементальный рефакторинг ui/theme.py → пакет ui/theme/** | Parallel v2-система (удвоенный код), Full rewrite с layered tokens (больше работы без визуального выигрыша) |

## 3. Design tokens

Переделываются `LIGHT` и `DARK` словари в `ui/theme/palette.py`. Введена семантическая система имён:

### 3.1 Light palette

| Ключ | Hex | Применение |
|---|---|---|
| `paper` | `#F8EFE2` | основной фон страницы |
| `parchment` | `#FBF6F0` | фон карточек atelier, поверхность inputs |
| `sand` | `#F1E4C9` | фон sidebar, второй уровень поверхности |
| `ink` | `#2C2520` | основной текст |
| `ink_muted` | `#4E3E35` | вторичный текст, body |
| `ink_faint` | `#8A7064` | tertiary текст, метки |
| `rust` | `#A04A22` | primary accent, CTA-линии, активные ссылки |
| `rust_soft` | `#E9D5BE` | soft-заливки пиллов и hover-фонов |
| `moss` | `#3D4E2A` | secondary accent, CTA-кнопки |
| `moss_soft` | `#DCDDBC` | soft-заливки moss-пиллов |
| `brass` | `#9C7A1E` | декор, логотип, ornamental-линии |
| `brick` | `#9B4A28` | warning |
| `brick_soft` | `#F3DDC7` | warning soft-fill |
| `claret` | `#7A2E2E` | danger |
| `claret_soft` | `#F3D9D3` | danger soft-fill |
| `sage` | `#4A6150` | success text (с moss-тонкой разницы в контексте) |
| `sage_soft` | `#DFE5D4` | success soft-fill |
| `border` | `#E0CBA8` | тонкие разделители, paper-карточки |
| `border_strong` | `#C89A55` | латунная рамка folio |
| `shadow` | `QColor(90, 55, 25, α)` | тёплая коричневатая тень, α зависит от elevation-уровня |

### 3.2 Dark palette (Cognac leather)

| Ключ | Hex | Применение |
|---|---|---|
| `paper` (app_bg) | `#271710` | основной фон |
| `parchment` (surface) | `#3C2518` | карточка atelier |
| `sand` (sidebar) | `#2E1D12` | глубже чем paper (app_bg), «кожаный обрез книги» под светлыми карточками |
| `ink` | `#F0DDB2` | основной текст (парчамент) |
| `ink_muted` | `#C0A68A` | вторичный текст (лён) |
| `ink_faint` | `#8A7560` | tertiary |
| `rust` | `#C97A57` | primary accent (светлее, читаемее в темноте) |
| `rust_soft` | `rgba(201,122,87,0.16)` | заливка пиллов |
| `moss` (CTA) | `#8BA267` | primary button фон (moss-lit — подсвеченный) |
| `moss_soft` | `rgba(139,162,103,0.18)` | soft-fill |
| `brass` | `#C9A66B` | декор, логотип, линии |
| `brick` | `#D07A48` | warning |
| `claret` | `#D67580` | danger |
| `sage` | `#9EB389` | success |
| `border` | `#4A3225` | тонкие разделители |
| `border_strong` | `#7A5A32` | латунная рамка folio |
| `shadow` | `QColor(0, 0, 0, 140)` | глубокая тень на cognac-фоне |

### 3.3 Typography

**Serif** (основной голос, задаётся через `FONT_PRESETS`):

| Preset key | Label | Family chain |
|---|---|---|
| `georgia` (default) | Georgia | Georgia → Cambria → Times New Roman |
| `cambria` | Cambria | Cambria → Georgia → Times New Roman |
| `palatino` | Palatino | Palatino Linotype → Palatino → Georgia |

**Sans** (micro-UI, не user-selectable): Inter → Segoe UI → Bahnschrift → Arial. Резолвится через отдельную `resolve_ui_font()`.

**Scale** (`build_typography` возвращает, в px):

| Ключ | Значение (base=14) | Использование |
|---|---|---|
| `display` | 34-40 | splash, welcome hero |
| `page_title` | 28-32 | hero-заголовок вьюхи |
| `section_title` | 22-24 | section headings |
| `card_title` | 20 | заголовки карточек |
| `body` | 14.5 | основной текст (serif) |
| `subtitle` | 13 (italic) | serif italic — цитаты, sub-copy |
| `eyebrow` | 10.5 (sans, uppercase, ls=0.22em) | supralabel |
| `micro` | 11-12 (sans) | пиллы |
| `metric_value` | 22 (sans, tabular-nums, w700) | цифры метрик |
| `metric_label` | 11 (sans, uppercase, ls=0.08em) | подпись метрики |
| `input` / `button` | 13-14 (sans) | ввод и кнопки |

Tabular-nums в Qt 6 — через `font-feature-settings: "tnum"` в QSS или `QFont.setFeatures()` где поддерживается.

## 4. Materiality system

Три уровня + отдельная таблица теней. Живёт в `ui/theme/materiality.py`.

| Level | Role key | Где | Shadow | Radius (outer / inner) | Детали |
|---|---|---|---|---|---|
| **L1 Folio** | `folio` | героические карточки билетов, активный билет в training, превью диалога | `0 14px 28px -10px rgba(90,55,25,0.35)` + `inset 0 0 0 1px border_strong` | 10 / 6 | Два слоя: outer — `border_strong` 8px padding; inner — `parchment` бумага; сверху «закладка» 4×44px `rust` |
| **L2 Atelier** | `atelier` | MetricTile, EmptyStatePanel, settings-panels | `0 10px 22px -10px rgba(90,55,25,0.18)` + `inset 0 1px 0 rgba(255,255,255,0.55)` | 12 | Одиночный слой; опциональная `accent_strip` 2×44px под карточкой (`rust` или `moss`) |
| **L3 Paper** | `paper` | строки списков, sidebar-items, form rows, inline-блоки | `0 1px 0 rgba(90,55,25,0.06)` (только линия-подложка) | 4-6 | Тонкий `border` 1px; опциональная внутренняя рамка-штамп 0.5px `rust@12%` |

**Радиусы** (`RADII` в `spacing.py`):
```
xs: 4, sm: 6, md: 10, lg: 14, xl: 18, 2xl: 22
```

**Elevation taxonomy** (`ELEVATION` в `spacing.py`):
```
sm → (blur=4,  dy=1, α=15)  — paper-только-линия
md → (blur=22, dy=10, α=45) — atelier
lg → (blur=28, dy=14, α=90) — folio
```

**API:**
```
apply_shadow(widget, level: "sm"|"md"|"lg", palette: dict)
```
Старая сигнатура `apply_shadow(widget, color, blur, y_offset)` удаляется (всего 1 место применения — `ui/components/common.py:CardFrame`).

## 5. Component system

### 5.1 CardFrame

Расширяется:
```python
CardFrame(role: str = "atelier" | "folio" | "paper",
         accent_strip: str | None = None,   # "rust" | "moss" | None
         shadow: bool = True)
```
Для `role="folio"` — override `paintEvent` для двухслойной отрисовки (всё рисуется на самом виджете, БЕЗ QGraphicsEffect внутри — иначе вернётся шквал QPainter warnings, которые мы только что устранили). Для `atelier`/`paper` — QSS через property-селекторы `QFrame[role="atelier"] { ... }`.

### 5.2 Кнопки (QSS-only через property `variant`)

| Variant | Fill | Text | Border | Radius |
|---|---|---|---|---|
| `primary` | `moss` | `parchment` | нет | 10 |
| `secondary` | transparent | `rust` | 1px `rust` | 10 |
| `ghost` | transparent | `ink_muted` → hover `rust` | нет | 10 |
| `danger` | `claret` | `#F7ECE9` | нет | 10 |

Все — sans font, letter-spacing 0.02em, padding 9/16.

### 5.3 LogoMark

SVG-шаблоны остаются (`assets/logo/mark-full.svg.template`, `mark-minimal.svg.template`). Меняется только `logo_palette`:
```
light: emerald_* → moss_*  (#3D4E2A / #6E8554)
       gold_*    → brass_* (#9C7A1E / #D0A444)
dark:  emerald_* → moss_lit_* (#8BA267 / #BAD290)
       gold_*    → brass_lit_* (#C9A66B / #E6CE8F)
```
Тесты `test_logo_mark.py` (в частности `test_logo_palette_light_values` и `test_logo_palette_dark_values`) обновляются под новые значения.

### 5.4 Остальные компоненты

- **IconBadge** — `rust_soft`/`moss_soft`/`sage_soft` background, text — соответствующий dark partner. Font sans 9-11px 700.
- **StatusDot** — unicode-точка цветом `moss`/`rust`/`claret`, text sans 12px 600.
- **ScoreBadge** — три диапазона: >70% `moss_soft+moss`, 40-70% `rust_soft+rust`, <40% `claret_soft+claret`.
- **MetricTile** — L2 atelier carcass, `metric_value` + `metric_label` внутри, иконка-бейдж в углу.
- **DonutChart** — `track = sand`, accent = `moss`/`rust`/`claret` в зависимости от уровня (через `mastery_band_color`).
- **Inputs/Combos** — `parchment` fill, 1px `border`, focus-ring `2px rust` + `rust_soft` tint, serif placeholder.
- **ScrollBars** — handle `border_strong`, track прозрачный, ширина 7px, без стрелок.
- **Ornamental divider** — новый утилитарный виджет `OrnamentalDivider` в `ui/components/common.py`: тонкая 1px линия `border` с центральной точкой `brass` ø 4px. Применяется опционально в editorial-местах.

## 6. Shell redesign

### 6.1 Sidebar (`ui/components/sidebar.py`)

- Фон: `sand`
- Nav-item: высота 44px, padding 12/16
- Active item: **без заливки**; 3px `rust` accent-полоса слева + serif 14px `ink` + `brass`-dot справа
- Inactive item: sans 12-13px `ink_muted`; hover — `ink` + `brass`-dot
- Логотип в шапке: `LogoMark(size=52)` в moss+brass; под ним brand-title serif italic 14 `ink_muted`
- Нижняя граница: тонкая `border` 1px

### 6.2 TopBar (`ui/components/topbar.py`)

- Высота прежняя, фон `parchment`, bottom border `border`
- Центральный блок: serif 22px page-title + serif italic 13px `ink_muted` subtitle
- Справа: `ghost`-кнопки (settings, admin) с rust-hover
- Слева (опционально): `OrnamentalDivider` 32×1px brass для editorial-акцента

### 6.3 Splash (`ui/components/splash.py`)

- Фон: `paper`
- Логотип в центре (size=112)
- Welcome-text serif display 34px `ink`
- Subtitle serif italic 15px `ink_muted`
- Progress: `rust` fill по `sand` track, height 4px, radius 2px
- Никаких QGraphicsEffect; opacity — через `setWindowOpacity` если нужно

## 7. Views — scope этапа 1

### 7.1 LibraryView

- **Hero**: serif display 32px + serif italic subtitle + `OrnamentalDivider` 44×2px rust
- **Карточки документов**: `atelier` с hover-подсветкой (parchment → rust_soft на рамке). Eyebrow sans «Предмет», serif title, serif body-summary, sans метрики внизу.
- **Grid**: 2 колонки на широком окне (было 3-4)
- **Ollama-статус**: L3 `paper` полоска в углу, тихая
- **Empty-state**: L2 atelier с editorial serif-копией

### 7.2 TicketsView

- **Карточка билета = L1 folio**: латунная рамка + закладка, eyebrow «Билет №XX» sans uppercase, serif title 24, serif body, micro-метрики sans
- **Grid**: 2 колонки (было 3-4), больше vertical spacing
- **Фильтры сверху**: segmented control на `sand` фоне с sans uppercase 11px; активный — `rust` text + `rust_soft` fill
- **Empty state**: L2 atelier

### 7.3 TrainingView

- **Вопрос-блок = L1 folio** большой, max-width 68ch для читабельности
- **Варианты ответов**: `atelier` с rust-hover на рамке, `brass` accent-полоса слева при фокусе клавиатурой
- **Индикация правильности**: moss (правильный) / claret (неверный), без acid-green/red
- **Evaluation panel**: L2 atelier с serif-секциями, разделёнными `OrnamentalDivider`
- **«Следующий»**: `primary` moss-кнопка, крупная, справа
- **Timer/progress**: тонкая `rust` линия поверх `sand`-полосы 2px

### 7.4 Остальные 8 вьюх (не в scope ре-вёрстки)

Наследуют theme автоматически через QSS + role-варианты CardFrame. Цель: `subjects`, `sections`, `import`, `dialogue`, `statistics`, `knowledge-map`, `defense`, `settings` становятся «приличными из коробки», без персонального ре-дизайна. Персональный проход — этап 2.

## 8. Icons

`ui/icons.py` — обновляется `tone_mapping`:
- default: `ink_muted`
- active: `rust`
- decorative: `brass`
- disabled: `ink_faint`

SVG-файлы иконок **не меняются**. Новые иконки не добавляются.

## 9. Theme package structure

```
ui/theme/
  __init__.py          # re-export публичного API
  palette.py           # LIGHT, DARK, semantic tokens, logo_palette
  typography.py        # FONT_PRESETS (serif), UI_SANS, build_typography, scale
  spacing.py           # SPACING, RADII, ELEVATION, ornaments
  materiality.py       # apply_shadow(level=...), folio paint helpers, ornamental painter
  stylesheet.py        # build_stylesheet(palette, typography) — композиция
  stylesheets/
    base.py            # глобальный reset + QWidget defaults
    buttons.py         # QPushButton variants
    inputs.py          # QLineEdit/QTextEdit/QComboBox
    cards.py           # QFrame[role="folio|atelier|paper"], accent_strip
    navigation.py      # sidebar, topbar
    lists.py           # QListView, QScrollBar
  fonts.py             # resolve_font_family, resolve_ui_font
```

### 9.1 Backward-compat

`ui/theme/__init__.py` re-export'ит весь текущий публичный API: `LIGHT`, `DARK`, `FONT_PRESETS`, `apply_shadow`, `set_app_theme`, `build_stylesheet`, `build_typography`, `logo_palette`, `current_colors`, `is_dark_palette`, `mastery_band_color`, `alpha_color`, `SPACING`, `RADII`, `DEFAULT_FONT_PRESET`, `DEFAULT_FONT_SIZE`. Это обязательное требование — все вьюхи импортируют из `ui.theme` и не должны ломаться.

### 9.2 Порядок работ (этапы для writing-plans)

1. Split механический: `ui/theme.py` → `ui/theme/` пакет без изменения значений. Тесты зелёные.
2. Обновить `palette.py` на Warm Minimal LIGHT/DARK + semantic tokens. Тесты палитры обновить.
3. Обновить `typography.py` — новый UI_SANS, сокращение FONT_PRESETS до 3 serif-пресетов. Тесты пресетов обновить.
4. Добавить `materiality.py` (ELEVATION, `apply_shadow(level=...)`, folio-paint helpers). Тест materiality добавить.
5. Переписать `stylesheet.py` и `stylesheets/*` под новые токены. После каждого подмодуля — smoke-прогон UI-тестов.
6. Обновить компоненты: `CardFrame` (роли + folio paintEvent), `LogoMark` (moss+brass палитра SVG), `MetricTile`, `IconBadge`, `ScoreBadge`, `StatusDot`, `DonutChart`. Добавить `OrnamentalDivider`.
7. Обновить shell: `Sidebar`, `TopBar`, `Splash`.
8. Переверстать три видимые вьюхи: `LibraryView`, `TicketsView`, `TrainingView`.
9. Обновить `tone_mapping` в `ui/icons.py`.
10. Manual visual gate + скриншоты (light и dark) → `docs/superpowers/screenshots/2026-04-17-warm-minimal/`.

Каждый пункт — отдельная задача в writing-plans, с тестами и точкой проверки.

## 10. Testing strategy

### 10.1 Регрессия

Все 165 текущих тестов должны оставаться зелёными после каждого шага. Тесты, завязанные на конкретные hex-цвета или имена пресетов (например, `test_logo_palette_light_values`), обновляются одновременно с соответствующим шагом и указываются в commit'е как часть изменения.

### 10.2 Новые тесты

- `tests/test_theme_palette.py` — наличие всех semantic-токенов (`paper`, `rust`, `moss`, `brass`, `cognac` ключи) в LIGHT и DARK; `is_dark_palette()` возвращает корректно; ключевые hex-значения заморожены.
- `tests/test_materiality.py` — `apply_shadow(widget, level="md", palette=LIGHT)` навешивает `QGraphicsDropShadowEffect` с правильными blur/offset/color; folio painter рисует без падений и без QPainter warnings.
- `tests/test_painter_warnings.py` — **regression-тест на шквал warnings**: `qInstallMessageHandler` собирает сообщения, `MainWindow.show()` + 3 круга по всем вкладкам через `switch_view()`, assert `0` маркеров `"A paint device can only be painted by one painter"`, `"QWidgetEffectSourcePrivate::pixmap: Painter not active"`, `"QPainter::worldTransform: Painter not active"`. Защищает работу, сделанную в `a2a5a6e` + `b5b6edb` + сегодняшний фикс nested effects.

### 10.3 Visual gate (ручной)

После шага 8 — обязательная ручная проверка:
- Запуск приложения в light palette → скриншоты Library/Tickets/Training.
- Переключение на dark (cognac leather) → те же скриншоты.
- Сравнение с мокапами из `.superpowers/brainstorm/.../content/*.html`.
- Скриншоты коммитятся в `docs/superpowers/screenshots/2026-04-17-warm-minimal/`.

## 11. Risks and mitigations

| Риск | Митигация |
|---|---|
| Folio paintEvent даёт новые QPainter warnings (как было с LogoMark в `b5b6edb`) | Рисуем на self через один `QPainter(self)` + `painter.end()`. БЕЗ QGraphicsEffect внутри. `test_painter_warnings.py` ловит регресс. |
| Georgia недоступна на отдельных Windows | `resolve_font_family` уже умеет fallback chain. Resolved chain для default preset: Georgia → Cambria → Times New Roman. |
| Тёплые тени + параметр `shadow_color` у CardFrame.__init__ — разные модели материальности | Удаляем параметр `shadow_color`, заменяем на `level="atelier"|"folio"|..."`. Палитра сама даёт оттенок. Аргумент `shadow_color` удаляется из всех call-sites. |
| 165 тестов ломаются волной | Миграция шагами, после каждого — полный прогон. Тесты обновляются в том же commit'е. |
| Dark palette выглядит не так, как в мокапах в реальном окне | Manual gate со скриншотами после шага 8. |
| User preset настройки (`FONT_PRESETS`) сохраняется со старым ключом (например, `bahnschrift`) в `settings.json` | В `FONT_PRESETS` fallback: если сохранённый preset key больше не существует, резолв возвращает default (`georgia`). Существующая логика `FONT_PRESETS.get(preset_key, FONT_PRESETS[DEFAULT])` уже это даёт. Миграция настроек не нужна. |

## 12. Out of scope (этап 1)

Явно НЕ делается:
- Переверстка 8 вьюх кроме library/tickets/training (subjects, sections, import, dialogue, statistics, knowledge-map, defense, settings)
- Новые иконки (только перекраска существующих)
- Изменения в диалогах (AdminPasswordDialog, InterfaceTextEditorDialog) — наследуют через QSS
- Изменения SVG-шаблонов логотипа (меняется только палитра токенов)
- Анимации/переходы (после урока с QGraphicsOpacityEffect — никаких QGraphicsEffect в иерархии, только `setWindowOpacity` на главное окно, если нужно)
- Изменения в бэкенд-логике, i18n, бизнес-коде
- Изменения в knowledge_graph rendering (только перекраска nodes/edges в moss/brass)

## 13. Acceptance

Этап 1 считается принятым, когда:
- [ ] Пакет `ui/theme/` существует, re-export'ит backward-compat API.
- [ ] LIGHT/DARK обновлены под Warm Minimal + Cognac leather.
- [ ] Typography: 3 serif-пресета, Inter-stack для UI_SANS, новый scale.
- [ ] Materiality: 3 уровня (`paper`/`atelier`/`folio`), новый `apply_shadow`.
- [ ] Компоненты обновлены: CardFrame, LogoMark, MetricTile, IconBadge, ScoreBadge, StatusDot, DonutChart, OrnamentalDivider.
- [ ] Shell: Sidebar, TopBar, Splash в новой редакции.
- [ ] Вьюхи: Library, Tickets, Training переверстаны согласно §7.
- [ ] `ui/icons.py` tone_mapping обновлён.
- [ ] 165 текущих тестов + 3 новых теста зелёные.
- [ ] Manual visual gate пройден, скриншоты закоммичены.
- [ ] Проверка отсутствия QPainter warnings на программном проходе по всем вкладкам.
