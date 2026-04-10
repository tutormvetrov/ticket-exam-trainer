from __future__ import annotations

from domain.answer_profile import (
    AnswerBlockCode,
    AnswerBlockSpec,
    AnswerCriterionCode,
    AnswerCriterionSpec,
    AnswerProfileCode,
    AnswerProfileSpec,
)


STANDARD_TICKET_PROFILE = AnswerProfileSpec(
    code=AnswerProfileCode.STANDARD_TICKET,
    title="Обычный билет",
    description="Стандартный режим для обычных билетов без жёсткой рубрики госэкзамена.",
    blocks=[],
    criteria=[],
)


STATE_EXAM_PUBLIC_ADMIN_PROFILE = AnswerProfileSpec(
    code=AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN,
    title="Госэкзамен",
    description="Профиль ответа по структуре идеального ответа на госэкзамене по государственному и муниципальному управлению.",
    blocks=[
        AnswerBlockSpec(
            code=AnswerBlockCode.INTRO,
            title="Введение",
            description="Постановка проблемы, актуальность и цель ответа.",
            weight=1.0,
            keywords=["проблем", "актуаль", "цель", "контекст", "постановк"],
            training_hint="Кратко обозначьте проблему, её актуальность и цель ответа.",
            followup_hint="Уточните постановку проблемы и актуальность вопроса.",
        ),
        AnswerBlockSpec(
            code=AnswerBlockCode.THEORY,
            title="Теория",
            description="Теоретическая база, понятия, нормативно-правовые основы.",
            weight=1.25,
            keywords=["понят", "теор", "концепц", "закон", "норматив", "определен", "подход"],
            training_hint="Покажите понятийную и нормативную базу билета.",
            followup_hint="Раскройте теоретическую основу и ключевые понятия.",
        ),
        AnswerBlockSpec(
            code=AnswerBlockCode.PRACTICE,
            title="Практическая часть",
            description="Применение теории к анализу ситуации и выбору решений.",
            weight=1.15,
            keywords=["практик", "пример", "ситуац", "решени", "анализ", "кейс", "примен"],
            training_hint="Покажите, как теория применяется к реальной управленческой ситуации.",
            followup_hint="Добавьте практический пример или управленческое решение.",
        ),
        AnswerBlockSpec(
            code=AnswerBlockCode.SKILLS,
            title="Навыки",
            description="Демонстрация владения анализом, аргументацией, методами и инструментами.",
            weight=1.15,
            keywords=["анализ", "синтез", "аргумент", "метод", "инструмент", "планирован", "управлен"],
            training_hint="Покажите, какими профессиональными навыками и инструментами вы владеете.",
            followup_hint="Уточните, какие навыки и методы вы применяете в ответе.",
        ),
        AnswerBlockSpec(
            code=AnswerBlockCode.CONCLUSION,
            title="Заключение",
            description="Итог ответа, выводы и рекомендации.",
            weight=1.0,
            keywords=["итог", "вывод", "рекомендац", "перспектив", "резюм"],
            training_hint="Кратко подведите итог и сформулируйте вывод.",
            followup_hint="Сформулируйте ясный вывод и итог ответа.",
        ),
        AnswerBlockSpec(
            code=AnswerBlockCode.EXTRA,
            title="Дополнительные элементы",
            description="Сравнения, схемы, таблицы, междисциплинарные связи.",
            weight=0.75,
            keywords=["сравнен", "таблиц", "схем", "междисциплин", "связь", "нагляд"],
            training_hint="Добавьте сравнение, схему, таблицу или междисциплинарную связь, если это уместно.",
            followup_hint="Есть ли у ответа дополнительные усиливающие элементы.",
        ),
    ],
    criteria=[
        AnswerCriterionSpec(AnswerCriterionCode.COMPLETENESS, "Полнота", "Охват всех аспектов вопроса.", 1.0),
        AnswerCriterionSpec(AnswerCriterionCode.DEPTH, "Глубина анализа", "Использование теории, данных и примеров.", 1.0),
        AnswerCriterionSpec(AnswerCriterionCode.STRUCTURE, "Логичность и структурированность", "Ясная последовательность изложения.", 1.0),
        AnswerCriterionSpec(AnswerCriterionCode.PRACTICAL, "Практическая направленность", "Предложение конкретных решений и применения.", 0.95),
        AnswerCriterionSpec(AnswerCriterionCode.ORIGINALITY, "Оригинальность", "Нестандартность и осмысленность подхода.", 0.7),
        AnswerCriterionSpec(AnswerCriterionCode.COMPETENCE, "Соответствие компетенциям", "Демонстрация умений и профессиональных навыков.", 1.0),
    ],
    followup_templates={
        AnswerBlockCode.INTRO: ["Почему эта проблема актуальна именно в контексте государственного управления?"],
        AnswerBlockCode.THEORY: ["Какие ключевые теоретические и нормативные основания вы используете?"],
        AnswerBlockCode.PRACTICE: ["Как эта теория применяется к практической управленческой ситуации?"],
        AnswerBlockCode.SKILLS: ["Какие навыки и методы вы фактически продемонстрировали в ответе?"],
        AnswerBlockCode.CONCLUSION: ["Какой итоговый вывод следует из вашего ответа?"],
        AnswerBlockCode.EXTRA: ["Чем можно усилить ответ сравнением, схемой или междисциплинарной связью?"],
    },
    mode_hints={
        "reading": "Читайте билет как заготовку ответа по рубрике госэкзамена.",
        "active-recall": "Вспоминайте ответ не абстрактно, а по блокам госэкзамена.",
        "cloze": "Заполняйте пропуски в ключевых частях структуры госответа.",
        "plan": "Собирайте порядок ответа по структуре госэкзамена.",
        "mini-exam": "Отвечайте так, как будто закрываете все блоки комиссии под таймер.",
        "state-exam-full": "Дайте полный структурированный ответ по всей рубрике госэкзамена.",
    },
)


ANSWER_PROFILE_REGISTRY: dict[AnswerProfileCode, AnswerProfileSpec] = {
    STANDARD_TICKET_PROFILE.code: STANDARD_TICKET_PROFILE,
    STATE_EXAM_PUBLIC_ADMIN_PROFILE.code: STATE_EXAM_PUBLIC_ADMIN_PROFILE,
}


def get_answer_profile(code: AnswerProfileCode | str | None) -> AnswerProfileSpec:
    try:
        normalized = AnswerProfileCode(code or AnswerProfileCode.STANDARD_TICKET)
    except ValueError:
        normalized = AnswerProfileCode.STANDARD_TICKET
    return ANSWER_PROFILE_REGISTRY[normalized]


def answer_profile_label(code: AnswerProfileCode | str | None) -> str:
    return get_answer_profile(code).title
