# UI Refactor Plan: Move Pseudopotentials to Calculation Overview

## Overview

Move pseudopotential management from step-level (StepDetailPanel) to calculation-level (CalculationDetailPanel/CalculationOverviewTab).

## Phase 2: UI Refactor Plan

### A. Calculation Overview (Expanded Mode)

**Location**: `CalculationDetailPanel` component (in `CalculationListPanel.tsx`)

**Changes**:
1. Add new "Pseudopotentials" section after "Overview" section
2. Display:
   - Element → pseudo filename mapping (read-only table)
   - Source indicator badge (SSSP / Imported / Online)
   - Warnings if any (missing pseudos, etc.)
   - "Edit Pseudopotentials" button → opens modal/dialog with `CommonCardPseudo`
3. Fetch data using: `get_calculation_pseudo_mapping(projectRoot, calculationSelector)`

**Implementation**:
- Add state: `pseudoMapping`, `isLoadingPseudoMapping`, `isEditingPseudos`
- Add useEffect to fetch pseudo mapping when calculation changes
- Add new section in JSX after "Overview" section
- Create modal/dialog component that wraps `CommonCardPseudo` for editing

### B. Calculation Overview (Collapsed Mode)

**Location**: `CalculationDetailPanel` component (when step is selected, in focus mode)

**Changes**:
1. Add compact inline summary in "Overview" section
2. Format: `Structure: Si | Pseudo: Si.pbe-n-rrkjus_psl (SSSP)`
3. Show only if pseudos are configured

**Implementation**:
- Add helper function to format compact pseudo summary
- Display in "Overview" section's detail-grid

### C. Step Detail Panel

**Location**: `StepDetailPanel.tsx`

**Changes**:
1. Remove full `CommonCardPseudo` editor (lines 1323-1445)
2. Replace with read-only reference:
   - Show element → pseudo mapping (read-only)
   - Link: "Edit in Calculation Overview" → scrolls to calculation overview
3. Keep the data fetching (for display), but remove editing capability

**Implementation**:
- Remove `CommonCardPseudo` import and usage
- Add simple read-only display component
- Add link/button to navigate to calculation overview

## File-by-File Change Plan

### 1. `gui/src/components/panels/CalculationListPanel.tsx`

**Changes**:
- Add state for pseudo mapping:
  ```typescript
  const [pseudoMapping, setPseudoMapping] = useState<...>(null);
  const [isLoadingPseudoMapping, setIsLoadingPseudoMapping] = useState(false);
  const [isEditingPseudos, setIsEditingPseudos] = useState(false);
  ```
- Add useEffect to fetch pseudo mapping:
  ```typescript
  useEffect(() => {
    if (calculationForSteps && projectRoot) {
      setIsLoadingPseudoMapping(true);
      qv.getCalculationPseudoMapping(projectRoot, calculationForSteps.slug)
        .then(response => {
          if (response.ok && response.data) {
            setPseudoMapping(response.data);
          }
        })
        .finally(() => setIsLoadingPseudoMapping(false));
    }
  }, [calculationForSteps, projectRoot]);
  ```
- Add "Pseudopotentials" section in JSX (after "Overview" section, before "Calculation Steps")
- Add modal/dialog for editing (wraps `CommonCardPseudo`)

### 2. `gui/src/components/panels/StepDetailPanel.tsx`

**Changes**:
- Remove `CommonCardPseudo` import (line 16)
- Remove pseudo mapping state and loading (lines 206-214)
- Remove pseudo mapping fetch (lines 389-402)
- Remove full `CommonCardPseudo` component (lines 1323-1445)
- Replace with simple read-only display:
  ```typescript
  {/* Pseudopotentials Section - Read-only reference */}
  {module === 'pw' && pseudoMapping && (
    <div className="detail-section">
      <div className="section-header">
        <h3>Pseudopotentials</h3>
        <a href="#calculation-overview" onClick={handleEditInOverview}>
          Edit in Calculation Overview →
        </a>
      </div>
      <div className="pseudo-reference">
        {pseudoMapping.species.map(species => (
          <div key={species}>
            <strong>{species}</strong>: {pseudoMapping.mapping[species] || '—'}
          </div>
        ))}
      </div>
    </div>
  )}
  ```
- Keep `pseudoMapping` state for read-only display (but fetch from calculation-level)

### 3. `gui/src/components/common_cards/CommonCardPseudo.tsx`

**Changes**:
- No changes needed (component is already calculation-level aware)
- Will be reused in CalculationDetailPanel modal

### 4. `gui/src/components/panels/CalculationOverviewTab.tsx`

**Changes**:
- No changes needed (just passes props through)

### 5. CSS Files

**New CSS needed**:
- `.pseudo-reference` styles for read-only display
- Modal/dialog styles for pseudo editor

## Implementation Steps

1. **Step 1**: Add pseudo mapping state and fetch in `CalculationDetailPanel`
2. **Step 2**: Add "Pseudopotentials" section (read-only) in expanded mode
3. **Step 3**: Add compact summary in collapsed mode
4. **Step 4**: Create modal/dialog component for editing
5. **Step 5**: Remove full editor from `StepDetailPanel`
6. **Step 6**: Add read-only reference in `StepDetailPanel`
7. **Step 7**: Test both expanded and collapsed modes
8. **Step 8**: Verify no regressions in step detail panel

## Testing Checklist

- [ ] Pseudopotentials visible in calculation overview (expanded)
- [ ] Compact summary visible in calculation overview (collapsed)
- [ ] "Edit Pseudopotentials" button opens editor
- [ ] Editor saves changes correctly
- [ ] Step detail panel shows read-only reference
- [ ] "Edit in Calculation Overview" link works
- [ ] No duplicate pseudo editors
- [ ] SSSP defaults work correctly
- [ ] Import/download functions work
- [ ] Warnings display correctly

## Notes

- Keep all existing RPC calls (no backend changes needed)
- Maintain backward compatibility (old step-level overrides still work)
- UI should clearly indicate calculation-level is authoritative
- Preserve all existing functionality (import, download, SSSP, etc.)

