# LAMMPS Integration Design

**Version**: 1.0.0  
**Date**: 2026-01-19  
**Status**: Research & Design Phase  
**Constitution Reference**: §A (Parameters), §B (Assets), §C (Engine Registry), §D (Manifest)

---

## 1. Design Goals

1. **Fit into existing architecture**: LAMMPS becomes an engine family parallel to `qe`, `vasp`, `orca`, `pyscf`
2. **Respect SSOT principles**: `calculation.yaml` + `step.yaml` remain the single source of truth
3. **Reuse existing abstractions**: Leverage manifest, digest, asset staging, trajectory parsing patterns
4. **Minimize core changes**: Prefer engine-level implementation over core modifications
5. **Template-first approach**: Generate input scripts from templates; allow advanced user overrides

---

## 2. Engine Registration

### 2.1 Engine Family Definition

```python
# In src/quantumvitas/engine/lammps_engine.py

class LammpsEngine(Engine):
    """LAMMPS classical molecular dynamics engine."""
    
    name = "lammps"
    
    @property
    def supported_presets(self) -> list[str]:
        """
        LAMMPS supports classical simulation presets.
        
        Note: Does not support DFT-specific dimensions like 'precision' or 'magnetism'.
        """
        return ["classical_ensemble", "potential_type"]
```

### 2.2 Registry Integration

```python
# In src/quantumvitas/engine/registry.py

def create_default_registry(...) -> EngineRegistry:
    ...
    if include_lammps:
        registry.register(LammpsEngine())
    return registry
```

---

## 3. Step Types

### 3.1 GEN → SPEC Mapping

| GEN Step Type | LAMMPS SPEC Type | QE SPEC | VASP SPEC | Notes |
|---------------|------------------|---------|-----------|-------|
| `minimize_classical` | `lammps_minimize` | N/A | N/A | Classical only |
| `relax_classical` | `lammps_minimize` | N/A | N/A | Alias |
| `md` | `lammps_md` | N/A | N/A | Unified MD type |
| `restart_md` | `lammps_restart` | N/A | N/A | Continuation |

### 3.2 Workflow Registry Entry

```python
# In src/quantumvitas/workflow/registry.py

StepTypeSpec(
    name="lammps_minimize",
    engine="lammps",
    public_type="minimize_classical",
    description="Classical energy minimization using LAMMPS",
    category="classical",
    requires_potential=True,
    produces_trajectory=True,
),
StepTypeSpec(
    name="lammps_md",
    engine="lammps",
    public_type="md",
    description="Molecular dynamics simulation using LAMMPS",
    category="classical",
    requires_potential=True,
    produces_trajectory=True,
),
```

---

## 4. Parameter Organization in step.yaml

### 4.1 A-Class Parameters (QMatSuite Owned)

These parameters are strictly typed, validated, and used in digest computation:

```yaml
# step.yaml for LAMMPS minimize
meta:
  id: "01HQXYZ..."
  slug: "minimize-cu"

engine: lammps
step_type: lammps_minimize

# A-Class: QMatSuite-owned keys
parameters:
  # Structure reference (ULID or slug)
  structure: "01HQABC..."
  
  # Potential reference (from potential_map)
  potential: "eam_cu"
  
  # Units system (affects all numeric values)
  units: "metal"  # metal | real | lj
  
  # Atom style (must match potential requirements)
  atom_style: "atomic"  # atomic | charge | full | molecular
  
  # Minimization parameters
  energy_tolerance: 1.0e-6
  force_tolerance: 1.0e-8
  max_iterations: 1000
  max_evaluations: 10000
  
  # Output control
  thermo_frequency: 10
  dump_trajectory: true
  dump_frequency: 100
```

### 4.2 B-Class Parameters (Engine-Specific)

Free-form parameters passed through to input script generation:

```yaml
# step.yaml continued
  
  # B-Class: Engine-specific free keys
  engine_params:
    lammps:
      # Minimizer style
      min_style: "cg"  # cg | sd | fire | quickmin
      
      # Box relaxation
      box_relax: false
      box_relax_style: "iso"  # iso | aniso | tri
      
      # Neighbor list settings
      neighbor_skin: 2.0
      neighbor_delay: 5
      
      # Additional fix commands (raw LAMMPS syntax)
      extra_fixes:
        - "fix freeze frozen setforce 0.0 0.0 0.0"
      
      # Custom pair_style options
      pair_style_suffix: "/kk"  # For Kokkos acceleration
```

### 4.3 MD-Specific Parameters

```yaml
# step.yaml for LAMMPS MD
parameters:
  structure: "01HQABC..."
  potential: "eam_cu"
  units: "metal"
  atom_style: "atomic"
  
  # Ensemble
  ensemble: "nvt"  # nve | nvt | npt
  
  # Thermodynamic targets
  temperature: 300.0  # K
  pressure: 0.0  # bar (for npt only)
  
  # Time integration
  timestep: 0.001  # ps for metal units
  n_steps: 100000
  
  # Output
  thermo_frequency: 100
  dump_frequency: 1000
  dump_fields:
    - id
    - type
    - xu
    - yu
    - zu
    - vx
    - vy
    - vz
  
  # Restart
  restart_frequency: 10000
  
  engine_params:
    lammps:
      thermostat: "nose-hoover"  # nose-hoover | langevin
      thermostat_damp: 100.0  # damping in timestep units
      barostat: "iso"  # iso | aniso | tri (for npt)
      barostat_damp: 1000.0
      velocity_seed: 12345
```

---

## 5. Materialize Phase

### 5.1 Products

Materialize writes to `calc/raw/<step_ulid>/`:

```
calc/raw/<step_ulid>/
├── in.lammps               # Generated input script
├── structure.data          # LAMMPS data file
├── potentials/             # Staged potential files
│   ├── Cu_u3.eam          # Only needed files
│   └── ...
└── .meta/
    └── materialize.json    # Materialize metadata
```

### 5.2 Input Script Generation

**Strategy: Template + Parameter Injection**

```python
def materialize_lammps_input(
    step: Step,
    working_dir: Path,
    calculation: Calculation,
) -> None:
    """Generate LAMMPS input files from step specification."""
    
    working_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Convert structure to LAMMPS data format
    structure = load_structure(calculation, step.parameters["structure"])
    write_lammps_data(structure, working_dir / "structure.data")
    
    # 2. Stage potential files
    stage_potentials(
        calculation=calculation,
        potential_ref=step.parameters["potential"],
        target_dir=working_dir / "potentials",
    )
    
    # 3. Generate input script from template
    template = get_lammps_template(step.step_type)
    script = template.render(
        step=step,
        calculation=calculation,
        potentials_dir="potentials",
    )
    
    (working_dir / "in.lammps").write_text(script)
```

### 5.3 Structure Conversion

Convert QMatSuite structure to LAMMPS data format:

```python
def write_lammps_data(structure: Structure, path: Path) -> None:
    """
    Write structure in LAMMPS data file format.
    
    Handles:
    - Atom positions (unwrapped Cartesian)
    - Box dimensions (with tilt factors if needed)
    - Atom types (sequential integers)
    - Masses
    """
    ...
```

---

## 6. Run Phase

### 6.1 Binary Discovery

```python
def resolve_lammps_bin(variant: str = "mpi") -> Path:
    """
    Resolve LAMMPS binary path.
    
    Search order:
    1. QMATS_LAMMPS_BIN environment variable
    2. Project-local: .qmatsuite/engines/lammps/bin/lmp_*
    3. Homebrew: /opt/homebrew/opt/lammps/bin/lmp_*
    4. Conda: $CONDA_PREFIX/bin/lmp_*
    5. System PATH: lmp_mpi, lmp_serial, lmp
    """
    ...
```

### 6.2 Execution

```python
def run_lammps_step(
    step: Step,
    working_dir: Path,
) -> StepResult:
    """Execute LAMMPS step."""
    
    lmp_bin = resolve_lammps_bin()
    
    # Build command
    cmd = [str(lmp_bin)]
    
    # Input script
    cmd.extend(["-in", "in.lammps"])
    
    # Log file (explicit, for consistent naming)
    cmd.extend(["-log", "log.lammps"])
    
    # Screen output control
    cmd.extend(["-screen", "none"])
    
    # Run
    result = subprocess.run(
        cmd,
        cwd=working_dir,
        capture_output=True,
        text=True,
    )
    
    return StepResult(
        step_type=step.step_type,
        input_file=working_dir / "in.lammps",
        success=result.returncode == 0,
        output_file=working_dir / "log.lammps",
        return_code=result.returncode,
    )
```

### 6.3 Output File Naming Convention

| File | Purpose | Naming |
|------|---------|--------|
| Input script | Input | `in.lammps` |
| Log | Thermo + diagnostics | `log.lammps` |
| Trajectory | Atomic positions | `trajectory.lammpstrj` |
| Restart | Checkpoint | `restart.*.bin` |
| Final structure | Output | `final.data` |

---

## 7. Outputs Collection

### 7.1 Standard Artifacts

After successful run, collect:

```python
LAMMPS_ARTIFACTS = {
    "log": "log.lammps",
    "trajectory": "trajectory.lammpstrj",  # or dump.*
    "final_structure": "final.data",
    "restart": "restart.*.bin",  # glob pattern
}
```

### 7.2 Parsing Priority

1. **Log file** (`log.lammps`) - Always parse for thermo time series
2. **Trajectory dump** - Parse for atomic trajectories if exists
3. **Final structure** - Parse for relaxed geometry
4. **Restart files** - Note presence for continuation capability

---

## 8. Manifest and Digest

### 8.1 Step Digest Composition

```python
def compute_lammps_step_digest(
    structure_sha: str,
    potential_assets_sha: str,
    step_params: dict,
) -> str:
    """
    Compute step digest for skip determination.
    
    Includes:
    - structure_sha: Hash of input structure
    - potential_assets_sha: Hash of staged potential file contents
    - step_params: A-class parameters that affect results
    
    Excludes:
    - Output file hashes (per constitution)
    - B-class parameters that don't affect physics
    - Engine version (tracked in provenance, not skip logic)
    """
    digest_input = {
        "structure": structure_sha,
        "potentials": potential_assets_sha,
        "units": step_params["units"],
        "atom_style": step_params["atom_style"],
        "ensemble": step_params.get("ensemble"),
        "temperature": step_params.get("temperature"),
        "pressure": step_params.get("pressure"),
        "n_steps": step_params.get("n_steps"),
        "timestep": step_params.get("timestep"),
        # ... other physics-affecting parameters
    }
    return compute_sha256(canonical_json(digest_input))
```

### 8.2 Manifest Entry

```python
ManifestStepEntry(
    kind="lammps_md",
    step_ulid="01HQXYZ...",
    pseudo_set_sha="",  # Not applicable for LAMMPS
    potential_assets_sha="abc123...",  # NEW: For classical potentials
    structure_sha="def456...",
    step_sha="ghi789...",
    done=True,
    ...
)
```

---

## 9. Template vs User Script

### 9.1 Default: Template-Based Generation

For standard workflows, QMatSuite generates the input script from templates:

```
step.yaml (parameters) 
    ↓
Template Engine (Jinja2)
    ↓
in.lammps (generated)
```

Templates live in `resources/calculation_templates/lammps/`:
- `minimize.in.j2`
- `md_nvt.in.j2`
- `md_npt.in.j2`
- `restart.in.j2`

### 9.2 Advanced: User Script Override

Power users can provide a complete custom script:

```yaml
# step.yaml with custom script
parameters:
  structure: "01HQABC..."
  potential: "eam_cu"
  
  # Custom script mode
  custom_script:
    mode: "override"  # override | extend
    script: |
      # User-provided LAMMPS script
      units metal
      atom_style atomic
      ...
```

**When `custom_script.mode == "override"`**:
- The entire user script is written as-is
- `structure` parameter still used for `structure.data` generation
- `potential` still used for asset staging
- **The script content hash is included in step_sha**

### 9.3 Hybrid: Script Extension

```yaml
custom_script:
  mode: "extend"
  pre_run: |
    # Commands inserted before run/minimize
    compute myStress all stress/atom NULL
  post_run: |
    # Commands inserted after run/minimize
    write_dump all custom final_stress.dump id c_myStress[*]
```

---

## 10. Scan/Parameter Sweep

### 10.1 Scannable Parameters

Following existing scan patterns, LAMMPS steps support parameter sweeps:

```yaml
# calculation.yaml with scan
steps:
  - type: lammps_md
    parameters:
      structure: "01HQABC..."
      potential: "eam_cu"
      ensemble: "nvt"
      temperature: "{scan:temperature}"  # Scan token
      n_steps: 100000
      
scan:
  temperature:
    type: linspace
    start: 100
    stop: 500
    count: 5
```

### 10.2 Scan Digest Behavior

Each scan variant produces a unique step_sha:
- Base parameters + scan value → unique digest
- Consistent with existing QE/VASP scan behavior
- No special handling needed beyond existing infrastructure

---

## 11. Lock Semantics

Existing lock mechanism applies:

| Lock | Purpose | Behavior |
|------|---------|----------|
| `run.lock` | Prevent concurrent execution | Created before run, removed after |
| `edit.lock` | Prevent modification during run | Prevents parameter changes |

No LAMMPS-specific lock requirements.

---

## 12. Error Handling

### 12.1 Materialize Errors

| Error | Cause | Action |
|-------|-------|--------|
| `MissingPotentialError` | Potential not in potential_map | Hard fail with configuration guidance |
| `StructureConversionError` | Cannot convert to LAMMPS data | Hard fail with format details |
| `TemplateError` | Invalid template parameters | Hard fail with parameter info |

### 12.2 Run Errors

| Error | Detection | Action |
|-------|-----------|--------|
| Binary not found | FileNotFoundError | Engine discovery error |
| LAMMPS runtime error | Non-zero return code | Parse log for error message |
| Missing output | Expected files absent | Mark step failed |

---

## 13. Engine Discovery

### 13.1 Discovery Protocol

```python
def discover_lammps() -> Optional[LammpsEngineInfo]:
    """
    Discover LAMMPS installation and capabilities.
    
    Returns:
        LammpsEngineInfo with:
        - binary_path: Path to lmp executable
        - version: LAMMPS version string
        - packages: List of compiled-in packages
        - accelerators: Available accelerators (gpu, kokkos, etc.)
    """
    bin_path = resolve_lammps_bin()
    
    # Get version and packages
    result = subprocess.run(
        [str(bin_path), "-h", "packages"],
        capture_output=True,
        text=True,
    )
    
    # Parse output for package list
    packages = parse_lammps_packages(result.stdout)
    
    return LammpsEngineInfo(
        binary_path=bin_path,
        version=parse_lammps_version(result.stdout),
        packages=packages,
        accelerators=detect_accelerators(packages),
    )
```

### 13.2 Self-Test

Use standard benchmark input for validation:

```python
def self_test_lammps(lmp_info: LammpsEngineInfo) -> bool:
    """
    Run minimal LAMMPS test to verify installation.
    
    Uses: /opt/homebrew/opt/lammps/share/lammps/bench/in.lj
    """
    ...
```

---

## 14. Integration Checklist

| Component | Status | Notes |
|-----------|--------|-------|
| Engine class | 📝 Design | `LammpsEngine` |
| Binary discovery | 📝 Design | Multi-source resolution |
| Template system | 📝 Design | Jinja2 templates |
| Structure I/O | 📝 Design | LAMMPS data format |
| Potential staging | 📝 Design | See assets_and_potentials.md |
| Log parsing | 📝 Design | Thermo extraction |
| Trajectory parsing | 📝 Design | See output_parsing.md |
| Manifest integration | 📝 Design | potential_assets_sha |
| Registry entry | 📝 Design | Step types |
| Scan support | ✅ Reuse | Existing infrastructure |
| Lock support | ✅ Reuse | Existing infrastructure |

