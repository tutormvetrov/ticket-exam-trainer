from __future__ import annotations

from unittest.mock import patch

from infrastructure.ollama.client import (
    DEFAULT_GENERATION_TIMEOUT_SECONDS,
    DEFAULT_INSPECT_TIMEOUT_SECONDS,
    OllamaClient,
)


class _FakeResponse:
    def __init__(self) -> None:
        self.ok = True
        self.status_code = 200
        self.text = ""

    def json(self) -> dict:
        return {"models": []}


def test_default_timeouts_are_split() -> None:
    client = OllamaClient("http://localhost:11434")
    assert client.inspect_timeout_seconds == DEFAULT_INSPECT_TIMEOUT_SECONDS
    assert client.generation_timeout_seconds == DEFAULT_GENERATION_TIMEOUT_SECONDS


def test_legacy_timeout_arg_maps_to_generation() -> None:
    # Обратная совместимость: старый код звал OllamaClient(url, 120).
    client = OllamaClient("http://localhost:11434", 120.0)
    assert client.generation_timeout_seconds == 120.0
    assert client.inspect_timeout_seconds == DEFAULT_INSPECT_TIMEOUT_SECONDS


def test_get_tags_uses_inspect_timeout() -> None:
    client = OllamaClient(
        "http://localhost:11434",
        inspect_timeout_seconds=1.5,
        generation_timeout_seconds=90.0,
    )
    with patch("infrastructure.ollama.client.requests.request", return_value=_FakeResponse()) as mock_req:
        client.get_tags()
    assert mock_req.call_args.kwargs["timeout"] == 1.5


def test_generate_uses_generation_timeout() -> None:
    client = OllamaClient(
        "http://localhost:11434",
        inspect_timeout_seconds=1.5,
        generation_timeout_seconds=90.0,
    )
    with patch("infrastructure.ollama.client.requests.request", return_value=_FakeResponse()) as mock_req:
        client.generate("qwen3:8b", "hello")
    assert mock_req.call_args.kwargs["timeout"] == 90.0
