# Phase 3C TD and Regression Review

**Date**: 2024-12-19  
**Scope**: Code review and design notes for current test failures  
**Objective**: De-risk next implementation pass by documenting root causes and fix strategies

---

## Executive Summary

This document analyzes 12 failing tests across 4 groups to identify root causes and recommend fix strategies. **No code changes are made in this pass**—this is a pure review.

### Root Causes by Group

**Group A — Missing `pyscf_td` in registry (4 failures)**
- `MATERIALIZATION_MAP` includes `("pyscf", "TD"): "pyscf_td"` mapping
- `pyscf_td` `StepTypeSpec` entry does not exist in registry
- Tests expect `pyscf_td` to be registered with specific fields
- **Fix**: Add `pyscf_td` to `_STEP_TYPES` dict in `src/quantumvitas/workflow/registry.py`

**Group B — `StepResult` import regression (3 failures)**
- Tests import from `quantumvitas.calculation.results` (old location)
- `StepResult` was moved to `quantumvitas.engine.base`
- **Fix**: Update test imports to use `quantumvitas.engine.base.StepResult`

**Group C — CLI structure undefined (4 failures)**
- CLI `run step` command for direct step.yaml file paths is broken
- Variable `structure` is referenced but undefined in the code path
- Deprecated path (step.yaml file) should still work but lacks structure resolution
- **Fix**: Restore structure resolution for deprecated step.yaml file path

**Group D — Phase3C t4 dependency chain (1 failure)**
- `test_t4_runstep_mp2_chain_execution` fails: "No provider found for state 'mf'"
- Dependency resolver cannot find `pyscf_scf` step that produces `mf` state
- Likely root cause: Step materialization or calculation loading issue
- **Fix**: Debug step loading/materialization in test setup

### Recommended Fix Order

1. **Group B** (import fix) — simplest, low risk
2. **Group A** (add `pyscf_td`) — well-defined, requires PySCF TD design
3. **Group C** (CLI structure) — requires understanding deprecated path behavior
4. **Group D** (dependency chain) — requires debugging test setup

---

## Evidence Walkthrough

### Group A: Missing `pyscf_td` in Registry + Generalized Mapping

#### Findings

**File**: `src/quantumvitas/workflow/generalized_steps.py`

The `MATERIALIZATION_MAP` includes a mapping for TD:
```python
("pyscf", "TD"): "pyscf_td"
```

**File**: `src/quantumvitas/workflow/registry.py`

The `_STEP_TYPES` dictionary contains `pyscf_scf` and `pyscf_mp2` but not `pyscf_td`:
- Lines 327-342: `pyscf_scf` StepTypeSpec
- Lines 341-356: `pyscf_mp2` StepTypeSpec
- Missing: `pyscf_td` StepTypeSpec

**Failing Tests**:
1. `tests/unit/test_pyscf_integration.py::test_pyscf_td_in_registry` — expects `registry.has('pyscf_td') == True`
2. `tests/unit/test_pyscf_integration.py::test_pyscf_td_spec_properties` — expects `registry.get('pyscf_td')` to return a spec with specific properties
3. `tests/workflow/test_generalized_steps.py::test_all_mappings_return_valid_step_type` — expects materialized `pyscf_td` to exist in registry
4. `tests/unit/test_pyscf_chain.py::test_td_resolves_to_scf` — expects `pyscf_td` to exist for dependency resolution

**How Tests Assert Behavior**:

From `tests/unit/test_pyscf_integration.py`:
```python
def test_pyscf_td_spec_properties(self):
    registry = get_registry()
    spec = registry.get('pyscf_td')
    assert spec is not None
    assert spec.machine_type == "pyscf_td"
    assert spec.public_type == "td"
    assert spec.engine == "pyscf"
    assert spec.consumes_state == "mf"
    assert spec.produces_state is None
```

**Recommended Fix Strategy**:

1. Add `pyscf_td` entry to `_STEP_TYPES` dict in `src/quantumvitas/workflow/registry.py`
2. Follow the pattern of `pyscf_scf` and `pyscf_mp2` for field values
3. Set `consumes_state="mf"` (depends on SCF)
4. Set `produces_state=None` (or `"td"` if we want to support TD→property chains)
5. See "PySCF TD Implementation Notes" section for complete spec design

---

### Group B: StepResult Import Regression

#### Findings

**Root Cause**:

The `StepResult` class was moved from `quantumvitas.calculation.results` to `quantumvitas.engine.base`, but some code still imports from the old location.

**Old Location** (where some code still imports):
- `src/quantumvitas/calculation/results.py` — does NOT export `StepResult`
- `src/quantumvitas/calculation/runner.py` (line 513) — imports from old location: `from quantumvitas.calculation.results import StepResult`

**Current Location**:
- File: `src/quantumvitas/engine/base.py` (line 14)
- `StepResult = _LegacyStepResult` (where `_LegacyStepResult` comes from `quantumvitas.core.engines.qe_calculation`)
- Also aliased in `src/quantumvitas/calculation/step.py` (line 12): `from quantumvitas.engine.base import StepResult`

**Evidence**:
- `src/quantumvitas/calculation/runner.py` line 513 has: `from quantumvitas.calculation.results import StepResult`
- This import fails because `calculation.results` does not export `StepResult`
- The failing tests import `CalculationRunner` which triggers the import error

**Failing Tests**:
1. `tests/integration/test_pyscf_phase3c.py::test_t1_runcalc_incremental_uses_chkfile`
2. `tests/integration/test_pyscf_phase3c.py::test_t2_runcalc_full_forbids_chkfile`
3. `tests/integration/test_pyscf_phase3c.py::test_t3_runstep_scf_forbids_chkfile`

**Error Message**:
```
ImportError: cannot import name 'StepResult' from 'quantumvitas.calculation.results'
```

**Recommended Fix Strategy**:

1. **Primary fix**: Update import in `src/quantumvitas/calculation/runner.py` (line 513):
   ```python
   # Old:
   from quantumvitas.calculation.results import StepResult
   
   # New:
   from quantumvitas.engine.base import StepResult
   ```

2. **Verify**: Check if any other files import `StepResult` from `calculation.results`
   ```bash
   grep -r "from quantumvitas.calculation.results import StepResult" src/ tests/
   ```

3. **Test**: The test file itself doesn't import `StepResult` directly, but importing `CalculationRunner` triggers the import error in `runner.py`

---

### Group C: CLI Structure Undefined Regression

#### Findings

**File**: `src/quantumvitas/cli/main.py`

The `run_step_command` function handles deprecated step.yaml file paths via the `target` parameter, but the code references a variable `structure` that is not defined in that code path.

**Failing Tests**:
1. `tests/unit/test_project_and_cli.py::test_cli_run_stepfile_generates_input`
2. `tests/unit/test_project_and_cli.py::test_cli_run_step_accepts_step_yaml`
3. `tests/unit/test_project_and_cli.py::test_cli_show_command_import_preserves_original_parameters`
4. `tests/cli/test_cli_show_command_integration.py::test_cli_show_command_executes_against_references`

**Error Message**:
```
NameError: name 'structure' is not defined
```

**Code Path**:
- CLI command: `qv run step <step.yaml>` (deprecated `target` argument)
- Function: `run_step_command` in `src/quantumvitas/cli/main.py` (lines 1427-1635)
- The function uses `ProjectContext.load()` and `resolve_step_for_cli()` to handle the deprecated path
- The code likely calls a function that expects `structure` variable but it's not resolved from the step.yaml/calculation context

**Intended Behavior** (from docstring, lines 1457-1473):
- Deprecated path (`target` argument) should still work
- When `target` (step.yaml file) is provided, calculation is inferred from step path
- Structure is resolved from `calculation.structure_id` (DAG model), not from step.yaml

**Current Implementation** (lines 1506-1635):
- Uses `ProjectContext.load()` to get project context
- Calls `resolve_step_for_cli()` to resolve step from `target` parameter
- The resolution path likely needs structure but it's not being resolved

**Recommended Fix Strategy**:

1. **Locate the exact code path**: Find where `structure` variable is referenced but undefined
   - Check `resolve_step_for_cli()` in `src/quantumvitas/core/project_context.py`
   - Check if `_execute_step_spec()` or similar functions expect `structure` parameter
   
2. **Structure resolution for deprecated path**:
   - Step.yaml path → extract `parent_calculation_id` from step.yaml
   - Load `calculation.yaml` using `parent_calculation_id`
   - Extract `structure_id` from `calculation.yaml`
   - Resolve structure using `require_structure(project_root, structure_id, ...)`
   
3. **Alternative**: If step.yaml is orphaned (no parent_calculation_id):
   - Walk parent directories to find `calculation.yaml`
   - Or: require `--calculation` flag for orphaned steps
   - Or: raise clear error asking user to use `--calculation --step` selectors

**Investigation Needed**:
- Inspect `resolve_step_for_cli()` implementation in `src/quantumvitas/core/project_context.py`
- Check if `_execute_step_spec()` or QVService.run_step() is called and expects structure
- Understand the exact call chain that leads to `structure` being undefined
- Check git history for when structure resolution was removed from deprecated path

---

### Group D: Phase3C t4 Dependency Chain — Provider Missing

#### Findings

**File**: `tests/integration/test_pyscf_phase3c.py::test_t4_runstep_mp2_chain_execution`

**Error Message**:
```
QVServiceError: Failed to resolve dependency chain: No provider found for state 'mf' required by step 'pyscf_mp2' (ULID: ...). Scan left from target step but found no step with produces_state='mf'.
```

**Code Path**:
- `src/quantumvitas/api.py::run_step` (lines 1414-1462)
- `src/quantumvitas/engines/pyscf/chain.py::resolve_dependency_chain`

**How Dependency Resolution Works**:

From `src/quantumvitas/api.py` (lines 1419-1438):
```python
calculation_steps = []
for step in calculation.steps:
    step_ulid = step.meta.id
    # Read machine step_type from step.yaml
    step_yaml_path = project_root / step.meta.path
    step_data = yaml.safe_load(step_yaml_path.read_text()) or {}
    machine_type = step_data.get("step_type") or "unknown"
    calculation_steps.append((step_ulid, machine_type))
```

From `src/quantumvitas/engines/pyscf/chain.py::resolve_dependency_chain`:
- Scans `calculation_steps` left-to-right
- Looks up `StepTypeSpec` for each machine_type
- Checks `produces_state` and `consumes_state` fields

**Plausible Root Causes**:

1. **Step materialization issue**: The SCF step's `step.yaml` may not have `step_type="pyscf_scf"` set correctly
   - Test creates step with `step_type="scf"` (public type)
   - Materialization should convert to `"pyscf_scf"` (machine type)
   - If materialization fails, step.yaml may contain `"scf"` instead of `"pyscf_scf"`

2. **Calculation.steps not loaded correctly**: The calculation may not include the SCF step in `calculation.steps`
   - Test creates SCF step first, then MP2 step
   - `calculation.steps` list may be empty or only contain MP2 step
   - Check if `Calculation.from_yaml(..., materialize_steps=True)` loads all steps

3. **Step type lookup failure**: Registry lookup for `pyscf_scf` may fail
   - If `machine_type` in step.yaml is wrong (e.g., `"scf"` instead of `"pyscf_scf"`), registry lookup returns None
   - `resolve_dependency_chain` then cannot find `produces_state="mf"`

**Recommended Fix Strategy**:

1. **Debug step materialization**:
   - Add logging to verify step.yaml contains `step_type="pyscf_scf"` (not `"scf"`)
   - Check if `QVService.init_step` correctly materializes public type to machine type

2. **Verify calculation.steps loading**:
   - Ensure `calculation.steps` contains both SCF and MP2 steps
   - Verify step order (SCF should be before MP2)

3. **Check step type resolution**:
   - Verify registry lookup works: `registry.get("pyscf_scf")` returns spec with `produces_state="mf"`
   - Add assertions in test to verify step.yaml contents

**Test Setup Analysis Needed**:
- Review `test_t4_runstep_mp2_chain_execution` fixture setup
- Verify both steps are created and added to calculation
- Check if step.yaml files are created with correct machine types

---

## PySCF TD Implementation Notes

### Examples Consulted

**PySCF Examples Directory**: `.tmp/pyscf-master/examples/tddft/`

Key files:
- `20-td_rks.py` — TDDFT with RKS reference
- `40-td_analyze.py` — TD analysis and properties

**Pattern Observed**:

From PySCF examples, TD is typically used as:
```python
from pyscf import tddft

# After SCF (mf object exists)
td = tddft.TDDFT(mf)  # or tddft.TDA(mf) for Tamm-Dancoff
td.nstates = 5  # Number of excited states
td.kernel()  # Run TD calculation
```

Key parameters:
- `method`: TDDDFT vs TDA (Tamm-Dancoff approximation)
- `nstates`: Number of excited states to compute
- Reference method (HF/DFT) is derived from the SCF step (mf object)

### Recommended StepTypeSpec for `pyscf_td`

Based on existing patterns (`pyscf_scf`, `pyscf_mp2`) and PySCF usage:

```python
"pyscf_td": StepTypeSpec(
    id="td",  # Public type (shared with QE TDDFT)
    machine_type="pyscf_td",
    public_type="td",
    engine="pyscf",
    executable="python",
    description="PySCF TDDFT/TDA excited states calculation",
    accepts_presets=False,
    allowed_dimensions=frozenset(),
    requires_structure=True,
    requires_charge_density=True,  # Requires SCF (mf object)
    produces_charge_density=False,
    supports_incremental_skip=False,  # Always rerun (Phase 3C requirement)
    consumes_state="mf",  # Consumes mean-field state from SCF
    produces_state=None,  # Or "td" if we want TD→property chains in v1
)
```

### Recommended step.yaml Parameters for TD (v0 minimal)

```yaml
parameters:
  method: "tddft"  # or "tda" (Tamm-Dancoff approximation)
  nstates: 5  # Number of excited states
  # Optional v0:
  # conv_tol: 1e-6  # Convergence tolerance
  # max_cycle: 50  # Max iterations
```

**Notes**:
- `method` could be derived from SCF reference (RHF → TDHF, RKS → TDDFT), but for v0, allow explicit override
- `nstates` is the most critical parameter
- SCF method (HF vs DFT) is determined by the upstream SCF step, not stored in TD step.yaml (SSOT)

### Recommended Runner Behavior for TD (Design-Only)

**Inputs**:
- SCF checkpoint (mf object) from upstream `pyscf_scf` step
- step.yaml parameters (method, nstates, etc.)

**Execution**:
1. Load SCF checkpoint
2. Reconstruct mf object (run quick SCF kernel if needed)
3. Create TD object: `tddft.TDDFT(mf)` or `tddft.TDA(mf)` based on `parameters.method`
4. Set `td.nstates = parameters.nstates`
5. Run `td.kernel()`
6. Extract results: excitation energies, oscillator strengths, etc.

**Artifacts** (per Phase 3C v0 runner spec):
- `results.json`:
  ```json
  {
    "success": true,
    "converged": true,
    "nstates": 5,
    "excitation_energies": [0.123, 0.456, ...],
    "oscillator_strengths": [0.001, 0.002, ...],
    "runtime": 1.23,
    "pyscf_version": "2.x"
  }
  ```
- `stdout.txt` (PySCF log output)

**Future v1 considerations**:
- `produces_state="td"` to allow TD→property chains
- Analysis properties (transition dipole, etc.)

---

## TODO Checklist (for Next Implementation Pass)

### Group A: Add `pyscf_td` to Registry

- [ ] Add `pyscf_td` entry to `_STEP_TYPES` dict in `src/quantumvitas/workflow/registry.py`
  - Use spec from "PySCF TD Implementation Notes" section
  - Set `consumes_state="mf"`
  - Set `produces_state=None` (or `"td"` for v1)
- [ ] Verify `MATERIALIZATION_MAP` mapping `("pyscf", "TD"): "pyscf_td"` is correct
- [ ] Run tests:
  - [ ] `pytest tests/unit/test_pyscf_integration.py::test_pyscf_td_in_registry -v`
  - [ ] `pytest tests/unit/test_pyscf_integration.py::test_pyscf_td_spec_properties -v`
  - [ ] `pytest tests/workflow/test_generalized_steps.py::test_all_mappings_return_valid_step_type -v`
  - [ ] `pytest tests/unit/test_pyscf_chain.py::test_td_resolves_to_scf -v`

### Group B: Fix StepResult Import

- [ ] Locate all imports of `StepResult` from `quantumvitas.calculation.results` in test files
- [ ] Update imports to `from quantumvitas.engine.base import StepResult`
- [ ] Verify `StepResult` API hasn't changed (fields, methods)
- [ ] Run tests:
  - [ ] `pytest tests/integration/test_pyscf_phase3c.py::test_t1_runcalc_incremental_uses_chkfile -v`
  - [ ] `pytest tests/integration/test_pyscf_phase3c.py::test_t2_runcalc_full_forbids_chkfile -v`
  - [ ] `pytest tests/integration/test_pyscf_phase3c.py::test_t3_runstep_scf_forbids_chkfile -v`

### Group C: Fix CLI Structure Undefined

- [ ] Locate code path in `src/quantumvitas/cli/main.py` that handles `run step <step.yaml>`
- [ ] Identify where `structure` variable is referenced but undefined
- [ ] Investigate git history to understand previous structure resolution logic
- [ ] Implement structure resolution for deprecated step.yaml path:
  - Option A: Load step.yaml → extract calculation_id → load calculation.yaml → resolve structure
  - Option B: Find calculation.yaml in parent directories
  - Option C: Restore legacy structure_id handling if step.yaml contains it
- [ ] Add test to verify deprecated path still works
- [ ] Run tests:
  - [ ] `pytest tests/unit/test_project_and_cli.py::test_cli_run_stepfile_generates_input -v`
  - [ ] `pytest tests/unit/test_project_and_cli.py::test_cli_run_step_accepts_step_yaml -v`
  - [ ] `pytest tests/unit/test_project_and_cli.py::test_cli_show_command_import_preserves_original_parameters -v`
  - [ ] `pytest tests/cli/test_cli_show_command_integration.py::test_cli_show_command_executes_against_references -v`

### Group D: Fix t4 Dependency Chain

- [ ] Add debug logging to `test_t4_runstep_mp2_chain_execution` to inspect:
  - [ ] Contents of `calculation.steps` (should contain both SCF and MP2)
  - [ ] Contents of step.yaml files (should have `step_type="pyscf_scf"` and `step_type="pyscf_mp2"`)
  - [ ] Registry lookup results for `pyscf_scf` and `pyscf_mp2`
- [ ] Verify step materialization in test setup:
  - [ ] SCF step created with `step_type="scf"` (public) → should materialize to `"pyscf_scf"` (machine)
  - [ ] MP2 step created with `step_type="mp2"` (public) → should materialize to `"pyscf_mp2"` (machine)
- [ ] Check if `QVService.init_step` correctly materializes based on `calculation.engine_family`
- [ ] Verify `resolve_dependency_chain` receives correct `calculation_steps` list
- [ ] Fix root cause (likely step materialization or calculation loading)
- [ ] Run test:
  - [ ] `pytest tests/integration/test_pyscf_phase3c.py::test_t4_runstep_mp2_chain_execution -v`

### General Cleanup

- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Verify no regressions in QE/W90 paths
- [ ] Update changelog with fixes

---

## Appendix: Code References

### Key Files for Each Group

**Group A (pyscf_td)**:
- `src/quantumvitas/workflow/registry.py` — Add `pyscf_td` to `_STEP_TYPES`
- `src/quantumvitas/workflow/generalized_steps.py` — Verify `MATERIALIZATION_MAP` mapping

**Group B (StepResult import)**:
- `src/quantumvitas/engine/base.py` — `StepResult` definition
- `tests/integration/test_pyscf_phase3c.py` — Update imports

**Group C (CLI structure)**:
- `src/quantumvitas/cli/main.py` — `run step` command handler

**Group D (dependency chain)**:
- `src/quantumvitas/api.py` — `run_step` method (lines 1414-1462)
- `src/quantumvitas/engines/pyscf/chain.py` — `resolve_dependency_chain` function
- `tests/integration/test_pyscf_phase3c.py` — `test_t4_runstep_mp2_chain_execution`

---

---

## Code Review Investigation (2024-12-19)

### Additional Findings from Deep Code Review

After detailed code review (see `PHASE3C_CODE_REVIEW_INVESTIGATION.md` for full analysis):

#### Group C - CLI Structure Issue
**Current Code Analysis**:
- The deprecated path in `run_step_command` (lines 1520-1633) correctly:
  1. Resolves calculation from step path
  2. Resolves step from calculation
  3. Calls `QVService.run_step()` which should handle structure resolution
- **Hypothesis**: The error "name 'structure' is not defined" suggests:
  - Error originates inside `QVService.run_step()` call chain
  - Exception is caught and re-raised with "Failed to run step:" prefix
  - Need runtime debugging to identify exact line number

**Recommendation**: Run failing test with full traceback (`pytest -v -s`) to identify exact failure location.

#### Group D - Step Materialization Issue  
**Registry.get() Behavior**:
- `registry.get(public_type)` returns FIRST match when multiple engines share same public_type
- Example: `registry.get("scf")` might return `qe_scf` instead of `pyscf_scf` (non-deterministic)
- This is why materialization using `engine_family` is critical

**Materialization Fix Analysis**:
- The fix in `init_step` (lines 874-888) should work correctly:
  1. Gets `engine_family` from calculation model
  2. Calls `materialize_public_step_key(step_type, engine_family)`  
  3. Passes materialized machine_type to `create_step_doc`
- `create_step_doc` accepts machine types, so this should work
- **Potential issue**: `create_step_doc` also calls `registry.get_defaults(machine_step_type)` which might need public type

**Recommendation**: 
1. Verify step.yaml files contain `step_type: pyscf_scf` (not `step_type: scf`)
2. Add assertions in test to verify materialization worked
3. Check if `get_default_step_params` needs public type vs machine type

---

**End of Review Document**

