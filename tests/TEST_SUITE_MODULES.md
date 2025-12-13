# QE Test Suite Module Testing Scripts

This directory contains test scripts for different Quantum ESPRESSO modules, following the official test-suite structure and logic.

## Overview

Each module has its own test script that:
1. Reads `jobconfig` to get test order and files
2. Runs tests in the specified order (supporting calculation tests with multiple steps)
3. Compares output with benchmark files to determine pass/fail
4. Reports results in a format similar to `testcode.py`

## Test Scripts

所有 Makefile 要求的模块都已实现：

✅ **pw** - `run_pw_tests_official_style.py`  
✅ **cp** - `run_cp_tests.py`  
✅ **ph** - `run_ph_tests.py`  
✅ **pp** - `run_pp_tests.py`  
✅ **hp** - `run_hp_tests.py`  
✅ **tddfpt** - `run_tddfpt_tests.py`  
✅ **kcw** - `run_kcw_tests.py`  
✅ **epw** - `run_epw_tests.py`  
✅ **zg** - `run_zg_tests.py`  
✅ **all_currents** - `run_all_currents_tests.py`  
✅ **xsd-pw** - `run_xsd_pw_tests.py`  

### Core Modules

#### `run_pw_tests_official_style.py`
Tests for `pw.x` (Plane-Wave Self-Consistent Field calculations)
- **Executables**: `pw.x`
- **Categories**: `pw_atom`, `pw_scf`, `pw_metal`, `pw_noncolin`, etc.
- **Usage**:
  ```bash
  python3 tests/run_pw_tests_official_style.py --category pw_atom
  python3 tests/run_pw_tests_official_style.py --category pw_all
  ```

#### `run_ph_tests.py`
Tests for `ph.x` (Phonon calculations)
- **Executables**: `pw.x` (step 1), `ph.x` (step 2), `q2r.x`, `matdyn.x`, etc.
- **Categories**: `ph_base`, `ph_metal`, `ph_U_metal_us`, etc.
- **Calculation**: Most ph tests require running `pw.x` first, then `ph.x`
- **Usage**:
  ```bash
  python3 tests/run_ph_tests.py --category ph_base
  python3 tests/run_ph_tests.py  # Run all ph categories
  ```

#### `run_pp_tests.py`
Tests for `pp.x` (Post-processing)
- **Executables**: `pw.x` (step 1), `pp.x` or `ppacf.x` (step 2)
- **Categories**: `pp_base`, etc.
- **Calculation**: Requires `pw.x` SCF calculation first
- **Usage**:
  ```bash
  python3 tests/run_pp_tests.py --category pp_base
  ```

#### `run_cp_tests.py`
Tests for `cp.x` (Car-Parrinello Molecular Dynamics)
- **Executables**: `cp.x`
- **Categories**: `cp_al_edft`, `cp_cluster`, `cp_h2o`, etc.
- **Usage**:
  ```bash
  python3 tests/run_cp_tests.py --category cp_h2o
  ```

#### `run_hp_tests.py`
Tests for `hp.x` (Hubbard U parameter calculations)
- **Executables**: `pw.x` (step 1,2), `hp.x` (step 3,4)
- **Categories**: `hp_*`
- **Calculation**: Requires `pw.x` SCF calculation first
- **Usage**:
  ```bash
  python3 tests/run_hp_tests.py
  ```

#### `run_tddfpt_tests.py`
Tests for TDDFPT (Time-Dependent Density Functional Perturbation Theory)
- **Executables**: `pw.x`, `turbo_lanczos.x`, `turbo_spectrum.x`, `turbo_eels.x`, `turbo_magnon.x`
- **Categories**: `tddfpt_CH4`, `tddfpt_eels-si`, etc.
- **Calculation**: Complex multi-step calculations
- **Usage**:
  ```bash
  python3 tests/run_tddfpt_tests.py --category tddfpt_CH4
  ```

## Common Options

All test scripts support the following options:

- `--qe-path PATH`: Path to QE bin directory (default: `$HOME/src/q-e-qe-7.5/bin`)
- `--test-dir PATH`: Path to QE test-suite directory (default: inferred from `--qe-path`)
- `--category NAME`: Run specific test category (default: run all categories for the module)
- `--timeout SECONDS`: Timeout per test in seconds (default: 60-120 depending on module)
- `--max-tests N`: Maximum number of tests per category

## Base Framework

### `test_qe_module_base.py`

Provides common functionality for all module tests:

- `parse_jobconfig()`: Parse jobconfig file for a specific module prefix
- `run_module_test()`: Run a single QE module test
- `run_test_category()`: Run all tests in a category (supports calculation tests)
- `compare_with_benchmark()`: Compare test output with benchmark files

## Calculation Tests

Many QE modules require sequential calculations where intermediate files must be preserved:

1. **ph tests**: `pw.x` → `ph.x` (requires `pwscf.save/` directory)
2. **pp tests**: `pw.x` → `pp.x` (requires charge density files)
3. **hp tests**: `pw.x` → `hp.x` (requires wavefunctions)
4. **tddfpt tests**: `pw.x` → `turbo_lanczos.x` → `turbo_spectrum.x`

The test framework automatically:
- Uses a shared working directory for calculation tests
- Preserves intermediate files (`.save/`, charge density, etc.)
- Runs steps in the correct order
- Compares final results with benchmarks

## Executable Mapping

Each module script defines an `executable_map` that maps step arguments (from `jobconfig`) to QE executables:

```python
# Example from run_ph_tests.py
executable_map = {
    "1": "pw.x",      # Step 1: SCF calculation
    "2": "ph.x",      # Step 2: Phonon calculation
    "3": "q2r.x",     # Step 3: q2r interpolation
    "4": "matdyn.x",  # Step 4: Dynamical matrix diagonalization
    # ...
}
```

## Test Results

Each test script outputs:
- Individual test results (pass/fail with timing)
- Category summaries
- Overall summary with pass/fail statistics
- List of failed tests with error messages

Example output:
```
[1/18] Category: ph_base
  Running 9 tests...
  ph_base: 8 passed, 1 failed
    ✓ PASS (12.3s): c.scf.in - Energy matches: -11.23456789 Ry
    ✓ PASS (8.5s): c.phG.in - JOB DONE
    ✗ FAIL (0.1s): ni.phX.in - ph.x returned 1

============================================================
OVERALL SUMMARY
============================================================
Total tests: 9
Passed: 8 (88.9%)
Failed: 1 (11.1%)
```

## Integration with Official Test Suite

These scripts are designed to work with the official QE test-suite structure:
- Read from `jobconfig` file (same format as `testcode.py`)
- Use the same test ordering and file structure
- Compare with benchmark files in the same format
- Support the same calculation patterns

#### `run_kcw_tests.py`
Tests for `kcw.x` (Koopmans-compliant Wannier functions)
- **Executables**: `pw.x`, `wannier90.x`, `pw2wannier90.x`, `kcw.x`
- **Categories**: `kcw_*`
- **Calculation**: Complex multi-step: pw.x → wannier90.x -pp → pw2wannier90.x → wannier90.x → kcw.x
- **Usage**:
  ```bash
  python3 tests/run_kcw_tests.py
  ```

#### `run_epw_tests.py`
Tests for `epw.x` (Electron-phonon coupling)
- **Executables**: `pw.x`, `ph.x`, `epw.x`, `q2r.x`, `matdyn.x`, `postahc.x`, `nscf2supercond.x`
- **Categories**: `epw_base`, `epw_metal`, `epw_super`, etc.
- **Calculation**: Very complex multi-step calculations
- **Usage**:
  ```bash
  python3 tests/run_epw_tests.py --category epw_base
  ```

#### `run_zg_tests.py`
Tests for `ZG.x` (Zero-gap calculations)
- **Executables**: `ZG.x`
- **Categories**: `zg_conf`
- **Usage**:
  ```bash
  python3 tests/run_zg_tests.py
  ```

#### `run_all_currents_tests.py`
Tests for `all_currents.x`
- **Executables**: `all_currents.x`
- **Categories**: `all_currents_*`
- **Usage**:
  ```bash
  python3 tests/run_all_currents_tests.py
  ```

#### `run_xsd_pw_tests.py`
XML Schema validation tests for `pw.x` input files
- **Purpose**: Validates that pw.x input files conform to XML schema
- **Method**: Uses `validate_xsd_pw.py` from test-suite
- **Usage**:
  ```bash
  python3 tests/run_xsd_pw_tests.py
  ```

## Additional Modules

Other modules that may be added in the future:
- `run_image_tests.py` (Image calculations)
- `run_oscdft_tests.py` (Orbital-Spin Constrained DFT)
- `run_pioud_tests.py` (PIoud calculations)

