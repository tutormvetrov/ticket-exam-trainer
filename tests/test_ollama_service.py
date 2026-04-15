from __future__ import annotations

from infrastructure.ollama.client import OllamaResponse
from infrastructure.ollama.runtime import OllamaRuntimeStatus
from infrastructure.ollama.service import OllamaService


def test_inspect_uses_installed_qwen_fallback_when_preferred_missing(monkeypatch) -> None:
    service = OllamaService("http://localhost:11434")
    monkeypatch.setattr(
        service.runtime,
        "ensure_server_ready",
        lambda wait_timeout_seconds=0: OllamaRuntimeStatus(endpoint_ready=True, models_path="D:/OllamaModels"),
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
