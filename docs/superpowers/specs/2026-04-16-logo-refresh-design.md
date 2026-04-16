# Logo refresh — академический медальон

**Дата:** 2026-04-16
**Статус:** Утверждён, ожидает implementation plan
**Область:** UI / бренд

## Мотивация

Текущий `LogoMark` ([ui/components/common.py:64](../../../ui/components/common.py)) — нарисован через `QPainter`: три зелёных «листа» с дуговыми вырезами. Пользователь обозначил задачу как «сделать лого более красивым, богатым, изысканным, рафинированным». Текущая версия читается тех-овой иконкой, не брендом университетского продукта.

Лого видно в трёх местах:
- [ui/components/splash.py:29](../../../ui/components/splash.py) — splash 88px
- [ui/components/sidebar.py:57](../../../ui/components/sidebar.py) — sidebar 52px (виден в каждой сессии)
- [ui/components/title_bar.py:21](../../../ui/components/title_bar.py) — title bar 24px

## Решение

Академический медальон: изумрудный диск с золочёной серифной «Т», обрамлённый тонким золотым кольцом и пунктирным внутренним кольцом. Метафора — университетская эмблема / печать на дипломе.

### Визуальные параметры

**Мотив:** круглый медальон, серифная «Т» по центру, радиальная симметрия.

**Палитры:**

| Тема   | Изумруд (градиент) | Золото (градиент)  |
|--------|--------------------|--------------------|
| Light  | `#134734 → #228F64` | `#B9893D → #E6C478` |
| Dark   | `#165A42 → #2AA076` | `#D8A74E → #F4DB94` |

Градиенты диагональные (слева-сверху → справа-снизу).

**Элементы полной версии:**
1. Изумрудный диск (радиус 44 из viewBox 96×96, центр 48,48)
2. Внешнее золотое кольцо, stroke-width 1.6
3. Внутреннее пунктирное кольцо на радиусе 38, stroke-width 0.6, dasharray `1 2`
4. Золочёная серифная «Т»: перекладина `x∈[26;70] y∈[30;40]`, ножка `x∈[43;53] y∈[40;70]`
5. Мелкие засечки на концах перекладины `(30;30-36)`, `(66;30-36)`; нижний терминал под ножкой `(43-53; 68)`

**Адаптивная детализация:**

| Размер виджета     | Вариант SVG       | Что видно                        |
|--------------------|-------------------|----------------------------------|
| ≥ 40 px            | `mark-full`       | Все 5 элементов                  |
| < 40 px (24px bar) | `mark-minimal`    | Только диск (1) + серифная «Т» (4) |

Порог 40 выбран так, чтобы splash (88) и sidebar (52) получали полную версию, а title bar (24) — минимальную.

## Архитектура

### Формат: SVG, не QPainter

Причины:
- Полную детализацию (пунктир, градиенты, засечки) в `QPainter` дорого писать и ещё дороже редактировать
- `QSvgRenderer` входит в PySide6 по умолчанию (`PySide6.QtSvg`) — новых зависимостей не нужно
- Дизайнер может править SVG без касания Python

### Стратегия темизации: один шаблон + подстановка цветов

Вместо четырёх файлов (`mark-full-light.svg`, `mark-full-dark.svg`, и так же для minimal) — два SVG-шаблона с плейсхолдерами:

```
assets/logo/mark-full.svg.template
assets/logo/mark-minimal.svg.template
```

Плейсхолдеры в шаблоне:
- `{{emerald_stop_0}}`, `{{emerald_stop_1}}`
- `{{gold_stop_0}}`, `{{gold_stop_1}}`

Палитры живут в Python (модуль темы), runtime подставляет значения через `str.replace` перед передачей bytes в `QSvgRenderer`. Source of truth один — SVG.

### Компонент `LogoMark`

Интерфейс сохраняется: `LogoMark(size=52)` — те же точки использования не меняются.

Внутренности:
- Загружает шаблон по размеру (full или minimal)
- При каждом `paintEvent` — выбирает палитру через `ui.theme.current_colors()` / `is_dark_palette()`, подставляет цвета в кэшированные bytes, рендерит через `QSvgRenderer`
- При смене темы `MainWindow` уже вызывает `refresh_theme()` на дочерних виджетах — добавляется метод `refresh_theme()` в `LogoMark`, который инвалидирует кэш и зовёт `update()`

### Расположение ассетов и PyInstaller

SVG-шаблоны лежат в `assets/logo/` (новая директория). Для frozen-сборки (`pyinstaller`) — добавить `assets/logo/*.svg.template` в `datas` сборочного spec. Путь резолвится через новый helper `app.paths.logo_assets_dir()`, который знает про `sys._MEIPASS`.

## Скоуп изменений

### Изменяется
- [ui/components/common.py](../../../ui/components/common.py) — класс `LogoMark` полностью переписывается: убирается `paintEvent` с `QPainter`-геометрией, добавляется SVG-загрузка и темизация через подстановку.

### Добавляется
- `assets/logo/mark-full.svg.template` — полный медальон
- `assets/logo/mark-minimal.svg.template` — упрощённый
- `app/paths.py` — функция `logo_assets_dir() -> Path`, учитывающая `sys._MEIPASS`
- `ui/theme.py` — функция `logo_palette(is_dark: bool) -> dict[str, str]`, возвращающая словарь с ключами `emerald_stop_0`, `emerald_stop_1`, `gold_stop_0`, `gold_stop_1`. Её же использует `LogoMark` для подстановки в SVG, имена ключей совпадают с плейсхолдерами шаблона.
- Тесты: `tests/test_logo_mark.py`
- Build spec — добавить SVG-шаблоны в `datas` PyInstaller spec-файла

### Не изменяется
- [ui/components/splash.py](../../../ui/components/splash.py), [ui/components/sidebar.py](../../../ui/components/sidebar.py), [ui/components/title_bar.py](../../../ui/components/title_bar.py) — они просто создают `LogoMark(<size>)`, API остаётся прежним

## Тестирование

### Unit (pytest + PySide6 offscreen)

| Тест | Проверяет |
|------|-----------|
| `test_render_full_variant_for_large_size` | `LogoMark(52).grab()` — не пустой pixmap размера 52×52 |
| `test_render_minimal_variant_for_small_size` | `LogoMark(24).grab()` — не пустой pixmap 24×24, и загружен minimal template (проверяется по свойству `_variant` виджета) |
| `test_variant_threshold_at_40` | `LogoMark(39)` → minimal, `LogoMark(40)` → full |
| `test_theme_switch_triggers_refresh` | После смены темы и вызова `refresh_theme()` — pixmap меняется (сравнение хэша до/после) |
| `test_svg_template_cleanly_substitutes_colors` | Bytes после подстановки не содержат `{{` и содержат все четыре HEX-значения текущей темы |

### Visual smoke (существующие)
- `scripts/release_smoke.ps1` грабит splash и sidebar — новый логотип не должен ронять пайплайн. Новых чек-сетов не заводим.

## Out of scope

- `.ico` для `Tezis.exe` (сейчас дефолтная Python-иконка) — отдельная задача: требует либо `cairosvg` как новую зависимость, либо ручную конвертацию. Не раздуваем этот PR.
- Вордмарк «Тезис» рядом с логотипом — остаётся системным шрифтом через обычный `QLabel`
- Иконки в остальных местах (файлы, бейджи и т.д.)
- Любая анимация логотипа (появления, hover)

## Миграционные риски

**Низкие.** API `LogoMark(size=N)` сохраняется, все call-sites не трогаются. Если SVG-рендер падает (битый шаблон, проблемы со шрифтом) — в `paintEvent` есть `try/except` fallback: рисуется монохромный диск + «Т» через `QPainter` (чтобы пустоту в брендовом месте гарантированно не увидеть). Fallback не проектный артефакт, просто страховка.

## Критерии готовности

- [ ] Все пять unit-тестов зелёные
- [ ] `pytest -q` не красный в целом
- [ ] `python main.py` запускается, splash / sidebar / title bar показывают новый лого
- [ ] Переключение темы (`set_app_theme(app, "dark", ...)`) перерисовывает лого в палитре тёмной темы
- [ ] PyInstaller-сборка (`scripts/build_exe.ps1`) включает SVG-шаблоны и запускается
