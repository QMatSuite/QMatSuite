# Test Migration Plan for PR10 API Slimming

**Date:** 2025-01-XX  
**Purpose:** Restore full pytest suite to green while maintaining PR10/PR6 architectural constraints  
**Status:** Planning Phase (No Code Changes)

---

## (1) Executive Summary

### Current Pytest Failure Overview

**Baseline Test Run Results:**
- **Total Tests:** 2,590
- **Passed:** 2,298 (88.7%)
- **Failed:** 222 (8.6%)
- **Errors:** 67 (2.6%)
- **Total Issues:** 289

**Top Three Failure Categories:**

1. **Bucket A: Missing QVService Methods** (~200+ tests)
   - `AttributeError: type object 'QVService' has no attribute 'init_step'` (160 occurrences)
   - `AttributeError: type object 'QVService' has no attribute 'add_step_to_calculation'` (42 occurrences)
   - Many other missing static/instance methods removed during PR10

2. **Bucket B: Missing API Type Exports** (~30 tests)
   - `ImportError: cannot import name 'QECardType' from 'quantumvitas.api'`
   - `ImportError: cannot import name 'StructureStepSpec' from 'quantumvitas.api'`
   - Tests expect kernel types to be re-exported from `quantumvitas.api` (violates PR10)

3. **Bucket C: Path/Assertion Issues** (~20 tests)
   - Path double-append bugs (mostly fixed, 0 remaining)
   - Assertion mismatches (status string format, etc.)
   - CLI subprocess failures (cascading from missing methods)

### Why Test Layering Matters

**Contract Tests vs Kernel Tests:**

Contract tests verify **external behavior** through public APIs (QVService, daemon endpoints, CLI commands). They assert DTO fields, JSON serialization, and high-level capabilities. These tests must **not** depend on kernel internals (`.meta.id`, internal dataclasses, core imports).

Kernel tests verify **internal semantics** (models, algorithms, serialization, invariants). They can directly import `quantumvitas.core`, assert internal object structure, and test implementation details. These tests are **not** affected by PR10 API slimming.

**The Problem:** Many tests are "contract tests in name" but "kernel tests in practice" - they call QVService but assert internal object structure (`.meta.id`), or they import kernel types from `quantumvitas.api`. PR10 removed these exports, breaking the tests.

**The Solution:** Separate contract tests (which must migrate to DTO assertions) from kernel tests (which can keep internal assertions). This allows us to fix contract tests without breaking kernel test coverage.

---

## (2) Test Inventory Table

| File Path | Classification | Evidence | Current Failure Type | Suggested Action |
|-----------|---------------|----------|---------------------|------------------|
| `tests/api/test_*.py` (17 files) | **CONTRACT** | Uses `QVService`, asserts DTOs, no core imports | AttributeError (missing methods), ImportError (missing exports) | MIGRATE_ASSERTIONS: Use compat layer, fix imports |
| `tests/daemon/test_*.py` (14 files) | **CONTRACT** | Tests daemon endpoints, uses QVService, asserts JSON/DTOs | AttributeError (init_step, add_step_to_calculation) | MIGRATE_ASSERTIONS: Use compat layer for missing methods |
| `tests/cli/test_*.py` (9 files) | **CONTRACT** | Tests CLI commands via subprocess, asserts output | AttributeError (cascading), AssertionError (status format) | MIGRATE_ASSERTIONS: Fix status string expectations |
| `tests/gates/test_*.py` (10 files) | **CONTRACT** | Architectural gate tests, scan source code | Mostly passing | KEEP |
| `tests/integration/test_*.py` (41 files) | **MIXED** | Mix of contract (QVService) and kernel (core imports, .meta.id) | AttributeError, Path bugs | **SPLIT**: Contract parts → MIGRATE_ASSERTIONS, Kernel parts → MOVE_TO_KERNEL |
| `tests/unit/test_api_service*.py` | **CONTRACT** | Tests QVService facade, expects old API surface | AttributeError (many missing methods) | MIGRATE_ASSERTIONS: Use compat layer or new API |
| `tests/unit/test_workflow.py` | **CONTRACT** | Uses QVService.calc_set_steps | AttributeError | MIGRATE_ASSERTIONS: Use compat layer |
| `tests/unit/test_analysis_artifacts.py` | **CONTRACT** | Uses QVService.get_reference_analysis | AttributeError | MIGRATE_ASSERTIONS: Use compat layer |
| `tests/core/test_*.py` (9 files) | **KERNEL** | Direct core imports, tests internal models/algorithms | Mostly passing | KEEP (no migration needed) |
| `tests/unit/test_*.py` (149 files, excluding api_service) | **MIXED** | Varies: some kernel (core imports), some contract (QVService) | Varies | **AUDIT EACH**: Classify by imports and assertions |
| `tests/integration/orca/test_*.py` (4 files) | **MIXED** | Uses QVService but also core imports | AttributeError, Path bugs | **SPLIT**: Contract → MIGRATE, Kernel → KEEP |
| `tests/integration/vasp/test_*.py` (5 files) | **MIXED** | Similar to orca tests | AttributeError | **SPLIT** |
| `tests/drivers/*/test_*.py` (6 files) | **KERNEL** | Tests driver internals, core imports | Mostly passing | KEEP |
| `tests/ir/test_*.py` (3 files) | **KERNEL** | Tests IR mapping, core imports | Mostly passing | KEEP |
| `tests/presets/test_*.py` (2 files) | **KERNEL** | Tests preset internals | Mostly passing | KEEP |
| `tests/workflow/test_*.py` (1 file) | **KERNEL** | Tests workflow internals | Mostly passing | KEEP |

### Classification Evidence Patterns

**CONTRACT Indicators:**
- `from quantumvitas.api import QVService`
- `QVService.init_step()`, `QVService.run_calculation()`, etc.
- Tests daemon endpoints (`QVDaemon.handle_request()`)
- Tests CLI commands (subprocess calls)
- Asserts DTO fields (`step_id`, `calc_id`, `structure_id`)
- Asserts JSON serialization
- Located in `tests/api/`, `tests/daemon/`, `tests/cli/`, `tests/gates/`

**KERNEL Indicators:**
- `from quantumvitas.core import ...`
- `from quantumvitas.kernel import ...` (if exists)
- Direct imports of internal models (`CalculationModel`, `StepDoc`, etc.)
- Asserts `.meta.id`, `.meta.slug` (internal ResourceMeta)
- `isinstance(obj, CoreClass)`
- Tests internal algorithms, serialization, invariants
- Located in `tests/core/`, `tests/drivers/`, `tests/ir/`, `tests/presets/`

**AMBIGUOUS (Requires Manual Review):**
- `tests/integration/test_*.py` - Mix of contract and kernel patterns
- `tests/unit/test_*.py` (non-API) - Need to check each file
- Files that use QVService but also assert `.meta.id`

---

## (3) Contract Tests: "Legal Assertion Patterns" Rules

### ✅ Allowed Assertions (Contract Tests)

**DTO Fields:**
- `step_dto.step_id` (not `step_dto.meta.id`)
- `calc_dto.calc_id` (not `calc_dto.meta.id`)
- `struct_dto.structure_id` (not `struct_dto.meta.id`)
- `step_dto.status`, `step_dto.step_type`, `step_dto.calc_id`
- `calc_dto.name`, `calc_dto.structure_id`, `calc_dto.step_count`

**JSON Serialization:**
- `json.dumps(response)` succeeds
- Response keys match expected schema (e.g., `{"templates": [...]}`)
- Response values are JSON-serializable (no objects, only primitives/dicts/lists)

**Behavior/State:**
- Calculation status: `"pending"`, `"running"`, `"completed"`, `"failed"`
- Step execution results (via DTO, not internal objects)
- Daemon endpoint responses (via JSON, not Python objects)

**High-Level Capabilities:**
- `svc.calculation.add_step()` returns `StepDTO`
- `svc.calculation.list()` returns `list[CalculationDTO]`
- `svc.structure.get()` returns `StructureDTO`

### ❌ Forbidden Assertions (Contract Tests)

**Internal Object Structure:**
- ❌ `assert step.meta.id == "..."` → Use `assert step_dto.step_id == "..."`
- ❌ `assert isinstance(calc, CalculationModel)` → Use DTO type checks
- ❌ `assert calc.meta.slug == "..."` → Use `calc_dto.meta.slug` (if MetaDTO exposed) or remove
- ❌ `assert step.absolute_path.exists()` → Use step_id to query via API if needed

**Kernel Type Imports:**
- ❌ `from quantumvitas.api import Calculation, Step, QECardType` → Import from source modules or remove
- ❌ `from quantumvitas.api import StructureStepSpec` → Use DTO or import from `quantumvitas.calculation.structure_steps`
- ❌ `from quantumvitas.api import ParameterOverride` → Import from `quantumvitas.ir.parameters`

**Internal Tools as Capabilities:**
- ❌ `QVService.slugify()` → Not a public capability
- ❌ `QVService.is_ulid_like()` → Not a public capability
- ❌ `QVService.detect_context()` → Use `svc.project.resolve_enclosing_path()` or similar

**Direct Core/Kernel Access:**
- ❌ `from quantumvitas.core.models import load_calculation` → Use `svc.calculation.get()` or compat layer
- ❌ `from quantumvitas.core.resolution import require_calculation` → Use `svc.calculation.require_ref()`

### Migration Pattern Examples

**Before (Contract Test - WRONG):**
```python
from quantumvitas.api import QVService
step = QVService.init_step(project_root, "scf", calc_id)
assert step.meta.id.startswith("01")  # ❌ Internal structure
```

**After (Contract Test - CORRECT):**
```python
from quantumvitas.api.compat import init_step  # Or new API
step_dto = init_step(project_root, "scf", calc_id)
assert step_dto.step_id.startswith("01")  # ✅ DTO field
```

**Before (Contract Test - WRONG):**
```python
from quantumvitas.api import QECardType  # ❌ Kernel type
assert card.type == QECardType.CONTROL
```

**After (Contract Test - CORRECT):**
```python
# Option 1: Import from source
from quantumvitas.drivers.qe.io.model import QECardType
assert card.type == QECardType.CONTROL

# Option 2: Assert via DTO (preferred)
assert card_dto.type == "CONTROL"  # String representation
```

---

## (4) Kernel Tests: "Preserved Scope" Rules

### ✅ Allowed Assertions (Kernel Tests)

**Internal Object Structure:**
- ✅ `assert calc.meta.id == "..."` (ResourceMeta is internal)
- ✅ `assert isinstance(step, StepDoc)` (internal model)
- ✅ `assert step.meta.slug == "..."` (internal metadata)
- ✅ `assert calc.steps[0].step_id == "..."` (internal CalculationStepEntry)

**Direct Core/Kernel Imports:**
- ✅ `from quantumvitas.core.models import CalculationModel, load_calculation`
- ✅ `from quantumvitas.core.resolution import require_calculation, build_resource_index`
- ✅ `from quantumvitas.core.resources import ResourceMeta, generate_resource_id`

**Internal Algorithms/Invariants:**
- ✅ Tests for locking (`calc_edit_lock`, `calc_run_lock`)
- ✅ Tests for fingerprinting (`compute_structure_sha`, `compute_step_sha`)
- ✅ Tests for YAML serialization/deserialization
- ✅ Tests for path resolution logic
- ✅ Tests for selector matching (slugify, ULID validation)

**No Migration Required:**
- Kernel tests are **not** affected by PR10 API slimming
- They can continue using internal imports and assertions
- They should **not** be forced to use DTOs

### Reclassification Guidelines

**Files to Reclassify as KERNEL:**

1. **`tests/integration/test_incremental_run.py`** (partially)
   - **Evidence:** Uses `load_calculation()`, `calc_edit_lock()`, asserts `.meta.id`
   - **Action:** Split into contract tests (QVService calls) and kernel tests (locking/fingerprinting)

2. **`tests/integration/test_step_slug_consistency.py`**
   - **Evidence:** Tests internal slug/ULID resolution, uses `require_step_by_ulid()`
   - **Action:** MOVE_TO_KERNEL (or split if it also tests daemon endpoints)

3. **`tests/unit/test_resolution_absolute_path.py`**
   - **Evidence:** Tests path resolution internals
   - **Action:** MOVE_TO_KERNEL

4. **Any test that primarily tests:**
   - Lock semantics
   - Fingerprint computation
   - YAML structure/parsing
   - Selector resolution algorithms
   - Internal model invariants

---

## (5) Bucket Distribution & Top Offenders

### Bucket A: Missing QVService Methods (Top 20 by Frequency)

| Method Name | Occurrences | Test Files Affected | Suggested Fix |
|-------------|------------|-------------------|---------------|
| `init_step` | 160 | `tests/daemon/*`, `tests/unit/test_api_step_artifacts.py`, `tests/integration/*` | Add to `api.compat`, migrate tests |
| `add_step_to_calculation` | 42 | `tests/daemon/test_gui_job_and_step_flows.py` | Add to `api.compat`, migrate tests |
| `_detect_prefix_outdir_injection` | 22 | `tests/unit/test_prefix_outdir_injection.py` | Add to `api.compat` (internal method) |
| `_preflight_check_and_seed_pseudos` | 18 | Various integration tests | Add to `api.compat` (internal method) |
| `_build_structure_vis_payload` | 16 | `tests/unit/test_online_project_payload_contract.py`, `tests/integration/test_pipeline_alignment.py` | Add to `api.compat` (internal method) |
| `calc_set_steps` | 12 | `tests/unit/test_workflow.py` | Add to `api.compat` or migrate to new API |
| `configure_calculation` | 10 | `tests/unit/test_api_service.py` | Add to `api.compat` or use `svc.calculation.configure()` |
| `update_step_params` | 8 | `tests/daemon/test_update_step_params_persistence.py` | Add to `api.compat` or use `svc.calculation.update_step()` |
| `get_structure_vis_data` | 8 | `tests/daemon/test_si_bands_calculation_daemon.py` | Add to `api.compat` or use `svc.structure.get_visualization()` |
| `get_reference_analysis` | 8 | `tests/unit/test_analysis_artifacts.py` | Add to `api.compat` or use `svc.analysis.get_reference()` |
| `create_demo_project` | 8 | `tests/unit/test_demo_snapshot_restore.py` | Add to `api.compat` |
| `save_project_snapshot` | 6 | Various tests | Add to `api.compat` |
| `configure_structure` | 6 | `tests/unit/test_api_service.py` | Add to `api.compat` or use `svc.structure.configure()` |
| `write_structure` | 4 | `tests/unit/test_api_service_facade.py` | Add to `api.compat` or use `svc.structure.write()` |
| `update_calculation_species_map` | 4 | Various tests | Add to `api.compat` |
| `preflight_check` | 4 | `tests/daemon/test_qe_detection.py` | Add to `api.compat` |
| `needs_alat_preservation` | 4 | `tests/cli/test_cli_show_command_integration.py`, `tests/unit/test_step_defaults.py` | Add to `api.compat` |
| `list_calculations` | 4 | `tests/unit/test_api_service.py` | Use `svc.calculation.list()` |
| `is_ulid_like` | 4 | `tests/daemon/test_get_common_cards.py`, `tests/daemon/test_delete_calculation_daemon.py` | Not a public capability - remove or move to kernel test |
| `generate_kpath` | 4 | `tests/unit/test_api_service_facade.py` | Add to `api.compat` or use `svc.calculation.generate_kpath()` |

**Instance Methods Missing:**
- `require_calculation_ref` (4 tests) → Use `svc.calculation.require_ref()`
- `detect_context` (4 tests) → Use `svc.project.resolve_enclosing_path()`
- `resolve_calculation_ref` (2 tests) → Use `svc.calculation.resolve()`
- `resolve_structure_ref` (2 tests) → Use `svc.structure.resolve()`
- `require_structure_ref` (2 tests) → Use `svc.structure.require_ref()`
- `require_step_ref` (2 tests) → Use `svc.calculation.require_step_ref()`
- `make_structure_selector_resolver_ref` (2 tests) → Use `svc.structure.make_resolver()`
- `build_resource_index` (2 tests) → Use `svc.project.build_resource_index()`

### Bucket B: Missing API Type Exports (Top 15 by Frequency)

| Type Name | Occurrences | Test Files | Suggested Fix |
|-----------|------------|-----------|---------------|
| `PresetCompilationError` | 6 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.presets.compiler` |
| `DisplayModeParams` | 6 | `tests/unit/test_api_service_facade.py` | Import from source module or remove (if not needed) |
| `StructureStepSpec` | 4 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.calculation.structure_steps` |
| `PrecisionContextError` | 4 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.presets.precision_context` |
| `EngineConfig` | 4 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.core.engines.base` or remove |
| `Step` | 2 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.calculation.step` |
| `QeEngine` | 2 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.drivers.qe.engine.qe_engine` |
| `QEInputParser` | 2 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.drivers.qe.io.parser` |
| `QECardType` | 2 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.drivers.qe.io.model` |
| `ProjectContext` | 2 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.core.project_context` |
| `ParameterOverride` | 2 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.ir.parameters` |
| `DOSData` | 2 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.analysis.artifacts` |
| `CalculationStepEntry` | 2 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.core.models` |
| `Calculation` | 2 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.calculation.calculation` |
| `BandAnalysisFiles` | 2 | `tests/unit/test_api_service_facade.py` | Import from `quantumvitas.analysis.artifacts` |

**All Bucket B failures are in `tests/unit/test_api_service_facade.py`** - This file tests API re-exports, which violates PR10. It should be updated to test DTOs/behavior instead of type availability.

### Bucket C: Path/Assertion Issues

**Path Bugs:**
- ✅ **FIXED:** `calculation.yaml/calculation.yaml` double-append (0 remaining)
- All path resolution issues resolved in previous work

**Assertion Mismatches:**
- Status string format: Tests expect `StepStatus.SUCCESS` but get `SUCCESS`
  - Files: `tests/cli/test_template_calculation.py`, `tests/cli/test_si_dos_calculation_cli.py`
  - Fix: Update test expectations to match actual format

**CLI Subprocess Failures:**
- Cascading from missing `init_step` method
  - Files: `tests/cli/test_si_bands_manual_calculation_cli.py`, `tests/cli/test_si_bands_auto_calculation_cli.py`, `tests/cli/test_si_dos_calculation_comprehensive.py`
  - Fix: Will be resolved when `init_step` compat layer is available

**Other:**
- `AttributeError: 'dict' object has no attribute 'name'` in `tests/unit/test_project_and_cli.py`
  - Likely a test bug (expects object but gets dict)

---

## (6) Migration Roadmap

### Phase 1: Establish Compat Layer & Gate Tests (Foundation)

**Target:** Create infrastructure for migration

**Actions:**
1. ✅ **DONE:** Create `src/quantumvitas/api/compat.py` with `init_step()` and `add_step_to_calculation()`
2. Create gate test: `tests/gates/test_no_daemon_cli_import_api_compat.py`
   - Scan `src/quantumvitas/daemon/**` and `src/quantumvitas/cli/**`
   - Fail if `import quantumvitas.api.compat` found
   - Allow in comments/docstrings
3. Add pytest markers: `@pytest.mark.contract` and `@pytest.mark.kernel` (documentation only, no enforcement yet)

**Impact:** No test changes, only infrastructure

**Verification:**
```bash
python -m pytest tests/gates/test_no_daemon_cli_import_api_compat.py -v
python -m pytest tests/gates -v --tb=short -n auto --dist=loadfile
```

**Risk:** Low - only adds infrastructure

---

### Phase 2: Fix Bucket B - Contract Test ImportErrors (Quick Win)

**Target:** Fix all `ImportError: cannot import name '...' from 'quantumvitas.api'` in contract tests

**Actions:**
1. Update `tests/unit/test_api_service_facade.py`:
   - Remove tests that check for type re-exports (violates PR10)
   - Update remaining tests to import types from source modules
   - Change assertions from "type exists" to "DTO behavior works"

**Impact:** ~30 tests in 1 file (`tests/unit/test_api_service_facade.py`)

**Specific Changes:**
- Remove: `test_qe_model_enums_re_exported`, `test_qe_parser_re_exported`, `test_dos_data_re_exported`, etc.
- Update: Tests that use types → import from source modules
- Example: `from quantumvitas.api import QECardType` → `from quantumvitas.drivers.qe.io.model import QECardType`

**Verification:**
```bash
python -m pytest tests/unit/test_api_service_facade.py -v --tb=short -n auto --dist=loadfile
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile 2>&1 | grep -E "ImportError.*cannot import" | wc -l
# Should be 0
```

**Risk:** Low - only changes test imports, no API changes

---

### Phase 3: Expand Compat Layer for Top Missing Methods

**Target:** Add top 10 missing methods to `api.compat.py`

**Actions:**
1. Add to `api.compat.py`:
   - `_detect_prefix_outdir_injection()` (22 tests)
   - `_preflight_check_and_seed_pseudos()` (18 tests)
   - `_build_structure_vis_payload()` (16 tests)
   - `calc_set_steps()` (12 tests)
   - `configure_calculation()` (10 tests)
   - `update_step_params()` (8 tests)
   - `get_structure_vis_data()` (8 tests)
   - `get_reference_analysis()` (8 tests)
   - `create_demo_project()` (8 tests)
   - `save_project_snapshot()` (6 tests)

2. Each method should:
   - Use lazy imports (inside function body)
   - Delegate to new API where possible
   - Return JSON-friendly data or DTOs
   - Include docstring explaining it's for test compatibility

**Impact:** ~100+ tests across multiple files

**Verification:**
```bash
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile 2>&1 | grep -E "AttributeError.*QVService.*has no attribute" | wc -l
# Should decrease by ~100
```

**Risk:** Medium - compat layer must not introduce kernel imports at module level

---

### Phase 4: Migrate Daemon Tests to Compat Layer

**Target:** Update all `tests/daemon/test_*.py` to use compat layer

**Actions:**
1. For each file in `tests/daemon/`:
   - Replace `QVService.init_step()` → `from quantumvitas.api.compat import init_step`
   - Replace `QVService.add_step_to_calculation()` → `from quantumvitas.api.compat import add_step_to_calculation`
   - Replace other missing methods with compat equivalents
   - Update assertions: `.meta.id` → `.step_id` (for StepDTO)

2. Files to update:
   - `tests/daemon/test_si_bands_calculation_daemon.py` (4 tests)
   - `tests/daemon/test_gui_job_and_step_flows.py` (21 tests)
   - `tests/daemon/test_gui_calculation_detail.py` (4 tests)
   - `tests/daemon/test_update_step_params_persistence.py` (3 tests)
   - `tests/daemon/test_promote_relax_structure.py` (if uses missing methods)
   - `tests/daemon/test_delete_calculation_daemon.py` (if uses missing methods)
   - `tests/daemon/test_qe_detection.py` (2 tests - preflight_check)
   - `tests/daemon/test_get_common_cards.py` (if uses missing methods)

**Impact:** ~40 tests in `tests/daemon/`

**Verification:**
```bash
python -m pytest tests/daemon/ -v --tb=short -n auto --dist=loadfile
# All should pass
```

**Risk:** Low - only test changes, daemon code unchanged

---

### Phase 5: Migrate Unit API Tests to Compat Layer

**Target:** Update `tests/unit/test_api_*.py` and related files

**Actions:**
1. `tests/unit/test_api_step_artifacts.py` (9 tests):
   - Replace `QVService.init_step()` → compat layer
   - Update assertions to use DTO fields

2. `tests/unit/test_api_service.py`:
   - Replace missing static methods with compat layer
   - Update instance method calls to use new API (`svc.calculation.*`, `svc.structure.*`)

3. `tests/unit/test_workflow.py`:
   - Replace `QVService.calc_set_steps()` → compat layer

4. `tests/unit/test_analysis_artifacts.py`:
   - Replace `QVService.get_reference_analysis()` → compat layer

5. `tests/unit/test_api_get_band_structure_data.py`:
   - Replace `QVService.init_step()` → compat layer

6. `tests/unit/test_prefix_outdir_injection.py`:
   - Replace `QVService._detect_prefix_outdir_injection()` → compat layer

**Impact:** ~50 tests in `tests/unit/`

**Verification:**
```bash
python -m pytest tests/unit/test_api_*.py -v --tb=short -n auto --dist=loadfile
python -m pytest tests/unit/test_workflow.py -v
python -m pytest tests/unit/test_analysis_artifacts.py -v
```

**Risk:** Low - test-only changes

---

### Phase 6: Migrate Integration Tests (Contract Parts Only)

**Target:** Update contract-like parts of `tests/integration/test_*.py`

**Actions:**
1. For each integration test file:
   - **Identify contract parts:** QVService calls, daemon endpoints, CLI commands
   - **Identify kernel parts:** Core imports, `.meta.id` assertions, internal model tests
   - **Split or annotate:** Mark contract parts with `@pytest.mark.contract`, kernel parts with `@pytest.mark.kernel`

2. Update contract parts:
   - Replace `QVService.init_step()` → compat layer
   - Replace `.meta.id` → `.step_id` (for DTOs)
   - Fix imports: kernel types → source modules

3. Keep kernel parts unchanged (no migration needed)

**Priority Files:**
- `tests/integration/test_incremental_run.py` (already partially migrated)
- `tests/integration/test_relax_promote_e2e.py` (3 tests)
- `tests/integration/test_pipeline_alignment.py` (1 test)
- `tests/integration/test_relax_structure_save.py` (1 test)

**Impact:** ~20-30 tests (contract parts only)

**Verification:**
```bash
python -m pytest tests/integration/ -v --tb=short -n auto --dist=loadfile -m contract
# Contract tests should pass
python -m pytest tests/integration/ -v --tb=short -n auto --dist=loadfile -m kernel
# Kernel tests should still pass
```

**Risk:** Medium - need to carefully identify contract vs kernel parts

---

### Phase 7: Fix CLI Tests & Assertion Mismatches

**Target:** Fix CLI subprocess failures and assertion format mismatches

**Actions:**
1. Fix status string assertions:
   - `tests/cli/test_template_calculation.py`: Expect `SUCCESS` not `StepStatus.SUCCESS`
   - `tests/cli/test_si_dos_calculation_cli.py`: Same fix

2. CLI subprocess failures (cascading from missing methods):
   - These will be resolved automatically when `init_step` compat is available
   - Verify after Phase 4-5 completion

3. Fix other assertion bugs:
   - `tests/unit/test_project_and_cli.py`: Fix `AttributeError: 'dict' object has no attribute 'name'`

**Impact:** ~5-10 tests

**Verification:**
```bash
python -m pytest tests/cli/ -v --tb=short -n auto --dist=loadfile
python -m pytest tests/unit/test_project_and_cli.py -v
```

**Risk:** Low - test-only changes

---

### Phase 8: Final Verification & Cleanup

**Target:** Ensure all tests pass, verify constraints

**Actions:**
1. Run full test suite:
   ```bash
   python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
   ```

2. Verify gate tests:
   ```bash
   python -m pytest tests/gates/ -v --tb=short -n auto --dist=loadfile
   ```

3. Verify no daemon/cli imports compat:
   ```bash
   python -m pytest tests/gates/test_no_daemon_cli_import_api_compat.py -v
   ```

4. Verify import rules:
   ```bash
   python -m pytest tests/gates/test_import_rules.py -v
   ```

5. Verify serialization rules:
   ```bash
   python -m pytest tests/gates/test_daemon_no_hand_serialization.py -v
   ```

6. Document remaining compat layer usage:
   - List which tests still use `api.compat`
   - Plan for gradual removal (future work)

**Impact:** All tests

**Verification:**
```bash
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
# Should show: 0 failed, 0 errors
```

**Risk:** Low - verification only

---

## (7) Suggested Pytest Grouping Strategy

### Option A: Markers (Recommended)

**Implementation:**
- Add `@pytest.mark.contract` to all contract tests
- Add `@pytest.mark.kernel` to all kernel tests
- Add to `pytest.ini`:
  ```ini
  markers =
      contract: Contract tests (API/daemon/CLI behavior)
      kernel: Kernel tests (internal models/algorithms)
  ```

**Usage:**
```bash
# Run only contract tests
pytest -m contract

# Run only kernel tests
pytest -m kernel

# Run all tests
pytest
```

**Advantages:**
- ✅ No file reorganization needed
- ✅ Easy to apply incrementally
- ✅ Can mark individual test functions, not just files
- ✅ Works with existing test structure

**Disadvantages:**
- ⚠️ Requires manual marking (but can be done incrementally)
- ⚠️ No enforcement (markers are optional)

### Option B: Directory Reorganization (Not Recommended)

**Proposal:**
- `tests/contract/` - All contract tests
- `tests/kernel/` - All kernel tests
- Keep `tests/gates/` separate

**Advantages:**
- ✅ Clear physical separation
- ✅ Easy to see which tests are which

**Disadvantages:**
- ❌ Requires massive file moves (302 files)
- ❌ Breaks existing test organization (api/daemon/cli/core)
- ❌ High risk of merge conflicts
- ❌ Not necessary for PR10 migration

**Recommendation:** Use Option A (markers). Directory reorganization can be done later if needed, but is not required for PR10 migration.

---

## (8) "Do NOT Do" List (Anti-Drift Rules)

### ❌ API Surface Expansion

- **DO NOT** add kernel types back to `quantumvitas.api.__init__.__all__`
- **DO NOT** re-export `QECardType`, `StructureStepSpec`, `ParameterOverride`, etc. from `quantumvitas.api`
- **DO NOT** expand `api.__all__` beyond PR10 limits (≤30 items, 0 kernel symbols)

**Rationale:** PR10 explicitly removed these to enforce architectural boundaries. Re-adding them defeats the purpose.

### ❌ Internal Tools as Public Capabilities

- **DO NOT** add `QVService.slugify()` as a public method
- **DO NOT** add `QVService.is_ulid_like()` as a public method
- **DO NOT** add `QVService.detect_context()` as a public method (use `svc.project.resolve_enclosing_path()`)
- **DO NOT** add `QVService.generate_resource_id()` as a public method

**Rationale:** These are internal utilities, not user-facing capabilities. Tests can use them via compat layer temporarily, but they should not be in public API.

### ❌ Daemon/CLI Importing Compat

- **DO NOT** allow `from quantumvitas.api.compat import ...` in `src/quantumvitas/daemon/**`
- **DO NOT** allow `from quantumvitas.api.compat import ...` in `src/quantumvitas/cli/**`
- **DO** create gate test to enforce this

**Rationale:** Compat layer is for test migration only. Production code (daemon/cli) must use the new API.

### ❌ Schema Widening in Daemon Handlers

- **DO NOT** use `vars()` or `__dict__` in daemon handlers
- **DO NOT** manually construct dicts with object attributes (e.g., `{"id": obj.id}`)
- **DO** use `dataclasses.asdict()` or DTO `.to_dict()` methods
- **DO** filter keys to required schema

**Rationale:** PR6 gate test enforces this. Schema stability is critical for API compatibility.

### ❌ Kernel Imports at Module Level

- **DO NOT** add `from quantumvitas.core import ...` at module top-level in `api/compat.py`
- **DO** use lazy imports (inside function bodies)
- **DO** verify gate test `test_import_rules` stays green

**Rationale:** PR10 requires that API layer does not import kernel at module level.

### ❌ Large Refactors

- **DO NOT** refactor `service.py` in large chunks
- **DO NOT** change test file organization (directory moves)
- **DO** make small, incremental changes
- **DO** verify after each change

**Rationale:** Large refactors increase risk and make debugging harder. Incremental changes are safer.

### ❌ Test Deletion

- **DO NOT** delete tests to make suite green
- **DO** migrate tests to new patterns
- **DO** reclassify tests (contract → kernel) if appropriate
- **DO** mark tests as `@pytest.mark.skip` only if truly broken/unfixable

**Rationale:** Test coverage is valuable. Deletion should be last resort.

---

## Appendix: Detailed Test File Classification

### Contract Tests (Must Migrate)

**High Priority (Many Failures):**
- `tests/daemon/test_si_bands_calculation_daemon.py` - 4 tests, `init_step`
- `tests/daemon/test_gui_job_and_step_flows.py` - 21 tests, `add_step_to_calculation`
- `tests/unit/test_api_service_facade.py` - Many tests, ImportError + AttributeError
- `tests/unit/test_api_step_artifacts.py` - 9 tests, `init_step`
- `tests/unit/test_workflow.py` - 4 tests, `calc_set_steps`

**Medium Priority:**
- `tests/daemon/test_gui_calculation_detail.py` - 4 tests
- `tests/daemon/test_update_step_params_persistence.py` - 3 tests
- `tests/unit/test_analysis_artifacts.py` - 4 tests, `get_reference_analysis`
- `tests/unit/test_api_get_band_structure_data.py` - 4 tests, `init_step`
- `tests/cli/test_*.py` - 9 files, cascading failures

**Low Priority (Few Failures):**
- `tests/api/test_*.py` - 17 files, mostly passing
- `tests/gates/test_*.py` - 10 files, mostly passing

### Kernel Tests (No Migration Needed)

**Confirmed Kernel:**
- `tests/core/test_*.py` - 9 files, core imports
- `tests/drivers/*/test_*.py` - 6 files, driver internals
- `tests/ir/test_*.py` - 3 files, IR mapping
- `tests/presets/test_*.py` - 2 files, preset internals
- `tests/workflow/test_*.py` - 1 file, workflow internals

### Ambiguous (Requires Manual Review)

**Integration Tests (Mixed Patterns):**
- `tests/integration/test_*.py` - 41 files
  - Some use QVService (contract)
  - Some use core imports (kernel)
  - Need file-by-file review

**Unit Tests (Non-API):**
- `tests/unit/test_*.py` - 149 files (excluding `test_api_*`)
  - Need to check each for core imports vs QVService usage

---

## Summary

**Total Test Files:** 302  
**Contract Tests (Must Migrate):** ~80-100 files  
**Kernel Tests (No Migration):** ~25 files  
**Ambiguous (Need Review):** ~180 files (mostly integration/unit)

**Estimated Migration Effort:**
- Phase 1-2: 1-2 hours (infrastructure + Bucket B)
- Phase 3-5: 4-6 hours (compat layer + daemon/unit migration)
- Phase 6-7: 2-3 hours (integration + CLI fixes)
- Phase 8: 1 hour (verification)

**Total:** ~8-12 hours to reach full green

**Key Success Metrics:**
- ✅ 0 ImportError from `quantumvitas.api`
- ✅ 0 AttributeError for missing QVService methods (in contract tests)
- ✅ All gate tests passing
- ✅ Full test suite green (2,590 tests)

