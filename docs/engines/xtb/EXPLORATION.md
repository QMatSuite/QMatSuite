# xTB Engine Exploration

## 1. Installation & Verification

- **Package**: `xtb 6.7.1` from `conda-forge`
- **Binary**: `/opt/homebrew/Caskroom/miniforge/base/bin/xtb`
- **Build**: `edcfbbe`, compiled on 2025-09-04 for Apple Silicon
- **Dependencies**: None external (standalone binary, no MPI, no HDF5, no NetCDF, no FFTW)
- **Pseudopotentials**: Not needed (semi-empirical method, parameters built-in)
- **License**: LGPL v3+

## 2. What Is xTB

xTB (extended Tight-Binding) is a semi-empirical quantum mechanical method developed by Stefan Grimme's group at the University of Bonn. It provides fast approximate quantum chemistry calculations with parametrized Hamiltonians.

### Key Characteristics

- **Methods**: GFN0-xTB, GFN1-xTB, GFN2-xTB (default), GFN-FF (force field)
- **Basis**: Minimal basis set built into the parametrization (no external basis sets)
- **Pseudopotentials**: Not needed (parameters cover all elements up to Z=86)
- **Scaling**: Approximately O(N^2-N^3) depending on system size
- **Input format**: Standard XYZ files (also supports Turbomole coord, VASP POSCAR, PDB, etc.)
- **Output format**: Text stdout + files (xtbopt.xyz, charges, wbo, energy, gradient, etc.)
- **Parallelism**: OpenMP threading only (no MPI). Controlled via `OMP_NUM_THREADS`
- **Execution model**: Single binary, single process, single command

### Key Differences from Other Engines

| Aspect | QE | VASP | PySCF | xTB |
|--------|-----|------|-------|-----|
| Basis | Plane waves | Plane waves | Gaussians | Built-in minimal |
| PP/Basis files | UPF | POTCAR/PAW | Basis set strings | None needed |
| Input format | Namelists | INCAR/POSCAR | Python scripts | XYZ + CLI flags |
| SCF restart | outdir/ | CHGCAR/WAVECAR | In-memory | xtbrestart |
| Parallelism | MPI + OpenMP | MPI + OpenMP | Threads | OpenMP only |
| Method level | DFT (ab initio) | DFT (ab initio) | HF/DFT/post-HF | Semi-empirical |
| Cost | Expensive | Expensive | Moderate-Expensive | Very cheap |
| Accuracy | High | High | High | Qualitative-Semiquantitative |
| Primary use | Production DFT | Production DFT | Molecular QC | Pre-screening, large systems, structure optimization |

### xTB as a Structure Transformer

xTB's primary value in a multi-engine workflow is as a **fast structure optimizer**. It can:
- Rapidly relax geometries before expensive DFT calculations
- Pre-screen structures in high-throughput workflows
- Provide starting geometries for production calculations with QE/VASP/etc.

**It does NOT produce production-quality electronic structure** (no wavefunctions, no accurate band structures, no reliable electronic properties). Its relaxed geometries, however, are typically good starting points.

## 3. Calculations Performed

### 3.1 H2O Single-Point Energy (GFN2-xTB)

- **Topology**: Single SCF step
- **Command**: `xtb water.xyz --gfn 2`
- **Result**: E_total = -5.070365 Eh, HOMO-LUMO gap = 14.632 eV
- **Output files**: `charges`, `wbo`, `xtbrestart`, `xtbtopo.mol`
- **Exit code**: 0

### 3.2 H2O Geometry Optimization (GFN2-xTB)

- **Topology**: SCF + geometry optimization loop
- **Command**: `xtb input.xyz --opt --gfn 2`
- **Result**: Converged in 4 optimization cycles, E_total = -5.070544 Eh
- **Output files**: `xtbopt.xyz` (optimized geometry), `xtbopt.log` (trajectory), `xtb.out` (full log), `charges`, `wbo`, `.xtboptok` (success marker)
- **Key observation**: `xtbopt.xyz` contains the final relaxed structure with energy in comment line
- **Exit code**: 0

### 3.3 Ethanol Geometry Optimization (GFN2-xTB, tight convergence)

- **Topology**: SCF + geometry optimization loop (tight criteria)
- **Command**: `xtb ethanol.xyz --opt tight --gfn 2`
- **Result**: Converged in ~9 optimization cycles, E_total = -11.394339 Eh
- **Output files**: Same as above but with more optimization steps in `xtbopt.log`
- **Key observation**: `--opt tight` gives tighter convergence (gradient norm < 1e-4)

### 3.4 H2O Frequency Calculation (GFN2-xTB)

- **Topology**: Optimization + Hessian calculation
- **Command**: `xtb water.xyz --ohess --gfn 2`
- **Result**: 3 vibrational frequencies (1539, 3642, 3651 cm^-1), ZPE = 0.020121 Eh
- **Additional output**: `vibspectrum` (IR frequencies), `g98.out` (Gaussian-format modes), `hessian` (Cartesian Hessian)
- **Thermodynamics**: Total free energy = -5.068041 Eh at 298.15 K

### 3.5 Caffeine Gradient Calculation (GFN2-xTB)

- **Topology**: Single-point + gradient
- **Command**: `xtb caffeine.xyz --grad --gfn 2`
- **Result**: E_total = -41.821506 Eh, gradient norm = 0.854791 Eh/a0
- **Additional output**: `energy` (Turbomole format), `gradient` (Turbomole format), `caffeine.engrad`

### 3.6 Ethanol MD Simulation (GFN2-xTB)

- **Topology**: MD simulation from optimized geometry
- **Command**: `xtb ethanol_opt.xyz --md --gfn 2 --input md.inp`
- **Input file**: `md.inp` with `$md` block (temp=300K, time=0.5ps, step=1fs)
- **Result**: 500 MD steps completed, avg T = 293K
- **Output files**: `xtb.trj` (trajectory, 77KB), `mdrestart`, `xtbmdok` (success marker)
- **Key observation**: MD trajectory in `xtb.trj` is multi-frame XYZ format

### 3.7 Error Handling Test

- **Command**: `xtb bad.xyz --opt --gfn 2` (with invalid XYZ content)
- **Result**: Exit code = 1 (not 128 as documented - version-dependent)
- **Key observation**: Non-zero exit code on failure, no output files produced

## 4. xTB Output File Catalog

### Always Produced (Single-Point)
| File | Format | Content |
|------|--------|---------|
| `charges` | Text | Mulliken partial charges, one per atom |
| `wbo` | Text | Wiberg bond orders: `atom_i atom_j bond_order` |
| `xtbrestart` | Binary | SCC restart information |
| `xtbtopo.mol` | MOL | Molecular topology |

### Optimization Only
| File | Format | Content |
|------|--------|---------|
| `xtbopt.xyz` | XYZ | **Optimized geometry** (energy in comment line) |
| `xtbopt.log` | Multi-XYZ | All optimization frames with energies |
| `.xtboptok` | Empty | **Success marker** (exists = optimization converged) |

### Frequency/Hessian Only
| File | Format | Content |
|------|--------|---------|
| `vibspectrum` | Text | Vibrational frequencies with IR intensities |
| `g98.out` | Gaussian format | Normal modes for visualization |
| `hessian` | Text | Cartesian Hessian matrix |

### Gradient Only
| File | Format | Content |
|------|--------|---------|
| `energy` | Turbomole | Total energy |
| `gradient` | Turbomole | Geometry + energy + gradient |
| `*.engrad` | Text | Energy and gradient |

### MD Only
| File | Format | Content |
|------|--------|---------|
| `xtb.trj` | Multi-XYZ | MD trajectory (can be large!) |
| `mdrestart` | Text | MD restart data |
| `xtbmdok` | Empty | **MD success marker** |

### JSON Output (optional, with --json flag)
| File | Format | Content |
|------|--------|---------|
| `xtbout.json` | JSON | Structured output (charges, energies, orbital info) |

## 5. xTB Command-Line Interface

### Runtype Flags (mutually exclusive)

| Flag | Description |
|------|-------------|
| `--scc`, `--sp` | Single-point energy |
| `--grad` | Gradient calculation |
| `--opt [LEVEL]` | Geometry optimization (crude/sloppy/loose/normal/tight/verytight/extreme) |
| `--hess` | Numerical Hessian |
| `--ohess [LEVEL]` | Optimization + Hessian |
| `--md` | Molecular dynamics |
| `--omd` | Optimization + MD |

### Method Flags

| Flag | Description |
|------|-------------|
| `--gfn INT` | GFN parametrization level (0, 1, 2; default=2) |
| `--gfnff`, `--gff` | GFN-FF force field |

### Important Options

| Flag | Description |
|------|-------------|
| `-c INT`, `--chrg INT` | Molecular charge |
| `-u INT`, `--uhf INT` | Number of unpaired electrons |
| `--alpb SOLVENT` | Implicit solvation (ALPB model) |
| `--gbsa SOLVENT` | Implicit solvation (GBSA model) |
| `-I FILE`, `--input FILE` | xcontrol input file for advanced settings |
| `--json` | Write xtbout.json |
| `--namespace STRING` | Namespace for output files |
| `-P INT`, `--parallel INT` | Number of OpenMP threads |
| `--iterations INT` | Max SCF iterations (default 250) |
| `-a REAL`, `--acc REAL` | SCC accuracy (default 1.0, lower=better) |

### Input File (xcontrol)

Advanced settings via `$block` syntax in an xcontrol file:

```
$md
   temp=300       # Temperature in K
   time=10.0      # Simulation time in ps
   dump=50.0      # Dump interval in fs
   step=1.0       # Time step in fs
   hmass=4        # Hydrogen mass scaling
   shake=1        # SHAKE constraints on X-H bonds
$end

$opt
   optlevel=tight
   maxcycle=200
$end

$constrain
   force constant=0.5
   distance: 1, 2, auto
$end
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `OMP_NUM_THREADS` | Number of OpenMP threads (recommended: N,1) |
| `OMP_STACKSIZE` | Stack size per thread (recommended: 1G+ for large systems) |
| `MKL_NUM_THREADS` | Intel MKL thread count |
| `XTBPATH` | Path to parameter files |

## 6. Key Workflow Observations

### xTB vs Other Engine Workflows

**Critical simplicity**: xTB has the simplest possible I/O contract:
- **Input**: One XYZ file + command-line flags (+ optional xcontrol file)
- **Output**: Text stdout + output files in working directory
- **No pseudopotentials**: Parameters are built into the binary
- **No MPI**: Single-threaded or OpenMP only
- **No restart chains**: Each calculation is independent (fast enough to recompute)
- **No complex file staging**: Just the XYZ structure file

### Relaxation as Primary Use Case

For QMatSuite integration, xTB's primary value is **geometry relaxation**:
1. User provides initial structure
2. xTB optimizes geometry (`xtb input.xyz --opt --gfn 2`)
3. Relaxed structure extracted from `xtbopt.xyz`
4. Relaxed structure can be promoted and used for downstream DFT calculations

This is a **pure structure transformation**: input structure -> output structure. No electronic state is produced, reused, or chained.

### Exit Code Semantics

| Exit Code | Meaning |
|-----------|---------|
| 0 | Normal termination (success) |
| 1 | Error (bad input, runtime error) |
| 128 | Fatal error (documented but may vary) |

### Success Detection

For optimization:
- **Primary**: Check for `.xtboptok` file (exists = converged)
- **Secondary**: Check `xtbopt.xyz` exists
- **Tertiary**: Parse stdout for `GEOMETRY OPTIMIZATION CONVERGED`

For single-point:
- **Primary**: Exit code 0
- **Secondary**: Parse stdout for `normal termination of xtb`

## 7. Output Parsing Details

### Standard Output Key Patterns

```
# Total energy (always present)
| TOTAL ENERGY               -5.070544373345 Eh   |

# Gradient norm (always present)
| GRADIENT NORM               0.000148873735 Eh/a  |

# HOMO-LUMO gap (always present)
| HOMO-LUMO GAP              14.384652473341 eV   |

# Optimization convergence
*** GEOMETRY OPTIMIZATION CONVERGED AFTER 4 ITERATIONS ***

# Energy gain from optimization
total energy gain   :        -0.0001798 Eh       -0.1128 kcal/mol

# Normal termination
normal termination of xtb
```

### xtbopt.xyz Format

```
3
 energy: -5.070544373345 gnorm: 0.000148873735 xtb: 6.7.1 (edcfbbe)
O            0.00000000000000       -0.00000000034431        0.10525159408964
H            0.00000000000000        0.77249726255309       -0.46342379717833
H           -0.00000000000000       -0.77249726220878       -0.46342379691131
```

Key: Comment line contains `energy:` and `gnorm:` tokens.

### charges File Format

One charge per line, one per atom:
```
  -0.56453
   0.28226
   0.28226
```

### wbo File Format

Three columns: atom_i, atom_j, bond_order:
```
  1  2  0.92011
  1  3  0.92011
```

### energy File Format (Turbomole)

```
$energy
     1   -5.07054437335   -5.07054437335   -5.07054437335
$end
```

### gradient File Format (Turbomole)

```
$grad
  cycle =      1    SCF energy =   -41.82150596320   |dE/dxyz| =  0.854791
    x1  y1  z1  element
    ...
    gx1  gy1  gz1
    ...
$end
```

## 8. Supported Calculation Types Summary

| Calculation | Command | Key Output | Status |
|------------|---------|------------|--------|
| Single-point | `xtb input.xyz --gfn 2` | stdout, charges, wbo | Tested |
| Optimization | `xtb input.xyz --opt --gfn 2` | xtbopt.xyz, .xtboptok | Tested |
| Tight opt | `xtb input.xyz --opt tight --gfn 2` | xtbopt.xyz, .xtboptok | Tested |
| Frequencies | `xtb input.xyz --ohess --gfn 2` | vibspectrum, hessian | Tested |
| Gradient | `xtb input.xyz --grad --gfn 2` | energy, gradient | Tested |
| MD | `xtb input.xyz --md --gfn 2 --input md.inp` | xtb.trj, xtbmdok | Tested |
| Solvation | `xtb input.xyz --opt --alpb water` | xtbopt.xyz | Not tested |
| GFN-FF | `xtb input.xyz --opt --gfnff` | xtbopt.xyz | Not tested |

## 9. Artifacts Saved

All golden reference artifacts are in `docs/engines/xtb/artifacts/`:

```
artifacts/
  singlepoint_water/   # Single-point: charges, wbo, water.xyz, xtbtopo.mol
  opt_water/           # Optimization: xtb.out (full log), xtbopt.xyz, xtbopt.log, charges, wbo
  opt_ethanol/         # Optimization: ethanol.xyz, xtbopt.xyz, xtbopt.log, charges, wbo
  freq_water/          # Frequencies: vibspectrum, g98.out, hessian, charges, wbo
  grad_caffeine/       # Gradient: energy, gradient, caffeine.engrad, charges, wbo
```
