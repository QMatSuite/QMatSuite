# Pytest Recovery Progress Summary

**Date:** 2025-01-XX  
**Goal:** Restore full pytest suite to green (2,590 tests) while maintaining PR10/PR6 constraints

---

## Baseline Results

- **Total Tests:** 2,590
- **Passed:** 2,284 (88.2%)
- **Failed:** 215 (8.3%)
- **Errors:** 88 (3.4%)
- **Total Issues:** 303

---

## Current Results (After Initial Fixes)

- **Total Issues:** 289 (down from 303)
- **Improvement:** -14 tests fixed
- **Pass Rate:** 88.8% (up from 88.2%)

---

## Completed Work

### ✅ Bucket C: Path Double-Append Bug (COMPLETED)

**Problem:** `calculation.yaml/calculation.yaml` double-append causing 94 test failures

**Fixes:**
1. `src/quantumvitas/core/resolution.py` - `_calculation_to_resolved()` now returns directory path
2. `src/quantumvitas/api/service.py` - `init_calculation()` now returns directory path
3. `src/quantumvitas/core/models.py` - `load_calculation()` detects and fixes double-append

**Result:** 0 double-append errors remaining

### 🔄 Bucket A: Missing QVService Methods (IN PROGRESS)

**Problem:** ~200+ tests fail with `AttributeError: type object 'QVService' has no attribute '...'`

**Solution:** Created compatibility layer in `src/quantumvitas/api/compat.py`

**Completed:**
- Created `QVServiceCompat` class with `init_step()` and `add_step_to_calculation()`
- Returns wrapper objects with both DTO attributes and `absolute_path` for backward compatibility
- Updated `tests/integration/test_incremental_run.py` to use compat layer
- 1 test now passing: `test_run_lock_blocks_concurrent_runs`

**Remaining:**
- ~200+ tests still need migration to compat layer
- Need to add more compatibility methods for other missing QVService methods

---

## Next Steps (Priority Order)

### 1. Continue Bucket A Migration (HIGH PRIORITY)

**Target Files:**
- `tests/daemon/test_si_bands_calculation_daemon.py` (4 tests)
- `tests/daemon/test_gui_job_and_step_flows.py` (21 tests)
- `tests/unit/test_api_step_artifacts.py` (9 tests)
- `tests/integration/test_relax_promote_e2e.py` (3 tests)
- `tests/unit/test_api_get_band_structure_data.py` (4 tests)
- `tests/daemon/test_update_step_params_persistence.py` (3 tests)

**Action:** Update these files to use `from quantumvitas.api.compat import init_step, add_step_to_calculation`

### 2. Add More Compatibility Methods (MEDIUM PRIORITY)

**Missing Methods (by frequency):**
- `_detect_prefix_outdir_injection` (22 tests)
- `_preflight_check_and_seed_pseudos` (18 tests)
- `_build_structure_vis_payload` (16 tests)
- `calc_set_steps` (12 tests)
- `configure_calculation` (10 tests)
- `update_step_params` (8 tests)
- `get_structure_vis_data` (8 tests)
- `get_reference_analysis` (8 tests)
- `create_demo_project` (8 tests)
- And many more...

**Action:** Add these to `compat.py` as needed, delegating to new API

### 3. Fix Bucket B: Missing API Exports (MEDIUM PRIORITY)

**Problem:** ~30 tests fail with `ImportError: cannot import name '...' from 'quantumvitas.api'`

**Solution:** Update tests to import from source modules instead of `quantumvitas.api`

**Target Types:**
- `StructureStepSpec` → `from quantumvitas.calculation.structure_steps import StructureStepSpec`
- `QECardType` → `from quantumvitas.drivers.qe.io.model import QECardType`
- `ParameterOverride` → `from quantumvitas.ir.parameters import ParameterOverride`
- etc.

### 4. Create Gate Tests (HIGH PRIORITY)

**File:** `tests/gates/test_no_daemon_cli_import_api_compat.py`

**Purpose:** Prevent daemon/cli from importing `quantumvitas.api.compat`

**Implementation:**
- Scan `src/quantumvitas/daemon/**` and `src/quantumvitas/cli/**`
- Fail if `import quantumvitas.api.compat` or `from quantumvitas.api.compat` found
- Allow in comments/docstrings

---

## Constraints Maintained

✅ **PR10:** No kernel symbols exported to `quantumvitas.api`  
✅ **PR6:** No manual dict construction in daemon handlers  
✅ **No API surface expansion:** Compat module not in `api.__all__`  
✅ **Lazy imports:** All kernel imports inside functions  
✅ **Minimal changes:** Only compatibility wrappers, no large refactors

---

## Files Modified

1. `src/quantumvitas/core/resolution.py` - Fixed path resolution
2. `src/quantumvitas/api/service.py` - Fixed `init_calculation()` return path
3. `src/quantumvitas/core/models.py` - Added double-append detection
4. `src/quantumvitas/api/compat.py` - **NEW** - Compatibility layer
5. `tests/integration/test_incremental_run.py` - Migrated to compat layer

---

## Estimated Remaining Work

- **Bucket A:** ~200 tests need compat layer migration (~2-3 hours)
- **Bucket B:** ~30 tests need import updates (~30 minutes)
- **Gate Tests:** Create and verify (~15 minutes)
- **Final Verification:** Full test run and cleanup (~30 minutes)

**Total Estimated Time:** ~3-4 hours to reach full green

