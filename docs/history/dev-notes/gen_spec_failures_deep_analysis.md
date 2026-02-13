# GEN/SPEC Failures Deep Analysis & Fix Proposals

**Date**: 2025-01-28  
**Status**: Analysis Complete - Awaiting Review  
**Total Test Failures**: 170 (down from 250+ after Bucket A/B fixes)  
**Gate Failures**: 5

---

## Executive Summary

After completing Bucket A (function parameter mismatches) and Bucket B (wrong step type namespace), we have **170 remaining test failures** and **5 gate failures**. This document provides deep code review and fix proposals for all remaining issues.

### Failure Distribution

- **Bucket C (Undefined Variables)**: ~15 failures
- **Registry/Registration Issues**: ~40 failures  
- **Topology/Chain Dependencies**: ~30 failures
- **Contract/Golden Fixture Mismatches**: ~20 failures
- **Precision/Parameter Issues**: ~15 failures
- **Execution/Artifact Issues**: ~20 failures
- **Other**: ~30 failures

---

## Part 1: Bucket C - Undefined Variables and Bare step_type

### C1: Undefined `step_type` Variable in Tests

#### Problem C1.1: `test_precision_detection_custom.py:100`

**Location**: `tests/integration/test_precision_detection_custom.py:100`

**Code**:
```python
precision_advice = advisor.advise_for_step(PrecisionOption.MED, step_type)
```

**Issue**: Variable `step_type` is undefined. Looking at context, it should be `"scf"` (GEN type).

**Root Cause**: Test was written assuming `step_type` would be available from earlier context, but it's not defined.

**Fix Proposal**:
```python
# Line 100: Replace undefined step_type with explicit GEN type
precision_advice = advisor.advise_for_step(PrecisionOption.MED, "scf")
```

**Decision**: **FIX** - Simple undefined variable, should use explicit GEN type `"scf"`.

---

#### Problem C1.2: `test_incremental_run.py:585`

**Location**: `tests/integration/test_incremental_run.py:585`

**Code**:
```python
step_type_gen=step_type,
```

**Issue**: Variable `step_type` is undefined. Looking at context (line 580-590), this is inside a test that creates a duplicate step. The original step type should come from `step_ids[1]` or be explicitly `"nscf"`.

**Root Cause**: Test creates a copy of step `step_ids[1]` but doesn't extract its step type before using it.

**Fix Proposal**:
```python
# Around line 580-585: Extract step_type_gen from existing step
# Option 1: Read from step YAML
step1_path = calc_dir / "steps" / f"{step_ids[1]}.step.yaml"
step1_data = yaml.safe_load(step1_path.read_text())
step_type_gen = step1_data.get("step_type_gen", "nscf")  # Default to nscf if missing

# Option 2: Use explicit value (simpler)
step_type_gen = "nscf"  # Since test creates nscf-copy
```

**Decision**: **FIX** - Use explicit `"nscf"` since test comment says "nscf-copy".

---

#### Problem C1.3: `test_relax_execution.py:55` and `test_wannier90_evaluation.py:38`

**Location**: Multiple locations

**Issue**: Functions called with `step_type_gen=` parameter but function signature expects `step_type_spec=`.

**Examples**:
- `write_generated_structure(step_type_gen="relax", ...)` → should be `step_type_spec="qe_relax"`
- `evaluate_step_result(step_type_gen="wannierprep", ...)` → should be `step_type_spec="w90_wannierprep"` OR function should accept `step_type_gen`

**Root Cause**: These are **Bucket A issues** that were missed. Functions in execution layer expect SPEC types.

**Fix Proposal**:

1. **For `write_generated_structure`** (execution layer):
   ```python
   # Change from:
   write_generated_structure(..., step_type_gen="relax", ...)
   # To:
   write_generated_structure(..., step_type_spec="qe_relax", ...)
   ```

2. **For `evaluate_step_result`** (verification layer):
   - **Function Signature**: `evaluate_step_result(mode, step_type_spec: str, ...)`
   - **Analysis**: Function expects `step_type_spec` (SPEC type), but docstring says "also accepts gen types for backward compat". Implementation handles both by checking for underscore.
   - **Test Issue**: `test_wannier90_evaluation.py` calls with `step_type_gen="wannierprep"` but function expects `step_type_spec`.
   - **Fix**: Tests should pass SPEC types, or convert GEN to SPEC before calling.

**Fix Proposal**:
```python
# In test_wannier90_evaluation.py
from quantumvitas.workflow.step_type_convert import spec_from

# For wannierprep (W90 engine):
step_type_spec = spec_from("w90", "wannierprep")  # "w90_wannierprep"
step_status, message, metrics = evaluate_step_result(
    mode=StepMode.NORMAL,
    step_type_spec=step_type_spec,  # Use SPEC type
    ...
)

# For wannier (W90 engine):
step_type_spec = spec_from("w90", "wannier")  # "w90_wannier"
...

# For pw2wannier (QE engine):
step_type_spec = spec_from("qe", "pw2wannier")  # "qe_pw2wannier"
...
```

**Decision**: **FIX** - Function expects `step_type_spec`, tests should convert GEN to SPEC before calling.

---

### C2: Bare `step_type` Field Access

#### Problem C2.1: Tests accessing `step.step_type` or `step["step_type"]`

**Pattern**: Tests access `step.step_type` which no longer exists.

**Root Cause**: Step objects now have `step_type_spec` and `step_type_gen` instead of bare `step_type`.

**Fix Strategy**: 
1. Identify all `step.step_type` accesses
2. Determine if test needs GEN or SPEC type
3. Replace with appropriate field

**Files to Check**:
- `tests/unit/test_reference_resolver.py` - May access `step.step_type`
- `tests/unit/test_calculation_ulid_contracts.py` - Accesses step types from YAML

**Decision**: **FIX** - Systematic search and replace based on context.

---

## Part 2: Gate Failures Deep Analysis

### Gate Failure G1: `test_registry_provides_both_mappings`

**Location**: `tests/gates/test_gen_spec_convergence_gate.py:109`

**Error**: `AssertionError: Registry missing gen→spec mapping`

**Code Analysis**:
```python
gen_to_spec = rg_count(r'step_type_spec\s*=\s*f"\{.*\}_\{.*\}"', "src/quantumvitas/core/driver_registry.py")
assert gen_to_spec > 0, "Registry missing gen→spec mapping"
```

**Root Cause**: The gate is looking for string formatting patterns like `f"{prefix}_{gen}"` in `driver_registry.py`, but the actual implementation may use `spec_from()` function instead.

**Investigation**:
- `DriverRegistry._build_materialization_map()` should use `spec_from(prefix, gen)`
- Gate may be too strict - it's looking for f-strings but code uses function calls

**Fix Proposal**:
1. **Option A**: Update gate to also accept `spec_from(prefix, gen)` pattern
2. **Option B**: Ensure `_build_materialization_map()` uses f-string pattern (less preferred)
3. **Option C**: Gate is checking wrong file - should check where materialization map is built

**Decision**: **INVESTIGATE** - Check `driver_registry.py` implementation. If it uses `spec_from()`, update gate pattern. If it doesn't use either, that's the bug.

---

### Gate Failure G2: Wannier90 Step Types Not Registered

**Locations**:
- `test_wannierprep_owned_by_w90` - `w90_wannierprep` not found
- `test_wannier_owned_by_w90` - `w90_wannier` not found  
- `test_pw2wannier_owned_by_qe` - `qe_pw2wannier` not found

**Error**: `AssertionError: w90_wannierprep must be registered`

**Code Analysis**:
Gate test uses `DriverRegistry.get_step_type_spec("w90_wannierprep")` which returns `None`.

**Investigation**:
1. **W90 Driver Registration**: `src/quantumvitas/drivers/w90/driver.py` has:
   ```python
   PREFIX: str = "w90"
   SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({"wannierprep", "wannier"})
   ```

2. **QE Driver Registration**: `src/quantumvitas/drivers/qe/driver.py` has:
   ```python
   PREFIX: str = "qe"
   SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({..., "pw2wannier", ...})
   ```

3. **Registry Implementation**: `DriverRegistry._build_materialization_map()` should create:
   - `w90_wannierprep` from `PREFIX="w90"` + `gen="wannierprep"`
   - `w90_wannier` from `PREFIX="w90"` + `gen="wannier"`
   - `qe_pw2wannier` from `PREFIX="qe"` + `gen="pw2wannier"`

4. **Legacy Registry**: `src/quantumvitas/workflow/registry.py` has hardcoded entries:
   ```python
   "w90_wannierprep": StepTypeSpec(...),
   "qe_pw2wannier": StepTypeSpec(...),
   "w90_wannier": StepTypeSpec(...),
   ```

**Root Cause Analysis**:
- **Two registries exist**: `DriverRegistry` (new) and `StepTypeRegistry` (legacy)
- Gate test uses `DriverRegistry` but step types may only be in `StepTypeRegistry`
- `DriverRegistry` builds from `PREFIX + SUPPORTED_GEN_STEPS` but may not be called during import
- Driver registration may not be happening at import time

**Fix Proposal**:

1. **Ensure Driver Registration on Import**:
   ```python
   # In src/quantumvitas/drivers/w90/__init__.py
   from .driver import W90Driver
   DriverRegistry.register(W90Driver())
   ```

2. **Verify `_build_materialization_map()` Implementation**:
   - Should use `spec_from(driver.PREFIX, gen)` for each `gen` in `SUPPORTED_GEN_STEPS`
   - Should register each SPEC type in `_step_types` dict

3. **Check Import Order**:
   - Ensure `quantumvitas.drivers` is imported before gate tests run
   - May need explicit import in gate test setup

**Decision**: **FIX** - This is a registration issue. Drivers must be registered on import, and `DriverRegistry` must build SPEC types from GEN types correctly.

---

### Gate Failure G3: Cross-Assignment Violations

**Location**: `tests/gates/test_step_type_cross_assignment.py:411`

**Violations Found** (7 total):

1. **`src/quantumvitas/workflow/registry.py:924`**
   ```python
   step_type_gen = step_type_str  # Fallback if conversion fails
   ```
   **Issue**: `step_type_str` may be SPEC type (has underscore), assigned to `step_type_gen` sink.
   **Fix**: Use `gen_from(step_type_str)` before assignment, or validate it's actually GEN.

2. **`src/quantumvitas/api/service.py:6984`**
   ```python
   step_entry = CalculationStepEntry(step_ulid=..., step_type_spec=machine_step_type)
   ```
   **Issue**: `machine_step_type` may be GEN type, assigned to `step_type_spec` sink.
   **Fix**: Convert to SPEC using `spec_from(engine_prefix, machine_step_type)` if it's GEN.

3. **`src/quantumvitas/presets/integration.py:318, 381`**
   ```python
   step_type_gen = step_type_spec  # Fallback if conversion fails
   ```
   **Issue**: SPEC type assigned to GEN sink as fallback.
   **Fix**: Use `gen_from(step_type_spec)` instead of direct assignment.

4. **`src/quantumvitas/engine/pyscf_engine.py:519, 546`**
   ```python
   step_type_gen = step_type_spec
   ```
   **Issue**: SPEC type assigned to GEN sink.
   **Fix**: Use `gen_from(step_type_spec)`.

5. **`tests/integration/test_incremental_run.py:585`**
   ```python
   step_type_gen=step_type,
   ```
   **Issue**: `step_type` variable undefined (covered in C1.2).

**Fix Proposals**:

**For registry.py:924**:
```python
# Current:
step_type_gen = step_type_str  # Fallback if conversion fails

# Fix:
from quantumvitas.workflow.step_type_convert import gen_from
try:
    step_type_gen = get_step_type_gen(step_type_str) if "_" in step_type_str else step_type_str
except (KeyError, ValueError):
    # Only use as fallback if it's actually GEN (no underscore)
    if "_" not in step_type_str:
        step_type_gen = step_type_str
    else:
        # It's SPEC, extract GEN
        step_type_gen = gen_from(step_type_str)
```

**For service.py:6984**:
```python
# Current:
step_entry = CalculationStepEntry(step_ulid=..., step_type_spec=machine_step_type)

# Fix:
from quantumvitas.workflow.step_type_convert import spec_from, is_spec
if is_spec(machine_step_type):
    step_type_spec = machine_step_type
else:
    # It's GEN, need engine prefix to convert
    # Get engine from calculation or step context
    engine_prefix = ...  # Extract from context
    step_type_spec = spec_from(engine_prefix, machine_step_type)
step_entry = CalculationStepEntry(step_ulid=..., step_type_spec=step_type_spec)
```

**For presets/integration.py:318, 381**:
```python
# Current:
step_type_gen = step_type_spec  # Fallback if conversion fails

# Fix:
from quantumvitas.workflow.step_type_convert import gen_from
try:
    step_type_gen = get_step_type_gen(step_type_spec)
except (KeyError, ValueError):
    step_type_gen = gen_from(step_type_spec)  # Extract GEN from SPEC
```

**For pyscf_engine.py:519, 546**:
```python
# Current:
step_type_gen = step_type_spec

# Fix:
from quantumvitas.workflow.step_type_convert import gen_from
step_type_gen = gen_from(step_type_spec)
```

**Decision**: **FIX ALL** - These are clear violations of the GEN/SPEC boundary. All need explicit conversion functions.

---

## Part 3: Test Failure Categories

### Category 1: Registry/Registration Issues (~40 failures)

#### Problem R1: Step Types Not Found in Registry

**Failures**:
- `test_pyscf_integration.py` - PySCF step types not registered
- `test_orca_integration.py` - ORCA step types not registered
- `test_vasp_registry.py` - VASP step types not registered
- `test_step_type_mapping.py` - Lookups fail

**Root Cause**: Similar to Gate G2 - `DriverRegistry` not properly registering step types, or tests using wrong registry.

**Investigation**:
- Tests may be using `StepTypeRegistry` (legacy) instead of `DriverRegistry` (new)
- Or `DriverRegistry` registration not happening
- Or step types not being built from `PREFIX + SUPPORTED_GEN_STEPS`

**Fix Proposal**:
1. Ensure all drivers are registered on import
2. Ensure `DriverRegistry._build_materialization_map()` creates all SPEC types
3. Update tests to use `DriverRegistry` instead of `StepTypeRegistry` where appropriate
4. Or ensure both registries are kept in sync

**Decision**: **FIX** - This is a critical infrastructure issue affecting many tests.

---

#### Problem R2: Materialization Map Issues

**Failures**:
- `test_materialization_ssot.py::test_all_mapped_step_types_are_registered` - Orphan mappings
- `test_generalized_steps.py::test_all_mappings_return_valid_step_type` - Invalid step types

**Root Cause**: Materialization maps contain step types that aren't registered in registry.

**Fix Proposal**: Ensure materialization map only contains step types that are registered.

---

### Category 2: Topology/Chain Dependency Issues (~30 failures)

#### Problem T1: "Requires SCF root but none found"

**Failures**: Many relax/MP2/TD tests fail with:
```
TOPOLOGY_ERROR: Step 'step_0' (index 0) requires SCF root but none found. Add an SCF step before this step.
```

**Examples**:
- `test_relax_promote_e2e.py` - Relax steps require SCF
- `test_pyscf_phase3c.py` - MP2/TD require SCF
- `test_orca_relax_real.py` - ORCA relax requires SCF
- `test_pyscf_relax_real.py` - PySCF relax requires SCF

**Root Cause**: Tests create relax/MP2/TD steps without creating prerequisite SCF steps first.

**Analysis**: 
- **Relax steps**: Constitution says relax is standalone, but implementation may require SCF
- **MP2/TD steps**: These definitely require SCF (chain dependencies)
- Tests need to create SCF step before relax/MP2/TD

**Fix Proposal**:
1. **For relax steps**: Check if relax actually requires SCF or if this is a bug
   - If relax should be standalone: Fix topology checker
   - If relax requires SCF: Update tests to create SCF first

2. **For MP2/TD steps**: Tests must create SCF step first (this is correct behavior)

**Decision**: **INVESTIGATE** - Need to determine if relax requiring SCF is a bug or expected behavior. For MP2/TD, tests are wrong.

---

### Category 3: Contract/Golden Fixture Mismatches (~20 failures)

#### Problem C3.1: Golden Contract Mismatches

**Failures**:
- `test_golden_contracts.py::test_matches_golden[detect_workflow]` - Returns SPEC types instead of GEN
- `test_golden_contracts.py::test_matches_golden[add_step_to_calculation]` - Missing `step_type_gen` field

**Root Cause**: 
1. API now returns SPEC types where golden fixtures expect GEN types
2. API requires `step_type_gen` but golden fixtures don't provide it

**Analysis**:
- **detect_workflow**: Returns `present_steps: ["qe_scf", "qe_nscf"]` but golden expects `["scf", "nscf"]`
- **add_step_to_calculation**: API requires `step_type_gen` but request doesn't include it

**Fix Proposal**:
1. **For detect_workflow**: API should return GEN types, not SPEC types
   - Update `detect_workflow` implementation to return GEN types
   - Or update golden fixtures to expect SPEC types (less preferred)

2. **For add_step_to_calculation**: Golden fixtures need `step_type_gen` field
   - Update golden fixtures
   - Or make API accept both GEN and SPEC (less preferred)

**Decision**: **FIX** - APIs should return GEN types for workflow detection (GEN layer). Golden fixtures need updating.

---

### Category 4: Execution/Artifact Issues (~20 failures)

#### Problem E1: Missing Generated Structure Artifacts

**Failures**:
- `test_lammps_long_smoke.py` - `current.json` not created
- `test_qe_relax_real.py` - `current.json` not found after execution
- Various relax tests - Artifacts missing

**Root Cause**: Relax execution completes but post-processing doesn't create `current.json` artifact.

**Analysis**: 
- Execution succeeds but artifact creation fails
- May be post-job handler issue
- Or artifact path resolution issue

**Fix Proposal**: Investigate post-job handlers for relax steps. Ensure they call `write_generated_structure()`.

---

#### Problem E2: Parameter/Precision Issues

**Failures**:
- `test_precision_integration.py` - `KeyError: 'cards'` or `KeyError: 'SYSTEM'`
- `test_precision_roundtrip.py` - Missing `K_POINTS` in cards

**Root Cause**: Precision application or roundtrip logic doesn't preserve all required fields.

**Fix Proposal**: Review precision application logic to ensure all fields are preserved.

---

### Category 5: Other Issues (~30 failures)

#### Problem O1: LAMMPS Template Double Prefix

**Failure**: `test_lammps_writer.py::test_get_template_for_step_type`

**Error**: `ValueError: Unknown step type: lammps_lammps_relax`

**Root Cause**: `get_template_for_step_type()` receives `"lammps_relax"` (already SPEC), but code calls `spec_from("lammps", "lammps_relax")` creating double prefix.

**Code**:
```python
# In lammps_writer.py:68
step_type_spec = spec_from("lammps", step_type_gen)  # step_type_gen is already "lammps_relax"!
```

**Fix Proposal**:
```python
# Check if already SPEC before converting
from quantumvitas.workflow.step_type_convert import is_spec, gen_from
if is_spec(step_type_gen):
    step_type_spec = step_type_gen
else:
    step_type_spec = spec_from("lammps", step_type_gen)
```

**Decision**: **FIX** - Function parameter should be `step_type_gen` (GEN) but test/caller passes SPEC. Need to handle both or fix caller.

---

#### Problem O2: VASP Output Files Missing

**Failures**:
- `test_vasp_project_e2e.py` - `EIGENVAL`, `DOSCAR` files not created

**Root Cause**: VASP execution may not be producing expected output files, or paths are wrong.

**Fix Proposal**: Investigate VASP execution and output file paths.

---

## Part 4: Summary of Fix Decisions

### Must Fix (Critical)

1. **Gate G2**: Wannier90/QE step type registration - **FIX**
2. **Gate G3**: Cross-assignment violations (7 locations) - **FIX ALL**
3. **Bucket C1.1**: Undefined `step_type` in `test_precision_detection_custom.py` - **FIX**
4. **Bucket C1.2**: Undefined `step_type` in `test_incremental_run.py` - **FIX**
5. **Category R1**: Registry registration issues - **FIX**
6. **Problem O1**: LAMMPS double prefix - **FIX**

### Should Fix (High Priority)

7. **Category T1**: Topology/chain dependency issues - **INVESTIGATE THEN FIX**
8. **Category C3.1**: Golden contract mismatches - **FIX**
9. **Category E1**: Missing artifacts - **INVESTIGATE THEN FIX**
10. **Bucket C1.3**: Function parameter mismatches (missed from Bucket A) - **FIX**

### Nice to Fix (Medium Priority)

11. **Category E2**: Precision/parameter issues - **INVESTIGATE THEN FIX**
12. **Problem O2**: VASP output files - **INVESTIGATE THEN FIX**
13. **Gate G1**: Registry mapping pattern - **INVESTIGATE THEN FIX**

---

## Part 5: Implementation Order

### Phase 1: Critical Fixes (Gates + Bucket C)
1. Fix Gate G3 cross-assignments (7 locations)
2. Fix Gate G2 registration issues
3. Fix Bucket C undefined variables
4. Fix Problem O1 (LAMMPS double prefix)
5. Re-run gates - should all pass

### Phase 2: Registry Infrastructure
6. Fix Category R1 (registry registration)
7. Fix Category R2 (materialization maps)
8. Re-run registry-related tests

### Phase 3: Test Fixes
9. Fix Category T1 (topology dependencies)
10. Fix Category C3.1 (golden contracts)
11. Fix Category E1 (artifacts)
12. Fix remaining Bucket C issues

### Phase 4: Final Cleanup
13. Fix remaining precision/parameter issues
14. Fix VASP output issues
15. Full test suite run

---

## Part 6: Code Review Notes

### Critical Observations

1. **Two Registry Systems**: `DriverRegistry` (new) and `StepTypeRegistry` (legacy) both exist. Need to ensure they're in sync or migrate fully to one.

2. **Fallback Patterns Are Dangerous**: Code has many "fallback if conversion fails" patterns that assign SPEC to GEN or vice versa. These violate the boundary and should use explicit conversion.

3. **Relax Step Dependencies**: Constitution says relax is standalone, but implementation requires SCF. This is a design inconsistency that needs resolution.

4. **Function Signatures Inconsistent**: Some functions accept GEN, some SPEC, some both. Need clear documentation and consistent patterns.

5. **Import-Time Registration**: Driver registration must happen at import time, but may not be guaranteed. Need explicit registration in `__init__.py` files.

---

## Appendix: File-by-File Fix Checklist

### Source Files Needing Fixes

- [ ] `src/quantumvitas/workflow/registry.py:924` - Cross-assignment
- [ ] `src/quantumvitas/api/service.py:6984` - Cross-assignment  
- [ ] `src/quantumvitas/presets/integration.py:318, 381` - Cross-assignment
- [ ] `src/quantumvitas/engine/pyscf_engine.py:519, 546` - Cross-assignment
- [ ] `src/quantumvitas/engine/lammps_writer.py:68` - Double prefix bug
- [ ] `src/quantumvitas/core/driver_registry.py` - Registration logic
- [ ] `src/quantumvitas/drivers/*/__init__.py` - Ensure registration on import

### Test Files Needing Fixes

- [ ] `tests/integration/test_precision_detection_custom.py:100` - Undefined variable
- [ ] `tests/integration/test_incremental_run.py:585` - Undefined variable
- [ ] `tests/integration/test_relax_execution.py:55` - Parameter mismatch
- [ ] `tests/unit/test_wannier90_evaluation.py:38` - Parameter mismatch
- [ ] `tests/unit/test_lammps_writer.py:65` - Double prefix test
- [ ] All relax/MP2/TD tests - Add SCF step prerequisites
- [ ] All registry lookup tests - Use correct registry

---

**End of Analysis**

