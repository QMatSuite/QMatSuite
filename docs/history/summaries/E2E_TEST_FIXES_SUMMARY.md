# E2E Test Fixes Summary

**Date**: 2026-01-29
**Author**: Opus

---

## CI Failures Analyzed

### 1. Schema Drift: `discover_qe_engines` (FIXED)

**Error**:
```
FAILED tests/contract_crawler/test_schema_preservation.py::TestSchemaDrift::test_no_schema_drift[discover_qe_engines]
- discovered_engines: Empty list (baseline had 1 items)
```

**Root Cause**: CI doesn't have QE installed, so `discovered_engines` is empty (0 items) while baseline had 1 item. The schema drift test treats this as a violation.

**Fix**: Added `ALLOW_EMPTY_WHEN_BASELINE_HAD_ITEMS` set in `test_schema_preservation.py` to allow `discovered_engines` to be empty when baseline had items (environment-dependent).

**File Changed**: `tests/contract_crawler/test_schema_preservation.py`

---

### 2. Demo Gallery: Card showing ID instead of title (FIXED)

**Error**:
```
Expected pattern: /Silicon band structure/i
Received string:  "si_bands_demo"
```

**Root Cause**: `list_demo_projects()` was reading from wrong path in YAML:
- Was reading: `project.name` (doesn't exist) → fallback to `snapshot_path.stem` = "si_bands_demo"
- Should read: `meta.title` (top-level) = "Silicon band structure"

The demo YAML structure is:
```yaml
project:
  meta:
    name: project2_bands  # Internal name
meta:                      # Top-level metadata for GUI display
  title: "Silicon band structure"
  subtitle: "SCF → NSCF → Bands"
  tags: ["bands", "Si", "PW"]
```

**Fix**: Updated `QMSService.list_demo_projects()` to read from top-level `meta` section:
- `title` → `demo_meta.get("title")`
- `subtitle` → `demo_meta.get("subtitle")`
- `tags` → `demo_meta.get("tags")`

Also updated compat shaper `_shape_list_demo_projects()` to handle the new fields.

**Files Changed**:
- `src/qmatsuite/api/service.py` (lines 7602-7652)
- `src/qmatsuite/daemon/compat.py` (lines 232-270)

---

### 3. Step Count = 0 (FIXED)

**Error**:
```
expect(stepCount).toBeGreaterThan(0);
Expected: > 0
Received:   0
```

**Observed Behavior**: After creating demo project and navigating to calculation list, `steps` array was empty.

**Root Cause**:
1. The HEAD API uses DTOs (`CalculationDTO`) which return `step_ids` (list of ULIDs) instead of the full `steps` array that the v0 API returned
2. The compat layer's `_shape_list_calculations()` function tried to expand `step_ids` to full `steps` by reading `calculation.yaml`, but it couldn't find the file because:
   - It was computing the path as `{project_root}/calculations/{calc_id}` using the ULID as directory name
   - But the actual directory is named using the slug (e.g., `si-bands`), not the ULID

**Fix**:
1. Added `_project_root` to daemon handler response for `list_calculations` (server.py line 2040)
2. Updated `_shape_list_calculations()` to:
   - Extract `_project_root` from response
   - Compute `absolute_path` using `slug` (or `name`) instead of `id` for directory name
   - Pass the correct path to `_expand_step_ids_to_steps()` which reads `calculation.yaml`

**Files Changed**:
- `src/qmatsuite/daemon/server.py` (line 2040: added `_project_root`)
- `src/qmatsuite/daemon/compat.py` (lines 468-522: fixed path computation using slug)

---

### 4. Bands Step Tab & SCF Step Row Not Visible (EXPECTED TO BE FIXED)

**Error**:
```
Locator: getByTestId('qms-calc-analysis-panel').locator('[data-testid="qms-analysis-step-tab-bands"]')
Expected: visible
Error: element(s) not found
```

**Root Cause**: Cascading from Issue #3. If steps aren't showing, analysis tabs and step rows won't be rendered.

**Expected Resolution**: Should be fixed by Issue #3 fix - now that steps are returned correctly, the GUI should render the step tabs and rows.

---

## Summary of Changes Made

| Issue | Status | Files Changed |
|-------|--------|---------------|
| Schema drift `discover_qe_engines` | FIXED | `tests/contract_crawler/test_schema_preservation.py` |
| Demo card showing ID | FIXED | `src/qmatsuite/api/service.py`, `src/qmatsuite/daemon/compat.py` |
| Steps not showing | FIXED | `src/qmatsuite/daemon/server.py`, `src/qmatsuite/daemon/compat.py` |
| Analysis tabs not visible | EXPECTED FIXED | Cascading fix from steps issue |

## Test Coverage Verification

The golden contract tests gate these issues:
- `get_calculation_detail.json` verifies `steps` array is returned with `id`, `name`, `type`, `slug`, `step_file`, `missing`
- `list_calculations.json` verifies `calculations` array includes proper `steps` expansion
- `list_demo_projects.json` verifies `title`, `subtitle`, `tags` are returned
- `discover_qe_engines.json` verifies response schema (now allows empty list in CI)

## CI Workflow Status

All E2E-related issues should now be resolved:

1. **Schema drift `discover_qe_engines`**: Fixed - allows empty list in CI where QE is not installed
2. **Demo gallery title**: Fixed - reads from correct `meta.title` in YAML
3. **Steps not showing**: Fixed - compat layer now correctly expands `step_ids` to full `steps` array
4. **Analysis tabs/rows**: Expected to be fixed by steps fix (cascading dependency)

## Technical Details: Step Expansion Fix

The key insight is that the HEAD API (using DTOs) returns `step_ids` as a list of ULIDs, while the v0 API returned a full `steps` array with `{step_id, id, type, name, slug}` objects.

The compat layer's `_expand_step_ids_to_steps()` function:
1. Takes the list of `step_ids` and the calculation's `absolute_path`
2. Reads `calculation.yaml` from that path
3. Builds a step_id → type mapping from the YAML
4. Returns a full `steps` array with all required fields

The fix ensures the `absolute_path` is computed correctly:
- Before: Used ULID as directory name → path didn't exist → couldn't read YAML → empty types
- After: Uses slug/name as directory name → path exists → reads YAML correctly → full step info
