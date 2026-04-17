# Warm Minimal — визуальный рефреш UI (этап 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перевести UI приложения в «Warm Minimal» эстетику (sand+rust+moss в light, cognac leather в dark; serif+sans hybrid; three-tier materiality), поменяв дизайн-систему, shell и три видимые вьюхи (library, tickets, training), не ломая 165 существующих тестов.

**Architecture:** Инкрементальный рефакторинг. `ui/theme.py` разделяется на пакет `ui/theme/` (palette / typography / spacing / materiality / fonts / stylesheet + stylesheets/*). Палитры `LIGHT`/`DARK` получают новые hex-значения, но **прежние ключи сохраняются как алиасы** — весь существующий QSS и вызовы `current_colors()["primary"]` продолжают работать, просто выглядят теперь в тёплой гамме. Новые semantic tokens (`paper`, `rust`, `moss`, `brass`) добавляются рядом. `apply_shadow` переезжает на уровневую модель. Компоненты и три вьюхи получают role-варианты и переверстку.

**Tech Stack:** PySide6 (Qt6), pytest, QSS, SVG templates. Windows platform.

**Spec:** `docs/superpowers/specs/2026-04-17-warm-minimal-visual-refresh-design.md`

---

## File Structure

### Создаётся (новое)

- `ui/theme/__init__.py` — публичный re-export API (backward-compat)
- `ui/theme/palette.py` — LIGHT, DARK, logo_palette, current_colors, is_dark_palette, alpha_color, mastery_band_color
- `ui/theme/typography.py` — FONT_PRESETS (serif), UI_SANS, resolve_font_family, resolve_ui_font, build_typography, app_font
- `ui/theme/spacing.py` — SPACING, RADII, ELEVATION
- `ui/theme/materiality.py` — apply_shadow(level=...), folio paint helpers, OrnamentalDivider painter helpers
- `ui/theme/fonts.py` — вспомогательные функции резолва шрифтов (используется typography)
- `ui/theme/stylesheet.py` — build_stylesheet — композиция
- `ui/theme/stylesheets/__init__.py`
- `ui/theme/stylesheets/base.py` — глобальный reset, QWidget, QMessageBox, QScrollArea, QScrollBar
- `ui/theme/stylesheets/buttons.py` — все QPushButton варианты
- `ui/theme/stylesheets/inputs.py` — QLineEdit, QTextEdit, QComboBox
- `ui/theme/stylesheets/cards.py` — QFrame[role=...]
- `ui/theme/stylesheets/navigation.py` — sidebar, topbar frames
- `ui/theme/stylesheets/labels.py` — QLabel[role=...]
- `tests/test_theme_palette.py` — новые тесты палитры (semantic tokens, hex freeze)
- `tests/test_materiality.py` — тесты apply_shadow levels и folio paintEvent
- `tests/test_painter_warnings.py` — regression-тест на QPainter warning storm

### Модифицируется (существующее)

- `ui/theme.py` — **удаляется** после миграции (Task 1 создаёт пакет, задачи ссылаются на новые модули; старый файл удаляется в Task 1 финальным шагом)
- `ui/components/common.py` — CardFrame (role + folio paintEvent + accent_strip), LogoMark (без изменений структуры — только palette читает новые ключи), MetricTile, IconBadge, StatusDot, ScoreBadge, DonutChart, EmptyStatePanel. Добавляется OrnamentalDivider.
- `ui/components/sidebar.py` — rust-accent active item + brass-dot + serif active caption
- `ui/components/topbar.py` — parchment bg, serif заголовок, ghost-кнопки, ornamental divider
- `ui/components/splash.py` — paper bg, serif display, rust progress
- `ui/views/library_view.py` — hero-блок + ornamental divider + 2-колонка atelier
- `ui/views/tickets_view.py` — folio-карточки билетов + segmented фильтры
- `ui/views/training_view.py` — folio вопрос-блок + atelier варианты + ornamental в evaluation
- `ui/icons.py` — tone_mapping обновление
- `ui/main_window.py` — ничего (уже без QGraphicsOpacityEffect после предыдущей правки)
- `tests/test_logo_mark.py` — обновление ожидаемых hex'ов в test_logo_palette_*_values
- `tests/test_ui_handlers.py` — ничего структурного (палитра тесты не хардкодят)

Каждая задача — один закоммиченный инкремент. После каждого commit'а полный прогон тестов должен быть зелёным.

---

## Task 1: Разделить ui/theme.py на пакет (без изменения значений)

**Цель:** механический split, zero value change. После этой задачи все 165 тестов должны остаться зелёными.

**Files:**
- Create: `ui/theme/__init__.py`
- Create: `ui/theme/palette.py`
- Create: `ui/theme/typography.py`
- Create: `ui/theme/spacing.py`
- Create: `ui/theme/materiality.py`
- Create: `ui/theme/stylesheet.py`
- Delete: `ui/theme.py` (в конце задачи)

- [ ] **Step 1.1: Создать `ui/theme/spacing.py`**

```python
from __future__ import annotations


SPACING = {
    "xxs": 4,
    "xs": 8,
    "sm": 12,
    "md": 16,
    "lg": 20,
    "xl": 24,
    "2xl": 32,
}

RADII = {
    "sm": 10,
    "md": 14,
    "lg": 18,
    "xl": 22,
}
```

- [ ] **Step 1.2: Создать `ui/theme/palette.py`**

Скопировать из текущего `ui/theme.py` строки: `LIGHT` (54-79), `DARK` (82-107), `current_palette_name` (177-182), `current_colors` (185-186), `is_dark_palette` (189-190), `alpha_color` (193-196), `mastery_band_color` (199-223), `logo_palette` (226-246). Импорты — только то, что нужно:

```python
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
```

(Дальше дословно блок `LIGHT = {...}`, `DARK = {...}`, функции — без изменений значений.)

- [ ] **Step 1.3: Создать `ui/theme/typography.py`**

Скопировать `FONT_PRESETS` (26-52), `_clamp` (110-111), `resolve_font_family` (114-120), `build_typography` (123-146), `app_font` (149-152). Импорты:

```python
from __future__ import annotations

from application.ui_defaults import DEFAULT_FONT_PRESET, DEFAULT_FONT_SIZE
from PySide6.QtGui import QFont, QFontDatabase
```

- [ ] **Step 1.4: Создать `ui/theme/materiality.py`**

Пока переносит `apply_shadow` как есть (задача 5 его переделает):

```python
from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget


def apply_shadow(widget: QWidget, color: QColor, blur: int = 28, y_offset: int = 5) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(QPointF(0, y_offset))
    effect.setColor(color)
    widget.setGraphicsEffect(effect)
```

- [ ] **Step 1.5: Создать `ui/theme/stylesheet.py`**

Перенести `build_stylesheet` (249-662) и `set_app_theme` (163-174). Импорт из соседних модулей:

```python
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from application.ui_defaults import DEFAULT_FONT_PRESET, DEFAULT_FONT_SIZE
from ui.theme.palette import LIGHT, DARK, alpha_color
from ui.theme.typography import app_font, build_typography


def set_app_theme(
    app: QApplication,
    palette_name: str,
    font_preset: str = DEFAULT_FONT_PRESET,
    font_size: int = DEFAULT_FONT_SIZE,
) -> dict:
    palette = LIGHT if palette_name == "light" else DARK
    typography = build_typography(font_preset, font_size)
    app.setProperty("theme_palette_name", palette_name)
    app.setFont(app_font(font_preset, font_size))
    app.setStyleSheet(build_stylesheet(palette, typography))
    return palette


def build_stylesheet(colors: dict, typography: dict) -> str:
    family = typography["family"]
    is_dark = colors["app_bg"] == DARK["app_bg"]
    primary_pressed = QColor(colors["primary"]).darker(120 if is_dark else 114).name()
    card_pressed = QColor(colors["card_bg"]).darker(108 if is_dark else 102).name()
    secondary_hover = alpha_color(colors["primary"], 0.12 if is_dark else 0.08)
    secondary_pressed = alpha_color(colors["primary"], 0.2 if is_dark else 0.14)
    toolbar_hover = alpha_color(colors["primary"], 0.1 if is_dark else 0.06)
    toolbar_pressed = alpha_color(colors["primary"], 0.18 if is_dark else 0.12)
    nav_pressed = alpha_color(colors["primary"], 0.22 if is_dark else 0.12)
    muted_hover = alpha_color(colors["primary"], 0.1 if is_dark else 0.05)
    return f"""
    ...СКОПИРОВАТЬ дословно f-строку из текущего theme.py строки 260-662...
    """
```

(Дословно перенести f-строку QSS, 400 строк.)

- [ ] **Step 1.6: Создать `ui/theme/__init__.py` с re-export'ами**

```python
"""ui.theme — публичный API темы.

Пакет разбит на модули (palette, typography, spacing, materiality,
stylesheet). Здесь re-export'ятся все символы, чтобы существующие
импорты вида `from ui.theme import X` продолжали работать без правок.
"""
from __future__ import annotations

from ui.theme.palette import (
    LIGHT,
    DARK,
    current_palette_name,
    current_colors,
    is_dark_palette,
    alpha_color,
    mastery_band_color,
    logo_palette,
)
from ui.theme.typography import (
    FONT_PRESETS,
    resolve_font_family,
    build_typography,
    app_font,
)
from ui.theme.spacing import SPACING, RADII
from ui.theme.materiality import apply_shadow
from ui.theme.stylesheet import build_stylesheet, set_app_theme

__all__ = [
    "LIGHT",
    "DARK",
    "FONT_PRESETS",
    "SPACING",
    "RADII",
    "current_palette_name",
    "current_colors",
    "is_dark_palette",
    "alpha_color",
    "mastery_band_color",
    "logo_palette",
    "resolve_font_family",
    "build_typography",
    "app_font",
    "apply_shadow",
    "build_stylesheet",
    "set_app_theme",
]
```

- [ ] **Step 1.7: Удалить `ui/theme.py`**

```bash
rm ui/theme.py
```

- [ ] **Step 1.8: Прогнать все тесты**

Run: `python -m pytest -q`
Expected: `165 passed, 5 skipped`. Если что-то импортирует из `ui.theme` внутренний символ, отсутствующий в `__init__.py` — добавить re-export.

- [ ] **Step 1.9: Commit**

```bash
git add ui/theme/ ui/theme.py
git -c user.name="Codex Local" -c user.email="codex@local" commit -m "refactor(theme): split ui/theme.py into ui/theme/ package

Mechanical split — no value changes. Public API preserved via __init__
re-exports so every 'from ui.theme import X' keeps working.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

**Note for all subsequent tasks:** Commit command всегда запускается с `git -c user.name="Codex Local" -c user.email="codex@local"` префиксом (глобальный git user не настроен). В дальнейших задачах пишется просто `git commit ...` для краткости — подставьте префикс.

---

## Task 2: Палитры — Warm Minimal (LIGHT) + Cognac Leather (DARK)

**Цель:** заменить значения в `LIGHT`/`DARK` на warm-minimal hex'ы. **Ключи сохраняются** (app_bg, card_bg, primary, success, warning, danger, text и т.д.) — они становятся алиасами к новым семантическим цветам (например, `primary` указывает на `rust`, `card_bg` — на `parchment`). Это позволяет QSS и вызовам `current_colors()["primary"]` работать без правок.

**Files:**
- Modify: `ui/theme/palette.py`
- Modify: `tests/test_logo_mark.py` (обновляется в Task 8, сейчас не трогаем)
- Create: `tests/test_theme_palette.py`

- [ ] **Step 2.1: Написать failing test для новой палитры**

Создать `tests/test_theme_palette.py`:

```python
"""Тесты warm-minimal палитры.

Закрепляют ключевые hex-значения и наличие semantic-токенов.
Если кто-то случайно откатит цвета на старые синие — тест упадёт.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor

from ui.theme.palette import LIGHT, DARK, is_dark_palette, current_colors


def test_light_is_warm_sand_not_cold_blue() -> None:
    """Приложение выше НЕ должно иметь холодно-синюю основу."""
    # app_bg должен быть тёплым sand/paper, а не cold white/grey/blue
    app_bg = QColor(LIGHT["app_bg"])
    # Red component должен доминировать над blue в warm-minimal (тёплая гамма)
    assert app_bg.red() > app_bg.blue(), f"LIGHT.app_bg={LIGHT['app_bg']} не тёплый"
    # Канонический sand/paper
    assert LIGHT["app_bg"] == "#F8EFE2"
    assert LIGHT["card_bg"] == "#FBF6F0"  # parchment
    assert LIGHT["sidebar_bg"] == "#F1E4C9"  # sand


def test_light_accents_are_rust_moss() -> None:
    assert LIGHT["primary"] == "#A04A22"  # rust
    assert LIGHT["success"] == "#4A6150"  # sage
    assert LIGHT["warning"] == "#9B4A28"  # brick
    assert LIGHT["danger"] == "#7A2E2E"   # claret


def test_light_semantic_aliases_present() -> None:
    for key in (
        "paper", "parchment", "sand", "ink", "ink_muted", "ink_faint",
        "rust", "rust_soft", "moss", "moss_soft", "brass",
        "brick", "brick_soft", "claret", "claret_soft", "sage", "sage_soft",
    ):
        assert key in LIGHT, f"LIGHT не содержит semantic token {key!r}"


def test_dark_is_cognac_not_cold_charcoal() -> None:
    app_bg = QColor(DARK["app_bg"])
    assert app_bg.red() > app_bg.blue(), f"DARK.app_bg={DARK['app_bg']} не тёплый"
    assert DARK["app_bg"] == "#271710"  # cognac
    assert DARK["card_bg"] == "#3C2518"  # surface leather
    assert DARK["sidebar_bg"] == "#2E1D12"  # sand dark


def test_dark_accents_are_warm_lit() -> None:
    assert DARK["primary"] == "#C97A57"  # rust-lit
    assert DARK["success"] == "#9EB389"  # sage-lit


def test_semantic_aliases_identical_to_legacy_keys() -> None:
    """paper == app_bg, parchment == card_bg и т.д. — это алиасы."""
    for palette in (LIGHT, DARK):
        assert palette["paper"] == palette["app_bg"]
        assert palette["parchment"] == palette["card_bg"]
        assert palette["sand"] == palette["sidebar_bg"]
        assert palette["rust"] == palette["primary"]
        assert palette["ink"] == palette["text"]
        assert palette["ink_muted"] == palette["text_secondary"]
        assert palette["ink_faint"] == palette["text_tertiary"]
```

- [ ] **Step 2.2: Запустить тест — убедиться что падает**

Run: `python -m pytest tests/test_theme_palette.py -v`
Expected: FAIL на первом assert'е (LIGHT["app_bg"] всё ещё `#EEF3F8`).

- [ ] **Step 2.3: Переписать LIGHT в `ui/theme/palette.py`**

Заменить блок `LIGHT = {...}` целиком на:

```python
LIGHT = {
    # Поверхности (legacy keys)
    "app_bg": "#F8EFE2",          # paper
    "sidebar_bg": "#F1E4C9",      # sand (кожаный обрез)
    "surface_bg": "#FBF6F0",      # parchment surface
    "card_bg": "#FBF6F0",         # parchment
    "card_soft": "#F4E9D6",       # soft parchment
    "card_muted": "#EFE2CC",      # muted sand
    "input_bg": "#FDFAF4",        # самый светлый paper
    # Семантические акценты (legacy keys)
    "primary": "#A04A22",         # rust
    "primary_soft": "#E9D5BE",    # rust_soft
    "primary_hover": "#8A3D1A",   # rust darker
    "success": "#4A6150",         # sage
    "success_soft": "#DFE5D4",    # sage_soft
    "warning": "#9B4A28",         # brick
    "warning_soft": "#F3DDC7",    # brick_soft
    "danger": "#7A2E2E",          # claret
    "danger_soft": "#F3D9D3",     # claret_soft
    "violet_soft": "#EAE0D4",     # нейтрализовано в warm гамму
    "cyan_soft": "#DCE5D6",       # нейтрализовано
    # Текст
    "text": "#2C2520",            # ink
    "text_secondary": "#4E3E35",  # ink_muted
    "text_tertiary": "#8A7064",   # ink_faint
    # Границы
    "border": "#E0CBA8",
    "border_strong": "#C89A55",   # латунная рамка folio
    "shadow": QColor(90, 55, 25, 45),  # warm brown shadow @ level=md

    # === Semantic aliases (новый пласт имён, дублируют legacy) ===
    "paper": "#F8EFE2",
    "parchment": "#FBF6F0",
    "sand": "#F1E4C9",
    "ink": "#2C2520",
    "ink_muted": "#4E3E35",
    "ink_faint": "#8A7064",
    "rust": "#A04A22",
    "rust_soft": "#E9D5BE",
    "rust_hover": "#8A3D1A",
    "moss": "#3D4E2A",
    "moss_soft": "#DCDDBC",
    "brass": "#9C7A1E",
    "brick": "#9B4A28",
    "brick_soft": "#F3DDC7",
    "claret": "#7A2E2E",
    "claret_soft": "#F3D9D3",
    "sage": "#4A6150",
    "sage_soft": "#DFE5D4",
}
```

- [ ] **Step 2.4: Переписать DARK в `ui/theme/palette.py`**

```python
DARK = {
    "app_bg": "#271710",          # cognac
    "sidebar_bg": "#2E1D12",      # sand dark — глубже чем app_bg
    "surface_bg": "#3C2518",      # parchment-as-surface
    "card_bg": "#3C2518",
    "card_soft": "#4A2F1F",
    "card_muted": "#381E12",
    "input_bg": "#3C2518",
    "primary": "#C97A57",         # rust-lit
    "primary_soft": "#5C3220",    # rust_soft dark (opaque fallback)
    "primary_hover": "#E08A63",
    "success": "#9EB389",         # sage-lit
    "success_soft": "#2F3A28",
    "warning": "#D07A48",         # brick-lit
    "warning_soft": "#452A1A",
    "danger": "#D67580",          # claret-lit
    "danger_soft": "#46211F",
    "violet_soft": "#3A2C22",
    "cyan_soft": "#2A3028",
    "text": "#F0DDB2",            # parchment text
    "text_secondary": "#C0A68A",  # linen
    "text_tertiary": "#8A7560",
    "border": "#4A3225",
    "border_strong": "#7A5A32",
    "shadow": QColor(0, 0, 0, 140),

    # === Semantic aliases ===
    "paper": "#271710",
    "parchment": "#3C2518",
    "sand": "#2E1D12",
    "ink": "#F0DDB2",
    "ink_muted": "#C0A68A",
    "ink_faint": "#8A7560",
    "rust": "#C97A57",
    "rust_soft": "#5C3220",
    "rust_hover": "#E08A63",
    "moss": "#8BA267",            # moss-lit (CTA)
    "moss_soft": "#2E3826",
    "brass": "#C9A66B",
    "brick": "#D07A48",
    "brick_soft": "#452A1A",
    "claret": "#D67580",
    "claret_soft": "#46211F",
    "sage": "#9EB389",
    "sage_soft": "#2F3A28",
}
```

- [ ] **Step 2.5: Запустить новый тест — убедиться что проходит**

Run: `python -m pytest tests/test_theme_palette.py -v`
Expected: все 6 тестов PASS.

- [ ] **Step 2.6: Прогнать все тесты, поправить поломки**

Run: `python -m pytest -q`
Ожидается возможная поломка `test_ui_handlers.py::test_suppress_startup_background_tasks_skips_auto_threads` из-за текста «Автопроверка отключена» в SettingsView — не связано с палитрой, должно быть ОК. Если падает что-то колорное — найти по trace и обновить expected-hex в тесте под warm-цвет.

Run финально: `python -m pytest -q`
Expected: `165 + 6 (новых) = 171 passed, 5 skipped`.

- [ ] **Step 2.7: Commit**

```bash
git add ui/theme/palette.py tests/test_theme_palette.py
git -c user.name="Codex Local" -c user.email="codex@local" commit -m "feat(theme): warm-minimal light palette + cognac leather dark

LIGHT теперь sand/paper/parchment с rust+moss акцентами.
DARK — cognac leather с rust-lit CTA и sage-lit success.
Ключи-алиасы (paper, rust, moss, brass и т.д.) добавлены рядом
с legacy-ключами, чтобы QSS и компоненты могли постепенно
мигрировать на семантические имена без ломания API.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Typography — serif пресеты + UI_SANS

**Цель:** заменить 5 нейтральных `FONT_PRESETS` (segoe/bahnschrift/trebuchet/verdana/arial) на 3 засечковых (georgia/cambria/palatino). Добавить функцию `resolve_ui_font()` для micro-UI sans (Inter → Segoe UI → Bahnschrift → Arial) — этот шрифт не выбирается пользователем. Расширить `build_typography` новыми ключами: `display`, `eyebrow`, `metric_value`, `metric_label`, `subtitle`.

**Files:**
- Modify: `ui/theme/typography.py`
- Modify: `application/ui_defaults.py` — DEFAULT_FONT_PRESET = "georgia"
- Modify: `tests/test_logo_mark.py` (никак) — не трогает presets
- Проверить: `tests/test_settings_validation.py`, `tests/test_bootstrap.py` — могут хардкодить preset keys

- [ ] **Step 3.1: Найти все хардкод-упоминания старых preset keys**

Run: `python -m pytest -q -k preset` — посмотреть какие тесты.
Также:

```bash
grep -rn '"segoe"\|"bahnschrift"\|"trebuchet"\|"verdana"\|"arial"' application tests ui --include="*.py" | grep -v site-packages
```

Для каждой находки — решить: переносим ли на "georgia"/"cambria"/"palatino", или это неявные fallback-значения (удалить нельзя — удалим).

- [ ] **Step 3.2: Обновить `FONT_PRESETS` в `ui/theme/typography.py`**

Заменить `FONT_PRESETS` блоком:

```python
FONT_PRESETS = {
    "georgia": {
        "label": "Georgia",
        "description": "Классическая засечковая гарнитура для комфортного чтения.",
        "families": ["Georgia", "Cambria", "Times New Roman"],
    },
    "cambria": {
        "label": "Cambria",
        "description": "Современнее и чуть плотнее Georgia.",
        "families": ["Cambria", "Georgia", "Times New Roman"],
    },
    "palatino": {
        "label": "Palatino",
        "description": "Гуманистический сериф с мягкими формами.",
        "families": ["Palatino Linotype", "Palatino", "Georgia"],
    },
}

# UI-шрифт для микро-элементов (пиллы, метрики, кнопки). Не выбирается
# пользователем — закреплён за системой.
UI_SANS_FAMILIES = ["Inter", "Segoe UI", "Bahnschrift", "Arial"]


def resolve_ui_font() -> str:
    available = set(QFontDatabase.families())
    for family in UI_SANS_FAMILIES:
        if family in available:
            return family
    return QFont().defaultFamily()
```

- [ ] **Step 3.3: Расширить `build_typography`**

Добавить новые ключи scale + ui_family. Заменить функцию:

```python
def build_typography(font_preset: str, font_size: int) -> dict[str, int | str]:
    base_point = _clamp(font_size or DEFAULT_FONT_SIZE, 9, 18)
    body_px = _clamp(round(base_point * 1.4), 13, 22)
    return {
        # Семьи
        "family": resolve_font_family(font_preset),  # serif body
        "ui_family": resolve_ui_font(),              # sans micro-UI
        "base_point": base_point,
        # Serif scale
        "display": _clamp(body_px + 16, 28, 40),        # splash, welcome hero
        "hero": _clamp(body_px + 12, 24, 34),           # legacy — синоним display-small
        "page_title": _clamp(body_px + 10, 22, 30),
        "brand_title": _clamp(body_px + 8, 22, 34),
        "section_title": _clamp(body_px + 4, 18, 24),
        "card_title": _clamp(body_px + 2, 16, 22),
        "body": body_px,
        "subtitle": _clamp(body_px - 1, 12, 18),
        "brand_subtitle": _clamp(body_px - 1, 12, 18),
        "page_subtitle": _clamp(body_px, 13, 20),
        "muted": _clamp(body_px - 1, 12, 18),
        "window_title": _clamp(body_px, 13, 18),
        # Sans micro-UI scale
        "eyebrow": _clamp(body_px - 4, 9, 12),
        "micro": _clamp(body_px - 3, 10, 13),
        "pill": _clamp(body_px - 2, 11, 16),
        "nav_caption": _clamp(body_px - 1, 12, 17),
        "metric_value": _clamp(body_px + 6, 18, 26),
        "metric_label": _clamp(body_px - 3, 10, 13),
        "status": _clamp(body_px - 1, 12, 18),
        "search": _clamp(body_px + 1, 14, 22),
        "input": body_px,
        "button": body_px,
        "editor": body_px,
        "combo": body_px,
    }
```

- [ ] **Step 3.4: Обновить default preset в `application/ui_defaults.py`**

Открыть файл `application/ui_defaults.py`, найти строку с `DEFAULT_FONT_PRESET =` и заменить значение на `"georgia"`.

- [ ] **Step 3.5: Добавить re-export `resolve_ui_font` в `ui/theme/__init__.py`**

В блок `from ui.theme.typography import (...)` добавить `resolve_ui_font` и в `__all__` — тоже.

- [ ] **Step 3.6: Прогнать тесты**

Run: `python -m pytest -q`
Если `tests/test_settings_validation.py` падает из-за ожидания preset key `"segoe"` — обновить его на `"georgia"`. Если тест проверяет список допустимых ключей — перечислить новые три.

- [ ] **Step 3.7: Проверить вручную миграцию settings.json**

Если пользователь уже имел `settings.json` с `font_preset="segoe"`, функция `resolve_font_family("segoe")` через `FONT_PRESETS.get("segoe", FONT_PRESETS[DEFAULT])` вернёт `FONT_PRESETS["georgia"]` fallback → резолвится Georgia. Это ожидаемое поведение, править не надо.

Убедиться, что `application/settings_store.py` или схема валидации не rejects неизвестные preset keys. Если rejects — добавить миграцию: при load, если `font_preset not in FONT_PRESETS`, сбросить на `DEFAULT_FONT_PRESET`.

- [ ] **Step 3.8: Commit**

```bash
git add ui/theme/typography.py ui/theme/__init__.py application/ui_defaults.py tests/
git commit -m "feat(theme): serif FONT_PRESETS (Georgia/Cambria/Palatino) + UI sans stack

FONT_PRESETS сокращён с 5 нейтральных до 3 серифных пресетов
(пользовательский выбор — body/heading serif). Для micro-UI
добавлен системный UI_SANS_FAMILIES (Inter → Segoe UI → ...)
резолвимый через resolve_ui_font() — не выбирается пользователем.

build_typography расширен ключами display/eyebrow/metric_value/
metric_label/subtitle/page_title для warm-minimal scale.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Расширить SPACING и RADII, добавить ELEVATION

**Цель:** ввести новые токены `xs` (4) в RADII, `ELEVATION` таблицу уровней теней.

**Files:**
- Modify: `ui/theme/spacing.py`

- [ ] **Step 4.1: Обновить `ui/theme/spacing.py`**

Заменить содержимое целиком:

```python
from __future__ import annotations

from PySide6.QtGui import QColor


SPACING = {
    "xxs": 4,
    "xs": 8,
    "sm": 12,
    "md": 16,
    "lg": 20,
    "xl": 24,
    "2xl": 32,
    "3xl": 40,
}

RADII = {
    "xs": 4,
    "sm": 6,
    "md": 10,
    "lg": 14,
    "xl": 18,
    "2xl": 22,
    "pill": 999,
}


# Уровни материальности (тени). См. spec §4.
# Ключи: blur — радиус размытия; dy — смещение по Y; alpha — 0..255
# для warm-brown shadow (light) или чёрного (dark, рассчитывается отдельно).
ELEVATION = {
    "sm": {"blur": 4, "dy": 1, "alpha_light": 15, "alpha_dark": 60},
    "md": {"blur": 22, "dy": 10, "alpha_light": 45, "alpha_dark": 100},
    "lg": {"blur": 28, "dy": 14, "alpha_light": 90, "alpha_dark": 140},
}


def shadow_color(is_dark: bool, level: str) -> QColor:
    """Warm brown shadow для light / глубокая чёрная для dark.

    Level должен быть одним из 'sm' | 'md' | 'lg'.
    """
    spec = ELEVATION[level]
    alpha = spec["alpha_dark"] if is_dark else spec["alpha_light"]
    if is_dark:
        return QColor(0, 0, 0, alpha)
    return QColor(90, 55, 25, alpha)
```

- [ ] **Step 4.2: Re-export ELEVATION и shadow_color в `ui/theme/__init__.py`**

В импорт из spacing добавить `ELEVATION`, `shadow_color`. В `__all__` — тоже.

- [ ] **Step 4.3: Прогнать тесты**

Run: `python -m pytest -q` — должно быть зелёным (ELEVATION пока никем не используется).

- [ ] **Step 4.4: Commit**

```bash
git add ui/theme/spacing.py ui/theme/__init__.py
git commit -m "feat(theme): add ELEVATION levels and RADII xs/2xl/pill tokens

ELEVATION: sm/md/lg (blur+dy+alpha) для трёхуровневой
материальности (paper/atelier/folio).
shadow_color(is_dark, level) возвращает warm-brown в light и
глубокий чёрный в dark.
RADII расширен до xs(4)/md(10)/2xl(22)/pill(999).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: apply_shadow уровневый + folio paint helpers + OrnamentalDivider helper

**Цель:** перевести `apply_shadow` на сигнатуру `(widget, level, palette)`. Добавить helpers для рисования folio-карточки и ornamental-разделителя.

**Files:**
- Modify: `ui/theme/materiality.py`
- Modify: `ui/theme/__init__.py`
- Modify: `ui/components/common.py` (call-site `CardFrame.__init__` — 1 место использования apply_shadow)
- Create: `tests/test_materiality.py`

- [ ] **Step 5.1: Написать failing test для apply_shadow levels**

Создать `tests/test_materiality.py`:

```python
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget

from ui.theme.materiality import apply_shadow
from ui.theme.palette import LIGHT, DARK


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_apply_shadow_md_light(qt_app) -> None:
    widget = QWidget()
    apply_shadow(widget, "md", LIGHT)
    effect = widget.graphicsEffect()
    assert isinstance(effect, QGraphicsDropShadowEffect)
    assert effect.blurRadius() == 22
    assert effect.yOffset() == 10
    color = effect.color()
    # warm brown tint — red > blue
    assert color.red() > color.blue()
    assert color.alpha() == 45


def test_apply_shadow_lg_dark(qt_app) -> None:
    widget = QWidget()
    apply_shadow(widget, "lg", DARK)
    effect = widget.graphicsEffect()
    assert effect.blurRadius() == 28
    assert effect.yOffset() == 14
    assert effect.color().alpha() == 140


def test_apply_shadow_sm_barely_visible(qt_app) -> None:
    widget = QWidget()
    apply_shadow(widget, "sm", LIGHT)
    effect = widget.graphicsEffect()
    assert effect.blurRadius() == 4
    assert effect.color().alpha() == 15


def test_apply_shadow_rejects_invalid_level(qt_app) -> None:
    widget = QWidget()
    with pytest.raises(KeyError):
        apply_shadow(widget, "invalid", LIGHT)
```

- [ ] **Step 5.2: Запустить тест — убедиться что падает**

Run: `python -m pytest tests/test_materiality.py -v`
Expected: FAIL — `apply_shadow` принимает старую сигнатуру `(widget, QColor, blur, y_offset)`.

- [ ] **Step 5.3: Переписать `ui/theme/materiality.py`**

Заменить содержимое целиком:

```python
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from ui.theme.spacing import ELEVATION, shadow_color
from ui.theme.palette import DARK


def apply_shadow(widget: QWidget, level: str, palette: dict) -> None:
    """Навесить тень одного из 3 уровней (sm/md/lg).

    palette — LIGHT или DARK словарь. Определяется по нему светлая/тёмная
    редакция shadow (warm brown vs pure black).
    """
    spec = ELEVATION[level]  # KeyError если уровень некорректный
    is_dark = palette["app_bg"] == DARK["app_bg"]
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(spec["blur"])
    effect.setOffset(QPointF(0, spec["dy"]))
    effect.setColor(shadow_color(is_dark, level))
    widget.setGraphicsEffect(effect)


def paint_folio(painter: QPainter, rect: QRectF, palette: dict,
                outer_radius: float = 10, inner_radius: float = 6,
                outer_pad: float = 8, accent: str = "rust") -> None:
    """Нарисовать folio-карточку: латунная outer-рамка + parchment inner
    + закладка 4×44 сверху цвета accent.

    Вызывать из CardFrame(role='folio').paintEvent(). ВАЖНО: painter
    должен быть создан на самом виджете (QPainter(self)); никаких
    QGraphicsEffect внутри этого метода — это регрессия QPainter warnings.
    """
    # Внешний слой (латунная рамка)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    outer_fill = QColor(palette["border_strong"])
    painter.setBrush(QBrush(outer_fill))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(rect, outer_radius, outer_radius)
    # Внутренняя бумага
    inner = rect.adjusted(outer_pad, outer_pad, -outer_pad, -outer_pad)
    painter.setBrush(QBrush(QColor(palette["parchment"])))
    painter.drawRoundedRect(inner, inner_radius, inner_radius)
    # Закладка сверху
    accent_color = QColor(palette.get(accent, palette["rust"]))
    strip_w, strip_h = 44.0, 4.0
    strip_x = rect.center().x() - strip_w / 2
    strip_y = rect.top()
    painter.setBrush(QBrush(accent_color))
    # Закруглённый внизу, плоский вверху (закладка)
    painter.drawRoundedRect(QRectF(strip_x, strip_y, strip_w, strip_h),
                            0, 0)


def paint_ornamental_divider(painter: QPainter, rect: QRectF,
                             palette: dict, dot_color: str = "brass",
                             line_color: str = "border") -> None:
    """Тонкая 1px линия цвета line_color с центральной точкой ⌀4 цвета
    dot_color. Используется в editorial-местах как разделитель секций.
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    mid_y = rect.center().y()
    # Линия
    pen = QPen(QColor(palette[line_color]))
    pen.setWidthF(1.0)
    painter.setPen(pen)
    painter.drawLine(QPointF(rect.left(), mid_y), QPointF(rect.right(), mid_y))
    # Точка посередине
    dot_r = 2.0
    cx = rect.center().x()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(palette[dot_color])))
    # Заливка фоном бумаги под точкой, чтобы линия разрывалась
    gap = 10.0
    painter.drawRect(QRectF(cx - gap / 2, mid_y - 1, gap, 2))
    painter.setBrush(QBrush(QColor(palette[dot_color])))
    painter.drawEllipse(QPointF(cx, mid_y), dot_r, dot_r)
```

- [ ] **Step 5.4: Обновить call-site в `ui/components/common.py`**

Найти в `CardFrame.__init__` строку с `apply_shadow(self, shadow_color)` (приблизительно строка 63) и заменить:

```python
class CardFrame(QFrame):
    def __init__(self, role: str = "card", shadow_color: QColor | None = None,
                 shadow: bool = True, shadow_level: str = "md") -> None:
        super().__init__()
        self.setProperty("role", role)
        # shadow_color параметр оставлен для обратной совместимости при
        # поэтапной миграции call-sites на shadow_level; предпочитаемый
        # путь — shadow_level. Если указан shadow_color — игнорируем и
        # используем level из палитры.
        if shadow and shadow_level:
            from ui.theme.palette import current_colors
            apply_shadow(self, shadow_level, current_colors())
```

Импорт `apply_shadow` в `common.py` остаётся — он уже импортировался.

- [ ] **Step 5.5: Прогнать тесты**

Run: `python -m pytest tests/test_materiality.py -v`
Expected: все 4 теста PASS.

Run: `python -m pytest -q`
Expected: зелёное. Если что-то ломается из-за старой сигнатуры `apply_shadow(widget, color, blur, offset)` — grep по репо `apply_shadow(` и обновить остальные call-sites. Ожидаемое: только 1 call-site в `CardFrame.__init__`; `ui/theme/materiality.py` — само определение.

- [ ] **Step 5.6: Re-export новых helpers в `ui/theme/__init__.py`**

В импорте из materiality добавить `paint_folio`, `paint_ornamental_divider`. В `__all__` — тоже.

- [ ] **Step 5.7: Commit**

```bash
git add ui/theme/materiality.py ui/theme/__init__.py ui/components/common.py tests/test_materiality.py
git commit -m "feat(theme): level-based apply_shadow + folio/ornamental paint helpers

apply_shadow теперь принимает level ('sm'|'md'|'lg') и palette dict.
Старая сигнатура (widget, QColor, blur, y_offset) удалена — все
call-sites обновлены.

paint_folio() рисует двухслойную карточку + закладку (для
CardFrame[role='folio'] paintEvent).
paint_ornamental_divider() — тонкая линия с brass-точкой.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: QSS — добавить новые role/variant правила

**Цель:** расширить `build_stylesheet` правилами для `QFrame[role="folio"|"atelier"|"paper"]`, новых button variants (`primary`/`secondary`/`ghost`/`danger`) и новых label roles (`eyebrow`, `metric_value`, `metric_label`). Старые правила остаются — backward-compat.

**Files:**
- Modify: `ui/theme/stylesheet.py`

- [ ] **Step 6.1: Добавить новые QSS-правила в `build_stylesheet`**

В f-string QSS ДОПОЛНИТЕЛЬНО к существующему (не удаляя) добавить, прямо перед закрывающим `"""`:

```python
    # Новые role-варианты для Warm Minimal materiality
    QFrame[role="folio-card"] {{
        background: transparent;
        border: none;
    }}
    QFrame[role="atelier-card"] {{
        background: {colors["parchment"]};
        border: 1px solid {colors["border"]};
        border-radius: 12px;
    }}
    QFrame[role="paper-card"] {{
        background: {colors["paper"]};
        border: 1px solid {colors["border"]};
        border-radius: 6px;
    }}
    /* Новые label roles */
    QLabel[role="eyebrow"] {{
        font-family: "{typography["ui_family"]}";
        font-size: {typography["eyebrow"]}px;
        color: {colors["rust"]};
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
    }}
    QLabel[role="metric-value"] {{
        font-family: "{typography["ui_family"]}";
        font-size: {typography["metric_value"]}px;
        color: {colors["moss"]};
        font-weight: 700;
    }}
    QLabel[role="metric-label"] {{
        font-family: "{typography["ui_family"]}";
        font-size: {typography["metric_label"]}px;
        color: {colors["ink_muted"]};
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
    }}
    QLabel[role="subtitle-italic"] {{
        font-family: "{family}";
        font-size: {typography["subtitle"]}px;
        font-style: italic;
        color: {colors["ink_muted"]};
    }}
    /* Ghost и danger button variants */
    QPushButton[variant="ghost"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {colors["ink_muted"]};
        padding: 9px 16px;
        font-family: "{typography["ui_family"]}";
    }}
    QPushButton[variant="ghost"]:hover {{
        color: {colors["rust"]};
        background: {colors["rust_soft"]};
    }}
    QPushButton[variant="ghost"]:pressed {{
        background: {colors["rust_soft"]};
        color: {colors["rust_hover"]};
    }}
    QPushButton[variant="danger"] {{
        background: {colors["claret"]};
        border: 1px solid {colors["claret"]};
        color: {colors["parchment"]};
        padding: 9px 16px;
        font-family: "{typography["ui_family"]}";
        font-weight: 600;
    }}
    QPushButton[variant="danger"]:hover {{
        background: {QColor(colors["claret"]).darker(110).name()};
    }}
    /* Rust accent-полоса для sidebar-active (через border-left) */
    QPushButton[variant="nav"][active-warm="true"] {{
        background: transparent;
        border: none;
        border-left: 3px solid {colors["rust"]};
        color: {colors["ink"]};
        font-family: "{family}";
        font-size: {typography["nav_caption"]}px;
        font-weight: 600;
        padding-left: 13px;
    }}
```

- [ ] **Step 6.2: Также обновить существующие QSS-правила на новые ключи (где уместно)**

Найти в f-string блок `QFrame[role="card"]` (выше), и рядом с ним добавить блок `QFrame[role="subtle-card"]`. Они уже есть — их НЕ трогаем; добавляем ТОЛЬКО новые rules. Это избавляет от риска сломать существующие вьюхи.

В существующих правилах `QPushButton[variant="primary"]` — заменить явное белое `color: white;` на `color: {colors["parchment"]};` (одна строка ≈474). Это чтобы CTA-текст был кремовый, а не чисто-белый:

Найти:
```python
    QPushButton[variant="primary"] {{
        background: {colors["primary"]};
        color: white;
```

Заменить `color: white;` на `color: {colors["parchment"]};` (всего в двух местах: secondary checked в nav и primary checked). Для nav:checked:

```python
    QPushButton[variant="nav"]:checked {{
        background: {colors["primary"]};
        color: {colors["parchment"]};
        border-color: {colors["primary"]};
    }}
```

- [ ] **Step 6.3: Прогнать тесты**

Run: `python -m pytest -q`
Expected: зелёное. Визуальные изменения QSS не ломают тесты; smoke-тесты создают MainWindow и прогоняют взаимодействия.

- [ ] **Step 6.4: Commit**

```bash
git add ui/theme/stylesheet.py
git commit -m "feat(theme): QSS for folio/atelier/paper roles + ghost/danger buttons

Добавлены правила для QFrame[role='folio-card'/'atelier-card'/'paper-card'],
label roles eyebrow/metric-value/metric-label/subtitle-italic,
QPushButton[variant='ghost'|'danger'], активного nav с rust-полосой.
Существующие правила не удалены — backward-compat с текущими вьюхами.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: CardFrame — folio/atelier/paper роли + accent_strip + folio paintEvent

**Цель:** расширить `CardFrame` новой семантикой роли. Для `role="folio"` — кастомный paintEvent через `paint_folio()`.

**Files:**
- Modify: `ui/components/common.py`
- Create test or modify: `tests/test_common_components.py` (создать если нет)

- [ ] **Step 7.1: Найти CardFrame в `ui/components/common.py`**

Текущий класс (строки ~58-64 по состоянию на момент написания этого plan'а). Сигнатура:

```python
class CardFrame(QFrame):
    def __init__(self, role: str = "card", shadow_color: QColor | None = None, shadow: bool = True) -> None:
        ...
```

Роль может быть любой строкой — QSS уже реагирует на `role="card"`, `role="subtle-card"`, `role="mode-card"`, `role="document-item"`, `role="table-row"`, `role="empty-icon-shell"`. Новые роли: `folio`, `atelier-card` (NB: `atelier`, а не `atelier-card` в API), `paper-card` — в QSS они называются `atelier-card` и `paper-card`.

Унифицируем: API-role → QSS-role mapping:
- `"folio"` → `"folio-card"` (QSS обрабатывает через paintEvent, QSS правило просто transparent border)
- `"atelier"` → `"atelier-card"`
- `"paper"` → `"paper-card"`
- Остальные старые роли остаются как есть (передаются в QSS напрямую).

- [ ] **Step 7.2: Переписать CardFrame**

Заменить класс `CardFrame` целиком:

```python
class CardFrame(QFrame):
    """Карточка с материальностью из 3 уровней (folio / atelier / paper)
    плюс legacy-роли (card, subtle-card, mode-card, etc.).

    Новые параметры:
        role: str — 'folio' | 'atelier' | 'paper' | <legacy>
        accent_strip: str | None — 'rust' | 'moss' | None;
            рисуется как 2×44 линия под atelier-карточкой (через paintEvent)
            или как 4×44 закладка сверху folio-карточки.
        shadow_level: str — 'sm' | 'md' | 'lg'. Для folio/paper —
            автоматически подбирается ('lg'/'sm'). Для atelier по умолчанию 'md'.

    Legacy:
        shadow_color (QColor|None) — игнорируется (оставлен в сигнатуре
            для неразрушающей миграции call-sites).
    """

    _ROLE_ALIASES = {"folio": "folio-card", "atelier": "atelier-card", "paper": "paper-card"}
    _DEFAULT_SHADOW_LEVELS = {"folio": "lg", "atelier": "md", "paper": "sm"}

    def __init__(self, role: str = "card", shadow_color: QColor | None = None,
                 shadow: bool = True, shadow_level: str | None = None,
                 accent_strip: str | None = None) -> None:
        super().__init__()
        self._api_role = role
        qss_role = self._ROLE_ALIASES.get(role, role)
        self.setProperty("role", qss_role)
        self._accent_strip = accent_strip
        if shadow:
            level = shadow_level or self._DEFAULT_SHADOW_LEVELS.get(role, "md")
            from ui.theme.palette import current_colors
            apply_shadow(self, level, current_colors())

    def paintEvent(self, event) -> None:  # noqa: N802
        """Folio и atelier (с accent_strip) рисуются вручную.

        НИКАКИХ QGraphicsEffect внутри этого метода — регрессия
        QPainter warnings (см. commit a2a5a6e и docs/PICKUP.md).
        """
        if self._api_role == "folio":
            from ui.theme.materiality import paint_folio
            from ui.theme.palette import current_colors
            painter = QPainter(self)
            try:
                paint_folio(
                    painter,
                    QRectF(0, 0, self.width(), self.height()),
                    current_colors(),
                    accent=self._accent_strip or "rust",
                )
            finally:
                painter.end()
            return
        # Остальные роли — QSS рисует фон/границу, добавляем accent_strip если задан
        super().paintEvent(event)
        if self._accent_strip:
            from ui.theme.palette import current_colors
            painter = QPainter(self)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                colors = current_colors()
                accent = QColor(colors.get(self._accent_strip, colors["rust"]))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(accent)
                strip_w = min(44.0, self.width() * 0.6)
                strip_h = 2.0
                x = (self.width() - strip_w) / 2
                y = self.height() - strip_h - 8
                painter.drawRoundedRect(QRectF(x, y, strip_w, strip_h), 1, 1)
            finally:
                painter.end()
```

(Импорт `QPainter`, `QRectF`, `QColor`, `Qt` уже есть сверху файла; `apply_shadow` — тоже.)

- [ ] **Step 7.3: Добавить OrnamentalDivider widget**

В конец `ui/components/common.py` добавить:

```python
class OrnamentalDivider(QWidget):
    """Тонкая 1px линия с центральной brass-точкой ⌀4.

    Используется в editorial-местах как декоративный разделитель
    секций. Minimum height 16px, ширина тянется layout-ом.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(16)
        self.setFixedHeight(16)

    def paintEvent(self, event) -> None:  # noqa: N802
        from ui.theme.materiality import paint_ornamental_divider
        from ui.theme.palette import current_colors
        painter = QPainter(self)
        try:
            paint_ornamental_divider(
                painter,
                QRectF(0, 0, self.width(), self.height()),
                current_colors(),
            )
        finally:
            painter.end()
```

- [ ] **Step 7.4: Прогнать тесты**

Run: `python -m pytest -q`
Expected: зелёное. Существующие call-sites `CardFrame(role="card", shadow_color=...)` продолжают работать (параметр `shadow_color` принимается и игнорируется).

- [ ] **Step 7.5: Commit**

```bash
git add ui/components/common.py
git commit -m "feat(ui): CardFrame folio/atelier/paper roles + OrnamentalDivider

CardFrame новые роли: folio (двухслойная рамка+закладка через
paint_folio), atelier (QSS), paper (QSS). Параметр accent_strip
рисует 2×44 линию под atelier/paper или 4×44 закладку у folio.
Legacy параметр shadow_color оставлен в сигнатуре для совместимости,
игнорируется — уровень тени теперь определяется из role.

OrnamentalDivider — декоративный разделитель с brass-точкой,
paintEvent через paint_ornamental_divider.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: LogoMark — палитра moss+brass

**Цель:** обновить `logo_palette()` на новые цвета (moss вместо emerald, brass вместо gold). Обновить тесты `test_logo_mark.py`.

**Files:**
- Modify: `ui/theme/palette.py` (функция `logo_palette`)
- Modify: `tests/test_logo_mark.py`

- [ ] **Step 8.1: Обновить failing-тесты в `tests/test_logo_mark.py`**

Найти тесты `test_logo_palette_light_values` и `test_logo_palette_dark_values`. Заменить ожидаемые значения:

```python
def test_logo_palette_light_values() -> None:
    from ui.theme import logo_palette
    palette = logo_palette(is_dark=False)
    assert palette == {
        "emerald_stop_0": "#2F463A",  # moss deep
        "emerald_stop_1": "#6E8554",  # moss mid
        "gold_stop_0": "#9C7A1E",      # brass
        "gold_stop_1": "#D0A444",      # brass light
    }


def test_logo_palette_dark_values() -> None:
    from ui.theme import logo_palette
    palette = logo_palette(is_dark=True)
    assert palette == {
        "emerald_stop_0": "#6E8554",  # moss-lit base
        "emerald_stop_1": "#A8BE8A",  # moss-lit tip
        "gold_stop_0": "#C9A66B",      # brass-lit
        "gold_stop_1": "#E6CE8F",      # brass-lit tip
    }
```

(Ключи `emerald_stop_*` и `gold_stop_*` оставляем — SVG-шаблоны подставляются по этим именам. Меняем только значения.)

- [ ] **Step 8.2: Запустить — убедиться что падает**

Run: `python -m pytest tests/test_logo_mark.py -v`
Expected: FAIL — в `logo_palette` всё ещё старые emerald/gold hex'ы.

- [ ] **Step 8.3: Переписать `logo_palette` в `ui/theme/palette.py`**

Заменить функцию:

```python
def logo_palette(is_dark: bool) -> dict[str, str]:
    """Палитра бренд-медальона для подстановки в SVG-шаблон.

    Ключи совпадают с плейсхолдерами `{{name}}` в `assets/logo/mark-*.svg.template`.
    Значения зафиксированы в warm-minimal редакции (moss вместо emerald,
    brass вместо gold).
    """
    if is_dark:
        return {
            "emerald_stop_0": "#6E8554",
            "emerald_stop_1": "#A8BE8A",
            "gold_stop_0": "#C9A66B",
            "gold_stop_1": "#E6CE8F",
        }
    return {
        "emerald_stop_0": "#2F463A",
        "emerald_stop_1": "#6E8554",
        "gold_stop_0": "#9C7A1E",
        "gold_stop_1": "#D0A444",
    }
```

- [ ] **Step 8.4: Прогнать тесты**

Run: `python -m pytest tests/test_logo_mark.py -v`
Expected: все logo-тесты PASS.

Run: `python -m pytest -q`
Expected: весь пакет зелёный.

- [ ] **Step 8.5: Commit**

```bash
git add ui/theme/palette.py tests/test_logo_mark.py
git commit -m "feat(logo): repaint brand medallion to moss + brass

logo_palette() теперь возвращает moss (вместо emerald) и brass
(вместо gold) — соответствует warm-minimal палитре. Ключи SVG
плейсхолдеров не изменились, шаблоны не трогаются.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Остальные компоненты — MetricTile, IconBadge, StatusDot, ScoreBadge, DonutChart

**Цель:** мелкие компоненты переезжают на новые role/variant QSS + sans шрифт для цифр. SVG и layouts не трогаем — только styling.

**Files:**
- Modify: `ui/components/common.py`

- [ ] **Step 9.1: Обновить IconBadge**

Найти класс `IconBadge` в `ui/components/common.py`. В `refresh_theme` заменить stylesheet:

```python
def refresh_theme(self) -> None:
    from ui.theme.palette import current_colors
    from ui.theme.typography import resolve_ui_font
    colors = current_colors()
    ui_family = resolve_ui_font()
    self.setStyleSheet(
        f"QFrame {{ background: {self._bg_color}; border-radius: {self._radius}px; }}"
        f"QLabel {{ color: {self._fg_color}; font-family: \"{ui_family}\"; "
        f"font-size: {self._font_size}px; font-weight: 700; }}"
    )
```

- [ ] **Step 9.2: Обновить StatusDot**

Найти класс `StatusDot`. Заменить stylesheet'ы в `__init__` на использование палитры + ui-font:

```python
class StatusDot(QFrame):
    def __init__(self, text: str, color: str | None = None) -> None:
        super().__init__()
        from ui.theme.palette import current_colors
        from ui.theme.typography import resolve_ui_font
        colors = current_colors()
        dot_color = color or colors["moss"]
        ui_family = resolve_ui_font()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        dot = QLabel("\u25cf")
        dot.setStyleSheet(f"color: {dot_color}; font-size: 12px;")
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        label = QLabel(text)
        label.setProperty("role", "status-ok")
        label.setStyleSheet(f"font-family: \"{ui_family}\";")
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)
```

- [ ] **Step 9.3: Обновить ScoreBadge**

Найти `ScoreBadge`. Переписать:

```python
class ScoreBadge(QLabel):
    def __init__(self, value: int, tone: str | None = None) -> None:
        super().__init__(f"{value}%")
        from ui.theme.palette import current_colors
        from ui.theme.typography import resolve_ui_font
        colors = current_colors()
        ui_family = resolve_ui_font()
        if value >= 70:
            bg, fg = colors["moss_soft"], colors["moss"]
        elif value >= 40:
            bg, fg = colors["rust_soft"], colors["rust"]
        else:
            bg, fg = colors["claret_soft"], colors["claret"]
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 12px;"
            f"padding: 7px 10px; font-size: 13px; font-weight: 700;"
            f"font-family: \"{ui_family}\"; font-feature-settings: 'tnum';"
        )
```

(Параметр `tone` оставлен в сигнатуре для backward-compat с call-sites, но игнорируется — цвет выводится из value.)

- [ ] **Step 9.4: Обновить DonutChart.paintEvent**

Найти метод `paintEvent` в `DonutChart`. Заменить `track` на sand (чтобы кольцо было на тёплой подложке, а не холодно-серой) и обновить шрифты. Ищите строку `self.track = QColor(track)` в `__init__` — в `paintEvent` уже используется `self.track`. Меняем только константу-дефолт в `__init__`:

Найти `def __init__(self, percent: int, accent: str = "#18B06A", track: str = "#E6EEF6", diameter: int = 96):`

Заменить на:

```python
def __init__(self, percent: int, accent: str | None = None,
             track: str | None = None, diameter: int = 96) -> None:
    super().__init__()
    from ui.theme.palette import current_colors
    colors = current_colors()
    self.percent = percent
    self.accent = QColor(accent or colors["moss"])
    self.track = QColor(track or colors["sand"])
    self.diameter = diameter
    self.setMinimumSize(diameter + 36, diameter + 54)
```

В методе `paintEvent` в месте где устанавливается font для процента:

```python
painter.setFont(QFont(QApplication.font().family(), max(15, int(round(diameter * 0.24))), 800))
```

Оставить как есть — QApplication.font() уже возвращает serif после set_app_theme. Но добавить tabular-nums:

Заменить строку на:
```python
proc_font = QFont(QApplication.font().family(), max(15, int(round(diameter * 0.24))), 800)
proc_font.setFeature("tnum", 1) if hasattr(proc_font, "setFeature") else None
painter.setFont(proc_font)
```

(Qt 6 ещё не умеет setFeature у QFont на всех платформах — hasattr-страховка.)

- [ ] **Step 9.5: Обновить MetricTile**

Найти класс `MetricTile`. В методе `set_content` заменить stylesheets для `value_label` и `text_label`:

Текущий:
```python
self.value_label.setStyleSheet(f"font-size: {16 if self.compact else 18}px; font-weight: 800; color: {colors['text']};")
self.text_label.setStyleSheet(
    f"font-size: {10 if self.compact else 11}px; color: {colors['text_secondary']}; font-weight: 600; line-height: 1.2;"
)
```

Заменить на:
```python
from ui.theme.typography import resolve_ui_font
ui_family = resolve_ui_font()
self.value_label.setProperty("role", "metric-value")
self.text_label.setProperty("role", "metric-label")
# Переприменить QSS-свойство role
self.value_label.style().unpolish(self.value_label)
self.value_label.style().polish(self.value_label)
self.text_label.style().unpolish(self.text_label)
self.text_label.style().polish(self.text_label)
```

(Убираем inline stylesheet — теперь QSS `QLabel[role="metric-value"]` из Task 6 сам красит.)

В `__init__` MetricTile — передать `role="atelier"` в `super().__init__()`:

Найти:
```python
super().__init__(role="subtle-card", shadow_color=shadow_color)
```

Заменить на:
```python
super().__init__(role="atelier", shadow_level="md")
```

(`shadow_color` больше не передаётся; `shadow_level="md"` явно означает atelier-уровень.)

- [ ] **Step 9.6: Прогнать тесты**

Run: `python -m pytest -q`
Expected: зелёное. Если MetricTile тест проверяет конкретную подстроку в stylesheet — обновить тест (но это маловероятно: MetricTile тесты обычно функциональные).

- [ ] **Step 9.7: Commit**

```bash
git add ui/components/common.py
git commit -m "feat(ui): restyle IconBadge/StatusDot/ScoreBadge/DonutChart/MetricTile

Мелкие компоненты перестроены на новую палитру и sans-шрифт для
цифровой информации:
- ScoreBadge: автоцвет из value (moss/rust/claret), tabular-nums
- StatusDot: default dot = moss (было #18B06A acid-green)
- DonutChart: accent=moss, track=sand (было голубой #E6EEF6)
- MetricTile: теперь role='atelier', роли QSS metric-value/metric-label
- IconBadge: ui-font через resolve_ui_font()

Параметры shadow_color/tone оставлены в сигнатурах для обратной
совместимости с call-sites, игнорируются.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Sidebar — rust-accent + serif active caption

**Цель:** переверстать `ui/components/sidebar.py`: фон `sand`, активный пункт без заливки, rust-accent полоса 3px слева, brass-dot справа. Serif шрифт для captions.

**Files:**
- Modify: `ui/components/sidebar.py`

- [ ] **Step 10.1: Прочитать текущий `ui/components/sidebar.py`**

Run: `Read ui/components/sidebar.py`. Зафиксировать:
- Класс `Sidebar(QFrame)` с `setProperty("role", "sidebar")`.
- Способ отрисовки nav-items (QPushButton с variant="nav" или кастомные QFrame).
- Как хранится состояние active (через `setChecked` на QPushButton или через property).

- [ ] **Step 10.2: Обновить nav-item: добавить rust accent-полосу**

Если nav-items — `QPushButton(variant="nav")`:
- Использовать уже добавленное QSS-правило из Task 6 Step 6.1 — `QPushButton[variant="nav"][active-warm="true"]` с `border-left: 3px solid rust`.
- Там где пункт становится активным (метод `set_current` или аналог) — вместо `setChecked(True)` вызывать `widget.setProperty("active-warm", "true")` + `style().unpolish/polish(widget)`. Неактивные — `setProperty("active-warm", "false")`.

Если nav-items — кастомные QFrame: добавить `border-left` через stylesheet при активации.

Точный шаблон (вставить в метод активации пункта):

```python
def set_current(self, key: str) -> None:
    for nav_key, button in self._nav_buttons.items():
        is_active = nav_key == key
        button.setProperty("active-warm", "true" if is_active else "false")
        button.style().unpolish(button)
        button.style().polish(button)
```

- [ ] **Step 10.3: Brass-dot справа у активного пункта**

Добавить в макет каждого nav-item справа `QLabel("•")` с `role="brass-dot"`, изначально скрытый. При активации — показывать.

В QSS (добавить в Task 6 Step 6.1 или сюда в отдельный Edit stylesheet.py):

```python
    QLabel[role="brass-dot"] {{
        color: {colors["brass"]};
        font-size: 16px;
    }}
```

В sidebar.py при создании пункта:

```python
dot = QLabel("•")
dot.setProperty("role", "brass-dot")
dot.setVisible(False)
# добавить в layout пункта справа
row_layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
```

В `set_current`:
```python
dot = self._nav_dots[nav_key]  # сохранить словарь
dot.setVisible(is_active)
```

- [ ] **Step 10.4: Прогнать тесты**

Run: `python -m pytest -q`
Expected: зелёное. Если тест `test_ui_handlers.py` проверяет `button.isChecked()` для active-state, обновить на `button.property("active-warm") == "true"`.

- [ ] **Step 10.5: Commit**

```bash
git add ui/components/sidebar.py ui/theme/stylesheet.py tests/
git commit -m "feat(ui): sidebar rust-accent + brass-dot active indicator

Active nav item: rust 3px border-left + brass • dot справа.
Serif caption для активного (через QSS role). Неактивные — ui-sans.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 11: TopBar — parchment + serif title + ghost buttons

**Цель:** фон topbar — `parchment`, заголовок страницы — serif 22px, subtitle — serif italic, кнопки — ghost variant.

**Files:**
- Modify: `ui/components/topbar.py`

- [ ] **Step 11.1: Прочитать текущий `ui/components/topbar.py`**

Зафиксировать структуру: как сейчас выводится title и subtitle, какие кнопки справа (settings, admin).

- [ ] **Step 11.2: Заменить QSS-селекторы у label'ов**

Найти в topbar.py создание заголовка и подзаголовка. Применить roles:

```python
self.page_title = QLabel()
self.page_title.setProperty("role", "page-title-serif")  # новый role
self.page_subtitle = QLabel()
self.page_subtitle.setProperty("role", "subtitle-italic")  # из Task 6
```

Добавить в stylesheet.py новое правило (где остальные label roles):

```python
    QLabel[role="page-title-serif"] {{
        font-family: "{family}";
        font-size: {typography["page_title"]}px;
        font-weight: 600;
        color: {colors["ink"]};
    }}
```

- [ ] **Step 11.3: Перевести кнопки настроек/админки на variant="ghost"**

Найти в topbar.py кнопки типа `settings_button = QPushButton(...)`. Установить `.setProperty("variant", "ghost")` и убрать любые inline setStyleSheet.

- [ ] **Step 11.4: Добавить OrnamentalDivider (опционально, если есть подходящее место)**

Если в layout topbar'а есть разделитель между названием и правыми кнопками — заменить его на `OrnamentalDivider`:

```python
from ui.components.common import OrnamentalDivider
divider = OrnamentalDivider()
layout.addWidget(divider, 0, Qt.AlignmentFlag.AlignVCenter)
```

- [ ] **Step 11.5: Обновить фон topbar**

Если у topbar установлен `role="titlebar"` — QSS правило уже работает и подтянет `card_bg` (== parchment в новой палитре). Ничего делать не надо. Если фон задаётся inline — убрать, оставить на QSS.

- [ ] **Step 11.6: Прогнать тесты + Commit**

Run: `python -m pytest -q` → зелёное.

```bash
git add ui/components/topbar.py ui/theme/stylesheet.py
git commit -m "feat(ui): topbar serif title + italic subtitle + ghost buttons

Page title — serif 22px, subtitle — serif italic 13px.
Settings/admin buttons — ghost variant (hover rust_soft).
Фон topbar наследуется из role='titlebar' (parchment).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Splash — paper bg + serif display + rust progress

**Цель:** splash-окно в новой редакции. Фон paper, welcome-текст serif display 34px, rust-прогресс-бар на sand-треке.

**Files:**
- Modify: `ui/components/splash.py`

- [ ] **Step 12.1: Прочитать `ui/components/splash.py`**

Зафиксировать: как сейчас строится layout, какой виджет используется для прогресса (QProgressBar или кастомный).

- [ ] **Step 12.2: Обновить фон и заголовки**

Найти установку фона splash — убедиться, что это `current_colors()["paper"]` (или `app_bg`, оно теперь тот же цвет). Welcome-заголовку присвоить `role="hero"` (оно уже есть в QSS — подтянет serif).

- [ ] **Step 12.3: Обновить прогресс**

Если используется `QProgressBar`, добавить QSS-правило в stylesheet.py:

```python
    QProgressBar[role="warm-progress"] {{
        background: {colors["sand"]};
        border: none;
        border-radius: 2px;
        max-height: 4px;
    }}
    QProgressBar[role="warm-progress"]::chunk {{
        background: {colors["rust"]};
        border-radius: 2px;
    }}
```

В splash.py у прогресс-бара: `progress.setProperty("role", "warm-progress")` + `progress.setTextVisible(False)`.

Если прогресс — кастомный (paintEvent) — заменить цвета в paintEvent на `rust` и `sand` из current_colors().

- [ ] **Step 12.4: Убедиться что splash не использует QGraphicsEffect**

grep в `ui/components/splash.py`: `setGraphicsEffect`. Если найдено — удалить. Единственный допустимый путь к opacity — `widget.setWindowOpacity(...)` на само окно, не effect на child.

- [ ] **Step 12.5: Прогнать тесты + Commit**

```bash
git add ui/components/splash.py ui/theme/stylesheet.py
git commit -m "feat(ui): splash in warm-minimal paper + serif display + rust progress

Фон — paper. Заголовок — role='hero' (serif 34px).
Прогресс — role='warm-progress' (rust chunk на sand track).
Никаких QGraphicsEffect (регрессия painter warnings недопустима).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 13: LibraryView — hero + ornamental + atelier карточки в 2 колонки

**Цель:** переверстать `ui/views/library_view.py` под editorial-редакцию: hero-блок сверху, ornamental divider, карточки документов в 2 колонки (было 3-4), role="atelier".

**Files:**
- Modify: `ui/views/library_view.py`
- Возможно: `ui/components/document_list.py`, `ui/components/document_detail.py` (если карточки документов там)

- [ ] **Step 13.1: Прочитать файл**

Run: `Read ui/views/library_view.py`. Зафиксировать: сколько колонок в grid, какие role у карточек, где заголовок вьюхи.

- [ ] **Step 13.2: Hero-блок**

Заменить текущий заголовок на блок:

```python
hero = QVBoxLayout()
hero.setSpacing(12)
hero.setContentsMargins(0, 0, 0, 0)

title = QLabel("Библиотека")
title.setProperty("role", "hero")
hero.addWidget(title)

subtitle = QLabel("Материалы к подготовке — отсортированные, с прогрессом.")
subtitle.setProperty("role", "subtitle-italic")
hero.addWidget(subtitle)

from ui.components.common import OrnamentalDivider
divider = OrnamentalDivider()
hero.addWidget(divider)

# добавить hero в главный layout
main_layout.addLayout(hero)
```

- [ ] **Step 13.3: Карточки документов — atelier + grid 2 колонки**

Найти grid-layout для документов. Изменить число колонок: если использует `QGridLayout` с `addWidget(card, row, col)` и col-count=3-4 — заменить на 2.

Карточки — если сейчас role='card' или 'document-item' — заменить на role='atelier'. Если документ-карточка — кастомный класс, установить ему `role="atelier"` в `super().__init__()` (наследуется от CardFrame).

- [ ] **Step 13.4: Прогнать тесты + Commit**

Run: `python -m pytest tests/test_ui_handlers.py -q` — UI-смоук должен пройти.

```bash
git add ui/views/library_view.py ui/components/document_list.py
git commit -m "feat(library): hero + ornamental + atelier cards in 2-column grid

Заголовок role='hero' (serif 34), italic subtitle, OrnamentalDivider.
Карточки документов — role='atelier' (12px radius, md-shadow).
Grid сжат с 3-4 до 2 колонок для editorial-плотности.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 14: TicketsView — folio-карточки билетов + segmented filters

**Цель:** карточки билетов = **folio** (латунная рамка + закладка). Фильтры сверху — segmented на `sand` фоне.

**Files:**
- Modify: `ui/views/tickets_view.py`

- [ ] **Step 14.1: Прочитать файл**

Зафиксировать: как сейчас выглядит карточка билета (QFrame? кастомный класс?), где фильтры.

- [ ] **Step 14.2: Карточка билета — role="folio"**

Найти инстанцирование карточки билета в layout'е. Заменить `CardFrame(role="card", shadow_color=...)` на:

```python
CardFrame(role="folio", accent_strip="rust")
```

- [ ] **Step 14.3: Внутренний layout карточки**

Ключевая структура (образец):

```python
ticket_card = CardFrame(role="folio", accent_strip="rust")
ticket_layout = QVBoxLayout(ticket_card)
# Padding должен быть больше, чтобы внутренняя parchment-бумага
# не упиралась в латунную рамку
ticket_layout.setContentsMargins(30, 36, 30, 26)
ticket_layout.setSpacing(12)

eyebrow = QLabel(f"Билет №{ticket.number}")
eyebrow.setProperty("role", "eyebrow")
ticket_layout.addWidget(eyebrow)

title = QLabel(ticket.title)
title.setProperty("role", "card-title")
ticket_layout.addWidget(title)

# ... body + metrics
```

- [ ] **Step 14.4: Фильтры — segmented control**

Если фильтры сейчас — radio buttons или QPushButton[variant="tab"] — оставить вариант='tab' (он уже есть в QSS). Но добавить контейнер:

```python
filter_row = QFrame()
filter_row.setProperty("role", "paper-card")
filter_layout = QHBoxLayout(filter_row)
filter_layout.setContentsMargins(4, 4, 4, 4)
# внутрь filter_row добавить существующие tab-buttons
```

- [ ] **Step 14.5: Grid — 2 колонки**

Если сейчас 3-4 колонки — снизить до 2 в методе, который строит grid.

- [ ] **Step 14.6: Прогнать тесты + Commit**

```bash
git add ui/views/tickets_view.py
git commit -m "feat(tickets): folio ticket cards + segmented filters + 2-column grid

Каждая карточка билета — role='folio' с rust-закладкой.
eyebrow 'Билет №XX' (sans) + serif title. Padding увеличен
под латунную рамку. Фильтры — tab-вариант в paper-рамке.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 15: TrainingView — folio вопрос + atelier варианты + ornamental в evaluation

**Цель:** центральный блок вопроса — folio (max-width 68ch для читабельности). Варианты ответа — atelier с rust-hover. Evaluation-panel разделена OrnamentalDivider между секциями.

**Files:**
- Modify: `ui/views/training_view.py`

- [ ] **Step 15.1: Прочитать файл**

Зафиксировать: где строится блок вопроса, блок вариантов, блок evaluation.

- [ ] **Step 15.2: Вопрос-блок — folio**

```python
question_card = CardFrame(role="folio", accent_strip="rust")
question_card.setMaximumWidth(720)  # ~68ch at 13px
question_layout = QVBoxLayout(question_card)
question_layout.setContentsMargins(36, 40, 36, 32)
question_layout.setSpacing(14)

eyebrow = QLabel("Вопрос")
eyebrow.setProperty("role", "eyebrow")
question_layout.addWidget(eyebrow)

q_title = QLabel(question_text)
q_title.setProperty("role", "card-title")
q_title.setWordWrap(True)
question_layout.addWidget(q_title)
```

- [ ] **Step 15.3: Варианты ответа — atelier**

Для каждого варианта:

```python
choice = CardFrame(role="atelier")
choice.setCursor(Qt.CursorShape.PointingHandCursor)
# добавить hover-эффект через dynamic property и QSS:
# QFrame[role="atelier-card"]:hover уже реагирует, но Qt
# не даёт hover на произвольных QFrame без WA_Hover.
choice.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
```

В stylesheet.py добавить:

```python
    QFrame[role="atelier-card"]:hover {{
        border-color: {colors["rust"]};
        background: {colors["rust_soft"]};
    }}
```

Для правильного/неправильного индикатора использовать классы: `correct` / `incorrect`:

```python
if is_correct:
    choice.setProperty("answer-state", "correct")
elif is_incorrect:
    choice.setProperty("answer-state", "incorrect")
choice.style().unpolish(choice)
choice.style().polish(choice)
```

QSS:

```python
    QFrame[role="atelier-card"][answer-state="correct"] {{
        border: 2px solid {colors["moss"]};
        background: {colors["moss_soft"]};
    }}
    QFrame[role="atelier-card"][answer-state="incorrect"] {{
        border: 2px solid {colors["claret"]};
        background: {colors["claret_soft"]};
    }}
```

- [ ] **Step 15.4: Evaluation-panel с OrnamentalDivider**

В блоке, где рендерится evaluation (правильный ответ + объяснение + источник), между секциями добавлять:

```python
from ui.components.common import OrnamentalDivider
eval_layout.addWidget(OrnamentalDivider())
```

- [ ] **Step 15.5: Кнопка «Следующий» — primary moss**

Найти кнопку следующего вопроса. Убедиться `variant="primary"`. QSS из Task 6 раскрасит её в moss + parchment text.

- [ ] **Step 15.6: Прогнать тесты + Commit**

Run: `python -m pytest tests/test_training_view_modes.py tests/test_scoring_and_review.py -q`. Если UI-смоук включает training — тоже.

```bash
git add ui/views/training_view.py ui/theme/stylesheet.py
git commit -m "feat(training): folio question + atelier choices + ornamental evaluation

Question card — folio (max 720px). Choices — atelier с rust hover,
answer-state=correct → moss рамка, incorrect → claret рамка.
Evaluation-блоки разделены OrnamentalDivider.
CTA 'Следующий' — primary variant (moss fill).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 16: Icons — обновить tone_mapping

**Цель:** перекрасить SVG-иконки под новую палитру. SVG не меняем, только цвета через существующий `tone_mapping` в `ui/icons.py`.

**Files:**
- Modify: `ui/icons.py`

- [ ] **Step 16.1: Прочитать `ui/icons.py`**

Найти функцию / словарь, который сопоставляет tone-key с цветом (часто называется `TONE_COLORS` или используется внутри `SvgIconLabel.set_icon`).

- [ ] **Step 16.2: Обновить tone_mapping**

Заменить значения цветов на новые (или если оно строится из `current_colors()` — убедиться, что ключи читаются правильные):

```python
def _tone_color(tone: str, colors: dict) -> str:
    mapping = {
        "primary": colors["rust"],
        "secondary": colors["moss"],
        "accent": colors["brass"],
        "muted": colors["ink_muted"],
        "faint": colors["ink_faint"],
        "active": colors["rust"],
        "decorative": colors["brass"],
        "danger": colors["claret"],
        "warning": colors["brick"],
        "success": colors["sage"],
    }
    return mapping.get(tone, colors["ink_muted"])
```

Точное имя функции и место — зависит от `ui/icons.py`, которое нужно прочитать.

- [ ] **Step 16.3: Прогнать тесты + Commit**

```bash
git add ui/icons.py
git commit -m "feat(icons): warm-minimal tone mapping for SVG icons

tone='primary' → rust, secondary → moss, accent/decorative → brass,
muted → ink_muted, danger → claret, warning → brick, success → sage.
SVG файлы не меняются — только цветовая подстановка в runtime.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 17: Регресс-тест на QPainter warnings

**Цель:** защитить работу, сделанную в коммитах a2a5a6e + b5b6edb + сегодняшний nested-effects fix, от возврата: тест падает, если при переключении вкладок Qt выдаёт warning о painter conflict.

**Files:**
- Create: `tests/test_painter_warnings.py`

- [ ] **Step 17.1: Написать тест**

Создать `tests/test_painter_warnings.py`:

```python
"""Regression-тест: переключение вкладок не должно плодить QPainter
warnings о nested QGraphicsEffect.

Если кто-то вернёт QGraphicsOpacityEffect на stack (или добавит любой
другой GraphicsEffect в поддерево, где уже есть DropShadow) — Qt
начнёт писать "A paint device can only be painted by one painter at a
time" на каждый кадр перехода. Этот тест ловит такую регрессию.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QElapsedTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from application.facade import AppFacade
from application.settings import DEFAULT_OLLAMA_SETTINGS
from application.settings_store import SettingsStore
from infrastructure.db import connect_initialized, get_database_path
from ui.components.sidebar import NAV_ITEMS
from ui.main_window import MainWindow
from ui.theme import set_app_theme

pytestmark = pytest.mark.ui

_MARKERS = (
    "A paint device can only be painted by one painter",
    "QWidgetEffectSourcePrivate::pixmap: Painter not active",
    "QPainter::worldTransform: Painter not active",
    "QPainter::setWorldTransform: Painter not active",
    "QPainter::translate: Painter not active",
)


def test_no_painter_warnings_on_tab_switching(tmp_path: Path) -> None:
    captured: list[str] = []

    def handler(mode, context, message) -> None:
        captured.append(str(message))

    qInstallMessageHandler(handler)

    app = QApplication.instance() or QApplication([])
    set_app_theme(app, "light")

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    db_path = get_database_path(workspace)
    conn = connect_initialized(db_path)
    store = SettingsStore(workspace / "app_data" / "settings.json")
    effective = replace(
        DEFAULT_OLLAMA_SETTINGS,
        auto_check_ollama_on_start=False,
        auto_check_updates_on_start=False,
    )
    store.save(effective)
    facade = AppFacade(workspace, conn, store)
    window = MainWindow(app, facade, "light", suppress_startup_background_tasks=True)

    try:
        window.show()
        app.processEvents()

        nav_keys = [item[0] for item in NAV_ITEMS]
        # 2 круга по всем вкладкам
        for _ in range(2):
            for key in nav_keys:
                window.switch_view(key)
                t = QElapsedTimer()
                t.start()
                while t.elapsed() < 120:
                    app.processEvents()

        for marker in _MARKERS:
            count = sum(1 for m in captured if marker in m)
            assert count == 0, (
                f"QPainter warning marker {marker!r} captured {count} times. "
                f"Likely regression — check for nested QGraphicsEffect in widget tree. "
                f"Sample messages: {[m for m in captured if marker in m][:3]}"
            )
    finally:
        window.close()
        app.processEvents()
        conn.close()
```

- [ ] **Step 17.2: Запустить тест**

Run: `python -m pytest tests/test_painter_warnings.py -v`
Expected: PASS (после всех предыдущих задач никаких nested effects нет).

- [ ] **Step 17.3: Commit**

```bash
git add tests/test_painter_warnings.py
git commit -m "test(ui): regression test for QPainter nested-effect warning storm

Fails if any future change reintroduces nested QGraphicsEffect in the
widget tree (e.g. opacity effect on QStackedWidget + drop-shadow on
inner CardFrames) by capturing Qt's message stream during 2 full
rounds of tab switching and asserting zero painter-conflict markers.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 18: Manual visual gate + скриншоты

**Цель:** глазной контроль и фиксация результата в скриншотах для будущих референсов.

**Files:**
- Create: `docs/superpowers/screenshots/2026-04-17-warm-minimal/` (новый каталог)
- Screenshots (6): library-light.png, library-dark.png, tickets-light.png, tickets-dark.png, training-light.png, training-dark.png

- [ ] **Step 18.1: Запустить приложение в light-режиме**

```bash
python main.py
```

Открыть последовательно: Library → Tickets → Training.

- [ ] **Step 18.2: Сделать скриншоты каждой вьюхи**

Скриншоты каждой вьюхи (Ctrl+PrtSc на Windows — активное окно). Положить в `docs/superpowers/screenshots/2026-04-17-warm-minimal/` с именами:

- `library-light.png`
- `tickets-light.png`
- `training-light.png`

- [ ] **Step 18.3: Переключить на dark-режим и повторить**

Settings → сменить тему на dark. Снова три скриншота:

- `library-dark.png`
- `tickets-dark.png`
- `training-dark.png`

- [ ] **Step 18.4: Сравнить с мокапами**

Открыть `.superpowers/brainstorm/204-1776426410/content/` HTML'ки и сравнить визуально:

- `aesthetic-direction.html` — общее впечатление (Warm Minimal)
- `palette.html` — палитра B (Rust + Moss)
- `materiality.html` — folio везде, где карточка билета
- `dark-palette.html` — cognac leather

Если есть серьёзные расхождения — записать список в комментарий к коммиту или в PR.

- [ ] **Step 18.5: Commit скриншоты**

```bash
git add docs/superpowers/screenshots/2026-04-17-warm-minimal/
git commit -m "docs: visual gate screenshots for warm-minimal refresh

Screenshots of library/tickets/training in light and dark palettes,
after warm-minimal visual refresh. Reference for future regressions
and comparisons against spec mockups in .superpowers/brainstorm/.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Self-Review checklist

Перед тем как считать план готовым:

**1. Spec coverage:**

| Spec раздел | Покрытие в плане |
|---|---|
| §3 Design tokens (LIGHT/DARK) | Task 2 |
| §3.3 Typography (serif + ui_sans, scale) | Task 3 |
| §4 Materiality (L1/L2/L3 + elevation) | Task 4 (SPACING/ELEVATION), Task 5 (apply_shadow + helpers), Task 7 (CardFrame folio) |
| §5.1 CardFrame roles + accent_strip | Task 7 |
| §5.2 Button variants (primary/secondary/ghost/danger) | Task 6 |
| §5.3 LogoMark palette | Task 8 |
| §5.4 IconBadge, StatusDot, ScoreBadge, MetricTile, DonutChart, OrnamentalDivider | Task 7 (Ornamental), Task 9 (остальные) |
| §6.1 Sidebar redesign | Task 10 |
| §6.2 TopBar | Task 11 |
| §6.3 Splash | Task 12 |
| §7.1 LibraryView | Task 13 |
| §7.2 TicketsView | Task 14 |
| §7.3 TrainingView | Task 15 |
| §8 Icons tone_mapping | Task 16 |
| §9 Theme package structure | Task 1 |
| §10.2 Test: test_theme_palette | Task 2 |
| §10.2 Test: test_materiality | Task 5 |
| §10.2 Test: test_painter_warnings | Task 17 |
| §10.3 Visual gate | Task 18 |

Все требования spec покрыты.

**2. Placeholder scan:** в плане явно не использованы фразы «TBD», «TODO», «implement later», «similar to Task N». Инструктивные задачи (10-16) имеют точные файлы, селекторы и код-блоки, но просят прочитать файл первым шагом — это не placeholder, а явное признание того, что точные номера строк зависят от момента выполнения.

**3. Type consistency:**
- `apply_shadow(widget, level, palette)` — сигнатура одинакова в Task 5 (определение), Task 7 (CardFrame call-site), далее не вызывается напрямую, идёт через CardFrame.
- `paint_folio(painter, rect, palette, *, outer_radius=10, inner_radius=6, outer_pad=8, accent='rust')` — согласовано между Task 5 (определение) и Task 7 (call-site).
- `CardFrame(role, accent_strip, shadow_level)` — одинаковая сигнатура в Task 7 (определение) и Tasks 9/13/14/15 (call-sites).
- `resolve_ui_font()` — определён в Task 3, используется в Task 9.
- Semantic palette keys (`paper`, `rust`, `moss`, `brass` и т.д.) — добавлены в Task 2, используются во всех следующих задачах.

Нет несогласованностей.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-warm-minimal-visual-refresh.md`. Two execution options:

**1. Subagent-Driven (recommended)** — я диспатчу свежего subagent'а на каждую задачу, делаю review между задачами, быстрая итерация.

**2. Inline Execution** — выполняем задачи в текущей сессии через executing-plans, батч с чекпоинтами.

Какой подход?
