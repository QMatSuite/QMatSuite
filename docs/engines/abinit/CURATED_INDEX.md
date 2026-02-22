# ABINIT Curated Sample Index

**Engine**: ABINIT
**Format Family**: F1 (namelist-card, combined .abi format)
**Samples Location**: `tests/inputformat/samples/abinit/`
**Total Samples**: 10
**Last Updated**: 2026-02-06

---

## Overview

This document catalogs the curated ABINIT input samples used for parser/writer validation.
Each sample represents a distinct calculation type with specific features that exercise
different aspects of the ABINIT parser (star expansion, Fortran d-notation, multi-dataset,
structure variables, etc.).

---

## Sample Inventory

| Case ID | Calc Type | System | Special Features | Atoms |
|---------|-----------|--------|------------------|-------|
| si_scf | SCF | Si (diamond) | Basic ground state, 4x4x4 k-mesh | 2 |
| si_relax | Relax | Si (diamond) | BFGS ionic + isotropic cell (ionmov+optcell) | 2 |
| si_bands | Bands | Si (diamond) | Multi-dataset (2), high-symmetry k-path | 2 |
| si_dos | DOS | Si (diamond) | Multi-dataset (2), dense 8x8x8 NSCF grid | 2 |
| si_spin | Spin | Si (diamond) | Spin-polarized (nsppol 2), Gaussian smearing | 2 |
| al_scf | SCF | Al (FCC) | Metallic smearing (occopt 7), dense k-mesh | 1 |
| si_dfpt | DFPT | Si (diamond) | Multi-dataset (2), phonon response (rfphon) | 2 |
| si_vcrelax | VC-Relax | Si (diamond) | Full variable-cell (optcell 2), 6 strain components | 2 |
| fe_magnetic | Spin | Fe (BCC) | Ferromagnetic (spinat 4 muB), transition metal | 1 |
| si_paw | PAW | Si (diamond) | PAW (usepaw 1), double-grid (pawecutdg) | 2 |

---

## Diversity Rationale

### Calculation Types (7 distinct types)
- **Ground-state SCF**: si_scf, al_scf
- **Ionic relaxation**: si_relax
- **Variable-cell relaxation**: si_vcrelax
- **Band structure**: si_bands
- **Density of states**: si_dos
- **DFPT phonons**: si_dfpt
- **Spin-polarized**: si_spin, fe_magnetic

### Electronic Structure Coverage
- **Non-spin-polarized**: si_scf, si_relax, si_bands, si_dos, al_scf, si_dfpt, si_vcrelax, si_paw
- **Spin-polarized (nsppol=2)**: si_spin, fe_magnetic

### Chemical System Diversity
- **Semiconductor**: Si diamond (8 cases)
- **Metal**: Al FCC (al_scf)
- **Magnetic metal**: Fe BCC (fe_magnetic)

### Pseudopotential Types
- **Norm-conserving**: si_scf, si_relax, si_bands, si_dos, si_spin, al_scf, si_dfpt, si_vcrelax, fe_magnetic
- **PAW**: si_paw (usepaw 1, pawecutdg)

### ABINIT-Specific Feature Coverage
- **Star expansion (N*value)**: si_scf, all cases with `acell 3*X`
- **Fortran d-notation**: si_scf (toldfe 1.0d-8), si_relax (tolrff 1.0d-2)
- **Multi-dataset (ndtset)**: si_bands, si_dos, si_dfpt
- **Dataset variables (var1, var2)**: si_bands, si_dos, si_dfpt
- **Occupations (occopt)**: al_scf (occopt 7 = Gaussian), fe_magnetic (occopt 7)
- **Response functions (optdriver)**: si_dfpt (rfphon, nqpt, qpt)
- **Relaxation (ionmov)**: si_relax (ionmov 2), si_vcrelax (ionmov 2, optcell 2)
- **Spin (nsppol, spinat)**: si_spin, fe_magnetic

---

## Parser Coverage Matrix

| Feature | Tested By |
|---------|-----------|
| Basic key-value parsing | All samples |
| Star expansion (3*10.26) | si_scf, si_relax, al_scf, fe_magnetic, si_paw |
| Fortran d-notation (1.0d-8) | si_scf, si_relax, si_dfpt, si_vcrelax |
| Comment stripping (# and !) | All samples |
| `acell` / lattice vectors | All samples |
| `rprim` (3x3 matrix) | All samples |
| `xred` (fractional coordinates) | All samples |
| `znucl` / `typat` / `natom` / `ntypat` | All samples |
| `ngkpt` (k-point grid) | si_scf, si_relax, si_spin, al_scf, si_vcrelax, fe_magnetic, si_paw |
| `kptopt` (k-point generation options) | si_bands |
| Multi-dataset (ndtset, var1, var2) | si_bands, si_dos, si_dfpt |
| Response function variables (rfphon, nqpt) | si_dfpt |
| Relaxation variables (ionmov, optcell) | si_relax, si_vcrelax |
| Smearing (occopt, tsmear) | al_scf, fe_magnetic |
| Spin variables (nsppol, spinat) | si_spin, fe_magnetic |
| PAW variables (usepaw, pawecutdg) | si_paw |
| Tolerance variables (toldfe, tolrff, tolvrs) | All samples |

---

## Validation Status

| Case | Parser | Writer | Roundtrip | Real Run |
|------|--------|--------|-----------|----------|
| si_scf | OK | OK | OK | OK (golden ref) |
| si_relax | OK | OK | OK | OK (golden ref) |
| si_bands | OK | OK | OK | OK (golden ref) |
| si_dos | OK | OK | OK | -- |
| si_spin | OK | OK | OK | -- |
| al_scf | OK | OK | OK | -- |
| si_dfpt | OK | OK | OK | -- |
| si_vcrelax | OK | OK | OK | -- |
| fe_magnetic | OK | OK | OK | -- |
| si_paw | OK | OK | OK | -- |

**Note**: Real run validation available for si_scf, si_relax, si_bands via golden refs
in `docs/engines/abinit/golden_refs/`. Other cases are parser/writer tested only.

---

## Adding New Samples

When adding new curated samples:

1. Create a new directory under `tests/inputformat/samples/abinit/<case_name>/`
2. Add `<case_name>.abi` (the ABINIT input file)
3. Add `case.yaml` with metadata:
   ```yaml
   case_id: <case_name>
   title: "<Descriptive title>"
   engine: abinit
   workflow_tags: [<tags>]
   species: [<elements>]
   description: "<One-line description>"
   ```
4. Update this CURATED_INDEX.md
5. Ensure the sample parses correctly with existing tests

---

## References

- ABINIT documentation: https://docs.abinit.org/
- ABINIT variables reference: https://docs.abinit.org/variables/
- Metadata catalog: `src/qmatsuite/drivers/abinit/data/abinit_tags.json`
- Golden refs: `docs/engines/abinit/golden_refs/`
