# QE Fatbands Recipe

## Overview

Compute k-resolved orbital projections (fatbands) for Silicon using Quantum ESPRESSO.
Fatbands are band structure plots where the line width encodes the orbital character.

## 3-Step Workflow

### Step 1: SCF (self-consistent field)

```
&CONTROL
    calculation = 'scf'
    prefix = 'si'
    outdir = './tmp'
    pseudo_dir = '<PSEUDO_DIR>'
/
&SYSTEM
    ibrav = 2
    celldm(1) = 10.26
    nat = 2, ntyp = 1
    ecutwfc = 30.0
    nbnd = 8
/
&ELECTRONS
    conv_thr = 1.0d-8
/
ATOMIC_SPECIES
  Si  28.0855  Si_r.upf
ATOMIC_POSITIONS (alat)
  Si  0.00  0.00  0.00
  Si  0.25  0.25  0.25
K_POINTS (automatic)
  4 4 4  0 0 0
```

Run: `pw.x < si_scf.in > si_scf.out`

### Step 2: NSCF bands calculation

Same as SCF but with `calculation = 'bands'` and explicit k-path:

```
&CONTROL
    calculation = 'bands'
    prefix = 'si'
    outdir = './tmp'
    pseudo_dir = '<PSEUDO_DIR>'
/
&SYSTEM
    ibrav = 2
    celldm(1) = 10.26
    nat = 2, ntyp = 1
    ecutwfc = 30.0
    nbnd = 8
/
&ELECTRONS
    conv_thr = 1.0d-8
/
ATOMIC_SPECIES
  Si  28.0855  Si_r.upf
ATOMIC_POSITIONS (alat)
  Si  0.00  0.00  0.00
  Si  0.25  0.25  0.25
K_POINTS {crystal_b}
5
  0.500  0.500  0.500  10  ! L
  0.000  0.000  0.000  10  ! G
  0.500  0.000  0.500  10  ! X
  0.500  0.250  0.750  10  ! W
  0.375  0.375  0.750   1  ! K
```

Run: `pw.x < si_nscf_bands.in > si_nscf_bands.out`

### Step 3: projwfc.x (orbital projections)

```
&PROJWFC
    prefix = 'si'
    outdir = './tmp'
    filproj = 'si_bands'
/
```

Run: `projwfc.x < si_projwfc.in > si_projwfc.out`

## Expected Output Files

| File | Description |
|------|-------------|
| `si_bands.projwfc_up` | Per-k-point, per-band projection weights (text) |
| `si.pdos_atm#1(Si)_wfc#1(s)` | Atom 1, s-orbital PDOS |
| `si.pdos_atm#1(Si)_wfc#2(p)` | Atom 1, p-orbital PDOS |
| `si.pdos_atm#2(Si)_wfc#1(s)` | Atom 2, s-orbital PDOS |
| `si.pdos_atm#2(Si)_wfc#2(p)` | Atom 2, p-orbital PDOS |
| `si.pdos_tot` | Total projected DOS |

## projwfc_up File Format

The `filproj` output (`si_bands.projwfc_up`) contains:

1. **Global header** (9 lines): grid, cell parameters, species, atomic positions
2. **Line 8**: `n_atomwfc  n_kpoints  n_bands` (e.g., `8  41  8`)
3. **Per atomic wfc block** (repeated `n_atomwfc` times):
   - Header: `wfc_idx  atom_idx  element  nl_label  n  l  m`
   - Data: `k_idx  band_idx  |<psi_nk|phi_i>|^2` (repeated `n_kpoints * n_bands` times)

Example header for Si:
```
    1    1 Si   3S     1    0    1     (atom 1, s, m=1)
    2    1 Si   3P     2    1    1     (atom 1, p, m=1)
    3    1 Si   3P     2    1    2     (atom 1, p, m=2)
    4    1 Si   3P     2    1    3     (atom 1, p, m=3)
    5    2 Si   3S     1    0    1     (atom 2, s, m=1)
    6    2 Si   3P     2    1    1     (atom 2, p, m=1)
    7    2 Si   3P     2    1    2     (atom 2, p, m=2)
    8    2 Si   3P     2    1    3     (atom 2, p, m=3)
```

## QMatSuite Parser

The QE bands parser (`drivers/qe/parsers/bands.py`) automatically detects `*.projwfc_up` files
and populates `BandStructure.projections` (shape: n_kpoints x n_bands x n_atoms x n_orbitals).
Projections are grouped by (atom, l) with m-components summed.
