# QMCPACK Phase B1 — Sources

## Primary Sources (Bundled with QMCPACK 4.1.0)

| Source | Path in Source Tree | Extracted To | Date |
|--------|-------------------|-------------|------|
| Labs/tutorials | `labs/` (5 labs) | `extracted/labs/` | 2026-02-06 |
| Molecule examples | `examples/molecules/` (He, H2O) | `extracted/examples/` | 2026-02-06 |
| Solid examples | `examples/solids/` (LiH, RMG-diamond) | `extracted/examples/` | 2026-02-06 |
| Molecule tests | `tests/molecules/` (25 systems) | `extracted/tests_molecules/` | 2026-02-06 |
| Solid tests | `tests/solids/` (19 systems) | `extracted/tests_solids/` | 2026-02-06 |
| Converter tests | `tests/converter/` (22 systems) | `extracted/tests_converter/` | 2026-02-06 |
| XSD schema | `schema/` (10 files) | `extracted/schema/` | 2026-02-06 |
| Pseudopotentials | `tests/pseudopotentials_for_tests/` | `extracted/pseudopotentials_for_tests/` | 2026-02-06 |

**Corpus size**: 1,438 XML files total

## Online Documentation

| Source | URL | Crawled | Notes |
|--------|-----|---------|-------|
| Input overview | https://qmcpack.readthedocs.io/en/develop/input_overview.html | 2026-02-06 | XML structure, project, random |
| Running | https://qmcpack.readthedocs.io/en/develop/running.html | 2026-02-06 | CLI options, MPI, OpenMP |
| Hamiltonians | https://qmcpack.readthedocs.io/en/develop/hamiltonianobservable.html | 2026-02-06 | pairpot, estimators, force |
| Methods | https://qmcpack.readthedocs.io/en/develop/methods.html | 2026-02-06 | VMC, DMC, optimization params |
| Wavefunctions | https://qmcpack.readthedocs.io/en/develop/wavefunctions.html | 2026-02-06 | Jastrow, determinants, sposets |
| Examples | https://qmcpack.readthedocs.io/en/develop/examples.html | 2026-02-06 | Tutorial walkthroughs |
| Output overview | https://qmcpack.readthedocs.io/en/develop/output_overview.html | 2026-02-06 | scalar.dat, dmc.dat, HDF5 |
| AFQMC | https://qmcpack.readthedocs.io/en/develop/afqmc.html | 2026-02-06 | AFQMC input structure |
| Introduction | https://qmcpack.readthedocs.io/en/develop/introduction.html | 2026-02-06 | Overview, capabilities |
| Units | https://qmcpack.readthedocs.io/en/develop/units.html | 2026-02-06 | Hartree atomic units |
| Pseudopotentials | https://qmcpack.readthedocs.io/en/develop/pseudopotentials.html | 2026-02-06 | PP formats, conversion |
| Converting | https://qmcpack.readthedocs.io/en/develop/converting.html | 2026-02-06 | pw2qmcpack, convert4qmc |
| Lab QMC basics | https://qmcpack.readthedocs.io/en/develop/lab_qmc_basics.html | 2026-02-06 | O atom/dimer tutorial |
| Lab advanced molecules | https://qmcpack.readthedocs.io/en/develop/lab_advanced_molecules.html | 2026-02-06 | Multideterminant, CI |
| Lab condensed matter | https://qmcpack.readthedocs.io/en/develop/lab_condensed_matter.html | 2026-02-06 | Periodic systems |
| GitHub README | https://github.com/QMCPACK/qmcpack | 2026-02-06 | Build instructions, overview |

## Community & Academic Sources

| Source | URL | Crawled | Notes |
|--------|-----|---------|-------|
| Workshop 2019 | https://github.com/QMCPACK/qmcpack_workshop_2019 | 2026-02-06 | Tutorials, AFQMC, optimization |
| pw2qmcpack repo | https://github.com/QMCPACK/pw2qmcpack | 2026-02-06 | Converter tool |
| Nexus examples | https://nexus-workflows.readthedocs.io/en/latest/examples.html | 2026-02-06 | Workflow automation |
| BFD PP database | http://www.burkatzki.com/pseudos/index.2.html | 2026-02-06 | Energy-consistent PPs for QMC |
| PP library | https://pseudopotentiallibrary.org/ | 2026-02-06 | Community PP collection |

## Metadata Artifacts

| Artifact | Path | Entries | Date |
|----------|------|---------|------|
| XML elements catalog | `metadata/qmcpack_xml_elements.json` | 175 | 2026-02-06 |
| QMC parameters catalog | `metadata/qmcpack_qmc_parameters.json` | ~60 params | 2026-02-06 |
| Estimators catalog | `metadata/qmcpack_estimators.json` | ~15 types | 2026-02-06 |

## Normalized Cases

13 cases under `.tmp/engine_research/qmcpack/normalized/`:
- Self-contained: he_vmc_sto, he_opt_pade, he_dmc, he_bspline_jastrow, be_sto_vmc, h2_ae_vmc, heg_vmc
- PP-dependent: h2o_vmc_pp, lih_pp_vmc
- HDF5-dependent: o2_opt_bspline, o2_dmc_bspline, lih_solid_vmc_pp, diamond_vmc_pp

## Validation Runs

5 fast cases executed with QMCPACK 4.1.0:
- he_vmc_sto (VMC, 1.1s, -2.773 Ha)
- he_dmc (VMC+DMC, 4.9s, -2.870 Ha)
- he_opt_pade (opt+VMC, 6.9s, -2.897 Ha)
- be_sto_vmc (VMC, 7.8s, -14.626 Ha)
- h2_ae_vmc (VMC, 1.7s, -1.177 Ha)

## Tools

| Tool | Path | Version |
|------|------|---------|
| qmcpack | `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack` | 4.1.0 |
| convert4qmc | `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/convert4qmc` | 4.1.0 |
| convertpw4qmc | `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/convertpw4qmc` | 4.1.0 |
| ppconvert | `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/ppconvert` | 4.1.0 |
| qmcfinitesize | `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcfinitesize` | 4.1.0 |
| pw2qmcpack.x | `.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw2qmcpack.x` | QE 7.5 |
| pw.x | `.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw.x` | QE 7.5 |

## Academic References

- J. Kim et al., J. Phys. Cond. Mat. 30 195901 (2018) — Primary QMCPACK citation
- P. Kent et al., J. Chem. Phys. 152 174105 (2020) — Methods paper
- Nexus: Computer Physics Communications (2015) — Workflow system
