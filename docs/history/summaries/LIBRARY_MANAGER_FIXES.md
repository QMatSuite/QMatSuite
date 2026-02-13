# Library Manager Fixes - Developer Notes

## Overview
Fixed critical bugs in the Library Manager that prevented correct detection of installed libraries and improved the UI to provide a package-manager-like experience.

## Issues Fixed

### 1. Backend Installed Detection (Fixed)

**Problem**: The `get_library_status()` function was using `list_installed_sssp()` which iterated through multiple versions, but the status detection logic wasn't correctly checking the actual filesystem structure.

**Solution**: Rewrote `_get_sssp_status()` to directly check the filesystem using the correct directory structure:
- **Detection Rules**:
  - `precision` installed iff `<store_dir>/sssp/1.3.0/precision/library` exists and contains at least 1 `*.UPF` file
  - `efficiency` installed iff `<store_dir>/sssp/1.3.0/efficiency/library` exists and contains at least 1 `*.UPF` file

**Implementation** (`src/quantumvitas/core/library_manager.py`):
- Directly checks each variant's library directory
- Counts UPF files to determine if installed
- Computes size for installed variants
- Includes `path_checked` field for debugging
- Returns rich status object with `installed_variants`, `variant_statuses`, and overall `status` ("installed", "partial", "not_installed")

**Key Changes**:
```python
def _get_sssp_status(config: PseudoConfig) -> LibraryStatus:
    # Directly check each variant's library directory
    for variant in ["precision", "efficiency"]:
        lib_path = get_sssp_library_path(store_dir, "1.3.0", variant)
        library_path = lib_path / "library"
        
        if library_path.exists() and library_path.is_dir():
            upf_files = list(library_path.glob("*.UPF")) + list(library_path.glob("*.upf"))
            if len(upf_files) > 0:
                installed = True
                # ... compute file_count, size_bytes, etc.
```

### 2. Frontend Refresh Logic (Fixed)

**Problem**: After install/remove/repair operations, the UI wasn't reliably refreshing the library status, leading to stale "0 installed" displays even when libraries were actually installed.

**Solution**: 
- Added 500ms delay after filesystem operations to allow filesystem to settle
- Force refresh both individual library status and all statuses
- Ensured `loadAllStatuses()` is called after operations to maintain consistency

**Implementation** (`gui/src/hooks/useLibraryManager.ts`):
```typescript
if (result.success) {
  setInstallStage('installed');
  // Force refresh status - wait a bit for filesystem to settle
  await new Promise(resolve => setTimeout(resolve, 500));
  await loadLibraryStatus(libraryId);
  await loadStoreSize();
  // Also refresh all statuses to ensure consistency
  await loadAllStatuses();
}
```

**Applied to**:
- `installLibrary()` - after successful installation
- `removeLibrary()` - after successful removal
- `repairLibrary()` - after successful repair

### 3. UI Improvements (Package Manager Style)

**Added Features**:
1. **Filter Tabs**: All | Installed | Available
   - Segmented control at top of library list
   - Shows count in "Installed" tab
   - Filters libraries based on status

2. **Visual Status Indicators**:
   - **Installed libraries**: Blue accent border, green name, highlighted background
   - **Available libraries**: Grey, reduced opacity
   - **Partial install**: Warning badge

3. **Better Result Display**:
   - Toast messages persist for 10 seconds (was 8)
   - Shows warnings/details in addition to success/error messages
   - Clear visual feedback for all operations

4. **Variant Chips**:
   - Each variant shows installed status with checkmark
   - Hover tooltip shows file count and size
   - Installed variants highlighted in green

**Implementation** (`gui/src/components/panels/LibrariesPanel.tsx`):
- Added `filterTab` state: 'all' | 'installed' | 'available'
- Filter logic: `filteredLibraries` based on status
- CSS classes: `library-card--installed`, `library-card--available`
- Enhanced action result display with details

### 4. Status Source of Truth

**Single Source of Truth**: `get_library_status(library_id)`
- All UI status displays derive from this function
- Never rely on transient operation messages
- Status is computed fresh from filesystem on each query
- No caching that could become stale

**UI Status Computation**:
```typescript
// Installed count computed from authoritative status
const installedCount = libraryStatuses ? 
  Array.from(libraryStatuses.values()).filter(
    s => s && (s.status === 'installed' || s.status === 'partial')
  ).length : 0;
```

## Directory Structure

The detection logic correctly handles the nested structure:

```
<store_dir>/
  sssp/
    1.3.0/
      precision/
        library/
          *.UPF (pseudopotential files)
        cutoffs.json
        manifest.json
      efficiency/
        library/
          *.UPF
        cutoffs.json
        manifest.json
```

**Detection Path**: `<store_dir>/sssp/1.3.0/{variant}/library/*.UPF`

## Debugging Information

The status object now includes:
- `path_checked`: The exact path that was checked (for debugging)
- `file_count`: Number of UPF files found
- `size_bytes`: Total size of installed files
- `version`: Version string if installed

## Manual Test Checklist

### Test 1: Detection After Install
1. Install SSSP precision variant
2. Verify status shows "Installed" or "Partial" immediately
3. Verify "Installed: 1 libraries" in overview
4. Verify precision variant chip shows checkmark
5. Install efficiency variant
6. Verify status shows "Installed" (both variants)
7. Verify "Installed: 1 libraries" (one library, two variants)

### Test 2: Filter Tabs
1. With both variants installed, click "Installed" tab
2. Verify only SSSP library is shown
3. Click "Available" tab
4. Verify no libraries shown (or other libraries if any)
5. Click "All" tab
6. Verify all libraries shown

### Test 3: Remove and Refresh
1. Remove precision variant
2. Verify status immediately updates to "Partial"
3. Verify precision chip no longer shows checkmark
4. Verify "Installed: 1 libraries" still (partial install)
5. Remove efficiency variant
6. Verify status updates to "Not Installed"
7. Verify "Installed: 0 libraries"

### Test 4: Already Installed (Skip Detection)
1. Install precision (already installed)
2. Verify warning message: "Library already installed"
3. Verify status still shows "Installed" (not reset to 0)
4. Verify no duplicate installation

### Test 5: Repair from Seed
1. Delete store directory contents for one variant
2. Click "Repair" button
3. Verify variant is re-extracted
4. Verify status updates correctly
5. Verify file count matches original

### Test 6: Visual States
1. Verify installed library has blue border and green name
2. Verify available library has grey appearance
3. Verify partial install shows warning badge
4. Verify variant chips show correct installed state

## Files Modified

### Backend
- `src/quantumvitas/core/library_manager.py`:
  - Rewrote `_get_sssp_status()` with direct filesystem checks
  - Added `path_checked` field to `LibraryVariantStatus`
  - Improved detection logic to match actual directory structure

### Frontend
- `gui/src/hooks/useLibraryManager.ts`:
  - Added filesystem settle delay (500ms) after operations
  - Force refresh all statuses after install/remove/repair
  - Improved error handling

- `gui/src/components/panels/LibrariesPanel.tsx`:
  - Added filter tabs (All | Installed | Available)
  - Added visual states (installed/available styling)
  - Enhanced result display with details
  - Improved status badge display

- `gui/src/components/panels/SettingsPanel.css`:
  - Added `.libraries-filter-tabs` styles
  - Added `.library-card--installed` and `.library-card--available` styles
  - Added `.settings-action-result__details` styles

## Root Cause Analysis

The "2 skipped but Installed=0" issue was caused by:

1. **Detection Logic**: The old `_get_sssp_status()` relied on `list_installed_sssp()` which might not have been correctly checking the filesystem structure, or there was a mismatch between what the install function checked and what the status function checked.

2. **Refresh Timing**: The frontend wasn't waiting long enough for the filesystem to settle after install operations, and wasn't refreshing all statuses consistently.

3. **Status Source**: The UI was potentially using stale status data or not refreshing after operations completed.

**Fix**: 
- Direct filesystem checks in detection logic (matches install logic exactly)
- Consistent refresh pattern with filesystem settle delay
- Single source of truth: always query `get_library_status()` for current state

## Future Considerations

- Consider adding unit tests for `_get_sssp_status()` with mock filesystem
- Consider caching status with TTL to reduce filesystem queries
- Consider adding status change events/notifications for real-time updates
- Extend detection logic for future libraries (PseudoDojo, etc.) using same pattern

