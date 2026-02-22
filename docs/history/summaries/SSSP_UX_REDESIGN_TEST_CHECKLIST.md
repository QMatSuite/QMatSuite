# SSSP Settings UX Redesign - Test Checklist

## Implementation Summary

### Backend Changes
1. ✅ Modified `download_sssp_library()` to save downloaded archives to `seed_dir` automatically
   - Archives saved with deterministic naming: `SSSP_{version}_{flavor}_{sha256_prefix}.tar.gz`
   - SHA256-based deduplication (doesn't re-save if already exists)
   - Cutoffs JSON also saved to seed_dir
   - Seed save happens inside tempfile context (before temp cleanup)

2. ✅ Added `list_seed_archives()` function to scan seed_dir for cached archives
   - Returns `SeedArchiveInfo` with filename, path, size, SHA256, version, flavor

3. ✅ Added RPC handler `_handle_list_seed_archives` in `server.py`
   - Returns list of seed archives from config.seed_dir

### Frontend Changes
1. ✅ Restructured `PseudopotentialsSection` component:
   - **Normal view (default):**
     - Status summary (shows what's installed)
     - Download & Install buttons (one-click, auto-enables network if needed)
     - Progress indicator (Download → Verify → Extract → Installed)
     - Installed libraries list
     - Store directory (with Open button)
   
   - **Advanced section (collapsed by default):**
     - Seed cache management (shows cached archives, Install from Seed button)
     - Network behavior toggle
     - Diagnostics/Validate

2. ✅ Updated `usePseudoConfig` hook:
   - Added `seedArchives` state
   - Added `listSeedArchives()` function
   - Updated download functions to refresh seed archives after completion

3. ✅ Added CSS styles for new UI elements:
   - Status summary
   - Download section
   - Store directory (simplified)
   - Advanced section (accordion)
   - Archive list items

## Manual Test Checklist

### Normal Download/Install Flow

#### Test 1: First-time Download (Network Disabled)
- [ ] Open Settings → Pseudopotentials
- [ ] Verify "Allow Network Downloads" toggle is OFF (in Advanced section)
- [ ] Click "Download & Install Precision" button
- [ ] Verify button text shows "(Enable Network)" suffix
- [ ] Click button
- [ ] Verify network downloads are automatically enabled
- [ ] Verify download starts immediately (no separate "enable" step)
- [ ] Verify progress indicator shows: Download → Verify → Extract → Installed
- [ ] Verify success message appears
- [ ] Verify library appears in "Installed Libraries" section
- [ ] Verify status summary updates to show "Precision installed"
- [ ] Verify archive is saved to seed_dir (check Advanced → Seed Cache)

#### Test 2: Download with Network Already Enabled
- [ ] Ensure "Allow Network Downloads" is ON (in Advanced)
- [ ] Click "Download & Install Efficiency" button
- [ ] Verify download starts immediately (no enable step)
- [ ] Verify progress indicator works correctly
- [ ] Verify library installs successfully
- [ ] Verify status summary shows "Both Precision and Efficiency installed"

#### Test 3: Download All
- [ ] Click "Download & Install All" button
- [ ] Verify both libraries download and install
- [ ] Verify progress indicator shows stages for both
- [ ] Verify both appear in installed list

### Seed Cache Population

#### Test 4: Verify Automatic Seed Cache
- [ ] After downloading a library, expand Advanced section
- [ ] Navigate to "Seed Cache (Disaster Recovery)"
- [ ] Verify "Cached Archives" section shows downloaded archives
- [ ] Verify archive filenames show: `SSSP_1.3.0_{flavor}_{sha256_prefix}.tar.gz`
- [ ] Verify archive sizes are displayed correctly
- [ ] Verify SHA256 prefix is shown (first 16 chars)
- [ ] Verify cutoffs.json is also in seed_dir

#### Test 5: Seed Cache Deduplication
- [ ] Delete a library from store_dir (manually remove `store_dir/sssp/1.3.0/{flavor}/library/`)
- [ ] Click "Download & Install" for the same library again
- [ ] Verify download completes
- [ ] Verify seed cache message says "Archive already in seed cache" (not re-downloaded)
- [ ] Verify only one archive exists in seed_dir for that version/flavor

### Disaster Recovery (Seed → Store)

#### Test 6: Restore from Seed Cache
- [ ] Manually delete store_dir contents: `rm -rf store_dir/sssp/`
- [ ] Verify installed libraries list is empty
- [ ] Expand Advanced section
- [ ] Navigate to Seed Cache
- [ ] Verify cached archives are listed
- [ ] Click "Install from Seed" button
- [ ] Verify installation completes
- [ ] Verify libraries reappear in "Installed Libraries"
- [ ] Verify status summary updates correctly
- [ ] Verify UPF files are extracted to store_dir/library/

#### Test 7: Partial Store Corruption
- [ ] Delete only one library from store (e.g., delete `store_dir/sssp/1.3.0/precision/`)
- [ ] Keep efficiency library intact
- [ ] Click "Install from Seed"
- [ ] Verify only missing library is restored
- [ ] Verify existing library is not affected

### Advanced Features

#### Test 8: Network Toggle (Advanced)
- [ ] Expand Advanced section
- [ ] Find "Network Behavior" subsection
- [ ] Toggle "Allow network downloads" OFF
- [ ] Collapse Advanced section
- [ ] Click "Download & Install Precision"
- [ ] Verify network is auto-enabled and download proceeds
- [ ] Verify toggle in Advanced is now ON

#### Test 9: Validate Configuration (Advanced)
- [ ] Expand Advanced section
- [ ] Click "Validate Configuration" button
- [ ] Verify validation results appear:
  - [ ] Repo Pseudos: ✓ Found
  - [ ] Store Dir: ✓ Exists
  - [ ] Store Writable: ✓ Yes
  - [ ] Seed Dir: ✓ Exists (if configured)
  - [ ] Seed SSSP: ✓ Found (if archives exist)
- [ ] Test with missing store_dir: delete it, validate, verify "○ Not created"
- [ ] Test with non-writable store_dir: chmod 000, validate, verify "✗ No"

#### Test 10: Seed Directory Management (Advanced)
- [ ] Expand Advanced section
- [ ] Navigate to Seed Cache
- [ ] Verify "Seed Directory" path is displayed
- [ ] Click "📂 Open" button next to seed directory
- [ ] Verify Finder/File Manager opens to seed_dir
- [ ] Verify archives are visible in the file system

### Directory Management

#### Test 11: Store Directory (Normal View)
- [ ] Verify "Store Directory" is visible in normal view (not in Advanced)
- [ ] Verify path input is editable
- [ ] Change store directory path
- [ ] Verify "Apply" button appears
- [ ] Click "Apply"
- [ ] Verify path is saved
- [ ] Click "📂 Open" button
- [ ] Verify Finder/File Manager opens to store_dir

#### Test 12: Auto-Create Directories
- [ ] Set store_dir to a non-existent path (e.g., `/tmp/test_pseudo_store`)
- [ ] Click "Download & Install Precision"
- [ ] Verify directories are created automatically (no "Initialize Dirs" button needed)
- [ ] Verify download completes successfully
- [ ] Verify library is installed in the new location

### Edge Cases

#### Test 13: Offline Mode (No Network)
- [ ] Disconnect from network (or block GitHub in firewall)
- [ ] Ensure seed_dir has archives from previous download
- [ ] Click "Download & Install Precision"
- [ ] Verify error message appears (network unavailable)
- [ ] Expand Advanced → Seed Cache
- [ ] Click "Install from Seed"
- [ ] Verify installation succeeds from local archives

#### Test 14: Corrupted Archive in Seed
- [ ] Manually corrupt an archive in seed_dir (truncate file)
- [ ] Delete corresponding library from store_dir
- [ ] Click "Install from Seed"
- [ ] Verify error message appears
- [ ] Verify store_dir is not partially populated

#### Test 15: Permission Errors
- [ ] Set store_dir to a read-only location (or chmod 555)
- [ ] Click "Download & Install Precision"
- [ ] Verify error message appears
- [ ] Verify no partial installation

#### Test 16: Already Installed
- [ ] Ensure a library is already installed
- [ ] Click "Download & Install" for the same library
- [ ] Verify warning message: "Library already installed"
- [ ] Verify no re-download occurs
- [ ] Verify seed cache is not modified

### UI/UX Validation

#### Test 17: Visual Layout
- [ ] Verify normal view is clean and uncluttered
- [ ] Verify Advanced section is collapsed by default
- [ ] Verify status summary is prominent
- [ ] Verify download buttons are primary actions (prominent styling)
- [ ] Verify progress indicator is clear and visible during download
- [ ] Verify installed libraries list shows checkmarks (✓)

#### Test 18: Button States
- [ ] Verify download buttons are NOT disabled when network toggle is OFF
- [ ] Verify buttons show "(Enable Network)" text when toggle is OFF
- [ ] Verify buttons are disabled only during active download
- [ ] Verify button text changes to show current stage during download

#### Test 19: Progress Feedback
- [ ] Start a download
- [ ] Verify progress stages update: Download → Verify → Extract → Installed
- [ ] Verify active stage is highlighted/animated
- [ ] Verify completed stages show checkmark
- [ ] Verify progress indicator disappears after completion (or shows "Installed ✓")

#### Test 20: Error Handling
- [ ] Trigger a network error (disconnect)
- [ ] Verify clear error message appears
- [ ] Verify error doesn't break UI state
- [ ] Verify user can retry after fixing issue

### Integration Tests

#### Test 21: End-to-End Flow
- [ ] Fresh install (no libraries, no seed cache)
- [ ] Click "Download & Install All"
- [ ] Verify:
  - [ ] Network enabled automatically
  - [ ] Both libraries download
  - [ ] Progress shows all stages
  - [ ] Both libraries appear as installed
  - [ ] Archives saved to seed cache
  - [ ] Status shows "Both Precision and Efficiency installed"

#### Test 22: Disaster Recovery Flow
- [ ] Start with installed libraries
- [ ] Manually delete entire store_dir
- [ ] Verify libraries disappear from UI
- [ ] Expand Advanced → Seed Cache
- [ ] Click "Install from Seed"
- [ ] Verify all libraries restored
- [ ] Verify UI updates correctly

## Expected Behaviors

### Normal Workflow (Happy Path)
1. User clicks "Download & Install Precision"
2. If network disabled, it's enabled automatically
3. Download starts immediately
4. Progress shows: Download → Verify → Extract → Installed
5. Library appears in "Installed Libraries"
6. Archive is saved to seed cache automatically
7. Status summary updates

### Advanced Workflow (Disaster Recovery)
1. User expands Advanced section
2. Sees cached archives in Seed Cache
3. Clicks "Install from Seed"
4. Libraries are extracted from seed to store
5. Installed libraries list updates

### No Manual Steps Required
- ❌ No "Initialize Dirs" button in normal view
- ❌ No separate "Enable Network" step before download
- ❌ No "Install from Seed" in normal view (only in Advanced)
- ✅ Directories created automatically
- ✅ Network enabled automatically when needed
- ✅ Archives saved to seed automatically

## Files Modified

### Backend
- `src/qmatsuite/core/pseudo_config.py`
  - Modified `download_sssp_library()` to accept `seed_dir` parameter
  - Added seed archive saving logic (Step 5)
  - Added `list_seed_archives()` function
  - Added `SeedArchiveInfo` dataclass
  - Modified `download_all_sssp()` to pass `seed_dir`

- `src/qmatsuite/daemon/server.py`
  - Modified `_handle_download_sssp_library()` to pass `seed_dir`
  - Modified `_handle_download_all_sssp()` to pass `seed_dir`
  - Added `_handle_list_seed_archives()` handler
  - Added `list_seed_archives` to RPC command map

### Frontend
- `gui/src/hooks/usePseudoConfig.ts`
  - Added `seedArchives` state
  - Added `SeedArchiveInfo` interface
  - Added `listSeedArchives()` function
  - Updated return type to include `seedArchives` and `listSeedArchives`

- `gui/src/components/panels/SettingsPanel.tsx`
  - Completely restructured `PseudopotentialsSection`
  - Normal view: Status, Download buttons, Progress, Installed list, Store dir
  - Advanced section: Seed cache, Network toggle, Diagnostics
  - Removed "Initialize Dirs" from normal view
  - Removed "Install from Seed" from normal view
  - Simplified directory management

- `gui/src/components/panels/SettingsPanel.css`
  - Added styles for status summary
  - Added styles for download section
  - Added styles for store directory (simplified)
  - Added styles for advanced section (accordion)
  - Added styles for archive items

- `gui/src/types/qms.ts`
  - Added `list_seed_archives` RPC type definition

## Architecture Preserved

✅ **No breaking changes:**
- PseudoConfig structure unchanged
- Directory layout unchanged (`store_dir/sssp/{version}/{flavor}/library/`)
- Resolution flow unchanged
- Project self-containment unchanged

✅ **Backend behavior:**
- Download still extracts automatically
- Directories still created automatically
- Seed installation still works offline
- All existing RPCs still functional

## Known Limitations / Future Enhancements

1. **Import Seed Archives** - Not yet implemented (mentioned in requirements but not critical for MVP)
   - Would allow users to manually add archives to seed_dir via file picker
   - Can be added later if needed

2. **Clear Seed Cache** - Not yet implemented
   - Can be added later if needed
   - For now, users can manually delete seed_dir contents

3. **Progress percentage/bytes** - Currently shows stages only
   - Backend doesn't provide byte-level progress
   - Stage-based progress is sufficient for UX

4. **Multi-version support** - Currently hardcoded to 1.3.0
   - As specified: "Versioning is NOT a concern for now"

