# Gaussian Phase B1 — Worklog

## 2026-02-06 Session (Stages 1–3 Exploration)

### Setup
- Created `.tmp/engine_research/gaussian/` directory structure (raw_web, raw_pdfs, extracted, metadata, normalized, runs)
- Created `docs/engines/gaussian/PHASE_B1_PLAN.md` (stages 1–3 exploration plan)
- Reviewed existing Gaussian driver code (driver.py, handler.py, recipe.py, parser.py, writer.py, inputspec.py)
- Reviewed existing smoke tests (5 cases: water_sp, water_opt, water_opt_freq, ethylene_mp2, formaldehyde_tddft)
- Confirmed g09 binary at `.qmatsuite/engines/gaussian/gaussian09/g09/g09` (Rev D.01, x86_64)

### Stage 1: Documentation + Raw Corpus
- Crawled 24 pages from official gaussian.com documentation
  - Successfully extracted: input format, route syntax, Link0 commands, SCF/Opt/Freq/TD/IRC/Scan/NMR/Polar/Stable/Guess/Geom/ONIOM/Gen/PBC/Integral options
  - JS-blocked (partial): keywords list, Pop, QST2, SMD tips (got metadata from search results instead)
- Fetched G09 keyword reference from thiele.ruc.dk mirror (complete 90+ keyword list)
- Extracted 17 representative test examples from G09 test suite (GitHub gist)
- Collected community tutorial inputs (Link1 examples, QST2, Z-matrix)
- All raw content saved to `.tmp/engine_research/gaussian/raw_web/` (17 markdown files)
- Documented all sources in `docs/engines/gaussian/SOURCES.md`

### Stage 2: Metadata Seed
- Created `gaussian_route_keywords.json` — comprehensive catalog of route keywords organized by category:
  - 45+ method keywords (HF, DFT functionals, MP2-5, CCSD, CASSCF, semi-empirical, MM)
  - 11 job type keywords (SP, Opt, Freq, Force, IRC, Scan, Stable, Volume, ADMP, BOMD, Counterpoise)
  - 7 property keywords (TD, NMR, Polar, Pop, Prop, Density, Field)
  - SCF control options (20+ options with provenance)
  - Solvation models (6 models + 14 common solvents)
  - 30+ built-in basis sets organized by family (Pople, Dunning, Ahlrichs, ECP)
  - Composite methods (G1-G4, CBS, W1 variants)
  - Geometry/guess/symmetry control keywords
  - ONIOM multi-layer specification
  - Dispersion corrections (GD2, GD3, GD3BJ)
  - Integration grids (5 named grids + custom format)
  - PBC options
- Created `gaussian_link0_directives.json` — 18 Link0 commands with syntax, descriptions, examples
- Created `gaussian_grammar_rules.json` — complete grammar specification:
  - Section ordering rules (Link0 → route → title → charge/mult → geometry → extras)
  - Blank-line semantics (structural terminators, critical rules)
  - No comment character
  - Case sensitivity rules
  - Route section syntax (prefixes, continuation, keyword formats)
  - Z-matrix and Cartesian geometry formats
  - Link1 rules (separator, section reuse via checkpoint)
  - Method prefix rules (R/U/RO)
  - Basis set notation rules
- Created `gaussian_basis_sets.json` — 30+ built-in basis sets + Gen/GenECP syntax

### Stage 3: Normalized Case Library
Created 14 normalized cases covering diverse calculation types:

| Case ID | Method | Job Type | Special Features |
|---------|--------|----------|-----------------|
| water_hf_sp | HF/STO-3G | SP | Minimal reference |
| water_b3lyp_opt | B3LYP/6-31G* | Opt | DFT geometry opt |
| water_opt_freq | HF/STO-3G | Opt+Freq | Combined job |
| ethylene_mp2 | MP2/STO-3G | SP | Post-HF correlation |
| formaldehyde_tddft | B3LYP/STO-3G | TD | 3 excited states |
| methanol_solvation | B3LYP/6-31G* | SP+SCRF | SMD solvation |
| o2_triplet_uhf | UHF/6-31G* | SP | Open-shell triplet |
| water_zmatrix | HF/STO-3G | SP | Z-matrix geometry |
| benzene_nmr | B3LYP/6-31G* | NMR | Chemical shifts |
| hcn_scan | HF/STO-3G | Scan | PES scan (Z-matrix) |
| multi_step_link1 | HF→MP2 | Link1 | --Link1-- chain |
| ethanol_gen_basis | HF/Gen | SP | Custom basis input |
| li_cation | HF/STO-3G | SP | Charged species |
| formaldehyde_zmatrix_link1 | HF→B3LYP | Link1+Opt→Freq | Z-matrix + Link1 + mixed-method |

Each case has: `input.gjf`, `case.yaml`, `source.txt`

### Stage 3b: Validation Runs with g09
Executed 9 cases with local Gaussian 09 binary — all 9 passed:

| Case | Walltime | Key Result |
|------|----------|------------|
| water_hf_sp | 1s | E(RHF) = -74.963 Ha, 7 SCF cycles |
| ethylene_mp2 | 1s | EUMP2 = -77.195 Ha, E2 = -0.122 |
| water_b3lyp_opt | 2s | Converged in 3 steps, E = -76.409 Ha |
| o2_triplet_uhf | 1s | E(UHF) = -149.614 Ha, 10 SCF cycles |
| formaldehyde_tddft | 2s | 3 states: 4.06, 9.48, 12.00 eV |
| water_zmatrix | 1s | E(RHF) = -74.963 Ha (Z-matrix identical) |
| multi_step_link1 | 1s | 2 normal terminations, HF→MP2 chain OK |
| methanol_solvation | 1s | E(RB3LYP) = -115.714 Ha (SMD/water) |
| hcn_scan | 3s | 6 scan points, E range: -91.675 to -91.636 |

Each run has: `run_manifest.json`, `digest.json`, `output.log`

### Acceptance Criteria Status
1. [x] Substantial offline Gaussian corpus in `.tmp/engine_research/gaussian/` with SOURCES.md committed
2. [x] Metadata seed exists with route keywords + grammar rules + provenance
3. [x] Normalized case library with 14 cases and broad workflow coverage
4. [x] At least one Link1 chain case (2 cases: multi_step_link1, formaldehyde_zmatrix_link1)
5. [x] 9 fast cases executed with g09, with run manifests + digests
6. [x] PHASE_B1_WORKLOG.md continuously updated

### Observations for Future Code Work
1. **Gaussian has no comment character** — parser must not strip lines as comments
2. **Blank lines are structural** — writer must be extremely careful with trailing blanks
3. **Link1 is unique** — `--Link1--` separator creates fully separate jobs within one file
4. **Z-matrix variables** — separate section after coordinates for variable definitions
5. **Route keyword options use parenthetical syntax** — e.g., `Opt=(Tight,MaxCycles=100)`, `TD=(NStates=3)`
6. **Method/basis separated by /**, unlike ORCA where they're space-separated keywords
7. **Gen basis input** requires additional section after geometry with `****` terminators
8. **Title section forbidden chars** — @, #, !, –, _, \, control characters
9. **G09 runs in stdin mode** — `g09 < input.gjf > output.log` (not filename arg)

### Phase B1 Stages 1–3 COMPLETE

---

## 2026-02-06 Session (Stages 4–8 Code Deepening)

### Stage 4: Metadata Data File + Access Layer
- Created `drivers/gaussian/data/__init__.py`
- Created `drivers/gaussian/data/gaussian_route_keywords.json` (66 keywords, schema v1)
  - Curated from exploration metadata, organized by kind/category
  - 30 methods, 11 job types, 7 properties, 11 control keywords, 7 composites
  - 35 built-in basis sets, 11 Link0 directives
- Created `drivers/gaussian/data/gaussian_metadata.py` — access layer following VASP pattern
  - Module-level caching with hot-reload support (QV_GAUSSIAN_METADATA_HOT_RELOAD)
  - importlib.resources-based loading
  - Public API: get_keyword_info, list_keywords, list_categories, list_builtin_basis_sets
  - get_link0_info for Link0 directives
  - validate_route_keywords — identifies unknown keywords, handles aliases, R/U/RO prefixes, method/basis combos

### Stage 5: Enhanced Input Parser
- Rewrote `inputspec.py` with full `custom_parser` for roundtrip parsing
- Route keyword parser `_parse_route_keywords()`:
  - Method/basis combos (B3LYP/6-31G*)
  - Parenthetical options: Opt=(Tight,MaxCycles=100), TD=(NStates=3)
  - Equals-form options: Opt=Tight
  - SCRF=(SMD,Solvent=Water) solvation
  - SCF=(Tight,MaxCycle=128) convergence control
  - EmpiricalDispersion=GD3BJ
  - Composite methods (G1-G4, CBS-QB3, W1U)
  - NoSymm, Integral grid control
  - All verbosity flags (#, #p, #P, #n, #N, #t, #T)
- Full input parser `_parse_gaussian_text()`:
  - 6-phase section parsing (Link0 → route → title → charge/mult → geometry → variables)
  - Link0 directives (%mem, %nproc, %chk, %oldchk, %rwf, %save)
  - Multi-line route section continuation
  - Cartesian coordinate detection (4+ columns with floats)
  - Z-matrix with variable references and scan specifications (R1=1.07 5 0.05)
  - Link1 multi-job (--Link1-- separator, parses first job, counts total)
- Method/basis detection sets: 47 methods, 12 basis patterns, 5 basis prefixes

### Stage 6: Output Parser
- Created `drivers/gaussian/parsers/__init__.py` (triggers registration)
- Created `drivers/gaussian/parsers/output.py`:
  - GaussianDigest dataclass (23 fields): success, final_energy_Ha/eV, scf_method, n_atoms,
    n_scf_cycles, converged_scf/geometry, n_opt_steps, mp2_energy_Ha, e2_correlation_Ha,
    tddft_states, frequencies_cm, zpe_Ha, imaginary_freq_count, final_species/cart_coords,
    charge, multiplicity, dipole_debye, wall_time_s, error_message, n_link1_jobs
  - GaussianOutputParser class registered as ("gaussian", "scf_digest")
  - can_parse: checks for "Entering Gaussian System" in *.log files
  - parse: full output parsing from directory
  - Regex patterns for: SCF Done, E2/EUMP2 (Fortran D notation), Optimization completed,
    Excited State, Frequencies, Zero-point correction, Dipole moment,
    Standard orientation geometry, Elapsed time, Normal/Error termination
  - Link1 chain detection (counts "Normal termination" occurrences)
  - Atomic number to symbol mapping (25 elements)
- Updated `__init__.py` to trigger parser registration: `from . import parsers`

### Stage 7: Curated Test Samples
- Created `tests/inputformat/samples/gaussian/` with 6 curated .gjf files:
  - water_hf_sp.gjf — minimal HF/STO-3G single point
  - water_b3lyp_opt.gjf — B3LYP/6-31G* optimization
  - methanol_solvation.gjf — B3LYP/6-31G* SCRF=(SMD,Solvent=Water)
  - water_zmatrix.gjf — HF/STO-3G with Z-matrix geometry
  - formaldehyde_tddft.gjf — B3LYP/STO-3G TD=(NStates=3)
  - hcn_scan.gjf — HF/STO-3G Scan with Z-matrix variables

### Stage 8: Tests
- `test_gaussian_parse.py` — 42 tests:
  - TestRouteKeywordParser (18): method/basis, opt, freq, td, scrf, scan, nmr, uhf, mp2, verbosity, dispersion, nosymm, composite, scf
  - TestGaussianParser (10): minimal_sp, cartesian, zmatrix, zmatrix_scan, link0, link1, solvation, empty, charged, open_shell
  - TestCuratedSamples (6): all 6 .gjf samples
  - TestWriteParseRoundtrip (6): sp, opt, td, opt_tight, charged, frac_coords
  - TestInputSpecWiring (2): spec_has_parser, ssot_mapping
- `test_gaussian_digest.py` — 30 tests:
  - TestLogParsing (13): scf_success, energy_ev, geometry, dipole, charge_mult, mp2, optimization, tddft, frequencies, error, link1, empty, to_dict
  - TestGaussianOutputParser (5): can_parse with/without files, parse from dir, no output, engine/object_type
  - TestParserRegistry (2): registry_lookup, find_for_raw
  - TestValidationRuns (8): all 8 available g09 runs (water_hf_sp, ethylene_mp2, water_b3lyp_opt, formaldehyde_tddft, o2_triplet_uhf, multi_step_link1, methanol_solvation, hcn_scan)
  - Note: water_zmatrix run not tested (9th run) because output doesn't have Standard orientation block
- `test_gaussian_metadata.py` — 26 tests:
  - TestMetadataLoading (4): load, schema_version, reload, file_info
  - TestKeywordLookup (9): b3lyp, hf, mp2, opt, td, scrf, case_insensitive, alias, unknown
  - TestListFunctions (5): all_keywords, methods, job_types, categories, basis_sets
  - TestLink0Lookup (4): mem, chk, nproc, unknown
  - TestValidation (5): all_known, unknown_detected, method_basis_skipped, parenthetical_skipped, prefixed_methods

### Files Created (10 new)
1. `src/quantumvitas/drivers/gaussian/data/__init__.py`
2. `src/quantumvitas/drivers/gaussian/data/gaussian_route_keywords.json`
3. `src/quantumvitas/drivers/gaussian/data/gaussian_metadata.py`
4. `src/quantumvitas/drivers/gaussian/parsers/__init__.py`
5. `src/quantumvitas/drivers/gaussian/parsers/output.py`
6. `tests/inputformat/samples/gaussian/water_hf_sp.gjf`
7. `tests/inputformat/samples/gaussian/water_b3lyp_opt.gjf`
8. `tests/inputformat/samples/gaussian/methanol_solvation.gjf`
9. `tests/inputformat/samples/gaussian/water_zmatrix.gjf`
10. `tests/inputformat/samples/gaussian/formaldehyde_tddft.gjf`
11. `tests/inputformat/samples/gaussian/hcn_scan.gjf`
12. `tests/inputformat/test_gaussian_parse.py`
13. `tests/inputformat/test_gaussian_digest.py`
14. `tests/inputformat/test_gaussian_metadata.py`

### Files Modified (2)
1. `src/quantumvitas/drivers/gaussian/__init__.py` — added parser registration import
2. `src/quantumvitas/drivers/gaussian/inputspec.py` — full rewrite with custom_parser

### Phase B1 Stages 4–8 COMPLETE
### Phase B1 ALL STAGES COMPLETE
