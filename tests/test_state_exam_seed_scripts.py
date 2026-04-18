from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from docx import Document

from application.settings import DEFAULT_OLLAMA_SETTINGS
from application.settings_store import SettingsStore
from infrastructure.db import connect_initialized, get_database_path
from scripts.build_state_exam_seed import (
    DEFAULT_OUTPUT_DB,
    MANIFEST_SCHEMA_VERSION,
    SeedBuildSummary,
    REPO_ROOT,
    _ensure_qwen_model,
    default_summary_json,
    publish_seed_database,
    run_import_pipeline,
    write_manifest,
)
from scripts.verify_state_exam_seed import verify_state_exam_seed_database
from application.facade import AppFacade


STATE_EXAM_TEXT = (
    "Билет 1. Что представляет собой государственное имущество как объект управления? "
    "Актуальность темы связана с управлением публичными ресурсами и эффективностью власти. "
    "Теоретическая часть включает понятие имущества, правовой режим и управленческий цикл. "
    "Практическая часть раскрывается через учет, оценку, контроль и выбор решений. "
    "Навыки проявляются через анализ, аргументацию и применение методов управления. "
    "В заключении имущество рассматривается как активный управленческий ресурс. "
    "Дополнительно полезны схемы и сравнительный анализ практик."
)


def _build_facade(tmp_path: Path) -> AppFacade:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    settings_store.save(
        replace(
            DEFAULT_OLLAMA_SETTINGS,
            auto_check_ollama_on_start=False,
            auto_check_updates_on_start=False,
            import_llm_assist=False,
            examiner_followups=False,
            rewrite_questions=False,
        )
    )
    return AppFacade(workspace_root, connection, settings_store)


class _FakeImportResult:
    def __init__(self, *, resume_available: bool, done: int, pending: int) -> None:
        self.ok = True
        self.document_id = "doc-demo"
        self.document_title = "State exam"
        self.status = "partial_llm" if resume_available else "structured"
        self.tickets_created = 3
        self.llm_done_tickets = done
        self.llm_pending_tickets = pending
        self.llm_fallback_tickets = 0
        self.llm_failed_tickets = 0
        self.resume_available = resume_available
        self.warnings = []
        self.error = ""


class _FakeFacade:
    def __init__(self) -> None:
        self.complete_calls = []

    def complete_import_with_progress(self, *args, **kwargs):
        self.complete_calls.append(kwargs)
        return _FakeImportResult(resume_available=False, done=3, pending=0)


def test_run_import_pipeline_uses_unbounded_generation_timeout() -> None:
    facade = _FakeFacade()
    result = run_import_pipeline(facade, Path("demo.pdf"), max_resume_passes=2)
    assert result.resume_available is False
    assert facade.complete_calls[0]["generation_timeout_seconds"] is None
    assert facade.complete_calls[0]["max_resume_passes"] == 2


def test_publish_seed_database_copies_workspace_db_atomically(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    source_db = workspace_root / "exam_trainer.db"
    source_db.write_bytes(b"seed-demo")
    output_db = tmp_path / "sample_data" / "seed" / "demo.db"
    publish_seed_database(workspace_root, output_db)
    assert output_db.read_bytes() == b"seed-demo"


def test_default_output_db_lives_under_build_demo_seed() -> None:
    expected = REPO_ROOT / "build" / "demo_seed" / "state_exam_public_admin_demo.db"
    assert DEFAULT_OUTPUT_DB == expected


def test_default_summary_json_sits_next_to_seed_db(tmp_path: Path) -> None:
    seed_path = tmp_path / "demo" / "seed.db"
    assert default_summary_json(seed_path) == seed_path.with_name("seed.manifest.json")


def test_ensure_qwen_model_accepts_qwen_family() -> None:
    _ensure_qwen_model("qwen3:4b")
    _ensure_qwen_model("qwen3:8b")
    _ensure_qwen_model("Qwen3:14B")
    _ensure_qwen_model("  qwen3:0.6b  ")


@pytest.mark.parametrize("bad_model", ["mistral:7b", "llama3:8b", "gemma2:9b", ""])
def test_ensure_qwen_model_rejects_non_qwen(bad_model: str) -> None:
    with pytest.raises(RuntimeError, match="qwen"):
        _ensure_qwen_model(bad_model)


def test_write_manifest_captures_actual_counts_and_checksum(tmp_path: Path) -> None:
    output_db = tmp_path / "demo" / "seed.db"
    output_db.parent.mkdir(parents=True, exist_ok=True)
    output_db.write_bytes(b"seed-data")
    summary = SeedBuildSummary(
        output_db=output_db,
        status="structured",
        document_id="doc-1",
        document_title="State Exam Demo",
        documents=1,
        tickets_created=17,
        sections=3,
        queue_items=17,
        llm_done_tickets=17,
        llm_pending_tickets=0,
        llm_fallback_tickets=0,
        llm_failed_tickets=0,
        warnings=["minor warning"],
        model_used="qwen3:4b",
        source_pdf=tmp_path / "source.pdf",
        checksum_sha256="deadbeef",
        size_bytes=9,
        built_at="2026-04-17T12:00:00+00:00",
    )

    manifest_path = tmp_path / "demo" / "seed.manifest.json"
    write_manifest(summary, manifest_path)

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert payload["tickets"] == 17
    assert payload["sections"] == 3
    assert payload["documents"] == 1
    assert payload["model_used"] == "qwen3:4b"
    assert payload["checksum_sha256"] == "deadbeef"
    assert payload["size_bytes"] == 9
    assert payload["warnings"] == ["minor warning"]


def test_verify_state_exam_seed_database_accepts_real_seed(tmp_path: Path) -> None:
    document_path = tmp_path / "state-exam.docx"
    document = Document()
    document.add_paragraph(STATE_EXAM_TEXT)
    document.save(document_path)

    facade = _build_facade(tmp_path)
    facade.save_settings(
        replace(
            facade.settings,
            base_url="http://localhost:65500",
            timeout_seconds=1,
            examiner_followups=False,
            rewrite_questions=False,
        )
    )
    result = facade.import_document_with_progress(document_path, answer_profile_code="state_exam_public_admin")
    assert result.ok
    facade.connection.close()

    workspace_root = tmp_path / "workspace"
    seed_db = tmp_path / "sample_data" / "seed" / "state_exam_public_admin_demo.db"
    publish_seed_database(workspace_root, seed_db)
    summary = verify_state_exam_seed_database(
        seed_db,
        settings=replace(
            DEFAULT_OLLAMA_SETTINGS,
            base_url="http://localhost:65500",
            timeout_seconds=1,
            examiner_followups=False,
            rewrite_questions=False,
        ),
    )
    assert summary.documents >= 1
    assert summary.tickets >= 1
    assert summary.queue_items >= 1
    assert summary.attempts >= 3
    assert summary.block_attempt_scores >= 6
