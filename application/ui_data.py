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
    answer_profile_code: str = "standard_ticket"
    definition_mastery: float = 0.0
    structure_mastery: float = 0.0
    examples_mastery: float = 0.0
    feature_mastery: float = 0.0
    process_mastery: float = 0.0
    oral_short_mastery: float = 0.0
    oral_full_mastery: float = 0.0
    followup_mastery: float = 0.0
    confidence_score: float = 0.0
    intro_mastery: float = 0.0
    theory_mastery: float = 0.0
    practice_mastery: float = 0.0
    skills_mastery: float = 0.0
    conclusion_mastery: float = 0.0
    extra_mastery: float = 0.0
    state_exam_overall_score: float = 0.0


@dataclass(slots=True)
class StateExamStatisticsSnapshot:
    active: bool = False
    block_scores: dict[str, int] = field(default_factory=dict)
    criterion_scores: dict[str, int] = field(default_factory=dict)
    missing_blocks: dict[str, int] = field(default_factory=dict)


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
    document_id: str = ""
    document_title: str = ""
    status: str = ""
    answer_profile_code: str = "standard_ticket"
    answer_profile_label: str = "Обычный билет"
    tickets_created: int = 0
    sections_created: int = 0
    warnings: list[str] = field(default_factory=list)
    used_llm_assist: bool = False
    llm_done_tickets: int = 0
    llm_pending_tickets: int = 0
    llm_fallback_tickets: int = 0
    llm_failed_tickets: int = 0
    resume_available: bool = False
    error: str = ""


@dataclass(slots=True)
class TrainingEvaluationResult:
    ok: bool
    score_percent: int
    feedback: str
    weak_points: list[str]
    answer_profile_code: str = "standard_ticket"
    block_scores: dict[str, int] = field(default_factory=dict)
    criterion_scores: dict[str, int] = field(default_factory=dict)
    followup_questions: list[str] = field(default_factory=list)
    error: str = ""
    review: ReviewVerdict | None = None


@dataclass(slots=True)
class ThesisVerdict:
    thesis_label: str
    status: str  # "covered" | "partial" | "missing"
    comment: str
    student_excerpt: str


@dataclass(slots=True)
class ReviewVerdict:
    thesis_verdicts: list[ThesisVerdict]
    structure_notes: list[str]
    strengths: list[str]
    recommendations: list[str]
    overall_score: int
    overall_comment: str
