from __future__ import annotations

import importlib
from dataclasses import replace
from pathlib import Path

from reportlab.pdfgen import canvas

import application.import_service as import_service_module
import infrastructure.importers.ocr_support as ocr_support_module
import infrastructure.importers.pdf_importer as pdf_importer_module
from application.facade import AppFacade
from application.import_service import DocumentImportService
from application.settings import DEFAULT_OLLAMA_SETTINGS
from application.settings_store import SettingsStore
from application.user_profile import ProfileStore, build_profile
from infrastructure.db import connect_initialized, get_database_path
from infrastructure.importers.common import ImportedDocumentText
from infrastructure.importers.pdf_importer import import_pdf

SOURCE_TEXT = "Ticket 1. Demo topic. Demo body for OCR augmentation test."


def _build_facade(tmp_path: Path) -> tuple[AppFacade, Path]:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    database_path = get_database_path(workspace_root)
    connection = connect_initialized(database_path)
    settings_store = SettingsStore(workspace_root / "app_data" / "settings.json")
    settings_store.save(replace(DEFAULT_OLLAMA_SETTINGS, auto_check_ollama_on_start=False))
    return AppFacade(workspace_root, connection, settings_store), workspace_root


def test_prepare_import_preserves_importer_warnings_and_workspace_root(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "demo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    captured: dict[str, Path | None] = {}

    def _fake_import_pdf(path: str, *, workspace_root: Path | None = None) -> ImportedDocumentText:
        captured["workspace_root"] = workspace_root
        return ImportedDocumentText(
            path=Path(path),
            title="Demo",
            file_type="PDF",
            raw_text=SOURCE_TEXT,
            unit_count=1,
            warnings=("OCR warning",),
        )

    monkeypatch.setattr(import_service_module, "import_pdf", _fake_import_pdf)
    service = DocumentImportService(workspace_root=tmp_path)

    prepared = service.prepare_import(pdf_path, "exam-demo", "subject-demo", "section-demo")

    assert "OCR warning" in prepared.warnings
    assert captured["workspace_root"] == tmp_path


def test_pdf_import_appends_ocr_text(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "demo.pdf"
    pdf = canvas.Canvas(str(pdf_path))
    text = pdf.beginText(40, 800)
    text.textLine(SOURCE_TEXT)
    pdf.drawText(text)
    pdf.save()

    monkeypatch.setattr(
        pdf_importer_module,
        "_augment_pages_with_ocr",
        lambda pdf_path, page_texts, workspace_root=None: [page_texts[0] + "\n\nOCR supplement"],
    )

    imported = import_pdf(str(pdf_path), workspace_root=tmp_path)

    assert "OCR supplement" in imported.raw_text


def test_pdf_import_keeps_base_text_when_pymupdf_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "demo.pdf"
    pdf = canvas.Canvas(str(pdf_path))
    text = pdf.beginText(40, 800)
    text.textLine(SOURCE_TEXT)
    pdf.drawText(text)
    pdf.save()

    monkeypatch.setattr(
        pdf_importer_module,
        "_load_fitz",
        lambda: (_ for _ in ()).throw(RuntimeError("fitz unavailable on this platform")),
    )

    imported = import_pdf(str(pdf_path), workspace_root=tmp_path)

    assert "Demo topic" in imported.raw_text
    assert imported.warnings
    assert "fitz unavailable" in imported.warnings[0]


def test_pdf_import_keeps_base_text_when_rapidocr_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "demo.pdf"
    pdf = canvas.Canvas(str(pdf_path))
    text = pdf.beginText(40, 800)
    text.textLine(SOURCE_TEXT)
    pdf.drawText(text)
    pdf.save()

    original_import_module = importlib.import_module

    def _fake_import_module(name: str):
        if name == "rapidocr_onnxruntime":
            raise ImportError(f"missing optional dependency: {name}")
        return original_import_module(name)

    monkeypatch.setattr(ocr_support_module, "_ENGINE_CACHE", {})
    monkeypatch.setattr(ocr_support_module, "_RAPID_OCR_CLASS", None)
    monkeypatch.setattr(ocr_support_module, "_RAPID_OCR_IMPORT_ERROR", None)
    monkeypatch.setattr(ocr_support_module, "_RAPID_OCR_IMPORT_ATTEMPTED", False)
    monkeypatch.setattr(
        ocr_support_module,
        "_ensure_ocr_assets",
        lambda cache_dir: (_ for _ in ()).throw(AssertionError("OCR assets should not be downloaded")),
    )
    monkeypatch.setattr(
        ocr_support_module.importlib,
        "import_module",
        _fake_import_module,
    )

    imported = import_pdf(str(pdf_path), workspace_root=tmp_path)

    assert "Demo topic" in imported.raw_text
    assert imported.warnings
    assert "rapidocr_onnxruntime backend is unavailable" in imported.warnings[0]


def test_facade_reset_application_data_returns_workspace_to_cold_start(tmp_path: Path) -> None:
    facade, workspace_root = _build_facade(tmp_path)
    profile_path = workspace_root / "app_data" / "profile.json"
    ocr_cache = workspace_root / "app_data" / "ocr_models"
    backup_file = workspace_root / "backups" / "snapshot.txt"

    ProfileStore(profile_path).save(build_profile("Alice", "🐢"))
    ocr_cache.mkdir(parents=True, exist_ok=True)
    (ocr_cache / "dummy.bin").write_text("x", encoding="utf-8")
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    backup_file.write_text("backup", encoding="utf-8")
    facade.connection.execute("CREATE TABLE IF NOT EXISTS reset_probe(id INTEGER)")
    facade.connection.commit()

    database_path = get_database_path(workspace_root)
    assert database_path.exists()
    assert profile_path.exists()

    facade.reset_application_data()

    assert not database_path.exists()
    assert not profile_path.exists()
    assert not (workspace_root / "app_data" / "settings.json").exists()
    assert not ocr_cache.exists()
    assert list((workspace_root / "backups").iterdir()) == []

    rebuilt = AppFacade(
        workspace_root,
        connect_initialized(database_path),
        SettingsStore(workspace_root / "app_data" / "settings.json"),
    )
    assert ProfileStore(profile_path).load() is None
    assert rebuilt.settings.gemini_api_key == ""
    rebuilt.connection.close()
