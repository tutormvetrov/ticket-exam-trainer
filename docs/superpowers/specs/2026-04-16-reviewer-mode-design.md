# Reviewer Mode: Deep Thesis-Level Answer Review

**Date:** 2026-04-16
**Scope:** New "Review" training mode + upgraded feedback in existing text-input modes
**Affected layers:** `infrastructure/ollama/`, `application/`, `ui/components/`, `ui/views/`

---

## Problem

Current answer evaluation gives shallow feedback: a percentage score, 1-2 sentence feedback, and a list of weak points. For a written exam, students need a thesis-level review: which key points they covered, which they missed, what was superficial, and concrete recommendations for improvement.

## Strategy

Single-prompt approach (Approach A). One LLM call receives the student's answer + reference theses, returns structured JSON with per-thesis verdicts. Same complexity as the existing `analyze_logical_gaps` call — no additional performance burden.

Three deliverables:
1. **Review engine** — new prompt, service method, and DTO
2. **8th training mode "Рецензия"** — dedicated workspace for full written answers with detailed review
3. **Feedback upgrade** — existing text-input modes (Active Recall, Mini-Exam, State Exam Full) show thesis-level review when available

---

## Part 1: Review Engine

### Data Model

New dataclass in `application/ui_data.py`:

```
@dataclass(slots=True)
class ThesisVerdict:
    thesis_label: str                           # Reference thesis name ("Определение", "Классификация", ...)
    status: str                                 # "covered" | "partial" | "missing"
    comment: str                                # LLM commentary on this thesis
    student_excerpt: str                        # Fragment of student's answer covering this thesis, or ""

@dataclass(slots=True)
class ReviewVerdict:
    thesis_verdicts: list[ThesisVerdict]        # One per reference thesis
    structure_notes: list[str]                  # Structural observations ("нет вступления", ...)
    strengths: list[str]                        # What was done well
    recommendations: list[str]                  # Concrete actions ("добавь пример к тезису Y")
    overall_score: int                          # 0-100
    overall_comment: str                        # 1-2 sentence summary
```

### Prompt

New function in `infrastructure/ollama/prompts.py`:

```python
def review_prompt(
    ticket_title: str,
    reference_theses: list[dict[str, str]],   # [{"label": "Определение", "text": "..."}, ...]
    student_answer: str,
) -> tuple[str, str]:
```

System prompt instructs LLM to:
- Compare student answer against each reference thesis
- Mark each as covered/partial/missing with a comment
- Note structural issues (intro, transitions, conclusion)
- List strengths and concrete recommendations
- Return valid JSON matching ReviewVerdict schema

Estimated prompt size: ~1000-1500 input tokens, ~500-800 output tokens. Within qwen3:8b capability, same order as existing `refine_ticket_structure`.

### Service Method

New method in `infrastructure/ollama/service.py`:

```python
def review_answer(
    self,
    ticket_title: str,
    reference_theses: list[dict[str, str]],
    student_answer: str,
    model: str,
) -> OllamaScenarioResult:
```

Calls `review_prompt()`, parses JSON response, returns raw JSON string in `OllamaScenarioResult.text`.

### Integration in Scoring

In `application/scoring.py` (`MicroSkillScoringService`):
- New method `build_review_verdict(ticket, mode_key, answer_text) -> ReviewVerdict | None`
- Extracts reference theses from ticket atoms (standard) or answer_blocks (state exam)
- Calls `ollama_service.review_answer()`
- Parses JSON into `ReviewVerdict`
- Returns None on failure (LLM unavailable, parse error, timeout)

### Rule-Based Fallback

When LLM is unavailable:
- Extract keywords from each reference thesis
- Check keyword presence in student answer
- Mark as "covered" if >50% keywords present, "partial" if 20-50%, "missing" if <20%
- No comments, no structure_notes, no recommendations
- `overall_comment = "Рецензия без LLM: только сопоставление ключевых слов."`

This provides degraded but functional feedback, consistent with existing fallback pattern.

---

## Part 2: 8th Training Mode "Рецензия"

### Mode Registration

- Mode key: `"review"`
- Add `TrainingModeSpec` to `ui/training_mode_registry.py`
- Add to `ui/training_catalog.py` `DEFAULT_TRAINING_MODES`

### ReviewWorkspace

New class `ReviewWorkspace(TrainingWorkspaceBase)` in `ui/components/training_workspaces.py`.

**Layout:**
1. Ticket context: title + key thesis labels (like Reading mode)
2. `QTextEdit` for full written answer (min height 300px, placeholder: "Напишите полный ответ на билет, как на экзамене.")
3. "Отправить на рецензию" button (primary variant)
4. Result area — reusable `ReviewVerdictWidget` (see Part 3)

**Behavior:**
- `_set_ticket(ticket)` — populates ticket context, clears answer field
- `_submit()` — validates non-empty, sets "Рецензируем ответ...", emits `evaluate_requested`
- `show_evaluation(result)` — if `result.review` is not None, shows `ReviewVerdictWidget`; otherwise falls back to standard result display

### Evaluation Flow

When mode is `"review"`, `MicroSkillScoringService.evaluate_answer()`:
1. Runs standard scoring (score, weak_points) — same as other modes
2. Calls `build_review_verdict()` for thesis-level review
3. Returns `TrainingEvaluationResult` with `review` field populated

---

## Part 3: Feedback Upgrade in Existing Modes

### TrainingEvaluationResult Extension

Add optional field to existing dataclass in `application/ui_data.py`:

```python
@dataclass(slots=True)
class TrainingEvaluationResult:
    ok: bool
    score_percent: int
    feedback: str
    weak_points: list[str]
    error: str = ""
    block_scores: dict[str, int] = field(default_factory=dict)
    criterion_scores: dict[str, int] = field(default_factory=dict)
    followup_questions: list[str] = field(default_factory=list)
    review: ReviewVerdict | None = None          # NEW
```

### Which Modes Get Review

| Mode | Gets review? | Reason |
|------|-------------|--------|
| reading | No | No user text input |
| active-recall | Yes | Free-text recall answer |
| cloze | No | Fill-in-the-blank, binary check |
| matching | No | Pair matching, binary check |
| plan | No | Ordering, binary check |
| mini-exam | Yes | Full written answer under timer |
| state-exam-full | Yes | Block-structured written answer |
| review | Yes | Dedicated review mode |

### Scoring Integration

In `MicroSkillScoringService.evaluate_answer()`, after existing scoring logic:

```python
if mode_key in {"active-recall", "mini-exam", "state-exam-full", "review"}:
    review_verdict = self.build_review_verdict(ticket, mode_key, answer_text)
    result.review = review_verdict  # None if LLM failed
```

No change to existing scoring. Review is purely additive.

### ReviewVerdictWidget (Reusable UI Component)

New widget in `ui/components/review_verdict.py`:

**Takes:** `ReviewVerdict`
**Renders:**
- Per-thesis cards in a vertical layout:
  - Status icon: ✓ green (covered), ◐ yellow (partial), ✗ red (missing)
  - Thesis label (bold)
  - LLM comment
  - Student excerpt (muted, if present)
- "Сильные стороны" section (if non-empty)
- "Рекомендации" section (if non-empty)
- "Замечания по структуре" section (if non-empty)
- Overall score badge + comment at top

Styled with existing `current_colors()` palette, consistent with other workspace results.

### Integration in show_evaluation

In `TrainingWorkspaceBase.show_evaluation()`:
- If `result.review` is not None: hide the standard `result_body` text, show `ReviewVerdictWidget` instead
- If `result.review` is None: show standard feedback as before

This means existing behavior is completely preserved when LLM is unavailable.

---

## Files Affected

| File | Changes |
|------|---------|
| `application/ui_data.py` | Add `ThesisVerdict`, `ReviewVerdict` dataclasses. Add `review` field to `TrainingEvaluationResult` |
| `infrastructure/ollama/prompts.py` | Add `review_prompt()` function |
| `infrastructure/ollama/service.py` | Add `review_answer()` method |
| `application/scoring.py` | Add `build_review_verdict()` method. Call it for text-input modes |
| `ui/components/review_verdict.py` | New file: `ReviewVerdictWidget` |
| `ui/components/training_workspaces.py` | Add `ReviewWorkspace` class. Update `create_training_workspaces()`. Update `show_evaluation()` in base class |
| `ui/training_mode_registry.py` | Add `TrainingModeSpec` for `"review"` |
| `ui/training_catalog.py` | Add `"review"` to `DEFAULT_TRAINING_MODES` |

---

## Scope Boundaries

**In scope:**
- Review engine (prompt, service, DTO, fallback)
- 8th training mode "Рецензия"
- ReviewVerdictWidget (reusable)
- Feedback upgrade for active-recall, mini-exam, state-exam-full
- Tests for review engine and verdict parsing

**Out of scope:**
- Poabzatsny (paragraph-level) review — thesis-level is sufficient
- Review history / saved reviews — reviews are ephemeral like current evaluations
- Review for defense DLC — separate integration later
- Export reviews to PDF — future Export & Share feature

---

## Testing Strategy

- Unit tests for `review_prompt()` — verify prompt structure
- Unit tests for `build_review_verdict()` — mock Ollama, verify JSON parsing into `ReviewVerdict`
- Unit tests for rule-based fallback — keyword matching produces correct statuses
- UI test for `ReviewWorkspace` — renders empty state, sets ticket, shows evaluation
- Integration test with live Ollama (marker `live_ollama`) — full round-trip
- Existing tests must remain green — `TrainingEvaluationResult` change is backwards-compatible (new field has default None)
