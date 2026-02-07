# QMCPACK Curated Sample Index

**Engine**: QMCPACK
**Format Family**: F6 (XML)
**Samples Location**: `tests/inputformat/samples/qmcpack/`
**Total Samples**: 8
**Last Updated**: 2026-02-07

---

## Overview

This document catalogs the curated QMCPACK input samples used for parser/writer validation.
Each sample represents a distinct QMC calculation type with specific features that exercise
different aspects of the QMCPACK XML parser.

---

## Sample Inventory

| Case ID | QMC Method | Wavefunction | Boundary | Special Features | Atoms |
|---------|-----------|--------------|----------|------------------|-------|
| he_vmc_sto | VMC | STO determinant + Pade J2 | Open | Simplest case, no external assets | 1 |
| h2_ae_vmc | VMC | Gaussian LCAO + Bspline J1+J2 | Open | Multi-atom molecule, sposet_collection | 2 |
| lih_solid_vmc_pp | VMC+DMC | Einspline/HDF5 + Bspline J1+J2 | PBC | Pseudopotentials, 2 QMC blocks | 2 |
| he_opt_pade | Optimization+VMC | STO + Pade J2 | Open | Loop wrapper, linear method, cost functions | 1 |
| heg_vmc | VMC | Free-particle sposet + Bspline J2 | PBC | No ions (electron gas), rs parameter | 0 |
| he_dmc | VMC+DMC | STO + Pade J2 | Open | VMC→DMC chain, pbyp moves | 1 |
| be_sto_vmc | VMC | STO Bunge basis, sposet_collection MO | Open | Multi-orbital, no Jastrow | 1 |
| lih_qe_workflow | VMC | Einspline/HDF5 + Bspline J2 | PBC | QE→QMCPACK composite pipeline (§1.12 W1) | 2 |

---

## Diversity Rationale

### QMC Methods (4 distinct methods)
- **VMC only**: he_vmc_sto, h2_ae_vmc, heg_vmc, be_sto_vmc, lih_qe_workflow
- **VMC+DMC chain**: lih_solid_vmc_pp, he_dmc
- **Optimization (linear method)**: he_opt_pade
- **DMC projection**: lih_solid_vmc_pp, he_dmc (as second block)

### Wavefunction Types
- **STO basis (Slater)**: he_vmc_sto, he_opt_pade, he_dmc, be_sto_vmc
- **Gaussian LCAO**: h2_ae_vmc
- **Einspline/HDF5 (from DFT)**: lih_solid_vmc_pp, lih_qe_workflow
- **Free-particle (plane-wave)**: heg_vmc
- **sposet_collection MolecularOrbital**: h2_ae_vmc, be_sto_vmc

### Jastrow Factors
- **Pade Two-Body**: he_vmc_sto, he_opt_pade, he_dmc
- **Bspline Two-Body (J2)**: h2_ae_vmc, lih_solid_vmc_pp, heg_vmc, lih_qe_workflow
- **Bspline One-Body (J1)**: h2_ae_vmc, lih_solid_vmc_pp
- **No Jastrow**: be_sto_vmc

### Boundary Conditions
- **Open (molecule/atom)**: he_vmc_sto, h2_ae_vmc, he_opt_pade, he_dmc, be_sto_vmc
- **Periodic (PBC)**: lih_solid_vmc_pp, heg_vmc, lih_qe_workflow

### Pseudopotential vs All-Electron
- **All-electron**: he_vmc_sto, h2_ae_vmc, he_opt_pade, he_dmc, be_sto_vmc
- **Pseudopotential (XML)**: lih_solid_vmc_pp, lih_qe_workflow
- **No ions (jellium)**: heg_vmc

### System Diversity
- **Single atoms**: He (he_vmc_sto, he_opt_pade, he_dmc), Be (be_sto_vmc)
- **Molecules**: H2 (h2_ae_vmc)
- **Solids**: LiH rocksalt (lih_solid_vmc_pp, lih_qe_workflow)
- **Electron gas**: 14-electron HEG (heg_vmc)

### Cross-Engine Workflow (§1.12 W1)
- **QE→QMCPACK**: lih_qe_workflow (pw.x → pw2qmcpack.x → qmcpack)

### Driver Versions
- **batch**: he_vmc_sto, h2_ae_vmc, heg_vmc, he_dmc, be_sto_vmc, lih_qe_workflow
- **legacy**: he_opt_pade
- **Not set (default)**: lih_solid_vmc_pp (has batch set)

---

## Parser Coverage Matrix

| Feature | Tested By |
|---------|-----------|
| `<project>` id/series | All samples |
| `<parameter name="driver_version">` | All samples |
| `<simulationcell>` with lattice | lih_solid_vmc_pp, heg_vmc, lih_qe_workflow |
| `<parameter name="bconds">` PBC | lih_solid_vmc_pp, heg_vmc, lih_qe_workflow |
| `<parameter name="rs">` (electron gas) | heg_vmc |
| Ion `<particleset>` with groups | he_vmc_sto, h2_ae_vmc, lih_solid_vmc_pp, he_opt_pade, he_dmc, be_sto_vmc, lih_qe_workflow |
| `<attrib name="ionid">` stringArray | h2_ae_vmc, lih_solid_vmc_pp, be_sto_vmc, lih_qe_workflow |
| `condition="1"` (fractional coords) | lih_solid_vmc_pp, lih_qe_workflow |
| Cartesian coordinates (no condition) | he_vmc_sto, h2_ae_vmc, he_opt_pade, he_dmc, be_sto_vmc |
| No ion particleset (electron-only) | heg_vmc |
| Electron `<particleset>` u/d groups | All samples |
| `<wavefunction>` preserved XML | All samples |
| `<determinantset type="MO">` STO | he_vmc_sto, he_opt_pade, he_dmc |
| `<determinantset type="einspline">` | lih_solid_vmc_pp, lih_qe_workflow |
| `<sposet_collection type="MolecularOrbital">` | h2_ae_vmc, be_sto_vmc |
| `<sposet_collection type="free">` | heg_vmc |
| `<jastrow type="Two-Body" function="pade">` | he_vmc_sto, he_opt_pade, he_dmc |
| `<jastrow type="Two-Body" function="Bspline">` | h2_ae_vmc, lih_solid_vmc_pp, heg_vmc, lih_qe_workflow |
| `<jastrow type="One-Body">` | h2_ae_vmc, lih_solid_vmc_pp |
| `<hamiltonian>` coulomb pairpots | All samples |
| `<pairpot type="pseudo">` with hrefs | lih_solid_vmc_pp, lih_qe_workflow |
| `<estimator>` in hamiltonian | heg_vmc (gofr) |
| `<qmc method="vmc">` | All samples |
| `<qmc method="dmc">` | lih_solid_vmc_pp, he_dmc |
| `<qmc method="linear">` optimization | he_opt_pade |
| `<loop max="N">` wrapper | he_opt_pade |
| `<cost>` elements | he_opt_pade |
| `<estimator>` in qmc block | lih_solid_vmc_pp, lih_qe_workflow |
| Multiple QMC blocks | lih_solid_vmc_pp, he_dmc, he_opt_pade |
| Resource refs (HDF5 href) | lih_solid_vmc_pp, lih_qe_workflow |
| Resource refs (pseudo href) | lih_solid_vmc_pp, lih_qe_workflow |

---

## Validation Status

| Case | Parser | Writer | Roundtrip | Real Run |
|------|--------|--------|-----------|----------|
| he_vmc_sto | pass | pass | pass | pass (1.07s) |
| h2_ae_vmc | pass | pass | pass | pass (2.14s) |
| lih_solid_vmc_pp | pass | pass | pass | pass (1.82s) |
| he_opt_pade | pass | pass | pass | pass (0.92s) |
| heg_vmc | pass | pass | pass | pass (0.50s) |
| he_dmc | pass | pass | pass | n/a |
| be_sto_vmc | pass | pass | pass | n/a |
| lih_qe_workflow | pass | pass | pass | pass (1.80s, QE+QMCPACK) |

**Note**: Real run validation requires QMCPACK installation. Results from
`.tmp/engine_research/qmcpack/runs/`.

---

## Adding New Samples

When adding new curated samples:

1. Create a new directory under `tests/inputformat/samples/qmcpack/<case_name>/`
2. Add `qmc_input.xml` (the QMCPACK input file)
3. Add `case.yaml` with metadata:
   ```yaml
   case_id: <case_name>
   title: "<Descriptive title>"
   engine: qmcpack
   workflow_tags: [<tags>]
   species: [<elements>]
   description: "<One-line description>"
   ```
4. Update this CURATED_INDEX.md
5. Add parser/roundtrip tests in `tests/inputformat/test_qmcpack_parse.py`

---

## References

- QMCPACK Manual: https://qmcpack.readthedocs.io/en/develop/
- QMCPACK GitHub: https://github.com/QMCPACK/qmcpack
- Metadata catalog: `src/quantumvitas/drivers/qmcpack/data/qmcpack_tags.json`
