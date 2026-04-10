from __future__ import annotations

from datetime import datetime
import json
import sqlite3

from application.answer_profile_registry import answer_profile_label
from application.ui_data import ImportExecutionResult, SectionOverviewItem, StateExamStatisticsSnapshot, StatisticsSnapshot, TicketMasteryBreakdown, TrainingQueueItem, TrainingSnapshot
from domain.answer_profile import AnswerBlockCode, AnswerCriterionCode, AnswerProfileCode, TicketAnswerBlock
from domain.knowledge import (
    AtomType,
    CrossTicketLink,
    ExerciseTemplate,
    ExerciseType,
    ExaminerPrompt,
    KnowledgeAtom,
    ScoringCriterion,
    SkillCode,
    TicketKnowledgeMap,
    TicketSkill,
)
from domain.models import DocumentData, SectionData, SessionData, SubjectData, TicketData


class UiQueryService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def load_documents(self) -> list[DocumentData]:
        rows = self.connection.execute(
            """
            SELECT document_id, title, file_type, subject_id, imported_at, size_bytes, status, answer_profile_code
            FROM source_documents
            ORDER BY imported_at DESC
            """
        ).fetchall()
        documents: list[DocumentData] = []
        for row in rows:
            sections = [
                SectionData(self._display_section_title(section_row["title"]), int(section_row["tickets_count"]))
                for section_row in self.connection.execute(
                    """
                    SELECT sections.title AS title, COUNT(tickets.ticket_id) AS tickets_count
                    FROM tickets
                    JOIN sections ON sections.section_id = tickets.section_id
                    WHERE tickets.source_document_id = ?
                    GROUP BY sections.section_id, sections.title
                    ORDER BY sections.order_index
                    """,
                    (row["document_id"],),
                ).fetchall()
            ]
            tickets = [
                TicketData(index + 1, self._display_ticket_title(ticket_row["title"]), "готов")
                for index, ticket_row in enumerate(
                    self.connection.execute(
                        "SELECT title FROM tickets WHERE source_document_id = ? ORDER BY created_at, ticket_id",
                        (row["document_id"],),
                    ).fetchall()
                )
            ]
            documents.append(
                DocumentData(
                    id=row["document_id"],
                    title=self._display_document_title(row["title"]),
                    file_type=row["file_type"],
                    subject=self._display_subject(row["subject_id"]),
                    imported_at=self._format_dt(row["imported_at"]),
                    size=self._format_size(int(row["size_bytes"] or 0)),
                    status=self._display_status(row["status"]),
                    answer_profile_label=answer_profile_label(row["answer_profile_code"]),
                    display_tickets_count=len(tickets),
                    sections=sections,
                    tickets=tickets,
                )
            )
        return documents

    def load_subjects(self) -> list[SubjectData]:
        rows = self.connection.execute(
            """
            SELECT source_documents.subject_id AS subject_id,
                   COUNT(DISTINCT source_documents.document_id) AS documents,
                   COUNT(DISTINCT tickets.section_id) AS sections,
                   COUNT(DISTINCT tickets.ticket_id) AS tickets,
                   AVG(COALESCE(ticket_mastery_profiles.confidence_score, 0)) AS avg_mastery
            FROM source_documents
            LEFT JOIN tickets ON tickets.source_document_id = source_documents.document_id
            LEFT JOIN ticket_mastery_profiles ON ticket_mastery_profiles.ticket_id = tickets.ticket_id
            GROUP BY source_documents.subject_id
            ORDER BY source_documents.subject_id
            """
        ).fetchall()
        accents = ["#2E78E6", "#18B06A", "#F59A23", "#8B5CF6", "#14B8A6"]
        subjects: list[SubjectData] = []
        for index, row in enumerate(rows):
            progress = int(round(float(row["avg_mastery"] or 0.0) * 100))
            subjects.append(
                SubjectData(
                    name=self._display_subject(row["subject_id"]),
                    documents=int(row["documents"] or 0),
                    sections=int(row["sections"] or 0),
                    tickets=int(row["tickets"] or 0),
                    progress=progress,
                    accent=accents[index % len(accents)],
                )
            )
        return subjects

    def load_sections_overview(self) -> list[SectionOverviewItem]:
        rows = self.connection.execute(
            """
            SELECT sections.title AS title,
                   source_documents.subject_id AS subject_id,
                   COUNT(tickets.ticket_id) AS tickets_count
            FROM sections
            LEFT JOIN tickets ON tickets.section_id = sections.section_id
            LEFT JOIN source_documents ON source_documents.document_id = tickets.source_document_id
            GROUP BY sections.section_id, sections.title, source_documents.subject_id
            ORDER BY sections.order_index, sections.title
            """
        ).fetchall()
        return [
            SectionOverviewItem(
                title=self._display_section_title(row["title"]),
                subject=self._display_subject(row["subject_id"] or "no-subject"),
                tickets=int(row["tickets_count"] or 0),
            )
            for row in rows
        ]

    def load_ticket_maps(self) -> list[TicketKnowledgeMap]:
        rows = self.connection.execute(
            """
            SELECT ticket_id
            FROM tickets
            ORDER BY created_at DESC, ticket_id DESC
            """
        ).fetchall()
        return [self.load_ticket_map(row["ticket_id"]) for row in rows]

    def load_ticket_maps_for_document(self, document_id: str) -> list[TicketKnowledgeMap]:
        rows = self.connection.execute(
            """
            SELECT ticket_id
            FROM tickets
            WHERE source_document_id = ?
            ORDER BY created_at, ticket_id
            """,
            (document_id,),
        ).fetchall()
        return [self.load_ticket_map(row["ticket_id"]) for row in rows]

    def load_ticket_map(self, ticket_id: str) -> TicketKnowledgeMap:
        ticket_row = self.connection.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
        if ticket_row is None:
            raise KeyError(f"Ticket '{ticket_id}' not found.")

        atom_rows = self.connection.execute(
            "SELECT * FROM atoms WHERE ticket_id = ? ORDER BY order_index, atom_id",
            (ticket_id,),
        ).fetchall()
        atoms = [
            KnowledgeAtom(
                atom_id=row["atom_id"],
                type=AtomType(row["atom_type"]),
                label=row["label"],
                text=row["text"],
                keywords=self._json_load(row["keywords_json"]),
                weight=float(row["weight"]),
                dependencies=self._json_load(row["dependencies_json"]),
                parent_atom_id=row["parent_atom_id"],
                confidence=float(row["confidence"] or 0.0),
                source_excerpt=row["source_excerpt"] or "",
            )
            for row in atom_rows
        ]

        skill_rows = self.connection.execute("SELECT * FROM skills WHERE ticket_id = ? ORDER BY priority DESC, skill_id", (ticket_id,)).fetchall()
        skills = [
            TicketSkill(
                skill_id=row["skill_id"],
                code=SkillCode(row["skill_code"]),
                title=row["title"],
                description=row["description"],
                target_atom_ids=self._json_load(row["target_atom_ids_json"]),
                weight=float(row["weight"]),
                priority=int(row["priority"]),
            )
            for row in skill_rows
        ]

        template_rows = self.connection.execute(
            "SELECT * FROM exercise_templates WHERE ticket_id = ? ORDER BY template_id",
            (ticket_id,),
        ).fetchall()
        templates = [
            ExerciseTemplate(
                template_id=row["template_id"],
                exercise_type=ExerciseType(row["exercise_type"]),
                title=row["title"],
                instructions=row["instructions"],
                target_atom_ids=self._json_load(row["target_atom_ids_json"]),
                target_skill_codes=[SkillCode(value) for value in self._json_load(row["target_skill_codes_json"])],
                llm_required=bool(row["llm_required"]),
                rule_based_available=bool(row["rule_based_available"]),
                difficulty_delta=int(row["difficulty_delta"]),
            )
            for row in template_rows
        ]

        rubric_rows = self.connection.execute(
            "SELECT * FROM scoring_rubrics WHERE ticket_id = ? ORDER BY criterion_id",
            (ticket_id,),
        ).fetchall()
        rubric = [
            ScoringCriterion(
                criterion_id=row["criterion_id"],
                skill_code=SkillCode(row["skill_code"]),
                mastery_field=row["mastery_field"],
                description=row["description"],
                max_score=float(row["max_score"]),
                weight=float(row["weight"]),
            )
            for row in rubric_rows
        ]

        prompt_rows = self.connection.execute(
            "SELECT * FROM examiner_prompts WHERE ticket_id = ? ORDER BY prompt_id",
            (ticket_id,),
        ).fetchall()
        prompts = [
            ExaminerPrompt(
                prompt_id=row["prompt_id"],
                title=row["title"],
                text=row["text"],
                target_skill_codes=[SkillCode(value) for value in self._json_load(row["target_skill_codes_json"]) if value in SkillCode._value2member_map_],
                target_atom_ids=self._json_load(row["target_atom_ids_json"]),
                llm_assisted=bool(row["llm_assisted"]),
            )
            for row in prompt_rows
        ]

        concept_rows = self.connection.execute(
            """
            SELECT ticket_concepts.concept_id AS concept_id,
                   cross_ticket_concepts.label AS concept_label,
                   ticket_concepts.related_ticket_ids_json AS related_ticket_ids_json,
                   ticket_concepts.rationale AS rationale,
                   ticket_concepts.strength AS strength
            FROM ticket_concepts
            JOIN cross_ticket_concepts ON cross_ticket_concepts.concept_id = ticket_concepts.concept_id
            WHERE ticket_concepts.ticket_id = ?
            ORDER BY ticket_concepts.strength DESC, ticket_concepts.concept_id
            """,
            (ticket_id,),
        ).fetchall()
        links = [
            CrossTicketLink(
                concept_id=row["concept_id"],
                concept_label=row["concept_label"],
                related_ticket_ids=self._json_load(row["related_ticket_ids_json"]),
                rationale=row["rationale"] or "",
                strength=float(row["strength"] or 0.0),
            )
            for row in concept_rows
        ]

        block_rows = self.connection.execute(
            "SELECT * FROM ticket_answer_blocks WHERE ticket_id = ? ORDER BY block_code",
            (ticket_id,),
        ).fetchall()
        answer_blocks = [
            TicketAnswerBlock(
                block_code=AnswerBlockCode(row["block_code"]),
                title=row["title"],
                expected_content=row["expected_content"],
                source_excerpt=row["source_excerpt"] or "",
                confidence=float(row["confidence"] or 0.0),
                llm_assisted=bool(row["llm_assisted"]),
                is_missing=bool(row["is_missing"]),
            )
            for row in block_rows
        ]

        return TicketKnowledgeMap(
            ticket_id=ticket_row["ticket_id"],
            exam_id=ticket_row["exam_id"],
            section_id=ticket_row["section_id"],
            source_document_id=ticket_row["source_document_id"],
            title=ticket_row["title"],
            canonical_answer_summary=ticket_row["canonical_answer_summary"],
            atoms=atoms,
            skills=skills,
            exercise_templates=templates,
            scoring_rubric=rubric,
            examiner_prompts=prompts,
            cross_links_to_other_tickets=links,
            difficulty=int(ticket_row["difficulty"]),
            estimated_oral_time_sec=int(ticket_row["estimated_oral_time_sec"]),
            source_confidence=float(ticket_row["source_confidence"] or 0.0),
            answer_profile_code=AnswerProfileCode(ticket_row["answer_profile_code"] or AnswerProfileCode.STANDARD_TICKET),
            answer_blocks=answer_blocks,
        )

    def load_statistics_snapshot(self) -> StatisticsSnapshot:
        average_score_row = self.connection.execute(
            "SELECT AVG(confidence_score) AS avg_score FROM ticket_mastery_profiles"
        ).fetchone()
        processed_row = self.connection.execute("SELECT COUNT(*) AS total FROM tickets").fetchone()
        weak_row = self.connection.execute("SELECT COUNT(*) AS total FROM weak_areas").fetchone()
        sessions_row = self.connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM attempts
            WHERE created_at >= datetime('now', '-7 days')
            """
        ).fetchone()
        recent_rows = self.connection.execute(
            """
            SELECT tickets.title AS title, attempts.created_at AS created_at, attempts.score AS score
            FROM attempts
            JOIN tickets ON tickets.ticket_id = attempts.ticket_id
            ORDER BY attempts.created_at DESC
            LIMIT 3
            """
        ).fetchall()
        recent_sessions = [
            SessionData(
                title=self._compact_title(row["title"], 28),
                timestamp=self._format_dt(row["created_at"]),
                score=int(round(float(row["score"] or 0.0) * 100)),
                tone=self._score_tone(float(row["score"] or 0.0)),
            )
            for row in recent_rows
        ]
        return StatisticsSnapshot(
            average_score=int(round(float(average_score_row["avg_score"] or 0.0) * 100)),
            processed_tickets=int(processed_row["total"] or 0),
            weak_areas=int(weak_row["total"] or 0),
            sessions_week=int(sessions_row["total"] or 0),
            recent_sessions=recent_sessions,
        )

    def load_state_exam_statistics(self) -> StateExamStatisticsSnapshot:
        ticket_rows = self.connection.execute(
            """
            SELECT ticket_id
            FROM tickets
            WHERE answer_profile_code = ?
            """,
            (AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN.value,),
        ).fetchall()
        if not ticket_rows:
            return StateExamStatisticsSnapshot(active=False)

        block_rows = self.connection.execute(
            """
            SELECT *
            FROM ticket_block_mastery_profiles
            JOIN tickets ON tickets.ticket_id = ticket_block_mastery_profiles.ticket_id
            WHERE tickets.answer_profile_code = ?
            """,
            (AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN.value,),
        ).fetchall()
        block_scores = {
            "Введение": self._avg_percent(block_rows, "intro_mastery"),
            "Теория": self._avg_percent(block_rows, "theory_mastery"),
            "Практика": self._avg_percent(block_rows, "practice_mastery"),
            "Навыки": self._avg_percent(block_rows, "skills_mastery"),
            "Заключение": self._avg_percent(block_rows, "conclusion_mastery"),
            "Доп. элементы": self._avg_percent(block_rows, "extra_mastery"),
        }

        criterion_rows = self.connection.execute(
            """
            SELECT criterion_scores_json
            FROM attempt_block_scores
            JOIN attempts ON attempts.attempt_id = attempt_block_scores.attempt_id
            JOIN tickets ON tickets.ticket_id = attempts.ticket_id
            WHERE tickets.answer_profile_code = ?
            """,
            (AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN.value,),
        ).fetchall()
        criterion_values: dict[str, list[float]] = {
            criterion.value: [] for criterion in AnswerCriterionCode
        }
        for row in criterion_rows:
            payload = json.loads(row["criterion_scores_json"] or "{}")
            for key, value in payload.items():
                if key in criterion_values:
                    criterion_values[key].append(float(value))
        criterion_scores = {
            self._criterion_display_name(code): int(round((sum(values) / len(values)) * 100))
            for code, values in criterion_values.items()
            if values
        }

        missing_rows = self.connection.execute(
            """
            SELECT block_code, COUNT(*) AS total
            FROM ticket_answer_blocks
            JOIN tickets ON tickets.ticket_id = ticket_answer_blocks.ticket_id
            WHERE tickets.answer_profile_code = ? AND is_missing = 1
            GROUP BY block_code
            """,
            (AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN.value,),
        ).fetchall()
        missing_blocks = {
            self._block_display_name(row["block_code"]): int(row["total"] or 0)
            for row in missing_rows
        }
        return StateExamStatisticsSnapshot(
            active=True,
            block_scores=block_scores,
            criterion_scores=criterion_scores,
            missing_blocks=missing_blocks,
        )

    def load_profiles(self) -> dict[str, float]:
        rows = self.connection.execute(
            "SELECT ticket_id, confidence_score FROM ticket_mastery_profiles"
        ).fetchall()
        return {row["ticket_id"]: float(row["confidence_score"] or 0.0) for row in rows}

    def load_mastery_breakdowns(self) -> dict[str, TicketMasteryBreakdown]:
        rows = self.connection.execute(
            """
            SELECT ticket_mastery_profiles.*, tickets.answer_profile_code,
                   COALESCE(ticket_block_mastery_profiles.intro_mastery, 0) AS intro_mastery,
                   COALESCE(ticket_block_mastery_profiles.theory_mastery, 0) AS theory_mastery,
                   COALESCE(ticket_block_mastery_profiles.practice_mastery, 0) AS practice_mastery,
                   COALESCE(ticket_block_mastery_profiles.skills_mastery, 0) AS skills_mastery,
                   COALESCE(ticket_block_mastery_profiles.conclusion_mastery, 0) AS conclusion_mastery,
                   COALESCE(ticket_block_mastery_profiles.extra_mastery, 0) AS extra_mastery,
                   COALESCE(ticket_block_mastery_profiles.overall_score, 0) AS state_exam_overall_score
            FROM ticket_mastery_profiles
            LEFT JOIN tickets ON tickets.ticket_id = ticket_mastery_profiles.ticket_id
            LEFT JOIN ticket_block_mastery_profiles
                ON ticket_block_mastery_profiles.user_id = ticket_mastery_profiles.user_id
               AND ticket_block_mastery_profiles.ticket_id = ticket_mastery_profiles.ticket_id
            """
        ).fetchall()
        return {
            row["ticket_id"]: TicketMasteryBreakdown(
                ticket_id=row["ticket_id"],
                answer_profile_code=row["answer_profile_code"] or AnswerProfileCode.STANDARD_TICKET.value,
                definition_mastery=float(row["definition_mastery"] or 0.0),
                structure_mastery=float(row["structure_mastery"] or 0.0),
                examples_mastery=float(row["examples_mastery"] or 0.0),
                feature_mastery=float(row["feature_mastery"] or 0.0),
                process_mastery=float(row["process_mastery"] or 0.0),
                oral_short_mastery=float(row["oral_short_mastery"] or 0.0),
                oral_full_mastery=float(row["oral_full_mastery"] or 0.0),
                followup_mastery=float(row["followup_mastery"] or 0.0),
                confidence_score=float(row["confidence_score"] or 0.0),
                intro_mastery=float(row["intro_mastery"] or 0.0),
                theory_mastery=float(row["theory_mastery"] or 0.0),
                practice_mastery=float(row["practice_mastery"] or 0.0),
                skills_mastery=float(row["skills_mastery"] or 0.0),
                conclusion_mastery=float(row["conclusion_mastery"] or 0.0),
                extra_mastery=float(row["extra_mastery"] or 0.0),
                state_exam_overall_score=float(row["state_exam_overall_score"] or 0.0),
            )
            for row in rows
        }

    def load_training_snapshot(self, limit: int = 8) -> TrainingSnapshot:
        queue_rows = self.connection.execute(
            """
            SELECT spaced_review_queue.ticket_id AS ticket_id,
                   tickets.title AS title,
                   spaced_review_queue.reference_type AS reference_type,
                   spaced_review_queue.reference_id AS reference_id,
                   spaced_review_queue.priority AS priority,
                   spaced_review_queue.due_at AS due_at
            FROM spaced_review_queue
            JOIN tickets ON tickets.ticket_id = spaced_review_queue.ticket_id
            ORDER BY spaced_review_queue.priority DESC, spaced_review_queue.due_at
            LIMIT ?
            """,
            (max(1, min(limit, 24)),),
        ).fetchall()
        queue = [
            TrainingQueueItem(
                ticket_id=row["ticket_id"],
                ticket_title=self._compact_title(row["title"], 46),
                reference_type=self._display_queue_reference(row["reference_type"]),
                reference_id=row["reference_id"],
                priority=float(row["priority"]),
                due_label=self._format_dt(row["due_at"]),
            )
            for row in queue_rows
        ]
        return TrainingSnapshot(queue_items=queue, tickets=self.load_ticket_maps())

    def load_weak_areas(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM weak_areas ORDER BY severity DESC, last_detected_at DESC"
        ).fetchall()

    def load_latest_import_result(self) -> ImportExecutionResult:
        row = self.connection.execute(
            """
            SELECT *
            FROM source_documents
            ORDER BY COALESCE(last_attempted_at, imported_at) DESC, imported_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return ImportExecutionResult(False)

        queue_counts = {
            status_row["llm_status"]: int(status_row["total"] or 0)
            for status_row in self.connection.execute(
                """
                SELECT llm_status, COUNT(*) AS total
                FROM import_ticket_queue
                WHERE document_id = ?
                GROUP BY llm_status
                """,
                (row["document_id"],),
            ).fetchall()
        }
        warnings = self._json_load(row["warnings_json"]) if "warnings_json" in row.keys() else []
        ticket_total = int(row["ticket_total"] or 0)
        if not ticket_total:
            ticket_total_row = self.connection.execute(
                "SELECT COUNT(*) AS total FROM tickets WHERE source_document_id = ?",
                (row["document_id"],),
            ).fetchone()
            ticket_total = int(ticket_total_row["total"] or 0)

        llm_done = int(queue_counts.get("done", 0))
        llm_pending = int(queue_counts.get("pending", 0))
        llm_fallback = int(queue_counts.get("fallback", 0))
        llm_failed = int(queue_counts.get("failed", 0))

        status = row["status"] or "imported"
        legacy_resumable = not queue_counts and ticket_total > 0 and not bool(row["used_llm_assist"])
        legacy_fallback = legacy_resumable and any("LLM structuring fallback" in warning for warning in warnings)
        if legacy_resumable:
            if legacy_fallback:
                llm_fallback = max(ticket_total - llm_done, 1)
            else:
                llm_pending = max(ticket_total - llm_done, 1)
            status = "partial_llm" if status == "structured" else status
        elif not queue_counts and ticket_total:
            llm_done = int(ticket_total)

        resume_available = bool(
            status in {"importing", "partial_llm", "failed"} and (llm_pending or llm_fallback or llm_failed)
        )
        return ImportExecutionResult(
            ok=status in {"structured", "partial_llm", "importing"} or bool(ticket_total),
            document_id=row["document_id"],
            document_title=self._display_document_title(row["title"]),
            status=status,
            answer_profile_code=row["answer_profile_code"] or AnswerProfileCode.STANDARD_TICKET.value,
            answer_profile_label=answer_profile_label(row["answer_profile_code"]),
            tickets_created=ticket_total,
            sections_created=int(
                self.connection.execute(
                    "SELECT COUNT(DISTINCT section_id) AS total FROM tickets WHERE source_document_id = ?",
                    (row["document_id"],),
                ).fetchone()["total"] or 0
            ),
            warnings=warnings,
            used_llm_assist=bool(row["used_llm_assist"]) if "used_llm_assist" in row.keys() else False,
            llm_done_tickets=llm_done,
            llm_pending_tickets=llm_pending,
            llm_fallback_tickets=llm_fallback,
            llm_failed_tickets=llm_failed,
            resume_available=resume_available,
            error=row["last_error"] or "",
        )

    @staticmethod
    def _json_load(raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        return list(json.loads(raw_value))

    @staticmethod
    def _format_dt(raw_value: str | None) -> str:
        if not raw_value:
            return "Нет данных"
        try:
            dt = datetime.fromisoformat(raw_value)
        except ValueError:
            return raw_value
        return dt.strftime("%d.%m.%Y %H:%M")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} Б"
        if size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.0f} КБ"
        return f"{size_bytes / (1024 ** 2):.1f} МБ"

    @staticmethod
    def _display_status(status: str | None) -> str:
        mapping = {
            "structured": "Обработан",
            "imported": "Импортирован",
            "importing": "Импорт идёт",
            "partial_llm": "Частично доработан",
            "failed": "Импорт с ошибкой",
        }
        return mapping.get(status, status or "Неизвестно")

    @staticmethod
    def _display_subject(subject_id: str | None) -> str:
        if not subject_id:
            return "Без предмета"
        text = subject_id.replace("-", " ").replace("_", " ").strip()
        tokens = [token for token in text.split() if token.lower() not in {"ru", "rus"}]
        text = " ".join(tokens) if tokens else text
        if not text:
            return "Без предмета"
        return text[:1].upper() + text[1:] if text == text.lower() else text

    @staticmethod
    def _display_document_title(title: str | None) -> str:
        if not title:
            return "Импортированный документ"
        text = title.replace("_", " ").replace("-", " ").strip()
        tokens = [token for token in text.split() if token.lower() not in {"ru", "rus"}]
        text = " ".join(tokens) if tokens else text
        if not text:
            return "Импортированный документ"
        return text[:1].upper() + text[1:] if text == text.lower() else text

    @staticmethod
    def _display_section_title(title: str | None) -> str:
        if not title:
            return "Основной раздел"
        if title.strip().lower() == "imported section":
            return "Основной раздел"
        return title

    @staticmethod
    def _avg_percent(rows: list[sqlite3.Row], field_name: str) -> int:
        if not rows:
            return 0
        values = [float(row[field_name] or 0.0) for row in rows]
        return int(round((sum(values) / len(values)) * 100))

    @staticmethod
    def _criterion_display_name(code: str) -> str:
        mapping = {
            AnswerCriterionCode.COMPLETENESS.value: "Полнота",
            AnswerCriterionCode.DEPTH.value: "Глубина анализа",
            AnswerCriterionCode.STRUCTURE.value: "Логичность и структура",
            AnswerCriterionCode.PRACTICAL.value: "Практическая направленность",
            AnswerCriterionCode.ORIGINALITY.value: "Оригинальность",
            AnswerCriterionCode.COMPETENCE.value: "Соответствие компетенциям",
        }
        return mapping.get(code, code)

    @staticmethod
    def _block_display_name(code: str) -> str:
        mapping = {
            AnswerBlockCode.INTRO.value: "Введение",
            AnswerBlockCode.THEORY.value: "Теория",
            AnswerBlockCode.PRACTICE.value: "Практика",
            AnswerBlockCode.SKILLS.value: "Навыки",
            AnswerBlockCode.CONCLUSION.value: "Заключение",
            AnswerBlockCode.EXTRA.value: "Дополнительные элементы",
        }
        return mapping.get(code, code)

    @staticmethod
    def _display_ticket_title(title: str | None) -> str:
        if not title:
            return "Билет без названия"
        text = title.strip()
        if len(text) > 96:
            return text[:93].rstrip() + "..."
        return text

    @staticmethod
    def _compact_title(title: str | None, limit: int) -> str:
        if not title:
            return "Билет без названия"
        text = title.strip()
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."

    @staticmethod
    def _display_queue_reference(reference_type: str | None) -> str:
        mapping = {
            "ticket": "билет",
            "concept": "концепт",
            "section": "раздел",
            "skill": "навык",
            "atom": "атом",
        }
        return mapping.get(reference_type or "", reference_type or "элемент")

    @staticmethod
    def _score_tone(score: float) -> str:
        if score >= 0.8:
            return "success"
        if score >= 0.55:
            return "warning"
        return "danger"
