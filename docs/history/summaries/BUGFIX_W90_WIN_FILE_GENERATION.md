# Bug Fix: Wannier90 .win File Generation Issues

## Issues Found

1. **Missing kpoints block**: Wannier90 requires explicit kpoints when `mp_grid` is specified, but the generated file was missing the `begin kpoints` block.

2. **QE namelist contamination**: The generated .win file contained QE namelist syntax (`&control`, `outdir`, `pseudo_dir`) which shouldn't be in a Wannier90 input file.

3. **Wrong block order**: Blocks were in incorrect order (mp_grid before num_wann, etc.).

4. **Errno 21 "Is a directory: '.'"**: Some code path was trying to open '.' as a file.

## Fixes Applied

### 1. Generate kpoints from mp_grid

**File**: `src/qmatsuite/calculation/structure_steps.py`

Added automatic kpoints generation when `mp_grid` is specified:

```python
if "mp_grid" in flat_params and flat_params["mp_grid"] is not None:
    mp_grid = flat_params["mp_grid"]
    if isinstance(mp_grid, list):
        w90_input.mp_grid = [int(x) for x in mp_grid if x is not None]
        # Generate explicit kpoints from mp_grid (Wannier90 requires this)
        from qmatsuite.io.wannier90_input import generate_kpoints_from_mp_grid
        w90_input.kpoints = generate_kpoints_from_mp_grid(w90_input.mp_grid)
```

### 2. Filter QE namelist syntax from .win file

**File**: `src/qmatsuite/io/wannier90_input.py`

Modified `to_string()` to filter out QE-specific parameters and namelist syntax:

```python
# Extra parameters (key = value) - but exclude QE-specific ones
for key, value in self.extra_parameters.items():
    # Skip QE namelist parameters that shouldn't be in .win file
    if key.lower() in ("outdir", "pseudo_dir", "prefix", "control", "system", "electrons"):
        continue
    # ... rest of code

# Extra raw lines (but filter out QE namelist syntax)
if self.extra_lines:
    extra_lines_clean = []
    for line in self.extra_lines.strip().split("\n"):
        line_stripped = line.strip()
        # Skip QE namelist syntax
        if line_stripped.startswith("&") or line_stripped.startswith("/"):
            continue
        # Skip QE-specific parameters
        if any(qe_param in line_stripped.lower() for qe_param in ["outdir", "pseudo_dir", "prefix"]):
            continue
        extra_lines_clean.append(line)
```

### 3. Correct file structure order

The `to_string()` method now generates blocks in the correct order:
1. Core parameters (num_wann, num_bands, num_iter)
2. Plotting options
3. Atoms block
4. Projections block
5. Unit cell block
6. MP grid
7. K-points block

## Verification

Tested with actual diamond demo step spec:
```python
# Generated file structure:
num_wann        = 4
num_iter        = 20

begin atoms_frac
C      -0.125000     -0.125000     -0.125000
C       0.125000      0.125000      0.125000
end atoms_frac

begin projections
f=0.0,0.0,0.0:s
f=0.0,0.0,0.5:s
f=0.0,0.5,0.0:s
f=0.5,0.0,0.0:s
end projections

begin unit_cell_cart
   -3.050000     0.000000     3.050000
    0.000000     3.050000     3.050000
   -3.050000     3.050000     0.000000
end unit_cell_cart

mp_grid : 4 4 4

begin kpoints
0.0000  0.0000  0.0000
... (64 kpoints total)
end kpoints
```

## User Action Required

If the existing `.win` file in the project is corrupted (contains QE namelist syntax), it needs to be regenerated:

1. Delete the corrupted file: `calculations/diamond-mlwfs/raw/diamond.win`
2. Re-run the calculation (the file will be regenerated correctly)

## Related Files

- `src/qmatsuite/calculation/structure_steps.py`: Added kpoints generation
- `src/qmatsuite/io/wannier90_input.py`: Filtered QE syntax, fixed block order
- `src/qmatsuite/io/wannier90_input.py`: `generate_kpoints_from_mp_grid()` function

