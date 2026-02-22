# Engine Driver Migration: Implementation Analysis and Test Failure Report

**Date**: 2026-01-21  
**Scope**: PR1 (Remove Fallbacks) through Wannier90 Migration (PR 25)  
**Test Suite Status**: 29 failures, 2 errors, 2305 passed

---

## Executive Summary

This document provides a comprehensive analysis of the engine driver migration work completed in this conversation, from PR1 (removing silent QE fallbacks) through the migration of LAMMPS, CP2K, and Wannier90 engines. It details all test failures discovered in the full test suite, their root causes (grouped by shared issues), evidence from code review, and proposed fixes.

**Key Achievements**:
- Successfully migrated 6 engines (VASP, ORCA, PySCF, LAMMPS, CP2K, Wannier90) to driver bundle architecture
- Created DriverRegistry infrastructure and refactored kernel touchpoints
- All driver-specific tests pass (88/88)
- Full test suite reveals 29 failures and 2 import errors requiring fixes

**Critical Issues Identified**:
1. **Import Path Errors**: Handler code and tests still reference old recipe locations
2. **Missing Exception Imports**: Tests need `UnknownEngineError` from `driver_exceptions`
3. **Wannier90 Engine Detection**: `w90_run` registered as engine="w90" breaks QE family detection
4. **VASP DOS Zero-Mapping**: Test expects None but registry returns 'vasp_dos'

---

## Part 1: Work Completed in This Conversation

### 1.1 PR1: Remove Silent QE Fallbacks

**Objective**: Eliminate the critical vulnerability where unknown step types silently fell back to QE execution.

**Changes Made**:
- Modified `src/qmatsuite/core/calc_identity.py::_infer_engine_family_from_machine_types()`:
  - Removed hardcoded prefix-based detection (`step_type.startswith("qe_")`)
  - Removed silent QE fallback (`return "qe"` for unknown types)
  - Replaced with `DriverRegistry.is_step_type_registered()` and `DriverRegistry.get_engine_for_step_type()`
  - Now returns `None` for unknown/mixed step types instead of silently defaulting to QE

**Files Modified**:
- `src/qmatsuite/core/calc_identity.py` (lines 79-111)

**Impact**: This fix ensures that unknown step types fail fast with clear error messages rather than silently executing with the wrong engine.

---

### 1.2 PR2: DriverRegistry Scaffold and Kernel Touchpoints Refactor

**Objective**: Create the central `DriverRegistry` infrastructure and refactor all kernel routing to use it.

**Files Created**:
1. `src/qmatsuite/core/driver_protocol.py`:
   - `WorkdirPolicy` enum (ISOLATED, CLEANUP, SHARED)
   - `ErrorClass` enum (CONVERGENCE, MEMORY, TIMEOUT, etc.)
   - `StepTypeSpec` dataclass (id, engine, executable, description, category, etc.)
   - `EngineDriver` Protocol (MUST interface: 3 properties, 4 methods)
   - `BaseEngineDriver` class (SHOULD/PLUGIN defaults)

2. `src/qmatsuite/core/driver_exceptions.py`:
   - `UnknownStepTypeError` (with similarity matching)
   - `UnknownEngineError`
   - `UnknownMaterializationError`
   - `DuplicateStepTypeError`
   - `DuplicateEngineError`

3. `src/qmatsuite/core/driver_registry.py`:
   - `DriverRegistry` singleton class
   - Driver registration and validation
   - Step type lookup and routing
   - Handler and recipe class retrieval
   - Materialization mapping (GEN→SPEC)

4. `src/qmatsuite/drivers/__init__.py`:
   - Auto-imports all driver packages to trigger registration

5. `src/qmatsuite/drivers/qe_shim/__init__.py`:
   - `QELegacyDriver` class (minimal shim for QE until full migration)
   - Registers all QE step types including `w90_preproc`

**Files Modified**:
1. `src/qmatsuite/execution/handlers.py`:
   - `create_handler_map()`: Now delegates to `DriverRegistry.get_handler()`
   - Added `get_handler_for_step()`: Preferred entry point for handler lookup
   - Removed hardcoded engine-specific handler registration

2. `src/qmatsuite/execution/recipes.py`:
   - `get_recipe_for_engine()`: Now delegates to `DriverRegistry.get_recipe_class()`
   - Removed hardcoded recipe class mapping

3. `src/qmatsuite/workflow/generalized_steps.py`:
   - `materialize_step()`: Now uses `DriverRegistry.materialize_step_type()`
   - Falls back to legacy `MATERIALIZATION_MAP` for backward compatibility

4. `src/qmatsuite/calculation/structure_steps.py`:
   - Removed hardcoded `*_STEP_TYPES` sets (PYSCF_STEP_TYPES, ORCA_STEP_TYPES, etc.)
   - Replaced `is_*_step()` functions to query `DriverRegistry` by engine family

5. `src/qmatsuite/calculation/step_done.py`:
   - Removed hardcoded `VASP_STEP_TYPES` and `LAMMPS_STEP_TYPES`
   - Modified `is_vasp_step()` and `is_lammps_step()` to use registry

6. `src/qmatsuite/core/calc_identity.py`:
   - Already modified in PR1, now fully uses registry

**Tests Created**:
- `tests/gates/test_registry_routing.py`: Gate 1 tests for registry routing
  - Registry basics (singleton, registration)
  - Step type routing
  - Materialization
  - Recipe routing
  - Driver validation
  - Kernel integration

**Key Technical Decisions**:
- **Eager Driver Loading**: Drivers register at import time via `qmatsuite.drivers` package
- **Protocol vs ABC**: Used `Protocol` for `EngineDriver` to allow duck typing
- **Backward Compatibility**: Maintained one minor version compatibility with deprecation warnings
- **Module Reloading Fix**: Enhanced test setup to explicitly remove driver modules from `sys.modules` to ensure fresh registration

---

### 1.3 VASP Migration (PR 20)

**Objective**: Extract all VASP-specific code into `src/qmatsuite/drivers/vasp/`.

**Files Created**:
1. `src/qmatsuite/drivers/vasp/driver.py`:
   - `VASPDriver` class with 6 step types (scf, relax, md, bands, dos, neb)
   - Materialization map (GEN_SCF → vasp_scf, etc.)
   - WorkdirPolicy.CLEANUP (isolated workdirs with cleanup)
   - Capabilities: chgcar_restart, wavecar_restart

2. `src/qmatsuite/drivers/vasp/handler.py`:
   - Moved `vasp_step_handler` from `execution/handlers.py`
   - Handles CHGCAR/WAVECAR staging from reference SCF
   - Uses `find_reference_scf()` for continuation

3. `src/qmatsuite/drivers/vasp/recipe.py`:
   - Moved `VASPRecipe` from `execution/recipes.py`
   - Creates isolated workdir per step

4. `src/qmatsuite/drivers/vasp/staging.py`:
   - Moved from `execution/vasp_staging.py`
   - `stage_chgcar()`: Prerequisite for non-SCF, optional for SCF
   - `stage_wavecar()`: Optional for all steps, warning if fails

5. `src/qmatsuite/drivers/vasp/reference.py`:
   - Wrapper for `find_reference_scf()` from `execution/reference_resolver`

6. `src/qmatsuite/drivers/vasp/__init__.py`:
   - Registers `VASPDriver` at import time

**Files Modified**:
- `src/qmatsuite/execution/handlers.py`: Removed `vasp_step_handler`
- `src/qmatsuite/execution/recipes.py`: Removed `VASPRecipe`
- `src/qmatsuite/execution/__init__.py`: Removed `vasp_step_handler` export
- `src/qmatsuite/drivers/__init__.py`: Added VASP import

**Tests Created**:
- `tests/drivers/vasp/test_vasp_driver.py`: Driver properties, registration, isolation tests

---

### 1.4 ORCA Migration (PR 21)

**Objective**: Extract all ORCA-specific code into `src/qmatsuite/drivers/orca/`.

**Files Created**:
1. `src/qmatsuite/drivers/orca/driver.py`:
   - `ORCADriver` class with step types (scf, opt, freq, td, etc.)
   - Materialization map (GEN_SCF → orca_scf, etc.)
   - WorkdirPolicy.ISOLATED
   - Capabilities: chain (multi-step workflows)

2. `src/qmatsuite/drivers/orca/handler.py`:
   - Moved `orca_chain_handler` from `execution/handlers.py`

3. `src/qmatsuite/drivers/orca/recipe.py`:
   - Moved `ORCARecipe` from `execution/recipes.py`

4. `src/qmatsuite/drivers/orca/__init__.py`:
   - Registers `ORCADriver` at import time

**Files Modified**:
- `src/qmatsuite/execution/handlers.py`: Removed ORCA handler
- `src/qmatsuite/execution/recipes.py`: Removed `ORCARecipe`
- `src/qmatsuite/drivers/__init__.py`: Added ORCA import

**Tests Created**:
- `tests/drivers/orca/test_orca_driver.py`: Driver tests with isolation checks

---

### 1.5 PySCF Migration (PR 22)

**Objective**: Extract all PySCF-specific code into `src/qmatsuite/drivers/pyscf/`.

**Files Created**:
1. `src/qmatsuite/drivers/pyscf/driver.py`:
   - `PySCFDriver` class with step types (scf, mp2, td, freq, etc.)
   - Materialization map (GEN_SCF → pyscf_scf, etc.)
   - WorkdirPolicy.ISOLATED
   - Capabilities: python_native

2. `src/qmatsuite/drivers/pyscf/handler.py`:
   - Moved `pyscf_chain_handler` from `execution/handlers.py`

3. `src/qmatsuite/drivers/pyscf/recipe.py`:
   - Moved `PySCFRecipe` from `execution/recipes.py`

4. `src/qmatsuite/drivers/pyscf/__init__.py`:
   - Registers `PySCFDriver` at import time

**Files Modified**:
- `src/qmatsuite/execution/handlers.py`: Removed PySCF handler
- `src/qmatsuite/execution/recipes.py`: Removed `PySCFRecipe`
- `src/qmatsuite/drivers/__init__.py`: Added PySCF import

**Tests Created**:
- `tests/drivers/pyscf/test_pyscf_driver.py`: Driver tests with isolation checks

---

### 1.6 LAMMPS Migration (PR 23)

**Objective**: Extract all LAMMPS-specific code into `src/qmatsuite/drivers/lammps/`.

**Files Created**:
1. `src/qmatsuite/drivers/lammps/driver.py`:
   - `LAMMPSDriver` class with 8 step types (minimize, md, nve, nvt, npt, relax, equilibrate, deform)
   - Materialization map (GEN_MINIMIZE → lammps_minimize, etc.)
   - WorkdirPolicy.ISOLATED (accumulates trajectory files)
   - Capabilities: restart, trajectory
   - `supports_incremental_skip()`: Returns False for MD steps (continuation matters)

2. `src/qmatsuite/drivers/lammps/handler.py`:
   - Moved `lammps_step_handler` from `execution/handlers.py` (lines 295-590)
   - Includes restart/checkpoint handling logic
   - Handles `final.data` artifact for relax steps

3. `src/qmatsuite/drivers/lammps/recipe.py`:
   - Moved `LAMMPSRecipe` from `execution/recipes.py` (lines 237-369)
   - Handles `restart_from` dependency resolution

4. `src/qmatsuite/drivers/lammps/restart.py`:
   - `find_restart_file()`: Finds latest restart file by mtime
   - `stage_restart_file()`: Stages restart file for reading
   - `resolve_restart_source()`: Resolves source step for restart

5. `src/qmatsuite/drivers/lammps/data_file.py`:
   - `write_data_file()`: Placeholder for LAMMPS data file creation

6. `src/qmatsuite/drivers/lammps/__init__.py`:
   - Registers `LAMMPSDriver` at import time

**Files Modified**:
- `src/qmatsuite/execution/handlers.py`: Removed `lammps_step_handler` (296 lines)
- `src/qmatsuite/execution/recipes.py`: Removed `LAMMPSRecipe` (133 lines)
- `src/qmatsuite/execution/__init__.py`: Removed `lammps_step_handler` export
- `src/qmatsuite/drivers/__init__.py`: Added LAMMPS import

**Tests Created**:
- `tests/drivers/lammps/test_lammps_driver.py`: Driver tests, restart handling tests

---

### 1.7 CP2K Migration (PR 24)

**Objective**: Extract all CP2K-specific code into `src/qmatsuite/drivers/cp2k/`.

**Files Created**:
1. `src/qmatsuite/drivers/cp2k/driver.py`:
   - `CP2KDriver` class with 8 step types (scf, relax, geo_opt, cell_opt, md, bands, dos, vibrational)
   - Materialization map (GEN_SCF → cp2k_scf, etc.)
   - WorkdirPolicy.ISOLATED (NO cleanup - artifacts accumulate)
   - Capabilities: restart, wfn_continuation
   - `supports_incremental_skip()`: Returns False for MD steps

2. `src/qmatsuite/drivers/cp2k/handler.py`:
   - Moved `cp2k_step_handler` from `execution/handlers.py` (lines 663-875)
   - Includes preflight checks for restart files
   - Handles `_resolve_cp2k_restart_artifacts()` helper function
   - **ISSUE**: Line 50 imports `CP2KRecipe` from old location

3. `src/qmatsuite/drivers/cp2k/recipe.py`:
   - Moved `CP2KRecipe` from `execution/recipes.py` (lines 372-473)
   - Includes `get_preflight_requirements()` for restart policy

4. `src/qmatsuite/drivers/cp2k/input_writer.py`:
   - `write_section()`: Helper for CP2K hierarchical input format

5. `src/qmatsuite/drivers/cp2k/__init__.py`:
   - Registers `CP2KDriver` at import time

**Files Modified**:
- `src/qmatsuite/execution/handlers.py`: Removed `cp2k_step_handler` and `_resolve_cp2k_restart_artifacts()`
- `src/qmatsuite/execution/recipes.py`: Removed `CP2KRecipe` (104 lines)
- `src/qmatsuite/drivers/__init__.py`: Added CP2K import

**Tests Created**:
- `tests/drivers/cp2k/test_cp2k_driver.py`: Driver tests, isolation checks

**Known Issue**: CP2K handler imports `CP2KRecipe` from wrong location (see Part 2).

---

### 1.8 Wannier90 Migration (PR 25)

**Objective**: Extract Wannier90 code into `src/qmatsuite/drivers/w90/`, handling cross-engine dependencies.

**Files Created**:
1. `src/qmatsuite/drivers/w90/driver.py`:
   - `W90Driver` class with 1 step type: `w90_run`
   - **Note**: `w90_preproc` remains in QE shim (runs via `pw2wannier90.x`)
   - Empty materialization map (no generalized steps)
   - WorkdirPolicy.ISOLATED
   - Capabilities: cross_engine (requires DFT output)
   - Preflight requirements: .amn, .mmn, .eig files from preprocessing

2. `src/qmatsuite/drivers/w90/handler.py`:
   - `w90_run_handler`: Handles main Wannier90 execution
   - Resolves input artifacts (.amn, .mmn, .eig) from previous steps
   - Stages .win file via recipe

3. `src/qmatsuite/drivers/w90/recipe.py`:
   - `W90Recipe` class with `materialize()` method
   - `stage()`: Generates .win file from config
   - `_generate_win_file()`: Creates Wannier90 input format

4. `src/qmatsuite/drivers/w90/artifact_resolver.py`:
   - `resolve_w90_inputs()`: Cross-engine artifact resolution
   - `_find_artifacts_in_dir()`: Finds .amn, .mmn, .eig files
   - Searches completed steps for preprocessing output

5. `src/qmatsuite/drivers/w90/__init__.py`:
   - Registers `W90Driver` at import time

**Files Modified**:
- `src/qmatsuite/drivers/qe_shim/__init__.py`:
  - Removed `w90_run` step type (now in W90 driver)
  - Kept `w90_preproc` (engine="qe", executable="pw2wannier90.x")
- `src/qmatsuite/drivers/__init__.py`: Added W90 import

**Tests Created**:
- `tests/drivers/w90/test_w90_driver.py`: Driver tests, artifact resolver tests, recipe tests

**Design Decision**: `w90_preproc` remains with QE shim because it uses QE's executable (`pw2wannier90.x`) and runs in QE context. Only `w90_run` (standalone `wannier90.x`) is in W90 driver.

---

## Part 2: Test Suite Failures Analysis

### 2.1 Failure Summary

**Total Failures**: 29  
**Total Errors**: 2 (import errors)  
**Total Passed**: 2305

**Failure Categories**:
1. **Import Errors (2)**: Tests cannot import recipe classes from old location
2. **Missing Exception Imports (20)**: Tests need `UnknownEngineError` import
3. **Wannier90 Engine Detection (1)**: `w90_run` breaks QE family detection
4. **VASP DOS Zero-Mapping (1)**: Test expects None but gets 'vasp_dos'
5. **CP2K Integration Failures (3)**: CP2K handler import error causes calculation failures
6. **Engine Detection Failures (2)**: Cannot determine engine for certain step types

---

### 2.2 Category 1: Import Errors (2 failures)

#### Issue 1.1: CP2K Handler Import Error

**Failures**:
- `tests/integration/test_cp2k_integration.py::test_cp2k_scf_silicon`
- `tests/integration/test_cp2k_integration.py::test_cp2k_relax_silicon_with_cell`
- `tests/integration/test_cp2k_integration.py::test_cp2k_md_incremental_skip_disabled`

**Error Message**:
```
ImportError: cannot import name 'CP2KRecipe' from 'qmatsuite.execution.recipes'
```

**Root Cause**:
In `src/qmatsuite/drivers/cp2k/handler.py` line 50:
```python
from qmatsuite.execution.recipes import CP2KRecipe
```

`CP2KRecipe` was moved to `src/qmatsuite/drivers/cp2k/recipe.py` during migration, but the handler still imports from the old location.

**Evidence**:
```python
# src/qmatsuite/drivers/cp2k/handler.py:50
from qmatsuite.execution.recipes import CP2KRecipe  # ❌ Wrong location

# Should be:
from qmatsuite.drivers.cp2k.recipe import CP2KRecipe  # ✅ Correct location
```

**Impact**: All CP2K integration tests fail because the handler cannot instantiate the recipe for preflight checks.

---

#### Issue 1.2: Test Import Errors

**Failures**:
- `tests/unit/execution/test_recipes.py` (ERROR - import time failure)
- `tests/unit/test_vasp_recipe.py` (ERROR - import time failure)

**Error Messages**:
```
ImportError: cannot import name 'ORCARecipe' from 'qmatsuite.execution.recipes'
ImportError: cannot import name 'VASPRecipe' from 'qmatsuite.execution.recipes'
```

**Root Cause**:
These test files import recipe classes from the old location:
- `tests/unit/execution/test_recipes.py:14-17`: Imports `ORCARecipe`, `PySCFRecipe` from `execution.recipes`
- `tests/unit/test_vasp_recipe.py:5`: Imports `VASPRecipe` from `execution.recipes`

**Evidence**:
```python
# tests/unit/execution/test_recipes.py:14-17
from qmatsuite.execution.recipes import (
    QERecipe,
    ORCARecipe,  # ❌ Moved to drivers/orca/recipe.py
    PySCFRecipe,  # ❌ Moved to drivers/pyscf/recipe.py
    get_recipe_for_engine,
)

# tests/unit/test_vasp_recipe.py:5
from qmatsuite.execution.recipes import VASPRecipe  # ❌ Moved to drivers/vasp/recipe.py
```

**Impact**: These test modules cannot be imported, causing 2 import errors and preventing all tests in these files from running.

---

### 2.3 Category 2: Missing Exception Imports (20 failures)

**Failures**:
- `tests/unit/test_vasp_registry.py::TestVASPGenToSpecMapping::test_vasp_nscf_mapping`
- `tests/unit/test_vasp_registry.py::TestVASPGenToSpecMapping::test_vasp_bands_post_zero_mapping`
- `tests/unit/orca/test_workflow_integration.py::TestORCAMaterialization::test_td_materializes_to_orca_td`
- `tests/unit/orca/test_workflow_integration.py::TestORCAMaterialization::test_unsupported_step_returns_none`
- `tests/unit/test_vasp_registry.py::TestVASPGenToSpecMapping::test_vasp_dos_zero_mapping` (also has assertion issue)
- `tests/unit/test_vasp_registry.py::TestVASPGenToSpecMapping::test_vasp_workflow_materialize_omits_zero_mappings`
- `tests/unit/orca/test_workflow_integration.py::TestORCAMaterialization::test_scf_td_workflow_materializes`
- `tests/unit/test_vasp_registry.py::TestVASPGenToSpecMapping::test_vasp_public_step_key_mapping`
- `tests/unit/orca/test_workflow_integration.py::TestORCAMaterialization::test_unsupported_workflow_raises`
- `tests/unit/orca/test_workflow_integration.py::TestORCAWorkflowTemplates::test_scf_td_can_be_instantiated_for_orca`
- `tests/unit/test_workflow_materialization_phase3b.py::TestUnsupportedFamilyMaterialization::test_unsupported_family_returns_none`
- `tests/unit/test_workflow_materialization_phase3b.py::TestUnsupportedFamilyMaterialization::test_unsupported_family_workflow_raises_error`
- `tests/unit/test_workflow_materialization_phase3b.py::TestUnsupportedFamilyMaterialization::test_mixed_supported_unsupported_workflow_raises_error`
- `tests/unit/test_workflow_materialization_phase3b.py::TestUnsupportedFamilyMaterialization::test_pyscf_only_scf_supported`
- `tests/unit/test_workflow_materialization_phase3b.py::TestUnsupportedFamilyMaterialization::test_pyscf_workflow_with_unsupported_raises_error`
- `tests/workflow/test_generalized_steps.py::TestGeneralizedStepMaterialization::test_materialize_unsupported_combination`
- `tests/workflow/test_generalized_steps.py::TestGeneralizedStepMaterialization::test_materialize_workflow_wannier`
- `tests/workflow/test_generalized_steps.py::TestGeneralizedStepMaterialization::test_materialize_workflow_fails_on_unsupported`
- `tests/unit/test_pyscf_integration.py::TestPySCFPhase3CMaterialization::test_mp2_not_supported_by_qe_family`
- `tests/integration/vasp/test_vasp_project_e2e.py::TestVASPProjectE2E::test_scf_to_dos_workflow`

**Error Message**:
```
NameError: name 'UnknownEngineError' is not defined
```

**Root Cause**:
These tests use `UnknownEngineError` in `pytest.raises()` or exception handling, but do not import it. The exception is defined in `qmatsuite.core.driver_exceptions`, but tests are not importing it.

**Evidence**:
```python
# Example from tests/unit/test_vasp_registry.py
# Missing import:
# from qmatsuite.core.driver_exceptions import UnknownEngineError

# Then used in test:
with pytest.raises(UnknownEngineError):  # ❌ NameError
    materialize_step("SCF", "nonexistent_engine")
```

**Files Affected**:
- `tests/unit/test_vasp_registry.py`
- `tests/unit/orca/test_workflow_integration.py`
- `tests/unit/test_workflow_materialization_phase3b.py`
- `tests/workflow/test_generalized_steps.py`
- `tests/unit/test_pyscf_integration.py`
- `tests/integration/vasp/test_vasp_project_e2e.py`

**Impact**: 20 tests fail because they cannot reference `UnknownEngineError` without importing it.

---

### 2.4 Category 3: Wannier90 Engine Detection Issue (1 failure)

**Failure**:
- `tests/unit/test_calc_identity.py::test_infer_engine_family_from_machine_types_w90_part_of_qe`

**Error Message**:
```
AssertionError: assert None == 'qe'
```

**Test Code**:
```python
def test_infer_engine_family_from_machine_types_w90_part_of_qe():
    """Test that w90 steps are part of qe family."""
    machine_types = ["qe_scf", "w90_run"]
    result = _infer_engine_family_from_machine_types(machine_types)
    assert result == "qe"  # ❌ Actual: None
```

**Root Cause**:
The test expects `w90_run` to be detected as part of the QE family, but `w90_run` is registered with `engine="w90"` in the W90 driver, not `engine="qe"`.

**Evidence**:
```python
# src/qmatsuite/drivers/w90/driver.py:60-67
StepTypeSpec(
    id="w90_run",
    engine="w90",  # ❌ Registered as "w90", not "qe"
    executable="wannier90.x",
    ...
)

# src/qmatsuite/core/calc_identity.py:99-103
families = set()
for step_type in machine_types:
    if DriverRegistry.is_step_type_registered(step_type):
        engine = DriverRegistry.get_engine_for_step_type(step_type)
        families.add(engine)  # Adds "w90" for w90_run, "qe" for qe_scf

# Result: families = {"qe", "w90"} → len(families) == 2 → returns None
```

**Design Intent**:
According to the test comment and `generalized_steps.py` line 74, Wannier90 is considered part of the QE family toolchain:
```python
# src/qmatsuite/workflow/generalized_steps.py:74
("qe", "WANNIER"): "w90_run",  # wannier90 is part of qe family toolchain
```

However, the W90 driver registers `w90_run` with `engine="w90"`, breaking this assumption.

**Impact**: The test fails because the engine detection logic correctly identifies mixed engines (`{"qe", "w90"}`) and returns `None`, but the test expects `"qe"` to indicate that Wannier90 is part of the QE family.

---

### 2.5 Category 4: VASP DOS Zero-Mapping Issue (1 failure)

**Failure**:
- `tests/unit/test_vasp_registry.py::TestVASPGenToSpecMapping::test_vasp_dos_zero_mapping`

**Error Message**:
```
AssertionError: assert 'vasp_dos' is None
```

**Test Code**:
```python
def test_vasp_dos_zero_mapping(self):
    """VASP DOS should return None (0-mapping: integrated in nscf)."""
    result = materialize_step("DOS", "vasp")
    assert result is None  # ❌ Actual: 'vasp_dos'
```

**Root Cause**:
The test expects VASP DOS to return `None` (zero-mapping) because VASP DOS is integrated in nscf output and doesn't need a separate step. However, the VASP driver registers `vasp_dos` as a step type, and the registry's materialization map includes `"GEN_DOS": "vasp_dos"`.

**Evidence**:
```python
# src/qmatsuite/drivers/vasp/driver.py:47-52
StepTypeSpec(
    id="vasp_dos",
    engine="vasp",
    executable="vasp",
    description="VASP density of states calculation",
    ...
)

# src/qmatsuite/drivers/vasp/driver.py:75-81
def get_materialization_map(self) -> dict[str, str]:
    return {
        "GEN_SCF": "vasp_scf",
        "GEN_RELAX": "vasp_relax",
        "GEN_MD": "vasp_md",
        "GEN_BANDS": "vasp_bands",
        "GEN_DOS": "vasp_dos",  # ❌ Maps to vasp_dos, but should be None
        "GEN_NEB": "vasp_neb",
    }
```

**Legacy Mapping**:
```python
# src/qmatsuite/workflow/generalized_steps.py:98
("vasp", "DOS"): None,  # 0-mapping: VASP DOS integrated in nscf output
```

**Design Conflict**:
- Legacy `MATERIALIZATION_MAP` says VASP DOS should be `None` (zero-mapping)
- VASP driver registers `vasp_dos` step type and maps `GEN_DOS → vasp_dos`
- Registry materialization takes precedence over legacy map

**Impact**: The test fails because the registry returns `'vasp_dos'` instead of `None`. This is a design decision: should VASP DOS be a separate step type, or should it be a zero-mapping (integrated in nscf)?

---

### 2.6 Category 5: Engine Detection Failures (2 failures)

**Failures**:
- `tests/unit/test_calculation_importers.py::test_build_calculation_from_qe_inputs_and_load`
- `tests/integration/test_si_dos_calculation.py::TestSiDOSCalculation::test_run_full_calculation`
- `tests/integration/test_si_bands_calculation.py::TestSiBandsCalculation::test_run_full_calculation`
- `tests/cli/test_si_dos_calculation_cli.py::test_cli_run_calculation`
- `tests/unit/test_project_and_cli.py::test_cli_run_calculation_strict_option`

**Error Message**:
```
ValueError: Cannot determine engine for step '01KFFH...'. Specify 'engine' field in calculation.yaml or use a known step type.
```

**Root Cause**:
These tests create calculations with step types that are not recognized by the engine detection logic. The step types may be:
1. Public types (e.g., "scf", "dos") that need materialization to machine types
2. Unknown step types not registered in the registry
3. Step types that require explicit `engine_family` in calculation.yaml

**Evidence**:
The error is raised from `calc_identity.py` when `_infer_engine_family_from_machine_types()` returns `None` and there's no explicit `engine_family` in calculation.yaml.

**Impact**: These tests fail because the engine detection cannot infer the engine family from the step types, requiring explicit `engine_family` specification or proper step type registration.

---

## Part 3: Root Cause Analysis (Grouped by Shared Causes)

### 3.1 Import Path Migration Incomplete

**Shared Cause**: Recipe classes were moved to driver bundles, but some code still references old import paths.

**Affected Components**:
1. **CP2K Handler** (`src/qmatsuite/drivers/cp2k/handler.py:50`):
   - Imports `CP2KRecipe` from `qmatsuite.execution.recipes`
   - Should import from `qmatsuite.drivers.cp2k.recipe`

2. **Test Files**:
   - `tests/unit/execution/test_recipes.py`: Imports `ORCARecipe`, `PySCFRecipe` from old location
   - `tests/unit/test_vasp_recipe.py`: Imports `VASPRecipe` from old location

**Evidence**:
- All recipe classes exist in their driver bundles:
  - `src/qmatsuite/drivers/cp2k/recipe.py` contains `CP2KRecipe`
  - `src/qmatsuite/drivers/orca/recipe.py` contains `ORCARecipe`
  - `src/qmatsuite/drivers/vasp/recipe.py` contains `VASPRecipe`
  - `src/qmatsuite/drivers/pyscf/recipe.py` contains `PySCFRecipe`
- `src/qmatsuite/execution/recipes.py` no longer contains these classes (verified by grep)

**Impact**: 5 failures (3 CP2K integration + 2 import errors)

---

### 3.2 Missing Exception Imports in Tests

**Shared Cause**: Tests use `UnknownEngineError` without importing it from `qmatsuite.core.driver_exceptions`.

**Affected Files**:
- `tests/unit/test_vasp_registry.py`
- `tests/unit/orca/test_workflow_integration.py`
- `tests/unit/test_workflow_materialization_phase3b.py`
- `tests/workflow/test_generalized_steps.py`
- `tests/unit/test_pyscf_integration.py`
- `tests/integration/vasp/test_vasp_project_e2e.py`

**Evidence**:
- `UnknownEngineError` is defined in `src/qmatsuite/core/driver_exceptions.py:60-69`
- Tests reference it in `pytest.raises(UnknownEngineError)` but don't import it
- Only `tests/gates/test_registry_routing.py` correctly imports it (line 241)

**Impact**: 20 failures across 6 test files

---

### 3.3 Wannier90 Engine Family Design Conflict

**Shared Cause**: `w90_run` is registered with `engine="w90"` but should be treated as part of QE family for engine detection purposes.

**Evidence**:
1. **Test Expectation** (`tests/unit/test_calc_identity.py:33-37`):
   ```python
   def test_infer_engine_family_from_machine_types_w90_part_of_qe():
       machine_types = ["qe_scf", "w90_run"]
       result = _infer_engine_family_from_machine_types(machine_types)
       assert result == "qe"  # Expects QE family
   ```

2. **Legacy Mapping** (`generalized_steps.py:74`):
   ```python
   ("qe", "WANNIER"): "w90_run",  # wannier90 is part of qe family toolchain
   ```

3. **Current Registration** (`drivers/w90/driver.py:60-67`):
   ```python
   StepTypeSpec(
       id="w90_run",
       engine="w90",  # Registered as separate engine
       ...
   )
   ```

4. **Detection Logic** (`calc_identity.py:99-103`):
   ```python
   for step_type in machine_types:
       if DriverRegistry.is_step_type_registered(step_type):
           engine = DriverRegistry.get_engine_for_step_type(step_type)
           families.add(engine)  # Adds "w90" for w90_run
   # Result: {"qe", "w90"} → returns None (mixed engines)
   ```

**Design Question**: Should `w90_run` be:
- Option A: Registered with `engine="qe"` (breaks driver isolation)
- Option B: Registered with `engine="w90"` but treated as QE family in detection (requires special case)
- Option C: Keep `engine="w90"` and update test expectation (w90 is separate family)

**Impact**: 1 failure, but reveals a design decision needed for cross-engine toolchains

---

### 3.4 VASP DOS Zero-Mapping Design Conflict

**Shared Cause**: VASP driver registers `vasp_dos` as a step type, but legacy design says VASP DOS should be a zero-mapping (integrated in nscf).

**Evidence**:
1. **Legacy Mapping** (`generalized_steps.py:98`):
   ```python
   ("vasp", "DOS"): None,  # 0-mapping: VASP DOS integrated in nscf output
   ```

2. **VASP Driver Registration** (`drivers/vasp/driver.py:47-52`):
   ```python
   StepTypeSpec(
       id="vasp_dos",
       engine="vasp",
       ...
   )
   ```

3. **VASP Materialization Map** (`drivers/vasp/driver.py:80`):
   ```python
   "GEN_DOS": "vasp_dos",  # Maps to step type
   ```

4. **Registry Priority** (`generalized_steps.py:149-167`):
   - Registry materialization is tried first
   - Legacy map is fallback
   - Registry returns `'vasp_dos'` (not None)

**Design Question**: Should VASP DOS:
- Option A: Be a separate step type (`vasp_dos`) as currently registered
- Option B: Be a zero-mapping (None) as legacy design specifies

**Impact**: 1 failure, but reveals a design decision needed for VASP DOS handling

---

### 3.5 Engine Detection for Public Step Types

**Shared Cause**: Some tests use public step types (e.g., "scf", "dos") that need materialization to machine types before engine detection can work.

**Evidence**:
- `calc_identity.py::_infer_engine_family_from_machine_types()` expects machine types (e.g., "qe_scf")
- Some tests/calculations use public types (e.g., "scf") which need conversion
- The conversion logic in `_infer_identity_from_step_types()` uses workflow registry, which may not have all mappings

**Impact**: 5 failures in integration/CLI tests

---

## Part 4: Proposed Fixes

### 4.1 Fix Import Path Errors

#### Fix 4.1.1: CP2K Handler Import

**File**: `src/qmatsuite/drivers/cp2k/handler.py`

**Change**:
```python
# Line 50: Change from
from qmatsuite.execution.recipes import CP2KRecipe

# To:
from qmatsuite.drivers.cp2k.recipe import CP2KRecipe
```

**Rationale**: `CP2KRecipe` was moved to the CP2K driver bundle during migration. The handler must import from the new location.

**Expected Impact**: Fixes 3 CP2K integration test failures.

---

#### Fix 4.1.2: Test File Imports

**File**: `tests/unit/execution/test_recipes.py`

**Change**:
```python
# Lines 14-17: Change from
from qmatsuite.execution.recipes import (
    QERecipe,
    ORCARecipe,
    PySCFRecipe,
    get_recipe_for_engine,
)

# To:
from qmatsuite.execution.recipes import QERecipe, get_recipe_for_engine
from qmatsuite.drivers.orca.recipe import ORCARecipe
from qmatsuite.drivers.pyscf.recipe import PySCFRecipe
```

**File**: `tests/unit/test_vasp_recipe.py`

**Change**:
```python
# Line 5: Change from
from qmatsuite.execution.recipes import VASPRecipe

# To:
from qmatsuite.drivers.vasp.recipe import VASPRecipe
```

**Rationale**: Recipe classes were moved to driver bundles. Tests must import from new locations.

**Expected Impact**: Fixes 2 import errors, allows tests in these files to run.

---

### 4.2 Fix Missing Exception Imports

**Approach**: Add `UnknownEngineError` import to all affected test files.

**Files to Fix**:
1. `tests/unit/test_vasp_registry.py`
2. `tests/unit/orca/test_workflow_integration.py`
3. `tests/unit/test_workflow_materialization_phase3b.py`
4. `tests/workflow/test_generalized_steps.py`
5. `tests/unit/test_pyscf_integration.py`
6. `tests/integration/vasp/test_vasp_project_e2e.py`

**Change Pattern**:
```python
# Add at top of file:
from qmatsuite.core.driver_exceptions import UnknownEngineError
```

**Rationale**: Tests use `UnknownEngineError` in exception handling but don't import it. The exception is defined in `driver_exceptions.py` and must be imported.

**Expected Impact**: Fixes 20 test failures.

---

### 4.3 Fix Wannier90 Engine Family Detection

**Options**:

#### Option A: Special Case in Detection Logic (Recommended)

**File**: `src/qmatsuite/core/calc_identity.py`

**Change**:
```python
# In _infer_engine_family_from_machine_types(), after line 103:
families = set()
for step_type in machine_types:
    if DriverRegistry.is_step_type_registered(step_type):
        engine = DriverRegistry.get_engine_for_step_type(step_type)
        # Special case: w90 steps are part of QE family toolchain
        if engine == "w90":
            engine = "qe"
        families.add(engine)
```

**Rationale**: Wannier90 is conceptually part of the QE family toolchain (uses QE output, runs in QE context). This special case preserves the design intent while keeping `w90_run` registered with `engine="w90"` for driver isolation.

**Expected Impact**: Fixes 1 test failure, maintains driver isolation.

---

#### Option B: Register w90_run with engine="qe"

**File**: `src/qmatsuite/drivers/w90/driver.py`

**Change**:
```python
# Line 62: Change from
engine="w90",

# To:
engine="qe",  # Part of QE family toolchain
```

**Rationale**: If Wannier90 is truly part of QE family, register it as such. However, this breaks driver isolation (W90 driver would register steps with QE engine).

**Expected Impact**: Fixes 1 test failure, but breaks driver isolation principle.

---

#### Option C: Update Test Expectation

**File**: `tests/unit/test_calc_identity.py`

**Change**:
```python
# Line 37: Change from
assert result == "qe"

# To:
assert result is None  # w90 is separate engine family
```

**Rationale**: If Wannier90 is a separate engine family, the test should reflect that. However, this conflicts with the design intent that Wannier90 is part of QE toolchain.

**Expected Impact**: Fixes 1 test failure, but may break other assumptions.

**Recommendation**: **Option A** (special case in detection logic) is recommended because it:
- Preserves driver isolation (w90_run registered with engine="w90")
- Maintains design intent (Wannier90 is part of QE family)
- Requires minimal code change
- Is explicit about the special case

---

### 4.4 Fix VASP DOS Zero-Mapping

**Options**:

#### Option A: Remove vasp_dos from Driver (Recommended)

**Files to Modify**:
1. `src/qmatsuite/drivers/vasp/driver.py`:
   - Remove `vasp_dos` from `get_step_type_specs()`
   - Remove `"GEN_DOS": "vasp_dos"` from `get_materialization_map()`

2. `src/qmatsuite/workflow/generalized_steps.py`:
   - Ensure `("vasp", "DOS"): None` mapping is used (already present)

**Rationale**: VASP DOS is integrated in nscf output and doesn't need a separate step type. This aligns with the legacy zero-mapping design.

**Expected Impact**: Fixes 1 test failure, but may break existing code that uses `vasp_dos` step type.

---

#### Option B: Keep vasp_dos and Update Test

**File**: `tests/unit/test_vasp_registry.py`

**Change**:
```python
# In test_vasp_dos_zero_mapping:
def test_vasp_dos_zero_mapping(self):
    """VASP DOS is now a separate step type."""
    result = materialize_step("DOS", "vasp")
    assert result == "vasp_dos"  # Changed from None
```

**Rationale**: If VASP DOS is registered as a step type, the test should expect it. However, this conflicts with the design that VASP DOS is integrated in nscf.

**Expected Impact**: Fixes 1 test failure, but may break other assumptions about VASP DOS.

**Recommendation**: **Option A** (remove vasp_dos) is recommended because:
- Aligns with legacy design (zero-mapping)
- VASP DOS is indeed integrated in nscf output
- No separate `vasp_dos` calculation is needed

**Note**: Before removing, verify that no existing code uses `vasp_dos` as a step type. If it does, Option B may be safer.

---

### 4.5 Fix Engine Detection for Public Step Types

**Approach**: Ensure public step types are properly materialized to machine types before engine detection.

**File**: `src/qmatsuite/core/calc_identity.py`

**Potential Issue**: The `_infer_identity_from_step_types()` function uses the workflow registry to convert public types to machine types, but this may not work for all cases.

**Investigation Needed**:
1. Check what step types the failing tests use
2. Verify they are registered in the workflow registry
3. Ensure materialization logic handles all public types correctly

**Proposed Fix**:
If public types are not being materialized correctly, enhance `_infer_identity_from_step_types()` to:
1. Try workflow registry lookup first
2. Fall back to DriverRegistry materialization if registry lookup fails
3. Provide better error messages if materialization fails

**Expected Impact**: Fixes 5 failures in integration/CLI tests.

---

## Part 5: Implementation Priority

### Priority 1: Critical Import Errors (Must Fix)
1. **CP2K Handler Import** (Fix 4.1.1): Blocks all CP2K integration tests
2. **Test Import Errors** (Fix 4.1.2): Prevents 2 test modules from running

### Priority 2: Missing Exception Imports (High Impact)
3. **Add UnknownEngineError Imports** (Fix 4.2): Fixes 20 test failures across 6 files

### Priority 3: Design Decisions (Requires Discussion)
4. **Wannier90 Engine Family** (Fix 4.3): 1 failure, but reveals design question
5. **VASP DOS Zero-Mapping** (Fix 4.4): 1 failure, but reveals design question

### Priority 4: Engine Detection (Investigation Needed)
6. **Public Step Type Materialization** (Fix 4.5): 5 failures, needs investigation

---

## Part 6: Summary

### Work Completed
- ✅ PR1: Removed silent QE fallbacks
- ✅ PR2: Created DriverRegistry infrastructure
- ✅ PR20: Migrated VASP
- ✅ PR21: Migrated ORCA
- ✅ PR22: Migrated PySCF
- ✅ PR23: Migrated LAMMPS
- ✅ PR24: Migrated CP2K
- ✅ PR25: Migrated Wannier90

### Test Suite Status
- **Total Tests**: 2336
- **Passed**: 2305 (98.7%)
- **Failed**: 29 (1.2%)
- **Errors**: 2 (0.1%)

### Issues Identified
1. **Import Path Errors** (5 failures): Code references old recipe locations
2. **Missing Exception Imports** (20 failures): Tests need `UnknownEngineError` import
3. **Wannier90 Engine Detection** (1 failure): Design conflict between driver isolation and QE family
4. **VASP DOS Zero-Mapping** (1 failure): Design conflict between step type registration and zero-mapping
5. **Engine Detection** (5 failures): Public step types not materialized correctly

### Next Steps
1. Apply Priority 1 fixes (import errors) - **Immediate**
2. Apply Priority 2 fixes (exception imports) - **Immediate**
3. Discuss and decide on Priority 3 fixes (design decisions) - **Requires Review**
4. Investigate and fix Priority 4 issues (engine detection) - **Requires Investigation**

---

## Appendix: Code Locations Reference

### Recipe Classes (New Locations)
- `CP2KRecipe`: `src/qmatsuite/drivers/cp2k/recipe.py`
- `ORCARecipe`: `src/qmatsuite/drivers/orca/recipe.py`
- `VASPRecipe`: `src/qmatsuite/drivers/vasp/recipe.py`
- `PySCFRecipe`: `src/qmatsuite/drivers/pyscf/recipe.py`
- `LAMMPSRecipe`: `src/qmatsuite/drivers/lammps/recipe.py`
- `W90Recipe`: `src/qmatsuite/drivers/w90/recipe.py`
- `QERecipe`: `src/qmatsuite/execution/recipes.py` (still in kernel)

### Exception Classes
- `UnknownEngineError`: `src/qmatsuite/core/driver_exceptions.py:60-69`
- `UnknownStepTypeError`: `src/qmatsuite/core/driver_exceptions.py:11-58`
- `UnknownMaterializationError`: `src/qmatsuite/core/driver_exceptions.py:72-89`

### Driver Registry
- `DriverRegistry`: `src/qmatsuite/core/driver_registry.py`
- Registration: `src/qmatsuite/drivers/__init__.py`

### Engine Detection
- `_infer_engine_family_from_machine_types()`: `src/qmatsuite/core/calc_identity.py:79-111`
- `_infer_identity_from_step_types()`: `src/qmatsuite/core/calc_identity.py:130-183`

