# Phase 3C T4 Root Cause Review

**Date**: 2026-01-12  
**Issue**: `test_t4_runstep_mp2_chain_execution` fails with "Failed to build molecule: list index out of range"  
**Paradox**: Manual subprocess execution of generated `job_chain.json` succeeds

---

## 1) Code Path Analysis: Integration Test Execution

### Test Entry Point

**File**: `tests/integration/test_pyscf_phase3c.py`  
**Function**: `test_t4_runstep_mp2_chain_execution` (lines ~250-311)

The test calls:
```python
result = QMSService.run_step(
    project_root=temp_project,
    calculation_selector=calc_id,
    step_selector=mp2_step_id,
)
```

### Call Chain

**1. API Layer Entry**: `src/qmatsuite/api.py`
- Function: `QMSService.run_step()` (approx lines ~2000-2500)
- Routing logic determines engine based on `calculation.engine_family` ("pyscf")
- For PySCF, routes to: `PySCFEngine.run_step()` or `PySCFEngine.run_step_with_chain()`

**2. Engine Layer - Chain Detection**: `src/qmatsuite/engine/pyscf_engine.py`
- Function: `PySCFEngine.run_step()` (lines ~145-405)
  - Reads `step_type` from `step.yaml` (machine type: "pyscf_mp2")
  - Checks if step has dependencies via registry lookup
  - For `pyscf_mp2` (consumes_state="mf"), calls `run_step_with_chain()`

- Function: `PySCFEngine.run_step_with_chain()` (lines ~550-777)
  - **Line ~570**: Resolves dependency chain using `resolve_dependency_chain()` from `src/qmatsuite/engines/pyscf/chain.py`
  - **Line ~575-600**: Resolves structure from `calculation.structure_id` (for SCF step)
  - **Line ~620-690**: Builds `chain_step_specs` list:
    - For each step in chain, reads parameters from step.yaml
    - **Line ~681**: Only merges `structure_data` if `step_spec.requires_structure == True`
    - For MP2 (requires_structure=False), params should be empty (no structure data)
  - **Line ~695**: Writes `job_chain.json` file
  - **Line ~707**: Executes subprocess: `python -m qmatsuite.engines.pyscf <job_chain.json>`

**3. Dependency Resolution**: `src/qmatsuite/engines/pyscf/chain.py`
- Function: `resolve_dependency_chain()` (lines ~15-100)
  - Input: target_step_ulid, list of (ulid, step_type) tuples, registry
  - For `pyscf_mp2`, finds nearest left step with `produces_state == "mf"` (pyscf_scf)
  - Returns: list of step indices [0, 1] (SCF then MP2)

**4. Subprocess Entry**: `src/qmatsuite/engines/pyscf/__main__.py`
- **Line ~24**: Detects `job_chain.json` format (has "chain_steps" key)
- **Line ~26**: Calls `run_job_chain(job_chain_path)`

**5. Chain Execution Entry**: `src/qmatsuite/engines/pyscf/runner.py`
- Function: `run_job_chain()` (lines ~578-665)
  - **Line ~592**: Reads `job_chain.json`
  - **Line ~644**: Calls `run_chain_session()` from `chain_execution.py`

**6. In-Session Chain Execution**: `src/qmatsuite/engines/pyscf/chain_execution.py`
- Function: `run_chain_session()` (lines ~22-133)
  - **Line ~59**: Creates empty `state_objects: Dict[str, Any] = {}`
  - **Line ~62**: Loops through `chain_steps` sequentially
  - **Line ~80**: For `pyscf_scf` step_type:
    - **Line ~85**: Calls `_run_scf_in_session(params, working_dir, allow_chkfile_init_guess)`
    - **Line ~97**: Stores `state_objects["mf"] = step_result["mf_object"]`
  - **Line ~100**: For `pyscf_mp2` step_type:
    - **Line ~102**: Checks `if "mf" not in state_objects:` → returns error if missing
    - **Line ~107**: Retrieves `mf = state_objects["mf"]`
    - **Line ~108**: Calls `_run_mp2_in_session(params, mf, working_dir)`

**7. MP2 Execution**: `src/qmatsuite/engines/pyscf/chain_execution.py`
- Function: `_run_mp2_in_session()` (lines ~287-334)
  - **Line ~289**: Receives `mf` parameter (PySCF mean-field object)
  - **Line ~303**: Creates `mp2_calc = mp.MP2(mf)`
  - **Line ~304**: Calls `mp2_energy, mp2_corr = mp2_calc.kernel()`
  - **NO `build_mole()` call in this function**

### Summary: Test Execution Path

```
test_t4_runstep_mp2_chain_execution
  → QMSService.run_step()
    → PySCFEngine.run_step()
      → PySCFEngine.run_step_with_chain()
        → resolve_dependency_chain() [finds SCF provider]
        → Builds job_chain.json (with structure for SCF, empty params for MP2)
        → Subprocess: python -m qmatsuite.engines.pyscf job_chain.json
          → run_job_chain()
            → run_chain_session()
              → _run_scf_in_session() → stores state["mf"]
              → _run_mp2_in_session(mf=state["mf"]) → uses mf object
```

**Key Observation**: The test path uses **subprocess execution** - chain runs in a separate Python process via `run_job_chain()`.

---

## 2) Where "mf state" is Produced and Stored

### State Creation Location

**File**: `src/qmatsuite/engines/pyscf/chain_execution.py`  
**Function**: `run_chain_session()` (line ~59)

```python
state_objects: Dict[str, Any] = {}  # In-memory dict, not persisted
```

### State Storage Location

**File**: `src/qmatsuite/engines/pyscf/chain_execution.py`  
**Function**: `run_chain_session()` (lines ~85-98)

```python
if step_type in ("pyscf_scf", ...):
    step_result = _run_scf_in_session(params, working_dir, ...)
    if not step_result["success"]:
        return results  # Error path
    
    # Store mf object in state
    state_objects["mf"] = step_result["mf_object"]  # LINE 97
```

The `mf_object` comes from `_run_scf_in_session()` (lines ~138-285):
- **Line ~153**: Calls `build_mole(params)` to create PySCF `mol` object
- **Line ~157-180**: Creates PySCF mean-field object (`mf = scf.RHF(mol)`, etc.)
- **Line ~280**: Returns `{"mf_object": mf, ...}` in result dict

### State Consumption Location

**File**: `src/qmatsuite/engines/pyscf/chain_execution.py`  
**Function**: `run_chain_session()` (lines ~100-119)

```python
elif step_type == "pyscf_mp2":
    if "mf" not in state_objects:
        results["error"] = "MP2 step requires SCF mf object, but not found in chain state"
        return results
    
    mf = state_objects["mf"]  # LINE 107
    step_result = _run_mp2_in_session(params, mf, working_dir)  # LINE 108
```

### Serialization Boundary Analysis

**Critical Finding**: The chain execution happens in a **single Python subprocess session**.

- `job_chain.json` contains **parameters only** (no mf objects - they're not JSON-serializable)
- `run_chain_session()` maintains `state_objects` dict **in-memory within the same process**
- **No serialization/deserialization of mf objects** - they remain as Python objects in memory

**Contract**: State is **in-memory only, never persisted**. The `job_chain.json` contains step parameters, but state objects (`mf`, `mp2`) are created and passed in-memory within `run_chain_session()`.

---

## 3) Proof: Does MP2 Actually Receive mf?

### Evidence from Code

**File**: `src/qmatsuite/engines/pyscf/chain_execution.py`

**Function**: `_run_mp2_in_session()` (lines ~287-334)

```python
def _run_mp2_in_session(
    params: Dict[str, Any],
    mf: Any,  # PySCF mean-field object - passed as parameter
    working_dir: Path,
) -> Dict[str, Any]:
    from pyscf import mp
    
    start_time = time.time()
    
    try:
        # Run MP2
        mp2_calc = mp.MP2(mf)  # LINE 303 - uses mf parameter directly
        mp2_energy, mp2_corr = mp2_calc.kernel()
        # ...
```

**Key Finding**: `_run_mp2_in_session()` **does NOT call `build_mole()`**. It receives `mf` as a parameter and uses it directly.

### Where "Failed to build molecule" Error Originates

**File**: `src/qmatsuite/engines/pyscf/chain_execution.py`  
**Function**: `_run_scf_in_session()` (lines ~138-285)

```python
def _run_scf_in_session(...):
    from qmatsuite.engines.pyscf.runner import build_mole
    try:
        mol = build_mole(params)  # LINE 153
    except Exception as e:
        import traceback
        error_msg = f"Failed to build molecule: {e}"  # LINE 156
        traceback_str = traceback.format_exc()
        return {
            "success": False,
            "error": f"{error_msg}\n{traceback_str}",  # LINE 160
            "execution_time": 0.0,
        }
```

**Critical Discovery**: The error "Failed to build molecule: list index out of range" is coming from **SCF step execution**, not MP2 step execution.

### Error Propagation Path

1. `run_chain_session()` calls `_run_scf_in_session()` (line ~85)
2. `_run_scf_in_session()` calls `build_mole(params)` (line ~153)
3. `build_mole()` fails with `IndexError: list index out of range`
4. Error is caught and formatted as "Failed to build molecule: list index out of range" (line ~156-160)
5. `run_chain_session()` checks `if not step_result["success"]:` (line ~91)
6. Returns error (line ~92-94)
7. Since SCF failed, `state_objects["mf"]` is **never set**
8. MP2 step is **never reached** because chain execution stops after SCF failure

**However**: The test error message shows `step_type='mp2'` in the result, suggesting the error is being attributed to the MP2 step even though it originates in SCF.

### Analysis: Why Error is Attributed to MP2

The error result returned from `run_chain_session()` contains information about the **target step** (MP2), even though the failure occurred in a **provider step** (SCF). This is because:

- `run_step_with_chain()` sets `step_type=target_step_type` in the StepResult (line ~766 in `pyscf_engine.py`)
- The error message from SCF step is propagated up, but the StepResult metadata reflects the target step

**Conclusion**: MP2 **never executes** in the failing path. The error occurs in SCF step when `build_mole()` is called with invalid/empty atoms data.

---

## 4) Manual Subprocess Run vs Integration Test: Divergence Analysis

### Manual Subprocess Execution Path

**Command**: `python -m qmatsuite.engines.pyscf <job_chain.json>`

**Execution**:
1. `__main__.py` detects `job_chain.json` format
2. Calls `run_job_chain(job_chain_path)` directly
3. `run_job_chain()` calls `run_chain_session()` with chain_steps from JSON
4. `run_chain_session()` executes steps sequentially in same process
5. SCF runs → produces mf → stores in state
6. MP2 runs → consumes mf from state → succeeds

**Key**: Manual run uses the **exact same code path** as the test, but with a **different `job_chain.json` file**.

### Integration Test Execution Path

**Command**: `QMSService.run_step()` → `PySCFEngine.run_step_with_chain()` → subprocess

**Execution**:
1. Test calls `QMSService.run_step()`
2. Engine builds `job_chain.json` dynamically
3. Subprocess executes with that `job_chain.json`
4. **Same code path as manual**, but with different input data

### Side-by-Side Comparison

| Aspect | Manual Run | Integration Test |
|--------|------------|------------------|
| Entry point | Direct `run_job_chain()` | `QMSService.run_step()` → `run_step_with_chain()` |
| job_chain.json source | Pre-existing file (from test run) | Dynamically generated by engine |
| Structure data | Present in SCF step params | Should be present (resolved from calculation.structure_id) |
| MP2 params | Empty (no structure data) | Should be empty (requires_structure=False) |
| Execution path | `run_chain_session()` | `run_chain_session()` (same) |
| State creation | `state_objects["mf"]` set by SCF | `state_objects["mf"]` should be set by SCF |
| Error location | None (manual run succeeds) | SCF step `build_mole()` fails |

### Hypothesis: Structure Data Issue in Test-Generated job_chain.json

**Evidence**:
- Manual run succeeds with job_chain.json from test run directory
- Test fails even though code paths are identical
- Error occurs in SCF step, not MP2 step
- Error is "list index out of range" in `build_mole()`

**Possible Causes**:
1. **Structure data is missing/invalid in SCF params**: When `run_step_with_chain()` resolves structure (line ~575-600), the structure data might not be correctly merged into SCF step params
2. **Atoms list is empty**: `build_mole()` receives `params` with empty or invalid `atoms` list
3. **Timing/race condition**: Structure resolution happens, but params dict is not properly updated before job_chain.json is written

**File**: `src/qmatsuite/engine/pyscf_engine.py` (lines ~668-686)

```python
# Get parameters
params = {}
if hasattr(step, 'parameters'):
    params = step.parameters.copy() if isinstance(step.parameters, dict) else step.parameters
# ...
step_spec = registry.get(step_type)
if step_spec and step_spec.requires_structure and structure_data:
    params = {**params, **structure_data}  # LINE 681 - merge structure_data
```

**Critical Observation**: Structure data is merged **only if `step_spec.requires_structure == True`**. For SCF (`pyscf_scf.requires_structure == True`), this should work. However, if `structure_data` is `None` or empty, or if the merge happens after params are already copied, the structure might be missing.

**Another Hypothesis**: The error "list index out of range" suggests that `params["atoms"]` exists but is an empty list `[]`, or one of the atoms has empty `coords`. This could happen if:
- Structure resolution fails silently
- Structure data is not properly converted to atoms format
- Atoms list is created but not populated

---

## 5) Step Type Representation Analysis

### Multiple Step Type Representations

**1. step.yaml meta.step_type (Machine Type)**
- **Location**: `step.yaml` file, `meta.step_type` field
- **Example**: `"pyscf_mp2"`, `"pyscf_scf"`
- **Used by**: Step execution, engine dispatch, registry lookup

**2. calculation.yaml steps[].type (Public Type)**
- **Location**: `calculation.yaml`, `steps` list, optional `type` field
- **Example**: `"mp2"`, `"scf"`
- **Used by**: UI, workflow intent (not execution)

**3. StepType Enum**
- **Location**: `src/qmatsuite/calculation/types.py`
- **Examples**: `StepType.PYSCF_SCF`, `StepType.CUSTOM`
- **Limitation**: Does not have `PYSCF_MP2` (only has `PYSCF_SCF`)
- **Used by**: Legacy code, UI display

### Step Type Usage in Chain Execution

**Dependency Resolution**: `src/qmatsuite/engines/pyscf/chain.py`
- **Input**: List of `(ulid, step_type)` tuples where `step_type` is **machine type string** (from step.yaml)
- **Line ~40**: Looks up `registry.get(step_type)` using machine type
- **Line ~50**: Checks `spec.produces_state` and `spec.consumes_state`

**Engine Execution**: `src/qmatsuite/engine/pyscf_engine.py`
- **Line ~570**: Reads `step_type` from step.yaml (machine type)
- **Line ~658**: Validates `step_type` is in registry using machine type
- **Line ~680**: Looks up `registry.get(step_type)` using machine type

**Chain Session Execution**: `src/qmatsuite/engines/pyscf/chain_execution.py`
- **Line ~64**: Receives `step_type` from `step_spec["step_type"]` (machine type from job_chain.json)
- **Line ~80**: Checks `if step_type in ("pyscf_scf", ...)` using machine type string
- **Line ~100**: Checks `elif step_type == "pyscf_mp2"` using machine type string

### For the Failing Test

**Resolver sees**: Machine type `"pyscf_mp2"` (from step.yaml)  
**Engine sees**: Machine type `"pyscf_mp2"` (from step.yaml)  
**MP2 executor sees**: Machine type `"pyscf_mp2"` (from job_chain.json step_spec)

**Conclusion**: No "double truth" issue - all execution paths use machine type strings from step.yaml. The enum representation is not used in execution paths.

---

## 6) Minimal Fix Direction

### Root Cause Identification

**Violated Invariant**: SCF step must receive valid structure data (atoms list) to build molecule. The structure data is resolved from `calculation.structure_id` but may not be correctly merged into SCF step params before `job_chain.json` is written.

**Evidence**:
- Error occurs in `_run_scf_in_session()` → `build_mole(params)` (line 153)
- Error is "list index out of range", suggesting `atoms` list is empty or has invalid coords
- Manual run succeeds, suggesting the issue is in **structure data preparation**, not execution

### Proposed Fix

**Location**: `src/qmatsuite/engine/pyscf_engine.py`, `run_step_with_chain()` method

**Problem Area**: Lines ~575-600 (structure resolution) and ~668-686 (parameter merging)

**Fix Direction**:
1. **Ensure structure_data is always populated for SCF steps**:
   - Add explicit validation: if SCF step requires structure but `structure_data` is None/empty, raise clear error
   - Ensure structure resolution completes before building chain_step_specs

2. **Validate atoms list before writing job_chain.json**:
   - After merging structure_data into SCF params, validate that `params["atoms"]` is non-empty
   - Raise error immediately if structure data is invalid, rather than failing later in subprocess

3. **Add defensive check in build_mole()**:
   - In `src/qmatsuite/engines/pyscf/runner.py`, `build_mole()` function (line ~69)
   - Add explicit check: `if not atoms or len(atoms) == 0: raise ValueError("Atoms list is empty")`
   - This provides clearer error message than "list index out of range"

**Why This Fix Preserves Contract**:
- Does not change state dependency model (mf still passed in-memory)
- Does not change MP2 execution (MP2 still receives mf from state)
- Only fixes structure data preparation for SCF step
- Does not affect QE/W90 (they use different engine paths)

**Minimal Change**: Add validation in `run_step_with_chain()` after structure resolution to ensure `structure_data` contains valid atoms before merging into params.

---

## 7) Verification Checklist

To confirm this diagnosis, add temporary debug prints/asserts:

### Checklist Items

1. **Structure Resolution Validation** (in `run_step_with_chain()`, after line ~600):
   ```python
   assert structure_data is not None, "structure_data must not be None for SCF step"
   assert "atoms" in structure_data, "structure_data must contain 'atoms' key"
   assert len(structure_data["atoms"]) > 0, f"atoms list is empty: {structure_data}"
   ```

2. **Params Validation Before job_chain.json Write** (after line ~686, before line ~695):
   ```python
   for step_spec in chain_step_specs:
       step_type = step_spec["step_type"]
       params = step_spec["parameters"]
       if step_type == "pyscf_scf":
           assert "atoms" in params, f"SCF params missing atoms: {params.keys()}"
           assert len(params["atoms"]) > 0, f"SCF atoms list is empty"
   ```

3. **build_mole() Input Validation** (in `chain_execution.py`, `_run_scf_in_session()`, before line ~153):
   ```python
   print(f"DEBUG: _run_scf_in_session params keys: {params.keys()}")
   if "atoms" in params:
       print(f"DEBUG: atoms count: {len(params['atoms'])}")
       if len(params["atoms"]) > 0:
           print(f"DEBUG: first atom: {params['atoms'][0]}")
   ```

4. **State Object Verification** (in `run_chain_session()`, after line ~97):
   ```python
   assert "mf" in state_objects, "mf must be in state_objects after SCF"
   assert state_objects["mf"] is not None, "mf object must not be None"
   ```

5. **MP2 Execution Entry Point** (in `run_chain_session()`, line ~107):
   ```python
   print(f"DEBUG: MP2 step, mf type: {type(mf)}, mf.mol.natm: {mf.mol.natm}")
   ```

Running the test with these assertions would immediately reveal:
- Whether structure_data is None/empty
- Whether atoms list is empty in params
- Whether mf object is actually created and stored
- Whether MP2 step is reached (it should not be if SCF fails)

---

## Summary

**Root Cause**: The error "Failed to build molecule: list index out of range" originates in the **SCF step**, not MP2 step. The SCF step's `build_mole(params)` call receives invalid/empty atoms data, causing the chain execution to fail before MP2 is reached.

**Why Manual Run Succeeds**: Manual run uses a `job_chain.json` file that was successfully generated by a previous test run (or manually crafted), where structure data was correctly populated. The integration test generates `job_chain.json` dynamically, and structure data resolution/merging may fail silently or produce invalid data.

**Fix Direction**: Add validation to ensure structure data is correctly resolved and merged into SCF step params before writing `job_chain.json`. Add defensive checks in `build_mole()` to provide clearer error messages.

