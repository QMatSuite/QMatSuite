# CP2K Capabilities and Input Model

**Last reviewed**: 2025-01-19
**CP2K version target**: 2025.1
**Sources consulted**:
- [CP2K Official Manual](https://manual.cp2k.org/trunk/)
- [CP2K GitHub Repository](https://github.com/cp2k/cp2k)
- [CP2K Wikipedia](https://en.wikipedia.org/wiki/CP2K)
- [CP2K Journal Publication (JCP 2020)](https://pubs.aip.org/aip/jcp/article/152/19/194103/199081/CP2K-An-electronic-structure-and-molecular)
- [CP2K Static Calculation Tutorial](https://www.cp2k.org/howto:static_calculation)
- [CP2K Geometry Optimization Exercises](https://www.cp2k.org/exercises:2016_uzh_cmest:geometry_optimization)

---

## 1. What CP2K Is (High-Level)

CP2K is an open-source quantum chemistry and solid-state physics software package designed for atomistic simulations of solid-state, liquid, molecular, periodic, crystal, and biological systems. It is written in Fortran 2008 and can run efficiently in parallel using multi-threading (OpenMP), MPI, and GPU acceleration (CUDA, HIP/ROCm, OpenCL).

**Core Method**: CP2K is best known for its Quickstep module, which implements Kohn-Sham Density Functional Theory (DFT) using the Gaussian and Plane Waves (GPW) method and its all-electron variant, the Gaussian and Augmented Plane Waves (GAPW) method. This hybrid approach combines localized Gaussian basis sets (for wavefunctions) with plane wave auxiliary basis sets (for electron density), enabling efficient calculations on large periodic systems.

**Key Distinguishing Features**:
- Mixed Gaussian and plane waves (GPW/GAPW) approach
- Efficient linear-scaling methods for very large systems
- Strong MD capabilities (Born-Oppenheimer, Ehrenfest, PIMD)
- QM/MM support
- Support for GTH pseudopotentials and all-electron calculations

---

## 2. CP2K Input Model

### 2.1 Single Input File Structure

CP2K uses a **single `.inp` input file** with a hierarchical section-based structure. Sections are delimited by `&SECTION_NAME` and `&END SECTION_NAME` tags.

```
&GLOBAL
  PROJECT project_name
  RUN_TYPE ENERGY_FORCE
  PRINT_LEVEL MEDIUM
&END GLOBAL

&FORCE_EVAL
  METHOD Quickstep
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    POTENTIAL_FILE_NAME GTH_POTENTIALS
    &QS
      EPS_DEFAULT 1.0E-12
    &END QS
    &MGRID
      CUTOFF 300
      REL_CUTOFF 60
    &END MGRID
    &XC
      &XC_FUNCTIONAL PADE
      &END XC_FUNCTIONAL
    &END XC
    &SCF
      SCF_GUESS ATOMIC
      EPS_SCF 1.0E-6
      MAX_SCF 100
      &DIAGONALIZATION ON
        ALGORITHM STANDARD
      &END DIAGONALIZATION
      &MIXING
        METHOD BROYDEN_MIXING
        ALPHA 0.4
      &END MIXING
    &END SCF
  &END DFT
  &SUBSYS
    &CELL
      ABC 10.0 10.0 10.0
    &END CELL
    &COORD
      Si 0.0 0.0 0.0
      Si 2.5 2.5 0.0
    &END COORD
    &KIND Si
      ELEMENT Si
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PADE-q4
    &END KIND
  &END SUBSYS
&END FORCE_EVAL
```

### 2.2 Main Section Hierarchy

| Section | Purpose | Subsections |
|---------|---------|-------------|
| **GLOBAL** | Run parameters, project name, run type | PROJECT, RUN_TYPE, PRINT_LEVEL |
| **FORCE_EVAL** | Energy/force evaluation method | METHOD, DFT, SUBSYS, PROPERTIES |
| **SUBSYS** | System definition (cell, atoms) | CELL, COORD, KIND, TOPOLOGY |
| **DFT** | DFT-specific settings | QS, MGRID, XC, SCF, PRINT |
| **MOTION** | Geometry/cell optimization, MD | GEO_OPT, CELL_OPT, MD, PRINT |
| **EXT_RESTART** | External restart file reference | RESTART_FILE_NAME, RESTART_* flags |

### 2.3 Include Mechanism

CP2K supports file includes via the `@INCLUDE` directive:

```
@INCLUDE common_settings.inc
```

However, QMatSuite should generate **self-contained input files** without includes to ensure reproducibility and avoid external dependencies.

---

## 3. Physical Tasks (Ordered by Complexity)

### 3.1 Single-Point Energy/Forces (Easiest)

**RUN_TYPE**: `ENERGY` or `ENERGY_FORCE`

**Required Inputs**:
- Structure (cell, coordinates)
- Basis set (e.g., `DZVP-MOLOPT-SR-GTH`)
- Pseudopotential (e.g., `GTH-PADE-q4`)
- Exchange-correlation functional

**Key Knobs**:
- `CUTOFF` (plane wave cutoff, Ry)
- `REL_CUTOFF` (relative cutoff)
- `EPS_SCF` (SCF convergence threshold)
- `EPS_DEFAULT` (default accuracy)

**Typical Outputs**:
- Total energy (Hartree)
- Forces on atoms (Hartree/Bohr)
- Stress tensor (if requested)
- Wavefunction restart file (`-RESTART.wfn`)

**Restart Artifacts**: `PROJECT-RESTART.wfn`

**Source**: [CP2K Static Calculation Tutorial](https://www.cp2k.org/howto:static_calculation)

---

### 3.2 Geometry Optimization (GEO_OPT)

**RUN_TYPE**: `GEO_OPT`

**Required Inputs**: Same as single-point + optimizer settings

**Key Knobs** (in `MOTION/GEO_OPT`):
- `OPTIMIZER` (CG, BFGS, LBFGS)
- `MAX_ITER` (max optimization steps)
- `MAX_FORCE` (force convergence, Hartree/Bohr)
- `MAX_DR` (displacement convergence, Bohr)
- `RMS_FORCE`, `RMS_DR` (RMS convergence)

**Typical Outputs**:
- Optimized structure (`.xyz` trajectory)
- Energy convergence
- Final forces
- Hessian (if BFGS)

**Restart Artifacts**:
- `PROJECT.restart` (full restart file)
- `PROJECT-RESTART.wfn` (wavefunction)
- `PROJECT-BFGS.Hessian` (if BFGS optimizer)

**Source**: [CP2K Geometry Optimisation Guide](https://manual.cp2k.org/trunk/methods/optimization/geometry.html)

---

### 3.3 Cell Optimization (CELL_OPT)

**RUN_TYPE**: `CELL_OPT`

**Required Inputs**: Same as GEO_OPT + cell optimization settings

**Key Knobs** (in `MOTION/CELL_OPT`):
- `TYPE` (GEO_OPT, MD, DIRECT_CELL_OPT)
- `PRESSURE_TOLERANCE` (GPa)
- `KEEP_ANGLES` (fix cell angles)
- `KEEP_SYMMETRY` (preserve symmetry)

**Typical Outputs**:
- Optimized cell vectors
- Optimized atomic positions
- Stress tensor history

**Restart Artifacts**: Same as GEO_OPT

**Note**: Use `TYPE DIRECT_CELL_OPT` for simultaneous cell and geometry optimization (recommended by CP2K docs).

**Source**: [CP2K CELL_OPT Manual](https://manual.cp2k.org/trunk/CP2K_INPUT/MOTION/CELL_OPT.html)

---

### 3.4 Molecular Dynamics (MD)

**RUN_TYPE**: `MD`

**Key MD Ensembles** (in `MOTION/MD`):
- `NVE` (microcanonical)
- `NVT` (canonical, via thermostat)
- `NPT_F`, `NPT_I` (isothermal-isobaric)
- `LANGEVIN` (Langevin dynamics)

**Key Knobs**:
- `ENSEMBLE` (NVE, NVT, NPT_F, NPT_I, etc.)
- `TIMESTEP` (fs)
- `STEPS` (number of steps)
- `TEMPERATURE` (K)
- `THERMOSTAT` (NOSE, CSVR, GLE, etc.)
- `BAROSTAT` (for NPT)

**Typical Outputs**:
- Trajectory (`.xyz` or other format)
- Energy file (`.ener`)
- Velocity file (`.vel`)
- Cell file (`.cell`)
- Restart file (`.restart`)

**Restart Artifacts**:
- `PROJECT-1.restart` (periodic restart files)
- `PROJECT-RESTART.wfn` (wavefunction)

**Source**: [CP2K Molecular Dynamics Guide](https://manual.cp2k.org/cp2k-2024_1-branch/methods/sampling/molecular_dynamics.html)

---

### 3.5 Vibrational Analysis

**RUN_TYPE**: `VIBRATIONAL_ANALYSIS`

**Required**: Optimized geometry (from GEO_OPT)

**Key Knobs** (in `VIBRATIONAL_ANALYSIS`):
- `NPROC_REP` (parallelization)
- `DX` (finite difference displacement)
- `FULLY_PERIODIC` (for periodic systems)
- `INTENSITIES` (IR intensities)

**Typical Outputs**:
- Vibrational frequencies
- Normal modes
- IR intensities (if requested)
- Thermochemistry data

**Source**: [CP2K VIBRATIONAL_ANALYSIS Manual](https://manual.cp2k.org/trunk/CP2K_INPUT/VIBRATIONAL_ANALYSIS.html)

---

### 3.6 Electronic Structure Properties

#### 3.6.1 Density of States (DOS/PDOS)

**RUN_TYPE**: `ENERGY` with `FORCE_EVAL/DFT/PRINT/PDOS` section

**Key Knobs**:
- `NLUMO` (number of unoccupied states)
- `COMPONENTS` (separate spin components)
- Energy window settings

**Typical Outputs**:
- `.pdos` files (projected DOS per atom type)

**Source**: [CP2K PDOS Tutorial](https://www.cp2k.org/exercises:2017_uzh_cmest:pdos)

#### 3.6.2 Band Structure

**Via**: `FORCE_EVAL/PROPERTIES/BANDSTRUCTURE` section

**Key Knobs**:
- `KPOINT_SET` (k-path definition)
- `NPOINTS` (interpolation points)
- `DOS/KPOINTS` for DOS from k-mesh

**Typical Outputs**:
- Band eigenvalues along k-path
- DOS on k-mesh

**Source**: [CP2K BANDSTRUCTURE Manual](https://manual.cp2k.org/trunk/CP2K_INPUT/FORCE_EVAL/PROPERTIES/BANDSTRUCTURE.html)

---

### 3.7 Excited States (TD-DFT)

**Via**: `FORCE_EVAL/PROPERTIES/TDDFPT` section

**Key Knobs**:
- `NSTATES` (number of excited states)
- `RESTART` (restart from previous)
- `KERNEL` (XC kernel)

**Typical Outputs**:
- Excitation energies
- Oscillator strengths
- Transition dipole moments

**Source**: [CP2K TDDFPT Manual](https://manual.cp2k.org/trunk/CP2K_INPUT/FORCE_EVAL/PROPERTIES/TDDFPT.html)

---

### 3.8 Advanced Methods

#### 3.8.1 QM/MM

**Via**: `FORCE_EVAL/QMMM` section

**Key Components**:
- `QM_KIND` (QM region atoms)
- `MM_KIND` (force field for MM region)
- `CELL` (QM box)
- Link atoms (for covalent boundaries)

**Source**: [CP2K QM/MM Best Practice Guide](https://docs.bioexcel.eu/qmmm_bpg/)

#### 3.8.2 MP2, RPA, GW

**Via**: `FORCE_EVAL/DFT/XC/WF_CORRELATION` section

**Support Levels**:
- MP2 (RI-MP2)
- RPA (direct RPA)
- GW (G0W0)

**Note**: These methods require specialized basis sets (e.g., RI basis sets).

**Source**: [CP2K Journal Publication](https://pubs.aip.org/aip/jcp/article/152/19/194103/199081/CP2K-An-electronic-structure-and-molecular)

---

## 4. Summary: Task Complexity Matrix

| Task | RUN_TYPE | Complexity | Key Prerequisites |
|------|----------|------------|-------------------|
| Single-point | ENERGY_FORCE | Easy | Structure, basis, potential |
| Geometry optimization | GEO_OPT | Easy | Same as above |
| Cell optimization | CELL_OPT | Medium | Good starting cell |
| MD (NVE/NVT) | MD | Medium | Equilibrated structure |
| MD (NPT) | MD | Medium-Hard | Proper barostat settings |
| Vibrational analysis | VIBRATIONAL_ANALYSIS | Medium | Optimized geometry |
| DOS/PDOS | ENERGY + PRINT | Medium | Dense k-mesh |
| Band structure | ENERGY + BANDSTRUCTURE | Medium | K-path definition |
| TD-DFT | ENERGY + TDDFPT | Hard | Appropriate functional |
| QM/MM | QMMM | Hard | Force field, QM region |
| MP2/RPA/GW | ENERGY + WF_CORRELATION | Hard | RI basis sets |

---

## 5. QMatSuite Relevance

For initial QMatSuite integration, the following step types are recommended:

1. **cp2k_scf** (ENERGY_FORCE) - Basic single-point energy/forces
2. **cp2k_relax** (GEO_OPT) - Geometry optimization
3. **cp2k_md** (MD) - Molecular dynamics

These cover the most common workflows and have well-defined input/output contracts. More advanced methods (CELL_OPT, VIBRATIONAL_ANALYSIS, etc.) can be added incrementally.
