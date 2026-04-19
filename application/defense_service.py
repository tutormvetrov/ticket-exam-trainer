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
    DefenseGapFinding,
    DefenseGapKind,
    DefenseGapStatus,
    DefenseQuestion,
    DefenseRepairSourceType,
    DefenseRepairTask,
    DefenseRepairTaskStatus,
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
from infrastructure.db.transaction import atomic
from infrastructure.importers.common import ImportedDocumentText, normalize_import_title
from infrastructure.importers.docx_importer import import_docx
from infrastructure.importers.pdf_importer import import_pdf
from infrastructure.importers.pptx_importer import import_pptx
from infrastructure.ollama.defense_prompts import (
    defense_answer_review_prompt,
    defense_dossier_prompt,
    defense_gap_enrichment_prompt,
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

GAP_KIND_LABELS = {
    DefenseGapKind.UNSUPPORTED_CLAIM: "Тезис без опоры",
    DefenseGapKind.CONTRADICTION: "Противоречие между тезисами",
    DefenseGapKind.MISSING_BRIDGE: "Логический переход не построен",
    DefenseGapKind.WEAK_EVIDENCE: "Слабая доказательная база",
    DefenseGapKind.VAGUE_RESULT: "Результат сформулирован расплывчато",
    DefenseGapKind.NOVELTY_NOT_PROVEN: "Новизна не доказана",
    DefenseGapKind.LIMITATIONS_MISSING: "Ограничения не раскрыты",
    DefenseGapKind.METHODS_RESULTS_DISCONNECT: "Методы и результаты не связаны",
}

PERSONA_FOCUS = {
    CommitteePersonaKind.SCIENTIFIC_ADVISOR: "методология, ограничения и дисциплина формулировок",
    CommitteePersonaKind.OPPONENT: "новизна, доказательность и уязвимые места",
    CommitteePersonaKind.COMMISSION: "прикладная ценность, ясность и защищаемость выводов",
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

    def update_gap_status(self, project_id: str, finding_id: str, status: str) -> None:
        resolved = DefenseGapStatus(status) if status in DefenseGapStatus._value2member_map_ else DefenseGapStatus.OPEN
        self.repository.update_gap_status(project_id, finding_id, resolved)

    def update_repair_task_status(self, project_id: str, task_id: str, status: str) -> None:
        resolved = (
            DefenseRepairTaskStatus(status)
            if status in DefenseRepairTaskStatus._value2member_map_
            else DefenseRepairTaskStatus.TODO
        )
        self.repository.update_repair_task_status(project_id, task_id, resolved)

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
            warnings.extend(imported.warnings)
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

        combined_text = "\n\n".join(source.normalized_text for source in imported_sources if source.normalized_text.strip())
        claims, risk_topics, used_llm, claim_warnings = self._build_dossier(project, imported_sources, combined_text)
        warnings.extend(claim_warnings)
        llm_used = llm_used or used_llm

        if progress_callback is not None:
            progress_callback(52, "Defense dossier", "Собираем ключевые тезисы и риск-темы")

        outlines, outline_used_llm = self._build_outlines(project, claims)
        llm_used = llm_used or outline_used_llm

        if progress_callback is not None:
            progress_callback(70, "Текст защиты", "Готовим контуры доклада на 5, 7 и 10 минут")

        slides, slides_used_llm = self._build_slides(project_id, claims, outlines.get("7", []))
        llm_used = llm_used or slides_used_llm

        if progress_callback is not None:
            progress_callback(82, "Storyboard", "Строим план слайдов и опорных тезисов")

        questions, questions_used_llm = self._build_questions(project_id, claims, risk_topics, imported_sources)
        llm_used = llm_used or questions_used_llm

        if progress_callback is not None:
            progress_callback(90, "Логические дыры", "Проверяем доказательность, связность и слабые места защиты")

        gap_findings = self._build_gap_findings(project_id, claims, outlines, slides, questions, imported_sources)
        gap_findings = self._enrich_gap_findings(gap_findings, claims, imported_sources)
        repair_tasks = self._build_repair_tasks(project_id, gap_findings, [], [])

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

        # Атомарный блок: либо все артефакты защиты сохранены согласованно,
        # либо ничего (откатываемся, оставляем прошлую версию проекта).
        with atomic(self.repository.connection):
            self.repository.save_sources(imported_sources)
            self.repository.replace_claims(project_id, claims)
            for duration_label, segments in outlines.items():
                self.repository.replace_outline(project_id, duration_label, segments)
            self.repository.replace_slides(project_id, slides)
            self.repository.replace_questions(project_id, questions)
            self.repository.replace_gap_findings(project_id, gap_findings)
            self.repository.replace_repair_tasks(project_id, repair_tasks)
            self.repository.save_project(updated_project)

        if progress_callback is not None:
            progress_callback(100, "DLC обработан", "Материалы сохранены. Можно идти в mock defense.")

        return DefenseProcessingResult(
            ok=True,
            project_id=project_id,
            message="Материалы защиты обработаны локально.",
            warnings=warnings,
            llm_used=llm_used,
            gap_findings_count=len(gap_findings),
            repair_tasks_count=len(repair_tasks),
        )

    def evaluate_mock_defense(
        self,
        project_id: str,
        mode_key: str,
        persona_kind: str,
        timer_profile_sec: int,
        answer_text: str,
    ) -> DefenseEvaluationResult:
        answer = answer_text.strip()
        if not answer:
            return DefenseEvaluationResult(False, "", {}, error="Введите текст доклада или ответа.")

        project = self._load_workspace_project(project_id)
        if project is None:
            return DefenseEvaluationResult(False, "", {}, error="Проект не найден.")

        claims = [claim for claim in project.claims if claim.kind is not DefenseClaimKind.RISK_TOPIC]
        persona = CommitteePersonaKind(persona_kind) if persona_kind in CommitteePersonaKind._value2member_map_ else CommitteePersonaKind.COMMISSION
        actual_duration_sec = self._estimate_session_duration(answer, timer_profile_sec)
        score_cards = self._score_answer(answer, claims, mode_key, persona, actual_duration_sec, timer_profile_sec)
        weak_areas = self._build_weak_areas(project_id, score_cards)
        open_gap_findings = [finding for finding in project.gap_findings if finding.status in {DefenseGapStatus.OPEN, DefenseGapStatus.ACCEPTED}]
        followups = self._select_followups(project.questions, mode_key, persona, weak_areas, open_gap_findings)
        llm_summary = self._review_answer_with_llm(project.claims, followups, answer, mode_key, persona.value, timer_profile_sec)
        timer_verdict = self._build_timer_verdict(actual_duration_sec, timer_profile_sec)
        summary = llm_summary["summary"] if llm_summary and llm_summary.get("summary") else self._fallback_summary(score_cards, weak_areas, persona, timer_verdict)
        if llm_summary and llm_summary.get("followups"):
            followups = [text for text in llm_summary["followups"] if text]
        related_gap_ids = self._match_related_gap_ids(open_gap_findings, weak_areas, followups)
        repair_tasks = self._build_repair_tasks(project_id, project.gap_findings, weak_areas, followups)
        self.repository.replace_repair_tasks(project_id, repair_tasks)

        now = datetime.now()
        session = DefenseSession(
            session_id=f"defense-session-{uuid4().hex[:12]}",
            project_id=project_id,
            mode=DefenseSessionMode(mode_key),
            persona_kind=persona,
            timer_profile_sec=max(0, int(timer_profile_sec or 0)),
            duration_sec=actual_duration_sec,
            transcript_text=answer,
            questions=followups,
            answers=[answer],
            session_notes=timer_verdict,
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
            persona_kind=persona,
            timer_verdict=timer_verdict,
            weak_points=[area.title for area in weak_areas],
            followup_questions=followups,
            related_gap_ids=related_gap_ids,
            suggested_repair_tasks=[task.title for task in repair_tasks[:5]],
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
        gap_findings = [self.repository.row_to_gap_finding(row) for row in self.repository.load_gap_findings(project_id)]
        repair_tasks = [self.repository.row_to_repair_task(row) for row in self.repository.load_repair_tasks(project_id)]
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
            gap_findings=gap_findings,
            repair_tasks=repair_tasks,
            latest_score=self.repository.row_to_score(self.repository.load_latest_score(project_id)),
            weak_areas=[self.repository.row_to_weak_area(area_row) for area_row in self.repository.load_weak_areas(project_id)],
        )

    def _import_source(self, path: Path) -> ImportedDocumentText:
        suffix = path.suffix.lower()
        if suffix == ".docx":
            return import_docx(str(path), workspace_root=self.workspace_root)
        if suffix == ".pdf":
            return import_pdf(str(path), workspace_root=self.workspace_root)
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
                            difficulty=self._coerce_question_difficulty(raw_question.get("difficulty", 2)),
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
        response = service.request_generation(model, prompt, system=system, format_name="json", temperature=0.1)
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

    @staticmethod
    def _coerce_question_difficulty(value: object) -> int:
        if isinstance(value, (int, float)):
            return max(1, min(3, int(value)))
        raw = str(value or "").strip().lower()
        mapping = {
            "low": 1,
            "easy": 1,
            "medium": 2,
            "normal": 2,
            "high": 3,
            "hard": 3,
        }
        if raw in mapping:
            return mapping[raw]
        try:
            return max(1, min(3, int(raw)))
        except ValueError:
            return 2

    def _review_answer_with_llm(
        self,
        claims: list[DefenseClaim],
        questions: list[str],
        answer_text: str,
        mode_key: str,
        persona_kind: str,
        timer_profile_sec: int,
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
                persona_kind,
                timer_profile_sec,
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
        persona: CommitteePersonaKind,
        actual_duration_sec: int,
        timer_profile_sec: int,
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
        if persona is CommitteePersonaKind.SCIENTIFIC_ADVISOR:
            limitations = min(1.0, limitations + 0.05)
        elif persona is CommitteePersonaKind.OPPONENT:
            followup = max(0.0, followup - 0.06)
        elif persona is CommitteePersonaKind.COMMISSION:
            structure = min(1.0, structure + 0.04)
        if timer_profile_sec > 0:
            overrun = abs(actual_duration_sec - timer_profile_sec)
            if overrun > max(45, int(timer_profile_sec * 0.2)):
                structure = max(0.0, structure - 0.09)
                oral_clarity = max(0.0, oral_clarity - 0.08)

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
        persona: CommitteePersonaKind,
        weak_areas: list[DefenseWeakArea],
        gap_findings: list[DefenseGapFinding],
    ) -> list[str]:
        target = 4 if mode_key == DefenseSessionMode.FULL_MOCK_DEFENSE.value else 3
        risky_kinds = {area.claim_kind for area in weak_areas if area.claim_kind is not None}
        risky_kinds.update(kind for finding in gap_findings for kind in finding.related_claim_kinds)
        selected: list[str] = []
        for question in questions:
            if question.persona is not persona:
                continue
            topic_lower = question.topic.lower()
            if risky_kinds and any(kind.value.replace("_", " ") in topic_lower for kind in risky_kinds):
                selected.append(question.question_text)
            if len(selected) >= target:
                return selected
        for question in questions:
            if question.persona is not persona:
                continue
            if question.question_text not in selected:
                selected.append(question.question_text)
            if len(selected) >= target:
                break
        if gap_findings and len(selected) < target:
            for finding in gap_findings[: target - len(selected)]:
                selected.append(f"{PERSONA_FOCUS[persona].capitalize()}: {finding.title.lower()}. {finding.suggested_fix or finding.explanation}")
        return selected

    @staticmethod
    def _fallback_summary(
        score_cards: dict[str, int],
        weak_areas: list[DefenseWeakArea],
        persona: CommitteePersonaKind,
        timer_verdict: str,
    ) -> str:
        average = int(round(sum(score_cards.values()) / max(1, len(score_cards))))
        if not weak_areas:
            return (
                f"Репетиция для роли «{persona.value}» прошла ровно. Средний профиль: {average}%. "
                f"{timer_verdict}".strip()
            )
        weakest = weak_areas[0].title
        return f"Средний профиль защиты: {average}%. Главный риск сейчас: {weakest}. {timer_verdict}".strip()

    def _build_gap_findings(
        self,
        project_id: str,
        claims: list[DefenseClaim],
        outlines: dict[str, list[dict[str, object]]],
        slides: list[SlideStoryboardCard],
        questions: list[DefenseQuestion],
        sources: list[ThesisSource],
    ) -> list[DefenseGapFinding]:
        findings: list[DefenseGapFinding] = []
        now = datetime.now()
        non_risk_claims = [claim for claim in claims if claim.kind is not DefenseClaimKind.RISK_TOPIC]
        by_kind = {claim.kind: claim for claim in non_risk_claims}
        outline_text = " ".join(
            f"{segment.get('title', '')} {segment.get('talking_points', '')}"
            for items in outlines.values()
            for segment in items
        ).lower()
        slide_text = " ".join(f"{slide.title} {slide.purpose} {' '.join(slide.talking_points)}" for slide in slides).lower()

        def add_finding(
            gap_kind: DefenseGapKind,
            severity: float,
            title: str,
            explanation: str,
            evidence_links: list[str],
            related_claim_kinds: list[DefenseClaimKind],
            suggested_fix: str,
        ) -> None:
            finding_id = f"gap-{project_id}-{gap_kind.value}-{sha256((title + explanation).encode('utf-8')).hexdigest()[:8]}"
            findings.append(
                DefenseGapFinding(
                    finding_id=finding_id,
                    project_id=project_id,
                    gap_kind=gap_kind,
                    severity=severity,
                    title=title,
                    explanation=explanation,
                    evidence_links=evidence_links[:3],
                    related_claim_kinds=related_claim_kinds,
                    suggested_fix=suggested_fix,
                    status=DefenseGapStatus.OPEN,
                    llm_assisted=False,
                    created_at=now,
                    updated_at=now,
                )
            )

        for claim in non_risk_claims:
            if not claim.source_anchors:
                add_finding(
                    DefenseGapKind.UNSUPPORTED_CLAIM,
                    0.92,
                    f"{CLAIM_LABELS.get(claim.kind, claim.kind.value)} без опоры в материалах",
                    "Тезис присутствует в dossier, но не привязан ни к одному источнику проекта.",
                    [],
                    [claim.kind],
                    "Привяжите тезис к конкретному месту в материалах или ослабьте формулировку.",
                )
            elif len(claim.source_anchors) == 1 or claim.confidence < 0.6 or claim.needs_review:
                add_finding(
                    DefenseGapKind.WEAK_EVIDENCE,
                    0.68,
                    f"{CLAIM_LABELS.get(claim.kind, claim.kind.value)} подтверждён слабо",
                    "Для тезиса найдена только слабая или одиночная опора, из-за чего его легче оспорить на защите.",
                    claim.source_anchors,
                    [claim.kind],
                    "Добавьте более точную доказательную опору или переформулируйте тезис в более аккуратный вид.",
                )

        novelty_claim = by_kind.get(DefenseClaimKind.NOVELTY)
        if novelty_claim is None or len(novelty_claim.source_anchors) == 0 or novelty_claim.needs_review:
            add_finding(
                DefenseGapKind.NOVELTY_NOT_PROVEN,
                0.9,
                "Новизна не доказана",
                "Блок новизны отсутствует или не имеет внятной опоры в загруженных материалах.",
                novelty_claim.source_anchors if novelty_claim else [],
                [DefenseClaimKind.NOVELTY],
                "Сформулируйте новизну отдельно и подкрепите её конкретными результатами или сравнением с известными подходами.",
            )

        limitations_claim = by_kind.get(DefenseClaimKind.LIMITATIONS)
        if limitations_claim is None:
            add_finding(
                DefenseGapKind.LIMITATIONS_MISSING,
                0.87,
                "Ограничения работы не раскрыты",
                "В материалах защиты не найден отдельный блок ограничений, поэтому комиссия сможет упрекнуть доклад в односторонности.",
                [],
                [DefenseClaimKind.LIMITATIONS],
                "Добавьте 1-2 конкретных ограничения и заранее подготовьте спокойную формулировку ответа на этот блок.",
            )

        results_claim = by_kind.get(DefenseClaimKind.RESULTS)
        if results_claim is not None and self._is_vague_result(results_claim.text):
            add_finding(
                DefenseGapKind.VAGUE_RESULT,
                0.74,
                "Результаты сформулированы расплывчато",
                "Результаты звучат общо и не создают ощущения проверяемого вывода.",
                results_claim.source_anchors,
                [DefenseClaimKind.RESULTS],
                "Сделайте формулировку результатов конкретной: что именно получено, где это видно и почему это важно.",
            )

        methods_claim = by_kind.get(DefenseClaimKind.METHODS)
        if methods_claim is not None and results_claim is not None:
            method_tokens = set(self._keywords(methods_claim.text))
            result_tokens = set(self._keywords(results_claim.text))
            if method_tokens and result_tokens and not (method_tokens & result_tokens):
                add_finding(
                    DefenseGapKind.METHODS_RESULTS_DISCONNECT,
                    0.8,
                    "Методы и результаты выглядят несвязанными",
                    "Из dossier не видно, как выбранные методы приводят именно к заявленным результатам.",
                    list(dict.fromkeys(methods_claim.source_anchors + results_claim.source_anchors)),
                    [DefenseClaimKind.METHODS, DefenseClaimKind.RESULTS],
                    "Добавьте короткий переход от методов к результатам: какой метод что именно позволил показать.",
                )

        for claim_kind in (DefenseClaimKind.RELEVANCE, DefenseClaimKind.METHODS, DefenseClaimKind.RESULTS, DefenseClaimKind.NOVELTY):
            claim = by_kind.get(claim_kind)
            if claim is None:
                continue
            title_lower = CLAIM_LABELS.get(claim.kind, claim.kind.value).lower()
            if title_lower not in outline_text or title_lower not in slide_text:
                add_finding(
                    DefenseGapKind.MISSING_BRIDGE,
                    0.63,
                    f"{CLAIM_LABELS.get(claim.kind, claim.kind.value)} не доведён до доклада и слайдов",
                    "Тезис есть в dossier, но в outline или storyboard он почти не проявлен как отдельный смысловой блок.",
                    claim.source_anchors,
                    [claim.kind],
                    "Проведите этот тезис в outline и хотя бы в один опорный слайд.",
                )

        contradiction = self._detect_contradiction(by_kind)
        if contradiction is not None:
            add_finding(
                DefenseGapKind.CONTRADICTION,
                0.84,
                contradiction["title"],
                contradiction["explanation"],
                contradiction["evidence_links"],
                contradiction["related_claim_kinds"],
                contradiction["suggested_fix"],
            )

        for finding in findings:
            if not finding.evidence_links:
                finding.evidence_links = self._fallback_evidence_for_gap(finding, sources)
        return self._dedupe_gap_findings(findings)

    def _enrich_gap_findings(self, findings: list[DefenseGapFinding], claims: list[DefenseClaim], sources: list[ThesisSource]) -> list[DefenseGapFinding]:
        if not findings:
            return []
        settings = self.settings_store.load()
        service = OllamaService(settings.base_url, None, settings.models_path)
        payload = self._call_llm_json(
            service,
            *defense_gap_enrichment_prompt(
                [self._claim_to_prompt_dict(claim) for claim in claims if claim.kind is not DefenseClaimKind.RISK_TOPIC],
                [
                    {
                        "finding_id": finding.finding_id,
                        "gap_kind": finding.gap_kind.value,
                        "title": finding.title,
                        "explanation": finding.explanation,
                        "evidence_links": finding.evidence_links,
                    }
                    for finding in findings
                ],
            ),
            model=settings.model,
        )
        if not payload or not payload.get("findings"):
            return findings
        by_id = {finding.finding_id: finding for finding in findings}
        for item in payload["findings"]:
            finding_id = str(item.get("finding_id", "")).strip()
            finding = by_id.get(finding_id)
            if finding is None:
                continue
            explanation = str(item.get("explanation", "")).strip()
            suggested_fix = str(item.get("suggested_fix", "")).strip()
            if explanation:
                finding.explanation = explanation
            if suggested_fix:
                finding.suggested_fix = suggested_fix
            finding.llm_assisted = True
            if not finding.evidence_links:
                finding.evidence_links = self._find_anchors(f"{finding.title} {finding.explanation}", sources)
        return findings

    def _build_repair_tasks(
        self,
        project_id: str,
        gap_findings: list[DefenseGapFinding],
        weak_areas: list[DefenseWeakArea],
        followups: list[str],
    ) -> list[DefenseRepairTask]:
        now = datetime.now()
        tasks: list[DefenseRepairTask] = []
        seen: set[str] = set()

        def add_task(
            task_kind: str,
            title: str,
            reason: str,
            source_type: DefenseRepairSourceType,
            related_claim_kind: DefenseClaimKind | None,
            suggested_action: str,
            related_gap_ids: list[str] | None = None,
        ) -> None:
            signature = re.sub(r"\s+", " ", f"{task_kind}|{title}|{related_claim_kind.value if related_claim_kind else ''}").strip().lower()
            if signature in seen:
                return
            seen.add(signature)
            task_id = f"repair-{project_id}-{sha256(signature.encode('utf-8')).hexdigest()[:10]}"
            tasks.append(
                DefenseRepairTask(
                    task_id=task_id,
                    project_id=project_id,
                    task_kind=task_kind,
                    title=title,
                    reason=reason,
                    source_type=source_type,
                    related_claim_kind=related_claim_kind,
                    suggested_action=suggested_action,
                    status=DefenseRepairTaskStatus.TODO,
                    related_gap_ids=related_gap_ids or [],
                    created_at=now,
                    updated_at=now,
                )
            )

        for finding in gap_findings:
            if finding.status not in {DefenseGapStatus.OPEN, DefenseGapStatus.ACCEPTED}:
                continue
            if finding.severity >= 0.7:
                add_task(
                    task_kind=finding.gap_kind.value,
                    title=f"Исправить: {finding.title}",
                    reason=finding.explanation,
                    source_type=DefenseRepairSourceType.GAP,
                    related_claim_kind=finding.related_claim_kinds[0] if finding.related_claim_kinds else None,
                    suggested_action=finding.suggested_fix or "Уточните этот блок и привяжите его к доказательствам.",
                    related_gap_ids=[finding.finding_id],
                )

        for area in weak_areas:
            if area.title in {"Новизна звучит неуверенно", "Ограничения не названы", "Follow-up ответы шаткие", "Методы объяснены неубедительно"}:
                add_task(
                    task_kind=area.kind,
                    title=area.title,
                    reason=area.evidence,
                    source_type=DefenseRepairSourceType.WEAK_AREA,
                    related_claim_kind=area.claim_kind,
                    suggested_action="Подготовьте короткую, уверенную и доказуемую формулировку для этого блока.",
                )

        for question in followups[:3]:
            add_task(
                task_kind="followup_rehearsal",
                title=f"Отрепетировать ответ: {self._compact_text(question, 72)}",
                reason="Follow-up вопрос уже всплыл в репетиции и требует отдельной отработки.",
                source_type=DefenseRepairSourceType.FOLLOWUP,
                related_claim_kind=None,
                suggested_action="Сформулируйте короткий ответ на этот вопрос и привяжите его к конкретному тезису и доказательству.",
            )
        return tasks[:12]

    @staticmethod
    def _estimate_session_duration(answer_text: str, timer_profile_sec: int) -> int:
        word_based = len(re.findall(r"\w+", answer_text)) * 2
        if timer_profile_sec > 0 and word_based < max(30, int(timer_profile_sec * 0.35)):
            return max(word_based, int(timer_profile_sec * 0.55))
        return word_based

    @staticmethod
    def _build_timer_verdict(actual_duration_sec: int, timer_profile_sec: int) -> str:
        if timer_profile_sec <= 0:
            return ""
        delta = actual_duration_sec - timer_profile_sec
        if abs(delta) <= max(20, int(timer_profile_sec * 0.08)):
            return "Тайминг выдержан ровно."
        if delta > 0:
            return f"Доклад выходит за тайминг примерно на {delta} сек."
        return f"Доклад короче тайминга примерно на {abs(delta)} сек."

    @staticmethod
    def _keywords(text: str) -> list[str]:
        return [token.lower() for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9]{5,}", text)[:10]]

    @staticmethod
    def _is_vague_result(text: str) -> bool:
        compact = text.lower()
        generic_markers = ("повышение эффективности", "рекомендации", "улучшение", "оптимизация")
        has_number = bool(re.search(r"\d", compact))
        return len(compact) < 90 or (any(marker in compact for marker in generic_markers) and not has_number)

    def _detect_contradiction(self, by_kind: dict[DefenseClaimKind, DefenseClaim]) -> dict[str, object] | None:
        results = by_kind.get(DefenseClaimKind.RESULTS)
        limitations = by_kind.get(DefenseClaimKind.LIMITATIONS)
        novelty = by_kind.get(DefenseClaimKind.NOVELTY)
        if results and limitations:
            if any(token in limitations.text.lower() for token in ("не удалось", "не получ", "отсутств")) and any(
                token in results.text.lower() for token in ("получ", "доказ", "подтверж", "эффект")
            ):
                return {
                    "title": "Результаты и ограничения звучат противоречиво",
                    "explanation": "В одном месте защита заявляет сильный результат, а в другом формулирует ограничение так, будто результат не был получен.",
                    "evidence_links": list(dict.fromkeys(results.source_anchors + limitations.source_anchors))[:3],
                    "related_claim_kinds": [DefenseClaimKind.RESULTS, DefenseClaimKind.LIMITATIONS],
                    "suggested_fix": "Согласуйте формулировки результатов и ограничений, чтобы ограничение не отменяло сам вывод.",
                }
        if novelty and results and novelty.text.lower() == results.text.lower():
            return {
                "title": "Новизна дублирует результаты",
                "explanation": "Блок новизны повторяет блок результатов и не показывает, в чём именно новое отличие работы.",
                "evidence_links": list(dict.fromkeys(novelty.source_anchors + results.source_anchors))[:3],
                "related_claim_kinds": [DefenseClaimKind.NOVELTY, DefenseClaimKind.RESULTS],
                "suggested_fix": "Разведите новизну и результаты: новизна отвечает на вопрос «что новое», результаты — «что получено».",
            }
        return None

    def _fallback_evidence_for_gap(self, finding: DefenseGapFinding, sources: list[ThesisSource]) -> list[str]:
        query = f"{finding.title} {finding.explanation} {' '.join(kind.value for kind in finding.related_claim_kinds)}"
        return self._find_anchors(query, sources)

    @staticmethod
    def _dedupe_gap_findings(findings: list[DefenseGapFinding]) -> list[DefenseGapFinding]:
        deduped: list[DefenseGapFinding] = []
        seen: set[str] = set()
        for finding in findings:
            signature = f"{finding.gap_kind.value}|{'/'.join(kind.value for kind in finding.related_claim_kinds)}|{finding.title}".lower()
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(finding)
        return deduped

    @staticmethod
    def _match_related_gap_ids(
        gap_findings: list[DefenseGapFinding],
        weak_areas: list[DefenseWeakArea],
        followups: list[str],
    ) -> list[str]:
        related: list[str] = []
        followup_blob = " ".join(followups).lower()
        weak_claim_kinds = {area.claim_kind for area in weak_areas if area.claim_kind is not None}
        for finding in gap_findings:
            if weak_claim_kinds.intersection(finding.related_claim_kinds):
                related.append(finding.finding_id)
                continue
            if any(kind.value.replace("_", " ") in followup_blob for kind in finding.related_claim_kinds):
                related.append(finding.finding_id)
        return related[:5]
