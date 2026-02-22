# Phase 3C Execution Progress Log

**Status**: In Progress  
**Started**: 2025-01-10  
**Last Updated**: 2025-01-10

---

## Implementation Checklist

### 3.1 Run Mode Plumbing (C2)

- [ ] Verify run_mode exists end-to-end: UI/API → service → CalculationRunner → engine runner
- [ ] Ensure PySCF runner receives run_mode and knows whether it is incremental or full
- [ ] Implement SCF init_guess control:
  - [ ] RunCalc incremental: allow chkfile init_guess when chk exists (still run kernel)
  - [ ] RunCalc full: forbid chkfile init_guess
  - [ ] RunStep(target=scf): forbid chkfile init_guess
  - [ ] RunStep(target!=scf): prerequisite scf may use chkfile init_guess (normal incremental semantics)
- [ ] Add/adjust tests:
  - [ ] Unit test that run_mode reaches PySCF runner
  - [ ] Integration tests verifying init_guess behavior branches

**Files Changed**: (to be filled)
**Tests Added**: (to be filled)
**Commands Run**: (to be filled)

---

### 3.2 Dependency Model Fields in Registry (C3 Prerequisites)

- [x] Verify StepTypeSpec has consumes_state/produces_state fields
  - Verified: fields exist in StepTypeSpec dataclass
- [x] Verify PySCF step specs are correct (pyscf_scf, pyscf_mp2, pyscf_td)
  - Verified: pyscf_scf: produces_state="mf", consumes_state=None
  - Verified: pyscf_mp2: consumes_state="mf", produces_state=None
  - Verified: pyscf_td: consumes_state="mf", produces_state=None
- [x] Ensure existing steps not impacted (default None)
  - Verified: qe_scf has consumes_state=None, produces_state=None (defaults work)
- [x] Add unit tests for registry fields
  - Added: test_pyscf_scf_state_fields, test_pyscf_mp2_state_fields, test_pyscf_td_spec_properties, test_qe_steps_have_none_state_fields

**Files Changed**: 
- `tests/unit/test_pyscf_integration.py` (added state fields tests)
**Tests Added**: 
- test_pyscf_scf_state_fields
- test_pyscf_mp2_state_fields  
- test_pyscf_td_spec_properties
- test_qe_steps_have_none_state_fields
**Commands Run**: 
- Verified registry fields via Python script (all correct)

---

### 3.3 Implement Dependency Chain Resolution (C3)

- [x] Implement _resolve_dependency_chain(target_step_ulid, calculation_steps)
  - Created: `src/qmatsuite/engines/pyscf/chain.py` with `resolve_dependency_chain()` function
- [x] Implement nearest-provider rule (scan left for produces_state)
  - Implemented: recursive resolution, scans left for nearest provider
- [x] Handle missing provider (hard error)
  - Implemented: returns error message tuple if provider not found
- [ ] Add unit tests:
  - [ ] Chain resolution picks nearest provider
  - [ ] Missing provider errors
  - [ ] Multiple SCFs in list: post step binds to nearest left SCF

**Files Changed**: 
- `src/qmatsuite/engines/pyscf/chain.py` (new file with resolve_dependency_chain function)
**Tests Added**: (to be added next)
**Commands Run**: (to be run after tests added)

---

### 3.4 One-Session PySCF Execution (C3 Core)

- [ ] Implement _run_pyscf_chain(chain_steps, calculation, run_mode, target_step_ulid)
- [ ] Single python process/session per chain
- [ ] Import PySCF once, execute steps sequentially root→target
- [ ] Each step clears artifacts dir before running
- [ ] Maintain in-memory produced objects keyed by state type
- [ ] Each non-SCF step ALWAYS reruns (ignore done flags)
- [ ] SCF init_guess control (per run_mode rules)
- [ ] Integrate into CalculationRunner:
  - [ ] RunStep for PySCF machine steps resolves chain and runs in one session
  - [ ] RunCalc for PySCF executes left→right with proper init_guess control
- [ ] Add integration tests:
  - [ ] RunStep(mp2) executes scf then mp2 in one session
  - [ ] RunStep(scf) forbids chkfile init_guess
  - [ ] RunCalc(incremental) allows chkfile init_guess for scf if checkpoint exists
  - [ ] RunCalc(full) forbids chkfile init_guess
  - [ ] Verify artifacts clearing behavior

**Files Changed**: (to be filled)
**Tests Added**: (to be filled)
**Commands Run**: (to be filled)

---

### 3.5 Step Spec Storage Invariants (C5)

- [ ] Enforce/verify via tests:
  - [ ] step.yaml contains meta + machine step_type + parameters
  - [ ] step.yaml contains no structure fields
  - [ ] Downstream steps do NOT redundantly store SCF selections
  - [ ] chkfile path is fixed convention (not stored as parameter)
- [ ] Add unit tests that load created step.yaml and assert invariants

**Files Changed**: (to be filled)
**Tests Added**: (to be filled)
**Commands Run**: (to be filled)

---

## Compatibility Deviations

(Record any deviations from constitution here)

---

## Test Results

### Unit Tests
- [ ] tests/unit/test_pyscf_runner.py
- [ ] tests/unit/test_workflow_materialization_phase3b.py
- [ ] tests/unit/test_workflow.py

### Integration Tests
- [ ] tests/integration/test_pyscf_execution.py
- [ ] tests/integration/test_incremental_run.py

---

## Known Limitations / Deferrals

(To be filled at completion)

---

## Close-Out Summary

(To be filled at completion)

