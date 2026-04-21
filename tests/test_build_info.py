from __future__ import annotations

import json
from pathlib import Path

from app.build_info import get_runtime_build_info, write_runtime_build_info


def test_build_info_prefers_runtime_json(tmp_path: Path) -> None:
    payload = {
        "version": "1.1.0-beta",
        "commit": "abc123def456",
        "built_at": "2026-04-11T16:20:00+03:00",
    }
    (tmp_path / "build_info.json").write_text(json.dumps(payload), encoding="utf-8")

    build_info = get_runtime_build_info(tmp_path)

    assert build_info.version == "1.1.0-beta"
    assert build_info.commit == "abc123def456"
    assert build_info.release_label == "v1.1.0-beta • abc123def456"


def test_build_info_falls_back_to_git_metadata(tmp_path: Path, monkeypatch) -> None:
    def fake_git_output(root: Path, *args: str) -> str:
        mapping = {
            ("describe", "--tags", "--abbrev=0"): "v2.5.1",
            ("rev-parse", "--short=12", "HEAD"): "deadbeefcafe",
            ("show", "-s", "--format=%cI", "HEAD"): "2026-04-11T16:30:00+03:00",
        }
        return mapping.get(args, "")

    monkeypatch.setattr("app.build_info._git_output", fake_git_output)

    build_info = get_runtime_build_info(tmp_path)

    assert build_info.version == "2.5.1"
    assert build_info.commit == "deadbeefcafe"
    assert build_info.source == "git"


def test_build_info_falls_back_to_bundle_root_when_workspace_root_has_no_json(tmp_path: Path, monkeypatch) -> None:
    workspace_root = tmp_path / "workspace"
    bundle_root = tmp_path / "bundle"
    workspace_root.mkdir()
    bundle_root.mkdir()
    (bundle_root / "build_info.json").write_text(
        json.dumps({"version": "2.5.1", "commit": "abc123"}),
        encoding="utf-8",
    )

    monkeypatch.setattr("app.build_info.get_app_root", lambda: bundle_root)
    monkeypatch.setattr("app.build_info._git_output", lambda *_args: "")

    build_info = get_runtime_build_info(workspace_root)

    assert build_info.version == "2.5.1"
    assert build_info.commit == "abc123"
    assert build_info.source == "build-info-json"


def test_write_runtime_build_info_normalizes_version_tag(tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "build" / "build_info.json"
    monkeypatch.setattr("app.build_info._git_output", lambda *_args: "deadbeefcafe")

    info = write_runtime_build_info(output_path, version="v2.5.1", built_at="2026-04-21T19:00:00+03:00")

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["version"] == "2.5.1"
    assert payload["commit"] == "deadbeefcafe"
    assert info.release_label == "v2.5.1 • deadbeefcafe"
