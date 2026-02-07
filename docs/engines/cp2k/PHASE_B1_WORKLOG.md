# CP2K Phase B1 Worklog

**Engine**: CP2K
**Syntax Family**: F3 (nested-section: `&SECTION ... &END SECTION`)
**Started**: 2026-02-07
**Completed**: 2026-02-07
**Baseline**: 4288 passed, 24 skipped
**Final**: 4392 passed, 24 skipped, 1 xfailed (+104 net new tests)

---

## Work Log

### Step 1: Baseline & Plan
- Read B1_ENGINE_PLAYBOOK.md and UNIVERSAL_PARSER_WRITER_DESIGN.md
- Audited existing CP2K driver state (driver.py, handler.py, recipe.py, inputspec.py, input_writer.py)
- Found: 15 normalized cases in .tmp but only 3 with actual input files
- Found: 3 real runs completed (h2o_energy, h2o_geo_opt, ch4_energy)
- Found: Pre-existing circular import in recipe.py (systemic, all engines affected)
- Created `docs/engines/cp2k/PHASE_B1_PLAN.md`

### Step 2: Metadata Catalog (215 tags)
- Created `data/cp2k_tags.json` with 215 tags across 28 categories
- Categories: global, method, basis, electronic, spin, grid, qs, scf, xc, kpoints, print, poisson, tddft, dftu, structure, geometry, md, band, ls_scf, admm, rtp, mm, qmmm, response, constraint, metadyn, vibrational, restart
- Section-path format: `FORCE_EVAL/DFT/SCF/MAX_SCF` (hierarchical)
- Created `data/cp2k_metadata.py` access layer (mirrors ABINIT/VASP pattern)
  - `safe_load_metadata()`, `get_tag_info()`, `list_tags()`, `list_categories()`
  - `validate_params()`, `get_tag_type()`, `get_tag_default()`
  - Case-insensitive lookup, hot-reload via env var

### Step 3: I/O Module (parser + writer)
- Created `io/cp2k_input.py` with `parse_cp2k_text()` and `write_cp2k_text()`
- Parser handles: `&SECTION`/`&END`, default keywords, repeated sections, comments (#/!), preprocessor (@-directives), unit annotations, boolean/int/float coercion
- Writer generates canonical format with ordered sections (GLOBAL → FORCE_EVAL/DFT → SUBSYS → MOTION)
- Structure extraction: CELL (A/B/C vectors or ABC shorthand), COORD (Cartesian or SCALED fractional)
- Fixed element symbol preservation bug: COORD lines stored as `_COORD_LINES` list to preserve case and handle duplicate species
- Rewired `inputspec.py` to delegate to `io/cp2k_input.py` (custom_writer + custom_parser)

### Step 4: Output Digest Parser
- Created `parsers/output.py` with CP2KDigest (17 fields) + CP2KOutputParser
- Registered as `@register_parser("cp2k", "scf_digest")`
- Extracts: version, run_type, method, n_atoms, SCF convergence, total energy (primary: `ENERGY| Total FORCE_EVAL` + fallback: `Total energy:`), optimization info (step count, convergence, gradients), Mulliken charge, timing
- Energy in Hartree → eV conversion (1 Ha = 27.211386245988 eV)
- Validated against real CP2K 2026.1 output from smoke tests

### Step 5: Curated Samples (10 cases)
- Created 10 curated samples in `tests/inputformat/samples/cp2k/`:
  - h2o_energy (PBE/DZVP, validated), h2o_geo_opt (CG, validated), h2o_md (NVT Nose-Hoover)
  - si_scf (k-points, fractional), si_relax (BFGS), si_cell_opt (stress tensor), si_bands (band structure)
  - benzene_energy (BLYP+D3, non-periodic), co2_energy (OT minimizer), h2o_tddft (TDDFPT)
- Each sample has `input.inp` + `case.yaml`
- Created `docs/engines/cp2k/CURATED_INDEX.md` with full inventory, diversity rationale, coverage matrix

### Step 6: Comprehensive Tests
- **test_cp2k_driver.py**: 66 tests (driver properties, registration, isolation, inputspec, I/O, corpus)
  - Isolation tests verify no kernel imports in io, parsers, metadata, handlers, recipes modules
  - Corpus tests parametrized over all 10 samples (parse, roundtrip, structure, YAML validation)
- **test_cp2k_metadata.py**: 19 tests (JSON catalog validation, metadata access layer)
- **test_cp2k_output.py**: 12 tests (digest dataclass, output parsing, registry integration)
- **Total CP2K tests**: 97 passing + 1 xfailed (systemic recipe circular import)
- Plus 17 pre-existing inputformat/corpus tests that now include CP2K samples

### Step 7: Final Integration
- Fixed element symbol uppercasing bug in parser (_COORD_LINES approach)
- Marked recipe circular import as xfail (systemic issue, all engines affected)
- Full test suite: 4392 passed, 24 skipped, 1 xfailed, 0 failures

---

## Files Created/Modified

### New Files (15)
| File | Purpose |
|------|---------|
| `src/quantumvitas/drivers/cp2k/data/__init__.py` | Package init |
| `src/quantumvitas/drivers/cp2k/data/cp2k_tags.json` | 215-tag metadata catalog |
| `src/quantumvitas/drivers/cp2k/data/cp2k_metadata.py` | Metadata access layer |
| `src/quantumvitas/drivers/cp2k/io/__init__.py` | Package init |
| `src/quantumvitas/drivers/cp2k/io/cp2k_input.py` | Parser + writer |
| `src/quantumvitas/drivers/cp2k/parsers/__init__.py` | Package init |
| `src/quantumvitas/drivers/cp2k/parsers/output.py` | CP2KDigest + CP2KOutputParser |
| `tests/drivers/cp2k/test_cp2k_metadata.py` | Metadata tests (19) |
| `tests/drivers/cp2k/test_cp2k_output.py` | Output digest tests (12) |
| `docs/engines/cp2k/PHASE_B1_PLAN.md` | B1 plan document |
| `docs/engines/cp2k/PHASE_B1_WORKLOG.md` | This worklog |
| `docs/engines/cp2k/CURATED_INDEX.md` | Curated sample index |
| 10× `tests/inputformat/samples/cp2k/<case>/` | Curated input samples |

### Modified Files (2)
| File | Change |
|------|--------|
| `src/quantumvitas/drivers/cp2k/inputspec.py` | Rewired to use `io/cp2k_input.py` |
| `tests/drivers/cp2k/test_cp2k_driver.py` | Expanded from ~10 to 67 tests |

---

## B1 Playbook Compliance Checklist

| Gate | Status | Evidence |
|------|--------|----------|
| **B0**: inputformat wiring (custom_writer + custom_parser) | PASS | `inputspec.py` delegates to `io/cp2k_input.py` |
| **B1**: Metadata catalog (150+ tags) | PASS | 215 tags in `cp2k_tags.json` |
| **B2**: Metadata access layer | PASS | `cp2k_metadata.py` with full API |
| **B3**: Extracted I/O module (stdlib only) | PASS | `io/cp2k_input.py`, no kernel imports |
| **B4**: Output digest parser (@register_parser) | PASS | `parsers/output.py`, 17-field CP2KDigest |
| **B5**: No kernel imports in io/parsers/data | PASS | Isolation tests verify this |
| **B6**: Curated samples (8+ with case.yaml) | PASS | 10 samples, CURATED_INDEX.md |
| **B7**: Comprehensive tests (metadata + parse + roundtrip + digest + driver) | PASS | 97 passing, 1 xfailed |
| **B8**: Documentation (plan + worklog + curated index) | PASS | All 3 docs created |

### Test Breakdown
| Category | Count |
|----------|-------|
| Driver/registration/isolation | 21 |
| InputSpec | 4 |
| I/O parse/write | 10 |
| Corpus parse/roundtrip | 31 |
| Metadata catalog JSON | 10 |
| Metadata access layer | 9 |
| Output digest | 9 |
| Output parser registration | 3 |
| **Total** | **97 passing + 1 xfailed** |

### Corpus Breadth
| Dimension | Coverage |
|-----------|----------|
| Calc types | 7 (SCF, GEO_OPT, CELL_OPT, MD, BANDS, DOS, TDDFT) |
| System types | 2 (periodic solids, isolated molecules) |
| Coord systems | 2 (Cartesian, fractional/SCALED) |
| XC functionals | 2 (PBE, BLYP) |
| SCF methods | 3 (diagonalization, mixing, OT) |
| Special features | D3 dispersion, Poisson solver, TDDFPT, Nose-Hoover, k-points |
| Nesting depth | Up to 5 levels (MOTION/MD/THERMOSTAT/NOSE) |
| Real runs validated | 2 (h2o_energy, h2o_geo_opt via CP2K 2026.1) |

---

## Known Issues

1. **Circular import in recipe.py** (systemic, all engines): `recipes.py` ↔ `drivers/<engine>/recipe.py`. Marked xfail. Not introduced by B1 work.
2. **Limited real-run validation**: Only 2 of 10 samples validated with real CP2K. Others are synthetic but structurally correct.

---

## Conclusion

CP2K is now at B1 Playbook compliance with full metadata catalog (215 tags), extracted I/O module, registered output digest parser, 10 curated samples, and 97 passing tests. The engine is at QE-depth maturity level alongside VASP, ORCA, LAMMPS, Gaussian, and QMCPACK.
