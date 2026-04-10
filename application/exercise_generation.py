from __future__ import annotations

from random import Random
from uuid import uuid4

from domain.answer_profile import AnswerProfileCode
from domain.knowledge import ExerciseInstance, ExerciseType, TicketKnowledgeMap


class ExerciseGenerator:
    def __init__(self, seed: int = 17) -> None:
        self.random = Random(seed)

    def generate(self, ticket: TicketKnowledgeMap) -> list[ExerciseInstance]:
        instances: list[ExerciseInstance] = []
        for template in ticket.exercise_templates:
            prompt_text, expected_answer = self._render_prompt(ticket, template.exercise_type, template.target_atom_ids)
            instances.append(
                ExerciseInstance(
                    exercise_id=f"exercise-{uuid4().hex[:12]}",
                    ticket_id=ticket.ticket_id,
                    template_id=template.template_id,
                    exercise_type=template.exercise_type,
                    prompt_text=prompt_text,
                    expected_answer=expected_answer,
                    target_atom_ids=template.target_atom_ids,
                    target_skill_codes=template.target_skill_codes,
                    used_llm=False,
                )
            )
        return instances

    def _render_prompt(self, ticket: TicketKnowledgeMap, exercise_type: ExerciseType, atom_ids: list[str]) -> tuple[str, str]:
        if ticket.answer_profile_code is AnswerProfileCode.STATE_EXAM_PUBLIC_ADMIN and ticket.answer_blocks:
            return self._render_state_exam_prompt(ticket, exercise_type)

        atoms = [atom for atom in ticket.atoms if atom.atom_id in atom_ids]
        labels = ", ".join(atom.label.lower() for atom in atoms)
        facts = [atom.text for atom in atoms]
        if exercise_type is ExerciseType.ANSWER_SKELETON:
            prompt = f"Заполните каркас ответа по билету '{ticket.title}': {labels}."
            answer = "\n".join(facts)
            return prompt, answer

        if exercise_type is ExerciseType.STRUCTURE_RECONSTRUCTION:
            shuffled = facts[:]
            self.random.shuffle(shuffled)
            prompt = "Восстановите правильный логический порядок тезисов:\n" + "\n".join(f"- {item}" for item in shuffled)
            answer = "\n".join(facts)
            return prompt, answer

        if exercise_type is ExerciseType.SEMANTIC_CLOZE:
            masked = []
            for atom in atoms:
                words = atom.text.split()
                if len(words) > 4:
                    words[min(2, len(words) - 1)] = "____"
                masked.append(" ".join(words))
            prompt = "Восстановите пропущенные смысловые узлы:\n" + "\n".join(masked)
            answer = "\n".join(facts)
            return prompt, answer

        if exercise_type is ExerciseType.EXAMINER_FOLLOWUP:
            prompt = (
                f"Ответьте на уточняющие вопросы экзаменатора по билету '{ticket.title}'. "
                f"Зоны проверки: {labels}."
            )
            answer = "\n".join(facts)
            return prompt, answer

        if exercise_type is ExerciseType.CROSS_TICKET_REPEAT:
            prompt = (
                f"Свяжите билет '{ticket.title}' с родственными концептами и покажите, "
                f"как повторяются идеи: {', '.join(ticket.concept_ids)}."
            )
            answer = "\n".join(facts)
            return prompt, answer

        prompt = f"Вспомните и объясните: {labels}."
        answer = "\n".join(facts)
        return prompt, answer

    def _render_state_exam_prompt(self, ticket: TicketKnowledgeMap, exercise_type: ExerciseType) -> tuple[str, str]:
        blocks = ticket.answer_blocks
        ordered_titles = ", ".join(block.title.lower() for block in blocks)
        answer = "\n".join(f"{block.title}: {block.expected_content}" for block in blocks)

        if exercise_type is ExerciseType.ANSWER_SKELETON:
            return (
                f"Соберите полный ответ по билету '{ticket.title}' по структуре госэкзамена: {ordered_titles}.",
                answer,
            )
        if exercise_type is ExerciseType.STRUCTURE_RECONSTRUCTION:
            shuffled = [block.title for block in blocks]
            self.random.shuffle(shuffled)
            return (
                "Восстановите порядок блоков ответа по рубрике госэкзамена:\n" + "\n".join(f"- {item}" for item in shuffled),
                "\n".join(block.title for block in blocks),
            )
        if exercise_type is ExerciseType.SEMANTIC_CLOZE:
            masked = []
            for block in blocks[:3]:
                words = block.expected_content.split()
                if len(words) > 4:
                    words[min(2, len(words) - 1)] = "____"
                masked.append(f"{block.title}: " + " ".join(words))
            return ("Заполните пропуски в структуре госответа:\n" + "\n".join(masked), answer)
        if exercise_type in {ExerciseType.ORAL_SHORT, ExerciseType.ORAL_FULL, ExerciseType.EXAMINER_FOLLOWUP}:
            return (
                f"Ответьте по билету '{ticket.title}' так, чтобы закрыть блоки: {ordered_titles}.",
                answer,
            )
        return (f"Вспомните и раскройте блоки госответа: {ordered_titles}.", answer)
