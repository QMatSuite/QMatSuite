# Phase 3C Implementation Status

**Status**: In Progress  
**Last Updated**: 2025-01-10

---

## Completed Tasks

### ✅ C1: Generalized Step Key "td"
- [x] Added `TD = "TD"` to `GeneralizedStep` enum
- [x] Added `("pyscf", "TD"): "pyscf_td"` to `MATERIALIZATION_MAP`
- [x] Added `("qe", "TD"): None` (QE TD not yet in registry, handled gracefully)
- [x] Updated `materialize_public_step_key()` to handle "td" key
- [x] Added `pyscf_td` step type to registry with:
  - `id="td"`, `machine_type="pyscf_td"`, `public_type="td"`
  - `consumes_state="mf"`, `produces_state=None`
- [x] Added `scf_td` workflow template to `templates.py`

### ✅ Registry Extensions
- [x] Added `consumes_state: Optional[str]` to `StepTypeSpec`
- [x] Added `produces_state: Optional[str]` to `StepTypeSpec`
- [x] Updated `pyscf_scf`: `produces_state="mf"`, `consumes_state=None`
- [x] Updated `pyscf_mp2`: `consumes_state="mf"`, `produces_state=None`
- [x] Updated `pyscf_td`: `consumes_state="mf"`, `produces_state=None`

---

## In Progress

### 🔄 C2: Run Mode Plumbling
- [x] Verified `run_mode` parameter exists in `CalculationRunner.run()` and `QVService.run_calculation()`
- [ ] Verify UI dropdown for "Full Run" option (if separate UI code)
- [ ] Ensure `run_mode` reaches PySCF runner layer
- [ ] Implement SCF init_guess control based on `run_mode`

### 🔄 C3: PySCF Runner Chain Execution
- [ ] Implement `_resolve_dependency_chain()` function
- [ ] Implement `_run_pyscf_chain()` function
- [ ] Integrate chain execution into `CalculationRunner` for RunStep mode
- [ ] Implement SCF init_guess control (incremental vs full)

---

## Remaining Tasks

### ⏳ C4: Tests
- [ ] Unit test: `materialize_public_step_key("td", "pyscf")` → `"pyscf_td"`
- [ ] Unit test: Dependency chain resolution (nearest-provider rule)
- [ ] Unit test: Missing provider → HARD ERROR
- [ ] Unit test: SCF init_guess control (incremental vs full)
- [ ] Integration test: RunStep(mp2) resolves chain to scf, executes in one session
- [ ] Integration test: RunStep(scf) does NOT use chkfile init guess
- [ ] Integration test: RunCalc(incremental) uses chkfile init guess when present
- [ ] Integration test: RunCalc(full) does NOT use chkfile init guess

### ⏳ C5: Step Spec Storage Verification
- [ ] Verify `step.yaml` does NOT contain structure data
- [ ] Verify downstream steps do NOT redundantly store SCF selections

---

## Files Modified

- `src/quantumvitas/workflow/generalized_steps.py` (added TD enum and materialization)
- `src/quantumvitas/workflow/registry.py` (added consumes_state/produces_state, pyscf_td)
- `src/quantumvitas/workflow/templates.py` (added scf_td workflow)

---

## Files to Modify Next

- `src/quantumvitas/engines/pyscf/runner.py` (chain execution, init_guess control)
- `src/quantumvitas/calculation/runner.py` (integrate PySCF chain execution)
- `src/quantumvitas/engine/pyscf_engine.py` (if needed for engine interface)
- `tests/unit/test_pyscf_runner.py` (new test file)
- `tests/integration/test_pyscf_execution.py` (add chain execution tests)

---

**Next Step**: Implement chain execution logic in PySCF runner

