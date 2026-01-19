# QE Backend Code Review for VASP Integration

**Purpose**: Deep review of existing QE integration to guide VASP implementation.

---

## 1. Module Map: QE Backend Architecture

### 1.1 Engine Layer

```
src/quantumvitas/engine/
├── base.py              # Engine abstract base class (supported_presets property)
├── registry.py          # EngineRegistry + create_default_registry()
├── qe_engine.py         # QeEngine wrapper (thin adapter over legacy)
├── pyscf_engine.py      # PySCF engine (molecule engine, different pattern)
├── orca_engine.py       # ORCA engine (molecule engine)
└── installation.py      # Engine installation helpers

src/quantumvitas/core/engines/
├── base.py              # EngineConfig, legacy Engine class
├── qe.py                # QuantumEspressoEngine (main implementation)
├── qe_calculation.py    # QECalculationRunner, StepResult, get_capture_paths()
├── qe_resolver.py       # resolve_qe_bin_dir() - two-state QE discovery
├── qe_installation.py   # QEInstallation - path detection
├── qe_pseudopotentials.py  # QE pseudo handling (legacy)
├── qe_diagnostics.py    # diagnose_qe_resolution() for debugging
├── qe_registry.py       # QE home registry (global state)
├── qe_seed.py           # Seeding helpers
├── orca_resolver.py     # ORCA binary resolution (similar pattern)
└── __init__.py          # reset_qe_home() export
```

### 1.2 Step Type Registry

```
src/quantumvitas/workflow/
├── registry.py          # StepTypeRegistry, StepTypeSpec, gen→spec mapping
├── step_factory.py      # Step creation from templates
├── templates.py         # Workflow templates
└── generalized_steps.py # Gen step handling
```

**Key Classes in registry.py**:
- `StepTypeSpec`: Defines id/machine_type/public_type/engine/executable mapping
- `StepTypeRegistry`: Lookup by step_type, list by engine, validate
- `normalize_step_type_to_public()`: Machine type → public type conversion
- `resolve_engine_for_step()`: Step YAML → engine ID resolution

### 1.3 Execution Layer

```
src/quantumvitas/execution/
├── executor.py          # JobExecutor - job graph execution
├── handlers.py          # Engine-specific dispatch (QE/PySCF/ORCA)
├── job_graph.py         # Job/JobGraph data structures
├── recipes.py           # Workflow recipes
├── scan_expansion.py    # Parameter scan handling
├── post_job.py          # Post-job archiving
├── relax_artifacts.py   # Relax step structure extraction
├── pyscf_relax_handler.py  # PySCF relax post-processing
└── orca_relax_parser.py    # ORCA relax post-processing
```

### 1.4 Calculation Model

```
src/quantumvitas/calculation/
├── calculation.py       # Calculation model
├── step.py              # Step model
├── runner.py            # CalculationRunner - orchestrates execution
├── manifest.py          # Manifest for incremental runs
├── types.py             # StepStatus, StepMode enums
├── species_config.py    # species_map configuration
├── hash_utils.py        # Fingerprint/SHA computation
├── verification.py      # Step result verification
├── step_done.py         # Step completion detection
├── step_defaults.py     # Default parameters
├── step_artifacts.py    # Artifact collection
└── importers.py         # QE input → step spec import
```

### 1.5 Materialization (IR/Backend)

```
src/quantumvitas/ir/
├── parameters.py        # IRParameter registry (engine-agnostic)
├── backends/qe/
│   └── mapping.py       # IR ↔ QE parameter mapping
└── dialects/pw/
    └── __init__.py      # PW dialect specifics
```

### 1.6 Pseudopotential System

```
src/quantumvitas/core/
├── pseudo.py            # get_system_pseudo_dir()
├── pseudo_config.py     # Pseudo configuration loading
├── pseudo_installs.py   # Archive installation
├── pseudo_libinfo.py    # Bundle metadata loading
├── pseudo_materialization.py  # materialize_calc_pseudos()
├── pseudo_options.py    # materialize_pseudo_file()
├── pseudo_provenance.py # SHA computation for pseudos
└── pseudo_runtime.py    # Step0 pseudo preparation
```

### 1.7 History & Manifest

```
src/quantumvitas/history/
├── storage.py           # ProjectHistory, run directory management
├── run_revision.py      # RunRevision, create_run_revision()
├── digests.py           # StepDigest, compute_step_digest()
├── events.py            # History events
└── pins.py              # Pin management
```

### 1.8 Locking

```
src/quantumvitas/core/locking.py
  - calc_run_lock()      # Long lock during entire run (materialize + execute)
  - calc_edit_lock()     # Short lock during YAML writes
  - CalculationLockError # Raised when lock unavailable
  - LockReentrancyError  # Raised on nested lock attempt
```

---

## 2. Call Graph: Run Calculation / Run Step Entrypoint

### 2.1 High-Level Flow

```
QVService.run_calculation() / run_step()
    └── CalculationRunner.run()
        ├── Step 0: Pseudo preparation (prepare_project_pseudos_for_run)
        ├── Create RunRevision (history/run_revision.py)
        ├── Load/update Manifest
        ├── For each step:
        │   ├── Check incremental skip (manifest + fingerprints)
        │   ├── Materialize inputs (step.yaml → engine input files)
        │   ├── Execute engine (via engine registry)
        │   │   └── QeEngine.run_step() → QECalculationRunner.run_step()
        │   │       ├── Build command (build_command)
        │   │       ├── Subprocess execution
        │   │       └── Parse output (optional)
        │   ├── Update manifest entry (done=True)
        │   └── History: record step result
        └── Complete RunRevision
```

### 2.2 Detailed Execution Path (QE)

```
1. QVService.run_step(project_root, calc_selector, step_selector)
   └── src/quantumvitas/api.py

2. Resolution: resolve_calculation(), resolve_step()
   └── src/quantumvitas/core/resolution.py

3. CalculationRunner.run(calculation, target_step_id=...)
   └── src/quantumvitas/calculation/runner.py

4. Step 0: Pseudo preparation
   ├── species_map_to_selections()
   ├── prepare_project_pseudos_for_run()  # Copies to project/pseudo
   └── refresh_calc_pseudo_records_after_step0()  # Updates pseudo_set_sha

5. Manifest loading
   ├── load_manifest(calc_dir)
   └── compute_step_sha() for fingerprint comparison

6. For each step (in execution order):
   a. Check incremental skip:
      └── Compare (kind, structure_sha, pseudo_set_sha, step_sha, done)
   
   b. Materialize inputs:
      └── _materialize_step() → writes .in files to raw/
          ├── Load step YAML (step_doc = StepDoc.load())
          ├── Apply presets/defaults
          ├── Write engine-specific input file
          └── Copy pseudos to working_dir/pseudo (if needed)
   
   c. Execute:
      └── engine.run_step(step, working_dir)
          └── QeEngine → QuantumEspressoEngine.run_step()
              └── QECalculationRunner.run_step(input_file, working_dir, step_type)
                  ├── build_command(step_type, input_file, working_dir)
                  ├── subprocess.Popen(..., stdin=input_handle, ...)
                  └── Return StepResult

   d. Post-process:
      └── For relax steps: handle_qe_relax_output() → writes current.json

   e. Update manifest:
      └── save_manifest_atomic() with done=True

7. Complete run:
   └── complete_run_revision() → compute digests, save history
```

---

## 3. Extension Points for VASP

### 3.1 Must Extend (Engine-Specific)

| Component | Location | Required for VASP |
|-----------|----------|-------------------|
| VaspEngine class | `engine/vasp_engine.py` (new) | YES - core engine wrapper |
| VASP resolver | `core/engines/vasp_resolver.py` (new) | YES - binary discovery |
| Step types | `workflow/registry.py` | YES - add vasp_scf, vasp_bands, vasp_dos |
| IR backend | `ir/backends/vasp/` (new) | YES - INCAR parameter mapping |
| Input writer | `engines/vasp/input_writer.py` (new) | YES - POSCAR/INCAR/KPOINTS/POTCAR |
| Output parser | `engines/vasp/output_parser.py` (new) | YES - OUTCAR/OSZICAR/vasprun.xml |
| Execution handler | `execution/handlers.py` | EXTEND - add VASP dispatch |

### 3.2 Generalized (Reuse As-Is)

| Component | Location | Notes |
|-----------|----------|-------|
| EngineRegistry | `engine/registry.py` | Register VaspEngine like QE/ORCA |
| CalculationRunner | `calculation/runner.py` | Engine-agnostic orchestration |
| JobExecutor | `execution/executor.py` | Already supports handler dispatch |
| Manifest | `calculation/manifest.py` | Same skip logic applies |
| History/RunRevision | `history/` | Same recording applies |
| Locking | `core/locking.py` | Same locks apply |
| species_map | `calculation/species_config.py` | Extend for POTCAR mapping |
| Structure I/O | `io/structure_io.py` | Reuse pymatgen Structure |

### 3.3 Needs Generalization

| Component | Current State | Action for VASP |
|-----------|---------------|-----------------|
| Pseudo materialization | QE-specific (.UPF files) | Add POTCAR concatenation logic |
| pseudo_set_sha | QE pseudo hashing | Same approach: hash POTCAR fragments |
| ESPRESSO_PSEUDO env | QE-specific env var | Not needed for VASP (no env var) |

---

## 4. Invariants VASP Must Match

### 4.1 Constitution Rules (from user prompt)

1. **SSOT on disk**: Only `calculation.yaml` + `step.yaml`. Inputs in `raw/` are ephemeral.
2. **Engine invocation == Job == Run**: `run_id == job_id`. History is append-only.
3. **Two calc-level locks**: `edit.lock` (short, YAML writes) and `run.lock` (long, materialize→execute).
4. **Manifest is runtime bookkeeping**: Not SSOT. Incremental skip uses `kind + structure_sha + pseudo_set_sha + step_sha + done`.
5. **ULID-only internally**: Slug only in resource's own `meta.slug`.
6. **Gen step vs Spec/machine step**: UI uses GEN; step.yaml stores SPEC; dispatch is explicit mapping.
7. **species_map SSOT**: For project-run, pseudo/species_map must be in `calculation.yaml`.
8. **ScanRef rules**: Leaf scan ref is `@scan:<scan_id>` string; parameter_scan excluded from fingerprints.

### 4.2 Code Invariants

```python
# Step type bijection (workflow/registry.py)
# - Every machine_type maps to exactly one public_type
# - Every public_type maps to one machine_type per engine

# Manifest fingerprint (calculation/manifest.py)
# - ManifestStepEntry fields: kind, step_ulid, pseudo_set_sha, structure_sha, step_sha
# - Incremental skip: all must match AND done=True

# Lock usage (core/locking.py)
# - run.lock held for entire run (materialize + execute)
# - edit.lock held only during YAML writes (< 100ms)
# - Locks are NOT re-entrant

# ULID references (core/resources.py)
# - All internal references use ULID, not slug
# - Manifest.step_ulid, calculation.structure_id, step_id are ULIDs
```

---

## 5. QE Test Classification

### 5.1 Test Layers

#### Layer 1: Pure Writer/Materialization Tests
**Location**: `tests/unit/`
**Pattern**: Test input generation without execution

```python
# Example: tests/unit/test_qe_input.py
def test_generate_input_from_data():
    """Test that QE input file is generated correctly from dict."""
    input_data = {...}
    input_file = engine.generate_input(step_type='scf', input_data=input_data, working_dir=tmp_path)
    assert input_file.exists()
    content = input_file.read_text()
    assert '&control' in content
```

**Key Files**:
- `tests/unit/test_qe_input.py` - QE input parsing/generation
- `tests/unit/test_qe_modules.py` - Module detection
- `tests/unit/test_pseudo_materialization_*.py` - Pseudo staging
- `tests/unit/test_species_map.py` - species_map handling
- `tests/unit/test_step_type_mapping.py` - Gen→spec mapping

#### Layer 2: Runner/Job Tests (Mocked or Fake Engine)
**Location**: `tests/unit/` and `tests/integration/`
**Pattern**: Test execution flow with mocked subprocess

```python
# Example: tests/integration/test_qe_engine.py
def test_parse_input_file(engine, tmp_path):
    """Test parsing an input file."""
    input_file = tmp_path / "test.in"
    input_file.write_text("&control...")
    qe_input = engine.parse_input_file(input_file)
    assert qe_input is not None
```

**Key Files**:
- `tests/integration/test_qe_engine.py` - Engine input/output
- `tests/unit/test_calculation_dag_constitution.py` - DAG execution model
- `tests/unit/test_manifest_effective_structure.py` - Manifest updates

#### Layer 3: Service API Tests
**Location**: `tests/unit/` and `tests/integration/`
**Pattern**: Test QVService methods with temp projects

```python
# Example: tests/unit/test_api_service.py
def test_init_calculation(tmp_path):
    project_root = QVService.init_project(tmp_path / "proj")
    calc = QVService.init_calculation(project_root, "test_calc", ...)
    assert calc.id is not None
```

**Key Files**:
- `tests/unit/test_api_service.py` - QVService operations
- `tests/unit/test_api_service_steps.py` - Step operations
- `tests/unit/test_api_step_artifacts.py` - Artifact retrieval

#### Layer 4: Daemon/Persistence/Project Runs
**Location**: `tests/daemon/`
**Pattern**: Full project execution through daemon layer

```python
# Example: tests/daemon/test_si_bands_calculation_daemon.py
def test_full_bands_calculation(si_bands_project):
    # Create project via QVService
    # Run calculation
    # Verify all steps completed
```

**Key Files**:
- `tests/daemon/test_si_bands_calculation_daemon.py` - Full workflow
- `tests/daemon/test_gui_calculation_detail.py` - GUI integration
- `tests/daemon/test_gui_job_and_step_flows.py` - Job flows

#### Layer 5: Incremental Behavior Tests
**Location**: `tests/integration/`
**Pattern**: Test skip logic, manifest updates

```python
# Example: tests/integration/test_incremental_run.py
def test_incremental_skip_when_unchanged():
    # Run once
    # Run again
    # Verify second run skipped
```

**Key Files**:
- `tests/integration/test_incremental_run.py` - Incremental runs
- `tests/unit/test_step_done.py` - Completion detection

### 5.2 Test Harness Primitives

#### Temp Project Creation
```python
# tests/utils/calculation_projects.py
def create_calculation_project(
    project_root: Path,
    calculation_id: str,
    steps: Sequence[Dict[str, Any]],
    source_dir: Path,
    pseudo_src: Path,
) -> Path:
    """Create minimal project with calculation + steps."""
```

#### Engine Discovery Stubs
```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def reset_qe_registry():
    """Reset QE home registry before/after each test."""
    from quantumvitas.core.engines import reset_qe_home
    reset_qe_home()
    yield
    reset_qe_home()
```

#### Fake Binary Pattern (from ORCA tests)
```python
# tests/integration/orca/test_orca_execution.py
@pytest.fixture
def orca_engine():
    """Get ORCA engine if available."""
    if not ORCA_BIN:
        pytest.skip("QMATSUITE_ORCA_BIN not set")
    orca_path = Path(ORCA_BIN)
    if not orca_path.exists():
        pytest.skip(f"ORCA binary not found at {ORCA_BIN}")
    return ORCAEngine(orca_bin=orca_path)
```

#### ULID Usage
```python
# Always use generate_resource_id() for new resources
from quantumvitas.core.resources import generate_resource_id
step_ulid = generate_resource_id()
```

### 5.3 Patterns to Replicate for VASP

1. **Availability fixture with skip**:
   ```python
   @pytest.fixture
   def vasp_available():
       try:
           from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin
           vasp_bin = resolve_vasp_bin()
       except RuntimeError:
           pytest.skip("VASP not available")
       return vasp_bin
   ```

2. **Fake VASP harness** for CI:
   ```python
   # Create minimal fake outputs for each step type
   def fake_vasp_scf(workdir):
       (workdir / "OUTCAR").write_text("free  energy   TOTEN = -10.0 eV\n...")
       (workdir / "OSZICAR").write_text("1 F= -.10000000E+02\n")
   ```

3. **Input determinism tests**:
   ```python
   def test_poscar_roundtrip(structure):
       poscar_text = write_poscar(structure)
       structure2 = read_poscar(poscar_text)
       assert structure == structure2
   ```

### 5.4 Patterns to Avoid

1. **Excessive duplication**: QE tests have many similar files. VASP tests should use parametrization.

2. **Brittle path checks**: Don't hardcode paths. Use `tmp_path` and relative references.

3. **Missing skip logic**: Every test that needs VASP binary MUST have skip fixture.

4. **Mixing unit and integration**: Keep pure writer tests separate from execution tests.

---

## 6. Key Functions Reference

### 6.1 Engine Registration
```python
# engine/registry.py
def create_default_registry() -> EngineRegistry:
    registry = EngineRegistry()
    registry.register(QeEngine(config))
    registry.register(PySCFEngine())
    registry.register(ORCAEngine(defer_binary_resolution=True))
    # ADD: registry.register(VaspEngine(defer_binary_resolution=True))
    return registry
```

### 6.2 Step Type Definition
```python
# workflow/registry.py
_STEP_TYPES = {
    "qe_scf": StepTypeSpec(
        id="scf", machine_type="qe_scf", public_type="scf",
        engine="qe", executable="pw.x", ...
    ),
    # ADD: "vasp_scf": StepTypeSpec(...)
}
```

### 6.3 Execution Handler Dispatch
```python
# execution/handlers.py
def get_engine_handler(engine_name: str) -> Callable:
    handlers = {
        "qe": handle_qe_job,
        "pyscf": handle_pyscf_job,
        "orca": handle_orca_job,
        # ADD: "vasp": handle_vasp_job,
    }
    return handlers.get(engine_name)
```

### 6.4 Pseudo Materialization
```python
# core/pseudo_materialization.py
def materialize_calc_pseudos(
    project_root: Optional[Path],
    working_dir: Path,
    species_map: Dict[str, Dict[str, Any]],
) -> Path:
    """Materialize pseudos to working_dir/pseudo."""
    # For VASP: need to concatenate element POTCARs
```

### 6.5 Manifest Entry
```python
# calculation/manifest.py
@dataclass
class ManifestStepEntry:
    kind: str           # Step type
    step_ulid: str      # ULID
    pseudo_set_sha: str # SHA of pseudo set
    structure_sha: str  # SHA of structure
    step_sha: str       # SHA of step YAML
    done: bool = False
```

---

## 7. Summary: What VASP Implementation Needs

### Must Implement (New Code)
1. `VaspEngine` class in `engine/vasp_engine.py`
2. `resolve_vasp_bin()` in `core/engines/vasp_resolver.py`
3. Step type definitions in `workflow/registry.py`
4. Input writers (POSCAR, INCAR, KPOINTS, POTCAR assembly)
5. Output parsers (OUTCAR, OSZICAR, optional vasprun.xml)
6. Execution handler in `execution/handlers.py`
7. POTCAR concatenation in pseudo system

### Must Extend (Existing Code)
1. `create_default_registry()` to register VaspEngine
2. `species_map` handling for POTCAR references
3. Test utilities for VASP availability check

### Must Reuse (As-Is)
1. CalculationRunner, JobExecutor
2. Manifest, History, Locking
3. Structure I/O (pymatgen)
4. Resource management (ULID, resolution)
5. Project layout conventions

---

*Document generated for VASP integration planning. See companion documents for VASP specs and implementation plan.*

