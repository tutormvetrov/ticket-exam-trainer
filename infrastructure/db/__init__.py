"""Database infrastructure."""

from infrastructure.db.connection import connect, connect_initialized, get_database_path
from infrastructure.db.repository import KnowledgeRepository
from infrastructure.db.schema import initialize_schema

__all__ = [
    "KnowledgeRepository",
    "connect",
    "connect_initialized",
    "get_database_path",
    "initialize_schema",
]
