"""Тесты derivation недостающих answer-blocks из атомов."""

from __future__ import annotations

from dataclasses import dataclass

from application.block_derivation import derive_missing_blocks


@dataclass
class _FakeAtom:
    atom_id: str
    type: str
    label: str
    text: str

    # support both `.type` and `.atom_type` for robustness
    @property
    def atom_type(self) -> str:
        return self.type


@dataclass
class _FakeBlock:
    block_code: str
    is_missing: bool
    expected_content: str = ""


def _make_atoms(*specs: tuple[str, str, str]) -> list[_FakeAtom]:
    """spec = (type, label, text-длина-100)."""
    result = []
    for i, (type_, label, seed) in enumerate(specs):
        result.append(_FakeAtom(f"a-{i}", type_, label, seed * 10))
    return result


def test_derivation_empty_when_nothing_missing() -> None:
    blocks = [
        _FakeBlock("intro", is_missing=False, expected_content="x"),
        _FakeBlock("theory", is_missing=False, expected_content="x"),
        _FakeBlock("conclusion", is_missing=False, expected_content="x"),
    ]
    atoms = _make_atoms(("definition", "Термин", "содержание "))
    report = derive_missing_blocks("t1", blocks, atoms)
    assert report.count == 0


def test_derivation_fills_theory_from_definition_atoms() -> None:
    blocks = [
        _FakeBlock("intro", is_missing=False, expected_content="x"),
        _FakeBlock("theory", is_missing=True),
        _FakeBlock("practice", is_missing=True),
        _FakeBlock("conclusion", is_missing=False, expected_content="x"),
    ]
    atoms = _make_atoms(
        ("definition", "Бюджет", "определение бюджетной системы "),
        ("features", "Признаки", "перечень ключевых признаков "),
    )
    report = derive_missing_blocks("t1", blocks, atoms)
    derived_codes = {b.block_code for b in report.derived_blocks}
    assert "theory" in derived_codes


def test_derivation_fills_practice_from_examples_atoms() -> None:
    blocks = [_FakeBlock("practice", is_missing=True)]
    atoms = _make_atoms(
        ("examples", "Случай", "исторический пример реформы "),
        ("process_step", "Шаг", "этап внедрения нормы "),
    )
    report = derive_missing_blocks("t1", blocks, atoms)
    assert report.count == 1
    assert report.derived_blocks[0].block_code == "practice"
    assert "Случай" in report.derived_blocks[0].expected_content


def test_derivation_skips_block_when_no_matching_atoms() -> None:
    blocks = [_FakeBlock("skills", is_missing=True)]
    atoms = _make_atoms(("definition", "лишний", "только теория "))
    report = derive_missing_blocks("t1", blocks, atoms)
    assert report.count == 0


def test_derivation_does_not_reuse_atoms_across_blocks() -> None:
    blocks = [
        _FakeBlock("theory", is_missing=True),
        _FakeBlock("practice", is_missing=True),
    ]
    # один атом типа examples — может питать только practice, не theory
    atoms = [
        _FakeAtom("a1", "definition", "Термин", "определение " * 10),
        _FakeAtom("a2", "examples", "Кейс", "пример " * 10),
    ]
    report = derive_missing_blocks("t1", blocks, atoms)
    codes = [b.block_code for b in report.derived_blocks]
    sources = [set(b.source_atom_ids) for b in report.derived_blocks]
    theory_idx = codes.index("theory")
    practice_idx = codes.index("practice")
    assert sources[theory_idx].isdisjoint(sources[practice_idx])


def test_derivation_preserves_title() -> None:
    blocks = [_FakeBlock("extra", is_missing=True)]
    atoms = _make_atoms(("consequences", "Следствия", "долгосрочные последствия "))
    report = derive_missing_blocks("t1", blocks, atoms)
    assert report.count == 1
    assert report.derived_blocks[0].title == "Дополнительно"


def test_derivation_truncates_oversized_content() -> None:
    blocks = [_FakeBlock("theory", is_missing=True)]
    # 10 атомов по ~600 символов — должно быть обрезано до <= 1200
    atoms = [
        _FakeAtom(f"a{i}", "definition", f"Термин-{i}", "длинное определение " * 30)
        for i in range(10)
    ]
    report = derive_missing_blocks("t1", blocks, atoms)
    assert report.count == 1
    assert len(report.derived_blocks[0].expected_content) <= 1200


def test_derivation_skips_block_when_atoms_are_tiny() -> None:
    blocks = [_FakeBlock("theory", is_missing=True)]
    atoms = [_FakeAtom("a1", "definition", "", "кор")]  # < MIN_USEFUL_CONTENT
    report = derive_missing_blocks("t1", blocks, atoms)
    assert report.count == 0


def test_derivation_fallback_to_fragment_atoms_when_no_typed_match() -> None:
    # Билет без типизированных атомов: все атомы — conclusion с «Фрагмент» label.
    # Seed-pipeline обычно так и складывает unclassified chunks.
    blocks = [
        _FakeBlock("theory", is_missing=True),
        _FakeBlock("practice", is_missing=True),
        _FakeBlock("skills", is_missing=True),
    ]
    atoms = [
        _FakeAtom("a1", "conclusion", "Фрагмент 2", "первый кусок содержания билета " * 10),
        _FakeAtom("a2", "conclusion", "Фрагмент 3", "второй кусок содержания билета " * 10),
    ]
    report = derive_missing_blocks("t1", blocks, atoms)
    codes = [b.block_code for b in report.derived_blocks]
    assert "theory" in codes
    assert "practice" in codes
    # skills — не хватило фрагментов, пропущен (fail-safe)
    assert "skills" not in codes


def test_derivation_does_not_overwrite_typed_match_with_fragment() -> None:
    blocks = [
        _FakeBlock("theory", is_missing=True),
        _FakeBlock("practice", is_missing=True),
    ]
    atoms = [
        _FakeAtom("a1", "definition", "Термин", "правильная теория " * 10),
        _FakeAtom("a2", "conclusion", "Фрагмент 1", "распознанный фрагмент " * 10),
    ]
    report = derive_missing_blocks("t1", blocks, atoms)
    theory = next(b for b in report.derived_blocks if b.block_code == "theory")
    # theory должен быть собран из `definition`, а не из фрагмента
    assert "Термин" in theory.expected_content
    # practice берёт fragment как fallback
    practice_codes = [b.block_code for b in report.derived_blocks if b.block_code == "practice"]
    assert practice_codes == ["practice"]


def test_derivation_fragment_fallback_respects_canonical_order() -> None:
    blocks = [
        _FakeBlock("skills", is_missing=True),
        _FakeBlock("theory", is_missing=True),
    ]
    atoms = [
        _FakeAtom("a1", "conclusion", "Фрагмент 2", "единственный подходящий контент " * 10),
    ]
    report = derive_missing_blocks("t1", blocks, atoms)
    assert report.count == 1
    # Порядок fallback — theory → practice → skills → extra. Theory получает первой.
    assert report.derived_blocks[0].block_code == "theory"
