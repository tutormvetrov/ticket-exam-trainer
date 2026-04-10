from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AnswerProfileCode(StrEnum):
    STANDARD_TICKET = "standard_ticket"
    STATE_EXAM_PUBLIC_ADMIN = "state_exam_public_admin"


class AnswerBlockCode(StrEnum):
    INTRO = "intro"
    THEORY = "theory"
    PRACTICE = "practice"
    SKILLS = "skills"
    CONCLUSION = "conclusion"
    EXTRA = "extra"


class AnswerCriterionCode(StrEnum):
    COMPLETENESS = "completeness"
    DEPTH = "depth"
    STRUCTURE = "structure"
    PRACTICAL = "practical"
    ORIGINALITY = "originality"
    COMPETENCE = "competence"


@dataclass(frozen=True, slots=True)
class AnswerCriterionSpec:
    code: AnswerCriterionCode
    title: str
    description: str
    weight: float


@dataclass(frozen=True, slots=True)
class AnswerBlockSpec:
    code: AnswerBlockCode
    title: str
    description: str
    weight: float
    keywords: list[str] = field(default_factory=list)
    training_hint: str = ""
    followup_hint: str = ""


@dataclass(frozen=True, slots=True)
class AnswerProfileSpec:
    code: AnswerProfileCode
    title: str
    description: str
    blocks: list[AnswerBlockSpec]
    criteria: list[AnswerCriterionSpec]
    followup_templates: dict[AnswerBlockCode, list[str]] = field(default_factory=dict)
    mode_hints: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class TicketAnswerBlock:
    block_code: AnswerBlockCode
    title: str
    expected_content: str
    source_excerpt: str
    confidence: float
    llm_assisted: bool = False
    is_missing: bool = False


@dataclass(slots=True)
class AttemptBlockScore:
    attempt_id: str
    block_code: AnswerBlockCode
    coverage_score: float
    criterion_scores: dict[AnswerCriterionCode, float]
    feedback: str


@dataclass(slots=True)
class TicketBlockMasteryProfile:
    user_id: str
    ticket_id: str
    intro_mastery: float = 0.0
    theory_mastery: float = 0.0
    practice_mastery: float = 0.0
    skills_mastery: float = 0.0
    conclusion_mastery: float = 0.0
    extra_mastery: float = 0.0
    overall_score: float = 0.0
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None
