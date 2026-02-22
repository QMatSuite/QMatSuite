# Existing Job/Step System Review for VASP Integration

**Date**: 2026-01-18  
**Version**: 2.0 (Supplemental review for new requirements)  
**Purpose**: Deep review of runner/materialize/manifest/history/locks system with focus on extension points for VASP-specific behaviors.

---

## 1. System Overview: The Three Engine Execution Models

QMatSuite currently supports three distinct engine execution models:

| Engine | Execution Model | State Sharing | Workdir Pattern | Artifact Location |
|--------|----------------|---------------|-----------------|-------------------|
| **QE** | Directory-state | Via `outdir/` (charge density) | `calc/raw/` | `calc/raw/*.out`, `calc/raw/outdir/` |
| **ORCA** | Strong-chain | Via `.gbw` file (wavefunction) | `calc/raw/scf_<suffix>/` | Same directory |
| **PySCF** | Weak-chain/session | Via in-memory `mf` object | `calc/raw/scf_<suffix>/` | `step_artifacts/<ulid>/` |

**VASP Target Model**: Directory-state like QE, but with:
- Per-step isolated workdirs (`calc/raw/<step_ulid>/`)
- Explicit CHGCAR/WAVECAR copying between steps
- Reference SCF resolution with relax barrier

---

## 2. Extension Points Analysis for VASP Requirements

### 2.1 "Most Recent SCF Resolver + Relax Barrier"

**Current state**: No existing abstraction for "find reference step by GEN type with barrier".

**Where it should live**:
```
src/qmatsuite/execution/reference_resolver.py  (NEW)
```

**Why new module**: This is cross-engine logic (QE could also use it for restart from SCF). Not engine-specific, so shouldn't be in `vasp_engine.py`.

**Integration point**: Called from `vasp_step_handler` before staging, but could be generalized for all PBC engines.

**Existing code to examine**:
```python
# src/qmatsuite/execution/executor.py
def _load_effective_structure_for_step(self, step_idx, calculation):
    """Find relax step and load generated structure."""
    # This already walks backwards to find relax steps
    # Similar pattern needed for "find reference SCF"
```

**Minimal implementation**:
```python
def find_reference_scf(
    steps: List[Step],
    current_step_idx: int,
    registry: StepTypeRegistry,
) -> Optional[Tuple[int, Step]]:
    """
    Find the most recent SCF step that can serve as reference.
    
    Walk backwards from current_step_idx.
    Return first step where gen_type == 'scf'.
    Stop if we hit a relax step (barrier).
    """
    for i in range(current_step_idx - 1, -1, -1):
        step = steps[i]
        gen_type = get_gen_type(step, registry)
        
        if gen_type == "relax":
            return None  # Barrier - no valid reference
        
        if gen_type == "scf":
            return (i, step)
    
    return None  # No SCF found
```

### 2.2 "Staging Prerequisite (done + file exists)"

**Current state**: Manifest checking exists but not coupled with file existence check.

**Where it should live**:
```
src/qmatsuite/execution/vasp_staging.py  (NEW)
```

**Why new module**: VASP-specific staging logic (CHGCAR/WAVECAR). Other engines have different staging needs.

**Existing code to examine**:
```python
# src/qmatsuite/calculation/manifest.py
@dataclass
class ManifestStepEntry:
    done: bool  # ← This is the flag we need to check
    
def should_skip_step(manifest_entry, ...):
    if not manifest_entry.done:
        return False  # ← Already checks done flag
```

**Integration point**: Called from `vasp_step_handler` after reference resolution, before input materialization.

**Prerequisite enforcement**:
```python
def check_staging_prerequisites(
    reference_scf: Step,
    manifest: Manifest,
    calc_raw_dir: Path,
    required_artifacts: List[str],  # e.g., ["CHGCAR"]
) -> None:
    """
    Check that reference SCF is done and required files exist.
    
    Raises:
        MissingPrerequisiteError: If done=False
        MissingArtifactError: If file doesn't exist
    """
    entry = get_manifest_entry(manifest, reference_scf.meta.id)
    
    if entry is None or not entry.done:
        raise MissingPrerequisiteError(
            f"Reference SCF {reference_scf.meta.id} is not marked done in manifest. "
            f"Run SCF first."
        )
    
    ref_workdir = calc_raw_dir / reference_scf.meta.id
    for artifact in required_artifacts:
        artifact_path = ref_workdir / artifact
        if not artifact_path.exists():
            raise MissingArtifactError(
                f"Required artifact {artifact} not found in {ref_workdir}. "
                f"SCF may have completed without generating this file."
            )
```

### 2.3 "Workdir Clean Policy (rm-all)"

**Current state**: QE doesn't clean workdir (shared `calc/raw/`). ORCA/PySCF create fresh chain directories.

**Where it should live**: In `vasp_step_handler` directly (simple enough to not need abstraction).

**Existing code to examine**:
```python
# src/qmatsuite/execution/handlers.py
def qe_step_handler(...):
    raw_dir.mkdir(parents=True, exist_ok=True)
    # NO cleaning - QE shares the directory
    
    # Per-step artifacts directory IS cleaned:
    step_artifacts_dir = raw_dir / "step_artifacts" / step_ulid
    if step_artifacts_dir.exists():
        for item in step_artifacts_dir.iterdir():
            if item.is_file():
                item.unlink()
```

**VASP pattern**:
```python
def vasp_step_handler(...):
    working_dir = job.working_dir  # calc/raw/<step_ulid>
    
    # VASP: Complete clean before execution
    if working_dir.exists():
        shutil.rmtree(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)
```

### 2.4 "0-Mapping GEN Step Semantics (UI/selector/error)"

**Current state**: `materialize_workflow()` raises `ValueError` on unsupported steps.

**Where modification is needed**:
```
src/qmatsuite/workflow/generalized_steps.py  (MODIFY)
src/qmatsuite/api.py  (MODIFY - for explicit run_step error)
```

**Existing code to examine**:
```python
# src/qmatsuite/workflow/generalized_steps.py
def materialize_workflow(generalized_steps, engine_family):
    result = []
    for gen_step in generalized_steps:
        specific_step = materialize_public_step_key(gen_step, engine_family)
        if specific_step is None:
            raise ValueError(...)  # ← Current behavior: error
        result.append(specific_step)
    return result
```

**Required change**:
```python
def materialize_workflow(generalized_steps, engine_family):
    result = []
    for gen_step in generalized_steps:
        specific_step = materialize_public_step_key(gen_step, engine_family)
        if specific_step is None:
            continue  # ← New behavior: silently omit
        result.append(specific_step)
    return result
```

**For explicit run_step**:
```python
# src/qmatsuite/api.py (or wherever run_step is)
def run_step(project_root, calc_id, step_selector, ...):
    # NEW: Check if step_selector is GEN and maps to 0
    if looks_like_gen_step(step_selector):
        engine_family = get_calc_engine_family(project_root, calc_id)
        spec = materialize_step(step_selector.upper(), engine_family)
        if spec is None:
            raise UnsupportedStepError(
                f"Step '{step_selector}' is not supported by engine '{engine_family}'."
            )
    ...
```

---

## 3. Main Execution Path Call Graph

```
                    QMSService.run_calculation() / run_step()
                                    │
                                    ▼
                    ┌──────────────────────────────────┐
                    │    CalculationRunner.run()       │
                    └──────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
    Step0: Pseudo           Manifest Reconcile         Compute SHAs
          │                         │                         │
          └─────────────────────────┼─────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────────┐
                    │   _execute_with_jobgraph()       │
                    └──────────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────────┐
                    │   get_recipe_for_engine()        │
                    │   → VASPRecipe (NEW)             │
                    └──────────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────────┐
                    │   JobGraph.materialize()         │
                    │   → Creates isolated workdirs    │
                    └──────────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────────┐
                    │   JobExecutor.execute()          │
                    │   → Dispatches to handler        │
                    └──────────────────────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────────┐
                    │   vasp_step_handler (NEW)        │
                    │   1. find_reference_scf()        │
                    │   2. check_staging_prerequisites │
                    │   3. clean workdir               │
                    │   4. stage CHGCAR/WAVECAR        │
                    │   5. materialize inputs          │
                    │   6. execute VASP                │
                    └──────────────────────────────────┘
```

---

## 4. Recipe System Analysis

### 4.1 Current Recipes

```python
# src/qmatsuite/execution/recipes.py

class QERecipe(BaseRecipe):
    """One job per step, shared calc/raw/ directory"""
    working_dir = calc_raw_dir  # Shared

class ORCARecipe(BaseRecipe):
    """One job per subchain, dedicated scf_<suffix>/ directory"""
    working_dir = calc_raw_dir / namespace_folder

class PySCFRecipe(BaseRecipe):
    """One job per subchain, dedicated scf_<suffix>/ directory"""
    working_dir = calc_raw_dir / namespace_folder
```

### 4.2 VASPRecipe Design

```python
class VASPRecipe(BaseRecipe):
    """One job per step, ISOLATED per-step workdir"""
    
    def materialize(self, steps, calc_raw_dir, step_shas) -> JobGraph:
        jobs = []
        for idx, step in enumerate(steps):
            step_ulid = step.meta.id
            
            # KEY DIFFERENCE: Each step gets its own directory
            working_dir = calc_raw_dir / step_ulid
            
            job = Job(
                id=f"vasp_step_{idx:02d}",
                step_ids=[step_ulid],
                working_dir=working_dir,  # Isolated
                command=["vasp_std"],
                input_files=[...],
                metadata={
                    "engine": "vasp",
                    "step_index": idx,
                },
            )
            jobs.append(job)
        
        return JobGraph(jobs=jobs)
```

---

## 5. Handler System Analysis

### 5.1 Current Handler Pattern

```python
# src/qmatsuite/execution/handlers.py

def qe_step_handler(job, calculation, engine_registry, context) -> JobResult:
    step = _find_step_by_ulid(calculation, job.step_ids[0])
    engine = engine_registry.get("qe")
    
    # QE: No staging, no cleaning (shared directory)
    result = step.run(engine=engine, calculation_raw_dir=raw_dir, ...)
    
    return JobResult(...)

def create_handler_map(engine_registry, context):
    return {
        "qe": make_handler(qe_step_handler),
        "pyscf": make_handler(pyscf_chain_handler),
        "orca": make_handler(orca_chain_handler),
    }
```

### 5.2 vasp_step_handler Design

```python
def vasp_step_handler(job, calculation, engine_registry, context) -> JobResult:
    step = _find_step_by_ulid(calculation, job.step_ids[0])
    step_idx = job.metadata["step_index"]
    
    # 1. Find reference SCF (if not SCF step)
    reference_scf = None
    if not is_scf_step(step):
        ref_result = find_reference_scf(
            calculation.steps,
            step_idx,
            get_registry(),
        )
        if ref_result is None:
            return JobResult(
                job_id=job.id,
                success=False,
                error="No valid reference SCF found (may be blocked by relax barrier)",
            )
        _, reference_scf = ref_result
    
    # 2. Check staging prerequisites
    if reference_scf is not None:
        try:
            check_staging_prerequisites(
                reference_scf,
                load_manifest(calculation.dir),
                calculation.raw_dir,
                required_artifacts=["CHGCAR"],
            )
        except (MissingPrerequisiteError, MissingArtifactError) as e:
            return JobResult(job_id=job.id, success=False, error=str(e))
    
    # 3. Clean workdir
    working_dir = job.working_dir
    if working_dir.exists():
        shutil.rmtree(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)
    
    # 4. Stage CHGCAR/WAVECAR
    if reference_scf is not None:
        stage_artifacts(reference_scf, step, calculation.raw_dir)
    
    # 5. Materialize inputs
    engine = engine_registry.get("vasp")
    engine.materialize_inputs(step, working_dir, calculation)
    
    # 6. Execute VASP
    result = engine.run(working_dir=working_dir)
    
    return JobResult(
        job_id=job.id,
        success=result.success,
        error=result.error if not result.success else None,
        step_results={step.meta.id: {...}},
    )
```

---

## 6. Manifest System (No Changes Needed)

The manifest system is engine-agnostic and already provides:

```python
@dataclass
class ManifestStepEntry:
    kind: str              # Step type
    step_ulid: str         # ULID
    pseudo_set_sha: str    # Fingerprint
    structure_sha: str     # Fingerprint
    step_sha: str          # Fingerprint
    done: bool             # ← Used by staging prerequisite check
    run_id: Optional[str]
    started_at: Optional[str]
    done_at: Optional[str]
```

VASP steps will be tracked identically to QE/ORCA/PySCF steps.

---

## 7. Locking System (No Changes Needed)

The locking system is engine-agnostic:

```python
@contextlib.contextmanager
def calc_run_lock(calc_dir: Path, fail_fast: bool = True):
    """Long-held during entire calculation run"""

@contextlib.contextmanager
def calc_edit_lock(calc_dir: Path, fail_fast: bool = False):
    """Short-held during YAML writes"""
```

VASP execution will use the same locks.

---

## 8. Test Pyramid Analysis

### 8.1 Current Test Layers

| Layer | Location | Purpose | VASP Equivalent |
|-------|----------|---------|-----------------|
| Unit | `tests/unit/` | Pure functions | `test_vasp_parser.py`, `test_vasp_writer.py` |
| Materialize | `tests/unit/` | Input generation | `test_vasp_input_generation.py` |
| Runner (fake) | `tests/integration/` | With mocked engine | `test_vasp_runner_fake.py` |
| Runner (real) | `tests/integration/` | Actual execution | `test_vasp_execution_real.py` (skip in CI) |
| Service | `tests/daemon/` | API layer | `test_vasp_project_e2e.py` |

### 8.2 Key Test Fixtures

**From `tests/conftest.py`**:
```python
@pytest.fixture(scope="session", autouse=True)
def force_test_cwd_to_tmp(tmp_path_factory):
    """Force CWD to tmp directory"""

@pytest.fixture(scope="function", autouse=True)
def trap_repo_pseudo_creation():
    """Prevent writes to repo_root/pseudo"""
```

**VASP-specific fixtures needed**:
```python
@pytest.fixture(scope="module")
def skip_if_vasp_unavailable():
    if not is_vasp_available():
        pytest.skip("VASP not installed")

@pytest.fixture
def fake_vasp_bin(tmp_path, monkeypatch):
    """Create fake VASP binary for testing"""
    fake_script = tmp_path / "fake_vasp"
    fake_script.write_text(FAKE_VASP_SCRIPT)
    fake_script.chmod(0o755)
    monkeypatch.setenv("QMATS_VASP_STD_BIN", str(fake_script))
    return fake_script
```

---

## 9. Summary: What Exists vs What's Needed

### 9.1 Existing Abstractions (Reuse As-Is)

| Component | Status |
|-----------|--------|
| Recipe base class | ✅ Sufficient |
| Handler registration | ✅ Sufficient |
| Manifest system | ✅ Engine-agnostic |
| Locking system | ✅ Engine-agnostic |
| Step type registry | ✅ Extendable |
| GEN→SPEC mapping | ✅ Extendable |

### 9.2 New Modules Needed

| Module | Purpose |
|--------|---------|
| `reference_resolver.py` | Find reference SCF with relax barrier |
| `vasp_staging.py` | CHGCAR/WAVECAR staging with prerequisites |
| `vasp_resolver.py` | Binary/POTCAR discovery |
| `vasp_engine.py` | Engine implementation |
| `vasp_writer.py` | Input file generation |
| `vasp_parser.py` | Output parsing |

### 9.3 Modifications Needed

| File | Change |
|------|--------|
| `generalized_steps.py` | 0-mapping silent omission |
| `recipes.py` | Add VASPRecipe |
| `handlers.py` | Add vasp_step_handler |
| `registry.py` | Add VASP step types |
| `engine/registry.py` | Register VaspEngine |

### 9.4 No New Abstractions Needed

The existing architecture is well-designed for multi-engine support. VASP integration requires:
- **Adding** new implementations (recipe, handler, engine)
- **Extending** existing registries (step types, GEN→SPEC)
- **One semantic change**: 0-mapping silent omission in `materialize_workflow()`

No major architectural changes or new abstractions are required.
