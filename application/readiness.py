from __future__ import annotations

from application.ui_data import ReadinessScore, TicketMasteryBreakdown
from domain.knowledge import TicketKnowledgeMap


class ReadinessService:
    def calculate(
        self,
        tickets: list[TicketKnowledgeMap],
        mastery: dict[str, TicketMasteryBreakdown],
    ) -> ReadinessScore:
        if not tickets:
            return ReadinessScore(percent=0, tickets_total=0, tickets_practiced=0, weakest_area="")

        practiced = [
            t for t in tickets
            if t.ticket_id in mastery and mastery[t.ticket_id].confidence_score > 0
        ]

        if not practiced:
            return ReadinessScore(
                percent=0,
                tickets_total=len(tickets),
                tickets_practiced=0,
                weakest_area="",
            )

        avg_mastery = sum(mastery[t.ticket_id].confidence_score for t in practiced) / len(practiced)
        coverage = len(practiced) / len(tickets)
        percent = int(round(avg_mastery * coverage * 100))

        weakest = min(practiced, key=lambda t: mastery[t.ticket_id].confidence_score)
        weakest_area = weakest.title

        return ReadinessScore(
            percent=max(0, min(100, percent)),
            tickets_total=len(tickets),
            tickets_practiced=len(practiced),
            weakest_area=weakest_area,
        )
