from __future__ import annotations

import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

_FORBIDDEN_FILENAMES = {".DS_Store", "Desktop.ini", "Thumbs.db", "ehthumbs.db"}
_FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".db-shm", ".db-wal"}
_FORBIDDEN_SEGMENTS = {
    ".AppleDouble",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".hypothesis",
    ".tox",
    ".nox",
    ".venv",
}
_FORBIDDEN_ROOTS = {
    "app_data",
    "archive",
    "backups",
    "build_refresh",
    "dist",
    "dist_refresh",
    "local_tools",
}
_FORBIDDEN_ROOT_PREFIXES = ("llm_inbox_", "tmp-")
_ALLOWED_TRACKED_IGNORED_PATTERNS = (
    "build/ai-extract/tickets.json",
    "build/ai-generated/*.json",
    "data/state_exam_public_admin_demo.db",
)


@dataclass(slots=True)
class ReleaseGuardrailReport:
    forbidden_paths: list[str] = field(default_factory=list)
    case_collisions: list[tuple[str, ...]] = field(default_factory=list)
    crlf_shell_scripts: list[str] = field(default_factory=list)
    unexpected_tracked_ignored_paths: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (
            self.forbidden_paths
            or self.case_collisions
            or self.crlf_shell_scripts
            or self.unexpected_tracked_ignored_paths
        )

    def render(self) -> str:
        lines = ["Release guardrails failed:"]
        if self.case_collisions:
            lines.append("")
            lines.append("Case-insensitive path collisions:")
            for group in self.case_collisions:
                lines.append(f"  - {' | '.join(group)}")
        if self.forbidden_paths:
            lines.append("")
            lines.append("Forbidden tracked paths:")
            for path in self.forbidden_paths:
                lines.append(f"  - {path}")
        if self.crlf_shell_scripts:
            lines.append("")
            lines.append("Shell scripts with CRLF line endings:")
            for path in self.crlf_shell_scripts:
                lines.append(f"  - {path}")
        if self.unexpected_tracked_ignored_paths:
            lines.append("")
            lines.append("Tracked files still matched by .gitignore:")
            for path in self.unexpected_tracked_ignored_paths:
                lines.append(f"  - {path}")
        return "\n".join(lines)


def list_tracked_paths(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def list_tracked_ignored_paths(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-ci", "--exclude-standard"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def find_case_collisions(paths: list[str]) -> list[tuple[str, ...]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        groups[path.casefold()].append(path)
    collisions = [
        tuple(sorted(group)) for group in groups.values() if len(group) > 1
    ]
    return sorted(collisions)


def find_forbidden_tracked_paths(paths: list[str]) -> list[str]:
    forbidden: list[str] = []
    for path in sorted(paths):
        pure_path = PurePosixPath(path)
        parts = pure_path.parts
        root = parts[0] if parts else ""
        name = pure_path.name
        if root in _FORBIDDEN_ROOTS:
            forbidden.append(path)
            continue
        if any(root.startswith(prefix) for prefix in _FORBIDDEN_ROOT_PREFIXES):
            forbidden.append(path)
            continue
        if any(segment in _FORBIDDEN_SEGMENTS for segment in parts):
            forbidden.append(path)
            continue
        if name in _FORBIDDEN_FILENAMES:
            forbidden.append(path)
            continue
        if name.startswith("._"):
            forbidden.append(path)
            continue
        if any(path.endswith(suffix) for suffix in _FORBIDDEN_SUFFIXES):
            forbidden.append(path)
    return forbidden


def find_unexpected_tracked_ignored_paths(paths: list[str]) -> list[str]:
    unexpected: list[str] = []
    for path in sorted(paths):
        if any(
            fnmatchcase(path, pattern) for pattern in _ALLOWED_TRACKED_IGNORED_PATTERNS
        ):
            continue
        unexpected.append(path)
    return unexpected


def find_crlf_shell_scripts(repo_root: Path, paths: list[str]) -> list[str]:
    offenders: list[str] = []
    for path in sorted(paths):
        if not path.endswith(".sh"):
            continue
        data = (repo_root / path).read_bytes()
        if b"\r" in data:
            offenders.append(path)
    return offenders


def validate_repository(
    repo_root: Path,
    *,
    tracked_paths: list[str] | None = None,
    tracked_ignored_paths: list[str] | None = None,
) -> ReleaseGuardrailReport:
    paths = tracked_paths if tracked_paths is not None else list_tracked_paths(repo_root)
    ignored_paths = (
        tracked_ignored_paths
        if tracked_ignored_paths is not None
        else list_tracked_ignored_paths(repo_root)
    )
    return ReleaseGuardrailReport(
        forbidden_paths=find_forbidden_tracked_paths(paths),
        case_collisions=find_case_collisions(paths),
        crlf_shell_scripts=find_crlf_shell_scripts(repo_root, paths),
        unexpected_tracked_ignored_paths=find_unexpected_tracked_ignored_paths(
            ignored_paths
        ),
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    report = validate_repository(repo_root)
    if report.ok:
        print("Release guardrails passed.")
        return 0
    print(report.render())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
