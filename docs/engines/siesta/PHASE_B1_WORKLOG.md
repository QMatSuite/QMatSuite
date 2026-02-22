# Siesta Phase B1 Worklog

**Plan**: `docs/engines/siesta/PHASE_B1_PLAN.md`
**Started**: 2026-02-07
**Status**: COMPLETE

## 2026-02-07

### Step: Baseline and Environment Verification
- Actions:
  - Verified installed siesta executable path: `/opt/homebrew/Caskroom/miniforge/base/bin/siesta`.
  - Verified version banner from local executable (Siesta 5.4.2 conda-forge build metadata).
  - Verified pseudopotential files exist: `docs/engines/siesta/pseudopotentials/{H,O,Si}.psml`.
  - Ran baseline driver test file with required worker count: `python -m pytest tests/drivers/siesta/test_siesta_driver.py -v --tb=short -n 6 --dist=loadfile`.
- Result:
  - `15 passed`, `0 failed`, `0 skipped` for baseline siesta driver tests.
- Status: PASS

### Step: Plan and Worklog Initialization
- Actions:
  - Created `docs/engines/siesta/PHASE_B1_PLAN.md`.
  - Created `docs/engines/siesta/PHASE_B1_WORKLOG.md` and started append-only logging.
- Result: Required B1 process scaffolding established before code changes.
- Status: PASS

### Step: Parser/Writer Implementation (Universal Inputformat)
- Actions:
  - Added `src/qmatsuite/drivers/siesta/io/fdf.py` as dedicated FDF parser/writer module.
  - Added `src/qmatsuite/drivers/siesta/io/__init__.py`.
  - Wired `src/qmatsuite/drivers/siesta/inputspec.py` with `custom_parser` + `custom_writer`.
  - Reworked legacy writer path in `src/qmatsuite/drivers/siesta/writer.py` to delegate to `io/fdf.py`.
- Evidence/Citations:
  - Design alignment: `docs/design/UNIVERSAL_PARSER_WRITER_DESIGN.md`
  - Playbook writer extraction requirement: `docs/laws/L2/B1_ENGINE_PLAYBOOK.md`
- Result:
  - Siesta input parsing and writing are delegated through a robust `io/` leaf module.
- Status: PASS

### Step: Output Digest Parser
- Actions:
  - Added `src/qmatsuite/drivers/siesta/parsers/output.py` with `SiestaDigest`.
  - Registered parser via `@register_parser("siesta", "scf_digest")`.
  - Ensured registration import path through `src/qmatsuite/drivers/siesta/__init__.py`.
- Result:
  - Parser registry lookup for `("siesta", "scf_digest")` is available.
- Status: PASS

### Step: Curated Input Library + Parser/Writer Tests
- Actions:
  - Added 8 curated siesta cases under `tests/inputformat/samples/siesta/`:
    `h2o_scf`, `si_scf`, `si_relax`, `si_bands`, `si_dos`, `si_spin`, `si_md`, `si_vcrelax`.
  - Added parser/writer/roundtrip tests: `tests/inputformat/test_siesta_parse.py`.
  - Added digest tests: `tests/inputformat/test_siesta_digest.py`.
  - Ran siesta-focused test suite with fixed worker count:
    `source .venv/bin/activate && python -m pytest tests/inputformat/test_siesta_parse.py tests/inputformat/test_siesta_digest.py tests/inputformat/test_engine_materialize.py::TestSiestaMaterialize tests/drivers/siesta/test_siesta_driver.py -v --tb=short -n 6 --dist=loadfile`.
- Result:
  - `54 passed`, `0 failed`, `0 skipped`.
- Status: PASS

### Step: Corpus Audit + Expansion
- Actions:
  - Audited `.tmp/engine_research/siesta/raw_web/` and identified high 404 placeholder ratio.
  - Expanded authoritative corpus by cloning official upstream repository into:
    `.tmp/engine_research/siesta/extracted/siesta_repo/`.
  - Recorded source lists and audited index:
    - `.tmp/engine_research/siesta/SOURCES.md`
    - `.tmp/engine_research/siesta/CORPUS_INDEX.md`
    - `docs/engines/siesta/SOURCES.md`
    - `docs/engines/siesta/CORPUS_INDEX.md`
- Evidence/Citations:
  - Upstream repo snapshot: `.tmp/engine_research/siesta/extracted/siesta_repo/`
  - Local index quality note: `.tmp/engine_research/siesta/CORPUS_INDEX.md`
- Result:
  - Canonical corpus references now point to upstream authoritative extracted data.
- Status: PASS

### Step: Real-Run Evidence Hardening (Curated Cases)
- Actions:
  - Executed real siesta calculations for all 8 curated cases with local binary.
  - Created canonical evidence folders under `.tmp/engine_research/siesta/real_run/`:
    - `curated_h2o_scf_20260207`
    - `curated_si_scf_20260207`
    - `curated_si_relax_20260207`
    - `curated_si_bands_20260207`
    - `curated_si_dos_20260207`
    - `curated_si_spin_20260207`
    - `curated_si_md_20260207`
    - `curated_si_vcrelax_20260207`
  - For each run, added required files:
    `command.txt`, `run_manifest.json`, `inputs/`, `outputs/`, `compare_note.md`.
  - Added best-effort reference comparisons and citations in each run's `compare_note.md`.
- Result:
  - 8/8 curated runs completed with `exit_code = 0` and normal-exit markers.
- Status: PASS

### Step: Curated Index Closeout
- Actions:
  - Added committed curated mapping index:
    `docs/engines/siesta/CURATED_INDEX.md`.
  - Linked each committed curated input case to exact real-run evidence slug and source provenance.
- Result:
  - Repo-level curated index is complete and points to non-committed runtime evidence by slug.
- Status: PASS

## Final Checklist (B1 Closeout Snapshot)

### Playbook Compliance by Section
- Plan/worklog discipline: **YES**
- Corpus collected under `.tmp` and indexed: **YES** (audited; canonical indices promoted)
- Committed source/corpus/curated docs: **YES** (`SOURCES.md`, `CORPUS_INDEX.md`, `CURATED_INDEX.md`)
- Curated inputs committed (inputs-only policy): **YES** (8 cases)
- Parser/writer implemented and delegated to `io/`: **YES**
- Output digest parser implemented + registered: **YES**
- Real-run evidence for curated set with required files: **YES** (8/8 complete)
- Pipeline opportunity notes recorded: **YES** (`docs/engines/siesta/CORPUS_INDEX.md`)

### Corpus Breadth Summary
- `raw_web`: 60 files (52 are legacy 404 placeholders; audited)
- `raw_pdfs`: 1 file
- `extracted`: 2433 files (official `siesta_repo` clone)
- `normalized`: 16 case directories
- `real_run`: 11 run directories total (8 curated full runs + 3 legacy smoke runs)

### Curated Examples and Coverage
- `h2o_scf`: molecular SCF
- `si_scf`: periodic SCF
- `si_relax`: ionic/cell relaxation
- `si_bands`: bands workflow
- `si_dos`: DOS/PDOS workflow
- `si_spin`: spin-polarized SCF
- `si_md`: short MD (Verlet)
- `si_vcrelax`: fast variable-cell relax regime

### Parser/Writer Tests Summary
- Command:
  `source .venv/bin/activate && python -m pytest tests/inputformat/test_siesta_parse.py tests/inputformat/test_siesta_digest.py tests/inputformat/test_engine_materialize.py::TestSiestaMaterialize tests/drivers/siesta/test_siesta_driver.py -v --tb=short -n 6 --dist=loadfile`
- Result: **54 passed**, **0 failed**, **0 skipped**
- Scope note: full `tests/` run was intentionally skipped per user instruction to avoid collisions with concurrent engine threads.

### Digest/Analyzer Status
- `SiestaOutputParser` implemented in `src/qmatsuite/drivers/siesta/parsers/output.py`
- Registered object type: `("siesta", "scf_digest")`
- Digest tests: PASS (`tests/inputformat/test_siesta_digest.py`)

## 2026-02-07 — Post-B1 Regression Fix + Full-Suite Validation

### Siesta execution regression discovered/fixed
- Symptom from integration tests:
  - `test_si_scf_periodic` and `test_si_cg_relaxation` reported unphysical positive energies.
- Root causes:
  - Legacy `write_fdf(...)` wrapper emitted scaled lattice vectors with implicit `LatticeConstant = 1 Ang` while preserving `ScaledCartesian` coordinates, changing coordinate semantics.
  - `parse_main_output()` selected first `E_KS(eV)` match instead of the final one for multi-step outputs.
- Fixes:
  - `src/qmatsuite/drivers/siesta/writer.py`
    - preserve `LatticeConstant` from wrapper input (`<value> Ang`) so `ScaledCartesian` remains physically correct.
  - `src/qmatsuite/drivers/siesta/parser.py`
    - take final `E_KS(eV)` match for `total_energy_eV`.
  - Added regression tests:
    - `tests/drivers/siesta/test_siesta_writer_parser.py`

### Verification
- Targeted rerun:
  - `tests/integration/test_siesta_execution.py::TestSiestaSCF::test_si_scf_periodic`
  - `tests/integration/test_siesta_execution.py::TestSiestaRelax::test_si_cg_relaxation`
  - new siesta regression tests
  - Result: all pass.
- Full suite rerun:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - Result: `4529 passed, 19 skipped`.

### Checklist refresh
- Playbook compliance sections: **YES** (unchanged from B1 closeout).
- Curated inputs/evidence linkage: **YES** (8/8 siesta curated slugs complete).
- Parser/writer + digest status: **YES** with additional regression coverage.
