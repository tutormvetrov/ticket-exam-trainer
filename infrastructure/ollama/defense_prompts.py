from __future__ import annotations

import json


def defense_dossier_prompt(source_text: str, discipline_profile: str) -> tuple[str, str]:
    system = (
        "You are a local thesis defense assistant. "
        "Use only the provided materials. "
        "Do not invent facts. "
        "If evidence is weak, lower confidence and mark needs_review. "
        "Return valid JSON only."
    )
    prompt = (
        "Task: extract a defense dossier from the thesis materials.\n"
        "Return JSON with keys: claims, risk_topics.\n"
        "Each claim must contain: kind, text, confidence, needs_review.\n"
        "Allowed kinds: problem, relevance, object, subject, goal, tasks, methods, novelty, practical_significance, results, limitations, personal_contribution.\n"
        "Each risk topic must contain: text, confidence.\n"
        f"DISCIPLINE_PROFILE: {discipline_profile}\n"
        f"SOURCE: {source_text}"
    )
    return system, prompt


def defense_outline_prompt(dossier_json: list[dict[str, object]], duration_minutes: int) -> tuple[str, str]:
    system = (
        "You build a thesis defense speech outline. "
        "Use only the dossier claims. "
        "Do not invent new facts. "
        "Return valid JSON only."
    )
    prompt = (
        "Task: build a defense speech outline.\n"
        "Return JSON with key segments.\n"
        "Each segment must contain: title, talking_points, target_seconds.\n"
        f"DURATION_MINUTES: {duration_minutes}\n"
        f"DOSSIER: {json.dumps(dossier_json, ensure_ascii=False)}"
    )
    return system, prompt


def defense_storyboard_prompt(dossier_json: list[dict[str, object]], outline_segments: list[dict[str, object]]) -> tuple[str, str]:
    system = (
        "You build a slide storyboard for a thesis defense. "
        "Use only the provided dossier and outline. "
        "Return valid JSON only."
    )
    prompt = (
        "Task: create a slide storyboard.\n"
        "Return JSON with key slides.\n"
        "Each slide must contain: title, purpose, talking_points, evidence_links.\n"
        f"DOSSIER: {json.dumps(dossier_json, ensure_ascii=False)}\n"
        f"OUTLINE: {json.dumps(outline_segments, ensure_ascii=False)}"
    )
    return system, prompt


def defense_questions_prompt(
    dossier_json: list[dict[str, object]],
    risk_topics: list[str],
    persona: str,
    count: int,
) -> tuple[str, str]:
    system = (
        "You simulate a fair but demanding thesis defense role. "
        "Use only the dossier and risk topics. "
        "Return valid JSON only."
    )
    prompt = (
        "Task: generate defense follow-up questions.\n"
        "Return JSON with key questions.\n"
        "Each question must contain: topic, difficulty, question_text, risk_tag.\n"
        f"PERSONA: {persona}\n"
        f"QUESTION_COUNT: {count}\n"
        f"DOSSIER: {json.dumps(dossier_json, ensure_ascii=False)}\n"
        f"RISK_TOPICS: {json.dumps(risk_topics, ensure_ascii=False)}"
    )
    return system, prompt


def defense_answer_review_prompt(
    dossier_json: list[dict[str, object]],
    questions: list[str],
    answer_text: str,
    mode: str,
    persona: str,
    timer_profile_sec: int,
) -> tuple[str, str]:
    system = (
        "You review a student's thesis defense answer. "
        "Use only the dossier and the answer text. "
        "Do not invent missing facts. "
        "Return valid JSON only."
    )
    prompt = (
        "Task: score a thesis defense answer.\n"
        "Return JSON with keys scores, weak_points, summary, followups.\n"
        "scores must include: structure_mastery, relevance_clarity, methodology_mastery, novelty_mastery, results_mastery, limitations_honesty, oral_clarity_text_mode, followup_mastery.\n"
        f"MODE: {mode}\n"
        f"PERSONA: {persona}\n"
        f"TIMER_PROFILE_SEC: {timer_profile_sec}\n"
        f"DOSSIER: {json.dumps(dossier_json, ensure_ascii=False)}\n"
        f"QUESTIONS: {json.dumps(questions, ensure_ascii=False)}\n"
        f"ANSWER: {answer_text}"
    )
    return system, prompt


def defense_gap_enrichment_prompt(
    dossier_json: list[dict[str, object]],
    findings: list[dict[str, object]],
) -> tuple[str, str]:
    system = (
        "You improve a thesis defense gap report. "
        "Use only the provided dossier and gap list. "
        "Do not invent new facts. "
        "Return valid JSON only."
    )
    prompt = (
        "Task: refine gap findings for a thesis defense.\n"
        "Return JSON with key findings.\n"
        "Each finding must contain: finding_id, explanation, suggested_fix.\n"
        f"DOSSIER: {json.dumps(dossier_json, ensure_ascii=False)}\n"
        f"FINDINGS: {json.dumps(findings, ensure_ascii=False)}"
    )
    return system, prompt
