from __future__ import annotations

import json
import sqlite3

from domain.defense import (
    CommitteePersonaKind,
    DefenseClaim,
    DefenseClaimKind,
    DefenseQuestion,
    DefenseScoreProfile,
    DefenseSession,
    DefenseSessionMode,
    DefenseWeakArea,
    DlcLicenseState,
    DisciplineProfile,
    SlideStoryboardCard,
    ThesisProject,
    ThesisSource,
    ThesisSourceKind,
)


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class DefenseRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def load_license_state(self) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM dlc_license_state WHERE singleton_id = 1").fetchone()

    def save_license_state(self, state: DlcLicenseState) -> None:
        self.connection.execute(
            """
            INSERT INTO dlc_license_state (
                singleton_id, install_id, activated, license_tier, token, status,
                last_checked_at, activated_at, error_text
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(singleton_id) DO UPDATE SET
                install_id = excluded.install_id,
                activated = excluded.activated,
                license_tier = excluded.license_tier,
                token = excluded.token,
                status = excluded.status,
                last_checked_at = excluded.last_checked_at,
                activated_at = excluded.activated_at,
                error_text = excluded.error_text
            """,
            (
                state.install_id,
                int(state.activated),
                state.license_tier,
                state.token,
                state.status,
                state.last_checked_at.isoformat() if state.last_checked_at else None,
                state.activated_at.isoformat() if state.activated_at else None,
                state.error_text,
            ),
        )
        self.connection.commit()

    def save_project(self, project: ThesisProject) -> None:
        self.connection.execute(
            """
            INSERT INTO thesis_projects (
                project_id, title, degree, specialty, student_name, supervisor_name,
                defense_date, discipline_profile, status, created_at, updated_at, recommended_model
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                title = excluded.title,
                degree = excluded.degree,
                specialty = excluded.specialty,
                student_name = excluded.student_name,
                supervisor_name = excluded.supervisor_name,
                defense_date = excluded.defense_date,
                discipline_profile = excluded.discipline_profile,
                status = excluded.status,
                updated_at = excluded.updated_at,
                recommended_model = excluded.recommended_model
            """,
            (
                project.project_id,
                project.title,
                project.degree,
                project.specialty,
                project.student_name,
                project.supervisor_name,
                project.defense_date.isoformat() if project.defense_date else None,
                project.discipline_profile.value,
                project.status,
                project.created_at.isoformat(),
                project.updated_at.isoformat(),
                project.recommended_model,
            ),
        )
        self.connection.commit()

    def load_projects(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT thesis_projects.*,
                   COUNT(DISTINCT thesis_sources.source_id) AS source_count
            FROM thesis_projects
            LEFT JOIN thesis_sources ON thesis_sources.project_id = thesis_projects.project_id
            GROUP BY thesis_projects.project_id
            ORDER BY thesis_projects.updated_at DESC
            """
        ).fetchall()

    def load_project_row(self, project_id: str) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM thesis_projects WHERE project_id = ?", (project_id,)).fetchone()

    def save_sources(self, sources: list[ThesisSource]) -> None:
        for source in sources:
            self.connection.execute(
                """
                INSERT INTO thesis_sources (
                    source_id, project_id, kind, title, file_path, file_type, checksum, version,
                    imported_at, parse_status, confidence, raw_text, normalized_text, unit_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    kind = excluded.kind,
                    title = excluded.title,
                    file_path = excluded.file_path,
                    file_type = excluded.file_type,
                    checksum = excluded.checksum,
                    version = excluded.version,
                    imported_at = excluded.imported_at,
                    parse_status = excluded.parse_status,
                    confidence = excluded.confidence,
                    raw_text = excluded.raw_text,
                    normalized_text = excluded.normalized_text,
                    unit_count = excluded.unit_count
                """,
                (
                    source.source_id,
                    source.project_id,
                    source.kind.value,
                    source.title,
                    source.file_path,
                    source.file_type,
                    source.checksum,
                    source.version,
                    source.imported_at.isoformat(),
                    source.parse_status,
                    source.confidence,
                    source.raw_text,
                    source.normalized_text,
                    source.unit_count,
                ),
            )
        self.connection.commit()

    def load_sources(self, project_id: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM thesis_sources WHERE project_id = ? ORDER BY version, imported_at",
            (project_id,),
        ).fetchall()

    def replace_claims(self, project_id: str, claims: list[DefenseClaim]) -> None:
        self.connection.execute("DELETE FROM defense_claims WHERE project_id = ?", (project_id,))
        for claim in claims:
            self.connection.execute(
                """
                INSERT INTO defense_claims (
                    claim_id, project_id, claim_kind, text, confidence, source_anchors_json,
                    llm_assisted, needs_review, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim.claim_id,
                    project_id,
                    claim.kind.value,
                    claim.text,
                    claim.confidence,
                    _json_dump(claim.source_anchors),
                    int(claim.llm_assisted),
                    int(claim.needs_review),
                    claim.updated_at.isoformat() if claim.updated_at else None,
                ),
            )
        self.connection.commit()

    def load_claims(self, project_id: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM defense_claims WHERE project_id = ? ORDER BY claim_kind, claim_id",
            (project_id,),
        ).fetchall()

    def replace_outline(self, project_id: str, duration_label: str, segments: list[dict[str, object]]) -> None:
        self.connection.execute(
            "DELETE FROM defense_outline_segments WHERE project_id = ? AND duration_label = ?",
            (project_id, duration_label),
        )
        for index, segment in enumerate(segments, start=1):
            self.connection.execute(
                """
                INSERT INTO defense_outline_segments (
                    segment_id, project_id, duration_label, order_index, title, talking_points, target_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{project_id}-{duration_label}-{index}",
                    project_id,
                    duration_label,
                    index,
                    str(segment.get("title", "")).strip(),
                    str(segment.get("talking_points", "")).strip(),
                    int(segment.get("target_seconds", 0) or 0),
                ),
            )
        self.connection.commit()

    def load_outline_segments(self, project_id: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM defense_outline_segments WHERE project_id = ? ORDER BY duration_label, order_index",
            (project_id,),
        ).fetchall()

    def replace_slides(self, project_id: str, slides: list[SlideStoryboardCard]) -> None:
        self.connection.execute("DELETE FROM defense_slide_cards WHERE project_id = ?", (project_id,))
        for slide in slides:
            self.connection.execute(
                """
                INSERT INTO defense_slide_cards (
                    card_id, project_id, slide_index, title, purpose, talking_points_json, evidence_links_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slide.card_id,
                    project_id,
                    slide.slide_index,
                    slide.title,
                    slide.purpose,
                    _json_dump(slide.talking_points),
                    _json_dump(slide.evidence_links),
                ),
            )
        self.connection.commit()

    def load_slides(self, project_id: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM defense_slide_cards WHERE project_id = ? ORDER BY slide_index",
            (project_id,),
        ).fetchall()

    def replace_questions(self, project_id: str, questions: list[DefenseQuestion]) -> None:
        self.connection.execute("DELETE FROM defense_questions WHERE project_id = ?", (project_id,))
        for question in questions:
            self.connection.execute(
                """
                INSERT INTO defense_questions (
                    question_id, project_id, persona_kind, topic, difficulty, question_text,
                    source_anchors_json, risk_tag, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question.question_id,
                    project_id,
                    question.persona.value,
                    question.topic,
                    question.difficulty,
                    question.question_text,
                    _json_dump(question.source_anchors),
                    question.risk_tag,
                    question.created_at.isoformat() if question.created_at else None,
                ),
            )
        self.connection.commit()

    def load_questions(self, project_id: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM defense_questions WHERE project_id = ? ORDER BY persona_kind, difficulty DESC, question_id",
            (project_id,),
        ).fetchall()

    def save_session_bundle(
        self,
        session: DefenseSession,
        score: DefenseScoreProfile,
        weak_areas: list[DefenseWeakArea],
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO defense_sessions (
                session_id, project_id, mode, duration_sec, transcript_text, questions_json, answers_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.session_id,
                session.project_id,
                session.mode.value,
                session.duration_sec,
                session.transcript_text,
                _json_dump(session.questions),
                _json_dump(session.answers),
                session.created_at.isoformat() if session.created_at else None,
            ),
        )
        self.connection.execute(
            """
            INSERT INTO defense_scores (
                score_id, project_id, session_id, structure_mastery, relevance_clarity, methodology_mastery,
                novelty_mastery, results_mastery, limitations_honesty, oral_clarity_text_mode,
                followup_mastery, summary_text, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"score-{session.session_id}",
                score.project_id,
                score.session_id,
                score.structure_mastery,
                score.relevance_clarity,
                score.methodology_mastery,
                score.novelty_mastery,
                score.results_mastery,
                score.limitations_honesty,
                score.oral_clarity_text_mode,
                score.followup_mastery,
                score.summary_text,
                score.created_at.isoformat(),
            ),
        )
        self.connection.execute("DELETE FROM defense_weak_areas WHERE project_id = ?", (session.project_id,))
        for area in weak_areas:
            self.connection.execute(
                """
                INSERT INTO defense_weak_areas (
                    weak_area_id, project_id, kind, title, severity, evidence, claim_kind, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    area.weak_area_id,
                    area.project_id,
                    area.kind,
                    area.title,
                    area.severity,
                    area.evidence,
                    area.claim_kind.value if area.claim_kind else None,
                    area.created_at.isoformat() if area.created_at else None,
                ),
            )
        self.connection.commit()

    def load_latest_score(self, project_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM defense_scores WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()

    def load_weak_areas(self, project_id: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM defense_weak_areas WHERE project_id = ? ORDER BY severity DESC, created_at DESC",
            (project_id,),
        ).fetchall()

    @staticmethod
    def row_to_license(row: sqlite3.Row | None) -> DlcLicenseState:
        if row is None:
            return DlcLicenseState(install_id="")
        return DlcLicenseState(
            install_id=row["install_id"] or "",
            activated=bool(row["activated"]),
            license_tier=row["license_tier"] or "locked",
            token=row["token"] or "",
            status=row["status"] or "locked",
            last_checked_at=_parse_dt(row["last_checked_at"]),
            activated_at=_parse_dt(row["activated_at"]),
            error_text=row["error_text"] or "",
        )

    @staticmethod
    def row_to_project(row: sqlite3.Row) -> ThesisProject:
        return ThesisProject(
            project_id=row["project_id"],
            title=row["title"],
            degree=row["degree"],
            specialty=row["specialty"],
            student_name=row["student_name"],
            supervisor_name=row["supervisor_name"],
            defense_date=_parse_dt(row["defense_date"]),
            discipline_profile=DisciplineProfile(row["discipline_profile"]),
            status=row["status"],
            created_at=_parse_dt(row["created_at"]) or _parse_dt(row["updated_at"]) or _parse_dt("2000-01-01T00:00:00"),
            updated_at=_parse_dt(row["updated_at"]) or _parse_dt("2000-01-01T00:00:00"),
            recommended_model=row["recommended_model"] or "",
        )

    @staticmethod
    def row_to_source(row: sqlite3.Row) -> ThesisSource:
        return ThesisSource(
            source_id=row["source_id"],
            project_id=row["project_id"],
            kind=ThesisSourceKind(row["kind"]),
            title=row["title"],
            file_path=row["file_path"],
            file_type=row["file_type"],
            checksum=row["checksum"],
            version=int(row["version"]),
            imported_at=_parse_dt(row["imported_at"]) or _parse_dt("2000-01-01T00:00:00"),
            parse_status=row["parse_status"],
            confidence=float(row["confidence"] or 0.0),
            raw_text=row["raw_text"] or "",
            normalized_text=row["normalized_text"] or "",
            unit_count=int(row["unit_count"] or 0),
        )

    @staticmethod
    def row_to_claim(row: sqlite3.Row) -> DefenseClaim:
        return DefenseClaim(
            claim_id=row["claim_id"],
            project_id=row["project_id"],
            kind=DefenseClaimKind(row["claim_kind"]),
            text=row["text"],
            confidence=float(row["confidence"] or 0.0),
            source_anchors=_json_load(row["source_anchors_json"]),
            llm_assisted=bool(row["llm_assisted"]),
            needs_review=bool(row["needs_review"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    @staticmethod
    def row_to_slide(row: sqlite3.Row) -> SlideStoryboardCard:
        return SlideStoryboardCard(
            card_id=row["card_id"],
            project_id=row["project_id"],
            slide_index=int(row["slide_index"] or 0),
            title=row["title"],
            purpose=row["purpose"],
            talking_points=_json_load(row["talking_points_json"]),
            evidence_links=_json_load(row["evidence_links_json"]),
        )

    @staticmethod
    def row_to_question(row: sqlite3.Row) -> DefenseQuestion:
        return DefenseQuestion(
            question_id=row["question_id"],
            project_id=row["project_id"],
            persona=CommitteePersonaKind(row["persona_kind"]),
            topic=row["topic"],
            difficulty=int(row["difficulty"] or 1),
            question_text=row["question_text"],
            source_anchors=_json_load(row["source_anchors_json"]),
            risk_tag=row["risk_tag"] or "",
            created_at=_parse_dt(row["created_at"]),
        )

    @staticmethod
    def row_to_score(row: sqlite3.Row | None) -> DefenseScoreProfile | None:
        if row is None:
            return None
        return DefenseScoreProfile(
            project_id=row["project_id"],
            session_id=row["session_id"],
            structure_mastery=float(row["structure_mastery"] or 0.0),
            relevance_clarity=float(row["relevance_clarity"] or 0.0),
            methodology_mastery=float(row["methodology_mastery"] or 0.0),
            novelty_mastery=float(row["novelty_mastery"] or 0.0),
            results_mastery=float(row["results_mastery"] or 0.0),
            limitations_honesty=float(row["limitations_honesty"] or 0.0),
            oral_clarity_text_mode=float(row["oral_clarity_text_mode"] or 0.0),
            followup_mastery=float(row["followup_mastery"] or 0.0),
            summary_text=row["summary_text"] or "",
            created_at=_parse_dt(row["created_at"]) or _parse_dt("2000-01-01T00:00:00"),
        )

    @staticmethod
    def row_to_weak_area(row: sqlite3.Row) -> DefenseWeakArea:
        return DefenseWeakArea(
            weak_area_id=row["weak_area_id"],
            project_id=row["project_id"],
            kind=row["kind"],
            title=row["title"],
            severity=float(row["severity"] or 0.0),
            evidence=row["evidence"] or "",
            claim_kind=DefenseClaimKind(row["claim_kind"]) if row["claim_kind"] else None,
            created_at=_parse_dt(row["created_at"]),
        )


def _parse_dt(value: object):
    if not value:
        return None
    from datetime import datetime

    return datetime.fromisoformat(str(value))


def _json_load(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return list(json.loads(raw_value))
