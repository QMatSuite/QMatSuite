# Phase 3C Test Fixes Report

This document summarizes the fixes implemented to resolve 5 failing tests while maintaining the Phase 3C architecture and contract.

## Summary

All 5 failing tests are now passing. The fixes were minimal and focused on:
1. Early PySCF availability check for graceful failure
2. Adding missing result fields (homo_index, lumo_index, mo_energies_alpha/beta)
3. Creating pyscf.log file in chain execution
4. Updating TD registry contract test to match our contract

## Files Changed

1. **src/quantumvitas/engine/pyscf_engine.py**
   - Moved PySCF availability check before step.yaml read in `run_step_with_chain()`
   - This allows graceful failure messages when PySCF is not installed

2. **src/quantumvitas/engines/pyscf/chain_execution.py**
   - Added `homo_index` and `lumo_index` to RHF/RKS results
   - Added `mo_energies_alpha` and `mo_energies_beta` to UHF results
   - Added pyscf.log file creation (sets `mf.stdout` to log file handle)

3. **tests/unit/test_pyscf_chain_registry_contract.py**
   - Updated `test_pyscf_td_registry_contract` to expect `requires_structure=False` and `requires_charge_density=False`
   - Aligned test with our contract: TD consumes mf, does not require structure

## Results JSON Schema Changes

### Added Keys for RHF/RKS (Restricted methods):
- `homo_index` (int or None): Index of HOMO orbital
- `lumo_index` (int or None): Index of LUMO orbital

### Added Keys for UHF/UKS (Unrestricted methods):
- `mo_energies_alpha` (list of float): Alpha spin MO energies
- `mo_energies_beta` (list of float): Beta spin MO energies

These keys are added to the `results.json` file written by `_run_scf_in_session()` in chain execution.

## pyscf.log File Location

The `pyscf.log` file is created in the `step_artifacts_dir` (which is `working_dir` for single-step execution via `_run_scf()`). 

For chain execution:
- Location: `step_artifacts_dir / "pyscf.log"`
- For single-step execution via `_run_scf()`: `working_dir / "pyscf.log"` (matches test expectations)
- For chain execution via `run_step_with_chain()`: `calculation_raw_dir / "step_artifacts" / step_ulid / "pyscf.log"`

The log file is created by setting `mf.stdout = log_handle` in `_run_scf_in_session()`, which captures PySCF's verbose output.

## TD Registry Contract Confirmation

The TD registry contract test now correctly expects:
- `requires_structure = False` (TD consumes mf from state, does not need structure)
- `requires_charge_density = False` (TD consumes mf from state, not raw charge density)
- `consumes_state = "mf"` (TD consumes mean-field state from SCF)
- `produces_state = None` (TD does not produce new persisted state)

This aligns with our contract: only SCF requires structure; post-SCF steps (MP2/TD) consume mf from state.

## Test Results

All targeted test suites pass:
- `tests/integration/test_pyscf_execution.py` - 11 passed
- `tests/integration/test_pyscf_phase3c.py` - 5 passed
- `tests/unit/test_pyscf_integration.py` - 35 passed
- `tests/unit/test_pyscf_chain_registry_contract.py` - 3 passed

## Architecture Compliance

All fixes maintain the Phase 3C architecture:
- Chain-only runner: ✅ (no changes)
- Only SCF receives structure: ✅ (no changes)
- MP2/TD consume mf, do not receive structure: ✅ (no changes)
- Single source of truth (step.yaml): ✅ (PySCF availability check happens before step.yaml read, but SSOT is preserved)

