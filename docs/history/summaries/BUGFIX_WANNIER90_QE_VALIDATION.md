# Bug Fix: Wannier90 Steps Incorrectly Validated Against QE pw Schema

## Summary

Fixed a bug where Wannier90 step types (`w90_preproc`, `w90_run`, `pw2wannier90`) were incorrectly being validated against QE `pw` module schema, causing errors like:
```
Error: Parameter 'seedname' is not defined for module 'pw'. Provide the section explicitly via --SECTION.parameter=value.
```

## Root Cause

### Problem Location
**File**: `src/quantumvitas/calculation/structure_steps.py`  
**Function**: `materialize_step_spec`

### Analysis

1. **Materialization Flow**: `materialize_step_spec` was calling `generate_qe_input_from_spec` for ALL step types, including Wannier90 steps.

2. **QE Input Generation**: `generate_qe_input_from_spec` calls `generate_qe_input_from_structure`, which creates a QE input object and then calls `apply_parameter_overrides`.

3. **Parameter Validation**: `apply_parameter_overrides` (in `src/quantumvitas/calculation/input_runner.py:442-512`) validates parameters against QE module schemas by:
   - Detecting the QE module (defaults to `pw` for structure-based inputs)
   - Loading parameter metadata for that module
   - Checking if each parameter exists in the module's parameter sections
   - Raising `ValueError` if a parameter (like `seedname`) is not defined for that module

4. **The Bug**: Wannier90 parameters (`seedname`, `num_wann`, `projections`, etc.) are not QE parameters and do not exist in QE `pw` module schema, so validation failed.

### Why This Happened

The materialization code path was designed for QE steps only. Wannier90 steps were added to the registry (`workflow/registry.py`) with `engine="qe"` because they use QE executables, but the materialization logic didn't distinguish between:
- Steps that need QE input files (`.in` files)
- Steps that need Wannier90 input files (`.win` or `.pw2wan` files)

## Solution

### Fix Location
**File**: `src/quantumvitas/calculation/structure_steps.py`  
**Lines**: ~545-650

### Implementation

1. **Early Detection**: Added check for Wannier90 step types BEFORE calling `generate_qe_input_from_spec`:
   ```python
   WANNIER90_STEP_TYPES = {"w90_preproc", "w90_run", "pw2wannier90"}
   if step_type_lower in WANNIER90_STEP_TYPES:
       # WANNIER90 PATH: Generate .win or .pw2wan files, skip QE input generation
   ```

2. **Separate Generation Path**:
   - **For `w90_preproc` and `w90_run`**: Use `Wannier90Input` from `quantumvitas.io.wannier90_input` to generate `.win` files
   - **For `pw2wannier90`**: Use `Pw2Wannier90Input` to generate `.pw2wan` files
   - **Skip**: QE input generation, QE parameter validation, pseudo resolution (Wannier90 steps don't need pseudos directly)

3. **Structure Handling**: Still resolve structure for Wannier90 steps to populate `unit_cell_cart` and `atoms_frac` blocks in `.win` files.

### Key Invariant

**Wannier90 steps must NOT go through QE input generation or QE parameter validation.**

This is because:
- Wannier90 uses its own input format (`.win` files), not QE input format
- Wannier90 parameters are completely different from QE parameters
- Wannier90 executables (`wannier90.x`, `pw2wannier90.x`) are separate from QE executables, even though they're bundled together

## Files Changed

1. **`src/quantumvitas/calculation/structure_steps.py`**:
   - Added Wannier90 step type detection at the start of `materialize_step_spec`
   - Added separate generation path for Wannier90 steps using `wannier90_input.py`
   - Bypassed QE input generation and validation for Wannier90 steps

2. **`tests/unit/test_wannier90_step_materialization.py`** (new):
   - Unit tests verifying Wannier90 steps don't trigger QE validation
   - Tests for `.win` and `.pw2wan` file generation

## Verification

### Tests Added

1. **`test_w90_preproc_does_not_use_qe_validation`**: 
   - Verifies `w90_preproc` step with `seedname` parameter does NOT raise "seedname not defined for pw" error
   - Confirms `.win` file is generated instead of QE input

2. **`test_w90_preproc_generates_win_file`**: 
   - Verifies `.win` file contains correct Wannier90 parameters (`num_wann`, `num_bands`, etc.)
   - Verifies structure data (unit cell, atoms) is included

3. **`test_pw2wannier90_generates_pw2wan_file`**: 
   - Verifies `.pw2wan` file is generated with correct namelist format

All tests pass ✅

### Expected Behavior After Fix

- **w90_preproc step**: Generates `raw/<seedname>.win` file with Wannier90 parameters, no QE validation
- **w90_run step**: Generates `raw/<seedname>.win` file, no QE validation  
- **pw2wannier90 step**: Generates `raw/<seedname>.pw2wan` file, no QE validation
- **QE steps (scf, nscf, etc.)**: Continue to work as before, with QE input generation and validation

## Backward Compatibility

✅ **No breaking changes**:
- QE steps (scf, nscf, bands, etc.) continue to use existing QE input generation path
- Only Wannier90 steps use the new path
- Existing QE/PBC workflows remain unaffected

## Related Issues

- Fixed: "Parameter 'seedname' is not defined for module 'pw'" error when materializing `w90_preproc` steps
- This was blocking silicon-wannier90 demo from running past step 2 (nscf)

## Architecture Notes

**Step Type → Engine → Input Format Mapping**:

| Step Type | Engine | Executable | Input Format | Validation |
|-----------|--------|------------|--------------|------------|
| scf, nscf | qe | pw.x | `.in` (QE) | QE pw module schema |
| w90_preproc | qe | wannier90.x | `.win` (Wannier90) | None (no schema validation) |
| pw2wannier90 | qe | pw2wannier90.x | `.pw2wan` (Fortran namelist) | None |
| w90_run | qe | wannier90.x | `.win` (Wannier90) | None |

**Key Insight**: Engine and executable can be shared, but input format and validation are step-type-specific.

