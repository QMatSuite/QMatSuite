# Phase B1: VASP End-to-End "QE-Depth" — Implementation Plan

## Goal
Bring VASP driver to QE-level maturity: comprehensive INCAR metadata catalog, metadata access layer, expanded example library (12+ cases), parser/writer robustness, vasprun.xml output analyzer, POTCAR staging, and optional real execution framework.

## Baseline
- Tests: 3385 passed, 19 skipped, 0 failures
- VASP driver: ~1,728 lines across 11 files
- Tests: 57 methods across VASP test files
- 1 curated sample (Si SCF)

## Architecture (all new code in `drivers/vasp/`)
```
data/
  __init__.py
  vasp_incar_tags.json    (200+ INCAR tag metadata catalog)
  vasp_metadata.py        (access layer: tag lookup, validation, categories)
io/
  incar.py               (extend: add write_incar_text)
parsers/
  __init__.py
  output.py              (vasprun.xml + OUTCAR digest parser)
engine/
  __init__.py
  vasp_potcar.py          (POTCAR staging)
  vasp_runner.py          (dev-only execution)
```

## Step Dependency Graph
```
Step 1 (Metadata JSON)    Step 3 (Example Library)
         |                         |
         v                         |
Step 2 (Access Layer)              |
         |                         |
         +-------------------------+
         |
         v
Step 4 (Parser/Writer Robustness)
         |
         v
Step 5 (POTCAR Staging)
         |
         v
Step 6 (Output Analyzer)
         |
         v
Step 7 (Execution Framework)
         |
         v
Step 8 (Integration Polish)
```

Steps 1 and 3 can proceed in parallel.

---

## Step 1: INCAR Metadata Catalog JSON
- Create `data/vasp_incar_tags.json` (~200+ tags)
- Schema: name, type, default, category, subcategory, enum, description, see_also, status
- Types: INTEGER, REAL, LOGICAL, CHARACTER, INTEGER_ARRAY, REAL_ARRAY, CHARACTER_ARRAY
- Categories: electronic, ionic, output, symmetry, xc, magnetism, parallelization, hybrid, vdw, gw, response, wannier, ml
- Tests: JSON validation, tag count, required fields, type enum, no duplicates

## Step 2: Metadata Access Layer
- Create `data/vasp_metadata.py` (~250 lines)
- API: safe_load_metadata, get_tag_info, list_tags, list_categories, validate_incar_params, etc.
- Module-level cache with optional hot-reload via env var
- Uses `importlib.resources` anchored at `qmatsuite.drivers.vasp.data`
- Tests: load, lookup, case-insensitive, category filter, validation

## Step 3: Expanded Example Library (12 Cases)
- Restructure flat files into `si_scf/` subdirectory
- Add 11 new cases: si_relax, si_vc_relax, si_bands, si_dos, fe_magnetic, tio2_hubbard, graphene_vdw, al_md, mgo_slab, si_hybrid, gaas_soc
- Each: INCAR + POSCAR + KPOINTS + case.yaml
- Update existing test references (test_vasp_parse.py, test_harness.py, test_vasp_io.py)
- New: test_vasp_corpus.py (iterate all cases, parse, roundtrip, harness)

## Step 4: Parser/Writer Robustness Hardening
- Move INCAR writer from inputspec.py to io/incar.py as `write_incar_text()`
- inputspec.py delegates to io.incar.write_incar_text
- INCAR edge cases: SYSTEM with !/# in value, LDAUU/LDAUL arrays, trailing semicolons
- POSCAR edge cases: negative scale factor, selective dynamics roundtrip
- Tests: writer module, edge cases

## Step 5: POTCAR Staging
- Create `engine/vasp_potcar.py` (~150 lines)
- API: get_default_potcar_root, stage_potcar, list_available_potcars
- Concatenate per-species POTCARs in order
- potcar_overrides for variant selection (e.g., Fe -> Fe_pv)
- Tests: all skipif POTCAR library not found

## Step 6: Output Analyzer (vasprun.xml)
- Create `parsers/output.py` (~350 lines)
- VASPDigest dataclass: energy, structure, convergence, forces, magnetization, etc.
- VASPOutputParser: xml.etree.ElementTree for vasprun.xml, regex for OUTCAR fallback
- @register_parser("vasp", "scf_digest")
- Tests: synthetic vasprun.xml fixture, energy/structure/convergence/forces

## Step 7: Execution Framework + Reference Verification
- Create `engine/vasp_runner.py` (~200 lines) — dev-only, NOT product
- RunResult dataclass, run_vasp_case(), verify_reference()
- conftest.py: vasp_available, potcar_available fixtures
- Tests: all conditional on VASP availability
- ref_values.yaml for si_scf case

## Step 8: Final Integration + Test Count Verification
- Full test suite green
- Test count: baseline 3385 + ~130 new = ~3515 passed
- Skip count: 19 baseline + ~15 VASP-conditional = ~34 skipped
- No kernel imports in new driver code
- inputformat/ leaf package untouched

## Acceptance Criteria
- [x] Full pytest green (3539 passed, 24 skipped)
- [x] INCAR metadata catalog: 232 tags
- [x] Metadata access layer: tag lookup, validation, category listing
- [x] 12 curated cases with 100% parse + roundtrip success
- [x] INCAR writer extracted to io/incar.py module
- [x] vasprun.xml parser produces VASPDigest
- [x] POTCAR staging (where available)
- [x] VASPOutputParser registered: get_parser("vasp", "scf_digest") works
- [x] Si SCF runs successfully on local VASP (conditional)
- [x] No kernel/API surface changes, inputformat leaf untouched
