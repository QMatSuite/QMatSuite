# Bugfix: Wannier90 unit_cell_cart Unit Conversion Error

## Problem

Running `pw2wannier90` reported:
```
from pw2wannier90 : error # 4
Direct lattice mismatch
```

**Root Cause**: The generated `diamond.win` file had `unit_cell_cart` written in Bohr units (~3.05) instead of Angstrom (~1.614). Wannier90 expects Angstrom.

## Evidence

**Reference (correct)**: `.qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/examples/example05/diamond.win`
```
begin unit_cell_cart
-1.613990   0.000000   1.613990
 0.000000   1.613990   1.613990
-1.613990   1.613990   0.000000
end unit_cell_cart
```

**Generated (incorrect)**: Previously generated files had:
```
begin unit_cell_cart
   -3.050000     0.000000     3.050000
    0.000000     3.050000     3.050000
   -3.050000     3.050000     0.000000
end unit_cell_cart
```

The values are approximately 1.8897× larger (≈ 1/0.529177), indicating a Bohr conversion bug.

## Fixes Applied

### 1. Wannier90 unit_cell_cart Fix (`src/qmatsuite/calculation/structure_steps.py`)

**Before**:
```python
# Unit cell in Bohr (convert from Angstrom)
ANGSTROM_TO_BOHR = 1.0 / 0.5291772105638411
lattice = structure.lattice
w90_input.unit_cell_cart = [
    [lattice.matrix[i][j] * ANGSTROM_TO_BOHR for j in range(3)]
    for i in range(3)
]
w90_input.length_unit = "bohr"
```

**After**:
```python
# Wannier90 unit_cell_cart MUST be in Angstrom (not Bohr)
# Structure.lattice.matrix is always in Angstrom in pymatgen
lattice = structure.lattice
w90_input.unit_cell_cart = [
    [float(lattice.matrix[i][j]) for j in range(3)]
    for i in range(3)
]
w90_input.length_unit = "ang"
```

**Changes**:
- Removed Bohr conversion (no multiplication by `ANGSTROM_TO_BOHR`)
- Set `length_unit = "ang"` (Angstrom)
- Added consistency assertion to verify `unit_cell_cart @ atoms_frac == cartesian_coords`

### 2. Wannier90 atoms_frac Fix

**Before**: Already correct (used `structure.frac_coords`), but clarified in code comments.

**After**: Explicitly documented that `atoms_frac` must come directly from `structure.frac_coords`, not derived from other parameters.

### 3. Consistency Assertion Added

Added a fail-fast assertion that verifies:
```
unit_cell_cart (Å) @ atoms_frac == cartesian_coords (Å)
```

If this fails, raises a detailed error showing both lattice matrices and coordinate mismatches.

### 4. QE ATOMIC_POSITIONS Format Fix (`src/qmatsuite/io/structure_io.py`)

**Before**:
```python
# ATOMIC_POSITIONS in angstrom
atomic_positions_data = []
for site in structure.sites:
    x, y, z = site.coords  # Cartesian coordinates
    atomic_positions_data.append([site.specie.symbol, x, y, z])

atomic_positions_card = QECard(
    card_type=QECardType.ATOMIC_POSITIONS,
    option="angstrom",
    data=atomic_positions_data,
)
```

**After**:
```python
# ATOMIC_POSITIONS in crystal (fractional) coordinates
# Always use crystal format for better readability and consistency
atomic_positions_data = []
for site in structure.sites:
    # Use fractional coordinates directly from structure
    x, y, z = site.frac_coords
    atomic_positions_data.append([site.specie.symbol, x, y, z])

atomic_positions_card = QECard(
    card_type=QECardType.ATOMIC_POSITIONS,
    option="crystal",
    data=atomic_positions_data,
)
```

**Changes**:
- Changed from `site.coords` (Cartesian) to `site.frac_coords` (fractional)
- Changed option from `"angstrom"` to `"crystal"`
- Added comment explaining rationale

### 5. Wannier90Input Default Fix (`src/qmatsuite/io/wannier90_input.py`)

**Before**:
```python
length_unit: str = "bohr"  # 'bohr' or 'ang'
```

**After**:
```python
length_unit: str = "ang"  # 'bohr' or 'ang' - default to 'ang' (Angstrom)
```

## Regression Tests Added

Added `tests/unit/test_wannier90_unit_cell_fix.py` with:

1. **test_w90_unit_cell_cart_in_angstrom**: Verifies `unit_cell_cart` values are ~1.6 Å (not ~3.05 Bohr)
2. **test_w90_atoms_frac_from_structure**: Verifies `atoms_frac` matches `structure.frac_coords`
3. **test_w90_consistency_assertion**: Tests consistency check logic
4. **test_w90_from_reference_file**: Parses reference `diamond.win` and verifies Angstrom range
5. **test_qe_atomic_positions_crystal_format**: Verifies QE input uses `ATOMIC_POSITIONS {crystal}`

All tests pass ✅

## Files Modified

1. `src/qmatsuite/calculation/structure_steps.py`: Fixed Wannier90 lattice conversion, added consistency assertion
2. `src/qmatsuite/io/structure_io.py`: Changed QE `ATOMIC_POSITIONS` to use crystal format
3. `src/qmatsuite/io/wannier90_input.py`: Changed default `length_unit` to "ang"
4. `tests/unit/test_wannier90_unit_cell_fix.py`: New regression tests

## Verification

1. ✅ All regression tests pass
2. ✅ Generated `.win` files now have `unit_cell_cart` in Angstrom (~1.614, not ~3.05)
3. ✅ Generated QE inputs use `ATOMIC_POSITIONS {crystal}` format
4. ✅ Consistency assertion catches mismatches

## Next Steps

- Regenerate Wannier90 demos to apply fixes
- Run `pw2wannier90` and verify "Direct lattice mismatch" error is resolved
- Validate full Wannier90 workflow end-to-end

