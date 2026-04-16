from __future__ import annotations

from application.import_service import DocumentImportService, TicketCandidate
from application.readiness import ReadinessService
from application.ui_data import TicketMasteryBreakdown


def _ticket(title: str, body: str = "Short filler body для анализа структуры."):
    service = DocumentImportService()
    candidate = TicketCandidate(1, title, body, 0.9, "section-1")
    ticket, _, _ = service.build_ticket_map(candidate, "exam-demo", "section-1", "doc-demo")
    return ticket


def test_all_tickets_with_zero_confidence_count_as_unpracticed() -> None:
    ticket = _ticket("Ticket 1")
    mastery = {ticket.ticket_id: TicketMasteryBreakdown(ticket_id=ticket.ticket_id, confidence_score=0.0)}
    score = ReadinessService().calculate([ticket], mastery)
    assert score.tickets_practiced == 0
    assert score.percent == 0
    assert score.weakest_area == ""


def test_full_coverage_with_high_mastery_approaches_ceiling() -> None:
    ticket_a = _ticket("Ticket A")
    ticket_b = _ticket("Ticket B")
    mastery = {
        ticket_a.ticket_id: TicketMasteryBreakdown(ticket_id=ticket_a.ticket_id, confidence_score=0.95),
        ticket_b.ticket_id: TicketMasteryBreakdown(ticket_id=ticket_b.ticket_id, confidence_score=0.9),
    }
    score = ReadinessService().calculate([ticket_a, ticket_b], mastery)
    assert score.tickets_practiced == 2
    # coverage=1.0 * avg=0.925 = 92%.
    assert score.percent == 92


def test_weakest_area_is_the_lowest_confidence_practiced_ticket() -> None:
    strong = _ticket("Strong Ticket")
    weak = _ticket("Weak Ticket")
    medium = _ticket("Medium Ticket")
    mastery = {
        strong.ticket_id: TicketMasteryBreakdown(ticket_id=strong.ticket_id, confidence_score=0.9),
        weak.ticket_id: TicketMasteryBreakdown(ticket_id=weak.ticket_id, confidence_score=0.15),
        medium.ticket_id: TicketMasteryBreakdown(ticket_id=medium.ticket_id, confidence_score=0.55),
    }
    score = ReadinessService().calculate([strong, weak, medium], mastery)
    assert score.weakest_area == "Weak Ticket"


def test_percent_is_clamped_to_0_100() -> None:
    # Хотя математически выйти за 100 невозможно, проверяем sanity-clamp.
    ticket = _ticket("Ticket 1")
    mastery = {ticket.ticket_id: TicketMasteryBreakdown(ticket_id=ticket.ticket_id, confidence_score=2.0)}
    score = ReadinessService().calculate([ticket], mastery)
    assert 0 <= score.percent <= 100
