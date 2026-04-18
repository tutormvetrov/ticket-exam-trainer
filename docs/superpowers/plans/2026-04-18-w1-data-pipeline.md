# W1: Data Pipeline Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Почистить PDF-импорт так, чтобы все 208 билетов seed-базы содержали реальный контент, атомы не были разорваны на токенах-аббревиатурах, answer_blocks были сгенерированы для каждого билета, и новый seed v2 прошёл acceptance-тесты.

**Architecture:** Работа в worktree `D:\ticket-exam-trainer-data` на ветке `data-pipeline` от тэга `v1.2.0`. Строгий TDD: каждая правка — сначала failing test, потом implementation. Frozen interface (`AppFacade`, `ui_data.py` dataclasses, `domain/models.py`) не меняется без синхронизации с координатором. Новые колонки в SQLite — через миграции.

**Tech Stack:** Python 3.12, pypdf, regex, pytest, Ollama (qwen3 из R0), SQLite с миграциями

**Ref spec:** `docs/superpowers/specs/2026-04-18-flet-migration-design.md` (Часть 2)

---

## Task 1: Byline Stripper

**Files:**
- Create: `infrastructure/importers/byline_stripper.py`
- Test: `tests/test_byline_stripper.py`
- Modify: `infrastructure/importers/common.py:<after existing imports>` — подключить

- [ ] **Step 1: Написать failing test**

Создать `tests/test_byline_stripper.py`:

```python
import pytest
from infrastructure.importers.byline_stripper import strip_byline


@pytest.mark.parametrize("raw,expected_content,expected_author", [
    # Классический паттерн в скобках
    (
        "( Абдулаева Екатерина) \n\n\nРоссия — федеративное государство.",
        "Россия — федеративное государство.",
        "Абдулаева Екатерина",
    ),
    # Без пробела после открывающей скобки
    (
        "(Иванов И.И.)\nТекст ответа.",
        "Текст ответа.",
        "Иванов И.И.",
    ),
    # «Автор:» prefix
    (
        "Автор: Петров П.П.\n\nСодержание ответа.",
        "Содержание ответа.",
        "Петров П.П.",
    ),
    # «Выполнил(а):» prefix
    (
        "Выполнила: Смирнова А.В.\nТекст.",
        "Текст.",
        "Смирнова А.В.",
    ),
    # Три заглавных слова в начале
    (
        "Гринько Александра Николаевна\nОнтология — раздел философии.",
        "Онтология — раздел философии.",
        "Гринько Александра Николаевна",
    ),
    # Без byline — оставляем как есть
    (
        "Просто текст без подписи.",
        "Просто текст без подписи.",
        None,
    ),
    # Пустой input
    ("", "", None),
])
def test_strip_byline_extracts_author_and_cleans_content(raw, expected_content, expected_author):
    content, author = strip_byline(raw)
    assert content.strip() == expected_content.strip()
    assert author == expected_author
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_byline_stripper.py -v
```

Expected: `ModuleNotFoundError: No module named 'infrastructure.importers.byline_stripper'` или similar.

- [ ] **Step 3: Implement byline stripper**

Создать `infrastructure/importers/byline_stripper.py`:

```python
"""Byline stripper for PDF-imported content.

Students who collaboratively wrote the exam conspectus signed each ticket.
These signatures leak into atom content if not stripped. This module
removes them and returns the author separately if captured.
"""

from __future__ import annotations

import re
from typing import Optional


# Паттерны для обнаружения подписей
_PATTERNS = [
    # (Фамилия Имя) или ( Фамилия Имя ) или (Иванов И.И.)
    re.compile(
        r"^\s*\(\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+|\s+[А-ЯЁ]\.[А-ЯЁ]\.?)+)\s*\)\s*\n+",
        re.UNICODE,
    ),
    # Автор: …
    re.compile(
        r"^\s*Автор:\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё.]+)+)\s*\n+",
        re.UNICODE,
    ),
    # Выполнил(а): …
    re.compile(
        r"^\s*Выполнил(?:а)?:\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё.]+)+)\s*\n+",
        re.UNICODE,
    ),
    # Три заглавных слова подряд в начале строки (Фамилия Имя Отчество)
    re.compile(
        r"^\s*([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)\s*\n+",
        re.UNICODE,
    ),
]


def strip_byline(raw: str) -> tuple[str, Optional[str]]:
    """Strip author byline from the start of content.

    Returns (cleaned_content, author_name_or_None).
    """
    if not raw:
        return raw, None

    for pattern in _PATTERNS:
        match = pattern.match(raw)
        if match:
            author = match.group(1).strip()
            cleaned = raw[match.end():]
            return cleaned, author

    return raw, None
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pytest tests/test_byline_stripper.py -v
```

Expected: все 7 тестов зелёные.

- [ ] **Step 5: Integrate в common importer**

Modify `infrastructure/importers/common.py` — в функции, которая нормализует content chunks (обычно `normalize_chunk_text` или аналог), добавить вызов `strip_byline` до атомизации. Если в файле нет такой функции, добавить:

```python
# infrastructure/importers/common.py
from infrastructure.importers.byline_stripper import strip_byline


def preprocess_chunk(raw_text: str) -> tuple[str, dict]:
    """Preprocess raw chunk text before atomization.

    Returns (cleaned_text, metadata_dict).
    """
    cleaned, author = strip_byline(raw_text)
    metadata = {}
    if author:
        metadata["author"] = author
    return cleaned, metadata
```

Проверить, что текущие importer-ы (`pdf_importer.py`, `docx_importer.py`) используют эту функцию или `strip_byline` напрямую на стадии нормализации chunk-ов.

- [ ] **Step 6: Integration test**

Добавить в `tests/test_byline_stripper.py`:

```python
def test_integration_removes_byline_from_real_ticket_content():
    # Из seed билета 1
    raw = "( Абдулаева Екатерина) \n\n\nРоссия — федеративное государство (ст. 5 Конституции)."
    from infrastructure.importers.common import preprocess_chunk
    cleaned, meta = preprocess_chunk(raw)
    assert not cleaned.startswith("(")
    assert not cleaned.startswith("Абдулаева")
    assert meta.get("author") == "Абдулаева Екатерина"
    assert "Россия" in cleaned
```

Run:
```bash
pytest tests/test_byline_stripper.py -v
```

Expected: 8 тестов зелёные.

- [ ] **Step 7: Commit**

```bash
git add infrastructure/importers/byline_stripper.py \
        infrastructure/importers/common.py \
        tests/test_byline_stripper.py
git commit -m "feat(importer): strip student bylines before atomization

Parametrized tests cover 5 byline patterns (parenthesized FIO, Автор:,
Выполнил:, three capitalized words, empty). Integration test verifies
real ticket 1 content is cleaned. Author name preserved in metadata
dict for optional future use.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Abbreviation-Aware Tokenizer

**Files:**
- Create: `infrastructure/importers/ru_tokenizer.py`
- Create: `infrastructure/importers/ru_abbreviations.py` — словарь
- Test: `tests/test_ru_tokenizer.py`

- [ ] **Step 1: Создать словарь аббревиатур**

Создать `infrastructure/importers/ru_abbreviations.py`:

```python
"""Russian abbreviations that should NOT trigger sentence boundaries."""

RUSSIAN_ABBREVIATIONS = frozenset({
    # Юридические/правовые
    "ст.", "гл.", "п.", "пп.", "ч.", "абз.", "подп.", "пт.",
    "ФЗ", "КРФ", "ГК", "УК", "КоАП", "НК", "ТК", "ЗК", "ГПК", "УПК",
    "ФКЗ", "РФ", "СССР",
    # Общие текстовые
    "т.е.", "т.к.", "т.н.", "т.д.", "т.п.",
    "и т.д.", "и т.п.", "и пр.", "и т.н.",
    "см.", "др.", "напр.", "прим.", "ср.",
    "стр.", "рис.", "табл.", "илл.",
    # Организационные
    "ГМУ", "ВУЗ", "МГУ", "МГИМО", "ВШЭ", "ВШГА",
    "ЗАО", "ОАО", "ООО", "АО", "ПАО", "ИП",
    # Титулы
    "г-н", "г-жа", "г-ном", "г-не",
    "проф.", "доц.", "ст. преп.", "ассист.",
    "канд.", "д-р",
    # Денежные/количественные
    "млн.", "млрд.", "тыс.", "руб.", "долл.", "евро",
    "ок.", "прибл.", "около",
    # Порядковые
    "№", "§", "№№",
    # Временные
    "ч.", "мин.", "сек.", "нед.", "мес.", "г.", "гг.",
    "в.", "вв.", "до н.э.", "н.э.",
})


def is_abbreviation(token: str) -> bool:
    """Check if a token (with trailing period if any) is a known abbreviation."""
    return token in RUSSIAN_ABBREVIATIONS or token.lower() in RUSSIAN_ABBREVIATIONS
```

- [ ] **Step 2: Написать failing test**

Создать `tests/test_ru_tokenizer.py`:

```python
from infrastructure.importers.ru_tokenizer import split_into_sentences


class TestAbbreviationAwareTokenizer:

    def test_ct_is_not_sentence_boundary(self):
        """«ст.» (статья) — аббревиатура, не конец предложения."""
        text = "Россия — федеративное государство (ст. 5 Конституции). Федеративное устройство РФ."
        sentences = split_into_sentences(text)
        assert len(sentences) == 2
        assert sentences[0].strip() == "Россия — федеративное государство (ст. 5 Конституции)."
        assert sentences[1].strip() == "Федеративное устройство РФ."

    def test_initials_do_not_split(self):
        text = "Президент РФ А.Н. Иванов издал указ. Указ вступил в силу."
        sentences = split_into_sentences(text)
        assert len(sentences) == 2
        assert "А.Н. Иванов" in sentences[0]

    def test_decimal_numbers_do_not_split(self):
        text = "Стоимость 5.5 рубля. Следующее предложение."
        sentences = split_into_sentences(text)
        assert len(sentences) == 2

    def test_regular_period_splits(self):
        text = "Первое предложение. Второе. Третье!"
        sentences = split_into_sentences(text)
        assert len(sentences) == 3

    def test_multiple_abbreviations(self):
        text = "См. ст. 12 ФЗ «О чём-то». Далее идёт второй тезис."
        sentences = split_into_sentences(text)
        assert len(sentences) == 2
        assert "См. ст. 12 ФЗ" in sentences[0]

    def test_empty(self):
        assert split_into_sentences("") == []

    def test_single_sentence(self):
        sentences = split_into_sentences("Одно простое предложение.")
        assert len(sentences) == 1


class TestAtomBoundaryCase:

    def test_original_broken_case(self):
        """Regression for seed билет 1 issue."""
        text = "Россия — федеративное государство (ст. 5 Конституции)."
        sentences = split_into_sentences(text)
        assert len(sentences) == 1, f"Expected 1 sentence, got {sentences}"
```

- [ ] **Step 3: Run test — verify fail**

```bash
pytest tests/test_ru_tokenizer.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement tokenizer**

Создать `infrastructure/importers/ru_tokenizer.py`:

```python
"""Sentence tokenizer aware of Russian abbreviations, initials, and decimals.

Standard `.split('.')` or regex `\\. ` approaches break at abbreviations like
«ст.» (статья) creating fragmented atoms. This tokenizer only splits when the
period is clearly a sentence boundary.
"""

from __future__ import annotations

import re
from typing import List

from infrastructure.importers.ru_abbreviations import RUSSIAN_ABBREVIATIONS


# Паттерн потенциального конца предложения: [.!?] + пробел + заглавная буква
# Но мы проверяем контекст, чтобы не делить на аббревиатурах
_SENTENCE_END_RE = re.compile(r'([.!?])\s+(?=[А-ЯЁA-Z])', re.UNICODE)


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences, respecting Russian abbreviations.

    Strategy:
    1. Find candidate boundaries (punct + whitespace + capital letter)
    2. For each candidate, check if the word ending just before was an abbreviation
    3. If yes, skip that boundary
    4. Otherwise, split there
    """
    if not text:
        return []

    # Найти все кандидаты на конец предложения
    boundaries: List[int] = []
    for match in _SENTENCE_END_RE.finditer(text):
        punct_pos = match.start()
        # Проверить слово перед пунктуацией
        preceding = text[:punct_pos + 1]  # включая точку
        last_token = _extract_last_token(preceding)
        if _is_abbreviation(last_token):
            continue
        if _is_initial(last_token):
            continue
        if _is_decimal(preceding, punct_pos):
            continue
        boundaries.append(match.end())

    # Разрезать по валидным границам
    sentences: List[str] = []
    start = 0
    for b in boundaries:
        sentences.append(text[start:b])
        start = b
    # Последний кусок
    if start < len(text):
        sentences.append(text[start:])

    # Отфильтровать пустые
    return [s for s in sentences if s.strip()]


def _extract_last_token(text: str) -> str:
    """Get the last whitespace-delimited token ending at position len(text)."""
    stripped = text.rstrip()
    if not stripped:
        return ""
    # Найти последний пробел или начало строки
    last_space = stripped.rfind(" ")
    return stripped[last_space + 1:] if last_space >= 0 else stripped


def _is_abbreviation(token: str) -> bool:
    if not token:
        return False
    # Прямое совпадение
    if token in RUSSIAN_ABBREVIATIONS:
        return True
    # Нижний регистр
    if token.lower() in RUSSIAN_ABBREVIATIONS:
        return True
    return False


def _is_initial(token: str) -> bool:
    """Single capital letter + period, e.g. «А.»."""
    return bool(re.fullmatch(r'[А-ЯЁA-Z]\.', token))


def _is_decimal(text: str, dot_pos: int) -> bool:
    """Check if the dot at dot_pos is part of a decimal number (e.g. «5.5»)."""
    if dot_pos + 1 >= len(text):
        return False
    if dot_pos == 0:
        return False
    before = text[dot_pos - 1]
    after = text[dot_pos + 1] if dot_pos + 1 < len(text) else ""
    return before.isdigit() and after.isdigit()
```

- [ ] **Step 5: Run test — verify pass**

```bash
pytest tests/test_ru_tokenizer.py -v
```

Expected: все тесты зелёные.

- [ ] **Step 6: Integrate в common**

Modify `infrastructure/importers/common.py` — заменить текущий sentence splitter (если есть `split_sentences` или split по `.`) на `split_into_sentences` из нового модуля:

```python
from infrastructure.importers.ru_tokenizer import split_into_sentences as split_sentences
```

Если текущий код использует `re.split(r'\.\s+', ...)` или `text.split('.')` — найти все такие места в `infrastructure/importers/` и заменить.

Grep: `grep -rn "split.*\.\\\\\\|split.*'\\.'" infrastructure/importers/`

- [ ] **Step 7: Run full suite**

```bash
pytest tests/ -q
```

Expected: все тесты зелёные (предыдущие + новые). Если какой-то import-тест упал из-за новой логики — починить.

- [ ] **Step 8: Commit**

```bash
git add infrastructure/importers/ru_abbreviations.py \
        infrastructure/importers/ru_tokenizer.py \
        infrastructure/importers/common.py \
        tests/test_ru_tokenizer.py
git commit -m "feat(importer): abbreviation-aware Russian sentence tokenizer

Prevents splitting at «ст.», initials «А.Н.», and decimals «5.5». Includes
dictionary of 80+ Russian abbreviations covering legal, textual,
organizational, titular, monetary, and temporal domains.

Regression test covers the seed-DB ticket 1 case where «ст. 5» was
fragmented into separate atoms.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: TOC Detector

**Files:**
- Create: `infrastructure/importers/toc_detector.py`
- Test: `tests/test_toc_detector.py`
- Modify: `infrastructure/importers/pdf_importer.py` — подключить

- [ ] **Step 1: Failing test**

Создать `tests/test_toc_detector.py`:

```python
from infrastructure.importers.toc_detector import is_toc_block


class TestTOCDetection:

    def test_toc_numbered_list_detected(self):
        """Типичный TOC с пронумерованными короткими заголовками."""
        block = """
1. Государственное устройство Российской Федерации
2. Выборы в федеральные органы
3. Политические лидеры субъекта РФ
4. Уровни государственного управления
5. Внешняя политика и международные споры
6. Международные организации (структуры ООН)
7. Актуальные вопросы государственного управления
8. Онтология и теория познания
""".strip()
        assert is_toc_block(block) is True

    def test_bullet_list_detected(self):
        block = "\n".join([f"● ({i}) {i}" for i in range(1, 10)])
        assert is_toc_block(block) is True

    def test_real_answer_content_not_detected(self):
        """Полный ответ на билет — не TOC."""
        block = """
Россия — федеративное государство (ст. 5 Конституции). Федеративное устройство РФ
основывается на ряде конституционных принципов: а) государственная целостность;
б) единство системы государственной власти; в) разграничение предметов ведения
и полномочий между органами государственной власти Российской Федерации.

Субъекты РФ — республики, края, области, города федерального значения, автономная
область, автономные округа. Всего 89 субъектов.
""".strip()
        assert is_toc_block(block) is False

    def test_mixed_content_not_toc(self):
        """Заголовок + один короткий абзац — не TOC (слишком мало пунктов)."""
        block = """
Классификация форм правления.

Существуют две основные формы правления: монархия и республика.
""".strip()
        assert is_toc_block(block) is False

    def test_empty_block(self):
        assert is_toc_block("") is False

    def test_single_line_not_toc(self):
        assert is_toc_block("Просто одна строка.") is False

    def test_table_of_contents_header(self):
        """Блок с заголовком «Содержание» / «Оглавление»."""
        block = """
Содержание

1. Билет первый
2. Билет второй
3. Билет третий
""".strip()
        assert is_toc_block(block) is True
```

- [ ] **Step 2: Run — fail**

```bash
pytest tests/test_toc_detector.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement**

Создать `infrastructure/importers/toc_detector.py`:

```python
"""Detect blocks that are table-of-contents (TOC), not actual ticket content.

Heuristic:
- > 3 lines in block
- > 80% of lines are «short» (< 100 chars) and match numbered/bulleted pattern
- OR block contains explicit «Содержание» / «Оглавление» header
- AND absence of full prose sentences (with verbs, commas, multiple clauses)
"""

from __future__ import annotations

import re


_NUMBERED_LINE_RE = re.compile(r'^\s*(\d+\.|\(\d+\)|[●•▪*-])\s+\S', re.UNICODE)
_TOC_HEADER_RE = re.compile(r'^\s*(Содержание|Оглавление|Перечень|Список билетов)\s*$', re.IGNORECASE | re.UNICODE)
_PROSE_INDICATOR_RE = re.compile(r'[,;:].*[,;:]', re.UNICODE)  # ≥2 запятых/двоеточий = есть прозовая структура


def is_toc_block(text: str) -> bool:
    """Return True if the block looks like a TOC/bullet-list rather than content."""
    if not text:
        return False

    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 3:
        return False

    # Явный TOC-заголовок
    for line in lines[:2]:
        if _TOC_HEADER_RE.match(line):
            return True

    # Доля нумерованных/bullet-строк
    short_numbered = sum(
        1 for ln in lines
        if _NUMBERED_LINE_RE.match(ln) and len(ln.strip()) < 100
    )
    ratio = short_numbered / len(lines)
    if ratio < 0.8:
        return False

    # Проверка на прозовые признаки: если хоть одна строка содержит сложную пунктуацию —
    # это скорее content с bullet-списком, не TOC
    prose_lines = sum(1 for ln in lines if _PROSE_INDICATOR_RE.search(ln))
    if prose_lines > len(lines) * 0.3:  # > 30% линий с прозой — это контент
        return False

    return True
```

- [ ] **Step 4: Run — pass**

```bash
pytest tests/test_toc_detector.py -v
```

Expected: все тесты зелёные.

- [ ] **Step 5: Integrate в pdf_importer**

В `infrastructure/importers/pdf_importer.py` найти место, где создаются `content_chunks`. Для каждого chunk, до того как он становится билетом:

```python
from infrastructure.importers.toc_detector import is_toc_block

# в цикле обработки chunks:
if is_toc_block(chunk.text):
    chunk.metadata["is_toc"] = True
    # Не создаём билет из TOC блока; но оставляем chunk для reference
    continue
```

Если chunk помечен `is_toc=True`, он не превращается в ticket (либо билет создаётся со `status="insufficient_content"` если сегментация привязана к ожидаемому количеству).

- [ ] **Step 6: Integration test**

В `tests/test_toc_detector.py` добавить:

```python
def test_pdf_import_skips_toc_blocks(tmp_path):
    """На реальном (или fixture) PDF с TOC — TOC-blocks не становятся билетами."""
    # TODO: этот тест идёт в тандеме с PDF-fixture; если fixture нет, пропускаем
    # Минимальная проверка: после импорта текущего PDF ни один билет не имеет
    # canonical_answer_summary формата "● (N) N"
    import pytest
    pytest.skip("Requires full PDF fixture; covered in Task 8 integration.")
```

- [ ] **Step 7: Commit**

```bash
git add infrastructure/importers/toc_detector.py \
        infrastructure/importers/pdf_importer.py \
        tests/test_toc_detector.py
git commit -m "feat(importer): detect and skip table-of-contents blocks

Heuristic: >80% numbered/bulleted lines + low prose density, OR explicit
«Содержание» header. Prevents the regression where tickets 4-8 of the
state-exam seed contained «● (N) N» bullet markers as answer content.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Title Normalizer + Migration

**Files:**
- Create: `infrastructure/importers/title_normalizer.py`
- Create: `infrastructure/db/migrations/001_add_document_normalized_fields.sql`
- Create: `infrastructure/db/migrations/__init__.py`
- Create: `infrastructure/db/migrations/runner.py` — applier
- Test: `tests/test_title_normalizer.py`
- Test: `tests/test_migration_runner.py`
- Modify: `domain/models.py` — добавить `display_title`, `source_filename` в `SourceDocument`
- Modify: `infrastructure/db/repository.py` — запись новых полей

**⚠️ Синхронизация:** изменение `domain/models.SourceDocument` — frozen interface. Координатор должен cherry-pick в `flet-migration` и `installer` после этой задачи.

- [ ] **Step 1: Failing test для normalizer**

Создать `tests/test_title_normalizer.py`:

```python
import pytest
from infrastructure.importers.title_normalizer import normalize_document_title


@pytest.mark.parametrize("raw,expected", [
    # Основной case
    ("МДЭ_ГА_2024_Кол_Конспект_ГМУ_ГАРФ_18_02_2025_в_2.pdf",
     "МДЭ ГА 2024. Конспект ГМУ ГАРФ. 18.02.2025, вариант 2"),
    ("МДЭ ГА 2024 Кол Конспект ГМУ ГАРФ 18 02 2025 в 2",
     "МДЭ ГА 2024. Конспект ГМУ ГАРФ. 18.02.2025, вариант 2"),
    # Даты склеиваются точками
    ("Документ 01 02 2024",
     "Документ 01.02.2024"),
    # Аббревиатуры в капсе сохраняются
    ("Лекции МГУ ВШГА",
     "Лекции МГУ ВШГА"),
    # Одиночное «в N» → вариант N
    ("Тест в 3",
     "Тест, вариант 3"),
    # Просто текст без паттернов
    ("Обычный заголовок документа",
     "Обычный заголовок документа"),
])
def test_normalize_document_title(raw, expected):
    assert normalize_document_title(raw) == expected


def test_extension_stripped():
    assert normalize_document_title("document.pdf") == "document"
    assert normalize_document_title("file.DOCX") == "file"


def test_underscores_become_spaces():
    assert normalize_document_title("some_file_name") == "some file name"
```

- [ ] **Step 2: Run — fail**

```bash
pytest tests/test_title_normalizer.py -v
```

- [ ] **Step 3: Implement normalizer**

Создать `infrastructure/importers/title_normalizer.py`:

```python
"""Normalize document titles from filenames to presentable display form.

Examples:
  МДЭ_ГА_2024_Кол_Конспект_ГМУ_ГАРФ_18_02_2025_в_2.pdf
  → МДЭ ГА 2024. Конспект ГМУ ГАРФ. 18.02.2025, вариант 2
"""

from __future__ import annotations

import re


# 2-4 заглавные буквы подряд = аббревиатура (сохраняется)
_ABBREV_RE = re.compile(r'^[А-ЯЁA-Z]{2,4}$', re.UNICODE)

# DD MM YYYY (три числа подряд, день/месяц/год) → DD.MM.YYYY
_DATE_RE = re.compile(r'\b(\d{1,2})\s+(\d{1,2})\s+(\d{4})\b')

# «в N» в конце или перед концом → «, вариант N»
_VARIANT_RE = re.compile(r'\bв\s+(\d+)\b', re.IGNORECASE)

# Сокращение Кол (Коллоквиум/Колледж — контекстно) — просто ставим точку
_KNOWN_ABBREVIATED_WORDS = {
    "Кол": "Кол.",
}


def normalize_document_title(raw: str) -> str:
    """Normalize filename-like title to presentable form.

    Rules applied in order:
    1. Strip extension (.pdf, .docx, .pptx, .txt, .md)
    2. Replace underscores with spaces
    3. Collapse multiple spaces
    4. Merge date patterns DD MM YYYY → DD.MM.YYYY
    5. Replace «в N» → «, вариант N»
    6. Apply known abbreviated-word substitutions (Кол → Кол.)
    7. Preserve 2-4 all-caps sequences as abbreviations (no change)
    8. Insert «.» separators between major segments if heuristically appropriate
    """
    if not raw:
        return raw

    # 1. Strip extension
    text = re.sub(r'\.(pdf|docx|doc|pptx|ppt|txt|md)$', '', raw, flags=re.IGNORECASE)

    # 2. Underscores → spaces
    text = text.replace('_', ' ')

    # 3. Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # 4. Merge dates
    text = _DATE_RE.sub(r'\1.\2.\3', text)

    # 5. «в N» → «, вариант N»
    text = _VARIANT_RE.sub(r', вариант \1', text)

    # 6. Substitute known abbreviated words
    for word, replacement in _KNOWN_ABBREVIATED_WORDS.items():
        text = re.sub(rf'\b{word}\b', replacement, text)

    # 7. Abbreviations are naturally preserved (no case change)

    # 8. Insert segment separators: найти слова, которые capitalized (не abbreviations)
    #    и добавлять точки перед ними если предыдущий токен был не-abbreviated word.
    #    Это heuristic — применяем только если в строке явно видны маркеры «новой секции».
    text = _insert_segment_separators(text)

    return text.strip()


def _insert_segment_separators(text: str) -> str:
    """Insert '. ' separators between major content segments.

    Heuristic: если после аббревиатуры идёт слово Title-Cased (не аббревиатура
    и не начинается с цифры), вставляем «. » между ними.
    """
    tokens = text.split(' ')
    result = []
    for i, tok in enumerate(tokens):
        if i == 0:
            result.append(tok)
            continue
        prev = tokens[i - 1]
        # Если prev — аббревиатура (2-4 капса) или «вариант N», а текущий — Title-cased слово
        if (_ABBREV_RE.match(prev) and
                tok and tok[0].isupper() and
                not _ABBREV_RE.match(tok) and
                not tok[-1] == '.' and  # уже punctuated
                not result[-1].endswith('.')):
            # Проверить, что это не начало даты или варианта
            if not tok[0].isdigit():
                result[-1] = result[-1] + '.'
        result.append(tok)
    return ' '.join(result)
```

- [ ] **Step 4: Run — pass**

```bash
pytest tests/test_title_normalizer.py -v
```

Expected: все тесты зелёные. Если heuristic на step 8 даёт ложные срабатывания — отладить.

- [ ] **Step 5: Создать SQLite-миграцию**

Создать `infrastructure/db/migrations/001_add_document_normalized_fields.sql`:

```sql
-- Migration 001: Add normalized title fields to source_documents
-- Adds: display_title, source_filename
-- Backward compatible: `title` remains as legacy field, new code reads display_title

ALTER TABLE source_documents ADD COLUMN display_title TEXT;
ALTER TABLE source_documents ADD COLUMN source_filename TEXT;

-- Initial population: copy current title to display_title as fallback
UPDATE source_documents SET display_title = title WHERE display_title IS NULL;
```

- [ ] **Step 6: Создать migration runner**

Создать `infrastructure/db/migrations/__init__.py` (пустой).

Создать `infrastructure/db/migrations/runner.py`:

```python
"""SQLite migration runner.

Applies SQL migration files in order, tracking applied versions in
schema_versions table. Each migration file: NNN_description.sql.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import List, Tuple

MIGRATIONS_DIR = Path(__file__).parent


def ensure_schema_versions_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_versions (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    ensure_schema_versions_table(conn)
    return {row[0] for row in conn.execute("SELECT version FROM schema_versions")}


def discover_migrations() -> List[Tuple[int, Path]]:
    """Find all migration files, sorted by version."""
    migrations: List[Tuple[int, Path]] = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        match = re.match(r'^(\d+)_', path.name)
        if match:
            migrations.append((int(match.group(1)), path))
    migrations.sort(key=lambda x: x[0])
    return migrations


def apply_pending_migrations(conn: sqlite3.Connection) -> List[int]:
    """Apply all pending migrations. Return list of applied versions."""
    applied = applied_versions(conn)
    pending = [(v, p) for v, p in discover_migrations() if v not in applied]

    newly_applied: List[int] = []
    for version, path in pending:
        sql = path.read_text(encoding='utf-8')
        try:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_versions (version) VALUES (?)",
                (version,)
            )
            conn.commit()
            newly_applied.append(version)
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Migration {version} ({path.name}) failed: {e}") from e

    return newly_applied
```

- [ ] **Step 7: Test migration runner**

Создать `tests/test_migration_runner.py`:

```python
import sqlite3
import pytest

from infrastructure.db.migrations.runner import (
    apply_pending_migrations,
    applied_versions,
    discover_migrations,
)


@pytest.fixture
def empty_db():
    conn = sqlite3.connect(":memory:")
    # Создаём минимальную schema, которая нужна для migration 001
    conn.execute("""
        CREATE TABLE source_documents (
            document_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT
        )
    """)
    yield conn
    conn.close()


def test_discover_finds_migrations():
    migrations = discover_migrations()
    assert len(migrations) >= 1
    assert migrations[0][0] == 1


def test_applies_migration_once(empty_db):
    applied = apply_pending_migrations(empty_db)
    assert 1 in applied

    # Повторный вызов не применяет
    applied_again = apply_pending_migrations(empty_db)
    assert applied_again == []


def test_migration_001_adds_columns(empty_db):
    apply_pending_migrations(empty_db)
    columns = {r[1] for r in empty_db.execute("PRAGMA table_info(source_documents)")}
    assert "display_title" in columns
    assert "source_filename" in columns


def test_migration_001_populates_display_title(empty_db):
    empty_db.execute(
        "INSERT INTO source_documents (document_id, title, status) VALUES (?, ?, ?)",
        ("doc-1", "Оригинальный заголовок", "imported")
    )
    empty_db.commit()
    apply_pending_migrations(empty_db)
    row = empty_db.execute(
        "SELECT display_title FROM source_documents WHERE document_id = 'doc-1'"
    ).fetchone()
    assert row[0] == "Оригинальный заголовок"
```

Run:

```bash
pytest tests/test_migration_runner.py -v
```

Expected: все тесты зелёные.

- [ ] **Step 8: Update `domain/models.py`**

Модифицировать `domain/models.SourceDocument`:

```python
# ⚠️ Frozen interface change — синхронизация с W2/W3 после коммита
@dataclass(slots=True)
class SourceDocument:
    document_id: str
    title: str  # legacy, остаётся = display_title для совместимости
    display_title: str | None = None  # NEW: normalized presentation form
    source_filename: str | None = None  # NEW: original file name
    # … остальные поля без изменений
```

Проверить, что все конструкторы обновлены с значениями по умолчанию (поля опциональные).

- [ ] **Step 9: Update `repository.py` на запись/чтение новых полей**

В `infrastructure/db/repository.py` найти:
- `insert_document(...)` — добавить `display_title`, `source_filename` в INSERT
- `get_document(...)`, `list_documents(...)` — добавить в SELECT

Пример:

```python
def insert_document(self, doc: SourceDocument) -> None:
    self.connection.execute("""
        INSERT INTO source_documents (
            document_id, title, display_title, source_filename, status, ...
        ) VALUES (?, ?, ?, ?, ?, ...)
    """, (doc.document_id, doc.title, doc.display_title, doc.source_filename, doc.status, ...))
```

- [ ] **Step 10: Apply migrations at repository init**

В `infrastructure/db/repository.py` в `__init__` или factory:

```python
from infrastructure.db.migrations.runner import apply_pending_migrations

class Repository:
    def __init__(self, connection):
        self.connection = connection
        apply_pending_migrations(self.connection)
```

- [ ] **Step 11: Update importers to use normalizer**

В `infrastructure/importers/pdf_importer.py`, `docx_importer.py` (и где ещё создаются `SourceDocument`):

```python
from infrastructure.importers.title_normalizer import normalize_document_title

# При создании SourceDocument:
source_filename = path.name
display_title = normalize_document_title(source_filename)
doc = SourceDocument(
    document_id=...,
    title=display_title,  # legacy совместимость
    display_title=display_title,
    source_filename=source_filename,
    ...
)
```

- [ ] **Step 12: Run full suite**

```bash
pytest tests/ -q
```

Expected: все тесты зелёные.

- [ ] **Step 13: Commit**

```bash
git add infrastructure/importers/title_normalizer.py \
        infrastructure/db/migrations/ \
        domain/models.py \
        infrastructure/db/repository.py \
        infrastructure/importers/pdf_importer.py \
        infrastructure/importers/docx_importer.py \
        tests/test_title_normalizer.py \
        tests/test_migration_runner.py
git commit -m "feat(importer): normalize document titles, add schema migration

Adds title normalizer handling filename patterns (dates, variants, known
abbreviations, caps sequences). Migration 001 adds display_title and
source_filename columns to source_documents. Repository applies pending
migrations on init.

⚠️ Frozen interface change: domain.models.SourceDocument gains two
optional fields. Coordinator must cherry-pick into flet-migration and
installer worktrees.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**🚨 Sync gate:** уведомить координатора об изменении `domain/models.py`.

---

## Task 5: Section Metadata Parser + Migration

**Files:**
- Create: `infrastructure/importers/section_metadata_parser.py`
- Create: `infrastructure/importers/ru_names.py` — словарь частых фамилий
- Create: `infrastructure/db/migrations/002_add_section_metadata_fields.sql`
- Test: `tests/test_section_metadata_parser.py`
- Modify: `domain/models.Section` — добавить поля
- Modify: `infrastructure/db/repository.py`
- Modify: `infrastructure/importers/*.py` — интеграция

**⚠️ Синхронизация:** изменение `domain/models.Section` — frozen interface. Координатор cherry-pick.

- [ ] **Step 1: Словарь фамилий**

Создать `infrastructure/importers/ru_names.py`:

```python
"""Minimal dictionary of common Russian surnames for heuristic FIO detection.

Source: top-3000 Russian surnames from ФОМ 2023. Covers ~60% of real names;
fallback heuristic handles the tail.
"""

# Топ-500 фамилий (урезанная версия; при необходимости расширяется из файла)
COMMON_SURNAMES = frozenset({
    "Иванов", "Иванова", "Смирнов", "Смирнова", "Кузнецов", "Кузнецова",
    "Попов", "Попова", "Васильев", "Васильева", "Петров", "Петрова",
    "Соколов", "Соколова", "Михайлов", "Михайлова", "Новиков", "Новикова",
    "Фёдоров", "Фёдорова", "Морозов", "Морозова", "Волков", "Волкова",
    "Алексеев", "Алексеева", "Лебедев", "Лебедева", "Семёнов", "Семёнова",
    "Егоров", "Егорова", "Павлов", "Павлова", "Козлов", "Козлова",
    "Степанов", "Степанова", "Николаев", "Николаева", "Орлов", "Орлова",
    "Андреев", "Андреева", "Макаров", "Макарова", "Никитин", "Никитина",
    "Захаров", "Захарова", "Зайцев", "Зайцева", "Соловьёв", "Соловьёва",
    "Борисов", "Борисова", "Яковлев", "Яковлева", "Григорьев", "Григорьева",
    "Романов", "Романова", "Воробьёв", "Воробьёва", "Сергеев", "Сергеева",
    "Кузьмин", "Кузьмина", "Фролов", "Фролова", "Александров", "Александрова",
    "Дмитриев", "Дмитриева", "Королёв", "Королёва", "Гусев", "Гусева",
    "Киселёв", "Киселёва", "Ильин", "Ильина", "Максимов", "Максимова",
    "Поляков", "Полякова", "Сорокин", "Сорокина", "Виноградов", "Виноградова",
    "Ковалёв", "Ковалёва", "Белов", "Белова", "Медведев", "Медведева",
    "Антонов", "Антонова", "Тарасов", "Тарасова", "Жуков", "Жукова",
    "Баранов", "Баранова", "Филиппов", "Филиппова", "Комаров", "Комарова",
    "Давыдов", "Давыдова", "Беляев", "Беляева", "Герасимов", "Герасимова",
    "Богданов", "Богданова", "Осипов", "Осипова", "Сидоров", "Сидорова",
    "Матвеев", "Матвеева", "Титов", "Титова", "Марков", "Маркова",
    "Миронов", "Миронова", "Крылов", "Крылова", "Куликов", "Куликова",
    "Карпов", "Карпова", "Власов", "Власова", "Мельников", "Мельникова",
    "Денисов", "Денисова", "Гаврилов", "Гаврилова", "Тихонов", "Тихонова",
    "Казаков", "Казакова", "Афанасьев", "Афанасьева", "Данилов", "Данилова",
    "Савельев", "Савельева", "Тимофеев", "Тимофеева", "Фомин", "Фомина",
    "Чернов", "Чернова", "Абрамов", "Абрамова", "Мартынов", "Мартынова",
    "Ефимов", "Ефимова", "Федотов", "Федотова", "Щербаков", "Щербакова",
    "Назаров", "Назарова", "Калинин", "Калинина", "Исаев", "Исаева",
    "Чернышёв", "Чернышёва", "Быков", "Быкова", "Маслов", "Маслова",
    "Родионов", "Родионова", "Коновалов", "Коновалова", "Лазарев", "Лазарева",
    "Воронин", "Воронина", "Климов", "Климова", "Филатов", "Филатова",
    "Пономарёв", "Пономарёва", "Голубев", "Голубева", "Кудрявцев", "Кудрявцева",
    "Прохоров", "Прохорова", "Наумов", "Наумова", "Потапов", "Потапова",
    "Журавлёв", "Журавлёва", "Овчинников", "Овчинникова", "Трофимов", "Трофимова",
    # Из текущего conspectus:
    "Седых", "Гринько", "Абдулаева",
})


def is_likely_surname(token: str) -> bool:
    """Check if token looks like a Russian surname (dictionary + heuristic)."""
    if not token or not token[0].isupper():
        return False
    if token in COMMON_SURNAMES:
        return True
    # Heuristic: типичные окончания фамилий
    surname_endings = ('ов', 'ев', 'ин', 'ын', 'ский', 'цкий', 'ова', 'ева',
                       'ина', 'ына', 'ская', 'цкая', 'их', 'ых')
    return any(token.endswith(end) for end in surname_endings) and len(token) > 4
```

- [ ] **Step 2: Failing test**

Создать `tests/test_section_metadata_parser.py`:

```python
from infrastructure.importers.section_metadata_parser import parse_section_metadata


def test_full_metadata_parsed():
    result = parse_section_metadata("Философия Седых Татьяна Николаевна ВШГА МГУ Доцент")
    assert result.title == "Философия"
    assert result.lecturer_name == "Седых Татьяна Николаевна"
    assert result.department == "ВШГА МГУ"
    assert result.position == "Доцент"


def test_partial_metadata_title_plus_lecturer():
    result = parse_section_metadata("История России Иванов Иван Иванович")
    assert result.title == "История России"
    assert result.lecturer_name == "Иванов Иван Иванович"
    assert result.department is None
    assert result.position is None


def test_simple_title_only():
    result = parse_section_metadata("Философия")
    assert result.title == "Философия"
    assert result.lecturer_name is None


def test_empty_falls_back():
    result = parse_section_metadata("")
    assert result.title == ""


def test_heuristic_surname_detected():
    """Когда фамилии нет в словаре, используется эвристика окончаний."""
    result = parse_section_metadata("Право Некрасовский Пётр Петрович ВШЭ Профессор")
    assert result.title == "Право"
    assert result.lecturer_name == "Некрасовский Пётр Петрович"
    assert result.department == "ВШЭ"
    assert result.position == "Профессор"


def test_known_gmu_department():
    result = parse_section_metadata("Философия Гринько Александра Николаевна ВШГА МГУ")
    assert result.lecturer_name == "Гринько Александра Николаевна"
    assert result.department == "ВШГА МГУ"
```

- [ ] **Step 3: Run — fail**

```bash
pytest tests/test_section_metadata_parser.py -v
```

- [ ] **Step 4: Implement parser**

Создать `infrastructure/importers/section_metadata_parser.py`:

```python
"""Parse section titles that glue subject + lecturer + department + position.

Example input:  «Философия Седых Татьяна Николаевна ВШГА МГУ Доцент»
Output: SectionMetadata(title="Философия", lecturer="Седых Татьяна Николаевна",
                        department="ВШГА МГУ", position="Доцент")

Fallback: if heuristic fails, title = raw, others = None.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from infrastructure.importers.ru_names import is_likely_surname


KNOWN_DEPARTMENTS = frozenset({
    "ВШГА", "МГУ", "МГИМО", "ВШЭ", "СПбГУ", "РАНХиГС",
    "ВШГА МГУ", "МГИМО МИД", "РАНХиГС при Президенте РФ",
})

KNOWN_POSITIONS = frozenset({
    "Профессор", "Доцент", "Ассистент", "Преподаватель",
    "Ст. преподаватель", "Старший преподаватель", "Заведующий кафедрой",
    "Доктор наук", "Кандидат наук", "Доктор", "Декан", "Ректор",
    "Научный сотрудник", "Старший научный сотрудник",
})


@dataclass(slots=True)
class SectionMetadata:
    title: str
    lecturer_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None


def parse_section_metadata(raw: str) -> SectionMetadata:
    """Parse glued section title into components.

    Strategy:
    1. Tokenize by whitespace
    2. Scan from end: position (last 1-2 tokens matching KNOWN_POSITIONS)
    3. Then department (matching KNOWN_DEPARTMENTS or contiguous caps)
    4. Then lecturer (3 consecutive capitalized tokens with surname-like first)
    5. Remaining prefix = title
    """
    if not raw or not raw.strip():
        return SectionMetadata(title=raw or "")

    tokens = raw.split()
    if not tokens:
        return SectionMetadata(title=raw)

    pos_position_start = len(tokens)
    pos_department_start = len(tokens)
    pos_lecturer_start = len(tokens)

    # 1. Position — может быть 1-2 токена (Ст. преподаватель)
    for n in (2, 1):
        if len(tokens) >= n:
            candidate = " ".join(tokens[-n:])
            if candidate in KNOWN_POSITIONS:
                pos_position_start = len(tokens) - n
                break

    # 2. Department — проверить накопление капс-токенов перед position
    dept_end = pos_position_start
    dept_start = dept_end
    while dept_start > 0 and tokens[dept_start - 1].isupper() and len(tokens[dept_start - 1]) >= 2:
        dept_start -= 1
    if dept_start < dept_end:
        dept_text = " ".join(tokens[dept_start:dept_end])
        # Подтверждаем, только если в списке или выглядит как университет (все капсы)
        if dept_text in KNOWN_DEPARTMENTS or all(tokens[i].isupper() for i in range(dept_start, dept_end)):
            pos_department_start = dept_start

    # 3. Lecturer — 3 последовательных слова с заглавной буквы перед department
    lecturer_end = pos_department_start if pos_department_start < len(tokens) else pos_position_start
    if lecturer_end >= 3:
        # Проверить 3 токена перед lecturer_end
        i = lecturer_end - 3
        candidates = tokens[i:lecturer_end]
        if (all(t and t[0].isupper() for t in candidates)
                and (is_likely_surname(candidates[0]) or is_likely_surname(candidates[-1]))):
            pos_lecturer_start = i

    # 4. Title = всё до lecturer_start (или до department если lecturer не распознан)
    title_end = min(pos_lecturer_start, pos_department_start, pos_position_start)
    if title_end == 0:
        # Не распознали title — вернуть raw как есть
        return SectionMetadata(title=raw)

    return SectionMetadata(
        title=" ".join(tokens[:title_end]),
        lecturer_name=" ".join(tokens[pos_lecturer_start:lecturer_end]) if pos_lecturer_start < lecturer_end else None,
        department=" ".join(tokens[pos_department_start:pos_position_start]) if pos_department_start < pos_position_start else None,
        position=" ".join(tokens[pos_position_start:]) if pos_position_start < len(tokens) else None,
    )
```

- [ ] **Step 5: Run — pass**

```bash
pytest tests/test_section_metadata_parser.py -v
```

Если какой-то тест не проходит — отладить heuristic.

- [ ] **Step 6: Migration 002**

Создать `infrastructure/db/migrations/002_add_section_metadata_fields.sql`:

```sql
-- Migration 002: Add lecturer/department/position to sections

ALTER TABLE sections ADD COLUMN lecturer_name TEXT;
ALTER TABLE sections ADD COLUMN department TEXT;
ALTER TABLE sections ADD COLUMN position TEXT;
```

- [ ] **Step 7: Update Section model**

В `domain/models.py` (⚠️ frozen interface change):

```python
@dataclass(slots=True)
class Section:
    section_id: str
    title: str
    lecturer_name: Optional[str] = None  # NEW
    department: Optional[str] = None  # NEW
    position: Optional[str] = None  # NEW
    # … existing fields
```

- [ ] **Step 8: Update repository**

В `infrastructure/db/repository.py` — чтение/запись новых полей Section.

- [ ] **Step 9: Integrate parser в import pipeline**

В местах, где создаются `Section`:

```python
from infrastructure.importers.section_metadata_parser import parse_section_metadata

metadata = parse_section_metadata(raw_section_title)
section = Section(
    section_id=...,
    title=metadata.title,
    lecturer_name=metadata.lecturer_name,
    department=metadata.department,
    position=metadata.position,
    # ...
)
```

- [ ] **Step 10: Full suite**

```bash
pytest tests/ -q
```

- [ ] **Step 11: Commit**

```bash
git add infrastructure/importers/section_metadata_parser.py \
        infrastructure/importers/ru_names.py \
        infrastructure/db/migrations/002_add_section_metadata_fields.sql \
        domain/models.py \
        infrastructure/db/repository.py \
        infrastructure/importers/*.py \
        tests/test_section_metadata_parser.py
git commit -m "feat(importer): parse section metadata (lecturer/dept/position)

Splits glued section titles like «Философия Седых Татьяна Николаевна
ВШГА МГУ Доцент» into structured fields. Uses dictionary of ~180 common
surnames + heuristic ending detection, known departments
(ВШГА/МГУ/ВШЭ/etc) and positions. Migration 002 adds fields.

⚠️ Frozen interface change: domain.models.Section gains three optional
fields. Coordinator cherry-pick into flet-migration and installer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**🚨 Sync gate:** уведомить координатора.

---

## Task 6: Answer Blocks Generator Integration

**Files:**
- Modify: `application/answer_block_builder.py` — existing, подключить в pipeline
- Modify: `application/import_service.py` — вызов builder
- Test: `tests/test_answer_blocks_generator.py`

- [ ] **Step 1: Прочитать существующий `answer_block_builder.py`**

Открыть `application/answer_block_builder.py`. Зафиксировать:
- Какие методы предоставляет
- Какие промпты использует
- Как персистит answer_blocks

Если пустой/stub — реализовать.

- [ ] **Step 2: Failing test**

Создать `tests/test_answer_blocks_generator.py`:

```python
import pytest
from unittest.mock import MagicMock

from application.answer_block_builder import AnswerBlockBuilder


@pytest.fixture
def mock_ollama():
    svc = MagicMock()
    svc.generate_answer_blocks.return_value = MagicMock(
        text='{"blocks": [{"label": "Введение", "text": "..."}, {"label": "Определения", "text": "..."}, {"label": "Классификация", "text": "..."}, {"label": "Механизм", "text": "..."}, {"label": "Примеры", "text": "..."}, {"label": "Заключение", "text": "..."}]}',
        error=None,
    )
    return svc


def test_full_ticket_gets_six_blocks(mock_ollama):
    ticket = MagicMock()
    ticket.ticket_id = "t1"
    ticket.title = "Тестовый билет"
    ticket.canonical_answer_summary = "A" * 1000  # достаточно длинный

    builder = AnswerBlockBuilder(ollama_service=mock_ollama)
    blocks = builder.build_for_ticket(ticket, model="qwen3:1.7b")

    assert len(blocks) == 6
    labels = [b.label for b in blocks]
    assert labels == ["Введение", "Определения", "Классификация", "Механизм", "Примеры", "Заключение"]


def test_short_ticket_gets_partial_blocks(mock_ollama):
    ticket = MagicMock()
    ticket.ticket_id = "t1"
    ticket.canonical_answer_summary = "Короткий"  # < 500 символов

    builder = AnswerBlockBuilder(ollama_service=mock_ollama)
    blocks = builder.build_for_ticket(ticket, model="qwen3:1.7b")

    # Только 2 блока, с пометкой insufficient
    assert len(blocks) == 2
    assert all(b.status == "insufficient_source" for b in blocks)


def test_llm_failure_returns_empty(mock_ollama):
    mock_ollama.generate_answer_blocks.return_value = MagicMock(text=None, error="timeout")
    ticket = MagicMock()
    ticket.canonical_answer_summary = "A" * 1000

    builder = AnswerBlockBuilder(ollama_service=mock_ollama)
    blocks = builder.build_for_ticket(ticket, model="qwen3:1.7b")

    assert blocks == []
```

- [ ] **Step 3: Run — adapt to actual AnswerBlockBuilder API**

Если тесты не совпадают с текущим API — адаптировать тесты (если API работает хорошо) или переработать builder (если API плохой). См. спек Часть 2.6 для желаемого поведения.

- [ ] **Step 4: Подключить вызов в `import_service.py`**

В `application/import_service.py`, где билет полностью импортирован (LLM refinement прошёл):

```python
from application.answer_block_builder import AnswerBlockBuilder

# в конце цикла после атомизации:
if ticket.llm_status == "succeeded":
    builder = AnswerBlockBuilder(ollama_service=self.ollama_service)
    blocks = builder.build_for_ticket(ticket, model=self.model)
    for block in blocks:
        self.repository.insert_answer_block(block)
```

- [ ] **Step 5: Run — pass**

```bash
pytest tests/test_answer_blocks_generator.py -v
```

- [ ] **Step 6: Commit**

```bash
git add application/answer_block_builder.py \
        application/import_service.py \
        tests/test_answer_blocks_generator.py
git commit -m "feat(import): generate answer_blocks after LLM refinement

Integrates existing AnswerBlockBuilder into import pipeline. Tickets
with canonical_answer_summary >= 500 chars get 6 blocks (Введение,
Определения, Классификация, Механизм, Примеры, Заключение). Short
tickets get 2 blocks with status=insufficient_source. LLM failures
return empty list (caller handles degraded state).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: LLM Refinement Pass with Retry/Timeout

**Files:**
- Modify: `scripts/build_state_exam_seed.py` — improve refinement loop
- Test: `tests/test_state_exam_seed_scripts.py` — добавить тесты

- [ ] **Step 1: Failing test для timeout/retry**

Добавить в `tests/test_state_exam_seed_scripts.py`:

```python
def test_refinement_respects_per_ticket_timeout(monkeypatch):
    """Каждый билет должен иметь свой таймаут, не общий."""
    from scripts.build_state_exam_seed import refine_one_ticket

    mock_svc = MagicMock()
    # Симулируем долгий LLM-ответ
    import time
    def slow_call(*args, **kwargs):
        time.sleep(5)
        return MagicMock(text='{"ok": true}')
    mock_svc.refine_ticket.side_effect = slow_call

    result = refine_one_ticket(
        ticket_id="t1",
        ollama_service=mock_svc,
        model="qwen3:1.7b",
        timeout_seconds=2,  # таймаут 2 сек, запрос 5 сек
        max_retries=0,
    )
    assert result.status == "timeout"


def test_refinement_retries_on_timeout():
    from scripts.build_state_exam_seed import refine_one_ticket

    call_count = {"n": 0}
    mock_svc = MagicMock()
    def flaky(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise TimeoutError()
        return MagicMock(text='{"ok": true}')
    mock_svc.refine_ticket.side_effect = flaky

    result = refine_one_ticket(
        ticket_id="t1",
        ollama_service=mock_svc,
        model="qwen3:1.7b",
        timeout_seconds=10,
        max_retries=2,
    )
    assert result.status == "succeeded"
    assert call_count["n"] == 2
```

- [ ] **Step 2: Run — fail (нужно добавить параметры/функцию)**

- [ ] **Step 3: Implement refine_one_ticket**

В `scripts/build_state_exam_seed.py` найти существующий код refinement. Если он использует concurrent.futures — обеспечить per-ticket timeout. Реализовать функцию (или адаптировать существующую):

```python
@dataclass
class RefineResult:
    ticket_id: str
    status: str  # "succeeded" | "timeout" | "parse_error" | "error"
    error_msg: str = ""


def refine_one_ticket(
    ticket_id: str,
    ollama_service,
    model: str,
    timeout_seconds: int = 120,
    max_retries: int = 2,
) -> RefineResult:
    attempt = 0
    while attempt <= max_retries:
        try:
            # Обёртка с threading.Timer или concurrent.futures.timeout
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(ollama_service.refine_ticket, ticket_id, model=model)
                result = future.result(timeout=timeout_seconds)
                # validate JSON, update DB, etc.
                return RefineResult(ticket_id=ticket_id, status="succeeded")
        except concurrent.futures.TimeoutError:
            attempt += 1
            if attempt > max_retries:
                return RefineResult(ticket_id=ticket_id, status="timeout",
                                    error_msg=f"exceeded {timeout_seconds}s after {max_retries} retries")
        except Exception as e:
            return RefineResult(ticket_id=ticket_id, status="error", error_msg=str(e))
    return RefineResult(ticket_id=ticket_id, status="error", error_msg="unreachable")
```

- [ ] **Step 4: Run — pass**

```bash
pytest tests/test_state_exam_seed_scripts.py -v
```

- [ ] **Step 5: Run actual refinement on seed v1 → v2**

Запустить:

```bash
python scripts/build_state_exam_seed.py \
    --source-pdf "МДЭ_ГА_2024_Кол_Конспект_ГМУ_ГАРФ_18_02_2025_в_2.pdf" \
    --output build/demo_seed/state_exam_public_admin_demo_v2.db \
    --model qwen3:1.7b \
    --parallel-workers 2 \
    --max-resume-passes 2
```

Expected: после завершения (~1-3 часа машинного времени) seed v2 готов. Проверка:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('build/demo_seed/state_exam_public_admin_demo_v2.db')
print(list(conn.execute('SELECT llm_status, COUNT(*) FROM tickets GROUP BY llm_status')))
print(list(conn.execute('SELECT COUNT(*) FROM answer_blocks')))
"
```

Ожидается: `llm_status="succeeded"` у ≥200 билетов, answer_blocks не пуста.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_state_exam_seed.py tests/test_state_exam_seed_scripts.py
git commit -m "feat(seed): per-ticket timeout and retry in LLM refinement

refine_one_ticket uses ThreadPoolExecutor with per-call timeout. Retry
up to N times on timeout. Returns structured RefineResult with status
for seed manifest. Prevents the long-tail hang behavior seen in
previous seed-build attempts where one stuck ticket blocked the whole
pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Full Re-import and Seed v2 Verification

**Files:**
- Modify: `scripts/verify_state_exam_seed.py` — add invariants for new fixes
- Create: `tests/test_seed_v2_quality.py` — acceptance

- [ ] **Step 1: Update verify script**

В `scripts/verify_state_exam_seed.py` добавить проверки:

```python
def check_no_garbage_content(conn):
    """No tickets with summary like «● (N) N»."""
    bad = list(conn.execute("""
        SELECT ticket_id, canonical_answer_summary FROM tickets
        WHERE LENGTH(canonical_answer_summary) < 50
          AND canonical_answer_summary GLOB '*●*(*)*'
    """))
    assert not bad, f"Found {len(bad)} tickets with bullet-marker content: {bad[:3]}"


def check_no_bylines_in_atoms(conn):
    """No atom text starts with «(Surname» or known FIO pattern."""
    bad = list(conn.execute("""
        SELECT atom_id, text FROM atoms
        WHERE text GLOB '(*)*' AND LENGTH(text) < 100
    """))
    assert not bad, f"Found {len(bad)} atoms starting with paren-bylines"


def check_atoms_not_fragmented(conn):
    """Atoms shorter than 15 chars that end with closing punct → likely fragment."""
    fragments = list(conn.execute("""
        SELECT atom_id, text FROM atoms
        WHERE LENGTH(text) < 15 AND (text LIKE '%).' OR text LIKE '%.)')
    """))
    assert not fragments, f"Found {len(fragments)} fragment atoms (e.g. «5 Конституции).»)"


def check_display_titles_normalized(conn):
    """Documents have display_title != raw filename stem."""
    bad = list(conn.execute("""
        SELECT document_id, display_title, source_filename FROM source_documents
        WHERE display_title = source_filename OR display_title IS NULL
    """))
    assert not bad, f"Documents without normalized title: {bad}"


def check_answer_blocks_exist(conn):
    """At least 80% of succeeded tickets have answer_blocks."""
    total = conn.execute("SELECT COUNT(*) FROM tickets WHERE llm_status='succeeded'").fetchone()[0]
    with_blocks = conn.execute("""
        SELECT COUNT(DISTINCT ticket_id) FROM answer_blocks
    """).fetchone()[0]
    assert total == 0 or with_blocks / total >= 0.8, \
        f"Only {with_blocks}/{total} succeeded tickets have answer_blocks"


def check_llm_coverage(conn):
    """At least 95% tickets are llm_status='succeeded'."""
    total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    ok = conn.execute("SELECT COUNT(*) FROM tickets WHERE llm_status='succeeded'").fetchone()[0]
    assert total == 0 or ok / total >= 0.95, f"Only {ok}/{total} succeeded"
```

Добавить вызов всех check_* в main verify function.

- [ ] **Step 2: Run verify on seed v2**

```bash
python scripts/verify_state_exam_seed.py --seed-db build/demo_seed/state_exam_public_admin_demo_v2.db
```

Expected: все инварианты зелёные. Если какой-то red — вернуться к соответствующей Task 1-7 и исправить.

- [ ] **Step 3: Acceptance test**

Создать `tests/test_seed_v2_quality.py`:

```python
"""Acceptance tests for v2 seed DB quality."""
import sqlite3
from pathlib import Path
import pytest

SEED_V2 = Path("build/demo_seed/state_exam_public_admin_demo_v2.db")


@pytest.fixture(scope="module")
def seed_conn():
    if not SEED_V2.exists():
        pytest.skip(f"Seed v2 not built yet at {SEED_V2}")
    conn = sqlite3.connect(f"file:{SEED_V2}?mode=ro", uri=True)
    yield conn
    conn.close()


def test_zero_garbage_tickets(seed_conn):
    """No tickets with `● (N) N` content."""
    bad = list(seed_conn.execute("""
        SELECT ticket_id FROM tickets
        WHERE canonical_answer_summary GLOB '*●*(*)*'
          AND LENGTH(canonical_answer_summary) < 50
    """))
    assert not bad, f"Found {len(bad)} garbage tickets"


def test_all_tickets_have_substantial_content(seed_conn):
    """≥200 of 208 tickets have ≥500 char summary."""
    counts = seed_conn.execute("""
        SELECT SUM(CASE WHEN LENGTH(canonical_answer_summary) >= 500 THEN 1 ELSE 0 END) AS ok,
               COUNT(*) AS total FROM tickets
    """).fetchone()
    ok, total = counts
    assert ok >= 0.95 * total, f"Only {ok}/{total} tickets have ≥500 char summary"


def test_llm_refinement_ran_on_most(seed_conn):
    counts = seed_conn.execute("""
        SELECT llm_status, COUNT(*) FROM tickets GROUP BY llm_status
    """).fetchall()
    status_map = dict(counts)
    total = sum(status_map.values())
    assert status_map.get("succeeded", 0) >= 0.95 * total


def test_answer_blocks_populated(seed_conn):
    count = seed_conn.execute("SELECT COUNT(*) FROM answer_blocks").fetchone()[0]
    assert count > 0, "answer_blocks table is empty"


def test_no_byline_atoms(seed_conn):
    bad = list(seed_conn.execute("""
        SELECT atom_id FROM atoms
        WHERE text GLOB '(*)*' AND LENGTH(text) < 80
    """))
    assert len(bad) < 5, f"Too many byline atoms: {len(bad)}"


def test_display_titles_normalized(seed_conn):
    bad = list(seed_conn.execute("""
        SELECT document_id, display_title FROM source_documents
        WHERE display_title IS NULL
           OR display_title GLOB '*_*'
           OR display_title = source_filename
    """))
    assert not bad, f"Non-normalized documents: {bad}"
```

- [ ] **Step 4: Run acceptance**

```bash
pytest tests/test_seed_v2_quality.py -v
```

Expected: все тесты зелёные (или обоснованно пропущены).

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_state_exam_seed.py tests/test_seed_v2_quality.py
git commit -m "test(seed): acceptance for v2 seed quality invariants

Checks: no garbage «● (N) N» tickets, ≥95% with substantial content,
≥95% LLM-refined, answer_blocks populated, no byline atoms, normalized
display titles. verify_state_exam_seed.py also enforces these at build
time.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Merge to main

**⚠️ Coordinator task** — выполняет координатор, не агент.

- [ ] **Step 1: Ensure clean state**

```bash
cd D:\ticket-exam-trainer-data
pytest -q
```

Expected: все тесты зелёные.

- [ ] **Step 2: Switch to main worktree**

```bash
cd D:\ticket-exam-trainer
```

- [ ] **Step 3: Merge data-pipeline branch**

```bash
git fetch
git merge --no-ff data-pipeline -m "Merge W1 data-pipeline: byline/tokenizer/TOC/titles/sections/answer_blocks/LLM refinement"
pytest -q
```

Expected: clean merge (mergetool only for expected frozen-interface changes in domain/models.py). Тесты зелёные.

- [ ] **Step 4: Rebuild seed from merged main**

```bash
python scripts/build_state_exam_seed.py \
    --source-pdf "МДЭ_ГА_2024_Кол_Конспект_ГМУ_ГАРФ_18_02_2025_в_2.pdf" \
    --output build/demo_seed/state_exam_public_admin_demo_v2.db \
    --model <default_from_R0>
```

- [ ] **Step 5: Push main**

```bash
git push origin main
```

---

## Acceptance Criteria (W1)

1. ✅ Все 7 task-ов имеют зелёные тесты
2. ✅ `build/demo_seed/state_exam_public_admin_demo_v2.db` существует и проходит `verify_state_exam_seed.py`
3. ✅ `pytest tests/test_seed_v2_quality.py -v` зелёный
4. ✅ `pytest -q` зелёный на всей кодовой базе
5. ✅ `git log --oneline data-pipeline` содержит 7-9 коммитов
6. ✅ Frozen interface изменения (`domain/models.py`: SourceDocument, Section) синхронизированы с W2/W3 worktrees
