# Phase 1.1 Implementation Plan - Enum/Logical Quote-Aware Fixes

## Status Review

### Phase 1 - COMPLETED ✅
1. ✅ **Add Parameter always visible**: `AddParameterPalette` is in Active Parameters header, always visible
2. ✅ **String-only storage**: Python backend enforces `str(value)` in `api.py:3253`
3. ✅ **Unset action**: ActiveParametersPanel uses "Unset" (not "Reset")
4. ✅ **ParameterValueEditor exists**: Supports enum/logical with raw fallback
5. ✅ **Add parameter adds empty string**: New parameters start with empty string placeholder

### Phase 1.1 - NEEDS IMPLEMENTATION ❌
1. ❌ **Enum recognition not quote-aware**: `"'scf'"` doesn't match `"scf"` in enum list
2. ❌ **LOGICAL defaults to raw text**: Should default to toggle/select, not text input
3. ❌ **Empty string forces raw mode**: New enum/logical params show text input instead of dropdown
4. ❌ **CHARACTER enum quoting**: Should write `'scf'` (quoted) for CHARACTER enums, not `scf`

### Phase 2 - NOT STARTED
- K_POINTS structured UI via Python parsing

### Phase 3 - NOT STARTED  
- PSEUDO common card

## Phase 1.1 Implementation Tasks

### Task 1: Create QE String Utilities
**File**: `gui/src/utils/qeStringUtils.ts`
- `normalizeQeScalar(value: string): string` - strips quotes, trims whitespace
- `isQuoted(value: string): boolean` - checks if value is quoted
- `quoteSingle(value: string): string` - wraps in single quotes (simple, no escaping for now)

### Task 2: Fix ParameterValueEditor Enum Recognition
**File**: `gui/src/components/step_parameters/ParameterValueEditor.tsx`
- Use `normalizeQeScalar()` for enum matching
- Default to dropdown mode when metadata indicates enum (even if value is empty)
- For CHARACTER type enums, write quoted values by default
- Preserve original representation when switching modes

### Task 3: Fix ParameterValueEditor LOGICAL Default
**File**: `gui/src/components/step_parameters/ParameterValueEditor.tsx`
- Default to toggle/select mode when metadata indicates LOGICAL (even if value is empty)
- Recognize `.true.`, `.false.`, `true`, `false`, `t`, `f`, `1`, `0` (after normalization)
- Write canonical `.true.` / `.false.` when user selects from dropdown
- Show tri-state select for empty: `[-- Not set --, .true., .false.]`

### Task 4: Ensure New Parameters Use Metadata-First Controls
**File**: `gui/src/components/step_parameters/ParameterValueEditor.tsx`
- When value is empty string and metadata indicates enum/logical, show dropdown/toggle
- Only fallback to raw mode if value is non-empty and doesn't match expected values

## Files to Modify

1. **NEW**: `gui/src/utils/qeStringUtils.ts` - QE string normalization utilities
2. **MODIFY**: `gui/src/components/step_parameters/ParameterValueEditor.tsx` - Fix enum/logical recognition and defaults

## Acceptance Criteria

1. ✅ Existing `calculation='scf'` stored as `"'scf'"` displays as enum dropdown with "scf" selected
2. ✅ Switching dropdown from scf→nscf writes YAML string `"'nscf'"` (with quotes)
3. ✅ New LOGICAL param `tprnfor` immediately shows logical control (not raw text)
4. ✅ Selecting true writes `".true."` string to YAML
5. ✅ Selecting false writes `".false."` string to YAML
6. ✅ Clicking ✏️ switches to raw text and preserves current literal string
7. ✅ Custom values not in enum list stay in raw mode
8. ✅ Empty string placeholder doesn't force raw mode when metadata is enum/logical

