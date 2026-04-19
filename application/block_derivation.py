"""Восстановление недостающих answer-blocks из типизированных атомов.

Проблема seed-pipeline: из 208 билетов 113 имеют <4 non-missing блоков —
обычно заполнены только `intro` и `conclusion`, а `theory / practice /
skills / extra` остались `is_missing = 1` с пустым `expected_content`.

Решение: для каждого missing-блока собираем контент из уже
существующих атомов билета, сопоставляя тип атома ↔ назначение блока.
После derivation `plan`-mode и `state-exam-full` могут корректно
сверяться с билетом, а `skeleton_weak` маркер перестаёт гореть ложно.

Derivation — безопасная: если нет подходящих атомов, блок остаётся
missing. Существующие non-missing блоки **не трогаем**, они ценнее
любой derivation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from domain.answer_profile import AnswerBlockCode


_LOG = logging.getLogger(__name__)


# Какие атом-типы питают какой блок. Первый match выигрывает, затем
# остальные атомы того же билета идут в оставшиеся блоки.
_BLOCK_ATOM_MAP: dict[str, tuple[str, ...]] = {
    "theory":   ("definition", "features", "classification"),
    "practice": ("examples", "process_step"),
    "skills":   ("functions", "stages"),
    "extra":    ("consequences", "causes"),
}

# Порядок блоков для fallback-distribution «Фрагментов».
# Seed-pipeline нередко складывает весь текст билета в атомы с label
# «Фрагмент N / Основное содержание» и типом `conclusion` — это не
# настоящий conclusion, а unclassified chunks. Распределяем их по
# missing-блокам в каноническом порядке, давая per-block текст без
# потери содержания.
_FALLBACK_FRAGMENT_ORDER: tuple[str, ...] = ("theory", "practice", "skills", "extra")

_FRAGMENT_LABEL_HINTS: tuple[str, ...] = (
    "фрагмент",
    "основное содержание",
    "основная часть",
)

_DEFAULT_BLOCK_TITLES: dict[str, str] = {
    "intro":      "Введение",
    "theory":     "Теоретическая часть",
    "practice":    "Практическая часть",
    "skills":     "Навыки",
    "conclusion": "Заключение",
    "extra":      "Дополнительно",
}

_MAX_BLOCK_CONTENT = 1200   # защитный предел на derived-контент
_MIN_USEFUL_CONTENT = 50    # меньше этого — нет смысла derive, оставляем missing


@dataclass(frozen=True)
class DerivedBlock:
    block_code: str
    title: str
    expected_content: str
    source_atom_ids: tuple[str, ...]


@dataclass(frozen=True)
class DerivationReport:
    ticket_id: str
    derived_blocks: tuple[DerivedBlock, ...]

    @property
    def count(self) -> int:
        return len(self.derived_blocks)


def derive_missing_blocks(
    ticket_id: str,
    existing_blocks: list,
    atoms: list,
) -> DerivationReport:
    """Возвращает список блоков, которые можно заполнить из атомов.

    `existing_blocks` — ВСЕ блоки билета (включая is_missing=1). `atoms` —
    все атомы билета.

    Не возвращает блоки, которые:
      * уже non-missing и содержат контент (оставляем как есть);
      * не удалось derive (нет подходящих атомов).
    """
    used_atom_ids: set[str] = set()

    # Собираем non-missing блоки как-есть — они не нужны в отчёте.
    missing_codes = {
        _normalize_code(block.block_code): block
        for block in existing_blocks
        if getattr(block, "is_missing", False)
    }

    derived: list[DerivedBlock] = []

    # Этап 1: атомы с правильным типом → в соответствующий блок.
    for block_code, atom_types in _BLOCK_ATOM_MAP.items():
        if block_code not in missing_codes:
            continue
        built = _build_block_from_atoms(
            atoms,
            used_atom_ids,
            lambda a, ts=atom_types: _atom_type_value(a) in ts,
        )
        if built is None:
            continue
        content, source_ids = built
        used_atom_ids.update(source_ids)
        derived.append(
            DerivedBlock(
                block_code=block_code,
                title=_DEFAULT_BLOCK_TITLES[block_code],
                expected_content=content,
                source_atom_ids=tuple(source_ids),
            )
        )

    # Этап 2: fallback для missing-блоков, которые не нашли типовых атомов.
    # Источник — атомы с label «Фрагмент N / Основное содержание»
    # (impor-pipeline их складывает в type='conclusion' как unclassified
    # chunks). Распределяем по каноническому порядку блоков.
    remaining_missing = [
        code for code in _FALLBACK_FRAGMENT_ORDER
        if code in missing_codes and not any(b.block_code == code for b in derived)
    ]
    if remaining_missing:
        fragment_atoms = [a for a in atoms if _looks_like_fragment(a)]
        if fragment_atoms:
            for block_code in remaining_missing:
                built = _build_block_from_atoms(
                    fragment_atoms,
                    used_atom_ids,
                    lambda _a: True,
                    max_atoms=1,
                )
                if built is None:
                    break  # исчерпали фрагменты
                content, source_ids = built
                used_atom_ids.update(source_ids)
                derived.append(
                    DerivedBlock(
                        block_code=block_code,
                        title=_DEFAULT_BLOCK_TITLES[block_code],
                        expected_content=content,
                        source_atom_ids=tuple(source_ids),
                    )
                )

    return DerivationReport(ticket_id=ticket_id, derived_blocks=tuple(derived))


def _build_block_from_atoms(
    atoms: list,
    used_atom_ids: set[str],
    predicate,
    *,
    max_atoms: int | None = None,
) -> tuple[str, list[str]] | None:
    content_parts: list[str] = []
    source_ids: list[str] = []
    for atom in atoms:
        atom_id = getattr(atom, "atom_id", None) or str(id(atom))
        if atom_id in used_atom_ids:
            continue
        if not predicate(atom):
            continue
        snippet = _atom_to_block_snippet(atom)
        if not snippet:
            continue
        content_parts.append(snippet)
        source_ids.append(atom_id)
        if max_atoms is not None and len(content_parts) >= max_atoms:
            break
        if _joined_length(content_parts) >= _MAX_BLOCK_CONTENT:
            break
    content = "\n\n".join(content_parts).strip()[:_MAX_BLOCK_CONTENT]
    if len(content) < _MIN_USEFUL_CONTENT:
        return None
    return content, source_ids


def _looks_like_fragment(atom) -> bool:
    label = (getattr(atom, "label", "") or "").lower()
    return any(hint in label for hint in _FRAGMENT_LABEL_HINTS)


def _normalize_code(raw) -> str:
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw).lower().split(".")[-1]


def _atom_type_value(atom) -> str:
    raw = getattr(atom, "type", None) or getattr(atom, "atom_type", None)
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw).lower().split(".")[-1]


def _atom_to_block_snippet(atom) -> str:
    """Строит один параграф для derived-блока из атома.

    Формат: `**{label}.** {text}` — label выделяет узел, text — содержание.
    Если label пуст, используем только text. Лишние пробелы схлопываются.
    """
    text = (getattr(atom, "text", "") or "").strip()
    if not text:
        return ""
    label = (getattr(atom, "label", "") or "").strip()
    if label and not text.lower().startswith(label.lower()):
        return f"**{label}.** {text}"
    return text


def _joined_length(parts: list[str]) -> int:
    return sum(len(p) for p in parts) + max(0, len(parts) - 1) * 2
