# LAMMPS Phase B1 — Worklog

## 2026-02-05 Session (Explore Stages 1-3)

### Stage 1: Docs + Raw Corpus
- Identified LAMMPS Homebrew install: v22 Jul 2025 Update 3
- Copied 90 example directories (843 input files) to `extracted/bundled_examples/`
- Copied 257 potential files to `extracted/bundled_potentials/`
- Copied 202 benchmark files to `extracted/bundled_benchmarks/`
- Crawled 85 markdown pages from docs.lammps.org to `raw_web/`

### Stage 2: Metadata Seed
- Built `metadata/lammps_commands.json`: 79 commands, 121 sub-styles, 29 file references
- Built `metadata/lammps_input_syntax.md`: comprehensive syntax reference

### Stage 3: Normalized Case Library
- Created 40 normalized cases under `normalized/<case_id>/`
- Each case: in.lammps + case.yaml + source.txt
- Coverage: MD, minimize, NEB, shock, elastic, flow, transport, MC, accelerated dynamics, spin, peridynamics, granular, ML potentials, TTM, rerun, triclinic

### Explore Stage 4: Validation Runs
- Ran 7 fast cases locally with lmp_serial, all passed (<4s each)
- Results in `.tmp/engine_research/lammps/runs/RESULTS.md`

---

## 2026-02-06 Session (Implementation Stages 4-7)

### Migration Step
- Created `docs/engines/lammps/` with PHASE_B1_PLAN.md, PHASE_B1_WORKLOG.md, SOURCES.md, EXPLORE_SUMMARY.md
- Raw corpora remain in `.tmp/engine_research/lammps/`

### Stage 5: Output Digest
- Created `src/quantumvitas/drivers/lammps/parsers/__init__.py` and `output.py`
- LAMMPSDigest: 16 fields (success, energy, temp, pressure, atoms, steps, wall_time, minimize stats, etc.)
- LAMMPSOutputParser registered as ("lammps", "scf_digest")
- Parses: thermo blocks (dynamic column detection), Loop time, minimize stats, Total wall time, errors
- Added `from . import parsers` to LAMMPS `__init__.py` for registration
- Verified digest against 3 existing logs: melt_lj_nve, minimize_2d_lj, tersoff_sic — all correct

### Stage 4: Parser/Writer Enhancement
- Complete rewrite of `src/quantumvitas/drivers/lammps/inputspec.py` (~806 lines)
- **4A Script parser** (`_parse_lammps_script_text`):
  - Join continuation lines (`&` at EOL)
  - Strip comments, tokenize line-by-line
  - Dual representation: flat semantic fields + `_commands` list
  - Extracts ~25 key commands: units, atom_style, boundary, dimension, pair_style, pair_coeff (list), fixes (list of dicts), computes, thermo, timestep, run, minimize, etc.
  - Handles unfix/uncompute (removes from accumulated lists)
  - Preserves variable references as literal strings
- **4B Data file parser** (`_parse_lammps_data_text`):
  - Parses header (atom count, types, box bounds, tilt factors)
  - Masses section, Atoms section (auto-detects atomic/charge/full style by column count)
  - Returns StructureDoc-compatible dict with lattice, species, cart_coords, frac_coords
  - `_cart_to_frac()` — Cartesian to fractional via 3x3 inverse
- **4C Writer enhancement**:
  - Stream mode (`_write_from_commands`): faithful write-back from `_commands` list
  - Template mode (`_write_from_flat`): enhanced from original with full bonded/kspace/special_bonds support
  - Data file writer: handles masses, tilt factors, atomic/frac coordinate output
- **4D Wiring**: Parsers wired to both InputFileSpecs; `structure.data` marked `optional=True`
- **Regression check**: 3572 passed, 24 skipped — no regressions

### Stage 4D: Wiring + Curated Samples
- Wired `custom_parser` on both InputFileSpecs in `get_lammps_input_spec()`
- Marked `structure.data` as `optional=True` (many LAMMPS scripts use lattice-create)
- Created 8 curated samples under `tests/inputformat/samples/lammps/`:
  - melt_lj_nve, minimize_2d_lj, peptide_nvt, reaxff_rdx
  - eam_hyper, coreshell, meam_sic, elastic_sw
- All 8 samples parse without error via smoke test

### Stage 7: Tests
- Created `tests/inputformat/test_lammps_parse.py` (88 tests):
  - Script parser: 31 unit tests (commands, fixes, variables, unfix, etc.)
  - Line continuation: 5 tests
  - Data file parser: 9 tests (atomic/charge/full styles, triclinic)
  - Writer: 7 tests (commands mode, flat mode, data file)
  - Curated samples: 16 tests (parametric parse + per-sample field checks)
  - Roundtrip: 9 tests (commands + flat fields + data)
  - Orchestrator: 4 tests (write+parse, optional data)
  - EngineInputSpec: 4 tests (wiring, resources, SSOT, driver)
- Created `tests/inputformat/test_lammps_digest.py` (31 tests):
  - Inline log parsing: 16 tests (MD, minimize, error, lost atoms, empty)
  - Output parser class: 5 tests (can_parse, parse, registration)
  - Validation runs: 7 tests (all existing run logs)
  - Edge cases: 3 tests (wall time, to_dict)
- **Total new tests**: 119
- **All 119 tests pass**, 0 failures

### Stage 6: Validate Against Runs
- All 7 existing run logs parsed correctly (via test_lammps_digest.py TestValidationRuns)
- Verified values: atom counts, step counts, units, minimize convergence, success flags

### Gate Test Fix
- B5 gate scanner flagged `["id"]` in fix/compute dicts as legacy ULID pattern
- Renamed: `"id"` → `"fix_id"` in fix dicts, `"id"` → `"compute_id"` in compute dicts
- Updated inputspec.py, test_lammps_parse.py to use new field names
- Gate test passes clean

### Final Test Run
- **3691 passed, 24 skipped, 0 failed** (+119 new tests from baseline 3572)
- All acceptance criteria met
- Phase B1 COMPLETE
