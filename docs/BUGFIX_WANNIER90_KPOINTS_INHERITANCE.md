# Bugfix: Wannier90 Kpoints Inheritance and pw2wannier90 stderr Output

## Problem

Two issues were identified:

1. **pw2wannier90 "problems with k-points" error**: The generated `.win` file had kpoints in a different order than the `nscf` step, causing pw2wannier90 to report "k-point 2 is wrong" errors.

2. **pw2wannier90 stderr not written to file**: The stderr output from `pw2wannier90.x` was not being written to a file, making debugging difficult.

## Root Cause

### Issue 1: Kpoints Order Mismatch

**Problem**: The Wannier90 `.win` file was generating kpoints from `mp_grid` using `generate_kpoints_from_mp_grid`, which creates kpoints in the order:
```python
for i in range(n1):
    for j in range(n2):
        for k in range(n3):
            kpoints.append([i/n1, j/n2, k/n3])
```

This creates kpoints with **x fastest** (i changes fastest).

However, QE's `nscf` step may use kpoints in a different order (e.g., **y fastest**). The reference `diamond.nscf` shows:
- Point 1: (0, 0, 0)
- Point 2: (0, 0.25, 0)  ← y changes first
- Point 3: (0, 0.5, 0)

**pw2wannier90** compares kpoints by index (not as a set), so any order mismatch causes "k-point N is wrong" errors.

### Issue 2: stderr Not Written

The `pw2wannier90.x` execution was capturing stderr to a variable but not writing it to a file, making it difficult to debug errors.

## Fixes Applied

### Fix 1: Extract Kpoints from nscf Step (Preserve Order)

**New Module**: `src/quantumvitas/calculation/wannier90_kpoints.py`

This module provides:
- `extract_kpoints_from_qe_input()`: Extract kpoints from a QE input file, preserving exact order
- `canonicalize_kpoint()`: Snap kpoint coordinates near 0 and 1 to avoid floating-point precision issues
- `format_kpoint_for_w90()`: Format kpoints with stable precision (10 decimal places)
- `find_nscf_input_file()`: Locate the nscf step input file from calculation directory
- `extract_kpoints_from_nscf_step()`: Main function to extract kpoints from nscf step

**Modified**: `src/quantumvitas/calculation/structure_steps.py`

In `materialize_step_spec()`, for `w90_preproc` and `w90_run` steps:
1. **Extract kpoints from nscf step** instead of generating from `mp_grid`
2. **Preserve exact order** from nscf input file
3. **Add consistency check**: Verify that kpoints count matches `mp_grid[0] * mp_grid[1] * mp_grid[2]`
4. **Fallback**: If nscf kpoints cannot be extracted, generate from `mp_grid` but log a warning

**Modified**: `src/quantumvitas/io/wannier90_input.py`

In `Wannier90Input.to_string()`:
1. **Canonicalize kpoints** before writing (snap near 0 and 1)
2. **Format with 10 decimal places** for stable output
3. **Consistent spacing** in `.win` file

### Fix 2: Write pw2wannier90 stderr to File

**Modified**: `src/quantumvitas/core/engines/qe_calculation.py`

In `QECalculationRunner.run_step()`:
1. **For `pw2wannier90` step type**: Write stderr to `<seedname>.pw2wan.stderr` file
2. **Capture stderr during execution**: Open stderr file handle and redirect process stderr to it
3. **Read stderr from file**: After execution, read stderr file content for `StepResult`
4. **Fallback**: If stderr file wasn't created (e.g., from PIPE), write captured stderr to file

## Regression Tests

Added `tests/unit/test_wannier90_kpoints_inheritance.py`:

1. `test_extract_kpoints_from_nscf`: Verify kpoints extraction from nscf input
2. `test_canonicalize_kpoint`: Test kpoint canonicalization (snap near 0/1)
3. `test_format_kpoint_for_w90`: Test kpoint formatting
4. `test_w90_kpoints_match_nscf_order`: **Critical test** - Verify `.win` kpoints match nscf order exactly
5. `test_find_nscf_input_file`: Test finding nscf input file
6. `test_extract_kpoints_from_nscf_step`: Test full extraction workflow

All tests pass ✅

## Files Modified

1. `src/quantumvitas/calculation/wannier90_kpoints.py` (new)
2. `src/quantumvitas/calculation/structure_steps.py`
3. `src/quantumvitas/io/wannier90_input.py`
4. `src/quantumvitas/core/engines/qe_calculation.py`
5. `tests/unit/test_wannier90_kpoints_inheritance.py` (new)

## Verification

1. ✅ Kpoints extracted from nscf preserve exact order
2. ✅ Second kpoint is [0, 0.25, 0] (not generated order)
3. ✅ Kpoints are canonicalized (snap near 0/1)
4. ✅ Consistency check validates mp_grid count
5. ✅ pw2wannier90 stderr written to file

## Next Steps

- Regenerate Wannier90 demos to apply fixes
- Run `pw2wannier90` and verify "problems with k-points" error is resolved
- Verify stderr file is created: `<seedname>.pw2wan.stderr`
- Validate full Wannier90 workflow end-to-end

