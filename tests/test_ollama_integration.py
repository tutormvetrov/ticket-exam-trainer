from __future__ import annotations

import pytest

from application.import_service import DocumentImportService, TicketCandidate
from infrastructure.ollama.service import OllamaService

pytestmark = pytest.mark.live_ollama


def test_ollama_connection_check() -> None:
    service = OllamaService("http://localhost:11434", timeout_seconds=30)
    diagnostics = service.inspect("mistral:instruct")
    assert diagnostics.endpoint_ok
    assert diagnostics.model_ok


def test_ollama_fallback_when_unavailable() -> None:
    service = OllamaService("http://localhost:65500", timeout_seconds=1)
    diagnostics = service.inspect("mistral:instruct")
    assert not diagnostics.endpoint_ok


def test_real_response_from_local_model_if_available() -> None:
    service = OllamaService("http://localhost:11434", timeout_seconds=240)
    diagnostics = service.inspect("mistral:instruct")
    if not diagnostics.endpoint_ok or not diagnostics.model_ok:
        pytest.skip("Local Ollama or mistral:instruct is unavailable")

    result = service.rewrite_question(
        "What is active recall?",
        "Active recall is a memory practice based on retrieving information from memory.",
        "mistral:instruct",
    )
    assert result.ok
    assert result.used_llm
    assert result.content


def test_llm_assisted_structuring_if_available() -> None:
    service = OllamaService("http://localhost:11434", timeout_seconds=240)
    diagnostics = service.inspect("mistral:instruct")
    if not diagnostics.endpoint_ok or not diagnostics.model_ok:
        pytest.skip("Local Ollama or mistral:instruct is unavailable")

    import_service = DocumentImportService(
        ollama_service=service,
        llm_model="mistral:instruct",
        enable_llm_structuring=True,
    )
    candidate = TicketCandidate(
        index=1,
        title="What is public property as an object of management?",
        body="Public property is a public resource assigned to public bodies. It has a legal regime and requires control.",
        confidence=0.5,
        section_title="public-assets",
    )
    ticket, used_llm, warning = import_service.build_ticket_map(candidate, "exam-demo", "public-assets", "doc-demo")
    assert warning == ""
    assert used_llm
    assert len(ticket.atoms) >= 2
