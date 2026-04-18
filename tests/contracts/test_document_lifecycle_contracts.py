from __future__ import annotations

from tests.support.workspace_builder import create_workspace_bundle, seed_reading_attempt, seed_standard_document


def test_document_delete_contract_cleans_student_artifacts(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        result = seed_standard_document(bundle)
        seed_reading_attempt(bundle)

        before = {
            "documents": bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM source_documents").fetchone()["total"],
            "tickets": bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM tickets").fetchone()["total"],
            "attempts": bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM attempts").fetchone()["total"],
            "weak_areas": bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM weak_areas").fetchone()["total"],
            "review_queue": bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM spaced_review_queue").fetchone()["total"],
        }

        deleted = bundle.facade.delete_document(result.document_id)

        after = {
            "documents": bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM source_documents").fetchone()["total"],
            "tickets": bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM tickets").fetchone()["total"],
            "attempts": bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM attempts").fetchone()["total"],
            "weak_areas": bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM weak_areas").fetchone()["total"],
            "review_queue": bundle.facade.connection.execute("SELECT COUNT(*) AS total FROM spaced_review_queue").fetchone()["total"],
        }

        assert deleted is True
        assert before["documents"] == 1
        assert before["tickets"] == 3
        assert before["attempts"] >= 1
        assert after == {
            "documents": 0,
            "tickets": 0,
            "attempts": 0,
            "weak_areas": 0,
            "review_queue": 0,
        }
    finally:
        bundle.close()

