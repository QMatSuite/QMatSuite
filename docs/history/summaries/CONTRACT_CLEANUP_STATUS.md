# Contract Cleanup Status (Phase 3C)

**Date**: 2025-01-10  
**Status**: Core contracts fixed, verification refactoring deferred

## Completed Contract Fixes

### Contract I1: Step ULID Stability ✅
**Status**: FIXED

**Problem**: Step ULIDs were changing between fixture creation and execution because `_build_step` was calling `_build_step_meta()` which generated new ULIDs instead of using the ULID from step.yaml.

**Solution**: Modified `_build_step()` in `src/qmatsuite/calculation/calculation.py` to use `step_resolved.meta` directly (from step.yaml) instead of calling `_build_step_meta()` with `step_data` from calculation.yaml. Added assertion to ensure ULID consistency.

**Files Changed**:
- `src/qmatsuite/calculation/calculation.py`: `_build_step()` function

**Documentation**: See `docs/design/CONTRACT_I1_STEP_ULID_FIX.md`

### Contract I2: Artifact Directory Contract ✅
**Status**: VERIFIED (was already correct)

**Requirement**: Artifact paths must be `raw/step_artifacts/{step_ulid}/`, keyed by step ULID (not step_type).

**Status**: Confirmed correct implementation in `src/qmatsuite/calculation/runner.py`:
```python
step_artifacts_dir = raw_dir / "step_artifacts" / step.meta.id
```

This ensures multiple steps of the same type have separate artifact directories.

### Contract I3: Structure Handling ✅
**Status**: VERIFIED (already correct)

**Requirement**: Structure is defined ONLY at calculation level. Engine must resolve structure via canonical structure loader (`read_structure`), NOT via `step.options` hacks.

**Status**: Verified correct implementation in `src/qmatsuite/engine/pyscf_engine.py`:
- Structure is resolved canonically using `structure_id` and `project_root` from `step.options`
- Engine calls `require_structure()` and `read_structure()` (canonical resolution)
- No structure data stored in step.yaml
- Structure_id comes from `calculation.structure_id` (passed via `step.options` as transport mechanism)

## Deferred Contract Improvements

### Contract I4: Engine-Driven Verification ⚠️
**Status**: DEFERRED (acceptable temporarily, needs refactoring)

**Requirement**: Verification logic should be engine-driven (e.g., `Engine.verify_step_done(step_dir, step_spec)`), not step-type string matching.

**Current State**: `evaluate_step_result()` in `src/qmatsuite/calculation/verification.py` uses step-type string matching:
- Lines 127-147: Hardcoded set of PySCF step type strings
- Lines 106-124: Hardcoded set of Wannier90 step type strings
- Lines 149+: QE steps (default path)

**Future Refactoring** (not blocking Phase 3C):
1. Add `verify_step_done(step_dir, step_spec)` method to `Engine` base class
2. Implement in `QeEngine`, `PySCFEngine`, `Wannier90Engine`
3. Refactor `evaluate_step_result()` to call engine's verification method instead of branching on step_type strings

**Documentation**: This is documented as a known limitation. The current implementation works correctly but is not principled.

## Tests Status

### Integration Tests
- `test_t1_runcalc_incremental_uses_chkfile`: ✅ PASSING (after ULID fix)

### Regression Tests Needed
- Step ULID stability across materialize + execution
- Engine routing via `calculation.engine_family`
- Artifact dir keyed by `step_ulid` (multiple steps of same type)

## Next Steps

1. Add regression tests for Contract I1 (ULID stability)
2. Add regression tests for Contract I2 (artifact directories)
3. Document Contract I4 refactoring in Phase 3C roadmap
4. Update `CHANGELOG_FOR_TEST_FIXES.md` with contract cleanup changes

