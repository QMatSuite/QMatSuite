# LAMMPS Explore Track Summary

Explore Stages 1-3 completed 2026-02-05. All artifacts under `.tmp/engine_research/lammps/`.

## Stage 1: Docs + Raw Corpus
- 85 markdown pages crawled from docs.lammps.org (`raw_web/`)
- 843 input files in 90 bundled example directories (`extracted/bundled_examples/`)
- 257 potential files (`extracted/bundled_potentials/`)
- 202 benchmark files (`extracted/bundled_benchmarks/`)
- LAMMPS v22 Jul 2025 Update 3 via Homebrew

## Stage 2: Metadata Seed
- `metadata/lammps_commands.json` — 79 commands, 121 sub-styles (17 pair, 75 fix, 29 compute), 29 file reference entries
- `metadata/lammps_input_syntax.md` — syntax reference (command order, variable substitution, units table, atom styles, data file format)

## Stage 3: Normalized Case Library (40 cases)
Each under `normalized/<case_id>/` with `in.lammps`, `case.yaml`, `source.txt`.

| Case | Units | Pair Style | Workflow |
|------|-------|-----------|----------|
| melt_lj_nve | lj | lj/cut | md |
| crack_2d_lj | lj | lj/cut | fracture |
| peptide_nvt_charmm | real | lj/charmm/coul/long | md |
| meam_sic_nve | metal | meam | md |
| elastic_constants_sw | metal | sw | elastic |
| minimize_2d_lj | lj | lj/cut | minimize |
| reaxff_rdx | real | reaxff | md |
| flow_couette_2d | lj | lj/cut | flow |
| micelle_2d | lj | soft/lj/cut | md |
| hugoniostat_shock | lj | lj/cubic | shock |
| neb_si_vacancy | metal | sw | neb |
| dreiding_methanol | real | hybrid/overlay | md |
| eam_alloy_hyper | metal | eam/alloy | hyperdynamics |
| airebo_carbon | metal | airebo | md |
| colloid_2d | lj | colloid | md |
| kappa_heatflux_gk | lj | lj/cut | thermal_conductivity |
| kappa_muller_plathe | lj | lj/cut | thermal_conductivity |
| diffusion_msd_2d | lj | lj/cut | diffusion |
| viscosity_nemd | lj | lj/cut | viscosity |
| shear_metal_eam | metal | eam | deformation |
| indent_2d_lj | lj | lj/cut | indentation |
| granular_pour_drum | lj | granular | granular |
| rigid_bodies | lj | lj/cut | md |
| peri_crack | si | peri/lps | fracture |
| coreshell_nacl | metal | born/coul/long/cs | md |
| comb_copper | metal | comb | md |
| tersoff_sic | metal | tersoff | regression |
| vashishta_sio2 | metal | vashishta | md |
| streitz_al | metal | hybrid/overlay | md |
| snap_ta | metal | snap | md |
| eim_nacl | metal | eim | md |
| msst_shock | lj | lj/cut | shock |
| prd_vacancy | metal | eam | accelerated_dynamics |
| tad_vacancy | metal | eam | accelerated_dynamics |
| mc_gcmc_lj | lj | lj/cut | monte_carlo |
| spin_cobalt | metal | hybrid/overlay | spin_dynamics |
| balance_dynamic | lj | lj/cut | utility |
| ttm_electron_phonon | metal | eam/fs | multiphysics |
| rerun_trajectory | lj | lj/cut | post_processing |
| triclinic_box | lj | lj/cut | geometry_utility |

## Explore Stage 4: Validation Runs (7 passed)
All under `runs/<case_id>/` with `log.lammps`.
melt_lj_nve (0.4s), minimize_2d_lj (0.2s), crack_2d_lj (2.6s), flow_couette_2d (0.1s), indent_2d_lj (2.4s), tersoff_sic (0.5s), shear_metal_eam (3.3s).

## Key Parser/Writer Design Observations
1. Command-stream format (F5) — imperative, order-matters
2. Two-file I/O model: in.lammps (commands) + data file (structure)
3. Variable substitution (`${var}`, `$x`, `v_name`) is pervasive
4. Include files and multi-phase simulations are common
5. Data file format varies by atom_style
6. Existing inputspec.py already has correct 2-file model with syntax_family="command-stream"
