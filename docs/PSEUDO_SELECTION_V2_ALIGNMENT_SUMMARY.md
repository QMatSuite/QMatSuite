# Pseudo Selection V2: Full Constitution Alignment Summary

**Date**: 2025-01-XX  
**Status**: ✅ Complete

## Overview

This document summarizes the complete alignment of the pseudo selection implementation with `CONSTITUTION_ZH.md` Chapter 7, including the newly added tie-break rules for deterministic selection.

## Constitution Rules → Implementation Status

### ✅ Rule 7.4: sha256 vs sha_token semantics
- **Constitution**: UI dropdown selection key is sha256 (not sha_token). sha_token only for conflict handling, warnings, cross-calc updates.
- **Implementation**: 
  - `CommonCardPseudo.tsx`: Uses `selectedSha256ByElement` state
  - `pseudo_options.py`: Returns `PseudoVariant[]` keyed by sha256
  - `qv.ts`: `PseudoVariant` interface has `sha256` as primary field

### ✅ Rule 7.5.1: UI display/selectable options
- **Constitution**: Options must correspond to filesystem-real UPF files (project/internal/installed-lib only). No disabled entries for not-installed libs.
- **Implementation**: 
  - `CommonCardPseudo.tsx`: Filters to `realVariants` (filesystem-real only)
  - `pseudo_options.py`: Only includes installed lib sources

### ✅ Rule 7.5.1.1: Deterministic tie-break rules (NEW)
- **Constitution**: When sha256 matches multiple candidates:
  1. If calc.yml has pseudo_filename, prefer filename match
  2. Then source priority: project → internal → lib
  3. If multiple libs, sort by library/asset name lexicographically
  4. If same lib, sort by basename lexicographically
- **Implementation**: 
  - `CommonCardPseudo.tsx::restoreSelectionFromCalc()`: Full tie-break implementation
  - Test: `test_tie_break_multiple_libs()` verifies structure support

### ✅ Rule 7.5.2: Restore selection (no YAML write)
- **Constitution**: Restore by sha256 first (with tie-break), then fallback by filename. Must NOT write calc.yml.
- **Implementation**: 
  - `restoreSelectionFromCalc()`: Only calls `setLocalMapping*` (no `onUpdate`)
  - Uses `hasRestoredRef` to prevent multiple restores

### ✅ Rule 7.5.3: User selection change (write triplet)
- **Constitution**: Only on explicit user change, write triplet (filename+sha256+sha_token) together. Emit debug log.
- **Implementation**: 
  - `handlePseudoChange()`: Calls `onUpdate()` with triplet
  - Emits debug log: `[CommonCardPseudo] User selection changed: ...`

### ✅ Rule 7.5.4: Token-match edge case
- **Constitution**: If project basename and external have same sha_token but different sha256 → separate entries (no merge). Show token-match hints.
- **Implementation**: 
  - `pseudo_options.py`: Creates separate variants, adds `token_match_warnings`
  - `CommonCardPseudo.tsx`: Displays token-match warnings inline

### ✅ Rule 7.7.1: Step0 project source = noop
- **Constitution**: If user selects project/pseudo file, Step0 must noop (no overwrite/rename), but refresh calc sha256/sha_token.
- **Implementation**: 
  - `pseudo_runtime.py::prepare_project_pseudos_for_run()`: Checks `source_kind == "project"` and does noop
  - Still refreshes calc records

### ✅ Rule 7.7.2: Step0 external selection collision rules
- **Constitution**: 
  - same sha256 → noop
  - same sha_token, different sha256 → overwrite
  - different sha_token → rename_existing + update calcs by sha_token
- **Implementation**: 
  - `prepare_project_pseudos_for_run()`: Implements all three collision rules correctly

### ✅ Rule 7.7.3: Stale sha256 allowed
- **Constitution**: Calc can have stale sha256 (sha_token unchanged). Only sha_token change indicates physical change.
- **Implementation**: 
  - `pseudo_runtime.py`: Handles stale sha256 correctly
  - `runner.py`: Refreshes after Step0

## Files Changed

1. **CONSTITUTION_ZH.md**:
   - Added 7.5.1.1: Deterministic tie-break rules (lines 178-186)
   - Updated 7.5.2: Clarified tie-break usage (line 180)

2. **gui/src/components/common_cards/CommonCardPseudo.tsx**:
   - Updated `restoreSelectionFromCalc()`: Full tie-break implementation (lines 372-424)
   - Updated fallback filename matching: Same tie-break for lib matches (lines 419-424)

3. **tests/unit/test_pseudo_options_shatoken_grouping.py**:
   - Added `test_tie_break_multiple_libs()`: Verifies tie-break structure support

4. **docs/PSEUDO_SELECTION_V2_IMPLEMENTATION_SUMMARY.md**:
   - Updated "Default Selection Priority" section to include tie-break rules

5. **docs/PSEUDO_SELECTION_V2_ALIGNMENT_CHECKLIST.md**:
   - Created alignment checklist mapping constitution rules to implementation

## Verification

### Manual Verification Steps

1. **Tie-Break Rules**:
   - Open a calculation with multiple lib sources for same sha256
   - Verify selection is deterministic (same selection on reload)
   - Verify selection respects filename match, then source priority, then lexicographic sort

2. **Restore Selection (No Write)**:
   - Open a calculation with existing `pseudo_sha256` in `calc.yml`
   - Verify selection restores correctly
   - Verify no `calc.yml` write occurs during restore (check file mtime)

3. **User Selection Change (Write Triplet)**:
   - Change selection in UI
   - Verify `calc.yml` is updated with triplet (filename, sha256, sha_token)
   - Verify debug log appears in console

4. **Token-Match Warnings**:
   - Create project file with same basename but different sha256 (same sha_token) as external
   - Verify separate dropdown entries appear
   - Verify token-match warnings shown

5. **Step0 Project Source Noop**:
   - Select project-local pseudo
   - Run calculation
   - Verify Step0 does noop (no file change)
   - Verify calc records refreshed

6. **Step0 Collision Rules**:
   - Select external pseudo with same sha_token but different sha256 as existing project file
   - Run calculation
   - Verify overwrite occurs
   - Select external pseudo with different sha_token
   - Run calculation
   - Verify rename occurs and other calcs updated

## Test Coverage

- ✅ `test_sha256_keyed_variants`: Verifies sha256-keyed variants (not sha_token grouped)
- ✅ `test_token_match_warnings`: Verifies token-match warnings
- ✅ `test_tie_break_multiple_libs`: Verifies tie-break structure support
- ✅ `test_step0_noop_project_source`: Verifies project source noop
- ✅ `test_step0_overwrite_same_token_different_sha256`: Verifies overwrite rule
- ✅ `test_step0_rename_different_token_same_basename`: Verifies rename rule
- ✅ `test_calc_refresh_after_step0`: Verifies calc record refresh

## Remaining Gaps

**None**. All constitution rules are implemented and aligned.

## Next Steps

1. Create PR: "Align pseudo selection + Step0 with CONSTITUTION_ZH.md (sha256-keyed, deterministic restore, token-match edge cases)"
2. Include this summary in PR description
3. Request review focusing on:
   - Tie-break determinism
   - Restore selection behavior (no YAML write)
   - Step0 collision rules
   - Token-match edge cases

