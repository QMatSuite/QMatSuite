# QMatSuite Codebase Review Notes for LAMMPS Integration

**Version**: 1.0.0  
**Date**: 2026-01-19  
**Status**: Research & Design Phase

---

## 1. Engine Integration Lifecycle Review

### 1.1 Engine Discovery Pattern

**Location**: `src/quantumvitas/core/engines/`

| File | Purpose | LAMMPS Relevance |
|------|---------|------------------|
| `base.py` | Abstract `Engine` class, `EngineConfig` | Template for `LammpsEngine` |
| `vasp_resolver.py` | VASP binary resolution | Template for `lammps_resolver.py` |
| `qe_resolver.py` | QE binary resolution | Alternative pattern reference |
| `qe_binary_locator.py` | QE path finding | Search strategy reference |

**Current Pattern:**
```python
def resolve_vasp_bin(variant: str = "std") -> Path:
    """
    Search order:
    1. Environment variable
    2. Project-local engines dir
    3. System PATH
    """
```

**LAMMPS Implementation:**
- Follow same search order
- Check for `lmp_mpi`, `lmp_serial`, `lmp` variants
- Parse `lmp -h packages` for capability detection

---

### 1.2 Materialize Pattern

**Location**: `src/quantumvitas/engine/`

| File | Purpose | LAMMPS Relevance |
|------|---------|------------------|
| `vasp_engine.py` | VASP materialize_inputs() | Direct template |
| `vasp_writer.py` | POSCAR/INCAR/KPOINTS/POTCAR writers | Need LAMMPS data writer |

**VASP Pattern:**
```python
def materialize_inputs(self, step, working_dir, calculation):
    write_poscar(structure, working_dir / "POSCAR")
    write_incar(params, working_dir / "INCAR")
    write_kpoints(params, working_dir / "KPOINTS")
    write_potcar(structure, species_map, working_dir / "POTCAR")
```

**LAMMPS Analog:**
```python
def materialize_inputs(self, step, working_dir, calculation):
    write_lammps_data(structure, working_dir / "structure.data")
    stage_potentials(potential_map, working_dir / "potentials")
    generate_input_script(step, working_dir / "in.lammps")
```

---

### 1.3 Run Pattern

**Location**: `src/quantumvitas/calculation/runner.py`

**Key Method**: `CalculationRunner.run()`

**Flow:**
1. Pseudo/asset preparation (Step0)
2. Manifest reconciliation
3. JobGraph execution via `_execute_with_jobgraph()`
4. Per-step: materialize → execute → parse → update manifest

**LAMMPS Hooks:**
- Engine family detection via `_get_engine_family_from_step()`
- Recipe selection via `get_recipe_for_engine(engine_family)`
- Handler creation via `create_handler_map()`

---

### 1.4 JobGraph Execution

**Location**: `src/quantumvitas/execution/`

| File | Purpose | LAMMPS Relevance |
|------|---------|------------------|
| `job_graph.py` | Job DAG representation | Reuse for LAMMPS steps |
| `executor.py` | Job execution logic | Add LAMMPS handler |
| `handlers.py` | Per-engine execution handlers | Add `LammpsHandler` |
| `recipes.py` | Step → Job materialization | Add LAMMPS recipe |

**Handler Pattern:**
```python
class LammpsHandler(EngineHandler):
    def execute(self, job: Job, context: dict) -> JobResult:
        # 1. Materialize inputs
        self.engine.materialize_inputs(...)
        
        # 2. Run LAMMPS binary
        result = self.engine.run_step(...)
        
        # 3. Parse outputs
        artifacts = parse_lammps_outputs(...)
        
        return JobResult(success=result.success, ...)
```

---

## 2. Asset Management Review

### 2.1 Pseudopotential System

**Location**: `src/quantumvitas/core/`

| File | Purpose | LAMMPS Parallel |
|------|---------|-----------------|
| `pseudo.py` | `ensure_qe_pseudos()` main entry | `ensure_lammps_potentials()` |
| `pseudo_runtime.py` | Runtime pseudo staging | Runtime potential staging |
| `pseudo_config.py` | Pseudo configuration | Potential configuration |
| `pseudo_materialization.py` | Copy to raw/ | Copy potentials to raw/ |

**QE Pattern:**
```python
def ensure_qe_pseudos(
    qe_input_file: Path,
    project_pseudo_dir: Path,
    species_map: Dict[str, Dict[str, Any]],
) -> PseudoResolutionResult:
    # 1. Determine required pseudos from species_map
    # 2. Search: project_pseudo_dir → system_pseudo_dir → download
    # 3. Stage to project_pseudo_dir
    # 4. Return digest
```

**LAMMPS Analog:**
- No QE input file parsing needed
- Get potential refs from step parameters
- Stage specified potential files to working dir
- Compute digest for skip logic

---

### 2.2 Species Map Structure

**Current Structure (QE):**
```yaml
species_map:
  Si:
    pseudo_basename: "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
    mass: 28.085
  O:
    pseudo_basename: "O.pbe-n-rrkjus_psl.1.0.0.UPF"
    mass: 15.999
```

**Proposed LAMMPS Structure:**
```yaml
potential_map:
  eam_cu:
    type: eam
    style: eam
    file: "potentials/Cu_u3.eam"
    elements: [Cu]
```

**Key Difference:** 
- QE: One-to-one element→pseudo mapping
- LAMMPS: One potential may cover multiple elements

---

## 3. Manifest System Review

### 3.1 Manifest Structure

**Location**: `src/quantumvitas/calculation/manifest.py`

**Current Schema:**
```python
@dataclass
class ManifestStepEntry:
    kind: str                    # Step type
    step_ulid: str               # Step ID
    pseudo_set_sha: str          # Pseudo digest
    structure_sha: str           # Structure digest
    step_sha: str                # Step params digest
    effective_structure_sha: Optional[str] = None
    run_id: Optional[str] = None
    done: bool = False
    started_at: Optional[str] = None
    done_at: Optional[str] = None
```

**LAMMPS Need:**
Add `potential_assets_sha: Optional[str] = None`

**Skip Logic** (`should_skip_step()`):
```python
def should_skip_step(entry, current_kind, pseudo_sha, struct_sha, step_sha):
    return (
        entry.kind == current_kind and
        entry.pseudo_set_sha == pseudo_sha and  # or potential_assets_sha
        entry.structure_sha == struct_sha and
        entry.step_sha == step_sha and
        entry.done == True
    )
```

---

### 3.2 Digest Computation

**Location**: `src/quantumvitas/calculation/hash_utils.py`

**Functions:**
- `compute_pseudo_set_sha()` - Hash pseudo files
- `compute_structure_sha()` - Hash structure JSON
- `compute_step_sha()` - Hash step YAML

**LAMMPS Needs:**
```python
def compute_potential_assets_sha(
    potential_files: List[Path],
) -> str:
    """Compute deterministic hash of potential files."""
```

---

## 4. Trajectory/Analysis Review

### 4.1 Trajectory Specification

**Location**: `docs/specs/TRAJECTORY_CORE.md`, `docs/specs/ANALYSIS_OBJECTS_FRAMEWORK.md`

**Canonical Frame:**
```python
@dataclass
class Frame:
    frame_index: int
    positions: NDArray[np.float64]  # (N, 3), Å
    species: List[str]
    cell: NDArray[np.float64]       # (3, 3), Å
    pbc: Tuple[bool, bool, bool]
    
    # Optional
    time: Optional[float]           # fs
    velocities: Optional[NDArray]   # Å/fs
    forces: Optional[NDArray]       # eV/Å
    energy: Optional[float]         # eV
    temperature: Optional[float]    # K
    pressure: Optional[float]       # GPa
```

**LAMMPS Mapping:**
- All fields mappable from dump + log
- Units conversion required (metal → canonical)

---

### 4.2 Parser Structure

**Location**: `src/quantumvitas/parsers/`

**Current:**
```
parsers/
├── __init__.py
├── registry.py
└── qe/
    └── output_parser.py
```

**Add for LAMMPS:**
```
parsers/
├── lammps/
│   ├── __init__.py
│   ├── log_parser.py      # Thermo extraction
│   ├── dump_parser.py     # Trajectory extraction
│   ├── data_parser.py     # Structure parsing
│   └── units.py           # Unit conversion
```

---

## 5. Workflow Registry Review

### 5.1 Step Type Registration

**Location**: `src/quantumvitas/workflow/registry.py`

**Current Pattern:**
```python
STEP_TYPE_SPECS = [
    StepTypeSpec(
        name="qe_scf",
        engine="qe",
        public_type="scf",
        ...
    ),
    StepTypeSpec(
        name="vasp_scf",
        engine="vasp",
        public_type="scf",
        ...
    ),
]
```

**Add LAMMPS:**
```python
StepTypeSpec(
    name="lammps_minimize",
    engine="lammps",
    public_type="minimize_classical",
    description="Classical energy minimization",
    category="classical",
),
StepTypeSpec(
    name="lammps_md",
    engine="lammps",
    public_type="md",
    description="Molecular dynamics simulation",
    category="classical",
),
```

---

## 6. Key Files for LAMMPS Implementation

### 6.1 Files to Create (New)

| Path | Purpose |
|------|---------|
| `src/quantumvitas/engine/lammps_engine.py` | Main engine class |
| `src/quantumvitas/core/engines/lammps_resolver.py` | Binary discovery |
| `src/quantumvitas/io/lammps/` | Data file I/O |
| `src/quantumvitas/parsers/lammps/` | Output parsers |
| `resources/calculation_templates/lammps/` | Input templates |

### 6.2 Files to Modify (Minimal)

| Path | Change |
|------|--------|
| `src/quantumvitas/engine/registry.py` | Register LammpsEngine |
| `src/quantumvitas/workflow/registry.py` | Add step types |
| `src/quantumvitas/calculation/manifest.py` | Add potential_assets_sha |
| `src/quantumvitas/execution/handlers.py` | Add LammpsHandler |
| `src/quantumvitas/execution/recipes.py` | Add LAMMPS recipe |

---

## 7. Potential Pitfalls & Recommendations

### 7.1 Units Complexity

**Issue:** LAMMPS has multiple unit systems; QMatSuite assumes canonical units.

**Recommendation:**
- Parse `units` from step parameters
- Convert ALL values during parsing (not on read)
- Store canonical units in trajectory
- Document conversion in provenance

### 7.2 Template vs Script Freedom

**Issue:** Power users want full script control; MVP needs templates.

**Recommendation:**
- Default: Template-based generation
- Optional: `custom_script` override in step params
- If custom: Include script content in step_sha

### 7.3 Multi-Element Potentials

**Issue:** One EAM file may define Cu-Ni-Al; `species_map` is one-to-one.

**Recommendation:**
- `potential_map` is potential-centric, not element-centric
- Validation: Check structure elements ⊆ potential.elements
- pair_coeff: Generate correct element ordering

### 7.4 Restart File Binary Format

**Issue:** Restart files are platform-dependent binary.

**Recommendation:**
- Don't parse restart files directly
- For structure extraction: Use LAMMPS `restart2data`
- For continuation: Just reference file path

### 7.5 Package Availability

**Issue:** Not all LAMMPS builds have all packages.

**Recommendation:**
- Engine discovery: Detect available packages
- Validation: Check required packages before run
- Clear error: "ReaxFF requires REAXFF package"

---

## 8. Code Quality Observations

### 8.1 Good Patterns to Follow

- **Separation of Concerns**: Engine classes handle execution, parsers handle output
- **SSOT Discipline**: All truth from YAML, no input file parsing
- **Digest-based Skip**: Clean, deterministic, no output hashing

### 8.2 Patterns to Avoid

- **Hardcoded Paths**: Use resolvers with configurable search paths
- **Implicit State**: Everything explicit in step params
- **Parse-and-Merge**: Never parse old inputs to get parameters

