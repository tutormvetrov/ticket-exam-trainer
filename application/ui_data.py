from __future__ import annotations

from dataclasses import dataclass, field

from domain.knowledge import TicketKnowledgeMap
from domain.models import SessionData


@dataclass(slots=True)
class SectionOverviewItem:
    title: str
    subject: str
    tickets: int


@dataclass(slots=True)
class StatisticsSnapshot:
    average_score: int
    processed_tickets: int
    weak_areas: int
    sessions_week: int
    recent_sessions: list[SessionData] = field(default_factory=list)


@dataclass(slots=True)
class TicketMasteryBreakdown:
    ticket_id: str
    definition_mastery: float = 0.0
    structure_mastery: float = 0.0
    examples_mastery: float = 0.0
    feature_mastery: float = 0.0
    process_mastery: float = 0.0
    oral_short_mastery: float = 0.0
    oral_full_mastery: float = 0.0
    followup_mastery: float = 0.0
    confidence_score: float = 0.0


@dataclass(slots=True)
class TrainingQueueItem:
    ticket_id: str
    ticket_title: str
    reference_type: str
    reference_id: str
    priority: float
    due_label: str


@dataclass(slots=True)
class TrainingSnapshot:
    queue_items: list[TrainingQueueItem] = field(default_factory=list)
    tickets: list[TicketKnowledgeMap] = field(default_factory=list)


@dataclass(slots=True)
class ImportExecutionResult:
    ok: bool
    document_title: str = ""
    tickets_created: int = 0
    sections_created: int = 0
    warnings: list[str] = field(default_factory=list)
    used_llm_assist: bool = False
    error: str = ""


@dataclass(slots=True)
class TrainingEvaluationResult:
    ok: bool
    score_percent: int
    feedback: str
    weak_points: list[str]
    followup_questions: list[str] = field(default_factory=list)
    error: str = ""
