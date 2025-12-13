# Job I/O Directory Semantics

## Overview

QuantumVITAS uses a unified `io_dir` field to represent the I/O directory for job execution. This directory is where the runner writes QE input/output files and artifacts.

## Key Principles

1. **Runner is the single source of truth**: The I/O directory path is determined by the runner layer, not by hardcoded conventions in the server or GUI.

2. **Immediate availability**: `io_dir` is available immediately when a job is created (pending state), computed using the same logic the runner will use during execution.

3. **Consistency**: The `io_dir` shown in pending/running jobs matches the actual I/O directory used by the runner, ensuring no "jumps" in the UI when execution completes.

## Implementation

### Runner Layer

The runner layer provides a helper function that is the **single source of truth** for computing I/O directory paths:

```python
from quantumvitas.calculation.runner import compute_io_dir_from_workflow_model

# Compute I/O directory from calculation model
io_dir = compute_io_dir_from_workflow_model(calculation_dir, working_dir_name)
```

**Location**: `src/quantumvitas/calculation/runner.py`

**Parameters**:
- `calculation_dir`: Path to the calculation directory (containing calculation.yaml)
- `working_dir_name`: Name of the working directory subdirectory (from `calculation.working_dir` in calculation.yaml). If `None`, defaults to `"raw"` (the convention for local runner).

**Returns**: Absolute `Path` to the I/O directory.

**Note**: This function encapsulates the default `"raw"` convention. If the runner's I/O directory policy changes in the future, only this function needs to be updated.

### Server Layer

The daemon server uses `compute_io_dir_from_workflow_model()` to compute `planned_io_dir` when creating jobs:

**Location**: `src/quantumvitas/daemon/server.py`

- `_handle_run_calculation`: Computes `planned_io_dir` using the helper function
- `_handle_run_step`: Same approach

**No hardcoded paths**: The server does NOT construct paths like `calculation_dir / "raw"` directly. It always uses the runner-layer helper.

### Job Model

**Location**: `src/quantumvitas/daemon/jobs.py`

- `Job.io_dir`: Stores the I/O directory path (absolute string)
- `to_dict()`: Returns `io_dir` in job status responses
- `execute_job()`: 
  - Extracts `final_io_dir` from runner result
  - Compares `planned_io_dir` (from job creation) with `final_io_dir` (from runner)
  - Logs a warning if they differ: `[WARN] job <id> planned io_dir != final io_dir: planned=..., final=...`
  - Updates `job.io_dir` to the final value (runner is source of truth)

### API Layer

**Location**: `src/quantumvitas/api.py`

- `run_calculation`: Returns `io_dir` from `CalculationResult` (runner-provided)
- `run_step`: Returns `io_dir` (the actual directory used)

**Critical**: These functions do NOT construct paths. They pass through the `io_dir` provided by the runner.

### Frontend

**Location**: `gui/src/components/panels/JobsPanel.tsx`

- Displays `io_dir` in the job detail panel
- Shows "I/O Directory" section with path and "Reveal in Finder" button
- Available immediately when job is created (pending state)

**Types**: `gui/src/types/qv.ts`
- `JobInfo.io_dir`: Optional field for I/O directory path
- `JobSummary.io_dir`: Optional field (if `list_jobs` returns it)

## Data Flow

```
Calculation Model (calculation.yaml)
  ↓
  working_dir: "raw" (default) or custom name
  ↓
compute_io_dir_from_workflow_model() [SINGLE SOURCE OF TRUTH]
  ↓
  ├─> Server: planned_io_dir (for pending jobs)
  │   └─> job.io_dir (显示在 UI 中)
  │
  └─> Runner: calculation.raw_dir (for execution)
      └─> CalculationResult.io_dir
          └─> execute_job: final_io_dir
              └─> 比较 planned vs final
                  └─> 如果不同，警告并更新为 final
```

## Backward Compatibility

During the migration from `work_dir`/`working_dir` to `io_dir`:

- `execute_job` normalization accepts legacy keys: `working_dir`, `work_dir`, `raw_dir`
- These are normalized to `io_dir` internally
- Outward JSON responses contain only `io_dir` (no legacy keys)

## Migration Notes

- **Removed**: `work_dir` naming externally
- **Added**: `io_dir` as the unified field name
- **Helper function**: `compute_io_dir_from_workflow_model()` encapsulates the default "raw" convention
- **No hardcoding**: Server and GUI do not assume "raw" or construct paths directly

## Related Files

- `src/quantumvitas/calculation/runner.py`: `compute_io_dir_from_workflow_model()` helper
- `src/quantumvitas/daemon/server.py`: Uses helper to compute `planned_io_dir`
- `src/quantumvitas/daemon/jobs.py`: Job model with `io_dir` field
- `src/quantumvitas/api.py`: Returns `io_dir` from runner results
- `gui/src/components/panels/JobsPanel.tsx`: Displays `io_dir` in UI
- `gui/src/types/qv.ts`: Type definitions for `io_dir`
