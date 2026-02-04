# Siesta Engine Exploration

## 1. Installation & Verification

- **Package**: `siesta 5.4.2` from `conda-forge` (MPI/OpenMPI build)
- **Binary**: `/opt/homebrew/Caskroom/miniforge/base/bin/siesta`
- **Features**: MPI parallelization, NetCDF-4 support (MPI-IO), Lua support, PSML format
- **Pseudopotentials**: PseudoDojo nc-sr-04 PBE standard (PSML format), 72 elements
  - Source: http://www.pseudo-dojo.org
  - Format: PSML (native for Siesta 5.x)

## 2. What Is Siesta

Siesta (Spanish Initiative for Electronic Simulations with Thousands of Atoms) is a DFT code that uses **numerical atomic orbitals (NAO)** as basis sets (not plane waves like QE, not Gaussians like Gaussian/PySCF). Key characteristics:

- **Basis**: Localized numerical atomic orbitals (PAO: Pseudo-Atomic Orbitals)
  - Sizes: SZ, SZP, DZ, DZP, TZP (single-zeta through triple-zeta polarized)
  - Controlled by `PAO.BasisSize` and `PAO.EnergyShift`
- **Pseudopotentials**: Norm-conserving (PSF or PSML format)
- **XC functionals**: LDA, GGA (PBE, PBEsol, etc.), van der Waals
- **Scaling**: O(N) for large systems via sparse Hamiltonian
- **Input format**: FDF (Flexible Data Format) — key-value + blocks
- **Output naming**: All output files prefixed with `SystemLabel`

### Key Differences from Other Engines

| Aspect | QE | VASP | Siesta |
|--------|-----|------|--------|
| Basis | Plane waves | Plane waves | NAO (localized) |
| PP format | UPF | POTCAR/PAW | PSF/PSML |
| Input format | Namelists | INCAR/POSCAR/KPOINTS | FDF |
| File naming | `prefix.*` | Fixed names | `SystemLabel.*` |
| SCF restart | `outdir/` | CHGCAR/WAVECAR | `.DM` file |
| Parallelization | MPI + OpenMP | MPI + OpenMP | MPI |

## 3. Calculations Performed

### 3.1 H2O Molecule SCF (Molecular, Gamma-only)

- **Topology**: Single SCF step
- **Input**: `h2o.fdf` (SZ basis, MeshCutoff=100 Ry, 10 Ang box)
- **Result**: E_KS = -474.1735 eV, converged in 11 SCF iterations
- **Output files**: `.out`, `.EIG`, `.FA`, `.XV`, `.STRUCT_OUT`, `.DM`, `.HSX`, `.BONDS`, `FORCE_STRESS`, `OUTVARS.yml`, `0_NORMAL_EXIT`

### 3.2 Silicon Bulk SCF + Bands + PDOS (Periodic, k-points)

- **Topology**: SCF with post-processing (bands, PDOS, DOS in single run)
- **Input**: `si_scf.fdf` (DZP basis, MeshCutoff=200 Ry, 4x4x4 k-grid)
- **Result**: E_KS = -230.0361 eV, converged in 6 SCF iterations
- **Additional output**: `.DOS`, `.PDOS.xml`, `.KP`, band structure (via BandLines block)
- **Note**: Siesta computes bands/PDOS/DOS in the same run as SCF (no separate post-processing step needed, unlike QE)

### 3.3 Silicon Bulk Relaxation (Variable-cell CG)

- **Topology**: CG optimization with variable cell (multiple SCF per geometry step)
- **Input**: `si_relax.fdf` (DZP, MeshCutoff=200 Ry, CG method, variable cell)
- **Result**: 8 CG steps, E_KS converging from -229.997 to -230.051 eV
- **Additional output**: `.MDE` (trajectory), `.ANI` (animation), `.CG` (optimizer state), `.MD`, `.MD_CAR`, `.STRUCT_NEXT_ITER`

## 4. Siesta Output File Catalog

### Always Produced
| File | Format | Content |
|------|--------|---------|
| `{label}.out` | Text | Main log: SCF history, energies, forces, timing |
| `{label}.EIG` | Text | Eigenvalues per k-point (line 1: Ef, line 2: Nbands Nspin Nk) |
| `{label}.FA` | Text | Forces on atoms (eV/Ang) |
| `{label}.XV` | Text | Positions (Bohr) + velocities |
| `{label}.STRUCT_OUT` | Text | Final structure (lattice + fractional coords) |
| `{label}.DM` | Binary | Density matrix (for SCF restart) |
| `{label}.HSX` | Binary | Hamiltonian + overlap (sparse) |
| `{label}.BONDS` | Text | Bond analysis |
| `{label}.KP` | Text | K-points with weights |
| `{label}.ORB_INDX` | Text | Orbital index mapping |
| `FORCE_STRESS` | Text | Total energy + stress tensor + forces |
| `OUTVARS.yml` | YAML | Structured energy breakdown |
| `0_NORMAL_EXIT` | Text | Marker file for successful completion |
| `MESSAGES` | Text | Warning/error messages |

### Relaxation/MD Only
| File | Format | Content |
|------|--------|---------|
| `{label}.MDE` | Text | Trajectory: step, T, E_KS, E_tot, Vol, P |
| `{label}.ANI` | XYZ | Animation file (multi-frame XYZ) |
| `{label}.CG` | Text | CG optimizer state |
| `{label}.MD` | Text | MD/relaxation trajectory data |
| `{label}.STRUCT_NEXT_ITER` | Text | Structure for next iteration |

### Post-Processing (when requested)
| File | Format | Content |
|------|--------|---------|
| `{label}.DOS` | Text | Total DOS (energy, dos) |
| `{label}.PDOS.xml` | XML | Projected DOS per orbital |
| `{label}.bands` | Text | Band structure data |

### Binary/Large (do not save as artifacts)
| File | Format | Notes |
|------|--------|-------|
| `{label}.DM` | Binary | Density matrix — needed for restart |
| `{label}.HSX` | Binary | Hamiltonian/overlap sparse matrix |
| `*.ion` | Binary | Basis set data (generated at runtime) |
| `*.ion.nc` | NetCDF | Basis set data (NetCDF format) |
| `*.ion.xml` | XML | Basis set data (XML format) |

## 5. Siesta File Format Details

### FDF Input Format
- Case-insensitive key-value pairs: `KeyName value`
- Block data: `%block BlockName ... %endblock BlockName`
- Comments: `#` or any line not matching key-value format
- Units specified inline: `LatticeConstant 5.43 Ang`
- Boolean: `T`/`F` or `.true.`/`.false.`

### .EIG File Format
```
Ef_eV                           # Line 1: Fermi energy
Nbands  Nspin  Nkpoints         # Line 2: dimensions
kpt_idx  eig1  eig2  ...        # k-point block (may span multiple lines)
         eig_continued  ...     # continuation lines (no kpt index)
```

### FORCE_STRESS File Format
```
total_energy                    # Line 1: total energy (Ry)
s11  s12  s13                   # Lines 2-4: stress tensor (Ry/Bohr^3)
s21  s22  s23
s31  s32  s33
natoms                          # Line 5: number of atoms
sp_idx  Z  fx  fy  fz  label   # Lines 6+: forces (Ry/Bohr)
```

### .MDE File Format
```
# Step  T(K)  E_KS(eV)  E_tot(eV)  Vol(A^3)  P(kBar)
0  0.00  -229.99666  -229.99666  41.594  -4.247
```

### OUTVARS.yml
Standard YAML with `siesta:` (build info) and `energies:` (decomposed energy terms in Ry).

## 6. Key Workflow Observations

### Siesta vs QE Workflow Topology

**Critical difference**: Siesta computes bands, DOS, and PDOS in the **same run** as SCF. There is no separate `bands.x` or `dos.x` post-processing step. This means:

1. `BandLines` block in the SCF FDF file triggers band structure calculation
2. `ProjectedDensityOfStates` block triggers PDOS calculation
3. DOS is always computed from eigenvalues

This means Siesta's step topology is **simpler** than QE's:
- **SCF**: Single step (can include bands + PDOS in same run)
- **Relax**: Single step (SCF + geometry optimization loop)
- **MD**: Single step (SCF + dynamics loop)
- **NSCF**: Not a separate step — Siesta doesn't distinguish SCF/NSCF in the same way

### Restart Mechanism
- Siesta restarts from the `.DM` file (density matrix)
- Set `DM.UseSaveDM T` in the FDF to read previous DM
- The `.DM` file is binary and engine-specific

### Pseudopotential Handling
- Siesta looks for `{label}.psml` or `{label}.psf` in the working directory
- The label matches the species label from `ChemicalSpeciesLabel` block
- Must be staged into the working directory before running

## 7. Parser & Input Writer

### Parser (`scripts/siesta_parser.py`)
Tested against all 3 artifact sets:
- Parses `.out` file: total energy, Fermi energy, SCF history, convergence, forces, stress
- Parses `.EIG`: eigenvalues per k-point
- Parses `.FA`: forces on atoms
- Parses `.STRUCT_OUT`: final structure
- Parses `.XV`: positions + velocities in Bohr
- Parses `FORCE_STRESS`: energy + stress tensor + forces
- Parses `OUTVARS.yml`: energy decomposition
- Parses `.MDE`: relaxation/MD trajectory
- Parses `.DOS`: total DOS
- Parses `.PDOS.xml`: projected DOS per orbital
- Checks `0_NORMAL_EXIT` marker file

### Input Writer (`scripts/siesta_input_writer.py`)
Generates FDF files from structured parameters:
- System identification (name, label)
- Species and pseudopotential mapping
- Lattice and atomic coordinates
- K-point grid (Monkhorst-Pack)
- SCF parameters (MeshCutoff, mixing, XC functional)
- Relaxation/MD parameters (CG, Verlet, variable cell)
- Post-processing requests (PDOS, band lines)
