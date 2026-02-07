# Siesta Curated Input Index

Engine: `siesta`
Format family: FDF (flat-keyval + blocks)
Curated sample root: `tests/inputformat/samples/siesta/`
Updated: 2026-02-07

## Curated Cases

| Case | Capability | Inputs committed | Real-run evidence slug | Primary citation |
|---|---|---|---|---|
| `h2o_scf` | Molecular SCF single-point | `h2o.fdf`, `case.yaml` | `curated_h2o_scf_20260207` | `.tmp/engine_research/siesta/extracted/siesta_repo/Examples/H2O/h2o.fdf:1` |
| `si_scf` | Periodic bulk SCF | `si_scf.fdf`, `case.yaml` | `curated_si_scf_20260207` | `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/01.PseudoPotentials/base_si2.fdf:1` |
| `si_relax` | Ionic + cell relaxation (CG, variable cell) | `si_relax.fdf`, `case.yaml` | `curated_si_relax_20260207` | `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/08.GeometryOptimization/cg_vc.fdf:4` |
| `si_bands` | Band-structure path workflow | `si_bands.fdf`, `case.yaml` | `curated_si_bands_20260207` | `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/05.Bands/script.sh:12` |
| `si_dos` | DOS/PDOS workflow | `si_dos.fdf`, `case.yaml` | `curated_si_dos_20260207` | `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/06.DensityOfStates/pdos_kp.fdf:7` |
| `si_spin` | Spin-polarized SCF | `si_spin.fdf`, `case.yaml` | `curated_si_spin_20260207` | `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/02.SpinPolarization/fe_spin.fdf:4` |
| `si_md` | Short Verlet molecular dynamics | `si_md.fdf`, `case.yaml` | `curated_si_md_20260207` | `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/09.MolecularDynamics/verlet.fdf:6` |
| `si_vcrelax` | Fast variable-cell relaxation regime | `si_vcrelax.fdf`, `case.yaml` | `curated_si_vcrelax_20260207` | `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/08.GeometryOptimization/cg_vc.fdf:5` |

## Diversity Rationale

- Workflow diversity: SCF, relax/vc-relax, bands, DOS/PDOS, spin, MD.
- System diversity: molecular (H2O) and periodic crystalline Si.
- Numerical-regime diversity: SZ and DZP basis, static SCF and multi-step ionic dynamics.

## Evidence Policy

- Only minimal input files are committed under `tests/inputformat/samples/siesta/`.
- Runtime outputs, manifests, and comparison notes remain in `.tmp/engine_research/siesta/real_run/`.
