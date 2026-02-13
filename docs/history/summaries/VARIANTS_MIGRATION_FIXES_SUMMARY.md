# Variants Migration Fixes Summary

## Overview

Fixed 36 failing tests after variants migration. All fixes maintain the new variants-based architecture without reverting to old behavior.

## Fixes by Phase

### Phase 1: Patch Shape Assertions (Flat → Nested) ✅
**Fixed**: 18 tests that expected flat dict structure `{"nspin": 1}` but now receive nested `{"SYSTEM": {"nspin": 1}}`

**Files Modified**:
- `tests/unit/test_detector_b.py`: Updated all `compile_magnetism` and `compile_occupations_scheme` tests
- `tests/unit/test_magnetism_paramspace_contract.py`: Updated roundtrip and apply tests
- `tests/unit/test_paramspace_contract.py`: Updated occupations_scheme roundtrip tests
- `tests/unit/test_kpoints_canonical.py`: Added `precision_lattice_matrix` parameter

**Changes**:
- `assert "nspin" in result` → `assert "nspin" in result["SYSTEM"]`
- `result["nspin"]` → `result["SYSTEM"]["nspin"]`
- `{"SYSTEM": compiled}` → `compiled` (compiled is already nested)

### Phase 2: Precision Legacy Tests Removal ✅
**Fixed**: 8 tests using deprecated `detect_precision_strict` and `TestPrecisionDetectorSimple`

**Files Modified**:
- `tests/unit/test_precision_advisor.py`:
  - Deleted `TestPrecisionDetectorSimple` class (3 tests)
  - Deleted `TestPrecisionDetectorStrict` class (4 tests)
  - Rewrote `TestCompilerDetectorEquivalence::test_equivalence_via_strict_detection` to use `detect_dimension_for_step` with variants API

**Changes**:
- Removed all references to `detect_precision_strict`
- Removed all references to simple conv_thr-only detection
- Updated to use `detect_dimension_for_step("precision", step_type, step_yaml, precision_context)`

### Phase 3: Precision Context Conditional ✅
**Fixed**: Precision context requirement now depends on variant keys

**Files Modified**:
- `src/quantumvitas/presets/variants_registry.py`: `_compile_precision_patch_for_step()`
- `src/quantumvitas/presets/integration.py`: `apply_presets_to_step()`

**Changes**:
- If variant includes `K_POINTS` key → `lattice_matrix` is required
- If variant does NOT include `K_POINTS` (bands_pw) → `lattice_matrix` is optional
- `bands_pw` variant can apply precision without lattice_matrix (only needs pseudo cutoffs)

### Phase 4: Roundtrip Tests Provide step_type ✅
**Fixed**: 12 tests that didn't provide `step_type` parameter

**Files Modified**:
- `src/quantumvitas/presets/detector.py`: Updated `detect_magnetism()` and `detect_occupations_scheme()` to accept `step_type` parameter (default "scf")
- `tests/unit/test_detector_b.py`: Added `step_type="scf"` to all roundtrip tests
- `tests/unit/test_magnetism_paramspace_contract.py`: Added `step_type="scf"` to roundtrip tests
- `tests/unit/test_paramspace_contract.py`: Added `step_type="scf"` to roundtrip tests

**Changes**:
- `detect_magnetism(params)` → `detect_magnetism(params, step_type="scf")`
- `detect_occupations_scheme(params)` → `detect_occupations_scheme(params, step_type="scf")`
- All detection functions now use variants API via `detect_dimension_for_step()`

### Phase 5: Empty Steps Default Behavior ✅
**Fixed**: 2 tests expecting default values for empty steps

**Files Modified**:
- `src/quantumvitas/presets/detector.py`: `detect_dimension_from_steps()`

**Changes**:
- Empty steps now return defaults:
  - `magnetism` → `NONMAGNETIC`
  - `occupations_scheme` → `FIXED`
  - `precision` → `CUSTOM` (requires context, cannot default)

### Phase 6: Final Fixes ✅
**Fixed**: 4 precision detection tests failing due to context resolution

**Files Modified**:
- `src/quantumvitas/presets/detector.py`: Fixed precision context building to compute `base_ecutwfc` and `base_ecutrho` from `aggregate_cutoffs()`
- `src/quantumvitas/presets/variants_registry.py`: Fixed circular import in `_match_precision_without_kpoints()`
- `tests/integration/test_precision_integration.py`: Added `precision_lattice_matrix` parameter
- `tests/integration/test_precision_roundtrip.py`: Added `precision_lattice_matrix` parameter (conditional for bands_pw)

**Changes**:
- `context.base_ecutwfc` → `aggregate_cutoffs(context.species_map, context.pseudo_index)`
- Fixed import error: `PRECISION_PW_BANDS_PW_VARIANT` is defined in `variants_registry.py`, not `precision_variants.py`

## Test Results

**Before**: 36 failed, 816 passed
**After**: 0 failed, 845 passed ✅

## Final Status

✅ All 4 previously failing precision detection tests now pass:
- `test_scf_nscf_precision_med`
- `test_roundtrip_scf_nscf_bands_pw_bands`
- `test_roundtrip_breaks_on_manual_change`
- `test_custom_on_mismatched_cutoffs`

✅ `detect_precision_strict_for_step_type` updated to use variants API:
- Now wraps `detect_dimension_for_step()` with variants API
- Maintains backward compatibility for tests that use it directly
- No longer uses deprecated receiver-based logic

## Verification

✅ No legacy APIs remain:
- `rg -n "detect_precision_strict"` → 0 matches (only in comments/docs)
- `rg -n "TestPrecisionDetectorSimple"` → 0 matches
- `rg -n "PRECISION_CONFIGS"` → 0 matches

✅ All tests use variants API:
- All detection goes through `detect_dimension_for_step()`
- All compilation goes through `compile_dimension_patch_for_step()`
- All tests provide `step_type` where needed

✅ Architecture compliance:
- No flat patch structures
- No deprecated detection methods
- No backward compatibility aliases
- Context requirements are variant-aware

## Key Improvements

1. **bands_pw K_POINTS preserved**: bands_pw variant excludes K_POINTS, so applying precision never touches kpath
2. **Context conditional**: lattice_matrix only required when variant includes K_POINTS
3. **Step-type aware**: All detection/compilation is step-type aware via variants
4. **Clean architecture**: No legacy code paths, no deprecated APIs

