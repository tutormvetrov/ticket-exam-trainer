"""Простая миграционная система для SQLite.

Принципы:
- `SCHEMA_BASELINE_VERSION` — версия, которую создаёт `initialize_schema`
  на пустой БД (идемпотентный bootstrap). Менять её нельзя: существующие
  инсталляции отметили этим числом свою схему.
- `MIGRATIONS[version]` — функции, которые поднимают схему с `version-1`
  на `version`. Первая новая миграция должна быть `SCHEMA_BASELINE_VERSION + 1`.
- Каждая миграция запускается в отдельной транзакции. При падении миграции
  состояние БД откатывается до версии, которая была перед её запуском.
- Downgrade не поддерживается: если БД новее приложения, это ошибка.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable

SCHEMA_BASELINE_VERSION = 7


class SchemaDowngradeError(RuntimeError):
    """База данных сохранена более новой версией приложения, чем запущена сейчас."""


# Регистр миграций: {версия: функция(connection)->None}
# Функция не должна сама звать commit/rollback — runner обёрнет её в транзакцию.
MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {}


# ---------------------------------------------------------------------------
# Migration v8: backfill knowledge atoms for tickets imported via the LLM
# path (tkt-ai-* prefix) that skipped rule-based atom extraction.
# Atoms are derived from the stored answer_blocks expected_content using
# the same heuristics as ImportService.extract_atoms / extract_keywords.
# ---------------------------------------------------------------------------

_V8_BLOCK_ORDER = ["intro", "theory", "practice", "skills", "conclusion", "extra"]

_V8_TYPE_LABELS: dict[str, str] = {
    "definition":    "Определение",
    "examples":      "Примеры",
    "features":      "Особенности",
    "stages":        "Этапы",
    "functions":     "Функции",
    "causes":        "Причины",
    "consequences":  "Последствия",
    "classification": "Классификация",
    "process_step":  "Процесс",
    "conclusion":    "Вывод",
}

_V8_TYPE_WEIGHTS: dict[str, float] = {
    "definition": 1.0, "examples": 0.7, "features": 0.9,
    "stages": 1.1, "functions": 1.0, "causes": 1.0,
    "consequences": 1.0, "classification": 0.9,
    "process_step": 1.1, "conclusion": 0.8,
}

_V8_CUES = [
    ("definition",    ("представляет собой", "это", "понимается как", "определяется как")),
    ("examples",      ("например", "к таким относятся", "в частности", "примером")),
    ("features",      ("признаки", "характеризуется", "особенности", "свойства")),
    ("stages",        ("этапы", "стадии")),
    ("functions",     ("функции",)),
    ("causes",        ("причины", "обусловлено")),
    ("consequences",  ("последствия", "приводит к")),
    ("classification", ("классификация", "виды", "делится на")),
    ("process_step",  ("порядок", "последовательность", "цикл", "включает")),
    ("conclusion",    ("таким образом", "следовательно", "итак", "вывод")),
]


def _v8_split(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
    expanded: list[str] = []
    for para in paragraphs:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
        if len(sentences) >= 2 and len(para) > 120:
            expanded.extend(sentences)
        else:
            expanded.append(para)
    return expanded


def _v8_detect_type(text: str, index: int) -> tuple[str, float]:
    lowered = text.lower()
    for atom_type, patterns in _V8_CUES:
        if any(p in lowered for p in patterns):
            return atom_type, 0.88
    return ("definition" if index == 1 else "features"), (0.62 if index == 1 else 0.52)


def _v8_keywords(text: str, limit: int = 6) -> list[str]:
    words = re.findall(r"[а-яёА-ЯЁa-zA-Z]{4,}", text)
    seen: set[str] = set()
    unique: list[str] = []
    for w in words:
        if w.lower() not in seen:
            seen.add(w.lower())
            unique.append(w)
    return unique[:limit]


def _v8_atom_id(ticket_id: str, index: int, text: str) -> str:
    raw = f"{ticket_id}-atom-{index}-{text[:40]}"
    return "atom-" + hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _migrate_v8_backfill_atoms(connection: sqlite3.Connection) -> None:
    no_atom_tickets = connection.execute(
        """
        SELECT t.ticket_id
        FROM tickets t
        LEFT JOIN atoms a ON a.ticket_id = t.ticket_id
        GROUP BY t.ticket_id
        HAVING COUNT(a.atom_id) = 0
        """
    ).fetchall()

    for (ticket_id,) in no_atom_tickets:
        blocks = connection.execute(
            """
            SELECT block_code, expected_content
            FROM ticket_answer_blocks
            WHERE ticket_id = ? AND is_missing = 0 AND expected_content != ''
            """,
            (ticket_id,),
        ).fetchall()

        ordered = sorted(
            blocks,
            key=lambda b: _V8_BLOCK_ORDER.index(b[0]) if b[0] in _V8_BLOCK_ORDER else 99,
        )
        source_text = "\n\n".join(b[1] for b in ordered if (b[1] or "").strip())
        if not source_text.strip():
            continue

        fragments = _v8_split(source_text)
        if not fragments:
            continue

        previous_id: str | None = None
        for idx, fragment in enumerate(fragments, start=1):
            atom_type, confidence = _v8_detect_type(fragment, idx)
            aid = _v8_atom_id(ticket_id, idx, fragment)
            connection.execute(
                """
                INSERT OR IGNORE INTO atoms
                    (atom_id, ticket_id, atom_type, label, text,
                     keywords_json, weight, dependencies_json,
                     parent_atom_id, confidence, source_excerpt, order_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    aid, ticket_id, atom_type,
                    _V8_TYPE_LABELS.get(atom_type, f"Атом {idx}"),
                    fragment,
                    json.dumps(_v8_keywords(fragment), ensure_ascii=False),
                    _V8_TYPE_WEIGHTS.get(atom_type, 0.8),
                    json.dumps([previous_id] if previous_id else [], ensure_ascii=False),
                    None,
                    confidence,
                    fragment[:220],
                    idx,
                ),
            )
            previous_id = aid


MIGRATIONS[8] = _migrate_v8_backfill_atoms


def latest_schema_version() -> int:
    return max(SCHEMA_BASELINE_VERSION, max(MIGRATIONS.keys(), default=0))


def current_schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return 0


def _set_schema_version(connection: sqlite3.Connection, version: int) -> None:
    connection.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(version),),
    )


def run_pending_migrations(connection: sqlite3.Connection) -> list[int]:
    """Прогнать все зарегистрированные миграции выше текущей версии.

    Возвращает список применённых версий (пустой, если всё актуально).
    """
    target = latest_schema_version()
    current = current_schema_version(connection)
    if current > target:
        raise SchemaDowngradeError(
            f"База данных использует schema_version={current}, "
            f"но приложение знает только до версии {target}. "
            "Возможно, файл создан более новой версией приложения. "
            "Не запускайте эту версию на нём."
        )
    applied: list[int] = []
    for version in sorted(MIGRATIONS):
        if version <= current:
            continue
        if version > target:
            # Не должно происходить, но на всякий случай.
            break
        migration = MIGRATIONS[version]
        # Каждая миграция — отдельная транзакция.
        connection.execute("BEGIN")
        try:
            migration(connection)
            _set_schema_version(connection, version)
        except Exception:
            connection.rollback()
            raise
        connection.commit()
        applied.append(version)
    return applied
