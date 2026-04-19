"""Тесты на ``extract_json_from_response`` из ``application/scoring.py``.

Сценарии:
- JSON после ``</reasoning>`` — успешно извлекается;
- чистый JSON без reasoning — тоже;
- JSON с ведущими пробелами/скобками вне структуры;
- полностью мусорный текст — исключение.
"""
from __future__ import annotations

import json

import pytest

from application.scoring import extract_json_from_response

SAMPLE_PAYLOAD = {
    "thesis_verdicts": [
        {"thesis_label": "A", "status": "covered", "comment": "ok", "student_excerpt": "x"}
    ],
    "structure_notes": ["note"],
    "strengths": ["strong"],
    "recommendations": ["r"],
    "overall_score": 85,
    "overall_comment": "good",
}


def _json_str(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def test_extract_json_after_reasoning_block() -> None:
    raw = (
        "<reasoning>Тезисы раскрыты. Есть нормативная база. "
        "Есть пример. Итого — 85.</reasoning>\n"
        + _json_str(SAMPLE_PAYLOAD)
    )
    result = extract_json_from_response(raw)
    assert result["overall_score"] == 85
    assert result["thesis_verdicts"][0]["status"] == "covered"


def test_extract_plain_json_without_reasoning() -> None:
    result = extract_json_from_response(_json_str(SAMPLE_PAYLOAD))
    assert result["overall_score"] == 85


def test_extract_json_with_leading_and_trailing_whitespace() -> None:
    result = extract_json_from_response("   \n\n  " + _json_str(SAMPLE_PAYLOAD) + "\n\n  ")
    assert result["overall_score"] == 85


def test_extract_json_with_noise_before_and_after() -> None:
    raw = (
        "Некоторый пояснительный текст от модели.\n"
        + _json_str(SAMPLE_PAYLOAD)
        + "\nЕщё немного текста после."
    )
    result = extract_json_from_response(raw)
    assert result["overall_score"] == 85


def test_extract_json_with_reasoning_and_noise() -> None:
    raw = (
        "Думаю так: <reasoning>студент справился</reasoning>\n"
        "  \n"
        + _json_str(SAMPLE_PAYLOAD)
    )
    result = extract_json_from_response(raw)
    assert result["overall_comment"] == "good"


def test_empty_string_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        extract_json_from_response("")


def test_fully_malformed_input_raises() -> None:
    with pytest.raises((json.JSONDecodeError, ValueError)):
        extract_json_from_response("просто текст без скобок")


def test_non_object_payload_raises_value_error() -> None:
    """Если модель вернула массив вместо объекта — это не наша схема, падаем."""
    raw = "[1, 2, 3]"
    with pytest.raises(ValueError):
        extract_json_from_response(raw)


def test_reasoning_only_output_raises() -> None:
    """Если модель отдала только reasoning без JSON — возвращаем ошибку."""
    raw = "<reasoning>сыровато</reasoning>"
    with pytest.raises((json.JSONDecodeError, ValueError)):
        extract_json_from_response(raw)
