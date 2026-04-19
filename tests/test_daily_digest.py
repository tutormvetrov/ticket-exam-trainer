"""Тесты daily_digest.compute_daily_digest — агрегатор дня."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from application.daily_digest import (
    compute_daily_digest,
)
from infrastructure.db import connect_initialized


def _make_connection(tmp_path: Path) -> sqlite3.Connection:
    return connect_initialized(tmp_path / "trainer.db")


def _insert_ticket(conn: sqlite3.Connection, ticket_id: str, title: str) -> None:
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO exams (exam_id, title) VALUES ('e1', 'Экзамен') ON CONFLICT DO NOTHING",
    )
    conn.execute(
        "INSERT INTO sections (section_id, exam_id, title) VALUES ('s1', 'e1', 'Раздел') ON CONFLICT DO NOTHING",
    )
    conn.execute(
        """
        INSERT INTO source_documents (
            document_id, exam_id, title, file_path, file_type, imported_at
        ) VALUES ('doc-1', 'e1', 'Док', 'test', 'txt', ?)
        ON CONFLICT DO NOTHING
        """,
        (now,),
    )
    conn.execute(
        """
        INSERT INTO tickets (
            ticket_id, exam_id, section_id, source_document_id, title,
            canonical_answer_summary, created_at
        ) VALUES (?, 'e1', 's1', 'doc-1', ?, 'эталон', ?)
        """,
        (ticket_id, title, now),
    )


def _insert_attempt(
    conn: sqlite3.Connection,
    attempt_id: str,
    ticket_id: str,
    score: float,
    created_at: str,
    confidence: str | None = None,
) -> None:
    template_id = f"tpl-{attempt_id}"
    exercise_id = f"ex-{attempt_id}"
    conn.execute(
        """
        INSERT INTO exercise_templates (
            template_id, ticket_id, exercise_type, title, instructions
        ) VALUES (?, ?, 'atom_recall', 'Тест', 'Инструкции')
        """,
        (template_id, ticket_id),
    )
    conn.execute(
        """
        INSERT INTO exercise_instances (
            exercise_id, ticket_id, template_id, exercise_type,
            prompt_text, expected_answer, created_at
        ) VALUES (?, ?, ?, 'atom_recall', 'вопрос', 'эталон', ?)
        """,
        (exercise_id, ticket_id, template_id, created_at),
    )
    conn.execute(
        """
        INSERT INTO attempts (
            attempt_id, exercise_id, ticket_id,
            user_answer, score, created_at, confidence
        ) VALUES (?, ?, ?, '—', ?, ?, ?)
        """,
        (attempt_id, exercise_id, ticket_id, score, created_at, confidence),
    )


def test_digest_empty_state(tmp_path: Path) -> None:
    conn = _make_connection(tmp_path)
    digest = compute_daily_digest(conn)

    assert digest.today_iso == date.today().isoformat()
    assert digest.attempts == []
    assert digest.mastered_today == 0
    assert digest.best_attempt is None
    assert digest.has_attempts is False


def test_digest_today_attempts_only(tmp_path: Path) -> None:
    conn = _make_connection(tmp_path)
    _insert_ticket(conn, "t1", "Конституция")
    _insert_ticket(conn, "t2", "Бюджет")

    today = datetime.now().isoformat()
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()

    _insert_attempt(conn, "a-old", "t1", 0.5, yesterday)
    _insert_attempt(conn, "a1", "t1", 0.9, today)
    _insert_attempt(conn, "a2", "t2", 0.3, today)
    conn.commit()

    digest = compute_daily_digest(conn)
    assert len(digest.attempts) == 2
    assert {card.attempt_id for card in digest.attempts} == {"a1", "a2"}


def test_digest_best_attempt_picks_max_score(tmp_path: Path) -> None:
    conn = _make_connection(tmp_path)
    _insert_ticket(conn, "t1", "Бюджет")
    _insert_ticket(conn, "t2", "Право")

    today = datetime.now().isoformat()
    _insert_attempt(conn, "low", "t1", 0.4, today)
    _insert_attempt(conn, "hi", "t2", 0.95, today)
    conn.commit()

    digest = compute_daily_digest(conn)
    assert digest.best_attempt is not None
    assert digest.best_attempt.attempt_id == "hi"
    assert digest.best_attempt.score_percent == 95


def test_digest_mastered_today_counts_distinct_tickets(tmp_path: Path) -> None:
    conn = _make_connection(tmp_path)
    _insert_ticket(conn, "t1", "Первый")
    _insert_ticket(conn, "t2", "Второй")

    today = datetime.now().isoformat()
    _insert_attempt(conn, "a1", "t1", 0.8, today)
    _insert_attempt(conn, "a2", "t1", 0.9, today)  # same ticket again
    _insert_attempt(conn, "a3", "t2", 0.76, today)  # just above threshold
    _insert_attempt(conn, "a4", "t2", 0.5, today)  # doesn't drop it — different attempt
    conn.commit()

    digest = compute_daily_digest(conn)
    # t1 has 2 attempts (both ≥ 75) → counts once; t2 has one ≥ 75 attempt → counts once
    assert digest.mastered_today == 2


def test_digest_delta_vs_previous_attempt(tmp_path: Path) -> None:
    conn = _make_connection(tmp_path)
    _insert_ticket(conn, "t1", "Тема")

    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    today = datetime.now().isoformat()
    _insert_attempt(conn, "old", "t1", 0.6, yesterday)
    _insert_attempt(conn, "new", "t1", 0.85, today)
    conn.commit()

    digest = compute_daily_digest(conn)
    (card,) = digest.attempts
    assert card.attempt_id == "new"
    assert card.delta_percent == 85 - 60


def test_digest_delta_none_for_first_attempt_ever(tmp_path: Path) -> None:
    conn = _make_connection(tmp_path)
    _insert_ticket(conn, "t1", "Тема")
    today = datetime.now().isoformat()
    _insert_attempt(conn, "only", "t1", 0.7, today)
    conn.commit()

    digest = compute_daily_digest(conn)
    (card,) = digest.attempts
    assert card.delta_percent is None


def test_digest_queue_new_counts_untouched_tickets(tmp_path: Path) -> None:
    conn = _make_connection(tmp_path)
    _insert_ticket(conn, "t1", "Тронут")
    _insert_ticket(conn, "t2", "Не тронут")
    _insert_ticket(conn, "t3", "Не тронут тоже")

    today = datetime.now().isoformat()
    _insert_attempt(conn, "a1", "t1", 0.8, today)
    conn.commit()

    digest = compute_daily_digest(conn)
    assert digest.queue_new == 2


def test_digest_confidence_preserved_in_card(tmp_path: Path) -> None:
    conn = _make_connection(tmp_path)
    _insert_ticket(conn, "t1", "Тема")
    today = datetime.now().isoformat()
    _insert_attempt(conn, "a1", "t1", 0.8, today, confidence="sure")
    conn.commit()

    digest = compute_daily_digest(conn)
    (card,) = digest.attempts
    assert card.confidence == "sure"


def test_digest_estimate_minutes_at_least_one(tmp_path: Path) -> None:
    conn = _make_connection(tmp_path)
    digest = compute_daily_digest(conn)
    assert digest.queue_estimate_minutes >= 1
