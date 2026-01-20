# CP2K Workflows and Multi-Step Patterns

**Last reviewed**: 2025-01-19
**CP2K version target**: 2025.1
**Sources consulted**:
- [CP2K Restarting Guide](https://www.cp2k.org/restarting)
- [CP2K pwtools Restart Guide](https://elcorto.github.io/pwtools/written/cp2k_restart.html)
- [CP2K Geometry Optimization Tutorial](https://www.cp2k.org/exercises:2018_uzh_cmest:geometry_optimization)
- [CP2K CECAM Optimization Protocol](https://www.cp2k.org/_media/events:2015_cecam_tutorial:watkins_optimization.pdf)

---

## 1. Overview: Workflow Patterns in CP2K

CP2K workflows typically involve chaining multiple calculations where each step builds on the previous one's results. The primary state-transfer mechanisms are:

1. **Wavefunction restart** (`.wfn` files) - Electronic state
2. **Geometry restart** (`.restart` files) - Atomic positions/velocities
3. **File inheritance** - Explicitly referencing output files from previous steps

---

## 2. Common Scientific Workflows

### 2.1 Convergence Testing Workflow

**Purpose**: Establish reliable numerical parameters before production runs.

**Steps**:
1. **Cutoff convergence**: Vary `CUTOFF` (200, 300, 400, 500 Ry) with fixed basis
2. **Basis set convergence**: Test different basis sets (SZV, DZVP, TZVP, TZV2P)
3. **k-point convergence** (for periodic): Vary k-mesh density
4. **SCF convergence threshold**: Test `EPS_SCF` values

**File Flow**:
```
cutoff_200/PROJECT-RESTART.wfn  →  (compare energies)
cutoff_300/PROJECT-RESTART.wfn  →  (compare energies)
cutoff_400/PROJECT-RESTART.wfn  →  (compare energies)
...
→ Select optimal parameters for production
```

**QMatSuite Mapping**: This maps to **parameter scans** - multiple independent calculations varying a single parameter. Each is a separate job with no state dependency.

---

### 2.2 Geometry Optimization Workflow

**Purpose**: Find minimum energy structure.

**Steps**:
1. **SCF single-point** (optional pre-equilibration)
2. **GEO_OPT** with coarse convergence
3. **GEO_OPT** with tight convergence (restart from step 2)

**File Flow**:
```
step1_scf/
  PROJECT-RESTART.wfn           →  step2 (wavefunction guess)

step2_geo_coarse/
  PROJECT.restart               →  step3 (geometry + wfn)
  PROJECT-RESTART.wfn
  PROJECT-pos-1.xyz             →  (trajectory)

step3_geo_tight/
  PROJECT.restart               →  final result
  PROJECT-RESTART.wfn
  PROJECT-pos-1.xyz
```

**Restart Mechanism**:
```
! In step3 input:
&EXT_RESTART
  RESTART_FILE_NAME ../step2_geo_coarse/PROJECT.restart
&END EXT_RESTART

&FORCE_EVAL
  &DFT
    &SCF
      SCF_GUESS RESTART
      WFN_RESTART_FILE_NAME ../step2_geo_coarse/PROJECT-RESTART.wfn
    &END SCF
  &END DFT
&END FORCE_EVAL
```

**QMatSuite Mapping**:
- Step 1 (SCF): `cp2k_scf`
- Steps 2-3 (GEO_OPT): `cp2k_relax` with `restart_from` reference

---

### 2.3 Equilibration → Production MD Workflow

**Purpose**: Prepare system and run production dynamics.

**Steps**:
1. **Energy minimization** (GEO_OPT) - Remove bad contacts
2. **NVT equilibration** - Reach target temperature
3. **NPT equilibration** - Reach target pressure/density (optional)
4. **Production run** - Data collection (NVE or NVT)

**File Flow**:
```
step1_minimize/
  PROJECT.restart               →  step2
  PROJECT-RESTART.wfn

step2_nvt_equil/
  PROJECT-1.restart             →  step3 (periodic snapshots)
  PROJECT-RESTART.wfn
  PROJECT-pos-1.xyz
  PROJECT-1.ener

step3_npt_equil/
  PROJECT-1.restart             →  step4
  PROJECT-RESTART.wfn
  PROJECT-pos-1.xyz
  PROJECT-1.cell

step4_production/
  PROJECT-1.restart             →  (for continuation)
  PROJECT-pos-1.xyz             →  analysis
  PROJECT-1.ener                →  analysis
```

**Restart Mechanism for MD**:
```
&MOTION
  &MD
    ENSEMBLE NVT
    STEPS 10000
    TIMESTEP 0.5
    TEMPERATURE 300
  &END MD
&END MOTION

&EXT_RESTART
  RESTART_FILE_NAME ../step2_nvt_equil/PROJECT-1.restart
  RESTART_POS .TRUE.
  RESTART_VEL .TRUE.
  RESTART_THERMOSTAT .TRUE.
&END EXT_RESTART
```

**QMatSuite Mapping**:
- Step 1: `cp2k_relax`
- Steps 2-4: `cp2k_md` with `restart_from` references

---

### 2.4 Relaxation → Electronic Properties Workflow

**Purpose**: Calculate electronic structure of optimized geometry.

**Steps**:
1. **GEO_OPT** - Optimize structure
2. **ENERGY** with dense k-mesh - Calculate DOS/bands

**File Flow**:
```
step1_relax/
  PROJECT-pos-1.xyz             →  step2 (final geometry)
  PROJECT-RESTART.wfn           →  step2 (wfn guess)

step2_electronic/
  PROJECT.pdos                  →  analysis
  BANDSTRUCTURE output          →  analysis
```

**Note**: Step 2 uses the **final geometry** from step 1, not the restart file. The wavefunction can optionally be used as initial guess.

**QMatSuite Mapping**:
- Step 1: `cp2k_relax`
- Step 2: `cp2k_scf` with structure artifact from step 1

---

## 3. Are CP2K Steps Naturally Independent?

**Answer: No, CP2K steps are NOT naturally independent.**

CP2K steps are coupled through:

### 3.1 State Dependencies

| Artifact | Purpose | Passed Forward |
|----------|---------|----------------|
| `.restart` | Full state (positions, velocities, cell, wfn ref) | Yes, for continuations |
| `-RESTART.wfn` | Wavefunction (electronic state) | Yes, for SCF guess |
| `-pos-*.xyz` | Trajectory (final geometry) | Yes, for new calculations |
| `-1.cell` | Cell evolution | Yes, for cell-dependent runs |
| `.Hessian` | BFGS Hessian | Yes, for optimizer restart |

### 3.2 Dependency Patterns

**Strong Dependency** (must run sequentially):
- MD continuation (requires restart file with positions + velocities)
- GEO_OPT restart (requires restart file with geometry + Hessian)

**Weak Dependency** (can be parallelized with care):
- Wavefunction-only restart (only needs `.wfn` file)
- Geometry-only restart (can extract coordinates and run fresh SCF)

### 3.3 Artifact Passing Requirements

For QMatSuite integration, the following artifacts must be explicitly managed:

1. **For MD continuation**: `PROJECT-*.restart` (includes positions, velocities, thermostat state)
2. **For GEO_OPT continuation**: `PROJECT.restart` (includes geometry, optimizer state)
3. **For SCF restart**: `PROJECT-RESTART.wfn` (wavefunction for initial guess)
4. **For structure extraction**: `PROJECT-pos-*.xyz` (final/trajectory geometry)

---

## 4. Restart File Behavior

### 4.1 Automatic Restart File Generation

CP2K automatically generates restart files during runs:

| File Pattern | When Generated | Contains |
|--------------|----------------|----------|
| `PROJECT.restart` | Each optimization step | Full input + current state |
| `PROJECT-1.restart` | Every N MD steps | Snapshot for continuation |
| `PROJECT-RESTART.wfn` | Each SCF convergence | Wavefunctions |
| `PROJECT-RESTART.wfn.bak-1` | Backup of previous | Safety backup |

### 4.2 Using Restart Files

**Method 1: EXT_RESTART Section**
```
&EXT_RESTART
  RESTART_FILE_NAME PROJECT.restart
  RESTART_DEFAULT_EACH SECTION OFF
  RESTART_POS .TRUE.
  RESTART_VEL .FALSE.   ! Positions only, reset velocities
&END EXT_RESTART
```

**Method 2: Direct Use as Input**
```bash
cp2k.ssmp PROJECT.restart -o output.log
```
The `.restart` file IS a valid input file with all parameters set.

**Method 3: Wavefunction-Only Restart**
```
&FORCE_EVAL
  &DFT
    &SCF
      SCF_GUESS RESTART
      WFN_RESTART_FILE_NAME path/to/PROJECT-RESTART.wfn
    &END SCF
  &END DFT
&END FORCE_EVAL
```

### 4.3 Selective Restart Flags

```
&EXT_RESTART
  RESTART_POS .TRUE.           ! Atomic positions
  RESTART_VEL .TRUE.           ! Velocities
  RESTART_CELL .TRUE.          ! Cell vectors
  RESTART_THERMOSTAT .TRUE.    ! Thermostat state
  RESTART_BAROSTAT .TRUE.      ! Barostat state
  RESTART_RANDOMG .TRUE.       ! Random number state
&END EXT_RESTART
```

---

## 5. QMatSuite Workflow Mapping

### 5.1 Step Type → RUN_TYPE Mapping

| QMatSuite Step | CP2K RUN_TYPE | State Input | State Output |
|----------------|---------------|-------------|--------------|
| `cp2k_scf` | ENERGY_FORCE | Structure | `.wfn` |
| `cp2k_relax` | GEO_OPT | Structure, optional `.wfn` | `.restart`, `.wfn`, final `.xyz` |
| `cp2k_md` | MD | Structure OR `.restart` | `.restart`, `.wfn`, trajectory |

### 5.2 Restart Artifact References

Following QMatSuite's `restart_from` pattern (like LAMMPS):

```yaml
# cp2k_md step with restart
step_type: cp2k_md
parameters:
  restart_from: "01HYABCD..."  # ULID of previous step
  ensemble: nvt
  timestep: 0.5
  steps: 10000
```

The engine must:
1. Look up the referenced step's working directory
2. Find the appropriate restart file (`.restart` for MD, final `.xyz` for fresh calculations)
3. Generate input with `EXT_RESTART` section or embedded coordinates

### 5.3 Structure Transformer Pattern

`cp2k_relax` is a **structure transformer** (like QE relax):
- Input: Initial structure
- Output: Optimized structure artifact
- The optimized structure should be extractable as a new structure resource

---

## 6. Summary: Key Integration Points

1. **Single .inp file per job**: CP2K runs are monolithic; each job is one `.inp` invocation.

2. **Restart files carry state**: MD continuations require `.restart` files; GEO_OPT can use `.restart` or wavefunction.

3. **PROJECT naming is critical**: All output files use PROJECT prefix. QMatSuite must manage this consistently.

4. **Wavefunction restarts speed up SCF**: Always use `SCF_GUESS RESTART` with `.wfn` file when available.

5. **Structure extraction**: Final geometry from `PROJECT-pos-1.xyz` (last frame) or parse `.restart` file.

6. **MD checkpoints**: `PROJECT-*.restart` files provide safe restart points. Write frequency configurable via `MOTION/PRINT/RESTART/EACH`.
