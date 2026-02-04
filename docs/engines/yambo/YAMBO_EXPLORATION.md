# Yambo Engine Exploration

## COMPILATION RECIPE (macOS ARM64)

**CRITICAL**: The stock yambo 5.3.0 binary crashes on macOS ARM64 due to an
incompatibility between gfortran's `CDOTC` calling convention and Apple's
Accelerate BLAS framework. Apple Accelerate returns complex values differently
from what gfortran expects. You MUST recompile with OpenBLAS.

### Prerequisites

```bash
brew install gcc@14 openblas
# Verify: gfortran-14, gcc-14, /opt/homebrew/opt/openblas
```

### Build Steps

```bash
cd .qmatsuite/engines/yambo/yambo-5.3.0

# Clean previous build
make clean

# Configure with OpenBLAS instead of Apple Accelerate
./configure \
    FC=gfortran-14 \
    CC=gcc-14 \
    FPP="gfortran-14 -E -P" \
    CPP="gcc-14 -E -P" \
    --with-blas-libs="-L/opt/homebrew/opt/openblas/lib -lopenblas" \
    --with-lapack-libs="-L/opt/homebrew/opt/openblas/lib -lopenblas" \
    --prefix=$PWD

# Build core (yambo, ypp, p2y, a2y, c2y)
make core -j4
```

### Verify

```bash
otool -L bin/yambo | grep openblas
# Should show: /opt/homebrew/opt/openblas/lib/libopenblas.0.dylib
```

### Root Cause of Original Crash

Backtrace:
```
frame #0: libBLAS.dylib`CDOTC + 20          ← EXC_BAD_ACCESS (address=0x1)
frame #1: yambo`devxlib_linalg_MOD_dev_cdotc_gpu
frame #2: yambo`wrapper_MOD_vstar_dot_v_c2_gpu
frame #3: yambo`wf_load_
frame #4: yambo`dipole_g_space_
```

The devxlib GPU abstraction layer passes the BLAS increment argument `1` by
value instead of by reference. Apple's Accelerate framework then reads from
memory address `0x1` → segfault. OpenBLAS handles this correctly.

### Build Configuration Summary

```
Version:     5.3.0 Revision 23927 Hash 1730222ea
Build type:  Serial+HDF5_IO
Compilers:   gfortran-14 (Homebrew GCC 14.3.0), gcc-14
BLAS/LAPACK: OpenBLAS 0.3.31 (/opt/homebrew/opt/openblas)
FFT:         FFTW3 (bundled)
I/O:         HDF5 + NetCDF4 (bundled)
LibXC:       bundled
GPU:         no_gpu (devxlib CPU path)
Precision:   SINGLE
```

---

## 1. What Yambo Is

Yambo is an ab initio code for **many-body perturbation theory (MBPT)**
and **time-dependent DFT (TDDFT)** calculations. It computes:

- **GW quasiparticle corrections**: Band gaps, QP band structures
- **BSE (Bethe-Salpeter Equation)**: Optical spectra with excitons
- **TDDFT**: Optical properties via ALDA/LRC kernels
- **IP/RPA optics**: Independent-particle and random-phase approximation
- **Electron-phonon coupling** (yambo_ph)
- **Real-time dynamics** (yambo_rt)
- **Non-linear optics** (yambo_nl)
- **QP lifetimes**: Imaginary part of self-energy

**Yambo is a postprocessing engine.** It requires wavefunctions from an
upstream DFT code. Supported DFT interfaces:

| DFT Code          | Converter | Status           |
|-------------------|-----------|------------------|
| Quantum ESPRESSO  | `p2y`     | Primary, best supported |
| ABINIT            | `a2y`     | Supported        |
| CPMD              | `c2y`     | Less common      |
| **VASP**          | **None**  | **NOT SUPPORTED** |

---

## 2. Executables

| Executable  | Purpose                                       |
|-------------|-----------------------------------------------|
| `p2y`       | Convert QE wavefunctions → yambo SAVE format  |
| `a2y`       | Convert ABINIT wavefunctions → yambo SAVE     |
| `c2y`       | Convert CPMD wavefunctions → yambo SAVE       |
| `yambo`     | Main engine (GW, BSE, TDDFT, optics)          |
| `yambo_sc`  | Self-consistent calculations (SC-COHSEX, etc.)|
| `yambo_rt`  | Real-time dynamics                             |
| `yambo_nl`  | Non-linear optics                              |
| `yambo_ph`  | Electron-phonon coupling                       |
| `ypp`       | Post-processing (band interpolation, etc.)     |
| `ypp_*`     | Post-processing for specialized modules        |

---

## 3. Typical Workflow

### QE → Yambo GW+BSE Workflow

```
Step 1: QE SCF          pw.x < scf.in
Step 2: QE NSCF         pw.x < nscf.in  (more bands, force_symmorphic=.true.)
Step 3: p2y             cd work/prefix.save/ && p2y
Step 4: yambo init      cp -r SAVE ../ && cd .. && yambo
Step 5: GW              yambo -hf -gw0 p -dyson n -F gw.in
Step 6: BSE             yambo -optics b -kernel sex -Ksolver h -F bse.in
Step 7: ypp             ypp -s b -F ypp.in  (band interpolation)
```

### Key Rules
- Run yambo from the directory **containing** SAVE/, never inside SAVE/
- yambo generates input templates: `yambo -hf -gw0 p -F gw.in -Q`
- NSCF calculation needs `force_symmorphic = .true.` for yambo compatibility
- p2y creates SAVE/ inside `prefix.save/`; must copy SAVE to working directory

---

## 4. Input File Format

Three constructs:

### 4.1 Runlevel Flags (bare keywords)
```
HF_and_locXC          # enables HF self-energy
gw0                   # enables G0W0
ppa                   # enables PPA screening
em1d                  # enables dynamical dielectric matrix
dyson                 # enables Dyson equation solver
```

### 4.2 Scalar Variables
```
EXXRLvcs= 5961  RL    # [XX] Exchange RL components
DysSolver= "n"        # [GW] Dyson solver (n=Newton)
PPAPntXp= 27.21138 eV # [Xp] PPA imaginary energy
```

### 4.3 Block Variables
```
% BndsRnXp
   1 |  50 |          # [Xp] Polarization bands
%
% QPkrange
1|10|3|6|              # [GW] k-range | band-range
%
```

### Key Variables by Calculation Type

**GW**: `BndsRnXp`, `NGsBlkXp`, `GbndRnge`, `QPkrange`, `DysSolver`, `GTermKind`
**BSE**: `BndsRnXs`, `NGsBlkXs`, `BSEBands`, `BSENGexx`, `BSENGBlk`, `BSSmod`, `BSKmod`
**Optics**: `BndsRnXd`, `NGsBlkXd`, `ChiEnRnge`, `ChiEnStps`, `Chimod`

---

## 5. Output File Format

### Naming Convention
| Prefix | Type       | Description                          |
|--------|------------|--------------------------------------|
| `r-*`  | Report     | System info, parameters, warnings    |
| `o-*`  | Output     | Human-readable results               |
| `l-*`  | Log        | Runtime progress                     |
| `ndb.*`| Database   | Binary netCDF (machine-readable)     |
| `LOG/` | Directory  | Per-CPU logs (parallel runs)         |

### The `-J` flag
The `-J jobname` flag labels all output files: `o-jobname.qp`, `r-jobname_...`
and creates a database subdirectory `jobname/` for netCDF files.

### QP Output Format (o-*.qp)
```
#    K-point    Band    Eo [eV]    E-Eo [eV]    Sc|Eo [eV]
      1          4     0.000000   0.406459     1.680673
      1          5     2.832664   1.448329    -2.500886
```
- Eo = DFT eigenvalue
- E-Eo = GW correction
- QP energy = Eo + (E-Eo)

### Spectrum Output Format (o-*.eps_*)
```
#    E[1] [eV]    Im(eps)    Re(eps)    [optional extra columns]
     0.000000     0.356789   14.45286
     0.101010     0.357676   14.46300
```

---

## 6. File System: SAVE Directory

After p2y + yambo init:
```
SAVE/
├── ns.db1                    # Core: lattice, geometry, KS bands
├── ns.wf                     # Wavefunction metadata
├── ns.wf_fragments_*_1       # Wavefunction data per k-point
├── ns.kb_pp_pwscf            # Pseudopotential KB projectors
├── ns.kb_pp_pwscf_fragment_* # Pseudo data per k-point
├── ndb.gops                  # G-vector shells (init)
└── ndb.kindx                 # k/q-point indices (init)
```

After GW (`-J gw_run`):
```
gw_run/
├── ndb.HF_and_locXC          # HF and Vxc
├── ndb.pp                    # PPA parameters
├── ndb.em1d*                 # Dynamical dielectric matrix
├── ndb.QP                    # Quasiparticle corrections
└── ndb.dip_iR_and_P          # Dipole matrix elements
```

---

## 7. Smoke Test Results (Si, 4x4x4 k-grid, ONCV NC pseudo)

### Setup
- Structure: Si diamond, celldm(1) = 10.20 bohr, 2 atoms
- Pseudo: Si_ONCV_PBE-1.2.upf (norm-conserving)
- K-grid: 4x4x4 → 10 IBZ k-points, 256 BZ points
- ecutwfc = 30 Ry, nbnd = 50 (NSCF)

### DFT Results (from r_setup)
- Fermi level: 6.093 eV
- DFT indirect gap: 1.143 eV (K1→K8)
- DFT direct gap: 2.807 eV (K9)
- Filled bands: 4

### GW Results (G0W0 PPA, bands 3-6, all k-points)
- VBM (K1, band 4): Eo=0.000, E-Eo=+0.406 → QP=0.406 eV
- CBM (K8, band 5): Eo=1.143, E-Eo=+1.090 → QP=2.233 eV
- **GW indirect gap ≈ 1.83 eV** (vs DFT 1.14 eV)
- Wall time: 22 seconds (serial)

### IP Optics Results
- Static dielectric constant Re(ε₁(0)) ≈ 14.5 (IP level)
- 100 energy points from 0-10 eV
- 19 q-points computed

### BSE Results (SEX kernel, Haydock solver)
- Screening: 20 bands, 1 RL block
- BSE bands: 3-6 (2 valence, 2 conduction)
- Haydock converged in 42 iterations
- Static dielectric constant Re(ε₁(0)) ≈ 6.8 (with excitonic effects)
- 200 energy points from 0-10 eV

All results are physically reasonable for Si with a minimal basis.

---

## 8. Integration Points with QMatSuite

### Yambo as Postprocessing Engine
Like W90 (Wannier90) and QMCPACK, yambo is a postprocessing engine that
consumes output from an upstream DFT engine (QE). The key differences from W90:

1. **Converter step**: W90 doesn't need a converter; yambo needs `p2y`
2. **Initialization**: yambo needs a bare `yambo` run to create ndb.gops/ndb.kindx
3. **SAVE directory**: yambo requires the entire SAVE/ directory, not individual files
4. **Input generation**: yambo generates its own input templates from SAVE databases
5. **Multiple calculation types**: yambo supports GW, BSE, TDDFT, etc. (not just one)

### Dependency Chain
```
QE SCF → QE NSCF → p2y (convert) → yambo init → yambo GW/BSE/optics
```

### Key Artifacts
- **Input**: SAVE/ directory (from p2y + init)
- **Inter-step**: ndb.QP (GW→BSE), ndb.em1s (screening→BSE)
- **Output**: o-*.qp, o-*.eps_*, ndb.* databases

### VASP Integration: NOT POSSIBLE
Yambo has no VASP converter (no v2y). If the user's upstream DFT is VASP,
they cannot use yambo. This must be clearly documented in the driver.

---

## 9. Python Resources for Parsing

### yambopy (official)
- Reads all netCDF databases
- Classes: YamboLatticeDB, YamboQPDB, YamboExcitonDB, etc.
- Install: `pip install yambopy` or from git

### Text output parsing
- o-*.qp: Simple 5-column table (k, band, Eo, E-Eo, Sc|Eo)
- o-*.eps_*: Simple N-column table (E, Im(eps), Re(eps), ...)
- r-*: Section-based report with labeled key-value pairs
- All text files have # comment header with metadata

---

## 10. Files in This Exploration Directory

```
exploration/
├── YAMBO_EXPLORATION.md       # This file
├── YAMBO_INTEGRATION_PLAN.md  # Integration plan for QMatSuite
├── yambo_parser.py            # Output parser utility
├── yambo_writer.py            # Input writer utility
├── golden_refs/               # Golden reference artifacts
│   ├── r_setup                # Setup report
│   ├── gw/                    # GW outputs
│   │   ├── o-gw_si.qp
│   │   └── r-gw_si_...
│   ├── bse/                   # BSE outputs
│   │   ├── o-bse_si.eps_q1_haydock_bse
│   │   ├── o-bse_si.eel_q1_haydock_bse
│   │   └── r-bse_si_...
│   ├── ip/                    # IP optics outputs
│   │   ├── o-ip_si.eps_q1_ip
│   │   └── r-ip_si_...
│   └── inputs/                # Input files (QE + yambo)
│       ├── scf.in, nscf.in
│       ├── gw.in, bse.in, ip.in
│       └── *_generated.in     # Writer-generated inputs
├── smoke_si/                  # First smoke test (USPP — crashed)
└── smoke_si_nc/               # Working smoke test (ONCV NC)
    ├── scf.in, nscf.in
    ├── gw.in, bse.in, ip.in
    ├── work/                  # QE work directory
    ├── SAVE/                  # Yambo database directory
    ├── gw_si/                 # GW database output
    ├── bse_si/                # BSE database output
    ├── ip_si/                 # IP database output
    ├── gw_output/             # GW text output
    ├── bse_output/            # BSE text output
    └── ip_output/             # IP text output
```
