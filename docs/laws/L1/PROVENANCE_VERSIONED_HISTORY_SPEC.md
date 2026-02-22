# Provenance / Versioned History System Specification

**Status:** PROPOSED v1.1
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
8. [Gate Inventory](#8-gate-inventory)
9. [Testing Plan](#9-testing-plan)
10. [Migration and Compatibility](#10-migration-and-compatibility)
11. [Future Enhancements](#11-future-enhancements)

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

1. **Present World SSOT Unchanged**: The authoritative truth remains the YAML/JSON file tree (`project.qms.yml`, `calculation.yaml`, `step.yaml`, structure resources). This is what gets read at runtime.

2. **History World is Auxiliary**: SQLite database and Content-Addressed Store (CAS) are historical records. Deleting them must leave the project fully runnable—just losing history/rollback/analytics.

3. **Linear Timeline, Not DAG**: We use a simple linear event log, not an AiiDA-style directed acyclic graph. Cross-references are recorded as events, not modeled as graph edges.

4. **Explicit Intent, Not Inference**: Operations are recorded with explicit `OperationContext` passed through the call chain. We do not rely on observers/listeners to infer intent.

5. **Only SSOT-Writing Actions are Recorded**: UI-only state changes (like preset "select" without apply) are NOT provenance events. Only operations that result in SSOT YAML writes are recorded.

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
│  │  project.qms.yml                     │  │  .provenance/                │ │
│  │  calculations/                      │  │  ├── provenance.db (SQLite)  │ │
│  │  ├── <calc_ulid>/                   │  │  ├── provenance.lock         │ │
│  │  │   ├── calculation.yaml           │  │  └── .cas/                   │ │
│  │  │   ├── step_*.yaml                │  │      ├── objects/            │ │
│  │  │   └── raw/  (current outputs)    │  │      │   └── <sha256>/       │ │
│  │  pseudo/                            │  │      ├── tmp/                │ │
│  │  potentials/                        │  │      └── gc.lock             │ │
│  │  structures/                        │  │                              │ │
│  └─────────────────────────────────────┘  └──────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────┐                                   │
│  │         RUNTIME/EPHEMERAL           │                                   │
│  │  (Deletable, not truth)             │                                   │
│  ├─────────────────────────────────────┤                                   │
│  │  calculations/<ulid>/.run_tmp_info/ │                                   │
│  │  └── manifest.json                  │                                   │
│  │  calculations/<ulid>/.locks/        │                                   │
│  │  └── edit.lock, run.lock            │                                   │
│  └─────────────────────────────────────┘                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.4 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **SHA storage** | Only for CAS objects | Operation events do NOT store before/after SHA; only runs store snapshot SHAs |
| **Run step storage** | Normalized `runs` + `run_steps` tables | No JSON blobs; enables efficient per-step queries |
| **Lock ordering** | edit.lock → release → provenance.lock | Never hold both simultaneously; SQLite append after YAML write |
| **Preset events** | Only APPLY recorded | SELECT is UI-only; no SSOT write = no event |
| **Artifact scanning** | Single Runner-level scanner | No duplicate scanners in handlers/engines |

---

## 2. Invariants and Laws

These invariants are BINDING and must be enforced via gate tests.

### Law P1: SSOT Separation (History World Independence)

> **The History World (SQLite + CAS) MUST NOT participate in any runtime logic.**

- Runtime execution, materialization, and skip decisions read ONLY from Present World SSOT files.
- Deleting `.provenance/` directory MUST leave the project fully runnable.
- No kernel code path may fail due to missing/corrupt provenance data.
- History data is "write-only from kernel perspective"—reads are for UI/agents/analytics only.

**Enforcement:** Gate `test_provenance_independence.py`

### Law P2: OperationContext Required (Choke Point Rule)

> **Any write to Present World SSOT YAML MUST carry an explicit OperationContext.**

- `save_yaml_doc()` MUST require an `opctx` parameter.
- Calling `save_yaml_doc()` without `opctx` MUST raise `OperationContextRequiredError`.
- This guarantees all SSOT-writing operations are recorded without scattered logging calls.
- OperationContext minimum fields: `op` (enum), `actor` (human/agent/system), `source` (kernel public method name), `scope` (project/calc/step/structure), `payload` (JSON-serializable dict), `timestamp` (optional; recorder sets if None).

**Enforcement:** Gate `test_provenance_opctx_required.py`

### Law P3: No Provenance-Dependent Skip Logic

> **Skip/rerun decisions MUST NOT consult provenance data.**

- Manifest-based incremental run (Constitution §5) uses only: kind, pseudo_set_sha, structure_sha, step_sha, done flag.
- The provenance system is for audit/rollback, not runtime optimization.

**Enforcement:** Gate `test_provenance_skip_isolation.py`

### Law P4: Append-Only Timeline

> **The SQLite timeline is append-only. Events and runs are NEVER deleted or modified.**

- Operations and runs are immutable once recorded.
- Corrections are recorded as new events (e.g., `CORRECTION` event type).
- GC may delete CAS blobs, but SQLite records remain (with soft-delete flag if needed).

**Enforcement:** Schema design; no UPDATE/DELETE on events/runs tables.

### Law P5: CAS Integrity

> **CAS objects are immutable and content-addressed by SHA-256.**

- Object path is derived from hash: `.cas/objects/<first2>/<rest_of_hash>`
- Once written, a CAS object is never modified.
- Duplicate writes (same hash) are no-ops.
- GC may delete objects per tier policy, but must verify no live references first.
- **SHA exists ONLY for objects actually stored in CAS** (snapshots, artifacts). Operation events do NOT store before/after SHAs.

**Enforcement:** Gate `test_cas_integrity.py`

### Law P6: Lock Ordering (Sequential, Not Nested)

> **Locks MUST be acquired sequentially: edit.lock first, then provenance.lock. Never hold both simultaneously.**

- YAML write sequence:
  1. Acquire edit.lock → write YAML → release edit.lock
  2. Acquire provenance.lock → append SQLite event → release provenance.lock
- This prevents deadlocks and ensures YAML write is never blocked by provenance.
- **Critical:** Provenance append happens AFTER edit.lock is released, not inside it.

**Enforcement:** Gate `test_lock_ordering.py`

### Law P7: Graceful Degradation

> **Provenance failures MUST NOT fail YAML writes.**

- If SQLite append fails after YAML write succeeds, log warning and continue.
- Project remains runnable; provenance gap is logged when possible.
- Best-effort retry is optional (not required for MVP).
- History is NOT SSOT; YAML write success is the only success criterion.

**Enforcement:** Integration test `test_provenance_failure_graceful.py`

### Law P8: Only SSOT-Writing Actions are Provenance Events

> **Only operations that result in SSOT YAML writes are recorded as provenance events.**

- UI-only state changes (preset "select", parameter preview, validation) are NOT events.
- Preset APPLY that writes to step.yaml is an event; preset SELECT is not.
- If no `save_yaml_doc()` call occurs, no provenance event is recorded.

**Enforcement:** Architectural design; tested via preset integration tests.

### Law P9: Single Artifact Scanner (No Duplicate Logic)

> **Artifact scanning MUST occur only at Runner level. No duplicate scanners in handlers or engines.**

- Pre-step and post-step scans are Runner responsibility.
- Handlers and engine modules MUST NOT implement independent artifact scanning.
- Engine recipes define artifact policy (blacklist/whitelist); Runner applies it.

**Enforcement:** Gate `test_no_duplicate_scanners.py`

---

## 3. Data Model

### 3.1 Directory Layout

```
project_root/
├── .provenance/                          # Provenance root (project-level)
│   ├── provenance.db                     # SQLite database
│   ├── provenance.lock                   # Project-level lock for SQLite writes
│   └── .cas/                             # Content-Addressed Store
│       ├── objects/                      # Immutable blob storage
│       │   ├── <first2>/                 # First 2 chars of sha256
│       │   │   └── <remaining62>         # Remaining 62 chars (raw blob)
│       │   └── ...
│       ├── tmp/                          # Temp staging for atomic writes
│       └── gc.lock                       # Lock for GC operations
├── project.qms.yml                        # Present World SSOT
├── calculations/                         # Present World SSOT
│   └── <calc_ulid>/
│       ├── calculation.yaml
│       ├── step_*.yaml
│       ├── raw/                          # Engine I/O (current only)
│       ├── .run_tmp_info/
│       │   └── manifest.json             # Incremental run bookkeeping
│       └── .locks/
│           ├── edit.lock                 # Per-calc YAML write lock
│           └── run.lock                  # Per-calc execution lock
└── ...
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
    timestamp: Optional[str] = None       # ISO8601; recorder sets if None
    facade_endpoint: Optional[str] = None # Optional: higher-level API endpoint
    request_id: Optional[str] = None      # Optional: correlation ID for multi-op requests

    def to_dict(self) -> dict:
        """Serialize for SQLite JSON column."""
        return {
            "op": self.op.value,
            "actor": self.actor.value,
            "scope": self.scope.value,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "facade_endpoint": self.facade_endpoint,
            "request_id": self.request_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OperationContext":
        """Deserialize from SQLite JSON column."""
        return cls(
            op=OperationType(data["op"]),
            actor=ActorType(data["actor"]),
            scope=ScopeType(data["scope"]),
            source=data["source"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp"),
            facade_endpoint=data.get("facade_endpoint"),
            request_id=data.get("request_id"),
        )


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

    # Preset operations (APPLY only; SELECT is UI-only, not recorded)
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

### 3.3 SQLite Schema (Normalized Tables)

```sql
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO schema_version (version) VALUES (1);

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

--------------------------------------------------------------------------------
-- JOURNAL_ENTRIES TABLE: Agent/human narrative notes (optional, for future)
--------------------------------------------------------------------------------
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

-- Full-text search for journal (optional, for future)
CREATE VIRTUAL TABLE IF NOT EXISTS journal_fts USING fts5(
    title, tags,
    content='journal_entries',
    content_rowid='id'
);
```

### 3.4 Operation Event Payload Schema

Operations do NOT store before/after snapshot SHAs. Instead, they store a lightweight diff summary in the payload:

```python
@dataclass
class OperationPayload:
    """Payload structure for operation events."""

    # Operation-specific data (varies by op_type)
    preset_name: Optional[str] = None     # For PRESET_APPLY
    step_type_spec: Optional[str] = None  # For STEP_ADD/UPDATE
    structure_ulid: Optional[str] = None  # For STRUCTURE_* ops

    # Diff summary (computed from before/after YAML)
    changed_paths: List[str] = field(default_factory=list)  # JSONPointer-like paths
    summary: Optional[str] = None         # Human-readable description

    # Optional: run correlation
    run_ulid: Optional[str] = None        # If this op is part of a run

    def to_dict(self) -> dict:
        """Serialize for SQLite storage."""
        return {k: v for k, v in asdict(self).items() if v is not None}
```

**Example payloads:**

```json
// PRESET_APPLY
{
    "preset_name": "high_accuracy",
    "changed_paths": ["/parameters/ecutwfc", "/parameters/ecutrho", "/kpoints/grid"],
    "summary": "Applied preset 'high_accuracy' to step scf"
}

// STEP_UPDATE
{
    "step_type_spec": "qe_scf",
    "changed_paths": ["/parameters/ecutwfc"],
    "summary": "Updated ecutwfc from 40 to 60"
}

// RELAX_PROMOTE
{
    "structure_ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
    "summary": "Promoted relaxed structure from step relax"
}
```

### 3.5 CAS Object Formats

#### 3.5.1 Path Derivation

```python
def cas_path(cas_root: Path, sha256: str) -> Path:
    """Derive CAS path from SHA-256 hash."""
    return cas_root / "objects" / sha256[:2] / sha256[2:]
```

Example: `sha256 = "a1b2c3d4..."` → `.cas/objects/a1/b2c3d4...`

#### 3.5.2 Run Snapshot Object (Tier-0)

Snapshots are created at run start and capture the complete SSOT state:

```json
{
    "version": 1,
    "type": "run_snapshot",
    "run_ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAX",
    "calc_ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
    "timestamp": "2026-02-05T10:30:00.000000Z",

    "files": {
        "calculation.yaml": "<inline YAML content>",
        "step_scf.yaml": "<inline YAML content>",
        "step_bands.yaml": "<inline YAML content>"
    },

    "structure_refs": [
        {
            "ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
            "path": "structures/si_diamond.yaml",
            "sha256": "..."
        }
    ]
}
```

#### 3.5.3 Artifact Collection Object (Tier-2/3)

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
        "total_files_scanned": 15,
        "total_size_bytes": 20971520,
        "captured_count": 2,
        "captured_size_bytes": 153600
    }
}
```

### 3.6 Storage Tiers

| Tier | Contents | Retention | GC Policy |
|------|----------|-----------|-----------|
| **Tier-0** | Run snapshots (YAML, structures) | Forever | Never auto-delete |
| **Tier-0.5** | Reproducibility assets (pseudos, potentials, basis) | Forever | Never auto-delete; content-addressed dedup. Physical SSOT is `project/pseudo/` etc.; CAS is backup/dedup only |
| **Tier-1** | Derived outputs (reports, images, analysis, journal bodies) | Long-lived | Delete only on explicit user request |
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

**Critical Rule: Locks are acquired SEQUENTIALLY, never held simultaneously.**

```
YAML write + provenance recording sequence:

1. Acquire edit.lock
2. Write YAML to disk (atomic via temp + rename)
3. Capture diff summary (changed paths, before/after comparison)
4. Release edit.lock
   ─────────────────── edit.lock released ───────────────────
5. Acquire provenance.lock
6. Append operation event to SQLite (with diff summary in payload)
7. Release provenance.lock
```

**Why sequential, not nested:**
- Prevents deadlocks between concurrent YAML writers and provenance recorders
- Ensures YAML write is never blocked by slow SQLite operations
- If provenance append fails, YAML write already succeeded (Law P7)

### 4.3 YAML Write + Provenance Recording Sequence

```python
def save_yaml_doc(doc: YamlDoc, path: Path, opctx: OperationContext) -> None:
    """
    Single choke point for all SSOT YAML writes.

    Law P2: opctx is REQUIRED. Raises OperationContextRequiredError if None.
    """
    # 1. Validate opctx
    if opctx is None:
        raise OperationContextRequiredError(
            "save_yaml_doc() requires OperationContext. "
            "Pass opctx from the calling kernel method."
        )

    # 2. Capture before state (for diff summary)
    before = doc.get_snapshot()
    after = doc.to_dict()

    # 3. Compute diff summary BEFORE acquiring any locks
    diff_summary = compute_diff_summary(before, after)

    # 4. Acquire edit.lock and write YAML
    calc_dir = find_calc_dir_from_path(path)
    if calc_dir:
        with calc_edit_lock(calc_dir):
            _save_yaml_raw(after, path)
    else:
        _save_yaml_raw(after, path)

    # ─────────── edit.lock is now released ───────────

    # 5. Append provenance event (outside edit.lock)
    try:
        project_root = find_project_root(path)
        if project_root:
            record_operation_event(
                project_root=project_root,
                opctx=opctx,
                diff_summary=diff_summary,
            )
    except ProvenanceError as e:
        # Law P7: Provenance failure does not fail YAML write
        logger.warning(f"Provenance recording failed: {e}")
```

### 4.4 Provenance Lock Implementation

```python
@contextmanager
def provenance_lock(project_root: Path, timeout: float = 10.0):
    """
    Acquire project-level provenance lock for SQLite writes.

    Uses portalocker for cross-platform compatibility.
    Thread-local tracking prevents reentrancy.
    """
    canonical = project_root.resolve()
    held = _get_held_provenance_locks()

    if canonical in held:
        raise LockReentrancyError(f"Already holding provenance.lock for {canonical}")

    lock_path = canonical / ".provenance" / "provenance.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with portalocker.Lock(lock_path, timeout=timeout):
        held.add(canonical)
        try:
            yield
        finally:
            held.discard(canonical)
```

### 4.5 Failure Semantics (Law P7)

```
Scenario: SQLite append fails after YAML write succeeds

1. YAML write completes successfully (edit.lock held, then released)
2. provenance.lock acquired
3. SQLite INSERT fails (disk full, corruption, etc.)
4. Exception caught, logged as warning
5. Function returns success (YAML write succeeded)
6. Provenance gap exists but project is runnable

Recovery options (MVP: none required):
- Optional: Queue failed events for retry on next save
- Optional: Periodic background retry of failed events
- Long-term: Event gap detection in provenance query API
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
     │                  │   source="...",    │                   │
     │                  │   payload={preset} │                   │
     │                  │ )                  │                   │
     │                  │                    │                   │
     │                  │ step.apply_preset( │                   │
     │                  │   preset, opctx)   │                   │
     │                  ├───────────────────>│                   │
     │                  │                    │                   │
     │                  │                    │ # Load step doc   │
     │                  │                    │ # Apply patch     │
     │                  │                    │ # Compute diff    │
     │                  │                    │                   │
     │                  │                    │ ┌───────────────┐ │
     │                  │                    │ │ edit.lock     │ │
     │                  │                    │ │ Write YAML    │ │
     │                  │                    │ │ Release lock  │ │
     │                  │                    │ └───────────────┘ │
     │                  │                    │                   │
     │                  │                    │ # After edit.lock released:
     │                  │                    ├──────────────────>│
     │                  │                    │                   │ prov.lock
     │                  │                    │                   │ INSERT op
     │                  │                    │                   │ Release
     │                  │                    │<──────────────────┤
     │                  │                    │                   │
     │                  │<───────────────────┤                   │
     │<─────────────────┤                    │                   │
     │  OK              │                    │                   │
```

### 5.2 Run Calculation

```
┌──────────┐     ┌────────┐     ┌────────┐     ┌─────────┐     ┌───────────┐
│  Runner  │     │ Recipe │     │Handler │     │ Scanner │     │ Provenance│
└────┬─────┘     └───┬────┘     └───┬────┘     └────┬────┘     └─────┬─────┘
     │               │              │               │                │
     │ run_ulid = ULID()            │               │                │
     │               │              │               │                │
     │ # PRE-RUN: Create snapshot   │               │                │
     ├──────────────────────────────────────────────────────────────>│
     │               │              │               │                │
     │               │              │               │   Collect YAML │
     │               │              │               │   + structures │
     │               │              │               │   → CAS Tier-0 │
     │               │              │               │                │
     │               │              │               │   INSERT runs  │
     │               │              │               │   (status=     │
     │               │              │               │    running)    │
     │<──────────────────────────────────────────────────────────────┤
     │               │              │               │                │
     │ materialize() │              │               │                │
     ├──────────────>│              │               │                │
     │   JobGraph    │              │               │                │
     │<──────────────┤              │               │                │
     │               │              │               │                │
     │ FOR each step in JobGraph:   │               │                │
     │               │              │               │                │
     │   # PRE-STEP: Scan baseline  │               │                │
     │   ───────────────────────────────────────────>│               │
     │               │              │               │ Record mtimes  │
     │   <───────────────────────────────────────────┤               │
     │               │              │               │                │
     │   execute(job)│              │               │                │
     ├──────────────────────────────>│              │                │
     │               │              │ # Run engine  │                │
     │   JobResult   │              │               │                │
     │<──────────────────────────────┤              │                │
     │               │              │               │                │
     │   # POST-STEP: Scan changes  │               │                │
     │   ───────────────────────────────────────────>│               │
     │               │              │               │ Delta detect   │
     │               │              │               │ Apply policy   │
     │               │              │               │ Hash captures  │
     │   artifact_collection        │               │                │
     │   <───────────────────────────────────────────┤               │
     │               │              │               │                │
     │   # Store in CAS + record run_step           │                │
     │───────────────────────────────────────────────────────────────>│
     │               │              │               │   CAS Tier-2/3 │
     │               │              │               │   INSERT       │
     │               │              │               │   run_steps    │
     │<──────────────────────────────────────────────────────────────┤
     │               │              │               │                │
     │ END FOR       │              │               │                │
     │               │              │               │                │
     │ # Finalize run                               │                │
     │───────────────────────────────────────────────────────────────>│
     │               │              │               │   UPDATE runs  │
     │               │              │               │   SET status,  │
     │               │              │               │   finished_at  │
     │<──────────────────────────────────────────────────────────────┤
     │               │              │               │                │
```

### 5.3 Rollback/Restore

```
┌──────────┐     ┌──────────────┐     ┌───────────┐     ┌─────────────┐
│  UI/CLI  │     │    Kernel    │     │ Provenance│     │ Present SSOT│
└────┬─────┘     └──────┬───────┘     └─────┬─────┘     └──────┬──────┘
     │                  │                   │                  │
     │ restore(run_ulid)│                   │                  │
     ├─────────────────>│                   │                  │
     │                  │                   │                  │
     │                  │ # Get snapshot SHA│                  │
     │                  │ from runs table   │                  │
     │                  ├──────────────────>│                  │
     │                  │   snapshot_sha    │                  │
     │                  │<──────────────────┤                  │
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
     │                  │     from_run: ... │                  │
     │                  │   }               │                  │
     │                  │ )                 │                  │
     │                  │                   │                  │
     │                  │ # Write restored files (each via    │
     │                  │ # save_yaml_doc with RESTORE opctx) │
     │                  ├─────────────────────────────────────>│
     │                  │                   │  calc.yaml      │
     │                  │                   │  step*.yaml     │
     │                  │                   │  (structures)   │
     │                  │                   │                  │
     │<─────────────────┤                   │                  │
     │ OK + restore_summary                 │                  │
```

---

## 6. Engine Integration Points

### 6.1 Artifact Policy in Engine Recipes

Each engine driver MUST define artifact handling policy. This is the ONLY place artifact policy is defined (Law P9).

```python
# src/qmatsuite/drivers/<engine>/recipe.py

class EngineRecipe(BaseRecipe):

    # Artifact policy (REQUIRED for provenance support)
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
        ],

        # Tier-3 patterns (keep rolling window)
        tier3_patterns=[
            "*.save/",           # QE save directories
            "WAVECAR",           # VASP wavefunction
            "CHGCAR",            # VASP charge density
        ],

        # Whitelist overrides blacklist for specific files
        force_capture_patterns=[
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
    """Engine-specific artifact capture policy. Defined in recipe, applied by Runner."""

    mode: Literal["blacklist", "whitelist"] = "blacklist"

    # Blacklist mode: capture everything EXCEPT these
    blacklist_dirs: List[str] = field(default_factory=list)
    blacklist_patterns: List[str] = field(default_factory=list)

    # Whitelist mode: capture ONLY these (plus force_capture_patterns)
    whitelist_patterns: List[str] = field(default_factory=list)

    # Always capture these (overrides blacklist)
    force_capture_patterns: List[str] = field(default_factory=list)

    # Tier-3: large files that get rolling-window retention
    tier3_patterns: List[str] = field(default_factory=list)

    # Size limits
    tier2_max_size: int = -1  # -1 = no limit
    tier3_max_size: int = -1  # -1 = no limit

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

### 6.4 Artifact Scanner (Runner-Only)

The artifact scanner is implemented ONLY in the Runner. Handlers and engines MUST NOT implement their own scanners.

```python
# src/qmatsuite/provenance/scanner.py

@dataclass
class ScannedFile:
    """Result of scanning a single file."""
    rel_path: str
    abs_path: Path
    size_bytes: int
    mtime: float
    tier: int
    should_capture: bool
    skip_reason: Optional[str] = None
    sha256: Optional[str] = None  # Computed lazily at CAS ingestion


class ArtifactScanner:
    """
    Single scanner for artifact capture. Used ONLY by Runner.

    Law P9: No duplicate scanners in handlers or engines.
    """

    def __init__(self, calc_raw_dir: Path, policy: ArtifactPolicy):
        self.calc_raw_dir = calc_raw_dir
        self.policy = policy
        self._baseline: Dict[str, Tuple[float, int]] = {}  # path -> (mtime, size)

    def capture_baseline(self) -> None:
        """
        Capture baseline state before step execution.
        Called by Runner at PRE-STEP.
        """
        self._baseline = {}
        for path in self.calc_raw_dir.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(self.calc_raw_dir).as_posix()
                stat = path.stat()
                self._baseline[rel_path] = (stat.st_mtime, stat.st_size)

    def scan_changes(self) -> List[ScannedFile]:
        """
        Scan for changed/new files after step execution.
        Called by Runner at POST-STEP.

        Delta detection: Uses path + mtime + size comparison.
        Hashing is deferred to CAS ingestion for efficiency.
        """
        results = []

        for path in self.calc_raw_dir.rglob("*"):
            if path.is_dir():
                continue

            rel_path = path.relative_to(self.calc_raw_dir).as_posix()
            stat = path.stat()

            # Delta detection: skip unchanged files
            if rel_path in self._baseline:
                old_mtime, old_size = self._baseline[rel_path]
                if stat.st_mtime == old_mtime and stat.st_size == old_size:
                    continue  # Unchanged

            # Check policy
            should_capture, tier, skip_reason = self.policy.should_capture(
                rel_path, stat.st_size
            )

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
        tier3_groups = group_tier3_by_step_engine(db)

        for (step_ulid, engine), objects in tier3_groups.items():
            objects.sort(key=lambda o: o.created_at, reverse=True)
            for obj in objects[policy.tier3_keep_count:]:
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
            cas_file = cas_root / "objects" / sha256[:2] / sha256[2:]
            cas_file.unlink(missing_ok=True)
            db.execute("UPDATE cas_objects SET deleted = 1 WHERE sha256 = ?", (sha256,))
            report.deleted_count += 1
            report.freed_bytes += db.get_size(sha256)

    return report
```

### 7.3 GC Trigger Points

MVP: **Manual trigger only.** No automatic GC.

Future options:
1. Post-run: Optional, after successful run completion
2. On-demand: When CAS exceeds size threshold

---

## 8. Gate Inventory

### 8.1 Law to Gate Mapping

| Law | Gate Test File | Test Functions |
|-----|----------------|----------------|
| **P1: SSOT Separation** | `test_provenance_independence.py` | `test_project_runnable_without_provenance()`, `test_delete_provenance_then_run()` |
| **P2: OpCtx Required** | `test_provenance_opctx_required.py` | `test_save_yaml_doc_without_opctx_raises()`, `test_save_yaml_doc_with_opctx_succeeds()` |
| **P3: No Prov in Skip** | `test_provenance_skip_isolation.py` | `test_manifest_no_provenance_imports()`, `test_skip_logic_no_provenance_calls()` |
| **P4: Append-Only** | (Schema enforcement) | N/A - enforced by schema design |
| **P5: CAS Integrity** | `test_cas_integrity.py` | `test_cas_content_addressed()`, `test_cas_immutable()`, `test_cas_duplicate_noop()` |
| **P6: Lock Ordering** | `test_lock_ordering.py` | `test_sequential_lock_acquisition()`, `test_no_nested_locks()`, `test_concurrent_writers_no_deadlock()` |
| **P7: Graceful Degrade** | `test_provenance_failure_graceful.py` | `test_yaml_write_succeeds_despite_provenance_failure()` |
| **P8: Only SSOT Writes** | `test_preset_events.py` | `test_preset_apply_records_event()`, `test_preset_select_no_event()` |
| **P9: Single Scanner** | `test_no_duplicate_scanners.py` | `test_handler_no_scanner_import()`, `test_engine_no_scanner_import()` |

### 8.2 Integration Test Inventory

| Feature | Test File | Key Tests |
|---------|-----------|-----------|
| **Preset Recording** | `test_provenance_preset.py` | `test_preset_apply_creates_operation()`, `test_preset_payload_contains_name()` |
| **Run Recording** | `test_provenance_run.py` | `test_run_creates_runs_row()`, `test_run_steps_normalized()`, `test_snapshot_in_cas()` |
| **Artifact Capture** | `test_provenance_artifacts.py` | `test_artifact_scan_captures_outputs()`, `test_blacklist_excludes_outdir()`, `test_delta_detection()` |
| **Rollback** | `test_provenance_rollback.py` | `test_restore_from_run_snapshot()`, `test_restore_records_operation()` |
| **Concurrency** | `test_provenance_concurrent.py` | `test_concurrent_writes_no_corruption()`, `test_concurrent_runs_isolated()` |

---

## 9. Testing Plan

### 9.1 Gate Tests (Mandatory, CI-blocking)

#### Gate P2-1: OperationContext Required

```python
# tests/gates/test_provenance_opctx_required.py

def test_save_yaml_doc_without_opctx_raises():
    """Law P2: save_yaml_doc() MUST require opctx."""
    doc = YamlDoc({"key": "value"})
    path = tmp_path / "test.yaml"

    with pytest.raises(OperationContextRequiredError):
        save_yaml_doc(doc, path)  # No opctx


def test_save_yaml_doc_with_opctx_succeeds(tmp_path):
    """Law P2: save_yaml_doc() succeeds with opctx."""
    doc = YamlDoc({"key": "value"})
    path = tmp_path / "test.yaml"
    opctx = OperationContext(
        op=OperationType.CUSTOM,
        actor=ActorType.SYSTEM,
        scope=ScopeType.PROJECT,
        source="test_save_yaml_doc",
        payload={},
    )

    save_yaml_doc(doc, path, opctx)
    assert path.exists()
```

#### Gate P1-1: History World Independence

```python
# tests/gates/test_provenance_independence.py

def test_project_runnable_without_provenance(tmp_project):
    """Law P1: Deleting .provenance/ leaves project runnable."""
    calc = tmp_project.create_calculation("test_calc")
    calc.add_step("scf", step_type_spec="qe_scf")

    # Delete provenance
    provenance_dir = tmp_project.root / ".provenance"
    if provenance_dir.exists():
        shutil.rmtree(provenance_dir)

    # Verify project still works
    calc2 = tmp_project.load_calculation(calc.ulid)
    assert calc2.steps[0].step_type_spec == "qe_scf"

    # Verify run can proceed (mock execution)
    runner = Runner(calc2)
    runner.prepare_run()  # Should not raise
```

#### Gate P3-1: No Provenance in Skip Logic

```python
# tests/gates/test_provenance_skip_isolation.py

def test_manifest_no_provenance_imports():
    """Law P3: Skip logic must not import from provenance module."""
    import ast

    manifest_path = Path("src/qmatsuite/calculation/manifest.py")
    tree = ast.parse(manifest_path.read_text())

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "provenance" not in alias.name.lower()
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert "provenance" not in node.module.lower()
```

#### Gate P6-1: Lock Ordering

```python
# tests/gates/test_lock_ordering.py

def test_no_nested_locks(tmp_project):
    """Law P6: Provenance lock must not be acquired inside edit lock."""
    # This test inspects save_yaml_doc implementation
    import inspect
    from qmatsuite.core.yaml_io import save_yaml_doc

    source = inspect.getsource(save_yaml_doc)

    # Verify provenance recording is AFTER edit lock release
    # by checking the structure of the function
    assert "# edit.lock released" in source or \
           source.index("record_operation") > source.index("calc_edit_lock")
```

#### Gate P9-1: No Duplicate Scanners

```python
# tests/gates/test_no_duplicate_scanners.py

def test_handler_no_scanner_import():
    """Law P9: Handlers must not import artifact scanner."""
    import ast

    handler_files = Path("src/qmatsuite/drivers").rglob("handler.py")

    for handler_path in handler_files:
        tree = ast.parse(handler_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "scanner" in node.module:
                    pytest.fail(f"{handler_path} imports scanner: {node.module}")
```

### 9.2 Integration Tests

#### Integration: Run Produces Normalized Records

```python
# tests/integration/test_provenance_run.py

def test_run_creates_normalized_run_steps(tmp_project, mock_engine):
    """Run must produce normalized run_steps rows, not JSON blob."""
    calc = tmp_project.create_calculation("test_run")
    calc.add_step("scf", step_type_spec="qe_scf")
    calc.add_step("bands", step_type_spec="qe_bands")

    runner = Runner(calc)
    run_ulid = runner.run()

    # Check database structure
    db = open_provenance_db(tmp_project.root)

    # Verify runs table
    run_row = db.execute(
        "SELECT * FROM runs WHERE run_ulid = ?", (run_ulid,)
    ).fetchone()
    assert run_row is not None
    assert run_row["status"] == "success"
    assert run_row["snapshot_sha"] is not None  # Has CAS reference

    # Verify run_steps table (normalized, not JSON)
    step_rows = db.execute(
        "SELECT * FROM run_steps WHERE run_ulid = ? ORDER BY step_index",
        (run_ulid,)
    ).fetchall()

    assert len(step_rows) == 2
    assert step_rows[0]["step_index"] == 0
    assert step_rows[1]["step_index"] == 1
    assert all(row["snapshot_sha"] is not None for row in step_rows)
```

#### Integration: Preset Apply Records Event

```python
# tests/integration/test_provenance_preset.py

def test_preset_apply_creates_operation(tmp_project):
    """Preset APPLY produces operation event with correct payload."""
    calc = tmp_project.create_calculation("test_preset")
    calc.add_step("scf", step_type_spec="qe_scf")

    preset_name = "high_accuracy"
    calc.apply_preset(preset_name)

    db = open_provenance_db(tmp_project.root)
    ops = db.execute(
        "SELECT * FROM operations WHERE op_type = ?",
        (OperationType.PRESET_APPLY.value,)
    ).fetchall()

    assert len(ops) >= 1
    last_op = ops[-1]
    payload = json.loads(last_op["payload"])
    assert payload["preset_name"] == preset_name
    assert "changed_paths" in payload


def test_preset_select_no_event(tmp_project):
    """Preset SELECT (UI-only) does NOT produce operation event."""
    calc = tmp_project.create_calculation("test_preset")
    calc.add_step("scf", step_type_spec="qe_scf")

    # Detect presets (SELECT operation - UI only)
    presets = detect_presets_from_calculation(calc)

    db = open_provenance_db(tmp_project.root)
    ops = db.execute("SELECT COUNT(*) FROM operations").fetchone()[0]

    # Only the calc creation, not the select
    assert ops == 1  # CALC_CREATE only
```

### 9.3 Concurrency Tests

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

    assert not errors

    db = open_provenance_db(tmp_project.root)
    ops_count = db.execute(
        "SELECT COUNT(*) FROM operations WHERE op_type = ?",
        (OperationType.STEP_UPDATE.value,)
    ).fetchone()[0]

    assert ops_count == 100
```

---

## 10. Migration and Compatibility

### 10.1 New Projects

For new projects, provenance is enabled by default:

- First `save_yaml_doc()` call initializes `.provenance/` directory
- First event is `SEED` operation with initial state in payload

### 10.2 Existing Projects (No Provenance)

For existing projects without `.provenance/`:

1. **Lazy initialization:** First provenance-aware operation creates `.provenance/`
2. **Seed event:** First event is `SEED` with `payload={"migration": true}`
3. **No retroactive history:** Past operations are not recorded; timeline starts from migration point

```python
def ensure_provenance_initialized(project_root: Path) -> bool:
    """Initialize provenance for existing project if needed."""
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
    db.execute("""
        INSERT INTO operations (ulid, op_type, timestamp, actor, scope, source, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        generate_ulid(),
        OperationType.SEED.value,
        now_iso8601(),
        ActorType.SYSTEM.value,
        ScopeType.PROJECT.value,
        "ensure_provenance_initialized",
        json.dumps({"migration": True}),
    ))

    return True
```

### 10.3 Deleting Provenance

Deleting `.provenance/` is always safe:

```bash
rm -rf project/.provenance/
```

After deletion:
- Project remains fully runnable (Law P1)
- Next provenance-aware operation re-initializes with new `SEED`
- No warnings or errors

### 10.4 Schema Versioning

```python
CURRENT_SCHEMA_VERSION = 1

def check_schema_version(db: sqlite3.Connection) -> int:
    """Check schema version and migrate if needed."""
    version = db.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]

    if version < CURRENT_SCHEMA_VERSION:
        migrate_schema(db, version, CURRENT_SCHEMA_VERSION)

    return version
```

---

## 11. Future Enhancements

These are explicitly **NOT part of MVP** but designed for:

### 11.1 Buffered Write Mode (Performance)

MVP uses synchronous SQLite append. Future option:

- In-memory buffer for rapid edits
- Flush on: buffer full, before run, explicit save, process exit

### 11.2 Agent Journal (Memory)

Full-featured agent memory:

- Before-run rationale, after-run analysis
- Short titles in SQLite (FTS), bodies in CAS (Tier-1)

### 11.3 Query API

Rich querying for UI/agents:

```python
query = ProvenanceQuery(project)
recent_runs = query.runs().calc(calc_ulid).since(days=7).status("success").limit(10)
```

### 11.4 Export/Reporting

- Timeline visualization (HTML/SVG)
- Audit logs for reproducibility
- Export to W3C PROV format

---

## Appendix A: File Locations

| Component | Path |
|-----------|------|
| Provenance module | `src/qmatsuite/provenance/` |
| OperationContext | `src/qmatsuite/provenance/opctx.py` |
| SQLite schema | `src/qmatsuite/provenance/schema.py` |
| Database operations | `src/qmatsuite/provenance/db.py` |
| CAS implementation | `src/qmatsuite/provenance/cas.py` |
| Artifact scanner | `src/qmatsuite/provenance/scanner.py` |
| Lock utilities | `src/qmatsuite/provenance/locks.py` |
| Gate tests | `tests/gates/test_provenance_*.py` |
| Integration tests | `tests/integration/test_provenance_*.py` |

## Appendix B: API Surface

### Public Functions (Kernel)

```python
# OperationContext creation (convenience helpers)
def opctx_for_preset(preset_name: str, actor: ActorType) -> OperationContext
def opctx_for_step_update(step_ulid: str, actor: ActorType) -> OperationContext
def opctx_for_run(run_ulid: str, actor: ActorType) -> OperationContext

# Provenance recording (internal, called by save_yaml_doc / Runner)
def record_operation_event(project_root: Path, opctx: OperationContext, diff_summary: dict)
def record_run_start(project_root: Path, run_ulid: str, calc_ulid: str, snapshot_sha: str)
def record_run_complete(project_root: Path, run_ulid: str, status: str, finished_at: str)
def record_run_step(project_root: Path, run_ulid: str, step_ulid: str, index: int, ...)

# CAS operations
def cas_store(project_root: Path, content: bytes, tier: int) -> str
def cas_retrieve(project_root: Path, sha256: str) -> bytes
def cas_exists(project_root: Path, sha256: str) -> bool

# Snapshot operations
def create_run_snapshot(project_root: Path, calc_ulid: str, run_ulid: str) -> str
def restore_from_snapshot(project_root: Path, snapshot_sha: str, opctx: OperationContext)

# Query (for UI/agents)
def query_operations(project_root: Path, **filters) -> List[dict]
def query_runs(project_root: Path, **filters) -> List[dict]
def get_run_steps(project_root: Path, run_ulid: str) -> List[dict]
```

### Errors

```python
class OperationContextRequiredError(Exception):
    """Raised when save_yaml_doc() called without opctx."""

class CASIntegrityError(Exception):
    """Raised on CAS corruption or hash mismatch."""

class ProvenanceError(Exception):
    """Base class for provenance errors (non-fatal for YAML ops per Law P7)."""

class SnapshotNotFoundError(ProvenanceError):
    """Raised when requested snapshot doesn't exist in CAS."""
```

---

*End of Specification v1.1*
