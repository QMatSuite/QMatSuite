# SIESTA Integration Design for QMatSuite

**Author:** Claude Sonnet 4.5
**Date:** January 27, 2026
**Version:** 1.0
**Purpose:** Comprehensive design document for integrating SIESTA into QMatSuite

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [SIESTA Overview](#siesta-overview)
3. [SIESTA Architecture & Execution Model](#siesta-architecture--execution-model)
4. [Typical SIESTA Workflows](#typical-siesta-workflows)
5. [File I/O Patterns & Dependencies](#file-io-patterns--dependencies)
6. [QMatSuite Architecture Analysis](#qmatsuite-architecture-analysis)
7. [SIESTA-to-QMatSuite Mapping](#siesta-to-qmatsuite-mapping)
8. [Integration Design](#integration-design)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Challenges & Recommendations](#challenges--recommendations)
11. [References](#references)

---

## Executive Summary

**SIESTA** (Spanish Initiative for Electronic Simulations with Thousands of Atoms) is a mature, well-established DFT code optimized for large-scale calculations using localized atomic orbitals and norm-conserving pseudopotentials. This document provides a comprehensive analysis of SIESTA's architecture, typical workflows, and a detailed design for integrating SIESTA into the QMatSuite framework.

### Key Findings

1. **Execution Model**: SIESTA uses a **monolithic single-executable** model with FDF (Flexible Data Format) input files. All calculation types (SCF, relaxation, MD, bands, DOS, phonons) are handled by the same `siesta` binary, with behavior controlled by FDF parameters.

2. **Workflow Complexity**: SIESTA workflows range from simple single-step SCF calculations to complex multi-step chains (SCF → NSCF → Bands post-processing, relaxation with restart, MD simulations).

3. **File Dependencies**: SIESTA has a rich ecosystem of intermediate files (`.DM`, `.HSX`, `.TSHS`, `.nc`) that enable calculation chaining and restarts, similar to Quantum ESPRESSO's `outdir` but using individual files rather than directories.

4. **QMatSuite Fit**: SIESTA fits naturally into QMatSuite's driver-based architecture. The main challenge is handling SIESTA's **implicit multi-step calculations** (e.g., relaxation = SCF + geometry optimization in one FDF) vs QMatSuite's **explicit step decomposition** model.

5. **Kernel Flexibility**: The current QMatSuite kernel is **sufficiently flexible** to accommodate most SIESTA workflows with **minor extensions** for handling:
   - Restart file management (`.DM`, `.XV` files)
   - Auxiliary utility programs (gnubands, Eig2DOS, vibra)
   - Post-processing steps as separate step types

### Recommendation

**Proceed with SIESTA integration** using a phased approach:
- **Phase 1**: Basic SCF, relaxation, and MD support (monolithic steps)
- **Phase 2**: Multi-step workflows (bands, DOS, phonons) with dependency management
- **Phase 3**: Advanced features (TranSIESTA, TDDFT, optical properties, Lua scripting)

---

## SIESTA Overview

### What is SIESTA?

SIESTA is a first-principles materials simulation code based on Density Functional Theory (DFT), designed for efficient large-scale calculations on systems with thousands of atoms.

**Key Characteristics:**
- **Basis Set**: Linear combination of numerical atomic orbitals (LCAO) - localized, not plane waves
- **Pseudopotentials**: Norm-conserving pseudopotentials (PSF, PSML formats)
- **Scaling**: Efficient for large systems (O(N) methods available)
- **Capabilities**: Ground state, geometry optimization, MD, phonons, band structure, DOS, optical properties, transport (TranSIESTA)

**Official Resources:**
- Documentation: https://docs.siesta-project.org/
- GitLab Repository: https://gitlab.com/siesta-project/siesta
- Pseudopotentials: http://www.pseudo-dojo.org (PSML), http://departments.icmab.es/leem/siesta/Databases/Pseudopotentials/ (PSF)

### SIESTA in the DFT Ecosystem

| Feature | SIESTA | Quantum ESPRESSO | VASP |
|---------|--------|------------------|------|
| **Basis Set** | Numerical atomic orbitals | Plane waves | Plane waves + PAW |
| **Executables** | Single `siesta` binary | Multiple (pw.x, ph.x, dos.x, bands.x) | Single `vasp_std` |
| **Input Format** | FDF (flexible, case-insensitive) | Fortran namelist (strict) | INCAR/POSCAR/KPOINTS |
| **Pseudopotentials** | PSF, PSML | UPF | POTCAR |
| **Scaling** | O(N) available for large systems | Better for small systems | Good parallelization |
| **Best Use Case** | Large biomolecules, nanostructures | Precision calculations, phonons | Solid-state physics |

---

## SIESTA Architecture & Execution Model

### Execution Interface

SIESTA follows a **stdin-driven model**:

```bash
# Standard execution
siesta < input.fdf > output.out

# Alternative forms
siesta -fdf SystemLabel=mysystem < input.fdf
siesta -L mysystem input.fdf  # Short-hand for SystemLabel
siesta input.fdf              # Direct file read (modern versions)

# With MPI
mpirun -np 4 siesta < input.fdf > output.out
```

**Key Observations:**
1. **Single executable**: No separate binaries for different calculation types (unlike QE's pw.x, ph.x, dos.x)
2. **FDF input**: Human-readable, order-independent, case-insensitive parameter file
3. **SystemLabel**: Critical parameter - determines all output file names (`{SystemLabel}.{extension}`)
4. **Output to stdout**: Main output written to stdout (typically redirected to file)

### Installation Verification

From the user's conda installation:

```bash
$ which siesta
/opt/homebrew/Caskroom/miniforge/base/bin/siesta

$ siesta --version
Version         : #SIESTA_VERSION#
Architecture    : #CMAKE_SYSTEM_PROCESSOR#
Parallelisations: MPI
NetCDF support
NetCDF-4 support
NetCDF-4 MPI-IO support
Lua support
```

**Available Utilities:**
```bash
$ ls /opt/homebrew/Caskroom/miniforge/base/bin/ | grep -i siesta
siesta              # Main executable
siesta_qmmm         # QM/MM hybrid calculations
gnubands            # Band structure plotting utility
Eig2DOS             # Eigenvalue to DOS converter
```

### FDF Input Format

**Syntax Rules:**
- **Case-insensitive labels**: `LatticeConstant`, `lattice-constant`, `LATTICE_CONSTANT` are equivalent
- **Special characters ignored in labels**: `-`, `_`, `.` are stripped
- **Comments**: `#` character (rest of line ignored)
- **Physical units required**: All dimensional quantities must have units (Ang, Bohr, eV, Ry, etc.)
- **Blocks for complex data**: `%block ... %endblock` for matrices, lists
- **Include files**: `%include other.fdf` for modularity
- **First-occurrence precedence**: If a label appears multiple times, first value is used

**Example FDF Structure:**

```fdf
# System identification
SystemName         Water molecule
SystemLabel        h2o

# Structure definition
%include structure.fdf

# Electronic structure parameters
PAO.BasisSize      DZP
XC.functional      GGA
XC.authors         PBE
MeshCutoff         250.0 Ry

# K-point sampling
%block kgrid_Monkhorst_Pack
  4  0  0  0.0
  0  4  0  0.0
  0  0  4  0.0
%endblock kgrid_Monkhorst_Pack

# SCF convergence
MaxSCFIterations   100
DM.Tolerance       1.0e-4
DM.MixingWeight    0.1

# Output control
SaveHS             true
WriteCoorXmol      true
```

### Calculation Type Determination

**Critical Insight**: Unlike QE (separate executables) or VASP (INCAR tags), SIESTA **implicitly determines calculation type** from FDF parameters:

| Calculation Type | Key FDF Parameters | Implicit Behavior |
|------------------|-------------------|-------------------|
| **Single-point SCF** | (default) | Solve Kohn-Sham equations once |
| **Geometry optimization** | `MD.TypeOfRun CG` or `MD.TypeOfRun FIRE` | Iterative SCF + force/stress minimization |
| **Molecular dynamics** | `MD.TypeOfRun Verlet` or `MD.TypeOfRun Nose` | SCF at each MD step |
| **Band structure** | `%block BandLines ... %endblock` | SCF + k-path band calculation |
| **DOS calculation** | `%block ProjectedDensityOfStates ... %endblock` | SCF + DOS integration |
| **Phonons** | Call `vibra` utility on `.XV`, `.TSHS` files | Post-processing after SCF |

**Implication for QMatSuite**: SIESTA's "one executable, many modes" model differs from QMatSuite's "one step type per calculation" model. We need to decide:
- **Option A**: Map FDF parameter combinations to distinct step types (e.g., `siesta_scf`, `siesta_relax_cg`, `siesta_md_verlet`)
- **Option B**: Use a generic `siesta` step type with FDF parsing to determine actual calculation
- **Recommended**: **Option A** for explicit workflow representation, aligning with QMatSuite philosophy

---

## Typical SIESTA Workflows

This section catalogs SIESTA workflows from **simple to challenging**, stress-testing QMatSuite's runner/kernel/step abstractions.

### 1. Simple Workflows (Easy)

#### 1.1 Single-Point SCF Energy Calculation

**Description**: Ground-state energy of fixed geometry.

**FDF Snippet**:
```fdf
SystemLabel        scf_calc
%include structure.fdf
PAO.BasisSize      DZP
XC.functional      GGA
XC.authors         PBE
MeshCutoff         200 Ry
```

**Execution**:
```bash
siesta < scf.fdf > scf.out
```

**Outputs**:
- `scf_calc.out` (redirected stdout) - energy, forces, timing
- `scf_calc.DM` - density matrix (for restarts)
- `scf_calc.HSX` - Hamiltonian and overlap matrices
- `scf_calc.EIG` - eigenvalues at k-points
- `scf_calc.FA` - forces on atoms
- `scf_calc.STRUCT_OUT` - final structure (same as input for SCF)

**QMatSuite Mapping**:
- **Step Type**: `siesta_scf`
- **Runner**: Execute once, parse energy/forces from stdout
- **Artifacts**: Archive `.DM`, `.HSX` for potential reuse

**Kernel Fit**: ✅ **Perfect fit** - single-step execution, no dependencies.

---

#### 1.2 Geometry Optimization (Fixed Cell)

**Description**: Relax atomic positions to minimum energy (cell fixed).

**FDF Snippet**:
```fdf
SystemLabel        relax_atoms
MD.TypeOfRun       CG              # Conjugate gradient
MD.NumCGsteps      100             # Max optimization steps
MD.MaxForceTol     0.04 eV/Ang    # Convergence criterion
WriteMDXmol        true            # Trajectory in .ANI file
WriteMDhistory     true            # Energy history in .MDE file
```

**Execution**:
```bash
siesta < relax.fdf > relax.out
```

**Outputs**:
- `relax_atoms.STRUCT_OUT` - final relaxed structure
- `relax_atoms.ANI` - trajectory of all geometry steps (XYZ format)
- `relax_atoms.MDE` - energy/force history (human-readable)
- `relax_atoms.XV` - final positions + velocities (restart format)

**QMatSuite Mapping**:
- **Step Type**: `siesta_relax`
- **Is Structure Transform**: `True` (updates structure)
- **Runner**: Parse final structure, archive trajectory
- **Artifacts**: `STRUCT_OUT` → update `StructureRef` in calculation

**Kernel Fit**: ✅ **Good fit** - similar to `qe_relax`, `vasp_relax`. QMatSuite already handles structure-transforming steps.

---

#### 1.3 Variable-Cell Optimization

**Description**: Relax both atomic positions and cell parameters.

**FDF Snippet**:
```fdf
MD.TypeOfRun          CG
MD.VariableCell       true          # Enable cell optimization
MD.MaxStressTol       0.01 GPa     # Stress convergence
MD.TargetPressure     0.0 GPa      # Target external pressure
```

**Outputs**: Same as 1.2, plus cell vectors in `STRUCT_OUT`

**QMatSuite Mapping**:
- **Step Type**: `siesta_vc_relax` (distinct from `siesta_relax`)
- **Generalized Step**: `VC_RELAX`

**Kernel Fit**: ✅ **Good fit** - analogous to `qe_vc_relax`, `vasp_relax` with `ISIF=3`.

---

### 2. Intermediate Workflows (Moderate Complexity)

#### 2.1 Molecular Dynamics Simulation

**Description**: Born-Oppenheimer MD with thermostat.

**FDF Snippet**:
```fdf
MD.TypeOfRun          Verlet         # or Nose, Parrinello-Rahman, Anneal
MD.LengthTimeStep     1.0 fs
MD.InitialTimeStep    1
MD.FinalTimeStep      1000
MD.InitialTemperature 300 K          # Random velocity assignment
MD.UseSaveXV          true           # Restart from .XV file
WriteMDXmol           true
WriteMDhistory        true
```

**Execution**:
```bash
siesta < md.fdf > md.out
```

**Outputs**:
- `md_run.ANI` - full trajectory (XYZ format)
- `md_run.MDE` - thermodynamic properties (T, E, V, P) per step
- `md_run.XV` - final snapshot (for continuation)

**Restart Workflow**:
To continue an MD run:
1. Set `MD.UseSaveXV true` in new FDF
2. Ensure `md_run.XV` is present in working directory
3. Run siesta again

**QMatSuite Mapping**:
- **Step Type**: `siesta_md` (could further specialize: `siesta_md_verlet`, `siesta_md_nose`)
- **Restart Handling**: Need mechanism to pass `.XV` file from previous MD step
- **Trajectory Parsing**: Extract trajectory from `.ANI` file

**Kernel Fit**: ⚠️ **Moderate fit** - QMatSuite's current MD support is limited to LAMMPS. Need to add:
- MD trajectory artifact type
- Restart file staging (copy `.XV` to new step's working directory)
- Thermodynamic property extraction

---

#### 2.2 Band Structure Calculation (Two-Step)

**Description**: Calculate electronic band structure along high-symmetry path.

**Workflow**:
1. **Step 1**: SCF calculation on uniform k-mesh → converged Hamiltonian
2. **Step 2**: Band structure calculation along k-path (reads `.TSHS` from Step 1)

**Step 1 FDF**:
```fdf
SystemLabel        scf_bands
SaveHS             true            # CRITICAL: saves Hamiltonian
%block kgrid_Monkhorst_Pack
  8  0  0  0.0
  0  8  0  0.0
  0  0  8  0.0
%endblock kgrid_Monkhorst_Pack
```

**Step 2 FDF**:
```fdf
SystemLabel        bands           # MUST match Step 1 SystemLabel for .TSHS
BandLinesScale     pi/a
%block BandLines
  1  0.0 0.0 0.0  \Gamma
  40 0.5 0.0 0.5  X
  40 0.5 0.25 0.75 W
  40 0.5 0.5 0.5  L
  40 0.0 0.0 0.0  \Gamma
%endblock BandLines
```

**Execution**:
```bash
# Step 1
siesta < scf_bands.fdf > scf_bands.out

# Step 2 (must be in same directory as .TSHS file!)
siesta < bands.fdf > bands.out
```

**Outputs**:
- `bands.bands` - band structure data (k-point, band index, energy)
- `bands.EIG` - eigenvalues

**Post-processing**:
```bash
gnubands -G -F -b 1 -B 10 bands.bands
gnuplot bands.gplot > bands.png
```

**QMatSuite Mapping**:
- **Step 1**: `siesta_scf` (produces `.TSHS` artifact)
- **Step 2**: `siesta_bands` (consumes `.TSHS` artifact)
- **Step 3** (optional): `siesta_bands_plot` (post-processing utility, produces PNG)

**Dependencies**:
- `siesta_bands` `requires_hamiltonian=True` → must have prior `siesta_scf`
- Artifact passing: `.TSHS` file must be staged into Step 2 working directory

**Kernel Fit**: ⚠️ **Moderate fit** - challenges:
1. **Artifact Staging**: QMatSuite needs to copy `.TSHS` from Step 1 to Step 2 workdir
2. **SystemLabel Matching**: Step 2 `SystemLabel` must match Step 1 for SIESTA to find `.TSHS`
3. **Post-processing as Step**: `gnubands` utility as a separate step type (not a SIESTA calculation)

**Recommendation**:
- Add `requires_hamiltonian` flag to step type spec
- Implement artifact staging in recipe layer (copy `.TSHS` → `{new_label}.TSHS`)
- Create `siesta_gnubands` step type for post-processing

---

#### 2.3 Density of States (DOS) Calculation

**Description**: Calculate total and projected DOS.

**FDF Snippet**:
```fdf
SystemLabel        dos_calc
# ... standard SCF parameters ...

# PDOS specification
%block ProjectedDensityOfStates
  -20.0  10.0  0.2  1000  eV    # Emin Emax dE npoints units
%endblock ProjectedDensityOfStates

# Optional: Denser k-mesh for PDOS
%block PDOS.kgrid_Monkhorst_Pack
  12  0  0  0.0
   0 12  0  0.0
   0  0 12  0.0
%endblock PDOS.kgrid_Monkhorst_Pack
```

**Outputs**:
- `dos_calc.DOS` - total DOS
- `dos_calc.PDOS` - projected DOS (per atom, per orbital)

**Alternative (Two-Step)**:
1. SCF with `SaveHS true`
2. Run `Eig2DOS` utility on `.EIG` file:
   ```bash
   Eig2DOS -f dos_calc.EIG -o dos_calc_processed.DOS
   ```

**QMatSuite Mapping**:
- **Option A**: Single-step `siesta_dos` (SIESTA computes DOS internally)
- **Option B**: Two-step `siesta_scf` + `siesta_eig2dos` (utility post-processing)

**Kernel Fit**: ✅ **Good fit** - similar to QE's `qe_dos` (uses `dos.x` utility). Option B aligns better with QMatSuite's separation of concerns.

---

### 3. Advanced Workflows (Challenging for Kernel)

#### 3.1 Phonon Calculation (Frozen Phonon Method)

**Description**: Calculate vibrational modes using finite differences.

**Multi-Step Workflow**:
1. **Geometry optimization** → relaxed structure
2. **Supercell construction** → manual or scripted
3. **Finite displacement calculations** → N separate SCF runs (N = # displacements)
4. **Force constant matrix extraction** → `vibra` utility
5. **Phonon band structure calculation** → `vibra` utility

**FDF for Displacement Calculations**:
```fdf
SystemLabel        phonon_disp_01
# ... SCF parameters ...
MD.FCFirst         1              # First atom to displace
MD.FCLast          3              # Last atom to displace
WriteMDXmol        true
```

**Post-processing with Vibra**:
```bash
# After all displacement calculations:
vibra < vibra.fdf
```

`vibra.fdf`:
```fdf
SystemLabel        phonon
BandLinesScale     pi/a
%block BandLines
  # Phonon dispersion path
%endblock BandLines
```

**QMatSuite Mapping**:
- **Challenge**: Phonon workflow requires **dynamic step generation** (N displacement steps not known a priori)
- **Possible Solution**: Introduce `siesta_phonon_setup` step that:
  1. Determines number of displacements
  2. Generates N `siesta_phonon_disp` steps dynamically
  3. Final `siesta_vibra` step aggregates results

**Kernel Fit**: ❌ **Poor fit** - QMatSuite's current static step sequence model cannot handle dynamic step generation. This would require **kernel extension**:
- Add support for "generator steps" that emit new steps
- Or: Pre-compute displacement steps in workflow template (fixed supercell size)

**Recommendation**: **Phase 3 feature** - defer phonon support until kernel supports dynamic workflows or use pre-defined templates for common supercell sizes.

---

#### 3.2 TranSIESTA (Electron Transport)

**Description**: Non-equilibrium Green's function (NEGF) transport calculations for nanoscale devices.

**Workflow**:
1. **Electrode calculations** → converged `.TSHS` for left/right electrodes
2. **Scattering region calculation** → device Hamiltonian with electrodes embedded
3. **Transport calculation** → I-V curves, transmission spectra

**FDF for Electrode**:
```fdf
SystemLabel        electrode_left
TS.HS.Save         true           # Save Hamiltonian for TranSIESTA
# ... standard SCF ...
```

**FDF for Device**:
```fdf
SystemLabel        device
TS.Voltage         0.5 eV
TS.HS.Save         true

%block TS.ChemPots
  left
  right
%endblock TS.ChemPots

%block TS.ChemPot.left
  mu V/2
  contour.eq.begin
  ...
%endblock TS.ChemPot.left

# Electrode specification
%block TS.Elecs
  left
  right
%endblock TS.Elecs

%block TS.Elec.left
  HS electrode_left.TSHS       # Reference to electrode Hamiltonian
  chem-pot left
  ...
%endblock TS.Elec.left
```

**QMatSuite Mapping**:
- **Step 1**: `siesta_electrode` (left)
- **Step 2**: `siesta_electrode` (right)
- **Step 3**: `siesta_transiesta` (device, depends on Step 1 & 2)

**Kernel Fit**: ⚠️ **Moderate fit** - challenges:
1. **Multi-dependency**: Step 3 requires artifacts from **both** Step 1 and Step 2 (QMatSuite typically handles linear dependencies)
2. **Complex FDF generation**: `TS.Elec.left` block must reference electrode file paths
3. **Voltage scanning**: Often need to run Step 3 multiple times with different `TS.Voltage` values

**Recommendation**:
- Support as **advanced workflow template** in Phase 3
- Extend kernel to handle multi-parent dependencies (already implicitly supported via artifact staging, just needs formalization)

---

#### 3.3 Time-Dependent DFT (Optical Properties)

**Description**: Calculate absorption spectra using TDDFT.

**Workflow**:
1. **Ground-state SCF** → converged `.TSHS`
2. **TDDFT calculation** → read `.TSHS`, compute excitations

**FDF for TDDFT**:
```fdf
SystemLabel        tddft_calc
TS.HS.Save         true

# Optical properties block
OpticalCalculation     true
Optical.Energy.Minimum 0.0 eV
Optical.Energy.Maximum 10.0 eV
Optical.Broaden        0.1 eV
Optical.Mesh           [Nx, Ny, Nz]
```

**Outputs**:
- `tddft_calc.EPSIMG` - imaginary part of dielectric function
- `tddft_calc.EPSREAL` - real part of dielectric function

**QMatSuite Mapping**:
- **Step Type**: `siesta_tddft`
- **Generalized Step**: `TD` (time-dependent)

**Kernel Fit**: ✅ **Good fit** - similar to ORCA's `orca_td` or PySCF's `pyscf_td`. Just needs Hamiltonian dependency.

---

#### 3.4 Lua-Scripted Workflows

**Description**: SIESTA has embedded Lua interpreter for advanced workflow automation.

**Example**: Geometry optimization with custom convergence criteria

**FDF with Lua**:
```fdf
%block MD.FIRE-SETUP
  fire
%endblock MD.FIRE-SETUP

%include LUA
  function md_step(istep)
    -- Custom convergence check
    if siesta.Forces:max() < threshold then
      siesta.MD.Converged = true
    end
  end
%endinclude LUA
```

**QMatSuite Mapping**: ❓ **Unclear fit** - Lua scripting allows arbitrary in-calculation logic, which QMatSuite externalizes to the workflow layer.

**Recommendation**: **Ignore Lua features for Phase 1-2**. Advanced users can still write custom FDF files with Lua; QMatSuite just treats them as opaque inputs.

---

### Workflow Complexity Summary

| Workflow | Complexity | Kernel Fit | Notes |
|----------|-----------|-----------|-------|
| Single SCF | Easy | ✅ Perfect | Single step, no dependencies |
| Geometry optimization | Easy | ✅ Perfect | Structure transform, QMatSuite handles |
| Variable-cell relax | Easy | ✅ Perfect | Same as above |
| Molecular dynamics | Moderate | ⚠️ Moderate | Needs restart file staging, trajectory parsing |
| Band structure (2-step) | Moderate | ⚠️ Moderate | Hamiltonian artifact passing, post-processing step |
| DOS | Moderate | ✅ Good | Utility post-processing or internal |
| Phonons (frozen) | Challenging | ❌ Poor | Dynamic step generation required |
| TranSIESTA | Challenging | ⚠️ Moderate | Multi-parent dependencies |
| TDDFT | Moderate | ✅ Good | Hamiltonian dependency |
| Lua workflows | Advanced | ❓ N/A | Out of scope for automatic handling |

**Kernel Stress Test Verdict**:
- **Phases 1-2 workflows**: QMatSuite kernel is **flexible enough** with **minor extensions**:
  1. Artifact staging mechanism (copy `.DM`, `.TSHS`, `.XV` files between steps)
  2. Post-processing utilities as step types (gnubands, Eig2DOS)
  3. Multi-parent dependency support (formalize existing capability)

- **Phase 3 workflows**: Require **kernel enhancements**:
  1. Dynamic step generation for phonons
  2. Voltage/parameter scanning loops

---

## File I/O Patterns & Dependencies

### Output File Taxonomy

SIESTA produces a rich set of output files, all prefixed by `SystemLabel`:

| File Extension | Description | Used For | Binary? |
|----------------|-------------|----------|---------|
| `.out` | Main output (stdout redirect) | Energies, forces, convergence | Text |
| `.DM` | Density matrix | Restart SCF calculations | Binary |
| `.HSX` | Hamiltonian + overlap matrices (sparse) | Post-processing, transport | Binary |
| `.TSHS` | Hamiltonian (TranSIESTA format) | Bands, transport, TDDFT | Binary |
| `.nc` | NetCDF output (structure, energies, forces) | Modern unified format | Binary |
| `.EIG` | Eigenvalues at all k-points | DOS calculation (Eig2DOS) | Text |
| `.FA` | Forces on atoms | Geometry optimization, MD | Text |
| `.KP` | K-point information | Band plotting | Text |
| `.STRUCT_OUT` | Final structure (FDF format) | Geometry after relaxation | Text |
| `.XV` | Positions + velocities (MD restart) | Continue MD simulations | Text |
| `.ANI` | Trajectory (XYZ format) | Visualization of MD/relax | Text |
| `.MDE` | MD energy history | Analysis of MD runs | Text |
| `.bands` | Band structure data | gnubands plotting | Text |
| `.DOS` | Density of states | DOS plotting | Text |
| `.PDOS` | Projected DOS | Orbital-resolved DOS | Text |

### Restart File Requirements

| Calculation | Required Input Files | Produces |
|-------------|---------------------|----------|
| **SCF (fresh)** | None (just FDF + pseudopotentials) | `.DM`, `.HSX`, `.TSHS` |
| **SCF (restart)** | `.DM` (from previous SCF) | Updated `.DM` |
| **Relax (continue)** | `.XV` (positions + velocities) | Updated `.XV`, `.STRUCT_OUT` |
| **MD (continue)** | `.XV` (last snapshot) | Updated `.XV`, `.ANI` (appended) |
| **Bands** | `.TSHS` (from SCF) | `.bands` |
| **DOS (Eig2DOS)** | `.EIG` (from SCF) | `.DOS` |
| **TranSIESTA** | `.TSHS` (from electrode calcs) | Transport properties |
| **Vibra (phonons)** | `.XV`, `.FA` (from displacement calcs) | `.vectors`, `.bands` (phonon) |

### Dependency Graph Examples

**Example 1: Band Structure Workflow**
```
┌─────────────┐
│  siesta_scf │  (uniform k-mesh)
│   outputs:  │
│   .TSHS     │
│   .DM       │
└──────┬──────┘
       │ .TSHS passed to next step
       ▼
┌─────────────────┐
│  siesta_bands   │  (k-path, reads .TSHS)
│    outputs:     │
│    .bands       │
└──────┬──────────┘
       │ .bands passed to utility
       ▼
┌─────────────────┐
│ siesta_gnubands │  (utility, not siesta binary)
│    outputs:     │
│    .gplot       │
│    band.png     │
└─────────────────┘
```

**Example 2: Restart MD Workflow**
```
┌─────────────┐
│ siesta_md   │  (initial 1000 steps)
│  MD.FinalTimeStep 1000
│  outputs:   │
│  .XV        │
│  .ANI       │
└──────┬──────┘
       │ .XV passed to next MD
       ▼
┌─────────────┐
│ siesta_md   │  (continue 1000 more steps)
│  MD.UseSaveXV true
│  MD.InitialTimeStep 1001
│  MD.FinalTimeStep 2000
│  outputs:   │
│  .XV (updated)
│  .ANI (appended)
└─────────────┘
```

**Example 3: Phonon Workflow (Simplified)**
```
┌──────────────┐
│siesta_relax  │  (get equilibrium geometry)
│  outputs:    │
│  .STRUCT_OUT │
└──────┬───────┘
       │ Structure → generate displacements
       ▼
┌──────────────────────────────────────┐
│  Displacement calculations (N jobs)  │
│  siesta_scf (disp_001)               │
│  siesta_scf (disp_002)               │
│  ...                                 │
│  siesta_scf (disp_N)                 │
│  outputs: .FA, .XV for each          │
└──────────────┬───────────────────────┘
               │ All .FA files → vibra
               ▼
       ┌───────────────┐
       │ siesta_vibra  │  (utility, not siesta)
       │   outputs:    │
       │   .vectors    │
       │   .bands      │
       │   (phonon)    │
       └───────────────┘
```

### Working Directory Management

**SIESTA's Model**: Unlike Quantum ESPRESSO (which uses `outdir` for intermediate files), SIESTA writes **all output files to the current working directory**. There is no concept of a separate scratch directory.

**Implications for QMatSuite**:
1. **Workdir Policy**: Should use `WorkdirPolicy.ISOLATED` (each step gets its own directory)
2. **Artifact Staging**: When Step B needs `.TSHS` from Step A:
   - Copy `stepA_workdir/scf.TSHS` → `stepB_workdir/scf.TSHS`
   - Or: Symlink if on same filesystem
3. **Cleanup**: All files remain in workdir after completion (no automatic cleanup needed)

**Comparison with Other Codes**:

| Code | Workdir Policy | Intermediate Files |
|------|----------------|-------------------|
| **SIESTA** | ISOLATED (recommended) | All in CWD |
| **QE** | SHARED (`outdir` common across steps) | `outdir/*.save/` |
| **VASP** | CLEANUP (rm -rf before each step) | All in CWD, deleted after |

---

## QMatSuite Architecture Analysis

*[This section was provided by the Explore agent earlier. Key points summarized here for context.]*

### Runner System

QMatSuite's runner system executes calculations at multiple levels:
1. **CalculationRunner**: Orchestrates step execution using engine registry
2. **Step**: Unit of execution with input file, engine, options
3. **JobExecutor**: Processes JobGraph with incremental skip logic

**Key for SIESTA**: The `Step.run()` method delegates to `engine.run_step()`, which is engine-specific. SIESTA will need its own handler.

### Kernel (Driver Registry)

The driver registry is a singleton that routes step execution to appropriate handlers:
- Each driver implements `EngineDriver` protocol
- Drivers declare step type specs, handlers, recipe classes
- Auto-registration at import time

**Key for SIESTA**: Create `SiestaDriver` class implementing `EngineDriver`, register at import.

### Gen/Spec Steps

- **GEN (Generalized)**: Engine-agnostic operations (SCF, RELAX, BANDS, DOS, MD)
- **SPEC (Specific)**: Engine-prefixed types (`qe_scf`, `pyscf_scf`, `siesta_scf`)
- **Materialization**: `(engine_family, gen_step) → spec_step` (0-1 mapping)

**Key for SIESTA**: Define materialization map:
```python
("siesta", "SCF") → "siesta_scf"
("siesta", "RELAX") → "siesta_relax"
("siesta", "VC_RELAX") → "siesta_vc_relax"
("siesta", "BANDS") → "siesta_bands"
("siesta", "DOS") → "siesta_dos"
("siesta", "MD") → "siesta_md"
("siesta", "PHONON") → "siesta_phonon"  # Phase 3
("siesta", "TD") → "siesta_tddft"       # Phase 3
```

### Current Code Integrations

QMatSuite already supports:
- **QE**: Multi-executable model (`pw.x`, `dos.x`, `bands.x`, `ph.x`)
- **VASP**: Single executable with CLEANUP workdir policy
- **PySCF**: Subprocess runner (not in-process)
- **ORCA**: Single executable, molecular chemistry

**SIESTA's Fit**: Most similar to **ORCA** (single binary, FDF input) and **VASP** (single binary, multiple modes). But workdir policy more like **QE** (isolated).

---

## SIESTA-to-QMatSuite Mapping

### Step Type Definitions

Proposed SIESTA step types for **Phase 1** (basic support):

```python
# From drivers/siesta/step_types.py
SIESTA_STEP_TYPE_SPECS: list[StepTypeSpec] = [
    # Ground state calculations
    StepTypeSpec(
        id="siesta_scf",
        machine_type="siesta_scf",
        public_type="scf",
        engine="siesta",
        executable="siesta",
        description="SIESTA single-point SCF calculation",
        requires_structure=True,
        produces_charge_density=True,  # .DM file
        produces_state="dm",            # For restart
        supports_incremental_skip=True,
    ),

    # Geometry optimization
    StepTypeSpec(
        id="siesta_relax",
        machine_type="siesta_relax",
        public_type="relax",
        engine="siesta",
        executable="siesta",
        description="SIESTA geometry optimization (fixed cell)",
        requires_structure=True,
        is_structure_transform=True,   # Updates structure
        produces_state="xv",            # .XV file for restart
        supports_incremental_skip=False,  # Always run fresh
    ),

    StepTypeSpec(
        id="siesta_vc_relax",
        machine_type="siesta_vc_relax",
        public_type="vc_relax",
        engine="siesta",
        executable="siesta",
        description="SIESTA variable-cell optimization",
        requires_structure=True,
        is_structure_transform=True,
        produces_state="xv",
        supports_incremental_skip=False,
    ),

    # Molecular dynamics
    StepTypeSpec(
        id="siesta_md",
        machine_type="siesta_md",
        public_type="md",
        engine="siesta",
        executable="siesta",
        description="SIESTA Born-Oppenheimer MD",
        requires_structure=True,
        consumes_state="xv",  # Can restart from .XV
        produces_state="xv",
        supports_incremental_skip=False,
    ),
]

# Phase 2 additions:
SIESTA_PHASE2_STEPS = [
    StepTypeSpec(
        id="siesta_bands",
        machine_type="siesta_bands",
        public_type="bands",
        engine="siesta",
        executable="siesta",
        description="SIESTA band structure calculation",
        requires_structure=True,
        requires_charge_density=False,
        consumes_state="tshs",  # Requires .TSHS from SCF
    ),

    StepTypeSpec(
        id="siesta_gnubands",
        machine_type="siesta_gnubands",
        public_type="bands_post",
        engine="siesta",
        executable="gnubands",
        description="SIESTA band structure plotting utility",
        requires_structure=False,  # Just processes .bands file
    ),

    StepTypeSpec(
        id="siesta_dos",
        machine_type="siesta_dos",
        public_type="dos",
        engine="siesta",
        executable="siesta",
        description="SIESTA DOS calculation (internal)",
        requires_structure=True,
        requires_charge_density=True,
    ),

    StepTypeSpec(
        id="siesta_eig2dos",
        machine_type="siesta_eig2dos",
        public_type="dos_post",
        engine="siesta",
        executable="Eig2DOS",
        description="SIESTA DOS from eigenvalues utility",
        requires_structure=False,
    ),
]
```

### Generalized Step Materialization

```python
# From workflow/generalized_steps.py (additions)
MATERIALIZATION_MAP.update({
    # SIESTA family
    ("siesta", "SCF"): "siesta_scf",
    ("siesta", "NSCF"): None,  # SIESTA doesn't have distinct NSCF (bands step does this)
    ("siesta", "RELAX"): "siesta_relax",
    ("siesta", "VC_RELAX"): "siesta_vc_relax",
    ("siesta", "BANDS"): "siesta_bands",
    ("siesta", "BANDS_POST"): "siesta_gnubands",
    ("siesta", "DOS"): "siesta_dos",
    ("siesta", "MD"): "siesta_md",
    ("siesta", "PHONON"): "siesta_phonon",  # Phase 3
    ("siesta", "TD"): "siesta_tddft",       # Phase 3
})
```

### Artifact Types

New artifact types needed for SIESTA:

```python
# From calculation/step_artifacts.py (additions)
class SiestaArtifactType(str, Enum):
    DENSITY_MATRIX = "density_matrix"     # .DM file
    HAMILTONIAN_HSX = "hamiltonian_hsx"   # .HSX file
    HAMILTONIAN_TSHS = "hamiltonian_tshs" # .TSHS file (for bands/transport)
    NETCDF = "netcdf"                     # .nc file
    MD_RESTART = "md_restart"             # .XV file (positions + velocities)
    TRAJECTORY = "trajectory"             # .ANI file (MD trajectory)
    BANDS_DATA = "bands_data"             # .bands file
    DOS_DATA = "dos_data"                 # .DOS file
```

### Workdir Policy

```python
# From drivers/siesta/driver.py
class SiestaDriver(BaseEngineDriver):
    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.ISOLATED
        # Each step gets own directory; artifacts staged explicitly
```

---

## Integration Design

### Driver Architecture

```
src/quantumvitas/drivers/siesta/
├── __init__.py                 # Driver registration
├── driver.py                   # SiestaDriver class
├── step_types.py               # SIESTA step type specifications
├── handler.py                  # siesta_step_handler function
├── recipe.py                   # SiestaRecipe class (FDF generation)
├── engine/                     # Execution logic
│   ├── __init__.py
│   ├── executor.py             # Run siesta binary, parse output
│   └── utilities.py            # gnubands, Eig2DOS, vibra wrappers
├── io/                         # I/O utilities
│   ├── __init__.py
│   ├── fdf_writer.py           # FDF file generation
│   ├── fdf_parser.py           # FDF file parsing (for templates)
│   ├── output_parser.py        # Parse .out, .nc, .EIG, .FA files
│   └── structure_converter.py  # QMatSuite Structure ↔ SIESTA format
├── parsers/                    # Output file parsers
│   ├── __init__.py
│   ├── main_output.py          # Parse stdout (.out file)
│   ├── netcdf_parser.py        # Parse .nc file
│   ├── bands_parser.py         # Parse .bands file
│   └── dos_parser.py           # Parse .DOS file
└── ir/                         # Intermediate representation
    ├── __init__.py
    └── fdf_ir.py               # FDF parameter IR (for template generation)
```

### Driver Class

```python
# drivers/siesta/driver.py
from quantumvitas.core.driver_protocol import EngineDriver
from quantumvitas.workflow.registry import StepTypeSpec
from quantumvitas.execution.workdir import WorkdirPolicy

class SiestaDriver:
    """Driver for SIESTA DFT code."""

    @property
    def engine_family(self) -> str:
        return "siesta"

    @property
    def display_name(self) -> str:
        return "SIESTA"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        from .step_types import SIESTA_STEP_TYPE_SPECS
        return SIESTA_STEP_TYPE_SPECS

    def get_handler(self):
        from .handler import siesta_step_handler
        return siesta_step_handler

    def get_recipe_class(self):
        from .recipe import SiestaRecipe
        return SiestaRecipe

    def get_materialization_map(self) -> dict[str, str]:
        return {
            "SCF": "siesta_scf",
            "RELAX": "siesta_relax",
            "VC_RELAX": "siesta_vc_relax",
            "BANDS": "siesta_bands",
            "DOS": "siesta_dos",
            "MD": "siesta_md",
            # Phase 3:
            # "PHONON": "siesta_phonon",
            # "TD": "siesta_tddft",
        }

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        return {
            "scf",
            "relax",
            "vc_relax",
            "bands",
            "dos",
            "md",
            # Phase 3: "phonon", "td", "transport"
        }

    def supports_incremental_skip(self, step_type: str) -> bool:
        # Only SCF can be skipped if already converged
        return step_type == "siesta_scf"
```

### Handler Function

```python
# drivers/siesta/handler.py
from pathlib import Path
from quantumvitas.execution.job import Job, JobResult
from quantumvitas.calculation.calculation import Calculation
from .engine.executor import SiestaExecutor
from .io.output_parser import SiestaOutputParser

def siesta_step_handler(job: Job, calc: Calculation) -> JobResult:
    """
    Execute a SIESTA job.

    Workflow:
    1. Stage input files (FDF, pseudopotentials, restart files)
    2. Run siesta binary
    3. Parse output
    4. Extract artifacts
    5. Return JobResult
    """
    try:
        step = job.step
        workdir = calc.raw_dir / step.meta.slug

        # 1. Prepare working directory
        workdir.mkdir(parents=True, exist_ok=True)

        # 2. Stage artifacts from previous steps (if any)
        _stage_restart_files(job, calc, workdir)

        # 3. Execute SIESTA
        executor = SiestaExecutor(workdir)
        exec_result = executor.run(
            fdf_file=step.input_file,
            system_label=_extract_system_label(step.input_file),
            step_type=step.step_type,
        )

        # 4. Parse output
        parser = SiestaOutputParser(workdir, exec_result.system_label)
        parse_result = parser.parse_all(step.step_type)

        # 5. Handle structure updates (for relax steps)
        if step.step_type in ["siesta_relax", "siesta_vc_relax"]:
            _update_structure(calc, parse_result.final_structure)

        # 6. Archive artifacts
        artifacts = _collect_artifacts(workdir, step.step_type)

        return JobResult(
            success=exec_result.success,
            step_results={
                "energy": parse_result.final_energy,
                "forces": parse_result.forces,
                "stress": parse_result.stress if step.step_type.endswith("vc_relax") else None,
                "structure": parse_result.final_structure,
            },
            artifacts=artifacts,
            error=exec_result.error if not exec_result.success else None,
        )

    except Exception as e:
        return JobResult(success=False, error=str(e))


def _stage_restart_files(job: Job, calc: Calculation, workdir: Path):
    """
    Copy restart files from previous steps to current workdir.

    Examples:
    - siesta_bands needs .TSHS from siesta_scf
    - siesta_md (restart) needs .XV from previous siesta_md
    """
    step_type = job.step.step_type

    if step_type == "siesta_bands":
        # Need .TSHS from previous SCF
        scf_artifact = _find_artifact(calc, "hamiltonian_tshs")
        if scf_artifact:
            shutil.copy(scf_artifact, workdir / f"{job.step.meta.slug}.TSHS")

    elif step_type == "siesta_md" and _has_restart_option(job.step):
        # Need .XV from previous MD step
        xv_artifact = _find_artifact(calc, "md_restart")
        if xv_artifact:
            shutil.copy(xv_artifact, workdir / f"{job.step.meta.slug}.XV")

    # ... other cases ...


def _collect_artifacts(workdir: Path, step_type: str) -> dict:
    """
    Identify and catalog artifacts produced by this step.
    """
    artifacts = {}

    if step_type == "siesta_scf":
        artifacts["density_matrix"] = _find_file(workdir, "*.DM")
        artifacts["hamiltonian_tshs"] = _find_file(workdir, "*.TSHS")
        artifacts["hamiltonian_hsx"] = _find_file(workdir, "*.HSX")

    elif step_type in ["siesta_relax", "siesta_vc_relax"]:
        artifacts["final_structure"] = _find_file(workdir, "*.STRUCT_OUT")
        artifacts["trajectory"] = _find_file(workdir, "*.ANI")
        artifacts["md_restart"] = _find_file(workdir, "*.XV")

    elif step_type == "siesta_md":
        artifacts["trajectory"] = _find_file(workdir, "*.ANI")
        artifacts["md_restart"] = _find_file(workdir, "*.XV")
        artifacts["md_history"] = _find_file(workdir, "*.MDE")

    elif step_type == "siesta_bands":
        artifacts["bands_data"] = _find_file(workdir, "*.bands")

    # ... other cases ...

    return artifacts
```

### Recipe Class (FDF Generation)

```python
# drivers/siesta/recipe.py
from pathlib import Path
from quantumvitas.execution.recipes import BaseRecipe
from .io.fdf_writer import FDFWriter
from .io.structure_converter import SiestaStructureConverter

class SiestaRecipe(BaseRecipe):
    """
    Generate SIESTA FDF input files from QMatSuite step specifications.
    """

    def materialize(self, step: Step, calc: Calculation) -> Path:
        """
        Generate FDF file for the given step.

        Returns:
            Path to generated .fdf file
        """
        system_label = step.meta.slug
        fdf_path = calc.raw_dir / step.meta.slug / f"{system_label}.fdf"

        # Build FDF parameters from step options and presets
        fdf_params = self._build_fdf_params(step, calc)

        # Write FDF file
        writer = FDFWriter(fdf_path)
        writer.write_system_info(system_label, step.meta.name)

        # Structure (unless post-processing step)
        if step.step_type not in ["siesta_gnubands", "siesta_eig2dos"]:
            structure = self._resolve_structure(step, calc)
            writer.write_structure(structure)

        # Calculation-specific blocks
        if step.step_type == "siesta_scf":
            writer.write_scf_parameters(fdf_params)

        elif step.step_type == "siesta_relax":
            writer.write_relax_parameters(fdf_params, variable_cell=False)

        elif step.step_type == "siesta_vc_relax":
            writer.write_relax_parameters(fdf_params, variable_cell=True)

        elif step.step_type == "siesta_md":
            writer.write_md_parameters(fdf_params)

        elif step.step_type == "siesta_bands":
            writer.write_bands_parameters(fdf_params)

        # ... other step types ...

        writer.finalize()
        return fdf_path


    def _build_fdf_params(self, step: Step, calc: Calculation) -> dict:
        """
        Translate QMatSuite presets to SIESTA FDF parameters.

        Preset dimensions:
        - precision: LOW/MED/HIGH → MeshCutoff (Ry)
        - magnetism: NONMAGNETIC/COLLINEAR_LSDA/... → SpinPolarized, ...
        - xc_functional: PBE/LDA/... → XC.functional, XC.authors
        - basis_size: SZ/DZ/DZP/TZP/... → PAO.BasisSize
        - k_point_density: LOW/MED/HIGH → kgrid_Monkhorst_Pack
        - convergence: FAST/NORMAL/ROBUST → DM.Tolerance, MaxSCFIterations
        """
        params = {}

        # Extract presets from step.options
        presets = step.options.get("presets", {})

        # Precision → MeshCutoff
        precision = presets.get("precision", "MED")
        params["MeshCutoff"] = {
            "LOW": "150.0 Ry",
            "MED": "250.0 Ry",
            "HIGH": "400.0 Ry",
        }[precision]

        # Basis size
        basis = presets.get("basis_size", "DZP")
        params["PAO.BasisSize"] = basis

        # XC functional
        xc = presets.get("xc_functional", "PBE")
        params["XC.functional"] = "GGA" if xc in ["PBE", "PW91"] else "LDA"
        params["XC.authors"] = xc

        # Magnetism
        magnetism = presets.get("magnetism", "NONMAGNETIC")
        params["SpinPolarized"] = "T" if magnetism != "NONMAGNETIC" else "F"
        if magnetism == "NONCOLLINEAR":
            params["NonCollinearSpin"] = "T"

        # K-points
        k_density = presets.get("k_point_density", "MED")
        params["kgrid"] = self._get_k_grid(k_density, calc.structure)

        # Convergence
        convergence = presets.get("convergence", "NORMAL")
        params["DM.Tolerance"] = {
            "FAST": "1.0e-3",
            "NORMAL": "1.0e-4",
            "ROBUST": "1.0e-5",
        }[convergence]
        params["MaxSCFIterations"] = {
            "FAST": "50",
            "NORMAL": "100",
            "ROBUST": "200",
        }[convergence]

        # Override with explicit step.options
        params.update(step.options.get("fdf_overrides", {}))

        return params
```

### Executor (Run SIESTA Binary)

```python
# drivers/siesta/engine/executor.py
import subprocess
from pathlib import Path
from dataclasses import dataclass

@dataclass
class SiestaExecutionResult:
    success: bool
    return_code: int
    stdout: str
    stderr: str
    system_label: str
    error: str | None = None

class SiestaExecutor:
    """Execute SIESTA binary and capture output."""

    def __init__(self, workdir: Path):
        self.workdir = workdir

    def run(self, fdf_file: Path, system_label: str, step_type: str) -> SiestaExecutionResult:
        """
        Run SIESTA with given FDF input.

        Args:
            fdf_file: Path to .fdf input file
            system_label: SystemLabel value (for output files)
            step_type: Step type (for utility vs. siesta binary decision)

        Returns:
            SiestaExecutionResult with success status and output
        """
        # Determine executable
        if step_type == "siesta_gnubands":
            return self._run_gnubands(system_label)
        elif step_type == "siesta_eig2dos":
            return self._run_eig2dos(system_label)
        else:
            return self._run_siesta_binary(fdf_file, system_label)


    def _run_siesta_binary(self, fdf_file: Path, system_label: str) -> SiestaExecutionResult:
        """Run main siesta executable."""
        cmd = ["siesta"]

        # Modern SIESTA can take FDF file as argument
        # Fallback to stdin redirection for compatibility
        use_stdin = True  # Can detect version and decide

        if use_stdin:
            # siesta < input.fdf > output.out
            with open(fdf_file, 'r') as fdf_in:
                result = subprocess.run(
                    cmd,
                    stdin=fdf_in,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.workdir,
                    text=True,
                )
        else:
            # siesta input.fdf > output.out
            cmd.append(str(fdf_file))
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.workdir,
                text=True,
            )

        # Save stdout to .out file
        out_file = self.workdir / f"{system_label}.out"
        out_file.write_text(result.stdout)

        # Check for errors
        success = result.returncode == 0
        error = None

        if not success:
            error = f"SIESTA failed with return code {result.returncode}\n{result.stderr}"
        elif "FATAL" in result.stdout or "ERROR" in result.stdout:
            success = False
            error = "SIESTA reported fatal error (check .out file)"

        return SiestaExecutionResult(
            success=success,
            return_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            system_label=system_label,
            error=error,
        )


    def _run_gnubands(self, system_label: str) -> SiestaExecutionResult:
        """Run gnubands utility for band structure plotting."""
        bands_file = self.workdir / f"{system_label}.bands"

        if not bands_file.exists():
            return SiestaExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"{bands_file} not found",
                system_label=system_label,
                error=f"Required input {bands_file} missing",
            )

        cmd = [
            "gnubands",
            "-G",                        # Generate gnuplot script
            "-F",                        # Shift Fermi to zero
            "-b", "1",                   # First band
            "-B", "20",                  # Number of bands
            str(bands_file),
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.workdir,
            text=True,
        )

        return SiestaExecutionResult(
            success=result.returncode == 0,
            return_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            system_label=system_label,
        )


    def _run_eig2dos(self, system_label: str) -> SiestaExecutionResult:
        """Run Eig2DOS utility for DOS calculation."""
        # Similar to gnubands
        # Implementation omitted for brevity
        pass
```

### Output Parser

```python
# drivers/siesta/io/output_parser.py
import re
from pathlib import Path
from dataclasses import dataclass
import numpy as np

@dataclass
class SiestaParseResult:
    final_energy: float | None
    forces: np.ndarray | None
    stress: np.ndarray | None
    final_structure: dict | None
    scf_converged: bool = False

class SiestaOutputParser:
    """Parse SIESTA output files."""

    def __init__(self, workdir: Path, system_label: str):
        self.workdir = workdir
        self.system_label = system_label

    def parse_all(self, step_type: str) -> SiestaParseResult:
        """Parse all relevant outputs for given step type."""

        # Parse main output file (.out or stdout)
        out_file = self.workdir / f"{self.system_label}.out"
        result = self._parse_main_output(out_file)

        # Parse additional files based on step type
        if step_type in ["siesta_relax", "siesta_vc_relax"]:
            result.final_structure = self._parse_struct_out()

        # Try NetCDF if available (more robust)
        nc_file = self.workdir / f"{self.system_label}.nc"
        if nc_file.exists():
            self._parse_netcdf(nc_file, result)

        return result


    def _parse_main_output(self, out_file: Path) -> SiestaParseResult:
        """Parse SIESTA stdout output."""
        if not out_file.exists():
            return SiestaParseResult(None, None, None, None)

        text = out_file.read_text()

        # Extract final energy
        energy = None
        energy_match = re.search(r"siesta:\s+Total\s+=\s+([-\d.]+)", text)
        if energy_match:
            energy = float(energy_match.group(1))

        # Extract forces (last occurrence)
        forces = self._extract_forces(text)

        # Extract stress (for vc-relax)
        stress = self._extract_stress(text)

        # Check SCF convergence
        scf_converged = "SCF Convergence" in text or "scf: converged" in text

        return SiestaParseResult(
            final_energy=energy,
            forces=forces,
            stress=stress,
            final_structure=None,
            scf_converged=scf_converged,
        )


    def _extract_forces(self, text: str) -> np.ndarray | None:
        """Extract forces from output text."""
        # SIESTA prints forces in a table format
        # Example:
        # siesta: Atomic forces (eV/Ang):
        # siesta:    -0.000000   -0.000926   -0.000000
        # siesta:    -0.000000    0.000000    0.000004

        forces_section = re.findall(
            r"siesta: Atomic forces.*?\n((?:siesta:\s+[-\d.\s]+\n)+)",
            text,
            re.DOTALL
        )

        if not forces_section:
            return None

        # Take last occurrence (final geometry)
        last_forces = forces_section[-1]

        force_lines = re.findall(r"siesta:\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", last_forces)
        forces = np.array([[float(x), float(y), float(z)] for x, y, z in force_lines])

        return forces


    def _parse_struct_out(self) -> dict:
        """Parse .STRUCT_OUT file for final structure."""
        struct_file = self.workdir / f"{self.system_label}.STRUCT_OUT"

        if not struct_file.exists():
            return None

        # .STRUCT_OUT is in FDF format
        # Parse lattice vectors and atomic coordinates
        # Implementation omitted for brevity
        # Return structure dict compatible with QMatSuite
        pass


    def _parse_netcdf(self, nc_file: Path, result: SiestaParseResult):
        """Parse NetCDF output (more structured than text)."""
        try:
            import netCDF4 as nc

            with nc.Dataset(nc_file, 'r') as ds:
                # Energy
                if 'E_total' in ds.variables:
                    result.final_energy = float(ds.variables['E_total'][-1])

                # Forces
                if 'fa' in ds.variables:
                    result.forces = ds.variables['fa'][-1, :, :]

                # Stress
                if 'stress' in ds.variables:
                    result.stress = ds.variables['stress'][-1, :, :]

                # Structure
                if 'xa' in ds.variables:
                    positions = ds.variables['xa'][-1, :, :]
                    cell = ds.variables['cell'][-1, :, :]
                    result.final_structure = {
                        'positions': positions,
                        'cell': cell,
                        # ... species info ...
                    }

        except ImportError:
            # NetCDF4 not available, skip
            pass
```

---

## Implementation Roadmap

### Phase 1: Basic SCF and Relaxation (Weeks 1-2)

**Goals**: Single-step calculations without dependencies.

**Deliverables**:
1. ✅ Driver skeleton (`SiestaDriver`, registration)
2. ✅ Step types: `siesta_scf`, `siesta_relax`, `siesta_vc_relax`
3. ✅ Handler with basic execution flow
4. ✅ FDF recipe (structure + basic parameters)
5. ✅ Output parser (energy, forces, structure)
6. ✅ Tests: End-to-end SCF and relax on H2O, Si bulk

**Success Criteria**:
- Run `siesta_scf` on water molecule → correct energy
- Run `siesta_relax` on distorted Si → relaxed structure

---

### Phase 2: Multi-Step Workflows (Weeks 3-4)

**Goals**: Bands, DOS, MD with artifact passing.

**Deliverables**:
1. ✅ Artifact staging mechanism (copy `.TSHS`, `.XV` between steps)
2. ✅ Step types: `siesta_bands`, `siesta_gnubands`, `siesta_dos`, `siesta_md`
3. ✅ Recipe extensions (BandLines, PDOS blocks, MD parameters)
4. ✅ Output parsers (bands, DOS, trajectories)
5. ✅ Workflow templates: "siesta_bands_workflow", "siesta_dos_workflow"
6. ✅ Tests: SCF → Bands → gnubands chain, MD restart

**Success Criteria**:
- Run band structure workflow on Si → plotted bands
- Run MD, restart, continue → continuous trajectory

---

### Phase 3: Advanced Features (Weeks 5-8)

**Goals**: Phonons, TranSIESTA, TDDFT.

**Deliverables**:
1. ⏳ Phonon workflow with dynamic displacement steps
2. ⏳ TranSIESTA electrode + device workflow
3. ⏳ TDDFT step type (`siesta_tddft`)
4. ⏳ Optical properties parsing
5. ⏳ Kernel extension for dynamic step generation (if needed)

**Success Criteria**:
- Run phonon workflow on simple crystal → phonon dispersion
- Run TranSIESTA on molecular junction → I-V curve

---

### Testing Strategy

**Unit Tests** (`tests/drivers/siesta/`):
- FDF writer (various step types)
- Output parsers (mock output files)
- Structure converter (QMatSuite ↔ SIESTA format)

**Integration Tests** (`tests/integration/siesta/`):
- End-to-end SCF calculation
- Relaxation with structure update
- Band structure workflow (SCF + Bands + gnubands)
- MD restart

**Regression Tests**:
- Compare energies/forces against reference SIESTA calculations
- Use examples from official SIESTA tutorials

---

## Challenges & Recommendations

### Challenge 1: Implicit vs. Explicit Calculation Types

**Issue**: SIESTA determines calculation type from FDF parameters (implicit), while QMatSuite uses explicit step types.

**Example**: Same `siesta` binary can do SCF, relax, or MD depending on FDF content.

**Recommendation**:
- **Use explicit step types** (`siesta_scf`, `siesta_relax`, `siesta_md`)
- **Recipe layer handles FDF generation** based on step type
- **Benefit**: Clearer workflows, better matches QMatSuite philosophy

---

### Challenge 2: Artifact Staging

**Issue**: SIESTA reads restart files (`.DM`, `.TSHS`, `.XV`) from CWD, but QMatSuite uses isolated workdirs.

**Solution**:
- **Implement artifact staging** in handler:
  1. Identify required artifacts from step dependencies
  2. Copy artifacts from previous steps' workdirs to current step's workdir
  3. Rename if needed (SystemLabel matching)

**Code Location**: `drivers/siesta/handler.py::_stage_restart_files()`

---

### Challenge 3: SystemLabel Matching

**Issue**: SIESTA uses `SystemLabel` to name all output files. If Step B reads `.TSHS` from Step A, it expects file named `{StepB_SystemLabel}.TSHS`.

**Example**:
- Step A (SCF): `SystemLabel = scf_run` → produces `scf_run.TSHS`
- Step B (Bands): `SystemLabel = bands_run` → looks for `bands_run.TSHS` ❌

**Solution**:
- When staging artifacts, **rename to match current step's SystemLabel**:
  ```python
  shutil.copy(
      prev_step_workdir / "scf_run.TSHS",
      curr_step_workdir / "bands_run.TSHS"  # Rename
  )
  ```

---

### Challenge 4: Pseudopotential Management

**Issue**: SIESTA requires pseudopotential files (`.psf`, `.psml`, `.vps`) in CWD or specified path.

**Recommendation**:
- **QMatSuite pseudopotential library**: Create SIESTA subsection
  ```
  qmatsuite_data/
  └── pseudopotentials/
      └── siesta/
          ├── pbe/         # PBE functional
          │   ├── H.psml
          │   ├── O.psml
          │   └── Si.psml
          └── lda/         # LDA functional
  ```
- **Recipe layer**: Copy required pseudopotentials to workdir before execution
- **FDF parameter**: No need to specify paths (CWD is default)

---

### Challenge 5: Post-Processing Utilities as Steps

**Issue**: Utilities like `gnubands`, `Eig2DOS`, `vibra` are separate executables, not `siesta` binary.

**Recommendation**:
- **Treat utilities as distinct step types**: `siesta_gnubands`, `siesta_eig2dos`, `siesta_vibra`
- **Executor dispatches** based on step type:
  ```python
  if step_type == "siesta_gnubands":
      return self._run_gnubands(...)
  else:
      return self._run_siesta_binary(...)
  ```
- **Benefit**: Explicit workflow representation, clearer dependencies

---

### Challenge 6: Dynamic Step Generation (Phonons)

**Issue**: Phonon calculations require N displacement calculations, where N depends on supercell size and symmetry (not known a priori).

**Current QMatSuite Limitation**: Workflow steps are static (defined in template or user input).

**Recommendations**:
1. **Short-term (Phase 1-2)**: Use **fixed templates** for common cases (e.g., "3x3x3 supercell, 27 atoms" → predefined 81 displacement steps)
2. **Long-term (Phase 3)**: **Extend kernel** to support "generator steps":
   - Step `siesta_phonon_setup` analyzes structure
   - Emits N `siesta_phonon_disp` steps dynamically
   - Final `siesta_vibra` aggregates results
3. **Alternative**: **External scripting layer** generates displacement calculations, submits to QMatSuite as separate calculations

---

### Challenge 7: MD Trajectory Parsing

**Issue**: SIESTA produces trajectories in `.ANI` (XYZ format) or `.nc` (NetCDF), but QMatSuite doesn't have standard trajectory representation.

**Recommendation**:
- **Add trajectory artifact type**: `SiestaArtifactType.TRAJECTORY`
- **Parser extracts snapshots**: Convert `.ANI` → list of structures
- **Storage**: Archive `.ANI` file, store metadata (n_frames, time_step)
- **Future**: Unify trajectory format across codes (LAMMPS, SIESTA, QE CP)

---

### Challenge 8: Preset Mapping

**Issue**: QMatSuite presets are QE-centric (e.g., `ecutwfc`, `ecutrho`). SIESTA uses different parameters (e.g., `MeshCutoff`, `PAO.BasisSize`).

**Recommendation**:
- **Extend preset system** to be engine-aware:
  ```python
  # presets/dimensions.py
  class PrecisionOption(str, Enum):
      LOW = "low"
      MED = "med"
      HIGH = "high"

  # drivers/siesta/recipe.py
  def _precision_to_mesh_cutoff(precision: str) -> str:
      return {
          "LOW": "150.0 Ry",
          "MED": "250.0 Ry",
          "HIGH": "400.0 Ry",
      }[precision]
  ```
- **SIESTA-specific presets**: Add `basis_size` dimension (SZ, DZ, DZP, TZP)

---

### Challenge 9: Convergence Detection

**Issue**: SIESTA's SCF convergence messages vary by version. Need robust parsing.

**Recommendation**:
- **Multi-heuristic approach**:
  1. Search for "scf: converged" in stdout
  2. Check final DM tolerance vs. target
  3. Inspect `.nc` file for convergence flag (if available)
- **Fallback**: If uncertain, mark as "completed but check output"

---

### Challenge 10: Error Classification

**Issue**: SIESTA errors are printed to stdout (not stderr), making classification harder.

**Recommendation**:
- **Pattern matching** in `drivers/siesta/handler.py::classify_error()`:
  ```python
  def classify_error(self, stdout: str, exit_code: int) -> ErrorClass:
      if "not enough memory" in stdout.lower():
          return ErrorClass.RESOURCE
      elif "SCF_NOT_CONV" in stdout or "scf not converged" in stdout.lower():
          return ErrorClass.CONVERGENCE
      elif "SETUP_ERROR" in stdout or "wrong input" in stdout.lower():
          return ErrorClass.INPUT
      else:
          return ErrorClass.UNKNOWN
  ```

---

## References

### Official Documentation
- **SIESTA Manual**: https://docs.siesta-project.org/projects/siesta/en/stable/
- **SIESTA Tutorials**: https://docs.siesta-project.org/projects/siesta/en/stable/tutorials/index.html
- **FDF File Reference**: https://docs.siesta-project.org/projects/siesta/en/stable/reference/fdf-file.html
- **Band Structure Tutorial**: https://docs.siesta-project.org/projects/siesta/en/5.4/tutorials/basic/electronic-structure-analysis/bands/index.html

### Pseudopotentials
- **PseudoDojo** (PSML format): http://www.pseudo-dojo.org
- **SIESTA Pseudopotential Database**: http://departments.icmab.es/leem/siesta/Databases/Pseudopotentials/

### Code Repositories
- **SIESTA GitLab**: https://gitlab.com/siesta-project/siesta
- **Example FDF files**: https://github.com/pritampanda15/Siesta
- **Tutorial examples**: https://github.com/jfaraudo/SIESTA_examples

### Related Tools
- **sisl** (Python library for SIESTA): https://sisl.readthedocs.io/
- **AiiDA-SIESTA**: https://docs.siesta-project.org/projects/aiida-siesta/
- **ASE SIESTA Calculator**: https://wiki.fysik.dtu.dk/ase/ase/calculators/siesta.html

---

## Conclusion

SIESTA integration into QMatSuite is **feasible and well-aligned** with the existing architecture. The monolithic executable model, FDF input format, and artifact-based dependencies fit naturally into QMatSuite's driver system with minor extensions.

**Key Integration Points**:
1. ✅ **Driver model**: SiestaDriver implementing EngineDriver protocol
2. ✅ **Step types**: Explicit types for each calculation mode (scf, relax, bands, md)
3. ⚠️ **Artifact staging**: New mechanism to copy/rename restart files between steps
4. ✅ **Recipe system**: FDF generation from QMatSuite presets
5. ⚠️ **Post-processing**: Utilities (gnubands, Eig2DOS) as separate step types

**Kernel Flexibility Assessment**:
- **Phase 1-2 workflows**: ✅ Current kernel is **sufficiently flexible**
- **Phase 3 workflows**: ⚠️ Phonons require **minor kernel extension** (dynamic steps)
- **Advanced features**: TranSIESTA, Lua scripting work within current model

**Recommended Next Steps**:
1. **Approve this design document** and proceed with implementation
2. **Phase 1 implementation** (SCF, relax): 1-2 weeks
3. **Iterative testing** with SIESTA tutorials as benchmarks
4. **Phase 2 planning** after Phase 1 validation

---

**Document Status**: ✅ Ready for Review
**Next Action**: User approval → Begin Phase 1 implementation

