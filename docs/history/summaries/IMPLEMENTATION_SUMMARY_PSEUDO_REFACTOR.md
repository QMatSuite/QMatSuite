# Implementation Summary: Pseudopotential UI Refactor

## Overview

Moved pseudopotential management from step-level to calculation-level, making it visible in the Calculation Overview panel instead of hidden inside individual step panels.

## Changes Made

### 1. CalculationDetailPanel (`CalculationListPanel.tsx`)

**Added:**
- Pseudopotential state management (calculation-level)
- Fetch logic using `get_calculation_pseudo_mapping` RPC
- Pseudopotentials section in expanded mode (full table with element → filename + source badges)
- Compact pseudo summary in collapsed mode (one-liner in Overview section)
- Edit Pseudopotentials modal/dialog (reuses `CommonCardPseudo` component)
- Update logic using `update_calculation_species_map` RPC

**Key Features:**
- Expanded mode: Full table showing all elements, pseudopotential filenames, and source indicators (SSSP/Imported)
- Collapsed mode: Compact inline summary in Overview section (e.g., "Si | pseudos: Si.pbe... (SSSP)")
- Edit button opens modal with full `CommonCardPseudo` editor
- All import/download/SSSP functionality preserved

### 2. StepDetailPanel (`StepDetailPanel.tsx`)

**Removed:**
- Full `CommonCardPseudo` editor component
- All editing capabilities for pseudopotentials

**Added:**
- Read-only pseudopotential reference display
- "Edit in Calculation Overview" button that navigates back to overview
- Simple list showing element → filename mapping (read-only)

**Key Features:**
- Shows calculation-level pseudopotential mapping (read-only)
- Clear indication that pseudos are managed at calculation level
- Direct navigation to calculation overview for editing

### 3. CSS Styling (`CalculationListPanel.css`)

**Added:**
- `.pseudo-source-badge` - Source indicator badges (SSSP/Imported)
- `.pseudo-mapping-display` - Full table display in expanded mode
- `.pseudo-table` - Styled table for element → filename mapping
- `.pseudo-edit-modal-overlay` - Modal overlay for editing
- `.pseudo-edit-modal` - Modal container
- `.pseudo-reference` - Read-only reference display in step detail
- `.pseudo-reference-list` - List of pseudo mappings
- `.pseudo-warnings` - Warning display for missing/invalid pseudos

## Architecture Decisions

### State Ownership
- **Calculation-level**: Pseudopotential state lives in `CalculationDetailPanel`
- **Step-level**: StepDetailPanel only reads calculation-level state (no local editing)

### RPC Usage
- **Fetch**: `get_calculation_pseudo_mapping(projectRoot, calculationSelector)` - Gets calculation-level `species_map`
- **Update**: `update_calculation_species_map(projectRoot, calculationSelector, speciesMap)` - Updates calculation-level `species_map`
- **No step-level RPCs**: Removed `get_pseudo_mapping` and `set_pseudo_mapping` usage from StepDetailPanel

### UI Hierarchy
1. **Calculation Overview (Expanded)**: Full pseudopotential management
2. **Calculation Overview (Collapsed)**: Compact summary visible
3. **Step Detail**: Read-only reference with navigation link

## Testing Checklist

✅ Pseudopotentials visible in calculation overview (expanded mode)
✅ Compact summary visible in calculation overview (collapsed mode)
✅ "Edit Pseudopotentials" button opens modal
✅ Editor saves changes correctly via calculation-level RPC
✅ Step detail panel shows read-only reference
✅ "Edit in Calculation Overview" link navigates correctly
✅ No duplicate pseudo editors
✅ SSSP defaults work correctly
✅ Import/download functions work
✅ Warnings display correctly
✅ `pseudo_dir` is never shown in UI (runtime enforces `../pseudo`)

## Edge Cases Handled

### Step-Level Overrides
- **Decision**: Keep step-level `species_overrides` read-only for now
- **Rationale**: Calculation-level `species_map` is authoritative; step-level overrides can be added later if needed
- **Implementation**: StepDetailPanel only displays calculation-level mapping, no editing

### Navigation
- **Decision**: "Edit in Calculation Overview" button calls `onClose()` to exit focus mode
- **Rationale**: This returns user to calculation overview where they can edit pseudos
- **Implementation**: Button in StepDetailPanel calls parent's `onClose` callback

### Modal State
- **Decision**: Modal state (`isEditingPseudos`) lives in CalculationDetailPanel
- **Rationale**: Keeps editing logic centralized in calculation panel
- **Implementation**: Modal opens/closes via state in CalculationDetailPanel

## Files Modified

1. `gui/src/components/panels/CalculationListPanel.tsx` - Added pseudo management
2. `gui/src/components/panels/StepDetailPanel.tsx` - Removed editor, added read-only reference
3. `gui/src/components/panels/CalculationListPanel.css` - Added pseudo styling

## Files Not Modified (But Used)

1. `gui/src/components/common_cards/CommonCardPseudo.tsx` - Reused in modal (no changes needed)
2. `gui/src/hooks/useQMSClient.ts` - RPC methods already existed (no changes needed)
3. `src/qmatsuite/api.py` - Backend RPCs already existed (no changes needed)

## Backward Compatibility

- ✅ All existing RPC calls preserved
- ✅ Calculation-level `species_map` is authoritative (existing behavior)
- ✅ Step-level `species_overrides` still work (just not editable in UI)
- ✅ Runtime still enforces `../pseudo` (no UI changes to this)

## Next Steps (If Needed)

1. **Step-level overrides**: If needed later, can add per-step override UI
2. **Bulk operations**: Could add "Apply to all calculations" functionality
3. **Validation**: Could add more validation for pseudo file existence before runs

