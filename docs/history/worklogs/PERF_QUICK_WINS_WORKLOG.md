# Performance Quick Wins — Worklog

Started: 2026-02-24

## Context

Full performance audit (`docs/PERFORMANCE_AUDIT_2026-02-24.md`) identified 33 findings.
This worklog tracks implementation of safe quick wins: request-scoped optimizations,
lazy initialization, pure function caching, and targeted Electron/frontend fixes.

## Cache & Staleness Analysis

**Critical discovery**: Only 4 of ~16 mutation handlers call `invalidate_cache()`.
The missing 12 include: `rename_structure`, `delete_structure`, `rename_calculation`,
`update_step_params`, `apply_presets_to_step`, `add_step`, `delete_step`,
`change_calculation_structure`, `set_common_card`, `set_pseudo_mapping`,
`reset_step_params`, `update_calculation_species_map`.

This means cross-request caching is **unsafe**. All optimizations in this PR are
request-scoped or pure-function caching only.

## Changes Made

### Phase 0: Documentation
- [x] Created this worklog
- [x] Added performance deferred items to `docs/plans/DEFERRED_ITEMS.md`

### Phase 1: Benchmark Harness
- [x] `tests/benchmarks/create_bench_project.py` — creates 50-calc project
- [x] `tests/benchmarks/bench_rpc_performance.py` — benchmark runner

### Phase 2: Backend Fixes
- [x] F017: Lazy `__getattr__` imports in `src/qmatsuite/__init__.py`
- [x] F016: Lazy ULID generator in `src/qmatsuite/core/resources.py`
- [x] F001+F002: Request-scoped index sharing in `src/qmatsuite/api/service.py`
- [x] F006: Batch step loading in `get_detail()`
- [x] F014: `@lru_cache` on preset compiler pure functions
- [x] F018: %-style lazy logging in executor, input_runner, relax_artifacts

### Phase 3: Electron Main Process Fixes
- [x] F004: LogBuffer class replacing sync appendToLogFile
- [x] F008: Daemon `__ready__` handshake (Python + Electron)
- [x] F029: Conditional console.log behind `!app.isPackaged`
- [x] F032: Async readLogFile

### Phase 4: Frontend Quick Fixes
- [x] F026: Debounced parameter editor input (300ms)
- [x] F028: Removed redundant 5s polling interval

### Phase 5: Verification
- [ ] Baseline benchmark
- [ ] After benchmark
- [ ] Full test suite pass
