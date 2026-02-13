# Phase 3C: PySCF Engine-Family Support Implementation Plan

**Status**: In Progress  
**Goal**: Implement PySCF engine-family support with two generalized workflows:
- `scf` → `pyscf_scf`
- `scf_mp2` → `pyscf_scf` + `pyscf_mp2`

## Architecture Constraints (Non-Negotiable)

1. **SSOT**: `step.yaml` is the machine code. Must contain only PySCF parameters (NO IR/preset sections)
2. **Structure**: Structure is ONLY in `calculation.yaml` (or structure registry). `step.yaml` MUST NOT contain structure payload
3. **PySCF Checkpoint Policy (Conservative)**:
   - NO "mf shim" by injecting `mo_coeff` into a new mf object
   - Only supported reuse: load existing SCF chkfile as `init_guess` input, then run SCF kernel again to obtain mf
4. **Incremental Skip Gating**:
   - Step types may veto skipping even if sha/done suggests skip
   - v0: `pyscf_scf` may be skippable/restartable; `pyscf_mp2` must be always-rerun (not skippable)
5. **Artifacts Layout**: Use per-step artifacts directory (existing step_artifacts conventions). Before each step run, clear that step's artifacts dir (keep only newest results, like QE)

## Part A Review Status

✅ **A1: Calc identity recovery is strictly best-effort**
- Verified: `ensure_calculation_identity()` only infers when fields are missing; never overwrites existing values
- Test: `tests/unit/test_calc_identity.py::test_ensure_calculation_identity_preserves_existing`

✅ **A2: materialize_public_step_key contract**
- Verified: Returns 0 or 1 machine step type per (family, public_step_key)
- Returns `None` for unsupported combinations (no crash)
- Test: `tests/unit/test_workflow_materialization_phase3b.py`

✅ **A3: Workflow templates use canonical public step keys**
- Verified: All templates use lowercase identifiers
- Test: Verified manually with workflow service

## Implementation Tasks

### C1: Step Type Registry

- [ ] Add `pyscf_scf` step type to registry
  - `machine_type`: "pyscf_scf"
  - `public_type`: "scf"
  - `engine`: "pyscf"
  - `executable`: "python" (PySCF runner)
  - `supports_incremental_skip`: True (can be skipped if checkpoint exists)
  
- [ ] Add `pyscf_mp2` step type to registry
  - `machine_type`: "pyscf_mp2"
  - `public_type`: "mp2"
  - `engine`: "pyscf"
  - `executable`: "python" (PySCF runner)
  - `supports_incremental_skip`: False (always rerun)

- [ ] Add `supports_incremental_skip` field to `StepTypeSpec`
  - File: `src/quantumvitas/workflow/registry.py`
  - Default: `True` (backward compatible)

- [ ] Add step type defaults for PySCF steps
  - `pyscf_scf`: Default parameters (method, basis, etc.)
  - `pyscf_mp2`: Default parameters

**Tests**:
- [ ] Unit test: Registry has `pyscf_scf` and `pyscf_mp2`
- [ ] Unit test: `supports_incremental_skip` field works correctly

---

### C2: Workflow Materialization

- [ ] Update `MATERIALIZATION_MAP` in `generalized_steps.py`
  - `("pyscf", "SCF")`: "pyscf_scf"
  - `("pyscf", "MP2")`: "pyscf_mp2" (new generalized step)
  
- [ ] Add `MP2` to `GeneralizedStep` enum
  - File: `src/quantumvitas/workflow/generalized_steps.py`

- [ ] Update `materialize_public_step_key()` to support "mp2" public key
  - "mp2" → "pyscf_mp2" for engine_family="pyscf"
  - "mp2" → None for engine_family="qe"

- [ ] Add workflow template "scf_mp2"
  - File: `src/quantumvitas/workflow/templates.py`
  - `step_sequence`: ("scf", "mp2")
  - Public step keys (lowercase)

**Tests**:
- [ ] Unit test: `materialize_public_step_key("mp2", "pyscf")` → "pyscf_mp2"
- [ ] Unit test: `materialize_public_step_key("mp2", "qe")` → None
- [ ] Unit test: Workflow template "scf_mp2" exists and has correct step sequence
- [ ] Unit test: Materialization of "scf_mp2" workflow for pyscf family

---

### C3: Step.yaml Generation (Templates)

- [ ] Add PySCF step defaults to registry
  - File: `src/quantumvitas/workflow/registry.py`
  - `get_defaults("pyscf_scf")`: Returns default parameters dict
  - `get_defaults("pyscf_mp2")`: Returns default parameters dict

- [ ] Verify `create_step_doc()` handles PySCF steps correctly
  - File: `src/quantumvitas/workflow/step_factory.py`
  - Should use machine_type for step.yaml
  - Should include parameters dict (NO structure)
  - Should include meta (ULID, name, slug, path)

**Schema for step.yaml** (aligned with existing conventions):
```yaml
meta:
  id: <ULID>
  name: <step_name>
  slug: <slug>
  kind: step
step_type: pyscf_scf  # or pyscf_mp2 (machine type)
parent_calculation_id: <ULID>
parameters:
  method: rhf
  basis: sto-3g
  # ... PySCF-specific parameters
# NO structure field
# NO workflow/preset metadata
```

**Tests**:
- [ ] Unit test: `create_step_doc("pyscf_scf", ...)` creates valid step.yaml structure
- [ ] Unit test: Step.yaml does NOT contain structure field
- [ ] Unit test: Step.yaml contains parameters dict with PySCF defaults

---

### C4: Execution Engine

- [ ] Enhance PySCF runner to support session-based execution
  - File: `src/quantumvitas/engines/pyscf/runner.py`
  - Runner should accept multiple steps in one process
  - Import PySCF once per session (not per step)
  
- [ ] Implement step execution logic in PySCF runner
  - Read `calculation.yaml` for structure (via structure_id)
  - Read `step.yaml` for parameters
  - Clear step artifacts directory before each step run
  - For `pyscf_scf`:
    - Configure `mf.chkfile = artifacts/checkpoint.chk`
    - If checkpoint exists AND step is being resumed/skipped: load checkpoint as `init_guess`
    - Run `mf.kernel()`
    - Write `checkpoint.chk`, `results.json`, `stdout.txt`
  - For `pyscf_mp2`:
    - Load SCF checkpoint.chk (must exist, fail with clear error if missing/corrupt)
    - Rebuild mol + mf, set `init_guess='chkfile'`, run quick `mf.kernel()` to obtain valid mf
    - Run `MP2(mf).kernel()`
    - Write `results.json`, `stdout.txt` (NO checkpoint for mp2 in v0)

- [ ] Update PySCF engine to use session-based runner
  - File: `src/quantumvitas/engine/pyscf_engine.py`
  - Spawn ONE subprocess per "Run Calc" (not per step)
  - Pass multiple steps to runner in session

- [ ] Artifact contract implementation
  - `pyscf_scf`: `checkpoint.chk` + `results.json` + `stdout.txt`
  - `pyscf_mp2`: `results.json` + `stdout.txt`
  - Artifacts stored in per-step directory: `raw/<step_slug>/`

**Tests**:
- [ ] Integration test: Run `pyscf_scf` on tiny molecule (H2 or He)
  - Assert `checkpoint.chk` exists and is readable
  - Assert `results.json` contains expected fields (energy, converged, etc.)
  - Assert `stdout.txt` exists
- [ ] Integration test: Run `scf_mp2` workflow end-to-end
  - Assert mp2 results exist
  - Assert mp2 results.json contains correlation energy, total energy
- [ ] Integration test: Rerun behavior
  - Ensure artifacts directory is cleared and rewritten
- [ ] Integration test: Incremental behavior
  - `pyscf_scf` can be skipped/reused (by sha + checkpoint exists)
  - `pyscf_mp2` is rerun even if sha matches

---

### C5: Incremental Skip Gating

- [ ] Add `supports_incremental_skip` field to `StepTypeSpec`
  - File: `src/quantumvitas/workflow/registry.py`
  - Type: `bool`
  - Default: `True` (backward compatible)

- [ ] Update incremental planner to respect `supports_incremental_skip`
  - File: `src/quantumvitas/calculation/manifest_reconcile.py`
  - If `supports_incremental_skip=False`, step is never marked done/skip even if sha matches
  - Check step type capability before marking as done

- [ ] Update `is_step_done()` or skip logic to check capability
  - File: `src/quantumvitas/calculation/step_done.py` (or manifest_reconcile.py)
  - For PySCF steps, also check checkpoint existence for `pyscf_scf`

**Tests**:
- [ ] Unit test: `pyscf_scf` with `supports_incremental_skip=True` can be skipped
- [ ] Unit test: `pyscf_mp2` with `supports_incremental_skip=False` is never skipped
- [ ] Integration test: Incremental run with mp2 step is always rerun
- [ ] Integration test: Incremental run with scf step can be skipped if checkpoint exists

---

### C6: Failure Behavior

- [ ] Implement checkpoint validation for `pyscf_mp2`
  - Check that SCF checkpoint.chk exists before running MP2
  - If missing or corrupt, fail with clear error message
  - Do NOT auto-rerun SCF (user must explicitly request)

**Tests**:
- [ ] Integration test: MP2 fails with clear error if SCF checkpoint missing
- [ ] Integration test: MP2 fails with clear error if SCF checkpoint corrupt

---

## Engine-Family Mapping

- **periodic** → `engine_family="qe"` (existing behavior)
- **molecule** → `engine_family="pyscf"` (new)

This mapping is already implemented in Phase 3A via `_infer_structure_kind_from_engine_family()`.

## Workflow Templates

1. **"scf"** workflow:
   - PUBLIC step keys: `("scf",)`
   - Materializes to: `("pyscf_scf",)` for `engine_family="pyscf"`
   - Materializes to: `("qe_scf",)` for `engine_family="qe"` (existing)

2. **"scf_mp2"** workflow (NEW):
   - PUBLIC step keys: `("scf", "mp2")`
   - Materializes to: `("pyscf_scf", "pyscf_mp2")` for `engine_family="pyscf"`
   - Materializes to: Error for `engine_family="qe"` (mp2 not supported)

## Test Strategy

### Unit Tests (run frequently)
- `pytest tests/unit/test_workflow.py -q`
- `pytest tests/unit/test_workflow_materialization_phase3b.py -q`
- `pytest tests/unit/test_calc_identity.py -q`

### Integration Tests (requires PySCF installed)
- `pytest tests/integration/test_pyscf_*.py -q` (new test file)
- `pytest tests/integration/test_incremental_run.py -q` (regression)

### Milestone Commands
- After C1: Run workflow registry tests
- After C2: Run materialization tests
- After C3: Run step factory tests
- After C4: Run PySCF integration tests
- After C5: Run incremental run tests
- Before finalizing: Run full pytest suite

## Files to Modify/Create

### Modify
- `src/quantumvitas/workflow/registry.py` (step types, defaults)
- `src/quantumvitas/workflow/generalized_steps.py` (materialization map)
- `src/quantumvitas/workflow/templates.py` (scf_mp2 workflow)
- `src/quantumvitas/engines/pyscf/runner.py` (session-based execution)
- `src/quantumvitas/engine/pyscf_engine.py` (session management)
- `src/quantumvitas/calculation/manifest_reconcile.py` (incremental skip gating)

### Create
- `tests/integration/test_pyscf_workflows.py` (integration tests)
- `docs/design/PHASE3C_NOTES.md` (compatibility/implementation notes)

## Documentation

- [ ] Update `PHASE2_COMPAT_NOTES.md` with Phase 3C additions
- [ ] Create `PHASE3C_NOTES.md` for implementation decisions/compatibility notes
- [ ] Update completion summary when Phase 3C is done

## Exit Criteria

✅ All unit tests passing  
✅ All integration tests passing (with PySCF installed)  
✅ Regression tests passing  
✅ Documentation updated  
✅ Phase 3C plan checked off

