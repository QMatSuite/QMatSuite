# Provenance / Versioned History System Specification

**Status:** Draft v1.0
**Author:** Architecture Team
**Date:** 2026-02-05
**Target Implementer:** Auto (Claude)

---

## Table of Contents

1. [Introduction and Goals](#1-introduction-and-goals)
2. [Invariants and Laws](#2-invariants-and-laws)
3. [Data Model](#3-data-model)
4. [Locking and Concurrency Model](#4-locking-and-concurrency-model)
5. [MVP Workflows](#5-mvp-workflows)
6. [Engine Integration Points](#6-engine-integration-points)
7. [GC and Retention Policies](#7-gc-and-retention-policies)
8. [Testing Plan](#8-testing-plan)
9. [Migration and Compatibility](#9-migration-and-compatibility)
10. [Future Enhancements](#10-future-enhancements)

---

## 1. Introduction and Goals

### 1.1 Problem Statement

QMatSuite currently maintains a clean filesystem UX where `calc/raw/` contains only the "current" results (overwritten on each run). Users should not see versioned folders cluttering their workspace. However, we need:

- **Strong provenance**: Track who did what, when, and why
- **Rollback capability**: Restore previous states without manual backup management
- **Agent memory**: Provide queryable history for AI agents to learn from past runs
- **Audit trail**: Complete record of all operations for reproducibility

### 1.2 Design Philosophy

This system follows a **"behind-the-scenes"** approach:

1. **Present World SSOT Unchanged**: The authoritative truth remains the YAML/JSON file tree (`project.qv.yml`, `calculation.yaml`, `step.yaml`, structure resources). This is what gets read at runtime.

2. **History World is Auxiliary**: SQLite database and Content-Addressed Store (CAS) are historical records. Deleting them must leave the project fully runnable—just losing history/rollback/analytics.

3. **Linear Timeline, Not DAG**: We use a simple linear event log, not an AiiDA-style directed acyclic graph. Cross-references are recorded as events, not modeled as graph edges.

4. **Explicit Intent, Not Inference**: Operations are recorded with explicit `OperationContext` passed through the call chain. We do not rely on observers/listeners to infer intent.

### 1.3 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PROJECT ROOT                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────┐  ┌──────────────────────────────┐ │
│  │         PRESENT WORLD (SSOT)        │  │       HISTORY WORLD          │ │
│  │  (Runtime reads/writes; canonical)  │  │   (Provenance/rollback)      │ │
│  ├─────────────────────────────────────┤  ├──────────────────────────────┤ │
│  │  project.qv.yml                     │  │  .provenance/                │ │
│  │  calculations/                      │  │  ├── provenance.db (SQLite)  │ │
│  │  ├── <calc_ulid>/                   │  │  └── .cas/                   │ │
│  │  │   ├── calculation.yaml           │  │      ├── objects/            │ │
│  │  │   ├── step_*.yaml                │  │      │   └── <sha256>/       │ │
│  │  │   └── raw/  (current outputs)    │  │      └── tmp/                │ │
│  │  pseudo/                            │  │                              │ │
│  │  potentials/                        │  │                              │ │
│  │  structures/                        │  │                              │ │
│  └─────────────────────────────────────┘  └──────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────┐                                   │
│  │         RUNTIME/EPHEMERAL           │                                   │
│  │  (Deletable, not truth)             │                                   │
│  ├─────────────────────────────────────┤                                   │
│  │  calculations/<ulid>/.run_tmp_info/ │                                   │
│  │  └── manifest.json                  │                                   │
│  │  .locks/                            │                                   │
│  │  └── edit.lock, run.lock            │                                   │
│  └─────────────────────────────────────┘                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Invariants and Laws

These invariants are BINDING and must be enforced via gate tests.

### Law P1: SSOT Separation (History World Independence)

> **The History World (SQLite + CAS) MUST NOT participate in any runtime logic.**

- Runtime execution, materialization, and skip decisions read ONLY from Present World SSOT files.
- Deleting `.provenance/` directory MUST leave the project fully runnable.
- No kernel code path may fail due to missing/corrupt provenance data.
- History data is "write-only from kernel perspective"—reads are for UI/agents/analytics only.

**Enforcement:** Gate test that deletes `.provenance/` before a run and verifies success.

### Law P2: OperationContext Required (Choke Point Rule)

> **Any write to Present World SSOT YAML MUST carry an explicit OperationContext.**

- `save_yaml_doc()` MUST require an `opctx` parameter.
- Calling `save_yaml_doc()` without `opctx` MUST raise a hard error (not warning).
- This guarantees all operations are recorded without scattered logging calls.

**Enforcement:** Gate test that verifies `save_yaml_doc(doc, path)` without opctx raises `OperationContextRequiredError`.

### Law P3: No Provenance-Dependent Skip Logic

> **Skip/rerun decisions MUST NOT consult provenance data.**

- Manifest-based incremental run (Constitution §5) uses only: kind, pseudo_set_sha, structure_sha, step_sha, done flag.
- The provenance system is for audit/rollback, not runtime optimization.

**Enforcement:** Gate test that skip logic never imports from `quantumvitas.provenance`.

### Law P4: Append-Only Timeline

> **The SQLite timeline is append-only. Events are NEVER deleted or modified.**

- Operations and runs are immutable once recorded.
- Corrections are recorded as new events (e.g., `CORRECTION` event type).
- GC may delete CAS blobs, but SQLite event references remain (with `blob_deleted=true` flag if needed).

**Enforcement:** Schema has no UPDATE/DELETE statements for events table; audit trigger logs any attempts.

### Law P5: CAS Integrity

> **CAS objects are immutable and content-addressed by SHA-256.**

- Object path is derived from hash: `.cas/objects/<first2>/<rest_of_hash>`
- Once written, a CAS object is never modified.
- Duplicate writes (same hash) are no-ops.
- GC may delete objects per tier policy, but must verify no live references first.

**Enforcement:** Gate test that writing same content twice produces same hash; modification attempts fail.

### Law P6: Lock Ordering

> **Locks MUST be acquired in canonical order: edit.lock → provenance.lock**

- If both locks are needed, edit.lock is acquired first.
- This prevents deadlocks between YAML writes and provenance recording.
- Provenance recording should occur AFTER YAML write commits (inside edit.lock critical section).

**Enforcement:** Concurrency gate test with multi-threaded writers.

### Law P7: Graceful Degradation

> **Provenance failures MUST NOT fail YAML writes.**

- If SQLite append fails after YAML write succeeds, log warning and continue.
- Project remains runnable; provenance gap is recorded when possible.
- Best-effort retry is optional (not required for MVP).

**Enforcement:** Integration test that corrupts provenance.db and verifies YAML operations continue.

---

## 3. Data Model

### 3.1 Directory Layout

```
project_root/
├── .provenance/                          # NEW: Provenance root
│   ├── provenance.db                     # SQLite database (timeline + metadata)
│   ├── provenance.lock                   # Lock file for SQLite writes
│   └── .cas/                             # Content-Addressed Store
│       ├── objects/                      # Immutable blob storage
│       │   ├── <first2>/                 # First 2 chars of sha256
│       │   │   └── <remaining62>         # Remaining 62 chars (raw blob)
│       │   └── ...
│       ├── tmp/                          # Temp staging for atomic writes
│       └── gc.lock                       # Lock for GC operations
├── project.qv.yml                        # Present World SSOT
├── calculations/                         # Present World SSOT
│   └── ...
└── ...                                   # Other Present World files
```

### 3.2 OperationContext Schema

```python
@dataclass(frozen=True, slots=True)
class OperationContext:
    """Mandatory context for all SSOT writes. Immutable and serializable."""

    op: OperationType              # Enum: what kind of operation
    actor: ActorType               # Enum: who initiated (human/agent/system)
    scope: ScopeType               # Enum: project/calc/step/structure
    source: str                    # Kernel public method name (e.g., "Calculation.add_step")
    payload: dict                  # Operation-specific data (JSON-serializable)
    timestamp: Optional[str]       # ISO8601; recorder sets if None
    facade_endpoint: Optional[str] # Optional: higher-level API endpoint
    request_id: Optional[str]      # Optional: correlation ID for multi-op requests

    def to_dict(self) -> dict:
        """Serialize for SQLite JSON column."""
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "OperationContext":
        """Deserialize from SQLite JSON column."""
        ...


class OperationType(str, Enum):
    """Exhaustive list of operation types."""

    # Project-level
    PROJECT_CREATE = "project_create"
    PROJECT_UPDATE = "project_update"

    # Calculation-level
    CALC_CREATE = "calc_create"
    CALC_UPDATE = "calc_update"
    CALC_DELETE = "calc_delete"
    CALC_COPY = "calc_copy"
    CALC_FORK = "calc_fork"

    # Step-level
    STEP_ADD = "step_add"
    STEP_UPDATE = "step_update"
    STEP_REMOVE = "step_remove"
    STEP_REORDER = "step_reorder"

    # Preset operations
    PRESET_SELECT = "preset_select"
    PRESET_APPLY = "preset_apply"
    PRESET_CLEAR = "preset_clear"

    # Structure operations
    STRUCTURE_CREATE = "structure_create"
    STRUCTURE_UPDATE = "structure_update"
    STRUCTURE_IMPORT = "structure_import"
    RELAX_PROMOTE = "relax_promote"       # Relaxed structure promoted to resource

    # Species/Pseudo
    SPECIES_MAP_UPDATE = "species_map_update"
    PSEUDO_ASSIGN = "pseudo_assign"

    # Run operations
    RUN_START = "run_start"
    RUN_COMPLETE = "run_complete"
    RUN_ABORT = "run_abort"

    # Rollback/Restore
    RESTORE = "restore"                   # Restore from snapshot
    ROLLBACK = "rollback"                 # Rollback to previous state

    # Misc
    SEED = "seed"                         # Initial state capture
    CORRECTION = "correction"             # Manual correction event
    CUSTOM = "custom"                     # Extension point


class ActorType(str, Enum):
    HUMAN = "human"      # User-initiated via UI/CLI
    AGENT = "agent"      # AI agent initiated
    SYSTEM = "system"    # System-initiated (auto-saves, migrations, etc.)


class ScopeType(str, Enum):
    PROJECT = "project"
    CALC = "calc"
    STEP = "step"
    STRUCTURE = "structure"
    RESOURCE = "resource"  # Pseudo, potential, etc.
```

### 3.3 SQLite Schema

```sql
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO schema_version (version) VALUES (1);

-- Main timeline: unified events table
-- All events (operations + runs) in chronological order
CREATE TABLE IF NOT EXISTS events (
    -- Identity
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,            -- ULID for external references

    -- Classification
    event_kind TEXT NOT NULL,             -- 'operation' | 'run_start' | 'run_complete' | 'run_abort'
    op_type TEXT,                         -- OperationType enum value (for operations)

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

    -- Payload
    payload TEXT NOT NULL DEFAULT '{}',   -- JSON: operation-specific data

    -- Snapshot references (for operations that modify SSOT)
    before_snapshot_sha TEXT,             -- SHA-256 of before state in CAS
    after_snapshot_sha TEXT,              -- SHA-256 of after state in CAS

    -- Run-specific fields (for run events)
    run_ulid TEXT,                        -- Links run events together
    steps_json TEXT,                      -- JSON array of step execution records (run_complete only)
    status TEXT,                          -- 'success' | 'failed' | 'aborted' (run_complete/abort only)
    error_message TEXT,                   -- Error details (if failed/aborted)

    -- Indexes for common queries
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_event_kind ON events(event_kind);
CREATE INDEX IF NOT EXISTS idx_events_op_type ON events(op_type);
CREATE INDEX IF NOT EXISTS idx_events_target_ulid ON events(target_ulid);
CREATE INDEX IF NOT EXISTS idx_events_calc_ulid ON events(calc_ulid);
CREATE INDEX IF NOT EXISTS idx_events_run_ulid ON events(run_ulid);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor);
CREATE INDEX IF NOT EXISTS idx_events_request_id ON events(request_id);

-- Step execution records within runs
-- Normalized for efficient per-step queries
CREATE TABLE IF NOT EXISTS run_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ulid TEXT NOT NULL,               -- Links to events.run_ulid
    step_ulid TEXT NOT NULL,              -- Step ULID
    step_index INTEGER NOT NULL,          -- Position in execution order (0-based)

    -- Snapshot references
    snapshot_sha TEXT NOT NULL,           -- Tier-0: YAML/structure snapshot in CAS

    -- Artifact collection
    artifact_collection_sha TEXT,         -- Tier-2/3: Collection manifest in CAS

    -- Execution details
    started_at TEXT,                      -- ISO8601
    finished_at TEXT,                     -- ISO8601
    status TEXT NOT NULL,                 -- 'pending' | 'running' | 'success' | 'failed' | 'skipped'

    -- Optional digest
    digest_sha TEXT,                      -- SHA-256 of step digest in CAS

    UNIQUE(run_ulid, step_ulid)
);

CREATE INDEX IF NOT EXISTS idx_run_steps_run_ulid ON run_steps(run_ulid);
CREATE INDEX IF NOT EXISTS idx_run_steps_step_ulid ON run_steps(step_ulid);

-- CAS object metadata
-- Tracks objects in .cas/objects/ with tier and retention info
CREATE TABLE IF NOT EXISTS cas_objects (
    sha256 TEXT PRIMARY KEY,              -- Content hash
    tier INTEGER NOT NULL,                -- 0, 1, 2, or 3
    size_bytes INTEGER NOT NULL,          -- Object size
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_referenced_at TEXT,              -- Updated on access (for LRU)
    ref_count INTEGER NOT NULL DEFAULT 1, -- Reference counting for GC
    content_type TEXT,                    -- MIME type hint
    deleted BOOLEAN NOT NULL DEFAULT 0    -- Soft-delete for GC
);

CREATE INDEX IF NOT EXISTS idx_cas_objects_tier ON cas_objects(tier);
CREATE INDEX IF NOT EXISTS idx_cas_objects_deleted ON cas_objects(deleted);

-- Agent journal entries (optional, for future agent memory)
CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid TEXT NOT NULL UNIQUE,

    -- Association
    run_ulid TEXT,                        -- Optional: associated run
    calc_ulid TEXT,                       -- Optional: associated calculation

    -- Content
    title TEXT NOT NULL,                  -- Short summary (FTS-indexed)
    tags TEXT,                            -- JSON array of tags
    body_sha TEXT,                        -- Full body stored in CAS (Tier-1)

    -- Timing
    timing TEXT NOT NULL,                 -- 'before_run' | 'after_run' | 'note'
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_journal_entries_run_ulid ON journal_entries(run_ulid);
CREATE INDEX IF NOT EXISTS idx_journal_entries_calc_ulid ON journal_entries(calc_ulid);

-- Full-text search for journal
CREATE VIRTUAL TABLE IF NOT EXISTS journal_fts USING fts5(
    title, tags,
    content='journal_entries',
    content_rowid='id'
);

-- Triggers for FTS sync
CREATE TRIGGER IF NOT EXISTS journal_ai AFTER INSERT ON journal_entries BEGIN
    INSERT INTO journal_fts(rowid, title, tags) VALUES (new.id, new.title, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS journal_ad AFTER DELETE ON journal_entries BEGIN
    INSERT INTO journal_fts(journal_fts, rowid, title, tags) VALUES('delete', old.id, old.title, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS journal_au AFTER UPDATE ON journal_entries BEGIN
    INSERT INTO journal_fts(journal_fts, rowid, title, tags) VALUES('delete', old.id, old.title, old.tags);
    INSERT INTO journal_fts(rowid, title, tags) VALUES (new.id, new.title, new.tags);
END;
```

### 3.4 CAS Object Format

#### 3.4.1 Path Derivation

```python
def cas_path(sha256: str) -> Path:
    """Derive CAS path from SHA-256 hash."""
    return CAS_ROOT / "objects" / sha256[:2] / sha256[2:]
```

Example: `sha256 = "a1b2c3d4..."` → `.cas/objects/a1/b2c3d4...`

#### 3.4.2 Snapshot Object (Tier-0)

Snapshots capture the complete SSOT state needed for restore:

```json
{
    "version": 1,
    "type": "snapshot",
    "scope": "calc",
    "timestamp": "2026-02-05T10:30:00.000000Z",
    "target_ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAV",

    "files": {
        "calculation.yaml": {
            "sha256": "...",
            "content_inline": true
        },
        "step_scf.yaml": {
            "sha256": "...",
            "content_inline": true
        },
        "step_bands.yaml": {
            "sha256": "...",
            "content_inline": true
        }
    },

    "structure_refs": {
        "main": {
            "ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
            "sha256": "..."
        }
    },

    "content": {
        "calculation.yaml": "<base64 or raw YAML>",
        "step_scf.yaml": "<base64 or raw YAML>",
        "step_bands.yaml": "<base64 or raw YAML>"
    }
}
```

#### 3.4.3 Artifact Collection Object (Tier-2/3)

Artifact collections are manifests pointing to individual artifact blobs:

```json
{
    "version": 1,
    "type": "artifact_collection",
    "step_ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
    "run_ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAX",
    "created_at": "2026-02-05T10:35:00.000000Z",

    "artifacts": [
        {
            "relative_path": "scf.out",
            "sha256": "...",
            "size_bytes": 102400,
            "mtime": "2026-02-05T10:34:55.000000Z",
            "tier": 2,
            "captured": true
        },
        {
            "relative_path": "scf.xml",
            "sha256": "...",
            "size_bytes": 51200,
            "mtime": "2026-02-05T10:34:56.000000Z",
            "tier": 2,
            "captured": true
        },
        {
            "relative_path": "outdir/pwscf.save/data-file-schema.xml",
            "sha256": null,
            "size_bytes": 10485760,
            "mtime": "2026-02-05T10:34:57.000000Z",
            "tier": 3,
            "captured": false,
            "skip_reason": "blacklisted_dir"
        }
    ],

    "engine": "qe",
    "step_type_spec": "qe_scf",

    "scan_metadata": {
        "blacklist_applied": ["outdir/"],
        "whitelist_patterns": ["*.out", "*.xml", "*.json"],
        "total_files_scanned": 15,
        "total_size_bytes": 20971520,
        "captured_size_bytes": 153600
    }
}
```

### 3.5 Storage Tiers

| Tier | Contents | Retention | GC Policy |
|------|----------|-----------|-----------|
| **Tier-0** | SSOT snapshots (YAML, structures) | Forever | Never auto-delete |
| **Tier-0.5** | Reproducibility assets (pseudos, potentials, basis) | Forever | Never auto-delete; content-addressed dedup |
| **Tier-1** | Derived outputs (reports, images, analysis) | Long-lived | Delete only on explicit user request |
| **Tier-2** | Raw artifacts from calc/raw (excluding blacklist) | Long-lived | Configurable; default keep all |
| **Tier-3** | Large optional outputs (wavefunction, CHGCAR, restart) | Rolling window | Keep last N per step/engine (default: 3) |

---

## 4. Locking and Concurrency Model

### 4.1 Lock Files

| Lock | Path | Purpose | Scope | Duration |
|------|------|---------|-------|----------|
| **edit.lock** | `calc/.locks/edit.lock` | YAML SSOT writes | Per-calculation | ~100ms |
| **run.lock** | `calc/.locks/run.lock` | Materialization + execution | Per-calculation | Long (run duration) |
| **provenance.lock** | `.provenance/provenance.lock` | SQLite writes | Project-wide | ~10ms |
| **gc.lock** | `.provenance/.cas/gc.lock` | CAS garbage collection | Project-wide | Variable |

### 4.2 Lock Ordering (Law P6)

To prevent deadlocks, locks MUST be acquired in this order:

```
1. edit.lock (if needed for YAML write)
2. provenance.lock (if needed for SQLite append)
3. gc.lock (only for GC operations, never during writes)
```

**Critical Rule:** Never acquire edit.lock while holding provenance.lock.

### 4.3 YAML Write + Provenance Recording Sequence

```
save_yaml_doc(doc, path, opctx) {
    1. Validate opctx is not None (raise OperationContextRequiredError)
    2. Compute before_snapshot = hash(current_file_content)

    WITH edit.lock:
        3. Write YAML to disk (atomic via temp + rename)
        4. Compute after_snapshot = hash(new_file_content)

        # Provenance recording inside edit.lock (MVP: synchronous)
        WITH provenance.lock:
            5. Store before/after snapshots in CAS (if not exists)
            6. Append operation event to SQLite
        # provenance.lock released

    # edit.lock released

    7. Return success
}
```

### 4.4 Failure Semantics (Law P7)

```
save_yaml_doc(doc, path, opctx) {
    ...
    WITH edit.lock:
        3. Write YAML to disk
        4. Compute after_snapshot

        TRY:
            WITH provenance.lock:
                5-6. CAS + SQLite writes
        CATCH ProvenanceError as e:
            # YAML write succeeded - log warning, don't fail
            log.warning(f"Provenance recording failed: {e}")
            # Optional: Queue for retry later
            provenance_retry_queue.append((opctx, before, after))

    # edit.lock released
    7. Return success  # YAML write succeeded regardless of provenance
}
```

### 4.5 Thread-Local Lock Tracking

Reuse existing pattern from `locking.py`:

```python
_HELD_PROVENANCE_LOCKS: threading.local = threading.local()

def _get_held_provenance_locks() -> set:
    if not hasattr(_HELD_PROVENANCE_LOCKS, 'locks'):
        _HELD_PROVENANCE_LOCKS.locks = set()
    return _HELD_PROVENANCE_LOCKS.locks

@contextmanager
def provenance_lock(project_root: Path, fail_fast: bool = False):
    """Acquire provenance.lock with reentrancy detection."""
    canonical = project_root.resolve()
    held = _get_held_provenance_locks()

    if canonical in held:
        raise LockReentrancyError(f"Already holding provenance.lock for {canonical}")

    lock_path = canonical / ".provenance" / "provenance.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with portalocker.Lock(lock_path, timeout=10 if not fail_fast else 0):
        held.add(canonical)
        try:
            yield
        finally:
            held.discard(canonical)
```

---

## 5. MVP Workflows

### 5.1 Parameter Edit via Preset Apply

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────┐
│  UI/CLI  │     │    Facade    │     │    Kernel    │     │ Provenance│
└────┬─────┘     └──────┬───────┘     └──────┬───────┘     └─────┬─────┘
     │                  │                    │                   │
     │ apply_preset()   │                    │                   │
     ├─────────────────>│                    │                   │
     │                  │                    │                   │
     │                  │ opctx = OpCtx(     │                   │
     │                  │   op=PRESET_APPLY, │                   │
     │                  │   actor=HUMAN,     │                   │
     │                  │   payload={preset} │                   │
     │                  │ )                  │                   │
     │                  │                    │                   │
     │                  │ calc.apply_preset( │                   │
     │                  │   preset, opctx)   │                   │
     │                  ├───────────────────>│                   │
     │                  │                    │                   │
     │                  │                    │ # Modify step.yaml│
     │                  │                    │ step.update(...)  │
     │                  │                    │                   │
     │                  │                    │ save_yaml_doc(    │
     │                  │                    │   doc, path, opctx│
     │                  │                    │ )                 │
     │                  │                    │                   │
     │                  │                    │ ┌───────────────┐ │
     │                  │                    │ │WITH edit.lock │ │
     │                  │                    │ │  Write YAML   │ │
     │                  │                    │ │               │ │
     │                  │                    │ │WITH prov.lock │ │
     │                  │                    │ ├───────────────┼>│
     │                  │                    │ │               │ │ Store CAS
     │                  │                    │ │               │ │ Append event
     │                  │                    │ │<──────────────┼─┤
     │                  │                    │ │               │ │
     │                  │                    │ └───────────────┘ │
     │                  │                    │                   │
     │                  │<───────────────────┤                   │
     │<─────────────────┤                    │                   │
     │  OK              │                    │                   │
```

### 5.2 Run Calculation

```
┌──────────┐     ┌────────┐     ┌────────┐     ┌─────────┐     ┌───────────┐
│  Runner  │     │ Recipe │     │Handler │     │Artifacts│     │ Provenance│
└────┬─────┘     └───┬────┘     └───┬────┘     └────┬────┘     └─────┬─────┘
     │               │              │               │                │
     │ run_ulid = generate_ulid()   │               │                │
     │               │              │               │                │
     │ # PRE-RUN: Capture snapshots │               │                │
     │───────────────────────────────────────────────────────────────>│
     │               │              │               │   Snapshot     │
     │               │              │               │   calc.yaml +  │
     │               │              │               │   step*.yaml   │
     │               │              │               │   → CAS Tier-0 │
     │<──────────────────────────────────────────────────────────────┤
     │               │              │               │                │
     │ # Record RUN_START event     │               │                │
     │───────────────────────────────────────────────────────────────>│
     │               │              │               │   events.append│
     │<──────────────────────────────────────────────────────────────┤
     │               │              │               │                │
     │ materialize() │              │               │                │
     ├──────────────>│              │               │                │
     │   JobGraph    │              │               │                │
     │<──────────────┤              │               │                │
     │               │              │               │                │
     │ FOR each job in JobGraph:    │               │                │
     │               │              │               │                │
     │   execute(job)│              │               │                │
     ├──────────────────────────────>│              │                │
     │               │              │ # Run engine  │                │
     │               │              │ subprocess    │                │
     │   JobResult   │              │               │                │
     │<──────────────────────────────┤              │                │
     │               │              │               │                │
     │   # POST-STEP: Scan artifacts│               │                │
     │   scan_artifacts(job)        │               │                │
     ├──────────────────────────────────────────────>│               │
     │               │              │               │ # Scan raw/    │
     │               │              │               │ # Apply blacklist
     │               │              │               │ # Hash changed │
     │   artifact_collection        │               │ # files        │
     │<─────────────────────────────────────────────┤                │
     │               │              │               │                │
     │   # Store artifact collection│               │                │
     │───────────────────────────────────────────────────────────────>│
     │               │              │               │   CAS Tier-2/3 │
     │               │              │               │   Insert       │
     │               │              │               │   run_steps    │
     │<──────────────────────────────────────────────────────────────┤
     │               │              │               │                │
     │ END FOR       │              │               │                │
     │               │              │               │                │
     │ # Record RUN_COMPLETE event  │               │                │
     │───────────────────────────────────────────────────────────────>│
     │               │              │               │   events.append│
     │<──────────────────────────────────────────────────────────────┤
     │               │              │               │                │
```

### 5.3 Rollback/Restore

```
┌──────────┐     ┌──────────────┐     ┌───────────┐     ┌─────────────┐
│  UI/CLI  │     │    Kernel    │     │ Provenance│     │ Present SSOT│
└────┬─────┘     └──────┬───────┘     └─────┬─────┘     └──────┬──────┘
     │                  │                   │                  │
     │ restore(snapshot_sha)                │                  │
     ├─────────────────>│                   │                  │
     │                  │                   │                  │
     │                  │ # Fetch snapshot  │                  │
     │                  │ from CAS          │                  │
     │                  ├──────────────────>│                  │
     │                  │   snapshot_data   │                  │
     │                  │<──────────────────┤                  │
     │                  │                   │                  │
     │                  │ opctx = OpCtx(    │                  │
     │                  │   op=RESTORE,     │                  │
     │                  │   payload={       │                  │
     │                  │     from_sha: ... │                  │
     │                  │   }               │                  │
     │                  │ )                 │                  │
     │                  │                   │                  │
     │                  │ # Write restored files              │
     │                  │ # to Present SSOT                   │
     │                  ├─────────────────────────────────────>│
     │                  │                   │  calc.yaml      │
     │                  │                   │  step*.yaml     │
     │                  │                   │  structures/*   │
     │                  │                   │                  │
     │                  │ # Each write via save_yaml_doc      │
     │                  │ # records RESTORE event             │
     │                  │ # with provenance                   │
     │                  │                   │                  │
     │                  │                   │                  │
     │<─────────────────┤                   │                  │
     │ OK + restore_summary                 │                  │
```

---

## 6. Engine Integration Points

### 6.1 Artifact Policy in Engine Recipes

Each engine driver MUST define artifact handling policy in its recipe:

```python
# src/quantumvitas/drivers/<engine>/recipe.py

class EngineRecipe(BaseRecipe):

    # Artifact policy (REQUIRED)
    ARTIFACT_POLICY = ArtifactPolicy(
        mode="blacklist",  # or "whitelist" for strict engines

        # Directories to exclude from capture (relative to calc/raw/)
        blacklist_dirs=[
            "outdir/",           # QE scratch (huge)
            "*.tmp/",            # Temp directories
        ],

        # File patterns to exclude
        blacklist_patterns=[
            "*.wfc*",            # Wavefunction files (huge)
            "*.chg",             # Charge density (huge)
            "*.restart*",        # Restart files
        ],

        # Tier-3 patterns (keep rolling window)
        tier3_patterns=[
            "*.save/",           # QE save directories
            "WAVECAR",           # VASP wavefunction
            "CHGCAR",            # VASP charge density
        ],

        # Whitelist overrides blacklist for specific files
        whitelist_patterns=[
            "*.out",             # Always capture output
            "*.xml",             # Always capture XML
            "*.json",            # Always capture JSON
            "*.log",             # Always capture logs
        ],
    )

    def get_artifact_policy(self) -> ArtifactPolicy:
        """Return artifact policy for this engine."""
        return self.ARTIFACT_POLICY
```

### 6.2 ArtifactPolicy Schema

```python
@dataclass(frozen=True, slots=True)
class ArtifactPolicy:
    """Engine-specific artifact capture policy."""

    mode: Literal["blacklist", "whitelist"]

    # Blacklist mode: capture everything EXCEPT these
    blacklist_dirs: List[str] = field(default_factory=list)
    blacklist_patterns: List[str] = field(default_factory=list)

    # Whitelist mode: capture ONLY these (plus mandatory outputs)
    whitelist_patterns: List[str] = field(default_factory=list)

    # Tier-3: large files that get rolling-window retention
    tier3_patterns: List[str] = field(default_factory=list)

    # Size limit: skip files larger than this (bytes)
    # -1 = no limit (default for Tier-2)
    tier2_max_size: int = -1
    tier3_max_size: int = -1

    def should_capture(self, rel_path: str, size_bytes: int) -> Tuple[bool, int, Optional[str]]:
        """
        Determine if a file should be captured.

        Returns:
            (should_capture: bool, tier: int, skip_reason: Optional[str])
        """
        ...
```

### 6.3 Default Policies per Engine Family

| Engine | Mode | Blacklist | Tier-3 |
|--------|------|-----------|--------|
| **QE** | blacklist | `outdir/`, `*.wfc*` | `*.save/` |
| **VASP** | blacklist | (none by default) | `WAVECAR`, `CHGCAR` |
| **ORCA** | blacklist | `*.tmp`, `*.gbw.bak*` | `*.gbw` |
| **PySCF** | blacklist | `*.chk.bak*` | `*.chk` |
| **CP2K** | blacklist | `*.restart*` | `*-RESTART.wfn` |
| **Gaussian** | blacklist | `*.rwf` | `*.chk` |
| **LAMMPS** | blacklist | (none) | `*.restart` |
| **xTB** | blacklist | (none) | (none) |

### 6.4 Artifact Scanner Implementation

```python
# src/quantumvitas/provenance/artifacts.py

@dataclass
class ScannedFile:
    rel_path: str
    abs_path: Path
    size_bytes: int
    mtime: float
    tier: int
    should_capture: bool
    skip_reason: Optional[str] = None
    sha256: Optional[str] = None  # Computed lazily on capture


def scan_step_artifacts(
    calc_raw_dir: Path,
    step_ulid: str,
    policy: ArtifactPolicy,
    previous_scan: Optional[Dict[str, ScannedFile]] = None,
) -> List[ScannedFile]:
    """
    Scan calc/raw/ directory for step artifacts.

    Args:
        calc_raw_dir: Path to calc/raw/
        step_ulid: Step ULID for context
        policy: Engine-specific artifact policy
        previous_scan: Optional previous scan for delta detection

    Returns:
        List of ScannedFile objects with capture decisions
    """
    results = []

    for path in calc_raw_dir.rglob("*"):
        if path.is_dir():
            continue

        rel_path = path.relative_to(calc_raw_dir).as_posix()
        stat = path.stat()

        # Check policy
        should_capture, tier, skip_reason = policy.should_capture(
            rel_path, stat.st_size
        )

        # Delta detection: skip unchanged files
        if previous_scan and rel_path in previous_scan:
            prev = previous_scan[rel_path]
            if prev.mtime == stat.st_mtime and prev.size_bytes == stat.st_size:
                continue  # Unchanged, skip

        results.append(ScannedFile(
            rel_path=rel_path,
            abs_path=path,
            size_bytes=stat.st_size,
            mtime=stat.st_mtime,
            tier=tier,
            should_capture=should_capture,
            skip_reason=skip_reason,
        ))

    return results
```

---

## 7. GC and Retention Policies

### 7.1 Tier Retention Rules

```python
@dataclass
class RetentionPolicy:
    """Per-tier retention configuration."""

    tier0_policy: Literal["never_delete"] = "never_delete"
    tier05_policy: Literal["never_delete"] = "never_delete"
    tier1_policy: Literal["never_delete", "explicit_only"] = "never_delete"
    tier2_policy: Literal["never_delete", "age_based", "count_based"] = "never_delete"
    tier3_policy: Literal["rolling_window"] = "rolling_window"

    # Tier-2 age-based: delete objects older than N days (0 = never)
    tier2_max_age_days: int = 0

    # Tier-3 rolling window: keep last N per (step_ulid, engine)
    tier3_keep_count: int = 3


# Default policy
DEFAULT_RETENTION = RetentionPolicy(
    tier0_policy="never_delete",
    tier05_policy="never_delete",
    tier1_policy="never_delete",
    tier2_policy="never_delete",  # Safe default
    tier3_policy="rolling_window",
    tier3_keep_count=3,
)
```

### 7.2 GC Algorithm

```python
def gc_cas(project_root: Path, policy: RetentionPolicy, dry_run: bool = False) -> GCReport:
    """
    Garbage collect CAS objects per retention policy.

    MUST be called with gc.lock held.
    """
    db = open_provenance_db(project_root)
    cas_root = project_root / ".provenance" / ".cas"

    to_delete = []

    # Tier-3: Rolling window
    if policy.tier3_policy == "rolling_window":
        # Group Tier-3 objects by (step_ulid, engine) from artifact collections
        tier3_groups = group_tier3_by_step_engine(db)

        for (step_ulid, engine), objects in tier3_groups.items():
            # Sort by created_at descending
            objects.sort(key=lambda o: o.created_at, reverse=True)

            # Mark objects beyond keep_count for deletion
            for obj in objects[policy.tier3_keep_count:]:
                to_delete.append(obj.sha256)

    # Tier-2: Age-based (if enabled)
    if policy.tier2_policy == "age_based" and policy.tier2_max_age_days > 0:
        cutoff = datetime.now() - timedelta(days=policy.tier2_max_age_days)

        for obj in db.query_tier2_objects():
            if obj.created_at < cutoff:
                to_delete.append(obj.sha256)

    # Verify no live references before actual deletion
    safe_to_delete = []
    for sha256 in to_delete:
        if not has_live_references(db, sha256):
            safe_to_delete.append(sha256)

    # Delete
    report = GCReport()
    if not dry_run:
        for sha256 in safe_to_delete:
            cas_path = cas_root / "objects" / sha256[:2] / sha256[2:]
            cas_path.unlink(missing_ok=True)
            db.mark_deleted(sha256)
            report.deleted_count += 1
            report.freed_bytes += db.get_size(sha256)

    return report
```

### 7.3 GC Trigger Points

GC should be triggered:

1. **Manual:** User/agent explicitly requests GC
2. **Post-run:** Optional, after successful run completion
3. **On-demand:** When CAS exceeds size threshold (future)

MVP: Manual trigger only. No automatic GC.

---

## 8. Testing Plan

### 8.1 Gate Tests (Mandatory, CI-blocking)

#### Gate P2-1: OperationContext Required

```python
# tests/gates/test_provenance_opctx_required.py

def test_save_yaml_doc_without_opctx_raises():
    """Law P2: save_yaml_doc() MUST require opctx."""
    doc = YamlDoc({"key": "value"})
    path = Path("/tmp/test.yaml")

    with pytest.raises(OperationContextRequiredError):
        save_yaml_doc(doc, path)  # No opctx


def test_save_yaml_doc_with_opctx_succeeds():
    """Law P2: save_yaml_doc() succeeds with opctx."""
    doc = YamlDoc({"key": "value"})
    path = Path("/tmp/test.yaml")
    opctx = OperationContext(
        op=OperationType.CUSTOM,
        actor=ActorType.SYSTEM,
        scope=ScopeType.PROJECT,
        source="test_save_yaml_doc",
        payload={},
    )

    # Should not raise
    save_yaml_doc(doc, path, opctx)
    assert path.exists()
```

#### Gate P1-1: History World Independence

```python
# tests/gates/test_provenance_independence.py

def test_project_runnable_without_provenance(tmp_project):
    """Law P1: Deleting .provenance/ leaves project runnable."""
    # Setup: Create project with provenance data
    calc = tmp_project.create_calculation("test_calc")
    calc.add_step("scf", step_type_spec="qe_scf")

    # Delete provenance
    provenance_dir = tmp_project.root / ".provenance"
    if provenance_dir.exists():
        shutil.rmtree(provenance_dir)

    # Verify project still works
    assert calc.yaml_path.exists()
    calc2 = tmp_project.load_calculation(calc.ulid)
    assert calc2.steps[0].step_type_spec == "qe_scf"

    # Verify run can proceed (mock execution)
    runner = Runner(calc2)
    # Should not raise ProvenanceMissingError or similar
    runner.prepare_run()
```

#### Gate P3-1: No Provenance in Skip Logic

```python
# tests/gates/test_provenance_skip_isolation.py

def test_manifest_skip_logic_no_provenance_imports():
    """Law P3: Skip logic must not import from provenance module."""
    import ast

    manifest_path = Path("src/quantumvitas/calculation/manifest.py")
    tree = ast.parse(manifest_path.read_text())

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "provenance" not in alias.name, \
                    f"manifest.py imports provenance: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert "provenance" not in node.module, \
                    f"manifest.py imports from provenance: {node.module}"
```

#### Gate P5-1: CAS Integrity

```python
# tests/gates/test_cas_integrity.py

def test_cas_content_addressed(tmp_cas):
    """Law P5: Same content produces same hash."""
    content = b"test content for CAS"

    sha1 = tmp_cas.store(content)
    sha2 = tmp_cas.store(content)

    assert sha1 == sha2
    assert tmp_cas.exists(sha1)


def test_cas_immutable(tmp_cas):
    """Law P5: CAS objects cannot be modified."""
    content = b"original content"
    sha = tmp_cas.store(content)

    # Attempt to modify should fail or be ignored
    with pytest.raises((PermissionError, CASImmutabilityError)):
        tmp_cas.modify(sha, b"modified content")

    # Verify content unchanged
    assert tmp_cas.retrieve(sha) == content
```

#### Gate P6-1: Lock Ordering

```python
# tests/gates/test_lock_ordering.py

def test_provenance_lock_after_edit_lock(tmp_project):
    """Law P6: edit.lock must be acquired before provenance.lock."""
    import threading

    calc = tmp_project.create_calculation("test_lock_order")
    errors = []

    def writer():
        try:
            # This should acquire edit.lock first, then provenance.lock
            opctx = OperationContext(
                op=OperationType.STEP_UPDATE,
                actor=ActorType.SYSTEM,
                scope=ScopeType.STEP,
                source="test_writer",
                payload={},
            )
            calc.steps[0].update({"param": "value"}, opctx)
        except Exception as e:
            errors.append(e)

    # Run multiple concurrent writers
    threads = [threading.Thread(target=writer) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # No deadlock errors
    assert not any(isinstance(e, DeadlockError) for e in errors)
```

### 8.2 Integration Tests

#### Integration: Preset Apply Records Event

```python
# tests/integration/test_provenance_preset.py

def test_preset_apply_records_event(tmp_project):
    """Preset apply must produce operation event with op=PRESET_APPLY."""
    calc = tmp_project.create_calculation("test_preset")
    calc.add_step("scf", step_type_spec="qe_scf")

    # Apply preset
    preset_name = "high_accuracy"
    calc.apply_preset(preset_name)

    # Check provenance
    db = open_provenance_db(tmp_project.root)
    events = db.query_events(op_type=OperationType.PRESET_APPLY)

    assert len(events) >= 1
    last_event = events[-1]
    assert last_event.op_type == OperationType.PRESET_APPLY
    assert last_event.payload.get("preset_name") == preset_name
    assert last_event.actor == ActorType.HUMAN  # or appropriate actor
```

#### Integration: Run Produces Run Node

```python
# tests/integration/test_provenance_run.py

def test_run_produces_run_node_with_snapshots(tmp_project, mock_engine):
    """Run must produce run node with ordered steps and snapshot refs."""
    calc = tmp_project.create_calculation("test_run")
    calc.add_step("scf", step_type_spec="qe_scf")
    calc.add_step("bands", step_type_spec="qe_bands")

    # Run with mock engine
    runner = Runner(calc)
    run_ulid = runner.run()

    # Check run events
    db = open_provenance_db(tmp_project.root)

    # RUN_START event
    start_events = db.query_events(
        event_kind="run_start",
        run_ulid=run_ulid
    )
    assert len(start_events) == 1

    # RUN_COMPLETE event
    complete_events = db.query_events(
        event_kind="run_complete",
        run_ulid=run_ulid
    )
    assert len(complete_events) == 1

    # Run steps
    run_steps = db.query_run_steps(run_ulid=run_ulid)
    assert len(run_steps) == 2

    # Verify order
    assert run_steps[0].step_index == 0
    assert run_steps[1].step_index == 1

    # Verify snapshots exist in CAS
    cas = CAS(tmp_project.root)
    for step in run_steps:
        assert cas.exists(step.snapshot_sha)


def test_artifact_scan_records_expected_files(tmp_project, mock_engine):
    """Artifact scan must record expected files by path/mtime/size."""
    calc = tmp_project.create_calculation("test_artifacts")
    calc.add_step("scf", step_type_spec="qe_scf")

    # Create mock output files
    raw_dir = calc.dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "scf.out").write_text("mock output")
    (raw_dir / "scf.xml").write_text("<mock/>")

    # Run
    runner = Runner(calc)
    run_ulid = runner.run()

    # Check artifact collection
    db = open_provenance_db(tmp_project.root)
    run_steps = db.query_run_steps(run_ulid=run_ulid)

    assert run_steps[0].artifact_collection_sha is not None

    cas = CAS(tmp_project.root)
    collection = cas.retrieve_json(run_steps[0].artifact_collection_sha)

    artifacts = collection["artifacts"]
    paths = [a["relative_path"] for a in artifacts]

    assert "scf.out" in paths
    assert "scf.xml" in paths
```

### 8.3 Concurrency Tests

```python
# tests/concurrency/test_provenance_concurrent.py

def test_concurrent_yaml_writes_no_corruption(tmp_project):
    """Multiple concurrent YAML writes must not corrupt provenance."""
    import concurrent.futures

    calc = tmp_project.create_calculation("test_concurrent")
    calc.add_step("scf", step_type_spec="qe_scf")

    errors = []

    def write_param(i):
        try:
            opctx = OperationContext(
                op=OperationType.STEP_UPDATE,
                actor=ActorType.SYSTEM,
                scope=ScopeType.STEP,
                source=f"writer_{i}",
                payload={"iteration": i},
            )
            calc.steps[0].update({"param": f"value_{i}"}, opctx)
        except Exception as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(write_param, i) for i in range(100)]
        concurrent.futures.wait(futures)

    # No corruption errors
    assert not errors

    # DB is valid
    db = open_provenance_db(tmp_project.root)
    events = db.query_events(op_type=OperationType.STEP_UPDATE)
    assert len(events) == 100  # All writes recorded
```

### 8.4 Failure/Recovery Tests

```python
# tests/integration/test_provenance_failure.py

def test_yaml_write_succeeds_despite_provenance_failure(tmp_project, monkeypatch):
    """Law P7: YAML write must succeed even if provenance fails."""
    calc = tmp_project.create_calculation("test_graceful")
    calc.add_step("scf", step_type_spec="qe_scf")

    # Corrupt provenance DB
    db_path = tmp_project.root / ".provenance" / "provenance.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("corrupt data")

    # Attempt write
    opctx = OperationContext(
        op=OperationType.STEP_UPDATE,
        actor=ActorType.SYSTEM,
        scope=ScopeType.STEP,
        source="test_graceful",
        payload={},
    )

    # Should not raise
    calc.steps[0].update({"param": "new_value"}, opctx)

    # YAML should be updated
    step_data = calc.steps[0].load()
    assert step_data.get("param") == "new_value"
```

---

## 9. Migration and Compatibility

### 9.1 New Projects

For new projects, provenance is enabled by default:

- First `save_yaml_doc()` call initializes `.provenance/` directory
- First event is `SEED` operation with initial state snapshot

### 9.2 Existing Projects (No Provenance)

For existing projects without `.provenance/`:

1. **Lazy initialization:** First provenance-aware operation creates `.provenance/`
2. **Seed event:** First event is `SEED` with payload `{"migration": true}`
3. **No retroactive history:** Past operations are not recorded; timeline starts from migration point

```python
def ensure_provenance_initialized(project_root: Path) -> bool:
    """
    Initialize provenance for existing project if needed.

    Returns:
        True if newly initialized, False if already existed
    """
    provenance_dir = project_root / ".provenance"

    if provenance_dir.exists():
        return False

    # Create directory structure
    provenance_dir.mkdir(parents=True)
    (provenance_dir / ".cas" / "objects").mkdir(parents=True)
    (provenance_dir / ".cas" / "tmp").mkdir(parents=True)

    # Initialize database
    db = create_provenance_db(provenance_dir / "provenance.db")

    # Record seed event
    seed_event = Event(
        ulid=generate_ulid(),
        event_kind="operation",
        op_type=OperationType.SEED,
        timestamp=now_iso8601(),
        actor=ActorType.SYSTEM,
        scope=ScopeType.PROJECT,
        source="ensure_provenance_initialized",
        payload={"migration": True},
    )
    db.append_event(seed_event)

    return True
```

### 9.3 Deleting Provenance

Deleting `.provenance/` is always safe:

```bash
rm -rf project/.provenance/
```

After deletion:

- Project remains fully runnable
- Next provenance-aware operation re-initializes with new `SEED`
- No migration warnings or errors

### 9.4 Version Compatibility

SQLite schema includes version tracking:

```python
def check_schema_version(db: sqlite3.Connection) -> int:
    """Check schema version and migrate if needed."""
    version = db.execute("SELECT version FROM schema_version").fetchone()[0]

    if version < CURRENT_SCHEMA_VERSION:
        migrate_schema(db, version, CURRENT_SCHEMA_VERSION)

    return version
```

---

## 10. Future Enhancements

These are explicitly **NOT part of MVP** but designed for:

### 10.1 Buffered Write Mode (Performance)

MVP uses synchronous SQLite append. Future enhancement:

```python
class BufferedProvenanceWriter:
    """
    Buffer provenance events in memory, flush periodically.

    Benefits:
    - Reduced I/O during rapid edits
    - Batched SQLite transactions

    Invariants:
    - MUST flush before run starts
    - MUST flush on explicit save/sync
    - MUST flush on process exit (atexit handler)
    """

    def __init__(self, max_buffer_size: int = 100, max_age_seconds: float = 5.0):
        self.buffer: List[Event] = []
        self.max_buffer_size = max_buffer_size
        self.max_age_seconds = max_age_seconds
        self.last_flush = time.time()
        self._lock = threading.Lock()

    def append(self, event: Event):
        with self._lock:
            self.buffer.append(event)
            if len(self.buffer) >= self.max_buffer_size:
                self._flush_locked()

    def flush(self):
        with self._lock:
            self._flush_locked()
```

### 10.2 Agent Journal (Memory)

Full-featured agent memory system:

```python
@dataclass
class JournalEntry:
    """Agent memory entry."""

    ulid: str
    timing: Literal["before_run", "after_run", "note"]
    title: str                    # Short, FTS-indexed
    tags: List[str]               # Categorization
    body: str                     # Full content (stored in CAS)

    # Associations
    run_ulid: Optional[str] = None
    calc_ulid: Optional[str] = None
    step_ulid: Optional[str] = None

    # Metadata
    created_at: str = field(default_factory=now_iso8601)
    author: str = "agent"         # agent ID or "human"
```

Usage patterns:

- **Before-run:** Record rationale, expected outcomes, parameter choices
- **After-run:** Record analysis summary, lessons learned, next steps
- **Notes:** General observations, reminders, context

### 10.3 Cross-Project Provenance

For workflows spanning multiple projects:

- Global CAS for shared pseudopotentials/potentials
- Cross-project references via ULIDs
- Export/import of provenance subgraphs

### 10.4 Query API

Rich querying for UI/agents:

```python
class ProvenanceQuery:
    """Query builder for provenance data."""

    def events(self) -> "EventQuery":
        """Query events timeline."""
        ...

    def runs(self) -> "RunQuery":
        """Query run history."""
        ...

    def snapshots(self) -> "SnapshotQuery":
        """Query available snapshots."""
        ...

    def journal(self, search: str) -> "JournalQuery":
        """Full-text search journal."""
        ...


# Example usage
query = ProvenanceQuery(project)
recent_runs = (
    query.runs()
    .calc(calc_ulid)
    .since(datetime.now() - timedelta(days=7))
    .status("success")
    .limit(10)
    .execute()
)
```

### 10.5 Export/Reporting

Generate provenance reports:

- Timeline visualization (HTML/SVG)
- Run comparison reports
- Audit logs for reproducibility documentation
- Export to standard formats (W3C PROV, JSON-LD)

---

## Appendix A: File Locations

| Component | Path |
|-----------|------|
| Provenance module | `src/quantumvitas/provenance/` |
| OperationContext | `src/quantumvitas/provenance/opctx.py` |
| SQLite schema | `src/quantumvitas/provenance/schema.py` |
| CAS implementation | `src/quantumvitas/provenance/cas.py` |
| Artifact scanner | `src/quantumvitas/provenance/artifacts.py` |
| Lock utilities | `src/quantumvitas/provenance/locks.py` |
| Gate tests | `tests/gates/test_provenance_*.py` |
| Integration tests | `tests/integration/test_provenance_*.py` |

## Appendix B: API Surface

### Public Functions (Kernel)

```python
# OperationContext creation helpers
def opctx_for_preset(preset_name: str, actor: ActorType) -> OperationContext
def opctx_for_step_update(step_ulid: str, actor: ActorType) -> OperationContext
def opctx_for_run(run_ulid: str, actor: ActorType) -> OperationContext

# Provenance recording (internal, called by save_yaml_doc)
def record_operation(project_root: Path, opctx: OperationContext, before: bytes, after: bytes)
def record_run_start(project_root: Path, run_ulid: str, steps: List[str])
def record_run_complete(project_root: Path, run_ulid: str, status: str, step_results: List[StepResult])

# CAS operations
def cas_store(project_root: Path, content: bytes, tier: int) -> str
def cas_retrieve(project_root: Path, sha256: str) -> bytes
def cas_exists(project_root: Path, sha256: str) -> bool

# Snapshot operations
def create_snapshot(project_root: Path, scope: ScopeType, target_ulid: str) -> str
def restore_snapshot(project_root: Path, snapshot_sha: str, opctx: OperationContext)

# Query (for UI/agents)
def query_events(project_root: Path, **filters) -> List[Event]
def query_runs(project_root: Path, **filters) -> List[RunSummary]
def get_run_steps(project_root: Path, run_ulid: str) -> List[RunStep]
```

### Errors

```python
class OperationContextRequiredError(Exception):
    """Raised when save_yaml_doc() called without opctx."""

class CASIntegrityError(Exception):
    """Raised on CAS corruption or hash mismatch."""

class ProvenanceError(Exception):
    """Base class for provenance errors (non-fatal for YAML ops)."""

class SnapshotNotFoundError(ProvenanceError):
    """Raised when requested snapshot doesn't exist in CAS."""
```

---

## Appendix C: Checklist for Implementer

### Phase 1: Foundation (MVP Core)

- [ ] Create `src/quantumvitas/provenance/` package
- [ ] Implement `OperationContext` dataclass
- [ ] Implement `OperationType`, `ActorType`, `ScopeType` enums
- [ ] Create SQLite schema (events, run_steps, cas_objects tables)
- [ ] Implement CAS basic operations (store, retrieve, exists)
- [ ] Add `provenance.lock` context manager
- [ ] Modify `save_yaml_doc()` to require opctx parameter
- [ ] Implement `record_operation()` function
- [ ] Add gate test: opctx required
- [ ] Add gate test: history independence

### Phase 2: Run Integration

- [ ] Implement `record_run_start()` and `record_run_complete()`
- [ ] Implement `create_snapshot()` for YAML/structure capture
- [ ] Integrate with `Runner` for pre-run snapshots
- [ ] Implement `ArtifactPolicy` and default policies per engine
- [ ] Implement artifact scanner
- [ ] Add `run_steps` recording
- [ ] Add integration test: run produces run node

### Phase 3: Preset and Operation Recording

- [ ] Update preset apply code to pass opctx
- [ ] Update step modification code to pass opctx
- [ ] Update calculation modification code to pass opctx
- [ ] Add integration test: preset apply records event

### Phase 4: Rollback/Restore

- [ ] Implement `restore_snapshot()`
- [ ] Add restore operation recording
- [ ] Add tests for restore workflow

### Phase 5: GC and Cleanup

- [ ] Implement GC algorithm per tier
- [ ] Add gc.lock handling
- [ ] Implement manual GC trigger
- [ ] Add GC tests

---

*End of Specification*
