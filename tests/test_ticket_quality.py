"""Тесты эвристики skeleton-weakness."""

from __future__ import annotations

from dataclasses import dataclass

from application.ticket_quality import (
    MIN_BLOCK_COUNT,
    TicketQualityCache,
    assess_ticket,
)


@dataclass
class _FakeBlock:
    expected_content: str
    is_missing: bool = False


@dataclass
class _FakeTicket:
    ticket_id: str
    answer_blocks: list


def _full_block(words: int) -> _FakeBlock:
    return _FakeBlock(expected_content=" ".join(["слово"] * words))


def test_assess_full_plan_is_ok() -> None:
    blocks = [_full_block(30)] * 6  # 6 блоков по 30 слов
    verdict = assess_ticket(_FakeTicket("t1", blocks))
    assert verdict.plan_skeleton_weak is False
    assert verdict.reason == "ok"


def test_assess_too_few_blocks_is_weak() -> None:
    blocks = [_full_block(30)] * (MIN_BLOCK_COUNT - 1)
    verdict = assess_ticket(_FakeTicket("t1", blocks))
    assert verdict.plan_skeleton_weak is True
    assert verdict.reason == "too_few_blocks"


def test_assess_no_blocks_missing_reason() -> None:
    verdict = assess_ticket(_FakeTicket("t1", []))
    assert verdict.plan_skeleton_weak is True
    assert verdict.reason == "missing_blocks"


def test_assess_short_blocks_is_weak() -> None:
    blocks = [_full_block(5)] * 6  # 6 блоков, но по 5 слов каждый
    verdict = assess_ticket(_FakeTicket("t1", blocks))
    assert verdict.plan_skeleton_weak is True
    assert verdict.reason == "short_blocks"


def test_assess_excludes_is_missing_blocks() -> None:
    # 5 missing + 1 полный → usable=1, что меньше MIN → weak
    blocks = [_FakeBlock("x", is_missing=True)] * 5 + [_full_block(30)]
    verdict = assess_ticket(_FakeTicket("t1", blocks))
    assert verdict.plan_skeleton_weak is True
    assert verdict.reason == "too_few_blocks"


def test_assess_border_case_exactly_min_blocks_full_content() -> None:
    blocks = [_full_block(20)] * MIN_BLOCK_COUNT
    verdict = assess_ticket(_FakeTicket("t1", blocks))
    assert verdict.plan_skeleton_weak is False


def test_cache_is_lazy() -> None:
    cache = TicketQualityCache()
    ticket = _FakeTicket("t1", [_full_block(30)] * 6)
    assert cache.is_weak("t1") is False
    v = cache.verdict_for(ticket)
    assert v.plan_skeleton_weak is False
    # Вторая проверка — из кеша, не пересчитывается. Просто убедимся что API одинаковый.
    assert cache.verdict_for(ticket).reason == "ok"


def test_cache_prime_batch() -> None:
    cache = TicketQualityCache()
    good = _FakeTicket("good", [_full_block(30)] * 6)
    weak = _FakeTicket("weak", [_full_block(5)] * 6)
    cache.prime([good, weak])
    assert cache.is_weak("good") is False
    assert cache.is_weak("weak") is True


def test_cache_none_ticket_is_not_weak() -> None:
    cache = TicketQualityCache()
    verdict = cache.verdict_for(None)
    assert verdict.plan_skeleton_weak is False
