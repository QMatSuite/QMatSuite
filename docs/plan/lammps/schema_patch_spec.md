# LAMMPS Schema Patch Specification

**Version**: 1.0.0  
**Date**: 2026-01-20  
**Status**: Ready for Implementation  
**Constitution Reference**: §A (Parameters), §B (Assets)

---

## 1. Overview

This document specifies the YAML schema additions required for LAMMPS integration. All schemas follow QMatSuite's A-class/B-class parameter governance.

---

## 2. calculation.yaml Extensions

### 2.1 `potential_map` Schema (Scheme A: Potential Instance Keys)

```yaml
# calculation.yaml

# Engine declaration
engine: lammps

# Structure reference (ULID or path)
structure_id: "01HQABC..."

# === POTENTIAL MAP (NEW) ===
# Maps user-defined keys to potential definitions
# Key = user-friendly identifier, referenced in step.yaml
potential_map:
  <potential_key>:
    # Required fields
    style: <pair_style>         # LAMMPS pair_style name
    
    # File specification (choose one)
    file: <relative_path>       # Single file, relative to project root
    files:                      # Multiple files (MEAM, ReaxFF)
      - <relative_path>
      - <relative_path>
    
    # Optional fields
    elements: [<elem>, ...]     # Elements this potential covers
    cutoff: <float>             # Cutoff distance (for applicable styles)
    params:                     # Inline parameters (for simple potentials like lj/cut)
      <type_pair>: <values>
    source: <url>               # Provenance URL
    version: <string>           # Potential version
    notes: <string>             # User notes
```

### 2.2 `potential_map` Concrete Examples

#### Example 1: Simple EAM

```yaml
potential_map:
  eam_cu:
    style: eam
    file: potentials/Cu_u3.eam
    elements: [Cu]
    source: "https://www.ctcms.nist.gov/potentials/entry/..."
```

#### Example 2: EAM Alloy (multi-element)

```yaml
potential_map:
  eam_nialh:
    style: eam/alloy
    file: potentials/NiAlH_jea.eam.alloy
    elements: [Ni, Al, H]
```

#### Example 3: Tersoff

```yaml
potential_map:
  tersoff_sic:
    style: tersoff
    file: potentials/SiC.tersoff
    elements: [Si, C]
```

#### Example 4: ReaxFF (multi-file)

```yaml
potential_map:
  reaxff_cho:
    style: reaxff
    files:
      - potentials/ffield.reax.CHO
      - potentials/control.reax
    elements: [C, H, O]
```

#### Example 5: LJ/cut (inline params, no file)

```yaml
potential_map:
  lj_argon:
    style: lj/cut
    cutoff: 2.5
    params:
      "1 1": "1.0 1.0 2.5"  # epsilon sigma cutoff
    elements: [Ar]
```

#### Example 6: DeepMD

```yaml
potential_map:
  deepmd_si:
    style: deepmd
    file: potentials/dp_si.pb
    elements: [Si]
```

### 2.3 Validation Rules for `potential_map`

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `style` | string | Yes | Must be valid LAMMPS pair_style |
| `file` | string | Conditional | Required if style needs external file |
| `files` | list[string] | Conditional | For multi-file potentials |
| `elements` | list[string] | Recommended | Warn if missing |
| `cutoff` | float | Optional | Must be positive |
| `params` | dict | Conditional | For inline potentials (lj/cut, etc.) |
| `source` | string | Optional | URL format |
| `version` | string | Optional | Freeform |

**Mutual Exclusivity**: `file` and `files` are mutually exclusive.

**Element Coverage**: If `elements` specified, validate that structure elements are covered before materialize.

---

## 3. step.yaml Schema

### 3.1 Common A-Class Parameters (All LAMMPS Steps)

```yaml
# step.yaml base structure for LAMMPS

meta:
  id: <ulid>
  slug: <optional_name>
  created_at: <iso8601>

engine: lammps
step_type: lammps_minimize | lammps_md | lammps_restart

parameters:
  # === STRUCTURE ===
  structure: <ulid_or_ref>      # Required unless restart_from

  # === POTENTIAL ===
  potential: <potential_key>    # Key in calculation.yaml potential_map
  
  # === UNITS SYSTEM ===
  units: metal | real | lj      # Default: metal
  
  # === ATOM STYLE ===
  atom_style: atomic | charge | full | molecular  # Default: atomic
  
  # === OUTPUT CONTROL ===
  thermo_frequency: <int>       # Thermo output interval, default: 100
  dump_frequency: <int>         # Dump output interval, default: 1000
  dump_trajectory: <bool>       # Enable trajectory dump, default: true
  
  # === LJ SYSTEM (required if units=lj) ===
  lj_system:
    masses:
      <type_int>: <mass_float>  # e.g., 1: 1.0
    type_labels:                # Optional: human-readable labels
      <type_int>: <element>     # e.g., 1: "Ar"
  
  # === CUSTOM SCRIPT MODE ===
  custom_script:
    mode: override | extend     # override = full script; extend = inject
    content: |
      # User script content
    pre_run: |                  # For extend mode
      # Commands before run/minimize
    post_run: |                 # For extend mode
      # Commands after run/minimize
  
  assets:
    required_files:             # REQUIRED for custom_script mode
      - potentials/my_potential.eam
      - other_file.dat
  
  # === B-CLASS (engine_params) ===
  engine_params:
    lammps:
      # Arbitrary engine-specific params
      neighbor_skin: <float>
      extra_fixes: [<string>, ...]
      pair_style_suffix: <string>
```

### 3.2 `lammps_minimize` A-Class Parameters

```yaml
step_type: lammps_minimize

parameters:
  # Inherited common params...
  
  # === MINIMIZATION SPECIFIC ===
  energy_tolerance: <float>     # etol, default: 1.0e-6
  force_tolerance: <float>      # ftol, default: 1.0e-8
  max_iterations: <int>         # maxiter, default: 1000
  max_evaluations: <int>        # maxeval, default: 10000
  
  engine_params:
    lammps:
      min_style: cg | sd | fire | quickmin | hftn  # Default: cg
      box_relax: <bool>         # Allow cell relaxation
      box_relax_style: iso | aniso | tri  # Default: iso
      line_search: <string>     # Line search algorithm
```

### 3.3 `lammps_md` A-Class Parameters

```yaml
step_type: lammps_md

parameters:
  # Inherited common params...
  
  # === ENSEMBLE ===
  ensemble: nve | nvt | npt     # Required
  
  # === THERMODYNAMIC TARGETS ===
  temperature: <float>          # Target temperature in K (required for nvt/npt)
  pressure: <float>             # Target pressure in bar (required for npt)
  
  # === TIME INTEGRATION ===
  timestep_fs: <float>          # Timestep in CANONICAL fs (writer converts)
  n_steps: <int>                # Number of MD steps
  
  # === RESTART OUTPUT ===
  restart_frequency: <int>      # Restart file interval, default: 10000
  
  engine_params:
    lammps:
      thermostat: nose-hoover | langevin | csvr  # Default: nose-hoover
      thermostat_damp: <float>  # Damping in timestep units
      barostat: iso | aniso | tri  # For npt
      barostat_damp: <float>    # Damping in timestep units
      velocity_seed: <int>      # Random seed for velocity init
      velocity_dist: gaussian | uniform  # Default: gaussian
```

### 3.4 `lammps_restart` A-Class Parameters

```yaml
step_type: lammps_restart

parameters:
  # === RESTART SOURCE (REQUIRED) ===
  restart_from: <step_id>       # ULID or slug of upstream step (same calc only)
  
  # Inherited common params...
  # Note: structure is NOT required (read from restart)
  
  # === CONTINUATION ===
  n_steps: <int>                # Additional steps to run
  
  # Ensemble/temperature/pressure must match or be re-specified
  ensemble: nve | nvt | npt
  temperature: <float>
  pressure: <float>
  
  # Force field MUST be re-specified (not stored in restart)
  potential: <potential_key>
  units: <units>
  atom_style: <atom_style>
```

---

## 4. Units Conversion Table

### 4.1 Timestep Conversion

| YAML (canonical) | LAMMPS metal | LAMMPS real | LAMMPS lj |
|------------------|--------------|-------------|-----------|
| `timestep_fs: 1.0` | `timestep 0.001` (ps) | `timestep 1.0` (fs) | N/A (lj τ) |
| `timestep_fs: 2.0` | `timestep 0.002` (ps) | `timestep 2.0` (fs) | N/A |

**Conversion Formula**:
- metal: `lammps_timestep = timestep_fs / 1000`
- real: `lammps_timestep = timestep_fs`
- lj: Use `timestep_tau` (separate field, no fs conversion)

### 4.2 For `units=lj`

```yaml
parameters:
  units: lj
  timestep_tau: 0.005           # Use tau units directly, not fs
  lj_system:
    masses:
      1: 1.0                    # Reduced mass units
    type_labels:
      1: "Ar"
```

---

## 5. `lj_system` Schema (Required for units=lj)

```yaml
lj_system:
  # REQUIRED: Masses for each atom type
  masses:
    <type_int>: <mass_float>    # In LJ reduced units (m*)
    
  # OPTIONAL: Human-readable element labels
  type_labels:
    <type_int>: <element_symbol>
    
  # OPTIONAL: Reference values for unit conversion (if user wants physical output)
  reference:
    epsilon_eV: <float>         # ε in eV
    sigma_angstrom: <float>     # σ in Å
    mass_amu: <float>           # Reference mass in amu
```

### 5.1 Validation Rules

| Field | Required | Validation |
|-------|----------|------------|
| `masses` | Yes (if units=lj) | Must have entry for each atom type |
| `type_labels` | No | If present, must match masses keys |
| `reference` | No | Used for optional physical unit conversion |

### 5.2 Error Message

```python
if params.get("units") == "lj" and not params.get("lj_system", {}).get("masses"):
    raise ValueError(
        "units=lj requires explicit lj_system.masses. "
        "Specify mass for each atom type in reduced LJ units."
    )
```

---

## 6. `custom_script` Schema

### 6.1 Override Mode

Complete user script replaces template:

```yaml
parameters:
  custom_script:
    mode: override
    content: |
      # Full LAMMPS script
      units metal
      atom_style atomic
      boundary p p p
      
      read_data structure.data
      
      pair_style eam
      pair_coeff * * potentials/Cu_u3.eam Cu
      
      minimize 1e-6 1e-8 1000 10000
      
      write_data final.data
      
  assets:
    required_files:
      - potentials/Cu_u3.eam
```

**Behavior**:
- `structure.data` still generated by QMatSuite
- User must reference `structure.data` with correct path
- `assets.required_files` is **mandatory** - hard error if missing
- Script content hash included in step digest

### 6.2 Extend Mode

Inject custom commands into template:

```yaml
parameters:
  potential: eam_cu
  energy_tolerance: 1e-6
  
  custom_script:
    mode: extend
    pre_run: |
      # Before minimize command
      compute pe_atom all pe/atom
      dump pe_dump all custom 100 pe.dump id c_pe_atom
    post_run: |
      # After minimize command
      print "Optimization complete!"
```

**Behavior**:
- Template is used with normal param injection
- `pre_run` inserted before `minimize`/`run` command
- `post_run` inserted after `minimize`/`run` command

### 6.3 Validation Rules

| Mode | Requires `content` | Requires `assets.required_files` |
|------|-------------------|----------------------------------|
| override | Yes | Yes (hard error if missing) |
| extend | No (uses pre_run/post_run) | Only if referencing external files |

---

## 7. Schema Summary Table

### 7.1 A-Class Parameters (Physics-Affecting, Used in Digest)

| Parameter | Type | Default | Step Types | Notes |
|-----------|------|---------|------------|-------|
| `structure` | ULID/ref | - | minimize, md | Not for restart |
| `potential` | key | - | All | References potential_map |
| `units` | enum | "metal" | All | metal/real/lj |
| `atom_style` | enum | "atomic" | All | atomic/charge/full/molecular |
| `ensemble` | enum | - | md, restart | nve/nvt/npt |
| `temperature` | float | - | nvt, npt | Kelvin |
| `pressure` | float | - | npt | bar |
| `timestep_fs` | float | 1.0 | md, restart | Canonical fs |
| `n_steps` | int | - | md, restart | - |
| `energy_tolerance` | float | 1e-6 | minimize | etol |
| `force_tolerance` | float | 1e-8 | minimize | ftol |
| `max_iterations` | int | 1000 | minimize | - |
| `restart_from` | step_id | - | restart | Same calc only |

### 7.2 A-Class Parameters (Output Control, Used in Digest)

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `thermo_frequency` | int | 100 | - |
| `dump_frequency` | int | 1000 | - |
| `dump_trajectory` | bool | true | - |
| `restart_frequency` | int | 10000 | - |

### 7.3 B-Class Parameters (Engine-Specific, Under `engine_params.lammps`)

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `min_style` | string | "cg" | Minimizer algorithm |
| `box_relax` | bool | false | Cell optimization |
| `thermostat` | string | "nose-hoover" | - |
| `thermostat_damp` | float | 100.0 | In timestep units |
| `barostat` | string | "iso" | For npt |
| `velocity_seed` | int | random | - |
| `neighbor_skin` | float | 2.0 | Å |
| `extra_fixes` | list | [] | Raw LAMMPS fix commands |

---

## 8. Generated LAMMPS Commands

### 8.1 pair_style Block Generation

Given `potential_map` entry:

```yaml
potential_map:
  eam_cu:
    style: eam/alloy
    file: potentials/NiCu.eam.alloy
    elements: [Ni, Cu]
```

And structure with atom types `[Cu, Ni]` in that order:

Generated:
```bash
pair_style eam/alloy
pair_coeff * * potentials/NiCu.eam.alloy Cu Ni
```

**Note**: Element order in `pair_coeff` matches atom type order in data file.

### 8.2 Ensemble Fix Generation

For `ensemble: nvt`, `temperature: 300`, `thermostat_damp: 100`:

```bash
# metal units: damp in ps
fix thermostat all nvt temp 300 300 0.1
```

For `ensemble: npt`, `temperature: 300`, `pressure: 0`, `barostat: iso`:

```bash
fix thermostat all npt temp 300 300 0.1 iso 0 0 1.0
```

### 8.3 Dump Command Generation

Fixed fields per constitution:

```bash
dump traj all custom {dump_frequency} trajectory.lammpstrj id type x y z vx vy vz fx fy fz
dump_modify traj sort id
```

---

## 9. Digest Computation

### 9.1 Fields Included in Step Digest

```python
digest_input = {
    # Structure identity
    "structure_sha": structure_sha,
    
    # Potential identity (hash of staged file contents)
    "potential_assets_sha": potential_assets_sha,
    
    # A-class physics params
    "units": params["units"],
    "atom_style": params["atom_style"],
    "ensemble": params.get("ensemble"),
    "temperature": params.get("temperature"),
    "pressure": params.get("pressure"),
    "timestep_fs": params.get("timestep_fs"),
    "n_steps": params.get("n_steps"),
    "energy_tolerance": params.get("energy_tolerance"),
    "force_tolerance": params.get("force_tolerance"),
    
    # Custom script (if present)
    "custom_script_sha": compute_sha(custom_script_content) if custom_script else None,
    
    # lj_system (if units=lj)
    "lj_system_masses": params.get("lj_system", {}).get("masses"),
}
```

### 9.2 Fields NOT Included

- B-class `engine_params` (unless they affect physics)
- Output file hashes
- Engine version
- Timestamps
- Execution metrics

---

## 10. Example Complete calculation.yaml

```yaml
# calculation.yaml - LAMMPS NVT MD with EAM potential

meta:
  id: "01HQXYZ123456789ABCDEF"
  name: "copper_md_300K"
  created_at: "2026-01-20T10:30:00Z"

engine: lammps
structure_id: "01HQABC987654321FEDCBA"

potential_map:
  eam_cu:
    style: eam
    file: potentials/Cu_u3.eam
    elements: [Cu]
    source: "https://www.ctcms.nist.gov/potentials/..."

steps:
  - meta:
      id: "01HQSTEP1..."
      slug: "equilibrate"
    type: relax
    parameters:
      potential: eam_cu
      units: metal
      atom_style: atomic
      energy_tolerance: 1.0e-4
      force_tolerance: 1.0e-6
      thermo_frequency: 10
      
  - meta:
      id: "01HQSTEP2..."
      slug: "production_md"
    type: md
    parameters:
      potential: eam_cu
      restart_from: equilibrate
      units: metal
      atom_style: atomic
      ensemble: nvt
      temperature: 300
      timestep_fs: 1.0
      n_steps: 100000
      thermo_frequency: 100
      dump_frequency: 1000
      restart_frequency: 10000
      engine_params:
        lammps:
          thermostat: nose-hoover
          thermostat_damp: 100
          velocity_seed: 12345
```

