"""Unit-тесты ``review_prompt`` из ``infrastructure/ollama/prompts.py``.

Цель — гарантировать, что новый промпт:
- написан на русском (без 'You are …');
- содержит few-shot примеры (минимум два: excellent + weak);
- явно описывает рубрику overall_score с числовыми порогами;
- заканчивается требованием написать <reasoning>…</reasoning> перед JSON;
- не теряет сериализацию reference theses (они подставляются в user prompt).
"""
from __future__ import annotations

import re

from infrastructure.ollama.prompts import review_prompt, review_system_prompt


REFERENCE_THESES = [
    {"label": "Понятие", "text": "Определение ключевого термина."},
    {"label": "Пример", "text": "Уместный пример из практики."},
]


def test_system_prompt_is_in_russian() -> None:
    system = review_system_prompt()
    # Должна быть кириллица.
    assert re.search(r"[А-Яа-яЁё]", system) is not None
    # Не должно быть 'You are ...' или других английских директив.
    assert "You are" not in system
    assert "You are a strict" not in system
    assert "covered" in system  # status labels остаются английскими — это часть API
    assert "partial" in system
    assert "missing" in system


def test_system_prompt_mentions_numeric_rubric_thresholds() -> None:
    system = review_system_prompt()
    # Явные пороги оценки должны быть: 90, 70, 50, 30.
    for threshold in ("90", "70", "50", "30"):
        assert threshold in system, f"Missing rubric threshold '{threshold}'"


def test_system_prompt_requires_reasoning_before_json() -> None:
    system = review_system_prompt()
    assert "<reasoning>" in system
    assert "</reasoning>" in system
    # И требование валидного JSON.
    assert "JSON" in system


def test_user_prompt_contains_fewshot_examples() -> None:
    _, prompt = review_prompt("Бюджетное устройство РФ", REFERENCE_THESES, "Студент написал ответ.")
    # Few-shot-маркеры.
    assert "Example 1" in prompt
    assert "Example 2" in prompt
    # Хотя бы один overall_score у примеров (~90 в хорошем, ~25 в слабом).
    assert "overall_score" in prompt
    assert "\"overall_score\": 90" in prompt
    assert "\"overall_score\": 25" in prompt
    # Оба примера должны содержать reasoning-блоки.
    assert prompt.count("<reasoning>") >= 2
    assert prompt.count("</reasoning>") >= 2


def test_user_prompt_includes_real_task_details() -> None:
    ticket_title = "Бюджетное устройство Российской Федерации"
    student_answer = "Это очень важная тема для ГМУ."
    _, prompt = review_prompt(ticket_title, REFERENCE_THESES, student_answer)
    assert ticket_title in prompt
    assert student_answer in prompt
    # Тезисы должны попасть в тело промпта.
    for thesis in REFERENCE_THESES:
        assert thesis["label"] in prompt
        assert thesis["text"] in prompt


def test_user_prompt_ends_with_explicit_instruction() -> None:
    """Завершающая инструкция должна напомнить формат: reasoning + JSON."""
    _, prompt = review_prompt("T", REFERENCE_THESES, "a")
    # Последний блок содержит напоминание про reasoning и JSON.
    tail = prompt.splitlines()[-1]
    # Tail может быть многословным — главное, чтобы упоминал reasoning+JSON.
    assert "reasoning" in prompt.lower()
    assert "JSON" in prompt or "json" in prompt
    assert "reasoning" in tail.lower() or "JSON" in tail or "json" in tail
