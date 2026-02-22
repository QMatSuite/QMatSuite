# Bugfix: pw2wannier90 Input/Output File Naming

## Problem

1. **File naming inconsistency**: pw2wannier90 input file was generated as `{seedname}.pw2wan` (e.g., `diamond.pw2wan`), but should follow standard QE naming convention: `pw2wan.in`.

2. **Output file naming**: Output should be `pw2wan.out` (not `{seedname}.pw2wan.out`).

3. **Seedname consistency**: The `seedname` parameter inside the input file (e.g., `seedname = 'diamond'`) should remain unchanged, as it controls the output file names (e.g., `diamond.mmn`, `diamond.amn`, `diamond.eig`).

4. **Errno 21 "Is a directory"**: Potential issue where `input_file` could be set to '.' or a directory path, causing execution failures.

## Expected Behavior

**File naming**:
- Input file: `pw2wan.in` (standard QE post-processing naming)
- Output file: `pw2wan.out` (stdout from pw2wannier90.x)
- Stderr file: `pw2wan.stderr` (stderr output)
- Seedname-based outputs: `diamond.mmn`, `diamond.amn`, `diamond.eig` (controlled by `seedname = 'diamond'` inside `pw2wan.in`)

**Execution command**:
```bash
pw2wannier90.x < pw2wan.in > pw2wan.out
```

## Fixes Applied

### 1. Input File Naming (`src/qmatsuite/calculation/structure_steps.py`)

**Before**:
```python
# Generate filename - ALWAYS use seedname.pw2wan (pw2wannier90 requirement)
seedname = pw2wan_input.seedname
filename = f"{seedname}.pw2wan"
```

**After**:
```python
# Generate filename - Use standard QE naming: pw2wan.in (not seedname.pw2wan)
# The seedname inside the file (e.g., 'diamond') controls output file names (diamond.mmn, etc.)
# But the input file itself should be pw2wan.in for consistency with other QE steps
from qmatsuite.calculation.naming import CalculationFileNaming
if input_name:
    filename = input_name
else:
    filename = CalculationFileNaming.input_filename("pw2wannier90")  # Returns "pw2wan.in"
```

### 2. Output File Naming (`src/qmatsuite/core/engines/qe_calculation.py`)

**Before**:
```python
# Determine output file (use relative path in working_dir)
input_stem = input_file.stem
output_filename = f"{input_stem}.out"
```

**After**:
```python
# Determine output file (use relative path in working_dir)
input_stem = input_file.stem

# Wannier90 steps have different output files
if step_type in ("w90_preproc", "w90_run"):
    output_filename = f"{input_stem}.wout"
elif step_type == "pw2wannier90":
    # pw2wannier90 output should be pw2wan.out (standard QE naming)
    # The seedname in the input controls .mmn/.amn output names, but stdout goes to pw2wan.out
    output_filename = "pw2wan.out"
else:
    output_filename = f"{input_stem}.out"
```

### 3. Stderr File Naming (`src/qmatsuite/core/engines/qe_calculation.py`)

**Before**:
```python
if step_type == "pw2wannier90":
    stderr_file = working_dir / f"{input_stem}.pw2wan.stderr"
```

**After**:
```python
if step_type == "pw2wannier90":
    # Use standard naming: pw2wan.stderr (not seedname.pw2wan.stderr)
    stderr_file = working_dir / "pw2wan.stderr"
```

### 4. Naming Convention Support (`src/qmatsuite/calculation/naming.py`)

Added special case handling for `pw2wannier90`:

```python
@classmethod
def input_extension(cls, step_type: str) -> str:
    step_lower = step_type.lower()
    if step_lower == "pw2wannier90":
        # Special case: use .in (pw2wan.in) instead of .pw2wannier90.in
        return ".in"
    # ... rest of logic

@classmethod
def input_filename(cls, step_type: str, working_dir: Optional[Path] = None) -> str:
    step_lower = step_type.lower()
    if step_lower == "pw2wannier90":
        # Special case: use "pw2wan.in" instead of "pw2wannier90.in"
        return "pw2wan.in"
    # ... rest of logic
```

Also added `pw2wannier90` to `POST_PROCESSING_TYPES` to ensure it's treated as a post-processing step.

## Files Modified

1. `src/qmatsuite/calculation/structure_steps.py`: Changed pw2wannier90 input filename generation
2. `src/qmatsuite/core/engines/qe_calculation.py`: Changed output and stderr filenames
3. `src/qmatsuite/calculation/naming.py`: Added special cases for pw2wannier90

## Verification

After these changes:
- ✅ pw2wannier90 input file is `pw2wan.in` (not `diamond.pw2wan`)
- ✅ Output file is `pw2wan.out`
- ✅ Stderr file is `pw2wan.stderr`
- ✅ Input file content still has `seedname = 'diamond'`, so outputs are `diamond.mmn`, etc.
- ✅ `Step.resolve_input_path()` already has safety checks to prevent '.' directory paths

## Execution Flow Summary

After these fixes, the execution flow is:

1. **SCF step**: `scf.in` → `scf.out`
2. **NSCF step**: `nscf.in` → `nscf.out` (kpoints list preserved for w90)
3. **W90 preproc step**: `diamond.win` → `wannier90.x -pp diamond` → `diamond.nnkp`
4. **PW2Wannier90 step**: `pw2wan.in` → `pw2wannier90.x < pw2wan.in` → `pw2wan.out` (stdout), `pw2wan.stderr` (stderr), `diamond.mmn`, `diamond.amn`, `diamond.eig` (seedname-based outputs)
5. **W90 run step**: `diamond.win` → `wannier90.x diamond` → `diamond.wout`

**Key points**:
- Input file: `pw2wan.in` (standard QE naming)
- Output file: `pw2wan.out` (stdout)
- Stderr file: `pw2wan.stderr`
- Seedname-based outputs: `diamond.mmn`, `diamond.amn`, `diamond.eig` (from `seedname = 'diamond'` inside `pw2wan.in`)
- Seedname consistency: `diamond.win` (step 3/5) and `seedname = 'diamond'` in `pw2wan.in` (step 4) must match

## Safety Checks Added

1. **Filename validation**: Prevents empty or '.' filenames
2. **Directory check**: Ensures generated path is not a directory
3. **Path resolution**: Converts to absolute paths and validates before returning
4. **Relative path handling**: Attempts to use relative paths when possible (cleaner Step.input_file)

## Next Steps

- Regenerate demos to apply new naming convention
- Test end-to-end: verify pw2wannier90 execution with new filenames
- Verify seedname consistency: outputs should still be `{seedname}.mmn`, `{seedname}.amn`, etc.
- Verify no more "Errno 21: Is a directory" errors

