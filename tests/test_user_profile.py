"""Тесты локального профиля пользователя."""

from __future__ import annotations

from pathlib import Path

from application.user_profile import (
    AVATAR_CHOICES,
    ProfileStore,
    build_profile,
    validate_exam_date,
    validate_name,
    validate_reminder_time,
)


def test_validate_name_rejects_too_short() -> None:
    ok, err = validate_name("М")
    assert not ok
    assert "короткое" in err


def test_validate_name_rejects_too_long() -> None:
    ok, err = validate_name("М" * 100)
    assert not ok
    assert "длинное" in err


def test_validate_name_accepts_two_chars() -> None:
    ok, err = validate_name("Ми")
    assert ok
    assert err == ""


def test_validate_name_trims_whitespace() -> None:
    ok, _ = validate_name("   Миша   ")
    assert ok


def test_build_profile_sets_timestamp_and_trims() -> None:
    profile = build_profile("  Миша  ", "🦉")
    assert profile.name == "Миша"
    assert profile.avatar_emoji == "🦉"
    assert profile.created_at  # ISO-8601 string


def test_validate_exam_date_accepts_empty_and_iso_date() -> None:
    assert validate_exam_date("") == (True, "")
    assert validate_exam_date("2026-06-15") == (True, "")


def test_validate_exam_date_rejects_bad_format() -> None:
    ok, err = validate_exam_date("15.06.2026")
    assert not ok
    assert "ГГГГ-ММ-ДД" in err


def test_validate_reminder_time_accepts_hh_mm() -> None:
    assert validate_reminder_time("10:00") == (True, "")


def test_validate_reminder_time_rejects_invalid_values() -> None:
    for value in ("25:00", "утро"):
        ok, err = validate_reminder_time(value)
        assert not ok
        assert "ЧЧ:ММ" in err


def test_build_profile_saves_exam_date_and_reminder() -> None:
    profile = build_profile(
        "Миша",
        "🦉",
        active_exam_id="exam-state-mde-ai-2024",
        exam_date="2026-06-15",
        reminder_enabled=True,
        reminder_time="09:30",
    )
    assert profile.active_exam_id == "exam-state-mde-ai-2024"
    assert profile.exam_date == "2026-06-15"
    assert profile.reminder_enabled is True
    assert profile.reminder_time == "09:30"


def test_profile_store_round_trip(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profile.json")
    assert store.load() is None
    assert not store.exists()

    profile = build_profile("Миша", "🦉")
    store.save(profile)

    assert store.exists()
    loaded = store.load()
    assert loaded is not None
    assert loaded.name == "Миша"
    assert loaded.avatar_emoji == "🦉"
    assert loaded.created_at == profile.created_at


def test_profile_store_returns_none_on_empty_name(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text('{"name": "", "avatar_emoji": "🦉", "created_at": "x"}', encoding="utf-8")
    store = ProfileStore(path)
    assert store.load() is None


def test_profile_store_returns_none_on_empty_avatar(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text('{"name": "Миша", "avatar_emoji": "", "created_at": "x"}', encoding="utf-8")
    store = ProfileStore(path)
    assert store.load() is None


def test_profile_store_handles_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text("{{not valid json", encoding="utf-8")
    store = ProfileStore(path)
    # load_json_dict quarantines corrupt files → store.load() returns None
    assert store.load() is None


def test_avatar_choices_are_non_empty() -> None:
    assert len(AVATAR_CHOICES) == 12
    assert all(isinstance(avatar, str) and len(avatar) >= 1 for avatar in AVATAR_CHOICES)
