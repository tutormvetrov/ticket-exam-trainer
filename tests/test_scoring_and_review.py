from __future__ import annotations

from datetime import datetime

from application.adaptive_review import AdaptiveReviewService
from application.concept_linking import ConceptLinkingService
from application.exercise_generation import ExerciseGenerator
from application.import_service import DocumentImportService, TicketCandidate
from application.scoring import MicroSkillScoringService
from domain.answer_profile import AnswerProfileCode
from domain.knowledge import ExerciseType, ReviewMode, TicketMasteryProfile, WeakArea, WeakAreaKind


def build_ticket(title: str, body: str):
    service = DocumentImportService()
    candidate = TicketCandidate(1, title, body, 0.9, "public-assets")
    ticket, _, _ = service.build_ticket_map(candidate, "exam-demo", "public-assets", "doc-demo")
    return ticket


def test_exercise_generation_has_multiple_modes() -> None:
    ticket = build_ticket(
        "What is public property?",
        "Public property is a public resource. Examples include land and buildings. It has a legal regime. The management cycle includes accounting and review.",
    )
    generator = ExerciseGenerator()
    instances = generator.generate(ticket)
    exercise_types = {instance.exercise_type for instance in instances}
    assert ExerciseType.ANSWER_SKELETON in exercise_types
    assert ExerciseType.STRUCTURE_RECONSTRUCTION in exercise_types
    assert ExerciseType.ORAL_FULL in exercise_types


def test_micro_skill_scoring_updates_profile() -> None:
    ticket = build_ticket(
        "What is public property?",
        "Public property is a public resource. Examples include land and buildings. It has a legal regime. The management cycle includes accounting and review.",
    )
    exercise = ExerciseGenerator().generate(ticket)[0]
    service = MicroSkillScoringService()
    outcome = service.evaluate(
        ticket,
        exercise,
        "Public property is a public resource with a legal regime. Examples are land and buildings. It requires accounting and review.",
    )
    assert outcome.attempt.score > 0.3
    assert outcome.profile.confidence_score > 0
    assert outcome.skill_scores


def test_adaptive_repeat_queue_prioritizes_weak_items() -> None:
    ticket = build_ticket(
        "What is public property?",
        "Public property is a public resource. Examples include land and buildings. It has a legal regime. The management cycle includes accounting and review.",
    )
    profile = TicketMasteryProfile(
        user_id="local-user",
        ticket_id=ticket.ticket_id,
        definition_mastery=0.3,
        structure_mastery=0.2,
        examples_mastery=0.4,
        feature_mastery=0.3,
        process_mastery=0.2,
        oral_short_mastery=0.1,
        oral_full_mastery=0.1,
        followup_mastery=0.15,
        confidence_score=0.2187,
    )
    weak_areas = [
        WeakArea(
            weak_area_id="weak-1",
            user_id="local-user",
            kind=WeakAreaKind.SKILL,
            reference_id="give_full_oral_answer",
            title="give_full_oral_answer",
            severity=0.8,
            evidence="Low oral answer quality",
            related_ticket_ids=[ticket.ticket_id],
        )
    ]
    queue = AdaptiveReviewService().build_queue(
        "local-user",
        [ticket],
        [profile],
        weak_areas,
        mode=ReviewMode.EXAM_CRUNCH,
        now=datetime(2026, 4, 10, 12, 0, 0),
    )
    assert queue
    assert queue[0].priority >= 0.5


def test_cross_ticket_concept_linking() -> None:
    ticket_a = build_ticket(
        "Public property basics",
        "Public property is a public resource. The management cycle includes accounting and review.",
    )
    ticket_b = build_ticket(
        "Efficiency of public property",
        "Efficiency of public property depends on the management cycle and public goals.",
    )
    concepts = ConceptLinkingService().build([ticket_a, ticket_b])
    assert concepts
    assert ticket_a.cross_links_to_other_tickets
    assert ticket_b.cross_links_to_other_tickets


def test_state_exam_scoring_adds_block_and_criterion_scores() -> None:
    service = DocumentImportService()
    candidate = TicketCandidate(
        1,
        "Что представляет собой государственное имущество как объект управления?",
        (
            "Актуальность вопроса связана с управлением публичными ресурсами. "
            "Теоретическая часть включает понятие имущества, правовой режим и управленческий цикл. "
            "Практическая часть раскрывается через учет, оценку, контроль и выбор управленческих решений. "
            "Навыки проявляются через анализ, аргументацию и применение методов управления. "
            "В заключении имущество рассматривается как активный ресурс публичной власти. "
            "Дополнительно полезны схемы и сравнительный анализ практик."
        ),
        0.9,
        "state-exam",
    )
    ticket, _, _ = service.build_ticket_map(
        candidate,
        "exam-demo",
        "state-exam",
        "doc-demo",
        answer_profile_code=AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN,
    )
    exercise = next(instance for instance in ExerciseGenerator().generate(ticket) if instance.exercise_type is ExerciseType.ORAL_FULL)
    outcome = MicroSkillScoringService().evaluate(
        ticket,
        exercise,
        (
            "Проблема управления государственным имуществом связана с эффективностью публичных ресурсов. "
            "Теоретически важно определить правовой режим, функции и управленческий цикл. "
            "Практически нужно учитывать имущество, оценивать его использование и предлагать меры повышения эффективности. "
            "Навыки проявляются через анализ, выбор методов и аргументацию решений. "
            "Итог состоит в том, что имущество является активным управленческим ресурсом. "
            "Дополнительно можно показать схему и сравнить подходы."
        ),
    )

    assert outcome.block_scores
    assert len(outcome.block_scores) == 6
    assert outcome.criterion_scores
    assert len(outcome.criterion_scores) == 6
    assert outcome.block_profile is not None
    assert outcome.attempt_block_scores
    assert any(area.kind is WeakAreaKind.ANSWER_BLOCK or area.kind is WeakAreaKind.RUBRIC_CRITERION for area in outcome.weak_areas) or outcome.attempt.score > 0
