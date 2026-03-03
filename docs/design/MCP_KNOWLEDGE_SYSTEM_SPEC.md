# MCP Knowledge System — Design Specification

> **Status**: Living document. `✅` = implemented in code. `🔲` = planned, not yet implemented.
>
> **Last updated**: 2026-03-03 (architecture revision + R1–R10 refinements)

---

## 1. System Overview

### Target Architecture (Two-Layer) 🔲

```
┌─────────────────────────────────────────────────────────────┐
│  Agent (Claude Code / Codex / Gemini CLI)                   │
│         ↕  MCP Protocol (stdio / streamable HTTP)           │
├─────────────────────────────────────────────────────────────┤
│  QMatSuite MCP Server  (FastMCP)                            │
│  ┌────────────┬────────────┬───────────┬──────────────────┐ │
│  │ Discovery  │ Configure  │ Execution │ Knowledge Tools  │ │
│  │ Tools      │ Tools      │ Tools     │                  │ │
│  └────────────┴────────────┴───────────┴────────┬─────────┘ │
│                                                  │           │
│  ┌──────────────────────────┐  ┌────────────────┤           │
│  │  Per-Project Provenance  │  │ KnowledgeStore │           │
│  │  <project>/.provenance/  │  │ ┌────────────┐ │           │
│  │  ┌───────────────┐       │  │ │ builtin.db │ │           │
│  │  │ provenance.db │       │  │ │ (read-only)│ │           │
│  │  │ - operations  │       │  │ ├────────────┤ │           │
│  │  │ - runs        │       │  │ │ local.db   │ │           │
│  │  │ - run_steps   │       │  │ │ (read/write│ │           │
│  │  │ - snapshots   │       │  │ └────────────┘ │           │
│  │  ├───────────────┤       │  └────────────────┘           │
│  │  │ .cas/objects/  │      │                               │
│  │  └───────────────┘       │                               │
│  └──────────────────────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

Two systems. Two scopes. Two responsibilities:

| Layer | Scope | Answers | Storage |
|-------|-------|---------|---------|
| **Provenance** | Per-project | "What happened in THIS project? How did the agent reason?" | `<project>/.provenance/provenance.db` + CAS |
| **Knowledge** | Global | "Across ALL projects, what do we know?" | `<QMATSUITE_HOME>/knowledge/local.db` |

### Current Architecture (Three-Layer) ✅

```
Global Journal (JSONL)         Per-Project Provenance         Global Knowledge
~/.qmatsuite/journal/          <project>/.provenance/         ~/.qmatsuite/knowledge/

- intents                      - YAML mutations               - L3 findings
- ALL insights (L1-L5)           (save_yaml_doc hook)         - L4 patterns
- append-only JSONL            - SQLite run history           - L5 principles
- no query interface           - CAS artifacts                - FTS5 searchable
- GLOBAL scope                 - PROJECT scope                - GLOBAL scope
```

**Problem**: The global JSONL journal is a redundant middle layer. Intents and
L1/L2 insights are project-specific (tied to specific calculations) but stored
globally with no project context. Tracing from L3 back to reasoning requires
grepping an unindexed JSONL file. Meanwhile, the provenance system already has
a rich queryable SQLite schema per project.

### Key Locations

| Resource | Path | Scope | Status |
|----------|------|-------|--------|
| builtin.db | `<QMATSUITE_HOME>/knowledge/builtin.db` | Global, read-only | ✅ |
| local.db | `<QMATSUITE_HOME>/knowledge/local.db` | Global, cross-project | ✅ |
| Provenance DB | `<project>/.provenance/provenance.db` | Per-project | ✅ |
| Provenance CAS | `<project>/.provenance/.cas/objects/` | Per-project | ✅ |
| Global journal | `~/.qmatsuite/journal/journal.jsonl` | Global | ✅ (to be deprecated) |

Where `<QMATSUITE_HOME>` resolves via `get_app_data_dir()`:
1. `QMATSUITE_HOME` env var (explicit override)
2. Dev mode: `<repo_root>/.qmatsuite/`
3. Electron mode: platform app-data directory
4. Fallback: `~/.qmatsuite/`

---

## 2. MCP Tool Inventory

39 tools registered in `server.py`, organized by stage:

| # | Tool | Purpose | Category |
|---|------|---------|----------|
| 1 | `init_project` | Initialize a QMatSuite project | project |
| 2 | `ping` | Health check / connectivity test | discovery |
| 3 | `list_engines` | List available calculation engines | discovery |
| 4 | `list_workflows` | List workflow templates for an engine | discovery |
| 5 | `get_presets` | Get parameter presets for engine+workflow | discovery |
| 6 | `search_parameters` | Search engine parameter documentation | discovery |
| 7 | `create_calculation` | Create a new calculation | configuration |
| 8 | `set_species_map` | Set element-to-pseudopotential mapping | configuration |
| 9 | `set_parameters` | Set calculation parameters | configuration |
| 10 | `apply_preset` | Apply a parameter preset | configuration |
| 11 | `inspect_calculation` | Inspect calculation state | configuration |
| 12 | `list_calculations` | List project calculations | configuration |
| 13 | `preview_compilation` | Preview input file compilation | configuration |
| 14 | `run_calculation` | Run a calculation step | execution |
| 15 | `get_status` | Get run status | execution |
| 16 | `get_results_summary` | Get results after a run | execution |
| 17 | `quick_run` | One-shot create + configure + run | execution |
| 18 | `search_knowledge` | BM25 full-text search over knowledge | **knowledge** |
| 19 | `record_insight` | Record agent-authored insight | **knowledge** |
| 20 | `record_intent` | Record agent intent in provenance | **knowledge** |
| 21 | `list_insights` | Browse insights by grade | **knowledge** |
| 22 | `list_structures` | List project-level structures | structure |
| 23 | `import_structure` | Import a crystal structure | structure |
| 24 | `get_structure_detail` | Get structure details | structure |
| 25 | `promote_structure` | Promote calc-local structure to project | structure |
| 26 | `demo_store` | Browse and load demo calculations | demo |
| 27 | `list_resources` | List available resources | resource |
| 28 | `resolve_species_map` | Auto-resolve species map | resource |
| 29 | `download_pseudo_library` | Download pseudopotential library | resource |
| 30 | `cleanup_project` | Clean up stale project state | project |
| 31 | `install_engine` | Install a calculation engine | engine |
| 32 | `list_installable_engines` | List engines available for install | engine |
| 33 | `verify_engine` | Verify engine installation | engine |
| 34 | `register_engine_path` | Register custom engine binary path | engine |
| 35 | `uninstall_engine` | Uninstall an engine | engine |
| 36 | `set_active_engine` | Set active engine version | engine |
| 37 | `list_analyses` | List available analysis types | analysis |
| 38 | `plot_analysis` | Generate analysis plot | analysis |
| 39 | `generate_kpath` | Generate k-point path for band structure | analysis |

---

## 3. Knowledge Grade Hierarchy

```
Level  Grade         Promoted to local.db?  Provenance trace?  Who Creates
─────  ────────────  ─────────────────────  ─────────────────  ──────────────────────
L1     bookkeeping   NO                     YES (project)      Agent (mechanical notes)
L2     observation   NO                     YES (project)      Agent (preliminary)
L3     finding       YES                    YES (dual-write)   Agent (verified)
L4     pattern       YES                    YES (dual-write)   Agent (nudged at 8+ L3s)
L5     principle     YES                    YES (dual-write)   Agent (nudged at 3+ L4s)
```

### Grade Definitions

| Grade | Definition | Example |
|-------|-----------|---------|
| `bookkeeping` | Mechanical notes, not searchable | "Started SCF convergence test series" |
| `observation` | Preliminary observation, not yet verified | "ecutwfc=60 Ry seems sufficient for Si" |
| `finding` | Verified, reproducible conclusion from data | "Si SCF converges to <1 meV with ecutwfc>=50 Ry and 8x8x8 k-mesh" |
| `pattern` | Synthesis of multiple findings into recurring theme | "Semiconductors with diamond structure converge at lower ecutwfc than oxides" |
| `principle` | High-level rule distilled from patterns | "Start ecutwfc convergence at 0.8x the highest PP cutoff hint; increase by 10 Ry increments" |

### ✅ Enforcement Rules

- **L4 (`pattern`) requires references** — at least one L3 finding ID. Rejected without. ✅ G2: error hint says `grade='finding'`.
- **L5 (`principle`) requires references** — at least one L4 pattern ID. Rejected without. ✅ G2: error hint says `grade='pattern'`.
- **L1-L3** — references optional.
- Referenced IDs are validated: warn if not found in DB (non-blocking).
- ✅ G8: `list_insights` validates `mode` parameter (`"pending"` or `"recent"`).
- ✅ G9: `list_insights` response includes `mode` field.

### ✅ Ordering Constants

```python
_GRADE_ORDER = {"principle": 5, "pattern": 4, "finding": 3, "observation": 2, "bookkeeping": 1}
_PROMOTABLE_GRADES = frozenset({"finding", "pattern", "principle"})
```

---

## 4. Knowledge Tools — Detailed Spec

### 4.1 `search_knowledge` ✅

**File**: `src/qmatsuite/mcp/tools/search_knowledge.py`

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | `""` | Free-text search query (BM25) |
| `engine` | `str` | `""` | Engine scope filter (e.g. `"vasp"`, `"qe"`) |
| `workflow` | `str` | `""` | Workflow filter (NOT used as hard filter — BM25 handles relevance) |
| `system_type` | `str` | `""` | System type filter (e.g. `"metal"`, `"semiconductor"`) |
| `method` | `str` | `""` | Method filter (e.g. `"dft+u"`, `"hse"`) |
| `grade_min` | `str` | `""` | Minimum grade filter |
| `confidence_min` | `str` | `""` | Minimum confidence filter |
| `limit` | `int` | `10` | Max results (max 50) |

**Behavior**:

1. If `query` non-empty: FTS5 BM25 search across builtin + local DBs
2. If `query` empty: scope-only search (no text matching)
3. Results merged via reserved-slot algorithm (see §4.1.1)
4. Entries with `contradiction_count >= 3` get `[UNDER REVIEW]` prefix
5. Content truncated to 300 chars in response
6. Context note appended based on grade distribution (see §4.1.2)

#### 4.1.1 Reserved Slots ✅

```python
LOCAL_RESERVED_SLOTS = 3
```

Algorithm (`_merge_with_reserved_slots`):
1. Take up to 3 local results (preserving rank order)
2. Fill remaining `limit - len(local_take)` slots with builtin results
3. Local results always appear first in the result list

**Builtin toggle**: `QMS_KNOWLEDGE_BUILTIN` env var. Set to `"0"` to disable builtin DB in search. Default `"1"`. Only affects search — contradiction detection still checks both DBs.

#### 4.1.2 Context Note

**✅ Current**: Global count check, first-match-wins:

| Condition | Message |
|-----------|---------|
| `patterns >= 3 AND principles == 0` | "You have {N} patterns and 0 principles — consider synthesizing a principle..." |
| `findings >= 8 AND patterns == 0` | "You have {N} findings and 0 patterns — consider synthesizing a pattern..." |

**✅ R1+R3**: Replace with sliding-window pending count (see §4.1.2.1) and soft tone:

| Condition | Message |
|-----------|---------|
| `pending_patterns >= 3 AND pending_principles == 0` | "You have {N} patterns pending synthesis. Consider reviewing with list_insights(grade='pattern') when your current task is complete." |
| `pending_findings >= 8 AND pending_patterns == 0` | "You have {N} findings pending synthesis. Consider reviewing with list_insights(grade='finding') when your current task is complete." |

##### 4.1.2.1 Sliding Window SQL 🔲

```sql
-- Last L4 synthesis timestamp
SELECT MAX(created_at) AS last_l4 FROM insights
WHERE grade = 'pattern' AND status = 'active';

-- Pending L3 count (findings since last L4, or all if no L4)
SELECT COUNT(*) FROM insights
WHERE grade = 'finding' AND status = 'active'
  AND created_at > COALESCE(:last_l4, '1970-01-01');
```

Same pattern for L4-pending-since-last-L5.

#### 4.1.3 FTS5 Query Sanitization ✅

Raw queries are sanitized before FTS5 matching:
- Extract word tokens via `r"[a-zA-Z0-9_]+"`
- Strip FTS5 reserved words (`AND`, `OR`, `NOT`, `NEAR`)
- Join remaining tokens with `OR`
- BM25 naturally ranks multi-token matches higher

#### 4.1.4 Trust-Weighted Ranking ✅

```python
TRUST_WEIGHTS = {
    "builtin": 1.0, "local": 1.0, "literature": 0.9,
    "docs": 0.85, "mailinglist": 0.7, "tutorial": 0.7, "community": 0.6,
}
_CONFIDENCE_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}
```

Score formula: `confidence_weight * raw_bm25_rank * trust_weight`

Tie-breaking: `_GRADE_ORDER` (higher grades win).

**Response format**:

```json
{
  "status": "success",
  "data": {
    "query": "SCF convergence",
    "filters": {
      "engine": "qe",
      "workflow": null,
      "system_type": null,
      "method": null,
      "grade_min": null,
      "confidence_min": null
    },
    "results": [
      {
        "id": "01HXYZ1234",
        "grade": "finding",
        "scope_engine": "qe",
        "scope_workflow": "scf",
        "scope_system_type": "*",
        "scope_method": "*",
        "content": "Truncated to 300 chars...",
        "confidence": "medium",
        "tags": ["convergence", "scf"],
        "source_type": "local",
        "upvotes": 3,
        "downvotes": 0,
        "metadata": {"agent_model": "claude-opus-4-6", "created_at": "..."},
        "contradiction_count": 0
      }
    ],
    "total_results": 1
  },
  "context_hint": "Found 1 insight(s). Use these insights to inform...",
  "warnings": []
}
```

Note: ✅ G7: `tags` is now a parsed JSON list (not a raw string). `contradiction_count` only included when > 0. `metadata` parsed from JSON. ✅ R7: `id` field is 14-char short ID. ✅ R11: `upvotes`/`downvotes` always included. G1-G9 from naive agent review addressed.

---

### 4.2 `list_insights`

**File**: `src/qmatsuite/mcp/tools/list_insights.py`

**Parameters**:

| Parameter | Type | Default | Description | Status |
|-----------|------|---------|-------------|--------|
| `grade` | `str` | (required) | One of `"finding"`, `"pattern"`, `"principle"` | ✅ |
| `limit` | `int` | `20` | Max results (clamped to 1-100) | ✅ |
| `compound` | `str` | `""` | Optional compound filter (matches tags via LIKE) | ✅ |
| `mode` | `str` | `"pending"` | `"pending"` or `"recent"` | ✅ R5 |

**Behavior**:

1. Validates `grade` is one of `finding`, `pattern`, `principle`
2. Queries local.db only (not builtin)
3. ✅ R5: If `mode="pending"`: only insights since last higher-grade synthesis
4. ✅ R5: If `mode="recent"`: all active insights, ordered by `created_at DESC`
5. ✅ R9: Content returned in FULL (no truncation) — this tool is for synthesis review
6. ✅ R6: Response header shows pending count

**✅ Current SQL**:

```sql
SELECT * FROM insights WHERE grade = ? AND status = 'active'
  [AND tags LIKE '%compound%']
  ORDER BY created_at DESC LIMIT ?
```

**✅ R5 Pending Mode SQL**:

```sql
-- For grade='finding', pending since last pattern
SELECT * FROM insights
WHERE grade = 'finding' AND status = 'active'
  AND created_at > COALESCE(
    (SELECT MAX(created_at) FROM insights WHERE grade = 'pattern' AND status = 'active'),
    '1970-01-01'
  )
  [AND tags LIKE '%compound%']
  ORDER BY created_at DESC LIMIT ?
```

**✅ R6 Response Header**:

```
"Showing {shown} of {total_pending} pending findings (since last pattern synthesis at {last_l4_time})"
```

Or if no higher-grade synthesis has occurred:
```
"Showing {shown} of {total_pending} findings (no pattern synthesis yet)"
```

**Context hints by grade**:

| Grade | Hint |
|-------|------|
| `finding` | "Review findings, then synthesize a pattern with record_insight(grade='pattern', references=[...])" |
| `pattern` | "Review patterns, then synthesize a principle with record_insight(grade='principle', references=[...])" |
| `principle` | "These are your highest-level insights." |

**Response format** (✅ R5+R6+R7+R9 target):

```json
{
  "status": "success",
  "data": {
    "grade": "finding",
    "mode": "pending",
    "total_pending": 12,
    "since": "2026-03-01T10:00:00+00:00",
    "insights": [
      {
        "id": "01HXYZ1234",
        "grade": "finding",
        "content": "Full content, not truncated...",
        "tags": ["silicon", "convergence"],
        "created_at": "2026-03-03T12:00:00+00:00",
        "upvotes": 2,
        "downvotes": 0,
        "metadata": {"agent_model": "claude-opus-4-6", "created_at": "..."}
      }
    ]
  },
  "context_hint": "Showing 12 of 12 pending findings (no pattern synthesis yet). Review...",
  "warnings": []
}
```

---

### 4.3 `record_insight`

**File**: `src/qmatsuite/mcp/tools/record_insight.py`

**Parameters** ✅:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | (required) | Distilled conclusion text |
| `grade` | `str` | `"observation"` | Quality tier (see §3) |
| `reasoning` | `str` | `""` | Detailed thought process (provenance only) |
| `scope_engine` | `str` | `"*"` | Engine scope (e.g. `"qe"`, `"vasp"`) |
| `scope_workflow` | `str` | `"*"` | Workflow scope (e.g. `"scf"`, `"relax"`) |
| `scope_system_type` | `str` | `"*"` | System type (e.g. `"metal"`) |
| `scope_method` | `str` | `"*"` | Method scope (e.g. `"dft+u"`) |
| `tags` | `str` | `""` | Comma-separated or JSON array |
| `calc_ulid` | `str` | `""` | Optional link to source calculation |
| `source_calculation` | `str` | `""` | ULID of producing calculation |
| `references` | `str` | `""` | Comma-separated or JSON array of insight IDs |
| `citations` | `str` | `""` | Comma-separated `"ULID:up"` or `"ULID:down"` pairs |

**Behavior — Write Path**:

✅ Current:
```
Validation → Journal write (ALL grades) → Knowledge DB (L3+) → Citations → Nudge → Response
```

🔲 Target:
```
Validation → Provenance write (ALL grades) → Knowledge DB (L3+) → Citations → Nudge → Response
```

**Citation Format** ✅:

```
"01AAA:up,01BBB:down,01CCC:up"
```

Parsing: split on `,`, then `rsplit(":", 1)`. Vote must be `"up"` or `"down"`. Invalid pairs generate warnings but don't block the insight.

**Citation Effects** ✅:
1. Stored in insight metadata JSON: `metadata.citations = [{"id": "01AAA", "vote": "up"}, ...]`
2. Vote counters updated: `UPDATE insights SET upvotes = upvotes + 1 WHERE id = ?`
3. Missing IDs silently skipped (rowcount = 0)
4. Votes applied even for non-promoted grades (L1/L2)

**Nudge Behavior**:

✅ Current — fires after a promoted insight is recorded. Conditions (first match wins):

| Condition | Message |
|-----------|---------|
| `patterns >= 3 AND principles == 0` | "You have {N} patterns..." |
| `findings >= 8 AND patterns == 0 AND findings % 8 < 2` | "You have {N} findings..." |

The `findings % 8 < 2` window means nudges fire at: 8, 9, 16, 17, 24, 25, ...

✅ R1+R2+R3+R4 Target:

- `_maybe_nudge()` returns a **list** of nudge strings (not single-or-None)
- Uses sliding-window pending count (same SQL as §4.1.2.1)
- Fires **every time** pending count >= threshold (no `%8` window modulus)
- Both L3→L4 and L4→L5 can fire simultaneously (L5 listed first)
- Stochastic gate: `random.random() < float(os.environ.get("QMS_NUDGE_PROBABILITY", "1.0"))`
- Strong tone for record_insight nudges:

```
Knowledge synthesis checkpoint: {N} new findings since last pattern
synthesis, covering {compounds}. Synthesizing patterns is part of your
research program. Use list_insights(grade='finding') to review, then
record_insight(grade='pattern', references=[...]). It's okay to skip
if findings don't yet show a clear pattern.
```

**Response format** ✅ (✅ R7: `insight_id` will be 10-char):

```json
{
  "status": "success",
  "data": {
    "insight_id": "01HXYZ1234",
    "promoted": true,
    "grade": "finding",
    "contradictions": [],
    "citation_summary": "Cited 2 insight(s) (1 helpful, 1 not)"
  },
  "context_hint": "Insight recorded in knowledge base...",
  "warnings": []
}
```

🔲 Architecture change: Remove `journal_entry_ulid` and `journal_recorded` from response. Replace with `provenance_recorded: bool`.

---

### 4.4 `record_intent`

**File**: `src/qmatsuite/mcp/tools/record_intent.py`

**Parameters** ✅:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `intent` | `str` | (required) | Agent's intent statement |
| `calc_ulid` | `str` | `""` | Optional link to target calculation |
| `tags` | `str` | `""` | Comma-separated or JSON array |

**Behavior**:

✅ Current: Journal-only write via `get_journal().record_change()`.

🔲 Target: Provenance-only write via `record_operation_event()` with
`OperationType.CUSTOM` and `payload.type = "agent_intent"`. Requires
project context (see §14).

Does NOT write to knowledge DB.

**Response format** ✅:

```json
{
  "status": "success",
  "data": {
    "intent_id": "01HXYZ...",
    "intent": "Truncated to 200 chars...",
    "calc_ulid": null,
    "tags": ["convergence"]
  },
  "context_hint": "Intent recorded. Proceed with your planned action...",
  "warnings": []
}
```

---

## 5. Agent Workflow — Complete Session Path

### Designed Session Flow

```
SEARCH → PLAN → EXECUTE → RECORD → [SYNTHESIZE if nudged]
```

| Step | Tool(s) | Agent Sees | Agent Should |
|------|---------|-----------|--------------|
| **Search** | `search_knowledge(query, engine)` | Prior insights, best practices | Absorb relevant knowledge; cite helpful entries later |
| **Plan** | `record_intent(intent, calc_ulid)` | Confirmation | State reasoning before action |
| **Execute** | `run_calculation`, `get_results_summary` | Run results | Analyze outputs |
| **Record** | `record_insight(content, grade, citations)` | Confirmation + nudge? | Record verified conclusions |
| **Synthesize** | Nudge-triggered cycle (see below) | Nudge message in context_hint | Follow synthesis sub-flow |

### Synthesis Sub-Flow (when nudge fires)

```
Nudge received (in context_hint)
  → list_insights(grade='finding', mode='pending')   # Review pending L3s
  → Read findings, identify themes
  → record_insight(
      grade='pattern',
      content='...',
      references='ID1,ID2,ID3',       # L3 IDs that support this pattern
      citations='ID4:up,ID5:down'      # Prior knowledge that helped/misled
    )
  → [If L5 nudge fires next]
  → list_insights(grade='pattern', mode='pending')   # Review pending L4s
  → record_insight(
      grade='principle',
      content='...',
      references='PATID1,PATID2'
    )
```

### Write Path Summary

| Event | Provenance (per-project) | Knowledge (global) |
|-------|------------------------|--------------------|
| `record_intent` | 🔲 operations table | — |
| `record_insight` L1/L2 | 🔲 operations table | — |
| `record_insight` L3/L4/L5 | 🔲 operations table | ✅ local.db INSERT |
| `save_yaml_doc` | ✅ operations table | — |
| `run_calculation` | ✅ runs + run_steps tables | — |

### Traceability Chain

```
L5 principle (local.db)
  └── references → L4 pattern IDs (local.db)
        └── references → L3 finding IDs (local.db)
              └── source_calculation → calculation ULID
                    └── provenance.db → runs, run_steps, operations
                          └── .cas/ → snapshots, artifacts
```

---

## 6. Provenance System

### Per-Project Provenance ✅

**Location**: `<project>/.provenance/`

**Contents**:
- `provenance.db` — SQLite database (schema version 3)
- `provenance.lock` — portalocker-based file lock
- `.cas/objects/` — Content-addressed store (SHA-256 paths)
- `.cas/tmp/` — Atomic write staging
- `.cas/gc.lock` — Garbage collection lock

**Schema** (from `src/qmatsuite/provenance/schema.py`):

```sql
-- 5 tables, schema version 3

CREATE TABLE schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE operations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ulid            TEXT NOT NULL UNIQUE,
    op_type         TEXT NOT NULL,        -- OperationType enum (24 values)
    timestamp       TEXT NOT NULL,
    actor           TEXT NOT NULL,        -- HUMAN | AGENT | SYSTEM
    scope           TEXT NOT NULL,        -- PROJECT | CALC | STEP | STRUCTURE | RESOURCE
    target_ulid     TEXT,
    calc_ulid       TEXT,
    source          TEXT NOT NULL,        -- kernel method name
    facade_endpoint TEXT,
    request_id      TEXT,
    payload         TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ulid        TEXT NOT NULL UNIQUE,
    calc_ulid       TEXT NOT NULL,
    project_ulid    TEXT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL DEFAULT 'running',  -- running|success|failed|aborted
    error_message   TEXT,
    snapshot_sha    TEXT,                              -- CAS ref: pre-run SSOT snapshot
    engine          TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE run_steps (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ulid                TEXT NOT NULL,
    step_ulid               TEXT NOT NULL,
    step_index              INTEGER NOT NULL,
    started_at              TEXT,
    finished_at             TEXT,
    status                  TEXT NOT NULL DEFAULT 'pending',
    snapshot_sha            TEXT,
    artifact_collection_sha TEXT,
    digest_sha              TEXT,
    UNIQUE(run_ulid, step_ulid),
    FOREIGN KEY (run_ulid) REFERENCES runs(run_ulid)
);

CREATE TABLE analysis_snapshots (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ulid                TEXT NOT NULL,
    object_type             TEXT NOT NULL,
    canonical_sha           TEXT NOT NULL,
    thumbnail_sha           TEXT,
    match_key               TEXT,
    evidence_fingerprint    TEXT,
    step_ulids              TEXT NOT NULL,   -- JSON array
    gen_steps               TEXT NOT NULL,   -- JSON array
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(run_ulid, object_type, match_key),
    FOREIGN KEY (run_ulid) REFERENCES runs(run_ulid)
);

CREATE TABLE cas_objects (
    sha256              TEXT PRIMARY KEY,
    tier                INTEGER NOT NULL,   -- 0, 1, 2, 3
    size_bytes          INTEGER NOT NULL,
    content_type        TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    last_referenced_at  TEXT,
    deleted             BOOLEAN NOT NULL DEFAULT 0
);
```

**OperationType enum** (24 values from `provenance/opctx.py`):

```
PROJECT_CREATE, PROJECT_UPDATE,
CALC_CREATE, CALC_UPDATE, CALC_DELETE, CALC_COPY, CALC_FORK,
STEP_ADD, STEP_UPDATE, STEP_REMOVE, STEP_REORDER,
PRESET_APPLY, PRESET_CLEAR,
STRUCTURE_CREATE, STRUCTURE_UPDATE, STRUCTURE_IMPORT, RELAX_PROMOTE,
SPECIES_MAP_UPDATE, PSEUDO_ASSIGN,
RESTORE, ROLLBACK,
PIN_CREATE, PIN_DELETE,
SEED, CORRECTION, CUSTOM
```

**Key provenance laws**:
- P1: History world independence (deleting `.provenance/` leaves project runnable)
- P6: Lock ordering (edit.lock released before provenance.lock acquired)
- P7: Graceful degradation (provenance failures never break saves)

### Global JSONL Journal ✅ (to be deprecated)

**Location**: `~/.qmatsuite/journal/journal.jsonl`

**Format**: Append-only JSONL. One JSON object per line.

**JournalEntry fields**:

| Field | Type | Description |
|-------|------|-------------|
| `ulid` | `str` | Unique entry ID (ULID) |
| `target_ulid` | `str` | Document or calculation this entry relates to |
| `doc_type` | `str` | `"step"`, `"calc"`, `"project"`, `"unknown"` |
| `timestamp` | `str` | ISO 8601 UTC |
| `before` | `dict` | Snapshot before change (deep copy) |
| `after` | `dict` | Snapshot after change (deep copy) |
| `summary` | `str` | Human-readable description |
| `path` | `str?` | File path (debugging aid) |

**Current writers** (3):
1. `save_yaml_doc()` in `yaml_io.py:211-239` — all YAML mutations
2. `record_insight()` in `record_insight.py:127-153` — insight entries
3. `record_intent()` in `record_intent.py:56-71` — intent entries

**Current readers** (2 production, plus tests):
1. `daemon/server.py:4717-4745` — `_handle_list_journal_entries()` RPC handler
2. `daemon/server.py:4747-4767` — `_handle_get_journal_entry()` RPC handler

**IMPORTANT**: The daemon/GUI reads the journal via two JSON-RPC endpoints:
`list_journal_entries` and `get_journal_entry`. These are used by the GUI
for displaying change history. This blocks a clean removal of journal writes
(see §14.1 for details).

---

## 7. local.db Schema

### ✅ `insights` Table (25 columns)

```sql
CREATE TABLE IF NOT EXISTS insights (
    id                  TEXT PRIMARY KEY,
    grade               TEXT NOT NULL,
    scope_engine        TEXT DEFAULT '*',
    scope_workflow      TEXT DEFAULT '*',
    scope_system_type   TEXT DEFAULT '*',
    scope_method        TEXT DEFAULT '*',
    scope_extra         TEXT DEFAULT '{}',
    content             TEXT NOT NULL,
    confidence          TEXT DEFAULT 'medium',
    source_type         TEXT NOT NULL DEFAULT 'local',
    source_pack_id      TEXT,
    source_origin       TEXT,
    provenance_ref      TEXT,
    created_by          TEXT NOT NULL,
    tags                TEXT,
    status              TEXT DEFAULT 'active',
    superseded_by       TEXT,
    deprecated_reason   TEXT,
    merged_into         TEXT,
    last_validated      TEXT,
    contradiction_count INTEGER DEFAULT 0,
    upvotes             INTEGER DEFAULT 0,
    downvotes           INTEGER DEFAULT 0,
    metadata            TEXT DEFAULT '{}',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    FOREIGN KEY (superseded_by) REFERENCES insights(id)
);
```

### ✅ `insights_fts` Virtual Table (FTS5)

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS insights_fts USING fts5(
    content, tags, scope_engine, scope_system_type,
    content='insights', content_rowid='rowid'
);
```

Kept in sync via 3 triggers: `insights_ai` (INSERT), `insights_ad` (DELETE), `insights_au` (UPDATE).

### ✅ Indexes

```sql
CREATE INDEX idx_insights_grade      ON insights(grade);
CREATE INDEX idx_insights_scope      ON insights(scope_engine, scope_workflow, scope_system_type, scope_method);
CREATE INDEX idx_insights_source     ON insights(source_type);
CREATE INDEX idx_insights_status     ON insights(status);
CREATE INDEX idx_insights_confidence ON insights(confidence);
```

### ✅ Migrations

| Migration | Column | Default |
|-----------|--------|---------|
| `_migrate_metadata_column()` | `metadata TEXT` | `'{}'` |
| `_migrate_downvotes_column()` | `downvotes INTEGER` | `0` |

Both check `PRAGMA table_info(insights)` before altering. Called in `init_db()`.

### Metadata JSON Structure

Stored in `metadata TEXT` column. Built in `store.add()`:

```json
{
  "agent_model": "claude-opus-4-6",
  "created_at": "2026-03-03T12:00:00+00:00",
  "source_calculation": "01CALC...",
  "references": ["01AAA", "01BBB"],
  "citations": [
    {"id": "01CCC", "vote": "up"},
    {"id": "01DDD", "vote": "down"}
  ]
}
```

Only `agent_model` and `created_at` are always present. Others are conditional.

---

## 8. ID System

### ✅ Current

Full 26-character ULIDs everywhere:
- Insight IDs in local.db
- Insight IDs in search results, list results, nudge messages
- Reference and citation inputs from agent
- Journal entry ULIDs

### ✅ R7: Short IDs in Agent-Facing Output

All agent-facing ID output uses first 14 chars of ULID:
- `search_knowledge` results: `id` field
- `list_insights` results: `id` field
- `record_insight` response: `insight_id` field
- Nudge messages: any referenced IDs

Internal storage always full 26-char ULID.

**Implementation**: Truncation happens in tool layer (search_knowledge.py, list_insights.py,
record_insight.py), NOT in store.py. Store always returns full ULIDs.

### ✅ R8: Short ID Prefix Resolution on Input

Agent inputs (`references`, `citations`) accept 14-char (or longer) short IDs.

**Resolution** (in `store.py`):

```python
def resolve_short_id(self, prefix: str) -> str:
    """Resolve short ID prefix to full ULID. Raises on ambiguity."""
    rows = self.local_conn.execute(
        "SELECT id FROM insights WHERE id LIKE ? || '%'",
        (prefix,),
    ).fetchall()
    if len(rows) == 0:
        raise ValueError(f"No insight found matching prefix '{prefix}'")
    if len(rows) > 1:
        raise ValueError(f"Ambiguous prefix '{prefix}' matches {len(rows)} insights; use longer prefix")
    return rows[0][0]
```

Called from `record_insight.py` when parsing references and citations.
Errors returned as warnings (non-blocking for citations, blocking for references on L4/L5).

---

## 9. Configuration

### Environment Variables

| Variable | Default | Description | Used In | Status |
|----------|---------|-------------|---------|--------|
| `QMS_KNOWLEDGE_BUILTIN` | `"1"` | Set to `"0"` to disable builtin.db in search | `store.py:_builtin_enabled()` | ✅ |
| `QMS_AGENT_MODEL` | `"unknown"` | Agent model identifier stored in metadata | `store.py:add()` | ✅ |
| `QMATSUITE_HOME` | (platform) | Override app data root | `core/paths.py` | ✅ |
| `QMATSUITE_PROJECT` | `"."` | Project directory for auto-detection | `server.py` | ✅ |
| `QMS_NUDGE_PROBABILITY` | `"1.0"` | Nudge firing probability | `store.py:_maybe_nudge()` | ✅ R4 |

---

## 10. MCP Preamble

### ✅ Current text (from `src/qmatsuite/mcp/app.py`, post-G3/G6 rewrite):

```
You are a computational materials science research assistant powered by QMatSuite.

WORKFLOW FOR EVERY TASK:
1. search_knowledge — check what's known before calculating
2. record_intent — state your plan, referencing knowledge entries you'll use
3. Execute calculations (create_calculation, run_calculation, etc.)
4. record_insight — record verified results as grade='finding'
5. Respond to synthesis nudges when they appear

KNOWLEDGE GRADES (5 levels):
  bookkeeping/observation — preliminary notes (not searchable)
  finding — verified result from one calculation (promoted to knowledge DB)
  pattern — trend across multiple findings (requires references to findings)
  principle — general rule from patterns (requires references to patterns)

CITATIONS — when recording insights:
  Format: citations="ID:up,ID:down"
  up = your calculation CONFIRMS this knowledge was correct
  down = your calculation CONTRADICTS this knowledge
  No citation = knowledge was irrelevant to this calculation

Search results show upvotes/downvotes from prior sessions. High downvotes
suggest the knowledge may be unreliable — verify before relying on it.
```

### ✅ R10: Add Search-Before-Calculate Guidance

Append to preamble:

```
Before starting new calculations:
- Search the knowledge base for relevant prior findings
- Check if similar compounds or workflows have been studied before
```

---

## 11. Response Envelope

All tools use a standard envelope from `src/qmatsuite/mcp/envelope.py`:

### Success Envelope ✅

```json
{
  "status": "success",
  "data": { "..." : "..." },
  "context_hint": "Guidance for the agent's next action",
  "warnings": ["Optional warning messages"]
}
```

### Error Envelope ✅

```json
{
  "status": "error",
  "error_type": "VALIDATION_ERROR",
  "message": "Human-readable error",
  "severity": "error",
  "context_hint": "How to fix this",
  "suggestions": ["Actionable suggestions"],
  "diagnostics": [{"param": "grade", "issue": "Invalid value"}],
  "suggested_fixes": [{"action": "retry", "params": {"grade": "finding"}}]
}
```

---

## 12. InsightRecord Dataclass

**File**: `src/qmatsuite/mcp/knowledge/insight_record.py`

```python
@dataclass
class InsightRecord:
    content: str                                    # Distilled conclusion
    reasoning: str | None = None                    # Thought process (provenance only)
    grade: str = "observation"                      # Quality tier
    scope: dict = field(default_factory=dict)       # {engine, workflow, system_type, method}
    run_refs: list[str] = field(default_factory=list)  # Calculation ULIDs
    tags: list[str] = field(default_factory=list)   # Freeform tags
    intent_id: str | None = None                    # Links back to recorded intent
    created_by: str = "agent"                       # Origin
    source_calculation: str | None = None           # ULID of producing calculation
    references: list[str] = field(default_factory=list)  # IDs of referenced insights
    citations: list[dict] = field(default_factory=list)  # [{"id": str, "vote": str}]
```

---

## 13. Refinements Summary (R1-R10)

| # | Refinement | Files | Size | Depends On |
|---|-----------|-------|------|-----------|
| R1 | Sliding window nudge | `store.py` | M | — |
| R2 | Simultaneous L3→L4 + L4→L5 nudge | `store.py`, `record_insight.py` | S | R1 |
| R3 | Soft/strong nudge tone | `store.py`, `search_knowledge.py` | S | R1 |
| R4 | Stochastic nudge probability | `store.py` | S | R1 |
| R5 | `list_insights` mode param | `list_insights.py`, `store.py` | M | R1 |
| R6 | `list_insights` pending count header | `list_insights.py` | S | R5 |
| R7 | Short IDs (10-char) in output | `search_knowledge.py`, `list_insights.py`, `record_insight.py` | M | — |
| R8 | Short ID prefix resolution on input | `store.py`, `record_insight.py` | S | R7 |
| R9 | `list_insights` no truncation | `list_insights.py` | S | — |
| R10 | Preamble search-before-calculate | `app.py` | S | — |
| A1 | Architecture: journal → provenance | `record_insight.py`, `record_intent.py`, `yaml_io.py`, `daemon/server.py` | L | — |

### Dependency Graph

```
R1 (sliding window) ← R2 (simultaneous nudges)
                     ← R3 (nudge tone)
                     ← R4 (stochastic nudge)
                     ← R5 (list_insights mode) ← R6 (pending count header)
R7 (short ID output) ← R8 (short ID input)
R9, R10: independent
A1: independent (but largest blast radius)
```

### Suggested PR Grouping

| PR | Changes | Rationale |
|----|---------|-----------|
| PR-1 | R9, R10 | Trivial, no dependencies, safe to land first |
| PR-2 | R7, R8 | Short IDs — self-contained, UI-facing |
| PR-3 | R1, R2, R3, R4, R5, R6 | Nudge overhaul — all interdependent |
| PR-4 | A1 | Architecture change — large blast radius, separate from MCP refinements |

---

## 14. Architecture Migration Plan

### 14.1 Code Review Findings

#### 14.1.1 All Callers of Journal Write

| Caller | File:Line | What It Writes | Can Remove? |
|--------|-----------|---------------|-------------|
| `save_yaml_doc()` | `yaml_io.py:211-239` | YAML before/after snapshots for step/calc/project mutations | Yes — provenance `operations` table already records the same events (lines 241-270 of same function) |
| `record_insight()` | `record_insight.py:127-153` | Insight content, grade, reasoning, scope, tags, references | Yes — move to provenance |
| `record_intent()` | `record_intent.py:56-71` | Intent text, calc_ulid, tags | Yes — move to provenance |

#### 14.1.2 All Readers of Journal

| Reader | File:Line | What It Reads | Impact of Removing Writes |
|--------|-----------|--------------|--------------------------|
| `_handle_list_journal_entries()` | `daemon/server.py:4717-4745` | Filtered list of journal entries (by target_ulid, doc_type, limit) | **BREAKS GUI** — timeline view depends on this |
| `_handle_get_journal_entry()` | `daemon/server.py:4747-4767` | Single entry by ULID | **BREAKS GUI** — detail view depends on this |

**SURPRISE**: The daemon/GUI actively reads the journal. Two RPC endpoints
(`list_journal_entries`, `get_journal_entry`) serve journal data to the GUI.
Removing journal writes requires either:
- (a) Replacing these endpoints with provenance queries, or
- (b) Keeping journal writes for YAML mutations only (those are already
  dual-written to provenance anyway)

#### 14.1.3 save_yaml_doc() Dual-Write Analysis

`yaml_io.py` lines 210-270 show that `save_yaml_doc()` **already dual-writes**:
1. Lines 211-239: Journal write (global JSONL, before/after snapshots)
2. Lines 241-270: Provenance write (per-project SQLite `operations` table via `record_operation_event()`)

The journal write is redundant for YAML mutations. The provenance write is
strictly superior (queryable SQLite, per-project scoping, diff summary, OperationContext).

#### 14.1.4 Current Project Context Flow

MCP tools access project context via:
```python
from qmatsuite.mcp.project import get_project_root, get_service, ProjectNotFoundError
```

**Project-aware tools** (e.g. `create_calculation`, `run_calculation`):
```python
try:
    svc = get_service()  # → QMSService(get_project_root())
except ProjectNotFoundError as exc:
    return make_error("no_project", str(exc))
```

**`record_insight` and `record_intent` are completely project-UNAWARE**:
- No import of `get_project_root`
- No call to `get_service()`
- Write directly to global journal (no project path)
- Write to global knowledge DB (no project path)

To write to per-project provenance, these tools would need to:
1. Import `get_project_root()`
2. Handle `ProjectNotFoundError` gracefully
3. Call `record_operation_event(project_root=..., opctx=..., ...)`

#### 14.1.5 Provenance Schema — What's Available

The existing `operations` table can store agent intents and insights via
`OperationType.CUSTOM` with structured payloads:

```python
opctx = OperationContext(
    op=OperationType.CUSTOM,
    actor=ActorType.AGENT,
    scope=ScopeType.PROJECT,
    source="record_insight",
    payload={
        "type": "insight",
        "grade": "finding",
        "content": "...",
        "reasoning": "...",
        # ... all insight fields
    },
)
record_operation_event(project_root, opctx, ...)
```

No schema migration needed. The `payload` column is JSON text and accepts
arbitrary structured data.

#### 14.1.6 Journal Module Dependencies

```
core/journal.py (370 lines)
├── Exported: Journal, JournalEntry, get_journal, set_journal, reset_journal,
│             infer_doc_type, extract_target_ulid, generate_summary
├── Used by: yaml_io.py, record_insight.py, record_intent.py
├── Read by: daemon/server.py (2 RPC handlers)
├── Tested: tests/unit/test_journal.py, tests/unit/test_workflow.py,
│           tests/mcp/test_knowledge_write.py
└── Design doc: docs/design/journal_design.md
```

### 14.2 Gap Analysis

#### A1: Architecture — Journal to Provenance

| What Exists | What Needs to Change | Files | Blast Radius |
|-------------|---------------------|-------|-------------|
| `record_insight.py:127-153` writes to global journal | Replace with `record_operation_event()` call to per-project provenance | `record_insight.py` | Tests that check `journal.list_entries()` after insight recording |
| `record_intent.py:56-71` writes to global journal | Replace with `record_operation_event()` call to per-project provenance | `record_intent.py` | Tests that check `journal.list_entries()` after intent recording |
| `yaml_io.py:211-239` dual-writes journal+provenance | Remove journal write (provenance already recorded at lines 241-270) | `yaml_io.py` | Tests that verify journal entries after YAML saves; daemon RPC endpoints |
| `daemon/server.py:4717-4767` reads journal | Replace with provenance queries (`query_operations()`) | `daemon/server.py` | GUI timeline/history views |
| `record_insight.py` has no project context | Add `get_project_root()` import, handle `ProjectNotFoundError` gracefully | `record_insight.py` | New failure mode: outside project → provenance write skipped (non-fatal) |
| `record_intent.py` has no project context | Same as above | `record_intent.py` | Same as above |
| Response includes `journal_entry_ulid`, `journal_recorded` | Replace with `provenance_recorded` | `record_insight.py` | Consumer expectations in agent prompts, tests |

**Key decision**: Should L1/L2 insights (which are NOT promoted to knowledge DB) be silently
dropped when called outside a project? Currently they go to global journal. In the new
architecture they'd go to project provenance — but if there's no project, there's nowhere
to write them. Options:
- (a) Return error: "Cannot record L1/L2 insights outside a project"
- (b) Silently skip provenance write, return success with `provenance_recorded: false`
- (c) Fall back to global journal as last resort

Recommend **(b)** for consistency with Law P7 (graceful degradation).

#### R1: Sliding Window Nudge

| What Exists | What Needs to Change | Files |
|-------------|---------------------|-------|
| `store.py:408-415` `_count_by_grade()` — global COUNT by grade | Add `_count_pending()` method with sliding-window SQL | `store.py` |
| `store.py:417-443` `_maybe_nudge()` — uses global counts, `%8` modulus | Rewrite to use pending counts, remove modulus | `store.py` |
| `search_knowledge.py:86-101` context note — uses `_count_by_grade()` | Change to `_count_pending()` | `search_knowledge.py` |

#### R2: Simultaneous L3→L4 + L4→L5 Nudge

| What Exists | What Needs to Change | Files |
|-------------|---------------------|-------|
| `_maybe_nudge()` returns `str | None` (first-match-wins) | Return `list[str]` (both can fire) | `store.py` |
| `record_insight.py:229-237` appends single nudge to hint | Join list of nudges | `record_insight.py` |

#### R3: Soft/Strong Nudge Tone

| What Exists | What Needs to Change | Files |
|-------------|---------------------|-------|
| `_maybe_nudge()` returns generic "Consider synthesizing..." | Two tone variants: soft (search context) and strong (record nudge) | `store.py` |
| `search_knowledge.py:90-99` uses same text as record nudge | Use soft-tone variant | `search_knowledge.py` |

#### R4: Stochastic Nudge Probability

| What Exists | What Needs to Change | Files |
|-------------|---------------------|-------|
| `_maybe_nudge()` fires deterministically when threshold met | Add `random.random() < p` gate; read `QMS_NUDGE_PROBABILITY` env var | `store.py` |

#### R5: `list_insights` Mode Parameter

| What Exists | What Needs to Change | Files |
|-------------|---------------------|-------|
| `list_insights()` has 3 params: grade, limit, compound | Add `mode: str = "pending"` param | `list_insights.py` |
| `store.list_by_grade()` does flat SELECT | Add `list_pending()` method with sliding-window SQL | `store.py` |

#### R6: `list_insights` Pending Count Header

| What Exists | What Needs to Change | Files |
|-------------|---------------------|-------|
| Context hint is static per grade | Build dynamic header with pending count and last synthesis time | `list_insights.py` |
| `store.list_by_grade()` returns `{grade, total, insights}` | `list_pending()` also returns `since` timestamp | `store.py` |

#### R7: Short IDs in Output

| What Exists | What Needs to Change | Files |
|-------------|---------------------|-------|
| `search_knowledge.py:59` `"id": r["id"]` | `"id": r["id"][:10]` | `search_knowledge.py` |
| `list_insights.py` item `"id"` | Same truncation | `list_insights.py` |
| `record_insight.py` response `insight_id` | Truncate in response data | `record_insight.py` |
| `_maybe_nudge()` messages — no IDs currently | No change needed (nudge doesn't embed IDs) | — |

#### R8: Short ID Prefix Resolution

| What Exists | What Needs to Change | Files |
|-------------|---------------------|-------|
| `record_insight.py` uses raw reference/citation IDs | Call `store.resolve_short_id()` on each | `record_insight.py` |
| `store.py` has no prefix resolution | Add `resolve_short_id()` method | `store.py` |
| `store.get_by_id()` does exact match | Keep exact match; resolution is a separate method | `store.py` |

#### R9: `list_insights` No Truncation

| What Exists | What Needs to Change | Files |
|-------------|---------------------|-------|
| `list_insights.py` truncates content to 300 chars | Remove truncation (return full `content`) | `list_insights.py` |

#### R10: Preamble Search-Before-Calculate

| What Exists | What Needs to Change | Files |
|-------------|---------------------|-------|
| `app.py:14-38` `_MCP_INSTRUCTIONS` | Append search-before-calculate paragraph | `app.py` |

### 14.3 Estimated Effort

| Change | Size | Lines Changed (est.) | Test Changes |
|--------|------|---------------------|-------------|
| R9 | S | ~3 | ~2 assertions |
| R10 | S | ~5 | ~1 assertion |
| R7 | M | ~15 (3 files) | ~10 assertions |
| R8 | S | ~30 (store method + record_insight wiring) | ~5 new tests |
| R1 | M | ~40 (new _count_pending method, rewrite _maybe_nudge) | ~8 new tests |
| R2 | S | ~15 (return type change + join in record_insight) | ~3 new tests |
| R3 | S | ~20 (two message templates) | ~4 assertion updates |
| R4 | S | ~10 (random gate + env var read) | ~3 new tests |
| R5 | M | ~50 (new store method + tool param + SQL) | ~6 new tests |
| R6 | S | ~15 (header string construction) | ~3 assertion updates |
| **R1-R10 total** | | **~200 lines** | **~45 test changes** |
| A1 | L | ~150 (tool rewrites + daemon + yaml_io) | ~30 test changes |

### 14.4 Risk Assessment

#### R1-R10 (MCP Refinements)

**Low risk**. All changes are within the MCP knowledge system boundary:
- `store.py` — internal methods, no external consumers
- `search_knowledge.py`, `list_insights.py`, `record_insight.py` — tool layer
- `app.py` — preamble text only

**What could go wrong**:
- R1 sliding window SQL: edge case when no higher-grade synthesis exists (COALESCE handles this)
- R8 prefix resolution: collision on short prefixes (mitigated by error on ambiguity)
- R4 stochastic nudge: non-deterministic test failures (mock `random.random` in tests)

**Existing test coverage**: `tests/mcp/test_knowledge_write.py` has comprehensive
test classes for all knowledge features (TestBuiltinToggle, TestReservedSlots,
TestPatternGrade, TestMetadata, TestListInsights, TestNudge, TestSearchContext,
TestCitations, TestFullSynthesisFlow). All R1-R10 changes can be tested by
extending these existing classes.

#### A1 (Architecture Change)

**Medium-high risk**. Crosses multiple system boundaries:

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Daemon RPC endpoints break | High | Must replace `list_journal_entries` / `get_journal_entry` with provenance equivalents before removing journal writes |
| Project context unavailable (e.g. agent outside project) | Medium | Graceful degradation: `provenance_recorded: false` |
| Existing tests break (20+ tests check journal) | Medium | Mechanical: replace `journal.list_entries()` with provenance queries in tests |
| save_yaml_doc journal removal breaks workflow tests | Medium | 3 tests in `test_workflow.py` verify journal entries after saves |
| Provenance DB not initialized (new project, no `.provenance/`) | Low | `ensure_provenance_initialized()` is already called lazily |
| Lock ordering violations (Law P6) | Low | Knowledge tools don't hold edit.lock, so no conflict |

**Migration path for existing provenance DBs**: No schema change needed. The
existing `operations` table with `OperationType.CUSTOM` and JSON `payload`
column accommodates agent intents and insights without migration.

**Recommendation**: Implement R1-R10 first (PR-1 through PR-3). Ship and
validate in experiments. Defer A1 to a separate PR after experiments confirm
the knowledge system works correctly. The journal redundancy is a code smell,
not a correctness bug — it doesn't affect experiment results.
