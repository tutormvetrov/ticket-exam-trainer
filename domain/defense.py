from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ThesisSourceKind(str, Enum):
    THESIS = "thesis"
    NOTES = "notes"
    SLIDES = "slides"


class DefenseClaimKind(str, Enum):
    PROBLEM = "problem"
    RELEVANCE = "relevance"
    OBJECT = "object"
    SUBJECT = "subject"
    GOAL = "goal"
    TASKS = "tasks"
    METHODS = "methods"
    NOVELTY = "novelty"
    PRACTICAL_SIGNIFICANCE = "practical_significance"
    RESULTS = "results"
    LIMITATIONS = "limitations"
    PERSONAL_CONTRIBUTION = "personal_contribution"
    RISK_TOPIC = "risk_topic"


class DisciplineProfile(str, Enum):
    RESEARCH = "research"
    APPLIED = "applied"
    LEGAL_HUMANITIES = "legal_humanities"


class CommitteePersonaKind(str, Enum):
    SCIENTIFIC_ADVISOR = "scientific_advisor"
    OPPONENT = "opponent"
    COMMISSION = "commission"


class DefenseSessionMode(str, Enum):
    SPEECH_5 = "speech_5"
    SPEECH_7 = "speech_7"
    SPEECH_10 = "speech_10"
    PERSONA_QA = "persona_qa"
    FULL_MOCK_DEFENSE = "full_mock_defense"


@dataclass(slots=True)
class DlcLicenseState:
    install_id: str
    activated: bool = False
    license_tier: str = "locked"
    token: str = ""
    status: str = "locked"
    last_checked_at: datetime | None = None
    activated_at: datetime | None = None
    error_text: str = ""


@dataclass(slots=True)
class ThesisProject:
    project_id: str
    title: str
    degree: str
    specialty: str
    student_name: str
    supervisor_name: str
    defense_date: datetime | None
    discipline_profile: DisciplineProfile
    status: str
    created_at: datetime
    updated_at: datetime
    recommended_model: str = ""


@dataclass(slots=True)
class ThesisSource:
    source_id: str
    project_id: str
    kind: ThesisSourceKind
    title: str
    file_path: str
    file_type: str
    checksum: str
    version: int
    imported_at: datetime
    parse_status: str
    confidence: float
    raw_text: str
    normalized_text: str
    unit_count: int


@dataclass(slots=True)
class DefenseClaim:
    claim_id: str
    project_id: str
    kind: DefenseClaimKind
    text: str
    confidence: float
    source_anchors: list[str] = field(default_factory=list)
    llm_assisted: bool = False
    needs_review: bool = False
    updated_at: datetime | None = None


@dataclass(slots=True)
class DefenseOutlineSegment:
    segment_id: str
    project_id: str
    duration_label: str
    order_index: int
    title: str
    talking_points: str
    target_seconds: int


@dataclass(slots=True)
class SlideStoryboardCard:
    card_id: str
    project_id: str
    slide_index: int
    title: str
    purpose: str
    talking_points: list[str] = field(default_factory=list)
    evidence_links: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DefenseQuestion:
    question_id: str
    project_id: str
    persona: CommitteePersonaKind
    topic: str
    difficulty: int
    question_text: str
    source_anchors: list[str] = field(default_factory=list)
    risk_tag: str = ""
    created_at: datetime | None = None


@dataclass(slots=True)
class DefenseSession:
    session_id: str
    project_id: str
    mode: DefenseSessionMode
    duration_sec: int
    transcript_text: str
    questions: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass(slots=True)
class DefenseScoreProfile:
    project_id: str
    session_id: str
    structure_mastery: float
    relevance_clarity: float
    methodology_mastery: float
    novelty_mastery: float
    results_mastery: float
    limitations_honesty: float
    oral_clarity_text_mode: float
    followup_mastery: float
    summary_text: str
    created_at: datetime


@dataclass(slots=True)
class DefenseWeakArea:
    weak_area_id: str
    project_id: str
    kind: str
    title: str
    severity: float
    evidence: str
    claim_kind: DefenseClaimKind | None = None
    created_at: datetime | None = None
