from __future__ import annotations

from datetime import datetime, timedelta

from application.adaptive_review import (
    COLD_START_INTERVALS_DAYS,
    AdaptiveReviewService,
)
from application.import_service import DocumentImportService, TicketCandidate
from domain.knowledge import ReviewMode, TicketMasteryProfile, WeakArea, WeakAreaKind


NOW = datetime(2026, 4, 16, 12, 0, 0)


def _ticket(title: str = "Ticket", body: str = "Definition. Example. Regime."):
    service = DocumentImportService()
    candidate = TicketCandidate(1, title, body, 0.9, "section-1")
    ticket, _, _ = service.build_ticket_map(candidate, "exam-demo", "section-1", "doc-demo")
    return ticket


def test_empty_tickets_yields_empty_queue() -> None:
    queue = AdaptiveReviewService().build_queue("u", [], [], [], now=NOW)
    assert queue == []


def test_weak_ticket_gets_higher_priority_than_strong() -> None:
    weak = _ticket("Weak")
    strong = _ticket("Strong")
    profiles = [
        TicketMasteryProfile(user_id="u", ticket_id=weak.ticket_id, confidence_score=0.1,
                             definition_mastery=0.1, oral_short_mastery=0.1, oral_full_mastery=0.1,
                             followup_mastery=0.1),
        TicketMasteryProfile(user_id="u", ticket_id=strong.ticket_id, confidence_score=0.9,
                             definition_mastery=0.9, oral_short_mastery=0.9, oral_full_mastery=0.9,
                             followup_mastery=0.9),
    ]
    queue = AdaptiveReviewService().build_queue("u", [weak, strong], profiles, [], now=NOW)
    # Первый в очереди — более слабый.
    assert queue[0].ticket_id == weak.ticket_id


def test_exam_crunch_mode_boosts_priority() -> None:
    ticket = _ticket()
    profile = TicketMasteryProfile(user_id="u", ticket_id=ticket.ticket_id, confidence_score=0.4,
                                   definition_mastery=0.4, oral_short_mastery=0.4, oral_full_mastery=0.4,
                                   followup_mastery=0.4)
    standard = AdaptiveReviewService().build_queue("u", [ticket], [profile], [], mode=ReviewMode.STANDARD_ADAPTIVE, now=NOW)
    crunch = AdaptiveReviewService().build_queue("u", [ticket], [profile], [], mode=ReviewMode.EXAM_CRUNCH, now=NOW)

    # Приоритет crunch всегда ≥ standard (bonus 0.15).
    assert crunch[0].priority > standard[0].priority


def test_exam_crunch_shortens_due_for_post_coldstart_ticket() -> None:
    """Для билетов, прошедших cold-start, EXAM_CRUNCH обязан ужимать due.

    Для совсем новой карточки (attempts_count=0) обе ветки дают
    `now + 1 day` — ступенька cold-start одинакова для любого режима.
    Поэтому прогрев вручную: карточка уже прошла 3 попытки.
    """
    service = AdaptiveReviewService()
    ticket = _ticket()
    profile = TicketMasteryProfile(user_id="u", ticket_id=ticket.ticket_id, confidence_score=0.4)

    # Три прогона active-recall, чтобы выйти из cold-start.
    review_time = NOW
    for _ in range(3):
        profile = service.record_attempt(profile, "active-recall", 80, now=review_time)
        review_time = (profile.next_review_at or review_time) + timedelta(minutes=1)

    # Спрашиваем очередь сразу после последнего review (т.е. до наступления
    # нового due), чтобы EXAM_CRUNCH имел что ужимать.
    query_time = profile.last_reviewed_at or review_time
    standard = service.build_queue("u", [ticket], [profile], [], mode=ReviewMode.STANDARD_ADAPTIVE, now=query_time)
    crunch = service.build_queue("u", [ticket], [profile], [], mode=ReviewMode.EXAM_CRUNCH, now=query_time)
    assert crunch[0].due_at < standard[0].due_at


def test_concept_weak_area_adds_extra_queue_item() -> None:
    ticket = _ticket()
    profile = TicketMasteryProfile(user_id="u", ticket_id=ticket.ticket_id, confidence_score=0.3)
    weak = [
        WeakArea(
            weak_area_id="w1",
            user_id="u",
            kind=WeakAreaKind.CONCEPT,
            reference_id="concept-definition",
            title="Определение",
            severity=0.7,
            evidence="x",
            related_ticket_ids=[ticket.ticket_id],
        )
    ]
    queue = AdaptiveReviewService().build_queue("u", [ticket], [profile], weak, now=NOW)
    # Один item для билета + один для concept weak area.
    assert len(queue) == 2
    reference_types = {item.reference_type for item in queue}
    assert "ticket" in reference_types
    assert WeakAreaKind.CONCEPT.value in reference_types


def test_skill_weak_area_does_not_add_extra_item() -> None:
    # SKILL/ANSWER_BLOCK и пр. не порождают доп. запись — только поднимают priority билета.
    ticket = _ticket()
    profile = TicketMasteryProfile(user_id="u", ticket_id=ticket.ticket_id, confidence_score=0.3)
    weak = [
        WeakArea(
            weak_area_id="w1",
            user_id="u",
            kind=WeakAreaKind.SKILL,
            reference_id="give_full_oral_answer",
            title="give_full_oral_answer",
            severity=0.7,
            evidence="x",
            related_ticket_ids=[ticket.ticket_id],
        )
    ]
    queue = AdaptiveReviewService().build_queue("u", [ticket], [profile], weak, now=NOW)
    assert len(queue) == 1
    assert queue[0].reference_type == "ticket"


def test_ticket_without_profile_still_queued_with_default_profile() -> None:
    ticket = _ticket()
    queue = AdaptiveReviewService().build_queue("u", [ticket], [], [], now=NOW)
    # Незатронутый билет всё равно попадает в очередь.
    assert len(queue) == 1
    assert queue[0].ticket_id == ticket.ticket_id
    # Low mastery → высокий приоритет.
    assert queue[0].priority >= 0.4


def test_priority_is_bounded() -> None:
    ticket = _ticket()
    profile = TicketMasteryProfile(user_id="u", ticket_id=ticket.ticket_id, confidence_score=0.0)
    weak = [
        WeakArea(
            weak_area_id="w1",
            user_id="u",
            kind=WeakAreaKind.SKILL,
            reference_id="x",
            title="x",
            severity=1.0,
            evidence="x",
            related_ticket_ids=[ticket.ticket_id],
        )
    ]
    queue = AdaptiveReviewService().build_queue("u", [ticket], [profile], weak, mode=ReviewMode.EXAM_CRUNCH, now=NOW)
    for item in queue:
        assert 0.1 <= item.priority <= 1.5


def test_new_ticket_gets_cold_start_ladder_first_step() -> None:
    ticket = _ticket()
    queue = AdaptiveReviewService().build_queue("u", [ticket], [], [], now=NOW)
    expected = NOW + timedelta(days=COLD_START_INTERVALS_DAYS[0])
    assert queue[0].due_at == expected


def test_partially_trained_ticket_uses_next_ladder_step() -> None:
    """Профиль с attempts_count=1 → следующий шаг лестницы (3 дня)."""
    ticket = _ticket()
    profile = TicketMasteryProfile(
        user_id="u",
        ticket_id=ticket.ticket_id,
        attempts_count=1,
    )
    queue = AdaptiveReviewService().build_queue("u", [ticket], [profile], [], now=NOW)
    expected = NOW + timedelta(days=COLD_START_INTERVALS_DAYS[1])
    assert queue[0].due_at == expected
