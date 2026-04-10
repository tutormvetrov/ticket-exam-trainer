from __future__ import annotations

import json
import sqlite3

from domain.knowledge import (
    AttemptRecord,
    Exam,
    ExerciseInstance,
    Section,
    SourceDocument,
    SpacedReviewItem,
    TicketKnowledgeMap,
    TicketMasteryProfile,
    WeakArea,
)
from application.import_service import ContentChunk, StructuredImportResult


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class KnowledgeRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_exam(self, exam: Exam) -> None:
        self.connection.execute(
            """
            INSERT INTO exams (exam_id, title, description, total_tickets, subject_area)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(exam_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                total_tickets = excluded.total_tickets,
                subject_area = excluded.subject_area
            """,
            (exam.exam_id, exam.title, exam.description, exam.total_tickets, exam.subject_area),
        )

    def save_section(self, section: Section) -> None:
        self.connection.execute(
            """
            INSERT INTO sections (section_id, exam_id, title, order_index, description)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(section_id) DO UPDATE SET
                exam_id = excluded.exam_id,
                title = excluded.title,
                order_index = excluded.order_index,
                description = excluded.description
            """,
            (section.section_id, section.exam_id, section.title, section.order_index, section.description),
        )

    def save_source_document(self, document: SourceDocument, raw_text: str = "", status: str = "imported") -> None:
        self.connection.execute(
            """
            INSERT INTO source_documents (
                document_id, exam_id, subject_id, title, file_path, file_type, size_bytes,
                checksum, imported_at, raw_text, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                exam_id = excluded.exam_id,
                subject_id = excluded.subject_id,
                title = excluded.title,
                file_path = excluded.file_path,
                file_type = excluded.file_type,
                size_bytes = excluded.size_bytes,
                checksum = excluded.checksum,
                imported_at = excluded.imported_at,
                raw_text = excluded.raw_text,
                status = excluded.status
            """,
            (
                document.document_id,
                document.exam_id,
                document.subject_id,
                document.title,
                document.file_path,
                document.file_type,
                document.size_bytes,
                document.checksum,
                document.imported_at.isoformat(),
                raw_text,
                status,
            ),
        )

    def save_ticket_map(self, ticket: TicketKnowledgeMap) -> None:
        ticket.validate()
        self.connection.execute(
            """
            INSERT INTO tickets (
                ticket_id, exam_id, section_id, source_document_id, title,
                canonical_answer_summary, difficulty, estimated_oral_time_sec, source_confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticket_id) DO UPDATE SET
                exam_id = excluded.exam_id,
                section_id = excluded.section_id,
                source_document_id = excluded.source_document_id,
                title = excluded.title,
                canonical_answer_summary = excluded.canonical_answer_summary,
                difficulty = excluded.difficulty,
                estimated_oral_time_sec = excluded.estimated_oral_time_sec,
                source_confidence = excluded.source_confidence
            """,
            (
                ticket.ticket_id,
                ticket.exam_id,
                ticket.section_id,
                ticket.source_document_id,
                ticket.title,
                ticket.canonical_answer_summary,
                ticket.difficulty,
                ticket.estimated_oral_time_sec,
                ticket.source_confidence,
            ),
        )

        self._clear_ticket_children(ticket.ticket_id)
        self._save_atoms(ticket)
        self._save_skills(ticket)
        self._save_exercise_templates(ticket)
        self._save_scoring_rubrics(ticket)
        self._save_examiner_prompts(ticket)
        self._save_concepts(ticket)
        self.connection.commit()

    def save_chunks(self, document_id: str, chunks: list[ContentChunk]) -> None:
        self.connection.execute("DELETE FROM content_chunks WHERE document_id = ?", (document_id,))
        for chunk in chunks:
            self.connection.execute(
                """
                INSERT INTO content_chunks (
                    chunk_id, document_id, chunk_index, text, normalized_text,
                    confidence, section_guess, ticket_guess
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    document_id,
                    chunk.index,
                    chunk.text,
                    chunk.normalized_text,
                    chunk.confidence,
                    chunk.section_guess,
                    chunk.ticket_guess,
                ),
            )

    def save_import_result(self, result: StructuredImportResult, exam: Exam, sections: list[Section]) -> None:
        self.save_exam(exam)
        for section in sections:
            self.save_section(section)
        self.save_source_document(result.source_document, raw_text=result.normalized_text, status="structured")
        self.save_chunks(result.source_document.document_id, result.chunks)
        for ticket in result.tickets:
            self.save_ticket_map(ticket)
        for instances in result.exercise_instances.values():
            self.save_exercise_instances(instances)
        self.connection.commit()

    def save_exercise_instances(self, instances: list[ExerciseInstance]) -> None:
        for instance in instances:
            self.connection.execute(
                """
                INSERT INTO exercise_instances (
                    exercise_id, ticket_id, template_id, exercise_type, prompt_text,
                    expected_answer, target_atom_ids_json, target_skill_codes_json,
                    used_llm, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exercise_id) DO UPDATE SET
                    prompt_text = excluded.prompt_text,
                    expected_answer = excluded.expected_answer,
                    target_atom_ids_json = excluded.target_atom_ids_json,
                    target_skill_codes_json = excluded.target_skill_codes_json,
                    used_llm = excluded.used_llm,
                    created_at = excluded.created_at
                """,
                (
                    instance.exercise_id,
                    instance.ticket_id,
                    instance.template_id,
                    instance.exercise_type.value,
                    instance.prompt_text,
                    instance.expected_answer,
                    _json_dump(instance.target_atom_ids),
                    _json_dump([code.value for code in instance.target_skill_codes]),
                    int(instance.used_llm),
                    instance.created_at.isoformat(),
                ),
            )

    def save_attempt(self, attempt: AttemptRecord) -> None:
        self.connection.execute(
            """
            INSERT INTO attempts (
                attempt_id, exercise_id, ticket_id, user_answer, score, mastery_delta,
                weak_atom_ids_json, weak_skill_codes_json, feedback, used_llm, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(attempt_id) DO UPDATE SET
                user_answer = excluded.user_answer,
                score = excluded.score,
                mastery_delta = excluded.mastery_delta,
                weak_atom_ids_json = excluded.weak_atom_ids_json,
                weak_skill_codes_json = excluded.weak_skill_codes_json,
                feedback = excluded.feedback,
                used_llm = excluded.used_llm,
                created_at = excluded.created_at
            """,
            (
                attempt.attempt_id,
                attempt.exercise_id,
                attempt.ticket_id,
                attempt.user_answer,
                attempt.score,
                attempt.mastery_delta,
                _json_dump(attempt.weak_atom_ids),
                _json_dump([code.value for code in attempt.weak_skill_codes]),
                attempt.feedback,
                int(attempt.used_llm),
                attempt.created_at.isoformat(),
            ),
        )
        self.connection.commit()

    def save_mastery_profile(self, profile: TicketMasteryProfile) -> None:
        self.connection.execute(
            """
            INSERT INTO ticket_mastery_profiles (
                user_id, ticket_id, definition_mastery, structure_mastery, examples_mastery,
                feature_mastery, process_mastery, oral_short_mastery, oral_full_mastery,
                followup_mastery, confidence_score, last_reviewed_at, next_review_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, ticket_id) DO UPDATE SET
                definition_mastery = excluded.definition_mastery,
                structure_mastery = excluded.structure_mastery,
                examples_mastery = excluded.examples_mastery,
                feature_mastery = excluded.feature_mastery,
                process_mastery = excluded.process_mastery,
                oral_short_mastery = excluded.oral_short_mastery,
                oral_full_mastery = excluded.oral_full_mastery,
                followup_mastery = excluded.followup_mastery,
                confidence_score = excluded.confidence_score,
                last_reviewed_at = excluded.last_reviewed_at,
                next_review_at = excluded.next_review_at
            """,
            (
                profile.user_id,
                profile.ticket_id,
                profile.definition_mastery,
                profile.structure_mastery,
                profile.examples_mastery,
                profile.feature_mastery,
                profile.process_mastery,
                profile.oral_short_mastery,
                profile.oral_full_mastery,
                profile.followup_mastery,
                profile.confidence_score,
                profile.last_reviewed_at.isoformat() if profile.last_reviewed_at else None,
                profile.next_review_at.isoformat() if profile.next_review_at else None,
            ),
        )
        self.connection.commit()

    def save_weak_areas(self, user_id: str, ticket_id: str, weak_areas: list[WeakArea]) -> None:
        self.connection.execute("DELETE FROM weak_areas WHERE user_id = ?", (user_id,))
        for weak_area in weak_areas:
            self.connection.execute(
                """
                INSERT INTO weak_areas (
                    weak_area_id, user_id, kind, reference_id, title,
                    severity, evidence, related_ticket_ids_json, last_detected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    weak_area.weak_area_id,
                    weak_area.user_id,
                    weak_area.kind.value,
                    weak_area.reference_id,
                    weak_area.title,
                    weak_area.severity,
                    weak_area.evidence,
                    _json_dump(weak_area.related_ticket_ids),
                    weak_area.last_detected_at.isoformat(),
                ),
            )
        self.connection.commit()

    def save_review_queue(self, user_id: str, queue: list[SpacedReviewItem]) -> None:
        self.connection.execute("DELETE FROM spaced_review_queue WHERE user_id = ?", (user_id,))
        for item in queue:
            self.connection.execute(
                """
                INSERT INTO spaced_review_queue (
                    review_item_id, user_id, ticket_id, reference_type, reference_id,
                    mode, priority, due_at, scheduled_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.review_item_id,
                    item.user_id,
                    item.ticket_id,
                    item.reference_type,
                    item.reference_id,
                    item.mode.value,
                    item.priority,
                    item.due_at.isoformat(),
                    item.scheduled_at.isoformat(),
                ),
            )
        self.connection.commit()

    def count_rows(self, table_name: str) -> int:
        row = self.connection.execute(f"SELECT COUNT(*) AS total FROM {table_name}").fetchone()
        return int(row["total"])

    def _clear_ticket_children(self, ticket_id: str) -> None:
        for table_name in [
            "atoms",
            "skills",
            "exercise_templates",
            "scoring_rubrics",
            "examiner_prompts",
            "ticket_concepts",
        ]:
            self.connection.execute(f"DELETE FROM {table_name} WHERE ticket_id = ?", (ticket_id,))

    def _save_atoms(self, ticket: TicketKnowledgeMap) -> None:
        for index, atom in enumerate(ticket.atoms):
            self.connection.execute(
                """
                INSERT INTO atoms (
                    atom_id, ticket_id, atom_type, label, text, keywords_json, weight,
                    dependencies_json, parent_atom_id, confidence, source_excerpt, order_index
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    atom.atom_id,
                    ticket.ticket_id,
                    atom.type.value,
                    atom.label,
                    atom.text,
                    _json_dump(atom.keywords),
                    atom.weight,
                    _json_dump(atom.dependencies),
                    atom.parent_atom_id,
                    atom.confidence,
                    atom.source_excerpt,
                    index,
                ),
            )

    def _save_skills(self, ticket: TicketKnowledgeMap) -> None:
        for skill in ticket.skills:
            self.connection.execute(
                """
                INSERT INTO skills (
                    skill_id, ticket_id, skill_code, title, description,
                    target_atom_ids_json, weight, priority
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    skill.skill_id,
                    ticket.ticket_id,
                    skill.code.value,
                    skill.title,
                    skill.description,
                    _json_dump(skill.target_atom_ids),
                    skill.weight,
                    skill.priority,
                ),
            )

    def _save_exercise_templates(self, ticket: TicketKnowledgeMap) -> None:
        for template in ticket.exercise_templates:
            self.connection.execute(
                """
                INSERT INTO exercise_templates (
                    template_id, ticket_id, exercise_type, title, instructions,
                    target_atom_ids_json, target_skill_codes_json, llm_required,
                    rule_based_available, difficulty_delta
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.template_id,
                    ticket.ticket_id,
                    template.exercise_type.value,
                    template.title,
                    template.instructions,
                    _json_dump(template.target_atom_ids),
                    _json_dump([code.value for code in template.target_skill_codes]),
                    int(template.llm_required),
                    int(template.rule_based_available),
                    template.difficulty_delta,
                ),
            )

    def _save_scoring_rubrics(self, ticket: TicketKnowledgeMap) -> None:
        for criterion in ticket.scoring_rubric:
            self.connection.execute(
                """
                INSERT INTO scoring_rubrics (
                    criterion_id, ticket_id, skill_code, mastery_field, description, max_score, weight
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    criterion.criterion_id,
                    ticket.ticket_id,
                    criterion.skill_code.value,
                    criterion.mastery_field,
                    criterion.description,
                    criterion.max_score,
                    criterion.weight,
                ),
            )

    def _save_examiner_prompts(self, ticket: TicketKnowledgeMap) -> None:
        for prompt in ticket.examiner_prompts:
            self.connection.execute(
                """
                INSERT INTO examiner_prompts (
                    prompt_id, ticket_id, title, text, target_skill_codes_json, target_atom_ids_json, llm_assisted
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prompt.prompt_id,
                    ticket.ticket_id,
                    prompt.title,
                    prompt.text,
                    _json_dump([code.value for code in prompt.target_skill_codes]),
                    _json_dump(prompt.target_atom_ids),
                    int(prompt.llm_assisted),
                ),
            )

    def _save_concepts(self, ticket: TicketKnowledgeMap) -> None:
        for link in ticket.cross_links_to_other_tickets:
            normalized = link.concept_label.strip().lower()
            self.connection.execute(
                """
                INSERT INTO cross_ticket_concepts (
                    concept_id, label, normalized_label, description, strength, confidence
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(concept_id) DO UPDATE SET
                    label = excluded.label,
                    normalized_label = excluded.normalized_label,
                    strength = excluded.strength,
                    confidence = excluded.confidence
                """,
                (
                    link.concept_id,
                    link.concept_label,
                    normalized,
                    "",
                    link.strength,
                    ticket.source_confidence,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO ticket_concepts (
                    ticket_id, concept_id, atom_ids_json, related_ticket_ids_json, rationale, strength
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket.ticket_id,
                    link.concept_id,
                    _json_dump([]),
                    _json_dump(link.related_ticket_ids),
                    link.rationale,
                    link.strength,
                ),
            )
