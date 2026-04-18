from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json

from domain.answer_profile import AnswerBlockCode, TicketAnswerBlock
from domain.knowledge import AtomType, ExaminerPrompt, KnowledgeAtom
from infrastructure.ollama.dialogue import DialogueTurnContext, DialogueTurnPayload, DialogueTurnResult
from infrastructure.ollama.client import OllamaClient, OllamaResponse
from infrastructure.ollama.prompts import (
    dialogue_turn_prompt,
    followup_questions_prompt,
    logical_gaps_prompt,
    oral_answer_prompt,
    outline_prompt,
    review_prompt,
    rewrite_question_prompt,
    state_exam_blocks_system_prompt,
    state_exam_blocks_user_prompt,
    structuring_system_prompt,
    structuring_user_prompt,
)
from infrastructure.ollama.runtime import OllamaRuntimeManager


_UNSET_TIMEOUT = object()


@dataclass(slots=True)
class OllamaDiagnostics:
    endpoint_ok: bool
    model_ok: bool
    endpoint_message: str
    model_message: str
    model_name: str = ""
    model_size_label: str = ""
    checked_at: datetime | None = None
    latency_ms: int | None = None
    available_models: list[str] = field(default_factory=list)
    error_text: str = ""
    resolved_models_path: str = ""

    @property
    def last_checked_label(self) -> str:
        if not self.checked_at:
            return "Проверка не выполнялась"
        return self.checked_at.strftime("%d.%m.%Y %H:%M")

    @property
    def latency_label(self) -> str:
        if self.latency_ms is None:
            return "Нет данных"
        seconds = self.latency_ms / 1000
        return f"{seconds:.1f} s"


@dataclass(slots=True)
class OllamaScenarioResult:
    ok: bool
    content: str
    used_llm: bool
    latency_ms: int | None
    error: str = ""


@dataclass(slots=True)
class LLMStructuringResult:
    ok: bool
    summary: str
    atoms: list[KnowledgeAtom]
    examiner_prompts: list[ExaminerPrompt]
    concepts: list[str]
    difficulty: int
    estimated_oral_time_sec: int
    latency_ms: int | None
    error: str = ""


@dataclass(slots=True)
class LLMAnswerBlocksResult:
    ok: bool
    blocks: list[TicketAnswerBlock]
    used_llm: bool
    latency_ms: int | None
    error: str = ""


class OllamaService:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float | None = None,
        models_path=None,
        *,
        inspect_timeout_seconds: float | None = None,
        generation_timeout_seconds: float | None | object = _UNSET_TIMEOUT,
    ) -> None:
        self.base_url = base_url
        # Резолвим наш локальный sentinel до передачи в клиент — у клиента
        # свой отдельный `_UNSET_TIMEOUT`, и, пройдя через него как "unknown
        # object", sentinel доходил до self.timeout_seconds и ломал min/max
        # в inspect() ("'>' not supported between instances of 'float' and 'object'").
        if generation_timeout_seconds is _UNSET_TIMEOUT:
            generation_timeout_seconds = timeout_seconds
        # `timeout_seconds` сохраняем как generation-фактический таймаут, чтобы
        # старый код (и логи) продолжали видеть осмысленное значение.
        self.client = OllamaClient(
            base_url,
            timeout_seconds,
            inspect_timeout_seconds=inspect_timeout_seconds,
            generation_timeout_seconds=generation_timeout_seconds,
        )
        self.timeout_seconds = self.client.generation_timeout_seconds
        self.inspect_timeout_seconds = self.client.inspect_timeout_seconds
        self.generation_timeout_seconds = self.client.generation_timeout_seconds
        self.runtime = OllamaRuntimeManager(base_url, models_path)

    def inspect(self, preferred_model: str = "") -> OllamaDiagnostics:
        timeout_for_runtime = self.timeout_seconds if self.timeout_seconds is not None else 25.0
        runtime_status = self.runtime.ensure_server_ready(wait_timeout_seconds=min(max(timeout_for_runtime, 6.0), 25.0))
        checked_at = datetime.now()
        if not runtime_status.endpoint_ready:
            return OllamaDiagnostics(
                endpoint_ok=False,
                model_ok=False,
                endpoint_message="Endpoint недоступен",
                model_message="Модель не проверена",
                checked_at=checked_at,
                error_text=runtime_status.error,
                resolved_models_path=runtime_status.models_path,
            )

        response = self.client.get_tags()
        if not response.ok:
            return OllamaDiagnostics(
                endpoint_ok=False,
                model_ok=False,
                endpoint_message="Endpoint недоступен",
                model_message="Модель не проверена",
                checked_at=checked_at,
                latency_ms=response.latency_ms,
                error_text=response.error,
                resolved_models_path=runtime_status.models_path,
            )

        models = response.payload.get("models", [])
        names = [model.get("name", "") for model in models]
        resolved, used_fallback = self._resolve_model_entry(models, preferred_model)

        if preferred_model:
            model_ok = bool(resolved)
            if resolved and not used_fallback:
                model_message = "Модель загружена"
            elif resolved:
                model_message = f"Используется fallback: {resolved.get('name', '')}"
            else:
                model_message = "Модель не найдена"
            model_name = resolved.get("name", "") if resolved else ""
        else:
            model_ok = bool(resolved)
            model_message = "Модель доступна" if model_ok else "Модель не найдена"
            model_name = resolved.get("name", "") if resolved else ""

        size_bytes = int(resolved.get("size", 0) or 0) if resolved else 0
        endpoint_message = "Endpoint: OK"
        if runtime_status.started_server:
            endpoint_message = "Endpoint: OK, Ollama запущен автоматически"
        return OllamaDiagnostics(
            endpoint_ok=True,
            model_ok=model_ok,
            endpoint_message=endpoint_message,
            model_message=model_message,
            model_name=model_name,
            model_size_label=self._format_size(size_bytes),
            checked_at=checked_at,
            latency_ms=response.latency_ms,
            available_models=names,
            error_text="",
            resolved_models_path=runtime_status.models_path,
        )

    def list_models(self) -> list[str]:
        return self.inspect().available_models

    def ensure_server_ready(self) -> OllamaDiagnostics:
        return self.inspect()

    def rewrite_question(self, question: str, source_text: str, model: str) -> OllamaScenarioResult:
        system, prompt = rewrite_question_prompt(question, source_text)
        return self._generate_text(model, prompt, system=system)

    def generate_followup_questions(
        self,
        ticket_title: str,
        summary: str,
        weak_points: list[str],
        model: str,
        count: int = 3,
    ) -> OllamaScenarioResult:
        system, prompt = followup_questions_prompt(ticket_title, summary, weak_points, count)
        response = self.request_generation(model, prompt, system=system, format_name="json", temperature=0.3)
        if not response.ok:
            return OllamaScenarioResult(False, "", False, response.latency_ms, response.error)
        try:
            payload = self._parse_json_response(response.payload.get("response", ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return OllamaScenarioResult(False, "", False, response.latency_ms, str(exc))
        questions = payload.get("questions", [])
        return OllamaScenarioResult(True, "\n".join(f"- {question}" for question in questions), True, response.latency_ms)

    def answer_to_outline(self, answer_text: str, source_text: str, model: str) -> OllamaScenarioResult:
        system, prompt = outline_prompt(answer_text, source_text)
        return self._generate_text(model, prompt, system=system)

    def outline_to_oral_answer(self, outline_text: str, source_text: str, model: str, seconds: int = 60) -> OllamaScenarioResult:
        system, prompt = oral_answer_prompt(outline_text, source_text, seconds)
        return self._generate_text(model, prompt, system=system)

    def analyze_logical_gaps(self, question: str, user_answer: str, expected_summary: str, model: str) -> OllamaScenarioResult:
        system, prompt = logical_gaps_prompt(question, user_answer, expected_summary)
        response = self.request_generation(model, prompt, system=system, format_name="json", temperature=0.2)
        if not response.ok:
            return OllamaScenarioResult(False, "", False, response.latency_ms, response.error)
        try:
            parsed = self._parse_json_response(response.payload.get("response", ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return OllamaScenarioResult(False, "", False, response.latency_ms, str(exc))
        return OllamaScenarioResult(True, json.dumps(parsed, ensure_ascii=False), True, response.latency_ms)

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

    def generate_dialogue_turn(self, context: DialogueTurnContext, model: str) -> DialogueTurnResult:
        system, prompt = dialogue_turn_prompt(context)
        response = self.request_generation(model, prompt, system=system, format_name="json", temperature=0.25)
        if not response.ok:
            return self._dialogue_turn_fallback(context, model, response.latency_ms, response.error)

        try:
            payload = self._parse_json_response(response.payload.get("response", ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return self._dialogue_turn_fallback(context, model, response.latency_ms, str(exc))

        parsed_payload = self._parse_dialogue_turn_payload(payload, context)
        if parsed_payload is None:
            return self._dialogue_turn_fallback(context, model, response.latency_ms, "LLM returned incomplete dialogue JSON")
        return DialogueTurnResult(True, parsed_payload, True, False, response.latency_ms)

    def refine_ticket_structure(
        self,
        title: str,
        source_text: str,
        existing_atoms: list[KnowledgeAtom],
        model: str,
        entity_prefix: str = "llm",
    ) -> LLMStructuringResult:
        existing = [
            {
                "type": atom.type.value,
                "label": atom.label,
                "text": atom.text,
                "keywords": atom.keywords,
                "confidence": atom.confidence,
            }
            for atom in existing_atoms
        ]
        response = self.request_generation(
            model,
            structuring_user_prompt(title, source_text, existing),
            system=structuring_system_prompt(),
            format_name="json",
            temperature=0.1,
        )
        if not response.ok:
            return LLMStructuringResult(False, "", [], [], [], 0, 0, response.latency_ms, response.error)

        try:
            payload = self._parse_json_response(response.payload.get("response", ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return LLMStructuringResult(False, "", [], [], [], 0, 0, response.latency_ms, str(exc))
        atoms = self._build_atoms_from_json(payload.get("atoms", []), entity_prefix)
        prompts = self._build_prompts_from_json(payload.get("examiner_prompts", []), title, atoms, entity_prefix)
        concepts = [concept for concept in payload.get("concepts", []) if isinstance(concept, str)]
        return LLMStructuringResult(
            ok=bool(atoms),
            summary=str(payload.get("summary", "")).strip(),
            atoms=atoms,
            examiner_prompts=prompts,
            concepts=concepts,
            difficulty=self._coerce_difficulty(payload.get("difficulty")),
            estimated_oral_time_sec=self._coerce_int(payload.get("estimated_oral_time_sec"), 90),
            latency_ms=response.latency_ms,
            error="" if atoms else "LLM returned no valid atoms",
        )

    def refine_answer_blocks(
        self,
        *,
        ticket_title: str,
        source_text: str,
        existing_blocks: list[TicketAnswerBlock],
        model: str,
    ) -> LLMAnswerBlocksResult:
        payload_blocks = [
            {
                "block_code": block.block_code.value,
                "title": block.title,
                "expected_content": block.expected_content,
                "source_excerpt": block.source_excerpt,
                "confidence": block.confidence,
                "is_missing": block.is_missing,
            }
            for block in existing_blocks
        ]
        response = self.request_generation(
            model,
            state_exam_blocks_user_prompt(ticket_title, source_text, payload_blocks),
            system=state_exam_blocks_system_prompt(),
            format_name="json",
            temperature=0.1,
        )
        if not response.ok:
            return LLMAnswerBlocksResult(False, [], False, response.latency_ms, response.error)
        try:
            payload = self._parse_json_response(response.payload.get("response", ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return LLMAnswerBlocksResult(False, [], False, response.latency_ms, str(exc))

        blocks: list[TicketAnswerBlock] = []
        for raw_block in payload.get("blocks", []):
            if not isinstance(raw_block, dict):
                continue
            try:
                block_code = AnswerBlockCode(str(raw_block.get("block_code", "")))
            except ValueError:
                continue
            text = str(raw_block.get("expected_content", "")).strip()
            excerpt = str(raw_block.get("source_excerpt", "")).strip()
            confidence = max(0.0, min(float(raw_block.get("confidence", 0.3) or 0.3), 1.0))
            blocks.append(
                TicketAnswerBlock(
                    block_code=block_code,
                    title=str(raw_block.get("title", block_code.value)).strip() or block_code.value,
                    expected_content=text or "В исходном материале этот блок выражен слабо.",
                    source_excerpt=excerpt[:220],
                    confidence=confidence,
                    llm_assisted=True,
                    is_missing=bool(raw_block.get("is_missing", False)),
                )
            )
        return LLMAnswerBlocksResult(bool(blocks), blocks, bool(blocks), response.latency_ms, "" if blocks else "LLM returned no valid answer blocks")

    def _generate_text(self, model: str, prompt: str, *, system: str = "") -> OllamaScenarioResult:
        response = self.request_generation(model, prompt, system=system, temperature=0.3)
        if not response.ok:
            return OllamaScenarioResult(False, "", False, response.latency_ms, response.error)
        return OllamaScenarioResult(
            ok=True,
            content=str(response.payload.get("response", "")).strip(),
            used_llm=True,
            latency_ms=response.latency_ms,
        )

    def _dialogue_turn_fallback(
        self,
        context: DialogueTurnContext,
        model: str,
        latency_ms: int | None,
        error_text: str,
    ) -> DialogueTurnResult:
        fallback_focus = self._dialogue_weakness_focus(context)
        weak_points = context.weak_points or [fallback_focus] if fallback_focus else context.weak_points
        fallback_result = self.generate_followup_questions(
            context.ticket_title,
            context.ticket_summary,
            weak_points,
            model,
            count=1,
        )
        next_question = self._extract_first_followup_question(fallback_result.content) if fallback_result.ok else ""
        if not next_question:
            next_question = self._build_local_dialogue_question(context, fallback_focus)
        feedback = self._build_local_dialogue_feedback(context, fallback_focus)
        payload = DialogueTurnPayload(
            feedback_text=feedback,
            next_question=next_question,
            weakness_focus=fallback_focus,
            should_finish=False,
            finish_reason="fallback_followup_generator" if fallback_result.ok and fallback_result.content else "fallback_local",
        )
        return DialogueTurnResult(
            ok=True,
            payload=payload,
            used_llm=False,
            used_fallback=True,
            latency_ms=fallback_result.latency_ms if fallback_result.latency_ms is not None else latency_ms,
            error=error_text,
        )

    @staticmethod
    def _parse_dialogue_turn_payload(payload: dict[str, object], context: DialogueTurnContext) -> DialogueTurnPayload | None:
        feedback_text = str(payload.get("feedback_text", "")).strip()
        next_question = str(payload.get("next_question", "")).strip()
        weakness_focus = str(payload.get("weakness_focus", "")).strip()
        should_finish = OllamaService._coerce_bool(payload.get("should_finish"))
        finish_reason = str(payload.get("finish_reason", "")).strip()

        if not feedback_text:
            return None
        if not next_question and not should_finish:
            return None
        if not weakness_focus:
            weakness_focus = OllamaService._dialogue_weakness_focus(context)
        if should_finish and not finish_reason:
            finish_reason = "LLM signaled completion"
        return DialogueTurnPayload(
            feedback_text=feedback_text,
            next_question=next_question,
            weakness_focus=weakness_focus,
            should_finish=should_finish,
            finish_reason=finish_reason,
        )

    def request_generation(
        self,
        model: str,
        prompt: str,
        *,
        system: str = "",
        format_name: str | None = None,
        temperature: float = 0.2,
    ) -> OllamaResponse:
        response = self.client.generate(model, prompt, system=system, format_name=format_name, temperature=temperature)
        if response.ok or not self._is_missing_model_error(response.error):
            return response
        fallback_model = self._resolve_installed_model_name(model)
        if not fallback_model or fallback_model == model:
            return response
        fallback_response = self.client.generate(
            fallback_model,
            prompt,
            system=system,
            format_name=format_name,
            temperature=temperature,
        )
        if fallback_response.ok:
            return fallback_response
        return fallback_response if fallback_response.error else response

    @staticmethod
    def _parse_json_response(raw_text: str) -> dict[str, object]:
        cleaned = raw_text.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                return json.loads(cleaned[start:end + 1])
            raise

    @staticmethod
    def _build_atoms_from_json(raw_atoms: list[object], entity_prefix: str) -> list[KnowledgeAtom]:
        atoms: list[KnowledgeAtom] = []
        previous_atom_id: str | None = None
        for index, raw_atom in enumerate(raw_atoms, start=1):
            if not isinstance(raw_atom, dict):
                continue
            atom_type_raw = str(raw_atom.get("type", "features"))
            try:
                atom_type = AtomType(atom_type_raw)
            except ValueError:
                atom_type = AtomType.FEATURES
            text = str(raw_atom.get("text", "")).strip()
            if not text:
                continue
            atom_id = f"{entity_prefix}-atom-{index:02d}"
            keywords = raw_atom.get("keywords", [])
            if not isinstance(keywords, list):
                keywords = []
            confidence = float(raw_atom.get("confidence", 0.7) or 0.7)
            atoms.append(
                KnowledgeAtom(
                    atom_id=atom_id,
                    type=atom_type,
                    label=str(raw_atom.get("label", atom_type.value)).strip() or atom_type.value,
                    text=text,
                    keywords=[str(item) for item in keywords][:6],
                    weight=1.0,
                    dependencies=[previous_atom_id] if previous_atom_id else [],
                    confidence=max(0.0, min(confidence, 1.0)),
                    source_excerpt=text[:220],
                )
            )
            previous_atom_id = atom_id
        return atoms

    @staticmethod
    def _build_prompts_from_json(raw_prompts: list[object], title: str, atoms: list[KnowledgeAtom], entity_prefix: str) -> list[ExaminerPrompt]:
        atom_ids = [atom.atom_id for atom in atoms]
        prompts: list[ExaminerPrompt] = []
        for index, raw_prompt in enumerate(raw_prompts, start=1):
            if not isinstance(raw_prompt, str) or not raw_prompt.strip():
                continue
            prompts.append(
                ExaminerPrompt(
                    prompt_id=f"{entity_prefix}-prompt-{index:02d}",
                    title=f"Уточняющий вопрос {index}",
                    text=raw_prompt.strip(),
                    target_skill_codes=[],
                    target_atom_ids=atom_ids[: min(2, len(atom_ids))],
                    llm_assisted=True,
                )
            )
        if prompts:
            return prompts
        return [
            ExaminerPrompt(
                prompt_id=f"{entity_prefix}-prompt-01",
                title="Уточнение",
                text=f"Уточните главный смысл билета '{title}'.",
                target_skill_codes=[],
                target_atom_ids=atom_ids[: min(2, len(atom_ids))],
                llm_assisted=True,
            )
        ]

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes <= 0:
            return ""
        gb = size_bytes / (1024 ** 3)
        return f"{gb:.1f} GB"

    @staticmethod
    def _coerce_int(value: object, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _coerce_difficulty(value: object) -> int:
        if isinstance(value, int):
            return max(1, min(value, 5))
        if isinstance(value, str):
            normalized = value.strip().lower()
            mapping = {
                "beginner": 1,
                "easy": 2,
                "intermediate": 3,
                "medium": 3,
                "advanced": 4,
                "hard": 5,
            }
            if normalized in mapping:
                return mapping[normalized]
            try:
                return max(1, min(int(normalized), 5))
            except ValueError:
                return 3
        return 3

    @staticmethod
    def _is_missing_model_error(error_text: str) -> bool:
        lower = error_text.lower()
        return "model" in lower and "not found" in lower

    @staticmethod
    def _coerce_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized in {"1", "true", "yes", "y", "on"}
        return False

    @staticmethod
    def _dialogue_weakness_focus(context: DialogueTurnContext) -> str:
        if context.weak_points:
            return context.weak_points[0].strip()
        if context.answer_profile_hints:
            return context.answer_profile_hints[0].strip()
        if context.examiner_prompts:
            return context.examiner_prompts[0].strip()
        return context.ticket_title.strip()

    @staticmethod
    def _build_local_dialogue_feedback(context: DialogueTurnContext, weakness_focus: str) -> str:
        if weakness_focus:
            return (
                f"Сфокусируйтесь на блоке: {weakness_focus}. "
                "Ответ держите строго в пределах материала билета."
            )
        return (
            f"Сфокусируйтесь на ключевых блоках билета '{context.ticket_title}'. "
            "Ответ держите строго в пределах материала билета."
        )

    @staticmethod
    def _build_local_dialogue_question(context: DialogueTurnContext, weakness_focus: str) -> str:
        if weakness_focus:
            return f"Уточните, как в билете '{context.ticket_title}' раскрывается {weakness_focus}."
        return f"Назовите ключевые блоки билета '{context.ticket_title}' по исходному материалу."

    @staticmethod
    def _extract_first_followup_question(content: str) -> str:
        for line in content.splitlines():
            cleaned = line.strip().lstrip("-•").strip()
            if cleaned:
                return cleaned
        return ""

    def _resolve_installed_model_name(self, preferred_model: str) -> str:
        response = self.client.get_tags()
        if not response.ok:
            return preferred_model
        models = response.payload.get("models", [])
        resolved, _ = self._resolve_model_entry(models, preferred_model)
        return resolved.get("name", preferred_model) if resolved else preferred_model

    @staticmethod
    def _resolve_model_entry(models: list[object], preferred_model: str) -> tuple[dict[str, object] | None, bool]:
        normalized = [model for model in models if isinstance(model, dict) and model.get("name")]
        if not normalized:
            return None, False
        if preferred_model:
            selected = next((model for model in normalized if model.get("name") == preferred_model), None)
            if selected is not None:
                return selected, False

        fallback = OllamaService._pick_family_fallback(normalized, preferred_model)
        if fallback is not None:
            return fallback, bool(preferred_model and fallback.get("name") != preferred_model)
        return None, False

    @staticmethod
    def _pick_family_fallback(models: list[dict[str, object]], preferred_model: str) -> dict[str, object] | None:
        if not preferred_model:
            return models[0] if models else None
        family = preferred_model.split(":", 1)[0].strip().lower()
        family_matches = [
            model for model in models
            if family and family in str(model.get("name", "")).lower()
        ]
        if family_matches:
            return family_matches[0]
        return None
