"""R0 validation: run review engine on qwen3:0.6b / 1.7b / 8b.

Output: docs/superpowers/specs/2026-04-18-model-selection-raw.json with per-model
per-ticket results (valid_json, duration_ms, raw output).

This is empirical input for choosing the default model tier in the
installer wizard. Run before dispatching W3 agent.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from infrastructure.ollama.service import OllamaService  # noqa: E402

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "review_validation"
OUT_PATH = REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-04-18-model-selection-raw.json"

MODELS = ["qwen3:0.6b", "qwen3:1.7b", "qwen3:8b"]
PER_CALL_TIMEOUT_SEC = 180  # жёсткий таймаут на один вызов


def build_reference_theses(canonical: str) -> list[dict[str, str]]:
    """Build minimal reference theses from canonical answer.

    Since R0 fixtures don't have pre-split theses (that's answer_blocks
    territory after W1), we construct a single high-level thesis from
    canonical_answer_summary for validation purposes.
    """
    # Короткая версия каноничного ответа — первые ~1500 символов
    text = canonical[:1500].strip()
    return [{"label": "Содержание ответа", "text": text}]


def run_one(svc: OllamaService, model: str, ticket: dict, answer: str) -> dict:
    theses = build_reference_theses(ticket["canonical_answer_summary"])
    start = time.time()
    try:
        result = svc.review_answer(
            ticket_title=ticket["title"],
            reference_theses=theses,
            student_answer=answer,
            model=model,
        )
        duration_ms = int((time.time() - start) * 1000)
        return {
            "ok": result.ok,
            "duration_ms": duration_ms,
            "latency_ms": result.latency_ms,
            "text": result.content or "",
            "error": result.error or "",
        }
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "ok": False,
            "duration_ms": duration_ms,
            "latency_ms": None,
            "text": "",
            "error": f"{type(e).__name__}: {e}",
        }


def main() -> int:
    svc = OllamaService(
        base_url="http://localhost:11434",
        generation_timeout_seconds=PER_CALL_TIMEOUT_SEC,
    )

    # Load fixtures
    tickets = []
    answers = []
    for i in range(1, 6):
        ticket_path = FIXTURES_DIR / f"ticket_{i}.json"
        answer_path = FIXTURES_DIR / f"answer_{i}.txt"
        if not ticket_path.exists() or not answer_path.exists():
            print(f"ERROR: missing {ticket_path} or {answer_path}", file=sys.stderr)
            return 1
        tickets.append(json.loads(ticket_path.read_text(encoding="utf-8")))
        answers.append(answer_path.read_text(encoding="utf-8"))

    results: dict[str, list[dict]] = {}
    for model in MODELS:
        print(f"\n=== Testing {model} ===")
        results[model] = []
        for i, (ticket, answer) in enumerate(zip(tickets, answers, strict=False), start=1):
            print(f"  [{i}/5] {ticket['title'][:70]}")
            r = run_one(svc, model, ticket, answer)
            results[model].append({
                "ticket_index": i,
                "ticket_title": ticket["title"],
                **r,
            })
            # краткий отчёт
            if r["ok"]:
                print(f"        ok in {r['duration_ms']} ms, {len(r['text'])} chars")
            else:
                print(f"        FAIL in {r['duration_ms']} ms: {r['error'][:100]}")

    # Save raw
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✓ Raw results saved to {OUT_PATH.relative_to(REPO_ROOT)}")

    # Summary table
    print("\n=== Summary ===")
    print(f"{'Model':<15} {'OK':<5} {'Avg ms':<10} {'JSON valid':<12}")
    for model, items in results.items():
        ok_count = sum(1 for r in items if r["ok"])
        avg_ms = sum(r["duration_ms"] for r in items) // max(len(items), 1)
        # Определим, валиден ли JSON, по содержимому text
        json_ok = 0
        for r in items:
            if r["ok"] and r["text"]:
                try:
                    json.loads(r["text"])
                    json_ok += 1
                except Exception:
                    pass
        print(f"{model:<15} {ok_count}/5  {avg_ms:<10} {json_ok}/5")

    return 0


if __name__ == "__main__":
    sys.exit(main())
