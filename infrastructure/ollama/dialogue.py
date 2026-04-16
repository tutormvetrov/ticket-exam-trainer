from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DialogueTranscriptLine:
    speaker: str
    text: str


@dataclass(slots=True)
class DialogueTurnContext:
    session_id: str
    ticket_id: str
    ticket_title: str
    ticket_summary: str
    persona_kind: str
    turn_index: int
    transcript: list[DialogueTranscriptLine] = field(default_factory=list)
    ticket_atoms: list[dict[str, object]] = field(default_factory=list)
    ticket_answer_blocks: list[dict[str, object]] = field(default_factory=list)
    examiner_prompts: list[str] = field(default_factory=list)
    answer_profile_hints: list[str] = field(default_factory=list)
    weak_points: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DialogueTurnPayload:
    feedback_text: str
    next_question: str
    weakness_focus: str
    should_finish: bool
    finish_reason: str


@dataclass(slots=True)
class DialogueTurnResult:
    ok: bool
    payload: DialogueTurnPayload
    used_llm: bool
    used_fallback: bool
    latency_ms: int | None
    error: str = ""
