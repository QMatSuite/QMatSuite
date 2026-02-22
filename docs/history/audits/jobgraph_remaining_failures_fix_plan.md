# JobGraph Remaining Failures Fix Plan

**Date**: 2025-01-15  
**Author**: Cursor (Review + Plan Only)  
**Status**: REVIEW ONLY - NO CODE CHANGES

## Executive Summary

This document provides a minimal fix plan for the three remaining test failure clusters after Claude's JobGraph implementation. All fixes must be minimal, SSOT-compliant, and preserve existing architecture.

**Current Fail Set**:
- **Cluster A**: 1 failure (`test_cli_show_command_executes_against_references`)
- **Cluster B**: 1 failure (`test_pseudo_preflight_warning_and_update`)
- **Cluster C**: 2 failures (`test_crash_recovery_incremental_rerun_from_failed_step`, `test_pseudo_preflight_update_failure_non_blocking`)

**Confirmed Green**:
- `test_api_step_artifacts.py` (9 passed)
- `test_orca_project_level.py` (6 passed)

---

## 0) Current Fail Set

### Cluster A: CLI Show Command

**Test**: `tests/cli/test_cli_show_command_integration.py::test_cli_show_command_executes_against_references`

**Error**:
```
AssertionError: atom.in: JOB DONE not found in output for step scf
Output file: <HOME>/QMatSuite/.tmp/runs/cli_show_command_exec/project/calculations/wf_atom/steps/scf.step.yaml
```

**Key Evidence**:
- Warning: `No output file provided for step scf, using input_file as fallback` (line 1625 in `cli/main.py`)
- Test expects output file to contain "JOB DONE" marker
- Test extracts output_file from CLI stdout: `"Step finished: <output_path> -> (input <input_path>)"`
- CLI command uses `result.get("output_file")` from `QMSService.run_step()` return value
- `api.py:1449` returns `"output_file": None` with TODO comment

**Matches Previous Report**: ✅ Yes (same failure pattern)

---

### Cluster B: Pseudo Set SHA Not Updated

**Test**: `tests/integration/test_incremental_run.py::test_pseudo_preflight_warning_and_update`

**Error**:
```
AssertionError: calc.yaml pseudo_set_sha not updated: expected 52d2d981dddaaec4bb8d14245d8af08aabea35e74092e98697231874633c2819, got WRONG_SHA
```

**Key Evidence**:
- Test expects `calc.yaml` to have `pseudo_set_sha` updated after preflight
- Preflight code in `api.py:1246-1265` attempts update using `save_yaml_doc()`
- Update is "non-blocking" (warnings only, doesn't fail run)
- Test reads `calc.yaml` from disk after run completes
- Initial value is `WRONG_SHA` (placeholder)

**Matches Previous Report**: ✅ Yes (same failure)

---

### Cluster C: K_POINTS Validation Error

**Tests**:
1. `tests/integration/test_incremental_run.py::test_crash_recovery_incremental_rerun_from_failed_step`
2. `tests/integration/test_incremental_run.py::test_pseudo_preflight_update_failure_non_blocking`

**Error**:
```
ValueError: K_POINTS option 'crystal_b' requires 'data' to be provided. K-path formats (crystal_b, crystal_c, tpiba_b, tpiba_c) cannot use automatic grid data.
```

**Origin**: `src/qmatsuite/calculation/input_runner.py:687`

**Key Evidence**:
- Error occurs during `Calculation.from_yaml(..., materialize_steps=True)` call
- Materialization calls `materialize_step_spec()` → `generate_qe_input_from_spec()` → `apply_card_overrides_to_qe_input()`
- Validator at `input_runner.py:680-697` correctly rejects `crystal_b` without `data`
- Test fixture `minimal_calculation` creates step with `step_type="bands"` (line 169)
- `bands` step type likely uses `crystal_b` option by default, but fixture doesn't provide `data`

**Matches Previous Report**: ✅ Yes (same failures)

---

## 1) CLUSTER A: CLI Show Failure ("JOB DONE" Missing)

### A1) CLI Command Path Trace

**File**: `src/qmatsuite/cli/main.py`

**Entry Point**: `run_step_command()` (lines 1427-1633)

**Output File Resolution** (lines 1614-1626):
```python
output_file = result.get("output_file")
if not output_file:
    output_file = result.get("stdout_file")
if not output_file:
    logger.warning(f"No output file provided for step {step_resolved.meta.name or step_resolved.meta.slug}, using input_file as fallback")
    output_file = str(input_file)
```

**Evidence**:
- CLI expects `result["output_file"]` from `QMSService.run_step()` return value
- Falls back to `result["stdout_file"]`, then `input_file` (with warning)
- Test extracts output_file from CLI stdout line: `"Step finished: <output_path> -> (input <input_path>)"` (line 199)

**API Return Value** (`src/qmatsuite/api.py:1443-1453`):
```python
return {
    "step": step_selector,
    "step_id": target_step_id,
    "step_type": step_type,
    "success": success,
    "error": error_msg,
    "output_file": None,  # TODO: Extract from step result if available
    "io_dir": io_dir,
    "working_dir": io_dir,
    "run_id": result.run_id,
}
```

**Problem**: `output_file` is hardcoded to `None` with TODO comment.

---

### A2) StepResultSummary Construction in JobGraph Path

**File**: `src/qmatsuite/calculation/runner.py`

**Location**: `_execute_with_jobgraph()` method (lines 536-604)

**Current Code** (lines 589-599):
```python
summary = StepResultSummary(
    step_id=step_ulid,
    step_type=step_type,
    status=StepStatus.SUCCESS if step_success else StepStatus.FAILED,
    working_dir=job.working_dir,
    input_file=Path(),  # ❌ Empty
    output_file=Path(),  # ❌ Empty
    reference_file=step.reference_output if hasattr(step, 'reference_output') else None,
    message=step_error if step_error else "Step completed successfully",
    metrics={},
)
```

**Available Data Sources**:

1. **Job.input_files** (`src/qmatsuite/execution/job_graph.py:Job`):
   - Type: `List[Path]`
   - Contains: `[calc_raw_dir / f"{public_type}.in"]` (from `QERecipe`, line 128)
   - Evidence: `recipes.py:128` sets `input_file = f"{public_type}.in"`

2. **Job.expected_outputs** (`src/qmatsuite/execution/job_graph.py:Job`):
   - Type: `List[Path]`
   - Contains: `[calc_raw_dir / f"{public_type}.out"]` (from `QERecipe`, line 134)
   - Evidence: `recipes.py:134` sets `expected_outputs = [calc_raw_dir / f"{public_type}.out"]`

3. **JobResult.step_results** (`src/qmatsuite/execution/executor.py:JobResult`):
   - Type: `Dict[str, Dict[str, Any]]`
   - Contains: `{step_ulid: {"success": bool, "output_file": str, "return_code": int}}`
   - Evidence: `handlers.py:126-132` sets `"output_file": str(result.output_file)` from `StepResult.output_file`

4. **StepResult.output_file** (`src/qmatsuite/core/engines/qe_calculation.py:StepResult`):
   - Type: `Optional[Path]`
   - Set by: `qe_step_handler()` calls `step.run()` which returns `StepResult`
   - Evidence: `handlers.py:112` calls `step.run()`, `handlers.py:129` extracts `result.output_file`

**Root Cause**: `StepResultSummary` is constructed from `JobResult`, but `input_file` and `output_file` are not extracted from available sources (Job fields or JobResult.step_results).

---

### A3) Minimal Fix Plan (Ranked Options)

#### Option 1: Populate from Job Fields (PREFERRED)

**Rationale**: Job fields are the source of truth for filenames (GEN naming per Constitution §F). They are available at construction time and don't require handler execution.

**Location**: `src/qmatsuite/calculation/runner.py`, `_execute_with_jobgraph()` method, lines 589-599

**Change**:
```python
# Extract input/output from Job (source of truth for GEN filenames)
job_input_file = job.input_files[0] if job.input_files else Path()
job_output_file = job.expected_outputs[0] if job.expected_outputs else Path()

# For executed steps, prefer actual output from handler if available
if not job_result.skipped and job_result.step_results:
    step_result_data = job_result.step_results.get(step_ulid, {})
    handler_output_file = step_result_data.get("output_file")
    if handler_output_file:
        job_output_file = Path(handler_output_file)

summary = StepResultSummary(
    step_id=step_ulid,
    step_type=step_type,
    status=StepStatus.SUCCESS if step_success else StepStatus.FAILED,
    working_dir=job.working_dir,
    input_file=job_input_file,  # ✅ From Job.input_files
    output_file=job_output_file,  # ✅ From Job.expected_outputs or handler
    reference_file=step.reference_output if hasattr(step, 'reference_output') else None,
    message=step_error if step_error else "Step completed successfully",
    metrics={},
)
```

**SSOT Compliance**:
- ✅ Uses GEN filenames from Job (per Constitution §F)
- ✅ Preserves handler output_file if available (actual execution result)
- ✅ Works for both executed and skipped steps

**Tests Fixed**:
- `test_cli_show_command_executes_against_references` (output_file populated)
- `test_cli_show_command_import_preserves_original_parameters` (input_file populated)

**Risks**:
- Low: Job fields are always available (materialized before execution)
- Low: Handler output_file is optional (falls back to expected_outputs)

---

#### Option 2: Populate from Handler JobResult

**Rationale**: Handler returns actual execution results, including real output_file paths.

**Location**: Same as Option 1

**Change**:
```python
# Extract from JobResult.step_results (handler execution results)
step_result_data = job_result.step_results.get(step_ulid, {}) if not job_result.skipped else {}
handler_input_file = step_result_data.get("input_file")  # May not be in step_results
handler_output_file = step_result_data.get("output_file")

# Fallback to Job fields if handler data missing
job_input_file = job.input_files[0] if job.input_files else Path()
job_output_file = job.expected_outputs[0] if job.expected_outputs else Path()

summary = StepResultSummary(
    ...
    input_file=Path(handler_input_file) if handler_input_file else job_input_file,
    output_file=Path(handler_output_file) if handler_output_file else job_output_file,
    ...
)
```

**SSOT Compliance**:
- ✅ Uses actual execution results when available
- ⚠️ Requires handler to populate step_results (currently only output_file is set)

**Tests Fixed**: Same as Option 1

**Risks**:
- Medium: Handler must populate step_results["input_file"] (currently missing)
- Medium: Requires handler changes (not minimal)

---

#### Option 3: Populate via Manifest Lookup

**Rationale**: Manifest stores ref paths for artifacts.

**Location**: Same as Option 1

**Change**:
```python
# Lookup from manifest (if step was previously executed)
manifest_entry = manifest.get_step_entry(step_ulid) if manifest else None
manifest_ref = Path(manifest_entry.ref) if manifest_entry and manifest_entry.ref else None

summary = StepResultSummary(
    ...
    input_file=job.input_files[0] if job.input_files else Path(),
    output_file=manifest_ref or job.expected_outputs[0] if job.expected_outputs else Path(),
    ...
)
```

**SSOT Compliance**:
- ⚠️ Manifest ref may not exist for new steps
- ⚠️ Manifest ref format may not match expected Path format

**Tests Fixed**: Same as Option 1

**Risks**:
- High: Manifest ref may be None for new steps
- High: Requires manifest format changes (not minimal)

---

### A4) Recommended Fix: Option 1

**Implementation Checklist**:
1. In `runner.py:_execute_with_jobgraph()`, line 589-599:
   - Extract `job_input_file` from `job.input_files[0]` (if available)
   - Extract `job_output_file` from `job.expected_outputs[0]` (if available)
   - For executed steps, check `job_result.step_results[step_ulid]["output_file"]` and use if available
   - Set `StepResultSummary.input_file = job_input_file`
   - Set `StepResultSummary.output_file = job_output_file` (or handler output_file if available)

2. In `api.py:run_step()`, line 1449:
   - Extract `output_file` from `target_summary.output_file` (Path → str)
   - Set `"output_file": str(target_summary.output_file)` if `target_summary.output_file` exists

3. Also extract `input_file` for completeness:
   - Set `"input_file": str(target_summary.input_file)` if `target_summary.input_file` exists

**Files to Change**:
- `src/qmatsuite/calculation/runner.py` (lines 589-599)
- `src/qmatsuite/api.py` (lines 1443-1453)

**Test Validation**:
```bash
pytest tests/cli/test_cli_show_command_integration.py::test_cli_show_command_executes_against_references -v
pytest tests/unit/test_project_and_cli.py::test_cli_show_command_import_preserves_original_parameters -v
```

---

## 2) CLUSTER B: Pseudo Set SHA Not Updated

### B1) Pseudo Preflight Computation Trace

**File**: `src/qmatsuite/api.py`

**Location**: `run_calculation()` method, lines 1210-1265

**Fresh SHA Computation** (line 1227):
```python
fresh_pseudo_sha = compute_pseudo_set_sha(project_pseudo_dir, species_map)
```

**Update Attempt** (lines 1248-1255):
```python
calc_data = yaml.safe_load(calc_yaml_path.read_text()) or {}
calc_data["pseudo_set_sha"] = fresh_pseudo_sha
calc_doc = CalcDoc(calc_data)
save_yaml_doc(calc_doc, calc_yaml_path)
```

**Lock Handling**: `save_yaml_doc()` handles edit lock internally (line 1254 comment).

**Step0 Execution** (`src/qmatsuite/calculation/runner.py:180-227`):
- Step0 prepares pseudos in `project/pseudo` (line 197)
- Calls `refresh_calc_pseudo_records_after_step0()` (line 203)
- This function may update `calc.yaml` with pseudo file info

**Evidence**:
- Preflight runs BEFORE `CalculationRunner.run()` (line 1203 calls `Calculation.from_yaml()`)
- Preflight update is "non-blocking" (warnings only, doesn't fail)
- Test expects update to happen even if run fails (line 804 catches Exception)

---

### B2) Test Contract Analysis

**Test**: `tests/integration/test_incremental_run.py::test_pseudo_preflight_warning_and_update`

**Test Flow** (lines 738-823):
1. Create calculation with `pseudo_set_sha = "WRONG_SHA"` (placeholder)
2. Mock `ensure_qe_pseudos` to return fake result
3. Call `QMSService.run_calculation()` (may fail, but preflight should run)
4. Re-read `calc.yaml` from disk
5. Assert `pseudo_set_sha == actual_sha` (computed from species_map)

**Expected Behavior**:
- Preflight should update `calc.yaml` with fresh SHA BEFORE runner execution
- Update should happen even if run fails (non-blocking)
- Update should persist to disk (test reads from disk)

**Current Behavior**:
- Preflight code attempts update (lines 1248-1255)
- Update may fail silently (wrapped in try/except, warnings only)
- Test reads `WRONG_SHA` (update didn't persist)

---

### B3) Root Cause Hypothesis

**Hypothesis 1**: Lock contention
- Preflight acquires edit lock via `save_yaml_doc()`
- Runner may also acquire edit lock during Step0
- Lock ordering may cause preflight update to be overwritten

**Hypothesis 2**: Timing issue
- Preflight updates `calc.yaml` before Step0
- Step0 calls `refresh_calc_pseudo_records_after_step0()` which may overwrite `pseudo_set_sha`
- `refresh_calc_pseudo_records_after_step0()` may not preserve preflight SHA

**Hypothesis 3**: Update failure
- `save_yaml_doc()` may fail silently (wrapped in try/except)
- Error is logged as warning but not surfaced
- Test doesn't see update because it never happened

**Evidence for Hypothesis 2**:
- `refresh_calc_pseudo_records_after_step0()` is called AFTER preflight (line 203 in runner.py)
- This function may write to `calc.yaml` and overwrite preflight SHA
- Need to check if `refresh_calc_pseudo_records_after_step0()` preserves `pseudo_set_sha`

---

### B4) Minimal Fix Plan

**Option 1: Update After Step0 (PREFERRED)**

**Rationale**: Step0 is the authoritative source for pseudo file info. Update `pseudo_set_sha` after Step0 completes, using the same SHA computation as preflight.

**Location**: `src/qmatsuite/calculation/runner.py`, `run()` method, after Step0 (line 207)

**Change**:
```python
# After refresh_calc_pseudo_records_after_step0() (line 203)
# Update pseudo_set_sha in calc.yaml (using edit lock)
from qmatsuite.calculation.hash_utils import compute_pseudo_set_sha
from qmatsuite.core.locking import calc_edit_lock
from qmatsuite.core.yaml_io import save_yaml_doc
from qmatsuite.core.yamldoc import CalcDoc
import yaml

if calculation.species_map:
    project_pseudo_dir = calculation.project.root / "pseudo"
    fresh_pseudo_sha = compute_pseudo_set_sha(project_pseudo_dir, calculation.species_map)
    
    # Update calc.yaml with fresh SHA (inside calc run lock, acquire edit lock)
    calc_yaml_path = calculation.dir / "calculation.yaml"
    with calc_edit_lock(calculation.dir):
        calc_data = yaml.safe_load(calc_yaml_path.read_text()) or {}
        calc_data["pseudo_set_sha"] = fresh_pseudo_sha
        calc_doc = CalcDoc(calc_data)
        save_yaml_doc(calc_doc, calc_yaml_path)
```

**Lock Ordering**:
- Outer: `calc_run_lock` (already held by `run()` method)
- Inner: `calc_edit_lock` (acquired for YAML update)

**SSOT Compliance**:
- ✅ `pseudo_set_sha` is computed from actual files in `project/pseudo` (after Step0)
- ✅ Update happens in runner (single source of truth)
- ✅ Doesn't create second truth (manifest doesn't store `pseudo_set_sha`)

**Tests Fixed**:
- `test_pseudo_preflight_warning_and_update` (SHA updated after Step0)

**Risks**:
- Low: Update happens after Step0 (authoritative source)
- Low: Lock ordering is correct (run lock outer, edit lock inner)

---

**Option 2: Preserve Preflight SHA in Step0**

**Rationale**: Preflight already computes SHA. Step0 should preserve it instead of overwriting.

**Location**: `src/qmatsuite/core/pseudo_runtime.py`, `refresh_calc_pseudo_records_after_step0()`

**Change**: Check if `pseudo_set_sha` exists in `calc.yaml` before overwriting. If it exists and is valid, preserve it.

**SSOT Compliance**: ⚠️ Preflight SHA may be stale if Step0 changes pseudo files.

**Risks**: High: Preflight SHA may not match post-Step0 state.

---

**Option 3: Remove Preflight Update, Only Update After Step0**

**Rationale**: Preflight update is redundant. Only update after Step0 (authoritative).

**Location**: `src/qmatsuite/api.py`, remove preflight update (lines 1248-1265)

**Change**: Remove the `save_yaml_doc()` call in preflight. Keep only the warning.

**SSOT Compliance**: ✅ Single update point (after Step0)

**Risks**: Low: Preflight warning still works, update happens at correct time.

---

### B5) Recommended Fix: Option 1 + Option 3

**Implementation Checklist**:
1. In `runner.py:run()`, after `refresh_calc_pseudo_records_after_step0()` (line 207):
   - Compute `fresh_pseudo_sha` using `compute_pseudo_set_sha(project_pseudo_dir, species_map)`
   - Acquire `calc_edit_lock` (inner lock, run lock already held)
   - Update `calc.yaml` with `pseudo_set_sha = fresh_pseudo_sha`
   - Save using `save_yaml_doc()`

2. In `api.py:run_calculation()`, remove preflight update (lines 1248-1265):
   - Keep warning if SHA mismatch (lines 1241-1245)
   - Remove `save_yaml_doc()` call (lines 1248-1255)
   - Keep exception handling (warnings only)

**Files to Change**:
- `src/qmatsuite/calculation/runner.py` (after line 207)
- `src/qmatsuite/api.py` (remove lines 1248-1255)

**Test Validation**:
```bash
pytest tests/integration/test_incremental_run.py::test_pseudo_preflight_warning_and_update -v
```

---

## 3) CLUSTER C: K_POINTS Validation Error

### C1) Validation Code Location

**File**: `src/qmatsuite/calculation/input_runner.py`

**Location**: `apply_card_overrides_to_qe_input()` method, lines 680-697

**Validation Logic**:
```python
kpath_formats = ["crystal_b", "crystal_c", "tpiba_b", "tpiba_c"]
if new_option and new_option.lower() in kpath_formats:
    if "data" not in payload:
        raise ValueError(
            f"K_POINTS option '{new_option}' requires 'data' to be provided. "
            "K-path formats (crystal_b, crystal_c, tpiba_b, tpiba_c) cannot use automatic grid data."
        )
```

**Validator Rules**:
- `crystal_b`, `crystal_c`, `tpiba_b`, `tpiba_c` are k-path formats
- K-path formats **require** `data` field (list of `[kx, ky, kz, npts]` segments)
- Cannot use automatic grid data (QE limitation)

**Call Stack**:
1. `Calculation.from_yaml(..., materialize_steps=True)` (test line 912, 1000)
2. `_build_step_from_spec()` (calculation.py:726)
3. `materialize_step_spec()` (structure_steps.py:1054)
4. `generate_qe_input_from_spec()` (structure_steps.py:515)
5. `apply_card_overrides_to_qe_input()` (input_runner.py:687) ← **Error here**

---

### C2) Test Fixture Analysis

**Fixture**: `minimal_calculation()` (`tests/integration/test_incremental_run.py:109`)

**Step Creation** (lines 166-171):
```python
step3_resolved = QMSService.init_step(
    project_root=tmp_project,
    calculation_selector=calc_id,
    step_type="bands",  # ← Creates bands step
)
```

**Problem**: `bands` step type may default to `K_POINTS` with `option: crystal_b` but no `data` field.

**Evidence from Other Tests**:
- `test_precision_variants_bands_pw.py:96` shows valid `crystal_b` with `data`:
  ```python
  "option": "crystal_b",
  "data": [[0.0, 0.0, 0.0, 1.0], [0.5, 0.5, 0.5, 1.0]]
  ```

**QE Semantics**:
- `crystal_b` is a k-path format (band structure calculation)
- Requires explicit k-point segments: `[[kx1, ky1, kz1, npts1], [kx2, ky2, kz2, npts2], ...]`
- Cannot use automatic grid (QE limitation)

**Decision**: Validator is **correct**. Fixture is **wrong** (provides `crystal_b` without `data`).

---

### C3) Minimal Fix Plan

**Option 1: Fix Test Fixture (PREFERRED)**

**Rationale**: Validator is correct. Test fixture should provide valid `K_POINTS` data.

**Location**: `tests/integration/test_incremental_run.py`, `minimal_calculation()` fixture

**Change**: After creating `bands` step (line 169), configure it with valid `K_POINTS`:

```python
step3_resolved = QMSService.init_step(
    project_root=tmp_project,
    calculation_selector=calc_id,
    step_type="bands",
)

# Configure bands step with valid K_POINTS crystal_b data
from qmatsuite.api import QMSService
step3_spec_path = step3_resolved.absolute_path
step3_data = yaml.safe_load(step3_spec_path.read_text())
if "cards" not in step3_data:
    step3_data["cards"] = {}
if "K_POINTS" not in step3_data["cards"] or step3_data["cards"]["K_POINTS"].get("option") == "crystal_b":
    # Set valid crystal_b k-path data (minimal: gamma point)
    step3_data["cards"]["K_POINTS"] = {
        "option": "crystal_b",
        "data": [
            [0.0, 0.0, 0.0, 1],  # Gamma point, 1 k-point
        ]
    }
    step3_spec_path.write_text(yaml.safe_dump(step3_data))
```

**Alternative**: Use `automatic` option instead of `crystal_b`:
```python
step3_data["cards"]["K_POINTS"] = {
    "option": "automatic",
    "data": [[4, 4, 4, 0, 0, 0]]  # 4x4x4 grid
}
```

**SSOT Compliance**: ✅ Test fixture provides valid QE input (per QE semantics)

**Tests Fixed**:
- `test_crash_recovery_incremental_rerun_from_failed_step`
- `test_pseudo_preflight_update_failure_non_blocking`

**Risks**: Low: Only affects test fixture, no production code changes

---

**Option 2: Relax Validator (NOT RECOMMENDED)**

**Rationale**: Allow `crystal_b` without `data` if structure provides k-path.

**Location**: `src/qmatsuite/calculation/input_runner.py:680-697`

**Change**: If `data` is missing, generate from structure symmetry (if available).

**SSOT Compliance**: ⚠️ Violates QE semantics (crystal_b requires explicit data)

**Risks**: High: May produce invalid QE input files

---

### C4) Recommended Fix: Option 1 (Fix Test Fixture)

**Implementation Checklist**:
1. In `tests/integration/test_incremental_run.py`, `minimal_calculation()` fixture (after line 171):
   - Read `bands` step YAML file
   - Check if `K_POINTS` has `option: crystal_b` without `data`
   - If so, add valid `data` field (minimal: `[[0.0, 0.0, 0.0, 1]]`)
   - Or change to `automatic` option with grid data
   - Write updated YAML back to file

**Files to Change**:
- `tests/integration/test_incremental_run.py` (after line 171)

**Test Validation**:
```bash
pytest tests/integration/test_incremental_run.py::test_crash_recovery_incremental_rerun_from_failed_step -v
pytest tests/integration/test_incremental_run.py::test_pseudo_preflight_update_failure_non_blocking -v
```

---

## 4) Minimal Patch Checklist

### Cluster A: CLI Show Failure

**File**: `src/qmatsuite/calculation/runner.py`
- **Location**: `_execute_with_jobgraph()` method, lines 589-599
- **Change**: Extract `input_file` from `job.input_files[0]`, `output_file` from `job.expected_outputs[0]` (or handler `step_results` if available)
- **Set**: `StepResultSummary.input_file = job_input_file`, `StepResultSummary.output_file = job_output_file`

**File**: `src/qmatsuite/api.py`
- **Location**: `run_step()` method, lines 1443-1453
- **Change**: Extract `output_file` and `input_file` from `target_summary`
- **Set**: `"output_file": str(target_summary.output_file)` if exists, `"input_file": str(target_summary.input_file)` if exists

---

### Cluster B: Pseudo Set SHA Not Updated

**File**: `src/qmatsuite/calculation/runner.py`
- **Location**: `run()` method, after `refresh_calc_pseudo_records_after_step0()` (line 207)
- **Change**: Compute `fresh_pseudo_sha`, acquire `calc_edit_lock`, update `calc.yaml` with `pseudo_set_sha`
- **Lock Ordering**: `calc_run_lock` (outer, already held) → `calc_edit_lock` (inner, acquire here)

**File**: `src/qmatsuite/api.py`
- **Location**: `run_calculation()` method, lines 1248-1255
- **Change**: Remove `save_yaml_doc()` call (keep warning only)

---

### Cluster C: K_POINTS Validation Error

**File**: `tests/integration/test_incremental_run.py`
- **Location**: `minimal_calculation()` fixture, after line 171
- **Change**: Configure `bands` step with valid `K_POINTS` data (either `crystal_b` with `data` or `automatic` with grid)

---

## 5) Test Commands to Validate Each Fix

### Cluster A
```bash
pytest tests/cli/test_cli_show_command_integration.py::test_cli_show_command_executes_against_references -v
pytest tests/unit/test_project_and_cli.py::test_cli_show_command_import_preserves_original_parameters -v
```

### Cluster B
```bash
pytest tests/integration/test_incremental_run.py::test_pseudo_preflight_warning_and_update -v
```

### Cluster C
```bash
pytest tests/integration/test_incremental_run.py::test_crash_recovery_incremental_rerun_from_failed_step -v
pytest tests/integration/test_incremental_run.py::test_pseudo_preflight_update_failure_non_blocking -v
```

### All Remaining Failures
```bash
pytest tests/cli/test_cli_show_command_integration.py -q
pytest tests/integration/test_incremental_run.py -q
pytest tests/unit/test_project_and_cli.py -q
```

---

## 6) Summary

**Total Changes**: 3 files (2 production, 1 test)

**Production Code Changes**:
1. `src/qmatsuite/calculation/runner.py` (2 changes: Cluster A + Cluster B)
2. `src/qmatsuite/api.py` (2 changes: Cluster A + Cluster B)

**Test Code Changes**:
1. `tests/integration/test_incremental_run.py` (1 change: Cluster C)

**Estimated Complexity**: Low (minimal changes, no architectural modifications)

**SSOT Compliance**: ✅ All fixes preserve SSOT rules (GEN filenames, manifest truth, explicit dispatch)

**Risks**: Low (targeted fixes, no refactoring)

---

**END OF DOCUMENT**

