# Analysis Objects E2E — Worklog

**Started**: 2026-02-13

## Session 1: 2026-02-13

### Step 0: Baseline
- Full test suite: **5657 passed, 30 skipped**

### Step 2: canonical_match_key + effective_sequence
- [DONE] Added `effective_sequence: list[str]` to `CapabilityMatch` and `AnalysisResult`
- [DONE] Added `match_key: str = ""` to `AnalysisResult`
- [DONE] Added `canonical_match_key()` function to `capability.py`
  - Format: `engine:object_type:seq1+seq2:ulid1,ulid2`
- [DONE] Wired through orchestrator — all 4 AnalysisResult constructors
- [DONE] Replaced 2 ad-hoc match_key constructions in `service.py` (lines 294, 458) with `row.match_key` / `selected.match_key`
- [DONE] Set `effective_sequence=list(cap.gen_step_sequence)` in `enumerate_all_matches()`

### Step 3: ORCA + Gaussian convergence
- [DONE] Created `drivers/orca/parsers/convergence.py` — ORCAConvergenceProvider
  - Parses SCF iteration table, FINAL SINGLE POINT ENERGY, geometry opt cycles
  - Hartree->eV conversion, HURRAY detection
- [DONE] Created `drivers/gaussian/parsers/convergence.py` — GaussianConvergenceProvider
  - Parses E=.../Delta-E=... lines, SCF Done lines, Optimization completed
- [DONE] Added convergence capabilities to ORCA driver (scf + relax)
- [DONE] Added convergence capabilities to Gaussian driver (scf + relax)
- [DONE] Updated both parsers/__init__.py
- [DONE] Created tests: 12 tests for ORCA, 12 tests for Gaussian

### Step 4: GPAW, Psi4, PySCF, QMCPACK convergence
- [DONE] Created `drivers/gpaw/parsers/convergence.py` — GPAWConvergenceProvider
  - Parses `iter: N ... energy ...` lines, `Converged after N iterations`
- [DONE] Created `drivers/psi4/parsers/convergence.py` — Psi4ConvergenceProvider
  - Parses `@DF-RHF iter N: energy delta_E`, `Energy and wave function converged`
- [DONE] Created `drivers/pyscf/parsers/convergence.py` — PySCFConvergenceProvider
  - Parses `cycle= N E= ... delta_E= ...`, `converged SCF energy`
- [DONE] Created `drivers/qmcpack/parsers/convergence.py` — QMCPACKConvergenceProvider
  - Parses scalar.dat block energies, mean energy as ionic step
- [DONE] Added convergence capabilities to all 4 drivers
- [DONE] Updated all 4 parsers/__init__.py
- [DONE] Created tests: 11 GPAW + 11 Psi4 + 11 PySCF + 11 QMCPACK = 44 new tests

### Step 5: ENGINE_ANALYSIS_TYPES elimination
- [DONE] Replaced hardcoded `ENGINE_ANALYSIS_TYPES` dict in `generate_ref_packs_realrun.py` with `_get_engine_analysis_types()` function
  - Dynamically derives from `DriverRegistry.get_driver(engine).ANALYSIS_CAPABILITIES`
  - Updated all 3 call sites
- [DONE] Created `tools/demo_store/analysis_resweep.py`
  - Re-probes analysis over preserved workdirs without engine re-runs
  - Emits per-demo + global coverage report (JSON + log)

### Step 6: Final verification
- [DONE] Full test suite: **5736 passed, 30 skipped** (+79 new tests, 0 regressions)
- [DONE] Smoke test: `canonical_match_key()` produces correct format
- [DONE] Smoke test: All 11 DFT/QC engines now have `convergence` in ANALYSIS_CAPABILITIES
  - Was 5 (VASP, QE, ABINIT, CP2K, Siesta), now 11 (+ORCA, Gaussian, GPAW, Psi4, PySCF, QMCPACK)
- [DONE] Dynamic analysis type derivation confirmed working for all 15 engines

## Files Changed

| Action | File | Lines changed |
|--------|------|---------------|
| MODIFY | `src/qmatsuite/core/analysis/capability.py` | +30 (effective_sequence, match_key, canonical_match_key) |
| MODIFY | `src/qmatsuite/core/analysis/orchestrator.py` | +20 (wire effective_sequence + match_key) |
| MODIFY | `src/qmatsuite/api/service.py` | 2 lines replaced (ad-hoc -> row.match_key) |
| CREATE | `src/qmatsuite/drivers/orca/parsers/convergence.py` | 176 lines |
| MODIFY | `src/qmatsuite/drivers/orca/driver.py` | +8 (capabilities) |
| MODIFY | `src/qmatsuite/drivers/orca/parsers/__init__.py` | +2 |
| CREATE | `src/qmatsuite/drivers/gaussian/parsers/convergence.py` | 161 lines |
| MODIFY | `src/qmatsuite/drivers/gaussian/driver.py` | +8 (capabilities) |
| MODIFY | `src/qmatsuite/drivers/gaussian/parsers/__init__.py` | +2 |
| CREATE | `src/qmatsuite/drivers/gpaw/parsers/convergence.py` | 137 lines |
| MODIFY | `src/qmatsuite/drivers/gpaw/driver.py` | +8 (capabilities) |
| MODIFY | `src/qmatsuite/drivers/gpaw/parsers/__init__.py` | +2 |
| CREATE | `src/qmatsuite/drivers/psi4/parsers/convergence.py` | 143 lines |
| MODIFY | `src/qmatsuite/drivers/psi4/driver.py` | +8 (capabilities) |
| MODIFY | `src/qmatsuite/drivers/psi4/parsers/__init__.py` | +2 |
| CREATE | `src/qmatsuite/drivers/pyscf/parsers/convergence.py` | 131 lines |
| MODIFY | `src/qmatsuite/drivers/pyscf/driver.py` | +8 (capabilities) |
| MODIFY | `src/qmatsuite/drivers/pyscf/parsers/__init__.py` | +2 |
| CREATE | `src/qmatsuite/drivers/qmcpack/parsers/convergence.py` | 137 lines |
| MODIFY | `src/qmatsuite/drivers/qmcpack/driver.py` | +12 (import + capabilities) |
| MODIFY | `src/qmatsuite/drivers/qmcpack/parsers/__init__.py` | +2 |
| MODIFY | `tools/demo_store/generate_ref_packs_realrun.py` | ~20 (dynamic derivation) |
| CREATE | `tools/demo_store/analysis_resweep.py` | 170 lines |
| CREATE | 6 test files (convergence parsers) | ~400 lines total |
| MODIFY | `tests/core/analysis/test_capability.py` | +55 (match_key + eff_seq tests) |
| CREATE | `docs/history/worklogs/ANALYSIS_OBJECTS_E2E_PLAN.md` | plan doc |
| CREATE | `docs/history/worklogs/ANALYSIS_OBJECTS_E2E_WORKLOG.md` | this file |

---

## Session 2-3: 2026-02-13 (Real-Run Baseline + Debugging)

### Step 1: Full Demo Real-Run Baseline
- [DONE] Cleaned staging root: `rm -rf .tmp/refpack_runs/`
- [DONE] Ran full baseline: `python tools/demo_store/generate_ref_packs_realrun.py --keep-workdirs --timeout=600`
- Baseline results: **42 OK, 10 NO_ANALYSIS, 0 FAILED** across 52 demos
- All raw artifacts preserved under `.tmp/refpack_runs/<slug>/`

### Root Cause Analysis: 10 NO_ANALYSIS Failures

| Demo | Engine | Root Cause | Fix |
|------|--------|-----------|------|
| qmcpack_he_vmc | QMCPACK | Parser registration missing — `__init__.py` didn't import parsers | Added `from . import parsers` |
| qmcpack_h2_vmc | QMCPACK | Same as above | Same fix |
| psi4_ethanol_sp | Psi4 | Evidence dir in `step_artifacts/<ulid>/`, not `raw/<ulid>/` | Added step_artifacts fallback in service.py |
| psi4_h2o_opt | Psi4 | Same + `can_parse()` checked "Psi4" (capital) but file has "psi4" (lower) | Fixed case + increased sniff limit |
| psi4_water_scf | Psi4 | Same as above | Same fixes |
| pyscf_h2o_dft | PySCF | Output is `pyscf.log` not `*.out`, parser only checked `*.out` | Added `*.log` patterns |
| pyscf_n2_mp2 | PySCF | Same as above | Same fix |
| pyscf_water_scf | PySCF | Same as above | Same fix |
| gaussian_formaldehyde_tddft | Gaussian | gen_step `td` not in convergence caps (only `scf`, `relax`) | Added `hf`, `td`, `mp2`, `freq` caps |
| gpaw_si_bands | GPAW | gen_step `bandspw` not in convergence caps | Added `bandspw` cap |

### Evidence Directory Resolution (Systemic Fix)
- Engines use 4 different directory layouts in `raw/`:
  1. **SHARED** (QE): All files in `raw/` directly
  2. **ISOLATED with ULID** (VASP): `raw/<step_ulid>/`
  3. **step_artifacts** (Psi4, PySCF, GPAW): `raw/step_artifacts/<step_ulid>/`
  4. **Recipe-created** (ORCA, Gaussian): `raw/<gen_step>_<ulid_suffix>/`
- Created `_find_step_evidence_dir()` static method in QMSService:
  - Checks all 4 patterns in priority order
  - Skips empty dirs (QE creates empty step_artifacts dirs)
  - Used by all 3 evidence resolution paths (post-run, get_analysis, Domain B)

### Additional Parser Fixes
- Psi4 `can_parse()`: Case-insensitive "psi4" check, increased sniff from 2048→8192 bytes
- PySCF `can_parse()`: Added `*.log` pattern alongside `*.out`
- PySCF `_find_output_file()`: Added `pyscf.log` to name list
- Gaussian driver: Added convergence capabilities for `hf`, `td`, `mp2`, `freq`
- GPAW driver: Added convergence capability for `bandspw`

### Daemon Test Regression (Fixed)
- `test_qe_bands_demo_runs_new_analysis_pipeline_end_to_end` was failing
- Root cause: empty `step_artifacts/<ulid>/` dirs for QE were picked over shared `raw/`
- Fix: `any(dir.iterdir())` check ensures non-empty dirs are preferred

### Final Re-Sweep Results
- **52/52 demos with >= 1 analysis object** (was 42/52)
- **70/102 total capability matches resolved** (32 missing = legitimate no-evidence)
- **20 full-match**, 32 partial (partial = field3d/trajectory not produced)
- **0 zero-match**, 0 parser errors
- Missing types are all expected: field3d needs cube files, trajectory needs relaxation output
- Full test suite: **5760 passed, 30 skipped, 0 failed**

### Additional Files Changed (Sessions 2-3)

| Action | File | Change |
|--------|------|--------|
| MODIFY | `src/qmatsuite/api/service.py` | +30 lines: `_find_step_evidence_dir()`, 3-path evidence resolution |
| MODIFY | `src/qmatsuite/drivers/qmcpack/__init__.py` | +1 line: parser import |
| MODIFY | `src/qmatsuite/drivers/psi4/parsers/convergence.py` | Case-insensitive can_parse, 8KB sniff |
| MODIFY | `src/qmatsuite/drivers/pyscf/parsers/convergence.py` | Added *.log patterns |
| MODIFY | `src/qmatsuite/drivers/gaussian/driver.py` | +4 convergence capabilities (hf, td, mp2, freq) |
| MODIFY | `src/qmatsuite/drivers/gpaw/driver.py` | +1 convergence capability (bandspw) |
| REWRITE | `tools/demo_store/analysis_resweep.py` | Shows expected vs actual counts per demo |
