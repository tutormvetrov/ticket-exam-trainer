from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import sqlite3

from application.adaptive_review import AdaptiveReviewService
from application.import_service import DocumentImportService
from application.scoring import MicroSkillScoringService
from application.settings import OllamaSettings
from application.settings_store import SettingsStore
from application.ui_data import ImportExecutionResult, StatisticsSnapshot, TicketMasteryBreakdown, TrainingEvaluationResult, TrainingSnapshot
from application.ui_query_service import UiQueryService
from domain.knowledge import Exam, ExerciseType, ReviewMode, Section, TicketMasteryProfile
from domain.models import DocumentData, SubjectData
from infrastructure.db import KnowledgeRepository
from infrastructure.importers.common import normalize_import_title
from infrastructure.ollama import OllamaService
from infrastructure.ollama.service import OllamaDiagnostics


@dataclass(slots=True)
class AppFacade:
    workspace_root: Path
    connection: sqlite3.Connection
    settings_store: SettingsStore
    repository: KnowledgeRepository = field(init=False)
    queries: UiQueryService = field(init=False)
    scoring: MicroSkillScoringService = field(init=False)
    adaptive: AdaptiveReviewService = field(init=False)
    _settings: OllamaSettings = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.repository = KnowledgeRepository(self.connection)
        self.queries = UiQueryService(self.connection)
        self.scoring = MicroSkillScoringService()
        self.adaptive = AdaptiveReviewService()
        self._settings = self.settings_store.load()

    @property
    def settings(self) -> OllamaSettings:
        return self._settings

    def save_settings(self, settings: OllamaSettings) -> None:
        self._settings = settings
        self.settings_store.save(settings)

    def build_ollama_service(self) -> OllamaService:
        return OllamaService(self._settings.base_url, float(self._settings.timeout_seconds))

    def inspect_ollama(self) -> OllamaDiagnostics:
        return self.build_ollama_service().inspect(self._settings.model)

    def load_documents(self) -> list[DocumentData]:
        return self.queries.load_documents()

    def load_subjects(self) -> list[SubjectData]:
        return self.queries.load_subjects()

    def load_sections_overview(self):
        return self.queries.load_sections_overview()

    def load_ticket_maps(self):
        return self.queries.load_ticket_maps()

    def load_profiles(self) -> dict[str, float]:
        return self.queries.load_profiles()

    def load_mastery_breakdowns(self) -> dict[str, TicketMasteryBreakdown]:
        return self.queries.load_mastery_breakdowns()

    def load_weak_areas(self):
        return self.queries.load_weak_areas()

    def load_statistics_snapshot(self) -> StatisticsSnapshot:
        return self.queries.load_statistics_snapshot()

    def load_training_snapshot(self) -> TrainingSnapshot:
        snapshot = self.queries.load_training_snapshot(limit=self._settings.training_queue_size)
        if snapshot.queue_items:
            return snapshot
        tickets = snapshot.tickets
        if not tickets:
            return snapshot
        queue = self.adaptive.build_queue(
            user_id="local-user",
            tickets=tickets,
            profiles=self._load_profiles(tickets),
            weak_areas=self._load_weak_areas(),
            mode=self._resolve_review_mode(),
        )
        self.repository.save_review_queue("local-user", queue)
        return self.queries.load_training_snapshot(limit=self._settings.training_queue_size)

    def import_document(self, path: str | Path) -> ImportExecutionResult:
        document_path = Path(path)
        stem_title = normalize_import_title(document_path.stem)
        exam = Exam(
            exam_id="local-exam",
            title="Локальная база билетов",
            description="Автоматически созданный контейнер для импортированных материалов.",
            total_tickets=0,
            subject_area="exam-training",
        )
        subject_slug = self._slug(stem_title) or "default-subject"
        service = DocumentImportService(
            ollama_service=self.build_ollama_service(),
            llm_model=self._settings.model,
            enable_llm_structuring=self._settings.import_llm_assist,
        )
        try:
            result = service.import_document(
                document_path,
                exam_id=exam.exam_id,
                subject_id=subject_slug,
                default_section_id="imported-section",
            )
        except Exception as exc:  # noqa: BLE001
            return ImportExecutionResult(False, error=str(exc))

        unique_sections: list[Section] = []
        seen: set[str] = set()
        for index, ticket in enumerate(result.tickets, start=1):
            if ticket.section_id in seen:
                continue
            seen.add(ticket.section_id)
            section_title = ticket.section_id.replace("-", " ").title()
            if ticket.section_id in {"imported-section", "default-section"} or section_title == "Imported Section":
                section_title = "Основной раздел"
            unique_sections.append(
                Section(
                    section_id=ticket.section_id,
                    exam_id=exam.exam_id,
                    title=section_title,
                    order_index=index,
                    description="Раздел, выделенный при импорте документа",
                )
            )

        exam.total_tickets = len(result.tickets)
        self.repository.save_import_result(result, exam, unique_sections)
        self._refresh_review_queue()
        return ImportExecutionResult(
            ok=True,
            document_title=result.source_document.title,
            tickets_created=len(result.tickets),
            sections_created=len(unique_sections),
            warnings=result.warnings,
            used_llm_assist=result.used_llm_assist,
        )

    def evaluate_answer(self, ticket_id: str, mode_key: str, answer_text: str) -> TrainingEvaluationResult:
        answer = answer_text.strip()
        if not answer:
            return TrainingEvaluationResult(False, 0, "", [], error="Ответ пуст. Введите текст ответа перед проверкой.")

        ticket = self.queries.load_ticket_map(ticket_id)
        exercise = self._pick_exercise(ticket, mode_key)
        profile = self._load_profile(ticket_id)
        outcome = self.scoring.evaluate(ticket, exercise, answer, profile=profile)
        outcome.profile.next_review_at = datetime.now()
        self.repository.save_exercise_instances([exercise])
        self.repository.save_attempt(outcome.attempt)
        self.repository.save_mastery_profile(outcome.profile)
        self.repository.save_weak_areas("local-user", ticket_id, outcome.weak_areas)
        self._refresh_review_queue()

        followups: list[str] = []
        if self._settings.examiner_followups:
            weak_titles = [area.title for area in outcome.weak_areas[:2]]
            if weak_titles:
                llm_result = self.build_ollama_service().generate_followup_questions(
                    ticket.title,
                    ticket.canonical_answer_summary,
                    weak_titles,
                    self._settings.model,
                    count=2,
                )
                if llm_result.ok and llm_result.content:
                    followups = [line.removeprefix("- ").strip() for line in llm_result.content.splitlines() if line.strip()]

        return TrainingEvaluationResult(
            ok=True,
            score_percent=int(round(outcome.attempt.score * 100)),
            feedback=outcome.attempt.feedback,
            weak_points=[area.title for area in outcome.weak_areas[:4]],
            followup_questions=followups,
        )

    def _pick_exercise(self, ticket, mode_key: str):
        type_map = {
            "reading": ExerciseType.ANSWER_SKELETON,
            "active-recall": ExerciseType.ATOM_RECALL,
            "cloze": ExerciseType.SEMANTIC_CLOZE,
            "matching": ExerciseType.ODD_THESIS,
            "plan": ExerciseType.STRUCTURE_RECONSTRUCTION,
            "mini-exam": ExerciseType.ORAL_FULL,
        }
        target_type = type_map.get(mode_key, ExerciseType.ATOM_RECALL)
        for template in ticket.exercise_templates:
            if template.exercise_type is target_type:
                from application.exercise_generation import ExerciseGenerator

                for instance in ExerciseGenerator().generate(ticket):
                    if instance.template_id == template.template_id:
                        return instance
        from application.exercise_generation import ExerciseGenerator

        return ExerciseGenerator().generate(ticket)[0]

    def _load_profile(self, ticket_id: str) -> TicketMasteryProfile | None:
        row = self.connection.execute(
            "SELECT * FROM ticket_mastery_profiles WHERE user_id = ? AND ticket_id = ?",
            ("local-user", ticket_id),
        ).fetchone()
        if row is None:
            return None
        return TicketMasteryProfile(
            user_id=row["user_id"],
            ticket_id=row["ticket_id"],
            definition_mastery=float(row["definition_mastery"]),
            structure_mastery=float(row["structure_mastery"]),
            examples_mastery=float(row["examples_mastery"]),
            feature_mastery=float(row["feature_mastery"]),
            process_mastery=float(row["process_mastery"]),
            oral_short_mastery=float(row["oral_short_mastery"]),
            oral_full_mastery=float(row["oral_full_mastery"]),
            followup_mastery=float(row["followup_mastery"]),
            confidence_score=float(row["confidence_score"]),
            last_reviewed_at=datetime.fromisoformat(row["last_reviewed_at"]) if row["last_reviewed_at"] else None,
            next_review_at=datetime.fromisoformat(row["next_review_at"]) if row["next_review_at"] else None,
        )

    def _load_profiles(self, tickets) -> list[TicketMasteryProfile]:
        profiles: list[TicketMasteryProfile] = []
        for ticket in tickets:
            profile = self._load_profile(ticket.ticket_id)
            if profile:
                profiles.append(profile)
        return profiles

    def _load_weak_areas(self):
        from domain.knowledge import WeakArea, WeakAreaKind

        rows = self.queries.load_weak_areas()
        weak_areas = []
        for row in rows:
            weak_areas.append(
                WeakArea(
                    weak_area_id=row["weak_area_id"],
                    user_id=row["user_id"],
                    kind=WeakAreaKind(row["kind"]),
                    reference_id=row["reference_id"],
                    title=row["title"],
                    severity=float(row["severity"]),
                    evidence=row["evidence"],
                    related_ticket_ids=json_load(row["related_ticket_ids_json"]),
                    last_detected_at=datetime.fromisoformat(row["last_detected_at"]),
                )
            )
        return weak_areas

    def _refresh_review_queue(self) -> None:
        tickets = self.queries.load_ticket_maps()
        queue = self.adaptive.build_queue(
            user_id="local-user",
            tickets=tickets,
            profiles=self._load_profiles(tickets),
            weak_areas=self._load_weak_areas(),
            mode=self._resolve_review_mode(),
        )
        self.repository.save_review_queue("local-user", queue)

    def _resolve_review_mode(self) -> ReviewMode:
        try:
            return ReviewMode(self._settings.review_mode)
        except ValueError:
            return ReviewMode.STANDARD_ADAPTIVE

    @staticmethod
    def _slug(value: str) -> str:
        import re

        value = value.lower()
        value = re.sub(r"[^a-zа-яё0-9]+", "-", value, flags=re.IGNORECASE)
        value = re.sub(r"-{2,}", "-", value).strip("-")
        return value or "default"


def json_load(raw_value: str | None) -> list[str]:
    import json

    if not raw_value:
        return []
    return list(json.loads(raw_value))
