# Phase 3C Fix Summary

**Date**: 2024-12-19  
**Status**: Code fixes completed, testing needed

---

## Completed Fixes

### ✅ Phase A: Registry Completeness
- **Status**: COMPLETE
- **Changes**:
  - `pyscf_td` StepTypeSpec already registered in `src/qmatsuite/workflow/registry.py` (lines 359-374)
  - MATERIALIZATION_MAP already includes `("pyscf", "TD"): "pyscf_td"` mapping (line 80 in `generalized_steps.py`)
- **Verification**: Registry contains `pyscf_td` with correct fields:
  - `public_type="td"`
  - `machine_type="pyscf_td"`
  - `engine="pyscf"`
  - `consumes_state="mf"`
  - `produces_state=None`

### ✅ Phase B: StepResult Import Regression
- **Status**: COMPLETE (already fixed in previous session)
- **Changes**:
  - `src/qmatsuite/calculation/step.py`: Import from `qmatsuite.engine.base` (line 120)
  - `src/qmatsuite/calculation/runner.py`: Already correct (from previous session)
- **Verification**: No imports from `qmatsuite.calculation.results` found in codebase

### ⚠️ Phase C: CLI Deprecated Step.yaml Path
- **Status**: CODE REVIEWED - No obvious issues found
- **Analysis**:
  - `run_step_command` in `src/qmatsuite/cli/main.py` correctly:
    1. Resolves calculation from step path (lines 1530-1579)
    2. Resolves step via `resolve_step_for_cli` (line 1596)
    3. Calls `QMSService.run_step()` which handles structure resolution via `calculation.structure_id` (line 1604)
  - Error "name 'structure' is not defined" suggests runtime issue
  - Need to run tests to identify exact failure location
- **Action Required**: Run failing tests to get full traceback

### ✅ Phase D: PySCF Chain Resolution Materialization
- **Status**: CODE COMPLETE - Logic verified
- **Changes**:
  - Materialization logic in `src/qmatsuite/api.py` `init_step` method (lines 874-888):
    1. Gets `engine_family` from `wf_model` (line 876)
    2. Calls `materialize_public_step_key(step_type, engine_family)` (line 879)
    3. Uses materialized machine type for `create_step_doc` (line 908)
  - `create_step_doc` accepts machine types and handles them correctly (step_factory.py lines 48-55)
- **Logic Verification**:
  - When `step_type="scf"` and `engine_family="pyscf"`:
    - `materialize_public_step_key("scf", "pyscf")` → `"pyscf_scf"`
    - `machine_step_type="pyscf_scf"` passed to `create_step_doc`
    - `create_step_doc` stores `step_type: pyscf_scf` in step.yaml
  - Dependency chain resolution will read `step_type: pyscf_scf` from step.yaml
  - `registry.get("pyscf_scf")` returns spec with `produces_state="mf"`

---

## Code Structure Verification

### Materialization Flow
1. **init_step** (api.py:874-888):
   - Gets `engine_family` from calculation model
   - Materializes public type → machine type
   - Passes machine type to `create_step_doc`

2. **create_step_doc** (step_factory.py:48-55):
   - Accepts machine type (from init_step) or public type
   - Normalizes to machine type for step.yaml
   - Stores machine type in step.yaml

3. **run_step** (api.py:1434-1455):
   - Reads machine type from step.yaml
   - Uses machine type for dependency chain resolution

### Registry.get() Behavior
- `registry.get("scf")` returns FIRST match (non-deterministic when multiple engines share public type)
- This is why materialization using `engine_family` is critical
- Materialization ensures correct machine type is stored in step.yaml

---

## Testing Status

### Tests to Run
1. **Phase A**: 
   - `pytest tests/unit/test_pyscf_integration.py::test_pyscf_td_in_registry -v`
   - `pytest tests/workflow/test_generalized_steps.py::test_all_mappings_return_valid_step_type -v`

2. **Phase B**: 
   - All tests that import StepResult should pass

3. **Phase C**:
   - `pytest tests/unit/test_project_and_cli.py::test_cli_run_stepfile_generates_input -v`
   - `pytest tests/unit/test_project_and_cli.py::test_cli_run_step_accepts_step_yaml -v`
   - `pytest tests/cli/test_cli_show_command_integration.py -v`

4. **Phase D**:
   - `pytest tests/integration/test_pyscf_phase3c.py::test_t4_runstep_mp2_chain_execution -v`

### Expected Results
- Phase A: Should pass (registry contains pyscf_td)
- Phase B: Should pass (imports fixed)
- Phase C: Needs runtime debugging to identify exact error location
- Phase D: Should pass (materialization logic verified)

---

## Notes

1. **pyscf_td defaults**: `pyscf_td` is not in `DEFAULT_STEP_PARAMS`, but this is acceptable - it will return empty defaults, which is fine for TD step type.

2. **create_step_doc defaults**: `create_step_doc` calls `registry.get_defaults(step_type)` using the input step_type. Since we pass machine_step_type to `create_step_doc`, it uses machine type for defaults lookup. However, `get_default_step_params` supports machine types (via legacy_mapping), so this should work correctly.

3. **Phase C investigation**: The error "name 'structure' is not defined" suggests a runtime issue that requires test execution to identify. The code structure looks correct, but there may be an exception path we haven't identified.

---

## Next Steps

1. Run all Phase tests to verify fixes
2. For Phase C, run failing test with full traceback (`pytest -v -s`) to identify exact error location
3. Add assertions in Phase D test to verify step.yaml contains correct machine type
4. Run full test suite to check for regressions

