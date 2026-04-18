from __future__ import annotations

import json

from infrastructure.ollama.dialogue import DialogueTranscriptLine, DialogueTurnContext


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


def review_system_prompt() -> str:
    """Русский system-prompt для рецензии ответа студента.

    Маленькие локальные модели (4-7B) игнорируют директиву «будь строг», если
    она дана на английском; помимо этого они склонны ставить "covered" всем
    тезисам подряд (см. R0-отчёт в
    ``docs/superpowers/specs/2026-04-18-model-selection.md``).

    Поэтому:
    - промпт на русском,
    - рубрика содержит явные числовые пороги,
    - перед JSON модель пишет короткое рассуждение в
      ``<reasoning>…</reasoning>`` (single-pass chain-of-thought),
    - критерии "covered / partial / missing" описаны с привязкой к нормативной
      базе и примерам.
    """
    return (
        "Ты — строгий экзаменатор письменного госэкзамена ГМУ. Твоя задача — "
        "оценить ответ студента по заранее выделенным тезисам.\n"
        "\n"
        "Для каждого тезиса вынеси вердикт:\n"
        "- \"covered\"  — студент явно раскрыл тезис (есть конкретные формулировки "
        "и/или ссылки на нормы, уместные примеры).\n"
        "- \"partial\"  — студент упомянул тему тезиса, но без глубины: без "
        "определений, без нормативной базы или без примеров.\n"
        "- \"missing\"  — студент не упомянул тезис или затронул его поверхностно "
        "без содержательной информации.\n"
        "\n"
        "Числовая шкала overall_score:\n"
        "- 90-100  — все тезисы covered, есть нормативная база, нет фактических "
        "ошибок.\n"
        "- 70-89   — большинство covered, 1-2 partial, ошибок нет.\n"
        "- 50-69   — смешанный результат: половина partial/missing.\n"
        "- 30-49   — 2+ missing тезисов ИЛИ явные фактические ошибки.\n"
        "- 0-29    — ответ почти пустой или не по теме.\n"
        "\n"
        "Важно:\n"
        "- НЕ будь \"дружелюбным по умолчанию\". Если тезис реально не раскрыт — "
        "ставь missing, не partial.\n"
        "- Не придумывай факты: используй только то, что есть в REFERENCE THESES "
        "и STUDENT ANSWER.\n"
        "- Комментарии пиши на русском, 2-3 предложения, по делу.\n"
        "\n"
        "Перед JSON напиши короткое рассуждение в теге <reasoning>…</reasoning> "
        "(3-5 предложений: какие тезисы раскрыты, где пробелы, почему такая "
        "итоговая оценка).\n"
        "\n"
        "После </reasoning> верни ВАЛИДНЫЙ JSON с ключами:\n"
        "- thesis_verdicts: [{thesis_label, status, comment, student_excerpt}]\n"
        "- structure_notes: [строки]\n"
        "- strengths: [строки]\n"
        "- recommendations: [строки с конкретными советами]\n"
        "- overall_score: число 0-100\n"
        "- overall_comment: 1-2 предложения"
    )


# Few-shot: один сильный ответ (score ~90) и один слабый (score ~20).
# Оба приклеиваются к user prompt — модель видит паттерн «рассуждение →
# JSON», прежде чем получить реальный запрос. Примеры специально показывают:
# (а) что сильный ответ получает covered+уместные recommendations,
# (б) что слабый ответ получает missing, а не partial (ломаем дефолтную
#     "дружелюбность").
_REVIEW_FEWSHOT = """\
### Example 1 (отличный ответ, score 90)

TICKET: Бюджетное устройство Российской Федерации
REFERENCE THESES:
- Уровни бюджетной системы: федеральный, региональный, местный (классификация).
- Стадии бюджетного процесса: составление, рассмотрение, утверждение, исполнение, отчёт.
- Нормативная база: ст. 28 Бюджетного кодекса РФ — принципы бюджетной системы.
STUDENT ANSWER:
Бюджетная система РФ включает три уровня: федеральный, региональные бюджеты \
(субъектов) и местные. Бюджетный процесс проходит пять стадий — составление \
проекта, рассмотрение в парламенте, утверждение законом, исполнение \
(казначейское) и отчёт об исполнении. Согласно ст. 28 БК РФ принципы \
бюджетной системы включают единство, разграничение доходов и расходов, \
самостоятельность бюджетов. Пример: федеральный бюджет на очередной год \
рассматривается Государственной Думой в трёх чтениях.

<reasoning>
Студент раскрыл все три тезиса. Уровни перечислены полностью, стадии бюджетного \
процесса названы в правильном порядке, приведена нормативная база — ст. 28 БК РФ \
с перечнем принципов. Есть уместный пример с тремя чтениями бюджета. Ошибок нет, \
структура связная. Можно усилить: добавить по одному принципу пример их \
реализации.
</reasoning>
{"thesis_verdicts": [
  {"thesis_label": "Уровни бюджетной системы", "status": "covered", "comment": "Все три уровня перечислены верно.", "student_excerpt": "три уровня: федеральный, региональные бюджеты (субъектов) и местные"},
  {"thesis_label": "Стадии бюджетного процесса", "status": "covered", "comment": "Все пять стадий названы и в правильном порядке.", "student_excerpt": "составление проекта, рассмотрение в парламенте, утверждение законом, исполнение (казначейское) и отчёт"},
  {"thesis_label": "Нормативная база (ст. 28 БК РФ)", "status": "covered", "comment": "Указана статья и перечислены принципы.", "student_excerpt": "Согласно ст. 28 БК РФ принципы бюджетной системы включают единство, разграничение доходов и расходов, самостоятельность"}
],
"structure_notes": ["Ответ связный, переходов между блоками достаточно."],
"strengths": ["Полный перечень уровней", "Корректная ссылка на ст. 28 БК РФ", "Конкретный пример с тремя чтениями"],
"recommendations": ["Добавить по одному примеру практической реализации каждого принципа бюджетной системы."],
"overall_score": 90,
"overall_comment": "Сильный ответ: все тезисы раскрыты, есть нормативная база и пример."}

### Example 2 (слабый ответ, score 25)

TICKET: Бюджетное устройство Российской Федерации
REFERENCE THESES:
- Уровни бюджетной системы: федеральный, региональный, местный (классификация).
- Стадии бюджетного процесса: составление, рассмотрение, утверждение, исполнение, отчёт.
- Нормативная база: ст. 28 Бюджетного кодекса РФ — принципы бюджетной системы.
STUDENT ANSWER:
Бюджет — это план доходов и расходов государства. Он важен для экономики страны.

<reasoning>
Ответ состоит из двух предложений общего характера. Уровни бюджетной системы не \
перечислены, стадии бюджетного процесса не упомянуты, нормативная база \
отсутствует — ни статьи БК РФ, ни принципов. Фактических ошибок нет, но и \
содержательной информации по тезисам тоже нет. Это не partial, а missing: \
студент не зацепился ни за один из трёх тезисов.
</reasoning>
{"thesis_verdicts": [
  {"thesis_label": "Уровни бюджетной системы", "status": "missing", "comment": "Уровни не названы ни одним словом.", "student_excerpt": ""},
  {"thesis_label": "Стадии бюджетного процесса", "status": "missing", "comment": "Ни одной стадии не названо.", "student_excerpt": ""},
  {"thesis_label": "Нормативная база (ст. 28 БК РФ)", "status": "missing", "comment": "Нет ссылки на нормативный акт и принципы.", "student_excerpt": ""}
],
"structure_notes": ["Ответ слишком короткий, отсутствует структура (нет введения, раскрытия, вывода)."],
"strengths": [],
"recommendations": ["Перечислить три уровня бюджетной системы с конкретными примерами (РФ, субъект, муниципалитет).", "Назвать пять стадий бюджетного процесса по порядку.", "Сослаться на ст. 28 БК РФ и перечислить хотя бы 3 принципа."],
"overall_score": 25,
"overall_comment": "Ответ почти пустой: ни один тезис не раскрыт, нормативной базы нет."}
"""


def review_prompt(
    ticket_title: str,
    reference_theses: list[dict[str, str]],
    student_answer: str,
) -> tuple[str, str]:
    system = review_system_prompt()
    theses_text = "\n".join(
        f"- {thesis['label']}: {thesis['text']}" for thesis in reference_theses
    )
    prompt = (
        f"{_REVIEW_FEWSHOT}\n"
        "### Real task\n"
        "\n"
        f"TICKET: {ticket_title}\n"
        "REFERENCE THESES:\n"
        f"{theses_text}\n"
        "STUDENT ANSWER:\n"
        f"{student_answer}\n"
        "\n"
        "Сначала напиши <reasoning>…</reasoning>, затем один JSON-объект по "
        "схеме из примеров. Больше ничего."
    )
    return system, prompt


def dialogue_turn_prompt(context: DialogueTurnContext) -> tuple[str, str]:
    persona = _dialogue_persona_label(context.persona_kind)
    if persona == "Strict Examiner":
        system = (
            "You are a strict examiner in a session-aware oral dialogue. "
            "Use only the provided ticket materials and the current transcript. "
            "Do not introduce new facts, examples, terms, names, or conclusions that are not grounded in the ticket title, summary, atoms, answer blocks, examiner prompts, or answer-profile hints. "
            "Keep the next question short, direct, and grounded. "
            "Return valid JSON only with keys: feedback_text, next_question, weakness_focus, should_finish, finish_reason."
        )
    else:
        system = (
            "You are a Socratic tutor in a session-aware oral dialogue. "
            "Use only the provided ticket materials and the current transcript. "
            "Do not introduce new facts, examples, terms, names, or conclusions that are not grounded in the ticket title, summary, atoms, answer blocks, examiner prompts, or answer-profile hints. "
            "Keep the next question focused and constructive. "
            "Return valid JSON only with keys: feedback_text, next_question, weakness_focus, should_finish, finish_reason."
        )

    prompt = (
        f"SESSION_ID: {context.session_id}\n"
        f"TICKET_ID: {context.ticket_id}\n"
        f"TICKET_TITLE: {context.ticket_title}\n"
        f"TICKET_SUMMARY: {context.ticket_summary}\n"
        f"PERSONA: {persona}\n"
        f"TURN_INDEX: {context.turn_index}\n"
        f"TICKET_ATOMS: {json.dumps(context.ticket_atoms, ensure_ascii=False)}\n"
        f"ANSWER_BLOCKS: {json.dumps(context.ticket_answer_blocks, ensure_ascii=False)}\n"
        f"EXAMINER_PROMPTS: {json.dumps(context.examiner_prompts, ensure_ascii=False)}\n"
        f"ANSWER_PROFILE_HINTS: {json.dumps(context.answer_profile_hints, ensure_ascii=False)}\n"
        f"WEAK_POINTS: {json.dumps(context.weak_points, ensure_ascii=False)}\n"
        f"TRANSCRIPT: {json.dumps([_turn_line_to_dict(line) for line in context.transcript], ensure_ascii=False)}\n"
        "Rules:\n"
        "- Stay strictly within the provided ticket materials.\n"
        "- If the student's answer is weak, explain only the missing or weak ticket-grounded part.\n"
        "- Do not reference outside knowledge or invent new facts.\n"
        "- If the answer is sufficient to close the ticket, set should_finish to true and explain why.\n"
        "- If should_finish is false, next_question must be a single concise follow-up.\n"
        "- Return JSON only."
    )
    return system, prompt


def _dialogue_persona_label(persona_kind: str) -> str:
    normalized = persona_kind.strip().lower()
    if normalized in {"examiner", "strict_examiner", "strict-examiner"}:
        return "Strict Examiner"
    return "Socratic Tutor"


def _turn_line_to_dict(line: DialogueTranscriptLine) -> dict[str, str]:
    return {"speaker": line.speaker, "text": line.text}
