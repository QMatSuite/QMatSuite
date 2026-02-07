# ABINIT Phase B1 Plan

## Objective
Bring ABINIT engine driver to full B1 Playbook compliance:
- QE-depth metadata catalog
- Extracted IO module (parse + write)
- Output digest parser (@register_parser)
- 10 curated input cases
- Comprehensive test coverage
- No kernel imports in leaf modules

## Pre-existing State
- Driver bundle: driver.py, handler.py, recipe.py, inputspec.py, writer.py, parser.py
- 31 existing tests (11 parse + 20 integration)
- 3 real ABINIT runs in .tmp/engine_research/abinit/runs/
- Golden refs: si_scf.abo, si_relax.abo, si_bands.abo

## Deliverables

### 1. Parameter Metadata Catalog
- `data/abinit_tags.json` — 170+ input variables
- Schema v1 matching VASP pattern
- 20+ categories: structure, kpoints, scf, relaxation, dynamics, spin,
  dftu, gw, dfpt, paw, output, parallel, symmetry, pseudo, memory, etc.

### 2. Metadata Access Layer
- `data/abinit_metadata.py` — module-level cached loader
- API: get_tag_info, list_tags, list_categories, validate_params,
  get_tag_type, get_tag_default, reload_metadata, safe_load_metadata

### 3. IO Module Extraction
- `io/abinit_input.py` — parse_abinit_text + write_abinit_text
- Extracted from inputspec.py (318 -> 59 lines)
- Added: _expand_star (N*value), Fortran d-notation, comment stripping
- Stdlib only, no kernel imports

### 4. Output Digest Parser
- `parsers/output.py` — ABINITDigest (20 fields) + ABINITOutputParser
- @register_parser("abinit", "scf_digest")
- Regex-based parsing of .abo files
- Energy (Ha->eV), forces (Ha/Bohr->eV/A), Fermi, pressure, structure

### 5. Curated Input Cases
- 10 cases under tests/inputformat/samples/abinit/:
  si_scf, si_relax, si_bands, si_dos, si_spin, al_scf, si_dfpt,
  si_vcrelax, fe_magnetic, si_paw
- Each: .abi input + case.yaml metadata

### 6. Tests
- tests/drivers/abinit/test_abinit_metadata.py (21 tests)
  - JSON catalog validation (7 tests)
  - Access layer API (14 tests)
- tests/drivers/abinit/test_abinit_output.py (22 tests)
  - Digest dataclass (2 tests)
  - si_scf golden ref (14 tests)
  - si_relax, si_bands golden refs (5 tests)
  - can_parse + registry (4 tests)
- tests/drivers/abinit/test_abinit_driver.py (38 tests)
  - Registration (6 tests), Isolation (3 tests), InputSpec (2 tests)
  - IO module (5 tests), Corpus parse (20 tests parametrized)
