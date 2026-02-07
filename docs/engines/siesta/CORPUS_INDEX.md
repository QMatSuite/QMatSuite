# Siesta Corpus Index (B1 Audit)

Updated: 2026-02-07
Engine: `siesta`

## Corpus Breadth Summary

- `raw_web`: 60 files
- `raw_pdfs`: 1 file
- `raw_zips`: 0 files
- `extracted`: 2433 files
- `normalized`: 16 normalized case directories (32 files total)
- `real_run`: 11 run directories (including 8 curated full runs)

## Layout

- `.tmp/engine_research/siesta/raw_web/`
- `.tmp/engine_research/siesta/raw_pdfs/`
- `.tmp/engine_research/siesta/raw_zips/`
- `.tmp/engine_research/siesta/extracted/`
- `.tmp/engine_research/siesta/metadata/`
- `.tmp/engine_research/siesta/normalized/`
- `.tmp/engine_research/siesta/real_run/`
- `.tmp/engine_research/siesta/runs/`

## Audit Findings

1. Legacy web mirror quality issue
- 52 of 60 `raw_web` files contain `404 Not Found` placeholder content.
- Canonical corpus authority for B1 was promoted to the local upstream clone:
  `.tmp/engine_research/siesta/extracted/siesta_repo/`.

2. Legacy machine index mismatch
- Existing `.tmp/engine_research/siesta/CORPUS_INDEX.json` includes placeholder entries not backed by current files.
- Canonical audited index for B1 closeout is:
  - `.tmp/engine_research/siesta/CORPUS_INDEX.md` (local authoritative narrative index)
  - `docs/engines/siesta/CORPUS_INDEX.md` (committed summary)

## Normalized Coverage

- `h2o_relax`
- `h2o_scf`
- `si_bands`
- `si_dos`
- `si_dz`
- `si_dzp`
- `si_high_ecut`
- `si_hybrid`
- `si_md`
- `si_phonons`
- `si_relax`
- `si_scf_minimal`
- `si_spin`
- `si_tddft`
- `si_vcrelax`
- `si_vdw`

## Real-Run Coverage

Existing smoke runs:
- `.tmp/engine_research/siesta/real_run/si_scf_smoke/`
- `.tmp/engine_research/siesta/real_run/si_relax_smoke/`
- `.tmp/engine_research/siesta/real_run/si_bands_smoke/`

Curated full runs (B1):
- `.tmp/engine_research/siesta/real_run/curated_h2o_scf_20260207/`
- `.tmp/engine_research/siesta/real_run/curated_si_scf_20260207/`
- `.tmp/engine_research/siesta/real_run/curated_si_relax_20260207/`
- `.tmp/engine_research/siesta/real_run/curated_si_bands_20260207/`
- `.tmp/engine_research/siesta/real_run/curated_si_dos_20260207/`
- `.tmp/engine_research/siesta/real_run/curated_si_spin_20260207/`
- `.tmp/engine_research/siesta/real_run/curated_si_md_20260207/`
- `.tmp/engine_research/siesta/real_run/curated_si_vcrelax_20260207/`

Each curated run contains required evidence files:
- `command.txt`
- `run_manifest.json`
- `inputs/`
- `outputs/`
- `compare_note.md`

## Pipeline Opportunities (Recorded)

1. Two-stage SCF-to-bands chaining
- Opportunity: explicit split `si_scf` then `si_bands` with restart artifacts (`*.DM`, `*.XV`) rather than single-file mixed settings.
- Evidence anchor: `.tmp/engine_research/siesta/real_run/curated_si_bands_20260207/outputs/si_bands.DM`.

2. DOS post-processing from SCF artifacts
- Opportunity: split `si_scf` and DOS post stage to validate re-use of `EIG/KP/PDOS` inputs in staged workflows.
- Evidence anchor: `.tmp/engine_research/siesta/real_run/curated_si_dos_20260207/outputs/si_dos.PDOS.xml`.
