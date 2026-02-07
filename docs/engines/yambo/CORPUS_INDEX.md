# Yambo Corpus Index

Updated: 2026-02-07
Engine: `yambo`

## Corpus Breadth Summary

- `raw_web`: 41 files
- `raw_web_resolved`: 4 files
- `raw_pdfs`: 2 files
- `raw_zips`: 0 files
- `extracted`: upstream repo and example bundles present
- `normalized`: 17 normalized case folders
- `real_run`: 7 run folders total (legacy smoke + 4 fresh curated evidence runs)

## Canonical Layout

- `.tmp/engine_research/yambo/raw_web/`
- `.tmp/engine_research/yambo/raw_web_resolved/`
- `.tmp/engine_research/yambo/raw_pdfs/`
- `.tmp/engine_research/yambo/raw_zips/`
- `.tmp/engine_research/yambo/extracted/`
- `.tmp/engine_research/yambo/metadata/`
- `.tmp/engine_research/yambo/normalized/`
- `.tmp/engine_research/yambo/real_run/`
- `.tmp/engine_research/yambo/runs/`

## Curated Real-Run Evidence (B1)

- `.tmp/engine_research/yambo/real_run/si_ip_qe4x4_20260207/`
- `.tmp/engine_research/yambo/real_run/si_gw_qe4x4_20260207/`
- `.tmp/engine_research/yambo/real_run/si_bse_qe4x4_20260207/`
- `.tmp/engine_research/yambo/real_run/si_lrc_tddft_qe4x4_20260207/`

Each curated run contains required evidence artifacts:
- `command.txt`
- `run_manifest.json`
- `inputs/`
- `outputs/`
- `compare_note.md`

## Pipeline Notes

1. Verified QE-to-Yambo composite workflow evidence exists for B1:
- QE SCF/NSCF -> `p2y` -> `yambo` (IP, GW, BSE, TDDFT-LRC).

2. Additional upstream conversion chains identified as opportunities:
- `a2y` (ABINIT -> Yambo SAVE)
- `c2y` (CPMD -> Yambo SAVE)
