# PR #1 Summary: Eliminate Double Canonicalization + Add Shifted Wrap Helper

## Changes Made

### A. Eliminated Double Canonicalization

**Problem**: 
- `visualize_structure()` was calling `canonicalize_structure_in_place()` twice:
  1. Indirectly through `plot_structure_3d()` (line 1538)
  2. Directly for atom/bond counting (line 1769)

**Solution**:
1. **Modified `plot_structure_3d()`**:
   - Added optional parameter `structure_canon: Optional[PMGStructure] = None`
   - If `structure_canon` is provided, uses it directly (no canonicalization)
   - If `structure_canon` is None, canonicalizes the input structure (backward compatible)

2. **Modified `visualize_structure()`**:
   - Canonicalizes structure **once** at the beginning (line 1762)
   - Passes pre-canonicalized structure to `plot_structure_3d()` via `structure_canon` parameter
   - Reuses the same canonicalized structure for atom/bond counting
   - **Result**: `canonicalize_structure_in_place()` is now called exactly once

**Files Modified**:
- `src/quantumvitas/analysis/structure_viz.py`:
  - `plot_structure_3d()`: Added `structure_canon` parameter (lines 1520, 1536-1538)
  - `visualize_structure()`: Removed duplicate canonicalization, passes pre-canonicalized structure (lines 1762-1764, 1770)
  - Updated documentation comment (line 161)

### B. Added Shifted-Wrap Canonicalization Helper

**New Function**: `wrap_fractional_coords_shifted()`

**Location**: `src/quantumvitas/analysis/structure_viz.py:351`

**Signature**:
```python
def wrap_fractional_coords_shifted(
    frac: np.ndarray,
    wrap_tol: float = 0.0,
) -> np.ndarray
```

**Algorithm**:
- Wraps fractional coordinates to `[lo, lo+1)` where `lo = -wrap_tol`
- Formula: `(f - lo) - floor(f - lo) + lo`
- **No snapping, rounding, or threshold-based nudging** (unlike `canonicalize_frac_coords()`)
- Only performs modulo wrapping with a shift (representative selection)

**Purpose**: 
- Representative selection only: adds/subtracts integers to bring coordinates into target range
- Does not change geometry except by lattice translations (equivalent in periodic systems)
- Provides a pure wrapping function without the snapping behavior of `canonicalize_frac_coords()`

**Exported**: Added to `__all__` list (line 40)

### C. Updated Documentation

- Updated canonicalization contract comment to reflect that `plot_structure_3d()` now accepts pre-canonicalized structures (line 161)

## Testing

**New Test Class**: `TestCanonicalizationNoDouble` in `tests/unit/test_structure_viz.py`

**Tests Added**:

1. **`test_visualize_structure_no_double_canonicalize()`**:
   - Uses `unittest.mock` to count calls to `canonicalize_structure_in_place()`
   - Verifies that `visualize_structure()` calls canonicalization exactly once
   - Fails if double canonicalization is detected

2. **`test_plot_structure_3d_accepts_pre_canonicalized()`**:
   - Verifies that `plot_structure_3d()` accepts pre-canonicalized structure
   - Ensures no canonicalization occurs when `structure_canon` is provided
   - Validates backward compatibility (still works without `structure_canon`)

3. **`test_wrap_fractional_coords_shifted_no_snapping()`**:
   - Verifies that `wrap_fractional_coords_shifted()` does not snap values
   - Tests wrapping behavior with default range `[0, 1)`
   - Tests wrapping behavior with shifted range `[-0.1, 0.9)`
   - Confirms no snapping to 0.0 occurs

## Backward Compatibility

- **`plot_structure_3d()`**: Fully backward compatible
  - `structure_canon` parameter is optional (defaults to `None`)
  - If not provided, function canonicalizes as before
  - Existing callers continue to work without changes

- **`visualize_structure()`**: Behavior unchanged from caller's perspective
  - Still produces same results
  - Only internal implementation changed (eliminated duplicate canonicalization)

## Constraints Respected

✅ **No bond computation code paths modified**
✅ **No bond function signatures changed**
✅ **No metadata introduced (parent ids, etc.)**
✅ **Changes minimal and localized**
✅ **Existing data structures preserved**

## Verification

Run tests to verify:
```bash
pytest tests/unit/test_structure_viz.py::TestCanonicalizationNoDouble -v
```

Expected output: All tests pass, confirming:
- No double canonicalization in `visualize_structure()`
- `plot_structure_3d()` accepts pre-canonicalized structures
- `wrap_fractional_coords_shifted()` works correctly without snapping

