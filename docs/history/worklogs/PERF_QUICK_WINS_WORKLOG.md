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

---

## Phase 0: Documentation
- [x] Created this worklog
- [x] Added performance deferred items (P1, P2, P3) to `docs/plans/DEFERRED_ITEMS.md`

## Phase 1: Benchmark Harness
- [x] `tests/benchmarks/create_bench_project.py` — creates 50-calc benchmark project
- [x] `tests/benchmarks/bench_rpc_performance.py` — benchmark runner with 6 benchmarks
- [x] `tests/benchmarks/__init__.py` + `tests/benchmarks/results/` directory

## Phase 2: Backend Fixes

### F017: Lazy `__getattr__` imports — REVERTED (circular import issue)

**Attempted**: Replaced eager imports in `src/qmatsuite/__init__.py` with `__getattr__`
lazy loading for `Project`, `ProjectSettings`, `StructureRef`, `CalculationRef`,
`Calculation`, `CalculationRunner`. Kept `from .api import QMSService` eager.

**Problem**: This broke CLI subprocess tests (`tests/cli/test_history_commands.py`,
`test_cli_metadata_isolation.py`, etc.) with a circular import error:

```
qmatsuite.cli.main -> api.qe_io -> io.__init__ -> drivers.qe -> core.driver_registry
 -> workflow.step_type_convert -> workflow.__init__ -> workflow.step_factory
 -> core.public -> core.driver_registry (CIRCULAR!)
```

**Root cause**: The original import order in `__init__.py` matters critically. Lines 44-46
imported `.project.model`, `.calculation.calculation`, `.calculation.runner` BEFORE `.api`.
These imports pre-populate `sys.modules` with modules that appear in the circular chain
(e.g., `qmatsuite.core.public` gets loaded as a side-effect of `.calculation.runner`),
which breaks the circular dependency by having the module already partially loaded.

When we made these lazy, `.api` was imported first (as the only remaining eager import),
triggering the circular chain through a different path where `driver_registry` hadn't
finished loading yet.

**Resolution**: Reverted to eager imports. Added comment documenting why import order
matters. The lazy import optimization is not worth the fragility risk given the deep
circular import chain in the codebase.

**IMPORTANT FOR FUTURE**: The circular import chain is:
`driver_registry -> workflow -> step_factory -> core.public -> driver_registry`
This is a known systemic issue (see DEFERRED_ITEMS.md M7). Any future attempt to
lazy-load modules in `__init__.py` MUST verify CLI subprocess tests pass, since they
exercise a different import order than in-process tests.

### F016: Lazy ULID generator — DONE
- `src/qmatsuite/core/resources.py`: Replaced module-level `_MonotonicUlidGenerator()`
  with lazy `_get_generator()` that creates on first use.

### F001+F002: Request-scoped index sharing — DONE (highest impact)
- `src/qmatsuite/api/service.py`:
  - New `_get_detail_with_shared_context()` accepts pre-built `index`, `config`, `resolver`
  - `get_detail()` delegates to the new method after building context once
  - `list(detail=True)` builds shared context ONCE before the loop, then passes it
    to `_get_detail_with_shared_context()` for each calculation
  - Previously: N calculations × 1 `build_resource_index()` = N full directory walks
  - Now: 1 `build_resource_index()` + N dict lookups

### F006: Batch step loading — DONE
- Inside `_get_detail_with_shared_context()`: pre-reads all `*.step.yaml` files from
  the `steps/` directory in one glob pass, builds `step_specs_by_ulid` dict.
- Loop lookups are O(1) dict access instead of per-step `from_yaml()` calls.

### F014: Preset compilation caching — SKIPPED (user safety concern)
- Originally planned `@lru_cache` on `compile_magnetism()` and `compile_occupations_scheme()`
- **Reverted** per user instruction: preset system is extremely delicate and the
  returned dicts could theoretically be mutated by callers, corrupting the cache.
- The performance gain is minimal compared to F001+F002.
- Deferred to future work with proper mutation-safety analysis.

### F018: Lazy logging — DONE
- `src/qmatsuite/execution/executor.py`: 14 f-string logs → %-style
- `src/qmatsuite/calculation/input_runner.py`: 8 f-string logs → %-style
- `src/qmatsuite/execution/relax_artifacts.py`: 8 f-string logs → %-style

## Phase 3: Electron Main Process Fixes

### F004: LogBuffer class — DONE
- `gui/electron/main.ts`: Replaced sync `appendToLogFile()` with `LogBuffer` class
- Batches up to 500 lines, flushes every 500ms or on threshold
- `flushSync()` called on `before-quit` for clean shutdown
- Uses `fs.appendFile()` (async, fire-and-forget) instead of `fs.appendFileSync()`

### F008: Daemon readiness handshake — DONE
- **Python side** (`src/qmatsuite/daemon/server.py`): Emits `__ready__` JSON-RPC
  notification on stdout immediately after startup log, before the request loop.
- **Electron side** (`gui/electron/main.ts`): `handleDaemonLine()` detects the
  `__ready__` notification, sets `daemonStatus.connected = true`, and notifies renderer.
- **Test fix**: Updated `tests/unit/test_daemon.py` — two tests counted stdout lines.
  Both `test_processes_multiple_requests` and `test_shutdown_command_stops_loop` now
  account for the extra `__ready__` line (3 instead of 2).

### F029: Conditional console logging — DONE
- `gui/electron/main.ts`: IPC request/response logs wrapped with `if (!app.isPackaged)`

### F032: Async readLogFile — DONE
- `gui/electron/main.ts`: Converted to `async function` using `fs.promises.access` +
  `fs.promises.readFile`. IPC handler already uses `ipcMain.handle` (async-safe).

## Phase 4: Frontend Quick Fixes

### F026: Debounce parameter editor — DONE
- `gui/src/components/step_parameters/ParameterValueEditor.tsx`:
  - Added `localInputValue` state + `debouncedChange` ref
  - 300ms debounce on text input changes
  - Flush on blur to ensure no lost edits
  - Cleanup on unmount

### F028: Remove redundant polling — DONE
- `gui/src/hooks/useQMSClient.ts`: Removed 5-second `setInterval` polling.
  Event-driven `onDaemonStatus` subscription (lines 220-235) already handles
  ongoing status updates.

## Phase 5: Verification

- [x] Full test suite: **6535 passed, 0 failed, 4 skipped** (411s)
- [x] CLI subprocess tests pass (previously broken by lazy import attempt)
- [x] Daemon tests pass (updated for `__ready__` notification)
- [x] Benchmark run completed (50-calc project, 3 runs per benchmark)

## Benchmark Results

### Setup
- 50-calculation project created from 50 of 52 available demo projects (single cycle)
- Each benchmark: 3 runs, median reported
- Machine: MacBook Pro (Darwin 25.2.0)

### Results Table

| Benchmark | Before Fix¹ | After Fix² | Change |
|-----------|------------|------------|--------|
| Import time | 0.272s | 0.261s | -4% |
| `list(detail=False)` (50 calcs) | 43.06s | 43.40s | ~baseline |
| `list(detail=True)` (50 calcs) | 60.08s | **49.36s** | **-17.8%** |
| `get_detail()` (single calc) | 0.445s | **0.226s** | **-49.3%** |
| `build_resource_index()` | 0.110s | 0.106s | ~baseline |
| Preset compilation 100x | 0.0001s | 0.0002s | negligible |

¹ Before = after F001+F002 (shared context) but BEFORE passing `index=` to `require_calculation()`/`resolve_structure()`
² After = with `index=` properly passed through, eliminating redundant `build_resource_index()` calls

### Analysis

**What improved:**
- `get_detail()` single call: **-49%** (0.445s → 0.226s). The fix was passing the
  shared `index` to `require_calculation()` and `resolve_structure()`, which each
  previously called `build_resource_index()` internally (~110ms each).
- `list(detail=True)`: **-17.8%** (60.08s → 49.36s). The overhead of detail-fetching
  over the no-detail baseline dropped from ~17s to ~6s (65% reduction in incremental cost).

**What didn't improve (and why):**
- `list(detail=False)` = 43.4s for 50 calcs (~0.87s per calc). This is the **dominant
  baseline cost** and is caused by pervasive `build_resource_index()` calls from deep
  kernel layers: `Project.open()`, `load_calculation()`, `Calculation.from_yaml()` all
  call it internally. Each call walks the entire project directory tree (~110ms).
- This is **deferred item P2** in `docs/plans/DEFERRED_ITEMS.md`. Fixing it requires
  kernel-level changes to accept an optional `index` parameter throughout the call chain,
  which is a much larger refactor.

**Why `list_detail` exceeds 2s target:**
- The 2s target assumed ~40ms per `get_detail()` call (50 × 0.04s = 2s). Actual
  `get_detail()` is 226ms due to the 43s baseline overhead from kernel-layer
  `build_resource_index()` calls that our request-scoped sharing cannot reach.
- The incremental detail cost (list_detail - list_no_detail) IS fast: ~6s for 50 calcs
  = ~120ms per calc detail-fetch, which is reasonable.
- True fix requires P2 (kernel-level index threading) which is out of scope for quick wins.

### Bug Fixes During Benchmarking
1. `create_bench_project.py`: Used `d["name"]` (human title) instead of `d["ulid"]`
   (machine ID) for demo IDs → fixed to `d["ulid"]`
2. `bench_rpc_performance.py`: Called `compile_magnetism.cache_clear()` but `@lru_cache`
   was reverted → removed cache_clear calls
3. `_get_detail_with_shared_context()`: Missing `index=index` on `require_calculation()`
   and `resolve_structure()` calls → fixed, yielding the 49% get_detail improvement
4. Added `tests/benchmarks/conftest.py` to prevent pytest from collecting benchmark scripts

---

## Phase 6: Deep Investigation — list_calculations 43s Bottleneck

**Full report**: `docs/history/reviews/LIST_PERFORMANCE_INVESTIGATION.md`

### Summary

Profiled `list(detail=False)` on the 50-calc benchmark project. Found that **96.2% of the 42.2s** is spent in `build_resource_index()`, called **389 times** instead of once:

| Call Site | Calls | Est. Time |
|-----------|------:|----------:|
| `resolve_calculation()` (from `_build_step_inspection`) | 170 | ~17.7s |
| `resolve_step()` (from `_build_step_inspection`) | 170 | ~17.7s |
| `resolve_structure()` (from `load_calculation`) | 47 | ~4.9s |
| `Project.open` (`_load_structures` + `_load_calculations`) | 2 | ~0.2s |

**Root cause**: `_build_step_inspection()` calls `require_step()` for each of 85 steps. `require_step` → `resolve_step` → `resolve_calculation`, each calling `build_resource_index()` because no `index=` is passed. Each call scans ~135 YAML files via PyYAML's slow pure-Python parser.

**The fix**: Build `ResourceIndex` once at the top of `service.list()` and thread it through `load_calculation()`, `Calculation.from_yaml()`, and `_build_step_inspection()`. All these functions' downstream callees already accept an `index=` parameter — it's just never passed from above.

**Expected result**: Dropping from 389 to 1 `build_resource_index` call would bring `list(detail=False)` from **42s → ~1.5s**.

### Diagnostic Scripts Added

- `tests/benchmarks/profile_list_calcs.py` — cProfile, manual timing, I/O counting, scaling tests
- `tests/benchmarks/results/profile_list_calcs.json` — raw profiling data

---

## Phase 7: S4 — Index Threading Through Shallow Path

### Changes Made

Built `ResourceIndex` once at the top of `service.list()` and threaded it through the
entire call chain. Added `index=None` parameter (with backward-compatible default) to:

- `Project.open(index=)` → `_load_structures(index=)` + `_load_calculations(index=)`
- `load_calculation(index=)` → passes to `resolve_structure(index=)`
- `Calculation.from_yaml(index=)` → `_build_step_inspection(index=)` → `require_step(index=)`
- `_get_detail_with_shared_context` → passes `index=` to `load_calculation()`

All downstream functions (`resolve_structure`, `resolve_calculation`, `resolve_step`,
`require_step`) already accepted `index=` — the change was purely about passing it from above.

### Benchmark Results

| Metric | Before S4 | After S4 | Speedup |
|--------|-----------|----------|---------|
| `list(detail=False)` 50 calcs | 43.40s | **1.73s** | **25.1x** |
| `list(detail=True)` 50 calcs | 49.36s | **2.14s** | **23.1x** |
| `get_detail(single)` | 0.226s | **0.119s** | **1.9x** |
| `build_resource_index` | 0.106s | 0.110s | baseline |
| Import time | 0.261s | 0.259s | baseline |

### build_resource_index call count

| Path | Before S4 | After S4 |
|------|-----------|----------|
| `list(detail=False)` | 389 | **1** |
| `list(detail=True)` | 389+ | **1** |
| `get_detail(single)` | 3 | **1** |

### Verification

- Full test suite: **6535 passed, 0 failed, 4 skipped** (405s)
- Benchmark data: `tests/benchmarks/results/after-s4.json`
- All changes request-scoped (index is local variable, born and dies within RPC call)
- Backward compatible (all new `index=` params default to `None`, build internally if not provided)
- DTO shape unchanged (frontend sees no difference)

---

## Files Modified

| File | Finding | Change |
|------|---------|--------|
| `src/qmatsuite/__init__.py` | F017 | Kept eager imports (lazy reverted), added import order comment |
| `src/qmatsuite/core/resources.py` | F016 | Lazy ULID generator |
| `src/qmatsuite/api/service.py` | F001+F002+F006+S4 | Request-scoped sharing + batch step loading + index threading |
| `src/qmatsuite/core/models.py` | S4 | Added `index=` param to `load_calculation()` |
| `src/qmatsuite/project/model.py` | S4 | Added `index=` param to `open()`, `_load_structures()`, `_load_calculations()` |
| `src/qmatsuite/calculation/calculation.py` | S4 | Added `index=` param to `from_yaml()`, `_build_step_inspection()` |
| `src/qmatsuite/execution/executor.py` | F018 | %-style logging (14 lines) |
| `src/qmatsuite/calculation/input_runner.py` | F018 | %-style logging (8 lines) |
| `src/qmatsuite/execution/relax_artifacts.py` | F018 | %-style logging (8 lines) |
| `src/qmatsuite/daemon/server.py` | F008 | `__ready__` notification |
| `gui/electron/main.ts` | F004+F008+F029+F032 | LogBuffer, readiness, conditional log, async read |
| `gui/src/components/step_parameters/ParameterValueEditor.tsx` | F026 | Debounced input |
| `gui/src/hooks/useQMSClient.ts` | F028 | Remove polling interval |
| `tests/unit/test_daemon.py` | — | Updated for `__ready__` notification |
| `docs/plans/DEFERRED_ITEMS.md` | — | Added P1, P2, P3 deferred items |

## New Files

| File | Purpose |
|------|---------|
| `tests/benchmarks/__init__.py` | Package init |
| `tests/benchmarks/create_bench_project.py` | 50-calc benchmark project creator |
| `tests/benchmarks/bench_rpc_performance.py` | Benchmark runner |
| `tests/benchmarks/conftest.py` | Excludes benchmarks from pytest collection |
| `tests/benchmarks/profile_list_calcs.py` | Profiling script for list_calculations bottleneck |
| `tests/benchmarks/results/` | Results directory |
