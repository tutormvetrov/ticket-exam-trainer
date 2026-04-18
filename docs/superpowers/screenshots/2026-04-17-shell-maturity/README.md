# Shell Maturity Visual Gate

Набор референсных скриншотов после shell-first прохода Stage 2.

## Что входит

- `library-light.png`
- `library-dark.png`
- `tickets-light.png`
- `tickets-dark.png`
- `training-light.png`
- `training-dark.png`
- `settings-light.png`
- `settings-dark.png`
- `defense-light.png`
- `defense-dark.png`
- `statistics-light.png`
- `statistics-dark.png`

## Что проверялось

- облегчённый `Sidebar` без trailing brass-dot;
- более тихий `TopBar` с ослабленным divider и ghost action;
- compact utility surface для shell status;
- верхний ритм экранов `Settings`, `Knowledge Map`, `Sections`, `Statistics`, `Defense`;
- паритет иерархии между `light` и `dark`.

## Связанные проверки

- `python -m pytest -q`
- `python scripts/ui_click_audit.py --theme light`
- `python scripts/ui_click_audit.py --theme dark`
