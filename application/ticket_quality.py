"""Эвристика качества «эталонного скелета плана» для билета.

У некоторых билетов seed-pipeline построил слишком короткий или пустой
эталонный план — `plan`-режим тогда работает плохо (сравниваться не с чем).

Эта эвристика помечает такие билеты заранее, чтобы UI мог предупредить:
в Tickets — мягкой иконкой 🔶, в plan-workspace — полосой-warning.

Полного фикса seed-данных эта эвристика не заменяет — это только honest
signal пользователю. Полный фикс — отдельная сессия через пересмотр
конспект → план pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from domain.knowledge import TicketKnowledgeMap


MIN_BLOCK_COUNT = 4
MIN_AVG_WORDS_PER_BLOCK = 15
_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class TicketQualityVerdict:
    plan_skeleton_weak: bool
    reason: str                    # "too_few_blocks" | "short_blocks" | "missing_blocks" | "ok"


def assess_ticket(ticket: TicketKnowledgeMap) -> TicketQualityVerdict:
    blocks = list(getattr(ticket, "answer_blocks", None) or [])
    usable = [b for b in blocks if not getattr(b, "is_missing", False)]
    if len(usable) < MIN_BLOCK_COUNT:
        return TicketQualityVerdict(
            plan_skeleton_weak=True,
            reason="too_few_blocks" if blocks else "missing_blocks",
        )
    total_words = sum(_count_words(b.expected_content) for b in usable)
    avg = total_words / max(1, len(usable))
    if avg < MIN_AVG_WORDS_PER_BLOCK:
        return TicketQualityVerdict(plan_skeleton_weak=True, reason="short_blocks")
    return TicketQualityVerdict(plan_skeleton_weak=False, reason="ok")


class TicketQualityCache:
    """In-memory кеш эвристики по ticket_id.

    Рассчитывается один раз при первом доступе (ленивая инициализация из
    полного списка TicketKnowledgeMap) или по одному билету.
    """

    def __init__(self) -> None:
        self._verdicts: dict[str, TicketQualityVerdict] = {}

    def prime(self, tickets: list[TicketKnowledgeMap]) -> None:
        for ticket in tickets:
            self._verdicts[ticket.ticket_id] = assess_ticket(ticket)

    def verdict_for(self, ticket: TicketKnowledgeMap | None) -> TicketQualityVerdict:
        if ticket is None:
            return TicketQualityVerdict(plan_skeleton_weak=False, reason="ok")
        cached = self._verdicts.get(ticket.ticket_id)
        if cached is not None:
            return cached
        verdict = assess_ticket(ticket)
        self._verdicts[ticket.ticket_id] = verdict
        return verdict

    def is_weak(self, ticket_id: str) -> bool:
        """Быстрая проверка без TicketKnowledgeMap — True если уже в кеше weak."""
        cached = self._verdicts.get(ticket_id)
        return bool(cached and cached.plan_skeleton_weak)


def _count_words(text: str | None) -> int:
    if not text:
        return 0
    return len([token for token in text.split() if token.strip()])
