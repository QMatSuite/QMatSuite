# Gaussian Phase B1 — Deepening Plan (Stages 1–8)

**Status**: COMPLETE
**Baseline**: 3691 passed, 24 skipped
**Engine version**: Gaussian 09 Rev D.01 (local binary at `.qmatsuite/engines/gaussian/gaussian09/g09`)
**Syntax family**: F4 "keyword-block" (shared with ORCA)

---

## Overview

Gaussian uses the F4 "keyword-block" syntax family. Unlike ORCA (which uses `!` keywords, `%...end` blocks, and `*...*` geometry), Gaussian uses:
- **Link0 commands** (`%` prefix): resource directives (`%mem`, `%nproc`, `%chk`)
- **Route section** (`#` prefix): method/basis/keywords on one or more lines
- **Blank-line-delimited sections**: title, charge/mult, geometry, additional input
- **Link1 (`--Link1--`)**: multi-job inputs chaining calculations

Key Gaussian-specific challenges:
1. **Blank lines are structural terminators** — extra blanks break the file
2. **No comment character** — no way to add comments
3. **Section ordering is rigid** — Link0 → route → title → charge/mult → geometry → (extras)
4. **Z-matrix support** — both Cartesian and internal coordinates
5. **Link1 multi-job** — `--Link1--` separator for chained calculations
6. **Route keyword complexity** — nested options like `Opt=(MaxCycles=100,Tight)`

---

## Stage 1: Documentation + Raw Corpus (COMPLETE)

- Crawled 24 pages from official gaussian.com documentation
- 22 markdown files saved to `.tmp/engine_research/gaussian/raw_web/`
- G09 keyword reference from thiele.ruc.dk mirror (90+ keywords)
- 17 representative test examples from G09 test suite
- All sources documented in `docs/engines/gaussian/SOURCES.md`

## Stage 2: Metadata Seed (COMPLETE)

- `gaussian_route_keywords.json` — 45+ methods, 11 job types, 7 properties
- `gaussian_link0_directives.json` — 18 Link0 commands
- `gaussian_grammar_rules.json` — complete grammar specification
- `gaussian_basis_sets.json` — 30+ built-in basis sets

## Stage 3: Normalized Case Library (COMPLETE)

- 14 normalized cases in `.tmp/engine_research/gaussian/normalized/`
- 9 validation runs with g09 (all passed)
- Cases cover: SP, Opt, Opt+Freq, MP2, TDDFT, solvation, open-shell, Z-matrix, NMR, scan, Link1, Gen basis, charged

## Stage 4: Metadata Data File + Access Layer (COMPLETE)

- `drivers/gaussian/data/gaussian_route_keywords.json` — 66 keywords with kind/category/description
- `drivers/gaussian/data/gaussian_metadata.py` — cached access layer following VASP pattern
  - `get_keyword_info()` — case-insensitive lookup with alias support
  - `list_keywords()` — filtered by category
  - `list_builtin_basis_sets()` — 35 built-in basis sets
  - `get_link0_info()` — Link0 directive lookup
  - `validate_route_keywords()` — identify unknown keywords (skips method/basis combos, prefixed methods)

## Stage 5: Enhanced Input Parser (COMPLETE)

- `inputspec.py` now has `custom_parser` wired to `_parse_gaussian_text()`
- Route parser `_parse_route_keywords()` handles:
  - Method/basis combos (B3LYP/6-31G*)
  - Parenthetical options: Opt=(Tight,MaxCycles=100), TD=(NStates=3)
  - Equals-form options: Opt=Tight
  - SCRF=(SMD,Solvent=Water) solvation
  - SCF=(Tight,MaxCycle=128) convergence control
  - EmpiricalDispersion=GD3BJ
  - Composite methods (G1-G4, CBS-QB3, W1U)
  - NoSymm, Integral grid control
- Full input parser handles:
  - Link0 directives (%mem, %nproc, %chk, %oldchk)
  - Multi-line route sections
  - Title section
  - Charge/multiplicity
  - Cartesian coordinates
  - Z-matrix with variables and scan specifications
  - Link1 multi-job (parses first job, counts total)

## Stage 6: Output Parser (COMPLETE)

- `parsers/output.py` — GaussianDigest (23 fields) + GaussianOutputParser
- Registered as `@register_parser("gaussian", "scf_digest")`
- Parses: SCF energy, MP2 (Fortran D notation), optimization convergence, TDDFT states,
  frequencies/ZPE, dipole moment, Standard orientation geometry, elapsed time
- Link1 chain detection (counts normal terminations)
- Hartree→eV conversion
- `__init__.py` triggers parser registration at driver import

## Stage 7: Curated Test Samples (COMPLETE)

- 6 curated .gjf files in `tests/inputformat/samples/gaussian/`:
  - water_hf_sp.gjf, water_b3lyp_opt.gjf, methanol_solvation.gjf
  - water_zmatrix.gjf, formaldehyde_tddft.gjf, hcn_scan.gjf

## Stage 8: Tests (COMPLETE)

- `test_gaussian_parse.py` — 42 tests (route parser, full parser, curated samples, write-parse roundtrip, spec wiring)
- `test_gaussian_digest.py` — 30 tests (inline logs, parser class, registry, 8 validation runs)
- `test_gaussian_metadata.py` — 26 tests (loading, keyword lookup, listing, Link0, validation)
- Total: 98 new tests, all passing

---

## Acceptance Criteria

1. [x] Substantial offline Gaussian corpus in `.tmp/engine_research/gaussian/` with SOURCES.md committed
2. [x] Metadata seed exists with route keywords + grammar rules + provenance
3. [x] Normalized case library with 14 cases and broad workflow coverage
4. [x] At least one Link1 chain case (2 cases: multi_step_link1, formaldehyde_zmatrix_link1)
5. [x] 9 fast cases executed with g09, with run manifests + digests
6. [x] PHASE_B1_WORKLOG.md continuously updated
7. [x] Committable metadata JSON + access layer in `drivers/gaussian/data/`
8. [x] Enhanced input parser with custom_parser for roundtrip
9. [x] Output parser with @register_parser("gaussian", "scf_digest")
10. [x] 98 new tests passing with no regressions

---

## Test Command

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```
