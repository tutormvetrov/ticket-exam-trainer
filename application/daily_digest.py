"""Daily digest — агрегатор «что было сегодня».

Строит снапшот по попыткам за текущий день и размеру очереди:
  * сколько попыток сделано сегодня;
  * сколько билетов «усвоено» (score ≥ ``MASTERED_THRESHOLD``);
  * лучший момент дня (attempt с максимальным score);
  * размер очереди на сегодня + сколько в ней «свежих» (никогда не
    проходились);
  * дельта балла по билету (текущая попытка vs предыдущая).

Не трогает FSRS и не меняет данные — только read-side.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import sqlite3


MASTERED_THRESHOLD = 0.75  # score ≥ 75% → считается «в долговременную память»
NEW_TICKET_MARK = "первый"  # marker used to render "первый заход" delta hint
MINUTES_PER_ATTEMPT = 5  # крубая оценка для строки «примерно T минут»


@dataclass(frozen=True)
class AttemptCard:
    attempt_id: str
    ticket_id: str
    ticket_title: str
    mode_key: str
    score_percent: int
    created_at: str                       # ISO string
    confidence: str | None                # 'guess' | 'idea' | 'sure' | None
    delta_percent: int | None             # None if first attempt for this ticket


@dataclass(frozen=True)
class DailyDigest:
    today_iso: str                        # YYYY-MM-DD
    attempts: list[AttemptCard]           # newest first
    mastered_today: int                   # distinct tickets with today's score ≥ threshold
    best_attempt: AttemptCard | None      # max score today
    queue_due_today: int                  # billions due per FSRS queue
    queue_new: int                        # tickets never attempted
    queue_estimate_minutes: int

    @property
    def has_attempts(self) -> bool:
        return len(self.attempts) > 0


def compute_daily_digest(connection: sqlite3.Connection, user_id: str = "local-user") -> DailyDigest:
    today_iso = date.today().isoformat()
    attempts = _load_todays_attempts(connection, today_iso)

    best_attempt: AttemptCard | None = None
    for card in attempts:
        if best_attempt is None or card.score_percent > best_attempt.score_percent:
            best_attempt = card

    mastered_tickets: set[str] = set()
    for card in attempts:
        if card.score_percent >= int(MASTERED_THRESHOLD * 100):
            mastered_tickets.add(card.ticket_id)

    queue_due_today = _count_queue_due(connection, user_id, today_iso)
    queue_new = _count_never_attempted(connection)
    queue_total = queue_due_today + queue_new
    queue_estimate_minutes = max(1, queue_total * MINUTES_PER_ATTEMPT)

    return DailyDigest(
        today_iso=today_iso,
        attempts=attempts,
        mastered_today=len(mastered_tickets),
        best_attempt=best_attempt,
        queue_due_today=queue_due_today,
        queue_new=queue_new,
        queue_estimate_minutes=queue_estimate_minutes,
    )


def _load_todays_attempts(connection: sqlite3.Connection, today_iso: str) -> list[AttemptCard]:
    """Список попыток за сегодня, newest first, с дельтой vs предыдущая попытка
    этого же билета."""
    rows = connection.execute(
        """
        SELECT
            a.attempt_id AS attempt_id,
            a.ticket_id AS ticket_id,
            t.title AS ticket_title,
            ei.exercise_type AS mode_key,
            a.score AS score,
            a.created_at AS created_at,
            a.confidence AS confidence
        FROM attempts a
        JOIN tickets t ON t.ticket_id = a.ticket_id
        LEFT JOIN exercise_instances ei ON ei.exercise_id = a.exercise_id
        WHERE DATE(a.created_at) = ?
        ORDER BY a.created_at DESC
        """,
        (today_iso,),
    ).fetchall()

    cards: list[AttemptCard] = []
    for row in rows:
        score_percent = int(round(float(row["score"] or 0.0) * 100))
        delta = _previous_attempt_delta(connection, row["ticket_id"], row["created_at"], score_percent)
        cards.append(
            AttemptCard(
                attempt_id=row["attempt_id"],
                ticket_id=row["ticket_id"],
                ticket_title=str(row["ticket_title"] or "").strip() or row["ticket_id"],
                mode_key=_normalize_mode(row["mode_key"]),
                score_percent=score_percent,
                created_at=str(row["created_at"] or ""),
                confidence=row["confidence"],
                delta_percent=delta,
            )
        )
    return cards


def _previous_attempt_delta(
    connection: sqlite3.Connection,
    ticket_id: str,
    current_created_at: str,
    current_score_percent: int,
) -> int | None:
    row = connection.execute(
        """
        SELECT score FROM attempts
        WHERE ticket_id = ? AND created_at < ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (ticket_id, current_created_at),
    ).fetchone()
    if row is None:
        return None
    previous_percent = int(round(float(row["score"] or 0.0) * 100))
    return current_score_percent - previous_percent


def _count_queue_due(connection: sqlite3.Connection, user_id: str, today_iso: str) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM spaced_review_queue
        WHERE user_id = ? AND (due_at IS NULL OR DATE(due_at) <= ?)
        """,
        (user_id, today_iso),
    ).fetchone()
    return int(row["total"] if row else 0)


def _count_never_attempted(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM tickets t
        WHERE NOT EXISTS (
            SELECT 1 FROM attempts a WHERE a.ticket_id = t.ticket_id
        )
        """
    ).fetchone()
    return int(row["total"] if row else 0)


def _normalize_mode(raw: str | None) -> str:
    """Маппим ExerciseType → UI-mode-key.

    БД хранит доменные типы (``atom_recall``, ``oral_full``, ...). Карточки
    дневника показывают ближайшие UI-режимы из TrainingView. Маппинг —
    обратный к ``AppFacade._pick_exercise``.
    """
    if not raw:
        return ""
    mapping = {
        "answer_skeleton": "reading",
        "atom_recall": "active-recall",
        "semantic_cloze": "cloze",
        "odd_thesis": "matching",
        "structure_reconstruction": "plan",
        "oral_full": "state-exam-full",
        "oral_short": "active-recall",
    }
    return mapping.get(str(raw).lower(), str(raw).lower())
