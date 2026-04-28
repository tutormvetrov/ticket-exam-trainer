from __future__ import annotations

from app.release_guardrails import (
    find_case_collisions,
    find_crlf_shell_scripts,
    find_forbidden_tracked_paths,
    find_unexpected_tracked_ignored_paths,
    validate_repository,
)


def test_find_case_collisions_detects_casefold_duplicates() -> None:
    collisions = find_case_collisions(
        ["README.md", "docs/Quickstart.md", "docs/quickstart.md"]
    )

    assert collisions == [("docs/Quickstart.md", "docs/quickstart.md")]


def test_find_forbidden_tracked_paths_flags_transient_artifacts() -> None:
    forbidden = find_forbidden_tracked_paths(
        [
            "app/main.py",
            "tmp-build/output.txt",
            "ui_flet/__pycache__/state.cpython-312.pyc",
            "logs/Thumbs.db",
            "dist/Tezis.app/Contents/Info.plist",
        ]
    )

    assert forbidden == [
        "dist/Tezis.app/Contents/Info.plist",
        "logs/Thumbs.db",
        "tmp-build/output.txt",
        "ui_flet/__pycache__/state.cpython-312.pyc",
    ]


def test_find_crlf_shell_scripts_flags_only_shell_scripts(
    tmp_path,
) -> None:
    shell_script = tmp_path / "scripts" / "build_mac_app.sh"
    shell_script.parent.mkdir()
    shell_script.write_bytes(b"#!/usr/bin/env bash\r\necho test\r\n")
    python_file = tmp_path / "app.py"
    python_file.write_bytes(b"print('ok')\r\n")

    offenders = find_crlf_shell_scripts(
        tmp_path,
        ["scripts/build_mac_app.sh", "app.py"],
    )

    assert offenders == ["scripts/build_mac_app.sh"]


def test_find_unexpected_tracked_ignored_paths_allows_explicit_exceptions() -> None:
    unexpected = find_unexpected_tracked_ignored_paths(
        [
            "build/ai-generated/99-final-patches.json",
            "data/state_exam_public_admin_demo.db",
            "dist/Tezis.app/Contents/Info.plist",
        ]
    )

    assert unexpected == ["dist/Tezis.app/Contents/Info.plist"]


def test_validate_repository_returns_clean_report_for_safe_tree(tmp_path) -> None:
    shell_script = tmp_path / "scripts" / "build_mac_app.sh"
    shell_script.parent.mkdir()
    shell_script.write_bytes(b"#!/usr/bin/env bash\necho ok\n")
    installer_script = tmp_path / "scripts" / "installer" / "Tezis-Setup.iss"
    installer_script.parent.mkdir()
    installer_script.write_text(
        '#define AppId "{{11111111-2222-3333-4444-555555555555}}"\n',
        encoding="utf-8",
    )

    report = validate_repository(
        tmp_path,
        tracked_paths=["scripts/build_mac_app.sh", "app/main.py"],
        tracked_ignored_paths=[],
    )

    assert report.ok is True
    assert report.forbidden_paths == []
    assert report.case_collisions == []
    assert report.crlf_shell_scripts == []
    assert report.unexpected_tracked_ignored_paths == []
