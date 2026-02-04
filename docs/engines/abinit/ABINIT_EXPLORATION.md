# ABINIT Engine Exploration

**Date**: 2026-02-04
**Engine**: ABINIT 10.4.7
**Status**: Exploration complete, ready for integration

---

## 1. Overview

ABINIT is a plane-wave DFT code for periodic systems, similar to Quantum ESPRESSO but with some unique features:

- **Primary focus**: Ground state, response functions (DFPT), GW, BSE
- **Unique strengths**: Multi-dataset calculations, comprehensive DFPT, strong symmetry handling
- **License**: GNU GPL
- **Language**: Fortran (with NetCDF/HDF5 support)

### Key Similarities to QE
- Plane-wave pseudopotential method
- Same basic workflow (SCF → NSCF → bands/DOS)
- Similar concepts (k-points, ecutwfc/ecut, pseudo files)
- MPI parallel

### Key Differences from QE
1. **Multi-dataset mode**: Single input file can contain multiple sequential calculations
2. **Stricter symmetry handling**: More validation, `chksymbreak` often needed
3. **Different variable names**: `ecut` vs `ecutwfc`, `xred` vs `ATOMIC_POSITIONS {crystal}`
4. **Single input file**: All parameters in one `.abi` file (no separate `*.in` files)
5. **Output format**: YAML-like structured blocks (`--- !ResultsGS`)

---

## 2. Installation

Installed to canonical location: `~/.qmatsuite/engines/abinit/10.4.7/`

### Binary Inventory
| Executable | Description |
|------------|-------------|
| `abinit` | Main DFT engine (28 MB) |
| `anaddb` | Phonon analysis |
| `mrgddb` | Merge DDB files |
| `mrgdv` | Merge derivatives |
| `cut3d` | 3D density tools |
| `abitk` | Toolkit utilities |
| `multibinit` | Multiscale simulations |

### Verification
```bash
~/.qmatsuite/engines/abinit/10.4.7/bin/abinit --version
# Output: 10.4.7-d
```

---

## 3. Input File Format

### Structure
```
# Comment
varname value
varname value1 value2 value3
varname
  value1 value2
  value3 value4
```

### Key Variables

#### Structure Definition
| Variable | Description | Example |
|----------|-------------|---------|
| `acell` | Lattice constant (Bohr) | `acell 3*10.26` |
| `rprim` | Primitive vectors (dimensionless) | `rprim 0 0.5 0.5 ...` |
| `natom` | Number of atoms | `natom 2` |
| `ntypat` | Number of atom types | `ntypat 1` |
| `typat` | Type assignment per atom | `typat 1 1` |
| `znucl` | Nuclear charge per type | `znucl 14` |
| `xred` | Reduced coordinates | `xred 0 0 0 0.25 0.25 0.25` |

#### Electronic Structure
| Variable | Description | Default |
|----------|-------------|---------|
| `ecut` | Plane-wave cutoff (Ha) | Required |
| `ngkpt` | K-point grid | Required |
| `shiftk` | K-point shift | `0 0 0` |
| `nband` | Number of bands | Auto |
| `occopt` | Occupation scheme | 1 |
| `tsmear` | Smearing width | 0.01 |

#### SCF Control
| Variable | Description | Default |
|----------|-------------|---------|
| `nstep` | Max SCF iterations | 30 |
| `toldfe` | Energy tolerance (Ha) | — |
| `tolvrs` | Potential residual tolerance | — |
| `tolwfr` | Wavefunction tolerance | — |
| `iscf` | SCF algorithm | 7 (Pulay) |
| `diemac` | Dielectric constant | 1e6 |

#### Relaxation
| Variable | Description |
|----------|-------------|
| `ionmov` | Ion motion algorithm (2=BFGS) |
| `optcell` | Cell optimization (0=none, 1=volume, 2=full) |
| `ntime` | Max ionic steps |
| `tolmxf` | Force tolerance (Ha/Bohr) |
| `ecutsm` | Cutoff smearing for cell opt |
| `dilatmx` | Max cell expansion factor |

#### Calculation Type Control
| Variable | Values | Description |
|----------|--------|-------------|
| `optdriver` | 0=GS, 1=DFPT, 3=SCR, 4=SIGMA | Calculation type |
| `ionmov` | 0=static, 2=BFGS, 12=MD | Ion motion |
| `iscf` | 7=SCF, -2=NSCF | Self-consistency |

### Multi-Dataset Mode
```
ndtset 2

# Common to all datasets
ecut 10.0
natom 2

# Dataset 1 specific
ngkpt1 4 4 4
toldfe1 1.0e-8

# Dataset 2 specific
iscf2 -2
getden2 1  # Read density from dataset 1
```

### Pseudopotential Specification
```
pp_dirpath "/path/to/pseudos"
pseudos "14si.pspnc"  # Or "Si.psp8, O.psp8" for multiple
```

---

## 4. Output File Format

### Main Output (.abo)

Structure:
1. **Header**: Version, date, files
2. **Input echo**: Preprocessed variables
3. **Per-dataset results**:
   - SCF iterations (`ETOT N energy delta residual`)
   - `--- !ResultsGS` YAML block (energy, forces, stress)
   - `--- !EnergyTerms` YAML block (energy components)
4. **Final echo**: Post-computation variables
5. **Timing**: CPU/wall time summary

### Key Output Patterns

```
# SCF iteration
ETOT  1  -8.8606750188494    -8.861E+00 1.762E-02 1.041E+01

# Results block (YAML-like)
--- !ResultsGS
etotal    :  -8.86646490E+00
fermie    :   2.13587267E-01
pressure_GPa:  -1.5674E+00
cartesian_forces: # hartree/bohr
- [ -0.00000000E+00,  -0.00000000E+00,  -0.00000000E+00, ]
...

# Energy components
--- !EnergyTerms
kinetic             :  3.03418909331926E+00
hartree             :  5.55693171668703E-01
xc                  : -3.53528025677776E+00
total_energy        : -8.86646490252249E+00
...

# Final summary
+Overall time at end (sec) : cpu=  0.3  wall=  0.3
```

### Generated Files
| Suffix | Description |
|--------|-------------|
| `.abo` | Main text output |
| `_WFK` | Wavefunctions (binary) |
| `_DEN` | Charge density (binary) |
| `_EIG` | Eigenvalues (text) |
| `_EIG.nc` | Eigenvalues (NetCDF) |
| `_GSR.nc` | Ground state results (NetCDF) |
| `_DDB` | Derivative database |
| `_HIST.nc` | Relaxation history |

---

## 5. Smoke Tests Performed

### Test 1: Si SCF
- **Input**: `si_scf.abi` - 2-atom diamond Si, 4x4x4 k-grid, ecut=10 Ha
- **Result**: SUCCESS
- **Total energy**: -8.8664649025 Ha
- **SCF iterations**: 6
- **Pressure**: -1.57 GPa (slightly compressed)

### Test 2: Si Relaxation (vc-relax)
- **Input**: `si_relax.abi` - Compressed cell (acell=10.0), ionmov=2, optcell=1
- **Result**: SUCCESS
- **Final acell**: 10.457 Bohr (relaxed from 10.0)
- **Total energy**: -8.7787 Ha
- **SCF iterations**: 12 (4 ionic steps × 3 SCF each)

### Test 3: Si Band Structure (multi-dataset)
- **Input**: `si_bands.abi` - Dataset 1 SCF, Dataset 2 NSCF along L-Γ-X-K-Γ path
- **Result**: SUCCESS
- **Dataset 1**: SCF converged, prtden=1
- **Dataset 2**: NSCF bands, 41 k-points along path

---

## 6. Calculation Types for Integration

### Phase 1 (Core)
| GEN Type | SPEC Type | optdriver | ionmov | Description |
|----------|-----------|-----------|--------|-------------|
| `scf` | `abinit_scf` | 0 | 0 | Ground state SCF |
| `nscf` | `abinit_nscf` | 0 (iscf=-2) | 0 | Non-self-consistent |
| `relax` | `abinit_relax` | 0 | 2 | Ionic relaxation |

### Phase 2 (Extended)
| GEN Type | SPEC Type | optdriver | Description |
|----------|-----------|-----------|-------------|
| `bandspw` | `abinit_bandspw` | 0 (iscf=-2) | Band structure |
| `dos` | `abinit_dos` | 0 | Density of states |
| `md` | `abinit_md` | 0, ionmov=12 | Molecular dynamics |

### Phase 3 (Advanced) - Future
| GEN Type | SPEC Type | optdriver | Description |
|----------|-----------|-----------|-------------|
| `dfpt` | `abinit_dfpt` | 1 | Response functions |
| `screening` | `abinit_screening` | 3 | Dielectric screening |
| `gw` | `abinit_gw` | 4 | GW quasiparticles |

---

## 7. Recipe Archetype Analysis

### Comparison with Existing Engines

| Engine | Archetype | WorkdirPolicy | Shared State |
|--------|-----------|---------------|--------------|
| QE | Directory-state | SHARED | outdir/ (wavefunctions) |
| VASP | Cleanup | CLEANUP | CHGCAR/WAVECAR staged |
| ABINIT | **Directory-state** | **SHARED** | Same prefix files |

### Recommendation: Directory-State (QE-like)

**Rationale**:
1. **Sequential step chaining**: NSCF reads density from SCF (`getden`)
2. **Shared output directory**: All steps write to same `calc/raw/`
3. **File naming**: ABINIT uses `{prefix}o_*` pattern for outputs
4. **Multi-dataset alternative**: Could use single input with ndtset, but explicit steps give more control

**Key differences from QE**:
- No separate `outdir/` - all outputs in main directory
- File prefix via `outdata_prefix` variable
- Multi-dataset mode is an option for coupled calculations

---

## 8. Parser and Writer Summary

### Writer (`abinit_writer.py`)
- `AbinitStructure` dataclass for crystal structure
- `SCFParams`, `RelaxParams`, `NSCFParams` for calculation parameters
- `write_scf_input()`, `write_relax_input()`, `write_bands_input()` functions
- Handles multi-dataset mode for SCF+NSCF workflows

### Parser (`abinit_parser.py`)
- `parse_abinit_output()` - Main entry point
- Extracts: total energy, forces, stress, eigenvalues, SCF iterations
- Handles multi-dataset outputs
- YAML block parsing for structured results
- Calculation type detection from input variables

### Golden References
- `si_scf.abo` - SCF calculation output
- `si_relax.abo` - Relaxation output
- `si_bands.abo` - Multi-dataset SCF+NSCF output
- `si_scfo_EIG` - Eigenvalue file

---

## 9. Integration Considerations

### Pseudopotential Handling
- ABINIT supports multiple PSP formats: `.pspnc`, `.psp8`, `.hgh`, `.xml`
- `pp_dirpath` + `pseudos` variables in input
- Similar to QE's `pseudo_dir` concept
- Can use existing `species_map` pattern

### Multi-Dataset vs Separate Steps
Two options for chained calculations (SCF → NSCF):
1. **Multi-dataset**: Single input file, `ndtset=2`, internal chaining via `getden`
2. **Separate steps**: Individual inputs, explicit file staging

**Recommendation**: Use separate steps for QMatSuite integration
- Matches existing QE pattern
- More granular control
- Easier incremental skip logic
- Clearer artifact tracking

### Convergence Criteria Mapping
| ABINIT | QE | Usage |
|--------|-----|-------|
| `toldfe` | `conv_thr` | Energy (SCF) |
| `tolvrs` | — | Potential residual |
| `tolwfr` | — | Wavefunction (NSCF) |
| `tolmxf` | `forc_conv_thr` | Force (relax) |

---

## 10. Files Produced

```
docs/engines/abinit/
├── ABINIT_EXPLORATION.md     # This file
├── ABINIT_INTEGRATION_PLAN.md # Integration plan
├── abinit_writer.py          # Input file writer utility
├── abinit_parser.py          # Output file parser utility
├── golden_refs/              # Test artifacts
│   ├── si_scf.abi
│   ├── si_scf.abo
│   ├── si_scfo_EIG
│   ├── si_relax.abi
│   ├── si_relax.abo
│   ├── si_relaxo_EIG
│   ├── si_bands.abi
│   ├── si_bands.abo
│   └── si_bandso_DS2_EIG
└── smoke_tests/              # Working smoke test directory
```
