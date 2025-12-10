# Standalone Step Execution Implementation

## Summary

Implemented a clean, explicit standalone mode for running QE steps without a project context, reusing existing core run logic.

## New Functions/Modules

### `src/quantumvitas/workflow/standalone.py` (NEW)
- **`StandaloneStepContext`**: Dataclass for standalone step execution context
  - `input_file`: Path to QE input file
  - `workdir`: Working directory
  - `outdir`: QE outdir (typically `workdir / "outdir"`)
  - `engine`: QE engine instance
  - `bidirectional`: Flag for bidirectional mode

- **`run_standalone_step(ctx: StandaloneStepContext)`**: Core standalone execution function
  - Handles bidirectional vs pass-through mode
  - Reuses `prepare_input_step` and `run_prepared_step` from `input_runner.py`
  - Manages file layout (original vs generated input)

### Modified Functions

#### `src/quantumvitas/cli/main.py`
- **`run_step_command`**: Extended with standalone mode support
  - New flags: `--standalone`, `--input`, `--engine`, `--bidirectional`
  - Mutual exclusion validation between standalone and project mode
  - Routes to `_run_standalone_step()` for standalone execution

- **`_run_standalone_step()`**: Helper function for standalone CLI execution
  - Builds `StandaloneStepContext` from CLI arguments
  - Calls `run_standalone_step()` from standalone module
  - Formats CLI output

#### `src/quantumvitas/workflow/input_runner.py`
- **`prepare_input_step()`**: Updated to handle `project_root=None` (standalone mode)
  - Skips `set_pseudo_dir_to_temp()` when `project_root` is None
  - Skips pseudopotential resolution when `project_root` is None
  - Allows standalone mode to use input file's existing pseudo_dir or system paths

- **`PreparedInputStep`**: Updated `project_root` field to `Optional[Path]`
  - Can be `None` in standalone mode

## CLI Semantics

### Standalone Mode
```bash
qv run step --standalone \
  --input pw.in \
  [--workdir PATH] \
  [--engine qe] \
  [--bidirectional]
```

**Flags:**
- `--standalone` (required): Enables standalone mode
- `--input <file>` (required in standalone): Path to QE input file
- `--workdir <dir>` (optional): Working directory (defaults to current directory)
- `--engine <name>` (optional): Engine name (defaults to "qe", only "qe" supported currently)
- `--bidirectional` (optional): Generate normalized input from original

**Mutual Exclusion:**
- `--standalone` cannot be used with `--project`, `--workflow`, or positional `target` argument
- `--bidirectional` only works in standalone mode
- Project mode flags are disallowed in standalone mode

### Project Mode (unchanged)
```bash
qv run step <target> [--workdir PATH] [--project PATH]
```
- Works as before
- `--standalone`-only flags are disallowed

## Behavior

### Pass-through Mode (default, no `--bidirectional`)
- Uses original input file as-is
- Copies input to workdir if needed
- Updates `outdir` parameter to `workdir / "outdir"`
- QE runs directly on the (possibly copied) input file

### Bidirectional Mode (`--bidirectional`)
- Parses original input file
- Generates normalized QE input
- Preserves original as `<stem>.raw.in` in workdir
- Generated input as `<stem>.generated.in` in workdir
- QE runs on the generated input
- Enables round-trip: original → parse → normalize → run

### File Layout
```
workdir/
  pw.in (or pw.raw.in in bidirectional mode)
  pw.generated.in (bidirectional mode only)
  pw.out (QE output)
  outdir/ (QE outdir)
```

### Outdir
- Always set to `workdir / "outdir"` (relative path `"./outdir"`)
- Explicitly controlled in standalone mode

### Pseudopotentials
- In standalone mode: Uses input file's `pseudo_dir` parameter or system paths
- No project-level pseudo directory resolution
- Pseudopotentials must be available via system paths or explicit paths in input

## Code Reuse

The implementation reuses existing core functions:
- `run_input_step()` / `prepare_input_step()` / `run_prepared_step()` from `input_runner.py`
- `QuantumEspressoEngine` for step type detection and execution
- `QEInputParser` / `QEInputGenerator` for input handling
- Existing error handling and logging

No duplication of core run logic - standalone mode is a thin wrapper that:
1. Handles file layout (bidirectional vs pass-through)
2. Sets up context (workdir, outdir)
3. Calls existing `run_input_step()` with `project_root=None`

## TODOs / Limitations

1. **Engine support**: Only QE engine is currently supported in standalone mode
   - `--engine` flag accepts only "qe" (or defaults to "qe")
   - Other engines would need similar standalone support

2. **Pseudopotentials**: In standalone mode, pseudopotentials must be:
   - Available via system paths (QE environment)
   - Or explicitly specified in input file's `pseudo_dir` parameter
   - No automatic resolution from project structure

3. **Tests**: Tests not updated in this pass (as requested)

4. **CLI output**: Currently prints:
   ```
   Standalone QE run:
     workdir: /abs/path/to/workdir
     input:   /abs/path/to/input_used_for_run
     outdir:  /abs/path/to/workdir/outdir
   Step finished: /abs/path/to/output_file -> (input /abs/path/to/input_used_for_run)
   ```
   - Could be enhanced to match project mode output format more closely

5. **Parameter overrides**: Standalone mode doesn't currently support parameter overrides
   - Could be added by extending `run_standalone_step()` to accept overrides
   - Would need to pass through to `prepare_input_step()`

