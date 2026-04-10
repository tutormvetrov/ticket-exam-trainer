from __future__ import annotations

import argparse
from pathlib import Path

from docx import Document

from application.facade import AppFacade
from application.settings_store import SettingsStore
from infrastructure.db import connect_initialized, get_database_path


DEMO_DOCS: dict[str, list[str]] = {
    "Теория вероятностей.docx": [
        "Раздел 1. Основы теории вероятностей",
        "Билет 1. Что такое вероятность события?",
        (
            "Вероятность события показывает меру возможности наступления результата. "
            "Она принимает значения от нуля до единицы. Нулевая вероятность означает невозможность, "
            "а единица означает достоверность. Для устного ответа важно дать определение, назвать "
            "границы значений и пояснить смысл вероятностной меры."
        ),
        "Билет 2. Что понимается под независимыми испытаниями?",
        (
            "Независимые испытания это такие повторяющиеся эксперименты, в которых исход одного испытания "
            "не влияет на вероятность исходов другого. В ответе нужно раскрыть определение, привести "
            "пример и показать, почему условие независимости важно для расчётов."
        ),
    ],
    "Гражданское право.docx": [
        "Раздел 1. Общие положения",
        "Билет 1. Что включает правоспособность гражданина?",
        (
            "Правоспособность гражданина означает признанную законом способность иметь гражданские права "
            "и нести обязанности. Она возникает с момента рождения и прекращается со смертью. "
            "Для полного ответа нужно назвать содержание правоспособности, признаки и правовое значение."
        ),
        "Билет 2. Чем отличается дееспособность от правоспособности?",
        (
            "Дееспособность выражает способность гражданина своими действиями приобретать и осуществлять права, "
            "создавать обязанности и исполнять их. В отличие от правоспособности она зависит от возраста и состояния лица. "
            "В ответе важно сравнить обе категории и показать практическое различие."
        ),
    ],
    "Микроэкономика.docx": [
        "Раздел 1. Поведение фирмы",
        "Билет 1. Что такое издержки производства?",
        (
            "Издержки производства это совокупность затрат фирмы на выпуск продукции и организацию процесса. "
            "Они включают постоянные и переменные элементы, используются для оценки эффективности и выбора объёма выпуска. "
            "В устном ответе нужно дать определение, привести классификацию и объяснить управленческое значение."
        ),
        "Билет 2. Как определяется предельный продукт ресурса?",
        (
            "Предельный продукт ресурса показывает, насколько увеличивается выпуск при использовании дополнительной единицы ресурса "
            "при прочих равных условиях. Он нужен для анализа производительности, выбора факторов производства и оценки эффективности. "
            "Важно раскрыть логику показателя и его связь с управленческими решениями фирмы."
        ),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-db", action="store_true")
    return parser.parse_args()


def build_docs(target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename, paragraphs in DEMO_DOCS.items():
        path = target_dir / filename
        document = Document()
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)
        document.save(path)
        paths.append(path)
    return paths


def reset_database(root: Path) -> None:
    database_path = get_database_path(root)
    if database_path.exists():
        database_path.unlink()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    demo_dir = root / "sample_data" / "generated_ui_demo"
    paths = build_docs(demo_dir)

    if args.reset_db:
        reset_database(root)

    connection = connect_initialized(get_database_path(root))
    facade = AppFacade(root, connection, SettingsStore(root / "app_data" / "settings.json"))

    for path in paths:
        result = facade.import_document(path)
        print(f"import {path.name}: ok={result.ok} tickets={result.tickets_created} warnings={len(result.warnings)}")

    for ticket in facade.load_ticket_maps()[:6]:
        short_answer = " ".join(atom.text for atom in ticket.atoms[:2])
        for mode in ("active-recall", "plan"):
            result = facade.evaluate_answer(ticket.ticket_id, mode, short_answer)
            print(f"train {ticket.ticket_id} {mode}: ok={result.ok} score={result.score_percent}")

    stats = facade.load_statistics_snapshot()
    print(
        f"stats avg={stats.average_score} processed={stats.processed_tickets} "
        f"weak={stats.weak_areas} sessions={stats.sessions_week}"
    )
    connection.close()


if __name__ == "__main__":
    main()
