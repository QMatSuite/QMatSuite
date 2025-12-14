# Bond Detection Notes

## Overview

Bond detection in QuantumVITAS uses a simple, deterministic algorithm based on Euclidean distance and covalent radii. This document explains the algorithm, parameters, and expected behavior.

## Bond Detection Algorithm

### Single Source of Truth

All bond detection goes through `build_bonds()` in `src/quantumvitas/analysis/structure_viz.py`, which uses a cell-list (neighbor-grid) algorithm by default, with brute-force as the gold standard for validation.

### Bond Criterion

A bond is formed between atoms `i` and `j` if:

```
distance(i, j) <= min(max_cutoff, (r_i + r_j) * max_factor + tolerance)
```

Where:
- `r_i`, `r_j`: Covalent radii of elements (from `COVALENT_RADII` dictionary)
- `max_factor`: Multiplier for sum of radii (default: 1.2)
- `tolerance`: Extra tolerance in Å (default: 0.3)
- `max_cutoff`: Maximum distance to consider in Å (default: 3.5)

### Default Parameters

- `max_factor = 1.2`
- `tolerance = 0.3` Å
- `max_cutoff = 3.5` Å

For Si-Si bonds:
- Si covalent radius: 1.11 Å
- Bond threshold: `min(3.5, 2.22 * 1.2 + 0.3) = min(3.5, 2.964) = 2.964` Å

### Bond Uniqueness

- Each bond is counted exactly once (unordered pair `(i, j)` with `i < j`)
- Bonds are returned in deterministic order (sorted by `(idx1, idx2)`)
- No duplicates are possible by construction

## Canonicalization

### Single-Point Canonicalization Rule

**CRITICAL**: Fractional coordinates are canonicalized exactly once at the entry point of the visualization pipeline, never again downstream.

1. **Entry Point**: `canonicalize_structure_in_place()` is called on the primitive structure at:
   - `build_display_atoms()` (main entry for GUI)
   - `plot_structure_3d()` (matplotlib visualization)
   - `visualize_structure()` (high-level API)
   - `detect_bonds()` (legacy API, canonicalizes its input)

2. **Canonicalization Logic** (`canonicalize_frac_coords()`):
   - Snaps values very close to integers (within `BOUNDARY_FRAC_TOL = 1e-4`) to those integers
   - Wraps into `[0, 1)` using modulo 1
   - Snaps values near boundaries to 0.0:
     - Values within 0.0101 of 1.0 → snap to 0.0 (handles 0.99 from -0.01 shifts)
     - Values within 0.0101 of 0.0 → snap to 0.0 (handles 0.01 from +0.01 shifts)

3. **Downstream Operations**:
   - `make_supercell()`: Does NOT canonicalize (assumes input is already canonicalized)
   - `generate_boundary_atoms()`: Does NOT canonicalize image atoms (they stay outside [0,1))
   - Supercell atoms may have fractional coords outside [0, 1) - this is correct

### Boundary Fractional Tolerance

`BOUNDARY_FRAC_TOL = 1e-4` is used for:
- Initial snapping to integers
- Boundary detection in `generate_boundary_atoms()`

The boundary snapping threshold (0.0101) is larger to ensure stability across typical fractional shifts (0.01 scale).

## Expected Bond Counts

### Si Diamond 2×2×2 Supercell

After robust canonicalization (snapping values near 0.0 and 1.0 to 0.0), a Si diamond 2×2×2 supercell consistently produces:

- **18 unique internal bonds**

This count is stable across small fractional shifts (tested with shifts of 0.0, ±0.001, ±0.01).

### Si Diamond Primitive Cell

- **Without boundary repeat**: 1 bond (2 atoms at distance ~2.35 Å)
- **With boundary repeat**: Variable (depends on number of image atoms generated), but always > 1

## Periodic Boundary Conditions

### No PBC in Bond Detection

Bond detection uses **strictly Euclidean distance** on the display atom list. There is no minimum-image convention or periodic wrapping in the bond calculation itself.

### Boundary Repeat (Display Feature)

"Boundary repeat" is a **display-only** feature that:
- Generates image atoms in neighboring cells for atoms near boundaries
- These image atoms are added to the display atom list
- Bonds are then computed on the combined list (base + images) using Euclidean distance
- Image atoms have fractional coordinates outside [0, 1) and are NOT canonicalized

## Implementation Details

### Cell-List Algorithm

The accelerated cell-list algorithm (`build_bonds_cell_list()`) produces identical results to brute-force but with better performance for larger systems:

1. Compute safe global cutoff: `r_cut = max_cutoff + CELL_LIST_EPS` (where `CELL_LIST_EPS = 1e-6`)
2. Use `cell_size = r_cut` (ensures only 27 neighbor cells needed)
3. Build grid keyed by integer cell indices
4. For each atom, only check neighbors in same cell + 26 adjacent cells
5. Use `i<j` discipline to avoid duplicates

### Validation

The cell-list algorithm is validated against brute-force in unit tests. Both methods must produce identical bond sets (same index pairs, same distances within tolerance).

## Test Expectations

All tests use exact bond counts, not ranges:

- `test_cell_list_vs_bruteforce_si_supercell`: Expects exactly 18 bonds
- `test_detect_bonds_supercell`: Expects exactly 18 bonds
- `test_si_supercell_bond_count_stability`: Expects exactly 18 bonds across all shifts
- `test_primitive_si_with_repeat_boundary_shows_extra_atoms_and_bonds`: Verifies boundary repeat adds atoms and bonds

## Code Locations

- Bond detection: `src/quantumvitas/analysis/structure_viz.py`
  - `build_bonds()`: Main entry point (line ~514)
  - `build_bonds_bruteforce()`: Gold standard (line ~322)
  - `build_bonds_cell_list()`: Accelerated (line ~391)
  - `detect_bonds()`: Legacy API wrapper (line ~610)

- Canonicalization: `src/quantumvitas/analysis/structure_viz.py`
  - `canonicalize_structure_in_place()`: Entry point (line ~145)
  - `canonicalize_frac_coords()`: Core logic (line ~197)

- Tests: `tests/unit/test_structure_viz.py`

