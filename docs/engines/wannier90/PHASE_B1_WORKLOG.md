# Wannier90 Phase B1 — WORKLOG

## 2026-02-06T15:20 — Stage 7: Real execution complete

### Standalone W90 (GaAs example01)
- Ran successfully with bundled gaas.amn/mmn/eig (pre-computed, no QE needed)
- Digest validated: success=True, num_wann=4, spread_total=4.468812116, wall_time=0.029s
- Files at .tmp/engine_research/wannier90/runs/example01_gaas/

### Full QE→W90 Pipeline (Diamond)
- Downloaded C.pz-vbc.UPF pseudopotential from QE pseudo library
- 5-step pipeline: pw.x scf → pw.x nscf → wannier90.x -pp → pw2wannier90.x → wannier90.x
- All steps completed successfully
- Digest validated: success=True, num_wann=4, spread_total=8.390118278, wall_time=0.174s
- Note: Spread (8.39) differs from old QE reference (4.38) — version difference (v3.1 vs v1.2).
  Optimization flat from iteration 0 (ΔΩ=0.0), likely local minimum with f-centered projections.
- Files at .tmp/engine_research/wannier90/runs/diamond_qe_pipeline/
- Run manifests and digest.json written for both runs

---

## 2026-02-06T14:40 — Stage 6: Output digest complete

- Created src/quantumvitas/drivers/w90/parsers/__init__.py + output.py
- W90Digest dataclass: 14 fields (success, converged, spreads, WF centres, wall_time, etc.)
- W90OutputParser registered as @register_parser("w90", "scf_digest")
- parse_wout_text() extracts all key metrics from .wout via regex
- 30 tests in tests/inputformat/test_w90_digest.py — all passing
- Includes validation against real diamond.sa.wout from QE examples (skipif)

---

## 2026-02-06T14:00 — Stage 8: Tests complete (partial — parser/writer)

- Created tests/inputformat/test_w90_parse.py — 102 tests
- 6 test classes: Parser(31), Writer(15), CuratedSamples(9), Roundtrip(20), Orchestrator(3), InputSpec(4)
- 5 curated .win samples under tests/inputformat/samples/w90/
- All 102 tests passing, no regressions

---

## 2026-02-06T13:00 — Stage 4: Parser/writer complete

- Parser (_parse_win_text) handles: comments, all separators, Fortran notation, booleans,
  all block types (unit_cell_cart with bohr/ang, atoms_frac/cart, projections, kpoints with weights,
  kpoint_path, exclude_bands), unknown key/block diagnostics
- Writer (_write_win_text) enhanced: kpoint_path, exclude_bands, atoms_cart, boolean formatting
- Parser wired into InputSpec via custom_parser=_parse_win_text
- 102 parser/writer tests all green

---

## 2026-02-05T23:00 — Phase B1 started (Stages 4-8)
- Baseline: 3691 passed, 24 skipped
- Created docs/engines/wannier90/ with PHASE_B1_PLAN.md, PHASE_B1_WORKLOG.md, SOURCES.md, EXPLORE_SUMMARY.md
- Migrated worklog content from .tmp; raw corpus stays in .tmp/engine_research/wannier90/

---

## Prior Work (Stages 1-3, from .tmp/engine_research/wannier90/WORKLOG.md)

### Environment
- Wannier90 version: 3.1.0
- Location: .qmatsuite/engines/qe/q-e-qe-7.5/bin/wannier90.x
- Related executables: pw2wannier90.x, merge_wann.x, wannier_ham.x, wannier_plot.x, wannier2pw.x
- QE version: 7.5 (bundled)

### 2026-02-05T00:00 — Session start
- Created directory structure under .tmp/engine_research/wannier90/
- Confirmed Wannier90 v3.1.0 executable works

### 2026-02-05T00:05 — Stage 1: Parallel crawl launched
- 4 parallel background agents: official docs, bundled examples, QE interface docs, GitHub examples

### 2026-02-05T00:10 — KEY DISCOVERY: Two local Wannier90 source trees
- QE-bundled Wannier90 at .qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/ has COMPLETE source
- "nucleus" build had EMPTY files. Decision: Use QE-bundled version as primary source.

### 2026-02-05T00:12 — Stage 1 corpus extraction
- Copied doc_full/user_guide/ (26 files), 34 example dirs, pw2wannier90 docs

### 2026-02-05T00:15 — Stage 1 deep documentation read
- Read complete parameters.tex (1800 lines) — all ~100+ .win parameters
- Read projections.tex, INPUT_pw2wannier90.txt
- Read example .win files: 01 (GaAs), 04 (Cu), 05 (diamond), 08 (Fe spin), 09 (BaTiO3), 17 (Fe spinors)

### 2026-02-05T00:20 — Example classification complete
- Pure W90: 01-04, 16-noqe
- QE pipeline: 05-13, 16-withqe, 17-20, 25-26, 28-32
- Complex/multi-variant: 14-15, 21-24, 27

### 2026-02-05T00:22 — Stages 2 & 3 launched in parallel
- Stage 2: metadata seed YAML (171 params, 9 blocks, 30 pw2wannier90 params)
- Stage 3: 20 normalized cases with case.yaml + source.txt

### 2026-02-05T00:30 — Stages 2 & 3 COMPLETE
- metadata/wannier90_params.yaml: 1723 lines, 59KB
- normalized/: 20 cases, 21 .win files, 13 materials
- SKIPPED.md: 13 examples documented

### Key Findings / Notes for Future Work

#### Parser Notes
- .win format: free-form, case-insensitive, ! and # for comments
- Key/value separators: space, =, or :
- Logical values: T, true, .true.
- Blocks: begin <name> ... end <name>
- Some blocks have optional first-line units (e.g., bohr in unit_cell_cart)
- Projections block has complex sub-syntax (site:ang_mtm:zaxis:xaxis:radial:zona)
- kpoints block may have optional 4th column (weights)

#### Interface Notes
- pw2wannier90 is a QE postprocessing tool (PP module)
- Workflow: pw.x scf -> pw.x nscf -> wannier90.x -pp -> pw2wannier90.x -> wannier90.x
- pw2wannier90 input is Fortran namelist (&INPUTPP ... /)
- seedname in pw2wannier90 must match .win seedname
