"""Build (or rebuild) the builtin knowledge database.

Idempotent: drops and recreates all data on every run, producing
byte-identical ULIDs from the same entry list.

Usage::

    python -m quantumvitas.mcp.knowledge.build_builtin
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from quantumvitas.mcp.knowledge.schema import init_db
from quantumvitas.mcp.knowledge.builtin_entries import BUILTIN_ENTRIES

# Crockford Base32 alphabet (ULID-compatible).
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_SALT = "qmatsuite-knowledge-builtin-v1"


def _deterministic_ulid(index: int, content_prefix: str) -> str:
    """Generate a deterministic ULID from entry index + content prefix."""
    seed = f"{_SALT}:{index}:{content_prefix[:60]}"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    value = int.from_bytes(digest[:16], "big")

    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5

    return "01K" + "".join(reversed(chars))[3:]


def _default_db_path() -> Path:
    from quantumvitas.core.paths import get_qmatsuite_home_root
    return get_qmatsuite_home_root() / "knowledge" / "builtin.db"


def build_builtin_db(output_path: Path | None = None) -> Path:
    """Build the builtin.db knowledge database.

    Drops all existing data and reinserts from ``BUILTIN_ENTRIES``.
    Returns the path to the database file.
    """
    db_path = output_path or _default_db_path()

    conn = init_db(db_path)
    try:
        # Wipe existing data for idempotent rebuild.
        conn.execute("DELETE FROM insights")
        # Rebuild FTS index after delete.
        conn.execute("INSERT INTO insights_fts(insights_fts) VALUES('rebuild')")
        conn.commit()

        now = datetime.now(timezone.utc).isoformat()

        for i, entry in enumerate(BUILTIN_ENTRIES):
            ulid = _deterministic_ulid(i, entry["content"])
            conn.execute(
                """
                INSERT INTO insights (
                    id, grade,
                    scope_engine, scope_workflow, scope_system_type, scope_method,
                    content, confidence,
                    source_type, source_origin,
                    created_by, tags,
                    status, upvotes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, ?, ?)
                """,
                (
                    ulid,
                    entry["grade"],
                    entry.get("scope_engine", "*"),
                    entry.get("scope_workflow", "*"),
                    entry.get("scope_system_type", "*"),
                    entry.get("scope_method", "*"),
                    entry["content"],
                    entry.get("confidence", "medium"),
                    entry.get("source_type", "builtin"),
                    entry.get("source_origin"),
                    entry.get("created_by", "qmatsuite-builtin"),
                    entry.get("tags"),
                    now,
                    now,
                ),
            )

        conn.commit()
    finally:
        conn.close()

    return db_path


if __name__ == "__main__":
    path = build_builtin_db()
    print(f"Built builtin.db at {path} ({len(BUILTIN_ENTRIES)} entries)")
