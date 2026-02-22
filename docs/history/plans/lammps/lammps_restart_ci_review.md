# LAMMPS restart/chain CI Regression: Root Cause Analysis

**Date**: 2026-01-19  
**Status**: Analysis Complete  
**Failing Tests**:
- `tests/integration/test_lammps_long_smoke.py::test_workflow_d_restart`
- `tests/integration/test_lammps_chain.py::test_chain_workflow`

**Environment**:
- ✅ Mac CI: PASS
- ✅ Mac Local: PASS
- ❌ Ubuntu CI: FAIL

---

## 1. Error Summary

```
Failed to materialize inputs: No restart artifact found for step <UPSTREAM_ULID>. 
Expected restart.bin or final.data in <calc>/raw/<UPSTREAM_ULID>/
```

**Stack Trace Path**:
```
lammps_step_handler (handlers.py:504)
  → LammpsEngine.materialize_inputs (lammps_engine.py:61)
    → _resolve_restart_artifact (lammps_engine.py:266)
      → FileNotFoundError raised (lammps_engine.py:333)
```

---

## 2. Code Flow Analysis

### 2.1 How `restart_from` flows from step.yaml to engine

1. **Step YAML** contains `parameters.restart_from: <upstream_step_ulid>`

2. **Recipe Materialization** (`recipes.py:LAMMPSRecipe.materialize()`):
   - Creates `JobGraph` with one `Job` per step
   - Sets linear dependencies: `deps = [jobs[-1].id]` (line 413-414)
   - **Note**: `deps` field exists but is NOT enforced by executor

3. **Executor Loop** (`executor.py:144`):
   ```python
   for job in jobs_to_execute:
       # ... skip logic ...
       job_result = self._execute_job(job, calculation)
       if not job_result.success:
           break  # Stop on first failure
   ```

4. **Handler Calls Engine** (`handlers.py:lammps_step_handler`):
   ```python
   engine.materialize_inputs(step_spec, working_dir, calculation)  # Line 504
   ```

5. **Engine Resolves Restart** (`lammps_engine.py:_resolve_restart_artifact()`):
   ```python
   ref_workdir = calculation.io.raw_dir / ref_step_ulid  # Line 315
   restart_bin = ref_workdir / "restart.bin"             # Line 318
   if restart_bin.exists(): return restart_bin
   # ... try restart.*.bin pattern ...
   final_data = ref_workdir / "final.data"               # Line 329
   if final_data.exists(): return final_data
   raise FileNotFoundError(...)                          # Line 333
   ```

### 2.2 What files `_resolve_restart_artifact` looks for

**Location**: `<calculation.io.raw_dir>/<upstream_step_ulid>/`

**Search Order**:
1. `restart.bin` (preferred - includes velocities)
2. `restart.*.bin` pattern (e.g., `restart.final.bin`)
3. `final.data` (fallback - structure only, for relax steps)

### 2.3 Why executor allows downstream materialize before upstream artifact exists

**Current Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│                     JobExecutor.execute()                       │
│                                                                 │
│  for job in jobs_to_execute:     ← Sequential loop             │
│      if should_skip: continue                                   │
│      job_result = _execute_job(job)                            │
│      if not success: break                                      │
└─────────────────────────────────────────────────────────────────┘
```

**Observations**:
1. **No Parallelism in Executor**: Jobs run sequentially in a simple `for` loop
2. **deps Field Unused**: `Job.deps` is declared but never checked by executor
3. **Break on Failure**: If job 1 fails, loop stops

**Therefore, the only way this error can occur**:
1. Job 1 (upstream) runs to "completion" but doesn't produce expected artifacts
2. Job 1 returns `success=True` despite missing output files
3. Job 2 then runs and fails to find the artifact

---

## 3. Mac vs Ubuntu Difference Analysis

### 3.1 Hypothesis: LAMMPS Output Verification Gap

**Current Success Check** (`handlers.py:532`):
```python
success = result.success if hasattr(result, "success") else False
```

This relies on `LammpsEngine.run_step()` return value, which checks:
- LAMMPS process exit code
- Basic log parsing

**Missing**: Verification that `final.data` or `restart.bin` actually exists before declaring success.

### 3.2 Hypothesis: Filesystem Timing Differences

**macOS APFS**:
- Unified buffer cache
- Immediate metadata visibility after `close()`

**Linux ext4**:
- More asynchronous I/O operations
- `final.data` might not be visible immediately after LAMMPS exits

**Evidence Needed**: Check if adding `fsync()` or file existence wait resolves the issue.

### 3.3 Hypothesis: LAMMPS Binary Behavior Differences

Ubuntu CI might have:
- Different LAMMPS version (apt-get vs brew)
- Different compile options (no `write_data` command support?)
- MPI vs serial build differences

**Evidence Needed**: Compare LAMMPS version/capabilities on both platforms.

---

## 4. Critical Finding: No Output Verification Before Continue

**Root Cause**: The LAMMPS handler does NOT verify that restart/relax artifacts exist before returning success.

```python
# handlers.py lammps_step_handler
result = engine.run_step(step_spec, working_dir, calculation)
success = result.success if hasattr(result, "success") else False
# ↑ Only checks LAMMPS exit code, not artifact existence!

# MISSING: Verification that expected outputs exist
# For relax: final.data must exist
# For MD with restart: restart.bin must exist
```

**Compare with QE**: QE's `is_step_done()` checks for "JOB DONE" marker in output file.
**LAMMPS Gap**: No equivalent output verification for LAMMPS.

---

## 5. Secondary Issue: restart_from Not in Explicit Dependency Graph

**Current State**:
- `restart_from` is only resolved at materialize time (inside `_resolve_restart_artifact`)
- JobGraph has linear deps but they're not enforced
- If we ever parallelize job execution, this will break catastrophically

**Constitutional Violation Risk**:
- `restart_from` represents an artifact dependency that should be in the DAG
- Current implementation hides this dependency inside engine-specific code

---

## 6. Recommended Fix Strategy

### Fix 1 (Immediate): Verify Output Before Declaring Success

Add output verification to `lammps_step_handler` after `run_step()`:

```python
# After run_step, verify expected outputs exist
public_type = job.metadata.get("public_type")
if success and public_type == "relax":
    if not (working_dir / "final.data").exists():
        success = False
        error_msg = "Relax step succeeded but final.data not found"

if success and "restart_from" not in params:
    # MD step without restart should produce restart.bin for downstream
    # (Optional: only if other steps depend on it)
    pass
```

### Fix 2 (Proper): Make restart_from an Explicit Dependency

Modify `LAMMPSRecipe.materialize()` to:
1. Parse `restart_from` from step parameters
2. Add edge in JobGraph: `restart_from_step_ulid → current_step_ulid`

This ensures:
- Topological ordering respects artifact dependencies
- Future parallel execution won't break
- Clear dependency graph for debugging

---

## 7. Evidence Collection Required

Before implementing, Auto should collect:

1. **Ubuntu CI LAMMPS Version**:
   ```bash
   which lmp_serial || which lmp_mpi || which lmp
   lmp_serial -h 2>&1 | head -5
   ```

2. **Ubuntu CI File System Check**:
   ```bash
   stat --file-system /tmp
   ```

3. **Reproduce Locally with Linux Container**:
   ```bash
   docker run -v $(pwd):/workspace -w /workspace ubuntu:latest bash -c "
     apt-get update && apt-get install -y lammps python3 python3-pip
     pip install -e .
     pytest tests/integration/test_lammps_chain.py -v
   "
   ```

4. **Add Debug Logging**:
   - Log directory contents after `run_step()` returns
   - Log file system sync status

---

## 8. Files Involved in Fix

| File | Change Type | Purpose |
|------|-------------|---------|
| `src/qmatsuite/execution/handlers.py` | Modify | Add output verification in `lammps_step_handler` |
| `src/qmatsuite/execution/recipes.py` | Modify | Parse restart_from and add dependency edges |
| `src/qmatsuite/calculation/step_done.py` | Add | LAMMPS step done detection |
| `tests/integration/test_lammps_chain.py` | Modify | Add parallel-safe assertions |
| `tests/integration/test_lammps_long_smoke.py` | Modify | Add parallel-safe assertions |

---

## 9. Conclusion

**Primary Root Cause**: LAMMPS handler declares success based only on process exit code, without verifying that expected output artifacts (`final.data`, `restart.bin`) actually exist.

**Secondary Issue**: `restart_from` is not represented as an explicit dependency in JobGraph, which is a latent bug that will manifest if we ever parallelize job execution.

**Why Mac Works**: Likely faster/more synchronous filesystem ensures artifacts are visible immediately after process exit. Linux's more asynchronous I/O may cause a brief window where files exist but aren't yet visible.

**Recommended Approach**: 
1. (PR1) Add output verification to `lammps_step_handler`
2. (PR2) Optionally add explicit `restart_from` edges to JobGraph for future-proofing

