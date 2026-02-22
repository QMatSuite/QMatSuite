# Runner System Deep Review

**Date**: 2026-02-19
**Scope**: Complete architecture review of QMatSuite's runner system
**Method**: READ-ONLY investigation of all source files involved in calculation execution

---

## 1. Architecture Overview

### 1.1 Entry Points

The runner system has a layered entry-point hierarchy:

| Layer | Function | File:Line | Signature |
|-------|----------|-----------|-----------|
| **MCP** | `run_calculation()` | `mcp/tools/run_calculation.py:10` | `(calc_ulid: str) -> dict` |
| **MCP** | `quick_run()` | `mcp/tools/quick_run.py:137` | (combo tool, calls `svc.run.run_calculation()`) |
| **Service** | `RunSubservice.run_calculation()` | `api/service.py:6197` | `(calc_selector, steps, *, run_mode, run_ulid) -> RunResultDTO` |
| **Service** | `RunSubservice.run_step()` | `api/service.py:6304` | `(calc_selector, step_selector, *, run_ulid) -> RunResultDTO` |
| **Kernel** | `CalculationRunner.run()` | `calculation/runner.py:115` | `(calculation, *, run_ulid, run_mode, target_step_ulid, compat_input_playback) -> CalculationResult` |
| **Kernel** | `CalculationRunner._execute_with_jobgraph()` | `calculation/runner.py:477` | (internal, orchestrates JobGraph pipeline) |
| **Executor** | `JobExecutor.execute()` | `execution/executor.py:95` | `(job_graph, calculation, selection, target_step_ulid, manifest, step_shas) -> ExecutionResult` |

**Call chain for MCP `run_calculation`:**
```
MCP run_calculation(calc_ulid)
  → svc.run.run_calculation(calc_ulid)       # service.py:6262, run_mode="incremental" hardcoded
    → CalculationRunner.run(calculation, run_mode="incremental")  # runner.py:115
      → reconcile_manifest(...)               # manifest_reconcile.py:31
      → _execute_with_jobgraph(...)           # runner.py:477
        → recipe.materialize(steps, ...)      # engine recipe
        → JobExecutor.execute(job_graph, ...) # executor.py:95
          → _should_skip_job(job, ...)        # executor.py:250
          → _execute_job(job, calculation)    # executor.py:672
```

### 1.2 Recipe System

Each engine declares a **Recipe** that knows how to turn a list of Step objects into a **JobGraph**. The recipe is the bridge between the abstract calculation topology and the engine-specific execution model.

**Protocol** (`execution/recipes.py:117`):
```python
class Recipe(Protocol):
    def materialize(self, steps, calc_raw_dir, step_shas) -> JobGraph: ...
```

**Base class** (`execution/recipes.py:145`): `BaseRecipe(ABC)` — all 15 engine recipes inherit from this.

**Factory** (`execution/recipes.py:167`):
```python
def get_recipe_for_engine(engine_family: str) -> BaseRecipe:
    recipe_class = DriverRegistry.get_recipe_class(engine_family)
    return recipe_class()
```

There are three recipe archetypes:

| Archetype | Working Dir | Jobs | Engines |
|-----------|------------|------|---------|
| **Directory-state** | Shared `calc/raw/` | 1 per step, `deps=[]` | QE, W90, ABINIT, Siesta, GPAW, xTB, Yambo, Gaussian, CP2K, QMCPACK |
| **Isolated-workdir** | Per-step `calc/raw/<step_ulid>/` | 1 per step, linear `deps` | VASP, LAMMPS |
| **QC strong-chain** | Per-chain `calc/raw/scf_<suffix>/` | 1 per subchain, `deps=[]` | ORCA, Psi4, PySCF |

### 1.3 Job Graph

**`execution/job_graph.py`** — runtime-only DAG (never persisted).

**Job fields** (dataclass at line 30):
- `id: str` — unique within graph (e.g., `"step_00"`, `"s_m2"`, or a ULID)
- `step_ulids: List[str]` — steps covered (1 for QE, N for ORCA subchain)
- `working_dir: Path` — where job executes
- `command: List[str]` — e.g., `["pw.x", "scf.in"]` or `["<internal>"]`
- `input_files: List[Path]` — input file references
- `expected_outputs: List[Path]` — completion markers
- `deps: List[str]` — job IDs this depends on (used by VASP/LAMMPS, empty for QE/ORCA)
- `fingerprint: Optional[str]` — combined step SHA(s)
- `metadata: Dict` — engine name, step types, scratch dir

**JobGraph** (dataclass at line 102):
- `jobs: List[Job]` — topologically sorted
- `get_jobs_for_target(target_step_ulid, mode)` — returns prefix-to-target for TARGET mode
- `get_job_by_step_ulid(step_ulid)` — lookup
- **Note**: The `deps` field on Job is declared but NOT used by the executor for skip logic or ordering. Jobs are executed in list order. `deps` exists for future parallel execution.

### 1.4 GEN → SPEC Step Mapping

Steps have two type identifiers:
- `step_type_gen` — user-facing intent (e.g., `"scf"`, `"bandspw"`, `"bands"`)
- `step_type_spec` — engine-specific execution unit (e.g., `"qe_scf"`, `"qe_bandspw"`, `"qe_bands"`)

The mapping is resolved via the **StepTypeRegistry** (`workflow/registry.py`):
- `registry.get(gen_type)` → `StepTypeSpec` with `.step_type_gen`, `.step_type_spec`, `.engine`, `.executable`, `.supports_incremental_skip`
- `gen_from(spec_type)` extracts the GEN type from a SPEC type

The recipe uses GEN types for file naming (`scf.in`, `bandspw.in`) and SPEC types for registry lookups. The step YAML stores `step_type_spec` as the canonical identifier.

---

## 2. Run Modes

### 2.1 Run Calc — Incremental (Default)

**Entry**: `runner.py:263-304`

Flow:
1. **Compute current SHAs**: `pseudo_set_sha`, `structure_sha`, and per-step `step_sha` (lines 362-423)
2. **Reconcile manifest**: `reconcile_manifest()` aligns old manifest to current topology, returns `(manifest, first_changed_idx)` (line 291)
3. **`start_idx` is computed but NEVER USED** — it is only logged (line 298)
4. **Build JobGraph**: `recipe.materialize(steps, raw_dir, step_shas)` (line 537)
5. **Execute**: `executor.execute(job_graph, manifest=manifest, step_shas=step_shas)` (line 564)
6. **Per-job skip decision**: Executor's `_should_skip_job()` checks each job independently against manifest
7. **Post-execution**: For each executed (not skipped) job, update manifest with new SHAs and `done=True` (line 623)

### 2.2 Run Calc — Full

**Entry**: `runner.py:305-352`

Flow:
1. **Reconcile manifest** (same as incremental, line 329)
2. **Force all entries to `done=False`**: Loops through all manifest entries and clears done/timestamps/run_ulid (lines 339-344)
3. **Save cleared manifest**: `save_manifest_atomic()` (line 344)
4. **`start_idx = 0`** (line 349, but unused)
5. **Execute**: Same JobGraph pipeline as incremental, but now all entries have `done=False`, so no jobs are skipped

### 2.3 Run Step — Single Step (TARGET Mode)

**Entry**: Service layer `run_step()` at `api/service.py:6304` calls `runner.run()` with `target_step_ulid=<ulid>`

Flow:
1. Runner passes `target_step_ulid` to `_execute_with_jobgraph()` (line 434)
2. `SelectionMode.TARGET` is set (line 542)
3. `job_graph.get_jobs_for_target()` returns jobs from start up to and including the target job (line 122/executor.py)
4. Executor determines `target_job_id` (line 136-139)
5. For target job: `is_target_job=True` → `_should_skip_job()` returns `False` (always runs)
6. For preceding jobs: Normal skip logic applies

**Critical gap**: After successful target step execution, **`clear_manifest_from_step()` is NOT called**. Constitution §5.3 mandates: "After success, conservatively marks downstream steps as `done=false`." This function exists at `manifest.py:227-256` but is dead code — never called from any runner path.

### 2.4 Run Step — Chained Engine (ORCA/PySCF)

For QC engines, the recipe creates **subchain jobs**. For a chain [SCF, MP2, TDDFT]:
- Job `"s"`: Runs SCF only (step_ulids: [scf_ulid])
- Job `"s_m2"`: Runs SCF+MP2 fused (step_ulids: [scf_ulid, mp2_ulid])
- Job `"s_t"`: Runs SCF+TDDFT fused (step_ulids: [scf_ulid, tddft_ulid])

Each subchain is self-contained (`deps=[]`). In TARGET mode, `get_jobs_for_target()` returns all jobs up to and including the target — the target job already contains the full chain from SCF root, so no separate "trace back to SCF" logic is needed. The chain boundary is implicit in the recipe's materialization.

---

## 3. Skip Logic

### 3.1 `_should_skip_job()` — Complete Analysis

**Location**: `execution/executor.py:250-289`

```python
def _should_skip_job(self, job, *, manifest, step_shas, is_target_job) -> bool:
    # Rule 1: Target job MUST run
    if is_target_job:
        return False

    # Rule 2: No manifest = can't skip
    if manifest is None:
        return False

    # Rule 3: Check ALL steps in this job
    for step_ulid in job.step_ulids:
        entry = self._get_manifest_entry_for_step(manifest, step_ulid)

        # 3a: No manifest entry = can't skip
        if entry is None:
            return False

        # 3b: Not done = can't skip
        if not entry.done:
            return False

        # 3c: Fingerprint mismatch = can't skip
        if step_shas:
            current_sha = step_shas.get(step_ulid)
            if current_sha and entry.step_sha != current_sha:
                return False

    # All steps done with matching SHAs → SKIP
    return True
```

**What it checks**:
- Target job status
- Manifest existence
- Per-step: `done` flag + `step_sha` match

**What it does NOT check**:
- `pseudo_set_sha` match (only checked in `reconcile_manifest` and standalone `should_skip_step()`)
- `structure_sha` match (same)
- `kind` match (same)
- **Whether any upstream job ran in this execution** (NO cascade check)
- **Whether any upstream step's SHA changed** (NO inter-step dependency)

### 3.2 `should_skip_step()` — Standalone Function

**Location**: `manifest.py:277-320`

This is a more thorough check used by `reconcile_manifest`:
```python
def should_skip_step(manifest_entry, current_kind, current_pseudo_set_sha,
                     current_structure_sha, current_step_sha) -> bool:
    # Checks: kind match + 3 SHA matches + done==True
```

It checks `kind`, `pseudo_set_sha`, `structure_sha`, `step_sha`, and `done`. However, it is only used during reconciliation to evaluate each step's OWN inputs — it does NOT check upstream step status.

### 3.3 The Cascade Rule — ABSENT

**Constitutional mandate** (§5.3): "Run Single Step: The target step must always execute (no skip). After success, conservatively marks downstream steps as `done=false`."

**Implementation status**: NOT IMPLEMENTED in any form.

Searched for cascade logic in:
- `reconcile_manifest()` — evaluates each step INDEPENDENTLY. `first_changed_idx` is returned but never used to cascade.
- `_should_skip_job()` — evaluates each job INDEPENDENTLY. No tracking of "which jobs ran in this execution."
- `runner._execute_with_jobgraph()` — iterates job results after execution but never calls `clear_manifest_from_step()`.
- `clear_manifest_from_step()` — EXISTS at `manifest.py:227-256`, properly sets `done=False` for all entries from a given index onward. **But it is dead code — never called from any production path.** Only referenced in one test (`tests/integration/test_incremental_run.py:745`).

**The cascade rule exists nowhere in the execution pipeline.** Each step/job is evaluated purely on its own manifest entry. Upstream step re-execution has zero effect on downstream skip decisions.

### 3.4 Manifest Structure

**Location**: `manifest.py:25-61`

```python
@dataclass
class ManifestStepEntry:
    kind: str                              # Step type (e.g., "scf", "bandspw")
    step_ulid: str                         # Step ULID
    pseudo_set_sha: str                    # SHA256 of pseudo set
    structure_sha: str                     # SHA256 of structure JSON
    step_sha: str                          # SHA256 of step YAML (meta stripped)
    effective_structure_sha: Optional[str]  # For relax-aware skip logic
    run_ulid: Optional[str]                # Last run ULID
    done: bool                             # Completion flag
    started_at: Optional[str]              # ISO8601
    done_at: Optional[str]                 # ISO8601
```

**Persistence**: JSON file at `<calc_dir>/.run_tmp_info/manifest.json`. Written atomically (temp file + rename). Schema version 1.

**Lifecycle**:
1. Created/updated during `reconcile_manifest()` at run start
2. Individual entries updated via `update_manifest_step()` after each job executes
3. Deletable (§5.1: "runtime bookkeeping — deletable, not SSOT")

### 3.5 SHA Computation

**Location**: `calculation/hash_utils.py`

**`compute_step_sha(step_doc, variant_assignments=None)`** (line 266):
1. If `variant_assignments` provided, resolves `@scan:X` tokens to concrete values
2. Removes `parameter_scan` section
3. Strips meta keys: `meta`, `__qms_meta__`, `id`, `name`, `slug`, `path`, `kind`, `created_at`, `updated_at`
4. Canonicalizes: sorts dict keys, normalizes floats to `1e-10` tolerance
5. JSON-serializes with `sort_keys=True`
6. Returns `sha256(serialized).hexdigest()`

**What's included in step_sha**:
- ALL remaining keys in step YAML after meta stripping: `parameters`, `cards`, `step_type_spec`, `step_type_gen`, `engine`, `options`, etc.
- **Cards ARE included** — changing K_POINTS data DOES change step_sha
- **step_type fields ARE included** — changing step type changes SHA

**What's NOT included**:
- Meta fields (ulid, slug, name, timestamps)
- `parameter_scan` section

**`compute_structure_sha(structure_path)`** (line 226): Strips meta, canonicalizes, hashes structure JSON.

**`compute_pseudo_set_sha(project_pseudo_dir, species_map)`** (line 314): Derives from `pseudo_sha256` in species_map records (does NOT read files). Tokens: `"element:sha256"` sorted and joined.

### 3.6 `clear_manifest_from_step()` — Dead Code

**Location**: `manifest.py:227-256`

```python
def clear_manifest_from_step(calc_dir: Path, from_step_index: int) -> None:
    """Sets done=False for all entries from from_step_index to end."""
    manifest = load_manifest(calc_dir)
    if not manifest:
        return
    if from_step_index >= len(manifest.steps):
        return
    for i in range(from_step_index, len(manifest.steps)):
        entry = manifest.steps[i]
        entry.done = False
        entry.done_at = None
        # Keeps run_ulid, started_at, and SHAs for traceability
    save_manifest_atomic(calc_dir, manifest)
```

**Callers**: NONE in production code. Only called in one integration test (`test_incremental_run.py:745`). This function was written for the cascade rule but never wired into the runner.

### 3.7 `reconcile_manifest()` — No Cascade

**Location**: `manifest_reconcile.py:31-261`

The reconciler processes steps independently in a single pass:

```
for each step i in current topology:
    if old_manifest has entry at i:
        if kind matches:
            if all 3 SHAs match:
                if supports_incremental_skip AND actually_done → done=True (skip)
                else → done=False
            else → done=False (SHAs changed)
        else → done=False (kind mismatch)
    else → done=False (new step)

    track first_changed_idx = min(first_changed_idx, i) when done=False
```

**Critical observation**: When step 1's SHAs change (`done=False`), step 2 is still evaluated independently. If step 2's own SHAs haven't changed and it was previously done, it stays `done=True`. There is no cascade: "step 1 changed, therefore step 2 must also re-run."

The returned `first_changed_idx` is intended to enable cascade but is never consumed by the runner.

---

## 4. Engine-Specific Recipes

### 4.1 QE Recipe

**File**: `drivers/qe/recipe.py`

```python
class QERecipe(BaseRecipe):
    def materialize(self, steps, calc_raw_dir, step_shas):
        for idx, step in enumerate(steps):
            job = Job(
                id=f"step_{idx:02d}",
                step_ulids=[step.meta.ulid],
                working_dir=calc_raw_dir,          # SHARED directory
                command=[executable, f"{gen_type}.in"],
                deps=[],                           # NO explicit deps
                metadata={"engine": "qe", ...},
            )
```

- One job per step
- All jobs share the same working directory (`calc/raw/`)
- No explicit dependencies (`deps=[]`)
- Steps are "independently runnable" — each reads from shared `outdir/` scratch (QE's internal state management)
- Independence is implicit: scf writes wavefunctions to outdir; bandspw reads them from there
- **No dependency declaration means the recipe doesn't know that bands depends on bandspw**

### 4.2 ORCA Recipe

**File**: `drivers/orca/recipe.py`

```python
class ORCARecipe(BaseRecipe):
    def materialize(self, steps, calc_raw_dir, step_shas):
        for target_idx, target_step in enumerate(steps):
            subchain_steps = steps[:target_idx + 1]  # SCF root to target
            job = Job(
                id=basename,                       # e.g., "s_m2"
                step_ulids=[s.meta.ulid for s in subchain_steps],
                working_dir=calc_raw_dir / namespace_folder,
                deps=[],                           # Self-contained subchains
                fingerprint=compute_job_fingerprint([shas]),
            )
```

- One job per **subchain** (SCF root → target)
- Each subchain re-executes all steps from SCF
- Self-contained: `deps=[]`
- Multi-step fingerprint: hash of ALL step SHAs in the subchain
- If SCF's step_sha changes, ALL subchain fingerprints change → all re-run
- **The strong-chain model naturally handles cascade** because any upstream change affects the subchain fingerprint

### 4.3 VASP Recipe

**File**: `drivers/vasp/recipe.py`

```python
class VASPRecipe(BaseRecipe):
    def materialize(self, steps, calc_raw_dir, step_shas):
        for step in steps:
            job = Job(
                id=step.meta.ulid,
                working_dir=calc_raw_dir / step.meta.ulid,  # ISOLATED per step
                deps=[jobs[-1].id] if jobs else [],          # LINEAR deps
            )
```

- One job per step (like QE)
- **Isolated working directories** per step
- **Linear dependencies**: each step depends on the previous one
- Dependencies exist for future parallel execution scheduling (currently unused by executor)

### 4.4 LAMMPS Recipe

**File**: `drivers/lammps/recipe.py`

Same pattern as VASP: isolated workdirs, linear deps, plus explicit `restart_from` artifact deps.

### 4.5 PySCF Recipe

**File**: `drivers/pyscf/recipe.py`

Same pattern as ORCA (QC weak-chain): subchain jobs, `command=["<internal>"]`, self-contained.

### 4.6 Recipe Impact on Skip Logic

**Recipes do NOT declare step dependencies that the skip logic uses.** The `deps` field exists on Job but the executor does NOT consult it for skip decisions. Skip logic is purely manifest-based: check each job's steps against their manifest entries.

For ORCA/PySCF, cascade is naturally handled because subchain jobs include all upstream steps — if any step's SHA changes, the combined fingerprint changes. For QE/VASP/LAMMPS (one job per step), there is NO inter-job dependency in the skip logic.

---

## 5. Bug Analysis: Si Bands Incremental Skip

### 5.1 Scenario

1. Agent creates Si bands calculation with 3 steps: scf (step 0), bandspw (step 1), bands (step 2)
2. Runs full calculation — all 3 steps execute successfully
3. Manifest after first run:
   ```json
   {"steps": [
     {"kind": "scf",     "step_sha": "aaa...", "done": true},
     {"kind": "bandspw", "step_sha": "bbb...", "done": true},
     {"kind": "bands",   "step_sha": "ccc...", "done": true}
   ]}
   ```
4. Agent changes bandspw parameters (adds `nbnd=8`) via `set_parameters`
5. This modifies `bandspw.step.yaml` → `step_sha` changes from `"bbb..."` to `"bbb2..."`
6. Agent runs calculation again (incremental, the only mode MCP exposes)

### 5.2 Exact Code Path Trace

**Phase 1: Reconcile Manifest** (`manifest_reconcile.py`)

The reconciler evaluates each step independently:

- **Step 0 (scf, i=0)**: old entry exists, kind matches, SHAs all match (scf wasn't modified), `actually_done=True` → keeps `done=True`
- **Step 1 (bandspw, i=1)**: old entry exists, kind matches, `step_sha` MISMATCH (`"bbb..." != "bbb2..."`) → creates new entry with `done=False`. Sets `first_changed_idx=1`.
- **Step 2 (bands, i=2)**: old entry exists, kind matches, ALL SHAs match (bands.step.yaml was NOT modified), `actually_done=True` → keeps `done=True`

Reconciled manifest:
```json
{"steps": [
  {"kind": "scf",     "step_sha": "aaa...", "done": true},
  {"kind": "bandspw", "step_sha": "bbb2..","done": false},
  {"kind": "bands",   "step_sha": "ccc...", "done": true}
]}
```

`first_changed_idx=1` is returned to the runner, which logs it and discards it.

**Phase 2: Build JobGraph** (`QERecipe.materialize()`)

Three jobs created: `step_00` (scf), `step_01` (bandspw), `step_02` (bands). All `deps=[]`.

**Phase 3: Execute** (`executor.execute()`)

- **Job step_00 (scf)**: `_should_skip_job()` → manifest entry has `done=True`, `step_sha` matches → **SKIP** ✓
- **Job step_01 (bandspw)**: `_should_skip_job()` → manifest entry has `done=False` → **EXECUTE** ✓
  - After execution: `update_manifest_step()` sets entry to `done=True` with new SHA
- **Job step_02 (bands)**: `_should_skip_job()` → manifest entry has `done=True`, `step_sha` matches current → **SKIP** ✗ BUG

### 5.3 Root Cause

The root cause is the **absence of cascade invalidation** in both:

1. **`reconcile_manifest()`**: Evaluates each step independently. When step 1 (bandspw) is marked `done=False` because its SHA changed, step 2 (bands) is still evaluated on its own SHAs. Since bands.step.yaml wasn't modified, its SHAs match, and it stays `done=True`.

2. **`executor._should_skip_job()`**: Evaluates each job independently. Does not track "which jobs actually ran in this execution" to force downstream jobs to also run.

3. **`first_changed_idx`**: Computed by reconcile_manifest, returned to runner, but **never used**. It was designed to be the cascade trigger — "start execution from this index" — but was never wired in.

4. **`clear_manifest_from_step()`**: Written specifically for cascade invalidation. Sets `done=False` for all steps from a given index onward. **Dead code** — never called from any runner path.

The bug is NOT in SHA computation (bands.step.yaml SHA is correctly computed — it didn't change). The bug is NOT in should_skip_step. The bug is the total absence of cascade: **when an upstream step re-runs, downstream steps are not invalidated.**

### 5.4 Why the Bug is Specific to QE-Style Recipes

ORCA/PySCF recipes are NOT affected because:
- Each downstream job (subchain) includes ALL upstream steps in its `step_ulids`
- The job fingerprint is computed from ALL step SHAs in the subchain
- If the SCF step_sha changes, ALL subchain fingerprints change → all re-run

QE/VASP/LAMMPS recipes ARE affected because:
- Each job covers exactly ONE step
- The job's fingerprint is just that one step's SHA
- No inter-job dependency tracking

### 5.5 What SHOULD Happen

Per Constitution §5.3 and engineering intent:

When bandspw (step 1) is determined to need re-running (its SHA changed), ALL downstream steps (bands at step 2, and any subsequent steps) should be marked `done=False` in the manifest. This ensures the executor naturally re-runs them.

The mechanism should be: **cascade in `reconcile_manifest()`** — once `first_changed_idx` is set, force `done=False` for all steps at and after that index.

---

## 6. MCP Integration

### 6.1 Current Exposure

The `run_calculation` MCP tool (`mcp/tools/run_calculation.py:10`) accepts ONLY:
- `calc_ulid: str`

It does NOT expose:
- `run_mode` — hardcoded to `"incremental"` (via service layer default)
- `target_step_ulid` — not passed at all
- `steps` — not passed

The service layer `run_calculation()` (`api/service.py:6262`) calls `runner.run(calculation, run_ulid=run_ulid, run_mode=run_mode)` with `run_mode="incremental"` by default and no `target_step_ulid`.

### 6.2 Missing Controls

| Parameter | Available in Kernel | Exposed in MCP | Impact |
|-----------|-------------------|----------------|--------|
| `run_mode` | Yes (`"incremental"` / `"full"`) | No | Agent cannot force full re-run |
| `target_step_ulid` | Yes | No | Agent cannot run single step |
| `steps` | Yes (service layer) | No | Agent cannot select subset |

### 6.3 Workarounds

An agent hit by the cascade bug has no workaround via MCP:
- Cannot force `run_mode="full"` (would re-run scf unnecessarily)
- Cannot use `run_step` (not exposed as MCP tool)
- Only option: delete the manifest file manually (not exposed)

---

## 7. Proposed Fix

### 7.1 Primary Fix: Cascade in `reconcile_manifest()`

**Location**: `calculation/manifest_reconcile.py`

**Change**: After the main loop, add a cascade pass. If `first_changed_idx < len(steps)`, force `done=False` for all entries from `first_changed_idx` onward.

This is the minimal, correct fix because:
- It's in the reconciliation phase, before execution
- It affects ALL run modes (incremental, full) uniformly
- It's consistent with how kind mismatch is already handled (comment at line 215: "from this index onward, create fresh entries with done=false" — but the code doesn't actually cascade)
- It uses existing infrastructure
- It does NOT require changes to the executor

**Conceptual diff** (after the main loop, before saving):
```python
# Cascade: if any step changed, force all downstream steps to done=False
if first_changed_idx < len(new_steps):
    for i in range(first_changed_idx, len(new_steps)):
        if new_steps[i].done:
            new_steps[i].done = False
            new_steps[i].done_at = None
```

### 7.2 Secondary Fix: Wire `clear_manifest_from_step()` for Run Step Mode

**Location**: `calculation/runner.py:_execute_with_jobgraph()` (after line 573)

For TARGET mode (Run Step), after successful target step execution, call `clear_manifest_from_step()` to invalidate downstream steps. This implements Constitution §5.3.

### 7.3 Tertiary Fix: Expose `run_mode` in MCP

**Location**: `mcp/tools/run_calculation.py`

Add optional `run_mode` parameter (default `"incremental"`). Pass through to service layer. This gives agents the ability to force full re-runs when needed.

### 7.4 Impact Analysis

| Engine Type | Fix 7.1 Impact |
|-------------|---------------|
| QE (directory-state) | Fixed: cascade invalidates downstream steps |
| VASP (isolated-workdir) | Fixed: same cascade |
| LAMMPS (isolated-workdir) | Fixed: same cascade |
| ORCA (strong-chain) | No change: subchain fingerprints already handle cascade |
| PySCF (weak-chain) | No change: same as ORCA |
| All 10 others | Fixed: all use QE-style recipe (1 job per step) |

The fix is safe for all engines. For ORCA/PySCF, the reconciler may redundantly mark subchain steps as `done=False`, but this is harmless since the subchain job would re-run anyway due to fingerprint mismatch.

---

## 8. Source File Index

| File | Role |
|------|------|
| `src/qmatsuite/calculation/runner.py` (790 lines) | Main runner: `CalculationRunner.run()` orchestrates reconciliation, SHA computation, JobGraph execution |
| `src/qmatsuite/execution/executor.py` (732 lines) | `JobExecutor.execute()`: iterates jobs, skip logic, handler dispatch |
| `src/qmatsuite/calculation/manifest.py` (327 lines) | Manifest data model, load/save, `should_skip_step()`, `clear_manifest_from_step()` (dead) |
| `src/qmatsuite/calculation/manifest_reconcile.py` (262 lines) | `reconcile_manifest()`: aligns manifest to topology, per-step SHA comparison |
| `src/qmatsuite/calculation/hash_utils.py` (449 lines) | SHA computation: `compute_step_sha()`, `compute_structure_sha()`, `compute_pseudo_set_sha()` |
| `src/qmatsuite/execution/recipes.py` (225 lines) | `BaseRecipe`, `Recipe` protocol, `get_recipe_for_engine()` factory |
| `src/qmatsuite/execution/job_graph.py` (204 lines) | `Job`, `JobGraph`, `SelectionMode`, `compute_job_fingerprint()` |
| `src/qmatsuite/drivers/qe/recipe.py` (109 lines) | QE recipe: 1 job/step, shared workdir, no deps |
| `src/qmatsuite/drivers/orca/recipe.py` (137 lines) | ORCA recipe: subchain jobs, self-contained |
| `src/qmatsuite/drivers/vasp/recipe.py` (121 lines) | VASP recipe: 1 job/step, isolated workdirs, linear deps |
| `src/qmatsuite/drivers/lammps/recipe.py` (155 lines) | LAMMPS recipe: isolated workdirs, restart_from deps |
| `src/qmatsuite/drivers/pyscf/recipe.py` (137 lines) | PySCF recipe: weak-chain subchains |
| `src/qmatsuite/calculation/step_done.py` (246 lines) | `is_step_done()`: engine-specific completion detection (JOB DONE, OUTCAR, log.lammps) |
| `src/qmatsuite/mcp/tools/run_calculation.py` (187 lines) | MCP tool: only exposes `calc_ulid`, no `run_mode` or `target_step_ulid` |
| `src/qmatsuite/api/service.py:6197-6302` | Service layer: `run_calculation()` bridges MCP to kernel |
| `src/qmatsuite/api/service.py:6304-6340` | Service layer: `run_step()` (not exposed in MCP) |
| `CONSTITUTION.md:105-123` | §5 Incremental Run Manifest: skip rules, run modes, cascade mandate |

---

## 9. Corrections to Previous Review (SI_BANDS_ISSUES_REVIEW.md)

The previous review (M1) correctly identified that `clear_manifest_from_step()` is not called. However, it:

1. **Underestimated the scope**: Described the fix as "~5 lines in runner.py." The actual fix should be in `reconcile_manifest()`, not the runner, because the cascade must fire for ALL run modes (incremental Run Calc, not just Run Step). The M1 fix would only help TARGET mode.

2. **Misidentified the fix location**: Proposed adding `clear_manifest_from_step()` call after target step execution. While this is needed for Run Step mode (§5.3 compliance), the primary bug (Run Calc incremental skipping bands after bandspw re-runs) requires cascade in the reconciler.

3. **Missed that `first_changed_idx` is dead**: The reconciler already computes `first_changed_idx` and returns it, but the runner discards it. The infrastructure for cascade exists in three places — `first_changed_idx`, `clear_manifest_from_step()`, and `start_idx` — but none are wired together.

4. **Correctly identified** that the skip logic works per-step and that the MCP tool doesn't expose `run_mode`. These findings are confirmed.
