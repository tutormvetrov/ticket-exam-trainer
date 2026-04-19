"""All UI strings. Nothing hardcoded in components/views."""

TEXT = {
    "app_title":                 "Тезис",
    "app_subtitle":               "Подготовка к письменному госэкзамену ГМУ",

    # Navigation
    "nav.tickets":                "Билеты",
    "nav.training":               "Тренировка",
    "nav.settings":               "Настройки",

    # Common actions
    "action.start":               "Начать",
    "action.back":                "Назад",
    "action.check":               "Проверить",
    "action.submit":              "Отправить ответ",
    "action.close":               "Закрыть",
    "action.toggle_theme":        "Переключить тему",
    "action.retry":               "Повторить",

    # Tickets view
    "tickets.title":              "Билеты",
    "tickets.subtitle":           "208 билетов экзамена",
    "tickets.filter.all":         "Все",
    "tickets.filter.section":     "Раздел",
    "tickets.filter.difficulty":  "Сложность",
    "tickets.empty":              "Нет билетов по выбранным фильтрам.",
    "tickets.empty.hint":         "Попробуйте сбросить фильтры или изменить поисковый запрос.",
    "tickets.search":             "Поиск по заголовку",
    "tickets.open":               "Открыть",
    "tickets.train":              "Тренировать",
    "tickets.ticket_number":      "Билет",
    "tickets.section_label":      "Раздел",
    "tickets.lecturer_label":     "Лектор",
    "tickets.difficulty_label":   "Сложность",
    "tickets.mastery_label":      "Готовность",
    "tickets.no_selection":       "Выберите билет слева",
    "tickets.no_selection.hint": "Справа появится карточка с эталонным кратким ответом и выбором режима тренировки.",
    "tickets.summary_label":      "Краткий ответ",
    "tickets.count":              "билетов",
    "tickets.reset_filters":      "Сбросить фильтры",
    "tickets.progress.title":     "Прогресс",
    "tickets.progress.queue":     "Очередь повторений",
    "tickets.progress.ready":     "Готовность билета",
    "tickets.progress.empty":     "Нет запланированных повторений",
    "tickets.progress.today":      "Сегодня к повторению",
    "tickets.progress.today.hint": "Билеты, у которых подошло время по FSRS",
    "tickets.progress.today.clear":"На сегодня всё — возвращайтесь завтра",
    "tickets.pick_mode":          "Режим тренировки",

    # Training view
    "training.title":             "Тренировка билета",
    "training.back_to_list":      "К списку билетов",
    "training.pick_mode":         "Выберите режим тренировки",

    "mode.reading.title":         "Чтение эталона",
    "mode.reading.hint":           "Прочитайте эталонный ответ и разметку ключевых узлов. Низкая эффективность для запоминания — используйте только для первого знакомства.",
    "mode.plan.title":             "Восстановление плана",
    "mode.plan.hint":              "Расставьте 6 блоков в правильном порядке для полного ответа по структуре МДЭ ГМУ.",
    "mode.cloze.title":            "Закрытие пропусков",
    "mode.cloze.hint":             "Подставьте недостающие термины, нормы, определения.",
    "mode.active_recall.title":    "Активное воспроизведение",
    "mode.active_recall.hint":     "Напишите короткий ответ по памяти, затем сверьтесь с эталоном. Ключевая методика (Dunlosky #1).",
    "mode.state_exam_full.title":  "Полный письменный ответ",
    "mode.state_exam_full.hint":   "Симуляция письменного экзамена: 6 блоков, таймер 20–40 минут, per-block рецензия.",
    "mode.review.title":           "Рецензия ответа",
    "mode.review.hint":             "Разбор готового ответа — по тезисам и блокам.",

    # State-exam-full blocks
    "block.intro":                "Введение (постановка проблемы)",
    "block.theory":               "Теоретическая часть (знать)",
    "block.practice":             "Практическая часть (уметь)",
    "block.skills":               "Навыки (владеть)",
    "block.conclusion":           "Заключение",
    "block.extra":                "Дополнительные элементы",

    # Timer
    "timer.start":                "Запустить таймер",
    "timer.pause":                "Пауза",
    "timer.elapsed":              "Прошло:",
    "timer.suggested_20":          "20 мин",
    "timer.suggested_30":          "30 мин",
    "timer.suggested_40":          "40 мин",

    # Scoring / feedback
    "result.score":               "Оценка",
    "result.weak_points":         "Слабые места",
    "result.strengths":           "Сильные стороны",
    "result.recommendations":     "Рекомендации",
    "result.per_thesis":          "Разбор по тезисам",
    "result.covered":             "раскрыто",
    "result.partial":             "частично",
    "result.missing":             "не раскрыто",
    "result.review_fallback":     "Рецензия в упрощённом режиме (Ollama не запущена)",
    "result.review_fallback_short": "Упрощённая рецензия",
    "result.by_block":            "Оценка по блокам",
    "result.by_criterion":        "Оценка по критериям",
    "result.positions_correct":   "Правильных позиций",
    "result.matches":             "Совпадений",

    # Ticket side-panel
    "ticket.section":             "Раздел",
    "ticket.difficulty":          "Сложность",
    "ticket.time_to_answer":      "Время ответа",
    "ticket.mastery":             "Mastery",
    "ticket.difficulty.easy":     "Лёгкий",
    "ticket.difficulty.medium":   "Средний",
    "ticket.difficulty.hard":     "Сложный",
    "ticket.about":               "О билете",
    "ticket.not_found":           "Билет не найден или удалён.",

    # Training — reading workspace headings
    "reading.summary":            "Эталонный ответ",
    "reading.atoms":              "Ключевые узлы",
    "reading.blocks":             "Структура ответа",

    # Plan workspace
    "plan.move_up":               "Выше",
    "plan.move_down":             "Ниже",

    # Criteria labels (state_exam_full)
    "criterion.completeness":     "Полнота",
    "criterion.depth":            "Глубина",
    "criterion.structure":        "Структура",
    "criterion.practical":        "Практика",
    "criterion.originality":      "Оригинальность",
    "criterion.competence":       "Компетентность",

    # Workspace hints / placeholders
    "active_recall.placeholder":  "Напишите короткий ответ из памяти — не подглядывая в эталон.",
    "review.placeholder":         "Вставьте или напишите полный ответ для разбора…",
    "review.action":              "Рецензировать",
    "state_exam_full.placeholder_suffix": "— напишите раздел ответа",
    "cloze.empty":                "В этом билете пока нет подходящих атомов для пропусков.",

    # Settings view
    "settings.title":              "Настройки",
    "settings.theme":              "Тема",
    "settings.theme.light":         "Светлая",
    "settings.theme.dark":          "Тёмная",
    "settings.font_size":           "Размер шрифта",
    "settings.ollama.title":         "Рецензирование (Ollama)",
    "settings.ollama.enabled":       "Использовать Ollama",
    "settings.ollama.model":         "Модель",
    "settings.ollama.status":        "Статус:",
    "settings.ollama.status.ok":     "подключена",
    "settings.ollama.status.offline":"не запущена",
    "settings.ollama.test":          "Проверить соединение",
    "settings.ollama.install_hint":  "Без Ollama рецензия работает в упрощённом режиме (ключевые слова).",
    "settings.about":                "О приложении",
    "settings.version":              "Версия",
    "settings.seed":                 "База билетов",

    # Window mode
    "settings.window":               "Окно",
    "settings.window.fullscreen":    "Полноэкранный",
    "settings.window.windowed":      "Оконный",
    "settings.window.hint":          "Esc выходит в оконный режим. Размеры окна сохраняются.",

    # Ollama badge
    "ollama.ok":                     "Ollama OK",
    "ollama.offline":                "Fallback-режим",

    # Empty states
    "empty.no_ticket":            "Билет не выбран",
    "empty.no_ticket.hint":        "Откройте список билетов слева и выберите один для тренировки.",
    "empty.generic":               "Данных нет",

    # Onboarding (первый запуск — создание профиля)
    "onboarding.welcome":           "Привет. Давай познакомимся.",
    "onboarding.subtitle":          "Это твой тренажёр к госэкзамену. Без регистрации и без облака — всё остаётся на этом компьютере.",
    "onboarding.name_label":        "Как к тебе обращаться?",
    "onboarding.name_hint":         "Имя или короткое прозвище, которое увидишь в приложении.",
    "onboarding.avatar_label":      "Выбери аватар",
    "onboarding.avatar_hint":       "Любой — его можно будет поменять в настройках позже.",
    "onboarding.start":             "Начнём",
    "onboarding.avatar_not_picked": "Выбери аватар, прежде чем продолжить.",

    # Journal
    "nav.journal":                  "Дневник",
    "journal.morning.greeting":      "С добрым утром",
    "journal.morning.queue":          "Сегодня тебя ждёт:",
    "journal.morning.queue_review":  "{count} повторений",
    "journal.morning.queue_new":     "{count} новых",
    "journal.morning.queue_time":    "примерно {minutes} минут",
    "journal.morning.queue_empty":   "Очередь пуста — можно взять любой билет, который хочется освежить.",
    "journal.morning.start":         "Начать",
    "journal.morning.yesterday":      "Вчера: {count} билетов, {mastered} легли в долговременную память.",

    "journal.day.title":             "Сегодня",
    "journal.day.empty":             "Пока ни одной попытки. Очередь ждёт.",
    "journal.day.continue":          "Продолжить",
    "journal.day.finish":            "Хватит на сегодня",
    "journal.day.attempt_first":      "первый заход",
    "journal.day.attempt_delta_up":  "+{delta}",
    "journal.day.attempt_delta_down":"−{delta}",

    "journal.evening.title":          "Итог дня",
    "journal.evening.summary":        "Разобрал {count} билетов, {mastered} легли в долговременную память.",
    "journal.evening.summary_simple": "Сегодня разобрано билетов: {count}.",
    "journal.evening.best":           "Лучший момент: {ticket} — {score}%.",
    "journal.evening.tomorrow":        "Завтра: {count} повторений, {new} новых.",
    "journal.evening.close":          "До завтра, {name}.",
    "journal.evening.empty":          "Сегодня ты не занимался. Бывает. Очередь подождёт до завтра.",
    "journal.evening.reopen":         "Открыть дневник заново",

    # Calibration
    "calibration.prompt":             "Насколько ты уверен в ответе?",
    "calibration.guess":              "Угадываю",
    "calibration.idea":               "Есть идеи",
    "calibration.sure":               "Точно знаю",
    "calibration.reply.sure_ok":      "Ты был уверен — и оказался прав.",
    "calibration.reply.sure_miss":    "Был уверен, а это {score}%. Калибровка важнее уверенности.",
    "calibration.reply.idea_ok":      "Ты сомневался, а зря — знаешь лучше, чем думаешь.",
    "calibration.reply.idea_miss":    "Ожидания совпали с реальностью. Это нормально — дай мозгу время.",
    "calibration.reply.guess_ok":     "Неожиданный успех. Не записывай в «знаю» — повтори через день.",
    "calibration.reply.guess_miss":   "Честная самооценка. Возвращайся к этому билету завтра.",
    "calibration.required":           "Выбери уровень уверенности, прежде чем проверить ответ.",

    # Skeleton marker
    "skeleton.weak.tooltip":          "Эталонный план у этого билета короткий — сверяй смысл, не структуру.",
    "skeleton.weak.warning":          "У этого билета эталонный скелет неточный — ориентируйся на смысл ответа, не на количество блоков.",
}
