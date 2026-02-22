# MCP Stage 11: Phase 1 Final Integration — Worklog

**Status**: Complete
**Date**: 2026-02-18

---

## Deferred Items Collected

See `docs/plans/DEFERRED_ITEMS.md` for the full list. Summary:

- **High**: Law P2 opctx gap (systemic migration)
- **Medium**: Parser auto-registration (6 engines), CP2K circular import, engine preflight checkers
- **Low**: Binary detection, search index caching, preset value normalization

## Context Hint Audit (22 tools)

| Tool | Hint Summary | Correct? | Fix |
|------|-------------|----------|-----|
| ping | N/A | ✅ | — |
| list_engines | → list_workflows | ✅ | — |
| list_workflows | → get_presets | ✅ | — |
| get_presets | → apply_preset | ✅ | — |
| search_parameters | → set_parameters | ✅ | — |
| create_calculation | → apply_preset/set_parameters/inspect | ✅ | Added hints to error paths |
| set_parameters | → inspect_calculation | ✅ | — |
| apply_preset | → inspect_calculation | ✅ | — |
| inspect_calculation | → set_parameters/run_calculation | ✅ | Added dry_run mention for step detail |
| preview_compilation | → set_parameters | ✅ | — |
| run_calculation | → get_results_summary | ✅ | Added promote_structure for relax |
| get_status | → run_calculation/get_results_summary | ✅ | Added promote_structure for relax completed |
| get_results_summary | → inspect_calculation | ✅ | Added promote_structure for relax + calc_ulid |
| quick_run | → get_results_summary | ✅ | Added promote_structure for relax |
| search_knowledge | → set_parameters/apply_preset | ✅ | — |
| list_structures | → create_calculation | ✅ | — |
| import_structure | → create_calculation | ✅ | — |
| get_structure_detail | → create_calculation | ✅ | — |
| promote_structure | → create_calculation | ✅ | — |
| search_demos | → get_demo_results/load_demo | ✅ | Added fallback hint for empty results |
| get_demo_results | → load_demo | ✅ | — |
| load_demo | → inspect/run_calculation | ✅ | — |

## Phase 1 Feature Completeness

| Item | Status |
|------|--------|
| 22 tools | ✅ |
| FastMCP server + stdio + .mcp.json | ✅ |
| Standard envelope with context_hint | ✅ |
| BM25 index | ✅ |
| builtin.db ≥ 35 entries (actual: 40) | ✅ |
| QE preflight ≥ 20 rules (actual: 20) | ✅ |
| Preflight in preview_compilation + inspect_calculation | ✅ |
| Error enrichment with knowledge-backed suggested_fixes | ✅ |
| load_demo as new calc in existing project | ✅ |
| demo_origin on loaded calculations | ✅ |
| Reserved schema: last_validated, contradiction_count | ✅ |
| InsightRecord dataclass | ✅ |
| Contract tests for all tools | ✅ |
| Structure relaxation provenance tracking | ✅ |
| Relax convergence validation in QE preflight | ✅ |
| import_structure, list_structures, get_structure_detail | ✅ |

## End-to-End Results

| Scenario | Result | Timing |
|----------|--------|--------|
| A: QE relax → promote → reuse (demo-based) | ✅ PASS | ~15s |
| B: Demo load → run real QE | ✅ PASS | ~10s |
| C: search → demo_results → load → inspect(dry_run) → run → results | ✅ PASS | ~12s |
| D: create → bad params → preflight warns → fix → run → converge | ✅ PASS | ~15s |
| E: knowledge-informed → create → configure → run → converge | ✅ PASS | ~12s |

## Integration Issues Found

1. **Species map required for from-scratch QE runs**: `create_calculation` alone doesn't set species_map. Demo-based tests already include it. Fix: tests use `svc.calculation.update_species_map()` for from-scratch calcs.

2. **QE params namespacing**: `set_parameters` with flat params (e.g. `{"ecutwfc": 5.0}`) doesn't namespace into `SYSTEM`. Preflight expects `SYSTEM.ecutwfc`. Fix: tests use `{"SYSTEM": {"ecutwfc": 5.0}}` for QE.

3. **asyncio event loop for tool counting**: `mcp.get_tools()` is async; test needed `asyncio.new_event_loop()` instead of deprecated `get_event_loop()`.

## Test Results

```
tests/mcp/test_stage11.py: 15 passed (6 real QE + 9 contract/correctness)
tests/mcp/ (all): 339 passed
tests/ (full suite): 5999 passed, 0 failed, 4 skipped
```

## Files Created/Modified

| File | Action |
|------|--------|
| `docs/plans/DEFERRED_ITEMS.md` | CREATE |
| `docs/history/worklogs/MCP_STAGE11_WORKLOG.md` | UPDATE |
| `src/qmatsuite/mcp/tools/run_calculation.py` | FIX: promote_structure hint for relax |
| `src/qmatsuite/mcp/tools/get_results_summary.py` | FIX: promote_structure hint + calc_ulid in hint |
| `src/qmatsuite/mcp/tools/quick_run.py` | FIX: promote_structure hint for relax |
| `src/qmatsuite/mcp/tools/get_status.py` | FIX: promote_structure hint for relax completed |
| `src/qmatsuite/mcp/tools/create_calculation.py` | FIX: context_hint on error paths |
| `src/qmatsuite/mcp/tools/demo_store.py` | FIX: empty result fallback hint |
| `src/qmatsuite/mcp/tools/inspect_calculation.py` | FIX: dry_run/preflight mention in hint |
| `tests/mcp/test_stage11.py` | CREATE: 15 tests |
