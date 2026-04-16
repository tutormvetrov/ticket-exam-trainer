from __future__ import annotations

from domain.models import TrainingModeData


DEFAULT_TRAINING_MODES = [
    TrainingModeData("reading", "Чтение билета", "Ознакомьтесь с вопросом и ответом", "↗", "#F5FAFF", "#5B9BFF"),
    TrainingModeData("active-recall", "Активное вспоминание", "Сначала вопрос, потом ответ", "◌", "#F2FCF7", "#37C887"),
    TrainingModeData("cloze", "Заполнение пропусков", "Заполните пропуски в тексте", "□", "#F8F3FF", "#8D68F3"),
    TrainingModeData("matching", "Сопоставление", "Соотнесите термины и определения", "⚖", "#FFF8F0", "#F4A65A"),
    TrainingModeData("plan", "Сбор плана ответа", "Расположите тезисы в правильном порядке", "⌘", "#F1FBFF", "#59C7DB"),
    TrainingModeData("mini-exam", "Мини-экзамен", "Случайный билет с таймером", "◔", "#FFF5F6", "#F27A89"),
    TrainingModeData("state-exam-full", "Полный госответ", "Ответьте по структуре госэкзамена", "≣", "#F0FAF6", "#18B06A"),
    TrainingModeData("review", "Рецензия ответа", "Потезисный разбор письменного ответа", "✎", "#FFF8F0", "#D4863A"),
]
