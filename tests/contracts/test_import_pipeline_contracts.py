from __future__ import annotations

from tests.support.workspace_builder import create_workspace_bundle, seed_standard_document, seed_state_exam_document


def test_standard_import_contract_creates_trainable_snapshot(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        result = seed_standard_document(bundle)

        assert result.ok
        assert result.status == "structured"
        assert result.tickets_created == 3

        documents = bundle.facade.load_documents()
        tickets = bundle.facade.load_ticket_maps()
        snapshot = bundle.facade.load_training_snapshot(tickets)

        assert len(documents) == 1
        assert documents[0].tickets_count == 3
        assert len(tickets) == 3
        assert snapshot.queue_items
        assert snapshot.tickets
        assert all(ticket.title.strip() for ticket in tickets)
        assert all(ticket.canonical_answer_summary.strip() for ticket in tickets)
        assert all(ticket.atoms for ticket in tickets)
        assert all(ticket.exercise_templates for ticket in tickets)
    finally:
        bundle.close()


def test_state_exam_import_contract_creates_block_based_ticket(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        result = seed_state_exam_document(bundle)

        assert result.ok
        assert result.status == "structured"
        assert result.answer_profile_code == "state_exam_public_admin"

        ticket = bundle.facade.load_ticket_maps()[0]
        answer_text = "\n\n".join(f"{block.title}: {block.expected_content}" for block in ticket.answer_blocks)
        evaluation = bundle.facade.evaluate_answer(
            ticket.ticket_id,
            "state-exam-full",
            answer_text,
            include_followups=False,
        )

        assert ticket.answer_profile_code.value == "state_exam_public_admin"
        assert len(ticket.answer_blocks) == 6
        assert evaluation.ok
        assert len(evaluation.block_scores) == 6
        assert evaluation.review is not None
        assert bundle.facade.load_state_exam_statistics().active is True
    finally:
        bundle.close()

