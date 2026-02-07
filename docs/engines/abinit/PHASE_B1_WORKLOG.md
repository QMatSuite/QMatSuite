# ABINIT Phase B1 Worklog

## Session 1: 2026-02-06

### Assessment
- Audited existing ABINIT driver against B1 Playbook
- Found: driver bundle (6 files), 31 tests, 3 real runs, golden refs
- Missing: data/ (metadata), io/ (extracted), parsers/ (output digest)
- Missing: curated cases (had 1, need 8-12), documentation

### IO Module Extraction (Task #14) — DONE
- Created `io/__init__.py` + `io/abinit_input.py`
- Extracted parse_abinit_text + write_abinit_text from inputspec.py
- Added: _expand_star (N*value), Fortran d-notation, _SYMBOL_TO_Z
- Rewrote inputspec.py to delegate (318 -> 59 lines)
- All 31 existing tests pass unchanged

### Output Digest Parser (Task #15) — DONE
- Created `parsers/__init__.py` + `parsers/output.py`
- ABINITDigest: 20 fields (energy, forces, convergence, structure, timing, etc.)
- ABINITOutputParser: @register_parser("abinit", "scf_digest")
- Helpers: _parse_version, _detect_calc_type, _parse_etotal, _parse_forces,
  _parse_convergence, _parse_final_structure
- Ha->eV: 27.211386245988, Ha/Bohr->eV/A: / 0.529177249

### Metadata Catalog (Task #11) — DONE
- Created `data/abinit_tags.json` — 170+ tags, schema v1
- Categories: basic, structure, kpoints, scf, relaxation, dynamics,
  spin, dftu, gw, dfpt, paw, output, parallel, symmetry, pseudo,
  memory, exchange_correlation, dataset, bse_tddft, wannier

### Metadata Access Layer (Task #12) — DONE
- Created `data/abinit_metadata.py`
- API: safe_load_metadata, get_tag_info, list_tags, list_categories,
  validate_params, get_tag_type, get_tag_default, reload_metadata
- Module-level cache, importlib.resources loading, hot-reload support

### Curated Cases (Task #13) — DONE
- 10 cases under tests/inputformat/samples/abinit/:
  si_scf, si_relax, si_bands, si_dos, si_spin, al_scf, si_dfpt,
  si_vcrelax, fe_magnetic, si_paw
- Each with .abi input file + case.yaml metadata
- Coverage: scf, relax, vc_relax, bands, dos, dfpt, spin-polarized, PAW

### Tests (Task #16) — DONE
- Created tests/drivers/abinit/ with 3 test files:
  - test_abinit_metadata.py: 21 tests (JSON catalog + access layer)
  - test_abinit_output.py: 22 tests (digest, golden refs, registry)
  - test_abinit_driver.py: 38 tests (registration, isolation, IO, corpus)
- Total new tests: 81, all passing
- Full suite: 4288 passed, 24 skipped, 0 failed

### Documentation — DONE
- PHASE_B1_PLAN.md (this file's companion)
- PHASE_B1_WORKLOG.md (this file)
- CURATED_INDEX.md (curated case catalog)

## Test Count Summary
| Component | Tests |
|-----------|-------|
| Metadata JSON catalog | 7 |
| Metadata access layer | 14 |
| Output digest dataclass | 2 |
| si_scf golden ref | 14 |
| si_relax/si_bands golden | 5 |
| can_parse/registry | 4 |
| Driver registration | 6 |
| Driver isolation | 3 |
| InputSpec wiring | 2 |
| IO module | 5 |
| Corpus parse (10 cases x 2) | 20 |
| **TOTAL NEW** | **81** |
| Existing ABINIT tests | 31 |
| **TOTAL ABINIT** | **112** |
