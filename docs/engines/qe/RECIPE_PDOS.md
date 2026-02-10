# QE PDOS Recipe

## Overview

Compute orbital-projected density of states (PDOS) for Silicon using Quantum ESPRESSO.
PDOS shows the contribution of each atomic orbital to the total DOS.

## 2-Step Workflow

### Step 1: SCF (self-consistent field)

Standard SCF calculation with converged charge density.

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
  8 8 8  0 0 0
```

Run: `pw.x < si_scf.in > si_scf.out`

### Step 2: projwfc.x (orbital projections)

```
&PROJWFC
    prefix = 'si'
    outdir = './tmp'
    filpdos = 'si'
    Emin = -10.0
    Emax = 20.0
    DeltaE = 0.01
/
```

Run: `projwfc.x < si_projwfc.in > si_projwfc.out`

## Expected Output Files

| File | Description |
|------|-------------|
| `si.pdos_atm#1(Si)_wfc#1(s)` | Atom 1, s-orbital PDOS |
| `si.pdos_atm#1(Si)_wfc#2(p)` | Atom 1, p-orbital PDOS |
| `si.pdos_atm#2(Si)_wfc#1(s)` | Atom 2, s-orbital PDOS |
| `si.pdos_atm#2(Si)_wfc#2(p)` | Atom 2, p-orbital PDOS |
| `si.pdos_tot` | Total projected DOS |

## PDOS File Format

Each `*.pdos_atm*` file is plain text:
```
# E (eV)  ldos(E)  pdos(E)
-10.000   0.0000   0.0000
-9.990    0.0000   0.0000
...
```

The QE DOS parser (`drivers/qe/parsers/dos.py`) already parses these files
into `DOS.pdos` (shape: n_atoms x nedos x n_orbitals).
