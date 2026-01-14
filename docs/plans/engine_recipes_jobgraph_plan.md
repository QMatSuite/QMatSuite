# Engine Recipes + JobGraph Generalization Plan

**Date**: 2026-01-13
**Status**: DESIGN PHASE
**Scope**: Generalize execution planning to support multiple engine families without rewriting bespoke runners

---

## 0. Why We Are Doing This

We want to add more engines soon (VASP, ABINIT, Psi4, potentially others) without re-writing bespoke runners for each. We will generalize execution in a minimal way that preserves existing filesystem contracts and tests.

**What We Will NOT Do:**
- Broad rewrite of existing engines
- Change QE, Wannier, ORCA, or PySCF behavior
- Add new locks or change lock semantics
- Create redundant state or violate single-source-of-truth

**What We WILL Do:**
- Extract common execution planning into a minimal JobGraph abstraction
- Define THREE engine recipes (QE-Recipe, ORCA-Recipe, PySCF-Recipe)
- Implement a general runner that executes JobGraphs
- Preserve all existing filesystem contracts and test behavior

---

## 1. As-Is Evidence Map (Current Implementation)

### A. Current Execution Flow

**File**: `src/quantumvitas/calculation/runner.py`
- **Class**: `CalculationRunner`
- **Method**: `run(calculation, skip_history, run_id, run_mode)`
- **Flow**:
  1. Acquire calc_run_lock (outermost, long-held)
  2. Step0: Prepare pseudos in project/pseudo (line 113-167)
  3. Manifest reconciliation for incremental mode (line 172-265)
  4. Loop over steps (line 268-658):
     - Skip if before start_idx and manifest says done (line 269-345)
     - Update manifest: started_at, done=false, run_id (line 370-432)
     - Resolve engine from step YAML machine step_type (line 435-461)
     - Create per-step artifact directory (line 469-479)
     - Call `step.run(engine, calculation_raw_dir, project_root, species_map)` (line 493-520)
     - Evaluate result (line 559-586)
     - Update manifest: done=true/false, done_at (line 623-646)
  5. History recording (lines 683-856)

**Key Observation**: Runner is engine-agnostic at the orchestration level. Engine-specific logic happens in `step.run()` and the engine itself.

### B. Current Manifest System

**File**: `src/quantumvitas/calculation/manifest.py`
- **Storage**: `calc/.run_tmp_info/manifest.json`
- **Schema**: `ManifestStepEntry`
  - `kind` (str): Step type (e.g., "scf", "nscf")
  - `step_ulid` (str): ULID for traceability
  - `pseudo_set_sha` (str): SHA256 of pseudo set
  - `structure_sha` (str): SHA256 of structure
  - `step_sha` (str): SHA256 of step YAML
  - `run_id` (Optional[str]): Last attempted run ID
  - `done` (bool): Whether step is completed
  - `started_at` (Optional[str]): ISO8601 timestamp
  - `done_at` (Optional[str]): ISO8601 timestamp when done==true
- **Skip Logic** (`should_skip_step`, line 272-316):
  - Skip if: kind matches AND all 3 SHAs match AND done==true
- **Persistence**: Atomic save via temp file + rename (line 122-158)

**Key Observation**: Manifest is the single source of truth for run tracking. No redundant state.

### C. Current Lock Implementation

**File**: `src/quantumvitas/core/locking.py`
- **Two Locks**:
  1. `calc_run_lock(calc_dir, fail_fast)` (line 54-109):
     - Long-held during entire calculation run (materialization + execution)
     - Lock file: `calc/.locks/run.lock`
     - Enforces "at most one run per calc at a time"
  2. `calc_edit_lock(calc_dir, fail_fast)` (line 112-194):
     - Short-held during YAML file writes (< 100ms typically)
     - Lock file: `calc/.locks/edit.lock`
     - Non-reentrant with thread-local tracking to prevent deadlocks
- **Lock Order**: calc_run_lock outermost; calc_edit_lock may occur inside when writing manifests/YAMLs
- **No Additional Locks Needed**: calc_run_lock prevents concurrent writes to raw/ within a calc

**Key Observation**: Lock semantics are minimal and complete. DO NOT add more locks.

### D. Current Engine Filesystem Contracts

#### QE (Quantum ESPRESSO)

**Engine File**: `src/quantumvitas/engine/qe_engine.py`, `src/quantumvitas/core/engines/qe.py`

**Filesystem Contract**:
- **Scratch Directory**: `calc/raw/outdir` (hardcoded QE convention)
- **Evidence**: QE input files reference `outdir='./outdir'` in control namelist
- **Step Execution**: Each step (scf, nscf, bands, dos, ph) runs in `calc/raw/` with shared `outdir/` scratch
- **Reuse**: QE steps read/write to shared `outdir/` for wavefunction files, charge density, etc.
- **"Done" Criteria**: Process exit code 0 + output file parsing (convergence messages)
- **Code Reference**: `src/quantumvitas/core/engines/qe_calculation.py:147` (run_step method)

**Current Behavior**:
- Working directory = `calc/raw/`
- QE binary invoked with: `<qe_executable> < input.in > output.out 2> error.err`
- stdout/stderr captured to: `<step_type>.out`, `<step_type>.err` (overwritten, not versioned)
- Input files may be versioned (e.g., scf.in, scf-1.in), but outputs are always latest

#### Wannier90

**Engine File**: Integrated with QE engine (step types: `w90_preproc`, `pw2wannier90`, `w90_run`)

**Filesystem Contract**:
- **Scratch Directory**: `calc/raw/` (in-place execution)
- **Evidence**: `src/quantumvitas/core/engines/qe_calculation.py:298-308`
  - `w90_preproc`: primary artifact is `<seed>.wout`, stdout captured to `w90_preproc.out`
  - `pw2wannier90`: primary output is `pw2wannier90.out` (stdout capture)
  - `w90_run`: primary artifact is `<seed>.wout`, stdout captured to `w90_run.out`
- **Reuse**: Wannier90 reads `.mmn`, `.amn`, `.eig` files written by `pw2wannier90` in same directory
- **"Done" Criteria**: Exit code 0 + `.wout` file parsing for convergence

**Current Behavior**:
- Working directory = `calc/raw/`
- Wannier90 executables run in-place, no separate scratch subdirectory
- Files like `<seed>.win`, `<seed>.wout`, `<seed>.amn`, `<seed>.mmn`, `<seed>.eig` all in `raw/`

#### ORCA (Strong-Chain Model)

**Engine File**: `src/quantumvitas/engine/orca_engine.py`

**Filesystem Contract**:
- **Namespace Folders**: `calc/raw/scf_<scf_ulid_suffix>/` (per SCF-root chain)
- **Canonical Orbitals File**: `scf.gbw` (immutable name, used for MORead reuse)
- **Evidence**: `docs/architecture/ORCA_INTEGRATION_SPEC.md` (v2.0, created earlier in session)
  - Subchain basenames: `s`, `s_m2`, `s_t`, `s_m2_n` (based on stable tokens)
  - Input/output files: `<basename>.inp`, `<basename>.out`, `<basename>.property.txt`
  - Inputs versioned (never overwritten), outputs/artifacts overwritten (latest only)
- **Reuse**: Non-SCF subchains add `MORead` keyword + `%moinp "scf.gbw"` to input (line 70-75 of input_compiler.py)
- **"Done" Criteria**: Exit code 0 + `.property.txt` file parsing (SCF_Energy, TDDFT_Excitation_Energies)
- **Code Reference**: `src/quantumvitas/engines/orca/input_compiler.py:30-88` (compile method), `src/quantumvitas/engine/orca_engine.py:128-271` (run_chain method)

**Current Behavior**:
- Each chain executes as ONE ORCA job (strong-chain model)
- Working directory = `calc/raw/scf_<suffix>/`
- ORCA binary invoked with: `orca <basename>.inp > <basename>.out 2>&1`
- All steps in a chain fused into single input file

#### PySCF (Weak-Chain / Session Model)

**Engine File**: `src/quantumvitas/engines/pyscf/runner.py`

**Filesystem Contract**:
- **Namespace Folders**: `calc/raw/scf_<scf_ulid_suffix>/` (same as ORCA)
- **Per-Step Artifacts**: Each step writes to `calc/raw/step_artifacts/<step_ulid>/`
- **Evidence**:
  - `src/quantumvitas/engines/pyscf/runner.py:637-731` (run_job_chain function)
  - `src/quantumvitas/engines/pyscf/chain_execution.py` (run_chain_session - not shown but referenced)
- **Checkpoint File**: `checkpoint.chk` for SCF wavefunction (line 244-253 in runner.py)
- **Reuse**: MP2 loads checkpoint from previous SCF step (line 505-576)
- **"Done" Criteria**: `success==True` in results.json + convergence flag
- **Code Reference**: `src/quantumvitas/engines/pyscf/runner.py:181-392` (run_scf), `478-634` (run_mp2)

**Current Behavior**:
- Chain execution in one Python subprocess (weak-chain / session model)
- Working directory = `calc/raw/scf_<suffix>/`
- PySCF runner invoked with: `python -m quantumvitas.engines.pyscf.runner job_chain.json`
- Results written to `<step_artifacts_dir>/results.json` for each step

### E. How "Done" is Decided Today

**QE Steps**:
- File: `src/quantumvitas/calculation/verification.py` (evaluate_step_result)
- Criteria: Exit code 0 + output parsing for convergence messages (e.g., "convergence achieved", "JOB DONE")
- Reference output comparison (if provided)

**ORCA Steps**:
- File: `src/quantumvitas/engines/orca/property_parser.py`
- Criteria: Exit code 0 + `.property.txt` parsing for energy values
- Convergence check via is_converged() function

**PySCF Steps**:
- File: `src/quantumvitas/engines/pyscf/runner.py`
- Criteria: `converged==True` field in results.json + `success==True`

**Wannier90 Steps**:
- File: `src/quantumvitas/calculation/verification.py`
- Criteria: Exit code 0 + `.wout` parsing for "All done" messages

### F. Three Execution Entrypoints (Project-Based and Standalone)

#### F.1. Project-Based Run Calc (Run Full Calculation)

**API Entrypoint**: `src/quantumvitas/api.py:1146` (`QVService.run_calculation()`)

**Flow**:
1. Acquire calc_run_lock (fail-fast if already locked)
2. Load calculation and materialize steps
3. Call `CalculationRunner.run(calculation, run_id, run_mode)` (line ~1268)
4. Runner uses manifest reconciliation to determine `start_idx`
5. Runs all steps from `start_idx` to end (incremental skip for steps before start_idx)

**Selection Semantics**:
- `run_mode="incremental"` (default): Skip steps before start_idx if manifest says done + SHAs match
- `run_mode="full"`: Mark all manifest entries as done=false, run all steps from step0
- Both modes run from start_idx to END (no target selection)

**Key Observation**: Run Calc is a prefix selection (run from start_idx to end).

#### F.2. Project-Based Run Step (Run to Target Step)

**API Entrypoint**: `src/quantumvitas/api.py:1319` (`QVService.run_step()`)

**Current Implementation** (AS-IS):
- **SEPARATE pipeline from Run Calc** (NOT a selection mode of CalculationRunner)
- Engine-specific routing:
  - **PySCF** (line 1419): Calls `resolve_dependency_chain(target_step_ulid)`, then `engine.run_step_with_chain()`
  - **QE/W90** (line 1514): Generates input for target step, calls `run_input_step()` (single step execution)
- No incremental skip logic (always regenerates input and runs)
- No manifest updates for intermediate steps in dependency chain

**Gap in Current Design**:
- Run Step is implemented as separate logic per engine, NOT unified with CalculationRunner
- No shared incremental skip logic
- PySCF uses dependency resolution, but QE/W90 path only runs the single target step (ignores deps)

**Target Design** (THIS PLAN):
- **Unify Run Step into the same runner pipeline as Run Calc**
- Run Step becomes a SELECTION MODE: runner uses target_step_id to select which jobs to execute
- One runner entrypoint; selection determines which steps/jobs to execute
- Manifest-based skip logic applies to ALL steps in the dependency chain (incremental)
- "Target step must always run" rule: target step is forced to execute even if upstream can be skipped

**Selection Semantics (MVP)**:
- Conservative prefix-to-target selection: run all steps from step0 (or SCF root for QC) to target
- This is SAFE but not minimal (true deps would allow skipping independent branches)
- Document as "conservative / safe", not as "true deps"
- Future: Engine-provided upstream requirements can enable true minimal deps

#### F.3. Standalone Step Execution (OUT OF SCOPE for This Plan)

**File**: `src/quantumvitas/calculation/standalone.py`

**Function**: `run_standalone_step(ctx: StandaloneStepContext)`

**Purpose**: Run QE steps without a project context (standalone input files)

**Behavior**:
- Reads QE input file, parses it, generates normalized version
- Runs QE on generated input (roundtrip: parse → generate → run)
- Used for testing, debugging, or non-project workflows

**OUT OF SCOPE**: This plan does NOT touch standalone execution. It remains independent from project-based run logic.

---

## 2. Proposed Minimal JobGraph Interface

### Design Principles

1. **Runtime-Only**: JobGraph is NOT persisted. It is materialized at run time from calculation steps and engine recipe.
2. **Single Source of Truth**:
   - Manifest is the only persisted run-tracking truth
   - Step YAMLs are the only persisted step truth
   - JobGraph is derived from these sources, never stored
3. **Minimal Fields**: Avoid redundant/derived state. If something can be derived, DO NOT store it twice.
4. **Stable Identifiers**: Use step ULIDs and stable tokens (already in repo) for job IDs. DO NOT leak long ULIDs into filenames.

### Job Structure

```python
@dataclass
class Job:
    """
    A Job represents a single unit of execution.

    For QE-Recipe: Job = one executable invocation (one step)
    For ORCA-Recipe: Job = one subchain execution (SCF root → target step)
    For PySCF-Recipe: Job = one chain_session execution (SCF root → target step)
    """

    # Identity
    id: str  # Derived from step order or stable tokens (e.g., "s_m2", "step_01")
    step_ids: List[str]  # List of step ULIDs covered by this job

    # Execution
    working_dir: Path  # Where this job runs (engine-specific, see recipes)
    command: List[str]  # Command to execute (or ["<internal>"] for session-based)

    # Inputs/Outputs (minimal)
    input_files: List[Path]  # Input files this job reads (for reference, not staging)
    expected_outputs: List[Path]  # Expected output files (for "done" check)

    # Dependencies
    deps: List[str]  # List of job IDs this job depends on (DAG edges)

    # Fingerprint (incremental skip)
    fingerprint: Optional[str] = None  # SHA256 of (step_sha, structure_sha, pseudo_set_sha) for all steps in this job

    # Engine-specific metadata (opaque to runner)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Key Decisions**:
- `id`: For QE, `"step_{i:02d}"`. For ORCA/PySCF, stable token path (e.g., `"s_m2"`).
- `step_ids`: List of step ULIDs. For QE (one step per job), this is `[step.meta.id]`. For ORCA/PySCF (chain), this is `[scf_root.id, ..., target_step.id]`.
- `deps`: List of job IDs. For QE, `deps = [prev_step_job_id]` (linear chain). For ORCA/PySCF, `deps = []` (self-contained subchain).
- `fingerprint`: Computed from step_sha + structure_sha + pseudo_set_sha for all steps in this job. Used for incremental skip.
- `expected_outputs`: Minimal list. For QE, `[<step_type>.out]`. For ORCA, `[<basename>.out, <basename>.property.txt, scf.gbw]`. For PySCF, `[results.json, checkpoint.chk]`.

### JobGraph Structure

```python
@dataclass
class JobGraph:
    """
    Runtime-only DAG of jobs for a calculation.

    JobGraph is materialized from calculation steps + engine recipe.
    NOT persisted. Derived each run.
    """

    jobs: List[Job]  # List of jobs in execution order (topologically sorted)

    # Derived methods (NOT stored)
    def get_job(self, job_id: str) -> Optional[Job]: ...
    def get_dependencies(self, job_id: str) -> List[Job]: ...
    def get_subgraph_to_target(self, target_step_id: str) -> "JobGraph": ...
```

**Key Decisions**:
- `jobs`: Stored as a topologically sorted list (NOT both "deps dict" + "topo list"). The topo-sort happens once during materialization.
- `get_subgraph_to_target`: For Run Step mode, extract the minimal subgraph needed to satisfy target_step_id.

### Fingerprint Concept

**Purpose**: Incremental skip logic (already exists in manifest)

**Current Manifest** (3 SHAs):
- `pseudo_set_sha`: SHA256 of pseudo set
- `structure_sha`: SHA256 of structure JSON
- `step_sha`: SHA256 of step YAML

**Proposed Job Fingerprint**:
- For single-step jobs (QE-Recipe): `fingerprint = step_sha` (pseudo_set_sha and structure_sha are same for all steps in a calc)
- For multi-step jobs (ORCA/PySCF): `fingerprint = hash([step_sha_1, step_sha_2, ..., step_sha_n])` (all steps in the job)

**Where Checked**:
- Runner compares `job.fingerprint` with manifest entries for all steps in `job.step_ids`
- If ALL steps have matching fingerprints AND done==true, skip the job
- Otherwise, run the job

**Single Source of Truth** (CRITICAL):
- **Manifest remains the ONLY persisted run-tracking truth**
- **JobGraph is runtime-only** (NOT persisted, derived each run)
- **Fingerprint is runtime-only**: computed on-the-fly from manifest SHAs, never stored
- Runner compares job.fingerprint with manifest SHAs to decide skip/run
- NO second source of truth: JobGraph does NOT become a persisted artifact

---

## 3. The Three Recipes (Engine Materialization Policies)

### Recipe 1: QE-Recipe (Directory-State, Step-Run)

**Philosophy**:
- Shared scratch/run directory within raw (engine-owned constant)
- Job = one executable invocation (one step)
- Steps share state via scratch_dir files

**Materialization Rules**:
- **One Job Per Step**: Each calculation step becomes one Job
- **Job ID**: `"step_{i:02d}"` (e.g., `"step_00"`, `"step_01"`)
- **Working Directory**: `calc/raw/` for ALL jobs
- **Scratch Directory**: `calc/raw/outdir/` (QE-specific, hardcoded)
- **Dependencies**: Linear chain: `job_i.deps = [job_{i-1}.id]` (except first job)
- **Command**: `[<qe_executable>, "<input_file>"]` (with stdin redirection)
- **Expected Outputs**: `[<step_type>.out]` (stdout capture file)
- **Fingerprint**: `step_sha` for the single step

**Example JobGraph (QE: SCF → NSCF → Bands)**:

```python
JobGraph(jobs=[
    Job(
        id="step_00",
        step_ids=["scf_step_ulid"],
        working_dir=Path("calc/raw"),
        command=["pw.x", "scf.in"],
        input_files=[Path("calc/raw/scf.in")],
        expected_outputs=[Path("calc/raw/scf.out")],
        deps=[],
        fingerprint="<scf_step_sha>",
        metadata={"scratch_dir": Path("calc/raw/outdir"), "step_type": "scf"},
    ),
    Job(
        id="step_01",
        step_ids=["nscf_step_ulid"],
        working_dir=Path("calc/raw"),
        command=["pw.x", "nscf.in"],
        input_files=[Path("calc/raw/nscf.in")],
        expected_outputs=[Path("calc/raw/nscf.out")],
        deps=["step_00"],  # Depends on SCF wavefunction in outdir/
        fingerprint="<nscf_step_sha>",
        metadata={"scratch_dir": Path("calc/raw/outdir"), "step_type": "nscf"},
    ),
    Job(
        id="step_02",
        step_ids=["bands_step_ulid"],
        working_dir=Path("calc/raw"),
        command=["bands.x", "bands.in"],
        input_files=[Path("calc/raw/bands.in")],
        expected_outputs=[Path("calc/raw/bands.out")],
        deps=["step_01"],  # Depends on NSCF outputs in outdir/
        fingerprint="<bands_step_sha>",
        metadata={"scratch_dir": Path("calc/raw/outdir"), "step_type": "bands"},
    ),
])
```

**"Done" Marker**:
- Engine-specific: Check exit code 0 + parse `<step_type>.out` for convergence
- Manifest entry: `done==true` AND fingerprint matches

**Run Step Mapping**:
- For target step `"nscf"`:
  - Subgraph = `[step_00, step_01]` (SCF + NSCF)
  - Skip `step_00` if manifest says done + fingerprint matches
  - Run `step_01` (target always runs per spec)

**Engines Using This Recipe**:
- **QE** (current)
- **Wannier90** (variant: in-place, no separate scratch_dir subdirectory, but same contract: `calc/raw/` working dir)
- **Future VASP**: `scratch_dir = calc/raw/vasp_outdir/` (NOT shared with QE)
- **Future ABINIT**: `scratch_dir = calc/raw/abinit_outdir/`

### Recipe 2: ORCA-Recipe (QC Strong-Chain)

**Philosophy**:
- Work happens under namespace folder: `calc/raw/scf_<suffix>/`
- Job granularity = subchain execution (SCF root → target step)
- Reuse via canonical file (scf.gbw) + MORead (no copying/linking)

**Materialization Rules**:
- **One Job Per Subchain**: For each QC step, create a job representing the subchain from SCF root to that step
- **Job ID**: Stable token path (e.g., `"s"` for SCF-only, `"s_m2"` for SCF+MP2, `"s_t"` for SCF+TD)
- **Working Directory**: `calc/raw/scf_<scf_ulid_suffix>/` (namespace folder)
- **Scratch Directory**: Same as working_dir (no separate scratch concept)
- **Dependencies**: No inter-job deps (each job is self-contained: runs full subchain)
- **Command**: `["orca", "<basename>.inp"]` (where basename = job_id like `"s_m2"`)
- **Expected Outputs**: `[<basename>.out, <basename>.property.txt, scf.gbw]`
- **Fingerprint**: `hash([scf_step_sha, ..., target_step_sha])` (all steps in subchain)
- **Reuse**: Non-SCF subchains include `MORead` + `%moinp "scf.gbw"` in input (compiler handles this)

**Example JobGraph (ORCA: SCF + MP2 + TD)**:

```python
JobGraph(jobs=[
    Job(
        id="s",  # SCF-only subchain
        step_ids=["scf_step_ulid"],
        working_dir=Path("calc/raw/scf_KR5DQ9"),
        command=["orca", "s.inp"],
        input_files=[Path("calc/raw/scf_KR5DQ9/s.inp")],
        expected_outputs=[Path("calc/raw/scf_KR5DQ9/s.out"), Path("calc/raw/scf_KR5DQ9/scf.gbw")],
        deps=[],
        fingerprint="<scf_step_sha>",
        metadata={"subchain_basename": "s", "chain_key": "scf_KR5DQ9"},
    ),
    Job(
        id="s_m2",  # SCF+MP2 subchain
        step_ids=["scf_step_ulid", "mp2_step_ulid"],
        working_dir=Path("calc/raw/scf_KR5DQ9"),
        command=["orca", "s_m2.inp"],
        input_files=[Path("calc/raw/scf_KR5DQ9/s_m2.inp")],
        expected_outputs=[Path("calc/raw/scf_KR5DQ9/s_m2.out"), Path("calc/raw/scf_KR5DQ9/scf.gbw")],
        deps=[],  # No deps: job runs full subchain internally
        fingerprint="<hash([scf_step_sha, mp2_step_sha])>",
        metadata={"subchain_basename": "s_m2", "moread_file": "scf.gbw"},
    ),
    Job(
        id="s_t",  # SCF+TD subchain
        step_ids=["scf_step_ulid", "td_step_ulid"],
        working_dir=Path("calc/raw/scf_KR5DQ9"),
        command=["orca", "s_t.inp"],
        input_files=[Path("calc/raw/scf_KR5DQ9/s_t.inp")],
        expected_outputs=[Path("calc/raw/scf_KR5DQ9/s_t.out"), Path("calc/raw/scf_KR5DQ9/scf.gbw")],
        deps=[],
        fingerprint="<hash([scf_step_sha, td_step_sha])>",
        metadata={"subchain_basename": "s_t", "moread_file": "scf.gbw"},
    ),
])
```

**"Done" Marker**:
- Check: All expected_outputs exist + parse `.property.txt` for energy values
- Manifest: ALL steps in `job.step_ids` have `done==true` AND fingerprints match

**Run Step Mapping**:
- For target step `"mp2"`:
  - Subgraph = `[s_m2]` (one job covering SCF+MP2)
  - Skip if BOTH scf and mp2 manifest entries say done + fingerprints match
  - Otherwise, run `s_m2` job (reruns SCF+MP2 as one ORCA invocation)

**Engines Using This Recipe**:
- **ORCA** (current)

### Recipe 3: PySCF-Recipe (QC Weak-Chain / Session)

**Philosophy**:
- Still QC chain semantics (namespace folder: `calc/raw/scf_<suffix>/`)
- Session-based execution (one Python subprocess runs full subchain)
- Artifacts are per-step (in `step_artifacts/<step_ulid>/`)

**Materialization Rules**:
- **One Job Per Subchain** (similar to ORCA-Recipe)
- **Job ID**: Stable token path (e.g., `"s_m2"`)
- **Working Directory**: `calc/raw/scf_<scf_ulid_suffix>/`
- **Scratch Directory**: Same as working_dir
- **Dependencies**: No inter-job deps (self-contained session)
- **Command**: `["<internal>"]` (special marker: Python subprocess, not external binary)
- **Expected Outputs**: `[step_artifacts/<step_ulid>/results.json, checkpoint.chk]` for each step
- **Fingerprint**: `hash([scf_step_sha, ..., target_step_sha])`
- **Reuse**: Checkpoint file (`checkpoint.chk`) for wavefunction reuse between steps in same session

**Example JobGraph (PySCF: SCF + MP2)**:

```python
JobGraph(jobs=[
    Job(
        id="s",  # SCF-only subchain
        step_ids=["scf_step_ulid"],
        working_dir=Path("calc/raw/scf_KR5DQ9"),
        command=["<internal>"],  # Special: PySCF runner subprocess
        input_files=[],  # Job spec passed via job_chain.json
        expected_outputs=[
            Path("calc/raw/step_artifacts/scf_step_ulid/results.json"),
            Path("calc/raw/scf_KR5DQ9/checkpoint.chk"),
        ],
        deps=[],
        fingerprint="<scf_step_sha>",
        metadata={"chain_spec": {...}, "target_step_ulid": "scf_step_ulid"},
    ),
    Job(
        id="s_m2",  # SCF+MP2 subchain
        step_ids=["scf_step_ulid", "mp2_step_ulid"],
        working_dir=Path("calc/raw/scf_KR5DQ9"),
        command=["<internal>"],
        input_files=[],
        expected_outputs=[
            Path("calc/raw/step_artifacts/scf_step_ulid/results.json"),
            Path("calc/raw/step_artifacts/mp2_step_ulid/results.json"),
            Path("calc/raw/scf_KR5DQ9/checkpoint.chk"),
        ],
        deps=[],
        fingerprint="<hash([scf_step_sha, mp2_step_sha])>",
        metadata={"chain_spec": {...}, "target_step_ulid": "mp2_step_ulid"},
    ),
])
```

**"Done" Marker**:
- Check: All `results.json` files exist + `success==true` in each
- Manifest: ALL steps in `job.step_ids` have `done==true` AND fingerprints match

**Run Step Mapping**:
- For target step `"mp2"`:
  - Subgraph = `[s_m2]` (one session covering SCF+MP2)
  - Skip if BOTH scf and mp2 manifest entries say done + fingerprints match
  - Otherwise, run `s_m2` session (reruns SCF+MP2 in one Python subprocess)

**Engines Using This Recipe**:
- **PySCF** (current)

---

## 4. Future Engines: Sanity Check Fit

### VASP (Vienna Ab initio Simulation Package)

**Execution Model** (based on public knowledge):
- **CLI Invocation**: `vasp` (reads from fixed filenames: INCAR, POSCAR, POTCAR, KPOINTS)
- **Input Files**: INCAR (parameters), POSCAR (structure), POTCAR (pseudopotentials), KPOINTS (k-point mesh)
- **Scratch Directory**: No separate scratch concept; works in-place with fixed filenames
- **Sequential Calculations**: SCF → NSCF (bands/DOS) done by running VASP multiple times in same directory with different INCAR settings
- **"Done" Criteria**: OUTCAR file parsing for "reached required accuracy" or "writing wavefunctions"

**Fit into QE-Recipe**:
- **Recipe**: QE-Recipe (directory-state, step-run)
- **Working Directory**: `calc/raw/`
- **Scratch Directory**: `calc/raw/vasp_outdir/` (NOT shared with QE outdir)
  - VASP writes WAVECAR, CHGCAR, etc. to working_dir, so `scratch_dir = working_dir` for VASP
- **Job Granularity**: One job per VASP invocation (one step)
- **Dependencies**: Linear chain (NSCF depends on SCF wavefunction in WAVECAR)
- **Reuse**: WAVECAR file for wavefunction reuse between steps

**Note**: VASP uses fixed filenames (INCAR, POSCAR, etc.), so input versioning requires copying inputs to `<step_type>-N.INCAR` before each run if versioning is needed. Outputs like OUTCAR can be moved to `<step_type>.OUTCAR` after each run.

### ABINIT

**Execution Model** (based on public knowledge):
- **CLI Invocation**: `abinit < input.files` (where input.files lists the main input file, output file, pseudopotentials, etc.)
- **Input Files**: Main input file (e.g., `ab.in`) with namelists/datasets
- **Multi-Dataset**: ABINIT supports multiple datasets in one input file (e.g., dataset 1 = SCF, dataset 2 = NSCF)
- **Scratch Directory**: Works in working directory; may write temporary files to `$TMPDIR` if set
- **Sequential Calculations**: Can do SCF + NSCF in one run (multi-dataset) OR separate runs
- **"Done" Criteria**: Output file parsing for "Calculation completed" or energy convergence messages

**Fit into QE-Recipe**:
- **Recipe**: QE-Recipe (directory-state, step-run)
- **Working Directory**: `calc/raw/`
- **Scratch Directory**: `calc/raw/abinit_outdir/` (if ABINIT uses scratch files) OR `calc/raw/` (if in-place like Wannier)
- **Job Granularity**: One job per ABINIT invocation (could be one dataset or entire multi-dataset run)
- **Dependencies**: Linear chain (NSCF dataset depends on SCF density/wavefunction files)
- **Reuse**: Density files (e.g., `*_DEN`) for wavefunction reuse

**Note**: ABINIT's multi-dataset feature allows combining multiple calculations in one input file, similar to ORCA's chain fusion. However, for QMatSuite, we may prefer separate invocations per step for better incremental support.

### Psi4 (Quantum Chemistry)

**Execution Model** (based on public knowledge and Psi4 docs):
- **CLI Invocation**: `psi4 input.dat output.dat` (input file, output file)
- **Input Files**: Python-like input script (e.g., `molecule { ... } energy('scf')`)
- **Scratch Directory**: Uses `PSI_SCRATCH` env var for temporary files (e.g., integrals, intermediate results)
- **Single-Invocation**: Typically one Psi4 call per calculation (SCF, MP2, CCSD, etc.)
- **Chaining**: Can define multiple calculations in one input script (e.g., `scf_e = energy('scf')` then `mp2_e = energy('mp2')`)
- **"Done" Criteria**: Exit code 0 + output parsing for "Psi4 exiting successfully" or final energy

**Fit into QE-Recipe** (or potential ORCA-like if chaining):
- **Recipe**: QE-Recipe (step-run) for separate calculations, OR ORCA-Recipe (chain fusion) if using Psi4's script chaining
- **Working Directory**: `calc/raw/` (QE-Recipe) OR `calc/raw/psi4_<job_id>/` (ORCA-like)
- **Scratch Directory**: `$PSI_SCRATCH` (env var, e.g., `/tmp/psi4_scratch` or `calc/raw/psi4_scratch/`)
- **Job Granularity**: One job per Psi4 invocation
- **Dependencies**: Linear chain if separate invocations (MP2 depends on SCF wavefunction file)
- **Reuse**: Wavefunction file (e.g., `<name>.180`) for reuse

**Recommendation**: Start with QE-Recipe (one invocation per step) for simplicity. Later, explore ORCA-Recipe (chain fusion) if Psi4 script chaining provides benefits.

---

## 5. Phased Refactor Plan (Checkbox-Driven, Test-Driven)

### Non-Goals

- **Do NOT change QE raw/outdir contract**: `calc/raw/outdir/` must remain the QE scratch directory
- **Do NOT change ORCA/PySCF namespace contracts**: `calc/raw/scf_<suffix>/` must remain as-is
- **Do NOT add more locks**: Two locks (calc_run_lock, calc_edit_lock) are sufficient
- **Do NOT implement VASP/ABINIT/Psi4 engines yet**: This plan only lays the groundwork
- **Do NOT change existing tests**: All 130+ tests must remain green incrementally

### Phase 0: Preparation (Evidence Gathering - DONE)

- [x] Read and document current runner.py implementation
- [x] Read and document manifest.py implementation
- [x] Read and document locking.py implementation
- [x] Read and document QE, ORCA, PySCF engine filesystem contracts
- [x] Identify how "done" is decided for each engine
- [x] Document how Run Step should work (currently NOT implemented)

### Phase 1: JobGraph Interface (Code-Only, No Behavior Change)

**Goal**: Introduce JobGraph dataclasses WITHOUT changing any execution behavior.

#### Tasks

- [ ] **P1.1**: Create `src/quantumvitas/execution/job_graph.py` module
  - [ ] Define `Job` dataclass (see Section 2)
  - [ ] Define `JobGraph` dataclass with helper methods
  - [ ] Add utility: `compute_job_fingerprint(step_shas: List[str]) -> str`
- [ ] **P1.2**: Create `src/quantumvitas/execution/recipes.py` module
  - [ ] Define `Recipe` protocol: `materialize_job_graph(calculation) -> JobGraph`
  - [ ] Implement `QERecipe.materialize_job_graph()` (QE-style: one job per step)
  - [ ] Implement `ORCARecipe.materialize_job_graph()` (ORCA-style: one job per subchain)
  - [ ] Implement `PySCFRecipe.materialize_job_graph()` (PySCF-style: one session job per subchain)
- [ ] **P1.3**: Add tests for JobGraph materialization (unit tests, NO execution)
  - [ ] Test QE recipe: 3-step calc (scf, nscf, bands) → 3 jobs
  - [ ] Test ORCA recipe: 3-step QC calc (scf, mp2, td) → 3 jobs (s, s_m2, s_t)
  - [ ] Test PySCF recipe: 2-step QC calc (scf, mp2) → 2 jobs (s, s_m2)
  - [ ] Verify job IDs, deps, fingerprints, working_dirs

#### Commands

```bash
# Create new modules
touch src/quantumvitas/execution/__init__.py
touch src/quantumvitas/execution/job_graph.py
touch src/quantumvitas/execution/recipes.py
touch tests/unit/execution/__init__.py
touch tests/unit/execution/test_job_graph.py
touch tests/unit/execution/test_recipes.py

# Run unit tests
pytest tests/unit/execution/ -v

# Expected: ~10-15 new tests pass, no existing tests broken
```

#### Acceptance Criteria

- [ ] JobGraph dataclasses exist and are well-documented
- [ ] Three recipe implementations exist and can materialize JobGraphs from test calculations
- [ ] Unit tests verify JobGraph structure (jobs, deps, fingerprints) without running engines
- [ ] NO behavior change: existing runner.py still works, all 130 tests still green

### Phase 2: JobGraph Runner (Parallel Execution Path)

**Goal**: Implement a JobGraphRunner that executes JobGraphs, running IN PARALLEL with existing runner.py (no replacement yet).

#### Tasks

- [ ] **P2.1**: Create `src/quantumvitas/execution/job_graph_runner.py` module
  - [ ] Define `JobGraphRunner` class with `run(job_graph, calc, run_id, run_mode) -> CalculationResult`
  - [ ] Implement job execution loop:
    - [ ] For each job in job_graph.jobs (topo-sorted order):
      - [ ] Check manifest: skip if all steps in job.step_ids have done==true + fingerprints match
      - [ ] Otherwise: execute job
      - [ ] Update manifest for each step in job.step_ids
  - [ ] Delegate actual execution to engine-specific handlers:
    - [ ] For QE jobs: call `_execute_qe_job(job)` → uses existing qe_engine.run_step()
    - [ ] For ORCA jobs: call `_execute_orca_job(job)` → uses existing orca_engine.run_chain()
    - [ ] For PySCF jobs: call `_execute_pyscf_job(job)` → uses existing pyscf subprocess runner
- [ ] **P2.2**: Implement Run Step mode in JobGraphRunner
  - [ ] Add method: `run_step(job_graph, calc, target_step_id, run_id) -> CalculationResult`
  - [ ] Logic:
    - [ ] Find target step in calculation.steps
    - [ ] Use `job_graph.get_subgraph_to_target(target_step_id)` to extract minimal subgraph
    - [ ] Run subgraph jobs (skip if done, otherwise execute)
    - [ ] Target step job ALWAYS runs (per spec: "target step must always run")
- [ ] **P2.3**: Add integration tests using JobGraphRunner (NOT replacing runner.py yet)
  - [ ] Test QE execution via JobGraphRunner: scf → nscf → bands (verify outputs match runner.py)
  - [ ] Test ORCA execution via JobGraphRunner: scf + td (verify outputs match existing ORCA tests)
  - [ ] Test PySCF execution via JobGraphRunner: scf + mp2 (verify outputs match existing PySCF tests)
  - [ ] Test Run Step mode: QE nscf as target (verify scf runs first if needed, nscf always runs)

#### Commands

```bash
# Create new module
touch src/quantumvitas/execution/job_graph_runner.py
touch tests/integration/execution/__init__.py
touch tests/integration/execution/test_job_graph_runner_qe.py
touch tests/integration/execution/test_job_graph_runner_orca.py
touch tests/integration/execution/test_job_graph_runner_pyscf.py

# Run integration tests
pytest tests/integration/execution/ -v -m integration

# Expected: ~15-20 new integration tests pass
# NO existing tests broken (runner.py still used by old tests)
```

#### Acceptance Criteria

- [ ] JobGraphRunner can execute JobGraphs for QE, ORCA, PySCF
- [ ] Run Step mode works: can run minimal subgraph to satisfy target step
- [ ] Integration tests verify outputs match existing engine behavior
- [ ] Manifest updates correctly for all job types
- [ ] NO behavior change to existing runner.py: all 130 tests still green

### Phase 3: Migrate runner.py to JobGraphRunner

**Goal**: Replace runner.py execution logic with JobGraphRunner, preserving all behavior.

#### Tasks

- [ ] **P3.1**: Refactor `runner.py` to use JobGraphRunner internally
  - [ ] In `CalculationRunner.run()`:
    - [ ] Detect engine family from first step (qe, orca, pyscf)
    - [ ] Select appropriate Recipe (QERecipe, ORCARecipe, PySCFRecipe)
    - [ ] Materialize JobGraph: `job_graph = recipe.materialize_job_graph(calculation)`
    - [ ] Delegate to JobGraphRunner: `job_graph_runner.run(job_graph, calculation, run_id, run_mode)`
  - [ ] Keep all existing logic:
    - [ ] Step0 pseudo preparation (before JobGraph)
    - [ ] Manifest reconciliation (JobGraphRunner uses manifest)
    - [ ] History recording (after JobGraph execution)
- [ ] **P3.2**: Implement Run Step mode in runner.py
  - [ ] Add parameter: `run(calculation, target_step_id: Optional[str] = None)`
  - [ ] If `target_step_id` provided:
    - [ ] Use `job_graph_runner.run_step(job_graph, calculation, target_step_id, run_id)`
  - [ ] Else:
    - [ ] Use `job_graph_runner.run(job_graph, calculation, run_id, run_mode)` (full calc)
- [ ] **P3.3**: Run ALL existing tests (130+ tests)
  - [ ] QE unit tests (should still pass)
  - [ ] ORCA unit tests (should still pass)
  - [ ] PySCF integration tests (should still pass)
  - [ ] QE integration tests (should still pass)
  - [ ] Wannier90 tests (should still pass)
- [ ] **P3.4**: Add Run Step tests to existing test suite
  - [ ] Test QE Run Step: run only NSCF (verify SCF runs first if needed, NSCF always runs)
  - [ ] Test ORCA Run Step: run only TD (verify SCF+TD subchain runs)
  - [ ] Test PySCF Run Step: run only MP2 (verify SCF+MP2 session runs)

#### Commands

```bash
# Modify runner.py
# (Use Edit tool, not shown here)

# Run ALL tests
pytest tests/ -v

# Expected: ALL 130+ tests pass + ~5-10 new Run Step tests
```

#### Acceptance Criteria

- [ ] runner.py uses JobGraphRunner internally
- [ ] Run Step mode implemented and tested
- [ ] ALL existing tests pass (no regressions)
- [ ] New Run Step tests pass
- [ ] Behavior identical to before refactor (verified by test pass rate)

### Phase 4: Documentation and Cleanup

**Goal**: Document the new architecture and clean up any dead code.

#### Tasks

- [ ] **P4.1**: Update ORCA_INTEGRATION_SPEC.md
  - [ ] Add section: "JobGraph Execution Model"
  - [ ] Document how ORCA recipe materializes jobs
  - [ ] Document Run Step behavior for ORCA
- [ ] **P4.2**: Create ENGINE_RECIPES.md in docs/architecture/
  - [ ] Document the three recipes (QE, ORCA, PySCF)
  - [ ] Provide examples of JobGraph materialization for each recipe
  - [ ] Document how to add a new engine (choose recipe, implement materialization)
- [ ] **P4.3**: Update README or docs/guides/ with Run Step usage
  - [ ] CLI: How to run a specific step (when CLI supports it)
  - [ ] API: How to call `runner.run(calculation, target_step_id="nscf")`
- [ ] **P4.4**: Remove dead code (if any)
  - [ ] Check for unused functions in old runner.py
  - [ ] Check for duplicate logic between runner.py and job_graph_runner.py
- [ ] **P4.5**: Code review and cleanup
  - [ ] Review JobGraph implementation for simplicity
  - [ ] Review Recipe implementations for correctness
  - [ ] Ensure no redundant state (single source of truth verified)

#### Commands

```bash
# Create/update docs
touch docs/architecture/ENGINE_RECIPES.md

# Review code
# (Manual code review)

# Final test run
pytest tests/ -v --tb=short

# Expected: ALL tests pass, docs complete
```

#### Acceptance Criteria

- [ ] ENGINE_RECIPES.md exists and is comprehensive
- [ ] ORCA_INTEGRATION_SPEC.md updated with JobGraph section
- [ ] No dead code remains
- [ ] Code review complete, no major issues
- [ ] ALL tests pass (130+ existing + ~20-30 new tests)

---

## 6. Risks, Non-Goals, and Open Questions

### Risks

1. **Risk**: JobGraph materialization logic becomes too complex for engines with unusual dependencies
   - **Mitigation**: Start with the three recipes (QE, ORCA, PySCF) which cover the main patterns. Add new recipes only when a new engine doesn't fit.

2. **Risk**: Fingerprint logic for multi-step jobs (ORCA/PySCF) may have edge cases
   - **Mitigation**: Comprehensive unit tests for fingerprint computation. Verify against manifest SHAs.

3. **Risk**: Run Step mode may not handle all edge cases (e.g., orphan steps, missing SCF root)
   - **Mitigation**: Document error cases clearly. Raise clear error messages. Test error cases.

4. **Risk**: Parallel execution (not in scope) may require job-level locking
   - **Mitigation**: NOT in scope for this plan. Current calc_run_lock prevents parallel runs within a calc. Cross-calc parallelism is already safe.

### Non-Goals

1. **NOT implementing parallel job execution** (within a calc): Jobs run sequentially as before
2. **NOT implementing job-level caching** beyond existing manifest: Manifest is sufficient
3. **NOT implementing job retry logic**: If a job fails, the calc fails (as before)
4. **NOT implementing VASP/ABINIT/Psi4 engines**: This plan only lays the groundwork
5. **NOT changing lock semantics**: Two locks (calc_run_lock, calc_edit_lock) remain as-is

### Open Questions (Not Blocking, Document for Future)

1. **Q**: Should we support DAG-based dependencies (non-linear) in JobGraph?
   - **A**: Not needed for current engines (QE is linear, ORCA/PySCF are self-contained subchains). Add only when a future engine needs it.

2. **Q**: How to handle multi-job parallelism (e.g., run multiple independent QE steps at once)?
   - **A**: Out of scope for MVP. Current sequential execution is correct and simple. Parallel execution requires careful coordination and is a future optimization.

3. **Q**: Should Job.fingerprint be SHA256 or something faster (e.g., xxHash)?
   - **A**: SHA256 is fine for now (already used in manifest). Optimize only if profiling shows it's a bottleneck.

4. **Q**: How to handle engines that don't fit the three recipes (e.g., multi-stage MD workflows)?
   - **A**: Add a new recipe. Recipes are extensible. Document the new pattern in ENGINE_RECIPES.md.

---

## 7. Test Strategy

### Test Categories

1. **Unit Tests** (fast, no engines):
   - JobGraph materialization (recipes)
   - Fingerprint computation
   - JobGraph helper methods (get_job, get_dependencies, get_subgraph_to_target)

2. **Integration Tests** (require engines):
   - JobGraphRunner execution for QE, ORCA, PySCF
   - Run Step mode for QE, ORCA, PySCF
   - Incremental skip logic (manifest + fingerprints)

3. **Regression Tests** (existing tests):
   - ALL 130+ existing tests must pass after each phase
   - No behavior change until Phase 3

### Test Commands Summary

```bash
# Phase 1: Unit tests only
pytest tests/unit/execution/ -v
# Expected: ~10-15 new tests pass

# Phase 2: Integration tests
pytest tests/integration/execution/ -v -m integration
# Expected: ~15-20 new tests pass

# Phase 3: ALL tests (regression + new)
pytest tests/ -v
# Expected: 150-160 tests pass (130 existing + 20-30 new)

# Phase 4: Final verification
pytest tests/ -v --tb=short
# Expected: ALL tests pass, no regressions
```

---

## 8. Summary

This plan introduces a minimal JobGraph abstraction and three engine recipes (QE, ORCA, PySCF) to generalize execution planning without changing existing behavior. The phased approach ensures tests remain green incrementally, preserving filesystem contracts and lock semantics. Run Step mode is implemented as a natural extension of JobGraph subgraph extraction. Future engines (VASP, ABINIT, Psi4) will fit into one of the three recipes or motivate a new recipe with a clear pattern.

**Single Source of Truth Preserved**:
- Manifest remains the only persisted run-tracking truth
- Step YAMLs remain the only persisted step truth
- JobGraph is runtime-only, derived from these sources

**Lock Semantics Preserved**:
- Exactly two locks: calc_run_lock (outermost), calc_edit_lock (inside)
- No additional locks needed
- Lock order prevents deadlocks

**Filesystem Contracts Preserved**:
- QE: `calc/raw/outdir/` (unchanged)
- Wannier90: `calc/raw/` (unchanged)
- ORCA: `calc/raw/scf_<suffix>/` (unchanged)
- PySCF: `calc/raw/scf_<suffix>/` + `step_artifacts/<step_ulid>/` (unchanged)

**End of Plan**
