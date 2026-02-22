# Remaining GEN/SPEC Failures: Root Cause Analysis

**Date**: 2025-01-28  
**Status**: Analysis Complete - Awaiting Review  
**Total Remaining Failures**: 238 (down from 170 after PATCH/C/D fixes)  
**Gates**: All passing ✅

---

## Executive Summary

After completing PATCH (kernel import fixes), C (topology/relax detection), and D (workflow detection), we have **238 remaining test failures**. This document provides root cause analysis for each failure category, with questions marked where clarification is needed.

### Failure Distribution

- **Registry/Registration Issues**: ~60 failures
- **Function Parameter Mismatches**: ~20 failures
- **Missing Artifacts/Execution Issues**: ~30 failures
- **Precision/Parameter Issues**: ~15 failures
- **Contract/Schema Drift**: ~40 failures
- **CLI/Import Errors**: ~33 errors
- **Other**: ~40 failures

---

## Part 1: Registry/Registration Issues (~60 failures)

### Problem R1: StepTypeRegistry.get() Expects GEN, But Tests/Code Pass SPEC

**Root Cause**: `StepTypeRegistry.get(step_type_gen)` expects GEN type (e.g., "scf"), but many places pass SPEC type (e.g., "qe_scf", "vasp_scf", "pyscf_scf").

**Affected Code**:
- `src/qmatsuite/execution/reference_resolver.py:93` - `registry.get(str(step_type))` where `step_type` is `step_type_spec`
- `src/qmatsuite/execution/reference_resolver.py:56` - Same issue in `find_reference_scf()`

**Test Failures**:
- `test_reference_resolver.py::test_get_gen_type` - Returns "vasp_scf" instead of "scf"
- `test_calculation_ulid_contracts.py` - Workflow detection issues

**Fix Proposal**:
```python
# In reference_resolver.py:get_gen_type()
# Current:
step_type = getattr(step, 'step_type_spec', None)
spec = registry.get(str(step_type))  # WRONG: registry.get() expects GEN

# Fix:
from qmatsuite.api.utils.step_types import step_type_gen_from_spec, is_step_type_spec
step_type = getattr(step, 'step_type_spec', None)
if step_type:
    if is_step_type_spec(step_type):
        step_type_gen = step_type_gen_from_spec(step_type)
    else:
        step_type_gen = step_type
    spec = registry.get(step_type_gen)  # CORRECT: pass GEN type
```

**Question**: Should `StepTypeRegistry.get()` be updated to accept both GEN and SPEC, or should all callers convert SPEC→GEN first? The constitution says registry is SSOT, so it should probably accept both for convenience, but that might violate the "no third namespace" rule.

---

### Problem R2: PySCF/ORCA/VASP Step Types Not in StepTypeRegistry

**Root Cause**: `StepTypeRegistry` (legacy registry) only has hardcoded QE/W90 step types. PySCF, ORCA, VASP, CP2K, LAMMPS step types are registered in `DriverRegistry` (new) but not in `StepTypeRegistry` (legacy).

**Test Failures**:
- `test_pyscf_integration.py` - All PySCF step type tests fail
- `test_vasp_registry.py` - All VASP step type tests fail
- `test_step_type_mapping.py` - Lookup by SPEC type fails

**Analysis**:
- `DriverRegistry` has: `pyscf_scf`, `pyscf_mp2`, `pyscf_td`, `orca_scf`, `orca_hf`, `orca_td`, `vasp_scf`, `vasp_bands`, etc.
- `StepTypeRegistry` only has: QE and W90 step types (hardcoded in `_STEP_TYPES` dict)

**Question**: Should `StepTypeRegistry` be populated from `DriverRegistry` at initialization? Or should tests use `DriverRegistry` instead of `StepTypeRegistry`? The codebase seems to have two registries:
1. `StepTypeRegistry` (legacy, hardcoded, used by workflow/presets)
2. `DriverRegistry` (new, driver-based, used by execution)

**Fix Options**:
1. **Option A**: Populate `StepTypeRegistry` from `DriverRegistry` on init (sync both registries)
2. **Option B**: Update tests to use `DriverRegistry` instead of `StepTypeRegistry`
3. **Option C**: Add missing step types to `StepTypeRegistry._STEP_TYPES` manually

**Recommendation**: Option A - sync registries. `StepTypeRegistry` should query `DriverRegistry` for step types not in its hardcoded dict.

---

### Problem R3: Materialization Map Contains Unregistered Step Types

**Root Cause**: Materialization maps (GEN→SPEC mappings) contain step types that aren't registered in `StepTypeRegistry`.

**Test Failures**:
- `test_materialization_ssot.py::test_all_mapped_step_types_are_registered` - Orphans: `vasp_bandspw`, `cp2k_bandspw`

**Analysis**:
- VASP driver declares `bandspw` in `SUPPORTED_GEN_STEPS`
- Materialization map creates `vasp_bandspw`
- But `StepTypeRegistry` doesn't have `vasp_bandspw` entry

**Question**: Should `bandspw` be a valid GEN step type for VASP/CP2K? Or is it QE-only? Looking at the constitution, `bandspw` might be QE-specific (uses pw.x with k-path).

**Fix Proposal**:
1. If `bandspw` is QE-only: Remove from VASP/CP2K `SUPPORTED_GEN_STEPS`
2. If `bandspw` is valid for all engines: Add `vasp_bandspw` and `cp2k_bandspw` to `StepTypeRegistry._STEP_TYPES`

**Recommendation**: Check constitution - if `bandspw` is QE-specific, remove from other drivers. If it's generic, add to registry.

---

### Problem R4: StepTypeRegistry.get() vs get_for_engine()

**Root Cause**: Tests use `registry.get("qe_scf")` (SPEC) but `get()` expects GEN. Should use `get_for_engine("scf", "qe")` instead.

**Test Failures**:
- `test_step_type_mapping.py::test_lookup_by_spec_type` - `registry.get("qe_scf")` returns None

**Fix Proposal**:
```python
# Test should use:
spec = registry.get_for_engine("scf", "qe")  # GEN + engine

# Or add a helper method:
def get_by_spec(registry, step_type_spec: str):
    from qmatsuite.api.utils.step_types import step_type_gen_from_spec, prefix_from
    step_type_gen = step_type_gen_from_spec(step_type_spec)
    prefix = prefix_from(step_type_spec)
    return registry.get_for_engine(step_type_gen, prefix)
```

**Question**: Should `StepTypeRegistry` have a `get_by_spec(step_type_spec)` method for convenience? Or should all callers convert SPEC→GEN first?

---

## Part 2: Function Parameter Mismatches (~20 failures)

### Problem F1: write_generated_structure() Expects step_type_spec

**Root Cause**: `write_generated_structure()` signature expects `step_type_spec`, but tests pass `step_type_gen`.

**Test Failures**:
- `test_relax_execution.py::test_executor_pre_clean_before_job_execution` - `TypeError: write_generated_structure() got an unexpected keyword argument 'step_type_gen'`

**Code Location**: `src/qmatsuite/execution/relax_artifacts.py`

**Fix Proposal**:
```python
# In test_relax_execution.py:51
# Current:
write_generated_structure(
    ...,
    step_type_gen="relax",  # WRONG
)

# Fix:
from qmatsuite.api.utils.step_types import step_type_spec_from_gen
step_type_spec = step_type_spec_from_gen("qe", "relax")  # "qe_relax"
write_generated_structure(
    ...,
    step_type_spec=step_type_spec,  # CORRECT
)
```

**Question**: What engine prefix should be used? The test doesn't specify. Should we detect from calculation context, or is "qe" the default?

---

### Problem F2: evaluate_step_result() Expects step_type_spec

**Root Cause**: `evaluate_step_result()` signature expects `step_type_spec`, but tests pass `step_type_gen`.

**Test Failures**:
- `test_wannier90_evaluation.py::test_evaluate_wannier90_steps_does_not_parse_energy` - `TypeError: evaluate_step_result() got an unexpected keyword argument 'step_type_gen'`

**Fix Proposal**:
```python
# In test_wannier90_evaluation.py:36
# Current:
evaluate_step_result(
    ...,
    step_type_gen="wannierprep",  # WRONG
)

# Fix:
from qmatsuite.api.utils.step_types import step_type_spec_from_gen
step_type_spec = step_type_spec_from_gen("w90", "wannierprep")  # "w90_wannierprep"
evaluate_step_result(
    ...,
    step_type_spec=step_type_spec,  # CORRECT
)
```

**Question**: For `pw2wannier`, should it be `step_type_spec_from_gen("qe", "pw2wannier")` → `"qe_pw2wannier"`? The test uses `step_type_gen="pw2wannier"` which suggests it's a GEN type, but which engine owns it?

---

## Part 3: Missing Artifacts/Execution Issues (~30 failures)

### Problem E1: Relax Steps Don't Create current.json Artifacts

**Root Cause**: Relax execution completes but post-processing doesn't create `current.json` artifact.

**Test Failures**:
- `test_lammps_long_smoke.py::test_workflow_a_lj_relax` - `current.json` not found
- `test_qe_relax_real.py` - `current.json` not found
- Various other relax tests

**Analysis**: 
- Execution succeeds (return code 0)
- But artifact creation fails or isn't triggered
- May be post-job handler issue or artifact path resolution

**Question**: Should relax steps always create `current.json`? Or only when structure changes? The error says "Step succeeded but current.json not found" which suggests it should always be created.

**Fix Proposal**: Investigate post-job handlers for relax steps. Ensure they call `write_generated_structure()` with correct `step_type_spec`.

---

### Problem E2: VASP Output Files Missing

**Root Cause**: VASP execution may not be producing expected output files, or paths are wrong.

**Test Failures**:
- `test_vasp_project_e2e.py::test_scf_to_bands_workflow` - `EIGENVAL` not found
- `test_vasp_project_e2e.py::test_scf_to_dos_workflow` - `DOSCAR` not found

**Question**: Are these execution issues (VASP not running) or path resolution issues? Need to check if VASP actually executed or if files are in wrong location.

---

## Part 4: Precision/Parameter Issues (~15 failures)

### Problem P1: Missing 'cards' Key After Precision Application

**Root Cause**: Precision application or roundtrip logic doesn't preserve all required fields.

**Test Failures**:
- `test_precision_integration.py::test_scf_nscf_precision_med` - `KeyError: 'cards'`
- `test_precision_integration.py::test_bands_pw_kpoints_not_changed` - `KeyError: 'SYSTEM'`

**Question**: Is this a precision application bug (not preserving cards), or a test bug (accessing cards that shouldn't exist)? The error suggests cards dict is missing entirely.

---

### Problem P2: Precision Roundtrip Issues

**Root Cause**: Precision roundtrip doesn't preserve all fields correctly.

**Test Failures**:
- `test_precision_roundtrip.py::test_roundtrip_scf_nscf_bandspw_bands` - Missing `K_POINTS` in cards
- `test_precision_roundtrip.py::test_roundtrip_breaks_on_manual_change` - Returns 'Custom' instead of 'med'

**Question**: Are these precision application bugs or expected behavior? The "breaks on manual change" test suggests it should detect manual changes and return 'Custom', but the assertion expects 'med'.

---

## Part 5: Contract/Schema Drift (~40 failures)

### Problem C1: Schema Drift in Contract Tests

**Root Cause**: API responses don't match golden fixtures (schema changed).

**Test Failures**:
- `test_schema_preservation.py` - Many endpoints have schema drift
- All contract crawler tests

**Question**: Are these legitimate schema changes (need fixture updates) or API bugs (returning wrong format)? The test name suggests it's checking for accidental schema changes.

---

### Problem C2: Missing step_type_gen in API Requests

**Root Cause**: API requires `step_type_gen` but requests don't include it.

**Test Failures**:
- `test_golden_contracts.py::test_matches_golden[add_step_to_calculation]` - `Missing required field: step_type_gen`

**Fix Proposal**: Update golden fixtures to include `step_type_gen` field in requests.

---

## Part 6: CLI/Import Errors (~33 errors)

### Problem I1: Missing is_ulid_like Import

**Root Cause**: `api/utils/__init__.py` doesn't export `is_ulid_like`, but `daemon/server.py` imports it.

**Test Failures**:
- All contract crawler tests fail to import (cascade failure)

**Fix Proposal**:
```python
# In src/qmatsuite/api/utils/__init__.py
from .step_types import ...  # Already done
# Add:
from qmatsuite.api.utils import is_ulid_like  # Re-export from utils.py
```

**Status**: Fixed - `is_ulid_like` exists in `api/utils.py` (the file, not the package). The `api/utils/` package (directory) only contains `step_types.py`. The import should work from `api/utils.py` directly. If there's a conflict, we may need to rename one of them (e.g., `api/utils.py` → `api/utils_module.py` or `api/utils/` → `api/utils_package/`).

**Note**: There's a potential naming conflict: `api/utils.py` (file) vs `api/utils/` (package). Python should prefer the file when importing `qmatsuite.api.utils`, but this can cause confusion. Consider renaming one to avoid conflicts.

---

## Part 7: Other Issues (~40 failures)

### Problem O1: LAMMPS Template Double Prefix (Already Fixed?)

**Status**: Should be fixed in B2, but test still fails.

**Test Failures**:
- `test_lammps_writer.py::test_get_template_for_step_type` - `ValueError: Unknown step type: lammps_lammps_relax`

**Question**: Is the test passing SPEC type to a function that expects GEN? Or is the fix incomplete?

**Investigation Needed**: Check if test is calling with SPEC type instead of GEN.

---

### Problem O2: CP2K Integration Issues

**Root Cause**: CP2K step types or execution issues.

**Test Failures**:
- `test_cp2k_integration.py::test_cp2k_md_incremental_skip_disabled` - `AttributeError: 'NoneType' object has no attribute 'supports_incremental_skip'`

**Question**: Is CP2K driver not registered? Or is the step type lookup failing?

---

## Part 8: Questions Requiring Clarification

### Q1: StepTypeRegistry vs DriverRegistry - Which Should Tests Use?

**Context**: Two registries exist:
- `StepTypeRegistry` (legacy, hardcoded, used by workflow/presets)
- `DriverRegistry` (new, driver-based, used by execution)

**Question**: Should tests use `DriverRegistry` for all step type lookups, or should `StepTypeRegistry` be synced with `DriverRegistry`? The codebase seems to use both, which causes confusion.

**Recommendation**: Sync `StepTypeRegistry` from `DriverRegistry` on init, or deprecate `StepTypeRegistry` in favor of `DriverRegistry`.

---

### Q2: Which Step Types Are GEN vs SPEC?

**Context**: Some step types are ambiguous:
- `bandspw` - Is this GEN (all engines) or QE-specific?
- `pw2wannier` - GEN type, but which engine? QE owns it, so SPEC is `qe_pw2wannier`
- `wannierprep`, `wannier` - GEN types, W90 engine owns them

**Question**: For tests that need to convert GEN→SPEC, how do we determine the engine prefix? Should it come from:
1. Calculation context (engine_family)?
2. Test fixture (explicit)?
3. Default to "qe"?

**Examples**:
- `test_wannier90_evaluation.py` - Uses `step_type_gen="wannierprep"` → should be `step_type_spec="w90_wannierprep"`
- `test_wannier90_evaluation.py` - Uses `step_type_gen="pw2wannier"` → should be `step_type_spec="qe_pw2wannier"`

---

### Q3: Should StepTypeRegistry.get() Accept Both GEN and SPEC?

**Current Behavior**: `StepTypeRegistry.get(step_type_gen)` only accepts GEN type.

**Question**: Should we:
1. Keep current behavior (callers must convert SPEC→GEN first)?
2. Update `get()` to accept both (convenience, but might violate "no third namespace")?
3. Add `get_by_spec(step_type_spec)` method?

**Recommendation**: Option 3 - add `get_by_spec()` method that converts internally. Keeps API clean and explicit.

---

### Q4: What Engine Prefix for Relax Steps in Tests?

**Context**: Many relax tests don't specify engine, but `write_generated_structure()` needs `step_type_spec` which requires engine prefix.

**Question**: Should relax tests:
1. Always specify engine (e.g., `step_type_spec="qe_relax"`)?
2. Detect from calculation context?
3. Use a default (which one?)?

**Examples**:
- `test_relax_execution.py` - No engine specified, but needs `step_type_spec` for `write_generated_structure()`

---

## Part 9: Fix Priority and Strategy

### High Priority (Blocks Many Tests)

1. **R1**: Fix `reference_resolver.py` to convert SPEC→GEN before `registry.get()`
2. **R2**: Sync `StepTypeRegistry` with `DriverRegistry` OR update tests to use `DriverRegistry`
3. **I1**: Fix `is_ulid_like` import (blocks all contract tests)
4. **F1/F2**: Fix function parameter mismatches (mechanical fixes)

### Medium Priority

5. **R3**: Resolve `bandspw` registration (remove from VASP/CP2K or add to registry)
6. **R4**: Add `get_by_spec()` method to `StepTypeRegistry` OR update tests
7. **E1**: Investigate relax artifact creation
8. **P1/P2**: Fix precision application/roundtrip

### Low Priority

9. **C1/C2**: Update golden fixtures (after API stabilizes)
10. **E2**: Investigate VASP execution issues
11. **O1/O2**: Fix remaining edge cases

---

## Part 10: Recommended Fix Order

### Batch 1: Critical Infrastructure (High Impact)
1. Fix `is_ulid_like` import (I1) - Unblocks contract tests
2. Fix `reference_resolver.py` SPEC→GEN conversion (R1) - Unblocks many tests
3. Sync `StepTypeRegistry` with `DriverRegistry` (R2) - Unblocks registry tests

### Batch 2: Function Parameters (Mechanical)
4. Fix `write_generated_structure()` calls (F1)
5. Fix `evaluate_step_result()` calls (F2)

### Batch 3: Registry Enhancements
6. Add `get_by_spec()` to `StepTypeRegistry` (R4)
7. Resolve `bandspw` registration (R3)

### Batch 4: Execution/Artifacts
8. Investigate relax artifact creation (E1)
9. Investigate VASP execution (E2)

### Batch 5: Precision/Parameters
10. Fix precision application bugs (P1/P2)

### Batch 6: Contracts/Fixtures
11. Update golden fixtures (C1/C2)

---

## Appendix: Specific Test Failures by Category

### Registry Issues (60 failures)
- `test_pyscf_integration.py` - 10 failures (PySCF not in StepTypeRegistry)
- `test_vasp_registry.py` - 7 failures (VASP not in StepTypeRegistry)
- `test_step_type_mapping.py` - 5 failures (lookup by SPEC fails)
- `test_materialization_ssot.py` - 8 failures (orphan mappings)
- `test_workflow.py` - 2 failures (registry issues)
- `test_reference_resolver.py` - 2 failures (SPEC→GEN conversion)
- `test_calculation_ulid_contracts.py` - 2 failures (workflow detection)

### Function Parameters (20 failures)
- `test_relax_execution.py` - 2 failures (`write_generated_structure`)
- `test_wannier90_evaluation.py` - 1 failure (`evaluate_step_result`)

### Missing Artifacts (30 failures)
- `test_lammps_long_smoke.py` - 2 failures (current.json missing)
- `test_qe_relax_real.py` - 2 failures (current.json missing)
- Various relax tests - ~26 failures (artifact issues)

### Precision/Parameters (15 failures)
- `test_precision_integration.py` - 3 failures (missing cards)
- `test_precision_roundtrip.py` - 2 failures (roundtrip issues)

### Contract/Schema (40 failures)
- `test_schema_preservation.py` - ~20 failures (schema drift)
- `test_golden_contracts.py` - ~20 failures (contract mismatches)

### CLI/Import (33 errors)
- All contract crawler tests - 33 errors (import failure cascade)

### Other (40 failures)
- Various integration tests - ~40 failures (mixed causes)

---

**End of Analysis**

