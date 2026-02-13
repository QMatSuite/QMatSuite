# ORCA Documentation Exploration and Verification

**Date**: 2026-01-12
**Status**: Exploration Complete
**Primary Sources**: ORCA 6.0 Manual, ORCA 6.0 Tutorials, ORCA Input Library

---

## 1. Executive Summary

This document provides verified information about ORCA quantum chemistry software based on direct exploration of official documentation. All claims are verified against the ORCA 6.0/6.1 Manual and Tutorials.

### Key Findings

1. **Execution Model**: ORCA is an executable (not library); manages MPI internally; do NOT use `mpirun` wrapper
2. **Restart Semantics**: `AutoStart` auto-detects existing `.gbw` files for single-points; use `MORead` + `%moinp` for explicit control
3. **Property Files**: ORCA generates `.property.txt` files; use `orca_2json` to convert to JSON
4. **Chain Fusion**: ORCA supports multiple jobs in single input via `$new_job` separator
5. **Output Parsing**: Prefer `orca_2json` over stdout parsing for reliable data extraction

---

## 2. ORCA Execution Patterns

### 2.1 Basic Execution

**Source**: [ORCA 6.0 Manual - Calling the Program](https://www.faccts.de/docs/orca/6.0/manual/contents/calling.html)

```bash
# CORRECT: Direct invocation
/path/to/orca input.inp > output.out 2>&1

# WRONG: Do NOT use mpirun
mpirun -np 4 orca input.inp   # INCORRECT!
```

**Key Rules**:
- ORCA executable must be called directly
- ORCA manages MPI internally via `%pal` block
- All parameters in input file, not command-line flags
- Input file is positional argument (not stdin)

### 2.2 Parallelism Configuration

**Source**: [ORCA 6.1 Manual - Parallel Runs](https://orca-manual.mpi-muelheim.mpg.de/contents/essentialelements/parallel.html)

```
# In input file:
%pal
  nprocs 4
end

# Or simple keyword:
! PAL4
```

**Parallelism Guidelines**:
| Method | Recommended Cores | Efficiency |
|--------|-------------------|------------|
| RI-DFT | Up to 16 | Good |
| Hybrid DFT/HF | Up to 16-32 | Moderate |
| CCSD | 8-16 | Good |
| DLPNO-CCSD | 8-32 | Good |

**Environment Requirements**:
- Set `PATH` and `LD_LIBRARY_PATH` for OpenMPI
- ORCA must find its parallel executables via full pathname

---

## 3. Input File Structure

### 3.1 General Format

**Source**: [ORCA 6.0 Manual - Input Structure](https://www.faccts.de/docs/orca/6.0/manual/contents/structure.html)

```
# Comments start with #

! Keywords Method BasisSet Options
! Additional keywords

%blockname
  variable value
  variable2 = value2
end

* xyz charge multiplicity
  C  0.0  0.0  0.0
  O  0.0  0.0  1.13
*
```

**Components**:
1. **Keyword lines** (`!`): Method selection, basis set, run type
2. **Input blocks** (`%...end`): Detailed control
3. **Coordinate specification** (`*...*`): Geometry in various formats

### 3.2 Multi-Job Syntax (`$new_job`)

**Source**: [ORCA 6.0 Manual - Input Structure](https://www.faccts.de/docs/orca/6.0/manual/contents/structure.html)

```
! HF def2-SVP
* xyz 0 1
C  0.0  0.0  0.0
O  0.0  0.0  1.13
*

$new_job
! BP86 def2-SVP
* xyzfile 0 1 prev.xyz   # Reuse geometry
$end
```

**Key Points**:
- Settings transfer between jobs (only specify changes)
- Can reference previous job's files
- **This enables chain fusion for ORCA**: Multiple QMatSuite steps → single ORCA input

---

## 4. Restart and Reuse Semantics

### 4.1 AutoStart Feature

**Source**: [ORCA 6.0 Manual - Initial Guess](https://www.faccts.de/docs/orca/6.0/manual/contents/detailed/initguess.html)

**AutoStart Behavior**:
1. For single-point calculations, ORCA checks for existing `.gbw` file with same basename
2. If found and valid: uses orbitals as initial guess, sets `Guess=MORead`
3. Renames existing `.gbw` to `.ges` before starting
4. **AutoStart is IGNORED for geometry optimizations**

**Disabling AutoStart**:
```
! NoAutoStart

# Or in block:
%scf
  AutoStart false
end
```

### 4.2 Explicit Orbital Reuse (MORead)

**Source**: [ORCA Input Library - Restarting Calculations](https://sites.google.com/site/orcainputlibrary/restarting-calculations)

```
! MORead
%moinp "previous_job.gbw"
```

**Critical Constraint**: The `.gbw` filename must be DIFFERENT from current input basename, or ORCA will fail.

**For Legacy GBW Files** (older ORCA versions):
```
! Rescue MORead
%moinp "old_version.gbw"
```

### 4.3 Reuse Summary Matrix

| Scenario | AutoStart | MORead Required | Notes |
|----------|-----------|-----------------|-------|
| Same-name single-point rerun | Automatic | No | `.gbw` auto-detected |
| Geometry optimization | Ignored | Yes | Must use explicit `%moinp` |
| Different-name continuation | N/A | Yes | Specify source `.gbw` |
| Cross-version restart | N/A | Yes + Rescue | Use `! Rescue MORead` |
| Property calculation (TDDFT, NMR) | N/A | Yes | Read SCF `.gbw` |

---

## 5. Output Artifacts

### 5.1 File Types Generated

**Source**: [ORCA 6.0 Manual - Property File](https://www.faccts.de/docs/orca/6.0/manual/contents/detailed/property_file.html)

| Extension | Purpose | Stable for Analysis | Reusable |
|-----------|---------|---------------------|----------|
| `.out` | Main output (stdout) | Yes (verbose) | No |
| `.gbw` | Wavefunction/orbitals | N/A | **Yes** (primary seed) |
| `.property.txt` | Structured properties | **Yes** (preferred) | No |
| `.hess` | Hessian matrix | Yes | Yes (frequency restart) |
| `.molden` | Visualization orbitals | Yes | No |
| `.xyz` | Final geometry | Yes | Yes (restart geometry) |
| `.engrad` | Energy + gradient | Yes | Yes (opt restart) |
| `.tmp/` | Temporary files | No | No (delete) |

### 5.2 Property File Format

**Source**: [ORCA 6.0 Manual - Property File](https://www.faccts.de/docs/orca/6.0/manual/contents/detailed/property_file.html)

```
# basename.property.txt structure

$PropertyName
&GeometryIndex [integer]
&ListStatus [status]
&ComponentName [type]
value
$End
```

**Component Types**:
- `Double`: Floating-point numbers
- `Integer`: Whole numbers
- `String`: Text in quotation marks
- `ArrayOfDoubles`: Matrices with `&Dim (rows, cols)`
- `Boolean`: True/false values

### 5.3 orca_2json Tool

**Source**: [ORCA 6.0 Manual - orca_2json](https://www.faccts.de/docs/orca/6.0/manual/contents/detailed/orca_2json.html)

**Usage**:
```bash
# Convert property file to JSON
orca_2json basename property

# Request from input file
%Method
  WriteJSONPropertyfile True
end
```

**Capabilities**:
- Converts `.property.txt` to `.json`
- Can export basis sets, integrals, densities (with config file)
- Can generate GBW files from external data

**This is the PREFERRED method for QMatSuite analysis integration**.

---

## 6. Method Families and Capabilities

### 6.1 Capability Landscape

**Source**: [ORCA 6.0 Manual](https://www.faccts.de/docs/orca/6.0/manual/)

| Family | Methods | One-Shot | Chain-Fusable | Primary Output |
|--------|---------|----------|---------------|----------------|
| HF | RHF, UHF, ROHF | Yes | Yes | `.gbw`, energy |
| DFT | B3LYP, PBE, TPSS, etc. | Yes | Yes | `.gbw`, energy |
| TDDFT | TDA, full TDDFT | Needs SCF | Yes | excited states |
| Frequency | Analytical/Numerical | Needs SCF | Yes | `.hess`, freqs |
| NMR | GIAO-based | Needs SCF | Yes | shifts |
| MP2 | RI-MP2, SCS-MP2 | Needs HF/DFT | Limited | correlation E |
| CCSD(T) | DLPNO-CCSD(T) | Needs HF | No | correlation E |
| EOM-CCSD | IP/EA/EE variants | Needs CCSD | No | excited states |
| STEOM-CCSD | DLPNO-STEOM | Needs CCSD | No | excited states |
| CASSCF | Multireference | Optional MOs | No | `.gbw`, energy |

### 6.2 Chain-Fusable Patterns

**What can be combined in a single ORCA input?**

| Base | + Property | Fused Example |
|------|------------|---------------|
| DFT | TDDFT | `! B3LYP def2-SVP` + `%tddft nroots 5 end` |
| DFT | Freq | `! B3LYP def2-SVP Opt Freq` |
| DFT | NMR | `! B3LYP def2-SVP NMR` |
| DFT | Multiple | `! B3LYP def2-SVP Opt Freq` + `%eprnmr ...` |

**What typically requires separate calcs?**
- CCSD(T) (expensive, different memory requirements)
- CASSCF (different active space selection)
- EOM-CCSD (requires prior CCSD)

---

## 7. Canonical Input Examples

### 7.1 DFT Single-Point

**Source**: [ORCA 6.0 Tutorials](https://www.faccts.de/docs/orca/6.0/tutorials/)

```
! B3LYP def2-TZVP TightSCF
%pal nprocs 4 end

* xyz 0 1
O  0.0  0.0  0.0
H  0.0  0.0  0.96
H  0.0  0.93 -0.27
*
```

**Key Keywords**:
- `B3LYP`: Functional
- `def2-TZVP`: Basis set
- `TightSCF`: Tight convergence

### 7.2 DFT + TDDFT (Excited States)

**Source**: [ORCA 6.0 Manual - TDDFT](https://www.faccts.de/docs/orca/6.0/manual/contents/detailed/tddft.html)

```
! B3LYP def2-TZVP TightSCF
%pal nprocs 4 end

%tddft
  NRoots 10          # Number of excited states
  TDA true           # Use Tamm-Dancoff approximation (default)
  Triplets false     # Singlet states only
end

* xyz 0 1
...
*
```

**Output**: Excitation energies, oscillator strengths, transition moments

### 7.3 DFT + Frequency

**Source**: [ORCA 6.0 Manual - Frequencies](https://www.faccts.de/docs/orca/6.0/manual/contents/detailed/frequencies.html)

```
! B3LYP def2-TZVP Opt Freq
%pal nprocs 4 end

%freq
  Temp 298.15, 300, 350    # Multiple temperatures
  ScalFreq 0.967           # Scaling factor
end

* xyz 0 1
...
*
```

**Output**: Harmonic frequencies, IR intensities, thermochemistry

### 7.4 DFT + NMR

**Source**: [ORCA 6.0 Tutorials - NMR](https://www.faccts.de/docs/orca/6.0/tutorials/spec/NMR.html)

```
! TPSS PCSSEG-1 AUTOAUX NMR CPCM(CHCl3)
%pal nprocs 4 end

%eprnmr
  NUCLEI = ALL C {SHIFT}
  NUCLEI = ALL H {SHIFT}
  TAU DOBSON            # For meta-GGA functionals
end

* xyz 0 1
...
*
```

**Note**: NMR shifts need reference shielding (TMS) calculated separately.

### 7.5 Correlated Excited States (DLPNO-STEOM-CCSD)

**Source**: [ORCA 6.0 Manual - DLPNO-STEOM](https://www.faccts.de/docs/orca/6.0/manual/contents/detailed/dlpno-steom.html)

```
! STEOM-DLPNO-CCSD def2-TZVP def2-TZVP/C def2/J TightSCF
%pal nprocs 8 end

%mdci
  NRoots 6
  DoRootWise true
  OThresh 0.005
  VThresh 0.005
  TCutPNOSingles 1e-11
end

* xyz 0 1
C   0.016227  -0.000000   0.000000
O   1.236847   0.000000  -0.000000
H  -0.576537   0.951580  -0.000000
H  -0.576537  -0.951580  -0.000000
*
```

**Requirements**:
- Auxiliary basis sets required (`def2-TZVP/C def2/J` or `AUTOAUX`)
- TightSCF mandatory for CCSD
- RHF reference only (UHF not supported for DLPNO-STEOM)

### 7.6 Multi-Job Chain (DFT → TDDFT via $new_job)

```
! B3LYP def2-TZVP TightSCF
%pal nprocs 4 end
%base "step1_dft"

* xyz 0 1
O  0.0  0.0  0.0
H  0.0  0.0  0.96
H  0.0  0.93 -0.27
*

$new_job
! B3LYP def2-TZVP MORead NoAutoStart
%pal nprocs 4 end
%moinp "step1_dft.gbw"
%base "step2_tddft"

%tddft
  NRoots 5
end

* xyzfile 0 1 step1_dft.xyz
$end
```

**This demonstrates chain fusion: Two QMatSuite steps in one ORCA input.**

---

## 8. Critique of Prior Exploration Document

### 8.1 Claims Verified as CORRECT

| Claim | Source | Status |
|-------|--------|--------|
| ORCA is CLI executable, not library | Manual §3 | **CORRECT** |
| Do NOT use mpirun wrapper | Manual §3 | **CORRECT** |
| `%pal nprocs N` for parallelism | Manual §3 | **CORRECT** |
| `.gbw` files are primary seed artifacts | Manual §7.6 | **CORRECT** |
| `$new_job` for multi-step workflows | Manual §4 | **CORRECT** |
| GBW filename must differ from input basename | Input Library | **CORRECT** |

### 8.2 Claims Needing Correction

| Prior Claim | Correction | Source |
|-------------|------------|--------|
| "`.prop` files" | Correct extension is `.property.txt` | Manual §7.59 |
| "`orca_2mkl` for JSON conversion" | Correct tool is `orca_2json` | Manual §7.58 |
| "AutoStart works for all calculations" | AutoStart is IGNORED for geometry optimizations | Manual §7.6 |
| "Property steps always rerun" | Property calculations can benefit from MORead reuse | Manual |
| "Compound keyword in ORCA 6.0" | Compound is for special workflows, not general multi-step | Manual |

### 8.3 Missing Information Added

1. **`WriteJSONPropertyfile` option**: Can request JSON output directly in input
2. **orca_2json capabilities**: Can export integrals, densities, generate GBW files
3. **DLPNO-STEOM-CCSD**: Efficient correlated excited state method
4. **TightSCF requirement**: Mandatory for all CCSD calculations
5. **Tau treatment for meta-GGA NMR**: Use `TAU DOBSON` for gauge-invariance

---

## 9. ORCA Capability Matrix

| ORCA Family | QMatSuite Step | Chain-Fusable | Primary Artifacts | Reuse Semantics | MVP | Risks |
|-------------|----------------|---------------|-------------------|-----------------|-----|-------|
| DFT SCF | `orca_scf` | Yes (root) | `.gbw`, `.out`, `.property.txt` | AutoStart or MORead | **MVP** | None |
| HF SCF | `orca_hf` | Yes (root) | `.gbw`, `.out`, `.property.txt` | AutoStart or MORead | **MVP** | None |
| TDDFT | `orca_td` | Yes | excited states in `.out`, `.property.txt` | Needs SCF `.gbw` | **MVP** | Large systems slow |
| Frequency | `orca_freq` | Yes | `.hess`, freqs in `.out` | Needs SCF `.gbw` | **MVP** | Numerical Hess slow |
| NMR | `orca_nmr` | Yes | shifts in `.out`, `.property.txt` | Needs SCF `.gbw` | Future | Reference shielding needed |
| MP2 | `orca_mp2` | Limited | correlation E in `.out` | Needs HF `.gbw` | Future | Memory intensive |
| DLPNO-CCSD(T) | `orca_dlpno_ccsd` | No | correlation E in `.out` | Needs HF `.gbw` | Future | Very expensive |
| EOM-CCSD | `orca_eom_ccsd` | No | excited states in `.out` | Needs CCSD `.gbw` | Future | Very expensive |
| STEOM-DLPNO | `orca_steom` | No | excited states in `.out` | Needs DLPNO `.gbw` | Future | Complex setup |
| Geometry Opt | `orca_opt` | Yes | `.xyz`, `.gbw`, `.engrad` | No AutoStart | Future | Multi-cycle tracking |

---

## 10. Non-Negotiable Semantics (From Task Requirements)

### 10.1 Calc Independence
- Each calculation is runtime-isolated
- No cross-calc runtime references
- Future "duplicate calc" copies files but never runtime pointers

### 10.2 Chain Semantics for QC Engines
- **Chain**: Steps rooted at an SCF step
- **Run Calc**: Execute all chains (reuse allowed by default via AutoStart)
- **Run Step**: Execute partial chain from SCF root to target (target MUST run)
- **Fresh run option**: `! NoAutoStart` forces fresh SCF

### 10.3 ORCA Execution Model
- No session; ORCA is executable
- Chain compiles into ONE ORCA input file per chain (minimum ORCA runs)
- Use `$new_job` for multi-step fusion

### 10.4 Keep Logic Simple
- Do NOT introduce complex compatibility fingerprinting
- Use ORCA's native AutoStart/NoAutoStart semantics
- Use MORead + `%moinp` only when explicitly needed

---

## 11. References

### Official Documentation
- [ORCA 6.0 Manual](https://www.faccts.de/docs/orca/6.0/manual/)
- [ORCA 6.0 Tutorials](https://www.faccts.de/docs/orca/6.0/tutorials/index.html)
- [ORCA 6.1 Manual (MPI site)](https://orca-manual.mpi-muelheim.mpg.de/)
- [ORCA Input Library](https://sites.google.com/site/orcainputlibrary/home)

### Key Manual Sections Referenced
- §3: Calling the Program
- §4: Input File Structure
- §7.6: Initial Guess and Restart
- §7.27: Frequency Calculations
- §7.30: TDDFT
- §7.33: EOM-CCSD
- §7.37: DLPNO-STEOM-CCSD
- §7.58: orca_2json
- §7.59: Property File

---

## 12. Questions / Unknowns

1. **orca_2json binary availability**: Is `orca_2json` bundled with all ORCA installations, or is it a separate download?

2. **Property file completeness**: Does the property file contain ALL calculated results, or only a subset?

3. **ORCA 6.0 vs 6.1 differences**: Are there significant changes between 6.0 and 6.1 that affect our integration strategy?

4. **Windows support**: ORCA has Windows builds; does the execution model differ (no mpirun, but what about path handling)?

5. **Scratch directory control**: Best practices for `%tmpdir` in cluster environments?
