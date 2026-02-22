# Directory Terminology Reference

## Overview

This document clarifies the semantics of directory-related terms used across the codebase, particularly the distinction between test fixtures and product runtime directories.

## Terminology Map

| Term in code | Context | Current meaning | Recommended standard meaning | Notes/callsites |
|-------------|---------|----------------|------------------------------|-----------------|
| `raw_dir` (tests) | Tests | Fixture/template directory containing input files | `fixture_dir` or `template_dir` | `tests/integration/test_pw_step_specs.py`, `tests/integration/test_pw_scf_ibrav_step_specs.py` - READ-ONLY template directory |
| `raw_dir` (product) | Product | Runtime I/O directory: `project/calc/raw/` | `calculation.raw_dir` (keep as-is) | `src/qmatsuite/calculation/calculation.py`, `src/qmatsuite/calculation/runner.py` - WRITABLE runtime directory |
| `working_dir` (tests) | Tests | Base test directory (may contain fixtures) | `test_base_dir` or keep `working_dir` | `tests/core/qe_step_runner.py` - Base directory for test artifacts |
| `working_dir` (tests execution) | Tests | Sandbox directory where QE executes | `sandbox_dir` or `execution_dir` | `tests/integration/test_pw_step_specs.py` - Created via `create_sandbox_working_dir()` |
| `working_dir` (product) | Product | Same as `calculation.raw_dir` (I/O directory) | Keep `working_dir` in calculation model | `src/qmatsuite/calculation/calculation.py` - Runtime I/O directory name |
| `sandbox_dir` | Tests | Temporary execution directory | `sandbox_dir` (standard) | `tests/core/qe_step_runner.py::create_sandbox_working_dir()` - Execution sandbox |
| `output_dir` | Both | Directory where generated inputs are written | `output_dir` (keep as-is) | `materialize_step_spec()` - Can be fixture_dir (tests) or raw_dir (product) |
| `outdir` | Both | QE scratch directory (`./outdir` relative to execution) | `outdir` (keep as-is) | QE-specific, always relative to execution directory |

## Key Distinctions

### Test Context

1. **Fixture/Template Directory** (`fixture_dir`):
   - **Purpose**: Read-only directory containing input templates (`.in` files)
   - **Location**: Under `tests/` or generated in test temp directories
   - **Usage**: Source for copying inputs to sandbox
   - **Invariant**: Must remain read-only (no execution, no pseudo materialization)

2. **Sandbox/Execution Directory** (`sandbox_dir`):
   - **Purpose**: Writable directory where QE execution happens
   - **Location**: Temporary directory (pytest `tmp_path` or `temp/test_outputs/`)
   - **Usage**: Contains copied inputs, materialized pseudos (`sandbox_dir/pseudo/`), QE outputs
   - **Invariant**: All QE execution must happen here, never in fixture directories

### Product Context

1. **Calculation Raw Directory** (`calculation.raw_dir`):
   - **Purpose**: Runtime I/O directory for a calculation
   - **Location**: `project_root/calculations/<calc_id>/raw/`
   - **Usage**: Contains QE inputs, outputs, `outdir/`, and optionally `pseudo/` (standalone mode)
   - **Invariant**: Writable runtime directory, part of project structure

2. **Project Pseudo Directory** (`project_root/pseudo/`):
   - **Purpose**: Shared pseudopotential library for the project
   - **Location**: `project_root/pseudo/`
   - **Usage**: Materialized pseudos for all calculations in the project
   - **Invariant**: Shared across calculations, materialized at runtime

## Test Pattern (Sandbox Pattern)

All integration tests that execute QE must follow this pattern:

```python
# 1. Create fixture directory (read-only template)
fixture_dir = working_dir / "raw"  # or use better name: fixture_dir
materialize_step_spec(..., output_dir=fixture_dir)

# 2. Create sandbox for execution
sandbox_dir = create_sandbox_working_dir(working_dir, prefix="test_")

# 3. Copy inputs from fixture to sandbox
shutil.copy2(fixture_dir / "input.in", sandbox_dir / "input.in")

# 4. Materialize pseudos to sandbox
sandbox_pseudo_dir = sandbox_dir / "pseudo"
ensure_qe_pseudos(..., project_pseudo_dir=sandbox_pseudo_dir)

# 5. Execute in sandbox (not fixture_dir)
run_step(input_file=sandbox_dir / "input.in", working_dir=sandbox_dir)
```

## Product Pattern

In product code, the calculation's `raw_dir` is the execution directory:

```python
# calculation.raw_dir is the I/O directory (project/calc/raw)
raw_dir = calculation.raw_dir  # Runtime I/O directory
run_step(input_file=raw_dir / "input.in", working_dir=raw_dir)
```

## Migration Notes

- **Tests**: Variables named `raw_dir` that refer to fixture/template directories should be renamed to `fixture_dir` or `template_dir` for clarity
- **Product**: `calculation.raw_dir` and related product code should remain unchanged (correct semantics)
- **No API changes**: This is a documentation and variable naming clarification, not an architectural change

