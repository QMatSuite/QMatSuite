# Wannier90 Phase B1: End-to-End Parser/Writer/Digest

**Status**: IN PROGRESS
**Baseline**: 3691 passed, 24 skipped

## Goal
Bring Wannier90 to VASP/LAMMPS maturity: robust .win parser/writer with block support, output digest, and comprehensive tests with semantic roundtrip.

## Stages 1-3: Explore Track (Retrospective, DONE)

### Stage 1: Docs + Raw Corpus (DONE)
- Wannier90 v3.1.0 bundled with QE 7.5
- 26 LaTeX user guide files, 33 example dirs, pw2wannier90 docs
- ReadTheDocs (5 pages), QE interface docs (9 files), 3 PDFs
- All under .tmp/engine_research/wannier90/

### Stage 2: Metadata Seed (DONE)
- metadata/wannier90_params.yaml: 171 entries (120 .win + 9 blocks + 30 pw2wannier90)

### Stage 3: Normalized Case Library (DONE)
- 20 cases, 13 materials, 11 feature categories
- SKIPPED.md: 13 examples with reasons

## Stages 4-8: Implementation

### Stage 4: Parser/Writer (IN PROGRESS)
- **4A**: _parse_win_text — full block parser with diagnostics
- **4B**: _write_win_text enhancement — kpoint_path, exclude_bands, atoms_cart, kpoints block
- **4C**: Wire parser into EngineInputSpec

### Stage 5: Pipeline Awareness (DONE — existing infrastructure sufficient)
- ResourceRefSpec + artifact_resolver already handle .amn/.mmn/.eig

### Stage 6: Output Digest
- W90Digest + W90OutputParser in parsers/output.py
- Parse .wout for spreads, convergence, timing

### Stage 7: Optional Real Execution
- Run example01_gaas standalone
- Store in .tmp/engine_research/wannier90/runs/

### Stage 8: Tests
- test_w90_parse.py + test_w90_digest.py
- 4-5 curated samples under tests/inputformat/samples/w90/
- Target: ~45-55 new tests

## Acceptance Criteria
- [  ] All curated .win samples parse without error
- [  ] Semantic roundtrip passes for all samples
- [  ] W90Digest parses real .wout correctly
- [  ] All tests pass, no regressions
- [  ] docs/engines/wannier90/ committed docs exist
