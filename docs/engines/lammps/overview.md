# LAMMPS Engine Overview

**Version**: 1.0.0  
**Date**: 2026-01-19  
**Status**: Research & Design Phase  
**Constitution Reference**: §A (Parameters), §B (Assets), §C (Engine Registry)

---

## 1. What is LAMMPS?

LAMMPS (**L**arge-scale **A**tomic/**M**olecular **M**assively **P**arallel **S**imulator) is a classical molecular dynamics simulation engine developed primarily at Sandia National Laboratories. It is designed to simulate systems at the atomic, meso, or continuum scale using a wide variety of interatomic potentials (force fields) and boundary conditions.

### Key Characteristics

| Aspect | Description |
|--------|-------------|
| **Domain** | Classical molecular dynamics (MD), energy minimization, Monte Carlo |
| **Scale** | From small molecules to billions of atoms |
| **Potentials** | LJ, EAM, Tersoff, ReaxFF, SNAP, DeepMD, GAP, MACE, and 100+ others |
| **Parallelization** | MPI, OpenMP, GPU (CUDA/HIP), Kokkos abstraction layer |
| **License** | GPL-2.0 (open source) |

LAMMPS differs fundamentally from quantum-mechanical engines (QE, VASP, ORCA, PySCF) in that it uses classical force fields rather than solving electronic structure equations. This makes it orders of magnitude faster for large systems but requires appropriate potential parameterizations.

---

## 2. Core Concepts

### 2.1 Input Script Structure

LAMMPS uses a Domain-Specific Language (DSL) input script with a specific command ordering:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. INITIALIZATION                                           │
│    units, dimension, boundary, atom_style                   │
├─────────────────────────────────────────────────────────────┤
│ 2. SYSTEM DEFINITION                                        │
│    read_data / read_restart / create_box + create_atoms     │
├─────────────────────────────────────────────────────────────┤
│ 3. FORCE FIELD SETTINGS                                     │
│    pair_style, pair_coeff, bond_style, kspace_style         │
├─────────────────────────────────────────────────────────────┤
│ 4. SIMULATION SETTINGS                                      │
│    fix (thermostat, barostat), compute, neighbor settings   │
├─────────────────────────────────────────────────────────────┤
│ 5. OUTPUT SETTINGS                                          │
│    thermo, thermo_style, dump, restart                      │
├─────────────────────────────────────────────────────────────┤
│ 6. EXECUTION                                                │
│    minimize / run                                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Key Commands

| Command Category | Commands | Purpose |
|------------------|----------|---------|
| **Initialization** | `units`, `dimension`, `boundary`, `atom_style` | Define simulation box and atom properties |
| **Structure** | `read_data`, `read_restart`, `create_atoms` | Load or create atomic configuration |
| **Force Field** | `pair_style`, `pair_coeff`, `bond_style`, `kspace_style` | Define interatomic interactions |
| **Fixes** | `fix nve`, `fix nvt`, `fix npt`, `fix shake` | Thermostats, barostats, constraints |
| **Computes** | `compute temp`, `compute pe`, `compute stress/atom` | Calculate observables |
| **Output** | `thermo`, `thermo_style`, `dump`, `restart` | Control output frequency and content |
| **Execution** | `run`, `minimize` | Perform MD or energy minimization |

### 2.3 Units Systems

LAMMPS supports multiple unit systems. The most common:

| Units | Length | Energy | Time | Mass | Use Case |
|-------|--------|--------|------|------|----------|
| `metal` | Å | eV | ps | g/mol | Metals, semiconductors |
| `real` | Å | kcal/mol | fs | g/mol | Biomolecules, polymers |
| `lj` | σ | ε | τ | m | Lennard-Jones fluids |
| `si` | m | J | s | kg | SI units |

**IMPORTANT**: QMatSuite will normalize LAMMPS outputs to canonical units (Å, eV, fs) consistent with our trajectory specification.

### 2.4 atom_style

The `atom_style` determines what per-atom properties are stored:

| Style | Properties | Use Case |
|-------|------------|----------|
| `atomic` | position, type, velocity | Simple atomic systems |
| `charge` | + charge | Ionic systems |
| `full` | + bonds, angles, charges, molecule ID | Molecular systems |
| `molecular` | + bonds, angles, molecule ID | Polymers without charges |

---

## 3. Input Files

### 3.1 Input Script (`in.lammps`)

The primary input file containing commands. Example minimal script:

```bash
# Initialization
units metal
atom_style atomic
boundary p p p

# Read structure
read_data structure.data

# Force field (EAM for Cu)
pair_style eam/alloy
pair_coeff * * Cu_u3.eam Cu

# Output settings
thermo 100
thermo_style custom step temp pe etotal press

# Minimization
minimize 1.0e-6 1.0e-8 1000 10000
```

### 3.2 Data File (`structure.data`)

Contains atomic positions, topology, and simulation box:

```
LAMMPS data file

4 atoms
1 atom types

0.0 3.6 xlo xhi
0.0 3.6 ylo yhi
0.0 3.6 zlo zhi

Masses

1 63.546

Atoms

1 1 0.0 0.0 0.0
2 1 1.8 1.8 0.0
3 1 0.0 1.8 1.8
4 1 1.8 0.0 1.8
```

### 3.3 Potential Files

External files containing force field parameters:

- **EAM files**: `*.eam`, `*.eam.alloy`, `*.eam.fs` (embedding functions, pair potentials)
- **ReaxFF files**: `ffield.reax.*` (reactive force field parameters)
- **Tersoff files**: `*.tersoff` (multi-body potential parameters)
- **ML models**: `*.pb` (DeepMD), `*.model` (MACE), SNAP coefficients

---

## 4. Output Files

### 4.1 Log File (`log.lammps`)

Contains:
- Command echo (input script mirrored)
- Thermo output (energy, temperature, pressure time series)
- Timing and performance statistics
- Warnings and errors

Example thermo output block:
```
Step Temp PotEng TotEng Press
0    300.00  -3.5420  -3.5420  -12.345
100  298.52  -3.5418  -3.5404  -11.892
200  301.23  -3.5415  -3.5397  -12.103
```

### 4.2 Dump Files

Trajectory snapshots containing per-atom data:

```bash
dump myDump all custom 1000 dump.lammpstrj id type x y z vx vy vz fx fy fz
```

Common dump fields:
- `id`, `type` - Atom identity
- `x`, `y`, `z` - Positions (or `xu`, `yu`, `zu` for unwrapped)
- `vx`, `vy`, `vz` - Velocities
- `fx`, `fy`, `fz` - Forces
- `q` - Charge
- `c_peratom` - Custom compute values

### 4.3 Restart Files

Binary snapshots of complete simulation state for continuation:

```bash
restart 10000 restart.*.bin
```

**Note**: Restart files do NOT store fix/compute definitions—these must be re-specified in the continuation script.

### 4.4 Data Output (`write_data`)

Write current structure in LAMMPS data format:

```bash
write_data final_structure.data
```

---

## 5. Installation Methods & Build Constraints

### 5.1 Installation Options

| Method | Command | Notes |
|--------|---------|-------|
| **Homebrew (macOS)** | `brew install lammps` | Serial + basic MPI; limited packages |
| **Conda** | `conda install -c conda-forge lammps` | Pre-built with many packages |
| **Source** | `cmake` + `make` | Full control over packages |

### 5.2 Typical Homebrew Layout

```
/opt/homebrew/opt/lammps/
├── bin/
│   ├── lmp_serial      # Serial executable
│   └── lmp_mpi         # MPI-enabled executable (if available)
├── share/lammps/
│   ├── bench/          # Benchmark inputs
│   │   └── in.lj       # LJ fluid benchmark
│   ├── examples/       # Example scripts
│   └── potentials/     # Built-in potential files
└── lib/                # Libraries
```

**Sanity Check Path**: `/opt/homebrew/opt/lammps/share/lammps/bench/in.lj`  
This file can be used for engine discovery self-test.

### 5.3 Package Dependencies

Many features require specific packages to be compiled in:

| Feature | Package Required | Brew/Conda Default |
|---------|-----------------|-------------------|
| GPU acceleration | `GPU` or `KOKKOS` | ❌ Not included |
| ReaxFF | `REAXFF` | ⚠️ Sometimes |
| Long-range electrostatics | `KSPACE` | ✅ Usually |
| EAM potentials | `MANYBODY` | ✅ Usually |
| ML potentials (DeepMD) | `ML-PACE`, `ML-SNAP` | ❌ Rarely |

**Engine discovery must detect available packages** via `lmp -h packages` or similar.

---

## 6. Parallelization & Acceleration

### 6.1 MPI Parallelism

Standard LAMMPS parallelism via domain decomposition:

```bash
mpirun -np 4 lmp_mpi -in in.lammps
```

### 6.2 OpenMP Threading

Hybrid MPI+OpenMP:

```bash
export OMP_NUM_THREADS=4
mpirun -np 2 lmp_mpi -sf omp -in in.lammps
```

### 6.3 GPU Acceleration

Via GPU package or Kokkos:

```bash
# GPU package
lmp_gpu -sf gpu -pk gpu 1 -in in.lammps

# Kokkos (CUDA)
lmp_kokkos_cuda -k on g 1 -sf kk -in in.lammps
```

### 6.4 Kokkos Abstraction

Kokkos provides portable performance across backends:

| Backend | Build Flag | Use Case |
|---------|-----------|----------|
| `Serial` | Default | Single thread |
| `OpenMP` | `-DKokkos_ENABLE_OPENMP=ON` | CPU threading |
| `CUDA` | `-DKokkos_ENABLE_CUDA=ON` | NVIDIA GPUs |
| `HIP` | `-DKokkos_ENABLE_HIP=ON` | AMD GPUs |

**Note**: Kokkos support depends on build configuration. Pre-built packages often lack GPU backends.

---

## 7. Key Differences from QE/VASP

| Aspect | LAMMPS | QE/VASP |
|--------|--------|---------|
| **Physics** | Classical force fields | Quantum DFT |
| **Scaling** | Billions of atoms | Hundreds of atoms |
| **Input** | DSL script | Namelist/card format |
| **Potentials** | External files | Pseudopotentials |
| **Outputs** | dump/log/restart | xml/binary/text |
| **Time domain** | ns-µs trajectories | ps-scale MD |

---

## 8. QMatSuite Integration Implications

Based on this overview, LAMMPS integration requires:

1. **New engine family**: `lammps` alongside `qe`, `vasp`, `orca`, `pyscf`
2. **Potential asset management**: Similar to `species_map`/`pseudo_dir` but for classical potentials
3. **Units normalization**: Convert from LAMMPS units to canonical (Å, eV, fs)
4. **Trajectory parsing**: Handle dump/log/restart formats
5. **Template-based input generation**: DSL script generation with parameter injection
6. **Package discovery**: Detect available LAMMPS packages for capability reporting

See `integration_design.md` for detailed design.

