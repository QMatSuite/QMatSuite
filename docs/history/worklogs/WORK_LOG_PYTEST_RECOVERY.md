# Pytest Recovery Work Log

**Goal:** Restore full pytest suite to green while maintaining PR10/PR6 architectural constraints.

**Baseline:** 303 failures/errors (215 failed + 88 errors)

---

## Step 0: Baseline (Completed)

**Initial Test Run:**
```bash
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Results:**
- Total: 2,590 tests
- Passed: 2,284 (88.2%)
- Failed: 215 (8.3%)
- Errors: 88 (3.4%)
- **Total Issues: 303**

**Failure Buckets (Initial Classification):**
- **Bucket C (Path bugs):** ~94 tests with `calculation.yaml/calculation.yaml` double-append
- **Bucket A (Missing QVService methods):** ~200+ tests with `AttributeError: type object 'QVService' has no attribute '...'`
- **Bucket B (Missing API exports):** ~30 tests with `ImportError: cannot import name '...' from 'quantumvitas.api'`

---

## Step 1: Fix Bucket C - Path Double-Append Bug (COMPLETED)

### Problem Identified
- `_calculation_to_resolved()` in `src/quantumvitas/core/resolution.py` returned `calculation.yaml` file path instead of directory path
- `init_calculation()` in `src/quantumvitas/api/service.py` returned `calculation.yaml` file path instead of directory path
- `load_calculation()` in `src/quantumvitas/core/models.py` didn't handle double-append cases

### Changes Made

**File: `src/quantumvitas/core/resolution.py`**
- Line 1235: Changed `abs_path = calculation_yaml.resolve()` to `abs_path = calculation_dir.resolve()` (return directory, not file)
- Lines 1245-1248: Fixed fallback path construction to return directory path, stripping `calculation.yaml` if present

**File: `src/quantumvitas/api/service.py`**
- Line 3001: Changed `absolute_path=calc_yaml` to `absolute_path=calc_dir` (return directory, not file)

**File: `src/quantumvitas/core/models.py`**
- Lines 417-439: Added double-append detection and normalization in `load_calculation()`:
  - Detects paths ending with `/calculation.yaml/calculation.yaml`
  - Extracts correct directory part
  - Handles both directory and file path inputs

### Verification
```bash
# Before fix: 94 tests with double-append errors
# After fix: 0 tests with double-append errors
grep -E "calculation\.yaml/calculation\.yaml" pytest_output.txt | wc -l
# Result: 0
```

### Results
- **Before:** 303 failures/errors
- **After:** 301 failures/errors
- **Improvement:** -2 (path bug fixed, but revealed more AttributeError issues)

---

## Step 2: Create Compat Layer for Bucket A (IN PROGRESS)

### Problem
Many tests call `QVService.init_step()`, `QVService.add_step_to_calculation()`, etc., but these methods were removed during PR10 API slimming.

### Solution
Created `src/quantumvitas/api/compat.py` with:
- `QVServiceCompat` class with static methods
- Module-level compatibility functions
- Lazy imports to avoid kernel imports at module level
- Delegates to new API (`QVService(project_root).calculation.add_step()`)
- Returns wrapper objects with both DTO attributes and `absolute_path` for backward compatibility

### Changes Made

**File: `src/quantumvitas/api/compat.py` (NEW)**
- Created compatibility module with:
  - `QVServiceCompat.init_step()` - wraps `QVService(project_root).calculation.add_step()`
    - Returns `StepCompatWrapper` that has both `StepDTO` attributes and `absolute_path`
  - `QVServiceCompat.add_step_to_calculation()` - same wrapper
  - Module-level functions for easier test migration

**File: `tests/integration/test_incremental_run.py`**
- Updated to use `from quantumvitas.api.compat import init_step`
- Changed `step_resolved.meta.id` to `step_resolved.step_id` (StepDTO uses `step_id`, not `meta.id`)
- All 4 `QVService.init_step()` calls replaced with `init_step()`

### Verification
```bash
# Test now passes:
python -m pytest tests/integration/test_incremental_run.py::test_run_lock_blocks_concurrent_runs -xvs
# Result: 1 passed
```

### Next Steps
1. Update remaining tests to use compat layer for `init_step` and `add_step_to_calculation`
2. Add more compatibility methods for other missing QVService methods
3. Create gate test to prevent daemon/cli from importing compat

---

## Current Status

**Test Results After Bucket C + Partial Bucket A Fix:**
- **Total Issues: 289** (down from 303, **-14 tests fixed**)
- Path bugs: 0 (fixed ✅)
- Missing methods: ~200+ (partially addressed via compat layer - 1 test file migrated)
- Missing exports: ~30 (to be addressed by updating tests)

**Progress Summary:**
- ✅ **Bucket C:** Fixed path double-append bug (94 tests unblocked, but many still fail due to missing methods)
- 🔄 **Bucket A:** Created compat layer, migrated 1 test file (`test_incremental_run.py`)
  - `tests/integration/test_incremental_run.py::test_run_lock_blocks_concurrent_runs` now passes
  - Compat layer returns wrapper objects with both DTO attributes and `absolute_path`

**Next Priority:**
1. Continue migrating tests to use compat layer for `init_step` and `add_step_to_calculation`
   - Priority files: `tests/daemon/test_*.py`, `tests/unit/test_api_step_artifacts.py`, etc.
2. Add more compatibility methods for other missing QVService methods (see diagnostic report)
3. Fix Bucket B (ImportError) by updating test imports to use source modules instead of `quantumvitas.api`
4. Create gate test to prevent daemon/cli from importing compat

---

## Constraints Maintained

✅ **PR10:** No kernel symbols exported to `quantumvitas.api`  
✅ **PR6:** No manual dict construction in daemon handlers  
✅ **No API surface expansion:** Compat module not in `api.__all__`  
✅ **Lazy imports:** All kernel imports inside functions

