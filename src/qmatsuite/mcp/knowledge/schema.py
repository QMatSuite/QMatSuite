"""SQLite schema for the knowledge database.

Per AGENT_INTEGRATION_DESIGN.md Section 7.4: insights table with FTS5
full-text search and scope indexes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    grade TEXT NOT NULL,
    scope_engine TEXT DEFAULT '*',
    scope_workflow TEXT DEFAULT '*',
    scope_system_type TEXT DEFAULT '*',
    scope_method TEXT DEFAULT '*',
    scope_extra TEXT DEFAULT '{}',
    content TEXT NOT NULL,
    confidence TEXT DEFAULT 'medium',
    source_type TEXT NOT NULL DEFAULT 'local',
    source_pack_id TEXT,
    source_origin TEXT,
    provenance_ref TEXT,
    created_by TEXT NOT NULL,
    tags TEXT,
    status TEXT DEFAULT 'under_review',
    superseded_by TEXT,
    deprecated_reason TEXT,
    merged_into TEXT,
    last_validated TEXT,
    contradiction_count INTEGER DEFAULT 0,
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (superseded_by) REFERENCES insights(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS insights_fts USING fts5(
    content, tags, scope_engine, scope_system_type,
    content='insights', content_rowid='rowid'
);

-- Triggers to keep FTS5 in sync with the insights table.
CREATE TRIGGER IF NOT EXISTS insights_ai AFTER INSERT ON insights BEGIN
    INSERT INTO insights_fts(rowid, content, tags, scope_engine, scope_system_type)
    VALUES (new.rowid, new.content, new.tags, new.scope_engine, new.scope_system_type);
END;

CREATE TRIGGER IF NOT EXISTS insights_ad AFTER DELETE ON insights BEGIN
    INSERT INTO insights_fts(insights_fts, rowid, content, tags, scope_engine, scope_system_type)
    VALUES ('delete', old.rowid, old.content, old.tags, old.scope_engine, old.scope_system_type);
END;

CREATE TRIGGER IF NOT EXISTS insights_au AFTER UPDATE ON insights BEGIN
    INSERT INTO insights_fts(insights_fts, rowid, content, tags, scope_engine, scope_system_type)
    VALUES ('delete', old.rowid, old.content, old.tags, old.scope_engine, old.scope_system_type);
    INSERT INTO insights_fts(rowid, content, tags, scope_engine, scope_system_type)
    VALUES (new.rowid, new.content, new.tags, new.scope_engine, new.scope_system_type);
END;

CREATE INDEX IF NOT EXISTS idx_insights_grade ON insights(grade);
CREATE INDEX IF NOT EXISTS idx_insights_scope ON insights(scope_engine, scope_workflow, scope_system_type, scope_method);
CREATE INDEX IF NOT EXISTS idx_insights_source ON insights(source_type);
CREATE INDEX IF NOT EXISTS idx_insights_status ON insights(status);
CREATE INDEX IF NOT EXISTS idx_insights_confidence ON insights(confidence);
"""


def _migrate_metadata_column(conn: sqlite3.Connection) -> None:
    """Add ``metadata`` column to existing databases that lack it."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(insights)").fetchall()}
    if "metadata" not in cols:
        conn.execute("ALTER TABLE insights ADD COLUMN metadata TEXT DEFAULT '{}'")
        conn.commit()


def _migrate_downvotes_column(conn: sqlite3.Connection) -> None:
    """Add ``downvotes`` column to existing databases that lack it."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(insights)").fetchall()}
    if "downvotes" not in cols:
        conn.execute("ALTER TABLE insights ADD COLUMN downvotes INTEGER DEFAULT 0")
        conn.commit()


def _migrate_active_to_confirmed(conn: sqlite3.Connection) -> None:
    """One-time: rename status ``active`` → ``confirmed`` for existing entries."""
    cur = conn.execute("SELECT COUNT(*) FROM insights WHERE status = 'active'")
    if cur.fetchone()[0] > 0:
        conn.execute("UPDATE insights SET status = 'confirmed' WHERE status = 'active'")
        conn.commit()


def _migrate_stale_schema(conn: sqlite3.Connection) -> None:
    """Drop and recreate insights if it uses the old prototype schema.

    The old 7-column schema (id, content, grade, status, metadata,
    created_at, updated_at) is missing scope columns needed by the
    current DDL indexes and FTS triggers.  Detect this by checking
    for the ``scope_engine`` column; if absent, drop everything and
    let the DDL recreate from scratch.
    """
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='insights'"
    ).fetchall()
    if not rows:
        return  # Table doesn't exist yet — nothing to migrate
    cols = {row[1] for row in conn.execute("PRAGMA table_info(insights)").fetchall()}
    if "scope_engine" in cols:
        return  # Current schema — no migration needed
    # Old prototype schema: drop all related objects
    conn.executescript("""
        DROP TRIGGER IF EXISTS insights_ai;
        DROP TRIGGER IF EXISTS insights_ad;
        DROP TRIGGER IF EXISTS insights_au;
        DROP INDEX IF EXISTS idx_insights_grade;
        DROP INDEX IF EXISTS idx_insights_scope;
        DROP INDEX IF EXISTS idx_insights_source;
        DROP INDEX IF EXISTS idx_insights_status;
        DROP INDEX IF EXISTS idx_insights_confidence;
        DROP TABLE IF EXISTS insights_fts;
        DROP TABLE IF EXISTS insights;
    """)
    conn.commit()


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create or open a knowledge database, ensuring the schema exists.

    Idempotent: safe to call on an already-initialized database.

    Returns an open connection with ``row_factory = sqlite3.Row``.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _migrate_stale_schema(conn)
    conn.executescript(SCHEMA_DDL)
    conn.commit()
    _migrate_metadata_column(conn)
    _migrate_downvotes_column(conn)
    _migrate_active_to_confirmed(conn)
    return conn
