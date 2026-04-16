# Reviewer Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add thesis-level answer review — a new review engine, 8th training mode "Рецензия", and upgraded feedback in Active Recall / Mini-Exam / State Exam Full.

**Architecture:** Single LLM prompt returns structured JSON with per-thesis verdicts. New `ReviewVerdict` DTO flows from Ollama service through scoring to UI. A reusable `ReviewVerdictWidget` renders verdicts in the new ReviewWorkspace and in existing workspaces. Rule-based fallback when LLM is unavailable.

**Tech Stack:** Python 3.12+, PySide6, Ollama (qwen3:8b), pytest

**Spec:** `docs/superpowers/specs/2026-04-16-reviewer-mode-design.md`

---

### Task 1: Add ReviewVerdict DTOs

Add `ThesisVerdict` and `ReviewVerdict` dataclasses. Add `review` field to `TrainingEvaluationResult`.

**Files:**
- Modify: `application/ui_data.py`
- Test: `tests/test_scoring_and_review.py`

- [ ] **Step 1: Write test for new DTOs**

Add to `tests/test_scoring_and_review.py`:

```python
def test_review_verdict_dataclass_defaults() -> None:
    from application.ui_data import ReviewVerdict, ThesisVerdict, TrainingEvaluationResult

    tv = ThesisVerdict(thesis_label="Определение", status="covered", comment="Точно.", student_excerpt="Это ресурс.")
    assert tv.status == "covered"

    rv = ReviewVerdict(
        thesis_verdicts=[tv],
        structure_notes=["Нет вывода"],
        strengths=["Хорошее определение"],
        recommendations=["Добавить пример"],
        overall_score=72,
        overall_comment="Неплохо.",
    )
    assert rv.overall_score == 72
    assert len(rv.thesis_verdicts) == 1

    result = TrainingEvaluationResult(ok=True, score_percent=72, feedback="ok", weak_points=[])
    assert result.review is None

    result_with_review = TrainingEvaluationResult(ok=True, score_percent=72, feedback="ok", weak_points=[], review=rv)
    assert result_with_review.review is not None
    assert result_with_review.review.overall_score == 72
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scoring_and_review.py::test_review_verdict_dataclass_defaults -v`
Expected: FAIL — `ImportError: cannot import name 'ReviewVerdict'`

- [ ] **Step 3: Add DTOs to `application/ui_data.py`**

At the end of the file, after `TrainingEvaluationResult`, add:

```python
@dataclass(slots=True)
class ThesisVerdict:
    thesis_label: str
    status: str  # "covered" | "partial" | "missing"
    comment: str
    student_excerpt: str


@dataclass(slots=True)
class ReviewVerdict:
    thesis_verdicts: list[ThesisVerdict]
    structure_notes: list[str]
    strengths: list[str]
    recommendations: list[str]
    overall_score: int
    overall_comment: str
```

And add `review: ReviewVerdict | None = None` field to `TrainingEvaluationResult`. The field must go after all fields with defaults. Add it after the `error` field:

Change `TrainingEvaluationResult` to:

```python
@dataclass(slots=True)
class TrainingEvaluationResult:
    ok: bool
    score_percent: int
    feedback: str
    weak_points: list[str]
    answer_profile_code: str = "standard_ticket"
    block_scores: dict[str, int] = field(default_factory=dict)
    criterion_scores: dict[str, int] = field(default_factory=dict)
    followup_questions: list[str] = field(default_factory=list)
    error: str = ""
    review: ReviewVerdict | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scoring_and_review.py::test_review_verdict_dataclass_defaults -v`
Expected: PASS

- [ ] **Step 5: Run full suite to verify no regressions**

Run: `pytest tests/ -q`
Expected: all pass (new field has default `None`, backward-compatible)

- [ ] **Step 6: Commit**

```bash
git add application/ui_data.py tests/test_scoring_and_review.py
git commit -m "feat: add ThesisVerdict and ReviewVerdict DTOs

New dataclasses for thesis-level answer review. Add optional review
field to TrainingEvaluationResult (default None, backward-compatible)."
```

---

### Task 2: Add review prompt

Create the LLM prompt that produces a ReviewVerdict JSON.

**Files:**
- Modify: `infrastructure/ollama/prompts.py`
- Test: `tests/test_ollama_service.py`

- [ ] **Step 1: Write test for prompt structure**

Add to `tests/test_ollama_service.py`:

```python
def test_review_prompt_includes_all_theses() -> None:
    from infrastructure.ollama.prompts import review_prompt

    theses = [
        {"label": "Определение", "text": "Государственная собственность — это..."},
        {"label": "Примеры", "text": "Земля, здания, транспорт."},
    ]
    system, prompt = review_prompt("Что такое госсобственность?", theses, "Госсобственность — это ресурс.")

    assert "Определение" in prompt
    assert "Примеры" in prompt
    assert "Госсобственность — это ресурс" in prompt
    assert "JSON" in system
    assert "thesis_verdicts" in system or "thesis_verdicts" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ollama_service.py::test_review_prompt_includes_all_theses -v`
Expected: FAIL — `ImportError: cannot import name 'review_prompt'`

- [ ] **Step 3: Add `review_prompt` to `infrastructure/ollama/prompts.py`**

Add at the end of the file:

```python
def review_prompt(
    ticket_title: str,
    reference_theses: list[dict[str, str]],
    student_answer: str,
) -> tuple[str, str]:
    system = (
        "You are a strict exam answer reviewer. "
        "Compare the student answer against each reference thesis. "
        "For each thesis, decide: covered, partial, or missing. "
        "Add a short comment in Russian explaining your verdict. "
        "If the student's text covers the thesis, quote the relevant excerpt. "
        "Note structural issues (missing intro, no conclusion, weak transitions). "
        "List strengths and concrete recommendations in Russian. "
        "Return valid JSON with keys: thesis_verdicts, structure_notes, strengths, recommendations, overall_score, overall_comment. "
        "Each item in thesis_verdicts must have: thesis_label, status, comment, student_excerpt."
    )
    theses_text = "\n".join(
        f"- {thesis['label']}: {thesis['text']}" for thesis in reference_theses
    )
    prompt = (
        f"TICKET: {ticket_title}\n"
        f"REFERENCE THESES:\n{theses_text}\n"
        f"STUDENT ANSWER:\n{student_answer}\n"
        "Review the answer against each thesis. Return JSON."
    )
    return system, prompt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ollama_service.py::test_review_prompt_includes_all_theses -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add infrastructure/ollama/prompts.py tests/test_ollama_service.py
git commit -m "feat: add review_prompt for thesis-level answer review

LLM prompt that compares student answer against reference theses and
returns structured JSON with per-thesis verdicts, structure notes,
strengths, recommendations, and overall score."
```

---

### Task 3: Add `review_answer` service method

Wire the prompt into OllamaService with JSON parsing.

**Files:**
- Modify: `infrastructure/ollama/service.py`
- Test: `tests/test_ollama_service.py`

- [ ] **Step 1: Write test for `review_answer`**

Add to `tests/test_ollama_service.py`:

```python
def test_review_answer_parses_json_response(monkeypatch) -> None:
    import json
    from infrastructure.ollama.client import OllamaResponse
    from infrastructure.ollama.service import OllamaService

    service = OllamaService("http://localhost:11434")

    verdict_json = json.dumps({
        "thesis_verdicts": [
            {"thesis_label": "Определение", "status": "covered", "comment": "Верно.", "student_excerpt": "Это ресурс."},
            {"thesis_label": "Примеры", "status": "missing", "comment": "Не указаны.", "student_excerpt": ""},
        ],
        "structure_notes": ["Нет вывода"],
        "strengths": ["Точное определение"],
        "recommendations": ["Добавить примеры"],
        "overall_score": 55,
        "overall_comment": "Половина тезисов раскрыта.",
    })

    monkeypatch.setattr(
        service.client,
        "generate",
        lambda model, prompt, *, system="", format_name=None, temperature=0.2: OllamaResponse(
            ok=True, status_code=200, payload={"response": verdict_json}, latency_ms=500,
        ),
    )

    result = service.review_answer(
        "Что такое госсобственность?",
        [{"label": "Определение", "text": "Это..."}, {"label": "Примеры", "text": "Земля..."}],
        "Госсобственность — это ресурс.",
        "qwen3:8b",
    )

    assert result.ok is True
    assert result.used_llm is True
    parsed = json.loads(result.content)
    assert len(parsed["thesis_verdicts"]) == 2
    assert parsed["overall_score"] == 55
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ollama_service.py::test_review_answer_parses_json_response -v`
Expected: FAIL — `AttributeError: 'OllamaService' object has no attribute 'review_answer'`

- [ ] **Step 3: Add `review_answer` to `infrastructure/ollama/service.py`**

Add the import at the top of the file (with the other prompt imports):

```python
from infrastructure.ollama.prompts import review_prompt
```

Add the method to `OllamaService` class, after `analyze_logical_gaps`:

```python
    def review_answer(
        self,
        ticket_title: str,
        reference_theses: list[dict[str, str]],
        student_answer: str,
        model: str,
    ) -> OllamaScenarioResult:
        system, prompt = review_prompt(ticket_title, reference_theses, student_answer)
        response = self.request_generation(model, prompt, system=system, format_name="json", temperature=0.2)
        if not response.ok:
            return OllamaScenarioResult(False, "", False, response.latency_ms, response.error)
        try:
            parsed = self._parse_json_response(response.payload.get("response", ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return OllamaScenarioResult(False, "", False, response.latency_ms, str(exc))
        return OllamaScenarioResult(True, json.dumps(parsed, ensure_ascii=False), True, response.latency_ms)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ollama_service.py::test_review_answer_parses_json_response -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add infrastructure/ollama/service.py tests/test_ollama_service.py
git commit -m "feat: add review_answer method to OllamaService

Calls review_prompt, parses JSON response, returns OllamaScenarioResult.
Follows the same pattern as analyze_logical_gaps."
```

---

### Task 4: Add `build_review_verdict` to scoring + rule-based fallback

Build ReviewVerdict from Ollama response or rule-based keyword matching.

**Files:**
- Modify: `application/scoring.py`
- Test: `tests/test_scoring_and_review.py`

- [ ] **Step 1: Write test for rule-based fallback**

Add to `tests/test_scoring_and_review.py`:

```python
def test_build_review_verdict_fallback_keyword_matching() -> None:
    from application.scoring import MicroSkillScoringService
    from application.ui_data import ReviewVerdict

    ticket = build_ticket(
        "What is public property?",
        "Public property is a public resource. Examples include land and buildings. It has a legal regime. The management cycle includes accounting and review.",
    )

    service = MicroSkillScoringService()
    verdict = service.build_review_verdict_fallback(ticket, "Public property is a public resource with a legal regime.")

    assert isinstance(verdict, ReviewVerdict)
    assert len(verdict.thesis_verdicts) == len(ticket.atoms)
    statuses = {tv.status for tv in verdict.thesis_verdicts}
    assert statuses <= {"covered", "partial", "missing"}
    assert verdict.overall_score >= 0
    assert verdict.overall_score <= 100
    assert "ключевых слов" in verdict.overall_comment
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scoring_and_review.py::test_build_review_verdict_fallback_keyword_matching -v`
Expected: FAIL — `AttributeError: 'MicroSkillScoringService' object has no attribute 'build_review_verdict_fallback'`

- [ ] **Step 3: Implement fallback and full `build_review_verdict`**

Add imports at the top of `application/scoring.py`:

```python
import json
from application.ui_data import ReviewVerdict, ThesisVerdict
```

Add to `MicroSkillScoringService` class:

```python
    def build_review_verdict(
        self,
        ticket: TicketKnowledgeMap,
        mode_key: str,
        answer_text: str,
        ollama_service=None,
        model: str = "",
    ) -> ReviewVerdict | None:
        reference_theses = self._extract_reference_theses(ticket)
        if not reference_theses:
            return None

        if ollama_service is not None and model:
            try:
                result = ollama_service.review_answer(
                    ticket.title, reference_theses, answer_text, model,
                )
                if result.ok and result.content:
                    parsed = json.loads(result.content)
                    return self._parse_review_verdict(parsed)
            except Exception:  # noqa: BLE001
                pass

        return self.build_review_verdict_fallback(ticket, answer_text)

    def build_review_verdict_fallback(
        self,
        ticket: TicketKnowledgeMap,
        answer_text: str,
    ) -> ReviewVerdict:
        reference_theses = self._extract_reference_theses(ticket)
        answer_tokens = self._normalize(answer_text)
        verdicts: list[ThesisVerdict] = []
        covered_count = 0

        for thesis in reference_theses:
            keywords = [kw.lower() for kw in WORD_PATTERN.findall(thesis["text"]) if len(kw) > 3][:8]
            if not keywords:
                verdicts.append(ThesisVerdict(thesis["label"], "missing", "", ""))
                continue
            matched = sum(1 for kw in keywords if kw.lower() in answer_tokens)
            ratio = matched / len(keywords)
            if ratio >= 0.5:
                status = "covered"
                covered_count += 1
            elif ratio >= 0.2:
                status = "partial"
                covered_count += 0.5
            else:
                status = "missing"
            verdicts.append(ThesisVerdict(thesis["label"], status, "", ""))

        score = int(round(covered_count / max(len(reference_theses), 1) * 100))
        return ReviewVerdict(
            thesis_verdicts=verdicts,
            structure_notes=[],
            strengths=[],
            recommendations=[],
            overall_score=score,
            overall_comment="Рецензия без LLM: только сопоставление ключевых слов.",
        )

    def _extract_reference_theses(self, ticket: TicketKnowledgeMap) -> list[dict[str, str]]:
        if ticket.answer_profile_code is AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN and ticket.answer_blocks:
            return [
                {"label": block.title, "text": block.expected_content}
                for block in ticket.answer_blocks
                if not block.is_missing and block.expected_content.strip()
            ]
        return [
            {"label": atom.label, "text": atom.text}
            for atom in ticket.atoms
            if atom.text.strip()
        ]

    @staticmethod
    def _parse_review_verdict(data: dict) -> ReviewVerdict:
        verdicts = [
            ThesisVerdict(
                thesis_label=item.get("thesis_label", ""),
                status=item.get("status", "missing"),
                comment=item.get("comment", ""),
                student_excerpt=item.get("student_excerpt", ""),
            )
            for item in data.get("thesis_verdicts", [])
        ]
        return ReviewVerdict(
            thesis_verdicts=verdicts,
            structure_notes=data.get("structure_notes", []),
            strengths=data.get("strengths", []),
            recommendations=data.get("recommendations", []),
            overall_score=int(data.get("overall_score", 0)),
            overall_comment=str(data.get("overall_comment", "")),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scoring_and_review.py::test_build_review_verdict_fallback_keyword_matching -v`
Expected: PASS

- [ ] **Step 5: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add application/scoring.py tests/test_scoring_and_review.py
git commit -m "feat: add build_review_verdict with rule-based fallback

Extracts reference theses from ticket atoms or answer blocks.
Calls Ollama for LLM review, falls back to keyword matching.
Parses JSON into ReviewVerdict dataclass."
```

---

### Task 5: Integrate review into `evaluate_answer` in facade

Call `build_review_verdict` for text-input modes and attach to result.

**Files:**
- Modify: `application/facade.py:407-451`

- [ ] **Step 1: Modify `evaluate_answer` in `application/facade.py`**

Find the return statement at the end of `evaluate_answer` (around line 442-451). Before it, add the review call:

```python
        review_verdict = None
        if mode_key in {"active-recall", "mini-exam", "state-exam-full", "review"}:
            review_verdict = self.scoring.build_review_verdict(
                ticket, mode_key, answer,
                ollama_service=self.build_ollama_service(),
                model=self._settings.model,
            )
```

Then add `review=review_verdict` to the `TrainingEvaluationResult` constructor:

Change the return to:

```python
        return TrainingEvaluationResult(
            ok=True,
            score_percent=int(round(outcome.attempt.score * 100)),
            feedback=outcome.attempt.feedback,
            weak_points=[area.title for area in outcome.weak_areas[:4]],
            answer_profile_code=ticket.answer_profile_code.value,
            block_scores={code.value: int(round(score * 100)) for code, score in outcome.block_scores.items()},
            criterion_scores={code.value: int(round(score * 100)) for code, score in outcome.criterion_scores.items()},
            followup_questions=followups,
            review=review_verdict,
        )
```

- [ ] **Step 2: Add `"review"` to `_pick_exercise` type map**

In `_pick_exercise` (around line 453-462), add to the `type_map` dict:

```python
            "review": ExerciseType.ORAL_FULL,
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -q`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add application/facade.py
git commit -m "feat: integrate review verdict into evaluate_answer

Call build_review_verdict for active-recall, mini-exam, state-exam-full,
and review modes. Attach ReviewVerdict to TrainingEvaluationResult."
```

---

### Task 6: Add ReviewVerdictWidget (reusable UI component)

Create the widget that renders a `ReviewVerdict` as thesis cards.

**Files:**
- Create: `ui/components/review_verdict.py`

- [ ] **Step 1: Create `ui/components/review_verdict.py`**

```python
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from application.ui_data import ReviewVerdict
from ui.theme import current_colors


STATUS_ICONS = {"covered": "✓", "partial": "◐", "missing": "✗"}
STATUS_COLORS_KEY = {"covered": "success", "partial": "warning", "missing": "danger"}


class ReviewVerdictWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

    def set_verdict(self, verdict: ReviewVerdict) -> None:
        self._clear()
        colors = current_colors()

        header = QLabel(f"Рецензия: {verdict.overall_score}% — {verdict.overall_comment}")
        header.setWordWrap(True)
        header.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {colors['text']};")
        self._layout.addWidget(header)

        for tv in verdict.thesis_verdicts:
            card = self._build_thesis_card(tv, colors)
            self._layout.addWidget(card)

        if verdict.strengths:
            self._layout.addWidget(self._build_section("Сильные стороны", verdict.strengths, colors))
        if verdict.recommendations:
            self._layout.addWidget(self._build_section("Рекомендации", verdict.recommendations, colors))
        if verdict.structure_notes:
            self._layout.addWidget(self._build_section("Замечания по структуре", verdict.structure_notes, colors))

    def _build_thesis_card(self, tv, colors: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("ThesisVerdictCard")
        color_key = STATUS_COLORS_KEY.get(tv.status, "danger")
        border_color = colors.get(color_key, colors["border"])
        card.setStyleSheet(
            f"QFrame#ThesisVerdictCard {{ background: {colors['card_soft']}; "
            f"border-left: 4px solid {border_color}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        icon = QLabel(STATUS_ICONS.get(tv.status, "?"))
        icon.setStyleSheet(f"font-size: 16px; color: {border_color};")
        icon.setFixedWidth(20)
        top.addWidget(icon)

        label = QLabel(tv.thesis_label)
        label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colors['text']};")
        label.setWordWrap(True)
        top.addWidget(label, 1)
        layout.addLayout(top)

        if tv.comment:
            comment = QLabel(tv.comment)
            comment.setProperty("role", "body")
            comment.setWordWrap(True)
            layout.addWidget(comment)

        if tv.student_excerpt:
            excerpt = QLabel(f"«{tv.student_excerpt}»")
            excerpt.setStyleSheet(f"font-size: 12px; font-style: italic; color: {colors['text_tertiary']};")
            excerpt.setWordWrap(True)
            layout.addWidget(excerpt)

        return card

    def _build_section(self, title: str, items: list[str], colors: dict) -> QFrame:
        section = QFrame()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(4)

        heading = QLabel(title)
        heading.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {colors['text_secondary']};")
        layout.addWidget(heading)

        for item in items[:5]:
            line = QLabel(f"• {item}")
            line.setProperty("role", "body")
            line.setWordWrap(True)
            layout.addWidget(line)

        return section

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def refresh_theme(self) -> None:
        pass  # Rebuilt on each set_verdict call
```

- [ ] **Step 2: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass (no tests needed for pure UI widget — tested via ReviewWorkspace in Task 7)

- [ ] **Step 3: Commit**

```bash
git add ui/components/review_verdict.py
git commit -m "feat: add ReviewVerdictWidget for thesis-level feedback

Reusable widget that renders ReviewVerdict as thesis cards with
status icons, comments, excerpts, strengths, and recommendations.
Used by ReviewWorkspace and existing workspace show_evaluation."
```

---

### Task 7: Add 8th training mode "Рецензия"

Register the mode and create `ReviewWorkspace`.

**Files:**
- Modify: `ui/training_mode_registry.py`
- Modify: `ui/training_catalog.py`
- Modify: `ui/components/training_workspaces.py`

- [ ] **Step 1: Register mode spec in `ui/training_mode_registry.py`**

Add to `TRAINING_MODE_SPECS` dict:

```python
    "review": TrainingModeSpec(
        key="review",
        title="Рецензия ответа",
        workspace_title="Развёрнутая рецензия письменного ответа",
        workspace_hint="Напишите полный ответ на билет как на экзамене. Получите потезисный разбор с рекомендациями.",
        empty_title="Нет билета для рецензии",
        empty_body="Импортируйте материалы или выберите билет вручную, чтобы получить рецензию.",
    ),
```

- [ ] **Step 2: Add mode to catalog in `ui/training_catalog.py`**

Add to `DEFAULT_TRAINING_MODES` list:

```python
    TrainingModeData("review", "Рецензия ответа", "Потезисный разбор письменного ответа", "✎", "#FFF8F0", "#D4863A"),
```

- [ ] **Step 3: Add `ReviewWorkspace` to `ui/components/training_workspaces.py`**

Add import at the top:

```python
from ui.components.review_verdict import ReviewVerdictWidget
```

Add the class before `create_training_workspaces`:

```python
class ReviewWorkspace(TrainingWorkspaceBase):
    def __init__(self, spec: TrainingModeSpec) -> None:
        super().__init__(spec)

        self.context_label = QLabel()
        self.context_label.setWordWrap(True)
        self.context_label.setProperty("role", "body")
        self.content_layout.insertWidget(0, self.context_label)

        self.answer_input = QTextEdit()
        self.answer_input.setObjectName("training-review-input")
        self.answer_input.setProperty("role", "editor")
        self.answer_input.setPlaceholderText("Напишите полный ответ на билет, как на экзамене.")
        self.answer_input.setMinimumHeight(300)
        self.content_layout.insertWidget(1, self.answer_input)

        self.submit_button = QPushButton("Отправить на рецензию")
        self.submit_button.setObjectName("training-review-submit")
        self.submit_button.setProperty("variant", "primary")
        self.submit_button.clicked.connect(self._submit)
        self.content_layout.insertWidget(2, self.submit_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.verdict_widget = ReviewVerdictWidget()
        self.content_layout.insertWidget(3, self.verdict_widget)
        self.verdict_widget.hide()
        self._show_empty()

    def _submit(self) -> None:
        answer_text = self.answer_input.toPlainText().strip()
        if not answer_text:
            self.result_body.setText("Напишите ответ перед отправкой на рецензию.")
            return
        self.result_body.setText("Рецензируем ответ...")
        self.verdict_widget.hide()
        self.evaluate_requested.emit(answer_text)

    def show_evaluation(self, result) -> None:
        if not result.ok:
            self.verdict_widget.hide()
            super().show_evaluation(result)
            return
        if result.review is not None:
            self.result_box.hide()
            self.verdict_widget.set_verdict(result.review)
            self.verdict_widget.show()
        else:
            self.verdict_widget.hide()
            super().show_evaluation(result)

    def _set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        self.answer_input.clear()
        self.verdict_widget.hide()
        if ticket is None:
            self._show_empty()
            return
        self._show_content()
        if ticket.answer_profile_code == AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN and ticket.answer_blocks:
            self.context_label.setText(
                "Структура ответа: "
                + ", ".join(block.title for block in ticket.answer_blocks)
            )
        else:
            labels = [atom.label for atom in ticket.atoms[:6]]
            self.context_label.setText(
                "Ключевые тезисы: " + ", ".join(labels) if labels else "Тезисы пока не выделены."
            )

    def refresh_theme(self) -> None:
        super().refresh_theme()
        if self.current_ticket is not None:
            self._set_ticket(self.current_ticket)
```

- [ ] **Step 4: Register in `create_training_workspaces`**

In `create_training_workspaces()` function, add:

```python
        "review": ReviewWorkspace(TRAINING_MODE_SPECS["review"]),
```

- [ ] **Step 5: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add ui/training_mode_registry.py ui/training_catalog.py ui/components/training_workspaces.py
git commit -m "feat: add 8th training mode 'Рецензия'

Register ReviewWorkspace as the review mode. Students write a full
answer and receive a thesis-level review via ReviewVerdictWidget.
Includes mode spec, catalog entry, and workspace implementation."
```

---

### Task 8: Upgrade show_evaluation in existing workspaces

Show ReviewVerdictWidget in Active Recall, Mini-Exam, and State Exam Full when review is available.

**Files:**
- Modify: `ui/components/training_workspaces.py` — `TrainingWorkspaceBase.show_evaluation`

- [ ] **Step 1: Add ReviewVerdictWidget to base class**

In `TrainingWorkspaceBase.__init__`, after the `result_box` is added to `content_layout` (around line 163), add:

```python
        self.review_widget = ReviewVerdictWidget()
        self.review_widget.hide()
        self.content_layout.addWidget(self.review_widget)
```

The import `from ui.components.review_verdict import ReviewVerdictWidget` was already added in Task 7.

- [ ] **Step 2: Modify `TrainingWorkspaceBase.show_evaluation`**

Replace the existing `show_evaluation` method (around lines 173-191) with:

```python
    def show_evaluation(self, result: TrainingEvaluationResult) -> None:
        if not result.ok:
            self.review_widget.hide()
            self.result_box.show()
            self.result_body.setText(result.error or "Проверка завершилась ошибкой.")
            return
        if result.review is not None:
            self.result_box.hide()
            self.review_widget.set_verdict(result.review)
            self.review_widget.show()
        else:
            self.review_widget.hide()
            self.result_box.show()
            lines = [f"Оценка: {result.score_percent}%"]
            if result.feedback:
                lines.append(result.feedback)
            if result.weak_points:
                lines.append("Слабые места: " + ", ".join(result.weak_points[:4]))
            if result.block_scores:
                lines.append("Блоки госответа:")
                lines.extend(f"• {_block_display_name(code)}: {score}%" for code, score in result.block_scores.items())
            if result.criterion_scores:
                lines.append("Критерии оценки:")
                lines.extend(f"• {_criterion_display_name(code)}: {score}%" for code, score in result.criterion_scores.items())
            if result.followup_questions:
                lines.append("Уточняющие вопросы:")
                lines.extend(f"• {question}" for question in result.followup_questions[:3])
            self.result_body.setText("\n".join(lines))
```

- [ ] **Step 3: Update `_show_empty` to also hide review widget**

In `_show_empty` method, add `self.review_widget.hide()`:

```python
    def _show_empty(self, title: str | None = None, body: str | None = None) -> None:
        self.empty_title.setText(title or self.spec.empty_title)
        self.empty_body.setText(body or self.spec.empty_body)
        self.empty_box.show()
        self.content.hide()
        self.hint_label.hide()
        self.review_widget.hide()
```

- [ ] **Step 4: Update `set_ticket` to hide review widget**

In `set_ticket` method, add `self.review_widget.hide()`:

```python
    def set_ticket(self, ticket: TicketKnowledgeMap | None) -> None:
        self.current_ticket = ticket
        self.result_body.setText("Действие ещё не выполнялось.")
        self.review_widget.hide()
        self.result_box.show()
        self._set_ticket(ticket)
```

- [ ] **Step 5: Run full suite**

Run: `pytest tests/ -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add ui/components/training_workspaces.py
git commit -m "feat: show ReviewVerdictWidget in all text-input workspaces

When result.review is available, show thesis-level review cards
instead of the basic score text. Falls back to standard display
when review is None (LLM unavailable). Applies to Active Recall,
Mini-Exam, State Exam Full, and Review mode."
```

---

### Task 9: Final verification

Run full test suite and verify app launches.

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -q`
Expected: all tests PASS

- [ ] **Step 2: Smoke-test the app imports**

Run: `cd "D:/Coding projects/ticket-exam-trainer" && python -c "import sys; from PySide6.QtWidgets import QApplication; app = QApplication(sys.argv); from ui.main_window import MainWindow; print('MainWindow import OK')"`

Expected: `MainWindow import OK`

- [ ] **Step 3: Verify new mode is registered**

Run: `cd "D:/Coding projects/ticket-exam-trainer" && python -c "from ui.training_mode_registry import TRAINING_MODE_SPECS; assert 'review' in TRAINING_MODE_SPECS; print(f'Review mode registered: {TRAINING_MODE_SPECS[\"review\"].title}')"`

Expected: `Review mode registered: Рецензия ответа`

- [ ] **Step 4: Final commit (if any fixups needed)**

If any test failures were discovered and fixed, commit the fixes.
