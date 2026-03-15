"""Knowledge infrastructure for QMatSuite MCP server."""

from __future__ import annotations

from typing import Optional

_store = None


def get_knowledge_store():
    """Shared lazy singleton for the knowledge store (builtin + local).

    Returns a KnowledgeStore that searches both builtin.db and local.db.
    Builds builtin.db on first access if it's empty.
    """
    global _store
    if _store is None:
        from qmatsuite.mcp.knowledge.store import (
            KnowledgeStore,
            _builtin_enabled,
            _local_db_path,
        )
        from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db

        store = KnowledgeStore(local_db_path=_local_db_path())
        if _builtin_enabled() and store.count() == 0:
            store.close()
            build_builtin_db()
            store = KnowledgeStore(local_db_path=_local_db_path())
        _store = store
    return _store


def reset_knowledge_store() -> None:
    """Reset the singleton (for testing)."""
    global _store
    if _store is not None:
        _store.close()
    _store = None
