# GUI E2E Tests Refactor for New Calculations UI

## Overview

This document summarizes the E2E test updates made to align with the new Calculations UI paradigm introduced in QuantumVITAS/QMatSuite v2.

## UI Changes Summary

### Navigation & Layout
- **Left sidebar**: Unchanged (Home, Structures, Calculations, Jobs, Resources, Settings)
- **Global "Analysis" nav item**: **REMOVED** - Analysis is now accessed via Calculations → Analysis tab
- **Calculations view**: Now has a tabbed workspace with three tabs:
  - **Overview & Steps**: Calculation overview and step management
  - **Run & Logs**: Job monitoring for the selected calculation
  - **Analysis**: Analysis charts scoped to the selected calculation

### Overview & Steps Tab

#### Overview Mode (no step selected)
- Full calculation overview with:
  - Header: Calculation name + "Calculation" subtitle + "Run Calculation" button
  - Overview fields: Structure, Mode, Steps count, ID
  - Full step list with action buttons (Add Step, Import QE Input, Reorder)
  - File location section

#### Step Focus Mode (step selected)
- Two-column layout:
  - **Left (~30-35%)**: Compact step list
    - "← Back to overview" button
    - "Steps - Step X of N" header
    - Icon buttons for Add/Reorder/Import
    - Compact step list
    - "Run Calculation" button (at top of compact panel)
    - Footer with reveal button
  - **Right (~65-70%)**: StepDetailPanel
    - Breadcrumb: "Calculation Name › Step X · TYPE"
    - "Run step" button
    - Full parameter editor
    - Footer with reveal button (opens step YAML folder)

### Run & Logs Tab
- Shows only the latest job for the selected calculation
- Auto-switches to this tab when "Run Calculation" is clicked
- Job monitoring and logs display

### Analysis Tab
- Replaces the old global Analysis page
- Scoped to the currently selected calculation
- Same analysis types (SCF, DOS, Bands) and charts
- No global calculation dropdown - uses selected calculation from Calculations view

## Test Files Updated

### 1. `demo_calculation.spec.ts`
**Changes:**
- Updated to verify Overview & Steps tab is active by default
- Added verification for calculation header (name + "Calculation" subtitle)
- Updated step selection flow to handle Step Focus mode:
  - Clicking a step now enters Step Focus mode
  - Verifies compact step list appears
  - Verifies StepDetailPanel appears on the right
  - Uses "Back to overview" button to exit focus mode
- Removed assumption that StepDetailPanel is always visible below calculation list

**Key Updates:**
- Uses `qv-calc-tab-overview` to verify tab state
- Uses `qv-calc-overview-tab` and `qv-calc-overview-tab-focus` to distinguish modes
- Uses `qv-compact-step-list` to verify Step Focus mode
- Uses `qv-btn-back-to-overview` to exit focus mode

### 2. `demo_calculation_run.spec.ts`
**Changes:**
- **Removed**: Navigation to global Analysis page (`navigateToView('analysis')`)
- **Added**: Verification that clicking "Run Calculation" auto-switches to Run & Logs tab
- **Updated**: Analysis verification now uses Calculations → Analysis tab:
  - Navigate to Calculations view
  - Select calculation
  - Click Analysis tab (`qv-calc-tab-analysis`)
  - Verify analysis charts load

**Key Updates:**
- Verifies auto-switch to Run & Logs tab after clicking "Run Calculation"
- Uses `qv-calc-tab-run` to verify Run & Logs tab is active
- Uses `qv-calc-tab-analysis` to switch to Analysis tab
- Analysis assertions remain the same (bands chart, Fermi energy, k-path)

### 3. `step_defaults.spec.ts`
**Changes:**
- Updated to handle Step Focus mode when viewing step details
- Removed assumption that StepDetailPanel is always visible
- Added verification for Step Focus mode activation
- Uses "Back to overview" to exit focus mode after assertions

**Key Updates:**
- Clicks step to enter Step Focus mode before reading step details
- Verifies `qv-calc-overview-tab-focus` is visible
- Verifies `qv-step-detail` is visible in focus mode
- Exits focus mode using `qv-btn-back-to-overview`

### 4. `demo_gallery.spec.ts`
**Status**: ✅ No changes needed
- Only navigates to Calculations view and verifies calculations exist
- No assumptions about tabs or step details

### 5. `welcome.spec.ts`
**Status**: ✅ No changes needed
- Only tests welcome screen UI
- No Calculations view interactions

## New Test IDs Added

### Components
- **App.tsx**:
  - `qv-calc-tab-overview`: Overview & Steps tab button
  - `qv-calc-tab-run`: Run & Logs tab button
  - `qv-calc-tab-analysis`: Analysis tab button

- **CalculationOverviewTab.tsx**:
  - `qv-calc-overview-tab`: Overview mode container
  - `qv-calc-overview-tab-focus`: Step Focus mode container
  - `qv-compact-step-list`: Compact step list in focus mode
  - `qv-btn-back-to-overview`: Back to overview button
  - `qv-btn-run-calculation-focus`: Run Calculation button in focus mode (compact panel)

### Existing Test IDs (Still Used)
- `qv-calculations-view`: Calculations view container
- `qv-calculations-list`: Calculations list
- `qv-calculation-row`: Individual calculation row
- `qv-calculation-detail`: Calculation detail panel
- `qv-btn-run-calculation`: Run Calculation button (header)
- `qv-step-row-{stepId}`: Step row with unique ID
- `qv-step-detail`: Step detail panel
- `qv-step-id`: Step ID display
- `qv-step-file-path`: Step file path display
- `qv-add-step-btn`: Add Step button
- `qv-import-step-btn`: Import QE Input button
- `qv-steps-list`: Steps list container

## Selector Patterns

### Preferred Selectors
1. **Test IDs**: Use `getByTestId()` for stable selectors
2. **Role-based**: Use `getByRole('button', { name: /text/i })` for buttons/tabs
3. **Text-based**: Use `getByText()` for labels and headings

### Avoid
- `nth-child()` selectors (brittle to layout changes)
- Deep CSS chains (e.g., `.panel > .content > .section > button`)
- Pixel-based positioning
- Exact text matches (use regex with `/i` flag for case-insensitive)

## Test Flow Patterns

### Running a Calculation
```typescript
// 1. Navigate to Calculations
await navigateToView(appPage, 'calculations');

// 2. Select calculation
await appPage.getByTestId('qv-calculation-row').first().click();

// 3. Click Run Calculation
await appPage.getByTestId('qv-btn-run-calculation').click();

// 4. Verify auto-switch to Run & Logs tab
await expect(appPage.getByTestId('qv-calc-tab-run')).toHaveClass(/calculations-workspace-tab--active/);
```

### Viewing Step Details
```typescript
// 1. Select calculation (in Overview mode)
await appPage.getByTestId('qv-calculation-row').first().click();

// 2. Click a step to enter Step Focus mode
await stepRow.locator('button.step-item').click();

// 3. Verify Step Focus mode
await expect(appPage.getByTestId('qv-calc-overview-tab-focus')).toBeVisible();
await expect(appPage.getByTestId('qv-step-detail')).toBeVisible();

// 4. Exit focus mode
await appPage.getByTestId('qv-btn-back-to-overview').click();
```

### Accessing Analysis
```typescript
// 1. Navigate to Calculations
await navigateToView(appPage, 'calculations');

// 2. Select calculation
await appPage.getByTestId('qv-calculation-row').first().click();

// 3. Switch to Analysis tab
await appPage.getByTestId('qv-calc-tab-analysis').click();

// 4. Select analysis type (auto-loads data automatically)
const bandsTab = appPage.locator('.calculation-analysis-panel__type-btn').filter({ hasText: /bands/i });
await bandsTab.click();

// 5. Wait for chart to appear (CalculationAnalysisPanel auto-loads)
await expect(appPage.getByTestId('qv-analysis-bands-chart')).toBeVisible({ timeout: 30000 });
```

**Note**: `CalculationAnalysisPanel` automatically loads analysis data when the analysis type is selected. There is no "Load" button - data loads automatically via `useEffect` hooks.

## Remaining TODOs

### Coverage Gaps
1. **Run & Logs Tab**: 
   - ✅ Basic job monitoring is tested in `demo_calculation_run.spec.ts`
   - ⚠️ Could add dedicated test for job detail panel interactions
   - ⚠️ Could test job filtering/search if implemented

2. **Analysis Tab**:
   - ✅ Basic bands analysis is tested in `demo_calculation_run.spec.ts`
   - ✅ Auto-load behavior is verified (CalculationAnalysisPanel auto-loads on type selection)
   - ⚠️ Could add tests for SCF and DOS analysis types
   - ⚠️ Could test analysis type auto-detection based on calculation steps

3. **Step Focus Mode**:
   - ✅ Basic step selection and detail viewing is tested
   - ⚠️ Could add test for step parameter editing
   - ⚠️ Could test "Run step" button in focus mode
   - ⚠️ Could test step deletion from focus mode

4. **Tab Switching**:
   - ✅ Auto-switch to Run & Logs is tested
   - ⚠️ Could add test for manual tab switching
   - ⚠️ Could verify tab state persists when switching calculations

### Potential Improvements
1. **Helper Functions**: Create reusable helpers for:
   - Entering Step Focus mode
   - Switching calculation tabs
   - Verifying calculation selection

2. **Test Data**: Consider creating test fixtures for:
   - Pre-configured calculations
   - Mock job data
   - Analysis data snapshots

3. **Accessibility**: Add more ARIA label-based selectors where test IDs are not available

## Migration Checklist

When updating tests in the future:

- [ ] Remove any references to global Analysis navigation
- [ ] Update Analysis access to use Calculations → Analysis tab
- [ ] Verify tab state when testing calculation interactions
- [ ] Handle Step Focus mode when testing step details
- [ ] Use new test IDs for tabs and focus mode elements
- [ ] Verify auto-switch to Run & Logs after running calculation
- [ ] Update selectors to use test IDs or role-based queries
- [ ] Remove assumptions about StepDetailPanel always being visible

## Related Documentation

- `GUI_REFACTOR_CALCULATIONS.md`: Details of the Calculations UI refactor
- Component test IDs: See `gui/src/components/panels/*.tsx` for `data-testid` attributes

