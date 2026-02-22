# Cluster B: pseudo_set_sha Update Failure - Deep Code Review

## Status Summary

- **Cluster A (CLI show)**: ✅ FIXED - `StepResultSummary.input_file` and `output_file` populated correctly
- **Cluster C (K_POINTS crystal_b)**: ✅ FIXED - Test fixture updated with valid `data` field
- **Cluster B (pseudo_set_sha)**: ❌ STILL FAILING - `pseudo_set_sha` remains `WRONG_SHA` after run

## Test Failure Details

**Test**: `tests/integration/test_incremental_run.py::test_pseudo_preflight_warning_and_update`

**Error**:
```
AssertionError: calc.yaml pseudo_set_sha not updated: expected 52d2d981dddaaec4bb8d14245d8af08aabea35e74092e98697231874633c2819, got WRONG_SHA
```

**Expected Behavior**:
1. Test sets `pseudo_set_sha: WRONG_SHA` in `calc.yaml`
2. Test calls `QMSService.run_calculation()`
3. Step0 preparation should run (even with mocked `JobExecutor.execute`)
4. `refresh_calc_pseudo_records_after_step0()` should compute fresh SHA and update `calc.yaml`
5. Test reads `calc.yaml` and expects `pseudo_set_sha` to match computed SHA

**Actual Behavior**:
- `pseudo_set_sha` remains `WRONG_SHA` after the run
- Warning is logged correctly: "Pseudo set SHA mismatch"
- But the update to `calc.yaml` is not happening

## Code Changes Made

### 1. Modified `src/qmatsuite/core/pseudo_runtime.py`

**Function**: `refresh_calc_pseudo_records_after_step0()`

**Changes**:
- Added code to compute `pseudo_set_sha` using `compute_pseudo_set_sha()`
- Added code to update `pseudo_set_sha` directly in YAML file using `yaml.safe_load()` and `yaml.safe_dump()`
- Used `calc_edit_lock` to ensure atomic update

**Location**: Lines 736-754

```python
# Update pseudo_set_sha in same transaction
from qmatsuite.calculation.hash_utils import compute_pseudo_set_sha
import yaml
from qmatsuite.core.locking import calc_edit_lock

project_pseudo_dir = project_root / "pseudo"
fresh_pseudo_sha = compute_pseudo_set_sha(project_pseudo_dir, wf_model.species_map or {})

# Update both species_map and pseudo_set_sha in same transaction
# Use raw YAML write to preserve pseudo_set_sha (not in CalculationModel)
with calc_edit_lock(calculation_dir):
    # Reload to get latest state
    calc_data = yaml.safe_load(calculation_yaml.read_text()) or {}
    # Update species_map from model (refresh already updated it)
    calc_data["species_map"] = wf_model.species_map
    # Update pseudo_set_sha
    calc_data["pseudo_set_sha"] = fresh_pseudo_sha
    # Write directly to preserve all fields (including pseudo_set_sha)
    calculation_yaml.write_text(yaml.safe_dump(calc_data, sort_keys=False))
```

### 2. Modified `src/qmatsuite/calculation/runner.py`

**Function**: `CalculationRunner.run()`

**Changes**:
- Moved `refresh_calc_pseudo_records_after_step0()` call outside `if selections:` block
- Ensured it runs even when `selections` is empty
- Added `report` check to avoid `None` reference

**Location**: Lines 195-217

```python
if selections:
    # Prepare pseudos (mutates project/pseudo)
    report = prepare_project_pseudos_for_run(
        calculation.project.root,
        selections,
    )
else:
    # No selections to prepare, but still need to refresh records
    report = None

# Refresh calc records with actual file info and update pseudo_set_sha
# (refresh_calc_pseudo_records_after_step0 now handles pseudo_set_sha update)
# This runs even if selections is empty (to update SHA from existing files)
refresh_calc_pseudo_records_after_step0(
    calculation.project.root,
    calculation.dir,
    calculation.species_map or {},
)

# Log warnings if any
if report and report.warnings:
    # TODO: Consider logging these warnings somewhere visible
    pass
```

## Code Flow Analysis

### Expected Flow

1. **Test Setup** (`test_pseudo_preflight_warning_and_update`):
   - Creates `minimal_calculation` fixture with `species_map: {Si: {pseudopot: "Si.UPF"}}`
   - Creates fake pseudo file: `tmp_project / "pseudo" / "Si.UPF"` with content `"FAKE PSEUDO FILE"`
   - Sets `pseudo_set_sha: WRONG_SHA` in `calc.yaml`
   - Computes `actual_sha` from existing pseudo files

2. **Test Execution**:
   - Mocks `JobExecutor.execute` to avoid actual job execution
   - Mocks `ensure_qe_pseudos` to return fake result
   - Calls `QMSService.run_calculation()`

3. **API Layer** (`src/qmatsuite/api.py`):
   - Preflight check detects SHA mismatch and logs warning (line 1242)
   - Calls `CalculationRunner.run()`

4. **Runner Layer** (`src/qmatsuite/calculation/runner.py`):
   - Step0 preparation (lines 180-217):
     - Checks `if calculation.species_map:` (line 182)
     - Calls `species_map_to_selections()` (line 190)
     - If `selections` is empty, `report = None`
     - Calls `refresh_calc_pseudo_records_after_step0()` (line 208)

5. **Pseudo Runtime** (`src/qmatsuite/core/pseudo_runtime.py`):
   - `refresh_calc_pseudo_records_after_step0()`:
     - Loads `calc.yaml` and `wf_model` (line 694)
     - Checks `if not wf_model.species_map: return` (line 695)
     - Updates `wf_model.species_map` entries with actual file info (lines 704-735)
     - Computes `fresh_pseudo_sha` (line 742)
     - Updates `calc.yaml` with lock (lines 746-754)

### Potential Issues

#### Issue 1: Function Not Being Called

**Hypothesis**: `refresh_calc_pseudo_records_after_step0()` is not being called.

**Evidence**:
- The function is called at line 208 in `runner.py`
- It's inside `if calculation.species_map:` block (line 182)
- Test fixture sets `species_map` in `minimal_calculation` (line 141-146)

**Verification Needed**: Add logging or breakpoint to confirm function is called.

#### Issue 2: Early Return in Function

**Hypothesis**: Function returns early due to condition check.

**Evidence**:
- Line 692: `if not calculation_yaml.exists(): return`
- Line 696: `if not wf_model.species_map: return`

**Verification Needed**: Check if `wf_model.species_map` is populated when function is called.

#### Issue 3: Lock Conflict

**Hypothesis**: `calc_edit_lock` is not acquiring lock, or there's a lock conflict.

**Evidence**:
- Function uses `calc_edit_lock(calculation_dir)` (line 746)
- Runner might be holding `calc_run_lock` (outer lock)
- Lock order should be: calc_run_lock (outer) → calc_edit_lock (inner)

**Verification Needed**: Check if runner holds `calc_run_lock` when calling this function.

#### Issue 4: File Write Not Persisting

**Hypothesis**: File is written but overwritten later.

**Evidence**:
- Function writes directly to `calculation_yaml` (line 754)
- But `save_calculation()` might be called later and overwrite it
- `save_calculation()` uses `CalculationModel` which might not include `pseudo_set_sha`

**Verification Needed**: Check if `save_calculation()` is called after `refresh_calc_pseudo_records_after_step0()`.

#### Issue 5: Species Map Mismatch

**Hypothesis**: `species_map` parameter doesn't match `wf_model.species_map`.

**Evidence**:
- Function iterates over `species_map` parameter (line 704)
- But checks `if element not in wf_model.species_map:` (line 705)
- If elements don't match, updates might be skipped

**Verification Needed**: Check if `calculation.species_map` matches `wf_model.species_map`.

#### Issue 6: Exception Being Swallowed

**Hypothesis**: Exception in `refresh_calc_pseudo_records_after_step0()` is caught and ignored.

**Evidence**:
- Function is called inside `try/except` block in runner (line 189-232)
- Exception would set `calculation_failed = True` but might not propagate
- Test catches all exceptions (line 826-828)

**Verification Needed**: Check if exceptions are being logged or swallowed.

## Deep Code Review

### File: `src/qmatsuite/core/pseudo_runtime.py`

**Function**: `refresh_calc_pseudo_records_after_step0()`

**Lines**: 672-755

**Issues Found**:

1. **Line 704**: Iterates over `species_map` parameter, but checks `wf_model.species_map`
   - If `species_map` has elements not in `wf_model.species_map`, they're skipped
   - If `wf_model.species_map` has elements not in `species_map`, they're not updated

2. **Line 713**: Gets basename from `entry` (parameter), not `calc_entry` (from model)
   - This could cause mismatch if parameter and model have different basenames

3. **Line 742**: Computes SHA using `wf_model.species_map`, not `species_map` parameter
   - This is correct, but should be consistent

4. **Line 750**: Updates `calc_data["species_map"]` from `wf_model.species_map`
   - But `wf_model.species_map` was updated in-place (lines 704-735)
   - This should work, but might have issues if model doesn't reflect changes

5. **Line 754**: Writes using `yaml.safe_dump(calc_data, sort_keys=False)`
   - This should preserve all fields, but might not preserve exact formatting
   - Could cause issues if other code expects specific formatting

### File: `src/qmatsuite/calculation/runner.py`

**Function**: `CalculationRunner.run()`

**Lines**: 180-217 (Step0 preparation)

**Issues Found**:

1. **Line 182**: `if calculation.species_map:`
   - If `calculation.species_map` is `None` or empty, entire block is skipped
   - But test fixture should set `species_map`, so this should be fine

2. **Line 190**: `species_map_to_selections()` might return empty list
   - If no selections, `report = None` but function still called
   - This is correct behavior

3. **Line 208**: `refresh_calc_pseudo_records_after_step0()` called with `calculation.species_map or {}`
   - If `calculation.species_map` is `None`, passes empty dict
   - Function checks `if not wf_model.species_map: return` (line 696)
   - So if model has no species_map, function returns early

4. **Line 218**: Exception handler catches all exceptions
   - Sets `calculation_failed = True` and returns early
   - But doesn't log exception or propagate it
   - Test catches exceptions (line 826-828), so might hide errors

### File: `tests/integration/test_incremental_run.py`

**Test**: `test_pseudo_preflight_warning_and_update`

**Lines**: 754-851

**Issues Found**:

1. **Line 803**: Mocks `JobExecutor.execute` to avoid actual execution
   - But Step0 preparation happens BEFORE `JobExecutor.execute` is called
   - So mocking shouldn't affect Step0

2. **Line 815**: Mocks `ensure_qe_pseudos` to return fake result
   - This might affect `prepare_project_pseudos_for_run()`
   - But `refresh_calc_pseudo_records_after_step0()` doesn't use this

3. **Line 826-828**: Catches all exceptions
   - This might hide errors that prevent update
   - Should at least log exceptions

4. **Line 841**: Reads `calc.yaml` after run
   - Uses `yaml.safe_load()` to read
   - Checks top-level `pseudo_set_sha` first, then legacy `calculation.pseudo_set_sha`
   - This should work correctly

## Critical Finding: Model vs YAML Serialization

**Issue**: The function updates `wf_model.species_map` in-place (lines 704-735), then reloads YAML (line 748) and updates `calc_data["species_map"]` from `wf_model.species_map` (line 750).

**Problem**: `wf_model` is a `CalculationModel` object. When we update `wf_model.species_map[element]` in-place, we're modifying a dict. But when we serialize `wf_model.species_map` to YAML via `calc_data["species_map"] = wf_model.species_map`, the serialization might not preserve all fields or might serialize differently than expected.

**Evidence**: The function writes directly using `yaml.safe_dump(calc_data, sort_keys=False)` (line 754), which should work. But the `calc_data["species_map"] = wf_model.species_map` assignment might not correctly serialize the updated model.

**Potential Fix**: Instead of assigning `wf_model.species_map` directly, we should serialize it properly using the model's `to_dict()` method, or update `calc_data["species_map"]` element by element to match what we updated in `wf_model.species_map`.

## Lock Order Analysis

**API Layer** (`api.py` line 1200):
- Holds `calc_run_lock` (outer lock)
- Calls `runner.run()` (line 1257)

**Runner Layer** (`runner.py` line 208):
- Calls `refresh_calc_pseudo_records_after_step0()` inside `calc_run_lock`

**Pseudo Runtime** (`pseudo_runtime.py` line 746):
- Acquires `calc_edit_lock` (inner lock) inside the function
- This is correct: outer lock (calc_run_lock) → inner lock (calc_edit_lock)

**Conclusion**: Lock order is correct. No lock conflict.

## Recommended Next Steps

1. **Add Logging**: Add debug logging to `refresh_calc_pseudo_records_after_step0()` to confirm:
   - Function is called
   - `wf_model.species_map` is populated
   - `fresh_pseudo_sha` is computed correctly
   - File write succeeds
   - File content after write matches expected

2. **Fix Model Serialization**: Instead of `calc_data["species_map"] = wf_model.species_map`, use proper serialization:
   ```python
   # Option 1: Use model's to_dict() method
   model_dict = wf_model.to_dict()
   calc_data["species_map"] = model_dict.get("species_map", {})
   
   # Option 2: Update element by element (more explicit)
   for element, entry in wf_model.species_map.items():
       if element not in calc_data.get("species_map", {}):
           calc_data.setdefault("species_map", {})[element] = {}
       calc_data["species_map"][element].update(entry)
   ```

3. **Verify Species Map**: Check if `calculation.species_map` matches `wf_model.species_map` when function is called.

4. **Check Exception Handling**: Ensure exceptions in `refresh_calc_pseudo_records_after_step0()` are not silently swallowed. Add logging in the exception handler.

5. **Test Isolation**: Verify that test fixture creates pseudo files correctly and `species_map` is set.

6. **Add Assertion**: After writing the file, re-read it and assert that `pseudo_set_sha` was written correctly.

## Questions to Answer

1. Is `refresh_calc_pseudo_records_after_step0()` actually being called?
2. Is `wf_model.species_map` populated when function is called?
3. Is `fresh_pseudo_sha` computed correctly?
4. Is the file write succeeding?
5. Is the file being overwritten after the write?
6. Are there any exceptions being swallowed?
7. Is there a lock conflict preventing the write?

## Hypothesis: Early Return Due to Empty species_map

**Most Likely Issue**: The function returns early at line 695: `if not wf_model.species_map: return`

**Why This Could Happen**:
1. Test fixture sets `species_map` in `calc.yaml` (line 141-149)
2. But `load_calculation()` might not load it correctly
3. Or `wf_model.species_map` might be `None` or empty dict `{}`
4. Empty dict `{}` would fail the `if not wf_model.species_map:` check

**Verification**:
- Check if `wf_model.species_map` is actually populated when function is called
- Check if test fixture's `species_map` is being written to YAML correctly
- Check if `load_calculation()` is loading `species_map` correctly

**Potential Fix**:
- Change early return to: `if not wf_model.species_map or not species_map: return`
- Or add logging before early return to confirm it's happening
- Or ensure test fixture writes `species_map` correctly to YAML

## Test Data

**Test Fixture**: `minimal_calculation`
- Creates calculation with `species_map: {Si: {pseudopot: "Si.UPF"}}`
- Pseudo file: `tmp_project / "pseudo" / "Si.UPF"` with content `"FAKE PSEUDO FILE"`
- Expected SHA: `52d2d981dddaaec4bb8d14245d8af08aabea35e74092e98697231874633c2819`

**Test Setup**:
- Sets `pseudo_set_sha: WRONG_SHA` in `calc.yaml`
- Mocks `JobExecutor.execute` and `ensure_qe_pseudos`
- Calls `QMSService.run_calculation()`

**Test Assertion**:
- Expects `pseudo_set_sha` in `calc.yaml` to match computed SHA
- Currently fails: still `WRONG_SHA`

