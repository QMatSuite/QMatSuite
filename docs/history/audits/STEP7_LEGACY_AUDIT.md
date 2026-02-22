# Step 7: Legacy Code Paths Audit

## Summary

Audited codebase for legacy code paths that should be removed according to R0-R4 rules.

## Findings

### ✅ No Legacy Code Found

**Search Results**:
- ✅ No code accepts `parameters.k_points` as input (all code uses `cards.K_POINTS`)
- ✅ Step-level pseudo mapping is only used for **backwards compatibility during migration** (correct)
- ✅ CLI correctly routes `--k_points` to `card_overrides` (not `parameter_map`)

### Code Review Details

#### 1. K_POINTS Handling ✅
- **CLI** (`src/qmatsuite/cli/main.py:377`): Routes `--k_points` to `card_overrides` (correct)
- **Input Generation**: All code paths use `cards.K_POINTS` 
- **Parser**: Only parses `K_POINTS` as a card (never as namelist)
- **Generator**: Only generates `K_POINTS` as a card format

**Conclusion**: No legacy code to remove. All code correctly treats `K_POINTS` as a card.

#### 2. Step-Level Pseudo Mapping ✅
- **Current Usage**:
  - `src/qmatsuite/project/snapshot.py`: Migration from step-level to calc-level (legitimate use)
  - `src/qmatsuite/core/pseudo.py`: Error messages reference step-level for diagnostics (acceptable)
  - `src/qmatsuite/api.py`: Temporary step-level pseudo setting during import (acceptable)

**Conclusion**: All uses are for **backwards compatibility** or **diagnostic purposes**. No code relies on step-level pseudo mapping as the primary source of truth. The primary source is `calculation.species_map` (R1 compliance).

#### 3. Prefix/Outdir Handling ✅
- **Injection Logic**: Correctly injects from `calculation.meta.slug` (R1-R4 compliance)
- **Step-Level Values**: Correctly ignored at runtime
- **Schema**: Step-level prefix/outdir removed from exported demos (correct)

**Conclusion**: No legacy code to remove. All code correctly implements calculation-level injection.

## Recommendations

### ✅ No Action Required

All code paths are compliant with R0-R4 rules:
- R0: No deprecations needed (no legacy paths found)
- R1: Pseudopotentials only in `calculation.species_map` (runtime behavior correct)
- R2: `K_POINTS` only as card (no namelist handling found)
- R3: Demos reproducible from generators (fixed in Step 2)
- R4: Prefix/outdir from calculation.meta.slug (correctly implemented)

### Optional Cleanup (Low Priority)

1. **Error Messages**: Some error messages in `src/qmatsuite/core/pseudo.py` reference step-level pseudo mapping for diagnostic purposes. These are acceptable but could be updated to only reference `species_map` for consistency.

2. **Comments**: Some comments mention step-level pseudo mapping for backwards compatibility. These are accurate documentation and should remain.

## Test Coverage

All schema validation tests confirm:
- ✅ No `parameters.k_points` in demos
- ✅ No step-level `pseudopot` fields in demos
- ✅ No step-level `prefix`/`outdir` in demos
- ✅ `K_POINTS` correctly rendered as cards

## Conclusion

**Step 7 Status**: ✅ COMPLETE (no legacy code found, all code paths compliant)

No deprecated code paths need to be removed. The codebase is already compliant with R0-R4 rules.

