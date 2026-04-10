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
            answer_profile_code TEXT NOT NULL DEFAULT 'standard_ticket',
            title TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            checksum TEXT NOT NULL DEFAULT '',
            imported_at TEXT NOT NULL,
            raw_text TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'imported',
            warnings_json TEXT NOT NULL DEFAULT '[]',
            used_llm_assist INTEGER NOT NULL DEFAULT 0,
            ticket_total INTEGER NOT NULL DEFAULT 0,
            tickets_llm_done INTEGER NOT NULL DEFAULT 0,
            last_attempted_at TEXT,
            last_error TEXT NOT NULL DEFAULT '',
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
            answer_profile_code TEXT NOT NULL DEFAULT 'standard_ticket',
            title TEXT NOT NULL,
            canonical_answer_summary TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 1,
            estimated_oral_time_sec INTEGER NOT NULL DEFAULT 60,
            source_confidence REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'structured',
            llm_status TEXT NOT NULL DEFAULT 'pending',
            llm_error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exam_id) REFERENCES exams (exam_id) ON DELETE CASCADE,
            FOREIGN KEY (section_id) REFERENCES sections (section_id) ON DELETE CASCADE,
            FOREIGN KEY (source_document_id) REFERENCES source_documents (document_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS import_ticket_queue (
            ticket_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            ticket_index INTEGER NOT NULL,
            section_id TEXT NOT NULL,
            title TEXT NOT NULL,
            body_text TEXT NOT NULL DEFAULT '',
            candidate_confidence REAL NOT NULL DEFAULT 0,
            llm_status TEXT NOT NULL DEFAULT 'pending',
            llm_error TEXT NOT NULL DEFAULT '',
            llm_attempted INTEGER NOT NULL DEFAULT 0,
            used_llm INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES source_documents (document_id) ON DELETE CASCADE
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

        CREATE TABLE IF NOT EXISTS ticket_answer_blocks (
            ticket_id TEXT NOT NULL,
            block_code TEXT NOT NULL,
            title TEXT NOT NULL,
            expected_content TEXT NOT NULL DEFAULT '',
            source_excerpt TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0,
            llm_assisted INTEGER NOT NULL DEFAULT 0,
            is_missing INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (ticket_id, block_code),
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attempt_block_scores (
            attempt_id TEXT NOT NULL,
            block_code TEXT NOT NULL,
            coverage_score REAL NOT NULL DEFAULT 0,
            criterion_scores_json TEXT NOT NULL DEFAULT '{}',
            feedback TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (attempt_id, block_code),
            FOREIGN KEY (attempt_id) REFERENCES attempts (attempt_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ticket_block_mastery_profiles (
            user_id TEXT NOT NULL,
            ticket_id TEXT NOT NULL,
            intro_mastery REAL NOT NULL DEFAULT 0,
            theory_mastery REAL NOT NULL DEFAULT 0,
            practice_mastery REAL NOT NULL DEFAULT 0,
            skills_mastery REAL NOT NULL DEFAULT 0,
            conclusion_mastery REAL NOT NULL DEFAULT 0,
            extra_mastery REAL NOT NULL DEFAULT 0,
            overall_score REAL NOT NULL DEFAULT 0,
            last_reviewed_at TEXT,
            next_review_at TEXT,
            PRIMARY KEY (user_id, ticket_id),
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

        CREATE TABLE IF NOT EXISTS dlc_license_state (
            singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
            install_id TEXT NOT NULL DEFAULT '',
            activated INTEGER NOT NULL DEFAULT 0,
            license_tier TEXT NOT NULL DEFAULT 'locked',
            token TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'locked',
            last_checked_at TEXT,
            activated_at TEXT,
            error_text TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS thesis_projects (
            project_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            degree TEXT NOT NULL DEFAULT '',
            specialty TEXT NOT NULL DEFAULT '',
            student_name TEXT NOT NULL DEFAULT '',
            supervisor_name TEXT NOT NULL DEFAULT '',
            defense_date TEXT,
            discipline_profile TEXT NOT NULL DEFAULT 'research',
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            recommended_model TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS thesis_sources (
            source_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            checksum TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1,
            imported_at TEXT NOT NULL,
            parse_status TEXT NOT NULL DEFAULT 'imported',
            confidence REAL NOT NULL DEFAULT 0,
            raw_text TEXT NOT NULL DEFAULT '',
            normalized_text TEXT NOT NULL DEFAULT '',
            unit_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES thesis_projects (project_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS defense_claims (
            claim_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            claim_kind TEXT NOT NULL,
            text TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            source_anchors_json TEXT NOT NULL DEFAULT '[]',
            llm_assisted INTEGER NOT NULL DEFAULT 0,
            needs_review INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT,
            FOREIGN KEY (project_id) REFERENCES thesis_projects (project_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS defense_outline_segments (
            segment_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            duration_label TEXT NOT NULL,
            order_index INTEGER NOT NULL,
            title TEXT NOT NULL,
            talking_points TEXT NOT NULL DEFAULT '',
            target_seconds INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES thesis_projects (project_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS defense_slide_cards (
            card_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            slide_index INTEGER NOT NULL,
            title TEXT NOT NULL,
            purpose TEXT NOT NULL DEFAULT '',
            talking_points_json TEXT NOT NULL DEFAULT '[]',
            evidence_links_json TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY (project_id) REFERENCES thesis_projects (project_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS defense_questions (
            question_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            persona_kind TEXT NOT NULL,
            topic TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 1,
            question_text TEXT NOT NULL,
            source_anchors_json TEXT NOT NULL DEFAULT '[]',
            risk_tag TEXT NOT NULL DEFAULT '',
            created_at TEXT,
            FOREIGN KEY (project_id) REFERENCES thesis_projects (project_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS defense_sessions (
            session_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            duration_sec INTEGER NOT NULL DEFAULT 0,
            transcript_text TEXT NOT NULL DEFAULT '',
            questions_json TEXT NOT NULL DEFAULT '[]',
            answers_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT,
            FOREIGN KEY (project_id) REFERENCES thesis_projects (project_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS defense_scores (
            score_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            structure_mastery REAL NOT NULL DEFAULT 0,
            relevance_clarity REAL NOT NULL DEFAULT 0,
            methodology_mastery REAL NOT NULL DEFAULT 0,
            novelty_mastery REAL NOT NULL DEFAULT 0,
            results_mastery REAL NOT NULL DEFAULT 0,
            limitations_honesty REAL NOT NULL DEFAULT 0,
            oral_clarity_text_mode REAL NOT NULL DEFAULT 0,
            followup_mastery REAL NOT NULL DEFAULT 0,
            summary_text TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES thesis_projects (project_id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES defense_sessions (session_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS defense_weak_areas (
            weak_area_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            severity REAL NOT NULL DEFAULT 0,
            evidence TEXT NOT NULL DEFAULT '',
            claim_kind TEXT,
            created_at TEXT,
            FOREIGN KEY (project_id) REFERENCES thesis_projects (project_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sections_exam ON sections (exam_id);
        CREATE INDEX IF NOT EXISTS idx_documents_exam ON source_documents (exam_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_document ON content_chunks (document_id, chunk_index);
        CREATE INDEX IF NOT EXISTS idx_tickets_exam_section ON tickets (exam_id, section_id);
        CREATE INDEX IF NOT EXISTS idx_import_queue_document_status ON import_ticket_queue (document_id, llm_status, ticket_index);
        CREATE INDEX IF NOT EXISTS idx_atoms_ticket ON atoms (ticket_id, order_index);
        CREATE INDEX IF NOT EXISTS idx_skills_ticket ON skills (ticket_id);
        CREATE INDEX IF NOT EXISTS idx_templates_ticket ON exercise_templates (ticket_id);
        CREATE INDEX IF NOT EXISTS idx_attempts_ticket ON attempts (ticket_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_ticket_answer_blocks_ticket ON ticket_answer_blocks (ticket_id, block_code);
        CREATE INDEX IF NOT EXISTS idx_attempt_block_scores_attempt ON attempt_block_scores (attempt_id, block_code);
        CREATE INDEX IF NOT EXISTS idx_weak_areas_user ON weak_areas (user_id, severity DESC);
        CREATE INDEX IF NOT EXISTS idx_review_queue_user_due ON spaced_review_queue (user_id, due_at, priority DESC);
        CREATE INDEX IF NOT EXISTS idx_thesis_sources_project ON thesis_sources (project_id, version, imported_at);
        CREATE INDEX IF NOT EXISTS idx_defense_claims_project ON defense_claims (project_id, claim_kind);
        CREATE INDEX IF NOT EXISTS idx_defense_outline_project ON defense_outline_segments (project_id, duration_label, order_index);
        CREATE INDEX IF NOT EXISTS idx_defense_questions_project ON defense_questions (project_id, persona_kind, difficulty DESC);
        CREATE INDEX IF NOT EXISTS idx_defense_scores_project ON defense_scores (project_id, created_at DESC);

        INSERT INTO schema_meta (key, value)
        VALUES ('schema_version', '4')
        ON CONFLICT(key) DO UPDATE SET value = excluded.value;
        """
    )
    _ensure_column(connection, "source_documents", "warnings_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(connection, "source_documents", "used_llm_assist", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "source_documents", "ticket_total", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "source_documents", "tickets_llm_done", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "source_documents", "last_attempted_at", "TEXT")
    _ensure_column(connection, "source_documents", "last_error", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(connection, "source_documents", "answer_profile_code", "TEXT NOT NULL DEFAULT 'standard_ticket'")
    _ensure_column(connection, "tickets", "llm_status", "TEXT NOT NULL DEFAULT 'pending'")
    _ensure_column(connection, "tickets", "llm_error", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(connection, "tickets", "answer_profile_code", "TEXT NOT NULL DEFAULT 'standard_ticket'")
    connection.commit()


def _ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    existing = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name in existing:
        return
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
