from __future__ import annotations

from tests.support.workspace_builder import create_workspace_bundle


class _FakeQueries:
    def __init__(self) -> None:
        self.calls: list[str | None] = []

    def load_ticket_maps(self, exam_id: str | None = None):
        self.calls.append(exam_id)
        return ["sentinel"]


def test_load_ticket_maps_forwards_exam_id(tmp_path) -> None:
    bundle = create_workspace_bundle(tmp_path / "workspace")
    try:
        fake_queries = _FakeQueries()
        bundle.facade.queries = fake_queries

        result = bundle.facade.load_ticket_maps(exam_id="exam-state-mde-ai-2024")

        assert result == ["sentinel"]
        assert fake_queries.calls == ["exam-state-mde-ai-2024"]
    finally:
        bundle.close()
