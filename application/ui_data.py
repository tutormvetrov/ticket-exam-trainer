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
class DialogueTicketItem:
    ticket_id: str
    title: str
    section_title: str
    difficulty: int
    mastery_score: int = 0
    has_active_session: bool = False
    last_session_label: str = ""


@dataclass(slots=True)
class DialogueSessionSummary:
    session_id: str
    ticket_id: str
    ticket_title: str
    persona_kind: str
    status: str
    last_turn_index: int
    user_turn_count: int
    score_percent: int
    verdict: str
    summary: str
    started_label: str
    updated_label: str
    completed_label: str = ""
    resolved_model: str = ""


@dataclass(slots=True)
class DialogueTurn:
    turn_id: str
    turn_index: int
    speaker: str
    text: str
    weakness_focus: str = ""
    created_label: str = ""


@dataclass(slots=True)
class DialogueResult:
    ok: bool
    session_id: str
    ticket_id: str = ""
    persona_kind: str = "tutor"
    score_percent: int = 0
    feedback: str = ""
    weak_points: list[str] = field(default_factory=list)
    answer_profile_code: str = "standard_ticket"
    block_scores: dict[str, int] = field(default_factory=dict)
    criterion_scores: dict[str, int] = field(default_factory=dict)
    followup_questions: list[str] = field(default_factory=list)
    final_verdict: str = ""
    final_summary: str = ""
    review: ReviewVerdict | None = None
    error: str = ""


@dataclass(slots=True)
class DialogueSessionState:
    session: DialogueSessionSummary
    ticket: TicketKnowledgeMap
    turns: list[DialogueTurn] = field(default_factory=list)
    result: DialogueResult | None = None


@dataclass(slots=True)
class DialogueSnapshot:
    tickets: list[DialogueTicketItem] = field(default_factory=list)
    active_sessions: list[DialogueSessionSummary] = field(default_factory=list)
    recent_sessions: list[DialogueSessionSummary] = field(default_factory=list)
    active_session: DialogueSessionState | None = None
    readiness: ReadinessScore | None = None


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


@dataclass(slots=True)
class ReadinessScore:
    percent: int
    tickets_total: int
    tickets_practiced: int
    weakest_area: str
