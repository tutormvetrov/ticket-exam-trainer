from __future__ import annotations

import json
from pathlib import Path

from app.build_info import get_runtime_build_info


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
            ("rev-parse", "--short=12", "HEAD"): "deadbeefcafe",
            ("show", "-s", "--format=%cI", "HEAD"): "2026-04-11T16:30:00+03:00",
        }
        return mapping.get(args, "")

    monkeypatch.setattr("app.build_info._git_output", fake_git_output)

    build_info = get_runtime_build_info(tmp_path)

    assert build_info.commit == "deadbeefcafe"
    assert build_info.source == "git"
