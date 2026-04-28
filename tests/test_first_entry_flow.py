from __future__ import annotations

from types import SimpleNamespace

import flet as ft

from application.ui_query_service import UiQueryService
from application.user_profile import ProfileStore, UserProfile
from infrastructure.db import connect_initialized
from ui_flet.first_step import resolve_first_training_step
from ui_flet.state import AppState
from ui_flet.views.journal_view import build_journal_view
from ui_flet.views.onboarding_view import build_onboarding_view


class _MockPage:
    def __init__(self) -> None:
        self.route = "/onboarding"
        self.views: list = []
        self.on_route_change = None

    def go(self, route: str) -> None:
        self.route = route

    def update(self) -> None:
        pass


def _collect_controls(control: ft.Control | None) -> list[ft.Control]:
    if control is None:
        return []
    found = [control]
    content = getattr(control, "content", None)
    if content is not None:
        found.extend(_collect_controls(content))
    controls = getattr(control, "controls", None)
    if isinstance(controls, list):
        for child in controls:
            found.extend(_collect_controls(child))
    return found


def _collect_texts(control: ft.Control | None) -> list[str]:
    values: list[str] = []
    for child in _collect_controls(control):
        for attr in ("text", "value", "label", "hint_text", "tooltip"):
            raw = getattr(child, attr, None)
            if isinstance(raw, str) and raw:
                values.append(raw)
    return values


def _find_text_field(root: ft.Control, label: str) -> ft.TextField:
    for control in _collect_controls(root):
        if isinstance(control, ft.TextField) and control.label == label:
            return control
    raise AssertionError(f"TextField not found: {label}")


def _find_switch(root: ft.Control, label: str) -> ft.Switch:
    for control in _collect_controls(root):
        if isinstance(control, ft.Switch) and control.label == label:
            return control
    raise AssertionError(f"Switch not found: {label}")


def _find_button(root: ft.Control, text: str):
    for control in _collect_controls(root):
        if getattr(control, "text", None) == text and callable(getattr(control, "on_click", None)):
            return control
    raise AssertionError(f"Button not found: {text}")


def _facade(tmp_path, *, queue_items=None, tickets=None):
    queue_items = list(queue_items or [])
    tickets = list(tickets or [])
    connection = connect_initialized(tmp_path / "trainer.db")
    return SimpleNamespace(
        workspace_root=tmp_path,
        connection=connection,
        load_training_snapshot=lambda tickets=None, exam_id=None: SimpleNamespace(
            queue_items=queue_items,
            tickets=[] if tickets is None else tickets,
        ),
        load_ticket_maps=lambda exam_id=None: tickets,
    )


def _insert_ticket(conn, ticket_id: str, title: str, exam_id: str) -> None:
    section_id = f"section-{exam_id}"
    document_id = f"doc-{exam_id}"
    conn.execute("INSERT INTO exams (exam_id, title) VALUES (?, ?) ON CONFLICT DO NOTHING", (exam_id, exam_id))
    conn.execute(
        "INSERT INTO sections (section_id, exam_id, title) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
        (section_id, exam_id, "Раздел"),
    )
    conn.execute(
        """
        INSERT INTO source_documents (
            document_id, exam_id, title, file_path, file_type, imported_at
        ) VALUES (?, ?, ?, 'test', 'txt', '2026-04-28T10:00:00')
        ON CONFLICT DO NOTHING
        """,
        (document_id, exam_id, "Документ"),
    )
    conn.execute(
        """
        INSERT INTO tickets (
            ticket_id, exam_id, section_id, source_document_id, title,
            canonical_answer_summary, created_at
        ) VALUES (?, ?, ?, ?, ?, 'эталон', '2026-04-28T10:00:00')
        """,
        (ticket_id, exam_id, section_id, document_id, title),
    )


def _insert_queue_item(conn, item_id: str, ticket_id: str, priority: float) -> None:
    conn.execute(
        """
        INSERT INTO spaced_review_queue (
            review_item_id, user_id, ticket_id, reference_type, reference_id,
            mode, priority, due_at, scheduled_at
        ) VALUES (?, 'local-user', ?, 'ticket', ?, 'reading', ?, '2026-04-28T10:00:00', '2026-04-28T10:00:00')
        """,
        (item_id, ticket_id, ticket_id, priority),
    )


def test_training_snapshot_filters_queue_by_exam_id(tmp_path) -> None:
    conn = connect_initialized(tmp_path / "trainer.db")
    _insert_ticket(conn, "gmu-1", "ГМУ билет", "gmu")
    _insert_ticket(conn, "ai-1", "ИИ билет", "ai")
    _insert_queue_item(conn, "q-gmu", "gmu-1", 0.5)
    _insert_queue_item(conn, "q-ai", "ai-1", 1.0)
    conn.commit()

    snapshot = UiQueryService(conn).load_training_snapshot(tickets=[], exam_id="gmu")

    assert [item.ticket_id for item in snapshot.queue_items] == ["gmu-1"]


def test_first_step_prefers_queue_item(tmp_path) -> None:
    item = SimpleNamespace(ticket_id="tkt-1", ticket_title="Первый билет")
    state = AppState(page=_MockPage(), facade=_facade(tmp_path, queue_items=[item]))

    step = resolve_first_training_step(state, exam_id="exam-state-mde-gmu-2024")

    assert step.route == "/training/tkt-1/reading"
    assert step.ticket_title == "Первый билет"


def test_first_step_falls_back_to_catalog_when_no_ticket(tmp_path) -> None:
    state = AppState(page=_MockPage(), facade=_facade(tmp_path))

    step = resolve_first_training_step(state, exam_id="exam-state-mde-gmu-2024")

    assert step.route == "/tickets"
    assert not step.has_ticket


def test_onboarding_saves_profile_and_opens_first_ticket(tmp_path) -> None:
    item = SimpleNamespace(ticket_id="tkt-1", ticket_title="Первый билет")
    state = AppState(page=_MockPage(), facade=_facade(tmp_path, queue_items=[item]))

    view = build_onboarding_view(state)
    _find_text_field(view, "Как к тебе обращаться?").value = "Камила"
    _find_text_field(view, "Дата экзамена").value = "2026-06-15"
    _find_switch(view, "Мягкое напоминание").value = True
    _find_text_field(view, "Время").value = "09:30"

    start = _find_button(view, "Открыть первый билет")
    start.on_click(SimpleNamespace())

    profile = ProfileStore(tmp_path / "app_data" / "profile.json").load()
    assert profile is not None
    assert profile.name == "Камила"
    assert profile.exam_date == "2026-06-15"
    assert profile.reminder_enabled is True
    assert profile.reminder_time == "09:30"
    assert state.page.route == "/training/tkt-1/reading"


def test_onboarding_without_tickets_opens_catalog(tmp_path) -> None:
    state = AppState(page=_MockPage(), facade=_facade(tmp_path))

    view = build_onboarding_view(state)
    _find_text_field(view, "Как к тебе обращаться?").value = "Камила"

    start = _find_button(view, "Открыть первый билет")
    start.on_click(SimpleNamespace())

    assert state.page.route == "/tickets"


def test_journal_morning_shows_first_ticket_without_cold_queue_minutes(tmp_path) -> None:
    item = SimpleNamespace(ticket_id="tkt-1", ticket_title="Муниципальная служба")
    facade = _facade(tmp_path, queue_items=[item])
    state = AppState(page=_MockPage(), facade=facade)
    state.page.route = "/journal"
    state.user_profile = UserProfile(
        name="Камила",
        avatar_emoji="🦉",
        created_at="2026-04-28T10:00:00",
        exam_date="2026-06-15",
        reminder_enabled=True,
        reminder_time="09:30",
    )

    view = build_journal_view(state)
    text_blob = " ".join(_collect_texts(view))

    assert "Муниципальная служба" in text_blob
    assert "1040" not in text_blob
    assert "примерно" not in text_blob
