from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SectionData:
    title: str
    tickets_count: int


@dataclass(slots=True)
class TicketData:
    number: int
    title: str
    status: str


@dataclass(slots=True)
class DocumentData:
    id: str
    title: str
    file_type: str
    subject: str
    imported_at: str
    size: str
    status: str
    answer_profile_label: str = "Обычный билет"
    display_tickets_count: int = 0
    sections: list[SectionData] = field(default_factory=list)
    tickets: list[TicketData] = field(default_factory=list)

    @property
    def sections_count(self) -> int:
        return len(self.sections)

    @property
    def tickets_count(self) -> int:
        return self.display_tickets_count or len(self.tickets)


@dataclass(slots=True)
class SubjectData:
    name: str
    documents: int
    sections: int
    tickets: int
    progress: int
    accent: str


@dataclass(slots=True)
class SessionData:
    title: str
    timestamp: str
    score: int
    tone: str


@dataclass(slots=True)
class TrainingModeData:
    key: str
    title: str
    description: str
    icon_text: str
    tint: str
    border: str
