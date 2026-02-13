# QMatSuite Repository State Analysis for ORCA Integration

**Date**: 2026-01-12
**Status**: Analysis Complete
**Goal**: Document current PySCF integration, generalized step infrastructure, and core architecture for ORCA integration planning

---

## 1. Executive Summary

This document provides a comprehensive analysis of QMatSuite's current architecture as it relates to ORCA integration. The analysis covers:

1. **PySCF Integration Pattern**: How PySCF is currently integrated (execution flow, artifacts, step modeling, presets)
2. **Core Architecture Explanation**: Resource model, DAG semantics, preset/IR system, step taxonomy
3. **Generalized vs Specialized Steps**: How public step types map to engine-specific machine types
4. **Chain Execution Semantics**: Current implementation and deviations from target chain semantics

---

## 2. Constitution Key Invariants (Non-negotiable)

From `CONSTITUTION_ZH.md`, the following invariants **MUST** be respected:

### 2.1 Single Source of Truth
- **step.yaml** is the ONLY executable truth
- Persisted step.yaml **MUST** contain `machine step_type` registered in `StepTypeRegistry`
- Generalized steps, IR, preset results exist ONLY at runtime/UI/history

### 2.2 Session-Chain Engine Semantics (PySCF/ORCA)
```
Constitution §14.1: Session-chain engines
- Steps execute in single memory session, forming state chain
- run-step MUST replay entire chain from nearest dependency source
- ONLY chain start step consumes structure
- Subsequent steps consume ONLY runtime state (mf, mp2, ccsd), NOT structure directly
```

### 2.3 Intermediate State Non-Persistence
```
Constitution §14.3: Intermediate state CANNOT be persisted
- PySCF/ORCA have NO general intermediate state bridging mechanism
- MP2/CCSD/TD/EOM objects exist ONLY in runtime memory
- They are NOT artifacts, NOT serializable for reuse
- SCF checkpoint is the ONLY exception (initial guess only)
```

### 2.4 Preset/Compiler/Detector Contract
```
Constitution §10.3-10.6:
- Compiler: pure function (step_type, options) → parameters
- Detector B: UNIQUE source for preset state detection from params
- Mathematical equivalence: detect(compile(options)) == options
- ParamSpace: declarative data structure for preset dimensions
```

### 2.5 Step Type Registry Authority
```
Constitution §13.2:
- StepTypeRegistry is the ONLY authority for step_type validation
- machine step_type in step.yaml MUST be registry-known
- Execution phase MUST resolve engine from step.yaml machine step_type
- engine_family is ONLY for materialization-time selection
```

---

## 3. Current PySCF Integration Analysis

### 3.1 Key Files and Components

| Component | File Path | Purpose |
|-----------|-----------|---------|
| PySCF Engine Adapter | `src/quantumvitas/engine/pyscf_engine.py` | Subprocess-based engine, never imports PySCF in daemon |
| PySCF Runner | `src/quantumvitas/engines/pyscf/runner.py` | Entry point for subprocess execution |
| Chain Execution | `src/quantumvitas/engines/pyscf/chain_execution.py` | One-session dependency chain execution (Phase 3C) |
| Step Registry | `src/quantumvitas/workflow/registry.py` | Step type definitions with `StepTypeSpec` |
| Generalized Steps | `src/quantumvitas/workflow/generalized_steps.py` | Engine-agnostic step mapping |
| Calculation Runner | `src/quantumvitas/calculation/runner.py` | Orchestrates step execution |

### 3.2 PySCF Engine Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ CalculationRunner.run()                                              │
│    │                                                                 │
│    ▼                                                                 │
│ EngineRegistry.get("pyscf") → PySCFEngine                           │
│    │                                                                 │
│    ▼                                                                 │
│ PySCFEngine.run_step() or PySCFEngine.run_chain()                   │
│    │                                                                 │
│    ▼                                                                 │
│ subprocess: python -m quantumvitas.engines.pyscf job.json           │
│    │                                                                 │
│    ▼                                                                 │
│ Runner (runner.py) → imports PySCF, executes calculation            │
│    │                                                                 │
│    ▼                                                                 │
│ Artifacts: results.json, checkpoint.chk, stdout.txt                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 Key Implementation Details

**From `pyscf_engine.py` (lines 1-100):**
```python
class PySCFEngine(Engine):
    """
    PySCF engine using subprocess isolation.

    NEVER imports PySCF directly - all execution happens in subprocess.
    This ensures daemon process doesn't load PySCF's heavy dependencies.
    """

    def probe(self) -> Tuple[bool, str]:
        # Uses subprocess to check PySCF availability
        # Returns (available, version_or_error)

    def run_step(self, step, working_dir, ...) -> StepResult:
        # Creates job.json with step parameters
        # Launches subprocess: [python, -m, quantumvitas.engines.pyscf, job.json]
        # Reads results.json for structured output

    def run_chain(self, steps, working_dir, ...) -> List[StepResult]:
        # Phase 3C: Execute multiple steps in one PySCF session
        # Uses chain_execution.py for in-memory state passing
```

**From `chain_execution.py` (lines 1-100):**
```python
def run_chain_session(
    steps: List[StepConfig],
    project_root: Path,
    working_dir: Path,
    structure_id: str,
    run_mode: str,
) -> List[StepResult]:
    """
    Execute dependency chain in ONE PySCF session.

    State objects (mol, mf) maintained in-memory between steps.
    Only SCF produces 'mf' state; downstream steps consume it.
    Target step ALWAYS fully reruns (no init_guess from chkfile).
    """

    state_storage = {}  # Holds 'mf' object between steps

    for step in steps:
        # Clear step artifacts before execution
        # Execute step with state from previous steps
        # Store produced state (e.g., 'mf' from SCF)
```

### 3.4 Step Type Registry Structure

**From `registry.py` (lines 1-150):**
```python
@dataclass
class StepTypeSpec:
    """Step type specification in registry."""
    machine_type: str          # e.g., "pyscf_scf", "qe_scf"
    public_type: str           # e.g., "scf", "mp2"
    engine: str                # e.g., "pyscf", "qe"
    executable: Optional[str]  # e.g., "pw.x" for QE
    description: str
    supports_incremental_skip: bool = False
    consumes_state: Optional[str] = None   # e.g., "mf" for MP2
    produces_state: Optional[str] = None   # e.g., "mf" for SCF

# Registry entries (Phase 3C additions)
_STEP_TYPES = {
    "pyscf_scf": StepTypeSpec(
        machine_type="pyscf_scf",
        public_type="scf",
        engine="pyscf",
        executable=None,
        description="PySCF SCF calculation",
        supports_incremental_skip=True,
        consumes_state=None,      # SCF consumes structure, not state
        produces_state="mf",      # SCF produces mean-field object
    ),
    "pyscf_mp2": StepTypeSpec(
        machine_type="pyscf_mp2",
        public_type="mp2",
        engine="pyscf",
        executable=None,
        description="PySCF MP2 calculation",
        supports_incremental_skip=False,
        consumes_state="mf",      # MP2 consumes SCF result
        produces_state="mp2",     # MP2 produces MP2 object (runtime only)
    ),
    "pyscf_td": StepTypeSpec(
        machine_type="pyscf_td",
        public_type="td",
        engine="pyscf",
        executable=None,
        description="PySCF TDDFT calculation",
        supports_incremental_skip=False,
        consumes_state="mf",      # TD consumes SCF result
        produces_state=None,      # TD does not produce reusable state
    ),
    # ... more step types
}
```

### 3.5 Generalized Step Materialization

**From `generalized_steps.py` (lines 1-100):**
```python
class GeneralizedStep(Enum):
    """Engine-agnostic step types for workflow definition."""
    SCF = "scf"
    NSCF = "nscf"
    RELAX = "relax"
    VC_RELAX = "vc_relax"
    BANDS = "bands"
    DOS = "dos"
    MP2 = "mp2"
    TD = "td"
    CCSD = "ccsd"
    # ...

# Materialization mapping: (engine_family, generalized_step) → machine_step_type
MATERIALIZATION_MAP = {
    ("pyscf", GeneralizedStep.SCF): "pyscf_scf",
    ("pyscf", GeneralizedStep.MP2): "pyscf_mp2",
    ("pyscf", GeneralizedStep.TD): "pyscf_td",
    ("qe", GeneralizedStep.SCF): "qe_scf",
    ("qe", GeneralizedStep.NSCF): "qe_nscf",
    # ...
}

def materialize_step(engine_family: str, generalized_step: GeneralizedStep) -> str:
    """Convert generalized step to engine-specific machine step_type."""
    key = (engine_family, generalized_step)
    if key not in MATERIALIZATION_MAP:
        raise ValueError(f"No materialization for {engine_family}/{generalized_step}")
    return MATERIALIZATION_MAP[key]
```

---

## 4. Core Architecture Explanation

### 4.1 Resource Model (Project/Calc/Step)

```
┌─────────────────────────────────────────────────────────────────────┐
│ PROJECT                                                              │
│ ├── project.qv.yml (project root marker + config)                   │
│ ├── structures/                                                      │
│ │   └── {structure_ulid}/structure.yaml                             │
│ ├── pseudo/ (pseudopotentials, populated at runtime)                │
│ └── calculations/                                                    │
│     └── {calc_ulid}/                                                │
│         ├── calculation.yaml                                        │
│         ├── steps/                                                   │
│         │   └── {step_ulid}/step.yaml                               │
│         └── raw/ (I/O directory for execution)                      │
│             ├── step_artifacts/{step_ulid}/                         │
│             │   ├── results.json                                    │
│             │   ├── checkpoint.chk (SCF only)                       │
│             │   └── stdout.txt                                      │
│             └── manifest.yaml (incremental run tracking)            │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 ULID + Manifest + Artifact Registry

**ULID Generation** (`src/quantumvitas/core/resources.py`):
```python
def generate_resource_id() -> str:
    """Generate ULID for resource identification."""
    return str(ulid.new())
```

**Manifest System** (`src/quantumvitas/calculation/manifest.py`):
```yaml
# manifest.yaml structure
steps:
  - step_ulid: "01HX..."
    kind: "pyscf_scf"
    pseudo_set_sha: "abc123..."
    structure_sha: "def456..."
    step_sha: "ghi789..."
    done: true
    run_id: "01HY..."
    started_at: "2026-01-12T10:00:00Z"
    done_at: "2026-01-12T10:05:00Z"
```

**Artifact Contract** (per engine):
| Engine | Input Artifact | Output Artifacts | Seed Artifacts |
|--------|----------------|------------------|----------------|
| QE | `{step_type}.in` | `{step_type}.out`, `{step_type}.err` | `outdir/data-file-schema.xml` |
| PySCF | `job.json` | `results.json`, `stdout.txt` | `checkpoint.chk` (SCF only) |
| ORCA (proposed) | `{step_slug}.inp` | `{step_slug}.out`, `{step_slug}.err` | `{step_slug}.gbw` |

### 4.3 Preset IR and Compilation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ PRESET SYSTEM FLOW                                                   │
│                                                                      │
│ User Selection (UI)                                                  │
│       │                                                              │
│       ▼                                                              │
│ ┌─────────────────┐                                                  │
│ │ options: Dict   │ e.g., {precision: "high", magnetism: "collinear"}│
│ └────────┬────────┘                                                  │
│          │                                                           │
│          ▼ Compiler (pure function)                                  │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ compile_one(step_type, options) → parameters                     │ │
│ │                                                                   │ │
│ │ For each dimension in options:                                    │ │
│ │   - Look up ParamSpace for dimension                             │ │
│ │   - Get profile (row) for selected option                        │ │
│ │   - Write keys with VALUE cells to parameters                    │ │
│ │   - Remove keys with NOT_APPLICABLE cells                        │ │
│ └────────┬────────────────────────────────────────────────────────┘ │
│          │                                                           │
│          ▼                                                           │
│ ┌─────────────────┐                                                  │
│ │ step.yaml       │ Contains only parameters (no preset metadata)   │
│ │ parameters:     │                                                  │
│ │   ecutwfc: 60   │                                                  │
│ │   nspin: 2      │                                                  │
│ └────────┬────────┘                                                  │
│          │                                                           │
│          ▼ Detector B (pure function, reverse of compiler)          │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ detect(step.yaml parameters) → options                           │ │
│ │                                                                   │ │
│ │ For each dimension:                                               │ │
│ │   - Read keys from parameters                                     │ │
│ │   - Canonicalize values (aliases, tolerances)                    │ │
│ │   - Match against ParamSpace profiles                            │ │
│ │   - Return matched option or "custom"                            │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ INVARIANT: detect(compile(options)) == options                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.4 Generalized vs Specialized Steps

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP TYPE HIERARCHY                                                  │
│                                                                      │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ PUBLIC (Generalized) Step Types                                  │ │
│ │ - Exist in: UI, workflow templates, history                     │ │
│ │ - Examples: "scf", "mp2", "td", "freq"                          │ │
│ │ - NOT persisted in step.yaml                                    │ │
│ └────────┬────────────────────────────────────────────────────────┘ │
│          │                                                           │
│          │ materialize_step(engine_family, generalized_step)        │
│          │ (happens at step creation time only)                     │
│          ▼                                                           │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ MACHINE Step Types (Engine-specific)                             │ │
│ │ - Persisted in: step.yaml (SINGLE SOURCE OF TRUTH)              │ │
│ │ - Examples: "pyscf_scf", "qe_scf", "orca_dft_scf"               │ │
│ │ - MUST be registered in StepTypeRegistry                        │ │
│ └────────┬────────────────────────────────────────────────────────┘ │
│          │                                                           │
│          │ resolve_engine_for_step(step_yaml_path)                  │
│          │ (happens at execution time)                               │
│          ▼                                                           │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ Engine Dispatch                                                  │ │
│ │ - Reads machine step_type from step.yaml                        │ │
│ │ - Looks up StepTypeRegistry → engine name                       │ │
│ │ - Gets engine from EngineRegistry                               │ │
│ │ - NO fallback to "custom" or engine_family at this stage        │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.5 Workflow Templates and Steps

**From `templates.py`:**
```python
@dataclass
class WorkflowTemplate:
    """Workflow definition with step sequence."""
    id: str
    name: str
    description: str
    step_sequence: Tuple[str, ...]  # PUBLIC step keys
    optional_steps: Tuple[str, ...] = ()

# Built-in templates
WORKFLOW_TEMPLATES = {
    "scf": WorkflowTemplate(
        id="scf",
        name="SCF Single Point",
        description="Single-point SCF calculation",
        step_sequence=("scf",),
    ),
    "scf_td": WorkflowTemplate(
        id="scf_td",
        name="SCF + TDDFT",
        description="SCF followed by TDDFT excited states",
        step_sequence=("scf", "td"),
    ),
    "scf_mp2": WorkflowTemplate(
        id="scf_mp2",
        name="SCF + MP2",
        description="SCF followed by MP2 correlation",
        step_sequence=("scf", "mp2"),
    ),
    # ...
}
```

### 4.6 Job Manager / History Pipeline

**From `daemon/jobs.py`:**
```python
class JobManager:
    """Manages background job execution."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1)  # Sequential
        self._jobs: Dict[str, Job] = {}

    def submit(self, job_type, calc_id, ...) -> str:
        """Submit job for background execution."""
        job_id = str(ulid.new())
        job = Job(id=job_id, job_type=job_type, status=JobStatus.PENDING, ...)
        self._jobs[job_id] = job
        self._executor.submit(self._run_job, job)
        return job_id
```

**History Recording** (`calculation/runner.py:684-858`):
- Creates `RunRevision` with step IDs, types, structure, engine info
- Records `RunStartedEvent` and `RunFinishedEvent`
- Stores step results with status, metrics, working directory

---

## 5. Current Chain Execution Analysis

### 5.1 How PySCF Chain Execution Works

**From `chain_execution.py`:**
```python
def run_chain_session(steps, project_root, working_dir, structure_id, run_mode):
    """
    Execute dependency chain in ONE PySCF session.

    Key behaviors:
    1. Import PySCF once (not per-step)
    2. Maintain in-memory objects (mol, mf) between steps
    3. State storage for 'mf' object (mean-field from SCF)
    4. Target step always fully reruns (no init_guess from chkfile)
    5. Clear step artifacts before execution
    """

    # Resolve structure
    structure_path = resolve_structure(project_root, structure_id)

    # Create PySCF mol object
    from pyscf import gto
    mol = gto.M(atom=..., basis=..., charge=..., spin=...)

    state_storage = {}  # Holds runtime state between steps
    results = []

    for step in steps:
        step_type = step["step_type"]
        step_id = step["step_id"]

        # Clear artifacts directory
        artifacts_dir = working_dir / "step_artifacts" / step_id
        clear_directory(artifacts_dir)

        if step_type == "pyscf_scf":
            # SCF: consumes mol, produces mf
            mf = run_scf(mol, step["parameters"])
            state_storage["mf"] = mf
            write_results(artifacts_dir, mf)

        elif step_type == "pyscf_mp2":
            # MP2: consumes mf, produces mp2 object (runtime only)
            mf = state_storage.get("mf")
            if mf is None:
                raise RuntimeError("MP2 requires SCF to run first")
            mp2_result = run_mp2(mf, step["parameters"])
            write_results(artifacts_dir, mp2_result)

        elif step_type == "pyscf_td":
            # TD: consumes mf
            mf = state_storage.get("mf")
            if mf is None:
                raise RuntimeError("TD requires SCF to run first")
            td_result = run_tddft(mf, step["parameters"])
            write_results(artifacts_dir, td_result)

        results.append(StepResult(...))

    return results
```

### 5.2 Alignment with Target Chain Semantics

| Requirement | Current PySCF Implementation | Status |
|-------------|------------------------------|--------|
| Calc independence | Each calc runtime-isolated | **COMPLIANT** |
| Chain = SCF root + downstream | SCF produces `mf`, downstream consumes | **COMPLIANT** |
| Run Calc: execute all chains | Executes all steps in order | **COMPLIANT** |
| Reuse allowed (default) | SCF can use chkfile as init_guess | **PARTIAL** - see note |
| Full fresh run option | `run_mode="full"` clears manifest | **COMPLIANT** |
| Run Step: partial chain from SCF root | Must compute partial chain | **NOT IMPLEMENTED** |
| Run Step on SCF = fresh SCF | Target step always reruns | **COMPLIANT** |

**Note on Reuse**: Current implementation sets target step to always rerun. The "reuse" in PySCF context means using checkpoint file for initial guess, not skipping execution.

### 5.3 Gaps Requiring Generalization

1. **Run Step partial chain computation**: Not implemented - needs chain root detection and partial chain extraction
2. **Chain detection**: No explicit "chain" concept in code - currently just linear step sequence
3. **Multiple chains per calc**: Not supported - assumes single linear sequence
4. **ORCA fusion**: No "compile to single input" mechanism exists yet

---

## 6. Step Taxonomy Mapping (Current)

### 6.1 Current PySCF Step Types

| Machine Type | Public Type | Engine | Consumes | Produces | Skip? |
|--------------|-------------|--------|----------|----------|-------|
| `pyscf_scf` | `scf` | `pyscf` | structure | `mf` | Yes |
| `pyscf_mp2` | `mp2` | `pyscf` | `mf` | `mp2` | No |
| `pyscf_td` | `td` | `pyscf` | `mf` | - | No |
| `pyscf_ccsd` | `ccsd` | `pyscf` | `mf` | `ccsd` | No |

### 6.2 Current QE Step Types

| Machine Type | Public Type | Engine | Consumes | Produces | Skip? |
|--------------|-------------|--------|----------|----------|-------|
| `qe_scf` | `scf` | `qe` | structure | outdir | Yes |
| `qe_nscf` | `nscf` | `qe` | outdir | outdir | Yes |
| `qe_bands` | `bands` | `qe` | outdir | bands.dat | Yes |
| `qe_dos` | `dos` | `qe` | outdir | dos.dat | Yes |
| `qe_relax` | `relax` | `qe` | structure | outdir+xyz | Yes |

---

## 7. Critique: Current Implementation vs Target Semantics

### 7.1 Strengths (Already Aligned)

1. **Step.yaml as single truth**: Machine step_type persisted, presets detected at runtime
2. **StepTypeRegistry authority**: All step types registered with full metadata
3. **Subprocess isolation**: PySCF never imported in daemon process
4. **State passing**: `mf` object passed between steps in chain_execution
5. **Manifest system**: SHA-based incremental run tracking

### 7.2 Gaps (Need Generalization for ORCA)

1. **No explicit chain concept**: Steps are linear sequence, not DAG with SCF roots
2. **No chain compilation**: Can't fuse multiple steps into single engine input
3. **No Run Step partial chain**: `run_step` not implemented as per spec
4. **PySCF-specific assumptions**: `state_storage` hardcoded to PySCF patterns
5. **No generalized QC engine layer**: PySCF engine contains QC-specific logic that should be shared

### 7.3 Recommended Abstractions for ORCA Integration

```python
# Proposed: Generalized QC Engine Layer

class QCChain:
    """Represents a dependency chain rooted at an SCF step."""
    scf_step: StepConfig
    downstream_steps: List[StepConfig]

    def to_partial_chain(self, target_step_id: str) -> "QCChain":
        """Extract partial chain from SCF root to target step."""
        pass

class QCEngineBase(Engine):
    """Base class for quantum chemistry engines (PySCF, ORCA)."""

    def detect_chains(self, steps: List[StepConfig]) -> List[QCChain]:
        """Identify chains separated by SCF roots."""
        pass

    def compile_chain(self, chain: QCChain) -> Union[Path, List[Path]]:
        """
        Compile chain to engine-specific representation.
        - PySCF: returns job.json with full chain
        - ORCA: returns single .inp file with fused steps
        """
        pass

    def run_chain(self, chain: QCChain, ...) -> List[StepResult]:
        """Execute chain (abstract, engine-specific implementation)."""
        pass
```

---

## 8. Summary Tables

### 8.1 File Reference Table

| Purpose | File Path | Key Classes/Functions |
|---------|-----------|----------------------|
| Engine interface | `engine/base.py` | `Engine`, `EngineConfig`, `StepResult` |
| PySCF engine | `engine/pyscf_engine.py` | `PySCFEngine` |
| QE engine | `engine/qe_engine.py` | `QeEngine` |
| Engine registry | `engine/registry.py` | `EngineRegistry`, `create_default_registry` |
| Step types | `workflow/registry.py` | `StepTypeRegistry`, `StepTypeSpec`, `resolve_engine_for_step` |
| Generalized steps | `workflow/generalized_steps.py` | `GeneralizedStep`, `materialize_step`, `MATERIALIZATION_MAP` |
| Workflow templates | `workflow/templates.py` | `WorkflowTemplate`, `WORKFLOW_TEMPLATES` |
| Step factory | `workflow/step_factory.py` | `create_step_doc`, `save_step_doc` |
| Calculation runner | `calculation/runner.py` | `CalculationRunner` |
| Manifest | `calculation/manifest.py` | `Manifest`, `update_manifest_step` |
| PySCF chain | `engines/pyscf/chain_execution.py` | `run_chain_session` |
| Preset paramspace | `presets/paramspace.py` | `ParamSpace`, `Cell`, `ParamKey` |
| Preset compiler | `presets/compiler.py` | `compile_one` |
| Preset detector | `presets/detector.py` | `detect` |

### 8.2 Constitution Compliance Checklist

| Constitution Rule | Current Status | Notes |
|-------------------|----------------|-------|
| §10.1 step.yaml is single truth | **COMPLIANT** | Machine step_type persisted |
| §10.2 Presets non-persistent | **COMPLIANT** | Detected at runtime |
| §10.3 Compiler pure function | **COMPLIANT** | See `presets/compiler.py` |
| §10.4 Detector B unique source | **COMPLIANT** | See `presets/detector.py` |
| §10.6 Mathematical equivalence | **TESTED** | Contract tests exist |
| §13.2 StepTypeRegistry authority | **COMPLIANT** | All types registered |
| §14.1 Session-chain execution | **PARTIAL** | PySCF only, not generalized |
| §14.3 No intermediate persistence | **COMPLIANT** | `mf` in memory only |

---

## 9. Core Execution Semantics Map

This section provides a definitive map of what is persisted vs runtime-only, and how the execution system works.

### 9.1 Persisted vs Runtime-Only

| Artifact | Persisted? | Location | Authority |
|----------|------------|----------|-----------|
| **step.yaml** | **YES** | `calculations/{calc_id}/steps/{step_id}/step.yaml` | Single source of truth for step definition |
| Machine step_type | **YES** | `step.yaml` → `step_type` field | StepTypeRegistry validates |
| Step parameters | **YES** | `step.yaml` → `parameters` field | Engine-specific key-value pairs |
| Step ULID | **YES** | Directory name + `step.yaml` | Resource identity |
| **manifest.yaml** | **YES** | `calculations/{calc_id}/raw/manifest.yaml` | Tracks execution state (done, SHAs) |
| Step artifacts | **YES** | `calculations/{calc_id}/raw/step_artifacts/{step_id}/` | Results, logs, output files |
| **Preset IR / options** | NO (runtime) | UI/history only | Detected from params via Detector B |
| **Chain grouping** | NO (runtime) | Computed at execution time | QC engines detect SCF roots |
| **PySCF state objects (mf, mp2)** | NO (runtime) | In-memory only during chain execution | Cannot be serialized |
| **Detected preset state** | NO (runtime) | Computed on-demand from step.yaml | `detect(parameters)` |

### 9.2 StepTypeRegistry + Materialization Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP CREATION TIME (UI → Persistence)                                     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  User selects:                                                            │
│    - engine_family: "orca"                                                │
│    - workflow: "scf_td" (public step types: [scf, td])                   │
│    - preset options: {precision: "high", ...}                            │
│                                                                           │
│           │                                                               │
│           ▼                                                               │
│  materialize_step(engine_family="orca", GeneralizedStep.SCF)              │
│    → Returns: "orca_scf" (machine step_type)                             │
│    → Source: MATERIALIZATION_MAP in generalized_steps.py                 │
│                                                                           │
│           │                                                               │
│           ▼                                                               │
│  compile_one(step_type="orca_scf", options={precision: "high"})          │
│    → Returns: parameters dict (e.g., {functional: "B3LYP", ...})         │
│    → Source: presets/compiler.py                                          │
│                                                                           │
│           │                                                               │
│           ▼                                                               │
│  Persist step.yaml:                                                       │
│    step_type: "orca_scf"    # MACHINE type (not "scf")                   │
│    parameters:                                                            │
│      functional: "B3LYP"                                                  │
│      basis: "def2-TZVP"                                                   │
│      ...                                                                  │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ EXECUTION TIME (Persistence → Engine)                                     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  CalculationRunner reads step.yaml                                        │
│           │                                                               │
│           ▼                                                               │
│  resolve_engine_for_step(step_yaml_path)                                 │
│    → Reads step_type from step.yaml: "orca_scf"                          │
│    → Looks up StepTypeRegistry.get("orca_scf")                           │
│    → Returns: StepTypeSpec with engine="orca"                            │
│    → Source: workflow/registry.py:618-632                                │
│                                                                           │
│           │                                                               │
│           ▼                                                               │
│  EngineRegistry.get("orca") → ORCAEngine instance                        │
│           │                                                               │
│           ▼                                                               │
│  engine.run_step() or engine.run_chain()                                 │
│                                                                           │
│  NOTE: engine_family from calculation.yaml is NOT used at execution      │
│        time. Only step.yaml machine step_type matters.                   │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 9.3 CalculationRunner Skip/Redo Logic

**Location**: `src/quantumvitas/calculation/runner.py:172-336`

```
┌──────────────────────────────────────────────────────────────────────────┐
│ INCREMENTAL RUN (run_mode="incremental")                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. reconcile_manifest() called (runner.py:178, 204)                     │
│     - Loads manifest.yaml from calc directory                             │
│     - Compares topology (step count/types) with current steps            │
│     - Computes pseudo_set_sha, structure_sha                             │
│     - Returns: manifest object + start_idx                               │
│                                                                           │
│  2. For each step in calc.steps:                                         │
│                                                                           │
│     if step_idx < start_idx:                                              │
│       # Check 4-way match (runner.py:270-336)                            │
│       entry = manifest.entries[step_idx]                                  │
│       SKIP if ALL TRUE:                                                   │
│         - entry.done == True                                              │
│         - entry.kind == step.step_type                                    │
│         - entry.step_sha == SHA256(step.yaml content)                    │
│         - entry.pseudo_set_sha == current pseudo SHA                     │
│         - entry.structure_sha == current structure SHA                   │
│       On skip: Mark SUCCESS, log "already done, inputs unchanged"        │
│                                                                           │
│     else:                                                                 │
│       # Execute step (runner.py:434-461)                                 │
│       - Update manifest: started_at, done=False, run_id                  │
│       - Resolve engine via StepTypeRegistry                               │
│       - Execute step                                                      │
│       - On success: Update manifest: done=True, done_at                  │
│       - On failure: done remains False                                    │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ FULL RUN (run_mode="full")                                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. reconcile_manifest() to ensure length matches topology (line 242)    │
│                                                                           │
│  2. Mark ALL entries: done=False, run_id=None (lines 252-256)            │
│                                                                           │
│  3. Set start_idx=0 (line 262)                                           │
│                                                                           │
│  4. Execute ALL steps from step 0                                         │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 9.4 Run Step Implementation (Repo Evidence)

**Q1 Answer: YES, Run Step exists**

| Component | Location | Function |
|-----------|----------|----------|
| RPC Handler | `daemon/server.py:5450-5516` | `_handle_run_step()` |
| RPC Handler (always run) | `daemon/server.py:5518-5572` | `_handle_run_single_step()` |
| Backend | `api.py:1319-1470` | `QVService.run_step()` |
| Backend (always run) | `api.py:1675-1850+` | `QVService.run_single_step()` |
| Job Manager | `daemon/jobs.py:112-683` | `JobManager` class |

**Execution Flow**:
```
UI "Run Step" button
    │
    ▼
RPC: _handle_run_step(calc_id, step_id)   [server.py:5450]
    │
    ▼
JobManager.submit_with_id(func=QVService.run_step)   [server.py:5496]
    │
    ▼
QVService.run_step(calc_id, step_id)   [api.py:1319]
    │
    ├── resolve_engine_for_step() → engine name   [api.py:1386-1396]
    │
    ├── For PySCF: routes to chain_execution   [api.py:1419-1435]
    │
    └── For QE: single step execution
```

### 9.5 Engine Path Resolution (Repo Evidence)

**Q3 Answer: Global, same pattern as QE**

| Component | Location | Description |
|-----------|----------|-------------|
| QE Resolver | `core/engines/qe_resolver.py:139-190` | `resolve_qe_bin_dir()` |
| State 1: External | `qe_resolver.py:163` | `settings.qe.bin_dir` |
| State 2: Internal | `qe_resolver.py:57-136` | `find_internal_qe_bin_dir()` |
| Internal path pattern | `qe_resolver.py:71, 79` | `.qmatsuite/engines/qe/**/bin` |
| QE Engine init | `core/engines/qe.py:98-137` | `QuantumEspressoEngine.__init__()` |

**Bundled Engines Directory**:
```
<HOME>/QMatSuite/.qmatsuite/engines/
├── qe/
│   └── {qe_version}/bin/pw.x
└── orca/
    └── orca_6_1_1_macosx_arm64_openmpi411/orca   # VERIFIED EXECUTABLE
```

### 9.6 Manifest Structure

**Location**: `src/quantumvitas/calculation/manifest.py`

```yaml
# manifest.yaml structure
steps:
  - step_ulid: "01HX..."           # Step identifier
    kind: "orca_scf"               # Machine step_type
    pseudo_set_sha: "abc123..."    # SHA256 of pseudo files
    structure_sha: "def456..."     # SHA256 of structure
    step_sha: "ghi789..."          # SHA256 of step.yaml content
    done: true                     # Completion flag
    run_id: "01HY..."              # ULID of executing run
    started_at: "2026-01-12T..."   # ISO8601 start time
    done_at: "2026-01-12T..."      # ISO8601 completion time
```

**Update Points**:
- Before execution: `update_manifest_step()` sets `started_at`, `done=False`, `run_id`
- After success: `update_manifest_step()` sets `done=True`, `done_at`
- On failure: `done` remains `False`, `done_at` remains `None`

---

## 10. Next Steps

This analysis provides the foundation for:

1. **ORCA Exploration Document**: Verify ORCA docs claims, document capabilities
2. **Implementation Plan**: Design generalized QC engine layer for PySCF + ORCA

See companion documents:
- `docs/plans/orca_orca_exploration.md` - ORCA documentation analysis
- `docs/plans/orca_implementation_plan.md` - Concrete implementation plan
- `docs/plans/orca_execution_mvp_plan.md` - Test-driven MVP execution plan
