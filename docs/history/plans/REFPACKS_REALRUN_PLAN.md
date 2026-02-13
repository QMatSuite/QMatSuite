# Real-Run Reference Packs Plan

## Context

Phase 1 is done: 27 ref packs exist in CanonicalPrimitiveBundle format (from golden test dirs), GUI reference-only mode works. But:

1. **Golden dirs are synthetic** -- they come from `tests/data/` and don't prove the full pipeline works
2. **Only 27/57 demos** have ref packs -- 30 demos have nothing
3. **LAMMPS has no ref packs** -- despite trajectory support being implemented
4. **No trajectory ref packs exist at all** -- only convergence/dos/bands

**Goal**: Generate ref packs from **real daemon runs** for every demo where the engine produces chart-renderable analysis output. This proves the full pipeline: materialize -> run -> parse -> analyze -> serialize.

---

## ALL 15 Engines Are Available Locally

| Engine | Location | Binary |
|--------|----------|--------|
| QE 7.5 | `.qmatsuite/engines/qe/q-e-qe-7.5/bin/` | `pw.x`, `dos.x`, `bands.x`, ... |
| VASP 6.5.0 | `.qmatsuite/engines/vasp/vasp.6.5.0/bin/` | `vasp_std` |
| ORCA 6.1.1 | `.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/` | `orca` |
| ABINIT 10.4.7 | `.qmatsuite/engines/abinit/10.4.7/bin/` | `abinit` |
| Gaussian 09 | `.qmatsuite/engines/gaussian/gaussian09/g09/` | `g09` |
| QMCPACK 4.1.0 | `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/` | `qmcpack` |
| Yambo 5.3.0 | `.qmatsuite/engines/yambo/yambo-5.3.0/bin/` | `yambo` |
| CP2K 2026.1 | `/opt/homebrew/bin/` | `cp2k.psmp` |
| LAMMPS 2025 | `/opt/homebrew/bin/` | `lmp_serial` |
| Siesta 5.4.2 | `/opt/homebrew/Caskroom/miniforge/base/bin/` | `siesta` |
| Psi4 1.10 | `/opt/homebrew/Caskroom/miniforge/base/bin/` | `psi4` |
| xTB 6.7.1 | `/opt/homebrew/Caskroom/miniforge/base/bin/` | `xtb` |
| GPAW 25.7.0 | `.venv/` (pip) | `import gpaw` |
| PySCF 2.12.0 | `.venv/` (pip) | `import pyscf` |
| Wannier90 3.1.0 | `~/src/wannier90-3.1.0/` and QE bundled | `wannier90.x` |

**THERE IS NO FALLBACK. Every ref pack comes from a real engine run through the daemon pipeline.**

---

## Analysis Capabilities Per Engine (from driver.py ANALYSIS_CAPABILITIES)

| Engine | convergence | bands | dos | trajectory | field3d |
|--------|:-----------:|:-----:|:---:|:----------:|:-------:|
| QE | scf/relax/md | bandspw | dos | relax/md | - |
| VASP | scf/relax/md | bandspw | dos | relax/md | pp |
| ABINIT | scf/relax | nscf | nscf | relax/md | - |
| CP2K | scf/relax | bandspw | dos | relax/md | - |
| Siesta | scf/relax | bands | dos | relax/md | - |
| GPAW | - | bandspw | dos | relax/md | scf |
| LAMMPS | - | - | - | md/minimize | - |
| xTB | - | - | - | relax/md | - |
| ORCA | - | - | - | relax | scf |
| Gaussian | - | - | - | relax | scf |
| Psi4 | - | - | - | relax | scf |
| PySCF | - | - | - | relax | scf |
| W90 | - | - | - | - | wannier |
| **Yambo** | **NONE** | - | - | - | - |
| **QMCPACK** | **NONE** | - | - | - | - |

Yambo and QMCPACK have no ANALYSIS_CAPABILITIES -- they run successfully but produce no chart-renderable analysis bundles.

---

## Demo -> Expected Ref Pack Types

### QE (13 demos)
| Demo | Expected |
|------|----------|
| qe_si_scf | convergence |
| qe_al_dos | convergence, dos |
| qe_fe_dos | convergence, dos |
| qe_graphene_bands | convergence, bands |
| qe_si_bands_alt | convergence, bands |
| qe_si_dos_alt | convergence, dos |
| qe_si_vc_relax | convergence |
| qe_si_bulk_modulus | convergence |
| qe_si_phonon | convergence |
| qe_nmr_gipaw | convergence |
| qe_si_cpmd | convergence, trajectory |
| si_bands_demo | convergence, bands |
| si_dos_demo | convergence, dos |

### VASP (5 demos)
| Demo | Expected |
|------|----------|
| vasp_si_scf | convergence |
| vasp_si_relax | convergence |
| vasp_fe_magnetic | convergence |
| vasp_si_bands | convergence, bands |
| vasp_si_dos | convergence, dos |

### ABINIT (3 demos)
| Demo | Expected |
|------|----------|
| abinit_si_scf | convergence |
| abinit_si_relax | convergence |
| abinit_si_bands | convergence, bands |

### CP2K (3 demos)
| Demo | Expected |
|------|----------|
| cp2k_h2o_energy | convergence |
| cp2k_h2o_geo_opt | convergence |
| cp2k_si_relax | convergence |

### Siesta (3 demos)
| Demo | Expected |
|------|----------|
| siesta_si_scf | convergence |
| siesta_si_relax | convergence |
| siesta_si_bands | convergence, bands |

### LAMMPS (3 demos)
| Demo | Expected |
|------|----------|
| lammps_lj_melt | trajectory |
| lammps_lj_minimize | trajectory |
| lammps_peptide_nvt | trajectory |

### xTB (3 demos)
| Demo | Expected |
|------|----------|
| xtb_water_opt | trajectory |
| xtb_water_md | trajectory |
| xtb_caffeine_grad | trajectory |

### GPAW (3 demos)
| Demo | Expected |
|------|----------|
| gpaw_si_scf | (may not produce analysis) |
| gpaw_al_scf | (may not produce analysis) |
| gpaw_si_bands | bands |

### PySCF (3 demos)
| Demo | Expected |
|------|----------|
| pyscf_water_scf | (single-point, trajectory only if relax) |
| pyscf_h2o_dft | (single-point) |
| pyscf_n2_mp2 | (single-point) |

### ORCA (3 demos)
| Demo | Expected |
|------|----------|
| orca_water_sp | (single-point, no trajectory) |
| orca_methane_freq | (freq, no trajectory) |
| orca_formaldehyde_tddft | (TDDFT, no trajectory) |

### Gaussian (3 demos)
| Demo | Expected |
|------|----------|
| gaussian_water_hf | (single-point, no trajectory) |
| gaussian_water_opt | trajectory |
| gaussian_formaldehyde_tddft | (TDDFT, no trajectory) |

### Psi4 (3 demos)
| Demo | Expected |
|------|----------|
| psi4_water_scf | (single-point, no trajectory) |
| psi4_h2o_opt | trajectory |
| psi4_ethanol_sp | (single-point, no trajectory) |

### W90 (3 demos)
| Demo | Expected |
|------|----------|
| w90_copper | field3d (requires wannier_plot=true) |
| w90_diamond | field3d |
| w90_silicon | field3d |

### Yambo (3 demos) -- NO ANALYSIS
### QMCPACK (3 demos) -- NO ANALYSIS

---

## Architecture

### Generator Tool: `tools/demo_store/generate_ref_packs_realrun.py`

Uses `QVService` as the programmatic entry point (same API the daemon uses).

```
For each demo_slug:
  1. QVService.create_demo_project(tmp_dir, demo_slug, demo_slug)
  2. svc = QVService(project_root)
  3. calc = svc.calculation.list()[0]
  4. run_result = svc.run.run_calculation(calc.calc_ulid, run_mode="full")
  5. If run succeeded:
       For each object_type in ENGINE_ANALYSIS_TYPES[engine]:
         try: bundle = svc.analysis.get_analysis(run_ulid, object_type)
         Write bundle to ref_packs/<slug>/
  6. Clean up project dir
```

---

## Implementation Steps

### Step 1: Create generator (DONE)
`tools/demo_store/generate_ref_packs_realrun.py` created.

### Step 2: Fix framework bugs discovered during testing
- `calculation.py:_build_step` slug collision (FIXED: use ULID)
- `calculation.py:from_yaml` ULID extraction (FIXED: check meta.ulid)
- `service.py:run_calculation` structure check too strict (FIXED: allow structureless engines)

### Step 3: Add LAMMPS dump commands to demo YAMLs (DONE)
All 3 LAMMPS demos now have `dump` commands that produce `*.lammpstrj` files.

### Step 4: Run all 57 demos (IN PROGRESS)
Sequential execution, debug failures iteratively.

### Step 5: Update gate test
`tests/gates/test_ref_packs.py` -- parametric (no hardcoded count needed).

### Step 6: Update docs
- `docs/demo_store/DEMO_MATRIX.md` -- updated ref pack counts
- `docs/demo_store/REFPACKS_REALRUN_REPORT.md` -- per-demo results

### Step 7: Full test suite verification

---

## Expected Outcomes

| Category | Count | Source |
|----------|:-----:|--------|
| Real-run ref packs | ~42 | Demos with analysis capabilities |
| No ref pack (expected) | ~15 | Yambo(3) + QMCPACK(3) + single-point molecular(~9) |
| **Total demos** | **57** | |

---

## Files Created/Modified

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `tools/demo_store/generate_ref_packs_realrun.py` | Real-run ref pack generator |
| MODIFY | `src/quantumvitas/calculation/calculation.py` | Fix ULID resolution bugs |
| MODIFY | `src/quantumvitas/api/service.py` | Relax structure check |
| MODIFY | `resources/demo_projects/lammps_*.yml` | Add dump commands |
| REGENERATE | `resources/demo_projects/ref_packs/*/` | All ref pack directories |
| UPDATE | `docs/demo_store/DEMO_MATRIX.md` | Accurate ref pack column |
| CREATE | `docs/demo_store/REFPACKS_REALRUN_REPORT.md` | Per-demo results |
