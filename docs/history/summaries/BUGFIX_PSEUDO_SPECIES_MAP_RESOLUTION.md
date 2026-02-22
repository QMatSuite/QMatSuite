# Bug Fix: Pseudopotential Resolution Using Calculation-Level species_map

## Summary

Fixed two critical bugs in the silicon-wannier90 demo:
1. **Pseudo materialization error**: Calculation failed with "Pseudopotential not configured" even though `calculation.yaml` had correct `species_map`
2. **Daemon handler crash**: UI "Edit Pseudopotentials" crashed with `TypeError` due to wrong API parameter

## Root Cause

### Bug 1: Pseudo Materialization Error

**Problem**: During step materialization, `ensure_qe_pseudos` parsed the temporary QE input file (`.temp_input_for_pseudo_resolution.in`) to extract pseudo filenames. However, this file was generated from `generate_qe_input_from_spec` which creates ATOMIC_SPECIES with placeholders (`__MISSING_PSEUDO__Si`) when no species_map is passed. The parser saw placeholders and raised a configuration error.

**Root Cause**: 
- `materialize_step_spec` called `generate_qe_input_from_spec` without passing `calculation.species_map`
- The generated QE input had placeholders instead of real pseudo filenames
- `ensure_qe_pseudos` parsed this temp file and treated placeholders as missing configuration

### Bug 2: Daemon Handler API Mismatch

**Problem**: `_handle_get_pseudo_options_for_calculation` called `QMSService.get_calculation_detail` with `calculation_selector` parameter, but the API expected `calculation_ulid`.

## Solution

### Fix 1: Honor Calculation-Level species_map

**Changes**:

1. **Modified `ensure_qe_pseudos`** (`src/qmatsuite/core/pseudo.py`):
   - Added optional `species_map` parameter
   - Changed resolution precedence:
     - **PRIMARY**: If `species_map` is provided, use it as source of truth (calculation-level authority)
     - **FALLBACK**: Parse from QE input ATOMIC_SPECIES (for legacy/standalone cases)
   - Updated docstring to explain the precedence rules

2. **Modified `materialize_step_spec`** (`src/qmatsuite/calculation/structure_steps.py`):
   - Load `calculation.species_map` from `calculation.yaml` when available
   - Pass `species_map` to `generate_qe_input_from_spec` so ATOMIC_SPECIES is populated correctly
   - Pass `species_map` to `ensure_qe_pseudos` as PRIMARY source

3. **Updated `apply_species_overrides_to_qe_input`** (`src/qmatsuite/calculation/input_runner.py`):
   - Now handles both `pseudopot` (legacy) and `pseudo_basename` (new) keys from species_map

**Key Design Decision**:
- Calculation-level `species_map` is now the PRIMARY source of truth for pseudo filenames
- QE input parsing is only used as fallback for standalone/legacy execution paths
- This ensures `calculation.yaml` species_map is consistently honored during materialization

### Fix 2: Daemon Handler API Correction

**Changes**:

1. **Modified `_handle_get_pseudo_options_for_calculation`** (`src/qmatsuite/daemon/server.py`):
   - Added boundary resolution: accept calculation selector (slug/name/ULID) and resolve to ULID
   - Changed call from `calculation_selector=...` to `calculation_ulid=...`
   - Consistent with other endpoints like `_handle_get_calculation_pseudo_mapping`

## Testing

Added comprehensive unit tests in `tests/unit/test_pseudo_species_map_resolution.py`:

1. **`test_ensure_qe_pseudos_with_species_map_primary`**: Verifies species_map is used even when QE input has placeholders
2. **`test_ensure_qe_pseudos_with_species_map_pseudo_basename_only`**: Tests `pseudo_basename` key handling
3. **`test_ensure_qe_pseudos_without_species_map_legacy_path`**: Ensures legacy path (QE input parsing) still works
4. **`test_ensure_qe_pseudos_species_map_missing_element_raises`**: Verifies proper error when element missing
5. **`test_ensure_qe_pseudos_species_map_placeholder_in_map_raises`**: Verifies error when placeholder in species_map
6. **`test_apply_species_overrides_pseudo_basename`**: Tests `pseudo_basename` handling in override function

All tests pass ✅

## Files Changed

1. `src/qmatsuite/core/pseudo.py` - Added `species_map` parameter and resolution logic
2. `src/qmatsuite/calculation/structure_steps.py` - Pass species_map through the chain
3. `src/qmatsuite/daemon/server.py` - Fixed API parameter mismatch
4. `src/qmatsuite/calculation/input_runner.py` - Handle `pseudo_basename` key
5. `tests/unit/test_pseudo_species_map_resolution.py` - New regression tests

## Backward Compatibility

- ✅ Legacy path (QE input parsing) still works when `species_map=None`
- ✅ Standalone execution paths unchanged
- ✅ Existing demos (e.g., si-bands) continue to work
- ✅ All existing tests pass

## Resolution Precedence (Documented in Code)

```
1. If species_map is provided:
   - Use it as PRIMARY source (calculation-level authority)
   - Extract pseudo filenames from species_map[element]["pseudo_basename"] or species_map[element]["pseudopot"]
   - QE input parsing is NOT used

2. If species_map is NOT provided (legacy/standalone):
   - Parse QE input ATOMIC_SPECIES card
   - Extract pseudo filenames from [element, mass, pseudo_filename] rows
   - This maintains backward compatibility
```

## Verification

To verify the fix works:

1. Load silicon-wannier90 demo in UI
2. Click "Run Calculation" - should succeed (pseudo auto-seeded from resources/pseudo)
3. Click "Edit Pseudopotentials" - should open dialog without TypeError
4. Check daemon logs for diagnostic messages confirming species_map usage

## Related Issues

- Fixed: "Pseudopotential not configured for element(s): Si" error during run
- Fixed: `TypeError: get_calculation_detail() got an unexpected keyword argument 'calculation_selector'` in UI

