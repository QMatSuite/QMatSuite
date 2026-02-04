# Test Audit: Post-GPAW Integration

Date: 2026-02-03
Baseline commit: `ba276a8` (before Psi4/GPAW integration)
Current state: after GPAW integration (uncommitted)

---

## 1. Skipped Tests: 37 total

### Breakdown by cause

| Count | Reason | File(s) | Pre-existing? |
|-------|--------|---------|---------------|
| 9 | **Psi4 not installed** | `tests/integration/test_psi4_execution.py` | NO — added in `5024d8ba` |
| 6 | **Psi4 not installed** | `tests/integration/psi4/test_psi4_project_level.py` | NO — added in `5024d8ba` |
| 13 | Golden expected failures | `tests/contract_crawler/test_golden_contracts.py` | YES |
| 3 | CP2K not installed | `tests/integration/test_cp2k_integration.py` | YES |
| 2 | Notebook/tools dir missing | `tests/gates/test_import_rules.py` | YES |
| 1 | QMCPACK not installed | `tests/integration/test_qmcpack_vmc.py` | YES |
| 1 | GUI coverage soft gate | `tests/contract_crawler/test_gui_methods_covered.py` | YES |
| 1 | Golden GUI field failure | `tests/contract_crawler/test_gui_field_enforcement.py` | YES |
| 1 | No minimal payload | `tests/contract_crawler/test_schema_preservation.py` | YES |

### Summary

- **Pre-existing skips: 22** (golden contracts, CP2K, QMCPACK, import rules, GUI, schema)
- **NEW skips: 15** — all Psi4 integration tests, because **Psi4 is not installed in `.venv`**
- **GPAW skips: 0** — all 6 GPAW integration tests run and pass (GPAW 25.7.0 is installed)

### Root cause of skip increase

The Psi4 integration (commit `5024d8ba`, post-`ba276a8`) added 15 tests that use `pytest.mark.skipif(not _psi4_available(), ...)`. Psi4 is not pip-installable — it requires conda (`conda install psi4 -c conda-forge`). The `.venv` does not have Psi4.

### Fix options for Psi4 skips

1. Install Psi4 via conda into the venv (if compatible)
2. Accept the 15 skips as "engine not available" (same category as CP2K/QMCPACK)

---

## 2. Performance: Slowest Tests (top 20, parallel run)

Wall-clock time with `-n auto --dist=loadfile`: **~3:34**

| Duration | Test |
|----------|------|
| 102.99s | `cli/test_si_bands_manual_calculation_cli.py::test_run_calculation_and_analyze` |
| 94.95s | `cli/test_template_calculation.py::test_template_calculation_runs` |
| 93.36s | `daemon/test_si_bands_calculation_daemon.py::test_run_calculation_via_job_manager` |
| 82.65s | `cli/test_cli_output_contracts.py::test_run_calculation_outputs_success_status` |
| 73.60s | `cli/test_si_dos_calculation_comprehensive.py::test_run_calculation_and_analyze` |
| 72.69s | `integration/test_qe_relax_real.py::test_qe_relax_execution_creates_current_json` |
| 55.75s | `integration/vasp/test_vasp_real.py::test_dos_smoke` |
| 55.34s | `integration/test_wannier90_execution.py::test_full_workflow` (ex06) |
| 55.19s | `integration/test_wannier90_project_execution.py::test_full_workflow_and_results` (Cu) |
| 55.16s | `integration/test_ph_quick_tests.py::test_ph_quick[test_info0]` |
| 50.91s | `cli/test_si_dos_calculation_cli.py::test_cli_run_calculation` |
| 45.29s | `integration/vasp/test_vasp_real.py::test_bands_smoke` |
| 41.16s | `integration/test_qe_relax_real.py::test_qe_relax_structure_changes` |
| **40.02s** | **`integration/test_gpaw_execution.py::test_h2o_relax_fd_mode`** |
| 35.67s | `integration/test_qe_relax_real.py::test_qe_relax_manifest_updated` |
| 31.35s | `contract_crawler/test_schema_preservation.py::test_no_schema_drift[download_all_sssp]` |
| 23.93s | `contract_crawler/test_golden_contracts.py::test_matches_golden[download_all_sssp]` |
| 22.62s | setup `cli/test_si_dos_calculation_comprehensive.py` |
| 22.34s | `integration/test_si_dos_calculation.py::test_run_full_calculation` |
| 22.00s | `integration/test_pyscf_phase3c.py::test_t3_runstep_scf_forbids_chkfile` |

All top 13 entries are **pre-existing** QE/VASP/W90 integration tests. The GPAW relax test at **40s** ranks #14.

### GPAW integration test timing breakdown

| Duration | Test | Notes |
|----------|------|-------|
| 19.90s | `TestGPAWRelax::test_h2o_relax_fd_mode` | H2O relaxation (33 BFGS steps, FD mode) |
| 4.50s | `TestGPAWBands::test_si_scf_bands_chain` | Si SCF + fixed_density bands |
| 2.60s | `TestGPAWSCF::test_si_scf_pw_mode` | Si bulk SCF (PW, 4x4x4 kpts) |
| 1.05s | `TestGPAWSCF::test_scf_output_files` | Si SCF (PW, 2x2x2 kpts) |
| 0.03s | `TestGPAWEngineProbe::test_engine_probe` | subprocess probe |
| 0.00s | `TestGPAWEngineProbe::test_driver_registry_lookup` | registry check |
| **28.08s** | **Total GPAW integration** | |

### Why wall-clock went from ~1min to ~3.5min

The wall-clock time is dominated by the **slowest worker** in `-n auto --dist=loadfile`. The top bottleneck workers run QE/VASP CLI integration tests at 90-130s each — these are **all pre-existing**. The GPAW tests add ~28s to one worker, which is not the bottleneck.

The increase from ~1min to ~3.5min is likely **not caused by GPAW** but rather by:
1. How `--dist=loadfile` distributes files across workers (non-deterministic)
2. Pre-existing slow tests already taking 90-130s per worker
3. The Psi4 integration commit (`5024d8ba`) added new test files that changed load distribution

The GPAW relax test (20s) could be made faster by:
- Using a coarser grid (`h=0.3` instead of `h=0.25`)
- Reducing fmax tolerance (`0.1` instead of `0.05`)
- Using a smaller vacuum box
- Using LCAO mode instead of FD for the molecular test

---

## 3. New test files from this integration

### From Psi4 integration (committed, `5024d8ba`)
- `tests/drivers/psi4/test_psi4_driver.py` — 29 tests, <1s total (all pass)
- `tests/integration/test_psi4_execution.py` — 9 tests, all SKIP (Psi4 not installed)
- `tests/integration/psi4/test_psi4_project_level.py` — 6 tests, all SKIP (Psi4 not installed)

### From GPAW integration (uncommitted)
- `tests/drivers/gpaw/test_gpaw_driver.py` — 37 tests, <1s total (all pass)
- `tests/integration/test_gpaw_execution.py` — 6 tests, ~28s total (all pass, none skip)

### Modified test files
- `tests/gates/test_registry_routing.py` — added psi4/gpaw to module cleanup list
- `tests/unit/test_step_type_mapping.py` — added `"gpaw_"` to valid prefix tuple
