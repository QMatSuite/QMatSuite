# Calculations View Layout Refactor Summary

## Overview
Refactored the Calculations view to use a top-level tab bar (like VS Code) with a fixed left sidebar and a right workspace controlled by tabs. The step parameter inspector (StepDetailPanel) now appears only in the Overview & Steps tab.

**Update**: The global Analysis view has been removed. All analysis functionality is now accessed via the Calculations → Analysis tab only.

## Files Changed

### Modified Files

1. **`gui/src/App.tsx`**
   - Added `activeCalcTab` state: `'overview' | 'run' | 'analysis'` (default: 'overview')
   - Refactored `calculations` view case to use:
     - Left: Fixed-width `CalculationListPanel` (like VS Code Explorer)
     - Right: Workspace with top-level tab bar + tab content
   - Updated `handleSelectCalculation` to NOT change `activeCalcTab` when switching calculations
   - Updated `handleRunCalculation` to auto-switch to `'run'` tab after successful job submission
   - Updated `handleSelectStep` to handle empty string (clear selection)

2. **`gui/src/App.css`**
   - Added styles for `.calculations-view__workspace` (right workspace container)
   - Added styles for `.calculations-workspace-tabs` (top-level tab bar)
   - Added styles for `.calculations-workspace-tab` and `.calculations-workspace-tab--active`
   - Added styles for `.calculations-workspace-content` (tab content area)

3. **`gui/src/components/panels/CalculationListPanel.tsx`**
   - Removed internal tab navigation (removed `activeTab` state and tab UI)
   - Removed imports for `CalculationRunPanel` and `CalculationAnalysisPanel`
   - `CalculationDetailPanel` now renders only the overview and steps content (no tabs)
   - Run button always visible (no conditional on tab)

4. **`gui/src/components/panels/index.ts`**
   - Added exports for `CalculationOverviewTab`, `CalculationRunTab`, `CalculationAnalysisTab`

### New Files Created

1. **`gui/src/components/panels/CalculationOverviewTab.tsx`** + `.css`
   - Overview & Steps tab content component
   - Split pane layout: left (calculation overview + steps list), right (StepDetailPanel when step selected)
   - Uses `ResizablePane` for horizontal split
   - StepDetailPanel only rendered when `selectedStepId` is set

2. **`gui/src/components/panels/CalculationRunTab.tsx`** + `.css`
   - Run & Logs tab content component
   - Shows ONLY the latest job for the selected calculation (not a job list)
   - Filters jobs by calculation slug/ID using `useJobs` hook
   - Displays job status, step progress, I/O directory, logs
   - Includes StatusBadge component (reused pattern from JobsPanel)
   - Shows empty state when no jobs exist
   - Includes hint: "When the run is finished, switch to the Analysis tab to view results"
   - Does NOT auto-switch to Analysis when job completes

3. **`gui/src/components/panels/CalculationAnalysisTab.tsx`** + `.css`
   - Analysis tab content component
   - Wrapper around `CalculationAnalysisPanel` (reuses existing analysis logic)
   - Fixed to selected calculation (no global calculation selector)

## New Components

1. **`CalculationOverviewTab`** (`gui/src/components/panels/CalculationOverviewTab.tsx`)
   - Overview & Steps tab with split pane (calculation detail + step detail)
   - StepDetailPanel only visible when step is selected
   - All calculation editing features (add step, reorder, delete, change structure)

2. **`CalculationRunTab`** (`gui/src/components/panels/CalculationRunTab.tsx`)
   - Run & Logs tab showing latest job only
   - Filters jobs by calculation, shows most recent
   - Displays job info, step progress, logs
   - Empty state when no jobs exist

3. **`CalculationAnalysisTab`** (`gui/src/components/panels/CalculationAnalysisTab.tsx`)
   - Analysis tab wrapper
   - Reuses `CalculationAnalysisPanel` for SCF/DOS/Bands charts

## Behavior Changes

### User-Visible Changes

1. **Top-Level Tab Bar**
   - Tabs are now at the workspace level (not nested inside calculation card)
   - Three tabs: "Overview & Steps" | "Run & Logs" | "Analysis"
   - Tab bar is visually part of the right workspace header

2. **Layout Structure**
   - Left: Fixed calculation list (like VS Code Explorer)
   - Right: Workspace with tabs (3/4 of screen)
   - StepDetailPanel only appears in Overview & Steps tab (right pane when step selected)
   - StepDetailPanel is completely hidden in Run & Logs and Analysis tabs

3. **Tab Persistence**
   - When switching calculations, the active tab stays the same (user stays in current tab)
   - Step selection is cleared when switching calculations

4. **Run Calculation Auto-Switch**
   - Clicking "Run Calculation" in Overview & Steps tab:
     - Submits job via daemon API
     - On success: automatically switches to Run & Logs tab
     - On error: stays in Overview tab, shows error notification
   - Does NOT auto-switch to Analysis when run completes

5. **Run & Logs Tab**
   - Shows only the latest job for the selected calculation
   - No job list - focuses on current/most recent run
   - Displays job status, step progress timeline, logs
   - Empty state with hint to use "Run Calculation" button
   - Hint shown when job completes: "switch to Analysis tab to view results"

6. **Analysis Tab**
   - Fixed to selected calculation (no global selector)
   - Reuses existing analysis charts (SCF/DOS/Bands)
   - StepDetailPanel not visible here

### Preserved Behavior

- Standalone Jobs page (`/jobs`) still works as global job monitor (unchanged)
- Standalone Analysis page (`/analysis`) still works as global analysis dashboard (unchanged)
- All calculation editing features unchanged (add step, reorder, delete, change structure)
- Step parameter editing unchanged
- All API calls and backend behavior unchanged
- All tests pass (no backend changes)

## Technical Details

### State Management

**App.tsx state:**
- `selectedCalculationSummary`: CalculationInfo from list (for list display)
- `selectedCalculationDetail`: CalculationDetailResult from get_calculation_detail (canonical steps)
- `selectedStepId`: string | null (ULID of selected step, only used in Overview tab)
- `activeCalcTab`: 'overview' | 'run' | 'analysis' (top-level tab state)

**State flow:**
- Selecting calculation: Updates `selectedCalculationSummary` and `selectedCalculationDetail`, clears `selectedStepId`, keeps `activeCalcTab`
- Selecting step: Updates `selectedStepId` (only relevant in Overview tab)
- Running calculation: On success, sets `activeCalcTab = 'run'`
- Switching tabs: Updates `activeCalcTab` only

### Layout Structure

```
calculations-view (flex row)
├── ResizablePane (left, 320-600px, fixed)
│   └── CalculationListPanel
│   └── "New Calculation" button
└── calculations-view__workspace (right, flex: 1)
    ├── calculations-workspace-tabs (top-level tab bar)
    │   ├── Overview & Steps
    │   ├── Run & Logs
    │   └── Analysis
    └── calculations-workspace-content
        ├── activeCalcTab === 'overview' → CalculationOverviewTab
        │   ├── ResizablePane (left: CalculationDetailPanel)
        │   └── ResizablePane (right: StepDetailPanel, conditional)
        ├── activeCalcTab === 'run' → CalculationRunTab
        │   └── Latest job only (status + logs)
        └── activeCalcTab === 'analysis' → CalculationAnalysisTab
            └── CalculationAnalysisPanel (charts)
```

### Data Flow

**Overview Tab:**
- CalculationDetailPanel: Shows overview + steps list
- StepDetailPanel: Shows when `selectedStepId` is set
- Run Calculation: `handleRunCalculation` → daemon API → on success: `setActiveCalcTab('run')`

**Run & Logs Tab:**
- `useJobs({ projectRoot })` → filter by `calculation.slug` → find latest → `useJobDetail({ jobId: latestJob.id })`
- Displays job info, step progress, logs
- Polls every 2s while job is active

**Analysis Tab:**
- `CalculationAnalysisPanel` uses `selectedCalculation` from props
- Auto-detects analysis type from calculation's last step
- Loads data when tab is active

## Testing Notes

- ✅ All daemon tests pass (`pytest tests/daemon/test_gui_calculation_detail.py`)
- ✅ No backend API changes
- ✅ No linter errors

**Manual verification checklist:**
- [ ] Three-column layout: left list, right workspace with tabs
- [ ] Top-level tab bar visible and functional
- [ ] Overview & Steps: calculation detail + step list, StepDetailPanel on right when step selected
- [ ] Run & Logs: shows latest job only, no job list
- [ ] Analysis: shows charts for selected calculation, no StepDetailPanel
- [ ] Run Calculation: auto-switches to Run & Logs on success
- [ ] Run & Logs: does NOT auto-switch to Analysis when job completes
- [ ] Switching calculations: tab stays the same
- [ ] StepDetailPanel: only visible in Overview tab
- [ ] Standalone Jobs/Analysis pages: still work as before

## Global Analysis View Removal

### Changes Made

1. **Removed from Sidebar Navigation**
   - Removed 'analysis' from `ViewType` in `gui/src/components/layout/Sidebar.tsx`
   - Removed Analysis nav button from sidebar

2. **Removed from App.tsx Routing**
   - Removed `case 'analysis':` branch from `renderMainContent()`
   - Removed `AnalysisPanel` import (no longer used as top-level view)
   - Removed 'analysis' from header title logic
   - Removed 'analysis' view check from `useEffect` that fetches calculations

3. **Updated Navigation Callbacks**
   - `handleViewAnalysisFromJob`: Now navigates to Calculations view and auto-switches to Analysis tab
   - Jobs panel "View Analysis" button now routes to Calculations → Analysis tab

4. **Preserved Analysis Components**
   - `AnalysisPanel.tsx` kept (used by `CalculationAnalysisPanel` for chart components)
   - Chart components (`ScfConvergenceChart`, `DosChart`, `BandsChart`) still exported
   - All analysis data loading logic preserved

### User-Facing Changes

- **Sidebar Navigation**: No longer shows "Analysis" as a top-level nav item
- **Analysis Access**: Users access analysis via:
  1. Go to Calculations view
  2. Select a calculation
  3. Click "Analysis" tab in the right workspace
- **Jobs Panel**: "View Analysis" button now navigates to Calculations view with Analysis tab active

### Files Modified

- `gui/src/components/layout/Sidebar.tsx` - Removed Analysis nav item and ViewType
- `gui/src/App.tsx` - Removed global Analysis view routing, updated navigation callbacks
- `GUI_REFACTOR_CALCULATIONS.md` - Updated documentation

## Calculation List Width Optimization

### Changes Made

1. **Reduced Default and Minimum Width**
   - Changed `ResizablePane` default width from 420px → 260px → **200px** (final)
   - Changed minimum width from 320px → 220px → **180px** (final)
   - Maximum width: 600px → **420px** (final)
   - Calculation list now behaves like VS Code Explorer: narrow by default

2. **Fixed Layout Constraints Preventing Narrow Width**
   - **ResizablePane**: Added documentation explaining width behavior (inline `width: ${width}px` with `flexShrink: 0`)
   - **`.calculations-view__list`**: Changed from `flex: 1` to `flex: 0 0 auto` to respect ResizablePane width
   - Added `min-width: 0` to allow proper flex shrinking
   - Removed any implicit min-width constraints that were preventing the pane from getting narrow

3. **Text Wrapping for Long Content**
   - Added `word-break: break-word` and `overflow-wrap: anywhere` to:
     - Calculation names
     - Structure names
     - Step chains (scf→nscf→bands_pw→bands)
     - File paths
   - Added `min-width: 0` to calculation items and content containers to allow proper flex shrinking
   - Long step chains now wrap to multiple lines instead of forcing column wider

4. **Reduced Padding for Narrow Widths**
   - Calculation card padding: `var(--space-4)` → `var(--space-3)`
   - Calculation list padding: `var(--space-3)` → `var(--space-2)`
   - Panel header padding: `var(--space-4) var(--space-5)` → `var(--space-3) var(--space-4)`
   - Added `box-sizing: border-box` to ensure padding is included in width calculations

5. **Icon-Only Refresh Button**
   - Changed refresh button from icon + text to icon-only
   - Added `aria-label="Refresh"` and `title="Refresh"` for accessibility
   - Reduced horizontal footprint while maintaining usability
   - Button shows tooltip on hover

### Root Cause Analysis

**What Limited the Pane Width Originally:**
- `.calculations-view__list` was using `flex: 1` which made it grow to fill available space
- No explicit `flex: 0 0 auto` to respect ResizablePane's inline width
- Padding in cards and list container added extra width that wasn't accounted for
- Missing `min-width: 0` on flex items prevented proper shrinking

**The Fix:**
- Changed `.calculations-view__list` to `flex: 0 0 auto` so it uses ResizablePane's width exactly
- Reduced padding throughout to minimize wasted space at narrow widths
- Ensured all flex items have `min-width: 0` to allow shrinking
- ResizablePane's inline `width: ${width}px` with `flexShrink: 0` now properly controls the pane width

### Files Modified

- `gui/src/App.tsx` - Updated ResizablePane width settings (defaultWidth: 200px, minWidth: 180px, maxWidth: 420px)
- `gui/src/App.css` - Fixed `.calculations-view__list` flex behavior to respect ResizablePane width
- `gui/src/components/layout/ResizablePane.tsx` - Added documentation about width behavior
- `gui/src/components/panels/CalculationListPanel.tsx` - Made refresh button icon-only
- `gui/src/components/panels/CalculationListPanel.css` - Added text wrapping styles, reduced padding, icon-only button styles

## Sidebar Collapse/Expand Width Fix

### Changes Made

1. **Fixed Sidebar Width Behavior**
   - **Expanded state**: Fixed width of 230px (narrow, just enough for icons + labels)
   - **Collapsed state**: Fixed width of 64px (icon-only strip)
   - Width is controlled by `AppShell.css` using `:has()` selector to detect collapsed state
   - Main content area (`app-shell__body`) uses `flex: 1` to expand and fill remaining width

2. **Project Root Input Truncation**
   - Project Root path display now properly truncates with ellipsis inside the fixed 230px width
   - Added `min-width: 0` and `max-width: 100%` to path text container
   - Added `box-sizing: border-box` to ensure padding is included in width calculations
   - Path no longer forces sidebar to grow wider

3. **Layout Constraints**
   - Removed CSS variable-based width (`--sidebar-width`) in favor of fixed pixel widths
   - Sidebar sections and labels have `min-width: 0` and `max-width: 100%` to prevent overflow
   - Added smooth transition for width changes when collapsing/expanding

### Root Cause Analysis

**What Limited the Sidebar Width:**
- AppShell was using CSS variables (`--sidebar-width: 300px`) that didn't change based on collapsed state
- Sidebar component had its own width rules that conflicted with AppShell
- Project Root input didn't have proper truncation constraints
- No mechanism to detect collapsed state in AppShell CSS

**The Fix:**
- AppShell now uses fixed widths (230px expanded, 64px collapsed) with `:has()` selector
- Sidebar component width is controlled by parent (AppShell), not itself
- Project Root input has proper flex constraints for truncation
- Main content area automatically expands due to `flex: 1`

### Files Modified

- `gui/src/components/layout/AppShell.css` - Fixed sidebar width based on collapsed state
- `gui/src/components/layout/Sidebar.css` - Added truncation constraints, removed conflicting width rules
- `gui/src/components/layout/Sidebar.tsx` - Added comment explaining collapsed vs expanded behavior

## Calculation Card Actions Refactor

### Changes Made

1. **Moved Actions to Header Row**
   - Edit/delete actions moved from separate right-hand column into the header row next to the calculation title
   - Actions are now horizontally aligned (flex-direction: row) instead of vertically stacked
   - Actions remain hover-only (opacity: 0 by default, fade in on card hover)

2. **Title Truncation**
   - Calculation name now truncates with ellipsis (`text-overflow: ellipsis`, `white-space: nowrap`)
   - Title uses `flex: 1 1 auto` with `min-width: 0` to allow truncation
   - Actions use `flex-shrink: 0` to remain visible even when title is truncated

3. **Removed Separate Actions Column**
   - Removed the dedicated right-hand column that was enforcing a large minimum width
   - Card layout no longer has a separate actions gutter
   - Card now uses `width: 100%` and `max-width: 100%` with `box-sizing: border-box`

### Reason

The separate right-hand actions column was enforcing a large minimum width for the calculation list pane, preventing it from shrinking to the desired `minWidth` (180px). By moving actions into the header row and making the title truncate, the pane can now shrink much smaller while keeping actions accessible on hover.

### Files Modified

- `gui/src/components/panels/CalculationListPanel.tsx` - Refactored card structure to move actions into header
- `gui/src/components/panels/CalculationListPanel.css` - Updated styles for header layout, title truncation, and inline actions

## Button Visual Hierarchy Refactor

### Changes Made

1. **Calculations Refresh Button - Ghost Icon Style**
   - Changed from filled button to subtle ghost icon
   - No solid background by default, transparent
   - No heavy border
   - Icon-only (28px circular button)
   - On hover: soft circular background (rgba(255, 255, 255, 0.05))
   - Blends into header background, clearly secondary

2. **Run Calculation Button - Large Primary CTA**
   - Promoted to large, prominent primary call-to-action
   - Pill-shaped button (border-radius: 999px)
   - High-contrast primary color background
   - Larger size (padding: 0.55rem 1.4rem, font-size: 0.9rem)
   - Icon + label ("▶️ Run Calculation")
   - Hover effect with slight elevation (translateY + shadow)
   - Clearly stands out from secondary buttons like "Add Step", "Import QE Input"

3. **Title Truncation in Header**
   - Calculation title in header now truncates with ellipsis if long
   - Ensures Run Calculation button remains visible even with long names
   - Title uses `flex: 1 1 auto` with `min-width: 0` for proper truncation

### Visual Hierarchy

- **Primary CTA**: Run Calculation button (large, high-contrast, prominent)
- **Secondary Actions**: Add Step, Import QE Input, Reorder (smaller, lower contrast)
- **Tertiary Controls**: Refresh icon (ghost, subtle, blends into background)

### Files Modified

- `gui/src/components/panels/CalculationListPanel.tsx` - Updated button classes and structure
- `gui/src/components/panels/CalculationListPanel.css` - Added `.qms-icon-button--ghost` and `.qms-button--primary--large` styles

## Hierarchy Clarification Refactor

### Changes Made

1. **Left Column Header: "All Calculations"**
   - Changed title from "Calculations" to "All Calculations"
   - Makes it clear the left card is the list of all calculations
   - Refresh icon and "N total" badge remain unchanged

2. **Middle Column Header: "Calculation" Subtitle**
   - Added muted subtitle "Calculation" directly under the calculation name
   - Calculation name remains as main title (e.g. "Si bands")
   - Subtitle is small (11px), muted color, positioned below title
   - Clearly indicates the middle card is a single calculation

3. **Right Column: Breadcrumb + Step Position**
   - Added breadcrumb showing "Calculation Name · Step X of Y" above step title
   - Shows step type chip below step title (e.g. "SCF", "NSCF")
   - Breadcrumb only appears when calculation name and step position data are available
   - Explicitly shows that the step belongs to a specific calculation and its position in the chain

### Visual Hierarchy

- **All Calculations** (left) → **Calculation: Si bands** (middle) → **Si bands · Step 1 of 4** (right)
- Clear progression from list → detail → step detail
- Each level shows its relationship to the parent level

### Files Modified

- `gui/src/components/panels/CalculationListPanel.tsx` - Changed "Calculations" to "All Calculations", added subtitle structure
- `gui/src/components/panels/CalculationListPanel.css` - Added `.qms-calc-header-subtitle` styles
- `gui/src/components/panels/CalculationOverviewTab.tsx` - Compute step index/count and pass to StepDetailPanel
- `gui/src/components/panels/StepDetailPanel.tsx` - Added breadcrumb props and rendering
- `gui/src/components/panels/StepDetailPanel.css` - Added `.qms-step-breadcrumb` and `.qms-step-type-chip` styles

## Step Focus Mode

### Overview

Introduced a "Step Focus" mode in the **Overview & Steps** tab that provides a focused editing experience when working with individual calculation steps. When a step is selected, the layout transforms to give the step detail editor maximum space while keeping a compact step list accessible.

### Two Modes

1. **Overview Mode (no step selected)**
   - Full calculation overview with:
     - Calculation header (name + "Calculation" subtitle + "Run Calculation" button)
     - Overview fields (structure selector, mode, steps count, ID, etc.)
     - Full step list with large action buttons ("Add Step", "Import QE Input", "Reorder")
     - File location with reveal button
   - No StepDetailPanel is rendered

2. **Step Focus Mode (step selected)**
   - Two-column layout within the calculation panel:
     - **Left column (~30-35% width)**: Compact step list
       - "← Back to overview" button at top
       - Header with "Steps" label, "Step X of N" indicator, and three icon-only buttons (Add, Reorder, Import)
       - Compact step list showing step number, type, and file path
       - Footer with reveal button
     - **Right column (~65-70% width)**: StepDetailPanel as main workspace
       - Focus header with breadcrumb ("Calculation Name › Step X · TYPE") and "Run step" button
       - Full QE parameter editor
       - Footer with reveal button

### Entering/Exiting Focus Mode

- **Enter**: Click any step in the step list → automatically enters focus mode
- **Exit**: 
  - Click "← Back to overview" button
  - Click the already selected step again (toggle behavior)
  - Click on empty background area (anywhere in the focus mode container that's not an interactive element)
  - Step is deleted (if it was the selected one)

### Button Visibility Rules

- **Large action buttons** ("Add Step", "Import QE Input", "Reorder"):
  - Overview mode: Visible as large buttons
  - Focus mode: Hidden, replaced by icon-only buttons in compact step list header
- **Reveal button**:
  - Overview mode: Large "Reveal" button in file location section (reveals calculation folder)
  - Focus mode: Small icon button in StepDetailPanel footer (reveals step YAML folder, not calculation folder)
- **Run Calculation button**: Always visible in calculation header (both modes)

### Implementation Details

- Added `stepFocused` state in `CalculationOverviewTab` to track focus mode
- `CalculationDetailPanel` accepts `isFocusMode` prop to hide large buttons
- `StepDetailPanel` accepts `isFocusMode` prop to show focus header/footer
- Compact step list component (`CompactStepList`) handles step selection and actions in focus mode
- Two-column layout uses `ResizablePane` for the left column, flex for the right column

### Refinements (Latest Updates)

1. **Scrollable Content in Both Modes**
   - Both Overview and Step Focus modes now use a shared scroll container (`calculation-overview-tab__scroll-container`)
   - The entire content area (everything under the calculation header) is vertically scrollable
   - Prevents content overflow and ensures all content is accessible regardless of viewport height

2. **Background Click to Exit Focus**
   - Clicking on empty background areas in Step Focus mode exits focus and returns to Overview mode
   - Interactive elements (buttons, step cards, etc.) use `stopPropagation()` to prevent accidental exits
   - Provides intuitive way to exit focus mode without using the back button

3. **Run Calculation Button Always Visible**
   - The large "Run Calculation" button remains visible in both Overview and Step Focus modes
   - Ensures the primary action is always accessible regardless of mode
   - Auto-switches to "Run & Logs" tab after successful job submission (unchanged behavior)

4. **Step YAML Folder Reveal**
   - In Step Focus mode, the Reveal button in `StepDetailPanel` footer opens the step's YAML file directory (e.g., `.../calculations/si-bands/steps/`)
   - Previously opened the calculation root directory; now correctly opens the step-specific folder
   - Falls back to calculation directory if step YAML path cannot be computed
   - Uses Node.js `path` module (available in Electron) to compute `path.dirname(path.join(calculationPath, stepFile))`

### Files Modified

- `gui/src/components/panels/CalculationOverviewTab.tsx` - Added focus mode state and layout switching
- `gui/src/components/panels/CalculationOverviewTab.css` - Added styles for focus mode and compact step list
- `gui/src/components/panels/CalculationListPanel.tsx` - Added `isFocusMode` prop support
- `gui/src/components/panels/StepDetailPanel.tsx` - Added focus mode header/footer
- `gui/src/components/panels/StepDetailPanel.css` - Added focus mode styles

## Future Considerations

- Could add keyboard shortcuts for tab switching
- Could add visual indicator when job completes (without auto-switching)
- Could add "View in Jobs" link from Run & Logs tab to global Jobs page

