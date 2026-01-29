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

**Fix**: Updated `QVService.list_demo_projects()` to read from top-level `meta` section:
- `title` → `demo_meta.get("title")`
- `subtitle` → `demo_meta.get("subtitle")`
- `tags` → `demo_meta.get("tags")`

Also updated compat shaper `_shape_list_demo_projects()` to handle the new fields.

**Files Changed**:
- `src/quantumvitas/api/service.py` (lines 7602-7652)
- `src/quantumvitas/daemon/compat.py` (lines 232-270)

---

### 3. Step Count = 0 (INVESTIGATION NEEDED)

**Error**:
```
expect(stepCount).toBeGreaterThan(0);
Expected: > 0
Received:   0
```

**Observed Behavior**: After creating demo project and navigating to calculation detail, no step rows are rendered.

**Analysis**:
1. **Daemon code looks correct**: `get_calculation_detail` returns `steps` array from `calc_model.steps`
2. **Compat shaper preserves steps**: `_shape_calculation_detail` iterates and shapes each step, doesn't filter/remove
3. **Golden contracts verify steps**: `get_calculation_detail.json` fixture shows 2 steps

**Possible Causes**:
1. **Daemon**: `calc_model.steps` might be empty due to:
   - Calculation.yaml not having steps after materialization
   - `CalculationStepEntry.from_dict` raising `LegacyProjectError` (silent exception)

2. **GUI**: Step rows might not be rendered due to:
   - Frontend bug in step rendering component
   - Wrong `data-testid` attribute pattern

3. **Timing**: Race condition between project creation and calculation loading

**Recommended Next Steps**:
1. Add logging to `_shape_create_demo_project` to capture exceptions
2. Check if calculation.yaml is created correctly with steps after `materialize_project_from_snapshot`
3. Verify GUI renders steps when `steps` array is non-empty

---

### 4. Bands Step Tab & SCF Step Row Not Visible (CASCADING)

**Error**:
```
Locator: getByTestId('qv-calc-analysis-panel').locator('[data-testid="qv-analysis-step-tab-bands"]')
Expected: visible
Error: element(s) not found
```

**Root Cause**: Cascading from Issue #3. If steps aren't showing, analysis tabs and step rows won't be rendered.

---

## Summary of Changes Made

| Issue | Status | Files Changed |
|-------|--------|---------------|
| Schema drift `discover_qe_engines` | FIXED | `tests/contract_crawler/test_schema_preservation.py` |
| Demo card showing ID | FIXED | `src/quantumvitas/api/service.py`, `src/quantumvitas/daemon/compat.py` |
| Steps not showing | NEEDS INVESTIGATION | - |
| Analysis tabs not visible | CASCADING | - |

## Test Coverage Verification

The golden contract tests gate these issues:
- `get_calculation_detail.json` verifies `steps` array is returned with `id`, `name`, `type`, `slug`, `step_file`, `missing`
- `list_demo_projects.json` verifies `title`, `subtitle`, `tags` are returned
- `discover_qe_engines.json` verifies response schema (now allows empty list in CI)

## CI Workflow Status

The schema drift fix should resolve the `discover_qe_engines` test failure. The demo title fix should resolve the `demo_gallery.spec.ts` E2E failure.

The steps-related E2E failures require further investigation into whether it's a daemon issue (empty steps returned) or GUI issue (steps not rendered).
