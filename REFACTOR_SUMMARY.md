# Calculation Studio Refactor Summary

## Overview
Refactored the Calculations view into a "Calculation Studio" with a three-column layout and internal tabs, reusing existing Jobs & Analysis components.

## Files Changed

### Modified Files

1. **`gui/src/App.tsx`**
   - Refactored `calculations` view case to use three-column horizontal layout
   - Replaced `VerticalResizablePane` with three `ResizablePane` components (left, middle, right)
   - Left column: Calculation list (existing `CalculationListPanel`)
   - Middle column: Calculation detail with tabs (existing `CalculationDetailPanel`)
   - Right column: Step detail (existing `StepDetailPanel`, shown when step is selected)
   - Updated localStorage keys: `qv-calculation-detail-width`, `qv-step-detail-width`

2. **`gui/src/App.css`**
   - Updated `.calculations-view` CSS for three-column layout
   - Removed vertical split styles (`.calculation-detail-resizable`)
   - Added styles for `.calculations-view__step-detail` column

3. **`gui/src/components/panels/CalculationListPanel.tsx`**
   - Added tab navigation to `CalculationDetailPanel` component
   - Added `activeTab` state: `'overview' | 'run' | 'analysis'`
   - Wrapped existing overview/steps content in conditional render for `overview` tab
   - Added placeholder content for `run` and `analysis` tabs (later replaced with actual components)
   - Imported and integrated `CalculationRunPanel` and `CalculationAnalysisPanel`
   - Run button now only shows in Overview tab

4. **`gui/src/components/panels/CalculationListPanel.css`**
   - Added styles for `.calculation-detail-tabs` (tab navigation bar)
   - Added styles for `.calculation-detail-tab` and `.calculation-detail-tab--active`
   - Added styles for `.calculation-detail-tab-content` (tab content container)
   - Added `.tab-placeholder` styles (removed after implementation)

5. **`gui/src/components/panels/index.ts`**
   - Added exports for `CalculationRunPanel` and `CalculationAnalysisPanel`

### New Files Created

1. **`gui/src/components/panels/CalculationRunPanel.tsx`**
   - New component for "Run & Logs" tab
   - Filters jobs by calculation (matches by `target_name` or `target_calculation_id`)
   - Reuses `useJobs` and `useJobDetail` hooks from `JobsPanel`
   - Displays job list (left) and job detail with logs (right) in split view
   - Includes `StatusBadge` component (reused from `JobsPanel` pattern)
   - Auto-selects most recent job for the calculation

2. **`gui/src/components/panels/CalculationRunPanel.css`**
   - Styles for `CalculationRunPanel` component
   - Split layout for job list and job detail
   - Job item selection styles
   - Job detail panel styles (reusing `JobsPanel` patterns)

3. **`gui/src/components/panels/CalculationAnalysisPanel.tsx`**
   - New component for "Analysis" tab
   - Fixed to a single calculation (no global calculation selector)
   - Reuses chart components: `ScfConvergenceChart`, `DosChart`, `BandsChart` from `AnalysisPanel`
   - Auto-detects analysis type based on calculation's last step (DOS → DOS, Bands → Bands, else → SCF)
   - Auto-loads analysis data when tab is active
   - Includes analysis type selector (SCF/DOS/Bands buttons)
   - Includes SCF step selector when multiple SCF steps exist

4. **`gui/src/components/panels/CalculationAnalysisPanel.css`**
   - Styles for `CalculationAnalysisPanel` component
   - Tab-like analysis type selector
   - Step selector styles
   - Content area for charts

## New Components

1. **`CalculationRunPanel`** (`gui/src/components/panels/CalculationRunPanel.tsx`)
   - Shows jobs and logs for a specific calculation
   - Filters jobs by calculation slug/ID
   - Displays job list and detail in split view
   - Reuses `useJobs` and `useJobDetail` hooks

2. **`CalculationAnalysisPanel`** (`gui/src/components/panels/CalculationAnalysisPanel.tsx`)
   - Shows SCF/DOS/Bands analysis for a specific calculation
   - Reuses chart components from `AnalysisPanel`
   - Auto-detects and loads appropriate analysis type

## Behavior Changes

### User-Visible Changes

1. **Three-Column Layout**
   - Calculations view now has three resizable columns instead of two
   - Left: Calculation list (unchanged)
   - Middle: Calculation detail with tabs (new tabs)
   - Right: Step detail (moved from vertical split to horizontal column)
   - All columns are horizontally resizable with localStorage persistence

2. **Tabs in Calculation Detail**
   - "Overview & Steps" tab (default): Contains existing calculation overview and step list
   - "Run & Logs" tab: Shows jobs filtered for this calculation with logs
   - "Analysis" tab: Shows SCF/DOS/Bands analysis for this calculation
   - Run button only appears in Overview tab

3. **Step Selection Flow**
   - Clicking a step in the middle column (Overview & Steps tab) opens step detail in the right column
   - Step detail panel is now in a separate resizable column (more horizontal space)
   - Step selection behavior unchanged (still uses ULID from `calculation.yaml`)

4. **Jobs View**
   - Jobs are now filtered by calculation in the "Run & Logs" tab
   - Shows only jobs for the current calculation
   - Auto-selects most recent job
   - Job detail and logs displayed inline (not in separate panel)

5. **Analysis View**
   - Analysis is now calculation-specific in the "Analysis" tab
   - Auto-detects analysis type from calculation's last step
   - Auto-loads data when tab is active
   - No global calculation selector (fixed to current calculation)

### Preserved Behavior

- Standalone Jobs page (`/jobs`) still works as global job monitor
- Standalone Analysis page (`/analysis`) still works as global analysis dashboard
- All existing calculation editing features (add step, reorder, delete, change structure) unchanged
- Step parameter editing unchanged
- All API calls and backend behavior unchanged
- All tests should pass (no backend changes)

## Technical Details

### Layout Structure

```
calculations-view (flex row)
├── ResizablePane (left, 320-600px)
│   └── CalculationListPanel
│   └── "New Calculation" button
├── ResizablePane (middle, 400-800px)
│   └── CalculationDetailPanel
│       ├── Header (title + Run button)
│       ├── Tabs (Overview & Steps | Run & Logs | Analysis)
│       └── Tab Content
│           ├── Overview: existing overview + steps list
│           ├── Run & Logs: CalculationRunPanel
│           └── Analysis: CalculationAnalysisPanel
└── ResizablePane (right, 360-720px, conditional)
    └── StepDetailPanel (when step selected)
```

### State Management

- Tab state (`activeTab`) is local to `CalculationDetailPanel`
- Job filtering in `CalculationRunPanel` uses `useJobs` hook with calculation filter
- Analysis data loading in `CalculationAnalysisPanel` uses `useQVClient` hook
- All existing state in `App.tsx` preserved (selected calculation, selected step, etc.)

### Data Flow

- **Jobs**: `useJobs({ projectRoot })` → filter by `calculation.slug` → display in `CalculationRunPanel`
- **Analysis**: `qv.call('get_scf_convergence'|'get_dos_data'|'get_band_structure_data')` → display in `CalculationAnalysisPanel`
- **Steps**: Existing flow unchanged (ULID-based selection from `calculation.yaml`)

## Testing Notes

- No backend API changes, so daemon tests should pass unchanged
- Frontend tests may need updates if they depend on DOM structure (use `data-testid` attributes)
- Manual verification recommended:
  - Three-column layout resizes correctly
  - Tabs switch correctly
  - Jobs filter by calculation
  - Analysis loads for current calculation
  - Step selection still works
  - Standalone Jobs/Analysis pages still work

## Future Considerations

- Consider deprecating standalone Jobs/Analysis pages in favor of calculation-centric workflow
- Could add keyboard shortcuts for tab switching
- Could add "Run & Logs" tab auto-switch when job is submitted
- Could add "Analysis" tab auto-switch when calculation completes

