"""Adaptive review queue backed by the FSRS scheduling algorithm.

Этот модуль отвечает за две вещи:

1. Построение очереди повторений (``build_queue``) — вызывается из фасада и
   тестов. Для каждого билета решается: когда карточка должна снова появиться
   на глаза студенту.
2. Учёт очередной попытки (``record_attempt``) — после того как режим записан
   в ``attempt``, мы хотим обновить FSRS-состояние карточки.

Алгоритм:

- **Cold-start** — пока у карточки меньше
  ``len(COLD_START_INTERVALS_DAYS)`` (= 3) подтверждённых попыток, мы
  используем линейную лестницу интервалов: 1 день → 3 дня → 7 дней. Это
  стабилизирует первые повторения новичка: FSRS на дефолтных параметрах для
  совсем новой карточки даёт непредсказуемые интервалы, а нам нужен
  контролируемый ramp-up.
- **FSRS** — после того как карточка прошла cold-start (>=3 попыток) мы
  переключаемся на полноценный
  ``fsrs.Scheduler.review_card``. Persist-состояние храним в
  ``TicketMasteryProfile.fsrs_state_json`` (``Card.to_dict() / from_dict``).

Public API:

- ``AdaptiveReviewService.build_queue(...)`` — публичный интерфейс фасада
  (``load_training_snapshot``, ``_refresh_review_queue``) и тестов.
- ``AdaptiveReviewService.record_attempt(profile, mode_key, score_percent,
  now=None)`` — возвращает обновлённый ``TicketMasteryProfile`` (functional
  style: исходный profile не мутируется).
- ``score_to_rating(mode_key, score_percent)`` — маппинг результата попытки в
  ``fsrs.Rating``. Для пассивных режимов (чтение, план, клоузы, просмотр)
  возвращает ``None`` — такие режимы не влияют на расписание.
- ``is_cold_start(profile)`` — кто ещё не вышел из начальной лестницы.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fsrs import Card, Rating, Scheduler

from domain.knowledge import (
    ReviewMode,
    SpacedReviewItem,
    TicketKnowledgeMap,
    TicketMasteryProfile,
    WeakArea,
    WeakAreaKind,
)

# Cold-start ladder: на первых трёх попытках мы не доверяем FSRS-оценке,
# потому что для совсем новой карточки она выдаёт дефолтные параметры (stability
# непредсказуемая, первый интервал зависит от реализации). Вместо этого
# используем ручной ramp-up: 1 день → 3 дня → 7 дней.
COLD_START_INTERVALS_DAYS: tuple[int, ...] = (1, 3, 7)

# Режимы, которые реально двигают расписание карточки в текущем приложении.
_ACTIVE_MODES: frozenset[str] = frozenset({"state-exam-full", "active-recall", "review"})


def score_to_rating(mode_key: str, score_percent: int) -> Rating | None:
    """Маппинг ``(mode, score %) -> fsrs.Rating``.

    Пассивные режимы (reading, plan, cloze и пр.) не двигают FSRS —
    возвращаем ``None``.
    """
    score = max(0, min(100, int(score_percent)))
    if mode_key == "state-exam-full":
        if score >= 80:
            return Rating.Easy
        if score >= 60:
            return Rating.Good
        if score >= 40:
            return Rating.Hard
        return Rating.Again
    if mode_key in {"active-recall", "review"}:
        # Короткий формат — Easy выдавать рано. Максимум — Good.
        if score >= 75:
            return Rating.Good
        if score >= 50:
            return Rating.Hard
        return Rating.Again
    return None


def is_cold_start(profile: TicketMasteryProfile) -> bool:
    """Карточка всё ещё находится на начальной лестнице интервалов."""
    return int(profile.attempts_count or 0) < len(COLD_START_INTERVALS_DAYS)


def _ensure_aware(dt: datetime) -> datetime:
    """FSRS требует aware-datetime. Проектные profile.last_reviewed_at — наивные,
    поэтому обёртываем их в UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _load_card(state_json: str) -> Card | None:
    if not state_json:
        return None
    try:
        payload = json.loads(state_json)
        return Card.from_dict(payload)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        return None


def _dump_card(card: Card) -> str:
    return json.dumps(card.to_dict(), ensure_ascii=False)


def _build_scheduler() -> Scheduler:
    # enable_fuzzing=False делает расписание детерминированным — тестам и
    # верификации это нужно. В проде fuzzing не даёт заметной пользы для
    # маленьких пользовательских очередей.
    return Scheduler(enable_fuzzing=False)


class AdaptiveReviewService:
    """Очередь повторений на FSRS + cold-start.

    Инстанс держит ``Scheduler`` с детерминированными параметрами. Метод
    ``build_queue`` читает persist-состояние из профилей, но сам профили не
    мутирует: обновление происходит исключительно в ``record_attempt``.
    """

    def __init__(self, scheduler: Scheduler | None = None) -> None:
        self._scheduler = scheduler or _build_scheduler()

    def build_queue(
        self,
        user_id: str,
        tickets: list[TicketKnowledgeMap],
        profiles: list[TicketMasteryProfile],
        weak_areas: list[WeakArea],
        mode: ReviewMode = ReviewMode.STANDARD_ADAPTIVE,
        now: datetime | None = None,
    ) -> list[SpacedReviewItem]:
        current_time = now or datetime.now()
        profile_map = {profile.ticket_id: profile for profile in profiles}
        weakness_map: dict[str, list[WeakArea]] = {}
        for weak_area in weak_areas:
            for ticket_id in weak_area.related_ticket_ids:
                weakness_map.setdefault(ticket_id, []).append(weak_area)

        queue: list[SpacedReviewItem] = []
        for ticket in tickets:
            profile = profile_map.get(ticket.ticket_id) or TicketMasteryProfile(
                user_id=user_id, ticket_id=ticket.ticket_id
            )
            related_weaknesses = weakness_map.get(ticket.ticket_id, [])
            priority = self._compute_priority(ticket, profile, related_weaknesses, mode)
            due_at = self._compute_due_at(profile, current_time, mode)
            queue.append(
                SpacedReviewItem(
                    review_item_id=f"review-{uuid4().hex[:12]}",
                    user_id=user_id,
                    ticket_id=ticket.ticket_id,
                    reference_type="ticket",
                    reference_id=ticket.ticket_id,
                    mode=mode,
                    priority=priority,
                    due_at=due_at,
                    scheduled_at=current_time,
                )
            )

            for weak_area in related_weaknesses:
                if weak_area.kind not in {WeakAreaKind.CONCEPT, WeakAreaKind.CROSS_TICKET_CONCEPT}:
                    continue
                # Weak-area item должен наступать чуть раньше самого билета.
                weak_due = current_time + max(
                    (due_at - current_time) / 2, timedelta(hours=1)
                )
                queue.append(
                    SpacedReviewItem(
                        review_item_id=f"review-{uuid4().hex[:12]}",
                        user_id=user_id,
                        ticket_id=ticket.ticket_id,
                        reference_type=weak_area.kind.value,
                        reference_id=weak_area.reference_id,
                        mode=mode,
                        priority=round(min(1.5, priority + weak_area.severity * 0.2), 4),
                        due_at=weak_due,
                        scheduled_at=current_time,
                    )
                )

        queue.sort(key=lambda item: (-item.priority, item.due_at))
        return queue

    # ------------------------------------------------------------------ attempts

    def record_attempt(
        self,
        profile: TicketMasteryProfile,
        mode_key: str,
        score_percent: int,
        now: datetime | None = None,
    ) -> TicketMasteryProfile:
        """Учесть очередную попытку в FSRS-состоянии профиля.

        Возвращает **новый** ``TicketMasteryProfile`` с обновлёнными
        ``fsrs_state_json``, ``attempts_count``, ``last_reviewed_at`` и
        ``next_review_at``. Оригинальный объект не мутируется.

        Для пассивных режимов (``reading``/``plan``/``cloze``)
        ничего не делается: ``score_to_rating`` вернёт ``None`` и profile
        возвращается как есть.
        """
        rating = score_to_rating(mode_key, score_percent)
        if rating is None:
            return profile

        current_time = _ensure_aware(now or datetime.now())
        card = _load_card(profile.fsrs_state_json) or Card()

        new_attempts = int(profile.attempts_count or 0) + 1

        # Cold-start ladder: пока попыток < 3, мы сами диктуем интервал.
        # FSRS scheduler всё равно прогоняем, чтобы накапливалось состояние
        # (stability/difficulty) — но due перезаписываем.
        updated_card, _log = self._scheduler.review_card(card, rating, review_datetime=current_time)

        if new_attempts <= len(COLD_START_INTERVALS_DAYS):
            # Если оценка Again — не считаем попытку "успешной": откатываем
            # счётчик на минимум и даём ближайший интервал (1 день).
            if rating is Rating.Again:
                step_index = 0
                new_attempts = max(1, min(new_attempts, len(COLD_START_INTERVALS_DAYS)))
            else:
                # attempts_count==1 → берём COLD_START_INTERVALS_DAYS[0] (1 день)
                step_index = min(new_attempts - 1, len(COLD_START_INTERVALS_DAYS) - 1)
            forced_due = current_time + timedelta(days=COLD_START_INTERVALS_DAYS[step_index])
            updated_card.due = forced_due

        next_due_naive = updated_card.due.astimezone(timezone.utc).replace(tzinfo=None)
        last_reviewed_naive = current_time.astimezone(timezone.utc).replace(tzinfo=None)

        return replace(
            profile,
            fsrs_state_json=_dump_card(updated_card),
            attempts_count=new_attempts,
            last_reviewed_at=last_reviewed_naive,
            next_review_at=next_due_naive,
        )

    # ------------------------------------------------------------------ helpers

    def _compute_due_at(
        self,
        profile: TicketMasteryProfile,
        now: datetime,
        mode: ReviewMode,
    ) -> datetime:
        """Единая точка истины: очередь доверяет ``profile.next_review_at``.

        ``record_attempt`` уже прогоняет cold-start-лестницу и FSRS, пишет
        итог в ``profile.next_review_at``. Очередь не пересчитывает с нуля
        по-своему (это порождало off-by-one между профилем и due_at), а
        просто берёт профильное значение. Если его нет — профиль никогда
        не повторялся, используется первая ступенька лестницы.
        """
        attempts = int(profile.attempts_count or 0)

        # Никогда не повторялась — первый показ через шаг 0 (1 день).
        if attempts <= 0:
            return now + timedelta(days=COLD_START_INTERVALS_DAYS[0])

        # Если запись повторялась и имеет next_review_at — доверяем ему.
        if profile.next_review_at is not None:
            due = profile.next_review_at
            if due.tzinfo is not None:
                due = due.astimezone(timezone.utc).replace(tzinfo=None)
            # В EXAM_CRUNCH сжимаем "хвост" интервала, чтобы всё всплывало чаще.
            if mode is ReviewMode.EXAM_CRUNCH and due > now:
                shrink = (due - now) * 0.5
                return now + shrink
            return due

        # Legacy / battle-broken профиль: attempts>=1, но next_review_at
        # не проставлен. Синтезируем интервал по положению на лестнице
        # либо по mastery для пост-cold-start.
        if attempts < len(COLD_START_INTERVALS_DAYS):
            step_index = min(attempts - 1, len(COLD_START_INTERVALS_DAYS) - 1)
            return now + timedelta(days=COLD_START_INTERVALS_DAYS[step_index])
        mastery = max(0.1, profile.confidence_score or 0.0)
        base_hours = 18 * mastery if mode is ReviewMode.EXAM_CRUNCH else 72 * mastery
        return now + timedelta(hours=max(1, int(base_hours)))

    @staticmethod
    def _compute_priority(
        ticket: TicketKnowledgeMap,
        profile: TicketMasteryProfile,
        weak_areas: list[WeakArea],
        mode: ReviewMode,
    ) -> float:
        average_mastery = profile.confidence_score or 0.0
        oral_gap = 1.0 - ((profile.oral_short_mastery + profile.oral_full_mastery + profile.followup_mastery) / 3)
        weakness_penalty = max((weak_area.severity for weak_area in weak_areas), default=0.0)
        difficulty_factor = ticket.difficulty / 5
        mode_bonus = 0.15 if mode is ReviewMode.EXAM_CRUNCH else 0.0
        priority = (1.0 - average_mastery) * 0.45 + oral_gap * 0.3 + difficulty_factor * 0.15 + weakness_penalty * 0.25 + mode_bonus
        return round(min(1.5, max(0.1, priority)), 4)
