"""R1 review-validation harness.

Запускает выбранные Ollama-модели по набору билетов и вариантов ответа,
измеряет качественные и операционные метрики и пишет два артефакта:

- ``docs/superpowers/specs/2026-04-19-r1-validation-results.md`` — человеко-
  читаемый отчёт (таблицы модель×метрика, per-ticket breakdown, разрезы
  score ~ answer_quality).
- ``docs/superpowers/specs/2026-04-19-r1-validation-raw.json`` — сырой набор
  прогонов (answer tier, parsed verdicts, timings, ошибки парсинга).

Запуск (примеры)::

    python scripts/r1_review_validation.py --help
    python scripts/r1_review_validation.py --max-ticket 2 --max-answer 3
    python scripts/r1_review_validation.py \\
        --models qwen3:8b,qwen3:1.7b,mistral:instruct \\
        --timeout 180

Если модель не установлена локально — пропускается с ``installed=false`` в
raw-JSON и отдельным пунктом в Markdown-отчёте. Сам запуск не падает.

Harness сознательно **не** сравнивает вердикты с human-expert разметкой:
для R1 ручной review pending (см. приёмку в задании).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Разрешаем запуск как `python scripts/r1_review_validation.py` без CWD-танцев.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from infrastructure.ollama.service import OllamaService  # noqa: E402

_DEFAULT_FIXTURE = _PROJECT_ROOT / "tests" / "fixtures" / "review_validation" / "tickets.json"
_RESULTS_MD = _PROJECT_ROOT / "docs" / "superpowers" / "specs" / "2026-04-19-r1-validation-results.md"
_RESULTS_JSON = _PROJECT_ROOT / "docs" / "superpowers" / "specs" / "2026-04-19-r1-validation-raw.json"

_REQUIRED_KEYS = (
    "thesis_verdicts",
    "structure_notes",
    "strengths",
    "recommendations",
    "overall_score",
    "overall_comment",
)
# Полный порядок (для --max-answer 0 / все).
_ANSWER_QUALITY_ORDER = ("excellent", "good", "partial", "weak", "empty", "wrong_answer")
# Приоритет для усечённого прогона: первым делом берём крайние точки
# (excellent ↔ empty), чтобы всегда получить данные для discrimination,
# потом «середины» и «wrong» — они дают картину на false-covered случаях.
_ANSWER_QUALITY_PRIORITY = (
    "excellent",
    "empty",
    "good",
    "wrong_answer",
    "partial",
    "weak",
)


@dataclass(slots=True)
class CallResult:
    model: str
    ticket_id: str
    ticket_title: str
    answer_quality: str
    answer_length: int
    latency_seconds: float
    ok: bool
    json_valid: bool
    schema_valid: bool
    missing_keys: list[str]
    overall_score: int | None
    parsed_content: dict[str, object] | None
    error: str


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="R1 review-validation harness for Ollama review-models.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--models",
        default="",
        help=(
            "Comma-separated list of Ollama models to probe (e.g. "
            "'qwen3:8b,qwen3:1.7b,mistral:instruct'). Empty = use all installed."
        ),
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=_DEFAULT_FIXTURE,
        help="Path to fixtures JSON (see tests/fixtures/review_validation/tickets.json).",
    )
    parser.add_argument(
        "--max-ticket",
        type=int,
        default=0,
        help="Limit number of tickets (0 = all).",
    )
    parser.add_argument(
        "--max-answer",
        type=int,
        default=0,
        help="Limit number of answer variants per ticket (0 = all).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Per-call timeout in seconds.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama base URL.",
    )
    parser.add_argument(
        "--results-md",
        type=Path,
        default=_RESULTS_MD,
        help="Output Markdown report path.",
    )
    parser.add_argument(
        "--results-json",
        type=Path,
        default=_RESULTS_JSON,
        help="Output raw JSON path.",
    )
    return parser.parse_args(argv)


def _load_fixture(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _select_tickets(
    payload: dict,
    *,
    max_ticket: int,
    max_answer: int,
) -> list[dict]:
    tickets = list(payload.get("tickets", []))
    if max_ticket > 0:
        tickets = tickets[:max_ticket]

    selected = []
    for ticket in tickets:
        answers = ticket.get("answers", {}) or {}
        # Если стоит cap — сначала тянем по «discrimination-priority» порядку,
        # чтобы в любом усечённом прогоне excellent+empty точно попали в выборку.
        # Если cap=0 — берём «естественный» порядок по quality (excellent→wrong).
        if max_answer > 0:
            priority_keys = list(_ANSWER_QUALITY_PRIORITY)
            for key in answers:
                if key not in priority_keys:
                    priority_keys.append(key)
            ordered_pairs = [
                (key, answers[key]) for key in priority_keys if key in answers
            ]
            ordered_pairs = ordered_pairs[:max_answer]
        else:
            ordered_pairs = [
                (key, answers[key]) for key in _ANSWER_QUALITY_ORDER if key in answers
            ]
            for key, value in answers.items():
                if key not in _ANSWER_QUALITY_ORDER:
                    ordered_pairs.append((key, value))

        selected.append({
            "ticket_id": ticket.get("ticket_id", ""),
            "title": ticket.get("title", ""),
            "reference_theses": ticket.get("reference_theses", []),
            "answers": ordered_pairs,
        })
    return selected


def _installed_models(service: OllamaService) -> list[str]:
    try:
        diag = service.inspect()
    except Exception:  # noqa: BLE001
        return []
    return list(diag.available_models)


def _resolve_models(
    service: OllamaService,
    requested: list[str],
    installed: list[str],
) -> tuple[list[str], list[str]]:
    """Returns (models_to_run, missing_models)."""
    if not requested:
        return list(installed), []

    present, missing = [], []
    installed_lower = {name.lower() for name in installed}
    for candidate in requested:
        if candidate.lower() in installed_lower:
            present.append(candidate)
        else:
            missing.append(candidate)
    return present, missing


def _validate_schema(parsed: dict) -> tuple[bool, list[str]]:
    missing = [key for key in _REQUIRED_KEYS if key not in parsed]
    if missing:
        return False, missing
    # Легковесные дополнительные проверки: массивы — массивы, score — число.
    array_keys = ("thesis_verdicts", "structure_notes", "strengths", "recommendations")
    for key in array_keys:
        if not isinstance(parsed.get(key), list):
            missing.append(f"{key}:not_list")
    score = parsed.get("overall_score")
    if not isinstance(score, (int, float)):
        missing.append("overall_score:not_number")
    return (not missing), missing


def _coerce_score(parsed: dict) -> int | None:
    score = parsed.get("overall_score") if isinstance(parsed, dict) else None
    if isinstance(score, bool):  # bool is subclass of int — отбрасываем
        return None
    if isinstance(score, int):
        return max(0, min(score, 100))
    if isinstance(score, float):
        return max(0, min(int(score), 100))
    return None


def _run_single(
    service: OllamaService,
    model: str,
    ticket: dict,
    answer_quality: str,
    answer_text: str,
) -> CallResult:
    t0 = time.monotonic()
    try:
        result = service.review_answer(
            ticket["title"],
            ticket["reference_theses"],
            answer_text,
            model,
        )
    except Exception as exc:  # noqa: BLE001 — harness не должен падать
        dt = time.monotonic() - t0
        return CallResult(
            model=model,
            ticket_id=ticket["ticket_id"],
            ticket_title=ticket["title"],
            answer_quality=answer_quality,
            answer_length=len(answer_text),
            latency_seconds=dt,
            ok=False,
            json_valid=False,
            schema_valid=False,
            missing_keys=["<exception>"],
            overall_score=None,
            parsed_content=None,
            error=f"exception: {exc!r}",
        )
    dt = time.monotonic() - t0

    ok = bool(result.ok)
    json_valid = False
    schema_valid = False
    missing_keys: list[str] = []
    parsed_content: dict | None = None
    overall_score: int | None = None
    error = result.error or ""

    if ok and result.content:
        try:
            parsed_content = json.loads(result.content)
            json_valid = True
        except json.JSONDecodeError as exc:
            parsed_content = None
            json_valid = False
            error = f"json_decode: {exc}"

    if json_valid and isinstance(parsed_content, dict):
        schema_valid, missing_keys = _validate_schema(parsed_content)
        overall_score = _coerce_score(parsed_content)

    return CallResult(
        model=model,
        ticket_id=ticket["ticket_id"],
        ticket_title=ticket["title"],
        answer_quality=answer_quality,
        answer_length=len(answer_text),
        latency_seconds=dt,
        ok=ok,
        json_valid=json_valid,
        schema_valid=schema_valid,
        missing_keys=missing_keys,
        overall_score=overall_score,
        parsed_content=parsed_content,
        error=error,
    )


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    # statistics.quantiles хоть и есть, но на малых выборках ведёт себя
    # непредсказуемо — делаем руками на indexed-position (nearest-rank).
    k = max(0, min(int(round((pct / 100.0) * (len(ordered) - 1))), len(ordered) - 1))
    return ordered[k]


def _aggregate(calls: list[CallResult]) -> dict:
    if not calls:
        return {
            "calls": 0,
            "json_valid_rate": None,
            "schema_valid_rate": None,
            "latency_p50": None,
            "latency_p95": None,
            "discrimination": None,
            "score_by_tier": {},
            "errors": [],
        }

    total = len(calls)
    json_valid = sum(1 for c in calls if c.json_valid)
    schema_valid = sum(1 for c in calls if c.schema_valid)
    latencies = [c.latency_seconds for c in calls]

    by_tier: dict[str, list[int]] = {}
    for c in calls:
        if c.overall_score is not None:
            by_tier.setdefault(c.answer_quality, []).append(c.overall_score)

    score_means = {
        tier: (sum(scores) / len(scores)) if scores else None
        for tier, scores in by_tier.items()
    }

    discrimination: float | None = None
    excellent_avg = score_means.get("excellent")
    empty_avg = score_means.get("empty")
    if excellent_avg is not None and empty_avg is not None:
        discrimination = excellent_avg - empty_avg

    errors = [
        {
            "ticket_id": c.ticket_id,
            "answer_quality": c.answer_quality,
            "error": c.error,
        }
        for c in calls
        if c.error or not c.json_valid or not c.schema_valid
    ]

    return {
        "calls": total,
        "json_valid_rate": json_valid / total if total else None,
        "schema_valid_rate": schema_valid / total if total else None,
        "latency_p50": _percentile(latencies, 50),
        "latency_p95": _percentile(latencies, 95),
        "latency_mean": statistics.fmean(latencies) if latencies else None,
        "discrimination": discrimination,
        "score_means": score_means,
        "score_by_tier_samples": by_tier,
        "errors": errors,
    }


def _fmt_float(value, *, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float) and (value != value):  # NaN guard
        return "—"
    return f"{value:.{digits}f}{suffix}"


def _fmt_rate(value) -> str:
    if value is None:
        return "—"
    return f"{100 * value:.0f}%"


def _fmt_score(value) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}"


def _render_markdown(
    *,
    args: argparse.Namespace,
    requested_models: list[str],
    installed_models: list[str],
    models_run: list[str],
    models_missing: list[str],
    per_model: dict[str, dict],
    calls_by_model: dict[str, list[CallResult]],
    started_at: str,
    finished_at: str,
) -> str:
    lines: list[str] = []
    lines.append("# R1 Review-Validation Results")
    lines.append("")
    lines.append(f"- **Generated:** {finished_at}")
    lines.append(f"- **Fixture:** `{args.fixture.as_posix()}`")
    lines.append(f"- **Ollama endpoint:** `{args.base_url}`")
    lines.append(f"- **Requested models:** `{', '.join(requested_models) if requested_models else '(all installed)'}`")
    lines.append(f"- **Models run:** `{', '.join(models_run) if models_run else '(none)'}`")
    if models_missing:
        lines.append(
            "- **Missing (skipped):** `" + ", ".join(models_missing) + "` — "
            "модель не установлена локально; запустите `ollama pull <model>`."
        )
    lines.append(f"- **Max ticket / answer caps:** {args.max_ticket or 'all'} / {args.max_answer or 'all'}")
    lines.append(f"- **Per-call timeout:** {args.timeout:.0f}s")
    lines.append(f"- **Run window:** {started_at} → {finished_at}")
    lines.append("")
    lines.append(
        "> **Human-agreement:** manual review pending. Эта итерация фиксирует "
        "только JSON/schema-валидность, латентность и discrimination "
        "(|score(excellent) − score(empty)|)."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")

    if not per_model:
        lines.append("_No models produced any calls (ничего не прогнали)._")
        lines.append("")
    else:
        header = (
            "| Model | Calls | JSON-valid | Schema-valid | p50 (s) | p95 (s) | "
            "Mean (s) | Discrimination | Score(excellent) | Score(empty) |"
        )
        sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
        lines.append(header)
        lines.append(sep)
        for model, agg in per_model.items():
            excellent = agg["score_means"].get("excellent")
            empty = agg["score_means"].get("empty")
            lines.append(
                "| `{model}` | {calls} | {jv} | {sv} | {p50} | {p95} | {mean} | "
                "{discr} | {ex} | {em} |".format(
                    model=model,
                    calls=agg["calls"],
                    jv=_fmt_rate(agg["json_valid_rate"]),
                    sv=_fmt_rate(agg["schema_valid_rate"]),
                    p50=_fmt_float(agg["latency_p50"]),
                    p95=_fmt_float(agg["latency_p95"]),
                    mean=_fmt_float(agg["latency_mean"]),
                    discr=_fmt_float(agg["discrimination"]),
                    ex=_fmt_score(excellent),
                    em=_fmt_score(empty),
                )
            )
        lines.append("")
        lines.append(
            "Цель по discrimination (из research): ≥50. Ниже — warning, модель "
            "не различает полный и пустой ответы."
        )
        lines.append("")

    lines.append("## Per-ticket breakdown")
    lines.append("")
    if not calls_by_model:
        lines.append("_нет данных_")
        lines.append("")
    else:
        for model, calls in calls_by_model.items():
            lines.append(f"### `{model}`")
            lines.append("")
            if not calls:
                lines.append("_no calls_")
                lines.append("")
                continue
            lines.append(
                "| Ticket | Answer tier | Latency (s) | JSON | Schema | Score | Error |"
            )
            lines.append("|---|---|---:|:---:|:---:|---:|---|")
            for call in calls:
                lines.append(
                    "| {ticket} | {tier} | {lat} | {jv} | {sv} | {score} | {err} |".format(
                        ticket=call.ticket_id,
                        tier=call.answer_quality,
                        lat=_fmt_float(call.latency_seconds),
                        jv="yes" if call.json_valid else "no",
                        sv="yes" if call.schema_valid else "no",
                        score=_fmt_score(call.overall_score),
                        err=(call.error[:60] + "…") if call.error and len(call.error) > 60 else (call.error or "—"),
                    )
                )
            lines.append("")

    lines.append("## Artefacts")
    lines.append("")
    lines.append(f"- Raw JSON: `{args.results_json.as_posix()}`")
    lines.append("")
    lines.append("## How to reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append(
        "python scripts/r1_review_validation.py --models "
        f"{','.join(models_run) if models_run else 'qwen3:8b,qwen3:1.7b,mistral:instruct'}"
        f" --timeout {int(args.timeout)} --max-ticket {args.max_ticket or 2} --max-answer {args.max_answer or 3}"
    )
    lines.append("```")
    lines.append("")
    return "\n".join(lines) + "\n"


def _dump_raw(
    *,
    args: argparse.Namespace,
    requested_models: list[str],
    installed_models: list[str],
    models_run: list[str],
    models_missing: list[str],
    per_model: dict[str, dict],
    calls_by_model: dict[str, list[CallResult]],
    started_at: str,
    finished_at: str,
) -> dict:
    calls_payload: dict[str, list[dict]] = {}
    for model, calls in calls_by_model.items():
        calls_payload[model] = [
            {
                "model": c.model,
                "ticket_id": c.ticket_id,
                "ticket_title": c.ticket_title,
                "answer_quality": c.answer_quality,
                "answer_length": c.answer_length,
                "latency_seconds": c.latency_seconds,
                "ok": c.ok,
                "json_valid": c.json_valid,
                "schema_valid": c.schema_valid,
                "missing_keys": c.missing_keys,
                "overall_score": c.overall_score,
                "parsed_content": c.parsed_content,
                "error": c.error,
            }
            for c in calls
        ]

    return {
        "schema_version": 1,
        "kind": "r1-review-validation-raw",
        "started_at": started_at,
        "finished_at": finished_at,
        "base_url": args.base_url,
        "fixture": args.fixture.as_posix(),
        "timeout_seconds": args.timeout,
        "requested_models": requested_models,
        "installed_models": installed_models,
        "models_run": models_run,
        "models_missing": models_missing,
        "per_model_metrics": per_model,
        "calls": calls_payload,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    fixture_payload = _load_fixture(args.fixture)
    tickets = _select_tickets(
        fixture_payload,
        max_ticket=args.max_ticket,
        max_answer=args.max_answer,
    )
    if not tickets:
        print("no tickets to probe", file=sys.stderr)
        return 2

    service = OllamaService(
        args.base_url,
        timeout_seconds=args.timeout,
        inspect_timeout_seconds=min(args.timeout, 15.0),
        generation_timeout_seconds=args.timeout,
    )

    installed = _installed_models(service)
    if args.models:
        requested = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        requested = []

    models_run, models_missing = _resolve_models(service, requested, installed)

    started_at = datetime.now().isoformat(timespec="seconds")
    calls_by_model: dict[str, list[CallResult]] = {}
    per_model: dict[str, dict] = {}

    print(f"Installed models on endpoint: {installed}", flush=True)
    print(f"Will run: {models_run}; missing: {models_missing}", flush=True)
    print(
        f"Tickets x answers: {sum(len(t['answers']) for t in tickets)} calls per model",
        flush=True,
    )

    for model in models_run:
        print(f"\n=== Model: {model} ===", flush=True)
        calls: list[CallResult] = []
        for ticket in tickets:
            for answer_quality, answer_text in ticket["answers"]:
                label = (
                    f"  [{model}] {ticket['ticket_id']} / {answer_quality}"
                    f" (len={len(answer_text)})"
                )
                print(label, end=" ... ", flush=True)
                result = _run_single(service, model, ticket, answer_quality, answer_text)
                calls.append(result)
                status = "OK" if (result.ok and result.json_valid and result.schema_valid) else "MISS"
                print(
                    f"{status} latency={result.latency_seconds:.1f}s score={result.overall_score}",
                    flush=True,
                )
        calls_by_model[model] = calls
        per_model[model] = _aggregate(calls)

    finished_at = datetime.now().isoformat(timespec="seconds")

    raw_payload = _dump_raw(
        args=args,
        requested_models=requested or ["(all-installed)"],
        installed_models=installed,
        models_run=models_run,
        models_missing=models_missing,
        per_model=per_model,
        calls_by_model=calls_by_model,
        started_at=started_at,
        finished_at=finished_at,
    )
    args.results_json.parent.mkdir(parents=True, exist_ok=True)
    with args.results_json.open("w", encoding="utf-8") as fh:
        json.dump(raw_payload, fh, ensure_ascii=False, indent=2)

    markdown = _render_markdown(
        args=args,
        requested_models=requested or ["(all-installed)"],
        installed_models=installed,
        models_run=models_run,
        models_missing=models_missing,
        per_model=per_model,
        calls_by_model=calls_by_model,
        started_at=started_at,
        finished_at=finished_at,
    )
    args.results_md.parent.mkdir(parents=True, exist_ok=True)
    with args.results_md.open("w", encoding="utf-8") as fh:
        fh.write(markdown)

    print(
        f"\nWrote {args.results_md} and {args.results_json} "
        f"(models_run={len(models_run)}, total calls="
        f"{sum(len(c) for c in calls_by_model.values())}).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
