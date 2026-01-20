# CP2K Minimal Step Type Specification

**Last reviewed**: 2025-01-19
**CP2K version target**: 2025.1
**QMatSuite version**: v2-python branch

---

## 1. Machine Step Types

### 1.1 Step Type Summary

| Machine Type | Public Type | Engine | Executable | Description |
|--------------|-------------|--------|------------|-------------|
| `cp2k_scf` | `scf` | cp2k | cp2k.ssmp | Single-point energy/forces |
| `cp2k_relax` | `relax` | cp2k | cp2k.ssmp | Geometry optimization |
| `cp2k_md` | `md` | cp2k | cp2k.ssmp | Molecular dynamics |

### 1.2 Generalized Step Type Mapping

Per QMatSuite constitution, public "relax" is the only structure-transformer type:

| Public Type | Behavior | Structure Transform? |
|-------------|----------|----------------------|
| `scf` | Electronic ground state | No |
| `relax` | Structure optimization | **Yes** |
| `md` | Dynamics trajectory | No (trajectory, not single structure) |

---

## 2. Step Type Definitions

### 2.1 cp2k_scf

**Purpose**: Single-point energy and force calculation.

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
    produces_charge_density=False,  # Produces .wfn, not charge density
    supports_incremental_skip=True,
),
```

**Required Parameters**:
```yaml
parameters:
  # Method settings
  method: Quickstep    # or FIST for classical, QMMM for hybrid
  functional: PBE      # XC functional
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE

  # Grid settings
  cutoff: 300          # Ry, plane wave cutoff
  rel_cutoff: 60       # Ry, relative cutoff

  # SCF settings
  eps_scf: 1.0E-6      # SCF convergence threshold
  max_scf: 100         # Max SCF iterations
```

**Optional Parameters**:
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

---

### 2.2 cp2k_relax

**Purpose**: Geometry optimization (atomic positions, optionally cell).

**CP2K RUN_TYPE**: `GEO_OPT` or `CELL_OPT`

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
    is_structure_transform=True,  # Key: produces structure artifact
    supports_incremental_skip=True,
),
```

**Required Parameters**:
```yaml
parameters:
  # DFT settings (same as cp2k_scf)
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE
  cutoff: 300
  rel_cutoff: 60
  eps_scf: 1.0E-6

  # Optimization settings
  optimizer: BFGS       # CG, BFGS, LBFGS
  max_iter: 200         # Max optimization steps
  max_force: 4.5E-4     # Hartree/Bohr, force convergence
  max_dr: 3.0E-3        # Bohr, displacement convergence
```

**Optional Parameters**:
```yaml
parameters:
  # Cell optimization
  optimize_cell: false   # If true, use CELL_OPT
  cell_opt_type: DIRECT_CELL_OPT  # or GEO_OPT, MD
  keep_angles: false
  keep_symmetry: false
  pressure_tolerance: 100  # bar

  # Restart
  restart_from: "01HYABCD..."  # ULID of previous step
```

**Structure Artifact Output**:
```
cp2k_calc-pos-1.xyz  # Last frame = optimized structure
```

---

### 2.3 cp2k_md

**Purpose**: Molecular dynamics simulation.

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
    supports_incremental_skip=False,  # MD is inherently non-idempotent
),
```

**Required Parameters**:
```yaml
parameters:
  # DFT settings
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE
  cutoff: 300
  rel_cutoff: 60
  eps_scf: 1.0E-6

  # MD settings
  ensemble: NVT         # NVE, NVT, NPT_F, NPT_I
  timestep: 0.5         # fs
  steps: 1000           # Number of MD steps
  temperature: 300      # K
```

**Optional Parameters**:
```yaml
parameters:
  # Thermostat (for NVT/NPT)
  thermostat: NOSE      # NOSE, CSVR, GLE
  thermostat_region: MASSIVE
  thermostat_timecon: 100  # fs

  # Barostat (for NPT)
  barostat: ISOTROPIC
  pressure: 1.0         # bar
  barostat_timecon: 1000  # fs

  # Output frequency
  trajectory_freq: 1     # Write positions every N steps
  energy_freq: 1         # Write energies every N steps
  restart_freq: 100      # Write restart every N steps

  # Restart
  restart_from: "01HYABCD..."  # ULID of previous MD step
```

---

## 3. Example step.yaml Files

### 3.1 cp2k_scf Example

```yaml
# steps/01HYAAAA123456789012.step.yaml
id: 01HYAAAA123456789012
step_type: cp2k_scf
name: silicon_scf

parameters:
  # DFT method
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE

  # Grid
  cutoff: 400
  rel_cutoff: 60

  # SCF
  eps_scf: 1.0E-7
  max_scf: 150

  # Smearing (silicon is semiconductor, but use for safety)
  smearing:
    method: FERMI_DIRAC
    electronic_temperature: 300
    added_mos: 4
```

### 3.2 cp2k_relax Example

```yaml
# steps/01HYBBBB123456789012.step.yaml
id: 01HYBBBB123456789012
step_type: cp2k_relax
name: silicon_relax

parameters:
  # DFT method
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE

  # Grid
  cutoff: 400
  rel_cutoff: 60
  eps_scf: 1.0E-7

  # Optimizer
  optimizer: BFGS
  max_iter: 100
  max_force: 1.0E-4
  max_dr: 1.0E-3
  rms_force: 5.0E-5
  rms_dr: 5.0E-4

  # Cell optimization (optional)
  optimize_cell: true
  cell_opt_type: DIRECT_CELL_OPT
```

### 3.3 cp2k_md Example

```yaml
# steps/01HYCCCC123456789012.step.yaml
id: 01HYCCCC123456789012
step_type: cp2k_md
name: silicon_nvt

parameters:
  # DFT method
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE
  cutoff: 300
  rel_cutoff: 60
  eps_scf: 1.0E-6

  # MD settings
  ensemble: NVT
  timestep: 1.0
  steps: 5000
  temperature: 500

  # Thermostat
  thermostat: CSVR
  thermostat_timecon: 50

  # Output
  trajectory_freq: 10
  energy_freq: 1
  restart_freq: 500
```

### 3.4 cp2k_md with Restart Example

```yaml
# steps/01HYDDDD123456789012.step.yaml
id: 01HYDDDD123456789012
step_type: cp2k_md
name: silicon_nvt_continued

parameters:
  # Reference previous step
  restart_from: "01HYCCCC123456789012"

  # DFT settings (must match previous)
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE
  cutoff: 300
  rel_cutoff: 60
  eps_scf: 1.0E-6

  # Continue MD
  ensemble: NVT
  timestep: 1.0
  steps: 5000  # Additional steps
  temperature: 500
  thermostat: CSVR
  thermostat_timecon: 50
```

### 3.5 cp2k_scf with Scan Example

```yaml
# steps/01HYEEEE123456789012.step.yaml
id: 01HYEEEE123456789012
step_type: cp2k_scf
name: cutoff_convergence

parameters:
  method: Quickstep
  functional: PBE
  basis_set: DZVP-MOLOPT-SR-GTH
  potential: GTH-PBE

  # Scanned parameter
  cutoff: "@scan:cutoff_test"
  rel_cutoff: 60
  eps_scf: 1.0E-6

parameter_scan:
  cutoff_test:
    values: [200, 300, 400, 500, 600]
```

---

## 4. Parameter Materialization

### 4.1 step.yaml → CP2K .inp Mapping

| step.yaml Path | CP2K Section | CP2K Keyword |
|----------------|--------------|--------------|
| `method` | `&FORCE_EVAL` | `METHOD` |
| `functional` | `&XC/&XC_FUNCTIONAL` | Subsection name |
| `basis_set` | `&KIND` | `BASIS_SET` |
| `potential` | `&KIND` | `POTENTIAL` |
| `cutoff` | `&MGRID` | `CUTOFF` |
| `rel_cutoff` | `&MGRID` | `REL_CUTOFF` |
| `eps_scf` | `&SCF` | `EPS_SCF` |
| `max_scf` | `&SCF` | `MAX_SCF` |
| `optimizer` | `&GEO_OPT` | `OPTIMIZER` |
| `max_iter` | `&GEO_OPT` | `MAX_ITER` |
| `max_force` | `&GEO_OPT` | `MAX_FORCE` |
| `ensemble` | `&MD` | `ENSEMBLE` |
| `timestep` | `&MD` | `TIMESTEP` |
| `steps` | `&MD` | `STEPS` |
| `temperature` | `&MD` | `TEMPERATURE` |

### 4.2 Runtime-Injected Keys

These are managed by the engine, not specified in step.yaml:

| Key | Value | Purpose |
|-----|-------|---------|
| `PROJECT` | `cp2k_calc` | Predictable output naming |
| `RUN_TYPE` | Derived from step_type | Execution mode |
| `RESTART_FILE_NAME` | Resolved path | If `restart_from` specified |
| `WFN_RESTART_FILE_NAME` | Resolved path | For SCF restart guess |

---

## 5. Engine Preset Support

### 5.1 Supported Preset Dimensions

For CP2K engine (to be defined in engine class):

```python
@property
def supported_presets(self) -> list[str]:
    return ["cp2k_precision"]  # Future: cp2k_functional, cp2k_basis
```

### 5.2 Preset Example (Future Work)

```yaml
# CP2K precision preset (not implemented in v0)
presets:
  cp2k_precision:
    low:
      cutoff: 200
      rel_cutoff: 40
      eps_scf: 1.0E-5
    medium:
      cutoff: 400
      rel_cutoff: 60
      eps_scf: 1.0E-6
    high:
      cutoff: 600
      rel_cutoff: 80
      eps_scf: 1.0E-7
```

---

## 6. Validation Rules

### 6.1 Required Field Validation

| Step Type | Required Fields |
|-----------|-----------------|
| `cp2k_scf` | method, functional, basis_set, potential, cutoff |
| `cp2k_relax` | Same as scf + optimizer, max_iter |
| `cp2k_md` | Same as scf + ensemble, timestep, steps, temperature |

### 6.2 Value Constraints

| Parameter | Type | Constraint |
|-----------|------|------------|
| `cutoff` | float | > 0, typical 100-1000 Ry |
| `rel_cutoff` | float | > 0, typical 40-80 Ry |
| `eps_scf` | float | > 0, typical 1E-4 to 1E-8 |
| `max_scf` | int | > 0, typical 50-500 |
| `timestep` | float | > 0, typical 0.5-2.0 fs |
| `steps` | int | > 0 |
| `temperature` | float | > 0, Kelvin |
| `ensemble` | str | NVE, NVT, NPT_F, NPT_I |
| `optimizer` | str | CG, BFGS, LBFGS |

### 6.3 Cross-Parameter Validation

1. **NPT requires barostat**: If `ensemble` is NPT_*, `barostat` settings should be present.
2. **NVT requires thermostat**: If `ensemble` is NVT, `thermostat` settings should be present.
3. **Cell optimization requires cell**: If `optimize_cell: true`, structure must have cell vectors.
