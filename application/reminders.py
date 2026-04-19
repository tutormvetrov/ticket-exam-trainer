"""Мягкие напоминания заниматься (стиль Duolingo, но не агрессивно).

MVP: in-app snackbar при старте приложения.

Срабатывание (`should_remind_now`) если:
- профиль есть и `reminder_enabled=True`,
- сейчас локальное время ≥ `reminder_time`,
- за сегодня ещё нет attempts (т. е. пользователь не занимался).

Системные Windows-уведомления (winrt) — отдельная итерация (когда приложение
свёрнуто/закрыто). MVP уведомляет только когда пользователь сам открыл Flet.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from application.user_profile import UserProfile

_LOG = logging.getLogger(__name__)


def _today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _attempts_today(connection) -> int:
    """Сколько попыток было сегодня (по всем тренировкам пользователя).

    Не разделяем по курсам — если человек сегодня уже что-то делал,
    напоминать смысла нет, даже если он переключил курс.
    """
    try:
        row = connection.execute(
            """
            SELECT COUNT(*) AS n
            FROM attempts
            WHERE substr(created_at, 1, 10) = ?
            """,
            (_today_iso(),),
        ).fetchone()
        return int(row["n"] if row else 0)
    except Exception:
        _LOG.exception("attempts_today query failed")
        return 0


def should_remind_now(profile: UserProfile | None, connection: Any) -> bool:
    if profile is None:
        return False
    if not getattr(profile, "reminder_enabled", False):
        return False
    raw_time = (profile.reminder_time or "10:00").strip() or "10:00"
    try:
        target = datetime.strptime(raw_time, "%H:%M").time()
    except ValueError:
        return False
    now = datetime.now().time()
    if now < target:
        return False
    if _attempts_today(connection) > 0:
        return False
    return True


def reminder_message(profile: UserProfile | None) -> str:
    name = profile.name if profile is not None else "магистрант"
    return f"{name}, твоё время для занятия. План на сегодня в Дашборде."
