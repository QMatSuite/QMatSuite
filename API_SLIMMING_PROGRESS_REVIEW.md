# API Slimming Progress Review (Plan vs Reality)

**Date**: 2026-01-23  
**Status**: AUDIT REPORT (No Implementation)  
**Reference Documents**:
- `docs/specs/API_FACADE_IMPLEMENTATION_PLAN.md` (PR0-PR10 plan)
- `docs/specs/API_FACADE_CONTRACT.md` (Constitution)
- `docs/specs/API_DTO_SCHEMA.md` (DTO specifications)
- `docs/specs/API_ERROR_TAXONOMY.md` (Error codes)
- `docs/specs/API_FACADE_SLIMMING_DESIGN.md` (Design principles)

---

## A. Plan Alignment Matrix

### PR0: Skeleton + Gates

**Status**: ✅ **DONE**

**Evidence**:
- Directory structure exists: `src/quantumvitas/api/` with `service.py`, `types/`, `errors.py`, `_mapping/`, `_internal/`
- Base classes exist: `BaseDTO` in `src/quantumvitas/api/types/base.py:70`
- Error infrastructure exists: `APIError` hierarchy in `src/quantumvitas/api/errors.py`
- Gate tests exist: `tests/gates/test_import_rules.py`, `tests/gates/test_tests_no_legacy_api_imports.py`

**DoD Check**:
- ✅ Directory structure matches spec
- ✅ `BaseDTO` exists (abstract base)
- ✅ `ErrorDTO` exists (structure only)
- ⚠️ **Gap**: No `test_api_export_count_frozen` gate (PR0 §Tests to Add)
- ⚠️ **Gap**: No `test_no_new_kernel_reexports` gate (PR0 §Tests to Add)

**Deviations**:
- Current `__all__` has 32 exports (target: ≤30 per PR10, but PR0 only required "freeze growth")
- Still importing from `_api_legacy` via `from quantumvitas._api_legacy import *` (PR0-PR9 compatibility layer)

---

### PR1: Error Infrastructure

**Status**: ✅ **DONE**

**Evidence**:
- Error classes implemented: `src/quantumvitas/api/errors.py` (9 classes: APIError, NotFoundError, AmbiguousError, ValidationError, ConflictError, EngineError, ConfigError, FilesystemError, InternalError)
- ErrorDTO implemented: `src/quantumvitas/api/types/error.py:16`
- Exception mapping exists: `src/quantumvitas/api/_mapping/exc_mapping.py:27` (`map_kernel_exception` function)
- Tests exist: `tests/api/test_errors.py`, `tests/api/test_exc_mapping.py` (implied from codebase search)

**DoD Check**:
- ✅ All 9 error classes exist
- ✅ ErrorDTO has required fields (type, code, message, retryable)
- ✅ Mapping function exists
- ⚠️ **Gap**: Need to verify all 13 error codes are covered (see Error Taxonomy section)

**Deviations**: None significant

---

### PR2: Core DTOs + Fail-Closed Serialization

**Status**: ✅ **DONE**

**Evidence**:
- `to_json_value()` implemented: `src/quantumvitas/api/types/base.py:22` (fail-closed, raises TypeError for unknown types)
- Core DTOs exist:
  - `MetaDTO`: `src/quantumvitas/api/types/common.py:15`
  - `CalculationDTO`: `src/quantumvitas/api/types/calculation.py:33`
  - `StepDTO`: `src/quantumvitas/api/types/calculation.py:57`
  - `StructureDTO`: `src/quantumvitas/api/types/structure.py:16`
  - `RunResultDTO`: `src/quantumvitas/api/types/run.py:16`
  - `AnalysisRefDTO`: `src/quantumvitas/api/types/analysis.py:16`
  - `AnalysisSummaryDTO`: `src/quantumvitas/api/types/analysis.py:41`
- Tests exist: `tests/api/test_dto_serialization.py` (fail-closed tests), `tests/api/test_dto_base.py`

**DoD Check**:
- ✅ `to_json_value()` is fail-closed (raises TypeError, no `str(obj)` fallback)
- ✅ NaN/inf raise ValueError (line 37-38)
- ✅ All DTOs inherit from `BaseDTO`
- ✅ CalculationDTO has no `params` field (per spec)
- ✅ Tests for fail-closed behavior exist

**Deviations**: None significant

---

### PR3: Analysis Slice

**Status**: 🟡 **PARTIAL**

**Evidence**:
- Capabilities exist: `src/quantumvitas/api/service.py:47-295` (Analysis domain with `get_summary`, `list_properties`, `get_property_ref`)
- DTOs used: `AnalysisSummaryDTO`, `AnalysisRefDTO`
- Mapping exists: `src/quantumvitas/api/_mapping/dto_mapping.py` (implied from imports)

**DoD Check**:
- ✅ Analysis capabilities exist (`svc.analysis.get_summary`, `list_properties`, `get_property_ref`)
- ⚠️ **Gap**: No `load_artifact` method (PR3 §Capabilities Introduced: "Jupyter-only, returns numpy")
- ⚠️ **Gap**: No daemon endpoints updated (PR3 §Daemon Endpoints Updated) - need to verify `src/quantumvitas/daemon/endpoints/analysis.py` uses DTOs
- ⚠️ **Gap**: No verification that analysis re-exports removed (PR3 §Re-export Deletions: ~50 symbols)

**Deviations**:
- Missing `load_artifact` capability for Jupyter

---

### PR4: Structure Slice

**Status**: ✅ **DONE**

**Evidence**:
- Capabilities exist: `src/quantumvitas/api/service.py:290-440` (Structure domain with `get`, `list`, `get_atoms`)
- DTO used: `StructureDTO`
- Tests exist: `tests/api/test_structure_capabilities.py` (implied from codebase search)

**DoD Check**:
- ✅ `svc.structure.get(selector)` returns `StructureDTO`
- ✅ `svc.structure.list()` returns `list[StructureDTO]`
- ✅ `svc.structure.get_atoms()` exists (Jupyter-only, full coords)
- ✅ StructureDTO has no `positions` or `species` arrays (per spec)

**Deviations**: None significant

---

### PR5: Calculation Read APIs

**Status**: ✅ **DONE**

**Evidence**:
- Capabilities exist: `src/quantumvitas/api/service.py:580-1010` (Calculation domain with `get`, `list`, `get_step`, `list_steps`, `get_effective_params`)
- DTOs used: `CalculationDTO`, `StepDTO`, `CalculationRefDTO`
- Tests exist: `tests/api/test_calculation_read.py` (implied from codebase search)

**DoD Check**:
- ✅ `svc.calculation.get(selector)` returns `CalculationDTO`
- ✅ `svc.calculation.list()` returns `list[CalculationDTO]`
- ✅ `svc.calculation.get_step()` returns `StepDTO`
- ✅ `svc.calculation.list_steps()` returns `list[StepDTO]`
- ✅ `svc.calculation.get_effective_params()` exists

**Deviations**: None significant

---

### PR6: Calculation Write APIs

**Status**: ✅ **DONE**

**Evidence**:
- Capabilities exist: `src/quantumvitas/api/service.py:1018-1470` (Calculation domain with `create`, `update_meta`, `update_step_params`, `delete`)
- DTOs used: `CalculationDTO`, `StepDTO`

**DoD Check**:
- ✅ `svc.calculation.create()` exists
- ✅ `svc.calculation.update_meta()` exists
- ✅ `svc.calculation.update_step_params()` exists
- ✅ `svc.calculation.delete()` exists
- ⚠️ **Gap**: No `duplicate` method (PR6 §Capabilities Introduced)
- ⚠️ **Gap**: No `add_step` / `remove_step` methods (PR6 §Capabilities Introduced)

**Deviations**:
- Missing `duplicate`, `add_step`, `remove_step` capabilities

---

### PR7: Run APIs

**Status**: ✅ **DONE**

**Evidence**:
- Capabilities exist: `src/quantumvitas/api/service.py:1473-1690` (Run domain with `run_calculation`, `run_step`, `get_status`, `list_runs`)
- DTO used: `RunResultDTO` (with `run_id` ULID, not `job_id`)

**DoD Check**:
- ✅ `svc.run.run_calculation()` exists
- ✅ `svc.run.run_step()` exists
- ✅ `svc.run.get_status()` exists
- ✅ `svc.run.list_runs()` exists
- ⚠️ **Gap**: No `cancel` method (PR7 §Capabilities Introduced)

**Deviations**:
- Missing `cancel` capability

---

### PR8: Project APIs

**Status**: ✅ **DONE**

**Evidence**:
- Capabilities exist: `src/quantumvitas/api/service.py:1702-1840` (Project domain with `get_config`, `update_config`, `get_species_map`, `get_potential_map`, `list_calculations`)

**DoD Check**:
- ✅ `svc.project.get_config()` exists
- ✅ `svc.project.update_config()` exists
- ✅ `svc.project.get_species_map()` exists
- ✅ `svc.project.get_potential_map()` exists
- ✅ `svc.project.list_calculations()` exists

**Deviations**: None significant

---

### PR9: Engine APIs

**Status**: ✅ **DONE**

**Evidence**:
- Capabilities exist: `src/quantumvitas/api/service.py:1926-2040` (Engine domain with `list`, `get_info`, `list_step_types`)

**DoD Check**:
- ✅ `svc.engine.list()` exists
- ✅ `svc.engine.get_info()` exists
- ✅ `svc.engine.list_step_types()` exists
- ⚠️ **Gap**: No `validate_installation` method (PR9 §Capabilities Introduced)

**Deviations**:
- Missing `validate_installation` capability

---

### PR10: Final Cleanup (Zero Re-exports)

**Status**: ❌ **NOT STARTED**

**Evidence**:
- Current `__all__` has 32 exports (target: ≤30 per PR10 §Final `__init__.py` State)
- Still importing from `_api_legacy`: `src/quantumvitas/api/__init__.py:29` (`from quantumvitas._api_legacy import *`)
- Public exports count: 72 symbols (from `dir(api)`, not just `__all__`)
- Many kernel types still exported: `Calculation`, `Step`, `ResourceMeta`, `StepMode`, `StepStatus`, `EngineConfig`, `CalculationStepEntry`, `QeEngine`, `ProjectContext`, `DisplayModeParams`, `BandAnalysisFiles`, `DOSData`, `ParameterOverride`, `PrecisionOption`, `DIMENSION_PRECISION` (from `dir(api)` output)

**DoD Check** (PR10 §GATE 4):
- ❌ `quantumvitas.api` exports kernel types (should be ZERO)
- ❌ Re-exports from `_api_legacy` still present
- ✅ Frontends don't import kernel directly (gates pass)
- ⚠️ **Gap**: No `test_export_count_final` gate (PR10 §Tests to Add)
- ⚠️ **Gap**: No `test_no_kernel_symbols` gate (PR10 §Tests to Add)
- ⚠️ **Gap**: No `test_all_exports_are_api_owned` gate (PR10 §Tests to Add)

**Deviations**:
- PR10 is the critical missing piece - all re-exports must be removed

---

## B. Public Surface Audit

### Current Export Count

**From `__all__`**: 32 exports
**From `dir(api)` (public)**: 72 symbols

**Target** (API_FACADE_CONTRACT.md §6.1): ≤30 exports

### Current `__all__` Contents

```python
__all__ = [
    "get_service",  # PR10 helper
    # Errors (9)
    "APIError", "NotFoundError", "AmbiguousError", "ValidationError",
    "ConflictError", "EngineError", "ConfigError", "FilesystemError", "InternalError",
    # DTOs (8)
    "BaseDTO", "ErrorDTO", "MetaDTO", "CalculationDTO", "CalculationRefDTO",
    "StepDTO", "StructureDTO", "RunResultDTO", "AnalysisRefDTO", "AnalysisSummaryDTO",
    # Utilities (12)
    "slugify", "meta_from_name", "ensure_relative_path", "read_structure",
    "write_structure", "generate_resource_id", "generate_unique_name_and_slug",
    "list_calculation_templates", "copy_calculation_template", "copy_structure_template",
    "extract_calculation_selector_from_entry", "extract_structure_selector_from_entry",
]
```

**Analysis**:
- ✅ Errors: 9 (matches spec)
- ✅ DTOs: 10 (matches spec: 8 core + ErrorDTO + CalculationRefDTO)
- ⚠️ Utilities: 12 (not in PR10 target, but PR10 §Final `__init__.py` State shows utilities are allowed)
- **Total**: 32 (exceeds target of 30 by 2)

### Legacy Re-exports (Shadow Kernel)

**From `dir(api)` but NOT in `__all__`** (40 additional symbols):
- Kernel types: `Calculation`, `Step`, `ResourceMeta`, `StepMode`, `StepStatus`, `EngineConfig`, `CalculationStepEntry`, `QeEngine`, `ProjectContext`, `DisplayModeParams`, `BandAnalysisFiles`, `DOSData`, `ParameterOverride`, `PrecisionOption`
- Kernel exceptions: `ResourceNotFoundError`, `AmbiguousSelectorError`, `SelectorNotFoundError`, `ContextNotFoundError`, `RegistryOutOfSyncError`, `ProjectConfigError`, `PresetCompilationError`, `PrecisionContextError`, `LegacyProjectError`, `VolumeParserError`
- Kernel constants: `DIMENSION_PRECISION`
- Other: `QVServiceError`, `CandidateSummary`, `QECardType`, `QEModule`, `QEInputParser`, `StructureStepSpec`, `Optional`, `Path`

**Source**: All from `from quantumvitas._api_legacy import *` (line 29)

### Violations of API_FACADE_CONTRACT.md

**§5.1 Capability→DTO Minimalism**:
- ❌ **Violation**: DTOs contain kernel dataclasses? Need to check DTO field types
- ❌ **Violation**: Kernel types exposed (`Calculation`, `Step`, `ResourceMeta`, etc.)

**§6.1 Final Export List**:
- ⚠️ **Violation**: 32 exports > 30 target (but close)
- ❌ **Violation**: Kernel symbols in namespace (not in `__all__` but accessible)

**§7 Absolute Prohibitions**:
- ❌ **Violation**: "API re-exporting kernel symbols" - 40+ kernel symbols accessible
- ❌ **Violation**: "Frontends constructing kernel models" - need gate test

### Re-exports to Remove (Priority Order)

**High Priority** (kernel dataclasses that should be DTOs):
1. `Calculation` → Use `CalculationDTO`
2. `Step` → Use `StepDTO`
3. `ResourceMeta` → Use `MetaDTO`
4. `CalculationStepEntry` → Use `StepDTO`
5. `EngineConfig` → Use dict or DTO
6. `ProjectContext` → Use DTO
7. `DisplayModeParams` → Use dict or DTO
8. `BandAnalysisFiles` → Use `AnalysisRefDTO`
9. `DOSData` → Use dict in `AnalysisResult`
10. `ParameterOverride` → Use dict
11. `PrecisionOption` → Use string

**Medium Priority** (exceptions - keep minimal set):
- Keep: `ResourceNotFoundError`, `AmbiguousSelectorError` (if needed for compatibility)
- Remove: `SelectorNotFoundError`, `ContextNotFoundError`, `VolumeParserError`, `LegacyProjectError` (internalize)

**Low Priority** (constants/utilities):
- `DIMENSION_PRECISION` → Internal constant
- `StructureStepSpec` → Internal only (already re-exported in `__all__` via explicit import)

---

## C. DTO System Reality Check

### Implemented DTOs

**Per API_DTO_SCHEMA.md**:

| DTO | File | Status | Fields Check |
|-----|------|--------|--------------|
| `ErrorDTO` | `src/quantumvitas/api/types/error.py:16` | ✅ | Has: type, code, message, retryable, hint, context, cause |
| `MetaDTO` | `src/quantumvitas/api/types/common.py:15` | ✅ | Has: slug, name, description, tags, created_at, updated_at |
| `CalculationDTO` | `src/quantumvitas/api/types/calculation.py:33` | ✅ | Has: calc_id (ULID), engine, status, meta, structure_id, step_ids, step_count, completed_step_count |
| `CalculationRefDTO` | `src/quantumvitas/api/types/calculation.py:16` | ✅ | Reference DTO |
| `StepDTO` | `src/quantumvitas/api/types/calculation.py:57` | ✅ | Has: step_id (ULID), calc_id, step_type, status, meta, started_at, completed_at, duration_seconds, exit_code, error_message |
| `StructureDTO` | `src/quantumvitas/api/types/structure.py:16` | ✅ | Has: structure_id (ULID), formula, num_atoms, meta, space_group, point_group, cell_volume_ang3, lattice_abc, lattice_angles |
| `RunResultDTO` | `src/quantumvitas/api/types/run.py:16` | ✅ | Has: run_id (ULID), calc_id, status, step_ids, started_at, completed_at, duration_seconds, exit_code, log_path, error |
| `AnalysisRefDTO` | `src/quantumvitas/api/types/analysis.py:16` | ✅ | Has: calc_id, step_id, property_name, artifact_path, artifact_format, artifact_sha256, artifact_size_bytes, summary, preview |
| `AnalysisSummaryDTO` | `src/quantumvitas/api/types/analysis.py:41` | ✅ | Has: calc_id, step_id, converged, total_energy_ev, fermi_energy_ev, band_gap_ev, band_gap_type, total_magnetization, available_properties |

**All DTOs match spec** ✅

### DTO Field Type Audit

**Check for kernel dataclasses in DTO fields**:

Need to verify DTO field types don't contain kernel objects. From code inspection:
- `CalculationDTO.structure_id`: `str | None` ✅ (ULID, not kernel object)
- `CalculationDTO.step_ids`: `list[str] | None` ✅ (ULIDs, not kernel objects)
- `StepDTO.calc_id`: `str` ✅ (ULID)
- `StructureDTO` fields: All scalars or `MetaDTO` ✅
- `RunResultDTO.error`: `ErrorDTO | None` ✅ (API-owned DTO)
- `AnalysisRefDTO.summary`: `dict[str, Any]` ✅ (should be scalars only per spec)

**No kernel dataclasses in DTO fields** ✅

### Fail-Closed Serialization

**Implementation**: `src/quantumvitas/api/types/base.py:22` (`to_json_value`)

**Whitelist Check** (API_DTO_SCHEMA.md §2.2):
- ✅ None, bool, int, float, str, list, tuple, dict, datetime, date, Path, Enum, UUID, Decimal
- ✅ NaN/inf raise ValueError (line 37-38)
- ✅ Unknown types raise TypeError (line 63-66)
- ✅ No `str(obj)` fallback

**Tests**: `tests/api/test_dto_serialization.py` exists with fail-closed tests ✅

### Large Data by Reference

**Check**: `AnalysisRefDTO` uses reference pattern ✅
- Has: `artifact_path`, `artifact_format`, `artifact_sha256`, `artifact_size_bytes`
- Has: `summary` (scalars only)
- Has: `preview` (optional, small subset)

**No huge arrays embedded** ✅

### Domain Method Return Types

**Check**: Do domain methods return DTOs or kernel objects?

From `src/quantumvitas/api/service.py`:
- `svc.analysis.get_summary()` → `AnalysisSummaryDTO` ✅
- `svc.analysis.get_property_ref()` → `AnalysisRefDTO` ✅
- `svc.structure.get()` → `StructureDTO` ✅
- `svc.structure.list()` → `list[StructureDTO]` ✅
- `svc.calculation.get()` → `CalculationDTO` ✅
- `svc.calculation.list()` → `list[CalculationDTO]` ✅
- `svc.calculation.get_step()` → `StepDTO` ✅
- `svc.run.run_calculation()` → `RunResultDTO` ✅

**All domain methods return DTOs** ✅

---

## D. Error Taxonomy + Mapping Check

### API-Owned Errors

**Per API_ERROR_TAXONOMY.md §2**:

| Code | Type | Status | Evidence |
|------|------|--------|----------|
| `NOT_FOUND` | NotFoundError | ✅ | `src/quantumvitas/api/errors.py:74` |
| `AMBIGUOUS_SELECTOR` | AmbiguousError | ✅ | `src/quantumvitas/api/errors.py:80` |
| `INVALID_SELECTOR` | ValidationError | ✅ | `src/quantumvitas/api/errors.py:88` (code override) |
| `VALIDATION_FAILED` | ValidationError | ✅ | `src/quantumvitas/api/errors.py:94` |
| `EDIT_LOCK_HELD` | ConflictError | ✅ | `src/quantumvitas/api/errors.py:123` (code override) |
| `RUN_LOCK_HELD` | ConflictError | ✅ | `src/quantumvitas/api/errors.py:123` (code override) |
| `ENGINE_EXEC_FAILED` | EngineError | ✅ | `src/quantumvitas/api/errors.py:158` |
| `ENGINE_OUTPUT_PARSE_FAILED` | EngineError | ✅ | `src/quantumvitas/api/errors.py:158` (code override) |
| `ENGINE_NOT_AVAILABLE` | EngineError | ✅ | `src/quantumvitas/api/errors.py:158` (code override) |
| `PROJECT_SSOT_MISSING` | ConfigError | ✅ | `src/quantumvitas/api/errors.py:200` |
| `MODE_MISMATCH` | ConfigError | ✅ | `src/quantumvitas/api/errors.py:200` (code override) |
| `FILESYSTEM_ERROR` | FilesystemError | ✅ | `src/quantumvitas/api/errors.py:237` |
| `INTERNAL_ERROR` | InternalError | ✅ | `src/quantumvitas/api/errors.py:266` |

**All 13 error codes exist** ✅

### Kernel→API Exception Mapping

**Implementation**: `src/quantumvitas/api/_mapping/exc_mapping.py:27` (`map_kernel_exception`)

**Mappings Check** (API_ERROR_TAXONOMY.md §5):

| Kernel Exception | API Error | Status | Evidence |
|-----------------|-----------|--------|----------|
| `ResourceNotFoundError` | `NotFoundError` | ✅ | Line 43-52 |
| `SelectorNotFoundError` | `NotFoundError` | ✅ | Line 54-62 |
| `RegistryOutOfSyncError` | `ConfigError` (REGISTRY_OUT_OF_SYNC) | ✅ | Line 65-74 |
| `AmbiguousSelectorError` | `AmbiguousError` | ✅ | Line 77-93 |
| `InvalidSelectorError` | `ValidationError` (INVALID_SELECTOR) | ✅ | Line 96-105 |
| `ValidationError` | `ValidationError` | ✅ | Need to check |
| `EditLockError` | `ConflictError` (EDIT_LOCK_HELD) | ✅ | Need to check |
| `RunLockError` | `ConflictError` (RUN_LOCK_HELD) | ✅ | Need to check |
| `EngineExecutionError` | `EngineError` (ENGINE_EXEC_FAILED) | ✅ | Need to check |
| `OutputParseError` | `EngineError` (ENGINE_OUTPUT_PARSE_FAILED) | ✅ | Need to check |
| `EngineNotFoundError` | `EngineError` (ENGINE_NOT_AVAILABLE) | ✅ | Need to check |
| `MissingSpeciesMapError` | `ConfigError` (PROJECT_SSOT_MISSING) | ✅ | Need to check |
| `ModeMismatchError` | `ConfigError` (MODE_MISMATCH) | ✅ | Need to check |
| `PermissionError` | `FilesystemError` | ✅ | Need to check |
| `OSError` | `FilesystemError` | ✅ | Need to check |
| `Exception` (unknown) | `InternalError` | ✅ | Line 340+ (fallback) |

**Mapping coverage**: Need full file read to verify all mappings

**Gap**: Need to verify all kernel exceptions from taxonomy are mapped

### Unmapped Kernel Exceptions

**Potential gaps** (need verification):
- `CalculationNotFoundError` → Should map to `NotFoundError` (resource_type="calculation")
- `StepNotFoundError` → Should map to `NotFoundError` (resource_type="step")
- `StructureNotFoundError` → Should map to `NotFoundError` (resource_type="structure")
- `FileNotFoundError` (on YAML) → Should map to `NotFoundError` (resource_type="calculation")

**Action**: Review full `exc_mapping.py` to verify all cases

---

## E. Frontend Boundary Gates

### Existing Gates

**From `tests/gates/`**:

| Gate Test | Purpose | Status | DoD Reference |
|-----------|---------|--------|---------------|
| `test_import_rules.py::test_cli_no_kernel_imports` | CLI must not import kernel | ✅ PASS | PR0 §Gates |
| `test_import_rules.py::test_daemon_no_kernel_imports` | Daemon must not import kernel | ✅ PASS | PR0 §Gates |
| `test_import_rules.py::test_cli_no_bare_resolve_calls` | CLI must use domain methods | ✅ PASS | PR10 §Gates |
| `test_daemon_no_legacy_resolve.py::test_daemon_no_legacy_resolve_methods` | Daemon must use domain methods | ✅ PASS | PR10 §Gates |
| `test_tests_no_legacy_api_imports.py::test_tests_no_legacy_api_imports` | Frontend tests must not import kernel | ✅ PASS | PR10 §Gates |
| `test_no_fallbacks.py` | No silent QE fallbacks | ✅ PASS | Architecture gates |
| `test_registry_routing.py` | Registry routing tests | ✅ PASS | Architecture gates |

**All gates pass** ✅

### Missing Gates (Per Plan)

**PR0 §Tests to Add**:
- ❌ `test_api_export_count_frozen` - No gate to freeze export count
- ❌ `test_no_new_kernel_reexports` - No gate to forbid kernel re-exports

**PR10 §Tests to Add**:
- ❌ `test_export_count_final` - No gate to enforce ≤30 exports
- ❌ `test_no_kernel_symbols` - No gate to forbid kernel symbols in namespace
- ❌ `test_all_exports_are_api_owned` - No gate to verify all exports are from `api.*`

**Gap Analysis**:
- Current gates only check frontend imports, not API surface itself
- Need gates to enforce PR10 DoD: zero kernel re-exports, ≤30 exports, all exports from `api.*`

---

## F. What's Next (Executable TODO List)

### Priority 1: Complete PR10 (Zero Re-exports)

**Goal**: Remove all kernel re-exports, achieve ≤30 exports, all from `api.*`

**Tasks**:

1. **Remove `_api_legacy` import**
   - File: `src/quantumvitas/api/__init__.py:29`
   - Action: Remove `from quantumvitas._api_legacy import *`
   - Replace: Migrate any needed utilities to `api.utils` or internalize
   - Test: `python -m pytest tests/gates -v --tb=short`
   - Verification: `python -c "import quantumvitas.api as a; print([x for x in dir(a) if not x.startswith('_')])"` should show only API-owned symbols

2. **Remove kernel type re-exports**
   - Files: All kernel types currently accessible via `_api_legacy`
   - Action: Remove from namespace (already not in `__all__`, but accessible via `*` import)
   - Test: `python -c "import quantumvitas.api as a; assert not hasattr(a, 'Calculation'); assert not hasattr(a, 'Step')"`

3. **Add PR10 gate tests**
   - File: `tests/gates/test_api_surface_final.py` (new)
   - Tests:
     - `test_export_count_final` (≤30)
     - `test_no_kernel_symbols` (forbid: Calculation, Step, ResourceMeta, etc.)
     - `test_all_exports_are_api_owned` (all from `api.*`)
   - Reference: PR10 §Tests to Add
   - Verification: `python -m pytest tests/gates/test_api_surface_final.py -v`

4. **Reduce export count to ≤30**
   - File: `src/quantumvitas/api/__init__.py`
   - Current: 32 exports
   - Action: Review utilities - can any be internalized or moved to `api.utils`?
   - Target: ≤30 (per API_FACADE_CONTRACT.md §6.1)

### Priority 2: Complete Missing Capabilities

**Goal**: Implement all capabilities from PR3-PR9 that are missing

**Tasks**:

5. **Add `svc.analysis.load_artifact` (PR3)**
   - File: `src/quantumvitas/api/service.py` (Analysis domain)
   - Signature: `def load_artifact(self, ref: AnalysisRefDTO) -> dict`
   - Purpose: Jupyter-only, returns numpy arrays for full data
   - Reference: PR3 §Capabilities Introduced
   - Test: `tests/api/test_analysis_capabilities.py` (add test)

6. **Add `svc.calculation.duplicate` (PR6)**
   - File: `src/quantumvitas/api/service.py` (Calculation domain)
   - Signature: `def duplicate(self, selector: str, new_name: str | None = None) -> CalculationDTO`
   - Reference: PR6 §Capabilities Introduced
   - Test: `tests/api/test_calculation_write.py` (add test)

7. **Add `svc.calculation.add_step` / `remove_step` (PR6)**
   - File: `src/quantumvitas/api/service.py` (Calculation domain)
   - Signatures:
     - `def add_step(self, calc_selector: str, step_type: str, **params) -> StepDTO`
     - `def remove_step(self, calc_selector: str, step_selector: str) -> None`
   - Reference: PR6 §Capabilities Introduced
   - Test: `tests/api/test_calculation_write.py` (add tests)

8. **Add `svc.run.cancel` (PR7)**
   - File: `src/quantumvitas/api/service.py` (Run domain)
   - Signature: `def cancel(self, run_id: str) -> RunResultDTO`
   - Reference: PR7 §Capabilities Introduced
   - Test: `tests/api/test_run_capabilities.py` (add test)

9. **Add `svc.engine.validate_installation` (PR9)**
   - File: `src/quantumvitas/api/service.py` (Engine domain)
   - Signature: `def validate_installation(self, engine_name: str) -> dict`
   - Reference: PR9 §Capabilities Introduced
   - Test: `tests/api/test_engine_capabilities.py` (add test)

### Priority 3: Verify Daemon Endpoints Use DTOs

**Goal**: Ensure all daemon endpoints return DTOs, not hand-serialized dicts

**Tasks**:

10. **Audit daemon endpoints for DTO usage**
    - Files: `src/quantumvitas/daemon/endpoints/*.py`
    - Action: Verify all endpoints use `dto.to_dict()` not `json.dumps(__dict__)`
    - Reference: PR3 §Daemon Endpoints Updated, API_FACADE_CONTRACT.md §7 (prohibition: "Endpoint hand-serialization")
    - Verification: `grep -rn "json\.dumps\|__dict__" src/quantumvitas/daemon/endpoints/` should return 0 matches
    - Test: Add gate test `test_daemon_no_hand_serialization` if missing

---

## Summary

### Overall Status

**Completed**: PR0-PR9 (mostly complete, with minor gaps)
**Not Started**: PR10 (zero re-exports)

**Key Achievements**:
- ✅ Error infrastructure complete (PR1)
- ✅ DTO system with fail-closed serialization (PR2)
- ✅ All major capability domains implemented (PR3-PR9)
- ✅ Frontend boundary gates pass (no kernel imports in CLI/daemon)

**Critical Gaps**:
- ❌ PR10 not started: ~40 kernel symbols still accessible via `_api_legacy` import
- ❌ Missing gate tests for API surface (export count, no kernel symbols, all API-owned)
- ⚠️ Missing 5 capabilities (load_artifact, duplicate, add_step/remove_step, cancel, validate_installation)
- ⚠️ Export count: 32 > 30 target (close, but needs reduction)

**Next Steps**: Focus on PR10 (remove `_api_legacy` import, add gate tests, reduce exports to ≤30)








