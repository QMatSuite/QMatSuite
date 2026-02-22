# Runner Cascade Fix — Worklog

## Problem Statement

The runner has a cascade bug: when an upstream step re-runs (step_sha changed), downstream steps remain `done=True` and get incorrectly skipped. Example: Si bands calc (scf -> bandspw -> bands), agent changes bandspw params, incremental re-run skips bands.x even though its input changed.

Constitution §5.3: "Run Single Step: target step must always execute. After success, conservatively marks downstream steps as `done=false`."

## Investigation Findings

Three pieces of cascade infrastructure exist but are disconnected:

1. `reconcile_manifest()` computes `first_changed_idx` but the runner discards it
2. `clear_manifest_from_step()` at `manifest.py:227-256` is dead code (never called from runner)
3. The runner's `start_idx` is assigned but never used for downstream invalidation

## Fix 7.1: Cascade pass in `reconcile_manifest()`

**File**: `src/qmatsuite/calculation/manifest_reconcile.py`

After the main for-loop builds `new_steps` and sets `first_changed_idx`, we add a cascade pass that forces all steps from `first_changed_idx` onward to `done=False`. This ensures that if step 1's SHA changes, steps 2+ are also marked for re-execution.

## Fix 7.2: Wire `clear_manifest_from_step()` for TARGET mode

**File**: `src/qmatsuite/calculation/runner.py`

In `_execute_with_jobgraph()`, after the job_results processing loop, we call `clear_manifest_from_step()` to invalidate downstream steps when running in TARGET mode. This fulfills Constitution §5.3.

## Fix 7.3: Expose `run_mode` in MCP `run_calculation`

**File**: `src/qmatsuite/mcp/tools/run_calculation.py`

Added `run_mode` parameter (default "incremental") to the MCP tool, with validation and pass-through to `svc.run.run_calculation()`.

## Tests Added

**File**: `tests/integration/test_cascade_invalidation.py`

6 tests covering cascade invalidation:
1. `test_reconcile_cascade_step1_sha_changed` — step 1 SHA changes, step 2 cascaded to done=False
2. `test_reconcile_cascade_step0_sha_changed` — step 0 SHA changes, all downstream cascaded
3. `test_reconcile_no_cascade_when_unchanged` — all SHAs match, all remain done=True
4. `test_reconcile_cascade_last_step_no_upstream_effect` — last step change doesn't affect upstream
5. `test_reconcile_cascade_single_step_calc` — single-step calc, no IndexError
6. `test_target_mode_invalidates_downstream` — TARGET mode invalidates downstream steps

**File**: `tests/mcp/test_stage_p2.py`

1 test: `test_run_calculation_accepts_run_mode` — MCP tool accepts run_mode parameter

## Results

- All new tests pass
- All existing tests pass (zero regressions)
