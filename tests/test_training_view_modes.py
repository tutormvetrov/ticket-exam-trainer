from __future__ import annotations

import sys

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit, QLineEdit, QComboBox

from application.ui_data import TrainingQueueItem, TrainingSnapshot
from domain.knowledge import AtomType, KnowledgeAtom, TicketKnowledgeMap
from ui.theme import set_app_theme
from ui.views.training_view import TrainingView


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        set_app_theme(app, "light")
    return app


def _build_ticket(ticket_id: str, title: str) -> TicketKnowledgeMap:
    atoms = [
        KnowledgeAtom(f"{ticket_id}-atom-1", AtomType.DEFINITION, "Определение", "Государственное имущество является базовым публичным ресурсом.", ["имущество", "ресурс"], 1.0),
        KnowledgeAtom(f"{ticket_id}-atom-2", AtomType.FEATURES, "Признаки", "Его отличают правовой режим, целевое назначение и контроль использования.", ["правовой", "контроль"], 1.0),
        KnowledgeAtom(f"{ticket_id}-atom-3", AtomType.PROCESS_STEP, "Управленческий цикл", "Сначала проводится учёт, затем оценка, после чего принимаются управленческие решения.", ["учёт", "оценка", "решения"], 1.0),
        KnowledgeAtom(f"{ticket_id}-atom-4", AtomType.CONCLUSION, "Вывод", "Имущество следует рассматривать как активный инструмент управления, а не пассивный актив.", ["инструмент", "управления"], 1.0),
    ]
    return TicketKnowledgeMap(
        ticket_id=ticket_id,
        exam_id="exam-1",
        section_id="section-1",
        source_document_id="doc-1",
        title=title,
        canonical_answer_summary="Государственное имущество это публичный ресурс с правовым режимом, управленческим циклом и контролем использования.",
        atoms=atoms,
        skills=[],
        exercise_templates=[],
        scoring_rubric=[],
        examiner_prompts=[],
        cross_links_to_other_tickets=[],
        difficulty=2,
        estimated_oral_time_sec=180,
    )


def test_training_modes_switch_to_real_workspaces() -> None:
    _qapp()
    view = TrainingView("#000000")
    ticket = _build_ticket("ticket-1", "Что представляет собой государственное имущество?")
    snapshot = TrainingSnapshot(
        queue_items=[TrainingQueueItem(ticket.ticket_id, ticket.title, "ticket", ticket.ticket_id, 0.9, "сегодня")],
        tickets=[ticket],
    )
    view.set_snapshot(snapshot)

    view.select_mode("reading")
    reading_workspace = view.workspace_stack.currentWidget()
    assert reading_workspace.findChild(QPushButton, "training-reading-understood") is not None
    assert not reading_workspace.findChildren(QTextEdit)

    view.select_mode("active-recall")
    recall_workspace = view.workspace_stack.currentWidget()
    assert recall_workspace.findChild(QTextEdit, "training-active-recall-input") is not None
    assert recall_workspace.findChild(QPushButton, "training-active-recall-submit") is not None

    view.select_mode("cloze")
    cloze_workspace = view.workspace_stack.currentWidget()
    assert cloze_workspace.findChild(QPushButton, "training-cloze-submit") is not None
    assert len(cloze_workspace.findChildren(QLineEdit)) >= 1

    view.select_mode("matching")
    matching_workspace = view.workspace_stack.currentWidget()
    assert matching_workspace.findChild(QPushButton, "training-matching-submit") is not None
    assert len(matching_workspace.findChildren(QComboBox)) >= 1

    view.select_mode("plan")
    plan_workspace = view.workspace_stack.currentWidget()
    assert plan_workspace.findChild(QPushButton, "training-plan-submit") is not None
    assert "Сбор структуры ответа" in view.workspace_title.text()

    view.select_mode("mini-exam")
    exam_workspace = view.workspace_stack.currentWidget()
    assert exam_workspace.findChild(QTextEdit, "training-mini-exam-input") is not None
    assert exam_workspace.findChild(QPushButton, "training-mini-exam-submit") is not None
    assert "Таймер:" in exam_workspace.findChild(QLabel, "training-mini-exam-timer").text()
