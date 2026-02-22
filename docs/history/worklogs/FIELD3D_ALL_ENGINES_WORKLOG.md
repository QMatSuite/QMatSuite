# Field3D for ALL Engines — Worklog

## Status: COMPLETE

## Baseline
- 4979 passed, 20 skipped

## Final
- 5085 passed, 19 skipped (+106 new tests, 0 failures)

## Changes Summary

### Shared Infrastructure (Step 1)

**1a. Promoted Field3D to core** (`src/qmatsuite/core/analysis/field3d.py`)
- Moved Field3D class from `drivers/vasp/parsers/field3d.py` to shared core location
- Added class-level `meta: AnalysisObjectMeta` annotation (required by Inv-A2 gate)
- Updated imports in VASP parser and test

**1b. Created shared parsers** (`src/qmatsuite/io/parser/cube_parser.py`)
- `parse_cube_file()`: Full Gaussian cube parser with Bohr->Angstrom conversion
  - Handles MO cubes (negative N_atoms), Z->symbol mapping, grid reconstruction
- `parse_xsf_field3d()`: Lightweight XSF DATAGRID_3D parser (no BlobStore dependency)
  - Handles PRIMVEC, PRIMCOORD, DATAGRID_3D blocks
- Constant: `BOHR_TO_ANGSTROM = 0.529177249`

### Per-Engine Providers (Steps 2-11)

All 10 new engines + VASP (existing) = 11 total field3d providers.

| Engine | Provider Class | Format | field_kind Detection | Fixture Source |
|--------|---------------|--------|---------------------|----------------|
| VASP | VASPField3DProvider | VASP volumetric | Filename map | Existing |
| W90 | W90Field3DProvider | XSF | Fixed "mlwf_density" | Existing XSF files |
| QE | QEField3DProvider | Cube/XSF | Comment line | pp.x run (Si SCF) |
| CP2K | CP2KField3DProvider | Cube | Filename pattern | CP2K run (H2O) |
| ABINIT | ABINITField3DProvider | Cube | Filename pattern | abinit+cut3d (Si) |
| Siesta | SiestaField3DProvider | Cube | Filename pattern | siesta+macroave (Si) |
| Gaussian | GaussianField3DProvider | Cube | Comment line | Existing g09 cube |
| ORCA | ORCAField3DProvider | Cube | Filename pattern | ORCA run (H2O) |
| GPAW | GPAWField3DProvider | Cube | Filename pattern | GPAW script (H2) |
| Psi4 | Psi4Field3DProvider | Cube | Filename pattern | Psi4 cubeprop (H2O) |
| PySCF | PySCFField3DProvider | Cube | Filename pattern | PySCF cubegen (H2O) |

### Fixture Grid Shapes

| Engine | Grid | Total Points | Species |
|--------|------|-------------|---------|
| W90 | 54x54x54 | 157,464 | C, C |
| QE | 24x24x24 | 13,824 | Si, Si |
| CP2K | 20x20x20 | 8,000 | O, H, H |
| ABINIT | 20x20x20 | 8,000 | Si, Si |
| Siesta | 20x20x20 | 8,000 | Si x15 |
| Gaussian | 40x40x20 | 32,000 | O, H, F |
| ORCA | 20x20x20 | 8,000 | O, H, H |
| GPAW | 10x10x10 | 1,000 | H, H |
| Psi4 | 41x56x47 | 107,912 | O, H, H |
| PySCF | 20x20x20 | 8,000 | O, H, H |

### Driver Updates

All 11 drivers updated with `ANALYSIS_CAPABILITIES` entries for field3d:
- `gen_step_sequence=["scf"]` for most engines
- `gen_step_sequence=["wannier"]` for W90
- `evidence_files=["*.cube"]` for cube-based engines
- `evidence_files=["*_00001.xsf"]` for W90

### Gate Tests (Step 12)

Added to `tests/gates/test_analysis_invariants.py`:
- `test_field3d_parser_matrix` — parametrized for 11 engines (11 tests)
- `test_field3d_engine_has_analysis_capabilities` — 11 engines declare field3d (11 tests)
- `test_field3d_core_importable` — Field3D importable from core
- `test_field3d_cube_parser_importable` — shared parsers importable

## New File Inventory

### Source Files (12 new)
- `src/qmatsuite/core/analysis/field3d.py` (promoted from VASP)
- `src/qmatsuite/io/parser/cube_parser.py`
- `src/qmatsuite/drivers/{w90,qe,cp2k,abinit,siesta,gaussian,orca,gpaw,psi4,pyscf}/parsers/field3d.py` (10 files)

### Test Files (10 new)
- `tests/drivers/{w90,qe,cp2k,abinit,siesta,gaussian,orca,gpaw,psi4,pyscf}/test_*_field3d_parser.py`

### Fixture Directories (10 new)
- `tests/data/analysis_{w90,qe,cp2k,abinit,siesta,gaussian,orca,gpaw,psi4,pyscf}_field3d/`

### Modified Files
- `src/qmatsuite/drivers/vasp/parsers/field3d.py` — import Field3D from core
- `tests/drivers/vasp/test_vasp_field3d_parser.py` — update import
- `tests/gates/test_analysis_invariants.py` — update import + new gate tests
- 10x `drivers/<engine>/parsers/__init__.py` — add field3d imports
- 10x `drivers/<engine>/driver.py` — add field3d ANALYSIS_CAPABILITIES

## Test Count Breakdown

| Category | Count |
|----------|-------|
| VASP field3d (existing) | 12 |
| W90 field3d | 8 |
| QE field3d | 8 |
| CP2K field3d | 8 |
| ABINIT field3d | 8 |
| Siesta field3d | 8 |
| Gaussian field3d | 8 |
| ORCA field3d | 8 |
| GPAW field3d | 8 |
| Psi4 field3d | 8 |
| PySCF field3d | 8 |
| Gate tests (field3d) | 25 |
| **Total new** | **+106** |
