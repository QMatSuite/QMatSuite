# Pseudo Selection v2 - Implementation Summary

## Overview

Implemented "Pseudo Selection v2" with **sha256-keyed selection** (filename-first, constitution-compliant). The system uses vendored manifest/index data and operates offline at runtime.

**Key Change (2025-01-XX):** Refactored from sha_token-grouped to sha256-keyed variants to align with final semantics:
- UI selection key = sha256 (not sha_token)
- Default selection priority: project filename → internal filename → lib
- sha_token used only for warnings and collision detection
- Token-match edge case: separate entries (don't merge) with warnings
- Step0: project source = noop (just refresh), token-match = overwrite, token-mismatch = rename

## Completed Phases

### Phase A: Code Mapping ✓
- Documented current implementation in `docs/PSEUDO_SELECTION_V2_PHASE0.md`
- Identified all files and functions to modify
- Created implementation plan in `docs/PSEUDO_SELECTION_V2_PHASE1_PLAN.md`

### Phase B: Generic Archive Management ✓
**Backend:**
- Created `src/qmatsuite/core/pseudo_installs.py` with:
  - `load_manifest_archives()` - Loads from vendored MANIFEST_PSEUDO_SEED.json
  - `check_archives_status()` - Checks install status by SHA256
  - `install_archive()` - Downloads and installs archives with verification
  - `is_archive_installed()` - Verifies installation by SHA256
  - `ArchiveStatus` dataclass - Archive metadata with install status

**RPC Handlers:**
- Added `list_pseudo_archives_status` RPC in `src/qmatsuite/daemon/server.py`
- Added `install_pseudo_archive` RPC in `src/qmatsuite/daemon/server.py`

**Settings UI:**
- ✅ Created `gui/src/components/settings/PseudoArchivesPanel.tsx` - Generic archives table
- ✅ Integrated into SettingsPanel - Renders in Settings → Pseudopotentials section
- ✅ Shows all archives grouped by library with install status
- ✅ Install/Reinstall/Verify actions with progress indicators

### Phase C: Pseudo Options API ✓
**Backend:**
- Created `src/qmatsuite/core/pseudo_options.py` with:
  - `get_pseudo_options_for_elements()` - Generates deduplicated options per element
  - `PseudoOption` dataclass - Option with sha256, basename, sources, availability
  - `PseudoSource` dataclass - Source chip with kind, label, installed status

**API Integration:**
- Added `get_pseudo_options_for_elements()` to `src/qmatsuite/api.py`
- Added `get_pseudo_options_for_calculation` RPC handler
- Added TypeScript types in `gui/src/types/qms.ts`
- Added hook method in `gui/src/hooks/useQMSClient.ts`

**Features:**
- SHA256-based deduplication (primary identity)
- Multiple library chips per option (from occurrences)
- Installed status per source (blue=installed, gray=available)
- Project/Internal chip injection (adds chips to existing options)
- Name collision handling (append sha256 prefix when needed)

### Phase D: UI Replacement ✓
**Component Updates:**
- Modified `gui/src/components/common_cards/CommonCardPseudo.tsx`:
  - Removed Library dropdown when using new API
  - Added single dropdown per element showing basename + source chips
  - Handles name collisions (appends sha256[:8] when needed)
  - Backward compatible: falls back to old API if calculation not provided

**Styling:**
- Added CSS for source chips in `gui/src/components/common_cards/CommonCardPseudo.css`:
  - `.common-card-pseudo__source-chips` - Container for chips
  - `.common-card-pseudo__source-chip--installed` - Blue chip (installed)
  - `.common-card-pseudo__source-chip--available` - Gray chip (not installed)

**Integration:**
- Updated `gui/src/components/panels/CalculationListPanel.tsx` to pass `calculation` prop

### Phase E: Unit Tests ✓
- Created `tests/unit/test_pseudo_options.py` with tests for:
  - SHA256 deduplication
  - Name collision handling (same basename, different sha256)
  - Library chips from occurrences
  - Installed status reflection
  - Project/Internal chip injection
  - JSON serialization stability

## Key Design Decisions

1. **SHA256 as Primary Selection Key**: The UI selection is keyed by `sha256` (strict bytes identity), not `sha_token`. This ensures deterministic selection and reproducibility.
2. **sha_token for Warnings Only**: `sha_token` is used only for:
   - Physical equivalence detection (warnings when files have same token but different bytes)
   - Step0 collision resolution (overwrite vs rename decisions)
   - Cross-calculation reference updates
3. **Default Selection Priority with Tie-Break**: When restoring selection from `calc.yml`, priority is:
   - First: Match by `pseudo_sha256` (exact match)
     - If multiple candidates match same sha256, apply tie-break:
       1. If `calc.yml` has `pseudo_filename`, prefer filename match
       2. Then source priority: project → internal → lib
       3. If multiple libs, sort by library/asset name lexicographically
       4. If same lib, sort by basename lexicographically
   - Fallback: Match by `pseudo_filename` in order: project → internal → installed lib (with same tie-break for libs)
4. **Three Sources Only**: Only three pseudo sources exist:
   - `lib`: Installed libraries under `temp/pseudo/...`
   - `internal`: `repo/resources/pseudo`
   - `project`: `project_root/pseudo`

### SHA256 as Primary Identity
- Options are deduplicated by SHA256, not filename
- Same content (same sha256) = one option with multiple source chips
- Different content (different sha256) = separate options, even with same basename

### Source Chips
- **Project**: Always installed (blue), from `project_root/pseudo/`
- **Internal**: Always installed (blue), from `resources/pseudo/`
- **Library**: Installed status checked via `check_archive_status()` - only blue if `installed AND NOT corrupt`
- **Corrupt**: Archives with SHA256 mismatch are marked as `installed=false` and `corrupt=true` (gray chip with warning)

### Name Collision Handling
- If multiple options have same `display_basename`, append `· <sha256[:8]>` in dropdown
- Selected value still uses full basename (for backward compatibility)

### Backward Compatibility
- Component falls back to old API if `calculation` prop not provided
- Old API still works (Library dropdown + file dropdown)
- New API only used when both `projectRoot` and `calculation` are provided

## Files Modified

### Backend
- `src/qmatsuite/core/pseudo_installs.py` (NEW)
- `src/qmatsuite/core/pseudo_options.py` (NEW)
- `src/qmatsuite/api.py` (added `get_pseudo_options_for_elements`)
- `src/qmatsuite/daemon/server.py` (added 3 RPC handlers)

### Frontend
- `gui/src/types/qms.ts` (added RPC types, ArchiveStatus, ArchiveInstallResult)
- `gui/src/hooks/useQMSClient.ts` (added hook methods: getPseudoOptionsForCalculation, materializePseudoFile, listPseudoArchivesStatus, installPseudoArchive)
- `gui/src/components/common_cards/CommonCardPseudo.tsx` (major refactor + auto-refresh listener)
- `gui/src/components/common_cards/CommonCardPseudo.css` (added chip styles)
- `gui/src/components/panels/CalculationListPanel.tsx` (pass calculation prop)
- `gui/src/components/settings/PseudoArchivesPanel.tsx` (NEW - archives management UI)
- `gui/src/components/settings/PseudoArchivesPanel.css` (NEW - table styling)
- `gui/src/components/panels/SettingsPanel.tsx` (integrated PseudoArchivesPanel)

### Tests
- `tests/unit/test_pseudo_options.py` (NEW)

### Documentation
- `docs/PSEUDO_SELECTION_V2_PHASE0.md` (NEW)
- `docs/PSEUDO_SELECTION_V2_PHASE1_PLAN.md` (NEW)
- `docs/PSEUDO_SELECTION_V2_IMPLEMENTATION_SUMMARY.md` (NEW)

## Integration & UX Polish ✓

### Settings Integration
- ✅ `PseudoArchivesPanel` rendered in Settings → Pseudopotentials section
- ✅ Archives grouped by library_name + library_version
- ✅ Status badges: Installed (✓), Not installed (⬜), Corrupt (⚠)
- ✅ Install/Reinstall/Verify buttons with progress indicators

### Auto-Refresh Flow
- ✅ Global event `pseudo-archives-changed` emitted after successful install
- ✅ `CommonCardPseudo` listens for event and refreshes options automatically
- ✅ Chips update from gray to blue without page reload

### Safety Rules
- ✅ Corrupt archives never used: `materialize_pseudo_file` checks `installed AND NOT corrupt`
- ✅ Options API marks corrupt archives as `installed=false` even if file exists
- ✅ Clear error messages when corrupt archive detected: "Archive exists but failed SHA256 verification. Reinstall from Settings → Pseudopotentials."

### Error UX
- ✅ Validation in `handleApply`: Checks all selected options have installed sources
- ✅ Error message shows required archive names and library labels
- ✅ Hints user to "Go to Settings → Pseudopotentials to install"

## Testing Status

- ✅ Unit tests pass for pseudo options API
- ✅ Manual testing checklist:

### Manual Test Steps

#### 1. Archive Installation & Auto-Refresh
1. Open Settings → Pseudopotentials
2. Find an archive that is "Not installed" (gray badge)
3. Click "Install" button
4. Wait for installation to complete (progress indicator shows)
5. Verify archive status changes to "✓ Installed" (blue badge)
6. Open a calculation with pseudo selection modal
7. **Expected**: Chips for that archive should now be blue (installed) without page reload

#### 2. Corrupt Archive Detection
1. Manually corrupt an installed archive file (e.g., truncate or modify it)
2. In Settings → Pseudopotentials, verify archive shows "⚠ Corrupt" badge
3. In calculation pseudo selection, verify chips for that archive are gray (not installed)
4. Try to materialize a pseudo from that archive
5. **Expected**: Error message: "Archive exists but failed SHA256 verification. Reinstall from Settings → Pseudopotentials."
6. Click "Reinstall" in Settings
7. **Expected**: Archive reinstalls and status returns to "✓ Installed"

#### 3. Non-Installed Selection Error
1. In calculation pseudo selection, select an option that has only gray (not installed) chips
2. Click "Apply"
3. **Expected**: Alert shows error listing required archive names and library labels, with hint to install from Settings

#### 4. Name Collision Handling
1. If multiple options have same basename but different SHA256
2. **Expected**: Dropdown shows "basename · sha256prefix" for disambiguation
3. Selection still works correctly

#### 5. Backward Compatibility
1. Open calculation without `calculation` prop
2. **Expected**: Falls back to old API (Library dropdown + file dropdown)
3. Old API still works as before

## Execution Semantics & Persistence (v2.1) ✓

### SHA256-Based Pinning
- ✅ Calculation stores pseudo identity by SHA256 (primary) + sha_token (secondary) + basename
- ✅ `species_map` schema extended: `{pseudo_sha256, pseudo_sha_token, pseudo_basename, pseudopot (legacy)}`
- ✅ Backward compatible: legacy filename-only entries treated as "un-pinned"

### Deterministic Materialization
- ✅ `materialize_calc_pseudos()` copies pseudos to `working_dir/pseudo` before execution
- ✅ Never creates/uses `project_root/pseudo` during run (user-managed runtime assets)
- ✅ SHA256 verification after copy ensures exact content match
- ✅ Legacy filename resolution: project/pseudo → internal → installed archives (deterministic order)

### Run Path Integration
- ✅ `step.run()` receives `species_map` from calculation
- ✅ `run_input_step()` calls `materialize_calc_pseudos()` before `prepare_input_step()`
- ✅ `ESPRESSO_PSEUDO` always set to `working_dir/pseudo` (never `project_root/pseudo`)
- ✅ GUARD: Never uses `repo_root/pseudo` (trap fixture catches attempts)

### UI/API Wiring
- ✅ `CommonCardPseudo` stores sha256 + sha_token when user selects option
- ✅ `onUpdate` sends extended format: `{pseudopot, pseudo_sha256, pseudo_sha_token, pseudo_basename}`
- ✅ Backend `update_calculation_species_map` accepts and stores all fields
- ✅ UI loads sha256 from existing `species_map` on mount

## Notes

- All manifest/index data comes from vendored bundle (no runtime network)
- SHA256 verification is strict (no "exists == installed" shortcuts)
- Archive installation happens only via Settings user action
- Canonical install path: `<store_dir>/archives/<asset_name>`
- **Execution invariant**: `working_dir/pseudo` is the only pseudo directory used during run
- **Project pseudo**: User-managed runtime assets; never auto-overwritten during run
- **Legacy migration**: Filename-only entries resolved deterministically, sha256 computed but not persisted (lazy upgrade)

