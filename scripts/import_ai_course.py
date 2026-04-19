"""Импорт PDF потока ИИ как второго курса в общую БД.

Использование:
    python scripts/import_ai_course.py

PDF ожидается в корне репозитория:
    3_1_MDE_IIiTsKvGA_2024_Kol_Konspekt_GMU_ot_03_05_2024.pdf

Курс пишется с exam_id="exam-state-mde-ai-2024" — соответствует записи
в COURSE_CATALOG (application/user_profile.py).

Перед запуском делается backup БД в *.pre-ai-import-<ts>.

Прогресс выводится в stdout. По завершении — счёт билетов по курсу.
"""

from __future__ import annotations

import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.paths import get_workspace_root
from application.facade import AppFacade
from application.settings_store import SettingsStore
from domain.answer_profile import AnswerProfileCode
from infrastructure.db import connect_initialized, get_database_path

PDF_PATH = REPO_ROOT / "3_1_MDE_IIiTsKvGA_2024_Kol_Konspekt_GMU_ot_03_05_2024.pdf"
EXAM_ID = "exam-state-mde-ai-2024"
EXAM_TITLE = "МДЭ ИИ и Цифровизация в ГА (2024)"
EXAM_DESC = "Магистратура «ИИ и Цифровизация в государственном администрировании»"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOG = logging.getLogger(__name__)


def main() -> int:
    if not PDF_PATH.exists():
        _LOG.error("PDF not found: %s", PDF_PATH)
        return 2

    workspace = get_workspace_root()
    db_path = get_database_path(workspace)
    if not db_path.exists():
        _LOG.error("DB not found: %s", db_path)
        return 3

    backup = db_path.with_suffix(
        db_path.suffix + f".pre-ai-import-{datetime.now():%Y%m%d-%H%M%S}"
    )
    shutil.copy2(db_path, backup)
    _LOG.info("Backup: %s", backup)

    connection = connect_initialized(db_path)
    settings_store = SettingsStore(workspace / "app_data" / "settings.json")
    facade = AppFacade(workspace, connection, settings_store)

    # Проверка — нет ли уже такого exam_id в БД (избежать дубликата).
    cur = connection.execute("SELECT title FROM exams WHERE exam_id = ?", (EXAM_ID,))
    if cur.fetchone() is not None:
        _LOG.error(
            "Exam '%s' already exists. Удали запись или используй другой exam_id.",
            EXAM_ID,
        )
        return 4

    def _progress(percent: int, stage: str, detail: str) -> None:
        _LOG.info("[%3d%%] %s — %s", percent, stage, detail)

    result = facade.import_document_with_progress(
        path=PDF_PATH,
        answer_profile_code=AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN,
        progress_callback=_progress,
        exam_id=EXAM_ID,
        exam_title=EXAM_TITLE,
        exam_description=EXAM_DESC,
        generation_timeout_seconds=None,
    )

    if not result.ok:
        _LOG.error("Import failed: %s", result.error)
        return 5
    _LOG.info(
        "Import OK: tickets_created=%d sections_created=%d warnings=%d",
        result.tickets_created, result.sections_created, len(result.warnings),
    )

    cur = connection.execute(
        "SELECT COUNT(*) AS n FROM tickets WHERE exam_id = ?", (EXAM_ID,)
    )
    n = cur.fetchone()["n"]
    _LOG.info("DONE — %d билетов записано в exam_id=%s", n, EXAM_ID)
    return 0


if __name__ == "__main__":
    sys.exit(main())
