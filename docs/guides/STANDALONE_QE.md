# Standalone QE Execution

## Overview

Standalone mode allows running Quantum ESPRESSO input files without a project context. It is a pure QE helper that operates on raw input files and does NOT create or depend on project/calculation/step resources in the DAG.

## Behavior

Standalone mode **always** performs a full roundtrip:

1. Read original QE input file
2. Parse into internal representation using `QEInputParser`
3. Generate normalized QE input using `QEInputGenerator`
4. Run QE on the generated input

The original input is preserved as `<stem>.raw.in`, and the generated normalized input is used for the actual QE execution.

## CLI Usage

```bash
qms run step --standalone --input <file> [--workdir PATH] [--engine qe]
```

**Flags:**
- `--standalone` (required): Enables standalone mode
- `--input <file>` (required): Path to QE input file
- `--workdir <dir>` (optional): Working directory (defaults to current directory)
- `--engine <name>` (optional): Engine name (defaults to "qe", only "qe" supported currently)

**Note:** The `--bidirectional` flag is deprecated and ignored. Standalone mode always performs the full parse→generate→run roundtrip.

## File Layout

```
workdir/
  <stem>.raw.in       # Original input (preserved)
  <stem>.in           # Generated normalized input (used for execution)
  <stem>.out          # QE output
  outdir/             # QE outdir
  pseudo/             # Pseudopotentials (materialized at runtime)
```

**Pseudo Directory Location:**
- In standalone mode, pseudopotentials are materialized to `workdir/pseudo/`
- The `ESPRESSO_PSEUDO` environment variable is set to `workdir/pseudo/` during execution
- Pseudos are resolved from system libraries (`resources/pseudo/` or SSSP store) and copied to `workdir/pseudo/` before QE execution

## Implementation

- Module: `src/qmatsuite/calculation/standalone.py`
- Function: `run_standalone_step(ctx: StandaloneStepContext)`
- Always uses `QEInputParser` and `QEInputGenerator` - no pass-through mode

## Separation from DAG

Standalone execution is conceptually separate from the DAG:
- Does NOT create Step resources
- Does NOT interact with project registry
- Does NOT require calculation or structure resources
- Operates purely on QE input files in a specified working directory

For project-based execution, use `qms run step` without `--standalone` to execute steps within a calculation context.
