# MCP Phase 1 — Deferred Items

Collected from `docs/history/worklogs/MCP_STAGE*` worklogs during Stage 11 QA audit.

---

## High Severity

### P1: Law P2 opctx gap (systemic migration)
- **Source**: MCP_STAGE10B_PROVENANCE_AUDIT.md
- `save_calculation()`, `save_project()`, `materialize_project_from_snapshot()`, `load_demo_as_calculation()` all skip opctx
- The `opctx` parameter is currently optional (migration mode); Law P2 enforcement deferred until all callers updated
- **Fix**: Systemic migration — update all callers to provide OperationContext

---

## Medium Severity

### Parser auto-registration chain missing for 6 engines
- **Source**: Engine integration audit
- QE, VASP, ORCA, ABINIT, CP2K, W90 output parsers are not auto-discovered via registry chain
- Currently works via direct import in tool code (e.g. `QEOutputParser()`)
- **Fix**: Wire parser registration into DriverRegistry so get_results_summary can be engine-agnostic

### CP2K recipes.py circular import
- **Source**: MCP_STAGE8_WORKLOG.md, CP2K Phase B1
- recipes.py imports from drivers/<engine>/recipe.py which imports back
- Systemic issue affecting all engines; 1 xfailed test
- **Fix**: Decouple recipe registration from module-level imports

### Remaining engine preflight checkers
- **Source**: MCP_STAGE5_WORKLOG.md
- Only QE has a full preflight checker (20 rules)
- VASP, ABINIT, ORCA, Gaussian, LAMMPS, CP2K — Phase 2
- **Fix**: Implement per-engine preflight checkers following QE pattern

---

## Low Severity

### Binary detection for `installed` field
- **Source**: MCP_STAGE1_WORKLOG.md (line 55, 133)
- `list_engines` always reports `installed: True`; `installed_only` parameter is a no-op
- Real binary detection deferred
- **Fix**: Implement PATH/config-based engine binary detection

### Search index serialization caching
- **Source**: MCP_STAGE1_WORKLOG.md (line 137)
- ~1000 documents from 11 engines; BM25 index rebuilt on every server start
- Not a performance concern at current scale
- **Fix**: Serialize index to disk, invalidate on metadata changes

### Preset value normalization for agent-friendly enum names
- **Source**: MCP_STAGE2_WORKLOG.md (line 99-100)
- Preset values use enum values (e.g. `collinear_lsda`), not profile names (e.g. `COL`)
- **Fix**: Add normalization layer in MCP tools for agent-friendly names

### inspect_calculation dry_run materialization
- **Source**: MCP_STAGE2_WORKLOG.md (line 95)
- Deferred from Stage 2, implemented in Stage 5
- **Status**: DONE (no longer deferred)

### PrecisionAdvisor in preview_compilation
- **Source**: MCP_STAGE2_WORKLOG.md (line 96)
- Requires structure access for precision recommendations
- **Fix**: Wire structure into preview_compilation for adaptive precision advice

---

## Demo Store Audit Additions

### D1: Corpus-level subtitle/difficulty validation gate
- **Source**: WORKLOG_DEMO_AUDIT.md
- **Priority**: Low
- Add a gate test that verifies every `demo_eligible: true` case.yaml has non-empty `subtitle` and `difficulty` fields
- Prevents regression when new demos are added

### D2: Text-search upgrade for search_demos
- **Source**: WORKLOG_DEMO_AUDIT.md
- **Priority**: Medium
- Current text search is substring-only. Consider BM25 or fuzzy matching for better recall (e.g. "iron" matching "Fe" demos)

### D3: Demo runtime benchmarking
- **Source**: WORKLOG_DEMO_AUDIT.md
- **Priority**: Low
- `estimated_runtime_s` values are manual estimates. A CI job could run each demo on a reference machine and record actual runtimes

### D4: Ref pack staleness detection
- **Source**: WORKLOG_DEMO_AUDIT.md
- **Priority**: Medium
- If demo input parameters change but ref pack isn't regenerated, results become stale. Add manifest checksum comparison to warn
