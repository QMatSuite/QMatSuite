# PR #2 Summary: Canonicalization → Shifted Wrap (No Snapping)

## Overview

This PR implements a major refactoring of the canonicalization system to use pure shifted wrap (representative selection only) with no snapping, rounding, or threshold-based geometry modifications. It also introduces supercell-aware tolerance scaling for boundary repeat detection.

## Key Changes

### 1. Canonicalization: Pure Shifted Wrap (No Snapping)

**Replaced `canonicalize_frac_coords()`**:
- **Before**: Used integer snapping, modulo wrapping, and boundary snapping (hardcoded 0.0101 threshold)
- **After**: Uses pure shifted wrap via `wrap_fractional_coords_shifted()` - only integer lattice translations
- **Canonical interval**: `[lo, lo+1)` where `lo = -wrap_tol` (default `[-1e-4, 0.9999)`)
- **No geometry modifications**: No snapping, rounding, or threshold-based nudging

**Updated `canonicalize_structure_in_place()`**:
- Changed parameter from `eps` to `wrap_tol` (default `WRAP_TOL = 1e-4`)
- Now uses pure shifted wrap throughout

### 2. Tolerance Constants: Split `wrap_tol` vs `boundary_tol`

**New constants**:
- `WRAP_TOL = 1e-4`: Controls shifted canonical interval `[lo, lo+1)` where `lo = -wrap_tol`
- `BOUNDARY_TOL = 0.01`: Used only for boundary-repeat near-face tests (not for geometry modification)
- `BOUNDARY_FRAC_TOL = 1e-6`: Legacy constant, now only used for debug consistency checks (atol)

**Semantics**:
- `wrap_tol`: Representative selection interval (geometry-preserving)
- `boundary_tol`: Detection threshold for boundary repeat (not geometry modification)
- `BOUNDARY_FRAC_TOL`: Debug atol only (no geometry modifications)

### 3. Adaptive Boundary Repeat: Supercell-Aware Scaling

**Updated `generate_boundary_atoms()`**:
- **New signature**: `generate_boundary_atoms(structure, boundary_tol=BOUNDARY_TOL, wrap_tol=WRAP_TOL, supercell_factors=(1,1,1))`
- **Supercell scaling**: For factors `(m,n,l)`, per-dimension tolerance = `boundary_tol / factor`
  - `tol_x = boundary_tol / m`
  - `tol_y = boundary_tol / n`
  - `tol_z = boundary_tol / l`
- **Geometric boundary detection**: Uses distances to `lo`/`hi` boundaries (not `abs(f-0)`/`abs(f-1)`)
  - Near `lo`: `(f[d] - lo) < tol_dim[d]` → generate `+1` image
  - Near `hi`: `(hi - f[d]) < tol_dim[d]` → generate `-1` image
- **No canonicalization of images**: Image atoms remain outside canonical interval

**Updated `build_display_atoms()`**:
- Determines supercell factors per mode:
  - Primitive/conventional: `(1,1,1)`
  - Supercell: `(m,n,l)` from `params.supercell`
- Passes factors to `generate_boundary_atoms()` for tolerance scaling

### 4. Updated Function Signatures

**Changed**:
- `canonicalize_structure_in_place(structure, wrap_tol=WRAP_TOL)` (was `eps=BOUNDARY_FRAC_TOL`)
- `canonicalize_frac_coords(frac, wrap_tol=WRAP_TOL)` (was `eps=BOUNDARY_FRAC_TOL`)
- `wrap_fractional_coords(frac, wrap_tol=WRAP_TOL)` (was `eps=BOUNDARY_FRAC_TOL`)
- `wrap_cartesian_coords(coords, lattice, wrap_tol=WRAP_TOL)` (was `eps=BOUNDARY_FRAC_TOL`)
- `generate_boundary_atoms(structure, boundary_tol=BOUNDARY_TOL, wrap_tol=WRAP_TOL, supercell_factors=(1,1,1))` (was `tolerance=BOUNDARY_FRAC_TOL`)

**All call sites updated**:
- `build_display_atoms()`: Uses `wrap_tol=WRAP_TOL` for canonicalization
- `plot_structure_3d()`: Uses `wrap_tol=WRAP_TOL` for canonicalization
- `visualize_structure()`: Uses `wrap_tol=WRAP_TOL` for canonicalization
- All `generate_boundary_atoms()` calls: Pass `boundary_tol`, `wrap_tol`, and `supercell_factors`

### 5. Tests

**New tests in `TestCanonicalizationNoDouble`**:
- `test_canonicalize_shifted_wrap_invariants`: Verifies shifted wrap preserves sign and neighborhood invariants (no snapping)
- `test_boundary_repeat_shifted_boundaries`: Verifies boundary repeat uses shifted boundaries and `boundary_tol`
- `test_supercell_scaling_factors`: Verifies supercell scaling factors work correctly for boundary repeat

**Test coverage**:
- Shifted wrap invariants: `wrap(+t/2) == +t/2`, `wrap(-t/2) == -t/2` (must remain negative)
- No snapping: Values near 0 or 1 are NOT forced to 0
- Boundary repeat: Uses geometric distances to `lo`/`hi` boundaries
- Supercell scaling: Per-dimension tolerance scaling works correctly
- No duplicates: Cartesian product construction ensures no duplicate boundary atoms

## Constraints Maintained

✅ **Bond algorithm unchanged**: `build_bonds*`, `build_bonds_cell_list`, etc. remain pure and unchanged  
✅ **No per-atom metadata**: Downstream continues to consume plain list/array of coordinates  
✅ **Representative selection only**: Canonicalization uses integer lattice translations (geometry-preserving)  
✅ **Convention A semantics**: Supercell lattice is the supercell lattice; fractional coords interpreted with respect to that lattice  
✅ **Single-point canonicalization**: Canonicalization happens exactly once at entry point

## Documentation Updates

- Updated module docstrings to reflect pure shifted wrap (no snapping)
- Updated canonicalization contract comments
- Updated `build_display_atoms()` docstring to describe supercell-aware tolerance scaling
- Updated `generate_boundary_atoms()` docstring to describe geometric boundary detection

## Public API Exports

Added to `__all__`:
- `WRAP_TOL`: Wrap tolerance constant
- `BOUNDARY_TOL`: Boundary tolerance constant
- `BOUNDARY_FRAC_TOL`: Legacy constant (debug checks only)

## Files Modified

- `src/quantumvitas/analysis/structure_viz.py`: Core implementation
- `tests/unit/test_structure_viz.py`: New tests for shifted wrap invariants and boundary repeat

## Summary

This PR successfully:
1. ✅ Replaces snapping+0.0101 logic with pure shifted wrap
2. ✅ Splits `wrap_tol` vs `boundary_tol` with clear semantics
3. ✅ Implements supercell-aware tolerance scaling for boundary repeat
4. ✅ Maintains all non-negotiable constraints (bond code unchanged, no metadata, etc.)
5. ✅ Adds comprehensive tests verifying invariants and behavior

**Bond code remains unchanged** - all bond detection functions are pure and consume prepared geometry without modification.

