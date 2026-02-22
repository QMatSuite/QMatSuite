# GUI E2E Test Investigation Report

**Date:** Investigation completed  
**Test File:** `gui/tests/e2e/demo_calculation_run.spec.ts`  
**Test Name:** "run calculation once and verify all computation-dependent behavior"  
**Status:** Investigation Complete - Root Cause Identified

## Executive Summary

The test failure is caused by a **race condition** where the test checks for the bands chart before the async data loading chain completes. The test clicks the "Plot" tab and immediately expects the chart to be visible, but doesn't wait for:
1. React state updates (`viewMode` change)
2. RPC calls to complete (`get_latest_run_for_step`, `get_analysis`)
3. Component state to update (`selectedObjectType`, `bundle`)

**Root Cause:** Missing wait conditions for async operations in the test.

## Test Failure Summary

**Test:** `demo_calculation_run.spec.ts:63:3` - "run calculation once and verify all computation-dependent behavior"

**Failure:** The test fails at line 285 when trying to locate the bands chart element with test ID `qms-analysis-bands-chart`. The element is not found within the 30-second timeout.

**Error Message:**
```
Error: expect(locator).toBeVisible() failed
Locator: getByTestId('qms-analysis-bands-chart')
Expected: visible
Timeout: 30000ms
Error: element(s) not found
```

## Investigation Findings

### 1. Test Flow Analysis

The test follows this sequence:
1. Creates a demo project (Si bands)
2. Navigates to Calculations view
3. Selects a calculation
4. Runs the calculation and waits for completion
5. Switches to Analysis tab
6. Clicks the 'bands' step chip
7. Clicks the "Plot" view mode tab
8. **FAILS HERE:** Waits for `qms-analysis-bands-chart` to be visible

### 2. Code Flow Analysis

#### Chart Rendering Conditions

The bands chart (`qms-analysis-bands-chart`) is rendered in `AnalysisVizPanel.tsx` (line 124) with the test ID:
```typescript
data-testid={`qms-analysis-${selectedObjectType ?? 'unknown'}-chart`}
```

**Critical Finding:** The test ID depends on `selectedObjectType`. If `selectedObjectType` is `null`, the test ID would be `qms-analysis-unknown-chart`, NOT `qms-analysis-bands-chart`.

The chart only renders when ALL of these conditions are met (AnalysisVizPanel.tsx:114):
```typescript
!loading && !error && bundle
```

Additionally, `availableObjectTypes.length > 0` must be true (line 76-82), otherwise a placeholder message is shown.

#### Data Loading Chain

The analysis data loading follows this async chain in `CalculationAnalysisPanel.tsx`:

1. **Step Selection** (line 43): `selectedStepId` is set when step chip is clicked
2. **Run Info Fetch** (line 76-115): `useEffect` calls `get_latest_run_for_step` to get `runInfo.run_ulid`
3. **Object Type Detection** (line 174-231): `useEffect` calls `get_analysis` for each object type and checks if `bundle.provenance_meta.step_ulids` includes `selectedStepId`
4. **Analysis Data Fetch** (line 233-295): `useEffect` calls `get_analysis` again with `selectedObjectType` to get the full bundle
5. **Chart Rendering**: Only after bundle is loaded and `viewMode === 'analysis'`

### 3. Root Cause Analysis

**Primary Issue: Race Condition / Timing Problem**

The test clicks the "Plot" tab (line 282) and immediately checks for the chart (line 285) without waiting for:
- The `viewMode` state to update (React state update is async)
- The `get_latest_run_for_step` RPC call to complete
- The `get_analysis` RPC calls to complete
- The `selectedObjectType` to be set
- The `bundle` data to be loaded

**Potential Failure Scenarios:**

1. **`selectedObjectType` is null**: The chart test ID would be `qms-analysis-unknown-chart`, not `qms-analysis-bands-chart`
2. **`availableObjectTypes` is empty**: The panel shows "No analysis object is available for this step in the current run" instead of the chart
3. **`loading` is still true**: The panel shows "Loading analysis..." instead of the chart
4. **`error` is set**: The panel shows an error message instead of the chart
5. **`bundle` is null**: The chart doesn't render even if other conditions are met
6. **`viewMode` hasn't updated**: The `RawFileViewer` is still shown instead of `AnalysisVizPanel`

### 4. Code Review Findings

#### Missing Wait Conditions in Test

The test at line 282-285:
```typescript
await plotTab.click();

// Wait for bands chart to appear (loading may take time)
await expect(appPage.getByTestId('qms-analysis-bands-chart')).toBeVisible({ timeout: 30000 });
```

**Issues:**
- No wait for `viewMode` to change after clicking Plot tab
- No wait for loading state to complete
- No check for error state before expecting chart
- No verification that `selectedObjectType` is set to "bands"

#### Async Data Loading Dependencies

The data loading has multiple async dependencies:
- `get_latest_run_for_step` (line 91-111): Must complete before object type detection can start
- `get_analysis` detection loop (line 192-227): Must complete to set `availableObjectTypes` and `selectedObjectType`
- `get_analysis` data fetch (line 263-291): Must complete to set `analysisResponse.bundle`

All of these are async and the test doesn't wait for any of them.

### 5. Evidence from Test Output

From the test logs, we can see:
- The calculation job completes successfully
- The Analysis tab is clicked and becomes active
- The bands step chip is clicked
- The Plot tab is clicked
- **Then the test immediately fails** - suggesting the chart hasn't rendered yet

No errors are visible in the daemon logs for `get_analysis` or `get_latest_run_for_step`, suggesting the issue is timing-related rather than an actual RPC failure.

### 6. Potential Issues in Component Logic

#### Object Type Detection Logic (line 210)

```typescript
if (payload.bundle.provenance_meta.step_ulids.includes(selectedStepId)) {
  matched.push(objectType);
}
```

**Potential Issue:** If the `provenance_meta.step_ulids` doesn't include the exact `selectedStepId` ULID, the object type won't be matched, and `availableObjectTypes` will be empty.

#### Step ULID Matching

The test selects the step by clicking the chip with `data-testid="qms-analysis-step-tab-bands"` (line 268), which sets `selectedStepId` to `step.ulid` (line 368). However, the analysis bundle's `provenance_meta.step_ulids` must include this exact ULID for the match to work.

### 7. Recommendations

#### Immediate Fixes (Test Side)

1. **Add wait for viewMode change**: After clicking Plot tab, wait for the tab to have the active class
2. **Add wait for loading state**: Wait for "Loading analysis..." to disappear or for error/placeholder to appear
3. **Add error handling**: Check for error messages before expecting the chart
4. **Add intermediate checks**: Verify `availableObjectTypes` is not empty, or wait for a placeholder/error message

#### Potential Component Fixes

1. **Add loading indicators with test IDs**: Make it easier for tests to wait for loading states
2. **Add error state test IDs**: Make error states testable
3. **Add debug logging**: Log when `selectedObjectType` is set and when bundle is loaded
4. **Consider optimistic UI**: Show a loading state immediately when Plot tab is clicked

### 8. Debugging Steps Needed

To fully diagnose this issue, we would need:

1. **Add console logging** in `CalculationAnalysisPanel.tsx`:
   - Log when `runInfo.run_ulid` is set
   - Log when `availableObjectTypes` is set
   - Log when `selectedObjectType` is set
   - Log when `analysisResponse` is set
   - Log when `viewMode` changes

2. **Add test debugging**:
   - Take a screenshot when the chart is expected
   - Check for error messages in the DOM
   - Check for loading indicators
   - Check for placeholder messages
   - Verify `selectedObjectType` value in the DOM

3. **Check RPC responses**:
   - Verify `get_latest_run_for_step` returns a valid `run_ulid`
   - Verify `get_analysis` returns valid data
   - Verify `bundle.provenance_meta.step_ulids` includes the selected step ULID

### 9. Conclusion

The test failure is most likely due to a **race condition** where the test checks for the chart before the async data loading chain completes. The test should wait for intermediate states (loading, error, or success) before expecting the final chart to be visible.

The component logic appears correct, but the test needs to be more defensive about waiting for async operations to complete.

**Most Likely Root Cause:** The test doesn't wait for `selectedObjectType` to be set to "bands" before checking for the chart, or the async `get_analysis` calls haven't completed yet when the test checks for the chart element.

