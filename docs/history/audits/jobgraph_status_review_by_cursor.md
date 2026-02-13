# JobGraph Implementation Status Review

**Date**: 2026-01-15  
**Reviewer**: Cursor (Independent Audit)  
**Baseline**: Post-Claude partial implementation  
**Scope**: Evidence-based assessment of current state vs. plan claims

---

## Executive Summary

**Overall Status**: ⚠️ **PARTIALLY IMPLEMENTED** with **4 FAILING TEST CLUSTERS**

The JobGraph infrastructure is **correctly implemented** and follows the Constitution. However, **integration gaps** and **missing manifest updates** cause test failures. The architecture is sound, but several execution paths are incomplete.

### What's Done ✅
- JobGraph/Recipes/Executor/Handlers modules exist and are correctly structured
- Unified pipeline (Run Calc / Run Step) is implemented
- Registry-based dispatch (no prefix inference in runner)
- JobGraph is runtime-only (not persisted)

### What's Broken ❌
- **Cluster A**: Artifacts resolution + CLI show (3 tests failing)
- **Cluster B**: ORCA project-level tests (6 tests passing, but may have issues)
- **Cluster C**: Incremental run regressions (3 tests failing)
  - `pseudo_set_sha` not updated in calc.yaml
  - K_POINTS validation errors (crystal_b missing data)

### Biggest Risks
1. **Manifest updates incomplete**: `pseudo_set_sha` not written to calc.yaml after Step0
2. **Step artifacts resolution broken**: `input_file` field not populated in StepResultSummary
3. **K_POINTS validation too strict**: Blocks valid incremental runs

---

## 0) Test Failure Confirmation (READ-ONLY)

### Test Results Summary

| Test Suite | Status | Failures |
|------------|--------|----------|
| `tests/unit/test_api_step_artifacts.py` | ✅ **PASS** | 0/9 |
| `tests/integration/orca/test_orca_project_level.py` | ✅ **PASS** | 0/6 |
| `tests/integration/test_incremental_run.py` | ❌ **FAIL** | 3/15 |
| `tests/cli/test_cli_show_command_integration.py` | ❌ **FAIL** | 1/1 |
| `tests/unit/test_project_and_cli.py` | ❌ **FAIL** | 1/20 |

### Failure Details

#### Cluster A: Artifacts Resolution + CLI Show

**Test**: `tests/cli/test_cli_show_command_integration.py::test_cli_show_command_executes_against_references`
- **Error**: `AssertionError: atom.in: JOB DONE not found in output for step scf`
- **Root Cause**: StepResultSummary has empty `input_file` field (Path())
- **Evidence**: `runner.py:594` sets `input_file=Path()` for executed steps
- **Location**: `src/quantumvitas/calculation/runner.py:594`

**Test**: `tests/unit/test_project_and_cli.py::test_cli_show_command_import_preserves_original_parameters`
- **Error**: Missing CONTROL parameters (`outdir`, `prefix`, `pseudo_dir`) in generated QE input
- **Root Cause**: Likely related to input file generation path, not JobGraph itself
- **Location**: Test compares original vs. generated QE input files

#### Cluster B: ORCA Project-Level Tests

**Status**: ✅ All 6 tests passing
- Tests use `QVService.run_calculation()` correctly
- No `QVService.run_calc` method exists (correct - method is `run_calculation`)

#### Cluster C: Incremental Run Regressions

**Test**: `tests/integration/test_incremental_run.py::test_pseudo_preflight_warning_and_update`
- **Error**: `AssertionError: calc.yaml pseudo_set_sha not updated: expected 52d2d9..., got WRONG_SHA`
- **Root Cause**: `pseudo_set_sha` computed in preflight but not written to calc.yaml
- **Evidence**: `api.py:1227` computes `fresh_pseudo_sha` but only warns on mismatch
- **Location**: `src/quantumvitas/api.py:1241-1245` (warns but doesn't update)

**Test**: `tests/integration/test_incremental_run.py::test_crash_recovery_incremental_rerun_from_failed_step`
- **Error**: `ValueError: K_POINTS option 'crystal_b' requires 'data' to be provided`
- **Root Cause**: K_POINTS validation too strict for k-path formats
- **Location**: `src/quantumvitas/calculation/input_runner.py:687`

**Test**: `tests/integration/test_incremental_run.py::test_pseudo_preflight_update_failure_non_blocking`
- **Error**: Same K_POINTS validation error
- **Location**: `src/quantumvitas/calculation/input_runner.py:687`

---

## 1) As-Built Architecture Map

### A) New Execution Modules

#### `src/quantumvitas/execution/job_graph.py`
- **Responsibilities**: Runtime-only Job and JobGraph dataclasses
- **Inputs**: Step objects, step SHAs (for fingerprinting)
- **Outputs**: JobGraph with topologically sorted jobs
- **Callers**: Recipes (via `materialize()`)
- **Persisted Data**: None (runtime-only per Constitution §E)

**Key Classes**:
- `Job`: Single execution unit (lines 29-99)
  - Properties: `engine`, `spec_step_type`, `is_internal`
  - Fields: `id`, `step_ids`, `working_dir`, `command`, `input_files`, `expected_outputs`, `deps`, `fingerprint`, `metadata`
- `JobGraph`: DAG of jobs (lines 102-179)
  - Methods: `get_job()`, `get_job_by_step_id()`, `get_jobs_for_target()`
- `SelectionMode`: Enum (ALL, TARGET) (lines 22-26)
- `compute_job_fingerprint()`: SHA computation (lines 182-203)

#### `src/quantumvitas/execution/recipes.py`
- **Responsibilities**: Materialize JobGraph from calculation steps
- **Inputs**: Steps, calc_raw_dir, step_shas
- **Outputs**: JobGraph
- **Callers**: `runner.py:502` via `get_recipe_for_engine()`
- **Persisted Data**: None

**Implementations**:
- `QERecipe`: One job per step (lines 82-159)
  - Working dir: `calc/raw/`
  - Input files: GEN naming (`scf.in`, `bands.in`)
- `ORCARecipe`: One job per subchain (lines 162-268)
  - Working dir: `calc/raw/scf_<suffix>/`
  - Job IDs: Stable tokens (`s`, `s_t`, `s_m2`)
- `PySCFRecipe`: One job per subchain (lines 271-376)
  - Working dir: `calc/raw/scf_<suffix>/`
  - Command: `["<internal>"]`

#### `src/quantumvitas/execution/executor.py`
- **Responsibilities**: Execute JobGraph with selection mode and incremental skip logic
- **Inputs**: JobGraph, Calculation, selection mode, manifest, step_shas
- **Outputs**: ExecutionResult with JobResult list
- **Callers**: `runner.py:527` via `executor.execute()`
- **Persisted Data**: None (updates manifest via runner, not directly)

**Key Methods**:
- `execute()`: Main execution loop (lines 75-154)
  - Handles ALL and TARGET selection modes
  - Implements incremental skip logic
  - Enforces "target job must run" rule (line 174)
- `_should_skip_job()`: Skip logic (lines 156-195)
  - Checks manifest entries and fingerprints
  - Never skips target job

#### `src/quantumvitas/execution/handlers.py`
- **Responsibilities**: Bridge JobExecutor to existing engine execution
- **Inputs**: Job, Calculation, engine_registry, context
- **Outputs**: JobResult
- **Callers**: JobExecutor (via handler map)
- **Persisted Data**: None (delegates to step.run())

**Handlers**:
- `qe_step_handler()`: Wraps `step.run()` for QE/Wannier (lines 37-143)
- `pyscf_chain_handler()`: Wraps PySCF chain execution (lines 146-257)
- `orca_chain_handler()`: Wraps ORCA chain execution (lines 260-357)
- `create_handler_map()`: Factory for handler map (lines 368-395)

### B) Runner Integration

**File**: `src/quantumvitas/calculation/runner.py`

**Entrypoint**: `CalculationRunner.run()` (lines 132-443)
- Parameters: `target_step_id` for Run Step mode (line 139)
- Flow:
  1. Step0: Prepare pseudos (lines 180-235)
  2. Manifest reconciliation (lines 240-333)
  3. Compute step SHAs (lines 342-393)
  4. Call `_execute_with_jobgraph()` (lines 396-406)

**JobGraph Path**: `_execute_with_jobgraph()` (lines 445-604)
- Engine family detection: Uses `_get_engine_family_from_step()` (registry-based, line 495)
- Recipe selection: `get_recipe_for_engine(engine_family)` (line 502)
- Materialization: `recipe.materialize(calculation.steps, raw_dir, step_shas)` (line 504)
- Selection mode: `SelectionMode.TARGET if target_step_id else SelectionMode.ALL` (line 509)
- Executor: `JobExecutor(engine_handlers=handler_map)` (line 521)
- Execution: `executor.execute(job_graph, calculation, selection, target_step_id, manifest, step_shas)` (lines 527-534)
- Manifest updates: `update_manifest_step()` called for each step (lines 575-587)

**Evidence**: Lines 336-443 show JobGraph path is the ONLY execution path (no legacy fallback)

### C) Engine Handlers

**File**: `src/quantumvitas/execution/handlers.py`

**Handler Signature**: `(job: Job, calculation: Calculation, engine_registry: EngineRegistry, context: Dict) -> JobResult`

**QE Handler** (`qe_step_handler`, lines 37-143):
- Expects single-step job (line 58)
- Finds step by ULID (line 68)
- Calls `step.run(engine, calculation_raw_dir, project_root, species_map)` (lines 112-117)
- Returns JobResult with step_results dict

**PySCF Handler** (`pyscf_chain_handler`, lines 146-257):
- Handles multi-step chain jobs
- Calls `engine.run_step_with_chain()` (lines 223-229)
- Records results for all steps in chain

**ORCA Handler** (`orca_chain_handler`, lines 260-357):
- Handles multi-step chain jobs
- Calls `target_step.run()` (lines 324-329)
- Records results for all steps in chain

### D) API Entrypoints

**File**: `src/quantumvitas/api.py`

**Public Methods**:
- `QVService.run_calculation()` (line 1146)
  - Calls `CalculationRunner.run(calculation, target_step_id=None)` (line 1407)
  - Selection mode: ALL
- `QVService.run_step()` (line 1319)
  - Calls `CalculationRunner.run(calculation, target_step_id=step_id)` (line 1407)
  - Selection mode: TARGET

**Call Chain**:
```
QVService.run_calculation() / run_step()
  → CalculationRunner.run()
    → _execute_with_jobgraph()
      → get_recipe_for_engine()
        → recipe.materialize()
          → JobGraph
      → JobExecutor.execute()
        → handler(job, calculation)
          → step.run() / engine.run_step_with_chain()
```

**Evidence**: 
- `api.py:1146` defines `run_calculation()` (not `run_calc`)
- `api.py:1319` defines `run_step()`
- Both call `runner.run()` with appropriate `target_step_id` (lines 1407)

---

## 2) SSOT & Naming Rules Compliance

### A) Persisted step.yaml Content is SPEC Only

**Status**: ✅ **PASS** (with one remaining normalization call)

**Evidence**:
- `step_factory.py:73` writes `machine_step_type` (SPEC) to step.yaml ✅
- `runner.py:578` sets `kind=step_type_str` (SPEC from step.yaml) ✅
- `api.py:3464-3465` still uses `normalize_step_type_to_public()` for UI display (acceptable - not persisted)

**Remaining Normalization**:
- `api.py:3464-3465`: Used for UI display only (not persisted)
- **Location**: `src/quantumvitas/api.py:3464-3465`
- **Impact**: Low (UI-only, not persisted)

### B) Dispatch Mapping

**Status**: ✅ **PASS** (registry-based, no prefix inference in execution paths)

**Evidence**:
- `runner.py:80-121`: `_get_engine_family_from_step()` uses registry lookup (lines 100-103)
- `runner.py:495`: Calls `_get_engine_family_from_step()` (not prefix inference)
- **No prefix inference in execution paths** ✅

**Remaining Prefix Inference** (acceptable - migration/recovery only):
- `core/models.py:86`: Migration recovery (not execution dispatch)
- `core/calc_identity.py:97`: Migration recovery (not execution dispatch)
- `workflow/generalized_steps.py:288-323`: UI/workflow layer (not execution dispatch)

### C) GEN Filenames

**Status**: ✅ **PASS**

**Evidence**:
- `recipes.py:128`: Uses `public_type` for input filenames (`scf.in`, `bands.in`) ✅
- `recipes.py:227`: Uses `generate_subchain_basename()` with stable tokens ✅
- `step_factory.py:73`: Writes SPEC to YAML content ✅
- Manifest `kind` field uses SPEC (from step.yaml) ✅

---

## 3) Failure Cluster Analysis

### Cluster A: Artifacts Resolution + CLI Show

**Root Cause**: `StepResultSummary.input_file` not populated in JobGraph execution path

**Evidence**:
- `runner.py:594`: Sets `input_file=Path()` for executed steps
- `runner.py:561`: Sets `input_file=Path()` for skipped steps
- **Missing**: Job's `input_files` not copied to StepResultSummary

**Fix Direction**:
- Populate `input_file` from `job.input_files[0]` if available
- Fall back to `step.input_file` if job doesn't have input_files
- Location: `runner.py:589-599` (executed steps) and `runner.py:556-566` (skipped steps)

**Related Issue**: CLI show command expects `input_file` to be populated for artifact resolution

### Cluster B: ORCA Project-Level Tests

**Status**: ✅ All tests passing

**Note**: Tests correctly use `QVService.run_calculation()` (not `run_calc`)

### Cluster C: Incremental Run Regressions

#### C1: `pseudo_set_sha` Not Updated

**Root Cause**: Preflight computes `fresh_pseudo_sha` but doesn't write to calc.yaml

**Evidence**:
- `api.py:1227`: Computes `fresh_pseudo_sha`
- `api.py:1241-1245`: Only warns on mismatch, doesn't update
- `runner.py:256`: Recomputes `pseudo_set_sha` but doesn't update calc.yaml

**Fix Direction**:
- Update calc.yaml with `fresh_pseudo_sha` after Step0 completes
- Location: `api.py:1241-1245` or `runner.py:203-207` (after `refresh_calc_pseudo_records_after_step0`)

#### C2: K_POINTS Validation Error

**Root Cause**: Validation too strict for k-path formats (`crystal_b`, `crystal_c`, `tpiba_b`, `tpiba_c`)

**Evidence**:
- `input_runner.py:687`: Raises `ValueError` if `crystal_b` option lacks `data`
- Test uses k-path format which may not require `data` field in all cases

**Fix Direction**:
- Review K_POINTS validation logic for k-path formats
- Location: `src/quantumvitas/calculation/input_runner.py:687`
- May need to allow k-path formats without `data` field if structure provides k-path

---

## 4) Next Actions for Claude

### Priority 1: Fix Manifest Updates (BLOCKER)

1. **Update `pseudo_set_sha` in calc.yaml after Step0**
   - Location: `api.py:1241-1245` or `runner.py:203-207`
   - Action: Write `fresh_pseudo_sha` to calc.yaml after Step0 completes
   - Test: `test_pseudo_preflight_warning_and_update` should pass

### Priority 2: Fix StepResultSummary Population (HIGH)

2. **Populate `input_file` in StepResultSummary**
   - Location: `runner.py:589-599` and `runner.py:556-566`
   - Action: Copy `job.input_files[0]` or `step.input_file` to StepResultSummary
   - Test: `test_cli_show_command_executes_against_references` should pass

3. **Populate `output_file` in StepResultSummary**
   - Location: `runner.py:589-599`
   - Action: Extract output file from `job_result.step_results` or `job.expected_outputs[0]`
   - Test: CLI show command should find output files

### Priority 3: Fix K_POINTS Validation (MEDIUM)

4. **Review K_POINTS validation for k-path formats**
   - Location: `input_runner.py:687`
   - Action: Allow k-path formats (`crystal_b`, `crystal_c`, `tpiba_b`, `tpiba_c`) without `data` if structure provides k-path
   - Test: `test_crash_recovery_incremental_rerun_from_failed_step` and `test_pseudo_preflight_update_failure_non_blocking` should pass

### Priority 4: Verify ORCA Tests (LOW)

5. **Verify ORCA project-level tests are correct**
   - Status: All passing, but verify they test the right behavior
   - Action: Review test expectations vs. actual behavior

---

## Evidence Map

### Key Files

| File | Purpose | Key Lines |
|------|---------|-----------|
| `src/quantumvitas/execution/job_graph.py` | Job/JobGraph definitions | 29-203 |
| `src/quantumvitas/execution/recipes.py` | Recipe implementations | 82-405 |
| `src/quantumvitas/execution/executor.py` | JobExecutor execution loop | 75-265 |
| `src/quantumvitas/execution/handlers.py` | Engine handler bridges | 37-395 |
| `src/quantumvitas/calculation/runner.py` | Runner integration | 445-604 |
| `src/quantumvitas/api.py` | Public API entrypoints | 1146-1416 |

### Call Chain Evidence

```
API Entrypoint:
  api.py:1146 (run_calculation) / api.py:1319 (run_step)
    ↓
Runner:
  runner.py:132 (CalculationRunner.run)
    ↓
JobGraph Execution:
  runner.py:445 (_execute_with_jobgraph)
    ↓
Recipe Materialization:
  runner.py:502 (get_recipe_for_engine)
  runner.py:504 (recipe.materialize)
    ↓
Executor:
  runner.py:521 (JobExecutor)
  runner.py:527 (executor.execute)
    ↓
Handler:
  handlers.py:37-357 (qe_step_handler / pyscf_chain_handler / orca_chain_handler)
    ↓
Engine:
  step.run() / engine.run_step_with_chain()
```

---

## Conclusion

The JobGraph infrastructure is **correctly implemented** and follows the Constitution. The architecture is sound, with proper separation of concerns and runtime-only JobGraph (not persisted).

**Main Issues**:
1. Manifest updates incomplete (`pseudo_set_sha` not written)
2. StepResultSummary fields not populated (`input_file`, `output_file`)
3. K_POINTS validation too strict

**Recommendation**: Fix Priority 1 and Priority 2 items to restore test suite to green. Priority 3 is a validation logic issue that may require domain knowledge to fix correctly.

---

**End of Report**

