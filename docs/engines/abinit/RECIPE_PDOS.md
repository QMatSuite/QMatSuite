# ABINIT PDOS Recipe

## Overview

Compute l-projected density of states (PDOS) for Silicon using ABINIT.
Uses `prtdos 3` to generate per-atom, l-resolved DOS files.

## Single-Run Workflow (Two Datasets)

### Input File

```
# Silicon PDOS calculation (two-dataset)
ndtset 2

# Dataset 1: SCF with moderate k-mesh
kptopt1 1
ngkpt1 4 4 4
nshiftk1 1
shiftk1 0.0 0.0 0.0
tolvrs1 1.0d-10
prtden1 1

# Dataset 2: NSCF with dense k-mesh for PDOS
iscf2 -2
getden2 1
kptopt2 1
ngkpt2 8 8 8
nshiftk2 1
shiftk2 0.0 0.0 0.0
tolwfr2 1.0d-12
prtdos2 3          # l-projected per-atom DOS
natsph2 2          # number of atoms to project onto
iatsph2 1 2        # atom indices
ratsph2 2*2.0      # projection sphere radii (Bohr)

# Common settings
ecut 10.0
nband 8
occopt 3
tsmear 0.01
nstep 30
diemac 12.0

# Structure: Si diamond
acell 3*10.26311
rprim
  0.0 0.5 0.5
  0.5 0.0 0.5
  0.5 0.5 0.0
ntypat 1
znucl 14
natom 2
typat 1 1
xred
  0.0 0.0 0.0
  0.25 0.25 0.25

pp_dirpath "<PSEUDO_DIR>"
pseudos "14si.pspnc"
```

Run: `abinit si_pdos.abi > si_pdos.log`

## Key Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `prtdos` | 3 | l-projected per-atom DOS (tetrahedron method) |
| `natsph` | 2 | Number of atoms for projection |
| `iatsph` | 1 2 | Atom indices to project onto |
| `ratsph` | 2*2.0 | Projection sphere radii in Bohr |

## Expected Output Files

| File | Description |
|------|-------------|
| `*_DOS_TOTAL` | Total DOS (sum of all projections) |
| `*_DOS_AT0001` | Atom 1 l-projected DOS |
| `*_DOS_AT0002` | Atom 2 l-projected DOS |
| `*_FATBANDS.nc` | NetCDF fatbands file (not parsed) |

## _DOS_AT File Format

```
# energy(Ha)  l=0      l=1      l=2      l=3      l=4    (integral=>)  l=0     l=1     l=2     l=3     l=4
   -0.30000    0.0000    0.0000    0.0000    0.0000    0.0000               0.00     0.00     0.00     0.00     0.00
```

- Column 1: energy in Hartree
- Columns 2-6: DOS per l-channel (l=0 through l=4) in electrons/Hartree
- Columns 7-11: integrated DOS per l-channel

## QMatSuite Parser

The ABINIT DOS parser (`drivers/abinit/parsers/dos.py`) automatically detects `*_DOS_AT*` files
and populates `DOS.pdos` (shape: n_atoms x nedos x n_orbitals).
Energies are converted from Hartree to eV, DOS from electrons/Hartree to electrons/eV.
When both `_DOS` and `_DOS_TOTAL` are present alongside `_DOS_AT` files,
the parser prefers `_DOS` for backward compatibility and validates grid consistency.
