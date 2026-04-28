"""Resolve the first useful training step for the active course."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ui_flet.state import AppState

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FirstTrainingStep:
    route: str
    ticket_id: str = ""
    ticket_title: str = ""
    source: str = "catalog"

    @property
    def has_ticket(self) -> bool:
        return bool(self.ticket_id)


def resolve_first_training_step(state: AppState, *, exam_id: str | None = None) -> FirstTrainingStep:
    """Pick the next concrete ticket route for a course.

    Priority:
    1. First item from the adaptive queue for the course.
    2. First ticket from the course catalog.
    3. Catalog route when no ticket is available.
    """
    resolved_exam_id = exam_id or state.active_exam_id
    try:
        snapshot = state.facade.load_training_snapshot(exam_id=resolved_exam_id)
        for item in list(getattr(snapshot, "queue_items", []) or []):
            ticket_id = str(getattr(item, "ticket_id", "") or "").strip()
            if ticket_id:
                title = str(getattr(item, "ticket_title", "") or "").strip()
                return FirstTrainingStep(
                    route=f"/training/{ticket_id}/reading",
                    ticket_id=ticket_id,
                    ticket_title=title or ticket_id,
                    source="queue",
                )

        tickets = list(getattr(snapshot, "tickets", []) or [])
        if not tickets:
            tickets = list(state.facade.load_ticket_maps(exam_id=resolved_exam_id))
        for ticket in tickets:
            ticket_id = str(getattr(ticket, "ticket_id", "") or "").strip()
            if ticket_id:
                title = str(getattr(ticket, "title", "") or "").strip()
                return FirstTrainingStep(
                    route=f"/training/{ticket_id}/reading",
                    ticket_id=ticket_id,
                    ticket_title=title or ticket_id,
                    source="ticket",
                )
    except Exception:
        _LOG.exception("Failed to resolve first training step exam_id=%s", resolved_exam_id)
    return FirstTrainingStep(route="/tickets")


def go_to_first_training_step(state: AppState, *, exam_id: str | None = None) -> None:
    state.go(resolve_first_training_step(state, exam_id=exam_id).route)
