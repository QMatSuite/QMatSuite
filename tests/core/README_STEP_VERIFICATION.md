# Standardized QE Step Execution and Verification

This document describes the centralized step execution and verification system for QE tests.

## Overview

All QE tests should use the standardized functions in `tests/core/` instead of implementing their own execution and verification logic. This ensures:

1. **Consistency**: All tests use the same verification logic
2. **Maintainability**: Verification logic is centralized and easy to update
3. **Automatic Step Detection**: Step type is auto-detected from input files
4. **Automatic Verification**: Verification method is selected based on step type

## Core Functions

### `run_and_verify_step_with_assert()`

The main function for running and verifying QE steps in tests.

```python
from tests.core import run_and_verify_step_with_assert

step_result = run_and_verify_step_with_assert(
    input_file=Path("si.1_scf.in"),
    qe_engine=qe_engine,
    working_dir=tmp_path,
    reference_file=Path("reference_out/si.1_scf.out"),  # Optional
    category="4_Si_DOS",  # Optional, for threshold selection
    timeout=300,  # Optional
    project_root=project_root  # Optional, auto-detected
)
```

This function:
1. **Auto-detects step type** from input file (scf, nscf, dos, bands, ph, etc.)
2. **Sets outdir and pseudo_dir** to `temp/outdir` and `temp/pseudo`
3. **Runs the step** using `qe_engine.run_step()`
4. **Verifies the result** based on step type:
   - **scf**: Compares total energy with reference
   - **nscf**: Compares Fermi energy with reference
   - **ph**: Compares frequencies with reference (if available)
   - **Other**: Checks JOB DONE

### `verify_step_result()`

Lower-level function that only verifies a step result without running it.

```python
from tests.core import verify_step_result

success, message = verify_step_result(
    step_result=step_result,
    reference_file=Path("reference_out/si.1_scf.out"),
    category="4_Si_DOS"
)
```

## Verification Logic

### SCF Steps
- **Verification**: Total energy comparison
- **Tolerance**: From `tests/core/thresholds.py` (default: 3e-6 Ry)
- **Pattern**: `! total energy = X.XXXXX Ry`

### NSCF Steps
- **Verification**: Fermi energy comparison
- **Tolerance**: 0.01 Ry (from `FERMI_ENERGY_TOLERANCE`)
- **Patterns**:
  - `the Fermi energy is X.XXXXX ev`
  - `Fermi energy = X.XXXXX Ry`
  - `the Fermi energy is X.XXXXX Ry`

### PH Steps
- **Verification**: Frequency comparison (if reference available)
- **Tolerance**: 0.015 THz (default)
- **Fallback**: JOB DONE if frequencies not available

### Other Steps
- **Verification**: JOB DONE check only

## Example Usage

### Before (Old Way)

```python
def test_scf(self, qe_engine, tmp_path):
    # Parse, modify, generate, run, verify - all manual
    result = run_input_roundtrip_execution(...)
    assert result["run_success"]
    
    # Manual energy extraction and comparison
    output_content = Path(result["output_file"]).read_text()
    energy_pattern = r"!\s+total energy\s+=\s+([-\d.]+)\s+Ry"
    output_match = re.search(energy_pattern, output_content)
    # ... many more lines of manual verification
```

### After (New Way)

```python
from tests.core import run_and_verify_step_with_assert

def test_scf(self, qe_engine, tmp_path):
    # One function call does everything
    step_result = run_and_verify_step_with_assert(
        input_file=Path("si.1_scf.in"),
        qe_engine=qe_engine,
        working_dir=tmp_path,
        reference_file=Path("reference_out/si.1_scf.out"),
        category="4_Si_DOS"
    )
    # Verification is automatic - no manual energy extraction needed!
```

## Migration Guide

1. **Replace** `run_input_roundtrip_execution()` calls with `run_and_verify_step_with_assert()`
2. **Remove** manual energy/Fermi energy extraction code
3. **Remove** manual `set_outdir_to_temp()` and `set_pseudo_dir_to_temp()` calls (handled automatically)
4. **Keep** retry mechanisms if needed for intermittent errors
5. **Update** imports to use `from tests.core import run_and_verify_step_with_assert`

## Benefits

- **Less Code**: Tests are much shorter and cleaner
- **Consistency**: All tests use the same verification logic
- **Maintainability**: Update verification logic in one place
- **Automatic**: Step type detection and verification method selection are automatic
- **Type Safety**: Uses `StepResult` dataclass for structured results

