# Gaussian Engine Exploration

## Overview

Gaussian is a widely-used commercial quantum chemistry package for electronic structure calculations. It supports a variety of methods including Hartree-Fock, DFT, post-HF methods (MP2, CCSD), and excited state calculations (TDDFT, CIS).

**Version tested**: Gaussian 09, Revision D.01
**Installation location**: `.qmatsuite/engines/gaussian/gaussian09/`

---

## 1. Engine Binary and Environment

### Binaries

| Binary | Description |
|--------|-------------|
| `g09` | Main Gaussian 09 executable |
| `g16` | Main Gaussian 16 executable (if available) |
| `formchk` | Checkpoint file formatter (binary .chk → text .fchk) |
| `unfchk` | Reverse formatter (text .fchk → binary .chk) |
| `freqchk` | Extract frequency data from checkpoint |

### Environment Variables

```bash
export g09root=/path/to/gaussian09
export GAUSS_EXEDIR=$g09root/g09
export GAUSS_SCRDIR=/tmp   # Scratch directory
export PATH=$GAUSS_EXEDIR:$PATH
```

### Execution

```bash
$GAUSS_EXEDIR/g09 < input.gjf > output.log 2>&1
```

Or simply:
```bash
g09 input.gjf
```

---

## 2. Input File Format (.gjf/.com)

Gaussian input files have a strict format with sections separated by blank lines:

```
%Link0 commands
#route line

Title

charge multiplicity
atom1 x y z
atom2 x y z
...

(blank line required at end)
```

### Link0 Commands

| Command | Description | Example |
|---------|-------------|---------|
| `%mem` | Memory allocation | `%mem=500MB`, `%mem=2GB` |
| `%nproc` | Number of processors | `%nproc=4` |
| `%chk` | Checkpoint file | `%chk=water.chk` |
| `%rwf` | Read-write file location | `%rwf=/scratch/water.rwf` |
| `%nosave` | Don't save checkpoint | `%nosave` |

### Route Line

Format: `#[p|n] method/basis [keywords]`

- `#p` = verbose output (print all)
- `#n` = normal output
- `#t` = terse output

Examples:
- `#p HF/STO-3G` — HF single point
- `#p B3LYP/6-31G* Opt` — DFT geometry optimization
- `#p MP2/cc-pVDZ` — MP2 single point
- `#p TD=(NStates=3) B3LYP/STO-3G` — TDDFT

### Geometry Specification

Cartesian format (Angstroms):
```
0 1
O    0.000000    0.000000    0.117499
H    0.000000    0.756950   -0.469996
H    0.000000   -0.756950   -0.469996
```

Z-matrix format:
```
0 1
O
H  1  0.96
H  1  0.96  2  104.5
```

---

## 3. Output File Format (.log)

### Key Parsing Patterns

| Data | Pattern |
|------|---------|
| SCF Energy | `SCF Done:  E(RHF) =  -74.9631155184     A.U. after    7 cycles` |
| MP2 Energy | `E2 =    -0.1218324231D+00 EUMP2 =    -0.77194688921108D+02` |
| Opt Converged | `Optimization completed.` or `Stationary point found.` |
| Frequencies | `Frequencies --   2169.8207              4141.9658              4393.0665` |
| ZPE | `Zero-point correction=                           0.024387 (Hartree/Particle)` |
| TDDFT States | `Excited State   1:      Singlet-A2     4.0615 eV  305.26 nm  f=0.0000` |
| Dipole | `X=   0.0000    Y=   0.0000    Z=  -1.7255  Tot=   1.7255` |
| Normal Term. | `Normal termination of Gaussian 09` |
| Error Term. | `Error termination via ...` |

### Archive Line

Compact summary at end of log:
```
1\1\GINC-HOST\SP\RHF\STO-3G\H2O1\USER\DATE\0\\#p HF/STO-3G\\Title\\
0,1\O,0,0.,0.,0.117499\H,0,0.,0.75695,-0.469996\...\\Version=...\HF=-74.9631155\...\\@
```

---

## 4. Supported Calculation Types

### 4.1 Single Point Energy (sp)

```
#p HF/STO-3G
```

Output: `SCF Done: E(RHF) = -74.9631155184 A.U.`

### 4.2 Geometry Optimization (opt/relax)

```
#p B3LYP/6-31G* Opt
```

Keywords:
- `Opt` — Default optimization
- `Opt=Tight` — Tight convergence
- `Opt=CalcFC` — Calculate force constants at start
- `Opt=(MaxCycles=100)` — Set max iterations

### 4.3 Frequency Calculation (freq)

```
#p HF/STO-3G Freq
```

Output: Frequencies, ZPE, thermal corrections, IR intensities.

### 4.4 Optimization + Frequency (opt+freq)

```
#p HF/STO-3G Opt Freq
```

### 4.5 MP2 (mp2)

```
#p MP2/STO-3G
```

Output: HF energy + E2 correlation + MP2 total energy.

### 4.6 TDDFT Excited States (td)

```
#p TD=(NStates=3) B3LYP/STO-3G
```

Output: Excitation energies (eV), wavelengths (nm), oscillator strengths.

### 4.7 Forces (force)

```
#p B3LYP/6-31G* Force
```

Output: Cartesian forces on atoms.

---

## 5. Smoke Tests Performed

All tests run with `%mem=500MB`, `%nproc=1`.

| Test | Method | Basis | Result |
|------|--------|-------|--------|
| Water SP | HF | STO-3G | E = -74.963 Ha ✓ |
| Water Opt | B3LYP | 6-31G* | Converged in 3 steps ✓ |
| Water Opt+Freq | HF | STO-3G | Freqs: 2170, 4142, 4393 cm⁻¹ ✓ |
| Ethylene MP2 | MP2 | STO-3G | EUMP2 = -77.195 Ha ✓ |
| Formaldehyde TDDFT | B3LYP | STO-3G | 3 states: 4.06, 9.48, 12.00 eV ✓ |

Artifacts saved in `smoke_tests/` directory.

---

## 6. Checkpoint Files

### Binary Checkpoint (.chk)

- Used for restart, reading wavefunction
- Binary format, machine-dependent
- Keywords: `Guess=Read`, `Geom=Checkpoint`

### Formatted Checkpoint (.fchk)

```bash
formchk water.chk water.fchk
```

Human-readable format, useful for:
- Reading orbitals, density matrices
- Interface with other programs
- Post-processing scripts

---

## 7. Comparison with Similar Engines

### vs ORCA

| Aspect | Gaussian | ORCA |
|--------|----------|------|
| Input format | `.gjf` with blank line separators | `.inp` with keyword blocks |
| Coordinate default | Angstroms | Angstroms |
| Parallelization | `%nproc=N` | `%pal nprocs N end` |
| Restart | `.chk` files | `.gbw` files |
| Output | Single `.log` file | Multiple output files |
| License | Commercial | Free for academics |

### vs PySCF

| Aspect | Gaussian | PySCF |
|--------|----------|-------|
| Interface | File-based | Python API |
| Integration | External binary | Native Python |
| Flexibility | Fixed workflow | Programmatic |

---

## 8. QMatSuite Integration Considerations

### Recipe Archetype

**Strong-chain + ISOLATED workdir** (similar to ORCA)
- Each step runs in isolated directory
- Checkpoint files (.chk) enable restart
- No multi-stage dependency like QE's NSCF→bands

### Step Types

| GEN Step | SPEC Step | Description |
|----------|-----------|-------------|
| `scf` | `gaussian_scf` | DFT/HF single point |
| `hf` | `gaussian_hf` | Hartree-Fock specifically |
| `relax` | `gaussian_relax` | Geometry optimization |
| `freq` | `gaussian_freq` | Frequency calculation |
| `mp2` | `gaussian_mp2` | MP2 correlation |
| `td` | `gaussian_td` | TDDFT excited states |

### Environment Discovery

Engine probe:
```python
"gaussian": EngineProbe(
    engine_name="gaussian",
    binary_names=["g09", "g16"],
    env_vars=["g09root", "g16root", "GAUSS_EXEDIR"],
),
```

---

## 9. Utility Scripts

### Parser (`gaussian_parser.py`)

Parses `.log` files for:
- SCF energy (all methods)
- MP2 energy (E2 + total)
- Optimization convergence + final geometry
- Frequencies + thermochemistry
- TDDFT excited states
- Dipole moment
- Mulliken charges
- Termination status

Usage:
```bash
python gaussian_parser.py output.log
```

### Writer (`gaussian_writer.py`)

Generates `.gjf` input files with:
- Link0 commands (mem, nproc, chk)
- Route line (method/basis + keywords)
- Molecule specification (charge, mult, coords)

Supports: sp, opt, freq, opt+freq, td job types.

---

## 10. Known Issues and Workarounds

### Memory Errors

Error: `Out-of-memory error in l101.exe`

Solution: Increase `%mem` directive. Default 500MB is usually sufficient for small molecules with minimal basis sets.

### Missing Environment

Error: `No executable for l1.exe`

Solution: Set `GAUSS_EXEDIR` environment variable:
```bash
export GAUSS_EXEDIR=/path/to/gaussian/g09
```

### Scratch Space

Error: `rwf file could not be written`

Solution: Set writable scratch directory:
```bash
export GAUSS_SCRDIR=/tmp
```

---

## 11. References

- [Gaussian Documentation](https://gaussian.com/man/)
- [cclib: Computational Chemistry Library](https://cclib.github.io/) — Python parser for Gaussian and other codes
- [GaussView](https://gaussian.com/gaussview/) — GUI for Gaussian
