from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from docx import Document

from application.facade import AppFacade
from application.settings import DEFAULT_OLLAMA_SETTINGS, OllamaSettings
from application.settings_store import SettingsStore
from domain.answer_profile import AnswerProfileCode
from infrastructure.db import connect_initialized, get_database_path


STANDARD_SOURCE_TEXT = """Section 1. Public assets

Ticket 1. What is public property as an object of management? Public property is a public resource assigned to public bodies. It includes land, buildings, transport and digital infrastructure. The management cycle includes accounting, valuation, use and regular review.

Ticket 2. How is efficiency of public property evaluated? Efficiency is evaluated through public goals, utilization, service quality and cost control. Analysts compare social effect, budget discipline and usage results before choosing the next management action.

Ticket 3. How does a public manager work with risks? A public manager identifies legal, financial and operational risks, defines indicators, allocates responsibility and prepares a corrective action plan with measurable checkpoints.
"""


STATE_EXAM_SOURCE_TEXT = """Билет 1. Что представляет собой государственное имущество как объект управления?

Актуальность темы связана с эффективным использованием публичных ресурсов и качеством решений органов власти.

Теоретическая часть включает понятие имущества, правовой режим, субъектов управления и управленческий цикл.

Практическая часть раскрывается через учет, оценку, контроль, выбор управленческих решений и критерии эффективности.

Навыковый блок связан с анализом, аргументацией, сравнением вариантов и защитой вывода на комиссии.

В заключении государственное имущество рассматривается как управленческий ресурс, который требует законности, прозрачности и измеримого результата.
"""


@dataclass(slots=True)
class WorkspaceBundle:
    workspace_root: Path
    facade: AppFacade

    @property
    def database_path(self) -> Path:
        return get_database_path(self.workspace_root)

    def close(self) -> None:
        self.facade.connection.close()


def create_workspace_bundle(
    workspace_root: Path,
    *,
    settings: OllamaSettings | None = None,
) -> WorkspaceBundle:
    workspace_root.mkdir(parents=True, exist_ok=True)
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    effective_settings = settings or _default_settings()
    settings_store.save(effective_settings)
    facade = AppFacade(workspace_root, connection, settings_store)
    return WorkspaceBundle(workspace_root=workspace_root, facade=facade)


def seed_standard_document(bundle: WorkspaceBundle, *, file_name: str = "standard-demo.docx"):
    document_path = bundle.workspace_root / "imports" / file_name
    _write_docx(document_path, STANDARD_SOURCE_TEXT.split("\n\n"))
    return bundle.facade.import_document_with_progress(
        document_path,
        answer_profile_code=AnswerProfileCode.STANDARD_TICKET,
    )


def seed_state_exam_document(bundle: WorkspaceBundle, *, file_name: str = "state-exam-demo.docx"):
    document_path = bundle.workspace_root / "imports" / file_name
    _write_docx(document_path, STATE_EXAM_SOURCE_TEXT.split("\n\n"))
    return bundle.facade.import_document_with_progress(
        document_path,
        answer_profile_code=AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN,
    )


def seed_reading_attempt(bundle: WorkspaceBundle) -> str:
    tickets = bundle.facade.load_ticket_maps()
    if not tickets:
        raise RuntimeError("Cannot seed attempt without imported tickets.")
    ticket = tickets[0]
    answer_text = ticket.canonical_answer_summary or "\n\n".join(atom.text for atom in ticket.atoms[:3])
    result = bundle.facade.evaluate_answer(
        ticket.ticket_id,
        "reading",
        answer_text,
        include_followups=False,
    )
    if not result.ok:
        raise RuntimeError(result.error or "Reading attempt failed.")
    return ticket.ticket_id


def create_acceptance_workspace(workspace_root: Path) -> Path:
    bundle = create_workspace_bundle(workspace_root)
    try:
        seed_standard_document(bundle)
        seed_state_exam_document(bundle)
        seed_reading_attempt(bundle)
    finally:
        bundle.close()
    return workspace_root


def _default_settings() -> OllamaSettings:
    return DEFAULT_OLLAMA_SETTINGS.__class__(
        base_url=DEFAULT_OLLAMA_SETTINGS.base_url,
        model=DEFAULT_OLLAMA_SETTINGS.model,
        models_path=DEFAULT_OLLAMA_SETTINGS.models_path,
        timeout_seconds=DEFAULT_OLLAMA_SETTINGS.timeout_seconds,
        rewrite_questions=False,
        examiner_followups=False,
        rule_based_fallback=DEFAULT_OLLAMA_SETTINGS.rule_based_fallback,
        auto_check_ollama_on_start=False,
        auto_check_updates_on_start=False,
        import_llm_assist=False,
        default_import_dir=DEFAULT_OLLAMA_SETTINGS.default_import_dir,
        preferred_import_format=DEFAULT_OLLAMA_SETTINGS.preferred_import_format,
        default_training_mode=DEFAULT_OLLAMA_SETTINGS.default_training_mode,
        review_mode=DEFAULT_OLLAMA_SETTINGS.review_mode,
        training_queue_size=DEFAULT_OLLAMA_SETTINGS.training_queue_size,
        show_dlc_teaser=DEFAULT_OLLAMA_SETTINGS.show_dlc_teaser,
        theme_name=DEFAULT_OLLAMA_SETTINGS.theme_name,
        startup_view=DEFAULT_OLLAMA_SETTINGS.startup_view,
        font_preset=DEFAULT_OLLAMA_SETTINGS.font_preset,
        font_size=DEFAULT_OLLAMA_SETTINGS.font_size,
    )


def _write_docx(path: Path, paragraphs: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    for paragraph in paragraphs:
        text = paragraph.strip()
        if text:
            document.add_paragraph(text)
    document.save(path)
