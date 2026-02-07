# Phase B1: Yambo End-to-End QE-Depth

## Scope
- Engine: `yambo`
- Driver paths only: `src/quantumvitas/drivers/yambo/`, `tests/`, `docs/engines/yambo/`, `.tmp/engine_research/yambo/`
- Constraint from user: isolate work to Yambo; run Yambo-focused tests only.

## Baseline (2026-02-07)
- Existing Yambo docs: `PLAN.md`, `WORKLOG_AUTO_PHASE0_1.md`
- Existing real runs: `si_gw_smoke`, `si_ip_smoke`, `si_bse_smoke`
- Existing parser/writer pieces: present but not fully B1-documented/tested in canonical layout.
- Existing pre-B1 Yambo test inventory: `15` collected tests from `tests/integration/test_yambo_execution.py` (collection-only baseline).

## B1 Execution Plan
1. Compliance audit
- Ensure canonical docs exist: `PHASE_B1_PLAN.md`, `PHASE_B1_WORKLOG.md`, `SOURCES.md`, `CURATED_INDEX.md`.
- Ensure `.tmp` has canonical corpus/worklog indexing (`CORPUS_INDEX.md`, append-only notes).

2. Evidence strengthening
- Re-run real calculations (no trust-by-inheritance): QE SCF/NSCF -> `p2y` -> `yambo` init -> GW/IP/BSE/LRC.
- Create new canonical `real_run/<slug>/` folders containing:
  - `command.txt`, `run_manifest.json`, `inputs/`, `outputs/`, `compare_note.md`
- Best-effort reference comparison with precise citations.

3. Curated golden inputs (inputs-only)
- Curate diverse examples under `tests/inputformat/samples/yambo/`:
  - GW PPA, BSE Haydock, IP optics, TDDFT-LRC optics.
- Keep outputs in `.tmp` only.
- Document coverage and provenance in `CURATED_INDEX.md`.

4. Parser/writer/digest completion
- Keep parser/writer in `io/` and `inputspec.py` delegation.
- Add Yambo-focused tests:
  - metadata catalog/access
  - output digest parser + registry
  - yaml/dict -> writer against curated samples
  - input -> parser using curated and normalized corpus
  - semantic roundtrip

5. Validation
- Run Yambo-focused pytest targets with `-n 6 --dist=loadfile`.
- Record pass/fail counts in worklog.

## Acceptance Criteria
- Canonical B1 docs complete for Yambo.
- Curated examples are diverse and each maps to a real-run slug.
- Every curated candidate has a corresponding `.tmp/engine_research/yambo/real_run/<slug>/` evidence folder.
- Parser/writer/digest tests pass (Yambo-focused suite).
- Worklog includes final checklist with:
  - playbook compliance matrix
  - corpus breadth summary
  - curated example coverage
  - parser/writer test summary
  - digest/analyzer status
