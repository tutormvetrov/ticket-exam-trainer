"""Fill the 15 empty answer blocks in the AI course (GMU-copied tickets
where the original GMU block was is_missing=1). Targets matched by
(section title, ticket title, block code); updates expected_content in
place without regenerating ticket_ids.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DB = REPO_ROOT / "data" / "state_exam_public_admin_demo.db"

# (section_title_prefix, ticket_title_prefix, block_code, content)
PATCHES: list[tuple[str, str, str, str, str]] = [
    (
        "Философия", "История, культура, цивилизация", "extra", "Дополнительные элементы",
        "Сравнительный анализ концепций цивилизации: формационный подход (Маркс — стадии общественно-экономических формаций) vs цивилизационный (Данилевский, Шпенглер, Тойнби, Хантингтон — локальные культурно-исторические типы). Междисциплинарные связи: история (всемирная и отечественная), культурология (семиотика культуры — Лотман), социология (теория модернизации — Parsons), антропология. Визуализация: карта цивилизаций Хантингтона; пирамида элементов цивилизации (материальная → институциональная → ценностная)."
    ),
    (
        "Философия", "Онтология и теория познания", "extra", "Дополнительные элементы",
        "Сравнительный анализ онтологических систем: материализм (Демокрит, Маркс), идеализм объективный (Платон, Гегель), идеализм субъективный (Беркли), дуализм (Декарт). Теория познания: эмпиризм (Локк, Юм), рационализм (Декарт, Лейбниц), трансцендентальная философия (Кант — синтез). Междисциплинарные связи: физика (quantum mechanics — проблемы наблюдателя), когнитивная психология, нейронаука. Визуализация: картография философских направлений; Кантовская схема синтеза a priori и a posteriori."
    ),
    (
        "Философия", "Философия, её роль в жизни человека и общества", "extra", "Дополнительные элементы",
        "Сравнительный анализ функций философии: мировоззренческая (формирование целостной картины мира), методологическая (общие методы познания), критическая (рефлексия оснований), прогностическая (futures thinking). Философские школы: античная (Платон, Аристотель), средневековая (Августин, Фома), новое время (Декарт, Кант, Гегель), современная (Хайдеггер, Витгенштейн, Гуссерль). Междисциплинарные связи: наука (philosophy of science), этика (moral philosophy), политика (political philosophy). Визуализация: дерево философских направлений; функции философии (4-5 ролей)."
    ),
    (
        "Экономика общественного сектора", "Формирование спроса и предложения общественных и с", "extra", "Дополнительные элементы",
        "Сравнительный анализ: общественные блага (non-rivalry + non-excludability — оборона, маяки) vs частные блага (rivalry + excludability — еда) vs clubblags (non-rivalry + excludability — подписки) vs общие блага (rivalry + non-excludability — рыба в океане). Теория free-rider (Олсон «Логика коллективных действий»). Междисциплинарные связи: микроэкономика, политическая экономия, теория общественного выбора (Бьюкенен). Визуализация: таблица 2×2 типов благ; spectrum публичности благ."
    ),
    (
        "Экономика общественного сектора", "Формирование спроса и предложения общественных и с", "skills", "Навыки",
        "Навыки анализа общественных благ: идентификация характеристик блага (rivalry/excludability), расчёт оптимального уровня предоставления (условие Самуэльсона: сумма MRS = MC), применение теории общественного выбора для анализа политических решений о финансировании. Работа с эмпирической оценкой спроса на общественные блага (contingent valuation, revealed preference). Владение терминологией: public goods, club goods, common goods, free-rider problem, MRS (Marginal Rate of Substitution), Samuelson condition, contingent valuation."
    ),
    (
        "Теория и механизмы современного государс", "Искусственный интеллект в государственном управлен", "extra", "Дополнительные элементы",
        "Сравнительный анализ AI-стратегий: США (OpenAI, частный сектор), Китай (national champions, Made in China 2025), ЕС (EU AI Act + EU AI Factory), РФ (Национальная стратегия AI до 2030, отечественные LLM). Ключевые документы РФ: Указ Президента № 490 (2019), Распоряжение Правительства № 2129-р (2020), обновление Стратегии 2024. Междисциплинарные связи: computer science, public administration, ethics, law. Визуализация: AI readiness index стран; architecture AI-enabled government."
    ),
    (
        "Теория и механизмы современного государс", "Современные теории государственного управления", "extra", "Дополнительные элементы",
        "Сравнительный анализ современных теорий госуправления: New Public Management (NPM, Thatcher 1980s — рыночные методы), New Public Governance (NPG, Osborne 2006 — сетевое), Digital-Era Governance (DEG, Dunleavy 2005 — цифровизация), Post-NPM trends, Whole-of-Government approach. Российская традиция: школа Атаманчука, Глазунова, Соловьёва. Междисциплинарные связи: политология (теория государства), менеджмент, социология управления, информатика. Визуализация: эволюция парадигм госуправления (Weber → NPM → NPG → Digital)."
    ),
    (
        "Правовое обеспечение государственного и ", "Методология подготовки нормативно-правовых актов в", "extra", "Дополнительные элементы",
        "Сравнительный анализ методологий законопроектной работы: континентальная европейская (Германия, Франция — системность, кодификация) vs англо-американская (case law, инкрементализм). Инструменты: regulation.gov.ru (общественные обсуждения в РФ), ОРВ (оценка регулирующего воздействия), ОФВ (оценка фактического воздействия). Междисциплинарные связи: теория государства и права, административное право, юридическая техника (Керимов, Тихомиров). Визуализация: lifecycle НПА от концепции до отмены; матрица стейкхолдеров законопроекта."
    ),
    (
        "Информационно-аналитические технологии в", "Информационно-аналитические системы в управлении", "extra", "Дополнительные элементы",
        "Сравнительный анализ классов ИАС: DSS (Decision Support Systems), EIS (Executive Information Systems), BI (Business Intelligence), DWH (Data Warehouse), Data Lake. Архитектуры: ETL vs ELT, star schema vs snowflake, lakehouse (Databricks, Iceberg). Отечественные ИАС: ГАС «Управление» (federal уровень), региональные ситуационные центры (88 СЦ в РФ). Междисциплинарные связи: computer science, statistics, management. Визуализация: иерархия ИАС по уровню управления (operational → tactical → strategic); архитектура DSS."
    ),
    (
        "Кадровая политика и кадровый аудит", "Кадровое обеспечение управленческой деятельности", "extra", "Дополнительные элементы",
        "Сравнительный анализ моделей кадрового обеспечения госслужбы: система заслуг (merit system, US, UK, Германия) vs система покровительства (spoils system, политические назначения), позиционная vs карьерная модель. Российская модель — гибридная карьерно-позиционная. НПА РФ: ФЗ № 79 «О гражданской службе», Указ Президента № 261 о федеральной программе «Реформирование и развитие системы государственной службы». Междисциплинарные связи: HR-менеджмент, трудовое право, социология профессий. Визуализация: модели комплектования госслужбы; lifecycle кадрового обеспечения."
    ),
    (
        "Публичные и деловые коммуникации (на ино", "Наука и научный стиль", "extra", "Дополнительные элементы",
        "Сравнительный анализ функциональных стилей: научный (объективность, точность, терминированность, абстрактность, логичность) vs публицистический vs деловой vs художественный vs разговорный. Подстили научного стиля: академический (монографии, статьи), учебно-научный (учебники), научно-популярный (популяризация), научно-деловой (патенты, стандарты). Междисциплинарные связи: лингвистика (функциональная стилистика — Виноградов, Кожина), риторика, науковедение. Визуализация: спектр функциональных стилей; черты научного стиля."
    ),
    (
        "Публичные и деловые коммуникации (на ино", "Технология продуцирования письменной научной речи.", "extra", "Дополнительные элементы",
        "Сравнительный анализ жанров научной письменной речи: статья (оригинальное исследование), обзор (литературный анализ), эссе (personal argumentation), аннотация (compressed summary), тезисы (краткая форма доклада), отзыв/рецензия (критический анализ). Международные стандарты: IMRAD (Introduction-Methods-Results-Discussion) для empirical papers, APA/MLA citation styles. Междисциплинарные связи: лингвистика текста, научная коммуникация, information literacy. Визуализация: structure IMRAD article; writing process (invention → drafting → revision)."
    ),
    (
        "Программное и проектное управление в гос", "Проекты – инструменты реализации масштабной задачи", "extra", "Дополнительные элементы",
        "Сравнительный анализ подходов к проектному управлению: waterfall (PMI PMBOK — классический, плановый), Agile/Scrum (итеративный, гибкий), PRINCE2 (UK government standard), IPMA (European). Особенности в ГМУ: регулятивные ограничения vs гибкость, длительный lifecycle, множество стейкхолдеров. Отечественные стандарты: ГОСТ Р 54869-2011 «Проектный менеджмент», ФЗ-172 о стратегическом планировании. Междисциплинарные связи: менеджмент, проектирование, risk management, управление изменениями. Визуализация: waterfall vs Agile; triple constraint треугольник (scope-time-cost)."
    ),
    (
        "Программное и проектное управление в гос", "Разработка, организация и реализация проектов (про", "extra", "Дополнительные элементы",
        "Сравнительный анализ фаз жизненного цикла проекта (PMBOK): 1) Initiation (charter, stakeholders); 2) Planning (scope, schedule, budget, risk); 3) Execution (deliverables); 4) Monitoring&Controlling; 5) Closing. Отечественная практика нацпроектов РФ: проектные офисы при Правительстве, федеральные/региональные PMOs. Инструменты: MS Project, Jira (для госкомпаний переход на 1С:Документооборот, Битрикс24). Междисциплинарные связи: operations management, risk management, strategic planning. Визуализация: PMBOK phases; RACI matrix для распределения ролей."
    ),
    (
        "Программное и проектное управление в гос", "Разработка, организация и реализация проектов (про", "skills", "Навыки",
        "Навыки реализации проекта: разработка устава проекта (Project Charter), WBS (Work Breakdown Structure), сетевой график (Gantt, PERT), управление рисками (risk register, PI matrix), контроль бюджета (EVM — Earned Value Management), управление изменениями (change control). Работа с инструментами: MS Project, Яндекс Трекер, Bitrix24. Владение терминологией: Project Charter, WBS, Gantt chart, critical path, EVM, risk register, change control board, RACI matrix, stakeholder engagement plan, PMBOK, PRINCE2."
    ),
]


def _match_title(db_title: str, prefix: str) -> bool:
    return db_title.startswith(prefix)


def main() -> int:
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    patched = 0
    for sec_prefix, tkt_prefix, block_code, block_title, content in PATCHES:
        cur = con.cursor()
        rows = list(cur.execute(
            """
            SELECT b.rowid as rid, t.title, s.title as s_title
              FROM ticket_answer_blocks b
              JOIN tickets t ON b.ticket_id=t.ticket_id
              JOIN sections s ON t.section_id=s.section_id
             WHERE t.exam_id='exam-state-mde-ai-2024'
               AND s.title LIKE ?
               AND t.title LIKE ?
               AND b.block_code=?
               AND length(b.expected_content) < 100
            """,
            (sec_prefix + "%", tkt_prefix + "%", block_code),
        ))
        for r in rows:
            cur.execute(
                """UPDATE ticket_answer_blocks
                      SET title=?, expected_content=?, is_missing=0, llm_assisted=1, confidence=1.0
                    WHERE rowid=?""",
                (block_title, content.strip(), r["rid"]),
            )
            patched += 1
            print(f"  patched: {r['s_title'][:30]} | {r['title'][:40]} | {block_code}")
    con.commit()
    print(f"Total patched: {patched}")
    # Final check
    remaining = con.execute(
        """SELECT COUNT(*) FROM ticket_answer_blocks b
             JOIN tickets t ON b.ticket_id=t.ticket_id
            WHERE t.exam_id='exam-state-mde-ai-2024'
              AND length(b.expected_content) < 100"""
    ).fetchone()[0]
    total = con.execute(
        """SELECT COUNT(*) FROM ticket_answer_blocks b
             JOIN tickets t ON b.ticket_id=t.ticket_id
            WHERE t.exam_id='exam-state-mde-ai-2024'"""
    ).fetchone()[0]
    print(f"Remaining empty: {remaining} / {total}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
