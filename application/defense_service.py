from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
from uuid import uuid4

from application.defense_ui_data import (
    DefenseEvaluationResult,
    DefenseProcessingResult,
    DefenseProjectSummary,
    DefenseWorkspaceProject,
    DefenseWorkspaceSnapshot,
    ModelRecommendation,
)
from application.dlc_license import DlcLicenseService
from application.model_profile_resolver import ModelProfileResolver
from application.settings_store import SettingsStore
from domain.defense import (
    CommitteePersonaKind,
    DefenseClaim,
    DefenseClaimKind,
    DefenseQuestion,
    DefenseScoreProfile,
    DefenseSession,
    DefenseSessionMode,
    DefenseWeakArea,
    DlcLicenseState,
    DisciplineProfile,
    SlideStoryboardCard,
    ThesisProject,
    ThesisSource,
    ThesisSourceKind,
)
from infrastructure.db.defense_repository import DefenseRepository
from infrastructure.importers.common import ImportedDocumentText, normalize_import_title
from infrastructure.importers.docx_importer import import_docx
from infrastructure.importers.pdf_importer import import_pdf
from infrastructure.importers.pptx_importer import import_pptx
from infrastructure.ollama.defense_prompts import (
    defense_answer_review_prompt,
    defense_dossier_prompt,
    defense_outline_prompt,
    defense_questions_prompt,
    defense_storyboard_prompt,
)
from infrastructure.ollama.service import OllamaService


CLAIM_LABELS = {
    DefenseClaimKind.PROBLEM: "Проблема исследования",
    DefenseClaimKind.RELEVANCE: "Актуальность",
    DefenseClaimKind.OBJECT: "Объект",
    DefenseClaimKind.SUBJECT: "Предмет",
    DefenseClaimKind.GOAL: "Цель",
    DefenseClaimKind.TASKS: "Задачи",
    DefenseClaimKind.METHODS: "Методы",
    DefenseClaimKind.NOVELTY: "Научная новизна",
    DefenseClaimKind.PRACTICAL_SIGNIFICANCE: "Практическая значимость",
    DefenseClaimKind.RESULTS: "Ключевые результаты",
    DefenseClaimKind.LIMITATIONS: "Ограничения",
    DefenseClaimKind.PERSONAL_CONTRIBUTION: "Личный вклад",
    DefenseClaimKind.RISK_TOPIC: "Риск-комиссии",
}

CLAIM_KEYWORDS = {
    DefenseClaimKind.PROBLEM: ("проблем", "problem"),
    DefenseClaimKind.RELEVANCE: ("актуаль", "relevance"),
    DefenseClaimKind.OBJECT: ("объект", "object"),
    DefenseClaimKind.SUBJECT: ("предмет", "subject"),
    DefenseClaimKind.GOAL: ("цель", "goal", "aim"),
    DefenseClaimKind.TASKS: ("задач", "tasks"),
    DefenseClaimKind.METHODS: ("метод", "methods", "methodology"),
    DefenseClaimKind.NOVELTY: ("новизн", "novelty"),
    DefenseClaimKind.PRACTICAL_SIGNIFICANCE: ("практическ", "significance"),
    DefenseClaimKind.RESULTS: ("результ", "results", "вывод"),
    DefenseClaimKind.LIMITATIONS: ("огранич", "limitations"),
    DefenseClaimKind.PERSONAL_CONTRIBUTION: ("личн", "author", "вклад"),
}


class DefenseService:
    PAYWALL_AMOUNT_LABEL = "донат 990 ₽"

    def __init__(
        self,
        workspace_root: Path,
        repository: DefenseRepository,
        settings_store: SettingsStore,
    ) -> None:
        self.workspace_root = workspace_root
        self.repository = repository
        self.settings_store = settings_store
        self.license_service = DlcLicenseService(workspace_root / "app_data" / "dlc_license.json")
        self.model_resolver = ModelProfileResolver()

    def load_workspace_snapshot(self, project_id: str | None = None) -> DefenseWorkspaceSnapshot:
        install_id = self.license_service.ensure_install_id()
        stored_license = self.repository.row_to_license(self.repository.load_license_state())
        if not stored_license.install_id or stored_license.install_id != install_id:
            stored_license.install_id = install_id
            self.repository.save_license_state(stored_license)
        recommendation = self._build_model_recommendation()
        project_rows = self.repository.load_projects()
        projects = [
            DefenseProjectSummary(
                project_id=row["project_id"],
                title=row["title"],
                status=row["status"],
                source_count=int(row["source_count"] or 0),
                updated_label=self._format_dt(row["updated_at"]),
            )
            for row in project_rows
        ]
        active_project_id = project_id or (projects[0].project_id if projects else None)
        active_project = self._load_workspace_project(active_project_id) if active_project_id else None
        return DefenseWorkspaceSnapshot(
            license_state=stored_license,
            paywall_amount_label=self.PAYWALL_AMOUNT_LABEL,
            install_id=install_id,
            recommendation=recommendation,
            projects=projects,
            active_project=active_project,
        )

    def activate_dlc(self, activation_code: str) -> DlcLicenseState:
        state = self.license_service.activate(self.license_service.ensure_install_id(), activation_code)
        self.repository.save_license_state(state)
        return state

    def issue_local_activation_code(self) -> str:
        return self.license_service.issue_code(self.license_service.ensure_install_id())

    def create_project(
        self,
        *,
        title: str,
        degree: str,
        specialty: str,
        student_name: str,
        supervisor_name: str,
        defense_date: str,
        discipline_profile: str,
    ) -> ThesisProject:
        now = datetime.now()
        project = ThesisProject(
            project_id=f"thesis-{uuid4().hex[:12]}",
            title=title.strip(),
            degree=degree.strip(),
            specialty=specialty.strip(),
            student_name=student_name.strip(),
            supervisor_name=supervisor_name.strip(),
            defense_date=datetime.fromisoformat(defense_date) if defense_date else None,
            discipline_profile=DisciplineProfile(discipline_profile),
            status="draft",
            created_at=now,
            updated_at=now,
            recommended_model=self._build_model_recommendation().model_name,
        )
        self.repository.save_project(project)
        return project

    def import_project_materials(
        self,
        project_id: str,
        paths: list[str | Path],
        progress_callback=None,
    ) -> DefenseProcessingResult:
        project_row = self.repository.load_project_row(project_id)
        if project_row is None:
            return DefenseProcessingResult(False, error="Проект защиты не найден.")

        path_list = [Path(path) for path in paths if Path(path).exists()]
        if not path_list:
            return DefenseProcessingResult(False, project_id=project_id, error="Не выбраны файлы для DLC.")

        warnings: list[str] = []
        llm_used = False
        project = self.repository.row_to_project(project_row)
        next_version = self._next_source_version(project_id)
        imported_sources: list[ThesisSource] = []

        if progress_callback is not None:
            progress_callback(10, "Импорт материалов защиты", f"Файлов: {len(path_list)}")

        for index, path in enumerate(path_list, start=1):
            try:
                imported = self._import_source(path)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{path.name}: {exc}")
                continue
            imported_sources.append(
                ThesisSource(
                    source_id=f"source-{uuid4().hex[:12]}",
                    project_id=project_id,
                    kind=self._infer_source_kind(path, len(imported_sources)),
                    title=imported.title,
                    file_path=str(path),
                    file_type=imported.file_type,
                    checksum=self._checksum(imported.raw_text),
                    version=next_version,
                    imported_at=datetime.now(),
                    parse_status="parsed",
                    confidence=0.9 if imported.raw_text.strip() else 0.0,
                    raw_text=imported.raw_text,
                    normalized_text=self._normalize_text(imported.raw_text),
                    unit_count=imported.unit_count,
                )
            )
            if progress_callback is not None:
                progress_callback(10 + int((index / max(1, len(path_list))) * 20), "Импорт материалов защиты", path.name)

        if not imported_sources:
            return DefenseProcessingResult(False, project_id=project_id, warnings=warnings, error="Не удалось извлечь текст из выбранных файлов.")

        self.repository.save_sources(imported_sources)
        combined_text = "\n\n".join(source.normalized_text for source in imported_sources if source.normalized_text.strip())
        claims, risk_topics, used_llm, claim_warnings = self._build_dossier(project, imported_sources, combined_text)
        warnings.extend(claim_warnings)
        llm_used = llm_used or used_llm
        self.repository.replace_claims(project_id, claims)

        if progress_callback is not None:
            progress_callback(52, "Defense dossier", "Собираем ключевые тезисы и риск-темы")

        outlines, outline_used_llm = self._build_outlines(project, claims)
        llm_used = llm_used or outline_used_llm
        for duration_label, segments in outlines.items():
            self.repository.replace_outline(project_id, duration_label, segments)

        if progress_callback is not None:
            progress_callback(70, "Текст защиты", "Готовим контуры доклада на 5, 7 и 10 минут")

        slides, slides_used_llm = self._build_slides(project_id, claims, outlines.get("7", []))
        llm_used = llm_used or slides_used_llm
        self.repository.replace_slides(project_id, slides)

        if progress_callback is not None:
            progress_callback(82, "Storyboard", "Строим план слайдов и опорных тезисов")

        questions, questions_used_llm = self._build_questions(project_id, claims, risk_topics, imported_sources)
        llm_used = llm_used or questions_used_llm
        self.repository.replace_questions(project_id, questions)

        updated_project = ThesisProject(
            project_id=project.project_id,
            title=project.title,
            degree=project.degree,
            specialty=project.specialty,
            student_name=project.student_name,
            supervisor_name=project.supervisor_name,
            defense_date=project.defense_date,
            discipline_profile=project.discipline_profile,
            status="ready_for_rehearsal",
            created_at=project.created_at,
            updated_at=datetime.now(),
            recommended_model=self._build_model_recommendation().model_name,
        )
        self.repository.save_project(updated_project)

        if progress_callback is not None:
            progress_callback(100, "DLC обработан", "Материалы сохранены. Можно идти в mock defense.")

        return DefenseProcessingResult(
            ok=True,
            project_id=project_id,
            message="Материалы защиты обработаны локально.",
            warnings=warnings,
            llm_used=llm_used,
        )

    def evaluate_mock_defense(
        self,
        project_id: str,
        mode_key: str,
        answer_text: str,
    ) -> DefenseEvaluationResult:
        answer = answer_text.strip()
        if not answer:
            return DefenseEvaluationResult(False, "", {}, error="Введите текст доклада или ответа.")

        project = self._load_workspace_project(project_id)
        if project is None:
            return DefenseEvaluationResult(False, "", {}, error="Проект не найден.")

        claims = [claim for claim in project.claims if claim.kind is not DefenseClaimKind.RISK_TOPIC]
        score_cards = self._score_answer(answer, claims, mode_key)
        weak_areas = self._build_weak_areas(project_id, score_cards)
        followups = self._select_followups(project.questions, mode_key, weak_areas)
        llm_summary = self._review_answer_with_llm(project.claims, followups, answer, mode_key)
        summary = llm_summary["summary"] if llm_summary and llm_summary.get("summary") else self._fallback_summary(score_cards, weak_areas)
        if llm_summary and llm_summary.get("followups"):
            followups = [text for text in llm_summary["followups"] if text]

        now = datetime.now()
        session = DefenseSession(
            session_id=f"defense-session-{uuid4().hex[:12]}",
            project_id=project_id,
            mode=DefenseSessionMode(mode_key),
            duration_sec=len(answer.split()) * 2,
            transcript_text=answer,
            questions=followups,
            answers=[answer],
            created_at=now,
        )
        profile = DefenseScoreProfile(
            project_id=project_id,
            session_id=session.session_id,
            structure_mastery=score_cards["structure_mastery"] / 100,
            relevance_clarity=score_cards["relevance_clarity"] / 100,
            methodology_mastery=score_cards["methodology_mastery"] / 100,
            novelty_mastery=score_cards["novelty_mastery"] / 100,
            results_mastery=score_cards["results_mastery"] / 100,
            limitations_honesty=score_cards["limitations_honesty"] / 100,
            oral_clarity_text_mode=score_cards["oral_clarity_text_mode"] / 100,
            followup_mastery=score_cards["followup_mastery"] / 100,
            summary_text=summary,
            created_at=now,
        )
        self.repository.save_session_bundle(session, profile, weak_areas)
        return DefenseEvaluationResult(
            ok=True,
            summary=summary,
            score_cards=score_cards,
            weak_points=[area.title for area in weak_areas],
            followup_questions=followups,
        )

    def _build_model_recommendation(self) -> ModelRecommendation:
        settings = self.settings_store.load()
        try:
            service = OllamaService(settings.base_url, min(float(settings.timeout_seconds), 3.0), settings.models_path)
            return self.model_resolver.recommend(service, settings.model)
        except Exception as exc:  # noqa: BLE001
            return ModelRecommendation(
                model_name=settings.model,
                label=f"Рекомендуемая модель: {settings.model}",
                rationale=f"Автоподбор не завершён: {exc}",
                available=False,
            )

    def _load_workspace_project(self, project_id: str | None) -> DefenseWorkspaceProject | None:
        if not project_id:
            return None
        row = self.repository.load_project_row(project_id)
        if row is None:
            return None
        project = self.repository.row_to_project(row)
        sources = [self.repository.row_to_source(source_row) for source_row in self.repository.load_sources(project_id)]
        claims = [self.repository.row_to_claim(claim_row) for claim_row in self.repository.load_claims(project_id)]
        slides = [self.repository.row_to_slide(slide_row) for slide_row in self.repository.load_slides(project_id)]
        questions = [self.repository.row_to_question(question_row) for question_row in self.repository.load_questions(project_id)]
        outline_rows = self.repository.load_outline_segments(project_id)
        outlines: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
        for row_item in outline_rows:
            outlines[row_item["duration_label"]].append(
                (row_item["title"], row_item["talking_points"], int(row_item["target_seconds"] or 0))
            )
        return DefenseWorkspaceProject(
            project=project,
            sources=sources,
            claims=claims,
            outlines=dict(outlines),
            slides=slides,
            questions=questions,
            latest_score=self.repository.row_to_score(self.repository.load_latest_score(project_id)),
            weak_areas=[self.repository.row_to_weak_area(area_row) for area_row in self.repository.load_weak_areas(project_id)],
        )

    def _import_source(self, path: Path) -> ImportedDocumentText:
        suffix = path.suffix.lower()
        if suffix == ".docx":
            return import_docx(str(path))
        if suffix == ".pdf":
            return import_pdf(str(path))
        if suffix == ".pptx":
            return import_pptx(str(path))
        if suffix in {".txt", ".md"}:
            raw_text = path.read_text(encoding="utf-8")
            return ImportedDocumentText(
                path=path,
                title=normalize_import_title(path.stem),
                file_type=suffix[1:].upper(),
                raw_text=raw_text,
                unit_count=max(1, len(raw_text.splitlines())),
            )
        raise ValueError(f"Формат {suffix} пока не поддерживается для DLC.")

    def _infer_source_kind(self, path: Path, current_count: int) -> ThesisSourceKind:
        suffix = path.suffix.lower()
        if suffix == ".pptx":
            return ThesisSourceKind.SLIDES
        if suffix in {".txt", ".md"}:
            return ThesisSourceKind.NOTES
        if current_count == 0:
            return ThesisSourceKind.THESIS
        return ThesisSourceKind.NOTES

    def _build_dossier(
        self,
        project: ThesisProject,
        sources: list[ThesisSource],
        combined_text: str,
    ) -> tuple[list[DefenseClaim], list[str], bool, list[str]]:
        settings = self.settings_store.load()
        service = OllamaService(settings.base_url, None, settings.models_path)
        warnings: list[str] = []
        llm_used = False
        risk_topics: list[str] = []
        payload = self._call_llm_json(
            service,
            *defense_dossier_prompt(combined_text[:40000], project.discipline_profile.value),
            model=settings.model,
        )
        claims: list[DefenseClaim] = []
        if payload is not None:
            llm_used = True
            for raw_claim in payload.get("claims", []):
                kind_value = str(raw_claim.get("kind", "")).strip()
                if kind_value not in DefenseClaimKind._value2member_map_:
                    continue
                text = str(raw_claim.get("text", "")).strip()
                if not text:
                    continue
                kind = DefenseClaimKind(kind_value)
                claims.append(
                    DefenseClaim(
                        claim_id=f"claim-{project.project_id}-{kind.value}",
                        project_id=project.project_id,
                        kind=kind,
                        text=text,
                        confidence=float(raw_claim.get("confidence", 0.6) or 0.6),
                        source_anchors=self._find_anchors(text, sources),
                        llm_assisted=True,
                        needs_review=bool(raw_claim.get("needs_review", False)),
                        updated_at=datetime.now(),
                    )
                )
            risk_topics = [str(item.get("text", "")).strip() for item in payload.get("risk_topics", []) if str(item.get("text", "")).strip()]
        if not claims:
            warnings.append("LLM dossier extraction недоступен или вернул пустой результат. Использован rule-based fallback.")
            claims, risk_topics = self._fallback_claims(project.project_id, sources, combined_text)
        for risk_text in risk_topics[:4]:
            claims.append(
                DefenseClaim(
                    claim_id=f"claim-{project.project_id}-risk-{sha256(risk_text.encode('utf-8')).hexdigest()[:8]}",
                    project_id=project.project_id,
                    kind=DefenseClaimKind.RISK_TOPIC,
                    text=risk_text,
                    confidence=0.55,
                    source_anchors=self._find_anchors(risk_text, sources),
                    llm_assisted=llm_used,
                    needs_review=False,
                    updated_at=datetime.now(),
                )
            )
        return claims, risk_topics, llm_used, warnings

    def _fallback_claims(
        self,
        project_id: str,
        sources: list[ThesisSource],
        combined_text: str,
    ) -> tuple[list[DefenseClaim], list[str]]:
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", combined_text) if paragraph.strip()]
        claims: list[DefenseClaim] = []
        for kind, keywords in CLAIM_KEYWORDS.items():
            paragraph = next((item for item in paragraphs if any(keyword in item.lower() for keyword in keywords)), "")
            if not paragraph and kind is DefenseClaimKind.RESULTS and paragraphs:
                paragraph = paragraphs[min(len(paragraphs) - 1, 2)]
            if not paragraph:
                continue
            claims.append(
                DefenseClaim(
                    claim_id=f"claim-{project_id}-{kind.value}",
                    project_id=project_id,
                    kind=kind,
                    text=self._compact_text(paragraph, 420),
                    confidence=0.48,
                    source_anchors=self._find_anchors(paragraph, sources),
                    llm_assisted=False,
                    needs_review=True,
                    updated_at=datetime.now(),
                )
            )
        return claims, self._build_risk_topics(claims)

    def _build_outlines(self, project: ThesisProject, claims: list[DefenseClaim]) -> tuple[dict[str, list[dict[str, object]]], bool]:
        settings = self.settings_store.load()
        service = OllamaService(settings.base_url, None, settings.models_path)
        claim_payload = [self._claim_to_prompt_dict(claim) for claim in claims if claim.kind is not DefenseClaimKind.RISK_TOPIC]
        outlines: dict[str, list[dict[str, object]]] = {}
        llm_used = False
        for duration in (5, 7, 10):
            payload = self._call_llm_json(service, *defense_outline_prompt(claim_payload, duration), model=settings.model)
            if payload and payload.get("segments"):
                outlines[str(duration)] = list(payload["segments"])
                llm_used = True
                continue
            outlines[str(duration)] = self._fallback_outline(claims, duration)
        return outlines, llm_used

    def _build_slides(
        self,
        project_id: str,
        claims: list[DefenseClaim],
        outline_segments: list[dict[str, object]],
    ) -> tuple[list[SlideStoryboardCard], bool]:
        settings = self.settings_store.load()
        service = OllamaService(settings.base_url, None, settings.models_path)
        payload = self._call_llm_json(
            service,
            *defense_storyboard_prompt(
                [self._claim_to_prompt_dict(claim) for claim in claims if claim.kind is not DefenseClaimKind.RISK_TOPIC],
                outline_segments,
            ),
            model=settings.model,
        )
        if payload and payload.get("slides"):
            return [
                SlideStoryboardCard(
                    card_id=f"slide-{project_id}-{index}",
                    project_id=project_id,
                    slide_index=index,
                    title=str(slide.get("title", "")).strip() or f"Слайд {index}",
                    purpose=str(slide.get("purpose", "")).strip(),
                    talking_points=[str(point).strip() for point in slide.get("talking_points", []) if str(point).strip()],
                    evidence_links=[str(point).strip() for point in slide.get("evidence_links", []) if str(point).strip()],
                )
                for index, slide in enumerate(payload["slides"], start=1)
            ], True
        return self._fallback_slides(project_id, claims), False

    def _build_questions(
        self,
        project_id: str,
        claims: list[DefenseClaim],
        risk_topics: list[str],
        sources: list[ThesisSource],
    ) -> tuple[list[DefenseQuestion], bool]:
        settings = self.settings_store.load()
        service = OllamaService(settings.base_url, None, settings.models_path)
        questions: list[DefenseQuestion] = []
        llm_used = False
        claim_payload = [self._claim_to_prompt_dict(claim) for claim in claims if claim.kind is not DefenseClaimKind.RISK_TOPIC]
        for persona in CommitteePersonaKind:
            payload = self._call_llm_json(
                service,
                *defense_questions_prompt(claim_payload, risk_topics, persona.value, 3),
                model=settings.model,
            )
            if payload and payload.get("questions"):
                llm_used = True
                for index, raw_question in enumerate(payload["questions"], start=1):
                    text = str(raw_question.get("question_text", "")).strip()
                    if not text:
                        continue
                    questions.append(
                        DefenseQuestion(
                            question_id=f"question-{project_id}-{persona.value}-{index}",
                            project_id=project_id,
                            persona=persona,
                            topic=str(raw_question.get("topic", "Основной тезис")).strip(),
                            difficulty=int(raw_question.get("difficulty", 2) or 2),
                            question_text=text,
                            source_anchors=self._find_anchors(text, sources),
                            risk_tag=str(raw_question.get("risk_tag", "")).strip(),
                            created_at=datetime.now(),
                        )
                    )
                continue
            questions.extend(self._fallback_questions(project_id, persona, claims, risk_topics))
        return questions, llm_used

    def _call_llm_json(self, service: OllamaService, system: str, prompt: str, *, model: str) -> dict[str, object] | None:
        response = service.client.generate(model, prompt, system=system, format_name="json", temperature=0.1)
        if not response.ok:
            return None
        raw = str(response.payload.get("response", "")).strip()
        if not raw:
            return None
        try:
            return service._parse_json_response(raw)
        except Exception:
            return None

    def _fallback_outline(self, claims: list[DefenseClaim], duration_minutes: int) -> list[dict[str, object]]:
        ordered = [
            DefenseClaimKind.RELEVANCE,
            DefenseClaimKind.GOAL,
            DefenseClaimKind.METHODS,
            DefenseClaimKind.NOVELTY,
            DefenseClaimKind.RESULTS,
            DefenseClaimKind.PRACTICAL_SIGNIFICANCE,
            DefenseClaimKind.LIMITATIONS,
        ]
        by_kind = {claim.kind: claim for claim in claims}
        duration_seconds = duration_minutes * 60
        titles = []
        for kind in ordered:
            claim = by_kind.get(kind)
            if claim:
                titles.append((CLAIM_LABELS[kind], self._compact_text(claim.text, 220)))
        if not titles:
            titles = [("Доклад", "Кратко объясните тему, цель, методы, результаты и выводы.")]
        segment_seconds = max(35, duration_seconds // max(1, len(titles)))
        return [{"title": title, "talking_points": text, "target_seconds": segment_seconds} for title, text in titles]

    def _fallback_slides(self, project_id: str, claims: list[DefenseClaim]) -> list[SlideStoryboardCard]:
        slides: list[SlideStoryboardCard] = []
        ordered_claims = [claim for claim in claims if claim.kind is not DefenseClaimKind.RISK_TOPIC][:8]
        for index, claim in enumerate(ordered_claims, start=1):
            slides.append(
                SlideStoryboardCard(
                    card_id=f"slide-{project_id}-{index}",
                    project_id=project_id,
                    slide_index=index,
                    title=CLAIM_LABELS.get(claim.kind, f"Слайд {index}"),
                    purpose=f"Показать блок: {CLAIM_LABELS.get(claim.kind, claim.kind.value)}",
                    talking_points=[self._compact_text(claim.text, 140)],
                    evidence_links=claim.source_anchors[:2],
                )
            )
        return slides

    def _fallback_questions(
        self,
        project_id: str,
        persona: CommitteePersonaKind,
        claims: list[DefenseClaim],
        risk_topics: list[str],
    ) -> list[DefenseQuestion]:
        prompts = {
            CommitteePersonaKind.SCIENTIFIC_ADVISOR: "Уточните, чем этот тезис поддержан в тексте работы.",
            CommitteePersonaKind.OPPONENT: "Почему этот тезис нельзя считать поверхностным или недоказанным?",
            CommitteePersonaKind.COMMISSION: "Объясните это коротко и по существу для комиссии.",
        }
        questions: list[DefenseQuestion] = []
        base_claims = [claim for claim in claims if claim.kind in {DefenseClaimKind.NOVELTY, DefenseClaimKind.METHODS, DefenseClaimKind.RESULTS, DefenseClaimKind.RELEVANCE}]
        for index, claim in enumerate(base_claims[:3], start=1):
            risk_tag = risk_topics[index - 1] if len(risk_topics) >= index else ""
            questions.append(
                DefenseQuestion(
                    question_id=f"question-{project_id}-{persona.value}-{index}",
                    project_id=project_id,
                    persona=persona,
                    topic=CLAIM_LABELS.get(claim.kind, claim.kind.value),
                    difficulty=2 if claim.kind in {DefenseClaimKind.METHODS, DefenseClaimKind.NOVELTY} else 1,
                    question_text=f"{CLAIM_LABELS.get(claim.kind, claim.kind.value)}. {prompts[persona]}",
                    source_anchors=claim.source_anchors[:2],
                    risk_tag=risk_tag,
                    created_at=datetime.now(),
                )
            )
        return questions

    def _review_answer_with_llm(
        self,
        claims: list[DefenseClaim],
        questions: list[str],
        answer_text: str,
        mode_key: str,
    ) -> dict[str, object] | None:
        settings = self.settings_store.load()
        service = OllamaService(settings.base_url, None, settings.models_path)
        return self._call_llm_json(
            service,
            *defense_answer_review_prompt(
                [self._claim_to_prompt_dict(claim) for claim in claims if claim.kind is not DefenseClaimKind.RISK_TOPIC],
                questions,
                answer_text,
                mode_key,
            ),
            model=settings.model,
        )

    def _next_source_version(self, project_id: str) -> int:
        rows = self.repository.load_sources(project_id)
        if not rows:
            return 1
        return max(int(row["version"] or 0) for row in rows) + 1

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        paragraphs = [re.sub(r"\s+", " ", block).strip() for block in re.split(r"\n{2,}", normalized)]
        return "\n\n".join(block for block in paragraphs if block)

    @staticmethod
    def _checksum(text: str) -> str:
        return sha256(text.encode("utf-8")).hexdigest()

    def _find_anchors(self, text: str, sources: list[ThesisSource]) -> list[str]:
        query = self._compact_text(text, 180).lower()
        keywords = [token for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9]{5,}", query)[:8]]
        anchors: list[str] = []
        for source in sources:
            paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", source.normalized_text) if paragraph.strip()]
            for paragraph in paragraphs:
                lower = paragraph.lower()
                if query and query[:40] in lower:
                    anchors.append(f"{source.title}: {self._compact_text(paragraph, 140)}")
                elif keywords and any(keyword in lower for keyword in keywords):
                    anchors.append(f"{source.title}: {self._compact_text(paragraph, 140)}")
                if len(anchors) >= 3:
                    return anchors
        return anchors

    @staticmethod
    def _claim_to_prompt_dict(claim: DefenseClaim) -> dict[str, object]:
        return {
            "kind": claim.kind.value,
            "text": claim.text,
            "confidence": round(claim.confidence, 3),
            "needs_review": claim.needs_review,
            "anchors": claim.source_anchors,
        }

    @staticmethod
    def _compact_text(text: str, limit: int) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= limit:
            return compact
        return compact[: max(0, limit - 1)].rstrip() + "…"

    @staticmethod
    def _format_dt(value: object) -> str:
        if not value:
            return "нет данных"
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value))
        return dt.strftime("%d.%m.%Y %H:%M")

    def _build_risk_topics(self, claims: list[DefenseClaim]) -> list[str]:
        risk_topics: list[str] = []
        by_kind = {claim.kind: claim for claim in claims}
        for kind in (DefenseClaimKind.NOVELTY, DefenseClaimKind.METHODS, DefenseClaimKind.RESULTS, DefenseClaimKind.LIMITATIONS):
            claim = by_kind.get(kind)
            if claim is None:
                risk_topics.append(f"Не раскрыт блок «{CLAIM_LABELS[kind]}».")
            elif claim.confidence < 0.55 or claim.needs_review:
                risk_topics.append(f"Блок «{CLAIM_LABELS[kind]}» требует ручной проверки перед защитой.")
        return risk_topics[:4]

    def _score_answer(
        self,
        answer_text: str,
        claims: list[DefenseClaim],
        mode_key: str,
    ) -> dict[str, int]:
        answer = answer_text.lower()
        answer_words = max(1, len(re.findall(r"\w+", answer_text)))
        by_kind = {claim.kind: claim for claim in claims}

        def claim_coverage(kind: DefenseClaimKind) -> float:
            claim = by_kind.get(kind)
            if claim is None:
                return 0.35
            keywords = [token.lower() for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9]{5,}", claim.text)[:8]]
            if not keywords:
                return 0.45
            hits = sum(1 for token in keywords if token in answer)
            return max(0.0, min(1.0, hits / max(1, min(4, len(keywords)))))

        structure = 0.45
        if answer_words >= 120:
            structure = 0.9
        elif answer_words >= 70:
            structure = 0.75
        elif answer_words >= 35:
            structure = 0.58

        oral_clarity = 0.55
        if 35 <= answer_words <= 220:
            oral_clarity = 0.78
        elif answer_words > 220:
            oral_clarity = 0.63

        followup = 0.72 if mode_key in {"persona_qa", "full_mock_defense"} and answer_words >= 45 else 0.48
        limitations = claim_coverage(DefenseClaimKind.LIMITATIONS)
        if limitations < 0.4 and any(token in answer for token in ("огранич", "риски", "границ")):
            limitations = 0.62

        return {
            "structure_mastery": int(round(structure * 100)),
            "relevance_clarity": int(round(claim_coverage(DefenseClaimKind.RELEVANCE) * 100)),
            "methodology_mastery": int(round(claim_coverage(DefenseClaimKind.METHODS) * 100)),
            "novelty_mastery": int(round(claim_coverage(DefenseClaimKind.NOVELTY) * 100)),
            "results_mastery": int(round(claim_coverage(DefenseClaimKind.RESULTS) * 100)),
            "limitations_honesty": int(round(limitations * 100)),
            "oral_clarity_text_mode": int(round(oral_clarity * 100)),
            "followup_mastery": int(round(followup * 100)),
        }

    def _build_weak_areas(self, project_id: str, score_cards: dict[str, int]) -> list[DefenseWeakArea]:
        mapping = {
            "structure_mastery": ("skill", "Структура доклада", "Ответ теряет каркас и может распасться под вопросами комиссии.", None),
            "relevance_clarity": ("claim", "Актуальность раскрыта слабо", "Пользователь не удерживает блок актуальности.", DefenseClaimKind.RELEVANCE),
            "methodology_mastery": ("claim", "Методы объяснены неубедительно", "Комиссия сможет уцепиться за методологию.", DefenseClaimKind.METHODS),
            "novelty_mastery": ("claim", "Новизна звучит неуверенно", "Новизна может быть оспорена на защите.", DefenseClaimKind.NOVELTY),
            "results_mastery": ("claim", "Результаты поданы размыто", "Главные результаты теряются в ответе.", DefenseClaimKind.RESULTS),
            "limitations_honesty": ("claim", "Ограничения не названы", "Пользователь избегает честного обсуждения ограничений.", DefenseClaimKind.LIMITATIONS),
            "oral_clarity_text_mode": ("skill", "Текст доклада тяжело слушать", "Ответ перегружен или недостаточно собран.", None),
            "followup_mastery": ("skill", "Follow-up ответы шаткие", "Под давлением дополнительных вопросов ответ проседает.", None),
        }
        weak_areas: list[DefenseWeakArea] = []
        for key, score in score_cards.items():
            if score >= 68:
                continue
            kind, title, evidence, claim_kind = mapping[key]
            weak_areas.append(
                DefenseWeakArea(
                    weak_area_id=f"weak-{project_id}-{key}",
                    project_id=project_id,
                    kind=kind,
                    title=title,
                    severity=round((100 - score) / 100, 3),
                    evidence=evidence,
                    claim_kind=claim_kind,
                    created_at=datetime.now(),
                )
            )
        return weak_areas

    def _select_followups(
        self,
        questions: list[DefenseQuestion],
        mode_key: str,
        weak_areas: list[DefenseWeakArea],
    ) -> list[str]:
        target = 4 if mode_key == DefenseSessionMode.FULL_MOCK_DEFENSE.value else 3
        risky_kinds = {area.claim_kind for area in weak_areas if area.claim_kind is not None}
        selected: list[str] = []
        for question in questions:
            topic_lower = question.topic.lower()
            if risky_kinds and any(kind.value.replace("_", " ") in topic_lower for kind in risky_kinds):
                selected.append(question.question_text)
            if len(selected) >= target:
                return selected
        for question in questions:
            if question.question_text not in selected:
                selected.append(question.question_text)
            if len(selected) >= target:
                break
        return selected

    @staticmethod
    def _fallback_summary(score_cards: dict[str, int], weak_areas: list[DefenseWeakArea]) -> str:
        average = int(round(sum(score_cards.values()) / max(1, len(score_cards))))
        if not weak_areas:
            return f"Текстовая mock-защита прошла ровно. Средний профиль: {average}%."
        weakest = weak_areas[0].title
        return f"Средний профиль защиты: {average}%. Главный риск сейчас: {weakest}."
