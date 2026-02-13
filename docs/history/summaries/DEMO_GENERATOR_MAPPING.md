# Demo Generator Mapping

**Generated**: 2025-01-XX
**Purpose**: Map each demo generator script to its output demo files.

## Generator Scripts → Demo Outputs

### 1. `tools/generate_demo_snapshots.py`
**Generates**:
- `resources/demo_projects/si_dos_demo.yml`
- `resources/demo_projects/si_bands_demo.yml`

**Source**: Test projects in repo (need to verify exact paths)
**Method**: Uses `export_project_to_snapshot()` to export existing project structures

---

### 2. `tools/generate_wannier90_demo.py`
**Generates**:
- `resources/demo_projects/diamond_wannier90_demo.yml`

**Source**: `.qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/examples/example05/`
**Method**: Manually constructs snapshot from diamond example files
**Issues**: 
- Uses `kpoints` in parameters instead of `K_POINTS` card (line 220)
- Uses step-level prefix/outdir that should be removed

---

### 3. `tools/generate_wannier90_demos.py`
**Generates**:
- `resources/demo_projects/diamond_wannier90_demo.yml`
- `resources/demo_projects/copper_wannier90_demo.yml`
- `resources/demo_projects/silicon_wannier90_demo.yml`

**Source**: `.qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/examples/example05/`, `example06/`, `example16-withqe/`
**Method**: Creates empty step specs, but steps are populated elsewhere (likely via `import_tutorial_datasets.py` or manual editing)
**Issues**:
- Creates steps without parameters initially
- Steps eventually populated with `k_points` in parameters (wrong)

---

### 4. `tools/import_tutorial_datasets.py`
**Generates**:
- `resources/demo_projects/00_Si_scf.yml`
- `resources/demo_projects/01_H2.yml`
- `resources/demo_projects/02_H2O.yml`
- `resources/demo_projects/03_Si_vc_relax.yml`
- `resources/demo_projects/08_Fe_DOS.yml`
- `resources/demo_projects/11_Si_100_surface_reconstruction.yml`
- `resources/demo_projects/15_bulk_modulus_Si.yml`
- `resources/demo_projects/18_H2O_MD.yml`
- `resources/demo_projects/19_Si_CPMD.yml`
- Potentially `silicon_wannier90_demo.yml` (if generated from example16)

**Source**: `tests/data/` folders `0_*` through `19_*`
**Method**: Uses `materialize_project_from_qe_input_folder()` which calls `build_step_spec_from_qe_input()` (should correctly extract K_POINTS as cards)
**Issues**:
- Some generated demos may have `k_points` in parameters (needs investigation)
- May have step-level pseudo mapping fields

---

### 5. `tools/generate_pyscf_demo.py`
**Generates**:
- `resources/demo_projects/water_pyscf_scf.yml`

**Source**: Manually constructed (PySCF water example)
**Method**: Manually constructs snapshot
**Issues**: Unknown (needs verification)

---

### 6. `tools/regenerate_si_bands_demo.py`
**Generates**:
- `resources/demo_projects/si_bands_demo.yml`

**Source**: Likely same as `generate_demo_snapshots.py`
**Method**: Similar to `generate_demo_snapshots.py`

---

## Issues Found

### K_POINTS in parameters (WRONG):
- `silicon_wannier90_demo.yml`: has `k_points` in parameters
- `copper_wannier90_demo.yml`: has `k_points` in parameters
- `diamond_wannier90_demo.yml`: has `kpoints` in parameters (different key name)

### K_POINTS in cards (CORRECT):
- `si_dos_demo.yml`: has `K_POINTS` in cards ✓
- `si_bands_demo.yml`: has `K_POINTS` in cards ✓
- `00_Si_scf.yml` and other numbered demos: have `K_POINTS` in cards ✓

### Step-level pseudo mapping (WRONG):
- `silicon_wannier90_demo.yml`: has `pseudopot`, `pseudo_basename`, `pseudo_sha256`, `pseudo_sha_family` in step-level (should only be in calculation-level `species_map`)

### Step-level prefix/outdir (should be removed):
- `si_dos_demo.yml`: has `prefix` and `outdir` in step parameters (should be injected from calculation.meta.slug)
- Other demos likely have similar issues

---

## Action Items

1. Refactor `generate_wannier90_demo.py` to:
   - Use `build_step_spec_from_qe_input()` to correctly extract K_POINTS as cards
   - Remove step-level prefix/outdir
   - Ensure no step-level pseudo mapping

2. Refactor `generate_wannier90_demos.py` to:
   - Parse QE input files and use `build_step_spec_from_qe_input()` or equivalent
   - Extract K_POINTS as cards, not parameters
   - Remove step-level prefix/outdir

3. Verify `import_tutorial_datasets.py` correctly uses `build_step_spec_from_qe_input()`:
   - Should already be correct, but verify K_POINTS extraction
   - Remove any step-level pseudo mapping fields from output

4. Check `generate_demo_snapshots.py`:
   - Verify K_POINTS are in cards
   - Remove step-level prefix/outdir from exported steps

5. Purge and regenerate all demos after fixes

