from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.release_seed import resolve_seed_database
from application.facade import AppFacade
from application.settings import OllamaSettings
from application.settings_store import SettingsStore
from domain.answer_profile import AnswerProfileCode
from infrastructure.db import connect_initialized, get_database_path
from scripts.build_state_exam_seed import load_seed_settings


@dataclass(slots=True)
class SeedVerificationSummary:
    documents: int
    tickets: int
    queue_items: int
    attempts: int
    block_attempt_scores: int
    reviewed_ticket_id: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a built state-exam seed database is trainable.")
    parser.add_argument("--seed-db", type=Path, required=True, help="Path to the seed database produced by build_state_exam_seed.py.")
    return parser.parse_args()


def _answer_text(ticket, *, full: bool) -> str:
    if ticket.answer_blocks:
        parts = [
            block.expected_content.strip()
            for block in ticket.answer_blocks
            if not block.is_missing and block.expected_content.strip()
        ]
        if parts:
            limit = 6 if full else 3
            return "\n\n".join(parts[:limit])
    atom_parts = [atom.text.strip() for atom in ticket.atoms if atom.text.strip()]
    limit = 6 if full else 3
    if atom_parts:
        return "\n\n".join(atom_parts[:limit])
    return ticket.canonical_answer_summary


def verify_state_exam_seed_database(seed_db: Path, *, settings: OllamaSettings | None = None) -> SeedVerificationSummary:
    resolved_seed = resolve_seed_database(seed_db)
    if resolved_seed is None:
        raise RuntimeError("Seed database path is empty")
    repo_root = REPO_ROOT
    with tempfile.TemporaryDirectory(prefix="tezis-state-exam-verify-") as temp_dir:
        workspace_root = Path(temp_dir) / "workspace"
        workspace_root.mkdir(parents=True, exist_ok=True)
        workspace_db = get_database_path(workspace_root)
        shutil.copy2(resolved_seed, workspace_db)
        settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
        settings_store.save(settings or load_seed_settings(repo_root))
        connection = connect_initialized(workspace_db)
        facade = AppFacade(workspace_root, connection, settings_store)
        try:
            documents = facade.load_documents()
            tickets = [
                ticket
                for ticket in facade.load_ticket_maps()
                if ticket.answer_profile_code is AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN
            ]
            if not documents:
                raise RuntimeError("Seed database does not contain documents")
            if not tickets:
                raise RuntimeError("Seed database does not contain state exam tickets")

            tickets_without_atoms = [t for t in tickets if not t.atoms]
            if tickets_without_atoms:
                example = tickets_without_atoms[0].ticket_id
                raise RuntimeError(
                    f"Seed contains {len(tickets_without_atoms)} ticket(s) with no atoms "
                    f"(Ключевые узлы would show '—'). Example: {example}"
                )

            snapshot = facade.load_training_snapshot(tickets=tickets)
            if not snapshot.queue_items:
                raise RuntimeError("Training snapshot queue is empty")

            sampled_tickets = (tickets * 3)[:3]
            active_result = facade.evaluate_answer(
                sampled_tickets[0].ticket_id, "active-recall", _answer_text(sampled_tickets[0], full=False)
            )
            plan_result = facade.evaluate_answer(
                sampled_tickets[1].ticket_id, "plan", _answer_text(sampled_tickets[1], full=False)
            )
            state_exam_result = facade.evaluate_answer(
                sampled_tickets[2].ticket_id, "state-exam-full", _answer_text(sampled_tickets[2], full=True)
            )

            if not active_result.ok or not plan_result.ok or not state_exam_result.ok:
                raise RuntimeError("One of the training evaluations failed")
            if state_exam_result.review is None:
                raise RuntimeError("State exam evaluation did not return review verdict")
            if not state_exam_result.block_scores:
                raise RuntimeError("State exam evaluation did not produce block scores")

            attempts = int(connection.execute("SELECT COUNT(*) AS total FROM attempts").fetchone()["total"] or 0)
            block_attempt_scores = int(
                connection.execute("SELECT COUNT(*) AS total FROM attempt_block_scores").fetchone()["total"] or 0
            )
            if attempts < 3:
                raise RuntimeError("Seed verification did not persist enough attempts")
            if block_attempt_scores < len(state_exam_result.block_scores):
                raise RuntimeError("State exam verification did not persist block attempt scores")

            return SeedVerificationSummary(
                documents=len(documents),
                tickets=len(tickets),
                queue_items=len(snapshot.queue_items),
                attempts=attempts,
                block_attempt_scores=block_attempt_scores,
                reviewed_ticket_id=sampled_tickets[2].ticket_id,
            )
        finally:
            facade.connection.close()


def main() -> int:
    args = parse_args()
    summary = verify_state_exam_seed_database(args.seed_db)
    print(
        f"Verified seed: documents={summary.documents}; tickets={summary.tickets}; "
        f"queue={summary.queue_items}; attempts={summary.attempts}; "
        f"attempt_block_scores={summary.block_attempt_scores}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
