# ORCA Curated Sample Index

**Engine**: ORCA
**Format Family**: F4 (keyword-block)
**Samples Location**: `tests/inputformat/samples/orca/`
**Total Samples**: 8
**Last Updated**: 2026-02-06

---

## Overview

This document catalogs the curated ORCA input samples used for parser/writer validation.
Each sample represents a distinct calculation type with specific features that exercise
different aspects of the ORCA parser.

---

## Sample Inventory

| Case ID | Calc Type | Method | Special Features | Atoms |
|---------|-----------|--------|------------------|-------|
| water_sp | SCF | B3LYP/def2-TZVP | D3BJ, RIJCOSX | 3 |
| water_opt | OPT | B3LYP/def2-SVP | Exact Hessian, %geom block | 3 |
| benzene_tddft | TD-DFT | B3LYP/def2-TZVP | 10 excited states, %tddft block | 12 |
| ts_sn2 | TS | B3LYP/def2-SVP | OPTTS, anion (charge -1) | 6 |
| methane_freq | FREQ | B3LYP/def2-TZVP | Thermochemistry, %freq block | 5 |
| ethanol_solvation | OPT | B3LYP/def2-TZVP | CPCM(Water), %cpcm block | 9 |
| fe_complex_uks | SCF | UKS-B3LYP/def2-SVP | Open-shell (S=2), transition metal | 19 |
| formaldehyde_casscf | CASSCF | CASSCF(4,4)/def2-TZVP | Multireference, state-averaging | 4 |

---

## Diversity Rationale

### Calculation Types (6 distinct types)
- **Single-point energy**: water_sp
- **Geometry optimization**: water_opt, ethanol_solvation
- **Transition state**: ts_sn2
- **Frequencies**: methane_freq
- **Excited states**: benzene_tddft
- **Multireference**: formaldehyde_casscf

### Electronic Structure Coverage
- **Closed-shell DFT**: water_sp, water_opt, benzene_tddft, methane_freq, ethanol_solvation
- **Open-shell (UKS)**: fe_complex_uks (quintet, S=2)
- **Multireference (CASSCF)**: formaldehyde_casscf (4 electrons, 4 orbitals)

### Charge States
- **Neutral**: water_sp, water_opt, benzene_tddft, methane_freq, ethanol_solvation, formaldehyde_casscf
- **Anionic (-1)**: ts_sn2
- **Cationic (+2)**: fe_complex_uks

### Method Categories
- **GGA + Hybrid DFT**: B3LYP (most samples)
- **Wavefunction**: CASSCF (formaldehyde_casscf)

### Special Features Coverage
- **Dispersion (D3BJ)**: water_sp, ts_sn2, methane_freq, ethanol_solvation
- **RI Acceleration (RIJCOSX)**: water_sp, water_opt, benzene_tddft, ts_sn2, methane_freq, ethanol_solvation, fe_complex_uks
- **Solvation (CPCM)**: ethanol_solvation
- **TD-DFT**: benzene_tddft
- **Hessian calculation**: water_opt, ts_sn2
- **State averaging**: formaldehyde_casscf

### Block Types Exercised
- `%pal`: All samples (parallelization)
- `%maxcore`: All samples (memory control)
- `%geom`: water_opt, ts_sn2 (geometry optimization settings)
- `%tddft`: benzene_tddft (excited state settings)
- `%freq`: methane_freq (frequency calculation settings)
- `%cpcm`: ethanol_solvation (solvation parameters)
- `%scf`: fe_complex_uks (SCF settings)
- `%casscf`: formaldehyde_casscf (multireference settings)

### System Diversity
- **Small organic molecules**: water (3 atoms), methane (5 atoms), formaldehyde (4 atoms)
- **Medium organic molecules**: benzene (12 atoms), ethanol (9 atoms)
- **Reaction intermediates**: SN2 transition state (6 atoms)
- **Transition metal complexes**: Fe(II) hexaquo (19 atoms)

---

## Parser Coverage Matrix

| Feature | Tested By |
|---------|-----------|
| `!` keyword line | All samples |
| Multiple keywords on `!` line | All samples |
| CPCM(solvent) in keyword line | ethanol_solvation |
| `* xyz charge mult` geometry | All samples |
| `%pal...end` block | All samples |
| `%maxcore N` | All samples |
| `%geom...end` with Calc_Hess | water_opt, ts_sn2 |
| `%tddft...end` with NRoots/TDA | benzene_tddft |
| `%freq...end` with Temp | methane_freq |
| `%cpcm...end` with epsilon/refrac | ethanol_solvation |
| `%scf...end` with MaxIter | fe_complex_uks |
| `%casscf...end` with nel/norb/weights | formaldehyde_casscf |
| Boolean values (true/false) | water_opt, benzene_tddft, ts_sn2 |
| Array syntax (weights[0]=...) | formaldehyde_casscf |
| Comment lines (#) | water_sp (implicit in test) |

---

## Validation Status

| Case | Parser | Writer | Roundtrip | Real Run |
|------|--------|--------|-----------|----------|
| water_sp | ✅ | ✅ | ✅ | ✅ (validated) |
| water_opt | ✅ | ✅ | ✅ | ⬜ |
| benzene_tddft | ✅ | ✅ | ✅ | ⬜ |
| ts_sn2 | ✅ | ✅ | ✅ | ⬜ |
| methane_freq | ✅ | ✅ | ✅ | ⬜ |
| ethanol_solvation | ✅ | ✅ | ✅ | ⬜ |
| fe_complex_uks | ✅ | ✅ | ✅ | ⬜ |
| formaldehyde_casscf | ✅ | ✅ | ✅ | ⬜ |

**Note**: Real run validation requires ORCA installation. water_sp was validated during
exploration phase (see `.tmp/engine_research/orca/runs/case_001_water_sp/`).

---

## Adding New Samples

When adding new curated samples:

1. Create a new directory under `tests/inputformat/samples/orca/<case_name>/`
2. Add `input.inp` (the ORCA input file)
3. Add `case.yaml` with metadata:
   ```yaml
   case_id: <case_name>
   title: "<Descriptive title>"
   engine: orca
   workflow_tags: [<tags>]
   species: [<elements>]
   functional: <method>
   basis_set: <basis>
   description: "<One-line description>"
   ```
4. Update this CURATED_INDEX.md
5. Ensure the sample parses correctly with existing tests

---

## References

- ORCA 6.0 Manual: https://www.faccts.de/docs/orca/6.0/manual/
- ORCA Input Library: https://sites.google.com/site/orcainputlibrary/
- Metadata catalog: `src/quantumvitas/drivers/orca/data/orca_keywords.json`
