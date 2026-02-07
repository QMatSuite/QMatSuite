# CP2K Curated Sample Index

**Engine**: CP2K
**Format Family**: F3 (nested-section)
**Samples Location**: `tests/inputformat/samples/cp2k/`
**Total Samples**: 10
**Last Updated**: 2026-02-07

---

## Overview

Ten curated CP2K input files covering the primary DFT workflow types: single-point energy, geometry optimization, cell optimization, band structure, molecular dynamics, TDDFT excited states, and dispersion-corrected calculations. Both molecular (isolated) and periodic (solid) systems are represented.

---

## Sample Inventory

| Case ID | Calc Type | System | Special Features | Atoms | Real Run |
|---------|-----------|--------|------------------|-------|----------|
| h2o_energy | SCF energy | H2O molecule | Basic PBE/DZVP | 3 | Yes |
| h2o_geo_opt | GEO_OPT | H2O molecule | CG optimizer, MOTION section | 3 | Yes |
| h2o_md | NVT MD | H2O molecule | Nose-Hoover thermostat, nested THERMOSTAT/NOSE | 3 | No |
| si_scf | SCF energy | Si diamond | k-points (MP 4x4x4), MGRID, QS, SCF/MIXING | 2 | No |
| si_relax | GEO_OPT | Si diamond | BFGS, force thresholds | 2 | No |
| si_cell_opt | CELL_OPT | Si diamond | Stress tensor, KEEP_SYMMETRY | 2 | No |
| si_bands | Band structure | Si diamond | Smearing, ADDED_MOS, DIAGONALIZATION, PRINT/BAND_STRUCTURE | 2 | No |
| benzene_energy | SCF energy | C6H6 | BLYP+D3 dispersion, MT Poisson solver, non-periodic | 12 | No |
| co2_energy | SCF energy | CO2 | OT minimizer, DIIS preconditioner, high-cutoff MGRID | 3 | No |
| h2o_tddft | TDDFT | H2O molecule | TDDFPT (3 excited states) | 3 | No |

---

## Diversity Rationale

### Calculation Types (7 distinct types)
- **Single-point SCF**: h2o_energy, si_scf, benzene_energy, co2_energy
- **Geometry optimization**: h2o_geo_opt, si_relax
- **Cell optimization**: si_cell_opt
- **Molecular dynamics**: h2o_md
- **Band structure**: si_bands
- **TDDFT**: h2o_tddft

### System Diversity
- **Isolated molecules**: h2o_energy, h2o_geo_opt, h2o_md, benzene_energy, co2_energy, h2o_tddft
- **Periodic solids**: si_scf, si_relax, si_cell_opt, si_bands

### Coordinate Systems
- **Cartesian (default)**: h2o_energy, h2o_geo_opt, h2o_md, benzene_energy, co2_energy, h2o_tddft
- **Fractional (SCALED .TRUE.)**: si_scf, si_relax, si_cell_opt, si_bands

### Section Coverage
- **GLOBAL**: All samples
- **FORCE_EVAL/DFT**: All samples
- **FORCE_EVAL/DFT/SCF**: All (various sub-configs)
- **FORCE_EVAL/DFT/SCF/OT**: co2_energy
- **FORCE_EVAL/DFT/SCF/MIXING**: si_scf
- **FORCE_EVAL/DFT/SCF/SMEAR**: si_bands
- **FORCE_EVAL/DFT/SCF/DIAGONALIZATION**: si_bands, h2o_tddft
- **FORCE_EVAL/DFT/XC**: All
- **FORCE_EVAL/DFT/XC/VDW_POTENTIAL**: benzene_energy
- **FORCE_EVAL/DFT/MGRID**: si_scf, si_relax, si_cell_opt, si_bands, co2_energy
- **FORCE_EVAL/DFT/QS**: si_scf
- **FORCE_EVAL/DFT/KPOINTS**: si_scf, si_bands
- **FORCE_EVAL/DFT/POISSON**: benzene_energy
- **FORCE_EVAL/DFT/TDDFPT**: h2o_tddft
- **FORCE_EVAL/DFT/PRINT**: si_bands
- **FORCE_EVAL/SUBSYS/CELL**: All (ABC vs explicit A/B/C vectors)
- **FORCE_EVAL/SUBSYS/COORD**: All (SCALED and Cartesian)
- **FORCE_EVAL/SUBSYS/KIND**: All (element-specific basis/potential)
- **MOTION/GEO_OPT**: h2o_geo_opt, si_relax
- **MOTION/CELL_OPT**: si_cell_opt
- **MOTION/MD**: h2o_md
- **MOTION/MD/THERMOSTAT**: h2o_md

### XC Functional Coverage
- **PBE**: h2o_energy, h2o_geo_opt, h2o_md, si_scf, si_relax, si_cell_opt, si_bands, co2_energy, h2o_tddft
- **BLYP+D3**: benzene_energy

---

## Parser Coverage Matrix

| Feature | Tested By |
|---------|-----------|
| Basic `&SECTION ... &END` nesting | All samples |
| Default keyword (`&XC_FUNCTIONAL PBE`) | All samples |
| Boolean values (`.TRUE.`/`.FALSE.`) | si_scf (SCALED), si_cell_opt (KEEP_SYMMETRY) |
| Integer values | All (MAX_SCF, NSTATES, etc.) |
| Float values | co2_energy (EPS_SCF), h2o_md (TIMESTEP) |
| Multi-value lines (ABC, A/B/C vectors) | All (CELL section) |
| Deeply nested sections (4+ levels) | h2o_md (THERMOSTAT/NOSE), si_bands (PRINT/BAND_STRUCTURE) |
| Repeated sections (multiple &KIND) | h2o_energy, benzene_energy, co2_energy |
| Cartesian coordinates | Molecular samples |
| Fractional coordinates (SCALED) | Si samples |
| MOTION section | h2o_geo_opt, h2o_md, si_relax, si_cell_opt |
| SCF sub-methods (OT, DIAG, MIXING) | co2_energy, si_bands, si_scf |

---

## Validation Status

| Case | Parser | Writer | Roundtrip | Real Run |
|------|--------|--------|-----------|----------|
| h2o_energy | Tested | Tested | Tested | Validated (CP2K 2026.1) |
| h2o_geo_opt | Tested | Tested | Tested | Validated (CP2K 2026.1) |
| h2o_md | Tested | Tested | Tested | Not run |
| si_scf | Tested | Tested | Tested | Not run |
| si_relax | Tested | Tested | Tested | Not run |
| si_cell_opt | Tested | Tested | Tested | Not run |
| si_bands | Tested | Tested | Tested | Not run |
| benzene_energy | Tested | Tested | Tested | Not run |
| co2_energy | Tested | Tested | Tested | Not run |
| h2o_tddft | Tested | Tested | Tested | Not run |

---

## Real Run Evidence

Evidence from real CP2K 2026.1 executions is stored in `.tmp/engine_research/cp2k/real_run/`:

| Slug | Energy (Ha) | SCF Steps | Status |
|------|-------------|-----------|--------|
| h2o_energy_smoke | -17.21966280 | 10 | Success |
| h2o_geo_opt_smoke | -17.22009447 | 5 opt steps | Success (hit MAX_ITER) |
| ch4_energy_smoke | -8.07448121 | 9 | Success |

---

## Adding New Samples

1. Create directory under `tests/inputformat/samples/cp2k/<case_name>/`
2. Add `input.inp` (the CP2K input file)
3. Add `case.yaml` with metadata:
   ```yaml
   case_id: <case_name>
   title: "<Descriptive title>"
   engine: cp2k
   workflow_tags: [<tags>]
   species: [<elements>]
   description: "<Description>"
   ```
4. Update this CURATED_INDEX.md
5. Ensure the sample parses correctly with existing tests
