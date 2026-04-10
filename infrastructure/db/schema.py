from __future__ import annotations

import sqlite3


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS exams (
            exam_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            total_tickets INTEGER NOT NULL DEFAULT 0,
            subject_area TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS subjects (
            subject_id TEXT PRIMARY KEY,
            exam_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (exam_id) REFERENCES exams (exam_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sections (
            section_id TEXT PRIMARY KEY,
            exam_id TEXT NOT NULL,
            title TEXT NOT NULL,
            order_index INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (exam_id) REFERENCES exams (exam_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS source_documents (
            document_id TEXT PRIMARY KEY,
            exam_id TEXT NOT NULL,
            subject_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            checksum TEXT NOT NULL DEFAULT '',
            imported_at TEXT NOT NULL,
            raw_text TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'imported',
            FOREIGN KEY (exam_id) REFERENCES exams (exam_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS content_chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            normalized_text TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0,
            section_guess TEXT NOT NULL DEFAULT '',
            ticket_guess TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (document_id) REFERENCES source_documents (document_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            exam_id TEXT NOT NULL,
            section_id TEXT NOT NULL,
            source_document_id TEXT NOT NULL,
            title TEXT NOT NULL,
            canonical_answer_summary TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 1,
            estimated_oral_time_sec INTEGER NOT NULL DEFAULT 60,
            source_confidence REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'structured',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exam_id) REFERENCES exams (exam_id) ON DELETE CASCADE,
            FOREIGN KEY (section_id) REFERENCES sections (section_id) ON DELETE CASCADE,
            FOREIGN KEY (source_document_id) REFERENCES source_documents (document_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS atoms (
            atom_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            atom_type TEXT NOT NULL,
            label TEXT NOT NULL,
            text TEXT NOT NULL,
            keywords_json TEXT NOT NULL DEFAULT '[]',
            weight REAL NOT NULL,
            dependencies_json TEXT NOT NULL DEFAULT '[]',
            parent_atom_id TEXT,
            confidence REAL NOT NULL DEFAULT 0,
            source_excerpt TEXT NOT NULL DEFAULT '',
            order_index INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE,
            FOREIGN KEY (parent_atom_id) REFERENCES atoms (atom_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS skills (
            skill_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            skill_code TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            target_atom_ids_json TEXT NOT NULL DEFAULT '[]',
            weight REAL NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS exercise_templates (
            template_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            exercise_type TEXT NOT NULL,
            title TEXT NOT NULL,
            instructions TEXT NOT NULL,
            target_atom_ids_json TEXT NOT NULL DEFAULT '[]',
            target_skill_codes_json TEXT NOT NULL DEFAULT '[]',
            llm_required INTEGER NOT NULL DEFAULT 0,
            rule_based_available INTEGER NOT NULL DEFAULT 1,
            difficulty_delta INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS scoring_rubrics (
            criterion_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            skill_code TEXT NOT NULL,
            mastery_field TEXT NOT NULL,
            description TEXT NOT NULL,
            max_score REAL NOT NULL,
            weight REAL NOT NULL,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS examiner_prompts (
            prompt_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            target_skill_codes_json TEXT NOT NULL DEFAULT '[]',
            target_atom_ids_json TEXT NOT NULL DEFAULT '[]',
            llm_assisted INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS cross_ticket_concepts (
            concept_id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            normalized_label TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            strength REAL NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS ticket_concepts (
            ticket_id TEXT NOT NULL,
            concept_id TEXT NOT NULL,
            atom_ids_json TEXT NOT NULL DEFAULT '[]',
            related_ticket_ids_json TEXT NOT NULL DEFAULT '[]',
            rationale TEXT NOT NULL DEFAULT '',
            strength REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (ticket_id, concept_id),
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE,
            FOREIGN KEY (concept_id) REFERENCES cross_ticket_concepts (concept_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS exercise_instances (
            exercise_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            template_id TEXT NOT NULL,
            exercise_type TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            expected_answer TEXT NOT NULL,
            target_atom_ids_json TEXT NOT NULL DEFAULT '[]',
            target_skill_codes_json TEXT NOT NULL DEFAULT '[]',
            used_llm INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE,
            FOREIGN KEY (template_id) REFERENCES exercise_templates (template_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS study_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            exam_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY (exam_id) REFERENCES exams (exam_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attempts (
            attempt_id TEXT PRIMARY KEY,
            exercise_id TEXT NOT NULL,
            ticket_id TEXT NOT NULL,
            user_answer TEXT NOT NULL,
            score REAL NOT NULL,
            mastery_delta REAL NOT NULL DEFAULT 0,
            weak_atom_ids_json TEXT NOT NULL DEFAULT '[]',
            weak_skill_codes_json TEXT NOT NULL DEFAULT '[]',
            feedback TEXT NOT NULL DEFAULT '',
            used_llm INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (exercise_id) REFERENCES exercise_instances (exercise_id) ON DELETE CASCADE,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS weak_areas (
            weak_area_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            reference_id TEXT NOT NULL,
            title TEXT NOT NULL,
            severity REAL NOT NULL,
            evidence TEXT NOT NULL DEFAULT '',
            related_ticket_ids_json TEXT NOT NULL DEFAULT '[]',
            last_detected_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ticket_mastery_profiles (
            user_id TEXT NOT NULL,
            ticket_id TEXT NOT NULL,
            definition_mastery REAL NOT NULL DEFAULT 0,
            structure_mastery REAL NOT NULL DEFAULT 0,
            examples_mastery REAL NOT NULL DEFAULT 0,
            feature_mastery REAL NOT NULL DEFAULT 0,
            process_mastery REAL NOT NULL DEFAULT 0,
            oral_short_mastery REAL NOT NULL DEFAULT 0,
            oral_full_mastery REAL NOT NULL DEFAULT 0,
            followup_mastery REAL NOT NULL DEFAULT 0,
            confidence_score REAL NOT NULL DEFAULT 0,
            last_reviewed_at TEXT,
            next_review_at TEXT,
            PRIMARY KEY (user_id, ticket_id),
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS spaced_review_queue (
            review_item_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            ticket_id TEXT NOT NULL,
            reference_type TEXT NOT NULL,
            reference_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            priority REAL NOT NULL,
            due_at TEXT NOT NULL,
            scheduled_at TEXT NOT NULL,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sections_exam ON sections (exam_id);
        CREATE INDEX IF NOT EXISTS idx_documents_exam ON source_documents (exam_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_document ON content_chunks (document_id, chunk_index);
        CREATE INDEX IF NOT EXISTS idx_tickets_exam_section ON tickets (exam_id, section_id);
        CREATE INDEX IF NOT EXISTS idx_atoms_ticket ON atoms (ticket_id, order_index);
        CREATE INDEX IF NOT EXISTS idx_skills_ticket ON skills (ticket_id);
        CREATE INDEX IF NOT EXISTS idx_templates_ticket ON exercise_templates (ticket_id);
        CREATE INDEX IF NOT EXISTS idx_attempts_ticket ON attempts (ticket_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_weak_areas_user ON weak_areas (user_id, severity DESC);
        CREATE INDEX IF NOT EXISTS idx_review_queue_user_due ON spaced_review_queue (user_id, due_at, priority DESC);

        INSERT INTO schema_meta (key, value)
        VALUES ('schema_version', '2')
        ON CONFLICT(key) DO UPDATE SET value = excluded.value;
        """
    )
    connection.commit()
