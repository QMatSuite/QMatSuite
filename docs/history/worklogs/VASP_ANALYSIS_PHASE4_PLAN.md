# VASP Analysis Phase 4: Arch Debt + PROCAR Fatbands + PDOS Enhancement

## Status: COMPLETE

## Steps

- [x] **Step 0**: Generate VASP fixtures (PROCAR + POSCAR) — real VASP 6.5.0 output
- [x] **Step 1**: Convergence architecture documentation
- [x] **Step 2**: Fix field3d primitive-by-reference
- [x] **Step 3**: Fix trajectory streaming safety
- [x] **Step 4**: PROCAR fatbands (object_type="bands")
- [x] **Step 5**: Enhance PDOS with real atom labels
- [x] **Step 6**: Gate tests
- [x] **Step 7**: Full suite + acceptance

## Dependency Graph

```
Step 0 (fixtures) ──────────────────────┐
Step 1 (convergence docs)  [independent]│
Step 2 (field3d fix)       [independent]│
Step 3 (trajectory fix)    [independent]│
Step 4 (PROCAR) ←── needs Step 0 ──────┘
Step 5 (PDOS labels) ←── needs Step 0b
Step 6 (gates) ←── needs Steps 2, 4
Step 7 (full suite) ←── needs ALL
```

## Worklog

### Step 0: Fixtures
- Ran real VASP 6.5.0 SCF (4x4x4 MP) + bands (3 segments x 5 kpts, LORBIT=11, NBANDS=8)
- PROCAR: 15 kpts x 8 bands x 2 ions x 9 orbitals, 44KB
- Copied real output: PROCAR, EIGENVAL, KPOINTS, POSCAR to `tests/data/analysis_vasp_bands_procar/`
- Stripped vasprun.xml to efermi-only (152 bytes)
- Copied real Si POSCAR from `.tmp/engine_research/vasp/real_run/si_dos/` to `tests/data/analysis_vasp_dos/POSCAR`
- Copied real TiO2 POSCAR from `.tmp/vasp_dos_fixtures/tio2/` to `tests/data/analysis_vasp_dos/POSCAR_tio2`
- Total fixture size: 64KB (well under 200KB limit)

### Step 1: Convergence docs
- Added architecture docstring to VASPConvergenceProvider (one-provider-three-trigger pattern)
- Added routing comment to driver.py ANALYSIS_CAPABILITIES

### Step 2: field3d fix
- Removed `grid_data` from `Field3D.to_primitives()` arrays (primitive-by-reference)
- Added `grid_data_nbytes`, `grid_data_dtype`, `grid_data_available` to volume_metadata
- Updated `test_to_primitives_valid`: asserts `"grid_data" not in canonical.arrays`
- Added `test_grid_data_not_in_bundle` and `test_volume_metadata_grid_info`

### Step 3: trajectory fix
- Rewrote `parse_vasprun_trajectory()` with `ET.iterparse()` + `elem.clear()`
- Added `_extract_species_from_elem()` helper for iterparse-compatible species extraction
- Added `_SIZE_WARN_THRESHOLD = 100MB` constant
- Added size warning in provider when vasprun.xml > threshold and XDATCAR exists
- Added `test_parse_uses_iterparse` and `test_size_warn_threshold_exists`

### Step 4: PROCAR fatbands
- Added `projections` (Optional[ndarray]) and `projection_labels` (Optional[Dict]) to BandStructure
- Validation: projections must be 4D, shape[0]==n_kpoints, shape[1]==n_bands
- `to_primitives()`: adds projections/projection_labels to arrays, fatband display hints to extra
- Display hints: has_projections, projection_shape, fatband_display_hint="width", fatband_width_eV=0.5
- Implemented `parse_procar()` in bands.py with regex-based PROCAR parser
- Integrated PROCAR in VASPBandsProvider.parse(): auto-detects, reads species from POSCAR
- Updated `to_dict()/from_dict()` for projections roundtrip
- 9 new tests: header, shape, labels, physics, integrated, primitives, display hints, SHA, no-procar

### Step 5: PDOS labels
- Fixed DOSCAR PDOS parser to handle per-atom header lines (was broken for all PDOS files!)
- Added POSCAR species reading in VASPDOSProvider.parse() for real atom labels
- py4vasp convention: "Ti_1", "Ti_2", "O_1", "O_2", "O_3", "O_4"
- 2 new tests: TiO2 labels from POSCAR, generic labels without POSCAR

### Step 6: Gate tests
- `test_field3d_bundle_excludes_full_grid`: source inspection gate
- `test_band_structure_supports_projections`: dataclass field gate

### Step 7: Full suite
- 4646 passed, 0 failed, 20 skipped (up from 4630 in Phase 3)
- +16 new tests total
