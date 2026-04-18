from __future__ import annotations

from infrastructure.ollama.client import OllamaResponse
from infrastructure.ollama.runtime import OllamaRuntimeStatus
from infrastructure.ollama.service import OllamaService


def test_inspect_uses_installed_qwen_fallback_when_preferred_missing(monkeypatch) -> None:
    service = OllamaService("http://localhost:11434")
    monkeypatch.setattr(
        service.runtime,
        "ensure_server_ready",
        lambda wait_timeout_seconds=0: OllamaRuntimeStatus(endpoint_ready=True, models_path="D:/Ollama/models"),
    )
    monkeypatch.setattr(
        service.client,
        "get_tags",
        lambda: OllamaResponse(
            ok=True,
            status_code=200,
            payload={"models": [{"name": "qwen3:latest", "size": 123456789}]},
            latency_ms=12,
        ),
    )

    diagnostics = service.inspect("qwen3:8b")

    assert diagnostics.endpoint_ok is True
    assert diagnostics.model_ok is True
    assert diagnostics.model_name == "qwen3:latest"
    assert "fallback" in diagnostics.model_message.lower()


def test_request_generation_retries_with_family_fallback(monkeypatch) -> None:
    service = OllamaService("http://localhost:11434")
    calls: list[str] = []

    def fake_generate(model: str, prompt: str, *, system: str = "", format_name: str | None = None, temperature: float = 0.2):
        calls.append(model)
        if model == "qwen3:8b":
            return OllamaResponse(False, 404, {}, 10, "model 'qwen3:8b' not found")
        return OllamaResponse(True, 200, {"response": "ok"}, 15)

    monkeypatch.setattr(service.client, "generate", fake_generate)
    monkeypatch.setattr(
        service.client,
        "get_tags",
        lambda: OllamaResponse(
            ok=True,
            status_code=200,
            payload={"models": [{"name": "qwen3:latest"}]},
            latency_ms=4,
        ),
    )

    response = service.request_generation("qwen3:8b", "prompt")

    assert response.ok is True
    assert calls == ["qwen3:8b", "qwen3:latest"]


def test_request_generation_does_not_fallback_to_unrelated_family(monkeypatch) -> None:
    service = OllamaService("http://localhost:11434")
    calls: list[str] = []

    def fake_generate(model: str, prompt: str, *, system: str = "", format_name: str | None = None, temperature: float = 0.2):
        calls.append(model)
        return OllamaResponse(False, 404, {}, 10, "model 'qwen3:8b' not found")

    monkeypatch.setattr(service.client, "generate", fake_generate)
    monkeypatch.setattr(
        service.client,
        "get_tags",
        lambda: OllamaResponse(
            ok=True,
            status_code=200,
            payload={"models": [{"name": "llama3:8b"}]},
            latency_ms=4,
        ),
    )

    response = service.request_generation("qwen3:8b", "prompt")

    assert response.ok is False
    assert calls == ["qwen3:8b"]


def test_review_answer_parses_json_response(monkeypatch) -> None:
    import json
    from infrastructure.ollama.client import OllamaResponse
    from infrastructure.ollama.service import OllamaService

    service = OllamaService("http://localhost:11434")

    verdict_json = json.dumps({
        "thesis_verdicts": [
            {"thesis_label": "Определение", "status": "covered", "comment": "Верно.", "student_excerpt": "Это ресурс."},
            {"thesis_label": "Примеры", "status": "missing", "comment": "Не указаны.", "student_excerpt": ""},
        ],
        "structure_notes": ["Нет вывода"],
        "strengths": ["Точное определение"],
        "recommendations": ["Добавить примеры"],
        "overall_score": 55,
        "overall_comment": "Половина тезисов раскрыта.",
    })

    monkeypatch.setattr(
        service.client,
        "generate",
        lambda model, prompt, *, system="", format_name=None, temperature=0.2: OllamaResponse(
            ok=True, status_code=200, payload={"response": verdict_json}, latency_ms=500,
        ),
    )

    result = service.review_answer(
        "Что такое госсобственность?",
        [{"label": "Определение", "text": "Это..."}, {"label": "Примеры", "text": "Земля..."}],
        "Госсобственность — это ресурс.",
        "qwen3:8b",
    )

    assert result.ok is True
    assert result.used_llm is True
    parsed = json.loads(result.content)
    assert len(parsed["thesis_verdicts"]) == 2
    assert parsed["overall_score"] == 55


def test_review_prompt_includes_all_theses() -> None:
    from infrastructure.ollama.prompts import review_prompt

    theses = [
        {"label": "Определение", "text": "Государственная собственность — это..."},
        {"label": "Примеры", "text": "Земля, здания, транспорт."},
    ]
    system, prompt = review_prompt("Что такое госсобственность?", theses, "Госсобственность — это ресурс.")

    assert "Определение" in prompt
    assert "Примеры" in prompt
    assert "Госсобственность — это ресурс" in prompt
    assert "JSON" in system
    assert "thesis_verdicts" in system or "thesis_verdicts" in prompt
