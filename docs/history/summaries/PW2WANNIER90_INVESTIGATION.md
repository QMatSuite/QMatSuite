# pw2wannier90 Investigation Report

## Summary

Investigated why `pw2wannier90` step is not running in the diamond Wannier90 demo.

## Findings

### 1. File Format Issue (FIXED)

**Problem**: The generated `diamond.pw2wan` file was missing:
- A space after `&inputpp` (reference format has `&inputpp ` with trailing space)
- A trailing newline at end of file

**Fix**: Updated `Pw2Wannier90Input.to_string()` in `src/quantumvitas/io/wannier90_input.py` to:
- Add space after `&inputpp`: `"&inputpp "` instead of `"&inputpp"`
- Add trailing newline: `return "\n".join(lines) + "\n"`

### 2. Integration Test Comparison

The integration tests in `tests/integration/test_wannier90_execution.py` and `test_wannier90_project_execution.py` show that `pw2wannier90.x` should be called with:

```python
command = [str(pw2wannier90_exe)]
# Input via stdin: pw2wannier90.x < seedname.pw2wan
# Output files: seedname.mmn, seedname.amn, seedname.eig
```

This matches our implementation in `QECalculationRunner.run_step()` which correctly uses stdin redirection for `pw2wannier90` step type.

### 3. Expected Output Files

After successful `pw2wannier90` execution, the following files should be created in `raw/`:
- `diamond.mmn` - Overlap matrices (large binary file)
- `diamond.amn` - Projection matrices (large binary file)
- `diamond.eig` - Eigenvalue file
- `diamond.pw2wan.out` (or `diamond.pw2wan.out`) - stdout from pw2wannier90.x

### 4. Current Status in Demo

**Files present:**
- ✅ `diamond.pw2wan` (input file)
- ✅ `diamond.nnkp` (from w90_preproc)
- ✅ `outdir/diamond-mlwfs.save/` (QE NSCF data exists)

**Files missing:**
- ❌ `diamond.mmn`
- ❌ `diamond.amn`
- ❌ `diamond.eig`
- ❌ `diamond.pw2wan.out`

### 5. Next Steps

1. ✅ Fixed file format issue (space after `&inputpp`, trailing newline)
2. ⏳ Regenerate demo and test if pw2wannier90 now works
3. ⏳ Check if there are any other issues preventing execution (e.g., data file paths, permissions)

## Command-Line Options Tested

Tested `pw2wannier90.x` with `-h` and `--help` options - neither works. The executable expects input via stdin and does not support command-line flags for input file specification.

The correct usage is:
```bash
pw2wannier90.x < seedname.pw2wan
```

## Reference Documentation

From `.qmatsuite/engines/qe/q-e-qe-7.5/PP/Doc/INPUT_pw2wannier90.txt`:
- `pw2wannier90.x` reads input from stdin (Fortran namelist `&inputpp`)
- Requires QE data files in `outdir/prefix.save/`
- Requires `.nnkp` file from `wannier90.x -pp` step
- Outputs: `.mmn`, `.amn`, `.eig` files

## Related Code

- `src/quantumvitas/core/engines/qe_calculation.py`: `QECalculationRunner.run_step()` - handles stdin redirection
- `src/quantumvitas/core/engines/qe.py`: `uses_stdin()` - returns `True` for `pw2wannier90` step type
- `src/quantumvitas/io/wannier90_input.py`: `Pw2Wannier90Input.to_string()` - generates `.pw2wan` file (now fixed)
- `src/quantumvitas/calculation/structure_steps.py`: `materialize_step_spec()` - generates `.pw2wan` file for `pw2wannier90` step type

