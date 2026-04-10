from __future__ import annotations

import json


def structuring_system_prompt() -> str:
    return (
        "You are a local exam training assistant. "
        "Use only the provided source text. "
        "Do not invent facts. "
        "If evidence is weak, lower confidence instead of adding content. "
        "Return valid JSON only."
    )


def structuring_user_prompt(title: str, source_text: str, existing_atoms: list[dict[str, object]]) -> str:
    return (
        "Task: restructure a single exam ticket into a compact knowledge map.\n"
        "Use only facts from SOURCE.\n"
        "Do not introduce any new concept that is absent from SOURCE.\n"
        "Return JSON with keys: summary, atoms, examiner_prompts, concepts, difficulty, estimated_oral_time_sec.\n"
        "Each atom must contain: type, label, text, keywords, confidence.\n"
        "Allowed atom types: definition, examples, features, stages, functions, causes, consequences, classification, process_step, conclusion.\n"
        "Concepts must be short noun phrases found in SOURCE.\n"
        f"TITLE: {title}\n"
        f"INITIAL_RULE_BASED_ATOMS: {json.dumps(existing_atoms, ensure_ascii=False)}\n"
        f"SOURCE: {source_text}"
    )


def rewrite_question_prompt(question: str, source_text: str) -> tuple[str, str]:
    system = (
        "You rewrite exam questions for clarity. "
        "Keep meaning unchanged. "
        "Use only the source context. "
        "Return one sentence."
    )
    prompt = f"QUESTION: {question}\nSOURCE: {source_text}\nRewrite the question more clearly in Russian."
    return system, prompt


def followup_questions_prompt(ticket_title: str, summary: str, weak_points: list[str], count: int) -> tuple[str, str]:
    system = (
        "You act as a strict but fair oral examiner. "
        "Ask concise follow-up questions based only on the source summary and weak points. "
        "Return JSON: {\"questions\": [..]}."
    )
    prompt = (
        f"TICKET: {ticket_title}\n"
        f"SUMMARY: {summary}\n"
        f"WEAK_POINTS: {json.dumps(weak_points, ensure_ascii=False)}\n"
        f"QUESTION_COUNT: {count}"
    )
    return system, prompt


def outline_prompt(answer_text: str, source_text: str) -> tuple[str, str]:
    system = (
        "You compress a full oral answer into a short outline. "
        "Use only the source text. "
        "Return plain text with 4-7 bullet points."
    )
    prompt = f"SOURCE: {source_text}\nANSWER: {answer_text}\nBuild a concise outline in Russian."
    return system, prompt


def oral_answer_prompt(outline_text: str, source_text: str, seconds: int) -> tuple[str, str]:
    system = (
        "You expand a study outline into a connected oral exam answer. "
        "Use only the source text. "
        "Do not add new facts. "
        "Return plain text."
    )
    prompt = (
        f"SOURCE: {source_text}\nOUTLINE: {outline_text}\n"
        f"Build a connected oral answer in Russian for about {seconds} seconds."
    )
    return system, prompt


def logical_gaps_prompt(question: str, user_answer: str, expected_summary: str) -> tuple[str, str]:
    system = (
        "You compare a student's answer with the expected summary. "
        "Use only the given materials. "
        "Return JSON: {\"gaps\": [..], \"strengths\": [..], \"confidence\": number}."
    )
    prompt = (
        f"QUESTION: {question}\n"
        f"EXPECTED: {expected_summary}\n"
        f"ANSWER: {user_answer}\n"
        "Identify missing logical links, omitted blocks and strong parts."
    )
    return system, prompt


def state_exam_blocks_system_prompt() -> str:
    return (
        "You structure a state exam answer into fixed blocks. "
        "Use only the provided source text. "
        "Do not invent facts. "
        "If a block is weak or absent, mark low confidence and keep text conservative. "
        "Return valid JSON only."
    )


def state_exam_blocks_user_prompt(
    ticket_title: str,
    source_text: str,
    existing_blocks: list[dict[str, object]],
) -> str:
    return (
        "Task: refine the answer structure for a Russian state exam ticket.\n"
        "Use only facts from SOURCE.\n"
        "Return JSON with key 'blocks'.\n"
        "Each block item must contain: block_code, title, expected_content, source_excerpt, confidence, is_missing.\n"
        "Allowed block_code values: intro, theory, practice, skills, conclusion, extra.\n"
        f"TICKET_TITLE: {ticket_title}\n"
        f"CURRENT_BLOCKS: {json.dumps(existing_blocks, ensure_ascii=False)}\n"
        f"SOURCE: {source_text}"
    )
