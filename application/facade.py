from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import sqlite3

from application.adaptive_review import AdaptiveReviewService
from application.import_service import DocumentImportService, TicketCandidate
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

    def build_ollama_service(self, timeout_seconds: float | None = None) -> OllamaService:
        resolved_timeout = float(self._settings.timeout_seconds if timeout_seconds is None else timeout_seconds)
        return OllamaService(self._settings.base_url, resolved_timeout, self._settings.models_path)

    def build_import_ollama_service(self) -> OllamaService:
        return OllamaService(self._settings.base_url, None, self._settings.models_path)

    def inspect_ollama(self) -> OllamaDiagnostics:
        return self.build_ollama_service(timeout_seconds=min(float(self._settings.timeout_seconds), 3.0)).inspect(self._settings.model)

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

    def load_latest_import_result(self) -> ImportExecutionResult:
        return self.queries.load_latest_import_result()

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
        return self.import_document_with_progress(path)

    def import_document_with_progress(
        self,
        path: str | Path,
        progress_callback=None,
    ) -> ImportExecutionResult:
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
            ollama_service=self.build_import_ollama_service(),
            llm_model=self._settings.model,
            enable_llm_structuring=self._settings.import_llm_assist,
        )
        prepared = None
        try:
            prepared = service.prepare_import(
                document_path,
                exam_id=exam.exam_id,
                subject_id=subject_slug,
                default_section_id="imported-section",
                progress_callback=progress_callback,
            )
        except Exception as exc:  # noqa: BLE001
            return ImportExecutionResult(False, error=str(exc))

        queue_items = service.create_import_queue_items(prepared.candidates, prepared.source_document.document_id, "imported-section")
        unique_sections = self._build_sections_from_queue(exam.exam_id, queue_items)
        exam.total_tickets = len(queue_items)

        if progress_callback is not None:
            progress_callback(30, "Сохранение каркаса импорта", "Фиксируем документ, фрагменты и очередь билетов в SQLite")
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
        for index, candidate in enumerate(prepared.candidates, start=1):
            queue_item = queue_items[index - 1]
            detail = f"Билет {index} из {total_candidates}: {candidate.title[:72]}"
            self.repository.update_document_import_state(
                prepared.source_document.document_id,
                status="importing",
                last_attempted_at=datetime.now().isoformat(),
            )
            if progress_callback is not None:
                progress_callback(
                    self._loop_progress(build_start, build_end, index - 1, total_candidates),
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
                )
                self.repository.save_ticket_map(
                    ticket,
                    llm_status="fallback" if llm_warning else "done",
                    llm_error=llm_warning,
                )
                self.repository.save_exercise_instances(service.generate_exercise_instances(ticket))
                self.repository.update_import_queue_item(
                    queue_item.ticket_id,
                    llm_status="fallback" if llm_warning else "done",
                    llm_error=llm_warning,
                    llm_attempted=service.should_use_llm_for_structuring(candidate, ticket.atoms),
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
                    self._loop_progress(build_start, build_end, index, total_candidates),
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
                "Импорт завершён" if final_result.status == "structured" else "Импорт сохранён частично",
                "Документ сохранён. При необходимости можно локально доделать хвост.",
            )
        return final_result

    def resume_document_import_with_progress(self, document_id: str, progress_callback=None) -> ImportExecutionResult:
        source_row = self.repository.load_source_document_row(document_id)
        if source_row is None:
            return ImportExecutionResult(False, error="Документ для локальной доработки не найден.")

        service = DocumentImportService(
            ollama_service=self.build_import_ollama_service(),
            llm_model=self._settings.model,
            enable_llm_structuring=True,
        )
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
        resume_start = 38
        resume_end = 88
        self.repository.update_document_import_state(
            document_id,
            status="importing",
            last_attempted_at=datetime.now().isoformat(),
            last_error="",
        )
        for index, row in enumerate(queue_rows, start=1):
            detail = f"Билет {row['ticket_index']} из {int(source_row['ticket_total'] or total_rows)}: {row['title'][:72]}"
            if progress_callback is not None:
                progress_callback(
                    self._loop_progress(resume_start, resume_end, index - 1, total_rows),
                    "Локальная доработка хвоста",
                    detail,
                )
            try:
                source_text = row["body_text"] or self._reconstruct_ticket_source_text(row["ticket_id"])
                try:
                    existing_ticket = self.queries.load_ticket_map(row["ticket_id"])
                except KeyError:
                    candidate = TicketCandidate(
                        index=int(row["ticket_index"] or index),
                        title=row["title"],
                        body=source_text,
                        confidence=float(row["candidate_confidence"] or 0.5),
                        section_title=row["section_id"],
                    )
                    updated_ticket, used_llm, llm_warning = service.build_ticket_map(
                        candidate,
                        source_row["exam_id"],
                        row["section_id"],
                        document_id,
                        ticket_id=row["ticket_id"],
                    )
                else:
                    updated_ticket, used_llm, llm_warning = service.rebuild_ticket_map(existing_ticket, source_text, force_llm=True)
                self.repository.save_ticket_map(
                    updated_ticket,
                    llm_status="fallback" if llm_warning else "done",
                    llm_error=llm_warning,
                )
                self.repository.save_exercise_instances(service.generate_exercise_instances(updated_ticket))
                self.repository.update_import_queue_item(
                    row["ticket_id"],
                    llm_status="fallback" if llm_warning else "done",
                    llm_error=llm_warning,
                    llm_attempted=True,
                    used_llm=used_llm,
                )
                warnings = self._replace_warning(warnings, updated_ticket.title, llm_warning)
                used_llm_assist = used_llm_assist or used_llm
            except Exception as exc:  # noqa: BLE001
                error_text = str(exc)
                warnings = self._replace_warning(warnings, row["title"], error_text)
                self.repository.update_import_queue_item(
                    row["ticket_id"],
                    llm_status="failed",
                    llm_error=error_text,
                    llm_attempted=True,
                    used_llm=False,
                )
            if progress_callback is not None:
                progress_callback(
                    self._loop_progress(resume_start, resume_end, index, total_rows),
                    "Локальная доработка хвоста",
                    detail,
                )

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
        ticket_total = int(source_row["ticket_total"] or 0) if source_row is not None else done + pending + fallback + failed
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
