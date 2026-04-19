from __future__ import annotations

import re
from dataclasses import dataclass

from application.answer_profile_registry import get_answer_profile
from domain.answer_profile import AnswerBlockCode, AnswerProfileCode, TicketAnswerBlock
from domain.knowledge import AtomType, KnowledgeAtom
from infrastructure.ollama.service import OllamaService


@dataclass(slots=True)
class AnswerBlockBuildResult:
    blocks: list[TicketAnswerBlock]
    used_llm: bool
    warning: str = ""


class AnswerBlockBuilder:
    def build(
        self,
        *,
        ticket_title: str,
        source_text: str,
        atoms: list[KnowledgeAtom],
        profile_code: AnswerProfileCode | str,
        llm_service: OllamaService | None = None,
        llm_model: str = "",
        enable_llm: bool = False,
    ) -> AnswerBlockBuildResult:
        try:
            normalized_code = AnswerProfileCode(profile_code)
        except ValueError:
            normalized_code = AnswerProfileCode.STANDARD_TICKET
        if normalized_code is not AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN:
            return AnswerBlockBuildResult([], False, "")

        blocks = self._build_rule_based(source_text, atoms, normalized_code)
        used_llm = False
        warning = ""

        if enable_llm and llm_service is not None and self._needs_llm_refinement(blocks):
            llm_result = llm_service.refine_answer_blocks(
                ticket_title=ticket_title,
                source_text=source_text,
                existing_blocks=blocks,
                model=llm_model,
            )
            if llm_result.ok and llm_result.blocks:
                blocks = self._merge_blocks(blocks, llm_result.blocks)
                used_llm = llm_result.used_llm
            elif llm_result.error:
                warning = f"LLM block structuring fallback: {llm_result.error}"

        return AnswerBlockBuildResult(blocks, used_llm, warning)

    def _build_rule_based(
        self,
        source_text: str,
        atoms: list[KnowledgeAtom],
        profile_code: AnswerProfileCode,
    ) -> list[TicketAnswerBlock]:
        profile = get_answer_profile(profile_code)
        paragraphs = [part.strip() for part in re.split(r"\n{1,2}", source_text) if part.strip()]
        blocks: list[TicketAnswerBlock] = []
        used_paragraphs: set[int] = set()

        for spec in profile.blocks:
            candidates: list[str] = []
            excerpts: list[str] = []

            for index, paragraph in enumerate(paragraphs):
                lowered = paragraph.lower()
                if any(keyword in lowered for keyword in spec.keywords):
                    candidates.append(paragraph)
                    excerpts.append(paragraph[:220])
                    used_paragraphs.add(index)

            if spec.code is AnswerBlockCode.INTRO and not candidates:
                first = paragraphs[0] if paragraphs else ""
                if first:
                    candidates = [first]
                    excerpts = [first[:220]]

            if spec.code is AnswerBlockCode.THEORY and not candidates:
                theory_atoms = [
                    atom.text for atom in atoms
                    if atom.type in {AtomType.DEFINITION, AtomType.FEATURES, AtomType.CLASSIFICATION, AtomType.FUNCTIONS}
                ]
                candidates = theory_atoms[:2]
                excerpts = [item[:220] for item in candidates]

            if spec.code is AnswerBlockCode.PRACTICE and not candidates:
                practice_atoms = [
                    atom.text for atom in atoms
                    if atom.type in {AtomType.EXAMPLES, AtomType.PROCESS_STEP, AtomType.CONSEQUENCES}
                ]
                candidates = practice_atoms[:2]
                excerpts = [item[:220] for item in candidates]

            if spec.code is AnswerBlockCode.SKILLS and not candidates:
                skills_atoms = [
                    atom.text for atom in atoms
                    if any(token in " ".join(atom.keywords).lower() for token in ("анализ", "метод", "инструмент", "управлен"))
                ]
                candidates = skills_atoms[:2]
                excerpts = [item[:220] for item in candidates]

            if spec.code is AnswerBlockCode.CONCLUSION and not candidates:
                conclusion_atoms = [atom.text for atom in atoms if atom.type is AtomType.CONCLUSION]
                candidates = conclusion_atoms[:1]
                excerpts = [item[:220] for item in candidates]

            if spec.code is AnswerBlockCode.EXTRA and not candidates:
                extra_paragraphs = [
                    paragraph
                    for index, paragraph in enumerate(paragraphs)
                    if index not in used_paragraphs and len(paragraph.split()) > 6
                ]
                candidates = extra_paragraphs[:1]
                excerpts = [item[:220] for item in candidates]

            if candidates:
                expected = "\n".join(candidates[:2]).strip()
                confidence = min(0.95, 0.45 + len(candidates) * 0.2)
                blocks.append(
                    TicketAnswerBlock(
                        block_code=spec.code,
                        title=spec.title,
                        expected_content=expected,
                        source_excerpt="\n".join(excerpts[:2]),
                        confidence=round(confidence, 4),
                        llm_assisted=False,
                        is_missing=False,
                    )
                )
            else:
                blocks.append(
                    TicketAnswerBlock(
                        block_code=spec.code,
                        title=spec.title,
                        expected_content="В исходном материале этот блок выражен слабо. Подготовьте его перед устным ответом.",
                        source_excerpt="",
                        confidence=0.18,
                        llm_assisted=False,
                        is_missing=True,
                    )
                )
        return blocks

    @staticmethod
    def _needs_llm_refinement(blocks: list[TicketAnswerBlock]) -> bool:
        return any(block.is_missing or block.confidence < 0.55 for block in blocks)

    @staticmethod
    def _merge_blocks(
        base_blocks: list[TicketAnswerBlock],
        llm_blocks: list[TicketAnswerBlock],
    ) -> list[TicketAnswerBlock]:
        llm_map = {block.block_code: block for block in llm_blocks}
        merged: list[TicketAnswerBlock] = []
        for block in base_blocks:
            candidate = llm_map.get(block.block_code)
            if candidate is None:
                merged.append(block)
                continue
            if candidate.confidence > block.confidence or block.is_missing:
                merged.append(candidate)
            else:
                merged.append(block)
        return merged
