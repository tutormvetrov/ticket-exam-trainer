"""Tests for the time-aware greeting in the Journal view.

Before this fix the morning screen said "С добрым утром" at any hour —
including 23:43. The greeting now follows wall-clock time; the journal
stage (morning / during / evening) still keys off today's attempts.
"""

from __future__ import annotations

from datetime import datetime

from ui_flet.views.journal_view import _time_aware_greeting


def _at(hour: int) -> datetime:
    return datetime(2026, 4, 19, hour, 30)


def test_morning_hours_return_morning_phrase() -> None:
    for h in (5, 7, 10):
        assert _time_aware_greeting(_at(h)) == "С добрым утром"


def test_day_hours_return_day_phrase() -> None:
    for h in (11, 13, 16):
        assert _time_aware_greeting(_at(h)) == "Добрый день"


def test_evening_hours_return_evening_phrase() -> None:
    for h in (17, 19, 21):
        assert _time_aware_greeting(_at(h)) == "Добрый вечер"


def test_late_night_returns_night_phrase() -> None:
    # The 23:43 bug report: "С добрым утром, Мишка" at 23:43 was wrong.
    for h in (22, 23, 0, 3):
        assert _time_aware_greeting(_at(h)) == "Доброй ночи"


def test_boundary_hours() -> None:
    # Boundaries belong to the later window: at 11:00 it's already день,
    # at 17:00 already вечер, at 22:00 already ночь, at 5:00 already утро.
    assert _time_aware_greeting(_at(5)) == "С добрым утром"
    assert _time_aware_greeting(_at(11)) == "Добрый день"
    assert _time_aware_greeting(_at(17)) == "Добрый вечер"
    assert _time_aware_greeting(_at(22)) == "Доброй ночи"
