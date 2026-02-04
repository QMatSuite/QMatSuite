# QMCPACK Engine Exploration Report

**Date**: 2026-02-03
**Status**: Complete — ready for integration planning review
**QMCPACK Version**: 4.1.0
**Installation**: `<HOME>/QMatSuite/.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/`

---

## 1. What is QMCPACK?

QMCPACK (Quantum Monte Carlo PACKage) is a high-performance open-source code for
quantum Monte Carlo calculations of electronic structure. It implements:

- **Variational Monte Carlo (VMC)** — stochastic evaluation of expectation values
  with a trial wavefunction
- **Diffusion Monte Carlo (DMC)** — projects out the ground state from a trial
  wavefunction via imaginary-time evolution
- **Wavefunction Optimization** — optimizes Jastrow parameters (and optionally
  determinant coefficients) to minimize energy or variance

QMCPACK is primarily used as a post-DFT method: it takes wavefunctions from DFT
codes (Quantum ESPRESSO, VASP, PySCF, etc.) and refines the total energy using
QMC methods that capture electron correlation beyond DFT.

### 1.1 Key Characteristics

| Property | Value |
|----------|-------|
| License | BSD 3-Clause |
| Language | C++ (with Python tools) |
| Parallelism | MPI + OpenMP + GPU (CUDA/HIP/SYCL) |
| Input format | XML |
| Output format | Text (.scalar.dat, .dmc.dat) + HDF5 (.stat.h5, .config.h5) |
| Wavefunction source | HDF5 files from DFT converters |
| Pseudopotentials | XML format (BFD, ccECP) — NOT QE .UPF format |

### 1.2 Typical Workflow

```
DFT (QE/VASP/PySCF)
    │
    ▼ converter (pw2qmcpack / convertpw4qmc / convert4qmc)
    │
    ▼ HDF5 wavefunction file (.h5)
    │
    ▼ QMCPACK
        ├── Series 0: Wavefunction optimization (optional, multi-loop)
        ├── Series 1: VMC production
        └── Series 2: DMC production (optional)
```

---

## 2. QMCPACK Input Format

### 2.1 XML Structure

A QMCPACK input file is a single XML document with this structure:

```xml
<?xml version="1.0"?>
<simulation>
  <project id="project_name" series="0"/>

  <qmcsystem>
    <simulationcell>
      <parameter name="lattice" units="bohr">...</parameter>
      <parameter name="bconds">p p p</parameter>
      <parameter name="LR_dim_cutoff">15</parameter>
    </simulationcell>

    <particleset name="e" random="yes">
      <group name="u" size="N_up">...</group>
      <group name="d" size="N_down">...</group>
    </particleset>

    <particleset name="ion0">
      <group name="ELEMENT" size="N_atoms">
        <attrib name="position" datatype="posArray">...</attrib>
      </group>
    </particleset>

    <wavefunction name="psi0" target="e">
      <sposet_collection type="bspline" href="wf.h5" ...>
        <sposet name="spo_ud" size="N_orb"/>
      </sposet_collection>
      <determinantset>
        <slaterdeterminant>
          <determinant sposet="spo_ud"/>
          <determinant sposet="spo_ud"/>
        </slaterdeterminant>
      </determinantset>
      <jastrow type="One-Body" ...>...</jastrow>
      <jastrow type="Two-Body" ...>...</jastrow>
    </wavefunction>

    <hamiltonian name="h0" type="generic" target="e">
      <pairpot type="coulomb" name="ElecElec" source="e" target="e"/>
      <pairpot type="coulomb" name="IonIon" source="ion0" target="ion0"/>
      <pairpot type="pseudo" name="PseudoPot" source="ion0" ...>
        <pseudo elementType="C" href="C.BFD.xml"/>
      </pairpot>
    </hamiltonian>
  </qmcsystem>

  <!-- QMC sections (one per series) -->
  <qmc method="vmc" move="pbyp">
    <parameter name="blocks">200</parameter>
    <parameter name="steps">10</parameter>
    <parameter name="timestep">0.3</parameter>
    ...
  </qmc>

  <qmc method="dmc" move="pbyp">
    <parameter name="targetwalkers">256</parameter>
    <parameter name="blocks">100</parameter>
    <parameter name="timestep">0.005</parameter>
    ...
  </qmc>
</simulation>
```

### 2.2 Key Input Sections

| Section | Purpose | Notes |
|---------|---------|-------|
| `<project>` | Project ID + starting series number | Series auto-increments per `<qmc>` block |
| `<simulationcell>` | Lattice vectors, boundary conditions | Omit for open-boundary molecules |
| `<particleset name="e">` | Electron definition | Up/down groups |
| `<particleset name="ion0">` | Ion positions + species | Includes mass, charge, valence |
| `<wavefunction>` | Trial wavefunction | SPO from HDF5 + Jastrow factors |
| `<hamiltonian>` | Potential energy terms | Coulomb + pseudopotential |
| `<qmc method="vmc">` | VMC calculation section | One per series |
| `<qmc method="dmc">` | DMC calculation section | Requires prior VMC for walkers |
| `<qmc method="linear">` | Wavefunction optimization | Wrapped in `<loop>` for iterations |

### 2.3 Important Parameters

**VMC Parameters:**
- `blocks` — number of blocks for averaging
- `steps` — MC steps per block
- `substeps` — sub-steps per step
- `timestep` — MC time step
- `warmupsteps` — equilibration steps
- `usedrift` — use drift in moves (yes/no)

**DMC Parameters:**
- `targetwalkers` — target walker population
- `blocks`, `steps`, `timestep` — same concept as VMC
- `nonlocalmoves` — T-moves for pseudopotentials (yes/no/v0/v1/v3)
- `reconfiguration` — walker reconfiguration (yes/no)

**Optimization Parameters:**
- `Minmethod` — optimization algorithm (adaptive/descent/hybrid)
- `samples` — number of samples for optimization
- `shift_i`, `shift_s` — regularization parameters
- `max_param_change` — maximum parameter change per iteration

---

## 3. QMCPACK Output Format

### 3.1 Output File Inventory

Each `<qmc>` section in the input produces a series of output files:

| File Pattern | Format | Content |
|-------------|--------|---------|
| `{id}.s{NNN}.scalar.dat` | TSV | Block-averaged energy estimators |
| `{id}.s{NNN}.dmc.dat` | TSV | Per-step DMC data (walkers, trial energy) |
| `{id}.s{NNN}.stat.h5` | HDF5 | Detailed statistics |
| `{id}.s{NNN}.config.h5` | HDF5 | Walker configurations |
| `{id}.s{NNN}.random.h5` | HDF5 | Random number state |
| `{id}.s{NNN}.cont.xml` | XML | Continuation input |
| `{id}.s{NNN}.info.xml` | XML | Run metadata |
| `{id}.s{NNN}.opt.xml` | XML | Optimized wavefunction (optimization only) |

Where `{id}` is the project ID and `{NNN}` is the zero-padded series number.

### 3.2 scalar.dat Format

```
#  index  LocalEnergy  Variance  Kinetic  LocalPotential  ...  AcceptRatio
   0     -10.4913      0.3729    11.2281  -21.7194        ...  0.5038
   1     -10.5021      0.3614    11.1897  -21.6918        ...  0.4997
   ...
```

- Header line starts with `#`
- First column is block index
- Subsequent columns are energy estimators
- Key columns: `LocalEnergy`, `Variance`, `Kinetic`, `LocalPotential`, `AcceptRatio`

### 3.3 dmc.dat Format (DMC only)

```
#  index  LocalEnergy  Variance  Kinetic  ...  NumOfWalkers  TrialEnergy  ...
```

Contains per-step DMC data including walker population dynamics.

### 3.4 stdout Summary

QMCPACK stdout contains section summaries:

```
====================================================
  End of a VMC section
    QMC counter        = 0
    time step          = 0.3
    reference energy   = -10.4905
    reference variance = 0.373664
====================================================
```

And ends with `QMCPACK execution completed successfully` on success.

---

## 4. Real Calculations Performed

### 4.1 Test 1: VMC on Diamond Carbon (Solid)

**Input**: Single VMC section, 200 blocks x 10 steps, timestep=0.3
**System**: 2-atom diamond C cell with periodic BC, BFD pseudopotential
**Wavefunction**: Pre-built HDF5 from DFT, with pre-optimized Jastrow factors

**Results**:
- Energy: -10.4905 Ha (reference energy from stdout)
- Mean energy (from scalar.dat): ~-10.49 Ha
- Acceptance ratio: ~50%
- 200 blocks of data in scalar.dat

**Findings**:
- QMCPACK 4.1.0 does NOT support `walkers` tag (removed; use `totalwalkers` or default)
- Output files: `.scalar.dat`, `.stat.h5`, `.config.h5`, `.random.h5`, `.cont.xml`, `.info.xml`

### 4.2 Test 2: VMC + DMC on Diamond Carbon (Solid)

**Input**: Two `<qmc>` sections — VMC (walker generation, 1 block) + DMC (production, 100 blocks)
**System**: Same diamond C cell as Test 1

**Results**:
- VMC energy: ~-10.49 Ha (series s000, 1 block only)
- DMC energy: -10.5279 Ha (reference energy, lower than VMC as expected)
- DMC scalar.dat: 100 blocks
- dmc.dat: per-step walker data with NumOfWalkers, TrialEnergy columns

**Findings**:
- DMC produces both `.scalar.dat` and `.dmc.dat` files
- DMC energy is systematically lower (better) than VMC
- VMC→DMC chaining is automatic within single input file

### 4.3 Test 3: Wavefunction Optimization + VMC on H4 Molecule

**Input**: `<loop max="3">` wrapping optimization, followed by VMC production
**System**: 4-hydrogen linear molecule (all-electron, no pseudopotential needed)

**Results**:
- Optimization series s000-s002: energy improved from -1.82 to -2.13 Ha
- VMC production series s003: final energy ~-2.13 Ha
- Optimization produces `.opt.xml` files with optimized Jastrow coefficients

**Findings**:
- `samples` parameter must satisfy: `samples <= walkers * steps * blocks`
- Optimization loop generates series s000, s001, s002 (one per loop iteration)
- Each optimization series produces an `.opt.xml` with updated wavefunction
- Subsequent VMC automatically uses the last optimized wavefunction

### 4.4 Failed Test: QE → QMCPACK Pipeline

**Attempted**: QE SCF → convertpw4qmc → QMCPACK
**QE SCF**: Succeeded (diamond C)
**Conversion**: Failed — QE 7.5 compiled without HDF5 support

**Error**: `convertpw4qmc` expects HDF5 charge density file but QE produced `.dat`
**Alternative**: `pw2qmcpack.x` not found in QE 7.5 bin directory

**Critical Finding**: QMCPACK integration requires either:
1. QE compiled with HDF5 support, or
2. A separate conversion step using `convert4qmc` with different input, or
3. PySCF or other converter path

---

## 5. Pseudopotential Handling

### 5.1 QMCPACK Pseudopotential Format

QMCPACK uses its own XML pseudopotential format, NOT QE .UPF files:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<pseudo version="0.5">
  <header symbol="C" atomic-number="6" zval="4" .../>
  <grid type="linear" ri="0.0" rf="10.0" npts="10001"/>
  <semilocal units="hartree" format="r*V" npots-down="3" npots-up="0" l-local="2">
    <vps principal-n="1" l="0" spin="-1" cutoff="0.0" occupation="2.0">
      <radfunc> <data> ... </data> </radfunc>
    </vps>
    ...
  </semilocal>
</pseudo>
```

### 5.2 Common Pseudopotential Libraries

| Library | Format | Notes |
|---------|--------|-------|
| BFD | `.xml` | Burkatzki-Filippi-Dolg, widely used |
| ccECP | `.xml` | Correlation-consistent ECPs, newer |
| SOREP | `.xml` | Spin-orbit REPs (for heavy elements) |

### 5.3 Conversion

QMCPACK includes `ppconvert` tool for converting between formats:
- Located at: `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/ppconvert`
- Can convert from GAMESS, Gaussian, Casino formats to QMCPACK XML

QE `.UPF` pseudopotentials cannot be directly used — they must be converted
or replaced with the equivalent BFD/ccECP pseudopotential in QMCPACK XML format.

---

## 6. QMCPACK Binaries Inventory

| Binary | Purpose |
|--------|---------|
| `qmcpack` | Main QMCPACK executable |
| `convertpw4qmc` | Convert QE wavefunctions (requires HDF5-enabled QE) |
| `convert4qmc` | Convert molecular wavefunctions (Gaussian, GAMESS, PySCF) |
| `ppconvert` | Pseudopotential format converter |
| `qmcfinitesize` | Finite-size correction tool |
| `qmca` | Python analysis tool for scalar.dat files |

---

## 7. Building pw2qmcpack.x Manually

### 7.1 Why

QE's configure-based build does not support pw2qmcpack (it requires cmake with
`-DQE_ENABLE_PLUGINS=pw2qmcpack`). Rather than rebuilding all of QE with cmake,
we can compile pw2qmcpack from its standalone repo using the existing QE libraries.

### 7.2 Prerequisites

- QE already built with HDF5 support (h5fc as Fortran compiler)
- HDF5 installed (`brew install hdf5` on macOS)
- The QE build used `h5fc` (HDF5 Fortran compiler wrapper) for F90/LD

### 7.3 Source

```bash
git clone https://github.com/QMCPACK/pw2qmcpack.git
```

The repo contains exactly two source files:
- `src/pw2qmcpack.f90` — Main Fortran program (~1150 lines)
- `src/esh5_interfaces.c` — C HDF5 interface functions (~700 lines)

### 7.4 Build Steps (3 commands)

Given:
```
QE=/path/to/q-e-qe-7.5        # QE source/build directory
SRC=/path/to/pw2qmcpack/src   # Cloned pw2qmcpack repo src/
BUILD=/tmp/pw2qmcpack_build   # Temporary build directory
```

#### Step 1: Compile the C file

```bash
h5cc -c -DH5_USE_16_API -D__HDF5_C -O2 \
    "$SRC/esh5_interfaces.c" -o "$BUILD/esh5_interfaces.o"
```

- `h5cc` is the HDF5 C compiler wrapper (provides `-I` and `-L` for HDF5)
- `-DH5_USE_16_API` — use HDF5 1.6 API compatibility (required by this code)
- `-D__HDF5_C` — enables the HDF5 code paths via `#if defined(__HDF5_C)`

#### Step 2: Compile the Fortran file

```bash
gfortran -cpp -c -O3 -g -fallow-argument-mismatch \
    -D__FFTW -D__HDF5_C \
    -I/opt/homebrew/include \
    -I"$QE/PW/src" \
    -I"$QE/PP/src" \
    -I"$QE/Modules" \
    -I"$QE/upflib" \
    -I"$QE/XClib" \
    -I"$QE/FFTXlib/src" \
    -I"$QE/LAXlib" \
    -I"$QE/UtilXlib" \
    -I"$QE/MBD" \
    -I"$QE/KS_Solvers" \
    -I"$QE/include" \
    "$SRC/pw2qmcpack.f90" -o "$BUILD/pw2qmcpack.o"
```

Key points:
- **Must use `gfortran` directly**, not `h5fc`. The `h5fc` wrapper strips the
  `-cpp` flag, which is essential for C preprocessor directives (`#ifdef __MPI`,
  `#if defined(__HDF5_C)`, etc.)
- `-I/opt/homebrew/include` — HDF5 Fortran module files (from `brew install hdf5`)
- The `-I` flags point to QE directories containing `.mod` (Fortran module) files
- `-D__FFTW` matches QE's own DFLAGS; `-D__HDF5_C` enables HDF5 code paths
- The `wxml` module comes from QE's `upflib/` (not FoX). The code uses
  `#if defined(__fox)` / `#else` / `USE wxml` — since QE was built without FoX,
  the `wxml` module from upflib is used instead.
- One expected warning about type mismatch in `esh5_write_psi_r` (REAL vs COMPLEX
  actual argument) — this is by design in the original code.

#### Step 3: Link

```bash
gfortran -g \
    "$BUILD/pw2qmcpack.o" \
    "$BUILD/esh5_interfaces.o" \
    "$QE/PW/src/libpw.a" \
    "$QE/PP/src/libpp.a" \
    "$QE/Modules/libqemod.a" \
    "$QE/KS_Solvers/libks_solvers.a" \
    "$QE/FFTXlib/src/libqefft.a" \
    "$QE/LAXlib/libqela.a" \
    "$QE/UtilXlib/libutil.a" \
    "$QE/upflib/libupf.a" \
    "$QE/XClib/xc_lib.a" \
    "$QE/MBD/libmbd.a" \
    "$QE/dft-d3/libdftd3qe.a" \
    "$QE/external/devxlib/src/libdevXlib.a" \
    -L/opt/homebrew/lib -lhdf5_hl_fortran -lhdf5_fortran -lhdf5 -lhdf5_hl \
    -framework Accelerate \
    -o "$BUILD/pw2qmcpack.x"
```

Key points:
- Library order matters: object files first, then QE libs (PW before PP before
  Modules before lower-level libs), then HDF5, then system BLAS/LAPACK.
- `-framework Accelerate` is the macOS BLAS/LAPACK (matching QE's make.inc).
- The QE `.a` files were produced during the original QE build.

#### Step 4: Install

```bash
cp "$BUILD/pw2qmcpack.x" "$QE/bin/pw2qmcpack.x"
```

### 7.5 Verification

```bash
echo "" | pw2qmcpack.x
```

Should show QE banner and error about "reading inputpp namelist" (expected with
empty input). Verify HDF5 linking:

```bash
otool -L pw2qmcpack.x | grep hdf5
```

Should show libhdf5, libhdf5_fortran, libhdf5_hl, libhdf5_hl_fortran.

### 7.6 QE Library Dependencies (for reference)

From CMakeLists.txt, pw2qmcpack links against these QE targets:
- `qe_pw` → `PW/src/libpw.a`
- `qe_pp` → `PP/src/libpp.a`
- `qe_modules` → `Modules/libqemod.a`
- `qe_fftx` → `FFTXlib/src/libqefft.a`
- `qe_upflib` → `upflib/libupf.a`
- `qe_fox` → not needed (QE built without FoX; `wxml.mod` in upflib suffices)
- `qe_xclib` → `XClib/xc_lib.a`

Additional libs needed for linking (transitive deps):
- `KS_Solvers/libks_solvers.a`, `LAXlib/libqela.a`, `UtilXlib/libutil.a`
- `MBD/libmbd.a`, `dft-d3/libdftd3qe.a`, `external/devxlib/src/libdevXlib.a`

---

## 8. Full Workflow: QE → pw2qmcpack → QMCPACK (Diamond Smoke Test)

### 8.1 Overview

This smoke test runs a minimal diamond carbon (2-atom primitive cell) calculation
through the complete pipeline:

1. **pw.x** (QE): DFT-LDA self-consistent field calculation → wavefunctions
2. **pw2qmcpack.x**: Convert QE wavefunctions to QMCPACK HDF5 format
3. **qmcpack**: Variational Monte Carlo (VMC) calculation

### 8.2 System: Diamond Carbon (1x1x1 primitive cell)

- 2 carbon atoms (FCC diamond structure)
- Lattice vectors (bohr): FCC with a = 6.7463223 bohr (3.57 A)
- BFD pseudopotential (4 valence electrons per C)
- 8 total electrons (4 up, 4 down)
- Single k-point (Gamma)

### 8.3 Required Files

All files can be found in QMCPACK's test suite:
`$QMCPACK/tests/solids/diamondC_1x1x1_pp/`

Pseudopotentials:
- `C.BFD.upf` — for QE (from `dft-inputs/`)
- `C.BFD.xml` — for QMCPACK (from top-level test dir)

### 8.4 Step 1: DFT-SCF with pw.x

Input file `scf.in`:
```
&CONTROL
   calculation     = 'scf'
   disk_io         = 'low'
   outdir          = 'pwscf_output'
   prefix          = 'pwscf'
   pseudo_dir      = './'
   restart_mode    = 'from_scratch'
   tprnfor         = .false.
   tstress         = .false.
   verbosity       = 'high'
   wf_collect      = .true.
/

&SYSTEM
   celldm(1)       = 1.0
   degauss         = 0.0001
   ecutrho         = 800
   ecutwfc         = 200
   ibrav           = 0
   input_dft       = 'lda'
   nat             = 2
   nosym           = .true.
   ntyp            = 1
   occupations     = 'smearing'
   smearing        = 'fermi-dirac'
   tot_charge      = 0
/

&ELECTRONS
   conv_thr        = 1e-08
   electron_maxstep = 1000
   mixing_beta     = 0.7
/

ATOMIC_SPECIES
   C  12.011 C.BFD.upf

ATOMIC_POSITIONS alat
   C        0.00000000       0.00000000       0.00000000
   C        1.68658058       1.68658058       1.68658058

K_POINTS automatic
   1 1 1  0 0 0

CELL_PARAMETERS cubic
         3.37316115       3.37316115       0.00000000
         0.00000000       3.37316115       3.37316115
         3.37316115       0.00000000       3.37316115
```

Key parameters:
- `celldm(1) = 1.0` with CELL_PARAMETERS in bohr (cubic keyword)
- `ecutwfc = 200` Ry, `ecutrho = 800` Ry (4x)
- `nosym = .true.` — required for QMCPACK (no symmetry reduction)
- `wf_collect = .true.` — write wavefunctions to disk (needed by pw2qmcpack)
- `input_dft = 'lda'` — LDA functional (standard for QMC starting point)

Run:
```bash
pw.x < scf.in > scf.out
```

Expected: converges in ~7 iterations, total energy ≈ -20.5449 Ry (-10.2724 Ha).

### 8.5 Step 2: Convert orbitals with pw2qmcpack.x

Input file `p2q.in`:
```
&inputpp
  write_psir = .false.
  prefix = 'pwscf'
  outdir = 'pwscf_output'
/
```

Run:
```bash
pw2qmcpack.x < p2q.in > p2q.out
```

Output files (in `pwscf_output/`):
- `pwscf.pwscf.h5` — HDF5 file with orbital data (~1.3 MB)
- `pwscf.ptcl.xml` — particle set XML
- `pwscf.wfs.xml` — wavefunction XML

### 8.6 Step 3: VMC with QMCPACK

Input file `vmc.in.xml`:
```xml
<?xml version="1.0"?>
<simulation>
   <project id="qmc_smoke" series="0">
      <application name="qmcapp" role="molecu" class="serial" version="1.0"/>
      <parameter name="driver_version">legacy</parameter>
   </project>
   <qmcsystem>
      <simulationcell>
         <parameter name="lattice" units="bohr">
                  3.37316115        3.37316115        0.00000000
                  0.00000000        3.37316115        3.37316115
                  3.37316115        0.00000000        3.37316115
         </parameter>
         <parameter name="bconds">p p p</parameter>
         <parameter name="LR_dim_cutoff">15</parameter>
      </simulationcell>
      <particleset name="e" random="yes">
         <group name="u" size="4" mass="1.0">
            <parameter name="charge">-1</parameter>
            <parameter name="mass">1.0</parameter>
         </group>
         <group name="d" size="4" mass="1.0">
            <parameter name="charge">-1</parameter>
            <parameter name="mass">1.0</parameter>
         </group>
      </particleset>
      <particleset name="ion0">
         <group name="C" size="2" mass="21894.7135906">
            <parameter name="charge">4</parameter>
            <parameter name="valence">4</parameter>
            <parameter name="atomicnumber">6</parameter>
            <parameter name="mass">21894.7135906</parameter>
            <attrib name="position" datatype="posArray" condition="0">
                     0.00000000        0.00000000        0.00000000
                     1.68658058        1.68658058        1.68658058
            </attrib>
         </group>
      </particleset>
      <wavefunction name="psi0" target="e">
         <determinantset type="einspline" href="pwscf_output/pwscf.pwscf.h5"
                         tilematrix="1 0 0 0 1 0 0 0 1" twistnum="0"
                         source="ion0" meshfactor="1.0" precision="float">
            <slaterdeterminant>
               <determinant id="updet" size="4">
                  <occupation mode="ground" spindataset="0"/>
               </determinant>
               <determinant id="downdet" size="4">
                  <occupation mode="ground" spindataset="0"/>
               </determinant>
            </slaterdeterminant>
         </determinantset>
      </wavefunction>
      <hamiltonian name="h0" type="generic" target="e">
         <pairpot type="coulomb" name="ElecElec" source="e" target="e"/>
         <pairpot type="coulomb" name="IonIon" source="ion0" target="ion0"/>
         <pairpot type="pseudo" name="PseudoPot" source="ion0"
                  wavefunction="psi0" format="xml">
            <pseudo elementType="C" href="C.BFD.xml"/>
         </pairpot>
      </hamiltonian>
   </qmcsystem>
   <qmc method="vmc" move="pbyp">
      <parameter name="walkers">1</parameter>
      <parameter name="blocks">50</parameter>
      <parameter name="steps">10</parameter>
      <parameter name="subSteps">2</parameter>
      <parameter name="timestep">0.3</parameter>
      <parameter name="warmupSteps">20</parameter>
   </qmc>
</simulation>
```

Key QMCPACK v4.x notes:
- **`<parameter name="driver_version">legacy</parameter>`** — REQUIRED in
  QMCPACK 4.x. The default "batched" driver removed `walkers` parameter support.
  Without this line, QMCPACK 4.x will abort with "Input tag walkers is not
  supported".
- `href` points to the h5 file produced by pw2qmcpack (relative path)
- No Jastrow factors in this smoke test (bare Slater determinant)
- `C.BFD.xml` must be in the working directory

Run:
```bash
qmcpack vmc.in.xml
```

Output files:
- `qmc_smoke.s000.scalar.dat` — per-block energies and estimators
- `qmc_smoke.s000.stat.h5` — statistics in HDF5 format
- `qmc_smoke.s000.config.h5` — walker configurations
- `qmc_smoke.s000.cont.xml` — continuation input

### 8.7 Expected Results

| Step | Energy | Notes |
|------|--------|-------|
| DFT (pw.x) | -10.272 Ha (-20.545 Ry) | LDA total energy |
| VMC (no Jastrow) | ≈ -10.23 Ha | Above DFT due to no correlation |
| VMC (with Jastrow, ref) | ≈ -10.49 Ha | Below DFT, proper VMC |

The no-Jastrow VMC energy (-10.23 Ha) being slightly above DFT (-10.27 Ha) is
expected. The DFT energy includes exchange-correlation approximation that
partially compensates for the missing electron correlation. Without Jastrow
factors, VMC uses only a Slater determinant and lacks explicit correlation.

With optimized Jastrow factors (from QMCPACK's reference data), the VMC energy
drops to -10.49 Ha, which is below DFT and closer to the true ground state.

### 8.8 Timing (Apple M3, serial)

- pw.x SCF: ~2 seconds
- pw2qmcpack.x: <1 second
- qmcpack VMC (50 blocks): <1 second
- Total: ~3 seconds

---

## 9. Engine System Code Review Summary

### 9.1 Current Architecture

The QMatSuite engine system follows a clean plug-in architecture:

1. **EngineDriver Protocol** (`core/driver_protocol.py`): 7-item MUST interface
2. **DriverRegistry** (`core/driver_registry.py`): Singleton registration
3. **BaseEngineDriver**: Default implementations for SHOULD/PLUGIN methods
4. **StepTypeSpec**: Frozen dataclass for step type declarations
5. **WorkdirPolicy**: ISOLATED, CLEANUP, or SHARED
6. **GenStepRegistry** (`workflow/gen_steps.py`): SSOT for valid GEN step names

### 9.2 Current Registered Engines

| Engine | PREFIX | GEN Steps | WorkdirPolicy | Recipe Archetype |
|--------|--------|-----------|---------------|------------------|
| QE | `qe` | scf, nscf, relax, bands, bandspw, dos, pw2wannier, ph, md, custom | SHARED | Directory-state |
| VASP | `vasp` | scf, nscf, relax, md, bandspw | CLEANUP | Cleanup |
| PySCF | `pyscf` | scf, relax, mp2, td | ISOLATED | Strong-chain |
| ORCA | `orca` | scf, hf, relax, td | ISOLATED | Strong-chain |
| LAMMPS | `lammps` | minimize, md, relax | ISOLATED | Directory-state |
| CP2K | `cp2k` | scf, relax, md, bandspw, dos | ISOLATED | Strong-chain |
| W90 | `w90` | wannierprep, wannier | SHARED | Directory-state |

### 9.3 How a Driver Bundle Works

```
drivers/<engine>/
├── __init__.py      # DriverRegistry.register(MyDriver())
├── driver.py        # PREFIX, SUPPORTED_GEN_STEPS, 7 MUST methods
├── handler.py       # Step execution handler function
├── recipe.py        # materialize(steps, calc_raw_dir, ...) -> JobGraph
├── writer.py        # Input file generation (optional)
└── parser.py        # Output parsing (optional)
```

The recipe's `materialize()` method converts calculation steps into a `JobGraph`
containing `Job` objects with commands, input files, expected outputs, and dependencies.

### 9.4 Key Law Constraints

From `ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md`:
- **Runner is engine-agnostic** — no `if engine == "..."` in runner
- **One engine → one recipe** — single central declaration
- **Materialization is clean rewrite** — YAML → input files, never parse old input
- **No scattered mapping dicts** — all routing via registry
- **No kernel edits to add engine** — only `drivers/` and `tests/` modified

From `STEP_TYPE_GEN_SPEC_CONSTITUTION.md`:
- GEN steps must not contain underscores
- `step_type_spec = f"{PREFIX}_{gen}"`
- `SUPPORTED_GEN_STEPS ⊆ GenStepRegistry.GEN_STEPS`

---

## 10. Key Observations for Integration

### 10.1 QMCPACK is Fundamentally Different from DFT Engines

Unlike QE/VASP/CP2K which are self-contained DFT solvers, QMCPACK:
- **Requires a prior DFT calculation** to generate the trial wavefunction
- **Uses a different pseudopotential format** (XML, not UPF)
- **Produces stochastic results** (energy ± error bar, not deterministic)
- **Has multi-series output** from a single input file

### 10.2 Single Input → Multi-Series Output

A single QMCPACK input file contains multiple `<qmc>` sections. Each section
produces its own series of output files (s000, s001, ...). This is different
from QE where each step has its own input file.

This means the **recipe must handle multi-section XML generation** where a
single "calculation" might contain optimization + VMC + DMC in one input file.

### 10.3 Cross-Engine Dependencies

QMCPACK calculations typically depend on:
1. A DFT calculation (QE, VASP, or PySCF) for the wavefunction
2. A wavefunction converter (convertpw4qmc, pw2qmcpack, convert4qmc)
3. QMCPACK-format pseudopotentials (ppconvert or manual download)

This creates a **cross-engine dependency** that the current QMatSuite architecture
may need to accommodate.

### 10.4 Wavefunction Optimization Loop

The optimization step uses `<loop max="N">` to iterate. Each iteration produces
a new series with an `.opt.xml` containing updated Jastrow parameters. The final
optimized wavefunction is automatically used by subsequent VMC/DMC sections.

---

## 11. Troubleshooting

### 11.1 Common Issues

1. **"reading inputpp namelist" error from pw2qmcpack.x**
   - The `prefix` and `outdir` in p2q.in must match the QE SCF calculation.

2. **"Input tag walkers is not supported" from QMCPACK 4.x**
   - Add `<parameter name="driver_version">legacy</parameter>` in `<project>`.

3. **FoX module not found during compilation**
   - This happens if QE was built without FoX (FOX_MOD is empty in make.inc).
   - The code handles this: `#if defined(__fox)` / `#else` / `USE wxml`.
   - DO NOT define `__fox`. The `wxml` module from QE's `upflib/` is used.

4. **h5fc strips -cpp flag**
   - Use `gfortran -cpp` directly instead of `h5fc` for compilation.
   - Add `-I/opt/homebrew/include` manually for HDF5 module files.
   - Use `h5fc -show` to see what flags/libs h5fc adds, then replicate manually.

5. **Missing .mod files**
   - QE must be fully built (not just pw.x) to have all module files.
   - Key directories: PW/src, PP/src, Modules, upflib, FFTXlib/src, LAXlib, etc.

---

## 12. Artifacts Produced

### 12.1 Golden Reference Files

Located in `golden_refs/`:

| File | Source | Purpose |
|------|--------|---------|
| `vmc_diamond_scalar.dat` | Test 1 | 200-block VMC scalar data |
| `vmc_diamond_input.xml` | Test 1 | VMC input reference |
| `vmc_dmc_diamond_vmc_scalar.dat` | Test 2 | VMC walker-gen scalar data |
| `vmc_dmc_diamond_dmc_scalar.dat` | Test 2 | 100-block DMC scalar data |
| `vmc_dmc_diamond_dmc_dmc.dat` | Test 2 | Per-step DMC walker data |
| `vmc_dmc_diamond_input.xml` | Test 2 | VMC+DMC input reference |
| `opt_vmc_h4_vmc_scalar.dat` | Test 3 | Post-optimization VMC scalar data |
| `opt_vmc_h4_input.xml` | Test 3 | Optimization+VMC input reference |

### 12.2 Utility Scripts

| File | Purpose |
|------|---------|
| `utils/qmcpack_parser.py` | Parses scalar.dat, dmc.dat, and stdout |
| `utils/qmcpack_writer.py` | Generates QMCPACK XML input files |

Both scripts include self-tests that pass against the golden references.

---

## 13. File Locations (QMatSuite setup)

```
QE:       .qmatsuite/engines/qe/q-e-qe-7.5/
QMCPACK:  .qmatsuite/engines/qmcpack/qmcpack-4.1.0/
HDF5:     /opt/homebrew/opt/hdf5/  (brew install hdf5)

pw.x:           .qmatsuite/engines/qe/q-e-qe-7.5/bin/pw.x
pw2qmcpack.x:   .qmatsuite/engines/qe/q-e-qe-7.5/bin/pw2qmcpack.x  (manually built)
qmcpack:        .qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack

Pseudopotentials:
  C.BFD.upf:  .qmatsuite/engines/qmcpack/qmcpack-4.1.0/labs/lab2_qmc_basics/your_system/pseudopotentials/
  C.BFD.xml:  .qmatsuite/engines/qmcpack/qmcpack-4.1.0/tests/solids/diamondC_1x1x1_pp/


Test inputs:
  .qmatsuite/engines/qmcpack/qmcpack-4.1.0/tests/solids/diamondC_1x1x1_pp/dft-inputs/
```

---

## 14. References

- [QMCPACK Manual](https://qmcpack.readthedocs.io/en/develop/)
- [Lab 2: QMC Basics](https://qmcpack.readthedocs.io/en/v3.11.0/lab_qmc_basics.html)
- [pw2qmcpack GitHub](https://github.com/QMCPACK/pw2qmcpack)
- [Nexus Complete Examples](https://nexus-workflows.readthedocs.io/en/latest/examples.html)
- [QMCPACK Additional Tools](https://qmcpack.readthedocs.io/en/develop/additional_tools.html)
