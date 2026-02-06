# ORCA Corpus Index

## Overview
This corpus was collected for QMatSuite ORCA integration research.
**Collected**: 2026-02-05
**ORCA Version Focus**: 6.0 / 6.1.1

---

## 1. PDF Documentation (`raw_pdfs/`)

| File | Size | Description |
|------|------|-------------|
| `ORCA_6.0_Manual.pdf` | 55MB | Official ORCA 6.0 complete manual |
| `ORCA_Winter_School_2021.pdf` | 2.5MB | Winter School CC 2021 tutorial |
| `ORCA_TAMU_Intro.pdf` | 500KB | Texas A&M ORCA introduction tutorial |

---

## 2. GitHub Repositories (`extracted/`)

### OrcaNotes (raghurama123/OrcaNotes)
Sample inputs and notes for ORCA. Contains markdown documentation on:
- SinglePointEnergy.md - SCF convergence, convergence criteria
- GeometryOptimization.md - Opt keywords, Hessian calculation
- Methods.md - HF, RI-MP2, DLPNO-MP2 examples
- VibrationalFrequencies.md
- MolecularDynamics.md
- TransitionState.md
- ExcitedStateDynamics.md
- TroubleShooting_STEOM-DLPNO-CCSD.md

### ccinput (cyllab/ccinput)
Python library for generating computational chemistry input files.
Key file: `ccinput/packages/orca.py` - Contains:
- ORCA input template structure
- Calculation type mappings (SP, OPT, TS, FREQ, etc.)
- Block handling logic
- Basis set and method handling
- Solvation model support (SMD, CPCM)

### autochem (tommason14/autochem)
Python automation for GAMESS, Gaussian, PSI4, ORCA.
Key file: `autochem/interfaces/orca.py` - Contains:
- OrcaJob class for input generation
- Template-based input creation
- Job script generation for HPC clusters

---

## 3. Online Documentation (Web Sources)

### Official Documentation
- **Manual**: https://www.faccts.de/docs/orca/6.0/manual/
- **Tutorials**: https://www.faccts.de/docs/orca/6.0/tutorials/
- **Forum**: https://orcaforum.kofo.mpg.de/

### ORCA Input Library
- URL: https://sites.google.com/site/orcainputlibrary/
- Categories: General Input, DFT, Geometry Optimization, Excited States, etc.

---

## 4. ORCA Input Syntax Summary

### Input File Structure
```
! <keyword-line>          # Method, basis, run type, options
%<block-name>             # Optional blocks for detailed settings
  <settings>
end
* xyz <charge> <mult>     # Geometry specification
<atom> <x> <y> <z>
*
```

### Keyword Line Examples
```
! HF DEF2-SVP                                    # Basic HF
! B3LYP DEF2-TZVP OPT                            # DFT optimization
! DLPNO-CCSD(T) CC-PVTZ CC-PVTZ/C               # Coupled cluster
! WB97X-D3 RIJCOSX DEF2-TZVP DEF2/J TIGHTSCF   # Range-separated hybrid with RI
```

### Block Types (37 documented blocks)
| Block | Purpose |
|-------|---------|
| `%scf` | SCF procedure control |
| `%geom` | Geometry optimization settings |
| `%cis` / `%tddft` | Excited state calculations |
| `%casscf` | CASSCF/NEVPT2 control |
| `%mdci` | Single-ref correlation |
| `%cpcm` | Solvation (CPCM) |
| `%pal` | Parallelization |
| `%basis` | Custom basis sets |
| `%coords` | Coordinate input |
| `%freq` | Frequency calculation |
| `%neb` | Nudged Elastic Band |
| `%irc` | Intrinsic Reaction Coord |
| `%md` | Molecular dynamics |
| `%eprnmr` | EPR/NMR properties |
| `%output` | Output control |
| `%plots` | Visualization |

### Geometry Input Formats
```
* xyz 0 1                  # Inline XYZ (charge=0, mult=1)
C 0.0 0.0 0.0
H 1.0 0.0 0.0
*

*xyzfile 0 1 molecule.xyz  # External XYZ file

* int 0 1                  # Z-matrix format
...
*
```

### Convergence Keywords
- SCF: `LOOSESCF`, `NORMALSCF`, `TIGHTSCF`, `VERYTIGHTSCF`, `EXTREMESCF`
- Geometry: `LOOSEOPT`, `NORMALOPT`, `TIGHTOPT`, `VERYTIGHTOPT`

### Common Methods
- **HF**: `HF`, `RHF`, `UHF`, `ROHF`
- **DFT**: `BP86`, `B3LYP`, `PBE`, `PBE0`, `M06-2X`, `WB97X-D3`
- **Post-HF**: `MP2`, `RI-MP2`, `DLPNO-MP2`
- **Coupled Cluster**: `CCSD`, `CCSD(T)`, `DLPNO-CCSD(T)`
- **Multi-ref**: `CASSCF`, `NEVPT2`, `MRCI`

### RI Approximations
- `RI` or `RIJK` - RI for Coulomb
- `RIJCOSX` - RI-J + COSX for exchange (default since ORCA 5.0)
- `RIJONX` - RI-J, exact exchange
- Auxiliary bases: `DEF2/J`, `DEF2/JK`, `CC-PVTZ/C`

### Dispersion Corrections
- `D3ZERO` - D3 with zero damping
- `D3BJ` - D3 with Becke-Johnson damping
- `D4` - D4 dispersion
- `NL` - Nonlocal correlation

---

## 5. Provenance

| Source | URL/Location | Access Date |
|--------|--------------|-------------|
| ORCA 6.0 Manual PDF | faccts.de | 2026-02-05 |
| Winter School Tutorial | winterschool.cc | 2026-02-05 |
| TAMU Tutorial | hprc.tamu.edu | 2026-02-05 |
| OrcaNotes | github.com/raghurama123 | 2026-02-05 |
| ccinput | github.com/cyllab | 2026-02-05 |
| autochem | github.com/tommason14 | 2026-02-05 |
| ORCA Input Library | sites.google.com/site/orcainputlibrary | 2026-02-05 |
