# Logo refresh — академический медальон — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить текущий QPainter-нарисованный `LogoMark` на академический медальон (изумруд + серифная золочёная «Т» + золотое кольцо + пунктир), загружаемый из двух SVG-шаблонов с runtime-подстановкой палитры под текущую тему.

**Architecture:** Два SVG-шаблона (`mark-full.svg.template`, `mark-minimal.svg.template`) живут в `assets/logo/`. `LogoMark` выбирает шаблон по размеру виджета (порог 40px), подставляет 4 HEX-значения текущей темы через `str.replace`, передаёт bytes в `QSvgRenderer` (уже используется в `ui/icons.py`). При смене темы пересборка через `refresh_theme()`. PyInstaller включает шаблоны в `datas`.

**Tech Stack:** Python 3.12, PySide6 (QSvgRenderer, QPainter, QPixmap), pytest, PyInstaller.

**Спек:** [`docs/superpowers/specs/2026-04-16-logo-refresh-design.md`](../specs/2026-04-16-logo-refresh-design.md)

---

## Карта файлов

**Создаётся:**
- `assets/logo/mark-full.svg.template` — полный медальон с плейсхолдерами цветов
- `assets/logo/mark-minimal.svg.template` — только диск + «Т», для размеров <40px
- `tests/test_logo_mark.py` — unit-тесты

**Изменяется:**
- `ui/components/common.py:64-97` — класс `LogoMark` полностью переписывается
- `ui/theme.py` — добавляется функция `logo_palette(is_dark: bool)`
- `app/paths.py` — добавляется `logo_assets_dir() -> Path`
- `scripts/build_exe.ps1:79-87` — добавляется `--add-data` для SVG-шаблонов

**Не трогается (API сохраняется):**
- `ui/components/splash.py`, `ui/components/sidebar.py`, `ui/components/title_bar.py`

---

## Task 1: SVG-шаблон полного медальона

**Files:**
- Create: `assets/logo/mark-full.svg.template`

- [ ] **Step 1: Создать директорию и файл**

Run:
```bash
mkdir -p "assets/logo"
```

Записать в `assets/logo/mark-full.svg.template`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">
  <defs>
    <linearGradient id="emerald" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{{emerald_stop_0}}"/>
      <stop offset="1" stop-color="{{emerald_stop_1}}"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{{gold_stop_0}}"/>
      <stop offset="1" stop-color="{{gold_stop_1}}"/>
    </linearGradient>
  </defs>
  <circle cx="48" cy="48" r="44" fill="url(#emerald)"/>
  <circle cx="48" cy="48" r="44" fill="none" stroke="url(#gold)" stroke-width="1.6"/>
  <circle cx="48" cy="48" r="38" fill="none" stroke="url(#gold)" stroke-width="0.6" stroke-dasharray="1 2"/>
  <path d="M26 30 L70 30 L70 40 L53 40 L53 70 L43 70 L43 40 L26 40 Z" fill="url(#gold)"/>
  <path d="M30 30 L30 36 M66 30 L66 36 M43 68 L53 68" stroke="url(#gold)" stroke-width="2.2" fill="none"/>
</svg>
```

- [ ] **Step 2: Commit**

```bash
git add "assets/logo/mark-full.svg.template"
git commit -m "feat(logo): add full medallion SVG template"
```

---

## Task 2: SVG-шаблон минимального медальона

**Files:**
- Create: `assets/logo/mark-minimal.svg.template`

- [ ] **Step 1: Записать файл `assets/logo/mark-minimal.svg.template`**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">
  <defs>
    <linearGradient id="emerald" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{{emerald_stop_0}}"/>
      <stop offset="1" stop-color="{{emerald_stop_1}}"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{{gold_stop_0}}"/>
      <stop offset="1" stop-color="{{gold_stop_1}}"/>
    </linearGradient>
  </defs>
  <circle cx="48" cy="48" r="44" fill="url(#emerald)"/>
  <path d="M26 30 L70 30 L70 40 L53 40 L53 70 L43 70 L43 40 L26 40 Z" fill="url(#gold)"/>
</svg>
```

- [ ] **Step 2: Commit**

```bash
git add "assets/logo/mark-minimal.svg.template"
git commit -m "feat(logo): add minimal medallion SVG template"
```

---

## Task 3: `logo_palette()` helper в `ui/theme.py`

**Files:**
- Modify: `ui/theme.py` (добавить функцию в конец файла)
- Test: `tests/test_logo_mark.py` (создать)

- [ ] **Step 1: Создать файл теста `tests/test_logo_mark.py`**

```python
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def test_logo_palette_light_values() -> None:
    from ui.theme import logo_palette
    palette = logo_palette(is_dark=False)
    assert palette == {
        "emerald_stop_0": "#134734",
        "emerald_stop_1": "#228F64",
        "gold_stop_0": "#B9893D",
        "gold_stop_1": "#E6C478",
    }


def test_logo_palette_dark_values() -> None:
    from ui.theme import logo_palette
    palette = logo_palette(is_dark=True)
    assert palette == {
        "emerald_stop_0": "#165A42",
        "emerald_stop_1": "#2AA076",
        "gold_stop_0": "#D8A74E",
        "gold_stop_1": "#F4DB94",
    }
```

- [ ] **Step 2: Запустить — убедиться, что тест красный**

Run: `python -m pytest tests/test_logo_mark.py -q`
Expected: `ImportError: cannot import name 'logo_palette'` или `AttributeError`.

- [ ] **Step 3: Добавить функцию в `ui/theme.py`**

В конец файла (после `mastery_band_color`):

```python
def logo_palette(is_dark: bool) -> dict[str, str]:
    """Палитра бренд-медальона для подстановки в SVG-шаблон.

    Ключи словаря совпадают с плейсхолдерами `{{name}}` в шаблонах
    `assets/logo/mark-*.svg.template`. Значения зафиксированы отдельно
    от LIGHT/DARK, потому что изумруд и золото — брендовые константы,
    а не семантические цвета UI (success/warning/danger).
    """
    if is_dark:
        return {
            "emerald_stop_0": "#165A42",
            "emerald_stop_1": "#2AA076",
            "gold_stop_0": "#D8A74E",
            "gold_stop_1": "#F4DB94",
        }
    return {
        "emerald_stop_0": "#134734",
        "emerald_stop_1": "#228F64",
        "gold_stop_0": "#B9893D",
        "gold_stop_1": "#E6C478",
    }
```

- [ ] **Step 4: Запустить — убедиться, что тесты зелёные**

Run: `python -m pytest tests/test_logo_mark.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add ui/theme.py tests/test_logo_mark.py
git commit -m "feat(logo): add logo_palette helper for SVG substitution"
```

---

## Task 4: `logo_assets_dir()` helper в `app/paths.py`

**Files:**
- Modify: `app/paths.py` (добавить функцию)
- Test: `tests/test_logo_mark.py` (расширить)

- [ ] **Step 1: Добавить тест в `tests/test_logo_mark.py`**

Дописать в конец файла:

```python
def test_logo_assets_dir_points_at_repo_assets_when_not_frozen() -> None:
    from app.paths import logo_assets_dir
    path = logo_assets_dir()
    assert path.name == "logo"
    assert path.parent.name == "assets"
    assert (path / "mark-full.svg.template").is_file()
    assert (path / "mark-minimal.svg.template").is_file()
```

- [ ] **Step 2: Запустить — тест красный**

Run: `python -m pytest tests/test_logo_mark.py::test_logo_assets_dir_points_at_repo_assets_when_not_frozen -v`
Expected: `ImportError: cannot import name 'logo_assets_dir'`.

- [ ] **Step 3: Добавить функцию в `app/paths.py`**

В конец файла:

```python
def logo_assets_dir() -> Path:
    """Папка с брендовыми SVG-шаблонами логотипа.

    В dev-режиме — `<repo>/assets/logo`. В PyInstaller-сборке `sys.frozen`
    выставлено, и данные лежат рядом с исполняемым файлом (см. `--add-data`
    в scripts/build_exe.ps1).
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / "logo"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1] / "assets" / "logo"
```

- [ ] **Step 4: Запустить — тест зелёный**

Run: `python -m pytest tests/test_logo_mark.py::test_logo_assets_dir_points_at_repo_assets_when_not_frozen -v`
Expected: `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add app/paths.py tests/test_logo_mark.py
git commit -m "feat(logo): add logo_assets_dir helper for frozen/dev lookup"
```

---

## Task 5: Тест — `LogoMark` выбирает full-шаблон на размерах ≥ 40

**Files:**
- Test: `tests/test_logo_mark.py` (расширить)

- [ ] **Step 1: Добавить фикстуру и тест в `tests/test_logo_mark.py`**

В начало файла после `importorskip`:

```python
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app
```

В конец файла:

```python
def test_logo_mark_full_variant_for_large_sizes(qt_app) -> None:
    from ui.components.common import LogoMark
    widget = LogoMark(size=52)
    assert widget._variant == "full"
    widget_big = LogoMark(size=88)
    assert widget_big._variant == "full"


def test_logo_mark_minimal_variant_for_small_sizes(qt_app) -> None:
    from ui.components.common import LogoMark
    widget = LogoMark(size=24)
    assert widget._variant == "minimal"


def test_logo_mark_threshold_is_40(qt_app) -> None:
    from ui.components.common import LogoMark
    assert LogoMark(size=39)._variant == "minimal"
    assert LogoMark(size=40)._variant == "full"
```

- [ ] **Step 2: Запустить — тесты красные**

Run: `python -m pytest tests/test_logo_mark.py -q`
Expected: Падают на `AttributeError: 'LogoMark' object has no attribute '_variant'` (или raw-тесты проходят, но три новых красные).

- [ ] **Step 3: (пока не реализуем — следующая таска)**

Переходим к Task 6.

---

## Task 6: Переписать `LogoMark` на SVG-рендер

**Files:**
- Modify: `ui/components/common.py:64-97` (полная замена класса `LogoMark`)

- [ ] **Step 1: Открыть `ui/components/common.py`, найти класс `LogoMark` (строки 64-97)**

Старый код (для справки — удаляется целиком):

```python
class LogoMark(QWidget):
    def __init__(self, size: int = 52) -> None:
        super().__init__()
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # ... ~30 строк QPainter-геометрии ...
```

- [ ] **Step 2: Заменить импорты в начале `ui/components/common.py`**

Найти строку с импортами из `PySide6.QtCore` и `PySide6.QtGui` (начиная с `from PySide6.QtCore import`) и убедиться, что в ней есть `QByteArray`. Если нет — добавить:

```python
from PySide6.QtCore import Qt, QRectF, Signal, QSize, QEasingCurve, Property, QPropertyAnimation, QByteArray
```

Добавить новый импорт сразу после существующих PySide6-импортов:

```python
from PySide6.QtSvg import QSvgRenderer
```

Найти импорт `from ui.theme import` и расширить его на `logo_palette`:

```python
from ui.theme import alpha_color, apply_shadow, current_colors, is_dark_palette, logo_palette, mastery_band_color
```

Добавить импорт путей в начало (после PySide6-импортов):

```python
from app.paths import logo_assets_dir
```

- [ ] **Step 3: Заменить класс `LogoMark` целиком на новый**

Найти `class LogoMark(QWidget):` и заменить весь класс (до следующего `class`, т.е. до `class IconBadge(QFrame):`) на:

```python
_LOGO_VARIANT_THRESHOLD_PX = 40


class LogoMark(QWidget):
    """Академический медальон, загружаемый из SVG-шаблона.

    Размер ≥ 40px — полная версия (кольца, пунктир, засечки).
    Размер < 40px — упрощённая (только диск + «Т»).
    При смене темы виджет перерисовывается через refresh_theme().
    """

    def __init__(self, size: int = 52) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self._variant = "full" if size >= _LOGO_VARIANT_THRESHOLD_PX else "minimal"
        self._template_bytes: bytes | None = None
        self._cached_svg: QByteArray | None = None
        self._cached_palette_key: tuple | None = None

    def refresh_theme(self) -> None:
        self._cached_svg = None
        self._cached_palette_key = None
        self.update()

    def _load_template(self) -> bytes:
        if self._template_bytes is None:
            filename = f"mark-{self._variant}.svg.template"
            path = logo_assets_dir() / filename
            self._template_bytes = path.read_bytes()
        return self._template_bytes

    def _build_svg(self) -> QByteArray:
        palette = logo_palette(is_dark_palette())
        palette_key = tuple(sorted(palette.items()))
        if self._cached_svg is not None and self._cached_palette_key == palette_key:
            return self._cached_svg
        template = self._load_template().decode("utf-8")
        for key, value in palette.items():
            template = template.replace(f"{{{{{key}}}}}", value)
        self._cached_svg = QByteArray(template.encode("utf-8"))
        self._cached_palette_key = palette_key
        return self._cached_svg

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            renderer = QSvgRenderer(self._build_svg())
            renderer.render(painter, QRectF(0, 0, self.width(), self.height()))
        except Exception:
            # Страховка: если SVG-шаблон сломан, рисуем монохромный диск + «Т»
            # чтобы пустоты в брендовом месте пользователь не увидел.
            self._paint_fallback(painter)

    def _paint_fallback(self, painter: QPainter) -> None:
        colors = current_colors()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors["primary"]))
        painter.drawEllipse(QRectF(2, 2, self.width() - 4, self.height() - 4))
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont(QApplication.font().family(), max(8, self.width() // 3), 800))
        painter.drawText(QRectF(0, 0, self.width(), self.height()), Qt.AlignmentFlag.AlignCenter, "Т")
```

- [ ] **Step 4: Запустить тесты из Task 5**

Run: `python -m pytest tests/test_logo_mark.py -q`
Expected: все 7 тестов зелёные (2 палитра + 1 assets_dir + 3 variant + 1 theme-switch если уже добавлен, иначе 6/6).

- [ ] **Step 5: Визуальный smoke — запустить приложение**

Run: `python main.py --view library`
Expected: Окно запускается, в sidebar виден новый медальон (изумруд + золотая «Т»), в title bar — уменьшенный вариант. Закрыть окно.

- [ ] **Step 6: Commit**

```bash
git add ui/components/common.py tests/test_logo_mark.py
git commit -m "feat(logo): rewrite LogoMark using SVG templates with adaptive variants"
```

---

## Task 7: Тест — смена темы инвалидирует кэш

**Files:**
- Test: `tests/test_logo_mark.py` (расширить)

- [ ] **Step 1: Добавить тест**

В конец `tests/test_logo_mark.py`:

```python
def test_logo_mark_theme_refresh_rebuilds_svg(qt_app) -> None:
    from ui.components.common import LogoMark
    from ui.theme import set_app_theme

    set_app_theme(qt_app, "light", "inter-style", 14)
    widget = LogoMark(size=52)
    svg_light = bytes(widget._build_svg())
    assert b"#228F64" in svg_light  # изумруд light

    set_app_theme(qt_app, "dark", "inter-style", 14)
    widget.refresh_theme()
    svg_dark = bytes(widget._build_svg())
    assert b"#2AA076" in svg_dark  # изумруд dark
    assert svg_light != svg_dark

    # Восстановить light, чтобы не зааффектить другие тесты.
    set_app_theme(qt_app, "light", "inter-style", 14)
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/test_logo_mark.py::test_logo_mark_theme_refresh_rebuilds_svg -v`
Expected: `PASSED`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_logo_mark.py
git commit -m "test(logo): verify theme switch invalidates svg cache"
```

---

## Task 8: Тест — подстановка не оставляет плейсхолдеров

**Files:**
- Test: `tests/test_logo_mark.py` (расширить)

- [ ] **Step 1: Добавить тест**

В конец `tests/test_logo_mark.py`:

```python
def test_logo_mark_svg_has_no_unresolved_placeholders(qt_app) -> None:
    from ui.components.common import LogoMark
    for size, variant in ((52, "full"), (24, "minimal")):
        widget = LogoMark(size=size)
        assert widget._variant == variant
        svg_bytes = bytes(widget._build_svg())
        assert b"{{" not in svg_bytes, f"Нерезолвленные плейсхолдеры в {variant}"
        assert b"}}" not in svg_bytes
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/test_logo_mark.py -q`
Expected: Все тесты зелёные.

- [ ] **Step 3: Commit**

```bash
git add tests/test_logo_mark.py
git commit -m "test(logo): verify no unresolved placeholders after substitution"
```

---

## Task 9: Подключить SVG-шаблоны в PyInstaller build

**Files:**
- Modify: `scripts/build_exe.ps1:79-87`

- [ ] **Step 1: Найти блок вызова PyInstaller в `scripts/build_exe.ps1` (около строки 79)**

Сейчас он выглядит так:

```powershell
& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $releaseName `
    --distpath $stageDistRoot `
    --workpath $workDir `
    --specpath $specDir `
    (Join-Path $root "main.py")
```

- [ ] **Step 2: Добавить строку `--add-data` перед `(Join-Path $root "main.py")`**

Заменить блок выше на:

```powershell
$logoAssets = Join-Path $root "assets/logo"
& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $releaseName `
    --distpath $stageDistRoot `
    --workpath $workDir `
    --specpath $specDir `
    --add-data "${logoAssets};assets/logo" `
    (Join-Path $root "main.py")
```

Формат `--add-data` на Windows: `<src>;<dest_relative_to_bundle>` (на POSIX разделитель — `:`, но этот скрипт только Windows).

- [ ] **Step 3: Commit**

```bash
git add scripts/build_exe.ps1
git commit -m "build(logo): include logo SVG templates in PyInstaller bundle"
```

---

## Task 10: Полный прогон тестов и приложения

**Files:** (ничего не изменяется, только запускаем)

- [ ] **Step 1: Прогнать весь набор тестов**

Run: `python -m pytest -q`
Expected: Все тесты зелёные (было 156 passed 5 skipped + 7 новых из test_logo_mark = ≈163 passed, 5 skipped). Если что-то красное — фикс без коммита в этой таске, возвращаемся к разборкам.

- [ ] **Step 2: Запустить приложение в светлой теме**

Run: `python main.py --view library --theme light`
Expected: Окно открывается, логотип в sidebar — изумрудный медальон с золотой «Т» и тонким кольцом. Title bar — маленький вариант. Закрыть окно.

- [ ] **Step 3: Запустить в тёмной теме**

Run: `python main.py --view library --theme dark`
Expected: Логотип в sidebar — чуть более светлый изумруд, золото чуть холоднее. Закрыть окно.

- [ ] **Step 4: Запустить smoke-скрипт релиза**

Run: `powershell -ExecutionPolicy Bypass -File scripts\release_smoke.ps1`
Expected: Скрипт отрабатывает без ошибок, собирает скриншоты в `smoke-*.png` или `audit/screens/`. Если `release_smoke.ps1` требует собранный exe — пропустить этот шаг и отметить в итоговом commit message.

- [ ] **Step 5: Финальный commit (если остались несохранённые правки)**

```bash
git status
# Если есть изменения — закоммитить их описательно. Иначе просто пропустить.
```

- [ ] **Step 6: Обновить audit/open_issues.md если нужно**

Проверить `audit/open_issues.md`. Если там есть открытый пункт про логотип — пометить как DONE. Если нет — ничего не трогать.

---

## Definition of Done

- [ ] Все 8 новых тестов в `tests/test_logo_mark.py` зелёные
- [ ] `python -m pytest -q` не красный в целом
- [ ] `python main.py` запускается в обеих темах, логотип виден и корректен
- [ ] SVG-шаблоны попали в `assets/logo/` и учтены в `build_exe.ps1`
- [ ] Fallback-путь (`_paint_fallback`) присутствует в `LogoMark` как страховка, но не тестируется (это safety net, не контракт)
