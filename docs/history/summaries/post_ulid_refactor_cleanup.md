# Post-ULID Refactor Cleanup

## Summary

This document describes fixes applied after the ULID-only core refactor to address UI/daemon boundary issues and ensure consistent ULID usage throughout the system.

## Issues Fixed

### 1. delete_calculation Crash: NoneType has no attribute 'strip'

**Problem**: `delete_calculation` RPC handler could crash when UI provided `selector=None`, causing `entry_matches()` to call `.strip()` on None.

**Root Cause**: 
- Daemon handler accepted `selector` without validation
- `entry_matches()` in `project_utils.py` called `identifier.strip()` without checking for None

**Fix**:
- Added validation in `_handle_delete_calculation`: checks for None, non-string, and empty string selectors
- Returns `invalid_argument` error with clear message instead of crashing
- Added defensive checks in `entry_matches()`: raises `ValueError` for None/non-string/empty identifiers
- Added ALWAYS-ON boundary logging: `[DELETE_CALCULATION] endpoint=DELETE_CALCULATION selector=<...> selector_type=<ulid|slug|path|invalid>`
- Updated `can_delete_calculation` and `delete_calculation` service methods to use `calculation_ulid` instead of `selector`

**Files Modified**:
- `src/quantumvitas/daemon/server.py`: `_handle_delete_calculation`, `_handle_can_delete_calculation`
- `src/quantumvitas/api.py`: `can_delete_calculation`, `delete_calculation`
- `src/quantumvitas/core/project_utils.py`: `entry_matches`

**Tests**: `tests/daemon/test_delete_calculation.py`

### 2. Workflow Indicator Missing in UI

**Problem**: Workflow detection badge ("Detected workflow: <name> (present/expected)") was not displaying correctly.

**Root Cause**:
- Backend response format didn't include `workflow_label` (formatted string)
- UI was manually constructing label from `workflow_name` and `coverage`

**Fix**:
- Updated `_handle_detect_workflow_for_calculation` to accept both `calculation_ulid` (preferred) and `calculation` (legacy selector)
- Added `workflow_label` to response: formatted string like "DOS (3/3)" or "Bands (2/3)"
- Added `present_steps` list to response (optional)
- Updated UI to use `workflow_label` directly instead of constructing it
- Added integration logging: `[DETECT_WORKFLOW] endpoint=DETECT_WORKFLOW_FOR_CALCULATION selector=<...> selector_type=<...> resolved_ulid=<...>`

**Files Modified**:
- `src/quantumvitas/daemon/server.py`: `_handle_detect_workflow_for_calculation`
- `gui/src/components/panels/CalculationListPanel.tsx`: Use `workflow_label` from response
- `gui/src/types/qv.ts`: Added `workflow_label` and `present_steps` to `DetectWorkflowForCalculationResult`

### 3. After create_calculation, UI Still Uses Slug → Boundary Resolve Spam

**Problem**: After creating a calculation, UI continued using slug for subsequent RPC calls, causing boundary resolve spam in logs.

**Root Cause**:
- `create_calculation` response included `calculation_id` but UI wasn't consistently using it
- Some UI code paths still used `calculation.slug` for `get_calculation_detail` calls

**Fix**:
- Updated `_handle_create_calculation` to explicitly return `calculation_ulid` in response (in addition to `calculation_id`)
- Updated UI to use `calculation.id` (ULID) for `get_calculation_detail` calls after creation
- Fixed one remaining call in `onCalculationUpdated` that used `selectedCalculationSummary.slug` instead of `.id`

**Files Modified**:
- `src/quantumvitas/daemon/server.py`: `_handle_create_calculation` (added `calculation_ulid` to response)
- `gui/src/App.tsx`: Use `calculation.id` instead of `calculation.slug` for `get_calculation_detail`

**Acceptance**: Normal navigation after creation produces NO `[BOUNDARY_RESOLVE]` logs for calc identity (except initial route entry if route is slug-based).

### 4. get_common_cards Calls get_step_detail with Old Keyword calculation_selector

**Problem**: `QVService.get_common_cards` called `get_step_detail` with `calculation_selector=` keyword, but `get_step_detail` signature had been updated to use `calculation_ulid=`, causing `TypeError`.

**Root Cause**:
- `get_common_cards` signature still used `calculation_selector` parameter
- Internal call to `get_step_detail` used old keyword name
- Daemon handler didn't resolve selector to ULID before calling service

**Fix**:
- Updated `get_common_cards` signature to use `calculation_ulid` instead of `calculation_selector`
- Updated internal call to `get_step_detail` to use `calculation_ulid` keyword
- Updated `_handle_get_common_cards` to resolve selector to ULID at boundary
- Applied same fix to related functions: `update_step_params`, `set_common_card`, `get_pseudo_mapping`, `set_pseudo_mapping`, `reset_step_params`, `import_step_from_qe_input`
- All daemon handlers now resolve selectors to ULIDs before calling service methods

**Files Modified**:
- `src/quantumvitas/api.py`: 
  - `get_common_cards` (signature + internal call)
  - `update_step_params` (signature + internal call)
  - `set_common_card` (signature + internal call)
  - `get_pseudo_mapping` (signature + internal call)
  - `set_pseudo_mapping` (signature + internal call)
  - `reset_step_params` (signature + internal call)
  - `import_step_from_qe_input` (signature + internal call)
- `src/quantumvitas/daemon/server.py`: All corresponding handlers updated to resolve selectors to ULIDs

**Tests**: `tests/daemon/test_get_common_cards.py`

## Design Principles Enforced

1. **ULID-only core**: Core service methods (`QVService.*`) require ULIDs only, not selectors
2. **Selector compatibility at boundary**: Daemon RPC handlers accept selectors (slug/name/ULID) and resolve to ULIDs at the boundary
3. **Explicit validation**: Boundary handlers validate selectors (None, non-string, empty) and return user-friendly errors
4. **Logging**: ALWAYS-ON boundary logs show selector type and resolution path for debugging

## Testing

All fixes include unit tests:
- `tests/daemon/test_delete_calculation.py`: Tests for selector validation
- `tests/daemon/test_get_common_cards.py`: Tests for ULID resolution and service method calls

## Migration Notes

- UI code should prefer `calculation.id` (ULID) over `calculation.slug` for RPC calls
- Daemon handlers automatically resolve selectors to ULIDs, so UI can still pass slugs for backwards compatibility
- Core service methods will reject non-ULID identifiers with `ValueError`

