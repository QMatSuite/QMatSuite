# Field3D for ALL Engines — Implementation Plan

## Status: COMPLETE

## Objective

Extend field3d (volumetric data) support from VASP-only to all 11 applicable engines.
Closes Gap 3 from `TRAJECTORY_ANALYSIS_DESIGN.md` compliance review.

## Baseline
- 4980 passed (pre-implementation)
- VASP field3d is the only engine with a field3d parser

## Engine x Field3D Capability Matrix

| Engine | Format | Field Types | Priority | Status |
|--------|--------|-------------|----------|--------|
| **VASP** | VASP volumetric | charge, potential, ELF, partial_charge | DONE | DONE |
| **QE** | .cube/.xsf | charge, potential, ELF, spin, LDOS, STM, orbitals | HIGH | TODO |
| **Wannier90** | .xsf | MLWF orbital densities | HIGH | TODO |
| **CP2K** | .cube | charge, potential, ELF, spin | HIGH | TODO |
| **ABINIT** | .cube (via cut3d) | charge, potential, ELF | MEDIUM | TODO |
| **Siesta** | .cube (via denchar) | charge, potential, LDOS | MEDIUM | TODO |
| **Gaussian** | .cube | charge, spin, MOs, potential | MEDIUM | TODO |
| **ORCA** | .cube | charge, spin, MOs, potential | MEDIUM | TODO |
| **GPAW** | .cube | charge, orbitals, potential | LOW | TODO |
| **Psi4** | .cube | charge, orbitals, potential | LOW | TODO |
| **PySCF** | .cube | charge, orbitals, potential | LOW | TODO |
| LAMMPS | N/A | Classical MD — no electron density | N/A | N/A |
| xTB | N/A | Semi-empirical — no grid output | N/A | N/A |
| QMCPACK | N/A | QMC — non-standard wfn format | N/A | N/A |
| Yambo | N/A | GW/BSE — reciprocal-space only | N/A | N/A |

**Result: 11 engines get field3d, 4 are NOT APPLICABLE.**

## File Format Summary

### Gaussian Cube (.cube) — shared by 9 engines
- Header: 2 comment lines, atom+grid info
- Grid: 3 vectors (step sizes), N1xN2xN3 dimensions
- **Units: Bohr** (must convert to Angstrom at parse time)
- **Data order: Z-fastest** (C order)
- 6 values per line, scientific notation
- N_atoms < 0 → MO cube (multiple datasets)

### XCrySDen XSF (.xsf) — Wannier90, QE
- `BEGIN_BLOCK_DATAGRID_3D` / `BEGIN_DATAGRID_3D_UNKNOWN` block
- **Units: Angstrom** (already correct)
- **Data order: FORTRAN i-fastest** (column-major)

### VASP volumetric — VASP only
- POSCAR header + NGXxNGYxNGZ grid — already implemented

## Architecture

### A. Promote Field3D to shared core
- Move `Field3D` class from `drivers/vasp/parsers/field3d.py` to `core/analysis/field3d.py`
- Update VASP parser/test imports

### B. Shared Gaussian Cube Parser
- `src/quantumvitas/io/parser/cube_parser.py`
- `parse_cube_file(path) -> dict` with Bohr→Angstrom conversion
- `parse_xsf_field3d(path) -> dict` lightweight XSF parser (no BlobStore)

### C. Per-Engine Providers
- Each engine gets `parsers/field3d.py` with `@register_parser(engine, "field3d")`
- All use shared cube/xsf parsers

## Implementation Steps

### Step 0: Baseline — run full test suite
### Step 1a: Promote Field3D to core/analysis/field3d.py
### Step 1b: Create shared cube + XSF parsers
### Step 2: Wannier90 field3d (XSF, existing fixtures)
### Step 3: QE field3d (run pp.x for cube fixtures)
### Step 4: CP2K field3d (run with &PRINT for cube)
### Step 5: ABINIT field3d (run + cut3d for cube)
### Step 6: Siesta field3d (run + denchar for cube)
### Step 7: Gaussian field3d (existing g09 cube fixtures)
### Step 8: ORCA field3d (run with %plots for cube)
### Step 9: GPAW field3d (run Python script for cube)
### Step 10: Psi4 field3d (run cubeprop for cube)
### Step 11: PySCF field3d (run cubegen for cube)
### Step 12: Gate tests
### Step 13: Full suite + worklog

## Dependency Graph

Steps 2-11 are independent (can run in any order).
Steps 2 and 7 are fastest (existing fixtures).
Steps 1a+1b must complete before any engine step.
Step 12 needs all engine steps done.

## File Inventory

### New Files (~25)
- `src/quantumvitas/core/analysis/field3d.py`
- `src/quantumvitas/io/parser/cube_parser.py`
- 10x `drivers/<engine>/parsers/field3d.py`
- 10x `tests/drivers/<engine>/test_*_field3d_parser.py`
- 10x `tests/data/analysis_<engine>_field3d/` fixture dirs

### Modified Files (~25)
- `drivers/vasp/parsers/field3d.py` — import Field3D from core
- `tests/drivers/vasp/test_vasp_field3d_parser.py` — update import
- 10x `parsers/__init__.py` — add field3d imports
- 10x `driver.py` — add ANALYSIS_CAPABILITIES
- `tests/gates/test_analysis_invariants.py` — new gate tests
