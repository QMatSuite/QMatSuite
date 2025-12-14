# Fractional Coordinate Canonicalization Design

## Overview

This document explains the canonicalization design for fractional coordinates in QuantumVITAS structure visualization. Canonicalization ensures stable, deterministic bond counts and correct visualization behavior across different input coordinate representations.

## Core Design Principle

**Single-Point Canonicalization**: Fractional coordinates are canonicalized exactly once at the entry point of the visualization pipeline, never again downstream.

This strict rule ensures:
- Deterministic, stable bond counts across small coordinate shifts
- No double-canonicalization that could fold boundary images back into the main cell
- Clear separation: canonicalization is pre-processing, not geometry logic

## Pipeline Flow

```
Raw Structure (from QE parser, CIF, etc.)
    ↓
canonicalize_structure_in_place() [ONCE, at entry point]
    ↓
make_supercell() [NO canonicalization - uses integer translations only]
    ↓
generate_boundary_atoms() [NO canonicalization - images stay outside [0,1)]
    ↓
detect_bonds() / build_bonds() [NO canonicalization - pure geometric functions]
```

## Entry Points

Canonicalization happens at these top-level entry points only:

1. **`build_display_atoms()`** (line 1123)
   - Main entry for GUI visualization
   - Called from `QVService.get_structure_vis_data()`

2. **`visualize_structure()`** (line 1520)
   - High-level API entry point
   - Used by CLI and notebooks

3. **`plot_structure_3d()`** (line 1287)
   - Matplotlib visualization entry point
   - Can be called directly for custom plots

## Forbidden: Internal Helpers

The following functions **MUST NOT** canonicalize:

- `detect_bonds()` - Must assume input is already canonicalized
- `make_supercell()` - Must assume input is already canonicalized
- `generate_boundary_atoms()` - Must assume input is already canonicalized
- `build_bonds()` / `build_bonds_bruteforce()` / `build_bonds_cell_list()` - Pure geometric functions, no canonicalization

## Canonicalization Algorithm

### Function: `canonicalize_frac_coords()`

Located at: `src/quantumvitas/analysis/structure_viz.py:204`

**Algorithm Steps**:

1. **Integer Snapping**:
   - For each fractional coordinate component `f`:
     - Compute nearest integer: `k = round(f)`
     - If `abs(f - k) < BOUNDARY_FRAC_TOL`, snap to `k`
   - This handles floating point errors that place values very close to integers

2. **Modulo Wrapping**:
   - Wrap all coordinates into `[0, 1)` using: `result = mod(result, 1.0)`
   - This ensures all coordinates are in the primitive cell range

3. **Boundary Snapping**:
   - Values within 0.0101 of 1.0 → snap to 0.0 (handles 0.99 from -0.01 shifts)
   - Values within 0.0101 of 0.0 → snap to 0.0 (handles 0.01 from +0.01 shifts)
   - This ensures consistent supercell construction across small coordinate shifts

### Boundary Fractional Tolerance: `BOUNDARY_FRAC_TOL = 1e-8`

**Selection Process**:
- Tested values from `1e-12` to `1e-4` with Si diamond 2×2×2 supercell
- Tested fractional shifts: `[0.0, 0.001, 0.01, -0.001, -0.01]`
- All values from `1e-12` to `1e-4` produced stable bond counts of 18
- Chose `1e-8` as a conservative balance:
  - **100x smaller** than the previous `1e-4`
  - Handles typical floating point errors in integer snapping
  - Works correctly with boundary atom detection
  - Appropriate for double-precision floating point operations

**Usage**:
- Integer snapping: `if abs(f - k) < BOUNDARY_FRAC_TOL` (line 239)
- Boundary detection: `abs(frac[dim]) < tolerance` in `generate_boundary_atoms()` (line 798)

**Note**: The boundary snapping threshold (0.0101) is separate and larger. It's used for snapping values near 1.0/0.0 to exactly 0.0 after modulo, handling cases where values like 0.99 (from -0.01 shift) need to be treated as equivalent to 0.0.

## Why Single-Point Canonicalization?

### Problem: Double Canonicalization

If canonicalization happens multiple times:
- Boundary image atoms get canonicalized back into the main cell
- Supercell atoms at boundaries get shifted incorrectly
- Bond counts become unstable across small coordinate shifts
- Visualization shows incorrect atom positions

### Solution: Canonicalize Once at Entry

By canonicalizing exactly once at the entry point:
- Primitive structure is stabilized (values near 0/1 snapped to 0.0)
- Supercell expansion uses integer translations only (no re-canonicalization)
- Boundary images stay outside [0,1) (not canonicalized)
- Bond detection operates on prepared geometry (no canonicalization)

## Bond Detection Purity

### Design Rule

Bond detection functions are **pure geometric functions**:
- Given fixed geometry (atom positions) and cutoff parameters, they return the same set of bonds deterministically
- They **MUST NOT** canonicalize, wrap, or modify coordinates
- They only consume prepared geometry and return bonds

### Functions

All bond detection functions are pure:
- `detect_bonds()` - Extracts atoms and calls `build_bonds()`
- `build_bonds()` - Wrapper that calls cell-list or brute-force
- `build_bonds_bruteforce()` - Pure O(N²) distance computation
- `build_bonds_cell_list()` - Pure cell-list neighbor search

### Precondition

All bond detection functions require:
- Input structure geometry (primitive or supercell) MUST already be prepared:
  - If it started as a primitive, its fractional coordinates have already been canonicalized once via `canonicalize_structure_in_place()` at an entry point
  - Any supercells or boundary-image atoms were built on top of that canonicalized primitive via integer lattice translations only (no further canonicalization)

## Expected Behavior

### Si Diamond 2×2×2 Supercell

After robust canonicalization:
- **Stable bond count: 18** (deterministic across all fractional shifts)
- Tested shifts: `[0.0, 0.001, 0.01, -0.001, -0.01]`
- All produce identical bond count: `[18, 18, 18, 18, 18]`

### Si Diamond Primitive Cell

- **Without boundary repeat**: 1 bond (2 atoms at distance ~2.35 Å)
- **With boundary repeat**: Variable (depends on number of image atoms), but always > 1

## Testing and Validation

### Guard Tests

`tests/unit/test_canonicalization_contract.py` enforces the contract:
- `test_canonicalize_frac_coords_usage_is_restricted()`: Ensures `canonicalize_frac_coords()` is only called from allowed locations
- `test_canonicalize_structure_in_place_usage_is_restricted()`: Ensures `canonicalize_structure_in_place()` is only called from entry points
- `test_bond_detection_functions_do_not_canonicalize()`: Verifies bond functions don't call canonicalization

### Stability Tests

`tests/unit/test_structure_viz.py`:
- `test_si_supercell_bond_count_stability()`: Verifies stable bond counts across shifts
- `test_cell_list_vs_bruteforce_si_supercell()`: Verifies exact bond count (18) and method agreement
- `test_detect_bonds_supercell()`: Verifies exact bond count (18)

## Code Locations

### Canonicalization Functions

- `canonicalize_structure_in_place()`: `src/quantumvitas/analysis/structure_viz.py:181`
- `canonicalize_frac_coords()`: `src/quantumvitas/analysis/structure_viz.py:204`
- `wrap_fractional_coords()`: `src/quantumvitas/analysis/structure_viz.py:268` (thin wrapper)

### Entry Points

- `build_display_atoms()`: `src/quantumvitas/analysis/structure_viz.py:1097` (line 1123)
- `visualize_structure()`: `src/quantumvitas/analysis/structure_viz.py:1478` (line 1520)
- `plot_structure_3d()`: `src/quantumvitas/analysis/structure_viz.py:1266` (line 1287)

### Bond Detection Functions

- `detect_bonds()`: `src/quantumvitas/analysis/structure_viz.py:693`
- `build_bonds()`: `src/quantumvitas/analysis/structure_viz.py:591`
- `build_bonds_bruteforce()`: `src/quantumvitas/analysis/structure_viz.py:386`
- `build_bonds_cell_list()`: `src/quantumvitas/analysis/structure_viz.py:461`

## Constants

- `BOUNDARY_FRAC_TOL = 1e-8`: Tolerance for integer snapping and boundary detection
- `boundary_threshold = 0.0101`: Threshold for snapping values near 1.0/0.0 to 0.0 (hardcoded in `canonicalize_frac_coords()`)

## Best Practices

1. **Always canonicalize at entry points**: When calling visualization functions with raw structures, ensure canonicalization happens at the entry point (it's automatic in `build_display_atoms()`, `visualize_structure()`, `plot_structure_3d()`)

2. **Never canonicalize in tests**: When testing bond detection, explicitly canonicalize before calling `detect_bonds()`:
   ```python
   structure_canon = structure.copy()
   canonicalize_structure_in_place(structure_canon, eps=BOUNDARY_FRAC_TOL)
   bonds = detect_bonds(structure_canon, ...)
   ```

3. **Don't modify BOUNDARY_FRAC_TOL without testing**: The value `1e-8` was chosen through extensive testing. Smaller values (down to `1e-12`) work but `1e-8` is a conservative balance.

4. **Respect the contract**: Never add canonicalization calls to internal helpers. Use guard tests to catch violations.

