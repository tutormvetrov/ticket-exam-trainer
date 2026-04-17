# Visual Defects Log

Статусы: `OPEN`, `FIXED`

На 2026-04-17 блокирующих визуальных дефектов по целевому scope `shell + library + tickets + training` не осталось. Ниже оставлен короткий журнал реально найденных и перепроверенных проблем.

| Экран | Зона | Что именно было не так | Почему мешало | Severity | Техническая причина | Как перепроверено | Статус |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Sidebar | Активная иконка раздела | Активный icon tone выпадал белым пятном из тёплой палитры | Нарушалась цельность навигации | medium | `on_tone` для `variant="nav"` перекрывал warm accent | Human visual check, `docs/superpowers/screenshots/2026-04-17-warm-minimal/tickets-dark.png` | FIXED |
| Sidebar | Бренд-блок | Верхняя коробка с подписью `Локальный тренажёр...` выглядела тяжело и избыточно | Шапка навигации выглядела сырой | medium | Переусложнённый `brand` container | Human visual check после упрощения `ui/components/sidebar.py` | FIXED |
| LogoMark | Контур круга и буква | На маленьком размере логотип выглядел пикселизированным | Подрывал ощущение качества интерфейса | medium | SVG кэшировался в низком raster без hi-dpi запаса | `ui/components/common.py`, визуальный preview 2026-04-17 | FIXED |
| TopBar | Заголовок раздела | После `switch_view("training")` текст оставался от `Библиотеки` | Пользователь терял контекст текущего экрана | heavy | `text_admin` возвращал старый base text dynamic-label'ам | `audit/ui_click_audit.md`, targeted offscreen smoke | FIXED |

Residual risk:

- для вторичных экранов warm-minimal пока обеспечивается общей theme inheritance, а не персональным redesign-проходом;
- отдельный full visual pass по всем вторичным экранам остаётся частью следующего цикла.
