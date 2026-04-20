from __future__ import annotations

import json
from types import SimpleNamespace

from infrastructure.ollama import OllamaBootstrapStatus
from infrastructure.ollama.service import OllamaScenarioResult
from tests.support.workspace_builder import (
    create_workspace_bundle,
    seed_standard_document,
    seed_state_exam_document,
)


class _OfflineProbeService:
    def __init__(self) -> None:
        self.client = SimpleNamespace(
            get_tags=lambda: SimpleNamespace(ok=False, error="offline"),
        )
        self.followup_calls = 0
        self.review_calls = 0

    def generate_followup_questions(self, *args, **kwargs):
        self.followup_calls += 1
        return OllamaScenarioResult(True, "- should not be used", True, 1)

    def review_answer(self, *args, **kwargs):
        self.review_calls += 1
        payload = json.dumps(
            {
                "thesis_verdicts": [],
                "structure_notes": [],
                "strengths": [],
                "recommendations": [],
                "overall_score": 99,
                "overall_comment": "should not be used",
            },
            ensure_ascii=False,
        )
        return OllamaScenarioResult(True, payload, True, 1)


class _TrustedFakeReviewService:
    def __init__(self) -> None:
        self.review_calls = 0

    def review_answer(self, *args, **kwargs):
        self.review_calls += 1
        payload = json.dumps(
            {
                "thesis_verdicts": [
                    {
                        "thesis_label": "Definition",
                        "status": "covered",
                        "comment": "ok",
                        "student_excerpt": "resource",
                    }
                ],
                "structure_notes": [],
                "strengths": ["strong"],
                "recommendations": ["add examples"],
                "overall_score": 88,
                "overall_comment": "LLM verdict",
            },
            ensure_ascii=False,
        )
        return OllamaScenarioResult(True, payload, True, 1)


class _BootstrapReadyService(_TrustedFakeReviewService):
    def __init__(self) -> None:
        super().__init__()
        self.ensure_calls: list[str] = []

    def ensure_bootstrap_ready(self, preferred_model: str):
        self.ensure_calls.append(preferred_model)
        return OllamaBootstrapStatus(
            state="ready",
            preferred_model=preferred_model,
            resolved_model=preferred_model,
            endpoint_ready=True,
        )


def test_evaluate_answer_review_falls_back_when_probe_is_offline(tmp_path, monkeypatch) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_standard_document(bundle)
        ticket = bundle.facade.load_ticket_maps()[0]
        answer_text = ticket.canonical_answer_summary or "\n\n".join(atom.text for atom in ticket.atoms[:3])
        fake_service = _OfflineProbeService()
        monkeypatch.setattr(type(bundle.facade), "build_ollama_service", lambda self, timeout_seconds=None: fake_service)

        result = bundle.facade.evaluate_answer(
            ticket.ticket_id,
            "review",
            answer_text,
            include_followups=False,
        )

        assert result.ok
        assert result.review is not None
        assert result.review.overall_comment
        assert fake_service.review_calls == 0
        assert result.used_fallback is True
        assert result.used_llm is False
        assert result.ollama_status == "installed_not_running"
    finally:
        bundle.close()


def test_evaluate_answer_state_exam_falls_back_without_llm_review_call(tmp_path, monkeypatch) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_state_exam_document(bundle)
        ticket = bundle.facade.load_ticket_maps()[0]
        answer_text = ticket.canonical_answer_summary or "\n\n".join(atom.text for atom in ticket.atoms[:3])
        fake_service = _OfflineProbeService()
        monkeypatch.setattr(type(bundle.facade), "build_ollama_service", lambda self, timeout_seconds=None: fake_service)

        result = bundle.facade.evaluate_answer(
            ticket.ticket_id,
            "state-exam-full",
            answer_text,
            include_followups=False,
        )

        assert result.ok
        assert result.review is not None
        assert result.block_scores
        assert result.criterion_scores
        assert fake_service.review_calls == 0
        assert result.used_fallback is True
        assert result.ollama_status == "installed_not_running"
    finally:
        bundle.close()


def test_evaluate_answer_trusts_fake_service_without_probe_client(tmp_path, monkeypatch) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_standard_document(bundle)
        ticket = bundle.facade.load_ticket_maps()[0]
        answer_text = ticket.canonical_answer_summary or "\n\n".join(atom.text for atom in ticket.atoms[:3])
        fake_service = _TrustedFakeReviewService()
        recorded_timeouts: list[float | None] = []

        def _build_service(self, timeout_seconds=None):
            recorded_timeouts.append(timeout_seconds)
            return fake_service

        monkeypatch.setattr(type(bundle.facade), "build_ollama_service", _build_service)

        result = bundle.facade.evaluate_answer(
            ticket.ticket_id,
            "review",
            answer_text,
            include_followups=False,
        )

        assert result.ok
        assert result.review is not None
        assert result.review.overall_comment == "LLM verdict"
        assert fake_service.review_calls == 1
        assert recorded_timeouts == [5.0]
        assert result.used_llm is True
        assert result.used_fallback is False
    finally:
        bundle.close()


def test_evaluate_answer_ensures_runtime_before_reviewing(tmp_path, monkeypatch) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_standard_document(bundle)
        ticket = bundle.facade.load_ticket_maps()[0]
        answer_text = ticket.canonical_answer_summary or "\n\n".join(atom.text for atom in ticket.atoms[:3])
        fake_service = _BootstrapReadyService()

        monkeypatch.setattr(type(bundle.facade), "build_ollama_service", lambda self, timeout_seconds=None: fake_service)

        result = bundle.facade.evaluate_answer(
            ticket.ticket_id,
            "review",
            answer_text,
            include_followups=False,
        )

        assert result.ok
        assert result.review is not None
        assert result.review.overall_comment == "LLM verdict"
        assert fake_service.ensure_calls == ["qwen3:8b"]
        assert result.used_llm is True
        assert result.ollama_status == "ready"
    finally:
        bundle.close()
