"""Локальный профиль пользователя — имя и аватар-emoji.

Хранится в `<workspace>/app_data/profile.json`. Одна запись на установку.
Отсутствие файла означает «профиль ещё не создан» — UI ведёт на onboarding.

Используется Journal/TopBar для обращения по имени и показа аватара.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from app.json_storage import load_json_dict, save_json_dict

AVATAR_CHOICES: tuple[str, ...] = (
    "🦉", "🐺", "🦊", "🐻", "🦁", "🐢",
    "🦅", "🐉", "🌲", "🌊", "🔥", "⚡",
)

NAME_MIN = 2
NAME_MAX = 40

# Каталог доступных курсов. Привязка курса — к профилю (выбирается в онбординге).
# Когда добавляем курс — расширяем этот список + завозим seed/импорт PDF в БД.
COURSE_CATALOG: tuple[dict[str, str], ...] = (
    {
        "exam_id": "exam-state-mde-gmu-2024",
        "short_title": "Госэкзамен по ГМУ",
        "long_title":  "МДЭ ГМУ ГАРФ (2024)",
        "description": "208 билетов · программа «Государственное администрирование»",
    },
    {
        "exam_id": "exam-state-mde-ai-2024",
        "short_title": "Госэкзамен по ИИ",
        "long_title":  "МДЭ ИИ и Цифровизация в ГА (2024)",
        "description": "190 билетов · программа «ИИ и Цифровизация в государственном администрировании»",
    },
)

DEFAULT_EXAM_ID = "exam-state-mde-gmu-2024"


@dataclass(frozen=True)
class UserProfile:
    name: str
    avatar_emoji: str
    created_at: str
    active_exam_id: str = DEFAULT_EXAM_ID
    exam_date: str | None = None             # ISO YYYY-MM-DD; None = не задана
    reminder_enabled: bool = False           # включить мягкие напоминания
    reminder_time: str = "10:00"             # HH:MM локального времени


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
        active_exam_id = str(payload.get("active_exam_id", "") or "").strip() or DEFAULT_EXAM_ID
        exam_date_raw = payload.get("exam_date")
        exam_date = str(exam_date_raw).strip() if exam_date_raw else None
        reminder_enabled = bool(payload.get("reminder_enabled", False))
        reminder_time = str(payload.get("reminder_time", "10:00") or "10:00").strip() or "10:00"
        if not name or not avatar:
            return None
        return UserProfile(
            name=name,
            avatar_emoji=avatar,
            created_at=created_at,
            active_exam_id=active_exam_id,
            exam_date=exam_date,
            reminder_enabled=reminder_enabled,
            reminder_time=reminder_time,
        )

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


def build_profile(
    name: str,
    avatar_emoji: str,
    active_exam_id: str = DEFAULT_EXAM_ID,
) -> UserProfile:
    """Собирает профиль с текущим timestamp. Предполагает валидный вход."""
    return UserProfile(
        name=name.strip(),
        avatar_emoji=avatar_emoji,
        created_at=datetime.now().isoformat(timespec="seconds"),
        active_exam_id=active_exam_id,
    )
