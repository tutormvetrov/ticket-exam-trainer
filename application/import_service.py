from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Callable
from uuid import uuid4

from application.answer_block_builder import AnswerBlockBuilder
from application.exercise_generation import ExerciseGenerator
from domain.answer_profile import AnswerProfileCode
from domain.knowledge import (
    AtomType,
    CrossTicketLink,
    ExerciseTemplate,
    ExerciseType,
    ExaminerPrompt,
    KnowledgeAtom,
    ScoringCriterion,
    SkillCode,
    SourceDocument,
    TicketKnowledgeMap,
    TicketSkill,
)
from infrastructure.importers import ImportedDocumentText, import_docx, import_pdf
from infrastructure.ollama.service import OllamaService


STOP_WORDS = {
    "и", "в", "во", "на", "по", "к", "из", "от", "до", "для", "что", "это", "как",
    "при", "под", "над", "с", "со", "не", "или", "а", "но", "об", "о", "у", "же",
}

SECTION_PATTERN = re.compile(r"^(?:раздел|section)\s*(\d+)?[\.\): -]*(.+)$", re.IGNORECASE)
TICKET_PATTERN = re.compile(r"^(?:[^\W\d_]+\s*)?(\d+)[\.\): -]*(.+)$", re.UNICODE)
NUMBERED_PATTERN = re.compile(r"^(\d{1,3})[\.\)]\s+(.+)$")
ImportProgressCallback = Callable[[int, str, str], None]


@dataclass(slots=True)
class ContentChunk:
    chunk_id: str
    index: int
    text: str
    normalized_text: str
    confidence: float
    section_guess: str = ""
    ticket_guess: str = ""


@dataclass(slots=True)
class TicketCandidate:
    index: int
    title: str
    body: str
    confidence: float
    section_title: str


@dataclass(slots=True)
class ImportQueueItem:
    ticket_id: str
    ticket_index: int
    section_id: str
    title: str
    body_text: str
    candidate_confidence: float
    llm_status: str = "pending"
    llm_error: str = ""
    llm_attempted: bool = False
    used_llm: bool = False


@dataclass(slots=True)
class PreparedImportBundle:
    source_document: SourceDocument
    normalized_text: str
    chunks: list[ContentChunk]
    candidates: list[TicketCandidate]
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StructuredImportResult:
    source_document: SourceDocument
    normalized_text: str
    chunks: list[ContentChunk]
    tickets: list[TicketKnowledgeMap]
    exercise_instances: dict[str, list] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    used_llm_assist: bool = False


class DocumentImportService:
    def __init__(
        self,
        ollama_service: OllamaService | None = None,
        llm_model: str = "mistral:instruct",
        enable_llm_structuring: bool = False,
    ) -> None:
        self.exercise_generator = ExerciseGenerator()
        self.answer_block_builder = AnswerBlockBuilder()
        self.ollama_service = ollama_service
        self.llm_model = llm_model
        self.enable_llm_structuring = enable_llm_structuring

    def import_document(
        self,
        path: str | Path,
        exam_id: str,
        subject_id: str,
        default_section_id: str,
        answer_profile_code: AnswerProfileCode | str = AnswerProfileCode.STANDARD_TICKET,
        progress_callback: ImportProgressCallback | None = None,
    ) -> StructuredImportResult:
        prepared = self.prepare_import(
            path,
            exam_id,
            subject_id,
            default_section_id,
            answer_profile_code=answer_profile_code,
            progress_callback=progress_callback,
        )

        tickets = []
        used_llm_assist = False
        total_candidates = max(1, len(prepared.candidates))
        build_start = 34
        build_end = 78
        for index, candidate in enumerate(prepared.candidates, start=1):
            detail = f"Билет {index} из {total_candidates}: {candidate.title[:72]}"
            self._report_progress(progress_callback, self._loop_progress(build_start, build_end, index - 1, total_candidates), "Построение карты билета", detail)
            section_id = self.resolve_section_id(candidate, default_section_id)
            ticket, used_llm, llm_warning = self.build_ticket_map(
                candidate,
                exam_id,
                section_id,
                prepared.source_document.document_id,
                answer_profile_code=prepared.source_document.answer_profile_code,
            )
            used_llm_assist = used_llm_assist or used_llm
            if llm_warning:
                prepared.warnings.append(llm_warning)
            tickets.append(ticket)
            self._report_progress(progress_callback, self._loop_progress(build_start, build_end, index, total_candidates), "Построение карты билета", detail)

        self._report_progress(progress_callback, 82, "Связи между билетами", "Строим cross-ticket concepts и перекрёстные ссылки")
        self.attach_cross_ticket_links(tickets)
        exercise_instances = {}
        exercise_start = 84
        exercise_end = 94
        total_tickets = max(1, len(tickets))
        for index, ticket in enumerate(tickets, start=1):
            detail = f"Генерируем упражнения для билета {index} из {total_tickets}"
            self._report_progress(progress_callback, self._loop_progress(exercise_start, exercise_end, index - 1, total_tickets), "Генерация упражнений", detail)
            exercise_instances[ticket.ticket_id] = self.exercise_generator.generate(ticket)
            self._report_progress(progress_callback, self._loop_progress(exercise_start, exercise_end, index, total_tickets), "Генерация упражнений", detail)
        return StructuredImportResult(
            source_document=prepared.source_document,
            normalized_text=prepared.normalized_text,
            chunks=prepared.chunks,
            tickets=tickets,
            exercise_instances=exercise_instances,
            warnings=prepared.warnings,
            used_llm_assist=used_llm_assist,
        )

    def prepare_import(
        self,
        path: str | Path,
        exam_id: str,
        subject_id: str,
        default_section_id: str,
        answer_profile_code: AnswerProfileCode | str = AnswerProfileCode.STANDARD_TICKET,
        progress_callback: ImportProgressCallback | None = None,
    ) -> PreparedImportBundle:
        self._report_progress(progress_callback, 3, "Чтение документа", "Извлекаем текст из исходного файла")
        imported = self._read_document(path)
        self._report_progress(progress_callback, 10, "Нормализация текста", "Приводим текст к рабочему формату")
        normalized = self.normalize_text(imported.raw_text)
        self._report_progress(progress_callback, 18, "Разбиение на фрагменты", "Готовим текст к поиску билетов")
        chunks = self.chunk_text(normalized)
        self._report_progress(progress_callback, 26, "Поиск билетов", "Пытаемся выделить разделы и кандидаты в билеты")
        candidates = self.extract_ticket_candidates(normalized)
        warnings: list[str] = []
        if not candidates:
            warnings.append("Структура билетов распознана с низкой уверенностью. Использован fallback на единый chunk.")
            title = self.infer_title(normalized, imported.title)
            candidates = [TicketCandidate(1, title, normalized, 0.42, default_section_id)]
            self._report_progress(progress_callback, 30, "Fallback-структурирование", "Явная структура не найдена, импорт продолжается через единый блок текста")

        source_document = SourceDocument(
            document_id=self._slug(f"doc-{imported.title}-{uuid4().hex[:8]}"),
            exam_id=exam_id,
            subject_id=subject_id,
            title=imported.title,
            file_path=str(imported.path),
            file_type=imported.file_type,
            size_bytes=imported.path.stat().st_size,
            imported_at=datetime.now(),
            checksum="",
            answer_profile_code=self._normalize_answer_profile_code(answer_profile_code),
        )
        return PreparedImportBundle(
            source_document=source_document,
            normalized_text=normalized,
            chunks=chunks,
            candidates=candidates,
            warnings=warnings,
        )

    def create_import_queue_items(
        self,
        candidates: list[TicketCandidate],
        source_document_id: str,
        default_section_id: str,
    ) -> list[ImportQueueItem]:
        queue_items: list[ImportQueueItem] = []
        for candidate in candidates:
            section_id = self.resolve_section_id(candidate, default_section_id)
            queue_items.append(
                ImportQueueItem(
                    ticket_id=self.make_ticket_id(candidate, source_document_id),
                    ticket_index=candidate.index,
                    section_id=section_id,
                    title=candidate.title,
                    body_text=candidate.body,
                    candidate_confidence=candidate.confidence,
                )
            )
        return queue_items

    def generate_exercise_instances(self, ticket: TicketKnowledgeMap) -> list:
        return self.exercise_generator.generate(ticket)

    def rebuild_ticket_map(
        self,
        ticket: TicketKnowledgeMap,
        source_text: str,
        *,
        force_llm: bool = True,
    ) -> tuple[TicketKnowledgeMap, bool, str]:
        candidate = TicketCandidate(
            index=1,
            title=ticket.title,
            body=source_text,
            confidence=ticket.source_confidence or 0.5,
            section_title=ticket.section_id,
        )
        original_flag = self.enable_llm_structuring
        try:
            if force_llm:
                self.enable_llm_structuring = True
            return self.build_ticket_map(
                candidate,
                ticket.exam_id,
                ticket.section_id,
                ticket.source_document_id,
                ticket_id=ticket.ticket_id,
                answer_profile_code=ticket.answer_profile_code,
            )
        finally:
            self.enable_llm_structuring = original_flag

    def _read_document(self, path: str | Path) -> ImportedDocumentText:
        document_path = Path(path)
        suffix = document_path.suffix.lower()
        if suffix == ".docx":
            return import_docx(str(document_path))
        if suffix == ".pdf":
            return import_pdf(str(document_path))
        raise ValueError(f"Unsupported document format: {document_path.suffix}")

    @staticmethod
    def normalize_text(raw_text: str) -> str:
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" ?([:;,.!?])", r"\1", text)
        return text.strip()

    def chunk_text(self, normalized_text: str, max_paragraphs: int = 4) -> list[ContentChunk]:
        paragraphs = [part.strip() for part in re.split(r"\n{2,}", normalized_text) if part.strip()]
        chunks: list[ContentChunk] = []
        for index in range(0, len(paragraphs), max_paragraphs):
            block = paragraphs[index:index + max_paragraphs]
            chunk_text = "\n\n".join(block)
            chunks.append(
                ContentChunk(
                    chunk_id=f"chunk-{uuid4().hex[:10]}",
                    index=len(chunks),
                    text=chunk_text,
                    normalized_text=chunk_text,
                    confidence=0.7 if len(block) > 1 else 0.5,
                )
            )
        return chunks

    def extract_ticket_candidates(self, normalized_text: str) -> list[TicketCandidate]:
        lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
        current_section = "default-section"
        current_title = ""
        current_body: list[str] = []
        current_confidence = 0.0
        candidates: list[TicketCandidate] = []

        def flush() -> None:
            if not current_title:
                return
            body = "\n".join(current_body).strip()
            if body:
                candidates.append(
                    TicketCandidate(
                        index=len(candidates) + 1,
                        title=current_title,
                        body=body,
                        confidence=current_confidence,
                        section_title=current_section,
                    )
                )

        for line in lines:
            section_match = SECTION_PATTERN.match(line)
            if section_match and len(line.split()) <= 10 and "?" not in line:
                current_section = section_match.group(2).strip() or current_section
                continue

            title_match = TICKET_PATTERN.match(line)
            if title_match and "?" in line:
                flush()
                raw_title = title_match.group(2).strip() or f"Билет {title_match.group(1)}"
                current_title, inline_body = self.split_inline_title_and_body(raw_title)
                current_body = [inline_body] if inline_body else []
                current_confidence = 0.95
                continue

            numbered_match = NUMBERED_PATTERN.match(line)
            if numbered_match and len(line) < 220 and "?" in line:
                flush()
                raw_title = numbered_match.group(2).strip()
                current_title, inline_body = self.split_inline_title_and_body(raw_title)
                current_body = [inline_body] if inline_body else []
                current_confidence = 0.82
                continue

            if current_title:
                current_body.append(line)

        flush()
        return candidates

    @staticmethod
    def split_inline_title_and_body(raw_title: str) -> tuple[str, str]:
        if "?" in raw_title:
            title, remainder = raw_title.split("?", 1)
            return title.strip() + "?", remainder.strip()
        if ". " in raw_title:
            title, remainder = raw_title.split(". ", 1)
            if len(title.split()) >= 4:
                return title.strip(), remainder.strip()
        return raw_title.strip(), ""

    def build_ticket_map(
        self,
        candidate: TicketCandidate,
        exam_id: str,
        section_id: str,
        source_document_id: str,
        ticket_id: str | None = None,
        answer_profile_code: AnswerProfileCode | str = AnswerProfileCode.STANDARD_TICKET,
    ) -> tuple[TicketKnowledgeMap, bool, str]:
        ticket_key = ticket_id or self.make_ticket_id(candidate, source_document_id)
        normalized_profile = self._normalize_answer_profile_code(answer_profile_code)
        atoms = self.extract_atoms(candidate.body, ticket_key)
        summary = self.build_summary(atoms)
        examiner_prompts = self.build_examiner_prompts(candidate.title, atoms)
        difficulty = self.estimate_difficulty(atoms)
        estimated_oral_time_sec = max(45, min(180, len(atoms) * 18))
        used_llm = False
        warning = ""

        if self.enable_llm_structuring and self.ollama_service and self.should_use_llm_for_structuring(candidate, atoms):
            llm_result = self.ollama_service.refine_ticket_structure(
                candidate.title,
                candidate.body,
                atoms,
                self.llm_model,
                entity_prefix=ticket_key,
            )
            if llm_result.ok and llm_result.atoms:
                atoms = llm_result.atoms
                summary = llm_result.summary or summary
                examiner_prompts = llm_result.examiner_prompts or examiner_prompts
                difficulty = llm_result.difficulty or difficulty
                estimated_oral_time_sec = llm_result.estimated_oral_time_sec or estimated_oral_time_sec
                used_llm = True
            elif llm_result.error:
                warning = f"LLM structuring fallback: {llm_result.error}"

        answer_block_result = self.answer_block_builder.build(
            ticket_title=candidate.title,
            source_text=candidate.body,
            atoms=atoms,
            profile_code=normalized_profile,
            llm_service=self.ollama_service,
            llm_model=self.llm_model,
            enable_llm=self.enable_llm_structuring,
        )
        used_llm = used_llm or answer_block_result.used_llm
        if answer_block_result.warning:
            warning = "; ".join(item for item in [warning, answer_block_result.warning] if item)

        skills = self.derive_skills(atoms)
        exercise_templates = self.derive_exercise_templates(atoms, skills)
        scoring_rubric = self.build_scoring_rubric(skills)
        ticket = TicketKnowledgeMap(
            ticket_id=ticket_key,
            exam_id=exam_id,
            section_id=section_id,
            source_document_id=source_document_id,
            title=candidate.title,
            canonical_answer_summary=summary,
            atoms=atoms,
            skills=skills,
            exercise_templates=exercise_templates,
            scoring_rubric=scoring_rubric,
            examiner_prompts=examiner_prompts,
            cross_links_to_other_tickets=[],
            difficulty=difficulty,
            estimated_oral_time_sec=estimated_oral_time_sec,
            source_confidence=candidate.confidence,
            answer_profile_code=normalized_profile,
            answer_blocks=answer_block_result.blocks,
        )
        ticket.validate()
        return ticket, used_llm, warning

    def make_ticket_id(self, candidate: TicketCandidate, source_document_id: str) -> str:
        return self._slug(f"{source_document_id}-ticket-{candidate.index}-{candidate.title}")

    def resolve_section_id(self, candidate: TicketCandidate, default_section_id: str) -> str:
        return self._slug(candidate.section_title or default_section_id)

    @staticmethod
    def _normalize_answer_profile_code(code: AnswerProfileCode | str) -> AnswerProfileCode:
        try:
            return AnswerProfileCode(code)
        except ValueError:
            return AnswerProfileCode.STANDARD_TICKET

    @staticmethod
    def _report_progress(
        progress_callback: ImportProgressCallback | None,
        percent: int,
        stage: str,
        detail: str = "",
    ) -> None:
        if progress_callback is None:
            return
        bounded = max(0, min(100, int(percent)))
        progress_callback(bounded, stage, detail)

    @staticmethod
    def _loop_progress(start: int, end: int, current: int, total: int) -> int:
        if total <= 0:
            return start
        span = max(0, end - start)
        ratio = current / total
        return start + int(round(span * ratio))

    @staticmethod
    def should_use_llm_for_structuring(candidate: TicketCandidate, atoms: list[KnowledgeAtom]) -> bool:
        if candidate.confidence < 0.75:
            return True
        if len(atoms) < 4:
            return True
        return any(atom.confidence < 0.65 for atom in atoms)

    def extract_atoms(self, text: str, ticket_key: str) -> list[KnowledgeAtom]:
        paragraphs = self.split_into_atom_fragments(text)

        atoms: list[KnowledgeAtom] = []
        previous_atom_id: str | None = None
        for index, paragraph in enumerate(paragraphs, start=1):
            atom_type, confidence = self.detect_atom_type(paragraph, index)
            atom_id = self._slug(f"{ticket_key}-atom-{index}-{paragraph[:40]}")
            atom = KnowledgeAtom(
                atom_id=atom_id,
                type=atom_type,
                label=self.atom_label(atom_type, index),
                text=paragraph,
                keywords=self.extract_keywords(paragraph),
                weight=self.weight_for(atom_type),
                dependencies=[previous_atom_id] if previous_atom_id else [],
                parent_atom_id=None,
                confidence=confidence,
                source_excerpt=paragraph[:220],
            )
            atoms.append(atom)
            previous_atom_id = atom_id

        if all(atom.type is not AtomType.CONCLUSION for atom in atoms) and len(atoms) > 1:
            last = atoms[-1]
            atoms[-1] = KnowledgeAtom(
                atom_id=last.atom_id,
                type=AtomType.CONCLUSION,
                label="Вывод",
                text=last.text,
                keywords=last.keywords,
                weight=max(last.weight, 0.85),
                dependencies=last.dependencies,
                parent_atom_id=last.parent_atom_id,
                confidence=min(last.confidence, 0.7),
                source_excerpt=last.source_excerpt,
            )

        return atoms

    @staticmethod
    def split_into_atom_fragments(text: str) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        expanded: list[str] = []
        for paragraph in paragraphs:
            sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", paragraph) if sentence.strip()]
            if len(sentences) >= 2 and len(paragraph) > 120:
                expanded.extend(sentences)
            else:
                expanded.append(paragraph)
        return expanded

    @staticmethod
    def detect_atom_type(paragraph: str, index: int) -> tuple[AtomType, float]:
        lowered = paragraph.lower()
        cues = [
            (AtomType.DEFINITION, ("представляет собой", "это", "понимается как", "определяется как")),
            (AtomType.EXAMPLES, ("например", "к таким относятся", "в частности", "примером")),
            (AtomType.FEATURES, ("признаки", "характеризуется", "особенности", "свойства")),
            (AtomType.STAGES, ("этапы", "стадии")),
            (AtomType.FUNCTIONS, ("функции",)),
            (AtomType.CAUSES, ("причины", "обусловлено")),
            (AtomType.CONSEQUENCES, ("последствия", "приводит к")),
            (AtomType.CLASSIFICATION, ("классификация", "виды", "делится на")),
            (AtomType.PROCESS_STEP, ("порядок", "последовательность", "цикл", "включает")),
            (AtomType.CONCLUSION, ("таким образом", "следовательно", "итак", "вывод")),
        ]
        for atom_type, patterns in cues:
            if any(pattern in lowered for pattern in patterns):
                return atom_type, 0.88
        if index == 1:
            return AtomType.DEFINITION, 0.62
        return AtomType.FEATURES, 0.52

    @staticmethod
    def atom_label(atom_type: AtomType, index: int) -> str:
        labels = {
            AtomType.DEFINITION: "Определение",
            AtomType.EXAMPLES: "Примеры",
            AtomType.FEATURES: "Признаки",
            AtomType.STAGES: "Стадии",
            AtomType.FUNCTIONS: "Функции",
            AtomType.CAUSES: "Причины",
            AtomType.CONSEQUENCES: "Последствия",
            AtomType.CLASSIFICATION: "Классификация",
            AtomType.PROCESS_STEP: "Процесс",
            AtomType.CONCLUSION: "Вывод",
        }
        return labels.get(atom_type, f"Атом {index}")

    @staticmethod
    def extract_keywords(text: str, limit: int = 6) -> list[str]:
        words = re.findall(r"[A-Za-zА-Яа-яЁё0-9-]{4,}", text.lower())
        unique: list[str] = []
        for word in words:
            if word in STOP_WORDS or word.isdigit():
                continue
            if word not in unique:
                unique.append(word)
            if len(unique) >= limit:
                break
        return unique

    @staticmethod
    def weight_for(atom_type: AtomType) -> float:
        weights = {
            AtomType.DEFINITION: 1.0,
            AtomType.EXAMPLES: 0.7,
            AtomType.FEATURES: 0.95,
            AtomType.STAGES: 1.0,
            AtomType.FUNCTIONS: 0.9,
            AtomType.CAUSES: 0.85,
            AtomType.CONSEQUENCES: 0.85,
            AtomType.CLASSIFICATION: 0.9,
            AtomType.PROCESS_STEP: 1.1,
            AtomType.CONCLUSION: 0.8,
        }
        return weights.get(atom_type, 0.8)

    def derive_skills(self, atoms: list[KnowledgeAtom]) -> list[TicketSkill]:
        atom_ids_by_type: dict[AtomType, list[str]] = {}
        for atom in atoms:
            atom_ids_by_type.setdefault(atom.type, []).append(atom.atom_id)

        skills: list[TicketSkill] = []

        def add_skill(code: SkillCode, title: str, description: str, target_types: list[AtomType], weight: float, priority: int) -> None:
            target_atom_ids = [atom_id for atom_type in target_types for atom_id in atom_ids_by_type.get(atom_type, [])]
            if not target_atom_ids:
                return
            skill_suffix = f"{target_atom_ids[0]}-{len(skills) + 1}"
            skills.append(
                TicketSkill(
                    skill_id=self._slug(f"skill-{code.value}-{skill_suffix}"),
                    code=code,
                    title=title,
                    description=description,
                    target_atom_ids=target_atom_ids,
                    weight=weight,
                    priority=priority,
                )
            )

        add_skill(
            SkillCode.REPRODUCE_DEFINITION,
            "Воспроизвести определение",
            "Кратко и точно сформулировать ядро билета.",
            [AtomType.DEFINITION],
            1.0,
            3,
        )
        add_skill(
            SkillCode.LIST_EXAMPLES,
            "Привести примеры",
            "Вспомнить показательные примеры по билету.",
            [AtomType.EXAMPLES],
            0.7,
            2,
        )
        add_skill(
            SkillCode.NAME_KEY_FEATURES,
            "Назвать ключевые признаки",
            "Перечислить признаки, свойства или классификацию.",
            [AtomType.FEATURES, AtomType.CLASSIFICATION],
            1.0,
            3,
        )
        add_skill(
            SkillCode.RECONSTRUCT_PROCESS_ORDER,
            "Восстановить структуру",
            "Выстроить процесс или стадии ответа в правильном порядке.",
            [AtomType.PROCESS_STEP, AtomType.STAGES],
            1.0,
            4,
        )
        add_skill(
            SkillCode.EXPLAIN_CORE_LOGIC,
            "Объяснить логику",
            "Показать причинно-следственные и функциональные связи.",
            [AtomType.CAUSES, AtomType.CONSEQUENCES, AtomType.FUNCTIONS, AtomType.CONCLUSION],
            1.1,
            4,
        )
        add_skill(
            SkillCode.GIVE_SHORT_ORAL_ANSWER,
            "Краткий устный ответ",
            "Ответить за 20-60 секунд, сохранив смысловой каркас.",
            [atom.type for atom in atoms[: min(3, len(atoms))]],
            1.1,
            4,
        )
        add_skill(
            SkillCode.GIVE_FULL_ORAL_ANSWER,
            "Полный устный ответ",
            "Последовательно раскрыть билет целиком.",
            list(atom_ids_by_type.keys()),
            1.3,
            5,
        )
        add_skill(
            SkillCode.ANSWER_FOLLOWUP_QUESTIONS,
            "Ответ на follow-up вопросы",
            "Удержать логику билета при уточняющих вопросах экзаменатора.",
            [AtomType.FEATURES, AtomType.PROCESS_STEP, AtomType.CONCLUSION],
            1.2,
            5,
        )
        return skills

    def derive_exercise_templates(
        self,
        atoms: list[KnowledgeAtom],
        skills: list[TicketSkill],
    ) -> list[ExerciseTemplate]:
        atom_ids = [atom.atom_id for atom in atoms]
        skill_codes = [skill.code for skill in skills]
        templates = [
            ExerciseTemplate(
                template_id=self._slug(f"tpl-skeleton-{atom_ids[0]}"),
                exercise_type=ExerciseType.ANSWER_SKELETON,
                title="Каркас ответа",
                instructions="Заполните основные смысловые блоки ответа.",
                target_atom_ids=atom_ids[: min(5, len(atom_ids))],
                target_skill_codes=[SkillCode.GIVE_FULL_ORAL_ANSWER, SkillCode.EXPLAIN_CORE_LOGIC],
            ),
            ExerciseTemplate(
                template_id=self._slug(f"tpl-structure-{atom_ids[0]}"),
                exercise_type=ExerciseType.STRUCTURE_RECONSTRUCTION,
                title="Восстановление структуры",
                instructions="Соберите логический порядок тезисов.",
                target_atom_ids=atom_ids,
                target_skill_codes=[SkillCode.RECONSTRUCT_PROCESS_ORDER],
            ),
            ExerciseTemplate(
                template_id=self._slug(f"tpl-recall-{atom_ids[0]}"),
                exercise_type=ExerciseType.ATOM_RECALL,
                title="Точечное вспоминание",
                instructions="Ответьте на короткие вопросы по отдельным атомам знания.",
                target_atom_ids=atom_ids,
                target_skill_codes=[SkillCode.REPRODUCE_DEFINITION, SkillCode.NAME_KEY_FEATURES],
            ),
            ExerciseTemplate(
                template_id=self._slug(f"tpl-cloze-{atom_ids[0]}"),
                exercise_type=ExerciseType.SEMANTIC_CLOZE,
                title="Cloze по смыслу",
                instructions="Восстановите пропущенные смысловые узлы.",
                target_atom_ids=atom_ids[: min(3, len(atom_ids))],
                target_skill_codes=[SkillCode.REPRODUCE_DEFINITION, SkillCode.EXPLAIN_CORE_LOGIC],
            ),
            ExerciseTemplate(
                template_id=self._slug(f"tpl-odd-{atom_ids[0]}"),
                exercise_type=ExerciseType.ODD_THESIS,
                title="Лишний тезис",
                instructions="Определите тезис, который не вписывается в логику ответа.",
                target_atom_ids=atom_ids,
                target_skill_codes=[SkillCode.NAME_KEY_FEATURES, SkillCode.EXPLAIN_CORE_LOGIC],
            ),
            ExerciseTemplate(
                template_id=self._slug(f"tpl-oral-short-{atom_ids[0]}"),
                exercise_type=ExerciseType.ORAL_SHORT,
                title="Краткий устный ответ",
                instructions="Дайте связный ответ за 20-60 секунд.",
                target_atom_ids=atom_ids[: min(4, len(atom_ids))],
                target_skill_codes=[SkillCode.GIVE_SHORT_ORAL_ANSWER],
            ),
            ExerciseTemplate(
                template_id=self._slug(f"tpl-oral-full-{atom_ids[0]}"),
                exercise_type=ExerciseType.ORAL_FULL,
                title="Полный устный ответ",
                instructions="Дайте полный ответ в формате экзамена.",
                target_atom_ids=atom_ids,
                target_skill_codes=[SkillCode.GIVE_FULL_ORAL_ANSWER],
            ),
            ExerciseTemplate(
                template_id=self._slug(f"tpl-followup-{atom_ids[0]}"),
                exercise_type=ExerciseType.EXAMINER_FOLLOWUP,
                title="Экзаменатор",
                instructions="Ответьте на уточняющие вопросы по слабым местам.",
                target_atom_ids=atom_ids[: min(4, len(atom_ids))],
                target_skill_codes=[SkillCode.ANSWER_FOLLOWUP_QUESTIONS],
                llm_required=True,
            ),
            ExerciseTemplate(
                template_id=self._slug(f"tpl-weak-{atom_ids[0]}"),
                exercise_type=ExerciseType.WEAK_AREA_REPEAT,
                title="Повторение слабых мест",
                instructions="Повторите слабые атомы и навыки по билету.",
                target_atom_ids=atom_ids,
                target_skill_codes=skill_codes,
            ),
            ExerciseTemplate(
                template_id=self._slug(f"tpl-cross-{atom_ids[0]}"),
                exercise_type=ExerciseType.CROSS_TICKET_REPEAT,
                title="Межбилетное повторение",
                instructions="Свяжите текущий билет с родственными концептами и соседними билетами.",
                target_atom_ids=atom_ids,
                target_skill_codes=[SkillCode.EXPLAIN_CORE_LOGIC, SkillCode.ANSWER_FOLLOWUP_QUESTIONS],
            ),
        ]
        return templates

    def build_scoring_rubric(self, skills: list[TicketSkill]) -> list[ScoringCriterion]:
        field_map = {
            SkillCode.REPRODUCE_DEFINITION: "definition_mastery",
            SkillCode.LIST_EXAMPLES: "examples_mastery",
            SkillCode.NAME_KEY_FEATURES: "feature_mastery",
            SkillCode.RECONSTRUCT_PROCESS_ORDER: "structure_mastery",
            SkillCode.EXPLAIN_CORE_LOGIC: "process_mastery",
            SkillCode.GIVE_SHORT_ORAL_ANSWER: "oral_short_mastery",
            SkillCode.GIVE_FULL_ORAL_ANSWER: "oral_full_mastery",
            SkillCode.ANSWER_FOLLOWUP_QUESTIONS: "followup_mastery",
        }
        return [
            ScoringCriterion(
                criterion_id=self._slug(f"criterion-{skill.skill_id}"),
                skill_code=skill.code,
                mastery_field=field_map[skill.code],
                description=skill.description,
                max_score=1.0,
                weight=skill.weight,
            )
            for skill in skills
        ]

    def build_examiner_prompts(self, title: str, atoms: list[KnowledgeAtom]) -> list[ExaminerPrompt]:
        prompts: list[ExaminerPrompt] = []
        for atom in atoms[:4]:
            prompts.append(
                ExaminerPrompt(
                    prompt_id=self._slug(f"prompt-{title}-{atom.atom_id}"),
                    title=f"Уточнение по теме: {atom.label}",
                    text=f"Уточните, как в билете '{title}' раскрывается блок '{atom.label}'.",
                    target_skill_codes=[SkillCode.ANSWER_FOLLOWUP_QUESTIONS],
                    target_atom_ids=[atom.atom_id],
                    llm_assisted=True,
                )
            )
        return prompts

    @staticmethod
    def build_summary(atoms: list[KnowledgeAtom]) -> str:
        sentences = [atom.text for atom in atoms[:3]]
        return " ".join(sentences)[:700]

    @staticmethod
    def estimate_difficulty(atoms: list[KnowledgeAtom]) -> int:
        complexity = len(atoms) + sum(1 for atom in atoms if atom.type in {AtomType.PROCESS_STEP, AtomType.CAUSES, AtomType.CONSEQUENCES})
        if complexity <= 3:
            return 1
        if complexity <= 5:
            return 2
        if complexity <= 7:
            return 3
        if complexity <= 9:
            return 4
        return 5

    def attach_cross_ticket_links(self, tickets: list[TicketKnowledgeMap]) -> None:
        keyword_index: dict[str, list[str]] = {}
        display_label: dict[str, str] = {}
        for ticket in tickets:
            keywords = {keyword for atom in ticket.atoms for keyword in atom.keywords}
            for keyword in keywords:
                keyword_index.setdefault(keyword, []).append(ticket.ticket_id)
                display_label.setdefault(keyword, keyword)

        for ticket in tickets:
            ticket_keywords = {keyword for atom in ticket.atoms for keyword in atom.keywords}
            links: list[CrossTicketLink] = []
            for keyword in sorted(ticket_keywords):
                related_ticket_ids = [ticket_id for ticket_id in keyword_index.get(keyword, []) if ticket_id != ticket.ticket_id]
                if not related_ticket_ids:
                    continue
                strength = min(0.95, 0.55 + 0.1 * len(related_ticket_ids))
                links.append(
                    CrossTicketLink(
                        concept_id=self._slug(f"concept-{keyword}"),
                        concept_label=display_label[keyword],
                        related_ticket_ids=related_ticket_ids,
                        rationale=f"Концепт '{keyword}' встречается в нескольких билетах одного экзамена.",
                        strength=strength,
                    )
                )
            ticket.cross_links_to_other_tickets[:] = links

    @staticmethod
    def infer_title(text: str, fallback_title: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines[:5]:
            if 10 <= len(line) <= 160:
                return line.rstrip(":")
        return fallback_title

    @staticmethod
    def _slug(value: str) -> str:
        value = value.lower()
        value = re.sub(r"[^a-zа-яё0-9]+", "-", value, flags=re.IGNORECASE)
        value = re.sub(r"-{2,}", "-", value).strip("-")
        return value or uuid4().hex[:10]
