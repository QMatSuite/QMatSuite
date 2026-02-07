# xTB Phase B1 Plan

Status: COMPLETE
Updated: 2026-02-07

## Baseline
- Existing auto groundwork: `docs/engines/xtb/PLAN.md`, `docs/engines/xtb/WORKLOG_AUTO_PHASE0_1.md`
- Existing xTB driver: `src/quantumvitas/drivers/xtb/`
- Existing sample coverage before B1: one flat sample (`tests/inputformat/samples/xtb/water.xyz`)

## Scope
1. Playbook compliance audit and layout normalization
2. Corpus hardening in `.tmp/engine_research/xtb/`
3. Real-run evidence for curated/golden candidates
4. Full parser/writer + metadata + digest implementation for xTB
5. Curated input library and complete committed docs indices
6. Tests: writer, parser, roundtrip, metadata, digest, execution
7. Final full test run with required command (`-n 6`)

## Planned Deliverables
- Committed docs:
  - `docs/engines/xtb/SOURCES.md`
  - `docs/engines/xtb/CORPUS_INDEX.md`
  - `docs/engines/xtb/CURATED_INDEX.md`
  - `docs/engines/xtb/PHASE_B1_PLAN.md`
  - `docs/engines/xtb/PHASE_B1_WORKLOG.md`
- `.tmp` evidence additions:
  - mirrored docs/repo corpus
  - diverse `real_run/<slug>/` evidence bundles
  - canonical `.tmp` source/index/worklog docs
- Driver code:
  - `src/quantumvitas/drivers/xtb/data/xtb_tags.json`
  - `src/quantumvitas/drivers/xtb/data/xtb_metadata.py`
  - `src/quantumvitas/drivers/xtb/io/xtb_input.py`
  - `src/quantumvitas/drivers/xtb/parsers/output.py`
- Tests:
  - `tests/inputformat/test_xtb_parse.py`
  - `tests/inputformat/test_xtb_digest.py`
  - `tests/drivers/xtb/test_xtb_driver.py`
  - `tests/drivers/xtb/test_xtb_metadata.py`
  - `tests/drivers/xtb/test_xtb_execution.py`

## Acceptance Criteria
- 50+ xTB tags in metadata catalog (specialized-engine threshold)
- Curated cases are diverse and mapped to real-run evidence slugs
- Parser/writer path supports both `input.xyz` and optional `xcontrol.inp`
- Digest parser registered at `(xtb, scf_digest)` and tested
- Full required pytest command passes
