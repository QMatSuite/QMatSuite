# Pseudo Selection V2: sha256-keyed UI Alignment + Restore/Write Semantics

**Date**: 2025-01-XX  
**Status**: Implementation Complete  
**PR**: [To be created]

## Overview

This document describes the refactor of Pseudo Selection V2 to align with the final agreed semantics: **sha256-keyed selection** (not sha_token-grouped) with **filename-first** default priority.

## Final Semantics (MUST ALIGN)

### 1. Dropdown Selection Key is SHA256 (NOT sha_token)

**Implementation:**
- `gui/src/components/common_cards/CommonCardPseudo.tsx`: Uses `selectedSha256ByElement` state (sha256 as primary selection key)
- `src/qmatsuite/core/pseudo_options.py`: Returns `PseudoVariant[]` keyed by sha256 (not sha_token-grouped)

**Manual Verification:**
- Open a calculation with pseudo selections
- Check browser console: selection state should show sha256 values, not sha_token
- Dropdown value attribute should be sha256

**Tests:**
- `tests/unit/test_pseudo_options_shatoken_grouping.py::test_sha256_keyed_variants` - Verifies separate variants per sha256

### 2. Only 3 Sources Exist

**Implementation:**
- `src/qmatsuite/core/pseudo_options.py`: Scans only:
  1. `project_root/pseudo` (project)
  2. `repo/resources/pseudo` (internal)
  3. Installed archives from `MANIFEST_PSEUDO_SEED.json` (lib)

**Manual Verification:**
- Check dropdown options: chips should show only "Project", "Internal", or library labels (SSSP, etc.)
- No fourth source should appear

**Tests:**
- `tests/unit/test_pseudo_no_repo_root.py` - Ensures no `repo_root/pseudo` usage

### 3. QE Runtime Only Reads from project/pseudo

**Implementation:**
- `src/qmatsuite/core/engines/qe_calculation.py`: Sets `ESPRESSO_PSEUDO = project_root / "pseudo"`
- `src/qmatsuite/calculation/input_runner.py`: Points QE input to `project_root / "pseudo"`

**Manual Verification:**
- Run a calculation, check QE input file: `pseudo_dir` should point to `project/pseudo`
- Check environment: `ESPRESSO_PSEUDO` should be `project/pseudo` (not `working_dir/pseudo`)

**Tests:**
- `tests/unit/test_pseudo_runtime_step0.py::test_step0_noop_project_source` - Verifies project source handling

### 4. UI Restores Selection WITHOUT Writing calc.yml

**Implementation:**
- `gui/src/components/common_cards/CommonCardPseudo.tsx::restoreSelectionFromCalc()`:
  - Only calls `setLocalMapping`, `setLocalMappingSha256`, `setLocalMappingShaToken`, `setSelectedSha256ByElement`
  - Does NOT call `onUpdate()` (which would write calc.yml)
  - Uses `hasRestoredRef` to prevent multiple restores

**Manual Verification:**
- Open a calculation, check calc.yml modification time: should NOT change on panel open
- Check browser console: no "User selection changed" log on initial load

**Tests:**
- [TODO] Add test that mocks `onUpdate` and verifies it's not called during restore

### 5. User Change Writes Triplet Together + Debug Log

**Implementation:**
- `gui/src/components/common_cards/CommonCardPseudo.tsx::handlePseudoChange()`:
  - Calls `onUpdate()` with triplet: `{filename, sha256, sha_token}`
  - Logs debug line: `[CommonCardPseudo] User selection changed: element=..., filename=..., sha256=..., sha_token=..., source=...`

**Manual Verification:**
- Change a selection in dropdown
- Check browser console: should see exactly one debug log line per change
- Check calc.yml: should have `pseudo_sha256`, `pseudo_sha_token`, `pseudo_basename` all updated together

**Tests:**
- [TODO] Add test that verifies `onUpdate` is called with triplet and debug log appears

### 6. Selection Restore Algorithm

**Implementation:**
- `gui/src/components/common_cards/CommonCardPseudo.tsx::restoreSelectionFromCalc()`:
  - **Primary**: Match by `pseudo_sha256` (if multiple matches, prefer same basename, then stable tie-break: project > internal > lib)
  - **Fallback**: Match by `pseudo_filename` (project > internal > lib)
  - **If not found**: Empty selection + console warning

**Manual Verification:**
- Create calc with `pseudo_sha256` set, open panel: should restore by sha256
- Create calc with only `pseudopot` filename, open panel: should restore by filename
- Create calc with invalid sha256/filename, open panel: should show empty selection + warning

**Tests:**
- [TODO] Add test for restore-by-sha256, restore-by-filename, and not-found cases

### 7. Token-Match Edge Case

**Implementation:**
- `src/qmatsuite/core/pseudo_options.py`: When project has same basename with token-match but sha256 differs:
  - Creates **separate variants** (one for project sha256, one for internal/lib sha256)
  - Adds `token_match_warnings` to both variants
- `gui/src/components/common_cards/CommonCardPseudo.tsx`: Displays warnings inline

**Manual Verification:**
- Create `project/pseudo/Si.upf` with content "Si UPF\n"
- Ensure internal has `Si.upf` with content "Si    UPF\n" (same token, different sha256)
- Open dropdown: should see two separate options for Si
- Both should show token-match warnings

**Tests:**
- `tests/unit/test_pseudo_options_shatoken_grouping.py::test_token_match_warnings` - Verifies separate variants and warnings

### 8. Step0 Runtime Semantics

**Implementation:**
- `src/qmatsuite/core/pseudo_runtime.py::prepare_project_pseudos_for_run()`:
  - If `source_kind == "project"` and sha256 matches: **noop** (just refresh calc records)
  - If `source_kind in ("internal", "lib")`:
    - Same sha256: noop
    - Same sha_token, different sha256: **overwrite** (no rename)
    - Different sha_token: **rename existing** + copy new

**Manual Verification:**
- Select project-local pseudo, run: Step0 should be noop (check logs)
- Select internal/lib with token-match but sha256 differs, run: Step0 should overwrite
- Select internal/lib with token-mismatch, run: Step0 should rename existing

**Tests:**
- `tests/unit/test_pseudo_runtime_step0.py::test_step0_noop_project_source` - Verifies project source = noop
- `tests/unit/test_pseudo_runtime_step0.py::test_step0_overwrite_same_token_different_sha256` - Verifies overwrite
- `tests/unit/test_pseudo_runtime_step0.py::test_step0_rename_different_token_same_basename` - Verifies rename

## Files Changed

### Backend
- `src/qmatsuite/core/pseudo_options.py`: Refactored to sha256-keyed `PseudoVariant` (not sha_token-grouped)
- `src/qmatsuite/core/pseudo_runtime.py`: Updated project source detection and Step0 logic
- `src/qmatsuite/api.py`: Removed `use_sha_token_grouping` flag
- `src/qmatsuite/daemon/server.py`: Updated to use sha256-keyed options
- `src/qmatsuite/calculation/runner.py`: Updated `refresh_calc_pseudo_records_after_step0` call

### Frontend
- `gui/src/types/qms.ts`: Updated `PseudoVariant` interface to match backend
- `gui/src/components/common_cards/CommonCardPseudo.tsx`: Complete refactor to sha256-keyed selection

### Tests
- `tests/unit/test_pseudo_options_shatoken_grouping.py`: Updated to test sha256-keyed variants (renamed from sha_token grouping)
- `tests/unit/test_pseudo_runtime_step0.py`: Added test for project source = noop

### Documentation
- `docs/PSEUDO_SELECTION_V2_SHA256_KEYED_ALIGNMENT.md`: This file

## What Changed from Previous Implementation

1. **UI selection key**: Changed from `sha_token` to `sha256`
2. **Options structure**: Changed from sha_token-grouped to sha256-keyed variants
3. **Default selection priority**: project filename → internal filename → lib (by filename, then sha256)
4. **Token-match edge case**: Separate entries (don't merge) with warnings
5. **Project source selection**: Step0 does noop (just refresh) instead of overwrite
6. **Restore logic**: Match by sha256 first, then fallback by filename (does NOT write calc.yml)
7. **Write logic**: Writes triplet together on user change (with debug log)

## Remaining Work

1. **Tests**: Add UI-level tests for restore/write semantics (mock `onUpdate`, verify no calls during restore)
2. **Documentation**: Update other docs that reference sha_token-first selection

## Acceptance Checklist

- [x] UI selection keyed by sha256 (not sha_token)
- [x] Only 3 sources exist (project, internal, lib)
- [x] QE runtime reads only from project/pseudo
- [x] UI restore does NOT write calc.yml
- [x] User change writes triplet together + debug log
- [x] Restore algorithm: sha256 first, then filename fallback
- [x] Token-match edge case: separate entries + warnings
- [x] Step0: project source = noop, token-match = overwrite, token-mismatch = rename
- [ ] All tests pass
- [ ] Manual verification complete

