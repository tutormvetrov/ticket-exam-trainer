"""Find exact and near-duplicate tickets between the AI-course (parsed
from PDF into tickets.json) and the GMU-course already in the seed DB.

The two magistratura programs (ГМУ vs ИИ-коммуникации) share ~40% of
the curriculum — same disciplines in the base block (1.1–1.8) and some
elective overlaps. Where discipline code + ticket title match, there's
zero reason to regenerate — we just copy the 6 answer blocks from the
GMU ticket into the AI ticket.

Output: build/ai-extract/gmu_overlap.json with, for every AI ticket:

    {
      "ai_discipline_code": "1.1",
      "ai_ticket_num": 1,
      "ai_title": "…",
      "match_strategy": "exact_title" | "fuzzy" | "none",
      "gmu_ticket_id": "tkt-001-…"    # or null
      "gmu_title": "…"                 # or null
      "similarity": 1.0                # [0, 1]
    }

Also prints a human-readable breakdown by discipline.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_DB = REPO_ROOT / "data" / "state_exam_public_admin_demo.db"
TICKETS_JSON = REPO_ROOT / "build" / "ai-extract" / "tickets.json"
OUT_JSON = REPO_ROOT / "build" / "ai-extract" / "gmu_overlap.json"

GMU_EXAM_ID = "exam-state-mde-gmu-2024"


def _normalize(text: str) -> str:
    """Lowercase + drop punctuation + collapse whitespace. Removes typical
    differences like trailing period, quote styles, figure numbers."""
    t = (text or "").lower()
    t = t.replace("ё", "е")
    t = re.sub(r"[«»\"()\[\].,;:!?\-–—/\\]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _token_set(text: str) -> set[str]:
    return {w for w in _normalize(text).split() if len(w) >= 3}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def load_gmu_tickets(con: sqlite3.Connection) -> list[dict]:
    con.row_factory = sqlite3.Row
    rows = list(
        con.execute(
            """
            SELECT t.ticket_id, t.title, s.title AS section_title, s.order_index AS section_order
              FROM tickets t
              JOIN sections s ON s.section_id = t.section_id
             WHERE t.exam_id = ?
             ORDER BY s.order_index, t.title
            """,
            (GMU_EXAM_ID,),
        )
    )
    return [dict(r) for r in rows]


def find_matches(ai_tickets: list[dict], gmu_tickets: list[dict]) -> list[dict]:
    # Index GMU by normalized title and by section title.
    gmu_by_title: dict[str, list[dict]] = {}
    for g in gmu_tickets:
        gmu_by_title.setdefault(_normalize(g["title"]), []).append(g)
    # For fuzzy matching — prefer GMU tickets in a section whose title
    # matches the AI discipline title. Groups GMU by section title.
    gmu_by_section: dict[str, list[dict]] = {}
    for g in gmu_tickets:
        gmu_by_section.setdefault(_normalize(g["section_title"]), []).append(g)

    results: list[dict] = []
    for a in ai_tickets:
        a_title_norm = _normalize(a["title"])
        a_disc_norm = _normalize(a["discipline_title"])

        match = {
            "ai_discipline_code": a["discipline_code"],
            "ai_discipline_title": a["discipline_title"],
            "ai_ticket_num": a["ticket_num"],
            "ai_title": a["title"],
            "match_strategy": "none",
            "gmu_ticket_id": None,
            "gmu_title": None,
            "gmu_section_title": None,
            "similarity": 0.0,
        }

        # 1. Exact normalized-title match within matching discipline section.
        candidates = gmu_by_title.get(a_title_norm, [])
        if candidates:
            # Prefer the one whose section title matches our discipline.
            best = None
            for c in candidates:
                if _normalize(c["section_title"]) == a_disc_norm:
                    best = c
                    break
            if best is None:
                best = candidates[0]
            match.update(
                {
                    "match_strategy": "exact_title",
                    "gmu_ticket_id": best["ticket_id"],
                    "gmu_title": best["title"],
                    "gmu_section_title": best["section_title"],
                    "similarity": 1.0,
                }
            )
            results.append(match)
            continue

        # 2. Fuzzy within the matching discipline — Jaccard on token sets.
        pool = gmu_by_section.get(a_disc_norm, [])
        if pool:
            a_tokens = _token_set(a["title"])
            best = None
            best_sim = 0.0
            for c in pool:
                sim = _jaccard(a_tokens, _token_set(c["title"]))
                if sim > best_sim:
                    best = c
                    best_sim = sim
            if best and best_sim >= 0.5:
                match.update(
                    {
                        "match_strategy": "fuzzy",
                        "gmu_ticket_id": best["ticket_id"],
                        "gmu_title": best["title"],
                        "gmu_section_title": best["section_title"],
                        "similarity": round(best_sim, 3),
                    }
                )
                results.append(match)
                continue

        results.append(match)
    return results


def summarise(results: list[dict]) -> None:
    total = len(results)
    by_strategy: dict[str, int] = {}
    by_disc: dict[str, dict[str, int]] = {}
    for r in results:
        by_strategy[r["match_strategy"]] = by_strategy.get(r["match_strategy"], 0) + 1
        key = f"{r['ai_discipline_code']} {r['ai_discipline_title']}"
        by_disc.setdefault(key, {"total": 0, "exact": 0, "fuzzy": 0, "none": 0})
        by_disc[key]["total"] += 1
        by_disc[key][r["match_strategy"]] = by_disc[key].get(r["match_strategy"], 0) + 1

    print(f"Total AI tickets: {total}")
    print("By strategy:")
    for k in ("exact_title", "fuzzy", "none"):
        print(f"  {k:12s} {by_strategy.get(k, 0):4d}")
    print()
    print("By discipline (exact / fuzzy / none of total):")
    for key in sorted(by_disc):
        s = by_disc[key]
        print(
            f"  {key[:70]:70s} "
            f"{s.get('exact_title',0):2d}+{s.get('fuzzy',0):2d}+{s.get('none',0):2d} = {s['total']}"
        )


def main() -> int:
    if not SEED_DB.exists():
        print(f"Seed DB missing: {SEED_DB}", file=sys.stderr)
        return 1
    if not TICKETS_JSON.exists():
        print("tickets.json missing - run parse_ai_pdf_to_tickets.py first", file=sys.stderr)
        return 1

    ai_tickets = json.loads(TICKETS_JSON.read_text(encoding="utf-8"))
    con = sqlite3.connect(str(SEED_DB))
    try:
        gmu_tickets = load_gmu_tickets(con)
    finally:
        con.close()

    print(f"GMU tickets loaded: {len(gmu_tickets)}")
    print(f"AI tickets loaded:  {len(ai_tickets)}")
    print()

    results = find_matches(ai_tickets, gmu_tickets)
    summarise(results)

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
