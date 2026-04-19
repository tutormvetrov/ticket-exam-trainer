"""Тесты FSRS-планировщика поверх AdaptiveReviewService.

Проверяем:
- маппинг ``score_to_rating`` для разных режимов,
- лестницу cold-start (1/3/7 дней),
- сериализационный round-trip ``fsrs_state_json``,
- интеграцию ``record_attempt`` с ``build_queue``.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from fsrs import Rating

from application.adaptive_review import (
    COLD_START_INTERVALS_DAYS,
    AdaptiveReviewService,
    is_cold_start,
    score_to_rating,
)
from application.import_service import DocumentImportService, TicketCandidate
from domain.knowledge import TicketMasteryProfile


NOW = datetime(2026, 4, 16, 12, 0, 0)


def _ticket(title: str = "Ticket"):
    service = DocumentImportService()
    candidate = TicketCandidate(1, title, "Definition. Example.", 0.9, "section-1")
    ticket, _, _ = service.build_ticket_map(candidate, "exam-demo", "section-1", "doc-demo")
    return ticket


# ---------------------------------------------------------------- score_to_rating


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, Rating.Easy),
        (85, Rating.Easy),
        (80, Rating.Easy),
        (79, Rating.Good),
        (60, Rating.Good),
        (59, Rating.Hard),
        (40, Rating.Hard),
        (39, Rating.Again),
        (0, Rating.Again),
    ],
)
def test_state_exam_full_scale(score: int, expected: Rating) -> None:
    assert score_to_rating("state-exam-full", score) is expected


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, Rating.Good),
        (75, Rating.Good),
        (74, Rating.Hard),
        (50, Rating.Hard),
        (49, Rating.Again),
        (0, Rating.Again),
    ],
)
def test_active_recall_scale_has_no_easy(score: int, expected: Rating) -> None:
    assert score_to_rating("active-recall", score) is expected


@pytest.mark.parametrize("mode_key", ["reading", "plan", "cloze", "matching"])
def test_passive_modes_return_none(mode_key: str) -> None:
    assert score_to_rating(mode_key, 95) is None


def test_score_out_of_range_is_clamped() -> None:
    # 120 должно восприниматься как 100 → Easy для state-exam-full.
    assert score_to_rating("state-exam-full", 120) is Rating.Easy
    # -30 — как 0 → Again.
    assert score_to_rating("state-exam-full", -30) is Rating.Again


# ------------------------------------------------------------------- cold start


def test_is_cold_start_threshold() -> None:
    assert is_cold_start(TicketMasteryProfile(user_id="u", ticket_id="t", attempts_count=0))
    assert is_cold_start(TicketMasteryProfile(user_id="u", ticket_id="t", attempts_count=1))
    assert is_cold_start(TicketMasteryProfile(user_id="u", ticket_id="t", attempts_count=2))
    assert not is_cold_start(TicketMasteryProfile(user_id="u", ticket_id="t", attempts_count=3))


def test_cold_start_ladder_sequence_for_successful_attempts() -> None:
    service = AdaptiveReviewService()
    profile = TicketMasteryProfile(user_id="u", ticket_id="t")

    # 1-я успешная попытка → через 1 день.
    profile = service.record_attempt(profile, "active-recall", 80, now=NOW)
    assert profile.attempts_count == 1
    assert profile.next_review_at == NOW + timedelta(days=COLD_START_INTERVALS_DAYS[0])

    # 2-я успешная попытка → через 3 дня.
    after_first = NOW + timedelta(days=COLD_START_INTERVALS_DAYS[0])
    profile = service.record_attempt(profile, "active-recall", 80, now=after_first)
    assert profile.attempts_count == 2
    assert profile.next_review_at == after_first + timedelta(days=COLD_START_INTERVALS_DAYS[1])

    # 3-я успешная попытка → через 7 дней.
    after_second = after_first + timedelta(days=COLD_START_INTERVALS_DAYS[1])
    profile = service.record_attempt(profile, "active-recall", 80, now=after_second)
    assert profile.attempts_count == 3
    assert profile.next_review_at == after_second + timedelta(days=COLD_START_INTERVALS_DAYS[2])

    # 4-я попытка — уже FSRS, интервал должен быть > 7 дней или отличаться от
    # ступенек лестницы.
    after_third = after_second + timedelta(days=COLD_START_INTERVALS_DAYS[2])
    profile = service.record_attempt(profile, "active-recall", 80, now=after_third)
    assert profile.attempts_count == 4
    assert profile.next_review_at is not None
    delta = profile.next_review_at - after_third
    assert delta > timedelta(days=3)  # после трёх Good обычно интервал растёт


def test_again_during_cold_start_resets_to_first_step() -> None:
    """Если на cold-start студент завалил ответ — возвращаем на первый шаг."""
    service = AdaptiveReviewService()
    profile = TicketMasteryProfile(user_id="u", ticket_id="t", attempts_count=2)
    # Имитируем предыдущее fsrs-состояние (dict не обязателен — record_attempt
    # создаст новый Card при пустом state).
    profile = service.record_attempt(profile, "state-exam-full", 20, now=NOW)
    # attempts должны не уйти за верх лестницы.
    assert profile.attempts_count <= len(COLD_START_INTERVALS_DAYS)
    # Due — на первом шаге (1 день).
    assert profile.next_review_at == NOW + timedelta(days=COLD_START_INTERVALS_DAYS[0])


def test_passive_mode_does_not_touch_profile() -> None:
    service = AdaptiveReviewService()
    profile = TicketMasteryProfile(user_id="u", ticket_id="t", attempts_count=2)
    updated = service.record_attempt(profile, "reading", 100, now=NOW)
    # Нет изменений — тот же объект возвращается.
    assert updated is profile
    assert updated.attempts_count == 2
    assert updated.fsrs_state_json == ""


# ------------------------------------------------------------------- persistence


def test_fsrs_state_json_roundtrip() -> None:
    """После записи попытки состояние FSRS сохраняется в profile.fsrs_state_json
    и восстанавливается при следующем build_queue."""
    service = AdaptiveReviewService()
    profile = TicketMasteryProfile(user_id="u", ticket_id="t")

    # Прогоняем 4 успешных попытки, чтобы точно выйти из cold-start.
    review_time = NOW
    for _ in range(4):
        profile = service.record_attempt(profile, "active-recall", 80, now=review_time)
        assert profile.fsrs_state_json  # non-empty
        review_time = (profile.next_review_at or review_time) + timedelta(minutes=1)

    # Парсим сохранённый JSON — должен быть валидный dict с ключами FSRS Card.
    parsed = json.loads(profile.fsrs_state_json)
    assert isinstance(parsed, dict)
    for key in ("card_id", "state", "due"):
        assert key in parsed

    # Следующая запись должна уметь прочитать и продолжить цепочку.
    profile_after = service.record_attempt(profile, "active-recall", 80, now=review_time)
    assert profile_after.attempts_count == profile.attempts_count + 1
    assert profile_after.fsrs_state_json != profile.fsrs_state_json


def test_build_queue_uses_fsrs_due_after_cold_start() -> None:
    """Когда attempts_count >= 3, build_queue подхватывает due из fsrs_state_json."""
    service = AdaptiveReviewService()
    ticket = _ticket()
    profile = TicketMasteryProfile(user_id="u", ticket_id=ticket.ticket_id)

    review_time = NOW
    for _ in range(4):
        profile = service.record_attempt(profile, "active-recall", 80, now=review_time)
        review_time = (profile.next_review_at or review_time) + timedelta(minutes=1)

    # Перезапускаем build_queue "сейчас" относительно последнего review.
    last_review = profile.last_reviewed_at or review_time
    queue = service.build_queue("u", [ticket], [profile], [], now=last_review)
    item = queue[0]
    # Элемент очереди должен быть назначен на fsrs-дату, т.е. не
    # равен последнему шагу лестницы (7 дней).
    expected_next = profile.next_review_at
    assert expected_next is not None
    assert item.due_at == expected_next
    # И этот интервал отличается от cold-start ступеньки.
    assert (item.due_at - last_review) != timedelta(days=COLD_START_INTERVALS_DAYS[-1])


def test_record_attempt_does_not_mutate_input_profile() -> None:
    """Functional style: исходный профиль остаётся прежним."""
    service = AdaptiveReviewService()
    profile = TicketMasteryProfile(user_id="u", ticket_id="t")
    updated = service.record_attempt(profile, "active-recall", 80, now=NOW)

    assert updated is not profile
    assert profile.attempts_count == 0
    assert profile.fsrs_state_json == ""
    assert updated.attempts_count == 1
    assert updated.fsrs_state_json != ""
