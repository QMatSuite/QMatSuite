# Yambo Phase B1 Worklog (Append-only)

## 2026-02-07

### Step 1 - Audit + Scope Lock
- Confirmed Yambo-only scope and avoided unrelated engine files.
- Verified canonical Yambo code layout is present:
  - `src/quantumvitas/drivers/yambo/data/`
  - `src/quantumvitas/drivers/yambo/io/`
  - `src/quantumvitas/drivers/yambo/parsers/`
- Gap identified: missing B1 canonical docs and curated sample/test coverage.
- Baseline pre-B1 Yambo test collection: `15` tests (`tests/integration/test_yambo_execution.py`, collect-only).

### Step 2 - Fresh Real-Run Evidence (No Trust Inheritance)
- Executed fresh QE->p2y->yambo pipeline in:
  - `.tmp/engine_research/yambo/runs/si_pipeline_20260207b`
- Ran real calculations:
  - `ip`, `gw`, `bse`, `lrc` (all successful; outputs produced)
- Promoted evidence to canonical real-run slugs:
  - `.tmp/engine_research/yambo/real_run/si_ip_qe4x4_20260207`
  - `.tmp/engine_research/yambo/real_run/si_gw_qe4x4_20260207`
  - `.tmp/engine_research/yambo/real_run/si_bse_qe4x4_20260207`
  - `.tmp/engine_research/yambo/real_run/si_lrc_tddft_qe4x4_20260207`
- Each contains required artifacts:
  - `command.txt`, `run_manifest.json`, `inputs/`, `outputs/`, `compare_note.md`
- Added best-effort references in `expected_refs.json` with citations.

### Step 3 - Curated Inputs
- Added curated sample library:
  - `tests/inputformat/samples/yambo/si_gw_ppa`
  - `tests/inputformat/samples/yambo/si_bse_haydock`
  - `tests/inputformat/samples/yambo/si_ip_optics`
  - `tests/inputformat/samples/yambo/si_tddft_lrc`
- Added `case.yaml` in each curated case.

### Step 4 - Documentation Canonicalization
- Added/updated canonical B1 docs:
  - `docs/engines/yambo/PHASE_B1_PLAN.md`
  - `docs/engines/yambo/PHASE_B1_WORKLOG.md`
  - `docs/engines/yambo/SOURCES.md`
  - `docs/engines/yambo/CURATED_INDEX.md`

### Step 5 - Parser/Digest Robustness
- Improved Yambo output digest spectrum file selection to prefer natural q-index ordering (`q1` before `q10`) in:
  - `src/quantumvitas/drivers/yambo/parsers/output.py`

### Step 6 - Pending
- Add Yambo-focused tests (metadata/output/parser-writer/roundtrip).
- Run Yambo-only pytest command with `-n 6 --dist=loadfile`.
- Append final compliance checklist and pass counts.

### Step 7 - Yambo-Focused Test Validation
- Command:
  - `source .venv/bin/activate && python -m pytest tests/drivers/yambo/test_yambo_metadata.py tests/drivers/yambo/test_yambo_output.py tests/inputformat/test_yambo_parse.py tests/integration/test_yambo_execution.py -v --tb=short -n 6 --dist=loadfile`
- First run: `48 passed, 2 failed` (report parsing ambiguity for `Bands` vs `Filled Bands`).
- Fix applied in `src/quantumvitas/drivers/yambo/parsers/output.py`:
  - guard total-bands regex so it does not match `Filled Bands`.
- Re-run result: `50 passed`, `0 failed`.

### Step 8 - Pipeline Opportunity Notes
- Upstream conversion workflows available but not yet curated as separate committed cases:
  - `a2y` (ABINIT -> Yambo SAVE)
  - `c2y` (CPMD -> Yambo SAVE)
- Current B1 evidence covers QE -> `p2y` -> Yambo end-to-end only.

## Final Checklist (Requested)

### Playbook Compliance Matrix
- Phase 0 corpus collection artifacts present: **YES**
- Phase 1 metadata catalog (50+ specialized floor): **YES** (`73` tags)
- Phase 2 metadata access layer API: **YES**
- Phase 3 curated case library committed: **YES** (`4` curated Yambo cases)
- Phase 4 parser/writer robustness + roundtrip tests: **YES**
- Phase 5 resource staging applicability: **N/A** (Yambo consumes upstream SAVE; no separate resource staging module required for this B1 scope)
- Phase 6 output digest parser + registry: **YES**
- Phase 7 execution evidence (real runs): **YES** (fresh QE->p2y->Yambo runs captured)
- Phase 8 integration validation (Yambo-focused per user constraint): **YES**

### Corpus Breadth Summary
- `raw_web/`: `41` mirrored files.
- `raw_web_resolved/`: `4` resolved mirror files.
- `raw_pdfs/`: `2` manuals/cheatsheets.
- `normalized/`: `17` normalized case folders.
- `real_run/`: `7` run evidence folders (legacy smoke + `4` fresh 2026-02-07 slugs).
- Upstream repository clone and extracted examples preserved under `.tmp/engine_research/yambo/extracted/`.

### Curated Examples and Coverage
- `si_gw_ppa` -> GW quasiparticle corrections (PPA/dyson/em1d)
- `si_bse_haydock` -> excitonic BSE spectrum (SEX + Haydock)
- `si_ip_optics` -> independent-particle optics
- `si_tddft_lrc` -> TDDFT optics with LRC kernel

### Parser/Writer Test Summary
- Targeted command (Yambo-only, `-n 6`) final result: **50 passed, 0 failed**.
- Coverage includes:
  - metadata JSON + API tests
  - output parser/digest + registry tests
  - curated writer conformance tests
  - curated parser tests
  - semantic roundtrip tests
  - normalized corpus parse tests
  - existing Yambo integration execution tests

### Digest / Analyzer Status
- Digest parser implemented and registered: `@register_parser("yambo", "scf_digest")`.
- Supports GW `.qp`, optics `.eps_*`, report `r-*` ingestion.
- Non-fatal behavior on missing outputs confirmed (default digest + error message).
- File-order robustness improved: spectrum parsing now prioritizes natural q-index order (`q1` before `q10`).

## 2026-02-07 — Cross-Engine Re-Audit + Full Suite Confirmation
- Committed corpus docs re-audited:
  - `docs/engines/yambo/CORPUS_INDEX.md` added to ensure canonical B1 doc set is complete.
  - `docs/engines/yambo/SOURCES.md`, `CURATED_INDEX.md`, `PHASE_B1_WORKLOG.md` verified present.
- Curated-to-evidence linkage re-check:
  - all 4 curated Yambo cases resolve to real_run directories containing:
    `command.txt`, `run_manifest.json`, `inputs/`, `outputs/`, `compare_note.md`.
- Full repository test run after final fixes:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - result: `4529 passed, 19 skipped`.
- Yambo B1 checklist status remains: **YES** across all applicable sections.
