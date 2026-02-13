# QMatSuite Workflow & Preset Design Document (v0)

**Version**: 0.1  
**Date**: 2025-01-XX  
**Status**: Design Exploration Phase  
**Scope**: First principled abstraction of workflows and presets for QMatSuite

---

## 1. Executive Summary

This document defines the conceptual framework for **workflows** (what physical quantity is computed) and **presets** (what modeling choices the user makes) in QMatSuite. It is grounded in:

1. **Tutorial datasets** (`tests/data/0_*` through `19_*`) as primary workflow examples
2. **QE parameter metadata** (parsed from official QE HTML docs)
3. **Standard DFT practice** for solid-state and molecular calculations
4. **Constitutional constraints** from `CONSTITUTION_ZH.md` Chapter 10

**Key Principles**:
- Workflows represent **physical tasks**, not step sequences
- Presets represent **physics-driven modeling choices**, not named recipes
- `step.yml` is the **unique execution truth**
- Workflows and presets are **runtime interpretations**, never persisted

---

## 2. Step Type Taxonomy (Engine-Agnostic)

### 2.1 Definition of step_type

A **step_type** represents ONE atomic, indivisible computational step that a domain expert naturally understands as "one calculation".

**Key Properties**:
1. Corresponds to one executable invocation or one tightly-coupled run unit
2. May come from ANY engine (QE, Wannier90, LAMMPS, PySCF, etc.)
3. Is NOT an arbitrary abstraction — must not be simplified for convenience
4. Is "obviously one step" to a practitioner

**Important**: Executables are IMPLEMENTATIONS, not definitions. A step_type exists because the computation is indivisible in practice.

### 2.2 QE (Quantum ESPRESSO) Step Types

#### 2.2.1 pw.x Step Types (by `calculation` mode)

| step_type | `calculation` | Physical Task | Indivisible? |
|-----------|---------------|---------------|--------------|
| `scf` | 'scf' | Self-consistent ground state | ✓ |
| `nscf` | 'nscf' | Non-self-consistent (fixed density) | ✓ |
| `bands` | 'bands' | Band energies along k-path | ✓ |
| `relax` | 'relax' | Atomic position optimization | ✓ |
| `vc-relax` | 'vc-relax' | Cell + atomic optimization | ✓ |
| `md` | 'md' | Born-Oppenheimer MD | ✓ |
| `vc-md` | 'vc-md' | Variable-cell MD | ✓ |

**Note**: `scf` and `nscf` are fundamentally different computations even though they use the same executable. Similarly for `relax` vs `vc-relax`.

#### 2.2.2 Other QE Executable Step Types

| step_type | Executable | Physical Task |
|-----------|------------|---------------|
| `dos` | dos.x | Density of states |
| `bands_pp` | bands.x | Band structure post-processing |
| `projwfc` | projwfc.x | Projected DOS |
| `pp` | pp.x | Charge/potential plotting |
| `ph` | ph.x | Phonon DFPT |
| `q2r` | q2r.x | q-space → real-space force constants |
| `matdyn` | matdyn.x | Phonon dispersion interpolation |
| `dynmat` | dynmat.x | Dynamical matrix analysis |
| `turbo_lanczos` | turbo_lanczos.x | TDDFT Lanczos |
| `turbo_spectrum` | turbo_spectrum.x | TDDFT spectrum |
| `gipaw` | gipaw.x | NMR chemical shifts |
| `hp` | hp.x | Hubbard U from first principles |
| `epw` | epw.x | Electron-phonon (Wannier) |
| `neb` | neb.x | Nudged elastic band |
| `cp` | cp.x | Car-Parrinello MD |

### 2.3 Wannier90 Step Types

Based on analysis of Wannier90 documentation and examples:

#### 2.3.1 Indivisible Wannier90 Steps

| step_type | Executable / Mode | Physical Task | Notes |
|-----------|-------------------|---------------|-------|
| `w90_preproc` | `wannier90.x -pp seedname` | Generate .nnkp file | Pre-processing mode |
| `pw2wannier90` | `pw2wannier90.x` | Generate .mmn/.amn/.eig | QE interface |
| `w90_main` | `wannier90.x seedname` | MLWF construction | Main wannierization |
| `postw90` | `postw90.x seedname` | Berry quantities, transport | Post-processing |

**Rationale for step separation**:
- `w90_preproc` MUST run before `pw2wannier90` (generates .nnkp)
- `pw2wannier90` MUST run after QE nscf (needs wavefunctions)
- `w90_main` MUST run after `pw2wannier90` (needs .mmn/.amn files)
- `postw90` is optional, requires completed wannierization

These are clearly separate invocations that practitioners run sequentially — NOT one combined step.

#### 2.3.2 Wannier90 Input/Output Files

| File | Producer | Consumer | Purpose |
|------|----------|----------|---------|
| `seedname.win` | User/QMatSuite | All W90 steps | Main input |
| `seedname.nnkp` | `w90_preproc` | `pw2wannier90` | k-point neighbors |
| `seedname.mmn` | `pw2wannier90` | `w90_main` | Overlap matrices |
| `seedname.amn` | `pw2wannier90` | `w90_main` | Projection matrices |
| `seedname.eig` | `pw2wannier90` | `w90_main` | Eigenvalues |
| `seedname.chk` | `w90_main` | `postw90` | Checkpoint (U matrices) |
| `seedname_hr.dat` | `w90_main` | Analysis | Hamiltonian in WF basis |

### 2.4 Step Type Registry Summary

**v0 (Core)**:
- QE pw.x: `scf`, `nscf`, `bands`, `relax`, `vc-relax`
- QE post-proc: `dos`, `bands_pp`, `projwfc`

**v1 (Secondary)**:
- QE: `md`, `ph`, `q2r`, `matdyn`
- Wannier90: `w90_preproc`, `pw2wannier90`, `w90_main`

**v2+ (Advanced)**:
- QE: `vc-md`, `turbo_lanczos`, `turbo_spectrum`, `gipaw`, `hp`, `epw`, `neb`, `cp`, `pp`
- Wannier90: `postw90`

---

## 2.5 Sources Analysis (from tutorial datasets)

### 2.5.1 Tutorial Datasets Mapping

The following table maps `tests/data/` tutorial folders to workflow categories:

| Dataset | Folder | Step Sequence | Physical Task | Category |
|---------|--------|---------------|---------------|----------|
| 0 | `0_Si_scf` | SCF | Ground state energy | Ground State |
| 1 | `1_H2` | relax, SCF | Molecular geometry + energy | Structure Optimization |
| 2 | `2_H2O` | relax | Molecular geometry | Structure Optimization |
| 3 | `3_Si_vc_relax` | vc-relax | Lattice optimization | Structure Optimization |
| 4 | `4_Si_DOS` | SCF → NSCF → DOS | Density of states | Electronic Structure |
| 5 | `5_NH3_inversion` | relax → NEB | Reaction pathway / barrier | Transition State |
| 6 | `6_Al_DOS` | vc-relax → SCF → NSCF → DOS | Metallic DOS | Electronic Structure |
| 7 | `7_Si_bandStructure` | SCF → NSCF → bands → bands.pp | Band structure | Electronic Structure |
| 8 | `8_Fe_DOS` | vc-relax → SCF → NSCF → DOS | Spin-polarized DOS | Electronic Structure (Magnetic) |
| 9 | `9_Si_phonon` | SCF → PH → Q2R → MATDYN | Phonon dispersion | Lattice Dynamics |
| 10 | `10_benzene_TDDFT` | relax → SCF → turbo_lanczos → turbo_spectrum | Optical absorption | Optical Properties |
| 11 | `11_Si_100_surface` | relax | Surface reconstruction | Surface Science |
| 12 | `12_NMR_gipaw` | SCF → GIPAW | NMR chemical shifts | Spectroscopy |
| 13 | `13_graphene` | vc-relax → SCF → bands → bands.pp | 2D material bands | Electronic Structure |
| 14 | `14_DFT_plus_U_NiO` | SCF → NSCF → DOS | Strongly correlated system | Electronic Structure (Correlated) |
| 15 | `15_bulk_modulus_Si` | SCF×3 | Equation of state | Mechanical Properties |
| 16 | `16_Si_vacancy_diffusion` | relax → NEB | Defect migration | Transition State |
| 17 | `17_H2O_vibration` | relax → PH | Molecular vibrations | Lattice Dynamics (Molecular) |
| 18 | `18_H2O_MD` | relax → MD | Molecular dynamics | Dynamics |
| 19 | `19_Si_CPMD` | vc-relax → CP | Car-Parrinello MD | Dynamics |

### 2.5.2 Existing Step Types (in codebase)

From `src/quantumvitas/calculation/step_defaults.py`:

```python
KNOWN_STEP_TYPES = {
    "scf", "nscf", "relax", "vc-relax", "md", "vc-md",  # pw.x
    "dos", "bands", "bands_pw",  # post-processing
    "ph", "q2r", "matdyn", "dynmat",  # phonon
    "pp", "projwfc",  # other post-processing
    "custom",  # escape hatch
}
```

### 2.5.3 Key QE Parameters for Presets

From `src/quantumvitas/data/qe_module_parameters.json`:

| Parameter | Section | Values | Physical Meaning |
|-----------|---------|--------|------------------|
| `nspin` | SYSTEM | 1, 2, 4 | Spin treatment (none, collinear, noncollinear) |
| `noncolin` | SYSTEM | .true./.false. | Noncollinear magnetism |
| `lspinorb` | SYSTEM | .true./.false. | Spin-orbit coupling |
| `starting_magnetization(i)` | SYSTEM | Real | Initial magnetic moment per type |
| `occupations` | SYSTEM | 'smearing', 'tetrahedra', 'fixed', 'from_input' | Band filling treatment |
| `smearing` | SYSTEM | 'gaussian', 'mp', 'mv', 'fd' | Smearing function type |
| `degauss` | SYSTEM | Real | Smearing width |
| `ecutwfc` | SYSTEM | Real | Plane-wave cutoff (Ry) |
| `ecutrho` | SYSTEM | Real | Charge density cutoff (Ry) |
| `lda_plus_u` | SYSTEM | .true./.false. | DFT+U correction |
| `Hubbard_U(i)` | SYSTEM | Real | Hubbard U parameter per type |
| `conv_thr` | ELECTRONS | Real | SCF convergence threshold |
| `mixing_beta` | ELECTRONS | Real | SCF mixing parameter |

---

## 3. Workflow Identification and Prioritization

### 3.1 Core Workflows (v0 - Must Have)

#### 3.1.1 Ground State Energy (SCF)
- **Physical Task**: Compute ground-state total energy and electron density
- **Step Sequence**: `scf`
- **System Type**: Both solid-state and molecular
- **Importance**: **Critical** - Foundation for all other calculations
- **Post-processing**: Energy, forces, stress (if computed)

#### 3.1.2 Structure Optimization
- **Physical Task**: Find equilibrium atomic positions and/or cell parameters
- **Variants**:
  - **Atomic Relaxation** (`relax`): Fixed cell, optimize atoms
  - **Full Relaxation** (`vc-relax`): Optimize both cell and atoms
- **System Type**: Both
- **Importance**: **Critical** - Required before most property calculations
- **Post-processing**: Final structure, energy, forces
- **Note**: Must be standalone calculation, not embedded in other workflows

#### 3.1.3 Density of States (DOS)
- **Physical Task**: Compute electronic density of states
- **Step Sequence**: `scf` → `nscf` → `dos`
- **System Type**: Both
- **Importance**: **High** - Very common analysis
- **Post-processing**: DOS plot, band gap estimation

#### 3.1.4 Band Structure
- **Physical Task**: Compute electronic band dispersion along k-path
- **Step Sequence**: `scf` → `bands_pw` → `bands` (post-processing)
- **System Type**: Primarily solid-state
- **Importance**: **High** - Very common analysis
- **Post-processing**: Band plot, band gap, effective masses

### 3.2 Secondary Workflows (v1)

#### 3.2.1 Phonon Dispersion
- **Physical Task**: Compute lattice vibrational frequencies
- **Variants**:
  - **Gamma-point (molecular)**: `scf` → `ph` (at Γ) - molecular vibrations
  - **DFPT dispersion**: `scf` → `ph` (q-grid) → `q2r` → `matdyn` - analytical, efficient
  - **Numerical/Supercell**: `scf` (supercell) → finite displacements - flexible, any functional
- **System Type**: Both
- **Importance**: **Medium** - Important for thermodynamics, stability, spectroscopy
- **Post-processing**: 
  - Phonon DOS (vibrational density of states)
  - Phonon dispersion along high-symmetry paths
  - Thermodynamic properties (free energy, entropy, heat capacity)
  - IR intensities (from Born effective charges)
- **Key Parameters**:
  - `tr2_ph`: Phonon convergence threshold
  - `asr`: Acoustic sum rule ('crystal', 'simple', 'no')
  - Q-point grid density
- **Reference**: [SCM QE DFPT Phonons](https://www.scm.com/doc/QuantumEspresso/examples.html#analytical-calculation-of-phonons-using-dfpt), [SCM QE Numerical Phonons](https://www.scm.com/doc/QuantumEspresso/examples.html#numerical-calculation-of-phonons)

#### 3.2.2 Molecular Dynamics
- **Physical Task**: Simulate atomic trajectories at finite temperature
- **Variants**:
  - **Born-Oppenheimer MD** (`md`): Forces from DFT at each step
  - **Car-Parrinello MD** (`cp.x`): Coupled electron-ion dynamics
- **System Type**: Both
- **Importance**: **Medium** - Important for dynamics, sampling
- **Post-processing**: Trajectory, RDF, MSD, diffusion coefficients

#### 3.2.3 Projected DOS (PDOS)
- **Physical Task**: Atom/orbital-resolved density of states
- **Step Sequence**: `scf` → `nscf` → `projwfc`
- **System Type**: Both
- **Importance**: **Medium** - Chemical bonding analysis

### 3.3 Advanced Workflows (v2+)

#### 3.3.1 Work Function / Surface Properties
- **Physical Task**: Compute work function and vacuum level from slab models
- **Step Sequence**: `scf` (with dipole correction) → `pp.x` → `average.x`
- **System Type**: Surface/slab (solid-state)
- **Importance**: **Medium** - Important for surface science, catalysis
- **Key Parameters**:
  - `tefield = .true.` (enable electric field)
  - `dipfield = .true.` (dipole correction)
  - `edir = 3` (direction perpendicular to slab)
  - `emaxpos`, `eopreg` (dipole correction positioning)
- **Post-processing**: Plane-averaged electrostatic potential profile, work function = vacuum level - Fermi energy
- **Reference**: [SCM QE Work Function Example](https://www.scm.com/doc/QuantumEspresso/examples.html#slab-with-dipole-correction-work-function)

#### 3.3.2 IR/Raman Spectra
- **Physical Task**: Compute vibrational spectra with IR and Raman intensities
- **Step Sequence**: `relax` → `scf` → DFPT phonons + Raman
- **System Type**: Both
- **Importance**: **Medium** - Important for spectroscopy
- **Requirements**: 
  - Norm-conserving pseudopotentials for Raman
  - LDA functional for Raman intensities
- **Post-processing**: IR spectrum, Raman spectrum, vibrational mode visualization
- **Reference**: [SCM QE IR/Raman Example](https://www.scm.com/doc/QuantumEspresso/examples.html#ir-raman-spectra)

#### 3.3.3 Transition State / Saddle Search
- **Physical Task**: Find minimum energy path, reaction barriers, transition states
- **Variants**:
  - **NEB** (`neb.x`): Nudged elastic band for reaction pathways
  - **PES Exploration**: Automated saddle point search with relaxation to products/reactants
- **Step Sequence**: `relax` (endpoints) → `neb.x` or PES exploration
- **System Type**: Both
- **Importance**: **Low** - Specialized for reaction kinetics
- **Reference**: [SCM QE PES Exploration Example](https://www.scm.com/doc/QuantumEspresso/examples.html#pes-exploration)

#### 3.3.4 Equation of State / PES Scanning
- **Physical Task**: Compute energy vs. volume curve, bulk modulus
- **Step Sequence**: Multiple SCF at systematically varied cell volumes
- **System Type**: Solid-state
- **Importance**: **Low** - Specialized for mechanical/thermodynamic properties
- **Note**: Can combine with DOS/bands calculation at each volume
- **Reference**: [SCM QE PESScan Example](https://www.scm.com/doc/QuantumEspresso/examples.html#pesscan-volume-scan)

#### 3.3.5 Optical Properties (TDDFT)
- **Physical Task**: Compute optical absorption spectrum
- **Step Sequence**: `scf` → `turbo_lanczos` → `turbo_spectrum`
- **System Type**: Primarily molecular
- **Importance**: **Low** - Specialized

#### 3.3.6 NMR Chemical Shifts
- **Physical Task**: Compute magnetic shielding tensors
- **Step Sequence**: `scf` → `gipaw.x`
- **System Type**: Both
- **Importance**: **Low** - Specialized for NMR spectroscopy

#### 3.3.7 Strongly Correlated Systems (DFT+U)
- **Physical Task**: Treat localized electrons with Hubbard correction
- **System Type**: Solid-state (transition metal oxides, f-electrons)
- **Importance**: **Low** - Specialized
- **Note**: Not a separate workflow, but a preset modifier

### 3.4 Wannier90 Workflows (v1-v2)

Wannier90 workflows enable advanced electronic structure analysis including band interpolation, Berry curvature, and transport properties.

#### 3.4.1 Basic MLWF Construction

**Physical Task**: Construct maximally localized Wannier functions from Bloch states

**Step Sequence**:
```
[QE] scf → [QE] nscf → [W90] w90_preproc → [QE] pw2wannier90 → [W90] w90_main
```

| Step | Engine | step_type | Input | Output |
|------|--------|-----------|-------|--------|
| 1 | QE | `scf` | structure | charge density |
| 2 | QE | `nscf` | charge density | wavefunctions on uniform k-grid |
| 3 | W90 | `w90_preproc` | .win | .nnkp |
| 4 | QE | `pw2wannier90` | wavefunctions + .nnkp | .mmn, .amn, .eig |
| 5 | W90 | `w90_main` | .mmn, .amn, .eig | MLWFs, .chk |

**Key Wannier90 Parameters** (in `seedname.win`):
- `num_wann`: Number of Wannier functions
- `num_bands`: Number of bands (if different from num_wann)
- `projections`: Initial projection orbitals
- `num_iter`: Number of MLWF iterations

**System Type**: Solid-state
**Importance**: **Medium** - Foundation for Wannier-based analysis
**Tier**: v1

#### 3.4.2 Wannier Band Interpolation

**Physical Task**: Interpolate band structure from coarse k-grid using MLWFs

**Step Sequence**: Basic MLWF construction, then:
```
[W90] w90_main (with kpoint_path)
```

**Key Parameters**:
- `kpoint_path`: High-symmetry k-path for interpolation
- `bands_plot = .true.`

**Output**: `seedname_band.dat` - interpolated bands
**Importance**: **Medium** - Efficient alternative to direct nscf bands calculation
**Tier**: v1

#### 3.4.3 Wannier with Disentanglement (Metals/Entangled Bands)

**Physical Task**: Extract MLWFs from entangled band manifold (e.g., metals)

**Step Sequence**: Same as Basic MLWF, but with disentanglement parameters

**Key Parameters**:
- `dis_win_min`, `dis_win_max`: Outer energy window
- `dis_froz_min`, `dis_froz_max`: Frozen (inner) energy window
- `dis_num_iter`: Disentanglement iterations
- `dis_mix_ratio`: Mixing for disentanglement

**Physical Meaning**:
- Outer window: All bands considered for projection
- Frozen window: Bands reproduced exactly (typically around Fermi level)

**Example** (from Fe SOC example):
```
dis_win_min = -8.0
dis_win_max = 70.0
dis_froz_min = -8.0
dis_froz_max = 30.0
```

**Importance**: **Medium** - Required for metals
**Tier**: v1

#### 3.4.4 Wannier Berry Curvature / Anomalous Hall Effect

**Physical Task**: Compute Berry curvature and anomalous Hall conductivity

**Step Sequence**: Basic MLWF construction, then:
```
[W90] postw90 (with berry options)
```

**Key Parameters**:
- `berry = .true.`
- `berry_task = ahc` (anomalous Hall conductivity)
- `berry_kmesh`: Dense k-mesh for integration

**System Type**: Magnetic metals (SOC required)
**Importance**: **Low** - Specialized
**Tier**: v2

#### 3.4.5 Wannier with SOC (Spinor Wavefunctions)

**Physical Task**: Construct MLWFs from spinor (SOC) calculations

**Step Sequence**: Same as Basic MLWF, but with:
- QE nscf: `noncolin = .true.`, `lspinorb = .true.`
- pw2wannier90: `spin_component = 'none'` (for spinors)
- W90: `spinors = .true.`

**Key Parameters** (Wannier90):
- `spinors = .true.`: Enable spinor mode
- Projections must include spin character

**Important Constraint**: Requires fully-relativistic pseudopotentials

**Importance**: **Low** - Specialized for topological materials
**Tier**: v2

#### 3.4.6 Wannier Transport (BoltzWann)

**Physical Task**: Compute Boltzmann transport coefficients

**Step Sequence**: Basic MLWF construction, then:
```
[W90] postw90 (with boltzwann options)
```

**Key Parameters**:
- `boltzwann = .true.`
- `boltz_kmesh`: k-mesh for transport
- `boltz_temp`: Temperature range
- `boltz_mu_min/max`: Chemical potential range

**Output**: Seebeck coefficient, electrical conductivity, thermal conductivity
**Importance**: **Very Low** - Specialized
**Tier**: v2+

### 3.5 Specialized Workflows (v3+ / Expert)

The following workflows are identified from the QE test-suite and represent specialized use cases:

#### 3.5.1 Electron-Phonon Coupling (EPW)
- **Physical Task**: Compute electron-phonon coupling matrix elements for superconductivity, transport
- **Step Sequence**: `scf` → `nscf` (coarse k) → `ph` (coarse q) → `epw.x` (Wannier interpolation)
- **System Type**: Solid-state
- **Importance**: **Very Low** - Specialized for superconductivity, thermoelectrics
- **Key Parameters**:
  - `elph = .true.` (compute e-ph coupling)
  - `wannierize = .true.` (construct Wannier functions)
  - `fsthick` (Fermi surface thickness)
  - Fine k/q grids for interpolation
- **Post-processing**: Eliashberg function α²F(ω), λ (coupling strength), Tc estimates

#### 3.5.2 Hubbard Parameters from First Principles (HP)
- **Physical Task**: Self-consistently compute Hubbard U values using DFPT
- **Step Sequence**: `scf` (with initial U guess) → `hp.x`
- **System Type**: Solid-state (transition metal compounds)
- **Importance**: **Very Low** - Specialized for strongly correlated systems
- **Key Parameters**:
  - `HUBBARD {atomic}` card with initial U values
  - `nq1, nq2, nq3` (q-grid for HP calculation)
  - `conv_thr_chi` (response function convergence)
- **Note**: Modern QE 7.x uses the `HUBBARD` card instead of `lda_plus_u` and `Hubbard_U`

#### 3.5.3 Koopmans Functionals (KCW)
- **Physical Task**: Beyond-DFT band gaps using orbital-density-dependent functionals
- **Step Sequence**: `scf` → `pw2wannier90` → `wannier90.x` → `kcw_wann2kcw` → `kcw_screen` → `kcw_ham`
- **System Type**: Solid-state
- **Importance**: **Very Low** - Research-level beyond-DFT method
- **Note**: Complex multi-step workflow requiring Wannier90 integration

#### 3.5.4 Berry Phase / Electric Polarization
- **Physical Task**: Compute electronic polarization using Berry phase formulation
- **Step Sequence**: `scf` → `nscf` (with `lberry = .true.`)
- **System Type**: Ferroelectrics, piezoelectrics (solid-state)
- **Importance**: **Very Low** - Specialized for polarization studies
- **Key Parameters**:
  - `lberry = .true.` (Berry phase calculation)
  - `gdir` (polarization direction: 1, 2, or 3)
  - `nppstr` (k-points along string)
- **Note**: Requires k-point strings along polarization direction

#### 3.5.5 TDDFPT Magnons
- **Physical Task**: Compute magnon dispersion using time-dependent DFPT
- **Step Sequence**: `scf` (magnetic) → `turbo_magnon.x` → `turbo_spectrum`
- **System Type**: Magnetic solids
- **Importance**: **Very Low** - Specialized for magnetic materials
- **Key Parameters**: Magnetic SCF setup + TDDFPT linear response

#### 3.5.6 EELS (Electron Energy Loss Spectroscopy)
- **Physical Task**: Compute EELS spectrum from linear response
- **Step Sequence**: `scf` → `turbo_eels.x` → `turbo_spectrum`
- **System Type**: Solid-state
- **Importance**: **Very Low** - Specialized spectroscopy

---

## 4. Preset Dimensions (Physics-Driven Options)

### 4.1 Core Presets (v0)

#### 4.1.1 Spin Treatment (`spin`)

**Physical Meaning**: How electron spin is treated in the calculation.

| Option | `nspin` | `noncolin` | Physical Scenario |
|--------|---------|------------|-------------------|
| `nonspin` | 1 | - | Closed-shell systems, nonmagnetic materials |
| `collinear` | 2 | .false. | Ferromagnets, antiferromagnets with collinear moments |
| `noncollinear` | 4 | .true. | Spin spirals, complex magnetic structures |

**Affected Workflows**: All  
**Parameters**:
- `SYSTEM.nspin`
- `SYSTEM.noncolin`
- `SYSTEM.starting_magnetization(i)` (when spin ≠ nonspin)

**Compiler Output (Canonical)**:
```yaml
# For nonspin:
SYSTEM:
  nspin: 1

# For collinear:
SYSTEM:
  nspin: 2
  starting_magnetization(1): 0.5  # Must be explicit

# For noncollinear:
SYSTEM:
  noncolin: .true.
  # nspin is NOT written (implicitly 4)
```

**Detector Logic**:
- If `nspin` absent → assume `1` (nonspin)
- If `nspin = 1` → nonspin
- If `nspin = 2` → collinear
- If `noncolin = .true.` → noncollinear

#### 4.1.2 Spin-Orbit Coupling (`soc`)

**Physical Meaning**: Whether relativistic spin-orbit interaction is included.

| Option | `lspinorb` | Physical Scenario |
|--------|------------|-------------------|
| `no_soc` | .false. | Light elements, non-relativistic |
| `with_soc` | .true. | Heavy elements, topological materials |

**Affected Workflows**: All  
**Parameters**:
- `SYSTEM.lspinorb`

**Interactions**:
- `soc = with_soc` requires `spin = noncollinear`
- This is a 2×2 interaction matrix:

| spin \ soc | no_soc | with_soc |
|------------|--------|----------|
| nonspin | ✓ | ✗ (invalid) |
| collinear | ✓ | ✗ (invalid) |
| noncollinear | ✓ | ✓ |

**Compiler Enforcement**: If `soc = with_soc`, automatically set `spin = noncollinear`.

**Compiler Output (Canonical)**:
```yaml
# For no_soc:
SYSTEM:
  lspinorb: .false.

# For with_soc:
SYSTEM:
  noncolin: .true.
  lspinorb: .true.
```

**Detector Logic**:
- If `lspinorb` absent → assume `.false.` (no_soc)
- If `lspinorb = .false.` → no_soc
- If `lspinorb = .true.` → with_soc

#### 4.1.3 Material Type (`material`)

**Physical Meaning**: Electronic structure characteristics affecting occupation treatment.

| Option | `occupations` | `smearing` | Physical Scenario |
|--------|---------------|------------|-------------------|
| `insulator` | 'tetrahedra' or 'fixed' | - | Semiconductors, ionic crystals |
| `metal` | 'smearing' | 'mv' | Metals, conducting systems |

**Affected Workflows**: DOS, bands  
**Parameters**:
- `SYSTEM.occupations`
- `SYSTEM.smearing` (if metal)
- `SYSTEM.degauss` (if metal)

**Compiler Output (Canonical)**:
```yaml
# For insulator (DOS):
SYSTEM:
  occupations: tetrahedra

# For metal:
SYSTEM:
  occupations: smearing
  smearing: marzari-vanderbilt
  degauss: 0.01
```

**Detector Logic**:
- If `occupations = 'tetrahedra'` or `'fixed'` → insulator
- If `occupations = 'smearing'` → metal
- If `occupations` absent → insulator (default)

### 4.2 Secondary Presets (v1)

#### 4.2.1 Accuracy Level (`accuracy`)

**Physical Meaning**: Trade-off between computational cost and precision.

| Option | `ecutwfc` | `conv_thr` | K-grid density |
|--------|-----------|------------|----------------|
| `low` | 30 Ry | 1e-6 | 4×4×4 |
| `medium` | 50 Ry | 1e-8 | 8×8×8 |
| `high` | 80 Ry | 1e-10 | 12×12×12 |

**Note**: Actual cutoffs depend on pseudopotential recommendations.

**Affected Workflows**: All  
**Parameters**:
- `SYSTEM.ecutwfc`
- `SYSTEM.ecutrho` (typically 8-12× ecutwfc)
- `ELECTRONS.conv_thr`
- `K_POINTS` grid

#### 4.2.2 DFT+U Correction (`hubbard`)

**Physical Meaning**: Hubbard correction for localized electrons.

| Option | `lda_plus_u` | Physical Scenario |
|--------|--------------|-------------------|
| `no_hubbard` | .false. | Standard DFT |
| `with_hubbard` | .true. | Transition metal oxides, rare earths |

**Affected Workflows**: All  
**Parameters**:
- `SYSTEM.lda_plus_u`
- `SYSTEM.Hubbard_U(i)` (must be provided per atom type)

**Note**: U values are material-specific; presets provide scaffolding, user specifies values.

#### 4.2.3 Wannier Disentanglement (`w90_disentangle`)

**Physical Meaning**: Whether to use disentanglement procedure for entangled bands.

| Option | Required for | Physical Scenario |
|--------|--------------|-------------------|
| `no_disentangle` | Isolated bands | Insulators, well-separated valence bands |
| `with_disentangle` | Entangled bands | Metals, materials with band crossings |

**Affected Workflows**: All Wannier90 workflows
**Parameters** (in `.win` file):
- `dis_win_min`, `dis_win_max`: Outer energy window
- `dis_froz_min`, `dis_froz_max`: Frozen (inner) window
- `dis_num_iter`: Disentanglement iterations

**Interaction with `material` preset**:

| material \ w90_disentangle | no_disentangle | with_disentangle |
|---------------------------|----------------|------------------|
| insulator | ✓ (typical) | ✓ (optional) |
| metal | ✗ (usually fails) | ✓ (required) |

**Compiler Logic**: If `material = metal` → automatically set `w90_disentangle = with_disentangle`

### 4.3 Preset Interaction Summary

The following interaction matrix shows valid preset combinations:

#### 4.3.1 Spin × SOC × Wannier Interactions

| Combination | QE Parameters | Wannier90 Requirements |
|-------------|---------------|------------------------|
| nonspin + no_soc | `nspin=1` | Standard projections |
| collinear + no_soc | `nspin=2` | Separate up/down runs (for each spin channel) |
| noncollinear + no_soc | `noncolin=.true.` | `spinors=.true.` |
| noncollinear + with_soc | `noncolin=.true.`, `lspinorb=.true.` | `spinors=.true.`, FR pseudopotentials |

**Important**: Wannier90 `spinors=.true.` is required when QE uses `noncolin=.true.`

#### 4.3.2 Three-Way Interaction Table: Spin × SOC × Material

```
                           no_soc                    with_soc
                    insulator   metal          insulator   metal
    nonspin            ✓          ✓               ✗          ✗
    collinear          ✓          ✓               ✗          ✗
    noncollinear       ✓          ✓               ✓          ✓
```

**Legend**: ✓ = valid, ✗ = invalid (SOC requires noncollinear)

### 4.4 Advanced Presets (v2+)

#### 4.3.1 System Type (`system_type`)

**Physical Meaning**: Boundary conditions and special treatment for different system geometries.

| Option | `assume_isolated` | `edir` | Physical Scenario |
|--------|-------------------|--------|-------------------|
| `bulk` | - | - | 3D periodic bulk crystal |
| `slab` | - | 3 | 2D periodic surface/slab |
| `molecule` | 'martyna-tuckerman' | - | Isolated molecule in box |
| `wire` | 'esm' | 3 | 1D periodic nanowire |

**Affected Workflows**: All, especially surface/work function calculations  
**Parameters**:
- `SYSTEM.assume_isolated`
- `CONTROL.tefield`, `CONTROL.dipfield` (for slab)
- `SYSTEM.edir`, `emaxpos`, `eopreg` (for dipole correction)

**Note**: Slab calculations with dipole correction are essential for accurate work function calculations.

#### 4.3.2 Phonon Method (`phonon_method`)

**Physical Meaning**: How phonon dynamical matrix is computed.

| Option | Method | Physical Scenario |
|--------|--------|-------------------|
| `dfpt` | Density Functional Perturbation Theory | Analytical, efficient for q-grids |
| `numerical` | Finite displacement (supercell) | Flexible, works with all functionals |

**Affected Workflows**: Phonon calculations  
**Parameters**:
- For DFPT: `ph.x` with `q_points`
- For numerical: `dynmat.x` with supercell displacements

### 4.4 Expert-Only Presets (Later)

#### 4.4.1 XC Functional (`functional`)

**Physical Meaning**: Exchange-correlation approximation

| Option | `input_dft` | Physical Scenario |
|--------|-------------|-------------------|
| `lda` | 'pz' | Simple systems, baseline |
| `pbe` | 'pbe' | General purpose |
| `pbesol` | 'pbesol' | Solids (better lattice constants) |
| `scan` | 'scan' | Meta-GGA, improved accuracy |
| `hse` | 'hse' | Hybrid, accurate gaps |

**Note**: Functional is often determined by pseudopotential choice.

#### 4.4.2 vdW Correction (`vdw_correction`)

**Physical Meaning**: Dispersion correction for van der Waals interactions

From QE test-suite (`pw_vdw/`):

| Option | `vdw_corr` | Physical Scenario |
|--------|-----------|-------------------|
| `none` | - | Systems without significant dispersion |
| `dft_d2` | 'grimme-d2' | Layered materials, molecules on surfaces |
| `dft_d3` | 'grimme-d3' | Improved D3 with coordination-dependent C6 |
| `ts` | 'ts-vdw' | Tkatchenko-Scheffler |
| `mbd` | 'mbd_vdw' | Many-body dispersion (most accurate) |
| `xdm` | 'xdm' | Exchange-hole dipole moment |
| `rvv10` | - | Nonlocal vdW-DF family |
| `vdw_df3` | 'vdw-df3-opt1' | Latest vdW-DF variant |

**Affected Workflows**: All structure optimization, especially layered materials
**Key Parameters**:
- `SYSTEM.vdw_corr`
- Method-specific parameters (e.g., damping functions)

#### 4.4.3 Pseudopotential Type (`pp_type`)

**Physical Meaning**: Treatment of core electrons

| Option | PP Type | Physical Scenario |
|--------|---------|-------------------|
| `nc` | Norm-conserving | Raman, response properties |
| `us` | Ultrasoft | General use, efficient |
| `paw` | PAW | High accuracy, all-electron-like |
| `fr` | Fully relativistic | SOC calculations |

**Note**: SOC requires FR pseudopotentials. Raman requires NC pseudopotentials.

#### 4.4.4 Electric Field / Dipole Correction (`dipole`)

**Physical Meaning**: Treatment of polar slabs and external fields

| Option | Parameters | Physical Scenario |
|--------|------------|-------------------|
| `none` | - | Bulk, symmetric surfaces |
| `dipole_correction` | `tefield`, `dipfield`, `edir` | Asymmetric slabs, work function |
| `electric_field` | `lelfield`, `gdir`, `nppstr` | Finite field calculations |

**Key Parameters** (for dipole correction):
- `CONTROL.tefield = .true.`
- `CONTROL.dipfield = .true.`
- `SYSTEM.edir = 3` (direction perpendicular to slab)
- `SYSTEM.emaxpos = 0.9` (position of field maximum)
- `SYSTEM.eopreg = 0.1` (field region width)

#### 4.4.5 Isolated System Treatment (`isolation`)

**Physical Meaning**: How periodic images are treated for non-periodic systems

| Option | `assume_isolated` | Physical Scenario |
|--------|-------------------|-------------------|
| `3d_periodic` | - | Bulk crystal |
| `martyna_tuckerman` | 'martyna-tuckerman' | Molecules in box |
| `esm` | 'esm' | Surfaces, 2D materials |
| `2d` | '2D' | True 2D (QE 7.x) |

**Note**: Molecular calculations benefit from MT isolation to avoid spurious interactions

---

## 5. Compiler & Detector Design Requirements

### 5.1 Compiler Responsibilities

The Compiler is a **pure function** that maps presets to step parameters:

```python
def compile_one(step_type: str, options: PresetOptions) -> Dict[str, Any]:
    """
    Generate canonical step parameters from preset options.
    
    Args:
        step_type: e.g., "scf", "nscf", "dos"
        options: PresetOptions with spin, soc, material, accuracy, etc.
    
    Returns:
        Full parameter dict with all relevant parameters explicitly set.
    """
```

**Requirements** (from Constitution 10.3):

1. **Canonical Encoding**: ALL relevant parameters MUST be explicitly written
   - Even if value equals QE default
   - No reliance on implicit defaults
   
2. **Independence**: Compiler MUST NOT depend on:
   - Step topology / DAG
   - Structure data
   - Pseudopotentials
   - Calculation state

3. **Completeness**: Output MUST be a complete parameter dict
   - No append/merge with previous values
   - Full overwrite semantics

4. **Interaction Handling**: Compiler MUST enforce preset interactions
   - `soc = with_soc` → automatically set `spin = noncollinear`
   - Invalid combinations → error

### 5.2 Detector Responsibilities

The Detector is a **semantic interpreter** that infers preset values from parameters:

```python
def detect(step_params: Dict[str, Any]) -> Dict[str, PresetValue]:
    """
    Infer preset options from step parameters.
    
    Args:
        step_params: Parameters dict from step.yml
    
    Returns:
        Dict mapping preset dimension to detected value.
    """
```

**Requirements** (from Constitution 10.4, 10.5):

1. **Implicit Default Support**: MUST interpret missing parameters as defaults
   - `nspin` absent → nonspin
   - `lspinorb` absent → no_soc
   
2. **Dimension Independence**: Each preset dimension detected independently

3. **Multi-Step Aggregation**:
   - For dimension d, collect values from relevant steps
   - If all same → Detected = that value
   - If different → Detected = Custom

4. **No Unknown State**: Every dimension MUST have a detected value

### 5.3 Equivalence Axiom

**For Compiler output** (strict):
```
detect(compile_one(step_type, options))[dimension] == options[dimension]
```

**For non-Compiler output** (tolerant):
- Detector MAY infer from implicit defaults
- MAY handle parameter redundancy/inconsistency gracefully
- Goal: reasonable interpretation, not exact round-trip

### 5.4 Preset-Parameter Mapping Table

| Preset | Dimension | Value | Parameters (Canonical) |
|--------|-----------|-------|------------------------|
| spin | nonspin | | `nspin = 1` |
| spin | collinear | | `nspin = 2`, `starting_magnetization(i) = X` |
| spin | noncollinear | | `noncolin = .true.` |
| soc | no_soc | | `lspinorb = .false.` |
| soc | with_soc | | `lspinorb = .true.`, `noncolin = .true.` |
| material | insulator | | `occupations = 'tetrahedra'` |
| material | metal | | `occupations = 'smearing'`, `smearing = 'mv'`, `degauss = 0.01` |

---

## 6. Infrastructure Implications

### 6.1 What Already Exists

1. **Step Types**: `step_defaults.py` defines known types and defaults
2. **Parameter Metadata**: `qe_module_parameters.json` has full QE param definitions
3. **Step Spec Model**: `StructureStepSpec` with parameters, cards, species_overrides
4. **Tutorial Import**: `import_tutorial_datasets.py` parses QE inputs to steps
5. **Resource Model**: ULID-based DAG with step/calc/project hierarchy

### 6.2 What Must Be Added (Conceptually)

1. **Preset Definitions**:
   ```python
   class PresetDimension(Enum):
       SPIN = "spin"
       SOC = "soc"
       MATERIAL = "material"
       ACCURACY = "accuracy"
   
   class SpinOption(Enum):
       NONSPIN = "nonspin"
       COLLINEAR = "collinear"
       NONCOLLINEAR = "noncollinear"
   ```

2. **Compiler Module**:
   ```python
   def compile_preset(
       step_type: str,
       presets: Dict[PresetDimension, Any]
   ) -> Dict[str, Any]:
       """Pure function: presets → parameters"""
   ```

3. **Detector Module**:
   ```python
   def detect_preset(
       step_params: Dict[str, Any],
       dimension: PresetDimension
   ) -> Any:
       """Detect single dimension value from params"""
   
   def detect_all_presets(
       steps: List[StepSpec]
   ) -> Dict[PresetDimension, Any]:
       """Aggregate detection across all steps"""
   ```

4. **Workflow Templates** (runtime only, never persisted):
   ```python
   WORKFLOW_TEMPLATES = {
       "dos": ["scf", "nscf", "dos"],
       "bands": ["scf", "bands_pw", "bands"],
       "phonon_gamma": ["scf", "ph"],
       "phonon_dispersion": ["scf", "ph", "q2r", "matdyn"],
       "wannier_mlwf": ["scf", "nscf", "w90_preproc", "pw2wannier90", "w90_main"],
       "wannier_bands": ["scf", "nscf", "w90_preproc", "pw2wannier90", "w90_main"],  # w90_main with kpoint_path
   }
   ```

5. **Multi-Engine Step Type Registry**:
   ```python
   STEP_TYPE_REGISTRY = {
       # QE pw.x
       "scf": {"engine": "qe", "executable": "pw.x", "calculation": "scf"},
       "nscf": {"engine": "qe", "executable": "pw.x", "calculation": "nscf"},
       "bands": {"engine": "qe", "executable": "pw.x", "calculation": "bands"},
       # ...
       # QE post-processing
       "dos": {"engine": "qe", "executable": "dos.x"},
       "bands_pp": {"engine": "qe", "executable": "bands.x"},
       # ...
       # Wannier90
       "w90_preproc": {"engine": "wannier90", "executable": "wannier90.x", "mode": "preproc"},
       "w90_main": {"engine": "wannier90", "executable": "wannier90.x", "mode": "main"},
       "pw2wannier90": {"engine": "qe", "executable": "pw2wannier90.x"},
       "postw90": {"engine": "wannier90", "executable": "postw90.x"},
   }
   ```

6. **Cross-Engine Data Dependencies**:
   ```python
   # Data flow between steps in Wannier90 workflow
   DATA_DEPENDENCIES = {
       "w90_preproc": {
           "requires": ["seedname.win"],
           "produces": ["seedname.nnkp"],
       },
       "pw2wannier90": {
           "requires": ["QE wavefunctions", "seedname.nnkp"],
           "produces": ["seedname.mmn", "seedname.amn", "seedname.eig"],
       },
       "w90_main": {
           "requires": ["seedname.mmn", "seedname.amn", "seedname.eig"],
           "produces": ["seedname.chk", "seedname_hr.dat"],
       },
       "postw90": {
           "requires": ["seedname.chk"],
           "produces": ["berry/transport outputs"],
       },
   }
   ```

### 6.3 Wannier90 Integration Requirements

**Conceptual requirements** (no implementation):

1. **Parameter Mapping**: Wannier90 uses `.win` file format, not QE namelists
   - Need parameter schema for Wannier90
   - Different serialization format

2. **Projection Specification**:
   - Wannier90 projections: `Si: sp3`, `Fe: sp3d2;dxy;dxz;dyz`
   - Must support both site-centered and atom-centered projections
   - Preset-driven default projections based on element/orbital character

3. **Consistency Enforcement**:
   - k-grid in QE nscf MUST match Wannier90 `mp_grid`
   - `nbnd` in QE MUST match or exceed Wannier90 `num_bands`
   - Spinor mode in Wannier90 MUST match QE `noncolin`

4. **Disentanglement Window Logic**:
   - `dis_froz_max` should typically be near Fermi level
   - `dis_win_max` should include all relevant conduction bands
   - Window values depend on band structure (not purely preset-driven)

### 6.4 Testing Requirements

1. **Compiler-Detector Round-Trip**:
   ```python
   def test_compiler_detector_equivalence():
       for preset_combo in all_valid_preset_combinations():
           params = compile_preset("scf", preset_combo)
           detected = detect_all_presets([params])
           for dim, value in preset_combo.items():
               assert detected[dim] == value
   ```

2. **Implicit Default Detection**:
   ```python
   def test_detector_implicit_defaults():
       # Empty params → all defaults
       params = {}
       detected = detect_preset(params, PresetDimension.SPIN)
       assert detected == SpinOption.NONSPIN
   ```

3. **Tutorial Dataset Detection**:
   ```python
   def test_detect_tutorial_presets():
       # For each tutorial dataset, verify detected presets match expected
       expected = {
           "8_Fe_DOS": {PresetDimension.SPIN: SpinOption.COLLINEAR},
           "14_DFT_plus_U": {PresetDimension.HUBBARD: HubbardOption.WITH_HUBBARD},
       }
   ```

---

## 7. Scope Control Summary

### 7.1 v0 (Must Have)

**Workflows**:
- Ground State (SCF)
- Structure Optimization (relax, vc-relax)
- DOS
- Band Structure

**Presets**:
- Spin Treatment (nonspin / collinear / noncollinear)
- SOC (no_soc / with_soc)
- Material Type (insulator / metal)

### 7.2 v1 (Secondary)

**Workflows**:
- Phonon (gamma, dispersion)
- MD (BOMD)
- PDOS
- **Wannier90: Basic MLWF construction**
- **Wannier90: Band interpolation**
- **Wannier90: Disentangled (metals)**

**Presets**:
- Accuracy Level
- DFT+U
- **Wannier Disentanglement (w90_disentangle)**

**Step Types (new)**:
- `w90_preproc` (Wannier90)
- `pw2wannier90` (QE interface)
- `w90_main` (Wannier90)

### 7.3 v2+ (Advanced)

**Workflows**:
- NEB / Transition State
- TDDFT / Optical
- NMR
- CPMD
- Elastic Properties
- Work Function / Surface
- **Wannier90: Berry curvature / AHE**
- **Wannier90: SOC bands**
- **Wannier90: BoltzWann transport**

**Presets**:
- XC Functional
- vdW Correction
- Electric Field / Dipole Correction
- System Isolation

**Step Types (new)**:
- `postw90` (Wannier90)

### 7.4 v3+ (Specialized / Expert)

**Workflows** (from QE test-suite):
- EPW (Electron-Phonon Wannier) - superconductivity
- HP (First-principles Hubbard U)
- KCW (Koopmans functionals)
- Berry Phase / Polarization
- TDDFPT Magnons
- EELS

**Presets**:
- Pseudopotential Type (NC/US/PAW/FR)
- Wannier-related settings

---

## 8. Open Questions and Uncertainties

1. **K-path Generation**: Should band structure workflows auto-generate k-paths from structure symmetry, or require explicit specification?

2. **Phonon q-grid vs Dispersion**: How to handle the distinction between gamma-point phonons and full dispersion calculations?
   - DFPT method: q-grid defined in `ph.x` input, then interpolated via `q2r`/`matdyn`
   - Numerical method: supercell size determines phonon accuracy

3. **Pseudopotential-Dependent Cutoffs**: Accuracy preset cutoffs depend on pseudopotentials. How to handle this dependency given Compiler's structure-independence?
   - Option A: Use conservative defaults (high cutoffs)
   - Option B: Query pseudopotential metadata at compile time (violates independence)
   - Option C: Provide guidance but allow user override

4. **Multi-Structure Workflows**: Bulk modulus / PES scans require multiple SCF at different volumes. How to represent this?
   - Option A: Single "scan" calculation type with parameter range
   - Option B: Generate multiple separate calculations programmatically

5. **Workflow Chaining**: When workflow A produces relaxed structure for workflow B, how is this represented without persistent workflow state?
   - Current approach: Separate calculations, structure copied at creation time
   - No automatic re-relaxation tracking

6. **Slab/Surface Workflows**: Dipole correction parameters (`emaxpos`, `eopreg`) depend on slab geometry.
   - May need structure-aware defaults or user guidance
   - Position slab in center of cell for symmetric vacuum regions

7. **Raman Spectroscopy Constraints**: Raman intensities require:
   - Norm-conserving pseudopotentials
   - LDA functional
   - How to enforce/warn about these constraints?

8. **Two-Step Precision Workflows**: The "Replay" pattern (coarse → fine) is useful but:
   - How to represent the dependency between low/high precision runs?
   - Should this be a workflow pattern or user-managed?

9. **Modern HUBBARD Card vs Legacy lda_plus_u**: QE 7.x introduces the `HUBBARD` card syntax (see `hp_*/` tests):
   ```
   HUBBARD {atomic}
   U Co-3d 7.75
   ```
   - Should QMatSuite support both legacy and modern syntax?
   - How to handle intersite V terms (`V` in HUBBARD card)?

10. **Relativistic Pseudopotentials**: SOC calculations require fully-relativistic (FR) pseudopotentials (`Si_r.upf`, `Pt.rel-*.UPF`):
    - Compiler cannot validate PP type (no structure dependency)
    - Detector should warn if SOC is enabled but PP is non-relativistic
    - This is a runtime validation concern, not preset concern

11. **QE Workflow Chaining**: The `pw_workflow_*` tests show QE's built-in workflow support:
    - `pw_workflow_scf_dos`, `pw_workflow_vc-relax_scf`, etc.
    - Should QMatSuite leverage this or maintain separate step management?

---

## 9. Appendix: Tutorial Dataset Details

### A.1 Step Sequences by Dataset

| ID | Name | Steps |
|----|------|-------|
| 0 | Si_scf | scf |
| 1 | H2 | relax, scf |
| 2 | H2O | relax |
| 3 | Si_vc_relax | vc-relax |
| 4 | Si_DOS | scf, nscf, dos |
| 5 | NH3_inversion | relax, neb |
| 6 | Al_DOS | vc-relax, scf, nscf, dos |
| 7 | Si_bandStructure | scf, nscf, bands, bands.pp |
| 8 | Fe_DOS | vc-relax, scf, nscf, dos |
| 9 | Si_phonon | scf, ph (gamma/q-grid), q2r, matdyn |
| 10 | benzene_TDDFT | relax, scf, turbo_lanczos, turbo_spectrum |
| 11 | Si_100_surface | relax |
| 12 | NMR_gipaw | scf, gipaw |
| 13 | graphene | vc-relax, scf, bands, bands.pp |
| 14 | DFT_plus_U_NiO | scf, nscf, dos |
| 15 | bulk_modulus_Si | scf ×3 |
| 16 | Si_vacancy_diffusion | relax, neb |
| 17 | H2O_vibration | relax, ph |
| 18 | H2O_MD | relax, md |
| 19 | Si_CPMD | vc-relax, cp |

### A.2 Preset Detection for Tutorial Datasets

| Dataset | Spin | SOC | Material | Special |
|---------|------|-----|----------|---------|
| 0_Si_scf | nonspin | no | insulator | - |
| 4_Si_DOS | nonspin | no | insulator | - |
| 7_Si_bandStructure | nonspin | no | insulator | - |
| 8_Fe_DOS | **collinear** | no | **metal** | nspin=2, smearing |
| 14_DFT_plus_U | **collinear** | no | insulator | **DFT+U** |
| 6_Al_DOS | nonspin | no | **metal** | smearing |

---

## 10. QE Test-Suite Insights

The QE test-suite (`q-e-qe-7.5/test-suite/`) provides additional workflow patterns and edge cases:

### 10.1 Notable Test Categories

| Directory | Coverage | Relevance for QMatSuite |
|-----------|----------|-------------------------|
| `pw_scf/`, `pw_relax/`, `pw_vc-relax/` | Basic workflows | **v0 Core** |
| `pw_lsda/`, `pw_noncolin/`, `pw_spinorbit/` | Magnetic systems | **v0 Spin preset** |
| `pw_metal/` | Metallic smearing | **v0 Material preset** |
| `pw_lda+U/` | DFT+U | **v1 Hubbard preset** |
| `pw_vdw/` | vdW corrections | **v2+ vdW preset** |
| `pw_berry/`, `pw_electric/` | Polarization, fields | **v3+ Specialized** |
| `ph_*/` | Phonon calculations | **v1 Phonon workflows** |
| `hp_*/` | Hubbard parameters | **v3+ HP workflow** |
| `epw_*/` | Electron-phonon | **v3+ EPW workflow** |
| `kcw_*/` | Koopmans | **v3+ Research** |
| `tddfpt_*/` | Optical, magnons | **v2+ TDDFT** |
| `cp_*/` | Car-Parrinello MD | **v2+ CPMD** |

### 10.2 Workflow Patterns from Test-Suite

The `pw_workflow_*` directories show QE's built-in workflow chaining:

| Pattern | Steps | Physical Task |
|---------|-------|---------------|
| `pw_workflow_scf_dos` | SCF → DOS | Standard DOS |
| `pw_workflow_vc-relax_dos` | VC-RELAX → DOS | Relaxed structure DOS |
| `pw_workflow_vc-relax_scf` | VC-RELAX → SCF | Relaxed energy |
| `pw_workflow_relax_relax` | RELAX → RELAX | Two-stage relaxation |
| `pw_workflow_exx_nscf` | SCF(EXX) → NSCF | Hybrid functional bands |

### 10.3 Key Parameter Examples from Test-Suite

**SOC Calculation** (from `epw_mob/scf.in`):
```fortran
&system
   noncolin = .true.
   lspinorb = .true.
/
ATOMIC_SPECIES
  Si  28.0855  Si_r.upf   ! Relativistic pseudopotential
```

**DFT+U with HUBBARD card** (from `hp_insulator_us/LiCoO2.scf.in`):
```fortran
HUBBARD {atomic}
U Co-3d 7.75
```

**vdW-D3** (from `pw_vdw/vdw-d3.in`):
```fortran
&system
   vdw_corr = 'grimme-d3'
/
```

**Berry Phase** (from `pw_berry/berry-1.in`):
```fortran
&control
   calculation = 'nscf'
   lberry = .true.
   gdir = 3
   nppstr = 7
/
```

---

## 11. External References

### 11.1 Official QE Documentation
- [INPUT_PW.html](https://www.quantum-espresso.org/Doc/INPUT_PW.html) - pw.x parameters
- [INPUT_PH.html](https://www.quantum-espresso.org/Doc/INPUT_PH.html) - ph.x parameters
- [INPUT_DOS.html](https://www.quantum-espresso.org/Doc/INPUT_DOS.html) - dos.x parameters
- [INPUT_BANDS.html](https://www.quantum-espresso.org/Doc/INPUT_BANDS.html) - bands.x parameters
- [INPUT_PP.html](https://www.quantum-espresso.org/Doc/INPUT_PP.html) - pp.x parameters
- [INPUT_EPW.html](https://www.quantum-espresso.org/Doc/INPUT_EPW.html) - epw.x parameters
- [INPUT_HP.html](https://www.quantum-espresso.org/Doc/INPUT_HP.html) - hp.x parameters

### 11.2 SCM/AMS Quantum ESPRESSO Examples
- [Single-Point + Band Structure](https://www.scm.com/doc/QuantumEspresso/examples.html#single-point-calculation-band-structure)
- [Lattice Optimization](https://www.scm.com/doc/QuantumEspresso/examples.html#lattice-optimization-of-silicon)
- [DFT+U for Antiferromagnetic FeO](https://www.scm.com/doc/QuantumEspresso/examples.html#dft-u-hubbard-u-calculation-for-anti-ferromagnetic-feo)
- [Slab with Dipole Correction / Work Function](https://www.scm.com/doc/QuantumEspresso/examples.html#slab-with-dipole-correction-work-function)
- [Numerical Phonons](https://www.scm.com/doc/QuantumEspresso/examples.html#numerical-calculation-of-phonons)
- [DFPT Phonons](https://www.scm.com/doc/QuantumEspresso/examples.html#analytical-calculation-of-phonons-using-dfpt)
- [IR/Raman Spectra](https://www.scm.com/doc/QuantumEspresso/examples.html#ir-raman-spectra)
- [PESScan Volume Scan](https://www.scm.com/doc/QuantumEspresso/examples.html#pesscan-volume-scan)
- [Born-Oppenheimer MD](https://www.scm.com/doc/QuantumEspresso/examples.html#born-oppenheimer-molecular-dynamics)
- [PES Exploration / Saddle Search](https://www.scm.com/doc/QuantumEspresso/examples.html#pes-exploration)

### 11.3 QMatSuite Internal Resources
- `tests/data/0_*` through `19_*`: Tutorial datasets
- `src/quantumvitas/data/qe_module_parameters.json`: Parsed QE parameter metadata
- `tools/import_tutorial_datasets.py`: Tutorial → Project/Calc/Step conversion
- `src/quantumvitas/calculation/step_defaults.py`: Default step parameters

---

## 12. Revision History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2025-01-XX | Initial design document |
| 0.2 | 2025-01-XX | Added surface/slab workflows, IR/Raman, phonon methods, external references |
| 0.3 | 2025-01-XX | QE test-suite analysis: EPW, HP, KCW, Berry phase, TDDFPT magnons/EELS; expanded vdW/XC/isolation presets |
| 0.4 | 2025-01-XX | **Major revision**: Formal step_type taxonomy (engine-agnostic); Wannier90 workflows (MLWF, bands, SOC, Berry, transport); preset interaction analysis; multi-engine infrastructure requirements |

---

*This document is a design exploration artifact. It will guide implementation but is not a specification.*

