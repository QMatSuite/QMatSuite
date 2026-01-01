# ParamSpace Invariant-Aware Apply - Final Verification

## Summary

Phase 6 (Tests) and Phase 7 (Code Review) have been completed successfully.

## Phase 6 - Tests ✅

All 8 tests in `tests/unit/test_paramspace_invariants.py` pass:

### Group A — Occupation → Precision (Invariant Enforcement)
- ✅ **test_a1_smearing_to_fixed_deletes_degauss**: smearing → fixed deletes degauss (precision untouched)
- ✅ **test_a2_precision_custom_still_deletes_degauss**: precision CUSTOM still deletes degauss when not applicable

### Group B — Strategy A (No Auto-fill)
- ✅ **test_b1_smearing_plus_precision_preset_writes_degauss**: smearing + precision preset writes degauss (LOW/MED/HIGH → 0.01/0.02/0.03)
- ✅ **test_b2_smearing_no_precision_apply_does_not_auto_fill**: smearing + no precision apply does NOT auto-fill degauss

### Group C — Detect Behavior (No Regression)
- ✅ **test_c1_smearing_missing_degauss_detect_custom**: smearing + missing degauss → detect CUSTOM
- ✅ **test_c2_fixed_plus_degauss_present_detect_custom**: fixed + degauss present → detect CUSTOM

### Group D — Apply Order / Oracle Truth
- ✅ **test_d1_oracle_reads_updated_yaml_not_stale_state**: oracle reads updated YAML, not stale state
- ✅ **test_d2_apply_order_occupation_before_precision**: apply order correctness (occupation before precision)

## Phase 7 - Code Review Checklist ✅

### ParamSpace
- ✅ Every ParamSpace has `apply_invariants()` (default no-op)
  - Verified in `src/quantumvitas/presets/paramspace.py:140`
  - Precision ParamSpace overrides it (line 745)
- ✅ No invariant logic inside detect
  - Verified: degauss deletion is in `apply_invariants()`, not in detect functions
  - Detect functions only read, never mutate
- ✅ No ParamSpace writes keys it does not own
  - Verified: degauss is only written/deleted by Precision ParamSpace
  - OccupationsScheme ParamSpace does not write degauss (only detects it in profiles)

### Precision
- ✅ degauss deletion happens ONLY in PrecisionParamSpace
  - Verified in `src/quantumvitas/presets/paramspace.py:755-760`
- ✅ deletion happens even when precision is CUSTOM
  - Verified: `apply_invariants()` is called unconditionally (line 674 in integration.py)
  - Test `test_a2_precision_custom_still_deletes_degauss` confirms this
- ✅ preset match is NOT required for deletion
  - Verified: invariant enforcement runs for all ParamSpaces regardless of preset application

### Oracle
- ✅ Oracle only reads parsed YAML
  - Verified in `src/quantumvitas/presets/oracle.py:44-54`
  - Only reads `SYSTEM.occupations` from `yaml_state`
- ✅ Oracle does NOT read preset IDs or detect results
  - Verified: Oracle has no access to preset IDs or detect results
  - Only reads YAML truth
- ✅ Oracle returns only bool / small enum
  - Verified: `degauss_applicability()` returns `bool` (line 32)

### Apply Scheduler
- ✅ prerequisite ParamSpaces execute before precision
  - Verified in `src/quantumvitas/presets/integration.py:413-548`
  - Phase 1: prerequisite dimensions (occupations_scheme, magnetism)
  - Phase 2: dependent dimensions (precision)
- ✅ `apply_invariants()` is ALWAYS called
  - Verified in `src/quantumvitas/presets/integration.py:672-674`
  - Called for all ParamSpaces in SPACES registry, unconditionally
- ✅ no "skip apply when CUSTOM" logic exists
  - Verified: No conditional logic that skips `apply_invariants()` when CUSTOM
  - Comment on line 670: "This ensures invariant enforcement runs even when CUSTOM"

## Absolute Rules Verification ✅

- ✅ Do NOT refactor precision math
  - Verified: Precision math unchanged, only added degauss writing logic
- ✅ Do NOT simplify structure/pseudo handling
  - Verified: Tests use same structure/pseudo setup as existing precision tests
- ✅ Do NOT introduce shared writers
  - Verified: degauss is owned exclusively by Precision ParamSpace
- ✅ Do NOT add guards or secondary detectors
  - Verified: No guards or secondary detectors added

## Final Verification ✅

- ✅ Precision CUSTOM still deletes degauss when not applicable
  - Test `test_a2_precision_custom_still_deletes_degauss` confirms
- ✅ smearing does NOT auto-fill degauss
  - Test `test_b2_smearing_no_precision_apply_does_not_auto_fill` confirms
- ✅ No existing precision tests break
  - All existing tests pass (verified with test run)
- ✅ All new tests pass
  - All 8 tests in `test_paramspace_invariants.py` pass

## Implementation Files

### Core Implementation
- `src/quantumvitas/presets/oracle.py` - Oracle implementation
- `src/quantumvitas/presets/paramspace.py` - ParamSpace API extension + Precision invariant enforcement
- `src/quantumvitas/presets/integration.py` - Apply scheduler with phased execution
- `src/quantumvitas/presets/variants_registry.py` - Precision degauss writing logic

### Tests
- `tests/unit/test_paramspace_invariants.py` - Comprehensive invariant enforcement tests

### Documentation
- `docs/paramspace_constitution_cn.md` - Constitution (Chinese)
- `docs/paramspace_apply_plan.md` - Implementation plan with checklists
- `docs/paramspace_invariants_verification.md` - This verification document

## Conclusion

All requirements from Phase 6 and Phase 7 have been met. The implementation follows the ParamSpace Constitution v1 exactly, and all tests pass. The system is ready for merge.

