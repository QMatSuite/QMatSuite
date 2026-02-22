# Phase 2 Close-Out Report

**Date**: Phase 2 completion
**Scope**: CLI support for structure_kind/engine_family + normalization contract documentation

## Summary

Phase 2 close-out items completed successfully. All required tasks have been implemented and tested.

## Changes Made

### 1. CLI Support for structure_kind and engine_family

**Files Modified**:
- `src/qmatsuite/cli/main.py`: Added `--structure-kind` and `--engine-family` options to `init_calculation_command`
  - Defaults: `structure_kind` defaults to "periodic", `engine_family` defaults to "qe" for periodic, "pyscf" for molecule
  - Validation: Validates `structure_kind` is "periodic" or "molecule"
  - Immutability: Fields are set only during creation (no configure command exists to modify them)

- `src/qmatsuite/core/templates.py`: Added defaults for structure_kind/engine_family in template copying
  - If template calculation.yaml is missing these fields, defaults are applied (periodic/qe or molecule/pyscf)

**New Files**:
- `tests/cli/test_calculation_structure_kind_engine_family.py`: Comprehensive test suite for CLI options
  - Test default behavior (periodic/qe)
  - Test molecule structure_kind (molecule/pyscf)
  - Test explicit engine_family override
  - Test invalid structure_kind rejection
  - Test molecule with qe engine_family (explicit override)

### 2. Normalization Contract Documentation

**Files Modified**:
- `PHASE2_COMPAT_NOTES.md`: Added "Step Type Normalization Contract" section
  - Definitions of public vs machine step types
  - Normalization rules (storage, hash computation, step loading, API boundary)
  - Mandatory normalization points
  - Helper functions documentation
  - Enforcement requirements

- `PHASE2_COMPAT_NOTES.md`: Added "structure_kind and engine_family CLI Support" section
  - Documented CLI options and defaults
  - Documented immutability enforcement

## Test Results

### New Tests
- `tests/cli/test_calculation_structure_kind_engine_family.py`: **5 tests, all passing**

### Regression Tests
- `tests/integration/test_incremental_run.py`: **15 tests, all passing**
- `tests/unit/test_api_step_artifacts.py`: **9 tests, all passing**

**Total**: 29 tests passing, 0 failures

### Commands Run

```bash
# New CLI tests
pytest tests/cli/test_calculation_structure_kind_engine_family.py -v
# Result: 5 passed

# Regression tests (incremental run)
pytest tests/integration/test_incremental_run.py -v
# Result: 15 passed

# Regression tests (step artifacts)
pytest tests/unit/test_api_step_artifacts.py -v
# Result: 9 passed

# Combined
pytest tests/cli/test_calculation_structure_kind_engine_family.py tests/integration/test_incremental_run.py tests/unit/test_api_step_artifacts.py -v
# Result: 29 passed, 0 failed
```

## Architecture Compliance

All Phase 2 invariants maintained:
1. ✅ `step.yaml` remains the ONLY execution SSOT (contains machine types only)
2. ✅ `calculation.yaml` stores structure_kind and engine_family (immutable metadata)
3. ✅ `engine_family` used only for materialization (not written to step.yaml)
4. ✅ Generalized steps never written to disk
5. ✅ Step type normalization contract documented and enforced

## Notes

- **Immutability Enforcement**: `structure_kind` and `engine_family` are immutable after creation. No configure command exists to modify these fields, so immutability is enforced by design (no code path exists to change them).

- **Template Support**: Templates copy existing calculation.yaml files. If structure_kind/engine_family are missing from the template, defaults are applied (periodic/qe or molecule/pyscf based on structure_kind if provided, otherwise periodic/qe).

- **Backward Compatibility**: All existing functionality remains unchanged. New CLI options are optional (defaults provided).

## Exit Condition Status

✅ All tests in (1) pass (29 tests total)
✅ CLI support in (2) implemented + tested (5 new tests)
✅ Notes updated per (3) (normalization contract documented)

**Phase 2 close-out complete.**

