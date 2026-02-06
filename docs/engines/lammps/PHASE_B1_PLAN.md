# LAMMPS Phase B1: End-to-End Parser/Writer/Digest

**Status**: COMPLETE
**Baseline**: 3572 passed, 24 skipped
**Final**: 3691 passed, 24 skipped (+119 new tests)

## Goal
Bring LAMMPS to VASP/ORCA maturity: robust command-stream parser/writer with roundtrip support, output digest, and comprehensive tests.

## Architecture

All new code in `drivers/lammps/`:
```
parsers/
  __init__.py            (triggers registration)
  output.py              (LAMMPSDigest + LAMMPSOutputParser)
inputspec.py             (enhanced: script parser, data parser, stream writer)
```

Tests in `tests/inputformat/`:
```
test_lammps_parse.py     (parser + roundtrip + orchestrator, 88 tests)
test_lammps_digest.py    (output digest + validation, 31 tests)
samples/lammps/          (8 curated samples)
```

## Key Design: Dual Representation
- Flat semantic fields for SSOT queries (units, pair_style, fixes, etc.)
- `_commands` list for faithful write-back (preserves order)
- Roundtrip defined on `_commands` structure, not text fidelity

## Stages 1-3: Explore Track (Retrospective)

### Stage 1: Docs + Raw Corpus (DONE)
- Identified LAMMPS Homebrew install: v22 Jul 2025 Update 3
- Copied 90 example directories (843 input files) to `extracted/bundled_examples/`
- Copied 257 potential files to `extracted/bundled_potentials/`
- Copied 202 benchmark files to `extracted/bundled_benchmarks/`
- Crawled 85 markdown pages from docs.lammps.org to `raw_web/`
- All raw data under `.tmp/engine_research/lammps/`

### Stage 2: Metadata Seed (DONE)
- Built `metadata/lammps_commands.json`: 79 commands, 121 sub-styles, 29 file references
- Built `metadata/lammps_input_syntax.md`: comprehensive syntax reference
- Classified commands by category: setup, geometry, forcefield, dynamics, output, etc.

### Stage 3: Normalized Case Library (DONE)
- Created 40 normalized cases under `normalized/<case_id>/`
- Each case: in.lammps + case.yaml + source.txt
- Coverage: MD, minimize, NEB, shock, elastic, flow, transport, MC, accelerated dynamics, spin, peridynamics, granular, ML potentials, TTM, rerun, triclinic
- Validation: 7 fast cases run locally with lmp_serial, all passed (<4s each)

## Stages 4-7: Implementation

### Stage 4: Parser/Writer (DONE)
- **4A Script parser** (`_parse_lammps_script_text`): line continuation, comment stripping, dual representation, ~25 key commands extracted
- **4B Data file parser** (`_parse_lammps_data_text`): header/masses/atoms sections, auto-detect atom_style (atomic/charge/full), Cartesian-to-fractional conversion
- **4C Writer enhancement**: stream mode (from `_commands`) + template mode (from flat fields), data file writer with tilt support
- **4D Wiring**: parsers on both InputFileSpecs, `structure.data` marked `optional=True`

### Stage 5: Output Digest (DONE)
- LAMMPSDigest: 16 fields (success, energy, temp, pressure, atoms, steps, wall_time, minimize stats, etc.)
- LAMMPSOutputParser registered as ("lammps", "scf_digest")
- Parses: thermo blocks (dynamic column detection), Loop time, minimize stats, Total wall time, errors

### Stage 6: Validate Against Runs (DONE)
- All 7 existing run logs parsed correctly by digest
- Verified: melt_lj_nve, minimize_2d_lj, crack_2d_lj, flow_couette_2d, indent_2d_lj, tersoff_sic, shear_metal_eam

### Stage 7: Tests (DONE)
- `test_lammps_parse.py`: 88 tests (parser, data, writer, samples, roundtrip, orchestrator, spec)
- `test_lammps_digest.py`: 31 tests (inline logs, parser class, 7 validation runs)
- 8 curated samples: melt_lj_nve, minimize_2d_lj, peptide_nvt, reaxff_rdx, eam_hyper, coreshell, meam_sic, elastic_sw

## Acceptance Criteria
- [x] All 8 curated samples parse without error
- [x] Roundtrip semantic equivalence for all samples
- [x] LAMMPSDigest parses all 7 existing run logs
- [x] All tests pass, no regressions
