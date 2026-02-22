# Bug Fix: ibrav=12/-12 Structure Parsing for Graphene

## Issue

Demo `13_graphene` failed with:
```
ValueError: ibrav=12/-12 requires b, c, and cos(angle).
```

This was incorrectly labeled as a "data issue" but was actually a **parser bug**.

## Root Cause

The `_ibrav_vectors` function in `src/qmatsuite/io/structure_io.py` had incorrect parameter mapping for ibrav=12:

- **Bug**: For `ibrav=12`, it was looking for `cosbc` (cos of angle between b and c)
- **Correct**: For `ibrav=12` (monoclinic, unique axis c), it should use `cosab` (cos of angle between a and b)

According to QE documentation:
- `ibrav=12`: Monoclinic, unique axis c. Uses cos(γ) where γ is the angle between a and b vectors.
- `ibrav=-12`: Monoclinic, unique axis b. Uses cos(β) where β is the angle between a and c vectors.

## Fix

**File**: `src/qmatsuite/io/structure_io.py`

**Change**: In `_ibrav_vectors` function, line 626:
```python
# Before (incorrect):
if ibrav == 12:
    cos_angle = params.get("cosbc")  # WRONG

# After (correct):
if ibrav == 12:
    cos_angle = params.get("cosab")  # cos(gamma) = cos(angle between a and b)
```

## Verification

### Test Results
All 6 unit tests pass:
- ✅ `test_graphene_input_has_correct_system_parameters`
- ✅ `test_extract_ibrav_parameters_for_graphene`
- ✅ `test_ibrav12_vectors_for_graphene`
- ✅ `test_graphene_structure_creation`
- ✅ `test_ibrav12_case_insensitive_parameters`
- ✅ `test_ibrav_minus12_uses_cosac`

### Demo Generation
```bash
python tools/import_tutorial_datasets.py
# Result: ✅ 13_graphene demo generated successfully

python tools/verify_demos.py
# Result: ✅ All 16 demos are valid (including 13_graphene.yml)
```

### Normalized SYSTEM Dict
For `graphene.1_vc_relax.in`:
```python
{
    'ibrav': 12,
    'a': 2.46,
    'b': 2.46,
    'c': 20,
    'cosab': -0.5  # ✅ Correctly extracted
}
```

### Generated Lattice Vectors
```python
v1 = [2.46,   0.0,    0.0]    # (a, 0, 0)
v2 = [-1.23,  2.1304, 0.0]    # (b*cos(120°), b*sin(120°), 0) ✅
v3 = [0.0,    0.0,    20.0]   # (0, 0, c)
```

## Impact

- ✅ Demo `13_graphene` now generates successfully
- ✅ All structure parsing tests pass
- ✅ No regressions in other ibrav types
- ✅ Case-insensitive parameter matching already in place (no changes needed)

## Files Modified

1. `src/qmatsuite/io/structure_io.py`: Fixed `_ibrav_vectors` to use `cosab` for ibrav=12
2. `tests/unit/test_graphene_ibrav12_parsing.py`: New comprehensive test suite
3. `docs/FAILED_DEMOS_REPORT.md`: Updated to reflect fix
4. `docs/BUGFIX_IBRAV12_GRAPHENE.md`: This documentation

