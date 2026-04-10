from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrainingModeSpec:
    key: str
    title: str
    workspace_title: str
    workspace_hint: str
    empty_title: str
    empty_body: str


TRAINING_MODE_SPECS: dict[str, TrainingModeSpec] = {
    "reading": TrainingModeSpec(
        key="reading",
        title="Чтение билета",
        workspace_title="Чтение и разбор билета",
        workspace_hint="Сначала изучите вопрос и эталонный ответ, потом отметьте, усвоен ли материал.",
        empty_title="Нет билета для чтения",
        empty_body="Импортируйте и обработайте материалы или выберите билет вручную.",
    ),
    "active-recall": TrainingModeSpec(
        key="active-recall",
        title="Активное вспоминание",
        workspace_title="Вспомнить до подсказки",
        workspace_hint="Сначала попытайтесь воспроизвести ответ по памяти, затем откройте эталон и оцените себя.",
        empty_title="Нет билета для вспоминания",
        empty_body="Импортируйте материалы или выберите билет вручную, чтобы начать recall-first тренировку.",
    ),
    "cloze": TrainingModeSpec(
        key="cloze",
        title="Заполнение пропусков",
        workspace_title="Смысловые пропуски",
        workspace_hint="Заполните ключевые пропуски в формулировках и проверьте, удерживаете ли смысловые узлы.",
        empty_title="Нет текста для пропусков",
        empty_body="Для этого режима нужен билет с выделенными атомами знания и ключевыми формулировками.",
    ),
    "matching": TrainingModeSpec(
        key="matching",
        title="Сопоставление",
        workspace_title="Термины и определения",
        workspace_hint="Соотнесите понятия с определениями и проверьте, не путаются ли смысловые пары.",
        empty_title="Нет данных для сопоставления",
        empty_body="Для режима сопоставления нужен билет хотя бы с двумя содержательными атомами знания.",
    ),
    "plan": TrainingModeSpec(
        key="plan",
        title="Сбор плана ответа",
        workspace_title="Сбор структуры ответа",
        workspace_hint="Соберите тезисы в правильный порядок и проверьте, держите ли логику ответа целиком.",
        empty_title="Нет тезисов для плана",
        empty_body="Для этого режима нужен билет с несколькими смысловыми блоками или шагами ответа.",
    ),
    "mini-exam": TrainingModeSpec(
        key="mini-exam",
        title="Мини-экзамен",
        workspace_title="Экзаменационный прогон",
        workspace_hint="Получите случайный билет, уложитесь в таймер и сдайте полноценный ответ как на устном экзамене.",
        empty_title="Нет билета для мини-экзамена",
        empty_body="Сначала импортируйте и обработайте материалы, затем выберите или сгенерируйте случайный билет.",
    ),
}

