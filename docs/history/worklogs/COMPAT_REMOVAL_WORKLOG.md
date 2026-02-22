# Compat Removal Worklog

## 2026-02-16: Milestone 1 — Delete Golden Contract Infrastructure

### Files Deleted
- `tests/fixtures/golden_0873ebf/` (entire directory — 102 JSON files + README)
- `tests/fixtures/golden_contracts/` (entire directory — 2 scripts)
- `tests/contract_crawler/test_golden_contracts.py`
- `tests/contract_crawler/golden_comparison.py`
- `tests/contract_crawler/normalization.py`
- `tests/contract_crawler/v0_payloads.py`
- `tests/contract_crawler/test_v0_payloads.py`
- `tests/contract_crawler/test_schema_preservation.py`
- `tests/contract_crawler/test_worktree_imports.py`

### Files Updated

#### `test_gui_field_enforcement.py`
- Removed imports: `shape_response` from compat, `load_golden` from golden_comparison
- Rewrote `_execute_method()` to call daemon directly (no compat shaping)
- Removed `get_testable_methods()` golden fixture dependency
- Soft manifest layer now uses recipe/payload discovery instead of golden fixtures

#### Recipe files (`recipes/*.py`)
- Removed `from ..v0_payloads import build_v0_payload, V0_PAYLOAD_BUILDERS` from:
  - `simple_queries.py`, `engine_methods.py`, `parameterized.py`,
  - `other_methods.py`, `destructive_methods.py`
- Inlined payload builders for methods that used V0_PAYLOAD_BUILDERS:
  - `run_single_step`, `get_structure_vis`, `import_structure`, `rename_structure`,
  - `reorder_calculation_steps`, `reset_step_params`, `instantiate_workflow`,
  - `can_delete_structure`, `set_common_card`, `delete_structure`

#### `report_coverage.py`
- Removed golden fixture dir reference
- `load_golden_fixtures()` returns empty dict (golden infra removed)

#### `test_gui_methods_covered.py`
- Updated to work without golden fixtures
- Uses recipe coverage as primary metric instead

#### Gate tests
- `test_gen_spec_convergence_gate.py`: Removed `test_no_bare_step_type_in_golden`
- `test_daemon_kernel_ban.py`: Removed `test_compat_py_specifically` (compat.py will be deleted)

### Test Results
- **5594 passed, 18 skipped** (full suite green)

---

## 2026-02-16: Milestones 2–5 — Remove Adapters, Shapers, Delete compat.py

Combined M2–M5 into a single batch since removing compat.py is atomic once golden
infrastructure is gone (M1).

### Files Deleted
- `src/qmatsuite/daemon/compat.py` (~997 lines — 12 payload adapters, 27 response shapers)

### Files Modified

#### `src/qmatsuite/daemon/server.py`
- Removed import: `from qmatsuite.daemon.compat import adapt_payload, shape_response`
- Removed `adapt_payload()` / `shape_response()` dispatch from `_dispatch_request()`:
  - Before: `adapted_payload → handler → shaped_result`
  - After: `handler(request.payload)` directly
- Changed `RPCResponse(data=shaped_result)` → `RPCResponse(data=result)`
- Removed `_project_root` injection from `_handle_list_calculations`
- Updated `_handle_set_pseudo_config` to return full config bundle via `get_pseudo_status_bundle()`

#### `src/qmatsuite/api/utils.py`
- Added `default_store_dir` and `default_seed_dir` to `get_pseudo_status_bundle()` config output
- Import `PseudoConfig` from core layer (API layer is allowed to import from core)
- This provides the defaults that compat.py used to inject

#### `gui/src/components/panels/CalculationListPanel.tsx`
- Added null coalescing: `calculation.n_steps ?? 0`
- Note: StructureInfo TypeScript types already match native DTO format (no changes needed)

#### `tests/daemon/contract/test_calculation_rpcs.py`
- Updated `TestAddStepToCalculation` assertions: native handler returns full calculation
  detail with `steps` array (not a standalone `step_ulid`/`ulid`)
- Changed assertions to check `"steps" in response` and verify step count

#### `tests/gates/test_daemon_kernel_ban.py`
- Updated module docstring (removed mention of compat.py)
- Comment on removed test preserved for audit trail

### Errors Encountered & Fixed
1. **Gate test: daemon kernel import ban** — Initially added `from qmatsuite.core.pseudo_config import PseudoConfig` directly in `server.py`. This violated P0 gate (daemon must not import from kernel). Fixed by moving the default dir computation into `api/utils.py:get_pseudo_status_bundle()`.

2. **test_calculation_rpcs.py**: 2 assertion failures — native `add_step_to_calculation` returns `{steps: [...]}` not `{step_ulid: ...}`. Fixed assertions.

### Verification
- Grepped entire `src/` and `tests/` for `daemon.compat` or `daemon/compat` — zero remaining imports
- Remaining "compat" references are all in comments or unrelated code (`calculation/compat_executor.py`, backward-compat comments in tests)

### Test Results
- **5594 passed, 18 skipped** (full suite green)

### Summary
- **Lines removed**: ~997 (compat.py) + ~110 (golden fixtures/tests from M1)
- **GUI changes**: Minimal (null coalescing, native field names)
- **API layer**: `get_pseudo_status_bundle()` now includes default dirs
- **Zero compat shims remain** — all RPC calls use native handler responses directly
