from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from domain.answer_profile import AnswerProfileCode, TicketAnswerBlock


class AtomType(StrEnum):
    DEFINITION = "definition"
    EXAMPLES = "examples"
    FEATURES = "features"
    STAGES = "stages"
    FUNCTIONS = "functions"
    CAUSES = "causes"
    CONSEQUENCES = "consequences"
    CLASSIFICATION = "classification"
    PROCESS_STEP = "process_step"
    CONCLUSION = "conclusion"


class SkillCode(StrEnum):
    REPRODUCE_DEFINITION = "reproduce_definition"
    LIST_EXAMPLES = "list_examples"
    NAME_KEY_FEATURES = "name_key_features"
    RECONSTRUCT_PROCESS_ORDER = "reconstruct_process_order"
    EXPLAIN_CORE_LOGIC = "explain_core_logic"
    GIVE_SHORT_ORAL_ANSWER = "give_short_oral_answer"
    GIVE_FULL_ORAL_ANSWER = "give_full_oral_answer"
    ANSWER_FOLLOWUP_QUESTIONS = "answer_followup_questions"


class ExerciseType(StrEnum):
    ANSWER_SKELETON = "answer_skeleton"
    STRUCTURE_RECONSTRUCTION = "structure_reconstruction"
    ATOM_RECALL = "atom_recall"
    SEMANTIC_CLOZE = "semantic_cloze"
    ODD_THESIS = "odd_thesis"
    ORAL_SHORT = "oral_short"
    ORAL_FULL = "oral_full"
    EXAMINER_FOLLOWUP = "examiner_followup"
    WEAK_AREA_REPEAT = "weak_area_repeat"
    CROSS_TICKET_REPEAT = "cross_ticket_repeat"


class WeakAreaKind(StrEnum):
    ATOM = "weak_atom"
    SKILL = "weak_skill"
    CONCEPT = "weak_concept"
    SECTION = "weak_section"
    CROSS_TICKET_CONCEPT = "weak_cross_ticket_concept"
    ANSWER_BLOCK = "weak_answer_block"
    RUBRIC_CRITERION = "weak_rubric_criterion"


class ReviewMode(StrEnum):
    STANDARD_ADAPTIVE = "standard_adaptive"
    EXAM_CRUNCH = "exam_crunch"


@dataclass(slots=True)
class SourceDocument:
    document_id: str
    exam_id: str
    subject_id: str
    title: str
    file_path: str
    file_type: str
    size_bytes: int
    imported_at: datetime
    checksum: str = ""
    answer_profile_code: AnswerProfileCode = AnswerProfileCode.STANDARD_TICKET


@dataclass(slots=True)
class Exam:
    exam_id: str
    title: str
    description: str
    total_tickets: int
    subject_area: str


@dataclass(slots=True)
class Section:
    section_id: str
    exam_id: str
    title: str
    order_index: int
    description: str = ""


@dataclass(slots=True)
class KnowledgeAtom:
    atom_id: str
    type: AtomType
    label: str
    text: str
    keywords: list[str]
    weight: float
    dependencies: list[str] = field(default_factory=list)
    parent_atom_id: str | None = None
    confidence: float = 1.0
    source_excerpt: str = ""


@dataclass(slots=True)
class TicketSkill:
    skill_id: str
    code: SkillCode
    title: str
    description: str
    target_atom_ids: list[str]
    weight: float
    priority: int = 1


@dataclass(slots=True)
class ExerciseTemplate:
    template_id: str
    exercise_type: ExerciseType
    title: str
    instructions: str
    target_atom_ids: list[str]
    target_skill_codes: list[SkillCode]
    llm_required: bool = False
    rule_based_available: bool = True
    difficulty_delta: int = 0


@dataclass(slots=True)
class ScoringCriterion:
    criterion_id: str
    skill_code: SkillCode
    mastery_field: str
    description: str
    max_score: float
    weight: float


@dataclass(slots=True)
class ExaminerPrompt:
    prompt_id: str
    title: str
    text: str
    target_skill_codes: list[SkillCode]
    target_atom_ids: list[str]
    llm_assisted: bool = True


@dataclass(slots=True)
class CrossTicketLink:
    concept_id: str
    concept_label: str
    related_ticket_ids: list[str]
    rationale: str
    strength: float


@dataclass(slots=True)
class TicketKnowledgeMap:
    ticket_id: str
    exam_id: str
    section_id: str
    source_document_id: str
    title: str
    canonical_answer_summary: str
    atoms: list[KnowledgeAtom]
    skills: list[TicketSkill]
    exercise_templates: list[ExerciseTemplate]
    scoring_rubric: list[ScoringCriterion]
    examiner_prompts: list[ExaminerPrompt]
    cross_links_to_other_tickets: list[CrossTicketLink]
    difficulty: int
    estimated_oral_time_sec: int
    source_confidence: float = 1.0
    answer_profile_code: AnswerProfileCode = AnswerProfileCode.STANDARD_TICKET
    answer_blocks: list[TicketAnswerBlock] = field(default_factory=list)

    def validate(self) -> None:
        atom_ids = {atom.atom_id for atom in self.atoms}
        if not atom_ids:
            raise ValueError("TicketKnowledgeMap requires at least one atom.")

        for atom in self.atoms:
            if atom.weight <= 0:
                raise ValueError(f"Atom '{atom.atom_id}' must have positive weight.")
            if atom.parent_atom_id and atom.parent_atom_id not in atom_ids:
                raise ValueError(f"Atom '{atom.atom_id}' references missing parent atom.")
            for dependency in atom.dependencies:
                if dependency not in atom_ids:
                    raise ValueError(f"Atom '{atom.atom_id}' references missing dependency '{dependency}'.")

        for skill in self.skills:
            if not set(skill.target_atom_ids).issubset(atom_ids):
                raise ValueError(f"Skill '{skill.skill_id}' references missing atoms.")

        for template in self.exercise_templates:
            if not set(template.target_atom_ids).issubset(atom_ids):
                raise ValueError(f"Exercise template '{template.template_id}' references missing atoms.")

        if self.answer_profile_code is not AnswerProfileCode.STANDARD_TICKET:
            seen_codes = set()
            for block in self.answer_blocks:
                if block.block_code in seen_codes:
                    raise ValueError(f"Duplicate answer block '{block.block_code.value}'.")
                seen_codes.add(block.block_code)

    def atom_by_id(self, atom_id: str) -> KnowledgeAtom | None:
        return next((atom for atom in self.atoms if atom.atom_id == atom_id), None)

    @property
    def concept_ids(self) -> list[str]:
        return [link.concept_id for link in self.cross_links_to_other_tickets]


@dataclass(slots=True)
class CrossTicketConcept:
    concept_id: str
    label: str
    normalized_label: str
    description: str
    ticket_ids: list[str]
    atom_ids: list[str]
    strength: float
    confidence: float


@dataclass(slots=True)
class ExerciseInstance:
    exercise_id: str
    ticket_id: str
    template_id: str
    exercise_type: ExerciseType
    prompt_text: str
    expected_answer: str
    target_atom_ids: list[str]
    target_skill_codes: list[SkillCode]
    used_llm: bool = False
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class AttemptRecord:
    attempt_id: str
    exercise_id: str
    ticket_id: str
    user_answer: str
    score: float
    mastery_delta: float
    weak_atom_ids: list[str]
    weak_skill_codes: list[SkillCode]
    feedback: str
    used_llm: bool
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class WeakArea:
    weak_area_id: str
    user_id: str
    kind: WeakAreaKind
    reference_id: str
    title: str
    severity: float
    evidence: str
    related_ticket_ids: list[str] = field(default_factory=list)
    last_detected_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class TicketMasteryProfile:
    user_id: str
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
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None
    fsrs_state_json: str = ""
    attempts_count: int = 0


@dataclass(slots=True)
class SpacedReviewItem:
    review_item_id: str
    user_id: str
    ticket_id: str
    reference_type: str
    reference_id: str
    mode: ReviewMode
    priority: float
    due_at: datetime
    scheduled_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class StudySession:
    session_id: str
    user_id: str
    exam_id: str
    mode: ReviewMode
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
