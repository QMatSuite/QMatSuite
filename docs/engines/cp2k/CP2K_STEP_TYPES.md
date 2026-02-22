# CP2K Step Types

**Version**: v2.0 (Alignment Update)
**Last Updated**: 2026-01-20
**CP2K Version**: 2025.1

---

## 1. Overview

This document defines the **machine step types** and **public step types** for CP2K integration with QMatSuite.

### 1.1 Naming Convention

| Type | Format | Example | Purpose |
|------|--------|---------|---------|
| **Machine Type** | `<engine>_<operation>` | `cp2k_scf` | Used in step.yaml `step_type` field |
| **Public Type** | `<operation>` | `scf` | Used in UI, workflow templates, APIs |

### 1.2 Minimal Step Type Set

For v0 integration, we define **three** step types:

| Machine Type | Public Type | CP2K RUN_TYPE |
|--------------|-------------|---------------|
| `cp2k_scf` | `scf` | `ENERGY_FORCE` |
| `cp2k_relax` | `relax` | `GEO_OPT` or `CELL_OPT` |
| `cp2k_md` | `md` | `MD` |

### 1.3 Key Alignment (v2 Update)

| Aspect | Policy |
|--------|--------|
| **MD Incremental Skip** | **DISABLED** for `cp2k_md` |
| **Cell Output** | **Enabled by default** for MD/relax (for trajectory cell info) |
| **Latest Selection** | mtime-based |
| **Runtime SSOT** | `raw/<step_ulid>/` only |

---

## 2. Step Type Definitions

### 2.1 `cp2k_scf` - Single-Point Calculation

**Purpose**: Electronic ground state calculation with energy and forces.

**CP2K RUN_TYPE**: `ENERGY_FORCE`

**Registry Entry**:
```python
"cp2k_scf": StepTypeSpec(
    id="scf",
    machine_type="cp2k_scf",
    public_type="scf",
    engine="cp2k",
    executable="cp2k.ssmp",
    description="CP2K single-point energy/force calculation (GPW/GAPW DFT)",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,  # Produces .wfn, not QE-style charge
    supports_incremental_skip=True,
    is_structure_transform=False,
),
```

**Expected Outputs**:
| Output | Path | Required |
|--------|------|----------|
| Main log | `output.log` | Yes |
| Wavefunction | `cp2k_calc-RESTART.wfn` | If WFN_RESTART enabled |

**Analysis Objects Produced**:
- `total_energy` (float, Hartree)
- `forces` (array, Hartree/Bohr)
- `stress` (optional, if enabled)

### 2.2 `cp2k_relax` - Geometry Optimization

**Purpose**: Optimize atomic positions (and optionally cell).

**CP2K RUN_TYPE**: `GEO_OPT` (positions) or `CELL_OPT` (positions + cell)

**Registry Entry**:
```python
"cp2k_relax": StepTypeSpec(
    id="relax",
    machine_type="cp2k_relax",
    public_type="relax",
    engine="cp2k",
    executable="cp2k.ssmp",
    description="CP2K geometry optimization (positions and/or cell)",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    supports_incremental_skip=True,
    is_structure_transform=True,  # KEY: produces structure artifact
),
```

**Expected Outputs**:
| Output | Path | Required |
|--------|------|----------|
| Main log | `output.log` | Yes |
| Trajectory | `cp2k_calc-pos-1.xyz` | Yes |
| Cell file | `cp2k_calc-1.cell` | **Yes (new)** - for cell info |
| Restart | `cp2k_calc.restart` or `cp2k_calc-N.restart` | Optional |
| Wavefunction | `cp2k_calc-RESTART.wfn` | Optional |

**Analysis Objects Produced**:
- `final_structure` (Structure) - extracted from last frame of trajectory + cell file
- `total_energy` (float, Hartree) - final energy
- `forces` (array) - final forces
- `optimization_history` (list) - energy/force per step

**Structure Artifact**:
This step produces a **structure artifact** at `generated_structures/step_<ulid>/current.json`:
```json
{
  "@class": "Structure",
  "lattice": { ... },
  "sites": [ ... ],
  "provenance": {
    "source_type": "cp2k_relax",
    "source_step_ulid": "01HY...",
    "run_id": "2026-01-20T..."
  }
}
```

### 2.3 `cp2k_md` - Molecular Dynamics

**Purpose**: Born-Oppenheimer molecular dynamics simulation.

**CP2K RUN_TYPE**: `MD`

**Registry Entry**:
```python
"cp2k_md": StepTypeSpec(
    id="md",
    machine_type="cp2k_md",
    public_type="md",
    engine="cp2k",
    executable="cp2k.ssmp",
    description="CP2K Born-Oppenheimer molecular dynamics",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    supports_incremental_skip=False,  # CRITICAL: MD is non-idempotent
    is_structure_transform=False,  # Produces trajectory, not single structure
),
```

**CRITICAL**: `supports_incremental_skip=False` - MD steps are **always executed** when targeted. Users can use `restart_policy` for continuation runs.

**Expected Outputs**:
| Output | Path | Required |
|--------|------|----------|
| Main log | `output.log` | Yes |
| Trajectory | `cp2k_calc-pos-1.xyz` | Yes |
| Energy file | `cp2k_calc-1.ener` | Yes |
| Cell file | `cp2k_calc-1.cell` | **Yes (for NPT)** / Optional (NVT/NVE) |
| Restart | `cp2k_calc-1.restart` | Optional (for continuation) |
| Velocity | `cp2k_calc-vel-1.xyz` | Optional |

**Analysis Objects Produced**:
- `trajectory` (Trajectory) - full position trajectory with cell info
- `energy_series` (list) - energy vs time
- `temperature_series` (list) - temperature vs time
- `conserved_quantity` (list) - conserved quantity vs time

---

## 3. GEN → SPEC Mapping

### 3.1 MATERIALIZATION_MAP Entries

Add to `src/qmatsuite/workflow/generalized_steps.py`:

```python
# CP2K family mappings
("cp2k", "SCF"): "cp2k_scf",
("cp2k", "RELAX"): "cp2k_relax",
("cp2k", "MD"): "cp2k_md",
```

### 3.2 Mapping Behavior

| Generalized Step | CP2K Machine Type | Notes |
|------------------|-------------------|-------|
| `SCF` | `cp2k_scf` | Single-point |
| `RELAX` | `cp2k_relax` | GEO_OPT (cell opt via parameter) |
| `VC_RELAX` | `cp2k_relax` | Same, with `optimize_cell: true` |
| `MD` | `cp2k_md` | All ensembles |
| `VC_MD` | `cp2k_md` | NPT via parameter |
| `NSCF` | N/A | Not applicable for CP2K model |
| `BANDS` | Future | Phase 2+ |
| `DOS` | Future | Phase 2+ |

---

## 4. Step Parameters

### 4.1 Common Parameters (All Step Types)

```yaml
parameters:
  # Method
  method: Quickstep           # Quickstep (DFT), FIST (classical), QMMM

  # DFT settings
  functional: PBE             # XC functional
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE

  # Grid settings
  cutoff: 400                 # Ry
  rel_cutoff: 60              # Ry

  # SCF settings
  eps_scf: 1.0E-6
  max_scf: 100

  # Data files (optional - relies on CP2K_DATA_DIR if not specified)
  basis_set_file_name: BASIS_MOLOPT
  potential_file_name: GTH_POTENTIALS

  # Restart policy (B-class, user-controlled)
  restart_policy:
    use_restart: false        # Use predecessor's .restart file
    use_wfn_guess: true       # Use predecessor's .wfn for SCF_GUESS
```

### 4.2 cp2k_scf Specific Parameters

```yaml
parameters:
  # Smearing (for metals)
  smearing:
    method: FERMI_DIRAC
    electronic_temperature: 300  # K
    added_mos: 10

  # Mixing
  mixing:
    method: BROYDEN_MIXING
    alpha: 0.4

  # Output control
  print_forces: true
  print_stress: false
```

### 4.3 cp2k_relax Specific Parameters

```yaml
parameters:
  # Optimizer
  optimizer: BFGS              # CG, BFGS, LBFGS
  max_iter: 200
  max_force: 4.5E-4            # Hartree/Bohr
  max_dr: 3.0E-3               # Bohr
  rms_force: 2.0E-4
  rms_dr: 1.0E-3

  # Cell optimization (optional)
  optimize_cell: false         # If true, use CELL_OPT RUN_TYPE
  cell_opt_type: DIRECT_CELL_OPT
  keep_angles: false
  keep_symmetry: false
  pressure_tolerance: 100      # bar

  # Cell output (for structure extraction)
  print_cell: true             # DEFAULT ON - needed for final structure
```

### 4.4 cp2k_md Specific Parameters

```yaml
parameters:
  # MD settings
  ensemble: NVT                # NVE, NVT, NPT_F, NPT_I
  timestep: 0.5                # fs
  steps: 5000
  temperature: 300             # K

  # Thermostat (for NVT/NPT)
  thermostat: NOSE             # NOSE, CSVR, GLE
  thermostat_region: MASSIVE
  thermostat_timecon: 100      # fs

  # Barostat (for NPT)
  barostat: ISOTROPIC
  pressure: 1.0                # bar
  barostat_timecon: 1000       # fs

  # Output frequency
  trajectory_freq: 1           # Write positions every N steps
  energy_freq: 1               # Write energies every N steps
  restart_freq: 100            # Write restart every N steps
  cell_freq: 1                 # Write cell every N steps (for NPT)
```

---

## 5. Example step.yaml Files

### 5.1 cp2k_scf Example

```yaml
# steps/01HYAAAA123456789012.step.yaml
meta:
  id: 01HYAAAA123456789012
  name: silicon_scf
step_type: cp2k_scf

parameters:
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE-q4
  cutoff: 400
  rel_cutoff: 60
  eps_scf: 1.0E-7
  max_scf: 150
  smearing:
    method: FERMI_DIRAC
    electronic_temperature: 300
    added_mos: 4
```

### 5.2 cp2k_relax Example

```yaml
# steps/01HYBBBB123456789012.step.yaml
meta:
  id: 01HYBBBB123456789012
  name: silicon_relax
step_type: cp2k_relax

parameters:
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE-q4
  cutoff: 400
  rel_cutoff: 60
  eps_scf: 1.0E-7

  optimizer: BFGS
  max_iter: 100
  max_force: 1.0E-4
  max_dr: 1.0E-3
  rms_force: 5.0E-5
  rms_dr: 5.0E-4

  # Cell optimization
  optimize_cell: true
  cell_opt_type: DIRECT_CELL_OPT

  # Enable cell output for structure extraction
  print_cell: true

  # Restart from previous SCF (if running after scf step)
  restart_policy:
    use_wfn_guess: true
```

### 5.3 cp2k_md Example

```yaml
# steps/01HYCCCC123456789012.step.yaml
meta:
  id: 01HYCCCC123456789012
  name: silicon_nvt
step_type: cp2k_md

parameters:
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE-q4
  cutoff: 300
  rel_cutoff: 60
  eps_scf: 1.0E-6

  ensemble: NVT
  timestep: 1.0
  steps: 5000
  temperature: 500

  thermostat: CSVR
  thermostat_timecon: 50

  trajectory_freq: 10
  energy_freq: 1
  restart_freq: 500
```

### 5.4 cp2k_md NPT Example (with cell output)

```yaml
# steps/01HYDDDD123456789012.step.yaml
meta:
  id: 01HYDDDD123456789012
  name: silicon_npt
step_type: cp2k_md

parameters:
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE-q4
  cutoff: 300
  rel_cutoff: 60
  eps_scf: 1.0E-6

  ensemble: NPT_F
  timestep: 1.0
  steps: 10000
  temperature: 300

  thermostat: CSVR
  thermostat_timecon: 50

  barostat: ISOTROPIC
  pressure: 1.0
  barostat_timecon: 500

  trajectory_freq: 10
  energy_freq: 1
  restart_freq: 1000
  cell_freq: 1              # IMPORTANT: Track cell evolution
```

### 5.5 cp2k_scf with Scan Example

```yaml
# steps/01HYEEEE123456789012.step.yaml
meta:
  id: 01HYEEEE123456789012
  name: cutoff_convergence
step_type: cp2k_scf

parameters:
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE-q4

  cutoff: "@scan:cutoff_scan"  # Scanned parameter
  rel_cutoff: 60
  eps_scf: 1.0E-6

parameter_scan:
  cutoff_scan:
    values: [200, 300, 400, 500, 600]
```

---

## 6. Trajectory AnalysisObject

### 6.1 CP2K Trajectory Schema

```python
@dataclass
class CP2KTrajectory:
    """
    Trajectory parsed from CP2K output.

    Attributes:
        frames: List of structure snapshots
        energies: List of energies (Hartree) per frame
        iterations: List of iteration numbers
        times: List of simulation times (fs) - for MD only
        temperatures: List of temperatures (K) - for MD only
        cells: List of cell matrices - from .cell file if available
        source_file: Path to source XYZ file
        has_cell_evolution: Whether cell varies over trajectory
    """
    frames: List[Structure]
    energies: List[float]
    iterations: List[int]
    times: Optional[List[float]] = None
    temperatures: Optional[List[float]] = None
    cells: Optional[List[np.ndarray]] = None  # NEW: from .cell file
    source_file: Optional[Path] = None
    has_cell_evolution: bool = False  # NEW: track if cell varies
```

### 6.2 Parsing Logic

```python
def parse_cp2k_trajectory(
    xyz_path: Path,
    ener_path: Optional[Path] = None,
    cell_path: Optional[Path] = None,
    initial_structure: Optional[Structure] = None,
) -> CP2KTrajectory:
    """
    Parse CP2K trajectory from XYZ, optional .ener file, and optional .cell file.

    Args:
        xyz_path: Path to cp2k_calc-pos-N.xyz
        ener_path: Optional path to cp2k_calc-N.ener (for MD)
        cell_path: Optional path to cp2k_calc-N.cell (for cell evolution)
        initial_structure: Fallback structure for cell if no cell file

    Returns:
        CP2KTrajectory with all frames and metadata.
    """
    frames = []
    energies = []
    iterations = []

    # Parse XYZ file
    with open(xyz_path) as f:
        while True:
            # Read atom count
            line = f.readline()
            if not line:
                break
            n_atoms = int(line.strip())

            # Read comment line: " i =        5, E =      -17.12345678"
            comment = f.readline()
            meta = parse_cp2k_xyz_comment(comment)
            iterations.append(meta.get("iteration", len(frames)))
            energies.append(meta.get("energy", 0.0))

            # Read coordinates
            coords = []
            species = []
            for _ in range(n_atoms):
                parts = f.readline().split()
                species.append(parts[0])
                coords.append([float(x) for x in parts[1:4]])

            frames.append({"species": species, "coords": coords})

    # Parse cell file if available
    cells = None
    has_cell_evolution = False
    if cell_path and cell_path.exists():
        cell_data = parse_cp2k_cell(cell_path)
        if cell_data:
            cells = [
                np.array([d["A"], d["B"], d["C"]])
                for d in cell_data
            ]
            has_cell_evolution = True

    # Parse energy file if available (has more columns)
    times = None
    temperatures = None
    if ener_path and ener_path.exists():
        ener_data = parse_cp2k_ener(ener_path)
        times = [d["time_fs"] for d in ener_data]
        temperatures = [d["temp_K"] for d in ener_data]

    # Build structures with cell info
    structures = []
    for i, frame in enumerate(frames):
        if cells and i < len(cells):
            lattice = Lattice(cells[i])
        elif initial_structure:
            lattice = initial_structure.lattice
        else:
            raise ValueError(f"No cell information for frame {i}")

        structures.append(Structure(
            lattice,
            frame["species"],
            frame["coords"],
            coords_are_cartesian=True,
        ))

    return CP2KTrajectory(
        frames=structures,
        energies=energies,
        iterations=iterations,
        times=times,
        temperatures=temperatures,
        cells=cells,
        source_file=xyz_path,
        has_cell_evolution=has_cell_evolution,
    )
```

---

## 7. Registry Integration Summary

### 7.1 Files to Modify

| File | Change |
|------|--------|
| `src/qmatsuite/workflow/registry.py` | Add `cp2k_scf`, `cp2k_relax`, `cp2k_md` to `_STEP_TYPES` |
| `src/qmatsuite/workflow/generalized_steps.py` | Add `("cp2k", ...)` entries to `MATERIALIZATION_MAP` |
| `src/qmatsuite/execution/recipes.py` | Add `CP2KRecipe` class, update `get_recipe_for_engine()` |
| `src/qmatsuite/execution/handlers.py` | Add `cp2k_step_handler()`, update `create_handler_map()` |

### 7.2 Preflight Requirements by Step Type

| Step Type | Preflight Requirements |
|-----------|------------------------|
| `cp2k_scf` | None (first step OK) or wfn if `restart_policy.use_wfn_guess` |
| `cp2k_relax` | wfn if `restart_policy.use_wfn_guess`, restart if `restart_policy.use_restart` |
| `cp2k_md` | wfn if `restart_policy.use_wfn_guess`, restart if `restart_policy.use_restart` |

### 7.3 Step Type Token (Future)

If CP2K supports QC-style chains in the future, add token mapping:
```python
PUBLIC_TYPE_TOKENS = {
    # Existing...
    "cp2k_scf": "c",  # Future: CP2K chain support
}
```

For now, CP2K is step-by-step (no subchains), so no token needed.
