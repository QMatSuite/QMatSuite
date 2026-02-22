# MCP Stage 4: Knowledge Infrastructure — Worklog

## Summary

Stage 4 adds the knowledge infrastructure: SQLite schema with FTS5 full-text
search, a curated `builtin.db` with 20 DFT best-practice entries, and the
`search_knowledge` MCP tool. After this, the agent has expert-level domain
expertise from the first session.

## Tools Implemented

| Tool | File | Purpose |
|------|------|---------|
| `search_knowledge` | `src/qmatsuite/mcp/tools/search_knowledge.py` | FTS5 search over curated DFT knowledge |

## Key Design Decisions

1. **DB location**: Lazy-generated at `<qmatsuite_home>/knowledge/builtin.db` via `core/paths.py:get_qmatsuite_home_root()`.
2. **Package scoping**: All knowledge code under `src/qmatsuite/mcp/knowledge/` (MCP-scoped, not kernel).
3. **Deterministic ULIDs**: SHA256-based with salt `"qmatsuite-knowledge-builtin-v1"` — same entry list always produces identical IDs.
4. **FTS5 + triggers**: Virtual table `insights_fts` kept in sync with `insights` via INSERT/UPDATE/DELETE triggers.
5. **Ranking**: `confidence_weight × abs(bm25_rank)`, with grade as tiebreaker (principles above findings).
6. **Content truncation**: 300 chars in list view; full content via `get_by_id`.
7. **Lazy initialization**: `search_knowledge` tool auto-builds `builtin.db` on first use if empty.
8. **Schema from design doc**: Columns match `docs/design/AGENT_INTEGRATION_DESIGN.md` Section 7.4 verbatim.

## Builtin Entries (20 curated)

| Category | Count | Tags |
|----------|-------|------|
| Error recovery | 5 | `error_recovery`, `scf`, `convergence`, `mixing`, `forces` |
| Smearing/occupations | 3 | `smearing`, `metal`, `semiconductor`, `occupations` |
| Convergence guidance | 4 | `convergence`, `ecutwfc`, `encut`, `kpoints`, `threshold` |
| Workflow-specific | 4 | `workflow`, `bands`, `dos`, `relax`, `phonon` |
| Method-specific | 4 | `method`, `dft+u`, `hse`, `gw`, `spin` |

Coverage: multi-engine (wildcard `*` + QE-specific), multi-workflow (scf, relax, bands, dos, phonon), multi-system-type (metal, semiconductor, magnetic).

## Files Created (7)

- `src/qmatsuite/mcp/knowledge/__init__.py`
- `src/qmatsuite/mcp/knowledge/schema.py` — `SCHEMA_DDL` + `init_db()`
- `src/qmatsuite/mcp/knowledge/store.py` — `KnowledgeStore` (search, get_by_id, count)
- `src/qmatsuite/mcp/knowledge/builtin_entries.py` — 20 curated entries
- `src/qmatsuite/mcp/knowledge/build_builtin.py` — idempotent builder
- `src/qmatsuite/mcp/tools/search_knowledge.py` — MCP tool
- `tests/mcp/test_stage4.py` — 20 tests

## Files Modified (1)

- `src/qmatsuite/mcp/server.py` — Stage 4 import for `search_knowledge`

## Schema

```sql
-- insights table: 22 columns (id, grade, 4 scope cols, scope_extra,
-- content, confidence, source_type, source_pack_id, source_origin,
-- provenance_ref, created_by, tags, status, superseded_by,
-- deprecated_reason, merged_into, upvotes, created_at, updated_at)
-- FTS5 virtual table: insights_fts(content, tags, scope_engine, scope_system_type)
-- 5 indexes: grade, scope (4-col composite), source_type, status, confidence
-- 3 triggers: AI (after insert), AD (after delete), AU (after update)
```

## Pattern Reuse

| Pattern | Source |
|---------|--------|
| Deterministic ULID | `demo_store/ulid_seed.py` (SHA256 → Crockford Base32) |
| SQLite schema DDL | `provenance/schema.py` (`executescript()`) |
| `row_factory = sqlite3.Row` | `provenance/db.py` |
| `@mcp.tool` + `make_response` | All Stage 0-3 tools |
| DB path via `get_qmatsuite_home_root()` | `core/paths.py` |

## Test Results

- **Stage 4 tests**: 20 passed (2 schema + 6 builtin + 8 search + 4 MCP tool)
- **All MCP tests**: 64 passed (stages 0-4)
- **Full suite**: 5724 passed, 0 failed, 4 skipped

## MCP Tool Count

- Stage 0: 1 tool (ping)
- Stage 1: 4 tools (list_engines, list_workflows, get_presets, search_parameters)
- Stage 2: 5 tools (create_calculation, set_parameters, apply_preset, inspect_calculation, preview_compilation)
- Stage 3: 4 tools (run_calculation, get_status, get_results_summary, quick_run)
- Stage 4: 1 tool (search_knowledge)
- **Total: 15 tools**
