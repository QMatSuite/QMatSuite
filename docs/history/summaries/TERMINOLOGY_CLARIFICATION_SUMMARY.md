# Directory Terminology Clarification Summary

## Executive Summary

Clarified and standardized the semantics of "raw_dir" and "working_dir" across the codebase to distinguish:
1. **Test fixture directories** (read-only templates) from
2. **Product runtime directories** (writable execution directories)

This prevents confusion that recently caused regressions around pseudo placement and `run_step` working_dir.

## Terminology Map

| Term in code | Context | Current meaning | Recommended standard meaning | Notes/callsites |
|-------------|---------|----------------|------------------------------|-----------------|
| `raw_dir` (tests) | Tests | Fixture/template directory containing input files | `fixture_dir` or `template_dir` | `tests/integration/test_pw_step_specs.py`, `tests/integration/test_pw_scf_ibrav_step_specs.py` - READ-ONLY template directory |
| `raw_dir` (product) | Product | Runtime I/O directory: `project/calc/raw/` | `calculation.raw_dir` (keep as-is) | `src/qmatsuite/calculation/calculation.py`, `src/qmatsuite/calculation/runner.py` - WRITABLE runtime directory |
| `working_dir` (tests base) | Tests | Base test directory (may contain fixtures) | Keep `working_dir` | `tests/core/qe_step_runner.py` - Base directory for test artifacts |
| `working_dir` (tests execution) | Tests | Sandbox directory where QE executes | `sandbox_dir` or `execution_dir` | `tests/integration/test_pw_step_specs.py` - Created via `create_sandbox_working_dir()` |
| `working_dir` (product) | Product | Same as `calculation.raw_dir` (I/O directory) | Keep `working_dir` in calculation model | `src/qmatsuite/calculation/calculation.py` - Runtime I/O directory name |
| `sandbox_dir` | Tests | Temporary execution directory | `sandbox_dir` (standard) | `tests/core/qe_step_runner.py::create_sandbox_working_dir()` - Execution sandbox |
| `output_dir` | Both | Directory where generated inputs are written | `output_dir` (keep as-is) | `materialize_step_spec()` - Can be fixture_dir (tests) or raw_dir (product) |
| `outdir` | Both | QE scratch directory (`./outdir` relative to execution) | `outdir` (keep as-is) | QE-specific, always relative to execution directory |

## Current Callsites with Meanings

### Test Fixture Directories (should be renamed to `fixture_dir`)

1. **`tests/integration/test_pw_step_specs.py:75`**
   - `raw_dir = working_dir / "raw"` 
   - **Meaning**: Read-only template directory for materialized step specs
   - **Action**: Renamed to `fixture_dir` with clarifying comments

2. **`tests/integration/test_pw_scf_ibrav_step_specs.py:94`**
   - `raw_dir = working_dir / "raw"`
   - **Meaning**: Read-only template directory for materialized step specs
   - **Action**: Renamed to `fixture_dir` with clarifying comments

3. **`tests/unit/test_qe_geometry_roundtrip.py:46`**
   - `raw_dir = working_dir / "raw"`
   - **Meaning**: Template directory (simpler test, no QE execution)
   - **Action**: Less critical, but could be renamed for consistency

### Product Runtime Directories (correct, keep as-is)

4. **`src/qmatsuite/calculation/calculation.py:36`**
   - `calculation.raw_dir` property
   - **Meaning**: Runtime I/O directory `project/calc/raw/` (writable)
   - **Action**: Keep as-is (correct semantics)

5. **`src/qmatsuite/calculation/runner.py:90`**
   - `raw_dir = calculation.raw_dir`
   - **Meaning**: Runtime I/O directory for execution
   - **Action**: Keep as-is (correct semantics)

6. **`src/qmatsuite/calculation/io.py:27`**
   - `CalculationIO.raw_dir` property
   - **Meaning**: Runtime I/O directory subdirectory name
   - **Action**: Keep as-is (correct semantics)

### Test Analysis Artifacts (simulating product structure)

7. **`tests/unit/test_analysis_artifacts.py`**
   - Multiple `raw_dir = calculation_dir / "raw"` or `tmp_path / "raw"`
   - **Meaning**: Simulating product `calculation.raw_dir` structure for analysis tests
   - **Action**: Keep as-is (correctly simulating product structure)

## Minimal Code Changes Proposed

### 1. Test Integration Files (renamed `raw_dir` → `fixture_dir`)

**File**: `tests/integration/test_pw_step_specs.py`
- **Change**: Renamed `raw_dir` variable to `fixture_dir` with clarifying comments
- **Rationale**: Makes it clear this is a read-only template, not a runtime directory

**File**: `tests/integration/test_pw_scf_ibrav_step_specs.py`
- **Change**: Renamed `raw_dir` variable to `fixture_dir` with clarifying comments
- **Rationale**: Same as above

### 2. Test Harness Documentation

**File**: `tests/core/qe_step_runner.py`
- **Change**: Added comprehensive terminology clarification in module docstring
- **Rationale**: Documents the distinction between fixture_dir, sandbox_dir, and product raw_dir

**File**: `tests/core/qe_step_runner.py::create_sandbox_working_dir()`
- **Change**: Enhanced docstring with terminology clarification
- **Rationale**: Explains the purpose and distinction from product directories

### 3. Documentation Updates

**File**: `docs/JOB_IO_DIRECTORY_SEMANTICS.md`
- **Change**: Added "Terminology: Product vs Tests" section
- **Rationale**: Clarifies that product "raw" is different from test fixtures

**File**: `docs/TERMINOLOGY_DIRECTORIES.md` (NEW)
- **Change**: Created comprehensive terminology reference document
- **Rationale**: Single source of truth for directory terminology

## Verification

### Test Harness Behavior Confirmed

✅ **`tests/core/qe_step_runner.py`**:
- `create_sandbox_working_dir()` creates temporary sandbox directories
- `run_and_verify_step()` uses `working_dir` as execution directory
- Tests never execute QE in fixture directories

✅ **Integration Tests**:
- `test_pw_step_specs.py`: Uses `fixture_dir` (read-only), creates `sandbox_dir` for execution
- `test_pw_scf_ibrav_step_specs.py`: Same pattern
- Pseudos materialized to `sandbox_dir/pseudo/` (standalone mode)
- `run_step()` called with `working_dir=sandbox_dir`

✅ **Product Code**:
- `calculation.raw_dir` correctly represents runtime I/O directory
- `runner.py` uses `calculation.raw_dir` as execution directory
- No changes needed to product code

### Test Results

✅ All tests pass:
- `tests/integration/test_pw_step_specs.py::TestPWStepSpecsExecution::test_pw_specs_generate_and_run` ✓
- `tests/integration/test_pw_scf_ibrav_step_specs.py::TestPWScfIbravStepSpecsExecution::test_pw_scf_ibrav_specs_generate_and_run` ✓

## Key Invariants Maintained

1. ✅ Tests never execute QE in directories under repo root (except reading fixtures)
2. ✅ Test fixture directories remain read-only (no execution, no pseudo materialization)
3. ✅ All QE execution in tests happens in temp sandbox directories
4. ✅ Product `calculation.raw_dir` semantics unchanged (writable runtime directory)
5. ✅ No new architectural layers or API changes
6. ✅ Existing DAG model and variable separation preserved

## Files Changed

1. `tests/integration/test_pw_step_specs.py` - Renamed `raw_dir` → `fixture_dir`, added comments
2. `tests/integration/test_pw_scf_ibrav_step_specs.py` - Renamed `raw_dir` → `fixture_dir`, added comments
3. `tests/core/qe_step_runner.py` - Added terminology clarification in docstrings
4. `docs/JOB_IO_DIRECTORY_SEMANTICS.md` - Added terminology distinction section
5. `docs/TERMINOLOGY_DIRECTORIES.md` - NEW: Comprehensive terminology reference

## Summary

The terminology clarification is complete with minimal code changes:
- **2 integration test files**: Renamed `raw_dir` → `fixture_dir` for clarity
- **1 test harness file**: Enhanced documentation
- **2 documentation files**: Added terminology clarifications
- **0 product code changes**: Product semantics were already correct

All tests pass and the distinction between test fixtures and product runtime directories is now clear and documented.

