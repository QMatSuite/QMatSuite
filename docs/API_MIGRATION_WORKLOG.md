# API Single Source Migration Worklog

## Phase A: Fix Test Legacy Dependencies

### Initial State (2026-01-28)

**Problem:** 6 test files import from `quantumvitas.api_legacy` and call `QVService._build_structure_vis_payload()`.

**Files to migrate:**
1. `tests/unit/test_online_project_payload_contract.py` - 3 callsites
2. `tests/unit/test_optimade_offline.py` - 3 callsites
3. `tests/unit/test_online_structure_supercell.py` - 4 callsites
4. `tests/integration/test_pipeline_alignment.py` - 2 callsites
5. `tests/integration/test_optimade_live.py` - 1 callsite

**Solution:** Canonical function already exists at `quantumvitas.analysis.structure_viz.build_structure_vis_payload`.
- Same signature except legacy has `trace_id` param (only for perf logging)
- Migration: import from canonical location, remove `trace_id` param

---

### Migration Actions (COMPLETED)

#### 1. test_online_project_payload_contract.py
- **Before:** `from quantumvitas.api_legacy import QVService`
- **After:** `from quantumvitas.analysis.structure_viz import build_structure_vis_payload, DisplayModeParams`
- **Changes:** 3 callsites: `QVService._build_structure_vis_payload(...)` → `build_structure_vis_payload(...)`
- **Status:** ✅ DONE

#### 2. test_optimade_offline.py
- **Before:** `from quantumvitas.api_legacy import QVService`
- **After:** `from quantumvitas.analysis.structure_viz import build_structure_vis_payload, DisplayModeParams`
- **Changes:** 3 callsites migrated, removed `trace_id` param
- **Status:** ✅ DONE

#### 3. test_online_structure_supercell.py
- **Before:** Two occurrences of `from quantumvitas.api_legacy import QVService`
- **After:** `from quantumvitas.analysis.structure_viz import build_structure_vis_payload, DisplayModeParams`
- **Changes:** 4 callsites migrated, removed `trace_id` param
- **Additional fix:** Removed assertion for `perf` key (only in legacy version)
- **Status:** ✅ DONE

#### 4. test_pipeline_alignment.py
- **Before:** `from quantumvitas.api_legacy import QVService`
- **After:** `from quantumvitas.analysis.structure_viz import build_structure_vis_payload, DisplayModeParams`
- **Changes:** 2 callsites migrated, removed `trace_id` param
- **Status:** ✅ DONE

#### 5. test_optimade_live.py
- **Before:** `from quantumvitas.api_legacy import QVService`
- **After:** `from quantumvitas.analysis.structure_viz import build_structure_vis_payload, DisplayModeParams`
- **Changes:** 1 callsite migrated, removed `trace_id` param
- **Status:** ✅ DONE

---

### Bug Fixes (During Migration)

#### 1. tests/gates/test_no_dangling_calls.py
- **Issue:** Missing `import pytest` caused NameError
- **Fix:** Added `import pytest` to imports
- **Status:** ✅ DONE

#### 2. tests/integration/vasp/test_vasp_real.py
- **Issue:** Test was failing because VASP binary has broken HDF5 library dependency
- **Fix:** Changed fixture to detect broken dynamic libraries and skip (not fail) when VASP isn't runnable
- **Status:** ✅ DONE

---

### Verification Results

**Test run:** `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

**Results:**
- 2547 passed
- 7 skipped
- 191 warnings
- Exit code: 0

**Legacy import check:**
```bash
grep -rn "from quantumvitas\.api_legacy\|from quantumvitas\._api_legacy" tests/ src/
# Result: No matches found
```

---

### Current State

1. **Legacy files moved to vault:**
   - `src/quantumvitas/api_legacy.py` → `src/quantumvitas/_vault/_legacy_facade.py`
   - `src/quantumvitas/_api_legacy.py` → `src/quantumvitas/_vault/_legacy_service.py`

2. **Vault import protection active:**
   - `_vault/__init__.py` raises `ImportError` on any import attempt
   - Escape hatch via `QMATSUITE_ALLOW_VAULT=1` (for migration tooling only)

3. **Zero legacy imports in production code or tests**

4. **All gates passing:**
   - Single QVService definition: ✅
   - No legacy imports: ✅
   - Dangling call scanner: 212 dangling calls remain (methods called on QVService that don't exist)

---

## Phase B: Migrate Dangling Calls

### Scanner State (2026-01-28)
- **Canonical QVService methods:** 27
- **Dangling call sites:** 212
- **Unique dangling methods:** 113

### Top 10 Dangling Methods (by call count)
| Method | Calls | Classification | Action |
|--------|-------|---------------|--------|
| `is_ulid_like` | 22 | C (utils) | Import from `api.utils`, call directly |
| `get_pseudo_config` | 15 | B (capability) | Add to QVService.pseudo or domain fn |
| `validate_ulid` | 7 | C (utils) | Import from `api.utils`, call directly |
| `load_pseudo_config` | 4 | B/D (internal) | Merge into get_pseudo_config or domain |
| `can_delete_structure` | 4 | A (exists) | Already on QVService.structure |
| `download_pseudo_by_filename` | 4 | B (capability) | Add to QVService.pseudo |
| `run_input_step` | 3 | B (capability) | Consolidate with run_step |
| `list_installed_sssp` | 3 | B (capability) | Add to QVService.pseudo |
| `check_archives_status` | 3 | B (capability) | Add to QVService.pseudo |
| `detect_engine_for_calculation` | 3 | B (capability) | Add to QVService.engine |

---

### Batch 1: Utils Functions (Category C)

#### `is_ulid_like` - 22 callsites in frontends/daemon/server.py
- **Classification:** C (pure utils)
- **Action:** Already in `quantumvitas.api.utils.is_ulid_like`. File needs to import from utils and call directly instead of `QVService.is_ulid_like()`
- **Status:** ✅ DONE

#### `validate_ulid` - 7 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`, replaced calls
- **Status:** ✅ DONE

---

### Batch 2: Structure Utils (Category C)

#### `can_delete_structure` - 4 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`, replaced calls in daemon/server.py and frontends/daemon/server.py
- **Status:** ✅ DONE

#### `load_calculation` - 3 callsites
- **Classification:** C (pure utils)
- **Action:** Already in `api.utils`, just needed to replace `QVService.load_calculation()` calls
- **Status:** ✅ DONE

---

### Batch 3: Pseudo Config Utils (Category C)

#### `get_pseudo_config` - 15+ callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`, replaced calls
- **Status:** ✅ DONE

#### `set_pseudo_config` - 2+ callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`, replaced calls
- **Status:** ✅ DONE

#### `validate_pseudo_config` - 1 callsite
- **Classification:** C (pure utils)
- **Action:** Added `validate_pseudo_config_dict()` to `api.utils`, replaced calls
- **Status:** ✅ DONE

#### `load_pseudo_config` - 4 callsites
- **Classification:** C (pure utils)
- **Action:** Added `load_pseudo_config_raw()` to `api.utils`, replaced calls
- **Status:** ✅ DONE

---

### Progress Summary (2026-01-28)

| Batch | Initial | After | Reduction |
|-------|---------|-------|-----------|
| Start | 212 | - | - |
| Utils (is_ulid_like, validate_ulid) | 212 | 183 | -29 |
| can_delete_structure | 183 | 179 | -4 |
| load_calculation | 179 | 176 | -3 |
| Pseudo config | 176 | 154 | -22 |
| delete_structure, rename_structure | 154 | 141 | -4 |
| detect_engine/presets, download_pseudo_by_filename | 141 | 131 | -10 |
| QE engine utils (detect_qe, list, discover, set, env_info) | 131 | 121 | -10 |
| resolve_pseudo_provenance, download_pseudo_from_url | 121 | 117 | -4 |

**Current state:** 117 dangling calls remaining (45% reduction)

---

### Batch 4: Structure Management (Category C)

#### `delete_structure` - 2 callsites (daemon + frontends)
- **Classification:** C (pure utils, wraps svc.structure.delete)
- **Action:** Added to `api.utils`, replaced calls
- **Status:** ✅ DONE

#### `rename_structure` - 2 callsites (daemon + frontends)
- **Classification:** C (pure utils, wraps svc.structure.update_meta)
- **Action:** Added to `api.utils`, replaced calls
- **Status:** ✅ DONE

---

### Batch 5: Calculation Detection (Category C)

#### `detect_engine_for_calculation` - 3 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`, wraps presets.integration._detect_engine_for_calculation
- **Status:** ✅ DONE

#### `detect_presets_from_calculation` - 3 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`, wraps presets.integration.detect_presets_from_calculation
- **Status:** ✅ DONE

#### `download_pseudo_by_filename` - 4 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils` with full implementation
- **Status:** ✅ DONE

---

### Batch 6: QE Engine Utils (Category C)

#### `detect_qe` - 2 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`, wraps core QE resolver
- **Status:** ✅ DONE

#### `get_environment_info` - 2 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`
- **Status:** ✅ DONE

#### `list_qe_engines` - 2 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`
- **Status:** ✅ DONE

#### `discover_qe_engines` - 2 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`
- **Status:** ✅ DONE

#### `set_qe_engine` - 2 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`
- **Status:** ✅ DONE

---

### Batch 7: Pseudo Utilities (Category C)

#### `resolve_pseudo_provenance` - 2 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils`, wraps core.pseudo_provenance
- **Status:** ✅ DONE

#### `download_pseudo_from_url` - 2 callsites
- **Classification:** C (pure utils)
- **Action:** Added to `api.utils` with full implementation
- **Status:** ✅ DONE

---

### Remaining Dangling Methods (117 calls)

| Method | Calls | Classification | Notes |
|--------|-------|---------------|-------|
| `run_input_step` | 3 | B (CLI-specific) | Complex workflow integration |
| `create_blob_store` | 3 | D (internal) | Analysis layer |
| `create_default_registry` | 2 | D (internal) | Project layer |
| `rename_calculation` | 2 | B (has internal deps) | Calls configure_calculation internally |
| `set_common_card` | 2 | B (QE-specific) | QE card manipulation |
| `get_pseudo_mapping` | 2 | B (step-specific) | Complex step context |
| `set_pseudo_mapping` | 2 | B (step-specific) | Complex step context |
| `import_pseudo_files` | 2 | B (pseudo) | Could be utils |
| `search_legacy_pseudos` | 2 | B (pseudo) | Network/scraping |
| ... and 97 more | varies | varies | Mostly CLI code |

### Exit Criteria Status

| Criterion | Status |
|-----------|--------|
| Zero legacy imports in src/ | ✅ PASS |
| Zero legacy imports in tests/ | ✅ PASS |
| All tests pass | ✅ PASS (2545 passed, 9 skipped) |
| Single QVService definition | ✅ PASS |
| Vault unreachable at runtime | ✅ PASS |
| Dangling calls eliminated | ⚠️ IN PROGRESS (117 remaining) |

### Test Results (Latest)

```
=========== 2545 passed, 9 skipped, 40 warnings in 96.65s ===========
```

### Bug Fixes During Migration

#### 1. frontends/daemon/server.py broken import
- **Issue:** Import `from quantumvitas.frontends.daemon.jobs` failed (module didn't exist)
- **Verification:** `python -c "import quantumvitas.frontends.daemon.jobs"` → ModuleNotFoundError
- **Fix:** Changed to `from quantumvitas.daemon.jobs import JobManager, JobStatus`
- **Status:** ✅ FIXED

#### 2. PySCF relax tests failing without optimizer
- **Issue:** Tests checked for PySCF but not for geometric/berny optimizer availability
- **Fix:** Updated `is_pyscf_available()` in both test files to check optimizer imports
- **Files:** `test_pyscf_relax_real.py`, `test_relax_promote_e2e.py`
- **Status:** ✅ FIXED (tests now skip properly)

#### 3. Missing QVServiceError compatibility alias
- **Issue:** frontends/daemon/server.py imported `QVServiceError` which was moved to vault
- **Fix:** Added compatibility aliases in api/__init__.py:
  - `QVServiceError = APIError`
  - `ErrorSpec = APIError`
  - `ErrorCodes = type("ErrorCodes", (), {})`
- **Status:** ✅ FIXED

---

## Part 1: Daemon Server Consolidation

### Entrypoint Analysis

**Console scripts (pyproject.toml):**
```
qv = "quantumvitas.cli:app"
```
The daemon is NOT a console script - it's used programmatically by GUI.

**Import surface analysis:**
- `quantumvitas.daemon.server`: 20+ imports across tests and daemon/__init__.py
- `quantumvitas.frontends.daemon.server`: ZERO external imports (orphaned)

**File sizes:**
- `daemon/server.py`: 6516 lines
- `frontends/daemon/server.py`: 6734 lines (stale fork)

### Conclusion
**Canonical implementation:** `quantumvitas.daemon.server`
- All tests import from it
- daemon/__init__.py re-exports from it
- frontends/daemon/server.py is an orphaned duplicate with zero consumers

### Action: Convert frontends/daemon/server.py to shim
- Remove 6700+ lines of duplicated business logic
- Replace with strict re-export shim
- Add deprecation warning
- Add gate test to prevent future divergence

---

## Phase C: GEN/SPEC Convergence Cleanup (2026-01-30)

### Overview
Complete cleanup to enforce canonical field naming across the codebase:
- **ULID fields**: `id` → `ulid`, `*_id` → `*_ulid`
- **Step types**: `step_type` → `step_type_spec` (SPEC) or `step_type_gen` (GEN)
- **YAML SSOT**: `step_type_spec` is the Single Source of Truth in YAML files

### Gate A: No Legacy Identity Fields
**Status: ✅ PASS (0 violations)**

Created `tests/gates/test_no_legacy_identity_fields.py`:
- Scans YAML/JSON resources for forbidden keys (`id` in meta, `*_id` patterns, `step_type`)
- Scans Python source for forbidden field names in dataclasses/DTOs
- Allowlist for legitimate non-ULID `id` usages (JSON-RPC, Job graph)

### Gate B: Schema Self-Consistency
**Status: ✅ ALL PASS (B3-B6)**

Created `tests/gates/test_schema_self_consistency.py`:
- B3: No legacy keyword arguments (`id=`, `step_id=`, `step_type=` in class calls) ✅
- B4: No unsafe dict-unpack (`**meta` into sensitive classes) ✅
- B5: No legacy key assertions in tests (`"id"`, `"calc_id"`, `"step_type"`, etc.) ✅
- B6: No legacy keys in golden fixtures ✅
- Allowlist for legitimate non-ULID classes: `RPCRequest`, `RPCResponse`, `Job`, `WorkflowTemplate`, etc.
- Allowlist for non-ULID contexts: OPTIMADE API, QE parameter metadata, v0 request payloads

### GEN/SPEC Convergence Audit
**Status: ✅ PASS (21 tests)**

Added `TestGenSpecBoundary` class to `tests/gates/test_gen_spec_convergence_gate.py`:
- Verified presets correctly map `step_type_spec` → `step_type_gen` for variant lookup
- Verified workflow templates use `step_type_gen` for workflow detection
- Verified registry provides both gen→spec and spec→gen mappings
- Verified step_factory writes `step_type_spec` to YAML (SPEC layer)

### Key Fixes Applied

#### Source Code Renames
1. `RunRevision.id` → `RunRevision.ulid`
2. `RunRevision.to_dict()` and `from_dict()` updated for `ulid` field
3. `StepResult(step_type=...)` → `StepResult(step_type_spec=...)`
4. `calc_identity.py`: Look for `step_type_spec` or `step_type_gen` instead of `type`

#### Test File Fixes
1. MockStep in ORCA tests: `id` → `ulid`, `step_type` → `step_type_spec`
2. StepResultSummary calls: `step_id` → `step_ulid`, `step_type` → `step_type_spec`
3. CalculationStepEntry calls: `step_id` → `step_ulid`
4. Various dict keys: `run_id` → `run_ulid`, `calc_id` → `calc_ulid`

### Test Results
- **Before:** 107+ failures
- **After Gate A+B:** 28 failures (unit/gates)
- Remaining failures are semantic issues requiring individual investigation

### Remaining Work
The 28 remaining failures are NOT schema violations. They are semantic test failures:
- History digest tests (output_exists checks)
- Wannier90 demo/kpoints tests
- Workflow detection tests
- Capability enforcement tests

These require individual investigation after the schema cleanup is complete.
