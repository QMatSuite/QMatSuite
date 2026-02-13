# Per-Calc Locking + Incremental Run Implementation Audit

**Date:** 2025-01-27  
**Goal:** Implement robust per-calc locking + incremental run (make/overleaf style) WITHOUT introducing DAG or per-step folders.

---

## 1. Current Architecture Map

### 1.1 Calculation YAML Read/Write

**Entry Points:**
- `src/quantumvitas/core/yamldoc.py::CalcDoc.load()` / `CalcDoc.save()`
- `src/quantumvitas/core/models.py::load_calculation()` / `save_calculation()`
- `src/quantumvitas/core/yaml_io.py::save_yaml_doc()` - **SINGLE COMMIT POINT** for all YAML saves
- `src/quantumvitas/calculation/calculation.py::Calculation.from_yaml()` - loads calc + steps with `materialize_steps` flag

**Key Classes:**
- `CalcDoc` (`src/quantumvitas/core/yamldoc.py:598-624`) - wrapper for `calculation.yaml`
- `Calculation` (`src/quantumvitas/calculation/calculation.py:23-552`) - runtime representation
- `CalculationModel` (`src/quantumvitas/core/models.py:125-320`) - data model

**Step YAML:**
- `StepDoc` (`src/quantumvitas/core/yamldoc.py:454-596`) - wrapper for step YAML
- Steps stored as `calculations/<id>/steps/<step_id>.step.yaml`
- Referenced in `calculation.yaml` via `steps[]` array with `step_id` (ULID)

**Registry:**
- `src/quantumvitas/core/resolution.py` - `ResourceIndex` maintains cache of all resources
- `project.qv.yml` contains calculation/structure references by ULID only (DAG model)

### 1.2 Materialization Flow

**Materialization Entry Point:**
- `src/quantumvitas/calculation/calculation.py::Calculation.from_yaml(..., materialize_steps=True)` (line 109-212)
  - When `materialize_steps=True`, calls `_build_step()` which calls `materialize_step_spec()`
  
**Core Materialization Function:**
- `src/quantumvitas/calculation/structure_steps.py::materialize_step_spec()` (line 588-942)
  - Takes step spec (YAML or `StructureStepSpec`) and generates QE input file
  - Writes to `output_dir` (typically `calc/raw`)
  - Returns `(generated_input_path, StructureStepSpec)`

**Materialization in Runner:**
- `src/quantumvitas/api.py::QVService.run_calculation()` (line 1129-1225)
  - Calls `Calculation.from_yaml(..., materialize_steps=True)` at line 1178
  - Materialization happens **INSIDE** the run path, NOT before submission

**Step Building:**
- `src/quantumvitas/calculation/calculation.py::_build_step()` (line 215-351)
  - Resolves step via registry using `step_id`
  - Loads step spec via `StructureStepSpec.from_yaml()`
  - Calls `materialize_step_spec()` to generate input file into `working_dir` (calc/raw)

**Current Behavior:**
- Materialization happens **during** `Calculation.from_yaml()` when `materialize_steps=True`
- All input files generated sequentially during calculation load
- Input files written to `calc/raw/` with naming like `scf.in`, `nscf.in`, `bands.in`
- Files are overwritten if they exist (no incremental check)

### 1.3 Run Execution / Job Manager / Daemon RPC

**GUI → Daemon Flow:**
- `gui/src/App.tsx::handleRunCalculation()` (line 1713-1767)
  - Calls `qv.call('run_calculation', { project_root, calculation: calculation.slug })`
  
**Daemon Handler:**
- `src/quantumvitas/daemon/server.py::_handle_run_calculation()` (line 5358-5440)
  - Receives `project_root`, `calculation` (slug)
  - Normalizes paths
  - Submits job via `JobManager.submit_with_id()` (line 5417-5438)
  
**Job Manager:**
- `src/quantumvitas/daemon/jobs.py::JobManager` (line 112-684)
  - Uses `ThreadPoolExecutor(max_workers=1)` - **sequential execution only**
  - Maintains in-memory `_jobs` dict keyed by job_id (ULID)
  - Thread-safe with `Lock()` for job state updates (line 133)
  - **NO cross-process locking** - only protects in-memory state

**Service Layer:**
- `src/quantumvitas/api.py::QVService.run_calculation()` (line 1129-1225)
  - Loads calculation: `Calculation.from_yaml(..., materialize_steps=True)` (line 1178)
  - Creates `CalculationRunner` and calls `runner.run()` (line 1195)
  
**Calculation Runner:**
- `src/quantumvitas/calculation/runner.py::CalculationRunner.run()` (line 67-355)
  - Iterates through `calculation.steps` sequentially (line 161)
  - For each step: calls `step.run()` which executes QE engine (line 194-199)
  - No skipping logic - always executes all steps
  - Records history via `_start_history_recording()` and `_complete_history_recording()`

**History Recording:**
- `src/quantumvitas/calculation/runner.py::_start_history_recording()` (line 357-455)
  - Creates `RunRevision` via `create_run_revision()` (line 413-429)
  - Stores snapshot in `.history/runs/run_<ULID>/run_revision.json`
  - Records `RunStartedEvent` to `.history/events.jsonl`
  
- `src/quantumvitas/history/run_revision.py::create_run_revision()` creates run directory and saves snapshot

### 1.4 Analysis Generation

**Analysis Entry Points:**
- `src/quantumvitas/api.py::QVService.analyze_scf()` (line 1517-1571)
- `src/quantumvitas/api.py::QVService.analyze_dos()` (line 1573-1661)
- `src/quantumvitas/api.py::QVService.analyze_band()` (line 1663-1695)
- `src/quantumvitas/analysis/calculation_analysis.py::analyze_calculation()` - called after run

**File Discovery:**
- Analysis functions read from `calc/raw/` directory
- `src/quantumvitas/analysis/parsers.py` - `find_bands_files()`, `find_dos_files()` scan raw dir
- CLI: `src/quantumvitas/cli/main.py::analyze_output_command()` (line 3386-3535) auto-locates files in `calc/raw`

**Output File Patterns:**
- QE outputs: `*.out`, `*.dat`, `*.gnu` in `calc/raw`
- Analysis artifacts: `calc/.analysis/` (JSON, plots)
- Artifacts managed via `src/quantumvitas/analysis/artifacts.py`

### 1.5 History Persistence

**History Storage:**
- `src/quantumvitas/history/storage.py::ProjectHistory` - manages `.history/` directory
- History directory: `project/.history/`
- Events: `.history/events.jsonl` (append-only JSONL)
- Runs: `.history/runs/run_<ULID>/` per run

**Run Revision:**
- `src/quantumvitas/history/run_revision.py::RunRevision` (line 41-480)
- `create_run_revision()` (line 153-268) - creates run directory, saves snapshot
- `complete_run_revision()` (line 270-341) - computes digests, finalizes run
- Snapshot stored as `run_revision.json` + optional `snapshot.tar.zst`

**File Locking:**
- `src/quantumvitas/history/storage.py::_atomic_append()` (line 180-198)
  - Uses `fcntl.flock(f.fileno(), fcntl.LOCK_EX)` for cross-process file locking
  - **EXISTING CROSS-PROCESS LOCKING** - but only for JSONL appends, not for calc-level coordination

**Snapshot Content:**
- `create_run_revision()` creates snapshot with `create_snapshot=True` (line 427)
- Snapshot includes calculation.yaml + steps YAML (not input files)
- Stored at `.history/runs/run_<ULID>/snapshot.tar.zst` (optional, can be None)

---

## 2. Gaps / Risks

### 2.1 Race Conditions

**Critical: Concurrent Run Attempts**
- **Location:** `src/quantumvitas/daemon/jobs.py::JobManager` uses `ThreadPoolExecutor(max_workers=1)` but only prevents concurrent runs **within a single daemon process**
- **Risk:** Multiple daemon processes (e.g., multiple GUI instances, CLI + GUI) can run the same calculation concurrently
- **Evidence:** `JobManager._lock` is in-memory only (line 133). No file-based locking prevents cross-process conflicts.
- **Impact:** Two runs can materialize inputs simultaneously, overwrite each other's outputs, corrupt state

**Edit-While-Run Race**
- **Location:** `src/quantumvitas/core/yaml_io.py::save_yaml_doc()` (line 117-210)
- **Risk:** User edits `calculation.yaml` or step YAML while a run is executing
- **Current Behavior:** Runner reads YAML once at start (line 1178 in `api.py`), but if YAML is edited mid-run, next run uses new YAML
- **Impact:** Low (runner already materialized), but no explicit protection

**Materialization Race**
- **Location:** `src/quantumvitas/calculation/calculation.py::Calculation.from_yaml()` (line 183-195)
- **Risk:** Materialization writes input files without locking `calc/raw/`
- **Evidence:** `materialize_step_spec()` writes directly to `output_dir` (line 913, 901)
- **Impact:** If two runs materialize simultaneously, input files can be partially written

### 2.2 Stale Outputs

**No Incremental Run Detection**
- **Location:** `src/quantumvitas/calculation/runner.py::CalculationRunner.run()` (line 161-330)
- **Risk:** Runner always executes all steps, even if inputs haven't changed
- **Evidence:** No hash/manifest comparison before step execution (line 161-194)
- **Impact:** Unnecessary recomputation, wasted time

**No Output Validation**
- **Location:** `src/quantumvitas/calculation/runner.py` - no check if output exists before running
- **Risk:** No verification that previous run's outputs are still valid
- **Impact:** User might expect reuse but runner always reruns

**No Downstream Cleanup**
- **Location:** None - no mechanism to clean stale outputs
- **Risk:** If step N is rerun, steps N+1, N+2 have stale outputs that are not invalidated
- **Evidence:** QE outputs accumulate in `calc/raw/` (e.g., `*.out`, `*.save/`, `*.wfc`)
- **Impact:** Analysis might read stale outputs from previous run

### 2.3 YAML Reading During Execution

**Current Behavior:**
- `QVService.run_calculation()` loads YAML once at start (line 1178)
- Runner only reads materialized input files from `calc/raw/` during execution (line 194-199)
- **Safe:** Runner does NOT re-read YAML mid-execution

**Potential Issue:**
- If user edits YAML while run is in progress, next run will use new YAML (expected, but no explicit lock)

### 2.4 Manifest/Hash System

**Missing:**
- No manifest file tracking input hashes per step
- No hash computation for materialized input files
- No comparison logic to detect changed inputs

**Required:**
- Manifest format: `calc/.history/manifest-latest.json` or `calc/raw/manifest.json`
- Hash source: materialized input files (not YAML text)
- Step boundaries: one manifest entry per step, keyed by `step_id`

### 2.5 History Snapshot Timing

**Current:**
- `create_run_revision()` creates snapshot at **start** of run (line 413-429 in runner.py)
- Snapshot contains YAML (calculation.yaml + steps), not input files
- **Gap:** Snapshot created before materialization completes (line 97-99 runs before materialization at line 1178 in api.py)

**Recommended:**
- Move snapshot creation to **after** materialization, **before** execution
- Snapshot should include materialized input files OR their hashes

---

## 3. Lock Insertion Plan

### 3.1 Lock File Locations

**Recommended Structure:**
```
calculations/<calc_id>/
├── .locks/
│   ├── run.lock        # Long-held during entire run
│   └── edit.lock       # Short-held during YAML writes
├── calculation.yaml
├── raw/
└── steps/
```

**Rationale:**
- `.locks/` directory keeps lock files organized and gitignored
- Separate locks for run (long) vs edit (short) prevents deadlocks
- Per-calc locks allow concurrent runs of different calculations

### 3.2 Lock Library Recommendation

**Option: `portalocker` (Cross-Platform)**
- **Package:** `portalocker` (not in requirements.txt currently)
- **Pros:** Works on Windows/macOS/Linux, simple API, file-based
- **Cons:** Additional dependency

**Option: `fcntl` (Unix) + `msvcrt` (Windows)**
- **Pros:** Standard library (no dependency)
- **Cons:** Platform-specific code required

**Recommendation: Use `portalocker`**
- Add to `requirements.txt`: `portalocker>=2.0.0`
- Cross-platform, well-maintained
- Consistent API across platforms

### 3.3 Run Lock (Long-Held)

**Acquisition Point:**
- `src/quantumvitas/api.py::QVService.run_calculation()` (line 1129)
  - **BEFORE** `Calculation.from_yaml()` (line 1178)
  - **BEFORE** materialization begins

**Release Point:**
- After `runner.run()` completes (line 1195)
- In `finally` block to ensure release on exception

**Lock File:**
- `calculation_dir / ".locks" / "run.lock"`
- Exclusive lock: `LOCK_EX | LOCK_NB` (non-blocking)
- On failure: raise `CalculationLockedError` with message "Calculation is currently running"

**Implementation:**
```python
# In api.py::QVService.run_calculation()
from pathlib import Path
import portalocker

calc_dir = calculation_resolved.absolute_path
lock_dir = calc_dir / ".locks"
lock_dir.mkdir(exist_ok=True)
run_lock_path = lock_dir / "run.lock"

try:
    with open(run_lock_path, "w") as lock_file:
        try:
            portalocker.lock(lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.LockException:
            raise QVServiceError(
                f"Calculation '{calculation_selector}' is currently running. "
                "Wait for the current run to complete or stop it first."
            )
        
        # ... existing materialization and execution code ...
        
finally:
    # Lock released automatically on context exit
    pass
```

**Error Handling:**
- If lock acquisition fails: return error to daemon, daemon returns JSON-RPC error to GUI
- GUI shows: "Calculation is running. Please wait or cancel the current run."

### 3.4 Edit Lock (Short-Held)

**Acquisition Point:**
- `src/quantumvitas/core/yaml_io.py::save_yaml_doc()` (line 117)
  - Wrap the entire save operation
  - Only for `CalcDoc` and `StepDoc` (not `ProjectDoc`)

**Release Point:**
- After `_save_yaml_raw()` completes (line 162)
- Before journal/history recording (lines 168-209)

**Lock File:**
- For calc YAML: `calculation_dir / ".locks" / "edit.lock"`
- For step YAML: `calculation_dir / ".locks" / "edit.lock"` (same lock for calc + steps)
- Exclusive lock: `LOCK_EX | LOCK_NB`

**Lock Ordering:**
- **Rule:** Edit lock must NOT be held while acquiring run lock (prevents deadlock)
- Edit operations should be fast (< 100ms), so run lock can wait briefly
- If edit lock held and run tries to acquire: run lock waits (blocking) with timeout (e.g., 5s)

**Implementation:**
```python
# In yaml_io.py::save_yaml_doc()
from pathlib import Path
import portalocker

def _get_edit_lock_path(path: Path) -> Optional[Path]:
    """Determine edit lock path for a YAML file."""
    # Find calculation directory
    current = path.resolve()
    if current.is_file():
        current = current.parent
    
    # Walk up to find calculation.yaml
    for _ in range(5):
        if (current / "calculation.yaml").exists():
            return current / ".locks" / "edit.lock"
        if current == current.parent:
            break
        current = current.parent
    
    return None  # Not a calc/step file, no lock needed

# In save_yaml_doc():
lock_path = _get_edit_lock_path(resolved_path)
if lock_path and isinstance(doc, (CalcDoc, StepDoc)):
    lock_path.parent.mkdir(exist_ok=True)
    with open(lock_path, "w") as lock_file:
        portalocker.lock(lock_file, portalocker.LOCK_EX)
        # ... existing save logic ...
```

### 3.5 Lock Failure Behaviors

**Run Lock Acquisition Failure:**
- Return `QVServiceError` with code `CALCULATION_LOCKED`
- Daemon returns JSON-RPC error: `{"ok": false, "error": {"code": "CALCULATION_LOCKED", "message": "..."}}`
- GUI shows notification: "Cannot run: calculation is already running"

**Edit Lock Acquisition Failure:**
- For YAML saves: retry with exponential backoff (max 3 retries, 100ms, 200ms, 400ms)
- If still fails: raise `YAMLSaveError` with message "Calculation is being edited by another process"
- GUI shows: "Save failed: calculation is being edited"

**Deadlock Prevention:**
- Edit lock held only during file write (< 100ms)
- Run lock waits for edit lock with timeout (5s)
- If timeout: run lock fails with "Calculation is being edited, please try again"

**Lock Cleanup:**
- Locks automatically released when process exits (file descriptor closes)
- No explicit cleanup needed (OS handles)

---

## 4. Incremental-Run Plan

### 4.1 Manifest File Format

**Location:** `calculations/<calc_id>/.history/manifest-latest.json`

**Format:**
```json
{
  "version": "1.0",
  "calculation_id": "<ULID>",
  "run_id": "<ULID>",  // Last successful run ID
  "created_at": "2025-01-27T12:00:00Z",
  "steps": [
    {
      "step_id": "<ULID>",
      "step_type": "scf",
      "input_file": "raw/scf.in",
      "input_hash": "sha256:abc123...",
      "output_files": ["raw/scf.out", "raw/outdir/"],
      "output_hash": "sha256:def456...",  // Hash of key output file
      "executed_at": "2025-01-27T12:05:00Z",
      "run_id": "<ULID>"
    },
    ...
  ]
}
```

**Storage:**
- Single manifest file per calculation
- Updated atomically (write to temp, rename)
- Located in `.history/` to keep it with run history

### 4.2 Hash Computation

**Hash Source (Materialized Input Files):**
- Hash the **materialized** input file (e.g., `raw/scf.in`), NOT the step YAML
- Reason: YAML → input transformation is deterministic, but hash input files for robustness
- Algorithm: SHA256 of file content
- Normalization: Strip trailing whitespace, normalize line endings (CRLF → LF)

**Hash for Step:**
- Each step has one primary input file (e.g., `scf.in`, `nscf.in`)
- Hash only the primary input file
- Dependencies (pseudos, structure) are tracked via `species_map` and `structure_id` in calculation.yaml

**Input Hash Computation:**
```python
import hashlib
from pathlib import Path

def compute_input_hash(input_file: Path) -> str:
    """Compute SHA256 hash of input file."""
    content = input_file.read_text().replace("\r\n", "\n").rstrip() + "\n"
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
```

**Output Hash (Optional, for Robustness):**
- Hash primary output file (e.g., `scf.out`) to detect if outputs were modified externally
- If output hash matches AND input hash matches → step is definitely up-to-date

### 4.3 Step Boundaries

**Current Step Execution:**
- Steps executed sequentially (line 161 in `runner.py`)
- Each step has one input file (e.g., `scf.in`, `nscf.in`, `bands.in`)
- Step boundaries are defined by `calculation.steps` list order

**Input File Naming:**
- Generated by `materialize_step_spec()` (line 588-942 in `structure_steps.py`)
- Naming via `CalculationFileNaming.input_filename()` (referenced in `api.py:1316`)
- Pattern: `<step_type>.in` (e.g., `scf.in`) or `<step_type>-<N>.in` if duplicates

**Manifest Entry Per Step:**
- One manifest entry per `step_id`
- Keyed by `step_id` (ULID) for stability across renames
- Contains `input_file` path relative to `calc/raw/`

### 4.4 Skip Criteria

**Step Skip Decision:**
```python
def should_skip_step(step: Step, manifest: dict, calc_raw_dir: Path) -> bool:
    """Check if step should be skipped based on manifest."""
    # Find manifest entry for this step
    step_entry = next((s for s in manifest["steps"] if s["step_id"] == step.id), None)
    
    if not step_entry:
        return False  # No previous run, must execute
    
    # Check input hash
    input_path = calc_raw_dir / step_entry["input_file"]
    if not input_path.exists():
        return False  # Input file missing, must regenerate
    
    current_hash = compute_input_hash(input_path)
    if current_hash != step_entry["input_hash"]:
        return False  # Input changed, must rerun
    
    # Check output exists and is valid
    output_files = step_entry.get("output_files", [])
    if not output_files:
        return False  # No output record, must rerun
    
    primary_output = calc_raw_dir / output_files[0]
    if not primary_output.exists():
        return False  # Output missing, must rerun
    
    # Optional: check output hash for robustness
    if "output_hash" in step_entry:
        current_output_hash = compute_output_hash(primary_output)
        if current_output_hash != step_entry["output_hash"]:
            return False  # Output modified externally, must rerun
    
    return True  # Input unchanged, output exists, skip step
```

**Key Output Detection:**
- For QE steps: primary output is `*.out` file (e.g., `scf.out`)
- For Wannier90: primary output is `<seedname>.wout`
- Output file path determined by engine (e.g., `QECalculationRunner.get_output_file()`)

### 4.5 Rerun-From-Step Logic

**Forward Propagation:**
- If step N input hash changed, mark step N and all subsequent steps (N+1, N+2, ...) for rerun
- Clear manifest entries for steps N+1, N+2, ... (they become "not executed")
- Execute steps starting from N

**Implementation:**
```python
# In CalculationRunner.run()
def find_first_changed_step(calculation: Calculation, manifest: dict, calc_raw_dir: Path) -> Optional[int]:
    """Find first step that needs rerun, or None if all up-to-date."""
    for i, step in enumerate(calculation.steps):
        if not should_skip_step(step, manifest, calc_raw_dir):
            return i
    return None  # All steps up-to-date

# In runner.run():
start_idx = 0
if not skip_history:  # Only check manifest if history enabled
    manifest = load_manifest(calculation.dir)
    if manifest:
        start_idx = find_first_changed_step(calculation, manifest, calculation.raw_dir) or 0
        # Clear manifest entries for steps from start_idx onward
        manifest["steps"] = manifest["steps"][:start_idx]
        save_manifest(calculation.dir, manifest)

# Execute steps from start_idx
for i, step in enumerate(calculation.steps[start_idx:], start=start_idx):
    # ... execute step ...
    # Update manifest after each step completes
    update_manifest_step(calculation.dir, step, input_hash, output_hash)
```

**Stale Output Cleanup:**
- **DO NOT** delete output files when rerunning (QE might need them as inputs for next step)
- QE will overwrite outputs naturally
- Exception: if step type changes, old outputs might be incompatible
- **Recommendation:** Only clean if step_type changed in manifest vs current step

**Manifest Update:**
- After each step completes successfully, update manifest entry
- If step fails, do NOT update manifest (keep previous successful state)
- Manifest updated atomically (write temp, rename)

### 4.6 Manifest Persistence Functions

**Location:** `src/quantumvitas/calculation/manifest.py` (new file)

**Functions:**
```python
def load_manifest(calculation_dir: Path) -> Optional[dict]:
    """Load manifest from .history/manifest-latest.json."""
    
def save_manifest(calculation_dir: Path, manifest: dict) -> None:
    """Save manifest atomically (temp + rename)."""
    
def update_manifest_step(calculation_dir: Path, step: Step, input_hash: str, output_hash: str) -> None:
    """Update single step entry in manifest."""
    
def clear_manifest_from_step(calculation_dir: Path, from_step_idx: int) -> None:
    """Clear manifest entries from step index onward."""
```

**Initial Manifest Creation:**
- Created after first successful run
- Populated during `_complete_history_recording()` in runner

---

## 5. Minimal API/UI Changes List

### 5.1 RPC/Backend Changes

**New Error Code:**
- `CALCULATION_LOCKED` - returned when run lock acquisition fails
- `YAML_EDIT_LOCKED` - returned when edit lock acquisition fails (optional, can use generic error)

**API Changes (None Required):**
- `QVService.run_calculation()` signature unchanged
- Lock acquisition is internal implementation detail
- Error returned via existing `QVServiceError` mechanism

**New RPC Response Field (Optional):**
- `run_mode: "full" | "incremental"` in `run_calculation` response
- Indicates whether run was full or incremental (for UI display)

### 5.2 CLI Changes

**New Option (Optional):**
- `qv run calculation --force` - force full run, ignore manifest
- Default: incremental (if manifest exists)

### 5.3 UI Changes

**Minimal (Lock Status Only):**
- Show "Running" badge on calculation card when run lock held
- Disable "Run" button while calculation is running
- Show error toast if run lock acquisition fails: "Calculation is already running"

**Enhanced (Incremental Run Feedback):**
- Show step status: "Skipped (up-to-date)" vs "Running" vs "Completed"
- Show tooltip: "Step skipped because input unchanged since last run"
- Optional: "Force Full Run" checkbox in run dialog

**No Breaking Changes:**
- UI contract unchanged: `run_calculation` RPC call same
- Only error handling enhanced (new error code)

### 5.4 Error Messages

**Run Lock Failure:**
```json
{
  "ok": false,
  "error": {
    "code": "CALCULATION_LOCKED",
    "message": "Calculation 'bands_si' is currently running. Please wait for the current run to complete."
  }
}
```

**Edit Lock Failure (Retry Exhausted):**
```json
{
  "ok": false,
  "error": {
    "code": "YAML_EDIT_FAILED",
    "message": "Failed to save: calculation is being edited by another process. Please try again."
  }
}
```

---

## 6. Test Plan

### 6.1 Unit Tests

**Lock Acquisition:**
- `tests/unit/test_calculation_locks.py` (new file)
  - Test run lock acquisition succeeds when unlocked
  - Test run lock acquisition fails when locked by another process
  - Test edit lock acquisition succeeds when unlocked
  - Test edit lock release on exception
  - Test lock file creation in `.locks/` directory

**Manifest:**
- `tests/unit/test_manifest.py` (new file)
  - Test manifest load/save
  - Test manifest update after step completion
  - Test manifest clearing from step index
  - Test hash computation for input files
  - Test hash normalization (line endings, trailing whitespace)

**Skip Logic:**
- `tests/unit/test_incremental_run.py` (new file)
  - Test `should_skip_step()` returns True when input/output unchanged
  - Test `should_skip_step()` returns False when input hash changed
  - Test `should_skip_step()` returns False when output missing
  - Test `find_first_changed_step()` finds correct step index

### 6.2 Integration Tests

**Cross-Process Lock Test:**
- `tests/integration/test_cross_process_locks.py` (new file)
  - Spawn two daemon processes
  - Process A acquires run lock
  - Process B attempts run lock → should fail
  - Process A releases lock
  - Process B acquires lock → should succeed
  - Use `multiprocessing` or `subprocess` to simulate separate processes

**Incremental Run Flow:**
- `tests/integration/test_incremental_run_flow.py` (new file)
  - Create calculation with 3 steps
  - Run calculation → all steps execute, manifest created
  - Run again without changes → all steps skipped
  - Modify step 2 input → steps 2, 3 rerun, step 1 skipped
  - Verify outputs are correct after incremental run

**Edit-While-Run:**
- `tests/integration/test_edit_during_run.py` (new file)
  - Start long-running calculation
  - Attempt to edit calculation.yaml → should succeed (edit lock separate from run lock)
  - Edit should complete, but next run uses new YAML (expected behavior)

### 6.3 End-to-End Tests

**GUI Integration:**
- `tests/integration/test_gui_locking.py` (new file)
  - Start calculation run from GUI
  - Attempt second run from another GUI instance → should show error
  - Verify "Running" badge appears during run

**CLI + GUI Concurrency:**
- `tests/integration/test_cli_gui_concurrency.py` (new file)
  - Start run from CLI
  - Attempt run from GUI → should fail with lock error
  - Verify error message displayed correctly

### 6.4 Regression Tests

**Backward Compatibility:**
- Existing calculations without manifest → should work (full run)
- Calculations with old manifest format → should migrate or ignore gracefully

**History Integration:**
- Verify manifest creation doesn't break existing history recording
- Verify run_id in manifest matches history run_id

---

## 7. Implementation Order

### Phase 1: Locking Infrastructure
1. Add `portalocker` to `requirements.txt`
2. Create `src/quantumvitas/core/locking.py` with lock utilities
3. Implement run lock in `QVService.run_calculation()`
4. Implement edit lock in `save_yaml_doc()`
5. Add unit tests for locks
6. Add integration tests for cross-process locks

### Phase 2: Manifest System
1. Create `src/quantumvitas/calculation/manifest.py`
2. Implement manifest load/save functions
3. Implement hash computation utilities
4. Add manifest update hooks in `CalculationRunner`
5. Add unit tests for manifest

### Phase 3: Incremental Run Logic
1. Implement `should_skip_step()` in `CalculationRunner`
2. Implement `find_first_changed_step()` in `CalculationRunner`
3. Modify `CalculationRunner.run()` to use incremental logic
4. Add manifest update after each step
5. Add integration tests for incremental run flow

### Phase 4: UI/Error Handling
1. Add `CALCULATION_LOCKED` error code
2. Update GUI to handle lock errors
3. Add "Running" badge to calculation cards
4. Add incremental run status display (optional)
5. Add end-to-end tests

### Phase 5: History Integration
1. Move snapshot creation to after materialization (before execution)
2. Link manifest to run_revision (store manifest path in run_revision.json)
3. Verify history recording still works with incremental runs
4. Add tests for history + incremental run integration

---

## 8. Critical Implementation Notes

### 8.1 Materialization Timing

**Current:** Materialization happens during `Calculation.from_yaml()` when `materialize_steps=True`

**Required Change:** Materialization should happen **after** run lock acquisition, **before** snapshot creation

**Rationale:**
- Lock must be held during materialization to prevent concurrent writes
- Snapshot should capture materialized inputs (or their hashes), not just YAML

**Implementation:**
- Move materialization out of `Calculation.from_yaml()` (keep `materialize_steps=False`)
- Add explicit materialization step in `QVService.run_calculation()` after lock acquisition

### 8.2 Manifest vs History

**Relationship:**
- Manifest tracks **what was executed** (input/output hashes)
- History tracks **when and why** (timestamps, run_id, events)
- Manifest is **operational** (for incremental runs)
- History is **audit** (for reproducibility, rollback)

**Storage:**
- Manifest: `calc/.history/manifest-latest.json` (single file, updated in-place)
- History: `project/.history/runs/run_<ULID>/` (append-only, immutable)

**Linking:**
- Manifest contains `run_id` field pointing to last successful run
- Run revision can reference manifest (optional, for rollback feature)

### 8.3 Step Input File Identification

**Current:** Step input file determined during materialization (returned by `materialize_step_spec()`)

**Required:** Manifest must record input file path **after** materialization

**Implementation:**
- After materialization, record `(step_id, input_file_path)` mapping
- Use this mapping when updating manifest
- Input file path relative to `calc/raw/` for portability

### 8.4 Output File Detection

**Current:** Output file determined by engine (e.g., `QECalculationRunner.get_output_file()`)

**Required:** Manifest must record primary output file path after step execution

**Implementation:**
- After step execution, extract output file from `StepResult.output_file`
- Store in manifest as `output_files[0]` (primary output)
- For QE: typically `*.out` file
- For Wannier90: `<seedname>.wout`

### 8.5 Windows Compatibility

**File Locking:**
- `portalocker` handles Windows file locking correctly
- Lock files must be opened in a mode that allows locking (not read-only)

**Path Handling:**
- Use `Path` objects consistently (already done in codebase)
- Lock file paths use forward slashes (Python `Path` normalizes)

**Testing:**
- Run cross-process lock tests on Windows CI (GitHub Actions)
- Verify lock acquisition/release works on Windows

---

## 9. Summary

### Key Findings

1. **No existing cross-process locking** - `JobManager` only prevents concurrent runs within a single process
2. **Materialization happens during calculation load** - should move to after lock acquisition
3. **No incremental run mechanism** - runner always executes all steps
4. **History system exists** - can be extended with manifest for incremental runs
5. **File locking exists** - `fcntl` used in history storage, but not for calc-level coordination

### Recommended Approach

1. **Add `portalocker`** for cross-platform file locking
2. **Implement run lock** before materialization, release after execution
3. **Implement edit lock** during YAML saves (short-held, < 100ms)
4. **Create manifest system** in `calc/.history/manifest-latest.json`
5. **Implement incremental run** by comparing input hashes and skipping up-to-date steps
6. **Update GUI** to show lock status and handle lock errors

### Risks Mitigated

- ✅ Race conditions: Run lock prevents concurrent runs
- ✅ Stale outputs: Manifest tracks input/output hashes, detects changes
- ✅ Edit conflicts: Edit lock prevents concurrent YAML modifications
- ✅ Cross-process safety: File locks work across daemon processes
- ✅ Windows compatibility: `portalocker` handles cross-platform locking

### Constraints Respected

- ✅ No DAG: Linear step execution only
- ✅ No per-step folders: All files in `calc/raw/`
- ✅ No project-level caches: Manifest per calculation
- ✅ Minimal changes: Locking and manifest are internal, API unchanged
- ✅ Existing patterns: Follows history storage patterns (file locking, atomic writes)

