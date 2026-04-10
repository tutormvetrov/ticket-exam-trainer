from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from uuid import uuid4

from application.state_exam_scoring import StateExamScoringService
from domain.answer_profile import AnswerBlockCode, AnswerCriterionCode, AnswerProfileCode, AttemptBlockScore, TicketBlockMasteryProfile
from domain.knowledge import (
    AttemptRecord,
    ExerciseInstance,
    KnowledgeAtom,
    SkillCode,
    TicketKnowledgeMap,
    TicketMasteryProfile,
    WeakArea,
    WeakAreaKind,
)


WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё0-9-]+")


@dataclass(slots=True)
class ScoringOutcome:
    attempt: AttemptRecord
    profile: TicketMasteryProfile
    block_profile: TicketBlockMasteryProfile | None
    weak_areas: list[WeakArea]
    atom_scores: dict[str, float]
    skill_scores: dict[str, float]
    block_scores: dict[AnswerBlockCode, float]
    criterion_scores: dict[AnswerCriterionCode, float]
    attempt_block_scores: list[AttemptBlockScore]


class MicroSkillScoringService:
    FIELD_MAP = {
        SkillCode.REPRODUCE_DEFINITION: "definition_mastery",
        SkillCode.LIST_EXAMPLES: "examples_mastery",
        SkillCode.NAME_KEY_FEATURES: "feature_mastery",
        SkillCode.RECONSTRUCT_PROCESS_ORDER: "structure_mastery",
        SkillCode.EXPLAIN_CORE_LOGIC: "process_mastery",
        SkillCode.GIVE_SHORT_ORAL_ANSWER: "oral_short_mastery",
        SkillCode.GIVE_FULL_ORAL_ANSWER: "oral_full_mastery",
        SkillCode.ANSWER_FOLLOWUP_QUESTIONS: "followup_mastery",
    }

    def __init__(self) -> None:
        self.state_exam_scoring = StateExamScoringService()

    def evaluate(
        self,
        ticket: TicketKnowledgeMap,
        exercise: ExerciseInstance,
        user_answer: str,
        user_id: str = "local-user",
        profile: TicketMasteryProfile | None = None,
        block_profile: TicketBlockMasteryProfile | None = None,
    ) -> ScoringOutcome:
        current_profile = profile or TicketMasteryProfile(user_id=user_id, ticket_id=ticket.ticket_id)
        answer_tokens = self._normalize(user_answer)
        atom_scores = self._score_atoms(ticket.atoms, answer_tokens)
        skill_scores = self._score_skills(ticket, exercise, atom_scores, answer_tokens)
        weak_atom_ids = [atom_id for atom_id, score in atom_scores.items() if score < 0.55]
        weak_skill_codes = [code for code, score in skill_scores.items() if score < 0.6]

        updated_profile = self._update_profile(current_profile, skill_scores)
        weak_areas = self._build_weak_areas(ticket, weak_atom_ids, weak_skill_codes, atom_scores, skill_scores, user_id)
        block_scores: dict[AnswerBlockCode, float] = {}
        criterion_scores: dict[AnswerCriterionCode, float] = {}
        attempt_block_scores: list[AttemptBlockScore] = []
        updated_block_profile: TicketBlockMasteryProfile | None = None
        if ticket.answer_profile_code is AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN and ticket.answer_blocks:
            state_exam = self.state_exam_scoring.evaluate(
                ticket,
                user_answer,
                user_id=user_id,
                profile=block_profile,
                attempt_id=f"attempt-{uuid4().hex[:12]}",
            )
            block_scores = state_exam.block_scores
            criterion_scores = state_exam.criterion_scores
            attempt_block_scores = state_exam.attempt_block_scores
            updated_block_profile = state_exam.profile
            weak_areas.extend(state_exam.weak_areas)
            feedback = self._build_state_exam_feedback(ticket, atom_scores, skill_scores, state_exam.feedback_lines)
            parts = [
                sum(skill_scores.values()) / max(len(skill_scores), 1) if skill_scores else 0.0,
                sum(block_scores.values()) / max(len(block_scores), 1),
                sum(criterion_scores.values()) / max(len(criterion_scores), 1),
            ]
            average_score = sum(parts) / len(parts)
        else:
            average_score = sum(skill_scores.values()) / max(len(skill_scores), 1)
            feedback = self._build_feedback(ticket, atom_scores, skill_scores)
        attempt = AttemptRecord(
            attempt_id=attempt_block_scores[0].attempt_id if attempt_block_scores else f"attempt-{uuid4().hex[:12]}",
            exercise_id=exercise.exercise_id,
            ticket_id=ticket.ticket_id,
            user_answer=user_answer,
            score=round(average_score, 4),
            mastery_delta=round(average_score - current_profile.confidence_score, 4),
            weak_atom_ids=weak_atom_ids,
            weak_skill_codes=[SkillCode(code) for code in weak_skill_codes],
            feedback=feedback,
            used_llm=exercise.used_llm,
            created_at=datetime.now(),
        )
        if attempt_block_scores:
            for item in attempt_block_scores:
                item.attempt_id = attempt.attempt_id
        return ScoringOutcome(
            attempt,
            updated_profile,
            updated_block_profile,
            weak_areas,
            atom_scores,
            skill_scores,
            block_scores,
            criterion_scores,
            attempt_block_scores,
        )

    @staticmethod
    def _normalize(text: str) -> set[str]:
        return {token.lower() for token in WORD_PATTERN.findall(text)}

    def _score_atoms(self, atoms: list[KnowledgeAtom], answer_tokens: set[str]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for atom in atoms:
            keywords = [keyword.lower() for keyword in atom.keywords] or self._fallback_keywords(atom.text)
            matched = sum(1 for keyword in keywords if keyword.lower() in answer_tokens)
            score = matched / max(len(keywords), 1)
            if atom.type.value in {"definition", "process_step", "conclusion"}:
                score = min(1.0, score + 0.1 if matched else score)
            scores[atom.atom_id] = round(min(score, 1.0), 4)
        return scores

    def _score_skills(
        self,
        ticket: TicketKnowledgeMap,
        exercise: ExerciseInstance,
        atom_scores: dict[str, float],
        answer_tokens: set[str],
    ) -> dict[str, float]:
        skill_scores: dict[str, float] = {}
        relevant_codes = {code.value for code in exercise.target_skill_codes} or {skill.code.value for skill in ticket.skills}
        for skill in ticket.skills:
            if skill.code.value not in relevant_codes:
                continue
            base = sum(atom_scores.get(atom_id, 0.0) for atom_id in skill.target_atom_ids) / max(len(skill.target_atom_ids), 1)
            adjustment = self._skill_adjustment(skill.code, ticket, answer_tokens)
            skill_scores[skill.code.value] = round(min(1.0, max(0.0, base + adjustment)), 4)
        return skill_scores

    def _skill_adjustment(self, skill_code: SkillCode, ticket: TicketKnowledgeMap, answer_tokens: set[str]) -> float:
        if skill_code is SkillCode.GIVE_SHORT_ORAL_ANSWER:
            return 0.15 if 20 <= len(answer_tokens) <= 80 else -0.05
        if skill_code is SkillCode.GIVE_FULL_ORAL_ANSWER:
            return 0.2 if len(answer_tokens) >= 40 else -0.1
        if skill_code is SkillCode.ANSWER_FOLLOWUP_QUESTIONS:
            return 0.1 if len(answer_tokens) >= 25 else -0.1
        if skill_code is SkillCode.RECONSTRUCT_PROCESS_ORDER:
            process_atoms = [atom for atom in ticket.atoms if atom.atom_id in {skill_atom.atom_id for skill_atom in ticket.atoms}]
            positions = []
            for atom in process_atoms:
                if not atom.keywords:
                    continue
                keyword = atom.keywords[0].lower()
                if keyword in answer_tokens:
                    positions.append(keyword)
            return 0.1 if positions else 0.0
        return 0.0

    def _update_profile(self, profile: TicketMasteryProfile, skill_scores: dict[str, float]) -> TicketMasteryProfile:
        updated = TicketMasteryProfile(
            user_id=profile.user_id,
            ticket_id=profile.ticket_id,
            definition_mastery=profile.definition_mastery,
            structure_mastery=profile.structure_mastery,
            examples_mastery=profile.examples_mastery,
            feature_mastery=profile.feature_mastery,
            process_mastery=profile.process_mastery,
            oral_short_mastery=profile.oral_short_mastery,
            oral_full_mastery=profile.oral_full_mastery,
            followup_mastery=profile.followup_mastery,
            confidence_score=profile.confidence_score,
            last_reviewed_at=datetime.now(),
            next_review_at=profile.next_review_at,
        )

        for skill_code, score in skill_scores.items():
            field_name = self.FIELD_MAP[SkillCode(skill_code)]
            previous = getattr(updated, field_name)
            setattr(updated, field_name, round((previous * 0.65) + (score * 0.35), 4))

        mastery_values = [
            updated.definition_mastery,
            updated.structure_mastery,
            updated.examples_mastery,
            updated.feature_mastery,
            updated.process_mastery,
            updated.oral_short_mastery,
            updated.oral_full_mastery,
            updated.followup_mastery,
        ]
        updated.confidence_score = round(sum(mastery_values) / len(mastery_values), 4)
        return updated

    def _build_weak_areas(
        self,
        ticket: TicketKnowledgeMap,
        weak_atom_ids: list[str],
        weak_skill_codes: list[str],
        atom_scores: dict[str, float],
        skill_scores: dict[str, float],
        user_id: str,
    ) -> list[WeakArea]:
        weak_areas: list[WeakArea] = []
        atom_lookup = {atom.atom_id: atom for atom in ticket.atoms}
        for atom_id in weak_atom_ids:
            atom = atom_lookup[atom_id]
            weak_areas.append(
                WeakArea(
                    weak_area_id=f"weak-{uuid4().hex[:10]}",
                    user_id=user_id,
                    kind=WeakAreaKind.ATOM,
                    reference_id=atom_id,
                    title=atom.label,
                    severity=round(1.0 - atom_scores[atom_id], 4),
                    evidence=f"Low atom coverage for '{atom.label}'.",
                    related_ticket_ids=[ticket.ticket_id],
                )
            )

        for skill_code in weak_skill_codes:
            weak_areas.append(
                WeakArea(
                    weak_area_id=f"weak-{uuid4().hex[:10]}",
                    user_id=user_id,
                    kind=WeakAreaKind.SKILL,
                    reference_id=skill_code,
                    title=skill_code,
                    severity=round(1.0 - skill_scores[skill_code], 4),
                    evidence=f"Low mastery for skill '{skill_code}'.",
                    related_ticket_ids=[ticket.ticket_id],
                )
            )

        for link in ticket.cross_links_to_other_tickets:
            if weak_skill_codes:
                weak_areas.append(
                    WeakArea(
                        weak_area_id=f"weak-{uuid4().hex[:10]}",
                        user_id=user_id,
                        kind=WeakAreaKind.CROSS_TICKET_CONCEPT,
                        reference_id=link.concept_id,
                        title=link.concept_label,
                        severity=0.65,
                        evidence=f"Weak skills affect shared concept '{link.concept_label}'.",
                        related_ticket_ids=[ticket.ticket_id, *link.related_ticket_ids],
                    )
                )
        return weak_areas

    @staticmethod
    def _build_feedback(ticket: TicketKnowledgeMap, atom_scores: dict[str, float], skill_scores: dict[str, float]) -> str:
        weakest_atom = min(atom_scores, key=atom_scores.get) if atom_scores else ""
        weakest_skill = min(skill_scores, key=skill_scores.get) if skill_scores else ""
        atom_label = next((atom.label for atom in ticket.atoms if atom.atom_id == weakest_atom), weakest_atom)
        return (
            f"Слабый атом: {atom_label or 'не определён'}. "
            f"Слабый навык: {weakest_skill or 'не определён'}. "
            "Повторите структуру ответа и ключевые смысловые блоки."
        )

    @staticmethod
    def _build_state_exam_feedback(
        ticket: TicketKnowledgeMap,
        atom_scores: dict[str, float],
        skill_scores: dict[str, float],
        block_feedback: list[str],
    ) -> str:
        base = MicroSkillScoringService._build_feedback(ticket, atom_scores, skill_scores)
        lines = [base]
        if block_feedback:
            lines.append("Госэкзаменационная структура:")
            lines.extend(f"• {line}" for line in block_feedback[:4])
        return "\n".join(lines)

    @staticmethod
    def _fallback_keywords(text: str) -> list[str]:
        return [token.lower() for token in WORD_PATTERN.findall(text)[:5]]
