"""Language contract test — весь user-facing UI обязан быть на русском.

Правило дизайн-кода: если строка попадает в widget, который рендерит текст
пользователю, она обязана содержать хотя бы один кириллический символ ИЛИ
быть в белом списке (технические токены, пустые строки, одиночные символы,
UI-ключи, числа/пунктуация/emoji).

Охват: весь `ui_flet/` — views, components. Docstring'и, комментарии и
identifier'ы не проверяются (их не видит пользователь).

Если тест падает — либо переведите строку на русский, либо добавьте её в
`_WHITELIST_EXACT` / `_WHITELIST_SUBSTRING`, если она действительно
техническая. Whitelist расширяется осознанно, не автоматически.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = REPO_ROOT / "ui_flet"

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_ALPHA_LATIN_RE = re.compile(r"[A-Za-z]")

_WIDGET_CALLABLES = {
    "Text",
    "ElevatedButton",
    "TextButton",
    "OutlinedButton",
    "FilledButton",
    "FilledTonalButton",
    "IconButton",
    "FloatingActionButton",
    "TextField",
    "Dropdown",
    "Checkbox",
    "Switch",
    "Radio",
    "Chip",
    "Tab",
    "SnackBar",
    "AlertDialog",
    "Banner",
    "Tooltip",
    "Markdown",
    "NavigationRailDestination",
    "NavigationDestination",
    "PopupMenuItem",
    "MenuItemButton",
    "ListTile",
}

_WIDGET_KWARGS = {
    "text",
    "label",
    "hint_text",
    "helper_text",
    "error_text",
    "counter_text",
    "prefix_text",
    "suffix_text",
    "title",
    "subtitle",
    "content",
    "tooltip",
    "value",
}

_WHITELIST_EXACT = {
    "",
    "Tezis",
    "FSRS",
    "Ollama",
    "SQLite",
    "JSON",
    "PDF",
    "Flet",
    "Esc",
    "id",
    "ID",
    "v1",
    "v2",
    "v2.0",
}

_WHITELIST_SUBSTRING_PATTERNS = (
    re.compile(r"^https?://"),
    re.compile(r"^/[a-z][a-z0-9/_-]*$"),
    re.compile(r"^[A-Za-z][A-Za-z0-9_]*$"),
)

_MODE_KEYS = {
    "reading",
    "active-recall",
    "cloze",
    "plan",
    "matching",
    "mini-exam",
    "state-exam-full",
    "review",
    "dialogue",
}


def _iter_ui_python_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ("views/*.py", "components/*.py", "workspaces/*.py"):
        files.extend(sorted(UI_ROOT.glob(pattern)))
    return [p for p in files if p.name != "__init__.py"]


def _is_user_facing_string(value: str) -> bool:
    if value in _WHITELIST_EXACT:
        return False
    stripped = value.strip()
    if not stripped:
        return False
    if stripped in _MODE_KEYS:
        return False
    for pattern in _WHITELIST_SUBSTRING_PATTERNS:
        if pattern.match(stripped):
            return False
    if not _ALPHA_LATIN_RE.search(stripped) and not _CYRILLIC_RE.search(stripped):
        return False
    return True


def _passes_language_contract(value: str) -> bool:
    if not _is_user_facing_string(value):
        return True
    return bool(_CYRILLIC_RE.search(value))


def _call_name(node: ast.Call) -> str | None:
    """Return the rightmost attribute name (e.g., ``ft.Text(...)`` → ``Text``)."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


class _WidgetStringCollector(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.violations: list[tuple[int, str, str]] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        name = _call_name(node)
        if name in _WIDGET_CALLABLES:
            if name == "Text" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    self._check(node.lineno, name, first.value)
            for keyword in node.keywords:
                if keyword.arg in _WIDGET_KWARGS and isinstance(keyword.value, ast.Constant):
                    if isinstance(keyword.value.value, str):
                        self._check(keyword.lineno, f"{name}({keyword.arg}=...)", keyword.value.value)
        self.generic_visit(node)

    def _check(self, lineno: int, origin: str, value: str) -> None:
        if not _passes_language_contract(value):
            self.violations.append((lineno, origin, value))


@pytest.mark.parametrize("path", _iter_ui_python_files(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_ui_strings_are_russian(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    collector = _WidgetStringCollector(path)
    collector.visit(tree)
    if collector.violations:
        formatted = "\n".join(
            f"  {path.relative_to(REPO_ROOT).as_posix()}:{lineno}  {origin}  →  {value!r}"
            for lineno, origin, value in collector.violations
        )
        pytest.fail(
            f"Найдены user-facing строки без кириллицы в {path.name}:\n{formatted}\n\n"
            "Либо переведите на русский, либо добавьте в whitelist "
            "tests/test_language_contract.py::_WHITELIST_EXACT, если это технический токен."
        )
