# xTB Corpus Index

Updated: 2026-02-07

## Corpus Breadth Summary
- raw_web mirror files: 186
- extracted upstream files: 575
- normalized files: 24
- real_run files: 176
- real_run case directories: 11

Source: `.tmp/engine_research/xtb/CORPUS_INDEX.md`

## Corpus Layout
- `.tmp/engine_research/xtb/raw_web/`
- `.tmp/engine_research/xtb/raw_pdfs/`
- `.tmp/engine_research/xtb/raw_zips/`
- `.tmp/engine_research/xtb/extracted/`
- `.tmp/engine_research/xtb/metadata/`
- `.tmp/engine_research/xtb/normalized/`
- `.tmp/engine_research/xtb/real_run/`
- `.tmp/engine_research/xtb/runs/`

## Normalized Case Coverage
- single-point: `h2o_sp`, `ch4_sp`, `nh3_sp`, `benzene_sp`, `co2_sp`, `h2_sp`
- optimization: `h2o_opt`, `ethanol_opt`, `ch4_opt`, `nh3_opt`, `benzene_opt`
- frequency/hessian: `h2o_freq`
- MD: `h2o_md`
- solvation: `h2o_solvation`
- gradient: `caffeine_grad`

## Real-run Coverage (Observed)
- Water SP: `.tmp/engine_research/xtb/real_run/water_sp_gfn2/`
- Water optimize: `.tmp/engine_research/xtb/real_run/water_opt_gfn2/`
- Water ohess: `.tmp/engine_research/xtb/real_run/water_freq_ohess/`
- Water MD: `.tmp/engine_research/xtb/real_run/water_md_short/`
- Ethanol tight opt: `.tmp/engine_research/xtb/real_run/ethanol_opt_tight/`
- Water ALPB SP: `.tmp/engine_research/xtb/real_run/water_sp_solvation_alpb/`
- O2 triplet SP: `.tmp/engine_research/xtb/real_run/o2_triplet_sp/`
- Caffeine gradient: `.tmp/engine_research/xtb/real_run/caffeine_grad/`

## Reference-value Anchors
- Water SP reference: `docs/engines/xtb/EXPLORATION.md:52`
- Water optimization reference: `docs/engines/xtb/EXPLORATION.md:60`
- Frequency/ZPE/free-energy reference: `docs/engines/xtb/EXPLORATION.md:77`
- Ethanol tight optimization reference: `docs/engines/xtb/EXPLORATION.md:69`
- Caffeine gradient reference: `docs/engines/xtb/EXPLORATION.md:85`
