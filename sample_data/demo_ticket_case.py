from __future__ import annotations

from domain.knowledge import (
    AtomType,
    CrossTicketLink,
    ExerciseTemplate,
    ExerciseType,
    ExaminerPrompt,
    KnowledgeAtom,
    ScoringCriterion,
    SkillCode,
    TicketKnowledgeMap,
    TicketSkill,
)


DEMO_TICKET = TicketKnowledgeMap(
    ticket_id="ticket-public-assets-01",
    exam_id="state-exam-public-admin",
    section_id="section-public-property-management",
    source_document_id="doc-public-admin-notes",
    title="Что представляет собой государственное и муниципальное имущество как объект управления?",
    canonical_answer_summary=(
        "Государственное и муниципальное имущество рассматривается как часть публичных ресурсов, "
        "которая имеет правовой режим, служит публичным целям, требует учета, оценки, контроля и "
        "включается в непрерывный управленческий цикл от выявления и закрепления до использования, "
        "мониторинга и корректировки."
    ),
    atoms=[
        KnowledgeAtom(
            atom_id="atom-definition-public-assets",
            type=AtomType.DEFINITION,
            label="Определение",
            text=(
                "Государственное и муниципальное имущество представляет собой часть публичных ресурсов, "
                "закрепленную за публично-правовыми образованиями и используемую для достижения общественных целей."
            ),
            keywords=["имущество", "публичные ресурсы", "объект управления"],
            weight=1.0,
            confidence=0.95,
        ),
        KnowledgeAtom(
            atom_id="atom-examples-public-assets",
            type=AtomType.EXAMPLES,
            label="Примеры имущества",
            text=(
                "К имуществу относятся земельные участки, здания, сооружения, инфраструктура, "
                "доли участия, оборудование и иные активы, находящиеся в публичной собственности."
            ),
            keywords=["земля", "здания", "инфраструктура", "активы"],
            weight=0.8,
            dependencies=["atom-definition-public-assets"],
            confidence=0.9,
        ),
        KnowledgeAtom(
            atom_id="atom-features-public-assets",
            type=AtomType.FEATURES,
            label="Ключевые признаки",
            text=(
                "Имущество характеризуется специальным правовым режимом, функциональной направленностью, "
                "обязательностью учета, оценки эффективности и контроля использования."
            ),
            keywords=["правовой режим", "функция", "оценка", "контроль"],
            weight=1.0,
            dependencies=["atom-definition-public-assets"],
            confidence=0.93,
        ),
        KnowledgeAtom(
            atom_id="atom-cycle-public-assets",
            type=AtomType.PROCESS_STEP,
            label="Управленческий цикл",
            text=(
                "Управление включает выявление имущества, закрепление правового статуса, учет, оценку, "
                "распределение способов использования, контроль результатов и корректировку решений."
            ),
            keywords=["учет", "оценка", "использование", "контроль", "корректировка"],
            weight=1.1,
            dependencies=["atom-features-public-assets"],
            confidence=0.91,
        ),
        KnowledgeAtom(
            atom_id="atom-conclusion-public-assets",
            type=AtomType.CONCLUSION,
            label="Вывод",
            text=(
                "Публичное имущество является не пассивным набором активов, а управленческим ресурсом, "
                "от качества управления которым зависит достижение общественно значимых результатов."
            ),
            keywords=["управленческий ресурс", "общественный результат"],
            weight=0.9,
            dependencies=["atom-cycle-public-assets"],
            confidence=0.94,
        ),
    ],
    skills=[
        TicketSkill(
            skill_id="skill-public-assets-definition",
            code=SkillCode.REPRODUCE_DEFINITION,
            title="Воспроизвести определение",
            description="Дать точное определение имущества как объекта публичного управления.",
            target_atom_ids=["atom-definition-public-assets"],
            weight=1.0,
            priority=3,
        ),
        TicketSkill(
            skill_id="skill-public-assets-examples",
            code=SkillCode.LIST_EXAMPLES,
            title="Привести примеры",
            description="Перечислить типичные виды государственного и муниципального имущества.",
            target_atom_ids=["atom-examples-public-assets"],
            weight=0.7,
            priority=2,
        ),
        TicketSkill(
            skill_id="skill-public-assets-features",
            code=SkillCode.NAME_KEY_FEATURES,
            title="Назвать ключевые признаки",
            description="Перечислить правовые и функциональные признаки объекта управления.",
            target_atom_ids=["atom-features-public-assets"],
            weight=1.0,
            priority=3,
        ),
        TicketSkill(
            skill_id="skill-public-assets-order",
            code=SkillCode.RECONSTRUCT_PROCESS_ORDER,
            title="Восстановить управленческий цикл",
            description="Правильно выстроить этапы управления имуществом.",
            target_atom_ids=["atom-cycle-public-assets"],
            weight=1.0,
            priority=3,
        ),
        TicketSkill(
            skill_id="skill-public-assets-logic",
            code=SkillCode.EXPLAIN_CORE_LOGIC,
            title="Объяснить управленческую логику",
            description="Показать, почему имущество является именно управленческим ресурсом.",
            target_atom_ids=[
                "atom-definition-public-assets",
                "atom-features-public-assets",
                "atom-cycle-public-assets",
                "atom-conclusion-public-assets",
            ],
            weight=1.2,
            priority=4,
        ),
        TicketSkill(
            skill_id="skill-public-assets-short-oral",
            code=SkillCode.GIVE_SHORT_ORAL_ANSWER,
            title="Дать краткий устный ответ",
            description="Ответить за 40 секунд с сохранением структуры и смысла.",
            target_atom_ids=[
                "atom-definition-public-assets",
                "atom-features-public-assets",
                "atom-conclusion-public-assets",
            ],
            weight=1.1,
            priority=4,
        ),
        TicketSkill(
            skill_id="skill-public-assets-full-oral",
            code=SkillCode.GIVE_FULL_ORAL_ANSWER,
            title="Дать полный устный ответ",
            description="Раскрыть определение, признаки, цикл и вывод в экзаменационном формате.",
            target_atom_ids=[
                "atom-definition-public-assets",
                "atom-examples-public-assets",
                "atom-features-public-assets",
                "atom-cycle-public-assets",
                "atom-conclusion-public-assets",
            ],
            weight=1.3,
            priority=5,
        ),
        TicketSkill(
            skill_id="skill-public-assets-followups",
            code=SkillCode.ANSWER_FOLLOWUP_QUESTIONS,
            title="Отвечать на уточняющие вопросы",
            description="Удерживать логику ответа при вопросах экзаменатора о целях, эффективности и контроле.",
            target_atom_ids=[
                "atom-features-public-assets",
                "atom-cycle-public-assets",
                "atom-conclusion-public-assets",
            ],
            weight=1.2,
            priority=5,
        ),
    ],
    exercise_templates=[
        ExerciseTemplate(
            template_id="tpl-public-assets-skeleton",
            exercise_type=ExerciseType.ANSWER_SKELETON,
            title="Каркас ответа",
            instructions="Заполните смысловые блоки: определение, примеры, признаки, цикл, вывод.",
            target_atom_ids=[
                "atom-definition-public-assets",
                "atom-examples-public-assets",
                "atom-features-public-assets",
                "atom-cycle-public-assets",
                "atom-conclusion-public-assets",
            ],
            target_skill_codes=[SkillCode.GIVE_FULL_ORAL_ANSWER, SkillCode.EXPLAIN_CORE_LOGIC],
        ),
        ExerciseTemplate(
            template_id="tpl-public-assets-order",
            exercise_type=ExerciseType.STRUCTURE_RECONSTRUCTION,
            title="Восстановление структуры",
            instructions="Расположите этапы управленческого цикла в логическом порядке.",
            target_atom_ids=["atom-cycle-public-assets"],
            target_skill_codes=[SkillCode.RECONSTRUCT_PROCESS_ORDER],
        ),
        ExerciseTemplate(
            template_id="tpl-public-assets-cloze",
            exercise_type=ExerciseType.SEMANTIC_CLOZE,
            title="Cloze по смыслу",
            instructions="Восстановите пропущенные смысловые узлы без дословного копирования.",
            target_atom_ids=["atom-definition-public-assets", "atom-features-public-assets"],
            target_skill_codes=[SkillCode.REPRODUCE_DEFINITION, SkillCode.NAME_KEY_FEATURES],
        ),
        ExerciseTemplate(
            template_id="tpl-public-assets-followup",
            exercise_type=ExerciseType.EXAMINER_FOLLOWUP,
            title="Экзаменатор",
            instructions="Ответьте на уточняющие вопросы по слабым местам билета.",
            target_atom_ids=["atom-features-public-assets", "atom-cycle-public-assets"],
            target_skill_codes=[SkillCode.ANSWER_FOLLOWUP_QUESTIONS],
            llm_required=True,
        ),
    ],
    scoring_rubric=[
        ScoringCriterion(
            criterion_id="crit-public-assets-definition",
            skill_code=SkillCode.REPRODUCE_DEFINITION,
            mastery_field="definition_mastery",
            description="Определение дано точно и без подмены объекта управления простым перечнем активов.",
            max_score=1.0,
            weight=1.0,
        ),
        ScoringCriterion(
            criterion_id="crit-public-assets-structure",
            skill_code=SkillCode.RECONSTRUCT_PROCESS_ORDER,
            mastery_field="structure_mastery",
            description="Этапы цикла названы в логическом порядке, без выпадения контроля и корректировки.",
            max_score=1.0,
            weight=1.1,
        ),
        ScoringCriterion(
            criterion_id="crit-public-assets-examples",
            skill_code=SkillCode.LIST_EXAMPLES,
            mastery_field="examples_mastery",
            description="Примеры релевантны публичной собственности и не подменяют признаки.",
            max_score=1.0,
            weight=0.7,
        ),
        ScoringCriterion(
            criterion_id="crit-public-assets-features",
            skill_code=SkillCode.NAME_KEY_FEATURES,
            mastery_field="feature_mastery",
            description="Отражены правовой режим, функциональная направленность, оценка и контроль.",
            max_score=1.0,
            weight=1.0,
        ),
        ScoringCriterion(
            criterion_id="crit-public-assets-process",
            skill_code=SkillCode.EXPLAIN_CORE_LOGIC,
            mastery_field="process_mastery",
            description="Показана связь между управленческим циклом и достижением общественного результата.",
            max_score=1.0,
            weight=1.2,
        ),
        ScoringCriterion(
            criterion_id="crit-public-assets-short-oral",
            skill_code=SkillCode.GIVE_SHORT_ORAL_ANSWER,
            mastery_field="oral_short_mastery",
            description="Краткий ответ удерживает смысловой каркас без распада на несвязанные тезисы.",
            max_score=1.0,
            weight=1.1,
        ),
        ScoringCriterion(
            criterion_id="crit-public-assets-full-oral",
            skill_code=SkillCode.GIVE_FULL_ORAL_ANSWER,
            mastery_field="oral_full_mastery",
            description="Полный ответ раскрывает билет последовательно и уверенно.",
            max_score=1.0,
            weight=1.3,
        ),
        ScoringCriterion(
            criterion_id="crit-public-assets-followup",
            skill_code=SkillCode.ANSWER_FOLLOWUP_QUESTIONS,
            mastery_field="followup_mastery",
            description="Уточняющие вопросы не ломают логику ответа и не уводят в общие слова.",
            max_score=1.0,
            weight=1.2,
        ),
    ],
    examiner_prompts=[
        ExaminerPrompt(
            prompt_id="prompt-public-assets-1",
            title="Проверка логики",
            text="Почему публичное имущество нельзя рассматривать только как перечень активов?",
            target_skill_codes=[SkillCode.EXPLAIN_CORE_LOGIC],
            target_atom_ids=["atom-conclusion-public-assets", "atom-cycle-public-assets"],
        ),
        ExaminerPrompt(
            prompt_id="prompt-public-assets-2",
            title="Проверка управления",
            text="Какие управленческие решения требуются после оценки эффективности использования имущества?",
            target_skill_codes=[SkillCode.ANSWER_FOLLOWUP_QUESTIONS],
            target_atom_ids=["atom-cycle-public-assets"],
        ),
        ExaminerPrompt(
            prompt_id="prompt-public-assets-3",
            title="Проверка признаков",
            text="Какие признаки отличают публичное имущество как объект управления от обычного актива организации?",
            target_skill_codes=[SkillCode.NAME_KEY_FEATURES, SkillCode.ANSWER_FOLLOWUP_QUESTIONS],
            target_atom_ids=["atom-features-public-assets"],
        ),
    ],
    cross_links_to_other_tickets=[
        CrossTicketLink(
            concept_id="concept-public-resources",
            concept_label="Публичные ресурсы",
            related_ticket_ids=["ticket-public-budget-02", "ticket-public-services-05"],
            rationale="Понятие публичных ресурсов повторяется в темах о бюджете и предоставлении услуг.",
            strength=0.92,
        ),
        CrossTicketLink(
            concept_id="concept-management-cycle",
            concept_label="Управленческий цикл",
            related_ticket_ids=["ticket-strategic-planning-04", "ticket-performance-control-07"],
            rationale="Цикл управления переносится на планирование, контроль и оценку результатов.",
            strength=0.88,
        ),
    ],
    difficulty=3,
    estimated_oral_time_sec=90,
    source_confidence=0.91,
)

DEMO_TICKET.validate()
