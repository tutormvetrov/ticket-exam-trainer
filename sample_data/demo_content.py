from __future__ import annotations

from domain.models import DocumentData, SectionData, SessionData, SubjectData, TicketData, TrainingModeData


DOCUMENTS: list[DocumentData] = [
    DocumentData(
        id="probability",
        title="Теория вероятностей.docx",
        file_type="DOCX",
        subject="Математика",
        imported_at="12.11.2024 в 14:32",
        size="245 КБ",
        status="Обработан",
        display_tickets_count=12,
        sections=[
            SectionData("Случайные события", 3),
            SectionData("Вероятность события", 4),
            SectionData("Независимые испытания", 2),
            SectionData("Случайные величины", 3),
        ],
        tickets=[
            TicketData(1, "Основные определения теории вероятностей", "готов"),
            TicketData(2, "Классическая вероятность и её свойства", "готов"),
            TicketData(3, "Независимые испытания и схема Бернулли", "повторить"),
            TicketData(4, "Случайные величины и распределения", "готов"),
        ],
    ),
    DocumentData(
        id="civil-law",
        title="Гражданское право.pdf",
        file_type="PDF",
        subject="Юриспруденция",
        imported_at="08.11.2024 в 09:14",
        size="1.6 МБ",
        status="Обработан",
        display_tickets_count=18,
        sections=[
            SectionData("Источники гражданского права", 2),
            SectionData("Субъекты правоотношений", 4),
            SectionData("Сделки и представительство", 3),
            SectionData("Право собственности", 5),
            SectionData("Обязательственное право", 2),
            SectionData("Наследование", 2),
        ],
        tickets=[
            TicketData(5, "Предмет и метод гражданского права", "готов"),
            TicketData(6, "Субъекты гражданских правоотношений", "в работе"),
            TicketData(7, "Сделки и их недействительность", "готов"),
        ],
    ),
    DocumentData(
        id="microeconomics",
        title="Микроэкономика.docx",
        file_type="DOCX",
        subject="Экономика",
        imported_at="01.11.2024 в 18:06",
        size="386 КБ",
        status="Обработан",
        display_tickets_count=15,
        sections=[
            SectionData("Спрос и предложение", 4),
            SectionData("Издержки производства", 3),
            SectionData("Совершенная конкуренция", 2),
            SectionData("Монополия", 3),
            SectionData("Рынки факторов производства", 3),
        ],
        tickets=[
            TicketData(8, "Равновесие рынка", "готов"),
            TicketData(9, "Эластичность спроса", "готов"),
            TicketData(10, "Издержки фирмы", "повторить"),
        ],
    ),
]


SUBJECTS: list[SubjectData] = [
    SubjectData("Математика", 1, 4, 12, 72, "#3B82F6"),
    SubjectData("Юриспруденция", 1, 6, 18, 61, "#F59E0B"),
    SubjectData("Экономика", 1, 5, 15, 78, "#10B981"),
    SubjectData("История", 2, 7, 24, 54, "#8B5CF6"),
]


RECENT_SESSIONS: list[SessionData] = [
    SessionData("Теория вероятностей", "Сегодня, 16:20", 85, "success"),
    SessionData("Гражданское право", "Вчера, 19:10", 60, "warning"),
    SessionData("Микроэкономика", "10.11.2024", 78, "success"),
]


TRAINING_MODES: list[TrainingModeData] = [
    TrainingModeData("reading", "Чтение билета", "Ознакомьтесь с вопросом и ответом", "✎", "#F2F7FF", "#8DB5FF"),
    TrainingModeData("active-recall", "Active Recall", "Сначала вопрос, потом ответ", "◔", "#F0FCF7", "#5DDAA6"),
    TrainingModeData("cloze", "Cloze Deletion", "Заполните пропуски в тексте", "□", "#F7F3FF", "#D7C0FF"),
    TrainingModeData("matching", "Сопоставление", "Соотнесите термины и определения", "⚖", "#FFF6EE", "#F7CAA0"),
    TrainingModeData("plan", "Сбор плана ответа", "Расположите тезисы в правильном порядке", "⧉", "#F0FBFF", "#A5E5F2"),
    TrainingModeData("mini-exam", "Мини-экзамен", "Случайный билет с таймером", "⏱", "#FFF2F4", "#FFBEC8"),
]


STAT_TILES = [
    {"icon": "▣", "value": "48", "label": "Отработано билетов", "tone": "blue"},
    {"icon": "♨", "value": "12", "label": "Слабых мест", "tone": "orange"},
    {"icon": "◫", "value": "5", "label": "Сессий за неделю", "tone": "slate"},
]


SECTIONS_OVERVIEW = [
    {"title": "Случайные события", "subject": "Математика", "tickets": 3},
    {"title": "Субъекты правоотношений", "subject": "Юриспруденция", "tickets": 4},
    {"title": "Издержки производства", "subject": "Экономика", "tickets": 3},
    {"title": "Причины реформ", "subject": "История", "tickets": 5},
]


TICKETS_OVERVIEW = [
    {"number": 1, "subject": "Математика", "title": "Классическая вероятность"},
    {"number": 7, "subject": "Юриспруденция", "title": "Сделки и их недействительность"},
    {"number": 10, "subject": "Экономика", "title": "Издержки фирмы"},
    {"number": 14, "subject": "История", "title": "Реформы Александра II"},
]
