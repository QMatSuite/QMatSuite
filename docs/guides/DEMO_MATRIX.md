# Demo Matrix

Authoritative table of all demo project snapshots in the demo store.
Generated from `corpus_index.yaml` demo-eligible entries.

**Total demos: 57** across 15 engines (all engines now have 3+ demos).
**Ref packs: 27** demos have pre-computed reference analysis bundles (convergence/dos/bands).

## Demo Table

| demo_slug | engine | step_type_gen | required_engine | availability | asset_policy | has_ref_pack | ref_type |
|-----------|--------|---------------|-----------------|-------------|--------------|:------------:|----------|
| `abinit_si_bands` | ABINIT | bandspw | abinit | open_source | redistributable | yes | bands |
| `abinit_si_relax` | ABINIT | relax | abinit | open_source | redistributable | yes | convergence |
| `abinit_si_scf` | ABINIT | scf | abinit | open_source | redistributable | yes | convergence |
| `cp2k_h2o_energy` | CP2K | scf | cp2k | open_source | none | yes | convergence |
| `cp2k_h2o_geo_opt` | CP2K | relax | cp2k | open_source | none | yes | convergence |
| `cp2k_si_relax` | CP2K | relax | cp2k | open_source | none | yes | convergence |
| `gaussian_formaldehyde_tddft` | Gaussian | td | gaussian | requires_local_install | none | no | |
| `gaussian_water_hf` | Gaussian | scf | gaussian | requires_local_install | none | no | |
| `gaussian_water_opt` | Gaussian | relax | gaussian | requires_local_install | none | no | |
| `gpaw_al_scf` | GPAW | scf | gpaw | open_source | none | no | |
| `gpaw_si_bands` | GPAW | bandspw | gpaw | open_source | none | yes | bands |
| `gpaw_si_scf` | GPAW | scf | gpaw | open_source | none | no | |
| `lammps_lj_melt` | LAMMPS | md | lammps | open_source | none | no | |
| `lammps_lj_minimize` | LAMMPS | minimize | lammps | open_source | none | no | |
| `lammps_peptide_nvt` | LAMMPS | md | lammps | open_source | none | no | |
| `orca_formaldehyde_tddft` | ORCA | td | orca | requires_local_install | none | no | |
| `orca_methane_freq` | ORCA | freq | orca | requires_local_install | none | no | |
| `orca_water_sp` | ORCA | scf | orca | requires_local_install | none | no | |
| `psi4_ethanol_sp` | Psi4 | scf | psi4 | open_source | none | no | |
| `psi4_h2o_opt` | Psi4 | relax | psi4 | open_source | none | no | |
| `psi4_water_scf` | Psi4 | scf | psi4 | open_source | none | no | |
| `pyscf_h2o_dft` | PySCF | scf | pyscf | open_source | none | no | |
| `pyscf_n2_mp2` | PySCF | scf | pyscf | open_source | none | no | |
| `pyscf_water_scf` | PySCF | scf | pyscf | open_source | none | no | |
| `qe_al_dos` | QE | relax | qe | open_source | redistributable | yes | dos |
| `qe_fe_dos` | QE | scf | qe | open_source | redistributable | yes | dos |
| `qe_graphene_bands` | QE | relax | qe | open_source | redistributable | yes | bands |
| `qe_nmr_gipaw` | QE | scf | qe | open_source | redistributable | yes | convergence |
| `qe_si_bands_alt` | QE | scf | qe | open_source | redistributable | yes | bands |
| `qe_si_bulk_modulus` | QE | scf | qe | open_source | redistributable | yes | convergence |
| `qe_si_cpmd` | QE | scf | qe | open_source | redistributable | no | |
| `qe_si_dos_alt` | QE | scf | qe | open_source | redistributable | yes | dos |
| `qe_si_phonon` | QE | scf | qe | open_source | redistributable | yes | convergence |
| `qe_si_scf` | QE | scf | qe | open_source | redistributable | yes | convergence |
| `qe_si_vc_relax` | QE | relax | qe | open_source | redistributable | yes | convergence |
| `qmcpack_h2_vmc` | QMCPACK | vmc | qmcpack | open_source | none | no | |
| `qmcpack_he_vmc` | QMCPACK | vmc | qmcpack | open_source | none | no | |
| `qmcpack_lih_solid` | QMCPACK | vmc | qmcpack | open_source | none | no | |
| `si_bands_demo` | QE | scf | qe | open_source | redistributable | yes | bands |
| `si_dos_demo` | QE | scf | qe | open_source | redistributable | yes | dos |
| `siesta_si_bands` | Siesta | bandspw | siesta | open_source | none | yes | bands |
| `siesta_si_relax` | Siesta | relax | siesta | open_source | none | yes | convergence |
| `siesta_si_scf` | Siesta | scf | siesta | open_source | none | yes | convergence |
| `vasp_fe_magnetic` | VASP | scf | vasp | requires_local_install | proprietary | yes | convergence |
| `vasp_si_bands` | VASP | bandspw | vasp | requires_local_install | proprietary | yes | bands |
| `vasp_si_dos` | VASP | dos | vasp | requires_local_install | proprietary | yes | dos |
| `vasp_si_relax` | VASP | relax | vasp | requires_local_install | proprietary | yes | convergence |
| `vasp_si_scf` | VASP | scf | vasp | requires_local_install | proprietary | yes | convergence |
| `w90_copper` | Wannier90 | wannier | w90 | open_source | none | no | |
| `w90_diamond` | Wannier90 | wannier | w90 | open_source | none | no | |
| `w90_silicon` | Wannier90 | wannier | w90 | open_source | none | no | |
| `xtb_caffeine_grad` | xTB | relax | xtb | bundled | none | no | |
| `xtb_water_md` | xTB | md | xtb | bundled | none | no | |
| `xtb_water_opt` | xTB | relax | xtb | bundled | none | no | |
| `yambo_si_bse` | Yambo | bse | yambo | open_source | none | no | |
| `yambo_si_gw` | Yambo | gw | yambo | open_source | none | no | |
| `yambo_si_optics` | Yambo | optics | yambo | open_source | none | no | |

## Ref Pack Coverage

| Ref Type | Count | Engines |
|----------|:-----:|---------|
| convergence | 15 | VASP (3), QE (5), ABINIT (2), Siesta (2), CP2K (3) |
| bands | 7 | VASP (1), QE (3), ABINIT (1), Siesta (1), GPAW (1) |
| dos | 5 | VASP (1), QE (4) |
| **Total** | **27** | 7 engines |

## Coverage Summary

| Engine | Demo Count | Ref Packs | Availability | Notes |
|--------|:----------:|:---------:|--------------|-------|
| QE | 13 | 11 | open_source | Most mature; includes si_bands_demo, si_dos_demo (C3 protected) |
| VASP | 5 | 5 | requires_local_install | Proprietary POTCARs required |
| ABINIT | 3 | 3 | open_source | |
| CP2K | 3 | 3 | open_source | |
| Gaussian | 3 | 0 | requires_local_install | No convergence/dos/bands provider |
| GPAW | 3 | 1 | open_source | Python-script engine; bands only |
| LAMMPS | 3 | 0 | open_source | Trajectory only, no chart providers |
| ORCA | 3 | 0 | requires_local_install | No convergence/dos/bands provider |
| Psi4 | 3 | 0 | open_source | Python-script engine |
| PySCF | 3 | 0 | open_source | Python-script engine |
| QMCPACK | 3 | 0 | open_source | QMC-specific, no chart providers |
| Siesta | 3 | 3 | open_source | |
| Wannier90 | 3 | 0 | open_source | Field3D only |
| xTB | 3 | 0 | bundled | Ships with QMatSuite |
| Yambo | 3 | 0 | open_source | GW/BSE specific |

## Availability Legend

- **bundled**: Engine ships with QMatSuite (no separate install)
- **open_source**: Engine is open-source and freely available
- **requires_local_install**: Engine must be installed separately (may be commercial)

## Asset Policy Legend

- **redistributable**: All required assets (pseudopotentials, etc.) are vendored in-repo
- **proprietary**: Required assets cannot be redistributed; user must provide their own
- **none**: No external assets required (e.g., molecular codes, classical forcefields)
