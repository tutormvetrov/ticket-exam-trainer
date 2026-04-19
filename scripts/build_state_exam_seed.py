from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from application.facade import AppFacade
from application.settings import DEFAULT_OLLAMA_SETTINGS, OllamaSettings
from application.settings_store import SettingsStore
from domain.answer_profile import AnswerProfileCode
from infrastructure.db import connect_initialized, get_database_path

DEFAULT_OUTPUT_DB = REPO_ROOT / "build" / "demo_seed" / "state_exam_public_admin_demo.db"
REQUIRED_MODEL_FAMILY = "qwen"
MANIFEST_SCHEMA_VERSION = 1


@dataclass(slots=True)
class SeedBuildSummary:
    output_db: Path
    status: str
    document_id: str
    document_title: str
    documents: int
    tickets_created: int
    sections: int
    queue_items: int
    llm_done_tickets: int
    llm_pending_tickets: int
    llm_fallback_tickets: int
    llm_failed_tickets: int
    warnings: list[str]
    model_used: str
    source_pdf: Path
    checksum_sha256: str
    size_bytes: int
    built_at: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the public demo seed database from a source PDF.")
    parser.add_argument("--source-pdf", type=Path, required=True, help="Absolute path to the source PDF (kept outside of git).")
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB, help="Output seed database path. Defaults to build/demo_seed/.")
    parser.add_argument("--summary-json", type=Path, default=None, help="Path to write the manifest JSON next to the seed database.")
    parser.add_argument("--max-resume-passes", type=int, default=4)
    parser.add_argument("--model", default="", help="Override Ollama model for the seed import (must be qwen-family).")
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=4,
        help="Number of concurrent LLM workers for resume phase (1 = sequential).",
    )
    return parser.parse_args()


def _progress_logger(stream: TextIO):
    encoding = getattr(stream, "encoding", None) or "utf-8"

    def _callback(percent: int, stage: str, detail: str = "") -> None:
        line = f"[{percent:3d}%] {stage}"
        if detail:
            line = f"{line}: {detail}"
        safe_line = line.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe_line, file=stream, flush=True)

    return _callback


def load_seed_settings(repo_root: Path, *, model_override: str = "") -> OllamaSettings:
    settings_path = repo_root / "app_data" / "settings.json"
    if settings_path.exists():
        base_settings = SettingsStore(settings_path).load()
    else:
        base_settings = DEFAULT_OLLAMA_SETTINGS
    return replace(
        base_settings,
        import_llm_assist=True,
        examiner_followups=False,
        rewrite_questions=False,
        auto_check_ollama_on_start=False,
        auto_check_updates_on_start=False,
        rule_based_fallback=True,
        model=model_override.strip() or base_settings.model,
    )


def publish_seed_database(workspace_root: Path, output_db: Path) -> Path:
    source_db = get_database_path(workspace_root)
    if not source_db.exists():
        raise RuntimeError(f"Seed workspace database not found: {source_db}")
    # SQLite работает в WAL-режиме: свежие коммиты уходят в .db-wal и не
    # попадают в сам .db-файл, пока не отработал checkpoint. Без этого шага
    # копия будет stale (последнее состояние импорта потеряется — например,
    # status "partial_llm" из _finalize_import_document).
    _checkpoint_sqlite_wal(source_db)
    output_db.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_db.with_name(f"{output_db.name}.tmp-{uuid4().hex[:8]}")
    shutil.copy2(source_db, temp_output)
    temp_output.replace(output_db)
    return output_db


def _checkpoint_sqlite_wal(database_path: Path) -> None:
    """Запускает PRAGMA wal_checkpoint(TRUNCATE) на SQLite-базе, если файл
    действительно SQLite и имеет открытый WAL. Для юнит-тестов, где в файле
    лежат произвольные байты, молча выходим."""
    import sqlite3

    try:
        connection = sqlite3.connect(database_path)
    except sqlite3.DatabaseError:
        return
    try:
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            connection.commit()
        except sqlite3.DatabaseError:
            # Файл не содержит валидной SQLite-базы (например, тестовый
            # placeholder) — просто оставляем как есть и полагаемся на copy2.
            return
    finally:
        connection.close()


def run_import_pipeline(
    facade: AppFacade,
    source_pdf: Path,
    *,
    progress_callback=None,
    max_resume_passes: int = 4,
    parallel_workers: int = 1,
):
    return facade.complete_import_with_progress(
        source_pdf,
        answer_profile_code=AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN,
        progress_callback=progress_callback,
        max_resume_passes=max_resume_passes,
        generation_timeout_seconds=None,
        parallel_workers=parallel_workers,
    )


def _checksum_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_qwen_model(model_name: str) -> None:
    lowered = (model_name or "").strip().lower()
    if not lowered.startswith(REQUIRED_MODEL_FAMILY):
        raise RuntimeError(
            f"Public seed pipeline requires a qwen-family model, got: {model_name!r}"
        )


def default_summary_json(output_db: Path) -> Path:
    return output_db.with_name(f"{output_db.stem}.manifest.json")


def write_manifest(summary: SeedBuildSummary, manifest_path: Path) -> Path:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "output_db": str(summary.output_db),
        "source_pdf": str(summary.source_pdf),
        "built_at": summary.built_at,
        "status": summary.status,
        "document_id": summary.document_id,
        "document_title": summary.document_title,
        "documents": summary.documents,
        "tickets": summary.tickets_created,
        "sections": summary.sections,
        "queue_items": summary.queue_items,
        "model_used": summary.model_used,
        "llm_done": summary.llm_done_tickets,
        "llm_pending": summary.llm_pending_tickets,
        "llm_fallback": summary.llm_fallback_tickets,
        "llm_failed": summary.llm_failed_tickets,
        "warnings": list(summary.warnings),
        "checksum_sha256": summary.checksum_sha256,
        "size_bytes": summary.size_bytes,
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    return manifest_path


def build_seed_database(
    source_pdf: Path,
    output_db: Path,
    *,
    max_resume_passes: int = 4,
    model_override: str = "",
    stream: TextIO | None = None,
    parallel_workers: int = 1,
) -> SeedBuildSummary:
    repo_root = REPO_ROOT
    progress_stream = stream or sys.stdout
    source_pdf = source_pdf.expanduser().resolve(strict=True)
    output_db = output_db.expanduser().resolve()

    with tempfile.TemporaryDirectory(prefix="tezis-state-exam-seed-") as temp_dir:
        workspace_root = Path(temp_dir) / "workspace"
        workspace_root.mkdir(parents=True, exist_ok=True)
        settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
        settings_store.save(load_seed_settings(repo_root, model_override=model_override))
        connection = connect_initialized(get_database_path(workspace_root))
        facade = AppFacade(workspace_root, connection, settings_store)
        try:
            diagnostics = facade.inspect_ollama()
            if not diagnostics.endpoint_ok:
                raise RuntimeError(diagnostics.error_text or diagnostics.endpoint_message)
            resolved_model = diagnostics.model_name or facade.settings.model
            _ensure_qwen_model(resolved_model)
            if resolved_model and resolved_model != facade.settings.model:
                facade.save_settings(replace(facade.settings, model=resolved_model))
            print(f"Using model: {facade.settings.model}", file=progress_stream, flush=True)
            print(f"Parallel workers: {parallel_workers}", file=progress_stream, flush=True)
            result = run_import_pipeline(
                facade,
                source_pdf,
                progress_callback=_progress_logger(progress_stream),
                max_resume_passes=max_resume_passes,
                parallel_workers=parallel_workers,
            )
            if not result.ok:
                raise RuntimeError(result.error or "State exam seed import failed")
            ticket_total = int(
                facade.connection.execute(
                    "SELECT COUNT(*) AS total FROM tickets WHERE answer_profile_code = ?",
                    (AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN.value,),
                ).fetchone()["total"]
                or 0
            )
            if ticket_total <= 0:
                raise RuntimeError("State exam seed import produced no tickets")

            documents_total = int(
                facade.connection.execute("SELECT COUNT(*) AS total FROM source_documents").fetchone()["total"]
                or 0
            )
            sections_total = int(
                facade.connection.execute(
                    "SELECT COUNT(DISTINCT section_id) AS total FROM tickets WHERE answer_profile_code = ?",
                    (AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN.value,),
                ).fetchone()["total"]
                or 0
            )
            queue_total = int(
                facade.connection.execute(
                    "SELECT COUNT(*) AS total FROM import_ticket_queue WHERE document_id = ?",
                    (result.document_id,),
                ).fetchone()["total"]
                or 0
            )
            publish_seed_database(workspace_root, output_db)
            checksum = _checksum_sha256(output_db)
            size_bytes = output_db.stat().st_size
            built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            return SeedBuildSummary(
                output_db=output_db,
                status=result.status,
                document_id=result.document_id,
                document_title=result.document_title,
                documents=documents_total,
                tickets_created=ticket_total,
                sections=sections_total,
                queue_items=queue_total,
                llm_done_tickets=result.llm_done_tickets,
                llm_pending_tickets=result.llm_pending_tickets,
                llm_fallback_tickets=result.llm_fallback_tickets,
                llm_failed_tickets=result.llm_failed_tickets,
                warnings=result.warnings,
                model_used=facade.settings.model,
                source_pdf=source_pdf,
                checksum_sha256=checksum,
                size_bytes=size_bytes,
                built_at=built_at,
            )
        finally:
            facade.connection.close()


def main() -> int:
    args = parse_args()
    summary = build_seed_database(
        args.source_pdf,
        args.output_db,
        max_resume_passes=max(0, args.max_resume_passes),
        model_override=args.model,
        parallel_workers=max(1, args.parallel_workers),
    )
    manifest_path = args.summary_json or default_summary_json(summary.output_db)
    write_manifest(summary, manifest_path)
    print(f"Seed database: {summary.output_db}")
    print(f"Manifest: {manifest_path}")
    print(
        "Status: "
        f"{summary.status}; documents={summary.documents}; tickets={summary.tickets_created}; "
        f"sections={summary.sections}; queue={summary.queue_items}; "
        f"llm_done={summary.llm_done_tickets}; pending={summary.llm_pending_tickets}; "
        f"fallback={summary.llm_fallback_tickets}; failed={summary.llm_failed_tickets}"
    )
    print(f"Model used: {summary.model_used}")
    print(f"Checksum (sha256): {summary.checksum_sha256}")
    if summary.warnings:
        print(f"Warnings: {len(summary.warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
