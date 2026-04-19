from __future__ import annotations

from dataclasses import dataclass, field

from domain.defense import (
    CommitteePersonaKind,
    DefenseClaim,
    DefenseGapFinding,
    DefenseQuestion,
    DefenseRepairTask,
    DefenseScoreProfile,
    DefenseWeakArea,
    DlcLicenseState,
    SlideStoryboardCard,
    ThesisProject,
    ThesisSource,
)


@dataclass(slots=True)
class DefenseProjectSummary:
    project_id: str
    title: str
    status: str
    source_count: int
    updated_label: str


@dataclass(slots=True)
class DefenseWorkspaceProject:
    project: ThesisProject
    sources: list[ThesisSource] = field(default_factory=list)
    claims: list[DefenseClaim] = field(default_factory=list)
    outlines: dict[str, list[tuple[str, str, int]]] = field(default_factory=dict)
    slides: list[SlideStoryboardCard] = field(default_factory=list)
    questions: list[DefenseQuestion] = field(default_factory=list)
    gap_findings: list[DefenseGapFinding] = field(default_factory=list)
    repair_tasks: list[DefenseRepairTask] = field(default_factory=list)
    latest_score: DefenseScoreProfile | None = None
    weak_areas: list[DefenseWeakArea] = field(default_factory=list)


@dataclass(slots=True)
class ModelRecommendation:
    model_name: str
    label: str
    rationale: str
    available: bool


@dataclass(slots=True)
class DefenseWorkspaceSnapshot:
    license_state: DlcLicenseState
    paywall_amount_label: str
    install_id: str
    recommendation: ModelRecommendation
    projects: list[DefenseProjectSummary] = field(default_factory=list)
    active_project: DefenseWorkspaceProject | None = None


@dataclass(slots=True)
class DefenseProcessingResult:
    ok: bool
    project_id: str = ""
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    llm_used: bool = False
    gap_findings_count: int = 0
    repair_tasks_count: int = 0
    error: str = ""


@dataclass(slots=True)
class DefenseEvaluationResult:
    ok: bool
    summary: str
    score_cards: dict[str, int]
    persona_kind: CommitteePersonaKind | None = None
    timer_verdict: str = ""
    weak_points: list[str] = field(default_factory=list)
    followup_questions: list[str] = field(default_factory=list)
    related_gap_ids: list[str] = field(default_factory=list)
    suggested_repair_tasks: list[str] = field(default_factory=list)
    error: str = ""
