# QuantumVITAS Python Architecture (v2)

This document captures the working architecture so contributors and tooling can
stay aligned over the life of the refactor.

## Layered Structure

```
src/quantumvitas/
├─ io/            # QE I/O models + parser/generator + pseudo helpers
├─ engine/        # Public engine interfaces + QE installation + registry
├─ calculation/      # Step definitions, runners, verification, input helpers
├─ project/       # Project metadata + storage layout helpers
├─ analysis/      # Post-processing skeletons (DOS/Bands/Energy)
├─ cli/           # Typer CLI (future)
└─ core/engines/  # Legacy QE engine implementation (still reused internally)
```

### Key Concepts

- **Project layer (`quantumvitas.project`)**  
  Knows where the project root lives, which structures/calculations are registered,
  and how to open them (currently via `project.qv.yml`, future CLI will call this).

- **Calculation layer (`quantumvitas.calculation`)**  
  Defines `Calculation`, `Step`, `StepType`, `CalculationRunner`, `input_runner`. Every
  calculation owns exactly one I/O directory (default `raw/`, configurable via `working_dir` in calculation.yaml) under its folder; all QE
  I/O (inputs, modified copies, outputs, shared `outdir/`) happens inside that
  folder so steps can pass restart data without juggling paths. The I/O directory path is determined by the runner layer (single source of truth).

- **Step execution**  
  Steps point to QE `.in` files located in the calculation’s `raw/` directory. Step
  type is auto-detected from the input file (SCF/NSCF/PH/DOS/etc.). When a step
  runs we:
  1. Copy the original input to `raw/<name>_original.in`.
  2. Apply `outdir='./outdir'` and `pseudo_dir=project_root/pseudo` to produce
     `<name>_modified.in`.
  3. Invoke QE via `calculation.input_runner.run_input_step`, capturing `.out` plus
     leaving QE’s own files in `raw/` (single shared `outdir/`).

- **Engine layer (`quantumvitas.engine`)**  
  Provides the public `Engine` interface, QE installation helpers, and a
  registry. Internally it still reuses the legacy implementations under
  `quantumvitas.core.engines`.

- **IO layer (`quantumvitas.io`)**  
  Owns `QEInputParser`, `QEInputGenerator`, card/namelist models, and pseudo
  management helpers.

- **Tests**  
  `tests/core/qe_step_runner.py` and friends call the same calculation helpers
  above, ensuring unit/integration tests and CLI share identical QE wiring.

## Example Project Layout

```
project_root/
  project.qv.yml          # lists structures + calculations by ID only (DAG + ID-only model)
  pseudo/                 # shared pseudopotentials (checked before downloading)
  calculations/
    si_dos/
      calculation.yaml       # structure_id (ULID), working_dir=raw (I/O directory name), step order by step_id
      steps/
        scf.step.yaml    # step-local config only (no structure_id, no parent_workflow_id)
        nscf.step.yaml
        dos.step.yaml
      raw/                # single QE workspace for this calculation
        scf.in
        nscf.in
        dos.in
        scf_original.in
        scf_modified.in
        scf.out
        nscf.out
        dos.out
        outdir/           # QE scratch shared by all steps
      reference/          # optional golden outputs for strict mode
      results/            # post-processing artifacts (JSON, plots, etc.)
```

**Schema notes**: See `docs/SCHEMA.md` for detailed schema documentation. The project follows a DAG + ID-only model where all cross-resource references use ULIDs.

All QE commands run inside `calculations/<id>/raw/` and use relative paths
(`outdir='./outdir'`). This keeps restart directories alive for subsequent steps
and makes cleanup trivial (`rm -rf raw/`).

## Ground Rules

1. **Editable install first** (`pip install -e .[dev]`). No new `sys.path`
   hacks; scripts and tests should import `quantumvitas` normally.
2. **Outdir/pseudo_dir** always rewired through `calculation.input_runner`.
3. **QE step execution** uses `QuantumEspressoEngine.run_step` +
   `calculation.input_runner.prepare_input_step` (or the higher-level
   `run_and_verify_step_with_assert` in tests).  
4. **Verification** stays centralized: SCF energy / NSCF Fermi energy /
   PH frequencies live in `tests/core/qe_step_verification.py` + thresholds.
5. **Calculation vs. Tests**  
   - Calculations specify structured steps (`Step(type=...)`).  
   - Test harnesses may still auto-detect step type from inputs, but the
     detection logic sits in the engine/calculation layer for reuse.
6. **Documentation** (this file, README, test README) must be updated
   whenever architecture shifts—new helpers, new directories, etc.

Keeping this document current ensures future agents and contributors can pick up
the intended structure immediately. Feel free to extend it with diagrams or
component details as the project matures.

## Current Working Directory Usage

**Intended rule**: Only the CLI layer should use `Path.cwd()` or rely on current working directory. QVService/daemon/engine helpers should receive explicit paths/project_root.

**Current status**: Some core modules (`core/project_utils.py`, `core/models.py`, `calculation/input_runner.py`, `calculation/structure_steps.py`) still use `Path.cwd()` for fallback behavior. This is acceptable for backwards compatibility but should be minimized in new code.

**See also**: `docs/SCHEMA.md` for detailed schema documentation, `docs/STANDALONE_QE.md` for standalone execution mode.

