# Phase 3C Implementation Summary

**Status**: Core implementation complete, testing in progress  
**Date**: 2025-01-10

## Overview

Phase 3C implements PySCF runner semantics and UI behavior alignment for PySCF engine-family support. This includes run mode plumbing, dependency chain execution, artifact directory management, and checkpoint handling.

## Files Changed

### Core Implementation

1. **src/qmatsuite/calculation/runner.py**
   - Added run_mode injection into step.options before execution
   - Added per-step artifact directory creation and clearing
   - Passes step_artifacts_dir to engine via step.options

2. **src/qmatsuite/engine/pyscf_engine.py**
   - Added run_mode reading from step.options
   - Added allow_chkfile_init_guess control based on run_mode
   - Added per-step artifact directory support
   - Added `run_step_with_chain()` method for one-session chain execution

3. **src/qmatsuite/engines/pyscf/runner.py**
   - Added `run_job_chain()` function for chain execution
   - Updated `run_job()` to read allow_chkfile_init_guess from job.json
   - Passes allow_chkfile_init_guess to run_scf()

4. **src/qmatsuite/engines/pyscf/chain_execution.py** (NEW)
   - Implements one-session chain execution
   - Maintains in-memory state objects (mol, mf) between steps
   - Handles step artifacts directory clearing
   - Implements init_guess control per step (target vs prerequisite)

5. **src/qmatsuite/engines/pyscf/__main__.py**
   - Updated to detect chain execution vs single step
   - Routes to run_job_chain() or run_job() accordingly

6. **src/qmatsuite/api.py**
   - Updated `run_step()` to detect PySCF engine
   - Added dependency chain resolution for PySCF steps
   - Routes PySCF steps to run_step_with_chain()
   - Preserves QE/W90 execution path (unchanged)

### Supporting Code

7. **src/qmatsuite/engines/pyscf/chain.py**
   - Already had resolve_dependency_chain() implementation
   - Fixed recursive resolution logic to properly build chains

8. **tests/unit/test_pyscf_chain.py** (NEW)
   - Unit tests for dependency chain resolution
   - Tests nearest-provider rule, missing provider errors, etc.

## Implementation Status

### Completed Tasks

- ✅ **Task A**: Run mode plumbing - run_mode wired through step.options
- ✅ **Task D**: Artifact directories - per-step artifact dirs created and cleared
- ✅ **Task E**: Chkfile wiring - allow_chkfile_init_guess wired through job.json
- ✅ **Task B**: PySCF chain execution - run_job_chain() and chain_execution.py implemented
- ✅ **Task C**: Engine entry point - run_step_with_chain() added to PySCFEngine

### Remaining Work

- ⏳ **Tests**: Integration tests need to be added and run
  - RunCalc incremental vs full (SCF behavior difference)
  - RunStep(X) one-session execution
  - SCF → MP2 chain execution
  - Missing dependency error cases

## Known Issues

1. **Import Error**: PySCFEngine class was accidentally truncated during edit. Fixed by restoring from git.

2. **Test Environment**: Tests require proper Python path setup (.venv activation or PYTHONPATH).

## Architecture Decisions (As Implemented)

1. **Run mode plumbing**: Uses step.options dict (no signature changes, backward compatible)
2. **Run Step entry point**: PySCF-specific path in QMSService.run_step() (QE/W90 unchanged)
3. **PySCF execution model**: New run_job_chain() function (clear separation from single-step execution)
4. **Artifact directories**: Per-step dirs at `raw/step_artifacts/{step_ulid}` (matches spec)
5. **Chkfile control**: Wired through job.json allow_chkfile_init_guess parameter (explicit, clear)
6. **Chain execution**: Engine-specific run_step_with_chain() method (optional, QE unchanged)

## Next Steps

1. Add integration tests for chain execution
2. Test run_mode behavior (incremental vs full)
3. Verify QE/W90 behavior unchanged
4. Run full test suite and fix any regressions
