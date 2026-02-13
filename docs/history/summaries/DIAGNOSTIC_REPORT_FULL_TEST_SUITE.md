# Full Test Suite Diagnostic Report

**Generated:** 2025-01-XX  
**Test Run Command:** `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`  
**Environment:** Python 3.14.0, pytest 9.0.2, venv: `<HOME>/QMatSuite/.venv`

---

## A) Global Summary

- **Total Tests:** 2,590
- **Passed:** 2,284 (88.2%)
- **Failed:** 215 (8.3%)
- **Errors:** 88 (3.4%)
- **Skipped:** 3 (0.1%)
- **Warnings:** 143
- **Total Runtime:** 60.60s

**Overall Status:** 215 failures + 88 errors = **303 test issues** blocking full suite green.

---

## B) Failure/ERROR Bucketing (Root Cause Analysis)

### Bucket 1: Missing QVService Static/Instance Methods (HIGH CONFIDENCE - PRIMARY ROOT CAUSE)

**Count:** ~200+ failing tests  
**Confidence:** High  
**Root Cause:** PR10 API slimming removed many methods from `QVService` that tests still expect. These methods were likely moved to domain services or removed entirely, but tests haven't been updated.

**Representative Traceback:**
```
AttributeError: type object 'QVService' has no attribute 'init_step'
AttributeError: type object 'QVService' has no attribute 'add_step_to_calculation'
AttributeError: type object 'QVService' has no attribute '_detect_prefix_outdir_injection'
```

**Top Missing Methods (by impact):**
1. `init_step` - **96 tests** (step creation/management)
2. `add_step_to_calculation` - **42 tests** (step addition)
3. `_detect_prefix_outdir_injection` - **22 tests** (prefix/outdir detection)
4. `_preflight_check_and_seed_pseudos` - **18 tests** (pseudo preflight)
5. `_build_structure_vis_payload` - **16 tests** (structure visualization)
6. `calc_set_steps` - **12 tests** (workflow instantiation)
7. `configure_calculation` - **10 tests** (calculation config)
8. `update_step_params` - **8 tests** (step parameter updates)
9. `get_structure_vis_data` - **8 tests** (structure visualization)
10. `get_reference_analysis` - **8 tests** (analysis data)
11. `create_demo_project` - **8 tests** (demo project creation)
12. `save_project_snapshot` - **6 tests** (snapshot operations)
13. `configure_structure` - **6 tests** (structure config)
14. `write_structure` - **4 tests** (structure I/O)
15. `update_calculation_species_map` - **4 tests** (species map)
16. `preflight_check` - **4 tests** (preflight validation)
17. `needs_alat_preservation` - **4 tests** (alat handling)
18. `detect_runtime_control_keys` - **4 tests** (runtime detection)
19. `list_calculations` - **4 tests** (calculation listing)
20. `is_ulid_like` - **4 tests** (ULID validation)
21. `generate_kpath` - **4 tests** (k-path generation)

**Instance Methods Missing:**
- `require_calculation_ref` - **4 tests**
- `detect_context` - **4 tests**
- `resolve_calculation_ref` - **2 tests**
- `resolve_structure_ref` - **2 tests**
- `require_structure_ref` - **2 tests**
- `require_step_ref` - **2 tests**
- `make_structure_selector_resolver_ref` - **2 tests**
- `build_resource_index` - **2 tests**

**Impacted Test Areas:**
- `tests/unit/test_api_service*.py` - API facade tests
- `tests/daemon/test_*.py` - Daemon handler tests
- `tests/cli/test_*.py` - CLI integration tests
- `tests/integration/test_*.py` - Integration tests
- `tests/unit/test_workflow.py` - Workflow tests
- `tests/unit/test_analysis_artifacts.py` - Analysis tests

**Why This Is The Root Cause:**
- PR10 explicitly removed many methods from `quantumvitas.api.__all__` and `QVService`
- Tests were written against the old API surface
- These methods likely exist in domain services (e.g., `calculation`, `structure`, `step`) but need thin wrapper methods in `QVService` for backward compatibility
- This is a **compatibility layer gap**, not a functional bug

**Fix Direction:**
Add thin `@staticmethod` wrappers in `QVService` that delegate to domain services. Example:
```python
@staticmethod
def init_step(project_root: str, step_type: str, ...) -> ...:
    from quantumvitas.api.calculation import CalculationService
    return CalculationService(project_root).init_step(...)
```

---

### Bucket 2: Missing API Type Exports (HIGH CONFIDENCE)

**Count:** ~30 failing tests  
**Confidence:** High  
**Root Cause:** PR10 removed type/class exports from `quantumvitas.api.__init__.__all__`. Tests import these types directly from `quantumvitas.api`, but they're no longer exported.

**Representative Traceback:**
```
ImportError: cannot import name 'StructureStepSpec' from 'quantumvitas.api'
ImportError: cannot import name 'QECardType' from 'quantumvitas.api'
ImportError: cannot import name 'ParameterOverride' from 'quantumvitas.api'
```

**Missing Exports (by frequency):**
1. `PresetCompilationError` - **6 tests**
2. `DisplayModeParams` - **6 tests**
3. `StructureStepSpec` - **4 tests**
4. `PrecisionContextError` - **4 tests**
5. `EngineConfig` - **4 tests**
6. `Step` - **2 tests**
7. `QeEngine` - **2 tests** (suggests `engine` instead)
8. `QEInputParser` - **2 tests**
9. `QECardType` - **2 tests**
10. `ProjectContext` - **2 tests**
11. `ParameterOverride` - **2 tests**
12. `DOSData` - **2 tests**
13. `CalculationStepEntry` - **2 tests**
14. `Calculation` - **2 tests** (suggests `calculation` instead)
15. `BandAnalysisFiles` - **2 tests**

**Impacted Test Areas:**
- `tests/unit/test_api_service_facade.py` - API facade re-export tests
- `tests/unit/test_project_and_cli.py` - CLI parameter parsing

**Why This Is The Root Cause:**
- PR10 explicitly slimmed `api.__all__` to remove internal types
- Tests expect these types to be importable from `quantumvitas.api`
- These types still exist in their source modules but aren't re-exported

**Fix Direction:**
Either:
1. Add these types back to `api.__init__.__all__` (if they're part of public API)
2. Update tests to import from source modules (e.g., `from quantumvitas.ir.parameters import ParameterOverride`)
3. Create type aliases in `api.__init__` that re-export without adding to `__all__` (if they're needed for backward compat)

---

### Bucket 3: Calculation Path Resolution Issues (MEDIUM CONFIDENCE)

**Count:** 76 FileNotFoundError + 18 NotADirectoryError = **94 tests**  
**Confidence:** Medium  
**Root Cause:** Tests expect `calculation.yaml/calculation.yaml` (nested path), but the actual path structure may have changed. This could be:
- A test fixture issue (incorrect path construction)
- A change in how calculation paths are resolved
- A parallel test execution issue (path conflicts)

**Representative Traceback:**
```
FileNotFoundError: Calculation file not found: /path/to/calculations/test_calc/calculation.yaml/calculation.yaml
NotADirectoryError: [Errno 20] Not a directory: '/path/to/calculations/h2o-scf/calculation.yaml/calculation.yaml'
```

**Pattern:** All errors show `calculation.yaml/calculation.yaml` (double nesting), suggesting tests are appending `/calculation.yaml` to a path that already ends in `calculation.yaml`.

**Impacted Test Areas:**
- `tests/integration/test_incremental_run.py` - **8 tests**
- `tests/integration/test_lammps_*.py` - **10+ tests**
- `tests/integration/test_pyscf_phase3c.py` - **3 tests**
- `tests/integration/test_step_slug_consistency.py` - **5 tests**
- `tests/integration/test_cp2k_integration.py` - **3 tests**
- `tests/integration/orca/test_orca_project_level.py` - **4 tests**
- `tests/integration/test_orca_relax_real.py` - **3 tests**
- `tests/integration/test_lammps_incremental_skip.py` - **2 tests**
- `tests/integration/test_lammps_chain.py` - **1 test**
- `tests/integration/test_lammps_eam_md.py` - **1 test**
- `tests/integration/test_lammps_lj_minimize.py` - **1 test**
- `tests/integration/test_lammps_restart_parallel.py` - **2 tests**

**Why This Is Likely The Root Cause:**
- The pattern `calculation.yaml/calculation.yaml` suggests a path construction bug
- Many integration tests use similar fixtures that may have been affected by a path resolution change
- This could be a cascading failure from Bucket 1 (if `init_step` or similar methods changed path handling)

**Fix Direction:**
1. Check test fixtures that construct calculation paths
2. Verify if `calculation.yaml` is now a directory (not a file) in the new structure
3. Update path construction logic in test fixtures
4. Check if this is related to changes in `Calculation` model or path resolution

---

### Bucket 4: CLI/Assertion Failures (LOW-MEDIUM CONFIDENCE)

**Count:** ~46 tests  
**Confidence:** Low-Medium  
**Root Cause:** Various assertion failures and CLI command failures. Some may be cascading from Bucket 1 (missing methods), others may be test expectation mismatches.

**Representative Failures:**
1. **CLI Command Failures:**
   - `subprocess.CalledProcessError` in `test_si_bands_manual_calculation_cli.py`, `test_si_bands_auto_calculation_cli.py`, `test_si_dos_calculation_comprehensive.py`
   - Likely caused by missing `init_step` or `detect_runtime_control_keys` methods

2. **Assertion Failures:**
   - `test_parse_override_args_basic` - `AttributeError: 'dict' object has no attribute 'name'`
   - `test_cli_delete_structure` - AssertionError (unspecified)
   - `test_cli_delete_calculation` - AssertionError (unspecified)
   - `test_template_calculation_runs` - Expects `StepStatus.SUCCESS` but gets `SUCCESS`
   - `test_cli_run_calculation` - Similar status string mismatch

3. **Test Logic Failures:**
   - `test_init_step_fails_at_project_root_without_calculation` - Error message assertion failure
   - `test_different_calcs_run_concurrently` - `assert False`

**Impacted Test Areas:**
- `tests/cli/test_*.py` - CLI tests
- `tests/unit/test_project_and_cli.py` - CLI parsing
- `tests/integration/test_incremental_run.py` - Concurrency tests

**Why This Is Likely Secondary:**
- Many CLI failures are likely cascading from missing `QVService` methods
- Assertion failures may be test expectation issues (e.g., status string format changed)
- Some may be legitimate bugs, but most are likely test compatibility issues

**Fix Direction:**
1. Fix Bucket 1 first (many CLI failures will resolve)
2. Update test expectations for status strings (if format changed)
3. Fix `ParsedOverride` attribute access (if dict structure changed)
4. Review concurrency test logic

---

### Bucket 5: Other Errors (LOW CONFIDENCE - INVESTIGATE)

**Count:** ~10 tests  
**Confidence:** Low  
**Root Cause:** Various other errors that need individual investigation.

**Examples:**
- `test_service_initialization_fails_for_non_project` - `ValueError: Not a project` (may be expected failure, test logic issue)
- `test_instance_methods_exist` - `AssertionError: assert False` (test may be checking for methods that don't exist)
- `test_init_calculation` - `AssertionError: assert False` (unclear cause)
- `test_ensure_calculation_analysis_method_exists` - `AssertionError: assert False` (method existence check)

**Impacted Test Areas:**
- `tests/unit/test_api_service*.py` - API service tests
- `tests/unit/test_analysis_artifacts.py` - Analysis tests

**Fix Direction:**
- Investigate each individually after fixing Buckets 1-4
- May be test logic issues rather than code bugs

---

## C) Top 10 Actionable "Primary" Issues

### 1. Add `QVService.init_step()` wrapper (UNBLOCKS 96 TESTS)
**Priority:** CRITICAL  
**Risk:** Low (thin wrapper)  
**Fix:** Add `@staticmethod` wrapper delegating to `CalculationService.init_step()`  
**Impact:** Unblocks all step creation/management tests

### 2. Add `QVService.add_step_to_calculation()` wrapper (UNBLOCKS 42 TESTS)
**Priority:** CRITICAL  
**Risk:** Low (thin wrapper)  
**Fix:** Add `@staticmethod` wrapper delegating to `CalculationService.add_step()`  
**Impact:** Unblocks all step addition tests

### 3. Fix calculation path resolution in test fixtures (UNBLOCKS 94 TESTS)
**Priority:** HIGH  
**Risk:** Medium (may affect test isolation)  
**Fix:** Update test fixtures to use correct calculation path structure (remove double `calculation.yaml`)  
**Impact:** Unblocks all integration tests with path issues

### 4. Add `QVService._detect_prefix_outdir_injection()` wrapper (UNBLOCKS 22 TESTS)
**Priority:** HIGH  
**Risk:** Low (internal method, thin wrapper)  
**Fix:** Add `@staticmethod` wrapper delegating to domain service  
**Impact:** Unblocks prefix/outdir injection tests

### 5. Re-export missing API types (UNBLOCKS 30 TESTS)
**Priority:** HIGH  
**Risk:** Low-Medium (may expand API surface, but types are needed)  
**Fix:** Add missing types to `api.__init__.__all__` or create type aliases  
**Impact:** Unblocks API facade re-export tests

### 6. Add `QVService._preflight_check_and_seed_pseudos()` wrapper (UNBLOCKS 18 TESTS)
**Priority:** MEDIUM  
**Risk:** Low (internal method)  
**Fix:** Add `@staticmethod` wrapper delegating to pseudo service  
**Impact:** Unblocks pseudo preflight tests

### 7. Add `QVService._build_structure_vis_payload()` wrapper (UNBLOCKS 16 TESTS)
**Priority:** MEDIUM  
**Risk:** Low (internal method)  
**Fix:** Add `@staticmethod` wrapper delegating to structure service  
**Impact:** Unblocks structure visualization tests

### 8. Add `QVService.calc_set_steps()` wrapper (UNBLOCKS 12 TESTS)
**Priority:** MEDIUM  
**Risk:** Low (thin wrapper)  
**Fix:** Add `@staticmethod` wrapper delegating to workflow service  
**Impact:** Unblocks workflow instantiation tests

### 9. Add instance method wrappers (UNBLOCKS 20 TESTS)
**Priority:** MEDIUM  
**Risk:** Low (thin wrappers)  
**Fix:** Add instance methods to `QVService` that delegate to domain services:
- `require_calculation_ref`
- `detect_context`
- `resolve_calculation_ref`
- `resolve_structure_ref`
- `require_structure_ref`
- `require_step_ref`
- `make_structure_selector_resolver_ref`
- `build_resource_index`

**Impact:** Unblocks API facade instance method tests

### 10. Fix CLI status string expectations (UNBLOCKS 2-3 TESTS)
**Priority:** LOW  
**Risk:** Low (test-only change)  
**Fix:** Update test expectations to match actual status string format (`SUCCESS` vs `StepStatus.SUCCESS`)  
**Impact:** Unblocks CLI status assertion tests

---

## D) "Do Not Touch" Constraints

**MUST NOT VIOLATE:**

1. **Do NOT re-expand `quantumvitas.api.__init__.__all__` beyond PR10 rules**
   - Only add types that are genuinely part of the public API
   - Prefer type aliases or re-exports without adding to `__all__` if backward compat is needed

2. **Do NOT reintroduce kernel imports at module top-level in `api/daemon/cli`**
   - All wrappers must use lazy imports (inside methods)
   - Gate test `test_daemon_no_kernel_imports` must remain green

3. **Keep daemon handlers JSON-serializable and schema-stable**
   - Gate test `test_daemon_no_hand_serialization` must remain green
   - No manual dict construction in handlers

4. **Prefer thin wrappers to existing canonical functions**
   - Wrappers should be 1-3 lines delegating to domain services
   - No business logic in wrappers

5. **Avoid large refactors**
   - Smallest change that unblocks most tests
   - Fix one bucket at a time, verify after each

---

## E) Appendices

### E.1) Raw Failure List by Bucket

#### Bucket 1: Missing QVService Methods (Partial List)
```
FAILED tests/unit/test_api_service.py::TestQVServiceStep::test_init_step
FAILED tests/unit/test_api_service.py::TestQVServiceStep::test_init_step_inherits_structure
FAILED tests/unit/test_api_service.py::TestQVServiceStep::test_list_steps
FAILED tests/unit/test_api_service.py::TestQVServiceStep::test_delete_step
ERROR tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_list_calculations
ERROR tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_run_calculation_via_job_manager
ERROR tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_get_band_structure_data
ERROR tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_analyze_bands_and_generate_plot
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestJobSubmissionAndListing::test_submit_job_and_list_jobs
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestJobSubmissionAndListing::test_job_list_path_normalization
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestStepDetailRetrieval::test_get_step_detail_with_ulid
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestStepDetailRetrieval::test_get_step_detail_requires_ulid_from_calculation_yaml
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestDAGInvariants::test_calculation_has_structure_id_ulid
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestDAGInvariants::test_step_yaml_no_structure_id
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestStepCreationRaceCondition::test_immediate_get_step_detail_after_add_step
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestStepDeletion::test_delete_step_via_daemon_removes_from_calculation_yaml
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestStepDeletion::test_delete_step_via_daemon_moves_step_file_to_trash
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestStepDeletion::test_delete_step_via_daemon_allows_missing_step_file
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestStepDeletion::test_delete_step_via_daemon_invalid_ulid_raises_resource_not_found
ERROR tests/daemon/test_gui_job_and_step_flows.py::TestCalculationFailureHandling::test_calculation_stops_after_step_failure
ERROR tests/unit/test_api_step_artifacts.py::TestListStepArtifacts::test_list_step_artifacts_empty_raw_dir
ERROR tests/unit/test_api_step_artifacts.py::TestListStepArtifacts::test_list_step_artifacts_with_files
ERROR tests/unit/test_api_step_artifacts.py::TestListStepArtifacts::test_list_step_artifacts_default_selection
ERROR tests/unit/test_api_step_artifacts.py::TestListStepArtifacts::test_list_step_artifacts_rejects_directories
ERROR tests/unit/test_api_step_artifacts.py::TestReadStepArtifactText::test_read_step_artifact_text_success
ERROR tests/unit/test_api_step_artifacts.py::TestReadStepArtifactText::test_read_step_artifact_text_truncation
ERROR tests/unit/test_api_step_artifacts.py::TestReadStepArtifactText::test_read_step_artifact_text_path_traversal_blocked
ERROR tests/unit/test_api_step_artifacts.py::TestReadStepArtifactText::test_read_step_artifact_text_directory_rejected
ERROR tests/unit/test_api_step_artifacts.py::TestReadStepArtifactText::test_read_step_artifact_text_nonexistent_file
... (many more)
```

#### Bucket 2: Missing API Type Exports
```
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_qe_model_enums_re_exported
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_qe_parser_re_exported
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_dos_data_re_exported
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_structure_step_spec_re_exported
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_parameter_override_re_export
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_step_re_export
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_calculation_re_export
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_find_band_analysis_files_wrapper
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_engine_config_re_export
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_calculation_step_entry_re_export
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_qe_engine_re_export
FAILED tests/unit/test_api_service_facade.py::TestAPIServiceFacade::test_project_context_re_export
```

#### Bucket 3: Path Resolution Issues
```
ERROR tests/integration/test_incremental_run.py::test_run_lock_blocks_concurrent_runs
ERROR tests/integration/test_incremental_run.py::test_manifest_trim_on_removing_last_step
ERROR tests/integration/test_incremental_run.py::test_reorder_forces_rerun_from_divergence
ERROR tests/integration/test_incremental_run.py::test_ignore_ulid_for_equivalence
ERROR tests/integration/test_incremental_run.py::test_single_step_invalidates_suffix
ERROR tests/integration/test_incremental_run.py::test_pseudo_preflight_warning_and_update
ERROR tests/integration/test_incremental_run.py::test_crash_recovery_incremental_rerun_from_failed_step
ERROR tests/integration/test_incremental_run.py::test_pseudo_preflight_update_failure_non_blocking
ERROR tests/integration/test_incremental_run.py::test_nested_calc_edit_lock_raises_fast
ERROR tests/integration/test_incremental_run.py::test_pseudo_set_sha_stable_under_reordering_and_rename
ERROR tests/integration/test_incremental_run.py::test_manifest_corruption_recovery
ERROR tests/integration/test_incremental_run.py::test_step_has_no_id_property
ERROR tests/integration/test_incremental_run.py::test_manifest_stores_ulid_not_slug
... (many more)
```

### E.2) Suspicious Warnings

**Note:** 143 warnings were reported. Common patterns likely include:
- Deprecation warnings (expected during API transition)
- Resource leak warnings (may indicate test cleanup issues)
- Import warnings (may indicate missing optional dependencies)

**Action:** Review warnings separately after fixing primary failures.

---

## Summary

**Primary Root Cause:** PR10 API slimming removed many `QVService` methods that tests still expect. These need thin compatibility wrappers.

**Secondary Issues:**
- Missing API type exports (30 tests)
- Calculation path resolution in test fixtures (94 tests)
- CLI/assertion expectation mismatches (46 tests)

**Recommended Fix Order:**
1. Add `QVService.init_step()` wrapper (unblocks 96 tests)
2. Add `QVService.add_step_to_calculation()` wrapper (unblocks 42 tests)
3. Fix calculation path resolution in test fixtures (unblocks 94 tests)
4. Add remaining missing method wrappers (unblocks ~100 tests)
5. Re-export missing API types (unblocks 30 tests)
6. Fix remaining assertion/CLI issues (unblocks ~20 tests)

**Estimated Impact:** Fixing the top 3 issues should unblock ~230 tests, bringing the suite from 88.2% pass to ~95% pass.

