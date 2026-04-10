from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from application.answer_profile_registry import STATE_EXAM_PUBLIC_ADMIN_PROFILE
from domain.answer_profile import (
    AnswerBlockCode,
    AnswerCriterionCode,
    AttemptBlockScore,
    TicketAnswerBlock,
    TicketBlockMasteryProfile,
)
from domain.knowledge import TicketKnowledgeMap, WeakArea, WeakAreaKind


WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё0-9-]+")


FIELD_MAP = {
    AnswerBlockCode.INTRO: "intro_mastery",
    AnswerBlockCode.THEORY: "theory_mastery",
    AnswerBlockCode.PRACTICE: "practice_mastery",
    AnswerBlockCode.SKILLS: "skills_mastery",
    AnswerBlockCode.CONCLUSION: "conclusion_mastery",
    AnswerBlockCode.EXTRA: "extra_mastery",
}


@dataclass(slots=True)
class StateExamScoringOutcome:
    block_scores: dict[AnswerBlockCode, float]
    criterion_scores: dict[AnswerCriterionCode, float]
    attempt_block_scores: list[AttemptBlockScore]
    profile: TicketBlockMasteryProfile
    weak_areas: list[WeakArea]
    feedback_lines: list[str]


class StateExamScoringService:
    def evaluate(
        self,
        ticket: TicketKnowledgeMap,
        answer_text: str,
        user_id: str,
        profile: TicketBlockMasteryProfile | None = None,
        attempt_id: str = "",
    ) -> StateExamScoringOutcome:
        current_profile = profile or TicketBlockMasteryProfile(user_id=user_id, ticket_id=ticket.ticket_id)
        answer_tokens = self._normalize(answer_text)

        block_scores: dict[AnswerBlockCode, float] = {}
        attempt_block_scores: list[AttemptBlockScore] = []
        weak_areas: list[WeakArea] = []
        feedback_lines: list[str] = []

        for block in ticket.answer_blocks:
            score = self._score_block(block, answer_tokens, answer_text)
            block_scores[block.block_code] = score
            feedback = self._feedback_for_block(block, score)
            attempt_block_scores.append(
                AttemptBlockScore(
                    attempt_id=attempt_id,
                    block_code=block.block_code,
                    coverage_score=score,
                    criterion_scores={},
                    feedback=feedback,
                )
            )
            if score < 0.58:
                weak_areas.append(
                    WeakArea(
                        weak_area_id=f"weak-block-{ticket.ticket_id}-{block.block_code.value}",
                        user_id=user_id,
                        kind=WeakAreaKind.ANSWER_BLOCK,
                        reference_id=block.block_code.value,
                        title=block.title,
                        severity=round(1.0 - score, 4),
                        evidence=feedback,
                        related_ticket_ids=[ticket.ticket_id],
                    )
                )
                feedback_lines.append(f"Проседает блок «{block.title.lower()}».")

        criterion_scores = self._score_criteria(block_scores, answer_tokens)
        for item in attempt_block_scores:
            item.criterion_scores = criterion_scores.copy()

        for criterion, score in criterion_scores.items():
            if score < 0.6:
                weak_areas.append(
                    WeakArea(
                        weak_area_id=f"weak-criterion-{ticket.ticket_id}-{criterion.value}",
                        user_id=user_id,
                        kind=WeakAreaKind.RUBRIC_CRITERION,
                        reference_id=criterion.value,
                        title=self._criterion_title(criterion),
                        severity=round(1.0 - score, 4),
                        evidence=f"Критерий «{self._criterion_title(criterion).lower()}» закрыт слабо.",
                        related_ticket_ids=[ticket.ticket_id],
                    )
                )
                feedback_lines.append(f"Критерий «{self._criterion_title(criterion).lower()}» требует усиления.")

        updated_profile = self._update_profile(current_profile, block_scores)
        if not feedback_lines:
            feedback_lines.append("Структура госответа закрыта ровно, без явных провалов по блокам.")
        return StateExamScoringOutcome(
            block_scores=block_scores,
            criterion_scores=criterion_scores,
            attempt_block_scores=attempt_block_scores,
            profile=updated_profile,
            weak_areas=weak_areas,
            feedback_lines=feedback_lines,
        )

    @staticmethod
    def _normalize(text: str) -> set[str]:
        return {token.lower() for token in WORD_PATTERN.findall(text)}

    def _score_block(self, block: TicketAnswerBlock, answer_tokens: set[str], answer_text: str) -> float:
        expected_tokens = self._normalize(block.expected_content)
        excerpt_tokens = self._normalize(block.source_excerpt)
        target_tokens = list((expected_tokens | excerpt_tokens))
        if not target_tokens:
            return 0.0
        overlap = sum(1 for token in target_tokens if token in answer_tokens) / max(len(target_tokens), 1)
        if block.block_code == AnswerBlockCode.INTRO and any(token in answer_text.lower() for token in ("актуаль", "проблем", "цель")):
            overlap += 0.12
        if block.block_code == AnswerBlockCode.PRACTICE and any(token in answer_text.lower() for token in ("пример", "решени", "ситуац", "практик")):
            overlap += 0.12
        if block.block_code == AnswerBlockCode.SKILLS and any(token in answer_text.lower() for token in ("метод", "анализ", "инструмент", "аргумент")):
            overlap += 0.12
        if block.block_code == AnswerBlockCode.CONCLUSION and any(token in answer_text.lower() for token in ("итог", "вывод", "таким образом")):
            overlap += 0.12
        if block.is_missing:
            overlap = min(overlap, 0.45)
        return round(min(1.0, max(0.0, overlap)), 4)

    def _score_criteria(
        self,
        block_scores: dict[AnswerBlockCode, float],
        answer_tokens: set[str],
    ) -> dict[AnswerCriterionCode, float]:
        intro = block_scores.get(AnswerBlockCode.INTRO, 0.0)
        theory = block_scores.get(AnswerBlockCode.THEORY, 0.0)
        practice = block_scores.get(AnswerBlockCode.PRACTICE, 0.0)
        skills = block_scores.get(AnswerBlockCode.SKILLS, 0.0)
        conclusion = block_scores.get(AnswerBlockCode.CONCLUSION, 0.0)
        extra = block_scores.get(AnswerBlockCode.EXTRA, 0.0)
        avg = sum(block_scores.values()) / max(len(block_scores), 1)
        diversity_bonus = min(0.15, len(answer_tokens) / 220)

        return {
            AnswerCriterionCode.COMPLETENESS: round(avg, 4),
            AnswerCriterionCode.DEPTH: round(min(1.0, (theory * 0.45) + (practice * 0.3) + (skills * 0.25) + diversity_bonus), 4),
            AnswerCriterionCode.STRUCTURE: round(min(1.0, (intro * 0.2) + (theory * 0.25) + (practice * 0.2) + (conclusion * 0.2) + 0.15), 4),
            AnswerCriterionCode.PRACTICAL: round(min(1.0, (practice * 0.65) + (skills * 0.25) + (extra * 0.1)), 4),
            AnswerCriterionCode.ORIGINALITY: round(min(1.0, (practice * 0.35) + (conclusion * 0.25) + (extra * 0.2) + diversity_bonus), 4),
            AnswerCriterionCode.COMPETENCE: round(min(1.0, (skills * 0.5) + (practice * 0.25) + (theory * 0.25)), 4),
        }

    def _update_profile(
        self,
        profile: TicketBlockMasteryProfile,
        block_scores: dict[AnswerBlockCode, float],
    ) -> TicketBlockMasteryProfile:
        updated = TicketBlockMasteryProfile(
            user_id=profile.user_id,
            ticket_id=profile.ticket_id,
            intro_mastery=profile.intro_mastery,
            theory_mastery=profile.theory_mastery,
            practice_mastery=profile.practice_mastery,
            skills_mastery=profile.skills_mastery,
            conclusion_mastery=profile.conclusion_mastery,
            extra_mastery=profile.extra_mastery,
            overall_score=profile.overall_score,
            last_reviewed_at=datetime.now(),
            next_review_at=profile.next_review_at,
        )
        for block_code, value in block_scores.items():
            field_name = FIELD_MAP[block_code]
            previous = getattr(updated, field_name)
            setattr(updated, field_name, round((previous * 0.65) + (value * 0.35), 4))
        values = [
            updated.intro_mastery,
            updated.theory_mastery,
            updated.practice_mastery,
            updated.skills_mastery,
            updated.conclusion_mastery,
            updated.extra_mastery,
        ]
        updated.overall_score = round(sum(values) / len(values), 4)
        return updated

    @staticmethod
    def _feedback_for_block(block: TicketAnswerBlock, score: float) -> str:
        if block.is_missing:
            return f"Блок «{block.title}» в источнике выражен слабо. Его нужно подготовить отдельно."
        if score >= 0.75:
            return f"Блок «{block.title}» закрыт уверенно."
        if score >= 0.58:
            return f"Блок «{block.title}» раскрыт частично."
        return f"Блок «{block.title}» раскрыт слабо и требует доработки."

    @staticmethod
    def _criterion_title(code: AnswerCriterionCode) -> str:
        for criterion in STATE_EXAM_PUBLIC_ADMIN_PROFILE.criteria:
            if criterion.code is code:
                return criterion.title
        return code.value
