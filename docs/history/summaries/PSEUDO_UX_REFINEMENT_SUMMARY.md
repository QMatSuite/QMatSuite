# Pseudopotential UX Refinement Summary

## Overview

Refined pseudopotential UX to support multiple sources (INTERNAL, SSSP libraries, project) and fix resolution logic to check all sources, not just project/pseudo.

## Changes Made

### Backend (src/qmatsuite/api.py)

**Extended `get_calculation_pseudo_mapping` API:**

1. **Added INTERNAL source support:**
   - Checks `resources/pseudo` directory (via `get_system_pseudo_dir()`)
   - Lists all UPF files in INTERNAL as candidates

2. **Enhanced SSSP library detection:**
   - Checks SSSP libraries in `temp/pseudo/sssp/1.3.0/{precision|efficiency}/library`
   - Reads `cutoffs.json` to build element → filename mappings
   - Lists all UPF files from installed libraries

3. **New API fields:**
   - `installed_sources`: `{internal: bool, sssp_precision: bool, sssp_efficiency: bool}`
   - `candidates_by_element`: `{element: [{filename, source, path?}]}` - all candidates from all sources
   - `resolved_by_element`: `{element: {filename, source, resolved, in_project}}` - resolution status

4. **Fixed resolution logic:**
   - Resolution order: INTERNAL → SSSP Precision → SSSP Efficiency → Project
   - `resolved=true` if pseudo exists in ANY source (not just project)
   - `in_project` flag indicates if file is already in project/pseudo

5. **Fixed warnings:**
   - Only warns if pseudo is truly unresolved (not found in any source)
   - Removed "Not in project" warning when pseudo is resolvable from INTERNAL/libs

### Frontend (gui/src/components/common_cards/CommonCardPseudo.tsx)

1. **Added INTERNAL as library option:**
   - Library selector now has: "Internal", "SSSP Precision", "SSSP Efficiency"
   - INTERNAL is always available (default)
   - SSSP options disabled if not installed (but selector still works)

2. **Improved empty state:**
   - Shows "SSSP libraries not installed" as note, not blocking
   - User can still select INTERNAL or import files

3. **Enhanced dropdown with source grouping:**
   - Dropdown shows candidates grouped by source (optgroups)
   - Labels: "Internal", "SSSP Precision", "SSSP Efficiency", "Project"
   - All candidates from all sources shown for each element

4. **Source badges:**
   - Shows resolved source badge: "Internal", "SSSP Precision", etc.
   - Shows "(will copy)" hint if resolved but not yet in project
   - Only shows warning if truly unresolved

5. **Fixed auto-preselect:**
   - Uses `candidates_by_element` to find candidates from preferred library
   - INTERNAL library: selects first INTERNAL candidate
   - SSSP libraries: uses SSSP defaults from cutoffs.json
   - Falls back to INTERNAL if SSSP not available

6. **Reduced UI clutter:**
   - Removed long explanatory paragraphs
   - Minimal info text: "Pseudopotentials will be copied into project/pseudo/ when the calculation runs"
   - Clean, focused interface

### Frontend (gui/src/components/panels/CalculationListPanel.tsx)

1. **Updated pseudo display:**
   - Expanded mode: Table shows Element | Filename | Source badge
   - Collapsed mode: Compact summary with source badges
   - Uses `resolved_by_element` for accurate source display

2. **Source badges in read-only view:**
   - Shows source badge (Internal/SSSP Precision/SSSP Efficiency/Project)
   - Shows "(will copy)" hint if not in project yet
   - Only shows warning if unresolved

### Styling (gui/src/components/common_cards/CommonCardPseudo.css)

1. **Dark theme compatibility:**
   - Removed hardcoded white backgrounds
   - Uses CSS variables: `var(--bg-input)`, `var(--text-primary)`
   - Dropdowns and inputs match existing dark theme

2. **Source badge styles:**
   - `.pseudo-source-badge--internal`: Info color (blue)
   - `.pseudo-source-badge--sssp-precision/efficiency`: Accent color
   - `.pseudo-source-badge--project`: Tertiary background
   - Compact variant for collapsed mode

3. **Improved contrast:**
   - All inputs use theme-aware colors
   - Better visibility in dark mode

### TypeScript Types (gui/src/types/qms.ts)

1. **Extended `CalculationPseudoMappingResult`:**
   - Added `installed_sources`
   - Added `candidates_by_element`
   - Added `resolved_by_element`

## Key Improvements

### 1. INTERNAL Source Support
- ✅ INTERNAL always available (resources/pseudo)
- ✅ Default library option when SSSP not installed
- ✅ Demo projects can reference internal pseudos
- ✅ Preselects correctly when filename matches INTERNAL

### 2. Correct Resolution Logic
- ✅ Checks all sources: INTERNAL → SSSP → Project
- ✅ `resolved=true` if found in ANY source
- ✅ Warnings only when truly unresolved
- ✅ Shows source badge for resolved pseudos

### 3. Better Empty State
- ✅ No blank white boxes
- ✅ Library selector always functional
- ✅ Clear note about SSSP installation status
- ✅ User can still use INTERNAL or import

### 4. Enhanced Dropdown
- ✅ Shows all candidates from all sources
- ✅ Grouped by source (optgroups)
- ✅ Clear source labels
- ✅ Preselects existing mappings correctly

### 5. Cleaner UI
- ✅ Removed verbose explanations
- ✅ Minimal, focused interface
- ✅ Dark theme compatible
- ✅ Better visual hierarchy

## Testing Checklist

✅ No SSSP installed: editor shows INTERNAL, no blank selector, can pick internal Si pseudo
✅ Demo project referencing internal pseudo: editor preselects and shows "Internal" badge, no warning
✅ SSSP installed: candidates include internal + SSSP; source badges correct
✅ Only warns when filename can't be found in internal/libs/project
✅ Runtime still copies required pseudos into project/pseudo before execution
✅ QE input uses ../pseudo (runtime enforced, not UI)

## Files Modified

1. `src/qmatsuite/api.py` - Extended API with candidates and resolution
2. `gui/src/types/qms.ts` - Extended TypeScript types
3. `gui/src/components/common_cards/CommonCardPseudo.tsx` - Added INTERNAL, source badges, improved dropdown
4. `gui/src/components/common_cards/CommonCardPseudo.css` - Dark theme fixes, source badge styles
5. `gui/src/components/panels/CalculationListPanel.tsx` - Updated display to use new API fields

## Architecture Decisions

### Resolution Order
1. INTERNAL (resources/pseudo) - always available
2. SSSP Precision (if installed)
3. SSSP Efficiency (if installed)
4. Project (project/pseudo)

### Source Priority for Candidates
When same filename exists in multiple sources, prefer: INTERNAL > SSSP > Project

### Warnings
- Only show warning if pseudo is truly unresolved (not in any source)
- Show source badge if resolved (even if not in project yet)
- Show "(will copy)" hint if resolved but not in project

### Library Preference
- Default: INTERNAL (always available)
- SSSP options disabled if not installed (but selector still functional)
- User can switch between libraries to see different candidates

