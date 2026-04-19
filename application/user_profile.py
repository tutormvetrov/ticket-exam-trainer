"""Локальный профиль пользователя — имя и аватар-emoji.

Хранится в `<workspace>/app_data/profile.json`. Одна запись на установку.
Отсутствие файла означает «профиль ещё не создан» — UI ведёт на onboarding.

Используется Journal/TopBar для обращения по имени и показа аватара.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from app.json_storage import load_json_dict, save_json_dict


AVATAR_CHOICES: tuple[str, ...] = (
    "🦉", "🐺", "🦊", "🐻", "🦁", "🐢",
    "🦅", "🐉", "🌲", "🌊", "🔥", "⚡",
)

NAME_MIN = 2
NAME_MAX = 40


@dataclass(frozen=True)
class UserProfile:
    name: str
    avatar_emoji: str
    created_at: str


class ProfileStore:
    """Read/write `profile.json`. Одна точка доступа к профилю."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> UserProfile | None:
        if not self.path.exists():
            return None
        payload = load_json_dict(self.path)
        name = str(payload.get("name", "") or "").strip()
        avatar = str(payload.get("avatar_emoji", "") or "").strip()
        created_at = str(payload.get("created_at", "") or "").strip()
        if not name or not avatar:
            return None
        return UserProfile(name=name, avatar_emoji=avatar, created_at=created_at)

    def save(self, profile: UserProfile) -> None:
        save_json_dict(self.path, asdict(profile))

    def exists(self) -> bool:
        return self.load() is not None


def validate_name(raw: str) -> tuple[bool, str]:
    """Проверяет имя. Возвращает (ok, error_message).

    Ошибка на русском — текст можно вставлять прямо в UI.
    """
    cleaned = raw.strip()
    if len(cleaned) < NAME_MIN:
        return False, f"Имя слишком короткое — нужно минимум {NAME_MIN} символа."
    if len(cleaned) > NAME_MAX:
        return False, f"Имя слишком длинное — максимум {NAME_MAX} символов."
    return True, ""


def build_profile(name: str, avatar_emoji: str) -> UserProfile:
    """Собирает профиль с текущим timestamp. Предполагает валидный вход."""
    return UserProfile(
        name=name.strip(),
        avatar_emoji=avatar_emoji,
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
