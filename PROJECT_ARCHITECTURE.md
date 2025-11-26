# QuantumVITAS Python Architecture (v2)

This document captures the working architecture so contributors and tooling can
stay aligned over the life of the refactor.

## Layered Structure

```
src/quantumvitas/
├─ io/                  # Parsing + serialization (QE inputs/outputs, pseudo helpers)
├─ core/
│  └─ engines/          # Engine abstractions + QE implementation
├─ workflow/
│  ├─ input_runner.py   # Input-driven helpers (prepare/run a QE step from .in file)
│  ├─ runner.py         # WorkflowRunner orchestrating structured Step objects
│  └─ verification.py   # Workflow-level verification hooks
├─ engine/              # Runtime registry + QE installation helpers
├─ project/             # Project/workflow metadata (structures, storage)
├─ analysis/            # Post-processing stubs (DOS/bands/energy, future CLI)
└─ cli/                 # Command-line entry points (to be expanded)
```

### Key Concepts

- **IO Layer (`quantumvitas.io`)**  
  Owns all QE parsing/generation logic (`QEInputParser`, `QEInputGenerator`),
  including the `QEInputParser.roundtrip_file()` helper for debugging/workflows.

- **Engine Layer (`quantumvitas.core.engines`, `quantumvitas.engine`)**  
  Encapsulates how we locate executables, run commands, and ensure resources
  (e.g. `QEWorkflowRunner`, `QEInputParser`, `ensure_pseudopotentials`).

- **Workflow Layer (`quantumvitas.workflow`)**  
  Provides structured steps (`Step`, `StepType`), the general `WorkflowRunner`,
  and **input-driven helpers** (`prepare_input_step`, `run_prepared_step`,
  `set_outdir_to_temp`, `set_pseudo_dir_to_temp`).  
  Tests and CLI should call these helpers; business logic should not reinvent
  outdir/pseudo_dir or input-copy handling.

- **Tests (`tests/core`)**  
  - `qe_step_runner.py` is now a light wrapper around `workflow.input_runner` that
    adds test-specific convenience (auto temp dirs, assertions).  
  - Verification logic lives in `qe_step_verification.py` + `thresholds.py`.  
  - Utilities (`qe_test_utils.py`) expose `run_command_with_timeout`,
    jobconfig parsing, PH frequency extraction, etc.  
  - Tests should not modify `sys.path`; rely on `pip install -e .[dev]`.

- **Extended Tests (`extended-tests/`)**  
  Legacy tooling now imports runtime helpers (`set_outdir_to_temp`, etc.) from
  `quantumvitas.workflow.input_runner`. Compatibility shims such as
  `extended-tests/utils/test_qe_roundtrip_execution.py` only re-export.

## Ground Rules

1. **Editable install first** (`pip install -e .[dev]`). No new `sys.path`
   hacks; scripts and tests should import `quantumvitas` normally.
2. **Outdir/pseudo_dir** always rewired through `workflow.input_runner`.
3. **QE step execution** uses `QuantumEspressoEngine.run_step` +
   `workflow.input_runner.prepare_input_step` (or the higher-level
   `run_and_verify_step_with_assert` in tests).  
4. **Verification** stays centralized: SCF energy / NSCF Fermi energy /
   PH frequencies live in `tests/core/qe_step_verification.py` + thresholds.
5. **Workflow vs. Tests**  
   - Workflows specify structured steps (`Step(type=...)`).  
   - Test harnesses may still auto-detect step type from inputs, but the
     detection logic sits in the engine/workflow layer for reuse.
6. **Documentation** (this file, README, test README) must be updated
   whenever architecture shifts—new helpers, new directories, etc.

Keeping this document current ensures future agents and contributors can pick up
the intended structure immediately. Feel free to extend it with diagrams or
component details as the project matures.

