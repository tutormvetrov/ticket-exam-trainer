from __future__ import annotations

from tests.support.workspace_builder import create_workspace_bundle, seed_standard_document


def test_standard_ticket_training_contract_persists_attempts(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        seed_standard_document(bundle)
        ticket = bundle.facade.load_ticket_maps()[0]
        answer_text = ticket.canonical_answer_summary or "\n\n".join(atom.text for atom in ticket.atoms[:3])

        reading = bundle.facade.evaluate_answer(
            ticket.ticket_id,
            "reading",
            answer_text,
            include_followups=False,
        )
        review = bundle.facade.evaluate_answer(
            ticket.ticket_id,
            "review",
            answer_text,
            include_followups=False,
        )

        attempts_total = bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM attempts").fetchone()["total"]
        sessions_week = bundle.facade.load_statistics_snapshot().sessions_week

        assert reading.ok
        assert review.ok
        assert review.review is not None
        assert attempts_total >= 2
        assert sessions_week >= 2
    finally:
        bundle.close()

