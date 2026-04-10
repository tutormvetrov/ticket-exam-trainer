from __future__ import annotations

from datetime import datetime
import json
import sqlite3

from application.ui_data import SectionOverviewItem, StatisticsSnapshot, TicketMasteryBreakdown, TrainingQueueItem, TrainingSnapshot
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
            SELECT document_id, title, file_type, subject_id, imported_at, size_bytes, status
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

    def load_profiles(self) -> dict[str, float]:
        rows = self.connection.execute(
            "SELECT ticket_id, confidence_score FROM ticket_mastery_profiles"
        ).fetchall()
        return {row["ticket_id"]: float(row["confidence_score"] or 0.0) for row in rows}

    def load_mastery_breakdowns(self) -> dict[str, TicketMasteryBreakdown]:
        rows = self.connection.execute("SELECT * FROM ticket_mastery_profiles").fetchall()
        return {
            row["ticket_id"]: TicketMasteryBreakdown(
                ticket_id=row["ticket_id"],
                definition_mastery=float(row["definition_mastery"] or 0.0),
                structure_mastery=float(row["structure_mastery"] or 0.0),
                examples_mastery=float(row["examples_mastery"] or 0.0),
                feature_mastery=float(row["feature_mastery"] or 0.0),
                process_mastery=float(row["process_mastery"] or 0.0),
                oral_short_mastery=float(row["oral_short_mastery"] or 0.0),
                oral_full_mastery=float(row["oral_full_mastery"] or 0.0),
                followup_mastery=float(row["followup_mastery"] or 0.0),
                confidence_score=float(row["confidence_score"] or 0.0),
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
