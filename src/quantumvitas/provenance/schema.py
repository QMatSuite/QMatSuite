"""
SQLite schema for provenance database.

Per PROVENANCE_VERSIONED_HISTORY_SPEC.md §3.3:
- operations table: Records all SSOT-writing operations
- runs table: Records calculation run events
- run_steps table: Normalized per-step execution records
- cas_objects table: Metadata for objects in .cas/objects/

Law P4 (Append-Only Timeline): Events and runs are NEVER deleted or modified.
"""

from __future__ import annotations

CURRENT_SCHEMA_VERSION = 1

# SQLite DDL for provenance database
SCHEMA_DDL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

--------------------------------------------------------------------------------
-- OPERATIONS TABLE: Records all SSOT-writing operations
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operations (
    -- Identity
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,            -- ULID for external references

    -- Classification
    op_type TEXT NOT NULL,                -- OperationType enum value

    -- Timing
    timestamp TEXT NOT NULL,              -- ISO8601 with microseconds

    -- Actor
    actor TEXT NOT NULL,                  -- ActorType enum value

    -- Scope & Target
    scope TEXT NOT NULL,                  -- ScopeType enum value
    target_ulid TEXT,                     -- ULID of affected entity (calc, step, structure)
    calc_ulid TEXT,                       -- Calculation ULID (for calc/step scoped events)

    -- Source (for audit)
    source TEXT NOT NULL,                 -- Kernel method name
    facade_endpoint TEXT,                 -- Optional higher-level endpoint
    request_id TEXT,                      -- Optional correlation ID

    -- Payload: operation-specific data + diff summary
    payload TEXT NOT NULL DEFAULT '{}',   -- JSON: includes changed_paths, summary, etc.

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for operations table
CREATE INDEX IF NOT EXISTS idx_operations_timestamp ON operations(timestamp);
CREATE INDEX IF NOT EXISTS idx_operations_op_type ON operations(op_type);
CREATE INDEX IF NOT EXISTS idx_operations_target_ulid ON operations(target_ulid);
CREATE INDEX IF NOT EXISTS idx_operations_calc_ulid ON operations(calc_ulid);
CREATE INDEX IF NOT EXISTS idx_operations_actor ON operations(actor);
CREATE INDEX IF NOT EXISTS idx_operations_request_id ON operations(request_id);

--------------------------------------------------------------------------------
-- RUNS TABLE: Records calculation run events
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS runs (
    -- Identity
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ulid TEXT NOT NULL UNIQUE,        -- Run ULID

    -- Association
    calc_ulid TEXT NOT NULL,              -- Calculation ULID
    project_ulid TEXT,                    -- Project ULID

    -- Timing
    started_at TEXT NOT NULL,             -- ISO8601
    finished_at TEXT,                     -- ISO8601 (NULL if running/aborted)

    -- Status
    status TEXT NOT NULL DEFAULT 'running',  -- 'running' | 'success' | 'failed' | 'aborted'
    error_message TEXT,                   -- Error details (if failed/aborted)

    -- Snapshot reference (Tier-0 CAS object)
    snapshot_sha TEXT,                    -- SHA-256 of pre-run SSOT snapshot in CAS

    -- Engine info
    engine TEXT,                          -- Engine family (qe, vasp, etc.)

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_runs_calc_ulid ON runs(calc_ulid);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at);

--------------------------------------------------------------------------------
-- RUN_STEPS TABLE: Normalized per-step execution records
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS run_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ulid TEXT NOT NULL,               -- FK to runs.run_ulid
    step_ulid TEXT NOT NULL,              -- Step ULID
    step_index INTEGER NOT NULL,          -- Position in execution order (0-based)

    -- Timing
    started_at TEXT,                      -- ISO8601
    finished_at TEXT,                     -- ISO8601

    -- Status
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'running' | 'success' | 'failed' | 'skipped'

    -- Snapshot reference (Tier-0)
    snapshot_sha TEXT,                    -- SHA-256 of step YAML snapshot in CAS

    -- Artifact collection reference (Tier-2/3)
    artifact_collection_sha TEXT,         -- SHA-256 of collection manifest in CAS

    -- Optional digest
    digest_sha TEXT,                      -- SHA-256 of step digest in CAS

    UNIQUE(run_ulid, step_ulid),
    FOREIGN KEY (run_ulid) REFERENCES runs(run_ulid)
);

CREATE INDEX IF NOT EXISTS idx_run_steps_run_ulid ON run_steps(run_ulid);
CREATE INDEX IF NOT EXISTS idx_run_steps_step_ulid ON run_steps(step_ulid);

--------------------------------------------------------------------------------
-- CAS_OBJECTS TABLE: Metadata for objects in .cas/objects/
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cas_objects (
    sha256 TEXT PRIMARY KEY,              -- Content hash
    tier INTEGER NOT NULL,                -- 0, 0.5, 1, 2, or 3
    size_bytes INTEGER NOT NULL,          -- Object size
    content_type TEXT,                    -- MIME type hint
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_referenced_at TEXT,              -- Updated on access (for LRU)
    deleted BOOLEAN NOT NULL DEFAULT 0    -- Soft-delete for GC
);

CREATE INDEX IF NOT EXISTS idx_cas_objects_tier ON cas_objects(tier);
CREATE INDEX IF NOT EXISTS idx_cas_objects_deleted ON cas_objects(deleted);
"""


def create_schema(conn) -> None:
    """
    Create provenance database schema.

    Idempotent: can be called multiple times safely.

    Args:
        conn: SQLite connection
    """
    conn.executescript(SCHEMA_DDL)

    # Check if we need to insert the initial version
    cursor = conn.execute("SELECT COUNT(*) FROM schema_version")
    if cursor.fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (CURRENT_SCHEMA_VERSION,)
        )

    conn.commit()


def get_schema_version(conn) -> int:
    """
    Get current schema version.

    Args:
        conn: SQLite connection

    Returns:
        Current schema version number
    """
    cursor = conn.execute("SELECT MAX(version) FROM schema_version")
    result = cursor.fetchone()
    return result[0] if result and result[0] else 0


def migrate_schema(conn, from_version: int, to_version: int) -> None:
    """
    Migrate schema from one version to another.

    Args:
        conn: SQLite connection
        from_version: Current schema version
        to_version: Target schema version
    """
    # Future migrations would be implemented here
    # For now, we only have version 1
    pass
