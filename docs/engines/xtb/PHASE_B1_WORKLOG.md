# xTB Phase B1 Worklog

Plan: `docs/engines/xtb/PHASE_B1_PLAN.md`
Status: COMPLETE

## 2026-02-07 — B1 takeover and compliance audit
- Read playbook and universal parser/writer design docs.
- Audited existing xTB state and found B1 gaps:
  - no committed B1 docs (`SOURCES`, `CURATED_INDEX`, `PHASE_B1_*`)
  - no metadata catalog/access layer
  - no registered output digest parser
  - no comprehensive curated sample set
  - `.tmp` raw corpus dirs existed but were mostly empty

## 2026-02-07 — Corpus hardening in `.tmp`
- Mirrored official ReadTheDocs content into `.tmp/engine_research/xtb/raw_web/readthedocs_mirror/`.
- Cloned official xTB repo into `.tmp/engine_research/xtb/extracted/xtb_repo/`.
- Created canonical `.tmp` docs:
  - `.tmp/engine_research/xtb/SOURCES.md`
  - `.tmp/engine_research/xtb/CORPUS_INDEX.md`
  - `.tmp/engine_research/xtb/WORKLOG.md`

## 2026-02-07 — Real engine execution evidence (mandatory)
- Verified local xTB availability from repo environment (`which xtb`, `xtb --version` -> 6.7.1).
- Executed diverse real runs and captured required artifacts per case:
  - `water_sp_gfn2`
  - `water_opt_gfn2`
  - `water_freq_ohess`
  - `water_md_short`
  - `ethanol_opt_tight`
  - `water_sp_solvation_alpb`
  - `o2_triplet_sp`
  - `caffeine_grad`
- For each case ensured presence of:
  - `command.txt`
  - `run_manifest.json`
  - `inputs/`
  - `outputs/`
  - `compare_note.md`

## 2026-02-07 — Driver implementation (B1)
- Added xTB metadata catalog and API:
  - `src/qmatsuite/drivers/xtb/data/xtb_tags.json` (82 tags)
  - `src/qmatsuite/drivers/xtb/data/xtb_metadata.py`
- Added xTB io parser/writer module:
  - `src/qmatsuite/drivers/xtb/io/xtb_input.py`
  - `src/qmatsuite/drivers/xtb/inputspec.py` updated to delegate writer+parser hooks
- Added xTB output digest parser and registry wiring:
  - `src/qmatsuite/drivers/xtb/parsers/output.py`
  - `src/qmatsuite/drivers/xtb/__init__.py` imports parsers for registration
- Extended command builder/parser helpers to cover more runtype/mode flags.

## 2026-02-07 — Curated inputs (committed)
- Added curated case directories under `tests/inputformat/samples/xtb/`:
  - `water_sp`, `water_opt`, `water_freq`, `water_md`
  - `ethanol_opt_tight`, `water_solvation_alpb`, `o2_triplet_sp`, `caffeine_grad`
- Each case has `case.yaml`; MD case includes `xcontrol.inp`.

## 2026-02-07 — Tests added
- Added test suites:
  - `tests/drivers/xtb/test_xtb_driver.py`
  - `tests/drivers/xtb/test_xtb_metadata.py`
  - `tests/drivers/xtb/test_xtb_execution.py`
  - `tests/inputformat/test_xtb_parse.py`
  - `tests/inputformat/test_xtb_digest.py`
- Targeted validation run (xTB-focused): 56 passed.

## 2026-02-07 — Documentation finalized
- Added committed xTB B1 docs:
  - `docs/engines/xtb/SOURCES.md`
  - `docs/engines/xtb/CORPUS_INDEX.md`
  - `docs/engines/xtb/CURATED_INDEX.md`
  - `docs/engines/xtb/PHASE_B1_PLAN.md`
  - `docs/engines/xtb/PHASE_B1_WORKLOG.md`

## Final Checklist (to be completed after full suite run)
- Playbook compliance sections:
  - Process rules: YES
  - Repository layout rules: YES
  - Corpus collection: YES
  - Metadata catalog + access layer: YES
  - Curated case library: YES
  - Parser/writer robustness: YES
  - Output digest parser: YES
  - Execution evidence: YES
- Corpus breadth summary:
  - raw_web: 186 files
  - extracted: 575 files
  - normalized: 24 files
  - real_run: 11 case directories
- Curated examples list + coverage: YES (8 diverse cases)
- Parser/writer tests summary (counts + pass): PENDING final full run
- Digest/analyzer status: IMPLEMENTED + TESTED

## 2026-02-07 — Isolation and cross-thread coordination update
- Enforced thread-safe test discipline for shared `.tmp`:
  - no concurrent pytest in this thread
  - serial execution only (`-n 0`) for xTB scope
  - xTB-only test selection (no full-suite run) per operator direction due concurrent yambo thread
- Verified no active pytest overlap before xTB validation run.

## Final Checklist (xtb-isolated validation, authoritative for this thread)
- Playbook compliance sections:
  - Process rules: YES
  - Repository layout rules: YES
  - Corpus collection: YES
  - Metadata catalog + access layer: YES
  - Curated case library: YES
  - Parser/writer robustness: YES
  - Output digest parser: YES
  - Execution evidence: YES
- Corpus breadth summary:
  - raw_web: 186 files
  - extracted: 575 files
  - normalized: 24 files
  - real_run: 11 case directories
- Curated examples list + what each covers:
  - `water_sp`: single-point baseline energy
  - `water_opt`: geometry optimization
  - `water_freq`: Hessian/frequency workflow
  - `water_md`: short MD with `xcontrol` input
  - `ethanol_opt_tight`: tighter optimization regime
  - `water_solvation_alpb`: implicit solvent (ALPB)
  - `o2_triplet_sp`: open-shell triplet single-point
  - `caffeine_grad`: larger-molecule gradient path
- Parser/writer tests summary (counts + pass):
  - Command: `python -m pytest tests/drivers/xtb tests/inputformat/test_xtb_parse.py tests/inputformat/test_xtb_digest.py tests/integration/test_xtb_execution.py -v --tb=short -n 0`
  - Result: `64 passed`
- Digest/analyzer status:
  - implemented (`src/qmatsuite/drivers/xtb/parsers/output.py`)
  - registered via driver import path
  - validated on synthetic + real-run outputs

## 2026-02-07 — Completion note
- xTB Phase B1 is complete for this thread scope.
- Coordination constraint acknowledged: because another active thread is running tests that share `.tmp`, validation was performed with xTB-only, serial runs and explicit no-overlap checks.
- Curated-to-evidence integrity re-checked: all curated slugs in `docs/engines/xtb/CURATED_INDEX.md` have required `real_run` artifacts (`command.txt`, `run_manifest.json`, `inputs/`, `outputs/`, `compare_note.md`).

## 2026-02-07 — Cross-Engine Re-Audit + Full Suite Confirmation
- Re-audited xTB committed docs:
  - `docs/engines/xtb/SOURCES.md`
  - `docs/engines/xtb/CORPUS_INDEX.md`
  - `docs/engines/xtb/CURATED_INDEX.md`
  - `docs/engines/xtb/PHASE_B1_WORKLOG.md`
  - status: complete.
- Re-validated curated-to-real_run linkage:
  - all xTB curated slugs resolve to complete real_run folders with required files.
- Full repository test run after final fixes:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - result: `4529 passed, 19 skipped`.
- xTB B1 checklist status remains: **YES** across all sections.
