from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from domain.knowledge import ReviewMode, SpacedReviewItem, TicketKnowledgeMap, TicketMasteryProfile, WeakArea, WeakAreaKind


class AdaptiveReviewService:
    def build_queue(
        self,
        user_id: str,
        tickets: list[TicketKnowledgeMap],
        profiles: list[TicketMasteryProfile],
        weak_areas: list[WeakArea],
        mode: ReviewMode = ReviewMode.STANDARD_ADAPTIVE,
        now: datetime | None = None,
    ) -> list[SpacedReviewItem]:
        current_time = now or datetime.now()
        profile_map = {profile.ticket_id: profile for profile in profiles}
        weakness_map: dict[str, list[WeakArea]] = {}
        for weak_area in weak_areas:
            for ticket_id in weak_area.related_ticket_ids:
                weakness_map.setdefault(ticket_id, []).append(weak_area)

        queue: list[SpacedReviewItem] = []
        for ticket in tickets:
            profile = profile_map.get(ticket.ticket_id) or TicketMasteryProfile(user_id=user_id, ticket_id=ticket.ticket_id)
            related_weaknesses = weakness_map.get(ticket.ticket_id, [])
            priority = self._compute_priority(ticket, profile, related_weaknesses, mode)
            due_at = current_time + timedelta(hours=self._compute_due_hours(profile, priority, mode))
            queue.append(
                SpacedReviewItem(
                    review_item_id=f"review-{uuid4().hex[:12]}",
                    user_id=user_id,
                    ticket_id=ticket.ticket_id,
                    reference_type="ticket",
                    reference_id=ticket.ticket_id,
                    mode=mode,
                    priority=priority,
                    due_at=due_at,
                    scheduled_at=current_time,
                )
            )

            for weak_area in related_weaknesses:
                if weak_area.kind not in {WeakAreaKind.CONCEPT, WeakAreaKind.CROSS_TICKET_CONCEPT}:
                    continue
                queue.append(
                    SpacedReviewItem(
                        review_item_id=f"review-{uuid4().hex[:12]}",
                        user_id=user_id,
                        ticket_id=ticket.ticket_id,
                        reference_type=weak_area.kind.value,
                        reference_id=weak_area.reference_id,
                        mode=mode,
                        priority=round(min(1.5, priority + weak_area.severity * 0.2), 4),
                        due_at=current_time + timedelta(hours=max(1, self._compute_due_hours(profile, priority, mode) // 2)),
                        scheduled_at=current_time,
                    )
                )

        queue.sort(key=lambda item: (-item.priority, item.due_at))
        return queue

    @staticmethod
    def _compute_priority(
        ticket: TicketKnowledgeMap,
        profile: TicketMasteryProfile,
        weak_areas: list[WeakArea],
        mode: ReviewMode,
    ) -> float:
        average_mastery = profile.confidence_score or 0.0
        oral_gap = 1.0 - ((profile.oral_short_mastery + profile.oral_full_mastery + profile.followup_mastery) / 3)
        weakness_penalty = max((weak_area.severity for weak_area in weak_areas), default=0.0)
        difficulty_factor = ticket.difficulty / 5
        mode_bonus = 0.15 if mode is ReviewMode.EXAM_CRUNCH else 0.0
        priority = (1.0 - average_mastery) * 0.45 + oral_gap * 0.3 + difficulty_factor * 0.15 + weakness_penalty * 0.25 + mode_bonus
        return round(min(1.5, max(0.1, priority)), 4)

    @staticmethod
    def _compute_due_hours(profile: TicketMasteryProfile, priority: float, mode: ReviewMode) -> int:
        mastery = max(0.1, profile.confidence_score or 0.0)
        if mode is ReviewMode.EXAM_CRUNCH:
            base_hours = 18 * mastery
        else:
            base_hours = 72 * mastery
        due_hours = int(max(1, base_hours / max(priority, 0.25)))
        return due_hours
