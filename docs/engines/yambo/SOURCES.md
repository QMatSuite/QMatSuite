# Yambo Sources (Phase B1)

All dates are `2026-02-06` or `2026-02-07` local run dates.

## Official Yambo Sources
- https://www.yambo-code.eu/
  - Local mirror: `.tmp/engine_research/yambo/raw_web/yambo_wiki_main.html`
  - Coverage: main entry and documentation navigation.
- https://www.yambo-code.eu/wiki/index.php?title=Input_file
  - Local mirror: `.tmp/engine_research/yambo/raw_web/yambo_wiki_input_file.html`
  - Coverage: input structure and variable syntax.
- https://www.yambo-code.eu/wiki/index.php?title=RunLevels
  - Local mirror: `.tmp/engine_research/yambo/raw_web/yambo_wiki_runlevels.html`
  - Coverage: runlevel flags and workflow selectors.
- https://www.yambo-code.eu/wiki/index.php?title=Variables
  - Local mirror: `.tmp/engine_research/yambo/raw_web/yambo_wiki_variables.html`
  - Coverage: variable catalog reference.
- https://www.yambo-code.eu/wiki/index.php?title=Output_files
  - Local mirror: `.tmp/engine_research/yambo/raw_web/yambo_wiki_output_files.html`
  - Coverage: output file naming and meaning.
- https://www.yambo-code.eu/wiki/index.php?title=GW_calculations
  - Local mirror: `.tmp/engine_research/yambo/raw_web/yambo_wiki_gw_calculations.html`
  - Coverage: GW workflow guidance.
- https://www.yambo-code.eu/wiki/index.php?title=BSE_calculations
  - Local mirror: `.tmp/engine_research/yambo/raw_web/yambo_wiki_bse_calculations.html`
  - Coverage: BSE workflow guidance.
- https://www.yambo-code.eu/wiki/index.php?title=Optics
  - Local mirror: `.tmp/engine_research/yambo/raw_web/yambo_wiki_optics.html`
  - Coverage: optical response workflows.
- https://www.yambo-code.eu/wiki/index.php?title=TDDFT
  - Local mirror: `.tmp/engine_research/yambo/raw_web/yambo_wiki_tddft.html`
  - Coverage: TDDFT runlevel and kernel context.
- https://www.yambo-code.eu/wiki/index.php?title=p2y
  - Local mirror: `.tmp/engine_research/yambo/raw_web/yambo_wiki_p2y.html`
  - Coverage: QE->Yambo conversion tool.

## Official Repository / Manuals
- https://github.com/yambo-code/yambo
  - Local clone: `.tmp/engine_research/yambo/extracted/yambo_repo/`
  - Coverage: source tree, docs, sample assets.
- `doc/QuickGuidedTour.pdf` from upstream repository
  - Local copy: `.tmp/engine_research/yambo/raw_pdfs/QuickGuidedTour.pdf`
  - Coverage: guided workflow and core concepts.
- Yambo cheatsheet PDF
  - Local copy: `.tmp/engine_research/yambo/raw_pdfs/Yambo-Cheatsheet-5.0.pdf`
  - Coverage: quick command/variable reminders.

## Tutorials / External
- https://enccs.github.io/efficient-materials-modelling-on-hpc/yambo-tutorial/
  - Local copy: `.tmp/engine_research/yambo/raw_web/enccs_yambo_tutorial.html`
  - Coverage: practical tutorial workflow.

## Repository-Local Evidence Used for Numeric Comparisons
- `docs/engines/yambo/smoke_si_nc/gw_output/o-gw_si.qp`
- `docs/engines/yambo/smoke_si_nc/ip_output/o-ip_si.eps_q1_ip`
- `docs/engines/yambo/smoke_si_nc/bse_output/o-bse_si.eps_q1_haydock_bse`
- `.tmp/engine_research/yambo/runs/tmp_template/lrc_template.in` (template provenance for LRC run; no published numeric benchmark found)
