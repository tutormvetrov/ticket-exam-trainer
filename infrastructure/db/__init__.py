"""Database infrastructure."""

from infrastructure.db.connection import connect, connect_initialized, get_database_path
from infrastructure.db.defense_repository import DefenseRepository
from infrastructure.db.dialogue_repository import DialogueRepository
from infrastructure.db.repository import KnowledgeRepository
from infrastructure.db.schema import initialize_schema

__all__ = [
    "DialogueRepository",
    "DefenseRepository",
    "KnowledgeRepository",
    "connect",
    "connect_initialized",
    "get_database_path",
    "initialize_schema",
]
