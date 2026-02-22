# Gaussian Curated Sample Index

**Engine**: Gaussian
**Format Family**: F4 (keyword-block)
**Samples Location**: `tests/inputformat/samples/gaussian/`
**Total Samples**: 10
**Last Updated**: 2026-02-06

---

## Overview

This document catalogs the curated Gaussian input samples used for parser/writer validation.
Each sample represents a distinct calculation type with specific features that exercise
different aspects of the Gaussian parser.

---

## Sample Inventory

| Case ID | Calc Type | Method | Special Features | Atoms |
|---------|-----------|--------|------------------|-------|
| water_hf_sp | SCF | HF/STO-3G | Checkpoint, minimal basis | 3 |
| water_b3lyp_opt | OPT | B3LYP/6-31G* | Opt keyword, DFT | 3 |
| methanol_solvation | SCF | B3LYP/6-31G* | SCRF=(SMD,Solvent=Water) | 6 |
| water_zmatrix | SCF | HF/STO-3G | Z-matrix internal coords | 3 |
| formaldehyde_tddft | TD-DFT | B3LYP/STO-3G | TD=(NStates=3) | 4 |
| hcn_scan | Scan | HF/STO-3G | Z-matrix scan variables | 3 |
| ethylene_mp2 | SCF | MP2/STO-3G | Post-HF correlated method | 6 |
| o2_triplet_uhf | SCF | UHF/6-31G* | Open-shell, mult=3 | 2 |
| water_opt_freq | OPT+FREQ | HF/STO-3G | Combined Opt Freq job | 3 |
| multi_step_link1 | Multi-step | HF+MP2/STO-3G | --Link1--, Geom=AllCheck | 3 |

---

## Diversity Rationale

### Calculation Types (7 distinct types)
- **Single-point energy**: water_hf_sp, ethylene_mp2, o2_triplet_uhf
- **Geometry optimization**: water_b3lyp_opt
- **Solvation**: methanol_solvation
- **Excited states (TD-DFT)**: formaldehyde_tddft
- **PES scan**: hcn_scan
- **Combined Opt+Freq**: water_opt_freq
- **Multi-step Link1**: multi_step_link1

### Electronic Structure Coverage
- **Closed-shell HF**: water_hf_sp, water_zmatrix, hcn_scan, water_opt_freq
- **Closed-shell DFT (B3LYP)**: water_b3lyp_opt, methanol_solvation, formaldehyde_tddft
- **Open-shell (UHF)**: o2_triplet_uhf (triplet, mult=3)
- **Post-Hartree-Fock (MP2)**: ethylene_mp2, multi_step_link1 (second job)

### Geometry Input Formats
- **Cartesian coordinates**: water_hf_sp, water_b3lyp_opt, methanol_solvation, formaldehyde_tddft, ethylene_mp2, o2_triplet_uhf, water_opt_freq, multi_step_link1
- **Z-matrix internal coordinates**: water_zmatrix, hcn_scan

### Charge States
- **Neutral (0)**: All 10 samples

### Multiplicity States
- **Singlet (1)**: water_hf_sp, water_b3lyp_opt, methanol_solvation, water_zmatrix, formaldehyde_tddft, hcn_scan, ethylene_mp2, water_opt_freq, multi_step_link1
- **Triplet (3)**: o2_triplet_uhf

### Special Features Coverage
- **Link0 %chk**: water_hf_sp, water_b3lyp_opt, methanol_solvation, formaldehyde_tddft, ethylene_mp2, o2_triplet_uhf, water_opt_freq, multi_step_link1
- **Link0 %mem/%nproc**: All samples
- **Implicit solvation (SCRF/SMD)**: methanol_solvation
- **TD-DFT with options**: formaldehyde_tddft
- **Z-matrix scan variables**: hcn_scan
- **Combined job keywords (Opt Freq)**: water_opt_freq
- **--Link1-- multi-job**: multi_step_link1
- **Geom=AllCheck/Guess=Read**: multi_step_link1

---

## Parser Coverage Matrix

| Feature | Tested By |
|---------|-----------|
| `#p` route line parsing | All samples |
| Method/basis combo (X/Y) | All samples |
| Link0 `%mem` directive | All samples |
| Link0 `%nproc` directive | All samples |
| Link0 `%chk` directive | water_hf_sp, water_b3lyp_opt, methanol_solvation, formaldehyde_tddft, ethylene_mp2, o2_triplet_uhf, water_opt_freq, multi_step_link1 |
| Title section | All samples |
| Charge/multiplicity line | All samples |
| Cartesian geometry | water_hf_sp, water_b3lyp_opt, methanol_solvation, formaldehyde_tddft, ethylene_mp2, o2_triplet_uhf, water_opt_freq, multi_step_link1 |
| Z-matrix geometry | water_zmatrix, hcn_scan |
| Z-matrix variables | water_zmatrix, hcn_scan |
| Z-matrix scan params (N step) | hcn_scan |
| Opt keyword | water_b3lyp_opt, water_opt_freq |
| Freq keyword | water_opt_freq |
| TD=(NStates=N) parsing | formaldehyde_tddft |
| SCRF=(SMD,Solvent=X) | methanol_solvation |
| Scan keyword | hcn_scan |
| UHF method prefix | o2_triplet_uhf |
| MP2 post-HF method | ethylene_mp2, multi_step_link1 |
| --Link1-- section delimiter | multi_step_link1 |
| Geom=AllCheck in Link1 job | multi_step_link1 |
| Open-shell mult > 1 | o2_triplet_uhf |

---

## Validation Status

| Case | Parser | Writer | Roundtrip | Real Run |
|------|--------|--------|-----------|----------|
| water_hf_sp | pass | pass | pass | pass (g09) |
| water_b3lyp_opt | pass | pass | pass | -- |
| methanol_solvation | pass | pass | pass | -- |
| water_zmatrix | pass | pass | N/A (Z-mat) | -- |
| formaldehyde_tddft | pass | pass | pass | -- |
| hcn_scan | pass | pass | N/A (Z-mat) | -- |
| ethylene_mp2 | pass | pass | pass | pass (g09) |
| o2_triplet_uhf | pass | pass | pass | -- |
| water_opt_freq | pass | pass | pass | -- |
| multi_step_link1 | pass | pass | N/A (Link1) | -- |

**Note**: Real run validation requires Gaussian installation. water_hf_sp and ethylene_mp2
were validated during the exploration phase (see `.tmp/engine_research/gaussian/runs/`).
Z-matrix and Link1 samples are not roundtrippable (writer produces Cartesian, single-job).

---

## Adding New Samples

When adding new curated samples:

1. Create a new directory under `tests/inputformat/samples/gaussian/<case_name>/`
2. Add `input.gjf` (the Gaussian input file)
3. Add `case.yaml` with metadata:
   ```yaml
   case_id: <case_name>
   title: "<Descriptive title>"
   engine: gaussian
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

- Gaussian User's Reference: https://gaussian.com/man/
- Gaussian Keywords: https://gaussian.com/keywords/
- Metadata catalog: `src/qmatsuite/drivers/gaussian/data/gaussian_route_keywords.json`
