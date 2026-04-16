from __future__ import annotations

import sqlite3


class DialogueRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_session(
        self,
        *,
        session_id: str,
        user_id: str,
        ticket_id: str,
        persona_kind: str,
        resolved_model: str,
        started_at: str,
        updated_at: str,
        commit: bool = True,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO dialogue_sessions (
                session_id, user_id, ticket_id, persona_kind, status, resolved_model,
                started_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                user_id = excluded.user_id,
                ticket_id = excluded.ticket_id,
                persona_kind = excluded.persona_kind,
                resolved_model = excluded.resolved_model,
                updated_at = excluded.updated_at
            """,
            (
                session_id,
                user_id,
                ticket_id,
                persona_kind,
                resolved_model,
                started_at,
                updated_at,
            ),
        )
        if commit:
            self.connection.commit()

    def update_session_progress(
        self,
        *,
        session_id: str,
        last_turn_index: int,
        user_turn_count: int,
        updated_at: str,
        commit: bool = True,
    ) -> None:
        self.connection.execute(
            """
            UPDATE dialogue_sessions
            SET last_turn_index = ?,
                user_turn_count = ?,
                updated_at = ?
            WHERE session_id = ?
            """,
            (
                last_turn_index,
                user_turn_count,
                updated_at,
                session_id,
            ),
        )
        if commit:
            self.connection.commit()

    def mark_session_completed(
        self,
        *,
        session_id: str,
        last_turn_index: int,
        user_turn_count: int,
        final_score_percent: int,
        final_verdict: str,
        final_summary: str,
        final_feedback: str,
        completed_at: str,
        updated_at: str,
        commit: bool = True,
    ) -> None:
        self.connection.execute(
            """
            UPDATE dialogue_sessions
            SET status = 'completed',
                last_turn_index = ?,
                user_turn_count = ?,
                final_score_percent = ?,
                final_verdict = ?,
                final_summary = ?,
                final_feedback = ?,
                completed_at = ?,
                updated_at = ?
            WHERE session_id = ?
            """,
            (
                last_turn_index,
                user_turn_count,
                final_score_percent,
                final_verdict,
                final_summary,
                final_feedback,
                completed_at,
                updated_at,
                session_id,
            ),
        )
        if commit:
            self.connection.commit()

    def append_turn(
        self,
        *,
        turn_id: str,
        session_id: str,
        turn_index: int,
        speaker: str,
        text: str,
        weakness_focus: str,
        created_at: str,
        commit: bool = True,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO dialogue_turns (
                turn_id, session_id, turn_index, speaker, text, weakness_focus, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(turn_id) DO UPDATE SET
                session_id = excluded.session_id,
                turn_index = excluded.turn_index,
                speaker = excluded.speaker,
                text = excluded.text,
                weakness_focus = excluded.weakness_focus,
                created_at = excluded.created_at
            """,
            (
                turn_id,
                session_id,
                turn_index,
                speaker,
                text,
                weakness_focus,
                created_at,
            ),
        )
        if commit:
            self.connection.commit()

    def load_session_row(self, session_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM dialogue_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

    def load_active_session_for_ticket(self, user_id: str, ticket_id: str, persona_kind: str) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM dialogue_sessions
            WHERE user_id = ? AND ticket_id = ? AND persona_kind = ? AND status = 'active'
            ORDER BY updated_at DESC, started_at DESC
            LIMIT 1
            """,
            (user_id, ticket_id, persona_kind),
        ).fetchone()

    def load_recent_sessions(
        self,
        user_id: str,
        *,
        limit: int = 8,
        ticket_id: str | None = None,
        status: str | None = None,
    ) -> list[sqlite3.Row]:
        clauses = ["user_id = ?"]
        params: list[object] = [user_id]
        if ticket_id:
            clauses.append("ticket_id = ?")
            params.append(ticket_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where_clause = " AND ".join(clauses)
        params.append(max(1, min(limit, 48)))
        return self.connection.execute(
            f"""
            SELECT *
            FROM dialogue_sessions
            WHERE {where_clause}
            ORDER BY updated_at DESC, started_at DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

    def load_session_turns(self, session_id: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT *
            FROM dialogue_turns
            WHERE session_id = ?
            ORDER BY turn_index, created_at, turn_id
            """,
            (session_id,),
        ).fetchall()
