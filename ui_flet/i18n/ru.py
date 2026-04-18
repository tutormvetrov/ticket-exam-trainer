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

    # Ollama badge
    "ollama.ok":                     "Ollama OK",
    "ollama.offline":                "Fallback-режим",

    # Empty states
    "empty.no_ticket":            "Билет не выбран",
    "empty.no_ticket.hint":        "Откройте список билетов слева и выберите один для тренировки.",
    "empty.generic":               "Данных нет",
}
