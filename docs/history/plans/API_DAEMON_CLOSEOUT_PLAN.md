# API & Daemon Closeout — Execution Plan

**Date:** 2026-02-16
**Review:** `docs/history/reviews/api_daemon_closeout_review.md`
**Worklog:** `docs/history/worklogs/api_daemon_closeout_worklog.md`

## Context

The comprehensive API/daemon review identified 8 actionable items remaining after the slimdown (Wave 1-3) and compat phaseout. This plan executes the safe, high-value items that reduce dead code, fix bugs, and improve architectural cleanliness.

## Milestones

### M1: Delete duplicate handler definitions in daemon
**Effort: S | Risk: Low**

The daemon has 3 pairs of duplicate method definitions where the first (simpler) version is shadowed by the second (canonical) version. Plus a duplicate dispatch dict key.

**Files:** `src/qmatsuite/daemon/server.py`

**Changes:**
1. Delete first `_handle_detect_workflow` definition (simple stub, shadowed by canonical version)
2. Delete first `_handle_list_wannier_3d_fixtures` definition (simple stub, shadowed by canonical version)
3. Delete first `_handle_compile_fixture_volume` definition (simple stub, shadowed by canonical version)
4. Remove duplicate `"detect_workflow"` key in the dispatch dict (keep the later one)

### M2: Delete svc.engine sub-object (dead code)
**Effort: S | Risk: Low**

`svc.engine` (4 methods) is never called by daemon, CLI, or any other code. Delete it.

**Files:**
- `src/qmatsuite/api/service.py` — delete Engine inner class and `engine` property
- `tests/api/test_engine_capabilities.py` — delete (tests only dead code)

### M3: Delete QE metadata re-exports from api.utils
**Effort: S-M | Risk: Low**

11 QE-specific symbols re-exported from `api.utils`. Remove them, add local imports where needed.

**Files:**
- `src/qmatsuite/api/utils.py` — remove re-export block, add local imports in `_qe_parameter_metadata()`
- `src/qmatsuite/cli/main.py` — rewrite `inspect_metadata` to use engine-agnostic path

### M4: Move Wannier 3D fixture scanning to API
**Effort: M | Risk: Low**

Move filesystem scanning logic from daemon handlers to API `svc.analysis`.

**Files:**
- `src/qmatsuite/api/service.py` — add `list_3d_fixtures()` and `compile_fixture_volume()` to Analysis
- `src/qmatsuite/daemon/server.py` — thin out both handlers

### M5: Enrich create_demo_project return value
**Effort: S | Risk: Low**

Move GUI enrichment from daemon into `QMSService.create_demo_project()`.

**Files:**
- `src/qmatsuite/api/service.py` — enrich return value
- `src/qmatsuite/daemon/server.py` — simplify handler

### M6: Add detail parameter to svc.calculation.list()
**Effort: S | Risk: Low**

Eliminate N+1 `get_detail()` loop in daemon.

**Files:**
- `src/qmatsuite/api/service.py` — add `detail: bool = False` to `Calculation.list()`
- `src/qmatsuite/daemon/server.py` — simplify handler

### M7: Make resolution helpers internal-only
**Effort: M | Risk: Low**

**UPDATE: SKIPPED per review reassessment.** The review document (section W4-2) concluded these methods ARE legitimate public API that Jupyter users need. They cannot be made private.

### Skipped (documented)
- **Simplify _handle_run_calculation** — Medium risk, touches job submission pipeline
- **CLI YAML reads** — Large effort (16 call sites)
- **Auto registry rebuild** — High risk relative to benefit

## Expected Metrics After All Milestones

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| svc.engine methods | 4 | 0 | -4 |
| api.utils public items | 72 | 61 | -11 |
| Daemon duplicate handlers | 4 | 0 | -4 |
| Daemon duplicate dispatch keys | 1 | 0 | -1 |
| Daemon business logic leaks | 3 | 1 (run_calculation) | -2 |

## Execution Rules

- Full pytest after every milestone
- Git commit after every green milestone
- Worklog updated per milestone
- If a change breaks tests unexpectedly, skip it and document
