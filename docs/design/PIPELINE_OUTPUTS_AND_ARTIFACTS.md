# Pipeline Outputs and Artifacts

**Version**: 1.0  
**Last Updated**: 2026-01-XX  
**Status**: Current Behavior Documentation

---

## Overview

This document describes the output file naming conventions, artifact recognition system, and CLI behavior for QMatSuite calculation steps. It covers the recent standardization of output capture, Wannier90 integration fixes, and the artifacts system for GUI Analysis.

**Key Principles**:
- Output files use fixed naming: `{step_type}.out` and `{step_type}.err`
- Input files may be versioned (e.g., `scf.in`, `scf-1.in`), but outputs are **never versioned**
- Output filenames are **never derived from input filenames**
- Artifacts are recognized per step type for GUI display
- Service/engine layers provide output paths; CLI/UI only select by priority

---

## Output Capture Policy

### Fixed Filenames

For every step, stdout and stderr are captured to fixed filenames:

- **Stdout**: `{step_type}.out` (e.g., `scf.out`, `w90_preproc.out`)
- **Stderr**: `{step_type}.err` (e.g., `scf.err`, `w90_preproc.err`)

These files are **always overwritten** on each run (opened with `mode="w"`).

### Input Versioning vs Output Overwriting

**Input files** (e.g., `scf.in`, `nscf.in`) may be versioned:
- First run: `scf.in`
- Second run: `scf-1.in` (if `scf.in` already exists)
- Third run: `scf-2.in` (if `scf-1.in` already exists)

**Output files** are **never versioned**:
- All runs write to the same file: `scf.out`, `scf.err`
- Files are overwritten on each run
- This ensures consistent naming for parsing, analysis, and GUI display

### Invariant: Never Derive Output Filenames from Input Filenames

**Critical rule**: Output filenames are determined by `step_type`, not by input filename.

- ✅ Correct: `scf-1.in` → `scf.out` (based on `step_type="scf"`)
- ❌ Wrong: `scf-1.in` → `scf-1.out` (derived from input filename)

This invariant ensures:
- Consistent output naming regardless of input versioning
- Predictable file locations for parsing and analysis
- No path confusion in CLI/UI

**Implementation**: The `get_capture_paths(working_dir, step_type)` function centralizes this naming convention.

---

## Wannier90 Workflow Notes

### Step Execution

The Wannier90 pipeline uses `wannier90.x` twice:

1. **`w90_preproc`**: `wannier90.x -pp <seedname>`
   - Generates `<seedname>.nnkp` file
   - Stdout/stderr captured to `w90_preproc.out/.err`

2. **`w90_run`**: `wannier90.x <seedname>`
   - Main MLWF optimization
   - Generates `<seedname>.wout` (primary artifact)
   - Stdout/stderr captured to `w90_run.out/.err`

**Note**: These commands may not produce meaningful stdout, but we still capture stdout/stderr to maintain consistency with all engines.

### Structure and Units Fixes

#### Unit Cell Units

**Issue**: Previously, `unit_cell_cart` in `.win` files was incorrectly converted from Angstrom to Bohr, causing "Direct lattice mismatch" errors.

**Fix**: `unit_cell_cart` must be in **Angstrom** (not Bohr). The lattice matrix is taken directly from `structure.lattice.matrix` without unit conversion.

**Consistency Check**: An optional internal consistency assertion verifies:
```
unit_cell_cart @ atoms_frac == cartesian_coords (in Angstrom)
```

#### Atomic Positions

- `atoms_frac` comes directly from `structure.frac_coords` (fractional coordinates)
- No conversion needed; Wannier90 expects fractional coordinates

#### K-Points Inheritance

- K-points in `.win` files are **inherited from the NSCF step**
- The k-point list in `.win` (and thus `.nnkp`) must be the **exact same list and order** as used by NSCF
- Do not generate k-points from `mp_grid` for `.win`; copy them directly from NSCF
- Fail-fast consistency checks ensure `len(kpoints) == mp_grid[0]*mp_grid[1]*mp_grid[2]`

#### QE Input Generation

QE input generation now always uses `ATOMIC_POSITIONS {crystal}` (fractional coordinates) for:
- Better readability
- Stability (fractional coordinates are invariant under lattice transformations)
- Consistency with Wannier90 workflows

---

## Artifacts & Analysis Selection

### Artifacts Recognition System

Each step type has a rule system that identifies expected artifact files (beyond stdout/stderr). This enables the GUI "Analysis" tab to show relevant output files.

### Artifact Rules by Step Type

#### Wannier90 Steps

- **`w90_preproc`**:
  - Primary artifact: `<seedname>.nnkp`
  - Stdout/stderr: `w90_preproc.out/.err`

- **`pw2wannier90`**:
  - Primary artifacts: `<seedname>.amn`, `<seedname>.mmn`, `<seedname>.eig`
  - Stdout/stderr: `pw2wannier90.out/.err`
  - Note: Artifacts are only listed if they exist (some may be optional)

- **`w90_run`**:
  - Primary artifact: `<seedname>.wout` (main output for GUI display)
  - Stdout/stderr: `w90_run.out/.err`

#### Bands Step

- **`bands`**:
  - Artifacts derived from `filband` parameter:
    - `<filband>` (e.g., `si.bands.dat`)
    - `<filband>.gnu` (e.g., `si.bands.dat.gnu`) — **preferred default**
    - `<filband>.rap` (e.g., `si.bands.dat.rap`)
  - Stdout/stderr: `bands.out/.err`
  - If `filband` is not specified, the system attempts to find files matching `*.bands.dat*` pattern

### Default Selection Priority

When displaying artifacts in the GUI "Analysis" tab, the default selection follows this priority:

1. **Primary artifact** (e.g., `.wout` for `w90_run`, `.gnu` for `bands`)
   - Must exist and be non-empty (size > 0)
   - For `bands`, prefer `.gnu` over `.dat`

2. **Stdout capture** (`{step_type}.out`)
   - Fallback if primary artifact is missing or empty

3. **Other artifacts**
   - Listed but not selected as default

4. **None** (if no suitable file exists)

### Security

- Artifacts are only listed from files inside `raw_dir`
- Path traversal is blocked (no `../` or absolute paths)
- File existence is verified before listing

---

## Common Failure Modes

### "Direct lattice mismatch" (Wannier90)

**Symptom**: `pw2wannier90` reports:
```
from pw2wannier90 : error # 4
Direct lattice mismatch
```

**Cause**: `unit_cell_cart` in `.win` file was in wrong units (Bohr instead of Angstrom).

**Resolution**: Ensure `unit_cell_cart` is in Angstrom, taken directly from `structure.lattice.matrix` without conversion.

### "Errno 21: Is a directory: '.'"

**Symptom**: Step execution fails with:
```
Error [Errno 21] Is a directory: '.'
```

**Cause**: A code path attempted to treat a directory path (".") as a file path to read.

**Resolution**: After fixes, the engine/service always provides correct `output_file`/`stdout_file` paths. No UI/CLI guessing is needed. All path validation occurs in the engine layer.

### "JOB DONE not found" (CLI)

**Symptom**: CLI test fails with "JOB DONE not found in output for step scf".

**Cause**: CLI was reading the input file (`scf-1.in`) instead of the output file (`scf.out`) because the service returned `output_file=None` and CLI fell back to `input_file`.

**Resolution**: 
- Engine/service now always returns `output_file`/`stdout_file` paths (even if files don't exist)
- CLI uses priority selection: `output_file` → `stdout_file` → `input_file` (last resort)
- No filename inference in CLI

---

## CLI Show Behavior

### Separation of Concerns

**File naming rules** live in the engine/service layer:
- `qe_calculation.run_step()` sets `StepResult.output_file` and `StepResult.stdout_file`
- `QVService.run_step()` returns these paths in the response

**CLI** only selects by priority:
- Reads `response.output_file` (primary artifact)
- Falls back to `response.stdout_file` if `output_file` is None
- Only uses `input_file` as last resort (with warning)

**No filename inference**: CLI never guesses output filenames based on `step_type` or `working_dir`.

### Output Format

The CLI `run step` command prints:
```
Step finished: <output_file> -> (input <input_file>)
```

Where:
- `<output_file>` is the primary artifact path (e.g., `scf.out`, `<seed>.wout`)
- `<input_file>` is the input file path (e.g., `scf.in`, `scf-1.in`)

This format is a **CLI contract** required by tests and must always be printed.

---

## Implementation Details

### StepResult Structure

The `StepResult` dataclass includes:

- `output_file`: Primary artifact (e.g., `<seed>.wout` for Wannier90, `scf.out` for QE)
- `stdout_file`: Stdout capture file (always `{step_type}.out`)
- `stderr_file`: Stderr capture file (always `{step_type}.err`)

For QE steps, `output_file` and `stdout_file` point to the same file (`{step_type}.out`).

### Service Response

`QVService.run_step()` returns:

- `output_file`: Primary artifact path (may not exist if execution failed)
- `stdout_file`: Stdout capture file path
- `stderr_file`: Stderr capture file path

All paths are always returned (even if files don't exist), ensuring CLI/UI can display them without guessing.

### Artifacts Recognition

The artifacts recognition system (`src/quantumvitas/calculation/step_artifacts.py`) provides:

- `get_step_artifacts(step_type, params, raw_dir)`: Returns list of expected artifact filenames
- `get_default_artifact(step_type, params, raw_dir, artifacts_list)`: Returns the default artifact for GUI display

Rules are registered per step type and can extract parameters (e.g., `seedname`, `filband`) from nested or flat parameter structures.

---

## See Also

- [Wannier90 Integration Specification](architecture/WANNIER90_INTEGRATION_SPEC.md)
- [CLI API Reference](CLI_API_REFERENCE.md)
- [Bugfix: Wannier90 Unit Cell Units](BUGFIX_WANNIER90_UNIT_CELL_UNITS.md)
- [Bugfix: pw2wannier90 Errno 21](BUGFIX_PW2WANNIER90_ERRNO21_FINAL.md)

