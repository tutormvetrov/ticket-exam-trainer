from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json

from domain.knowledge import AtomType, ExaminerPrompt, KnowledgeAtom
from infrastructure.ollama.client import OllamaClient
from infrastructure.ollama.prompts import (
    followup_questions_prompt,
    logical_gaps_prompt,
    oral_answer_prompt,
    outline_prompt,
    rewrite_question_prompt,
    structuring_system_prompt,
    structuring_user_prompt,
)


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


class OllamaService:
    def __init__(self, base_url: str, timeout_seconds: float = 2.5) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.client = OllamaClient(base_url, timeout_seconds)

    def inspect(self, preferred_model: str = "") -> OllamaDiagnostics:
        response = self.client.get_tags()
        checked_at = datetime.now()
        if not response.ok:
            return OllamaDiagnostics(
                endpoint_ok=False,
                model_ok=False,
                endpoint_message="Endpoint недоступен",
                model_message="Модель не проверена",
                checked_at=checked_at,
                latency_ms=response.latency_ms,
                error_text=response.error,
            )

        models = response.payload.get("models", [])
        names = [model.get("name", "") for model in models]
        selected = next((model for model in models if model.get("name") == preferred_model), None)
        fallback = models[0] if models else None
        resolved = selected or fallback

        if preferred_model:
            model_ok = preferred_model in names
            model_message = "Модель загружена" if model_ok else "Модель не найдена"
            model_name = preferred_model if model_ok else (resolved.get("name", "") if resolved else "")
        else:
            model_ok = bool(resolved)
            model_message = "Модель доступна" if model_ok else "Модель не найдена"
            model_name = resolved.get("name", "") if resolved else ""

        size_bytes = int(resolved.get("size", 0) or 0) if resolved else 0
        return OllamaDiagnostics(
            endpoint_ok=True,
            model_ok=model_ok,
            endpoint_message="Endpoint: OK",
            model_message=model_message,
            model_name=model_name,
            model_size_label=self._format_size(size_bytes),
            checked_at=checked_at,
            latency_ms=response.latency_ms,
            available_models=names,
            error_text="",
        )

    def list_models(self) -> list[str]:
        return self.inspect().available_models

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
        response = self.client.generate(model, prompt, system=system, format_name="json", temperature=0.3)
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
        response = self.client.generate(model, prompt, system=system, format_name="json", temperature=0.2)
        if not response.ok:
            return OllamaScenarioResult(False, "", False, response.latency_ms, response.error)
        try:
            parsed = self._parse_json_response(response.payload.get("response", ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return OllamaScenarioResult(False, "", False, response.latency_ms, str(exc))
        return OllamaScenarioResult(True, json.dumps(parsed, ensure_ascii=False), True, response.latency_ms)

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
        response = self.client.generate(
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

    def _generate_text(self, model: str, prompt: str, *, system: str = "") -> OllamaScenarioResult:
        response = self.client.generate(model, prompt, system=system, temperature=0.3)
        if not response.ok:
            return OllamaScenarioResult(False, "", False, response.latency_ms, response.error)
        return OllamaScenarioResult(
            ok=True,
            content=str(response.payload.get("response", "")).strip(),
            used_llm=True,
            latency_ms=response.latency_ms,
        )

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
