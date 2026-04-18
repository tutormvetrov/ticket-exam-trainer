from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import TypeVar
from uuid import uuid4

from application.adaptive_review import AdaptiveReviewService
from application.answer_profile_registry import answer_profile_label, get_answer_profile
from application.readiness import ReadinessService
from application.defense_service import DefenseService
from application.defense_ui_data import DefenseEvaluationResult, DefenseProcessingResult, DefenseWorkspaceSnapshot
from application.import_service import DocumentImportService, TicketCandidate
from application.scoring import MicroSkillScoringService
from application.settings import OllamaSettings
from application.settings_store import SettingsStore
from application.ui_data import (
    DialogueResult,
    DialogueSessionState,
    DialogueSnapshot,
    ImportExecutionResult,
    StateExamStatisticsSnapshot,
    StatisticsSnapshot,
    TicketMasteryBreakdown,
    TrainingEvaluationResult,
    TrainingSnapshot,
)
from application.ui_query_service import UiQueryService
from domain.answer_profile import AnswerProfileCode, TicketBlockMasteryProfile
from domain.knowledge import Exam, ExerciseType, ReviewMode, Section, TicketMasteryProfile
from domain.models import DocumentData, SubjectData
from infrastructure.db import DefenseRepository, DialogueRepository, KnowledgeRepository
from infrastructure.db.transaction import atomic
from infrastructure.importers.common import normalize_import_title
from infrastructure.ollama import OllamaService
from infrastructure.ollama.dialogue import DialogueTranscriptLine, DialogueTurnContext, DialogueTurnResult
from infrastructure.ollama.service import OllamaDiagnostics


_USE_SETTINGS_TIMEOUT = object()
_T = TypeVar("_T")


@dataclass(slots=True)
class AppFacade:
    workspace_root: Path
    connection: sqlite3.Connection
    settings_store: SettingsStore
    repository: KnowledgeRepository = field(init=False)
    dialogue_repository: DialogueRepository = field(init=False)
    defense_repository: DefenseRepository = field(init=False)
    defense: DefenseService = field(init=False)
    queries: UiQueryService = field(init=False)
    scoring: MicroSkillScoringService = field(init=False)
    adaptive: AdaptiveReviewService = field(init=False)
    _settings: OllamaSettings = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.repository = KnowledgeRepository(self.connection)
        self.dialogue_repository = DialogueRepository(self.connection)
        self.defense_repository = DefenseRepository(self.connection)
        self.queries = UiQueryService(self.connection)
        self.scoring = MicroSkillScoringService()
        self.adaptive = AdaptiveReviewService()
        self._settings = self.settings_store.load()
        self.defense = DefenseService(self.workspace_root, self.defense_repository, self.settings_store)

    @property
    def settings(self) -> OllamaSettings:
        return self._settings

    def save_settings(self, settings: OllamaSettings) -> None:
        self._settings = settings
        self.settings_store.save(settings)

    def build_ollama_service(self, timeout_seconds: float | None = None) -> OllamaService:
        # Раздельные таймауты: короткий на диагностику (tags/ping), длинный на
        # генерацию. Override `timeout_seconds` по-прежнему уважается: он
        # применяется только к генерации, inspect остаётся быстрым.
        resolved_generation = float(
            self._settings.timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        return OllamaService(
            self._settings.base_url,
            models_path=self._settings.models_path,
            inspect_timeout_seconds=3.0,
            generation_timeout_seconds=resolved_generation,
        )

    def build_import_ollama_service(self, generation_timeout_seconds: float | None | object = _USE_SETTINGS_TIMEOUT) -> OllamaService:
        resolved_generation = (
            float(self._settings.timeout_seconds)
            if generation_timeout_seconds is _USE_SETTINGS_TIMEOUT
            else generation_timeout_seconds
        )
        return OllamaService(
            self._settings.base_url,
            models_path=self._settings.models_path,
            inspect_timeout_seconds=3.0,
            generation_timeout_seconds=resolved_generation,
        )

    @staticmethod
    def _recommended_import_part_count(ticket_total: int) -> int:
        if ticket_total >= 192:
            return 6
        if ticket_total >= 144:
            return 5
        if ticket_total >= 96:
            return 4
        return 1

    @classmethod
    def _partition_import_items(cls, items: list[_T]) -> list[list[_T]]:
        if not items:
            return []
        parts = cls._recommended_import_part_count(len(items))
        if parts <= 1:
            return [items[:]]
        batch_size = max(1, (len(items) + parts - 1) // parts)
        return [items[index:index + batch_size] for index in range(0, len(items), batch_size)]

    @staticmethod
    def _import_progress_counts(result: ImportExecutionResult) -> tuple[int, int, int, int]:
        return (
            result.llm_done_tickets,
            result.llm_pending_tickets,
            result.llm_fallback_tickets,
            result.llm_failed_tickets,
        )

    def complete_import_with_progress(
        self,
        path: str | Path,
        answer_profile_code: str | AnswerProfileCode = AnswerProfileCode.STANDARD_TICKET,
        progress_callback=None,
        *,
        max_resume_passes: int = 8,
        generation_timeout_seconds: float | None | object = _USE_SETTINGS_TIMEOUT,
        parallel_workers: int = 1,
    ) -> ImportExecutionResult:
        result = self.import_document_with_progress(
            path,
            answer_profile_code=answer_profile_code,
            progress_callback=progress_callback,
            generation_timeout_seconds=generation_timeout_seconds,
        )
        previous_counts = self._import_progress_counts(result)
        attempts = 0
        while result.resume_available and attempts < max(0, max_resume_passes):
            attempts += 1
            result = self.resume_document_import_with_progress(
                result.document_id,
                progress_callback=progress_callback,
                generation_timeout_seconds=generation_timeout_seconds,
                parallel_workers=parallel_workers,
            )
            current_counts = self._import_progress_counts(result)
            if current_counts == previous_counts:
                break
            previous_counts = current_counts
        return result

    def complete_resume_document_import_with_progress(
        self,
        document_id: str,
        progress_callback=None,
        *,
        max_resume_passes: int = 8,
        generation_timeout_seconds: float | None | object = _USE_SETTINGS_TIMEOUT,
        parallel_workers: int = 1,
    ) -> ImportExecutionResult:
        result = self.resume_document_import_with_progress(
            document_id,
            progress_callback=progress_callback,
            generation_timeout_seconds=generation_timeout_seconds,
            parallel_workers=parallel_workers,
        )
        previous_counts = self._import_progress_counts(result)
        attempts = 1
        while result.resume_available and attempts < max(1, max_resume_passes):
            attempts += 1
            result = self.resume_document_import_with_progress(
                document_id,
                progress_callback=progress_callback,
                generation_timeout_seconds=generation_timeout_seconds,
                parallel_workers=parallel_workers,
            )
            current_counts = self._import_progress_counts(result)
            if current_counts == previous_counts:
                break
            previous_counts = current_counts
        return result

    def inspect_ollama(self) -> OllamaDiagnostics:
        return self.build_ollama_service().inspect(self._settings.model)

    def load_defense_workspace_snapshot(self, project_id: str | None = None) -> DefenseWorkspaceSnapshot:
        return self.defense.load_workspace_snapshot(project_id)

    def activate_defense_dlc(self, activation_code: str):
        return self.defense.activate_dlc(activation_code)

    def create_defense_project(self, payload: dict[str, str]):
        return self.defense.create_project(**payload)

    def import_defense_materials_with_progress(
        self,
        project_id: str,
        paths: list[str | Path],
        progress_callback=None,
    ) -> DefenseProcessingResult:
        return self.defense.import_project_materials(project_id, paths, progress_callback=progress_callback)

    def evaluate_defense_mock(self, project_id: str, mode_key: str, answer_text: str) -> DefenseEvaluationResult:
        return self.defense.evaluate_mock_defense(project_id, mode_key, "commission", 0, answer_text)

    def evaluate_defense_mock_with_context(
        self,
        project_id: str,
        mode_key: str,
        persona_kind: str,
        timer_profile_sec: int,
        answer_text: str,
    ) -> DefenseEvaluationResult:
        return self.defense.evaluate_mock_defense(project_id, mode_key, persona_kind, timer_profile_sec, answer_text)

    def update_defense_gap_status(self, project_id: str, finding_id: str, status: str) -> None:
        self.defense.update_gap_status(project_id, finding_id, status)

    def update_defense_repair_task_status(self, project_id: str, task_id: str, status: str) -> None:
        self.defense.update_repair_task_status(project_id, task_id, status)

    def load_documents(self) -> list[DocumentData]:
        return self.queries.load_documents()

    def delete_document(self, document_id: str) -> bool:
        """Полное удаление импортированного документа.

        Делегирует атомарное удаление репозиторию (FK-каскад + ручная чистка
        ``weak_areas`` и orphan ``cross_ticket_concepts``) и после успешного
        удаления перестраивает adaptive queue, чтобы Training/Statistics не
        ссылались на исчезнувшие билеты.
        """
        deleted = self.repository.delete_document(document_id)
        if deleted:
            self._refresh_review_queue()
        return deleted

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

    def load_state_exam_statistics(self) -> StateExamStatisticsSnapshot:
        return self.queries.load_state_exam_statistics()

    def load_latest_import_result(self) -> ImportExecutionResult:
        return self.queries.load_latest_import_result()

    def load_dialogue_snapshot(
        self,
        *,
        tickets: list | None = None,
        mastery: dict[str, TicketMasteryBreakdown] | None = None,
    ) -> DialogueSnapshot:
        snapshot = self.queries.load_dialogue_snapshot()
        snapshot.readiness = self.load_readiness_score(
            tickets=tickets if tickets is not None else self.load_ticket_maps(),
            mastery=mastery if mastery is not None else self.load_mastery_breakdowns(),
        )
        return snapshot

    def load_dialogue_session(self, session_id: str) -> DialogueSessionState:
        return self.queries.load_dialogue_session(session_id)

    def start_dialogue_session(
        self,
        ticket_id: str,
        persona_kind: str = "tutor",
        *,
        seed_focus: str | None = None,
    ) -> DialogueSessionState:
        persona = self._normalize_dialogue_persona(persona_kind)
        active_row = self.dialogue_repository.load_active_session_for_ticket("local-user", ticket_id, persona)
        if active_row is not None:
            return self.load_dialogue_session(active_row["session_id"])

        ticket = self.queries.load_ticket_map(ticket_id)
        now = datetime.now().isoformat()
        session_id = f"dialogue-{uuid4().hex[:12]}"
        with self.connection:
            self.dialogue_repository.create_session(
                session_id=session_id,
                user_id="local-user",
                ticket_id=ticket_id,
                persona_kind=persona,
                resolved_model=self._settings.model,
                started_at=now,
                updated_at=now,
                commit=False,
            )

        opening = self._generate_dialogue_turn(ticket, session_id, persona, [], opening=True, seed_focus=seed_focus)
        assistant_text = self._dialogue_message_text(opening.payload.feedback_text, opening.payload.next_question)
        if not assistant_text:
            assistant_text = self._dialogue_opening_fallback(ticket, persona)
        with self.connection:
            self.dialogue_repository.append_turn(
                turn_id=f"turn-{uuid4().hex[:12]}",
                session_id=session_id,
                turn_index=1,
                speaker="assistant",
                text=assistant_text,
                weakness_focus=opening.payload.weakness_focus if opening.ok else "",
                created_at=now,
                commit=False,
            )
            self.dialogue_repository.update_session_progress(
                session_id=session_id,
                last_turn_index=1,
                user_turn_count=0,
                updated_at=now,
                commit=False,
            )
        return self.load_dialogue_session(session_id)

    def submit_dialogue_turn(
        self,
        session_id: str,
        user_text: str,
        *,
        expected_last_turn_index: int | None = None,
    ) -> DialogueSessionState:
        user_answer = user_text.strip()
        if not user_answer:
            return self.load_dialogue_session(session_id)

        session = self.load_dialogue_session(session_id)
        if session.session.status != "active":
            return session
        if expected_last_turn_index is not None and session.session.last_turn_index != expected_last_turn_index:
            return session
        if session.session.user_turn_count >= 5:
            result = self.complete_dialogue_session(session_id)
            if session.result is None:
                session.result = result
            return session

        user_turn_index = session.session.last_turn_index + 1
        now = datetime.now().isoformat()
        with self.connection:
            self.dialogue_repository.append_turn(
                turn_id=f"turn-{uuid4().hex[:12]}",
                session_id=session_id,
                turn_index=user_turn_index,
                speaker="user",
                text=user_answer,
                weakness_focus="",
                created_at=now,
                commit=False,
            )
            self.dialogue_repository.update_session_progress(
                session_id=session_id,
                last_turn_index=user_turn_index,
                user_turn_count=session.session.user_turn_count + 1,
                updated_at=now,
                commit=False,
            )

        session = self.load_dialogue_session(session_id)
        turn_result = self._generate_dialogue_turn(
            session.ticket,
            session.session.session_id,
            session.session.persona_kind,
            session.turns,
            opening=False,
        )
        assistant_text = self._dialogue_message_text(turn_result.payload.feedback_text, turn_result.payload.next_question)
        if not assistant_text:
            assistant_text = self._dialogue_followup_fallback(session)
        turn_now = datetime.now().isoformat()
        final_turn_index = session.session.last_turn_index + 1
        with self.connection:
            self.dialogue_repository.append_turn(
                turn_id=f"turn-{uuid4().hex[:12]}",
                session_id=session_id,
                turn_index=final_turn_index,
                speaker="assistant",
                text=assistant_text,
                weakness_focus=turn_result.payload.weakness_focus if turn_result.ok else "",
                created_at=turn_now,
                commit=False,
            )
            self.dialogue_repository.update_session_progress(
                session_id=session_id,
                last_turn_index=final_turn_index,
                user_turn_count=session.session.user_turn_count,
                updated_at=turn_now,
                commit=False,
            )

        if turn_result.payload.should_finish or session.session.user_turn_count >= 5:
            result = self.complete_dialogue_session(session_id)
            refreshed = self.load_dialogue_session(session_id)
            refreshed.result = result
            return refreshed
        return self.load_dialogue_session(session_id)

    def complete_dialogue_session(self, session_id: str) -> DialogueResult:
        session = self.load_dialogue_session(session_id)
        if session.session.status == "completed" and session.result is not None:
            return session.result
        if session.session.status == "completed":
            return self._dialogue_result_from_session(session, ok=True)

        user_answer = "\n\n".join(turn.text for turn in session.turns if turn.speaker == "user").strip()
        if not user_answer:
            return DialogueResult(False, session_id=session_id, ticket_id=session.ticket.ticket_id, error="Диалог не содержит пользовательских ответов.")

        evaluation = self.evaluate_answer(
            session.ticket.ticket_id,
            "review",
            user_answer,
            model=session.session.resolved_model or self._settings.model,
            include_followups=False,
        )
        final_summary = evaluation.feedback
        final_verdict = evaluation.review.overall_comment if evaluation.review else evaluation.feedback
        now = datetime.now().isoformat()
        with self.connection:
            self.dialogue_repository.mark_session_completed(
                session_id=session_id,
                last_turn_index=session.session.last_turn_index,
                user_turn_count=session.session.user_turn_count,
                final_score_percent=evaluation.score_percent,
                final_verdict=final_verdict,
                final_summary=final_summary,
                final_feedback=evaluation.feedback,
                completed_at=now,
                updated_at=now,
                commit=False,
            )
        return self._dialogue_result_from_evaluation(session, evaluation, final_verdict, final_summary)

    @staticmethod
    def _normalize_dialogue_persona(persona_kind: str) -> str:
        normalized = (persona_kind or "tutor").strip().lower()
        if normalized in {"examiner", "strict_examiner", "strict-examiner"}:
            return "examiner"
        return "tutor"

    def _generate_dialogue_turn(
        self,
        ticket,
        session_id: str,
        persona_kind: str,
        turns,
        *,
        opening: bool,
        seed_focus: str | None = None,
    ):
        profile = get_answer_profile(ticket.answer_profile_code)
        weak_points = self._dialogue_weak_points(ticket.ticket_id, turns=turns, seed_focus=seed_focus)
        transcript = [
            DialogueTranscriptLine(turn.speaker, turn.text)
            for turn in turns[-8:]
        ]
        if opening and not transcript:
            transcript = []
        context = DialogueTurnContext(
            session_id=session_id,
            ticket_id=ticket.ticket_id,
            ticket_title=ticket.title,
            ticket_summary=ticket.canonical_answer_summary,
            persona_kind=persona_kind,
            turn_index=(turns[-1].turn_index + 1) if turns else 1,
            transcript=transcript,
            ticket_atoms=[
                {
                    "atom_id": atom.atom_id,
                    "type": atom.type.value,
                    "label": atom.label,
                    "text": atom.text,
                }
                for atom in ticket.atoms[:8]
            ],
            ticket_answer_blocks=[
                {
                    "block_code": block.block_code.value,
                    "title": block.title,
                    "expected_content": block.expected_content,
                }
                for block in ticket.answer_blocks[:6]
            ],
            examiner_prompts=[prompt.text for prompt in ticket.examiner_prompts[:6]],
            answer_profile_hints=[
                hint
                for hint in (
                    [profile.description]
                    + [block.training_hint for block in profile.blocks if block.training_hint]
                    + [block.followup_hint for block in profile.blocks if block.followup_hint]
                )
                if hint
            ][:8],
            weak_points=weak_points,
        )
        session_row = None if opening else self.dialogue_repository.load_session_row(session_id)
        resolved_model = session_row["resolved_model"] if session_row is not None and session_row["resolved_model"] else self._settings.model
        return self.build_ollama_service().generate_dialogue_turn(context, resolved_model)

    def _dialogue_weak_points(self, ticket_id: str, *, turns, seed_focus: str | None = None) -> list[str]:
        points: list[str] = []
        if seed_focus and seed_focus.strip():
            points.append(seed_focus.strip())
        for row in self.queries.load_weak_areas():
            related_ids = json_load(row["related_ticket_ids_json"])
            if row["reference_id"] == ticket_id or ticket_id in related_ids:
                title = str(row["title"] or "").strip()
                if title and title not in points:
                    points.append(title)
        for turn in turns:
            if turn.speaker == "assistant":
                focus = turn.weakness_focus.strip()
                if focus and focus not in points:
                    points.append(focus)
        for session_row in self.dialogue_repository.load_recent_sessions(
            "local-user",
            limit=5,
            ticket_id=ticket_id,
            status="completed",
        ):
            for turn_row in self.dialogue_repository.load_session_turns(session_row["session_id"]):
                focus = str(turn_row["weakness_focus"] or "").strip()
                if focus and focus not in points:
                    points.append(focus)
                if len(points) >= 6:
                    return points[:6]
        return points[:6]

    @staticmethod
    def _dialogue_message_text(feedback_text: str, next_question: str) -> str:
        parts = [feedback_text.strip(), next_question.strip()]
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def _dialogue_opening_fallback(ticket, persona_kind: str) -> str:
        persona_label = "экзаменатор" if persona_kind == "examiner" else "тьютор"
        return (
            f"Начинаем разбор билета «{ticket.title}». Я ваш локальный {persona_label}. "
            "Держитесь только материала билета и начните с краткого опорного ответа."
        )

    def _dialogue_followup_fallback(self, session: DialogueSessionState) -> str:
        weak_points = self._dialogue_weak_points(session.ticket.ticket_id, turns=session.turns)
        if weak_points:
            return (
                f"Уточните слабый блок: {weak_points[0]}.\n\n"
                f"Как именно этот фрагмент раскрывается в билете «{session.ticket.title}»?"
            )
        if session.ticket.examiner_prompts:
            return session.ticket.examiner_prompts[0].text
        return f"Сформулируйте связный ответ по билету «{session.ticket.title}» без выхода за пределы материала."

    def _dialogue_result_from_evaluation(
        self,
        session: DialogueSessionState,
        evaluation: TrainingEvaluationResult,
        final_verdict: str,
        final_summary: str,
    ) -> DialogueResult:
        return DialogueResult(
            ok=evaluation.ok,
            session_id=session.session.session_id,
            ticket_id=session.ticket.ticket_id,
            persona_kind=session.session.persona_kind,
            score_percent=evaluation.score_percent,
            feedback=evaluation.feedback,
            weak_points=evaluation.weak_points,
            answer_profile_code=evaluation.answer_profile_code,
            block_scores=evaluation.block_scores,
            criterion_scores=evaluation.criterion_scores,
            followup_questions=evaluation.followup_questions,
            final_verdict=final_verdict,
            final_summary=final_summary,
            review=evaluation.review,
            error=evaluation.error,
        )

    def _dialogue_result_from_session(self, session: DialogueSessionState, *, ok: bool) -> DialogueResult:
        weak_points = []
        for turn in session.turns:
            if turn.speaker == "assistant":
                focus = turn.weakness_focus.strip()
                if focus and focus not in weak_points:
                    weak_points.append(focus)
        return DialogueResult(
            ok=ok,
            session_id=session.session.session_id,
            ticket_id=session.ticket.ticket_id,
            persona_kind=session.session.persona_kind,
            score_percent=session.session.score_percent,
            feedback=session.result.feedback if session.result is not None else session.session.summary,
            weak_points=weak_points[:4],
            answer_profile_code=session.ticket.answer_profile_code.value,
            final_verdict=session.session.verdict,
            final_summary=session.session.summary,
            review=session.result.review if session.result is not None else None,
        )

    def load_readiness_score(self, tickets=None, mastery=None):
        from application.ui_data import ReadinessScore
        resolved_tickets = tickets if tickets is not None else self.load_ticket_maps()
        resolved_mastery = mastery if mastery is not None else self.load_mastery_breakdowns()
        return ReadinessService().calculate(resolved_tickets, resolved_mastery)

    def load_training_snapshot(self, tickets: list[TicketKnowledgeMap] | None = None) -> TrainingSnapshot:
        snapshot = self.queries.load_training_snapshot(limit=self._settings.training_queue_size, tickets=tickets)
        if snapshot.queue_items:
            return snapshot
        loaded_tickets = snapshot.tickets
        if not loaded_tickets:
            return snapshot
        queue = self.adaptive.build_queue(
            user_id="local-user",
            tickets=loaded_tickets,
            profiles=self._load_profiles(loaded_tickets),
            weak_areas=self._load_weak_areas(),
            mode=self._resolve_review_mode(),
        )
        self.repository.save_review_queue("local-user", queue)
        return self.queries.load_training_snapshot(limit=self._settings.training_queue_size, tickets=loaded_tickets)

    def import_document(
        self,
        path: str | Path,
        answer_profile_code: str | AnswerProfileCode = AnswerProfileCode.STANDARD_TICKET,
        *,
        generation_timeout_seconds: float | None | object = _USE_SETTINGS_TIMEOUT,
    ) -> ImportExecutionResult:
        return self.import_document_with_progress(
            path,
            answer_profile_code=answer_profile_code,
            generation_timeout_seconds=generation_timeout_seconds,
        )

    def import_document_with_progress(
        self,
        path: str | Path,
        answer_profile_code: str | AnswerProfileCode = AnswerProfileCode.STANDARD_TICKET,
        progress_callback=None,
        *,
        generation_timeout_seconds: float | None | object = _USE_SETTINGS_TIMEOUT,
    ) -> ImportExecutionResult:
        document_path = Path(path)
        stem_title = normalize_import_title(document_path.stem)
        profile_code = self._normalize_answer_profile_code(answer_profile_code)
        exam = Exam(
            exam_id="local-exam",
            title="Локальная база билетов",
            description="Автоматически созданный контейнер для импортированных материалов.",
            total_tickets=0,
            subject_area="exam-training",
        )
        subject_slug = self._slug(stem_title) or "default-subject"
        llm_refinement_enabled = bool(self._settings.import_llm_assist)
        service = DocumentImportService(
            ollama_service=None,
            llm_model=self._settings.model,
            enable_llm_structuring=False,
        )
        prepared = None
        try:
            prepared = service.prepare_import(
                document_path,
                exam_id=exam.exam_id,
                subject_id=subject_slug,
                default_section_id="imported-section",
                answer_profile_code=profile_code,
                progress_callback=progress_callback,
            )
        except Exception as exc:  # noqa: BLE001
            return ImportExecutionResult(False, error=str(exc))

        queue_items = service.create_import_queue_items(prepared.candidates, prepared.source_document.document_id, "imported-section")
        candidate_batches = self._partition_import_items(prepared.candidates)
        queue_batches = self._partition_import_items(queue_items)
        part_total = max(len(candidate_batches), 1)
        unique_sections = self._build_sections_from_queue(exam.exam_id, queue_items)
        exam.total_tickets = len(queue_items)

        if progress_callback is not None:
            progress_callback(29, "План обработки", f"Найдено билетов: {len(queue_items)} • частей: {part_total}")
            progress_callback(30, "Сохранение каркаса импорта", "Фиксируем документ, фрагменты и очередь билетов в SQLite")
        # Скелет импорта — одна транзакция: иначе крах между save_exam и
        # save_import_queue оставит БД в рассинхронизированном состоянии
        # (документ есть, а очередь пустая → UI показывает «0 билетов»).
        with atomic(self.connection):
            self.repository.save_exam(exam)
            for section in unique_sections:
                self.repository.save_section(section)
            self.repository.save_source_document(
                prepared.source_document,
                raw_text=prepared.normalized_text,
                status="importing",
                warnings=prepared.warnings,
                used_llm_assist=False,
                ticket_total=len(queue_items),
                tickets_llm_done=0,
                last_attempted_at=datetime.now().isoformat(),
                last_error="",
            )
            self.repository.save_chunks(prepared.source_document.document_id, prepared.chunks)
            self.repository.save_import_queue(prepared.source_document.document_id, queue_items)

        warnings = list(prepared.warnings)
        used_llm_assist = False
        total_candidates = max(1, len(prepared.candidates))
        build_start = 34
        build_end = 78
        processed_candidates = 0
        for part_index, (candidate_batch, queue_batch) in enumerate(zip(candidate_batches, queue_batches, strict=True), start=1):
            for candidate, queue_item in zip(candidate_batch, queue_batch, strict=True):
                processed_candidates += 1
                detail = (
                    f"Часть {part_index}/{part_total} • билет {processed_candidates} из {total_candidates}: "
                    f"{candidate.title[:72]}"
                )
                self.repository.update_document_import_state(
                    prepared.source_document.document_id,
                    status="importing",
                    last_attempted_at=datetime.now().isoformat(),
                )
                if progress_callback is not None:
                    progress_callback(
                        self._loop_progress(build_start, build_end, processed_candidates - 1, total_candidates),
                        "Построение карты билета",
                        detail,
                    )
                try:
                    ticket, used_llm, llm_warning = service.build_ticket_map(
                        candidate,
                        exam.exam_id,
                        queue_item.section_id,
                        prepared.source_document.document_id,
                        ticket_id=queue_item.ticket_id,
                        answer_profile_code=prepared.source_document.answer_profile_code,
                    )
                    needs_llm_refinement = llm_refinement_enabled and service.needs_llm_refinement(candidate, ticket)
                    queue_status = "pending" if needs_llm_refinement else ("fallback" if llm_warning else "done")
                    self.repository.save_ticket_map(
                        ticket,
                        llm_status=queue_status,
                        llm_error=llm_warning,
                    )
                    self.repository.save_exercise_instances(service.generate_exercise_instances(ticket))
                    self.repository.update_import_queue_item(
                        queue_item.ticket_id,
                        llm_status=queue_status,
                        llm_error=llm_warning,
                        llm_attempted=used_llm,
                        used_llm=used_llm,
                    )
                    if llm_warning:
                        warnings.append(f"{ticket.title}: {llm_warning}")
                    used_llm_assist = used_llm_assist or used_llm
                except Exception as exc:  # noqa: BLE001
                    error_text = str(exc)
                    warnings.append(f"{candidate.title}: {error_text}")
                    self.repository.update_import_queue_item(
                        queue_item.ticket_id,
                        llm_status="failed",
                        llm_error=error_text,
                        llm_attempted=True,
                        used_llm=False,
                    )
                if progress_callback is not None:
                    progress_callback(
                        self._loop_progress(build_start, build_end, processed_candidates, total_candidates),
                        "Построение карты билета",
                        detail,
                    )

        if progress_callback is not None:
            progress_callback(82, "Связи между билетами", "Строим cross-ticket concepts и перекрёстные ссылки")
        self._refresh_document_cross_links(prepared.source_document.document_id, service)

        final_result = self._finalize_import_document(
            prepared.source_document.document_id,
            prepared.source_document.title,
            warnings,
            used_llm_assist,
        )
        if progress_callback is not None:
            progress_callback(99, "Обновление очереди", "Перестраиваем adaptive queue и статистику")
        self._refresh_review_queue()
        if progress_callback is not None:
            progress_callback(
                100,
                "Импорт завершён" if final_result.status == "structured" else "Базовый импорт завершён",
                "Документ и упражнения сохранены. LLM-доработку можно запустить отдельно только для хвоста.",
            )
        return final_result

    def resume_document_import_with_progress(
        self,
        document_id: str,
        progress_callback=None,
        *,
        generation_timeout_seconds: float | None | object = _USE_SETTINGS_TIMEOUT,
        parallel_workers: int = 1,
    ) -> ImportExecutionResult:
        source_row = self.repository.load_source_document_row(document_id)
        if source_row is None:
            return ImportExecutionResult(False, error="Документ для локальной доработки не найден.")

        queue_rows = self.repository.load_import_queue(document_id, statuses=("pending", "fallback", "failed"))
        if not queue_rows:
            self._backfill_legacy_import_queue(document_id)
            queue_rows = self.repository.load_import_queue(document_id, statuses=("pending", "fallback", "failed"))
        if not queue_rows:
            return self._finalize_import_document(
                document_id,
                source_row["title"],
                self._load_document_warnings(document_id),
                bool(source_row["used_llm_assist"]),
            )

        warnings = self._load_document_warnings(document_id)
        used_llm_assist = bool(source_row["used_llm_assist"])
        total_rows = max(1, len(queue_rows))
        row_batches = self._partition_import_items(queue_rows)
        part_total = max(len(row_batches), 1)
        resume_start = 38
        resume_end = 88
        workers = max(1, int(parallel_workers))
        self.repository.update_document_import_state(
            document_id,
            status="importing",
            last_attempted_at=datetime.now().isoformat(),
            last_error="",
        )
        processed_rows = 0
        service: DocumentImportService | None = None
        shared_ollama = self.build_import_ollama_service(generation_timeout_seconds=generation_timeout_seconds)

        def _service_factory() -> DocumentImportService:
            return DocumentImportService(
                ollama_service=shared_ollama,
                llm_model=self._settings.model,
                enable_llm_structuring=True,
            )

        for part_index, batch_rows in enumerate(row_batches, start=1):
            service = _service_factory()
            if workers > 1 and len(batch_rows) > 1:
                processed_rows, warnings, used_llm_assist = self._resume_batch_parallel(
                    service_factory=_service_factory,
                    batch_rows=batch_rows,
                    source_row=source_row,
                    document_id=document_id,
                    warnings=warnings,
                    used_llm_assist=used_llm_assist,
                    processed_rows=processed_rows,
                    total_rows=total_rows,
                    part_index=part_index,
                    part_total=part_total,
                    resume_start=resume_start,
                    resume_end=resume_end,
                    progress_callback=progress_callback,
                    workers=workers,
                )
            else:
                for row in batch_rows:
                    processed_rows, warnings, used_llm_assist = self._resume_one_row_sequential(
                        service=service,
                        row=row,
                        source_row=source_row,
                        document_id=document_id,
                        warnings=warnings,
                        used_llm_assist=used_llm_assist,
                        processed_rows=processed_rows,
                        total_rows=total_rows,
                        part_index=part_index,
                        part_total=part_total,
                        resume_start=resume_start,
                        resume_end=resume_end,
                        progress_callback=progress_callback,
                    )

        if service is not None:
            self._refresh_document_cross_links(document_id, service)
        result = self._finalize_import_document(document_id, source_row["title"], warnings, used_llm_assist)
        if progress_callback is not None:
            progress_callback(96, "Обновление очереди", "Перестраиваем adaptive queue и статистику")
        self._refresh_review_queue()
        if progress_callback is not None:
            progress_callback(
                100,
                "Локальная доработка завершена" if result.status == "structured" else "Хвост всё ещё не закрыт",
                "Результат сохранён в SQLite и отражён в интерфейсе.",
            )
        return result

    def _prepare_resume_row(self, row, source_row, document_id: str, fallback_index: int):
        """Подгружает всё, что нужно для LLM-обработки билета, из SQLite.
        Выполняется строго в главном потоке, чтобы не трогать sqlite из воркеров."""
        source_text = row["body_text"] or self._reconstruct_ticket_source_text(row["ticket_id"])
        try:
            existing_ticket = self.queries.load_ticket_map(row["ticket_id"])
        except KeyError:
            existing_ticket = None
        candidate: TicketCandidate | None = None
        if existing_ticket is None:
            candidate = TicketCandidate(
                index=int(row["ticket_index"] or fallback_index),
                title=row["title"],
                body=source_text,
                confidence=float(row["candidate_confidence"] or 0.5),
                section_title=row["section_id"],
            )
        return {
            "row": row,
            "source_text": source_text,
            "existing_ticket": existing_ticket,
            "candidate": candidate,
            "answer_profile_code": self._normalize_answer_profile_code(source_row["answer_profile_code"]),
            "exam_id": source_row["exam_id"],
        }

    @staticmethod
    def _call_llm_for_resume_row(service: DocumentImportService, prep: dict, document_id: str):
        """Только LLM-вызовы и генерация упражнений в памяти — никаких обращений к БД.
        Возвращает готовые объекты; главный поток потом сам всё сохранит."""
        if prep["existing_ticket"] is None:
            updated_ticket, used_llm, llm_warning = service.build_ticket_map(
                prep["candidate"],
                prep["exam_id"],
                prep["row"]["section_id"],
                document_id,
                ticket_id=prep["row"]["ticket_id"],
                answer_profile_code=prep["answer_profile_code"],
            )
        else:
            updated_ticket, used_llm, llm_warning = service.rebuild_ticket_map(
                prep["existing_ticket"], prep["source_text"], force_llm=True
            )
        exercise_instances = service.generate_exercise_instances(updated_ticket)
        return updated_ticket, used_llm, llm_warning, exercise_instances

    def _resume_persist_success(
        self,
        row,
        updated_ticket,
        used_llm: bool,
        llm_warning: str,
        exercise_instances: list,
        warnings: list[str],
    ) -> tuple[list[str], bool]:
        status = "fallback" if llm_warning else "done"
        self.repository.save_ticket_map(updated_ticket, llm_status=status, llm_error=llm_warning)
        self.repository.save_exercise_instances(exercise_instances)
        self.repository.update_import_queue_item(
            row["ticket_id"],
            llm_status=status,
            llm_error=llm_warning,
            llm_attempted=True,
            used_llm=used_llm,
        )
        return self._replace_warning(warnings, updated_ticket.title, llm_warning), used_llm

    def _resume_persist_failure(self, row, error_text: str, warnings: list[str]) -> list[str]:
        self.repository.update_import_queue_item(
            row["ticket_id"],
            llm_status="failed",
            llm_error=error_text,
            llm_attempted=True,
            used_llm=False,
        )
        return self._replace_warning(warnings, row["title"], error_text)

    def _resume_one_row_sequential(
        self,
        *,
        service: DocumentImportService,
        row,
        source_row,
        document_id: str,
        warnings: list[str],
        used_llm_assist: bool,
        processed_rows: int,
        total_rows: int,
        part_index: int,
        part_total: int,
        resume_start: int,
        resume_end: int,
        progress_callback,
    ) -> tuple[int, list[str], bool]:
        processed_rows += 1
        detail = (
            f"Часть {part_index}/{part_total} • билет {row['ticket_index']} "
            f"из {int(source_row['ticket_total'] or total_rows)}: {row['title'][:72]}"
        )
        if progress_callback is not None:
            progress_callback(
                self._loop_progress(resume_start, resume_end, processed_rows - 1, total_rows),
                "Локальная доработка хвоста",
                detail,
            )
        try:
            prep = self._prepare_resume_row(row, source_row, document_id, fallback_index=processed_rows)
            updated_ticket, used_llm, llm_warning, exercise_instances = self._call_llm_for_resume_row(
                service, prep, document_id
            )
            warnings, llm_flag = self._resume_persist_success(
                row, updated_ticket, used_llm, llm_warning, exercise_instances, warnings
            )
            used_llm_assist = used_llm_assist or llm_flag
        except Exception as exc:  # noqa: BLE001
            warnings = self._resume_persist_failure(row, str(exc), warnings)
        if progress_callback is not None:
            progress_callback(
                self._loop_progress(resume_start, resume_end, processed_rows, total_rows),
                "Локальная доработка хвоста",
                detail,
            )
        return processed_rows, warnings, used_llm_assist

    def _resume_batch_parallel(
        self,
        *,
        service_factory,
        batch_rows: list,
        source_row,
        document_id: str,
        warnings: list[str],
        used_llm_assist: bool,
        processed_rows: int,
        total_rows: int,
        part_index: int,
        part_total: int,
        resume_start: int,
        resume_end: int,
        progress_callback,
        workers: int,
    ) -> tuple[int, list[str], bool]:
        """Параллельный прогон LLM-refinement для батча билетов.

        Главный поток: pre-load из БД → dispatch в пул → собираем futures → save в БД.
        Воркеры: только LLM-вызовы (thread-safe requests к Ollama) + экземпляры
        упражнений в памяти (чистые объекты, без БД).

        Каждый воркер получает свой `DocumentImportService` через `service_factory`
        (thread-local), чтобы избежать race-условия на мутациях
        ``enable_llm_structuring`` внутри ``rebuild_ticket_map``.
        """
        import threading as _threading

        # Pre-load всех prep-объектов одной серией (всё в main thread).
        preps_by_ticket: dict[str, dict] = {}
        for local_index, row in enumerate(batch_rows, start=1):
            preps_by_ticket[row["ticket_id"]] = self._prepare_resume_row(
                row, source_row, document_id, fallback_index=processed_rows + local_index
            )

        thread_local = _threading.local()

        def _worker(ticket_id: str):
            prep = preps_by_ticket[ticket_id]
            service = getattr(thread_local, "service", None)
            if service is None:
                service = service_factory()
                thread_local.service = service
            try:
                updated_ticket, used_llm, llm_warning, exercise_instances = self._call_llm_for_resume_row(
                    service, prep, document_id
                )
                return (ticket_id, True, updated_ticket, used_llm, llm_warning, exercise_instances, "")
            except Exception as exc:  # noqa: BLE001
                return (ticket_id, False, None, False, "", [], str(exc))

        # На каждый билет — по одному progress-callback'у (в момент запуска в пул),
        # иначе цифры прыгают непредсказуемо при `as_completed`.
        for local_index, row in enumerate(batch_rows, start=1):
            if progress_callback is not None:
                pending_index = processed_rows + local_index
                detail = (
                    f"Часть {part_index}/{part_total} • билет {row['ticket_index']} "
                    f"из {int(source_row['ticket_total'] or total_rows)}: {row['title'][:72]} [parallel]"
                )
                progress_callback(
                    self._loop_progress(resume_start, resume_end, pending_index - 1, total_rows),
                    "Локальная доработка хвоста",
                    detail,
                )

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tezis-resume") as pool:
            futures: list[Future] = [pool.submit(_worker, row["ticket_id"]) for row in batch_rows]
            completed_in_batch = 0
            for future in as_completed(futures):
                ticket_id, ok, updated_ticket, used_llm, llm_warning, exercise_instances, error_text = future.result()
                prep = preps_by_ticket[ticket_id]
                row = prep["row"]
                if ok:
                    warnings, llm_flag = self._resume_persist_success(
                        row, updated_ticket, used_llm, llm_warning, exercise_instances, warnings
                    )
                    used_llm_assist = used_llm_assist or llm_flag
                else:
                    warnings = self._resume_persist_failure(row, error_text, warnings)

                completed_in_batch += 1
                if progress_callback is not None:
                    completed_index = processed_rows + completed_in_batch
                    detail = (
                        f"Часть {part_index}/{part_total} • готов {completed_index} "
                        f"из {int(source_row['ticket_total'] or total_rows)} [parallel]"
                    )
                    progress_callback(
                        self._loop_progress(resume_start, resume_end, completed_index, total_rows),
                        "Локальная доработка хвоста",
                        detail,
                    )

        processed_rows += len(batch_rows)
        return processed_rows, warnings, used_llm_assist

    def evaluate_answer(
        self,
        ticket_id: str,
        mode_key: str,
        answer_text: str,
        *,
        model: str | None = None,
        include_followups: bool = True,
    ) -> TrainingEvaluationResult:
        answer = answer_text.strip()
        if not answer:
            return TrainingEvaluationResult(False, 0, "", [], error="Ответ пуст. Введите текст ответа перед проверкой.")

        ticket = self.queries.load_ticket_map(ticket_id)
        resolved_model = model or self._settings.model
        exercise = self._pick_exercise(ticket, mode_key)
        profile = self._load_profile(ticket_id)
        block_profile = self._load_block_profile(ticket_id)
        outcome = self.scoring.evaluate(ticket, exercise, answer, profile=profile, block_profile=block_profile)
        outcome.profile.next_review_at = datetime.now()
        self.repository.save_exercise_instances([exercise])
        self.repository.save_attempt(outcome.attempt)
        if outcome.attempt_block_scores:
            self.repository.save_attempt_block_scores(outcome.attempt.attempt_id, outcome.attempt_block_scores)
        self.repository.save_mastery_profile(outcome.profile)
        if outcome.block_profile is not None:
            self.repository.save_block_mastery_profile(outcome.block_profile)
        self.repository.save_weak_areas("local-user", ticket_id, outcome.weak_areas)
        self._refresh_review_queue()

        followups: list[str] = []
        if include_followups and self._settings.examiner_followups:
            weak_titles = [area.title for area in outcome.weak_areas[:2]]
            if weak_titles:
                llm_result = self.build_ollama_service().generate_followup_questions(
                    ticket.title,
                    ticket.canonical_answer_summary,
                    weak_titles,
                    resolved_model,
                    count=2,
                )
                if llm_result.ok and llm_result.content:
                    followups = [line.removeprefix("- ").strip() for line in llm_result.content.splitlines() if line.strip()]

        review_verdict = None
        if mode_key in {"active-recall", "mini-exam", "state-exam-full", "review"}:
            review_verdict = self.scoring.build_review_verdict(
                ticket, mode_key, answer,
                ollama_service=self.build_ollama_service(),
                model=resolved_model,
            )

        return TrainingEvaluationResult(
            ok=True,
            score_percent=int(round(outcome.attempt.score * 100)),
            feedback=outcome.attempt.feedback,
            weak_points=[area.title for area in outcome.weak_areas[:4]],
            answer_profile_code=ticket.answer_profile_code.value,
            block_scores={code.value: int(round(score * 100)) for code, score in outcome.block_scores.items()},
            criterion_scores={code.value: int(round(score * 100)) for code, score in outcome.criterion_scores.items()},
            followup_questions=followups,
            review=review_verdict,
        )

    def _pick_exercise(self, ticket, mode_key: str):
        type_map = {
            "reading": ExerciseType.ANSWER_SKELETON,
            "active-recall": ExerciseType.ATOM_RECALL,
            "cloze": ExerciseType.SEMANTIC_CLOZE,
            "matching": ExerciseType.ODD_THESIS,
            "plan": ExerciseType.STRUCTURE_RECONSTRUCTION,
            "mini-exam": ExerciseType.ORAL_FULL,
            "state-exam-full": ExerciseType.ORAL_FULL,
            "review": ExerciseType.ORAL_FULL,
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

    def _load_block_profile(self, ticket_id: str) -> TicketBlockMasteryProfile | None:
        row = self.connection.execute(
            "SELECT * FROM ticket_block_mastery_profiles WHERE user_id = ? AND ticket_id = ?",
            ("local-user", ticket_id),
        ).fetchone()
        if row is None:
            return None
        return TicketBlockMasteryProfile(
            user_id=row["user_id"],
            ticket_id=row["ticket_id"],
            intro_mastery=float(row["intro_mastery"] or 0.0),
            theory_mastery=float(row["theory_mastery"] or 0.0),
            practice_mastery=float(row["practice_mastery"] or 0.0),
            skills_mastery=float(row["skills_mastery"] or 0.0),
            conclusion_mastery=float(row["conclusion_mastery"] or 0.0),
            extra_mastery=float(row["extra_mastery"] or 0.0),
            overall_score=float(row["overall_score"] or 0.0),
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

    def _build_sections_from_queue(self, exam_id: str, queue_items) -> list[Section]:
        unique_sections: list[Section] = []
        seen: set[str] = set()
        for index, item in enumerate(queue_items, start=1):
            if item.section_id in seen:
                continue
            seen.add(item.section_id)
            section_title = item.section_id.replace("-", " ").title()
            if item.section_id in {"imported-section", "default-section"} or section_title == "Imported Section":
                section_title = "Основной раздел"
            unique_sections.append(
                Section(
                    section_id=item.section_id,
                    exam_id=exam_id,
                    title=section_title,
                    order_index=index,
                    description="Раздел, выделенный при импорте документа",
                )
            )
        return unique_sections

    def _refresh_document_cross_links(self, document_id: str, service: DocumentImportService) -> None:
        tickets = self.queries.load_ticket_maps_for_document(document_id)
        if not tickets:
            return
        service.attach_cross_ticket_links(tickets)
        queue_state = {row["ticket_id"]: row for row in self.repository.load_import_queue(document_id)}
        for ticket in tickets:
            ticket_row = queue_state.get(ticket.ticket_id)
            self.repository.save_ticket_map(
                ticket,
                llm_status=ticket_row["llm_status"] if ticket_row else "done",
                llm_error=ticket_row["llm_error"] if ticket_row else "",
            )

    def _finalize_import_document(
        self,
        document_id: str,
        document_title: str,
        warnings: list[str],
        used_llm_assist: bool,
    ) -> ImportExecutionResult:
        queue_counts = self.repository.count_import_queue_statuses(document_id)
        pending = int(queue_counts.get("pending", 0))
        fallback = int(queue_counts.get("fallback", 0))
        failed = int(queue_counts.get("failed", 0))
        done = int(queue_counts.get("done", 0))
        status = "structured" if pending == 0 and fallback == 0 and failed == 0 else "partial_llm"
        source_row = self.repository.load_source_document_row(document_id)
        actual_ticket_total = int(
            self.connection.execute(
                "SELECT COUNT(*) AS total FROM tickets WHERE source_document_id = ?",
                (document_id,),
            ).fetchone()["total"] or 0
        )
        queue_ticket_total = done + pending + fallback + failed
        source_ticket_total = int(source_row["ticket_total"] or 0) if source_row is not None else 0
        ticket_total = max(actual_ticket_total, queue_ticket_total, source_ticket_total)
        profile_code = source_row["answer_profile_code"] if source_row is not None else AnswerProfileCode.STANDARD_TICKET.value
        section_total = int(
            self.connection.execute(
                "SELECT COUNT(DISTINCT section_id) AS total FROM tickets WHERE source_document_id = ?",
                (document_id,),
            ).fetchone()["total"] or 0
        )
        self.repository.update_document_import_state(
            document_id,
            status=status,
            warnings=self._deduplicate_warnings(warnings),
            used_llm_assist=used_llm_assist,
            ticket_total=ticket_total,
            tickets_llm_done=done,
            last_attempted_at=datetime.now().isoformat(),
            last_error="; ".join(self._deduplicate_warnings(warnings)[-3:]) if status != "structured" else "",
        )
        return ImportExecutionResult(
            ok=True,
            document_id=document_id,
            document_title=document_title,
            status=status,
            answer_profile_code=profile_code,
            answer_profile_label=answer_profile_label(profile_code),
            tickets_created=ticket_total,
            sections_created=section_total,
            warnings=self._deduplicate_warnings(warnings),
            used_llm_assist=used_llm_assist,
            llm_done_tickets=done,
            llm_pending_tickets=pending,
            llm_fallback_tickets=fallback,
            llm_failed_tickets=failed,
            resume_available=status != "structured",
            error="",
        )

    def _load_document_warnings(self, document_id: str) -> list[str]:
        row = self.repository.load_source_document_row(document_id)
        if row is None or not row["warnings_json"]:
            return []
        return json_load(row["warnings_json"])

    def _reconstruct_ticket_source_text(self, ticket_id: str) -> str:
        ticket = self.queries.load_ticket_map(ticket_id)
        parts = [atom.text.strip() for atom in ticket.atoms if atom.text.strip()]
        if not parts:
            return ticket.canonical_answer_summary
        return "\n\n".join(parts)

    def _backfill_legacy_import_queue(self, document_id: str) -> None:
        source_row = self.repository.load_source_document_row(document_id)
        if source_row is None:
            return
        if source_row["used_llm_assist"]:
            return
        tickets = self.queries.load_ticket_maps_for_document(document_id)
        if not tickets:
            return
        queue_items = [
            service_item
            for service_item in (
                TicketCandidate(
                    index=index,
                    title=ticket.title,
                    body=self._reconstruct_ticket_source_text(ticket.ticket_id),
                    confidence=ticket.source_confidence or 0.5,
                    section_title=ticket.section_id,
                )
                for index, ticket in enumerate(tickets, start=1)
            )
        ]
        service = DocumentImportService(
            ollama_service=self.build_import_ollama_service(),
            llm_model=self._settings.model,
            enable_llm_structuring=True,
        )
        self.repository.save_import_queue(
            document_id,
            service.create_import_queue_items(queue_items, document_id, "imported-section"),
        )
        self.repository.update_document_import_state(
            document_id,
            status="partial_llm",
            ticket_total=len(tickets),
            tickets_llm_done=0,
            last_attempted_at=datetime.now().isoformat(),
            last_error="Для старого импорта восстановлена очередь локальной доработки.",
        )

    @staticmethod
    def _replace_warning(warnings: list[str], title: str, error_text: str) -> list[str]:
        prefix = f"{title}:"
        filtered = [warning for warning in warnings if not warning.startswith(prefix)]
        if error_text:
            filtered.append(f"{title}: {error_text}")
        return filtered

    @staticmethod
    def _deduplicate_warnings(warnings: list[str]) -> list[str]:
        unique: list[str] = []
        for warning in warnings:
            text = warning.strip()
            if text and text not in unique:
                unique.append(text)
        return unique

    @staticmethod
    def _loop_progress(start: int, end: int, current: int, total: int) -> int:
        if total <= 0:
            return start
        span = max(0, end - start)
        ratio = current / total
        return start + int(round(span * ratio))

    @staticmethod
    def _normalize_answer_profile_code(code: str | AnswerProfileCode) -> AnswerProfileCode:
        try:
            return AnswerProfileCode(code)
        except ValueError:
            return AnswerProfileCode.STANDARD_TICKET

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
