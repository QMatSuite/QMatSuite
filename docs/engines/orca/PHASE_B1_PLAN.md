# ORCA Phase B1 Plan

**Status**: COMPLETE (Stages 1-5, 7; Stage 6 optional)
**Started**: 2026-02-05 (Exploration) / 2026-02-06 (Implementation)
**Baseline**: 3539 passed, 24 skipped
**Constraint**: Follow UNIVERSAL_PARSER_WRITER_DESIGN.md, inputformat as leaf package

---

## Overview

This plan covers the complete ORCA integration from exploration through implementation:
- **Stages 1-3** (COMPLETE): Exploration track — docs, corpus, metadata, normalized cases
- **Stages 4-7** (IN PROGRESS): Implementation track — parser robustness, output digest, tests

**ORCA Syntax Family**: F4 (keyword-block)
- Keyword line: `!` prefix
- Block syntax: `%...end`
- Geometry block: `* xyz ... *`

---

## Stage 1: Documentation + Raw Corpus (COMPLETE)

**Completed**: 2026-02-05

### Objectives
- Collect official ORCA documentation
- Download tutorial materials and community resources
- Clone relevant GitHub repositories with ORCA examples/tools
- Catalog all block types and syntax patterns

### Deliverables

**Downloaded PDFs** (in `.tmp/engine_research/orca/raw_pdfs/`):
| File | Size | Source |
|------|------|--------|
| `ORCA_6.0_Manual.pdf` | 55MB | faccts.de official docs |
| `ORCA_Winter_School_2021.pdf` | 2.5MB | winterschool.cc tutorial |
| `ORCA_TAMU_Intro.pdf` | 500KB | Texas A&M HPRC intro |

**GitHub Repositories** (in `.tmp/engine_research/orca/extracted/`):
| Repository | Purpose |
|------------|---------|
| OrcaNotes | Markdown notes + example inputs |
| ccinput | Python input generator with ORCA support |
| autochem | Python automation with ORCA interface |

**Documentation Created**:
- `CORPUS_INDEX.md` — Complete inventory of all collected materials
- `SOURCES.md` — URLs and access dates for all sources
- Documented all 37 ORCA block types with purposes

### Key Findings
- ORCA uses F4 "keyword-block" syntax family (per UNIVERSAL_PARSER_WRITER_DESIGN.md)
- Input structure: `!` keyword line, `%...end` blocks, `*...*` geometry
- 37 documented block types for detailed configuration
- Extensive keyword catalog for methods, basis sets, convergence, etc.

---

## Stage 2: Metadata Catalog Seed (COMPLETE)

**Completed**: 2026-02-05

### Objectives
- Create comprehensive keyword catalog from documentation analysis
- Map QMatSuite step types to ORCA keywords/settings
- Document block parameters and types

### Deliverables

**Created** (in `.tmp/engine_research/orca/metadata_seed/`):

**`orca_keywords.json`** — Comprehensive keyword catalog:
- Keyword line categories (methods, basis, RI, dispersion, convergence)
- Block definitions with parameters and types
- Geometry input format specifications

**`orca_step_types.json`** — Step type mappings:
- Maps QMatSuite step types (scf, opt, ts, freq, tddft) to ORCA keywords
- Method presets (fast_dft, accurate_dft, gold_standard)

### Metadata Highlights
- 15+ calculation type keywords (SP, OPT, OPTTS, FREQ, NEB, IRC, MD, NMR)
- 20+ block types documented with parameters
- Method categories: HF, GGA-DFT, hybrid-DFT, range-separated, double-hybrid, MP, CC, multireference
- Basis set families: Pople, Karlsruhe (def2), Dunning (cc)
- RI approximations: RI, RIJK, RIJCOSX, RIJONX

---

## Stage 3: Normalized Case Library (COMPLETE)

**Completed**: 2026-02-05

### Objectives
- Create curated test cases covering major ORCA calculation types
- Each case: working `input.inp` + QMatSuite-compatible `metadata.yaml`
- Cover: SCF, optimization, TS, frequencies, TD-DFT, solvation, open-shell, multireference

### Deliverables

**8 Normalized Cases** (in `.tmp/engine_research/orca/normalized/`):

| Case ID | Title | Step Type | Method | Special Features |
|---------|-------|-----------|--------|------------------|
| case_001_water_sp | Water Single-Point | scf | B3LYP/def2-TZVP | D3BJ, RIJCOSX |
| case_002_water_opt | Water Optimization | opt | B3LYP/def2-SVP | Exact Hessian |
| case_003_benzene_tddft | Benzene TD-DFT | tddft | B3LYP/def2-TZVP | 10 excited states |
| case_004_ts_sn2 | SN2 Transition State | ts | B3LYP/def2-SVP | OPTTS, anion |
| case_005_methane_freq | Methane Frequencies | freq | B3LYP/def2-TZVP | Thermochemistry |
| case_006_ethanol_solvation | Ethanol CPCM | opt | B3LYP/def2-TZVP | CPCM solvation |
| case_007_fe_complex_uks | Fe(II) High-Spin | scf | UKS-B3LYP/def2-SVP | Open-shell, S=2 |
| case_008_formaldehyde_casscf | Formaldehyde CASSCF | casscf | CASSCF(4,4)/def2-TZVP | Multireference |

### Coverage Matrix
- [x] Single-point energy
- [x] Geometry optimization
- [x] Transition state
- [x] Vibrational frequencies
- [x] TD-DFT excited states
- [x] Implicit solvation (CPCM)
- [x] Open-shell / unrestricted
- [x] Multireference (CASSCF)

---

## Current State Assessment (Post-Exploration)

### Existing Code
- `drivers/orca/inputspec.py`: Basic parser + writer implemented
  - `_parse_orca_text()`: Handles ! keyword, %blocks, * xyz geometry
  - `_write_orca_text()`: Generates canonical ORCA input
- `tests/inputformat/test_orca_parse.py`: 10 tests, all passing
- `tests/inputformat/samples/orca/benzene_opt.inp`: Curated sample

### Normalized Cases (8 from Stages 1-3)
Located in `.tmp/engine_research/orca/normalized/`:
1. `case_001_water_sp` - Water single-point (B3LYP/def2-TZVP, D3BJ)
2. `case_002_water_opt` - Water optimization with Hessian
3. `case_003_benzene_tddft` - Benzene TD-DFT (10 excited states)
4. `case_004_ts_sn2` - SN2 transition state optimization
5. `case_005_methane_freq` - Methane vibrational frequencies
6. `case_006_ethanol_solvation` - Ethanol with CPCM solvation
7. `case_007_fe_complex_uks` - Fe(II) high-spin (UKS)
8. `case_008_formaldehyde_casscf` - Formaldehyde CASSCF(4,4)

### Gaps Identified
The current parser needs enhancement for:
1. Multi-line `%pal` blocks (current: only single-line `%pal nprocs N end`)
2. `%geom` block with nested sub-blocks (Calc_Hess, Scan, Constraints)
3. `%tddft` / `%cis` blocks
4. `%casscf` blocks
5. Solvation keywords: `CPCM(Water)`
6. Multiple `!` keyword lines (ORCA supports this)
7. Boolean value parsing in blocks (true/false, TRUE/FALSE)
8. Comment lines with `#`

---

## Stage 4: Parser/Writer Robustness

### 4.1 Enhance Parser

**File**: `src/quantumvitas/drivers/orca/inputspec.py`

**Changes**:
1. Multi-line `%pal` block support
2. Nested block parameter support (e.g., `%geom` with `Calc_Hess true`)
3. Boolean parsing (true/false/TRUE/FALSE/True/False)
4. CPCM solvation keyword on `!` line: `CPCM(Water)`
5. Handle comments (`#` lines)
6. Multiple `!` keyword lines merged

**Acceptance Criteria**:
- All 8 normalized cases parse without errors
- Roundtrip: params → write → parse → params matches semantically

### 4.2 Enhance Writer

**Changes**:
1. Multi-line `%pal` block format
2. Proper block formatting with indentation
3. CPCM solvation output
4. Boolean value formatting (lowercase `true`/`false`)

**Acceptance Criteria**:
- Written files parse back to equivalent params
- Output is canonical (consistent formatting)

### 4.3 Test Cases to Add

Add roundtrip tests for all 8 normalized cases:
```python
@pytest.mark.parametrize("case_id", [
    "case_001_water_sp",
    "case_002_water_opt",
    "case_003_benzene_tddft",
    "case_004_ts_sn2",
    "case_005_methane_freq",
    "case_006_ethanol_solvation",
    "case_007_fe_complex_uks",
    "case_008_formaldehyde_casscf",
])
def test_normalized_case_roundtrip(case_id):
    ...
```

---

## Stage 5: Output Analyzer / Digest

### 5.1 Create Output Parser

**File**: `src/quantumvitas/drivers/orca/parsers/output.py`

**Capabilities**:
- Detect convergence/success: Look for `HURRAY` or `****ORCA TERMINATED NORMALLY****`
- Extract final energy: Parse `FINAL SINGLE POINT ENERGY` line
- Extract geometry summary (if optimization): Final coordinates
- SCF convergence status

**Data Structure**:
```python
@dataclass
class ORCADigest:
    success: bool
    final_energy: float | None  # in Hartree
    n_scf_cycles: int | None
    converged: bool
    final_geometry: dict | None  # species + cart_coords
    wall_time: float | None  # in seconds
    error_message: str | None
```

### 5.2 Output Patterns

Key patterns from ORCA output:
```
FINAL SINGLE POINT ENERGY     -76.359831578643
****ORCA TERMINATED NORMALLY****
Total run time: 0 days 0 hours 0 min  3 sec
```

### 5.3 Tests

**File**: `tests/unit/test_orca_output_parser.py`

- Test with sample outputs (stored in `tests/fixtures/orca_outputs/`)
- Test success detection
- Test energy extraction
- Test geometry extraction from optimization

---

## Stage 6: Optional Real Execution

### 6.1 Run Fast Cases

**ORCA Path**: `.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411`

**Fast cases** (< 1 minute):
- `case_001_water_sp` - ~5 seconds
- `case_005_methane_freq` - ~30 seconds

**Classification**:
- Fast: < 1 minute
- Medium: 1-5 minutes
- Slow: > 5 minutes (skip in dev)

### 6.2 Reference Checks

Store under `.tmp/engine_research/orca/runs/<case_id>/`:
```
run_manifest.json   # params, timestamp, ORCA version
output.out          # ORCA output
digest.json         # parsed digest
ref_check.json      # comparison with expected values (if available)
```

### 6.3 Constraints

- NOT in CI (dev-only)
- Mark slow cases with `@pytest.mark.slow`
- Optional skip via `SKIP_ORCA_REAL=1`

---

## Stage 7: Tests

### 7.1 Parser/Writer Tests

**File**: `tests/inputformat/test_orca_parse.py`

Expand existing tests:
- [x] `test_parse_keyword_line`
- [x] `test_parse_geometry_block`
- [x] `test_parse_pal_block`
- [x] `test_parse_maxcore`
- [x] `test_parse_extra_block`
- [x] `test_parse_empty_input`
- [x] `test_curated_sample_parse`
- [ ] `test_parse_multiline_pal`
- [ ] `test_parse_geom_block_with_hess`
- [ ] `test_parse_tddft_block`
- [ ] `test_parse_cpcm_solvation`
- [ ] `test_parse_boolean_values`
- [ ] `test_normalized_case_roundtrip` (parametrized, 8 cases)

### 7.2 Output Parser Tests

**File**: `tests/unit/test_orca_output_parser.py`

- `test_parse_success_detection`
- `test_parse_final_energy`
- `test_parse_scf_cycles`
- `test_parse_geometry`
- `test_parse_error_output`

### 7.3 Integration Tests

**File**: `tests/integration/test_orca_materialize.py`

- `test_materialize_produces_valid_input`
- `test_materialize_roundtrip`

---

## File Inventory

### Files to Create
| File | Purpose |
|------|---------|
| `docs/engines/orca/PHASE_B1_PLAN.md` | This plan |
| `docs/engines/orca/PHASE_B1_WORKLOG.md` | Continuous worklog |
| `docs/engines/orca/SOURCES.md` | Documentation sources |
| `src/quantumvitas/drivers/orca/parsers/output.py` | Output digest parser |
| `tests/unit/test_orca_output_parser.py` | Output parser tests |
| `tests/fixtures/orca_outputs/water_sp.out` | Sample ORCA output |

### Files to Modify
| File | Changes |
|------|---------|
| `src/quantumvitas/drivers/orca/inputspec.py` | Enhanced parser/writer |
| `tests/inputformat/test_orca_parse.py` | Additional roundtrip tests |

### Directories
| Directory | Purpose |
|-----------|---------|
| `.tmp/engine_research/orca/runs/` | Real execution results (dev-only) |
| `tests/fixtures/orca_outputs/` | Sample outputs for testing |

---

## Acceptance Criteria (Summary)

1. **Parser Coverage**: All 8 normalized cases parse successfully
2. **Roundtrip**: YAML → write → parse → YAML matches semantically for all cases
3. **Output Digest**: Extracts energy, success, convergence from ORCA output
4. **Tests Green**: All existing + new tests pass
5. **Documentation**: Plan + worklog maintained in `docs/engines/orca/`

---

## Execution Order

1. Create worklog and sources files
2. Enhance parser (multi-line blocks, booleans, CPCM)
3. Add parser tests for normalized cases
4. Implement output digest parser
5. Add output parser tests
6. (Optional) Run fast cases, record results
7. Final test run, update worklog

---

## Test Command

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

Run frequently to ensure green suite.
