# M1: Fix Demo Snapshots

## Scope

Fix all 20 demo YAML snapshots to have explicit `engine_family` and correct `step_type_spec` prefixes.

## Prerequisites

M0 must be complete (ENGINE_ROLE + COMPANION_ENGINES on all drivers, gate tests exist).

## Exact File List

### Modify (20 files)

All files in `resources/demo_projects/*.yml`:

**ORCA demos (fix step_type_spec AND add engine_family)**:
1. `resources/demo_projects/water_orca_scf.yml`
2. `resources/demo_projects/methane_orca_freq.yml`
3. `resources/demo_projects/formaldehyde_orca_tddft.yml`

**QE demos (add engine_family: qe)**:
4. `resources/demo_projects/00_Si_scf.yml`
5. `resources/demo_projects/03_Si_vc_relax.yml`
6. `resources/demo_projects/04_Si_DOS.yml`
7. `resources/demo_projects/06_Al_DOS.yml`
8. `resources/demo_projects/07_Si_bandStructure.yml`
9. `resources/demo_projects/08_Fe_DOS.yml`
10. `resources/demo_projects/09_Si_phonon.yml`
11. `resources/demo_projects/12_NMR_gipaw.yml`
12. `resources/demo_projects/13_graphene.yml`
13. `resources/demo_projects/15_bulk_modulus_Si.yml`
14. `resources/demo_projects/19_Si_CPMD.yml`
15. `resources/demo_projects/si_bands_demo.yml`
16. `resources/demo_projects/si_dos_demo.yml`

**W90 demos (add engine_family: qe — NOT w90)**:
17. `resources/demo_projects/copper_wannier90_demo.yml`
18. `resources/demo_projects/diamond_wannier90_demo.yml`
19. `resources/demo_projects/silicon_wannier90_demo.yml`

**PySCF demo (add engine_family: pyscf)**:
20. `resources/demo_projects/water_pyscf_scf.yml`

## Do NOT Touch

- Any Python source files
- Any GUI files
- Any test files (gate tests already exist from M0)

## Exact Instructions

### Step 1: Fix ORCA demos

**water_orca_scf.yml**: Find `step_type_spec: qe_scf` and change to `step_type_spec: orca_scf`. Verify `engine_family: orca` is already present.

**methane_orca_freq.yml**: Find `step_type_spec: qe_scf` and change to `step_type_spec: orca_scf`. Verify `engine_family: orca` is already present.

**formaldehyde_orca_tddft.yml**: Find `step_type_spec: qe_scf` and change to `step_type_spec: orca_scf`. Find `step_type_spec: pyscf_td` and change to `step_type_spec: orca_td`. Verify `engine_family: orca` is already present.

### Step 2: Add engine_family to QE demos

For each of the 13 QE-only demos (files 4-16), add `engine_family: qe` at the calculation level. The field goes as a sibling of `mode:` and `working_dir:`.

Example — before:
```yaml
calculations:
  - meta:
      ...
    mode: normal
    working_dir: raw
    steps:
```

After:
```yaml
calculations:
  - meta:
      ...
    mode: normal
    working_dir: raw
    engine_family: qe
    steps:
```

### Step 3: Add engine_family to W90 demos

For the 3 Wannier90 demos (files 17-19), add `engine_family: qe` (NOT `w90`!). The base family is QE because the QE steps (scf, nscf, pw2wannier) are the base computation. W90 steps are companions.

### Step 4: Add engine_family to PySCF demo

For `water_pyscf_scf.yml`, add `engine_family: pyscf`.

## Invariants to Preserve

- `engine_family` must be at the calculation level (under `calculations[0]`), NOT at project level
- W90 demos use `engine_family: qe`, NOT `engine_family: w90`
- Do NOT change any step parameters, structure data, or meta fields
- Do NOT change step_type_spec values for QE/W90/PySCF demos (they are correct)
- Do NOT add structure_kind if it's not already there (optional field)

## Verifiers

```bash
# 1. Demo integrity gate passes
source .venv/bin/activate && python -m pytest tests/gates/test_demo_integrity.py -v

# 2. All 20 demos have engine_family
grep -c "engine_family:" resources/demo_projects/*.yml
# Expected: each file shows count >= 1, total = 20

# 3. ORCA demos have correct step_type_spec
grep "step_type_spec:" resources/demo_projects/water_orca_scf.yml
# Expected: orca_scf

grep "step_type_spec:" resources/demo_projects/formaldehyde_orca_tddft.yml
# Expected: orca_scf and orca_td

# 4. Full test suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

## Do NOT Do

- Do NOT set `engine_family: w90` on W90 demos (use `qe`)
- Do NOT modify Python code
- Do NOT remove any existing fields from demos
- Do NOT add new steps to demos
- Do NOT change meta ULIDs
- Do NOT reformat the YAML (preserve existing indentation)
