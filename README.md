# Тезис: тренажёр билетов к письменному госэкзамену

Локальное desktop-приложение на `Python 3.12+` и `Flet` для подготовки к письменному госэкзамену ГМУ (ВШГА МГУ, май 2026). 208 билетов курса вшиты в сборку, вся работа происходит офлайн, прогресс хранится только на компьютере пользователя. LLM-функции (содержательный рецензент) работают опционально через локальный `Ollama`.

## Что внутри

- **Ежедневный ритуал вместо тренажёра.** Главный экран — Дневник с тремя состояниями: утром приветствие и очередь на сегодня, днём лента попыток с дельтами балла, вечером сводка дня и лучший момент.
- **6 тренировочных режимов**, выстроенных по возрастанию нагрузки на память: `reading` (чтение эталона), `plan` (восстановление скелета), `cloze` (закрытие пропусков), `active-recall` (активное воспроизведение), `state-exam-full` (полный письменный ответ с таймером 20–40 минут), `review` (разбор готового ответа).
- **Алгоритм интервальных повторений FSRS** с cold-start-лестницей: приложение само выбирает, какой билет показать сегодня, основываясь на истории попыток и confidence-сигнале пользователя.
- **Калибровка уверенности.** Перед проверкой свободного ответа пользователь обязан выбрать 🤷 / 🤔 / 💡 — после проверки приложение сопоставляет уверенность с реальным баллом и даёт метакогнитивный отклик.
- **Локальный профиль** (имя + emoji-аватар), создаётся при первом запуске, никакой регистрации.
- **Light + dark warm-minimal тема**, шрифты Lora (serif) + Golos Text (sans) + JetBrains Mono (monospace), адаптивный layout от 1024 до 3840+.

## Скачать

Готовые сборки для Windows и macOS — в разделе [Releases](https://github.com/tutormvetrov/ticket-exam-trainer/releases).

Инструкция для однокурсников на 10 шагов, включая обход SmartScreen и Gatekeeper, лежит в каждом архиве в файле `README_classmates.md`.

## Запуск из исходников

```powershell
python -m pip install -r requirements.txt
python -m ui_flet.main
```

На macOS аналогично через `python3`.

При первом запуске приложение создаёт локальный workspace в `%LOCALAPPDATA%\Tezis\app_data\` (Windows) или `~/Library/Application Support/Tezis/app_data/` (macOS) и копирует туда предзагруженную БД билетов.

## Опциональный ИИ-рецензент (Ollama)

Без Ollama приложение проверяет ответы по ключевым словам — это работает офлайн и мгновенно. С Ollama рецензент даёт per-thesis verdict, сильные стороны и рекомендации.

Автоматическая установка через мастер (Windows):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_ollama_wizard.ps1
```

Мастер определит железо (RAM/VRAM), подберёт подходящий тир модели (qwen2.5:7b-instruct-q4_K_M для 8–16 GB RAM, vikhr-nemo-12b для 16+ GB, keyword-fallback для <8 GB), установит Ollama через winget, скачает модель, проверит canary и пропишет выбор в settings.

## Сборка бинарника

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_flet_exe.ps1
```

Выход: `dist\Tezis.exe` (~100 МБ, onefile-bundle). Seed-БД и TTF-шрифты упаковываются внутрь.

Для macOS — `scripts/build_mac_app.sh python3 data/state_exam_public_admin_demo.db`.

GitHub Actions workflow `.github/workflows/release.yml` собирает оба бинарника автоматически по push-у тега вида `v*` и публикует GitHub Release.

## Тесты

```powershell
python -m pytest -q
```

Текущий статус: `397 passed, 5 skipped, 0 failed`.

Ключевые test-контуры:
- `test_language_contract.py` — AST-визитор, проверяет, что все user-facing строки в `ui_flet/` на русском и что нет прямого рендеринга domain-enum'ов в widget-ах.
- `test_block_derivation.py` — эвристика восстановления недостающих answer-blocks из типизированных атомов и «Фрагмент N»-fallback'ов.
- `test_daily_digest.py` — агрегатор дневной сводки (попытки, best-moment, дельта vs предыдущая попытка, mastered-сегодня).
- `test_ticket_quality.py` — skeleton-weak heuristic.
- `test_user_profile.py` — валидация имени, round-trip профиля, corrupt-file handling.
- `test_flet_router.py` — auth-gate (нет профиля → /onboarding), /journal как root-route.

## Архитектура

Три слоя без циклов:

- `domain/` — чистые dataclass'ы билета, атома, оценки. Нулевые внешние зависимости.
- `application/` — сервисы: `AppFacade` (единая точка в UI), `MicroSkillScoringService`, `StateExamScoringService`, `AdaptiveReviewService` (FSRS), `user_profile`, `daily_digest`, `ticket_quality`, `block_derivation`.
- `infrastructure/` — `sqlite3` репозитории, Ollama HTTP-клиент.
- `ui_flet/` — Flet-интерфейс: `views/` (3 root-screen'а: onboarding, journal, tickets, training, settings), `workspaces/` (6 тренировочных), `components/` (top bar, ticket card, attempt card, calibration chips, ornamental divider и т.д.), `theme/` (tokens + elevation + buttons + fonts), `i18n/ru.py` — единственное место с пользовательскими строками.

## Документация

- [Архитектура](docs/architecture.md)
- [Быстрый старт](docs/quickstart.md)
- [Быстрый старт для госэкзамена](docs/quickstart_state_exam.md)
- [Руководство пользователя](docs/user_guide.md)
- [Специфика госэкзамена](docs/product_spec.md)
- [Handoff для разработки](PICKUP.md)
- [Инструкция для однокурсников](README_classmates.md) — humanitarian-friendly, 10 шагов от ZIP до первого разобранного билета

Активные дизайн-спеки Flet-миграции и сопутствующих полиш-этапов в `docs/superpowers/specs/`.

## Лицензия и контекст

Проект сделан для однокурсников. Билеты, структура ответа и методика основаны на конспекте курса и открытых исследованиях по педагогической психологии (retrieval practice, spaced repetition).

Код без лицензии. Если хочется переиспользовать — пишите автору.
