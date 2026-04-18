# R1 Review-Validation Results

- **Generated:** 2026-04-18T23:08:59
- **Fixture:** `D:/ticket-exam-trainer-flet/tests/fixtures/review_validation/tickets.json`
- **Ollama endpoint:** `http://localhost:11434`
- **Requested models:** `qwen3:0.6b`
- **Models run:** `qwen3:0.6b`
- **Max ticket / answer caps:** 2 / 2
- **Per-call timeout:** 120s
- **Run window:** 2026-04-18T23:05:09 → 2026-04-18T23:08:59

> **Human-agreement:** manual review pending. Эта итерация фиксирует только JSON/schema-валидность, латентность и discrimination (|score(excellent) − score(empty)|).

## Summary

| Model | Calls | JSON-valid | Schema-valid | p50 (s) | p95 (s) | Mean (s) | Discrimination | Score(excellent) | Score(empty) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `qwen3:0.6b` | 4 | 25% | 25% | 73.3 | 75.9 | 57.5 | — | 90.0 | — |

Цель по discrimination (из research): ≥50. Ниже — warning, модель не различает полный и пустой ответы.

## Per-ticket breakdown

### `qwen3:0.6b`

| Ticket | Answer tier | Latency (s) | JSON | Schema | Score | Error |
|---|---|---:|:---:|:---:|---:|---|
| budget-system-ru | excellent | 75.9 | yes | yes | 90.0 | — |
| budget-system-ru | empty | 40.2 | no | no | — | Expecting ',' delimiter: line 4 column 199 (char 526) |
| contract-freedom-principle | excellent | 73.3 | no | no | — | Expecting ',' delimiter: line 4 column 383 (char 1021) |
| contract-freedom-principle | empty | 40.5 | no | no | — | Expecting ',' delimiter: line 4 column 132 (char 607) |

## Artefacts

- Raw JSON: `D:/ticket-exam-trainer-flet/docs/superpowers/specs/2026-04-19-r1-validation-raw.json`

## How to reproduce

```bash
python scripts/r1_review_validation.py --models qwen3:0.6b --timeout 120 --max-ticket 2 --max-answer 2
```

