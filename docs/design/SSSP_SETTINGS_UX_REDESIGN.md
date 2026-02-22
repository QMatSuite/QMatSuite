# SSSP Settings UX Redesign Summary

## Overview
Redesigned the Settings → Pseudopotentials (SSSP) UI/UX to make the normal workflow dead-simple while keeping advanced features (seed/offline) accessible but hidden.

## Changes Implemented

### 1. Normal View (Default)
- **Status Summary**: Shows installed libraries (Precision/Efficiency) at a glance
- **Primary Actions**: Three prominent buttons:
  - "Download & Install Precision"
  - "Download & Install Efficiency"  
  - "Download & Install All"
- **Smart Network Handling**: 
  - If network downloads are disabled, buttons show "(Enable Network)" suffix
  - Clicking automatically enables network access and proceeds with download
  - No separate "Allow Network Downloads" toggle required in normal flow
- **Progress Indicator**: Browser-like progress with 4 stages:
  1. Download
  2. Verify
  3. Extract
  4. Installed
- **Installed Libraries List**: Shows installed libraries with file counts
- **Store Directory**: Visible with "Open" button to reveal in Finder
- **No "Initialize Dirs" Button**: Removed - directories are created automatically

### 2. Advanced Section (Collapsed by Default)
- **Seed Cache (Disaster Recovery)**:
  - Clear explanation: "Archives are kept here so you can reinstall if the store is corrupted"
  - Seed directory labeled as "Seed Directory (Advanced Cache)"
  - Shows cached archives with filename, size, and SHA256 prefix
  - Two buttons:
    - "Import Seed Archives…" - Multi-select tar/zip files, copies to seed_dir with SHA256 dedup
    - "Install from Seed" - Re-extracts cached archives into store_dir
- **Network Behavior**:
  - Single checkbox: "Allow network downloads"
  - Not required for normal users (download buttons handle it automatically)
- **Diagnostics**:
  - "Validate Configuration" button
  - Shows status table with checkmarks:
    - Repo pseudos found
    - Store dir exists + writable
    - Seed dir exists (optional)
    - Installed libs detected

### 3. Backend Enhancements
- **Automatic Seed Caching**: Downloads automatically save archives to seed_dir
- **SHA256 Deduplication**: Archives are deduplicated by SHA256 hash
- **New RPC Handler**: `import_seed_archives` - imports tar/zip files into seed cache
- **Deterministic Naming**: Archives saved as `SSSP_{version}_{flavor}_{sha256_prefix}.tar.gz`

## Architecture (Unchanged)
- **store_dir**: Extracted installed libraries (e.g., `temp/pseudo/sssp/1.3.0/{precision|efficiency}/library/*.UPF`)
- **seed_dir**: Stores original archives (tar/zip) for disaster recovery/offline install
- **repo/resources/pseudo**: Internal committed pseudos for demos/tests (always available)
- **Versioning**: Treats "latest" only (1.3.0)

## Files Modified

### Backend
- `src/qmatsuite/core/pseudo_config.py`:
  - Added `import_seed_archives()` function
- `src/qmatsuite/daemon/server.py`:
  - Added `_handle_import_seed_archives()` RPC handler

### Frontend
- `gui/src/hooks/usePseudoConfig.ts`:
  - Added `importSeedArchives()` function
- `gui/src/components/panels/SettingsPanel.tsx`:
  - Updated labels (seed directory as "Advanced Cache")
  - Added "Import Seed Archives…" button
  - Improved button styling and layout
- `gui/src/components/panels/SettingsPanel.css`:
  - Added `.settings-btn--secondary` style

## Manual Test Checklist

### Normal Download/Install Workflow
- [ ] **Test 1: Download Precision (Network Enabled)**
  1. Open Settings → Pseudopotentials
  2. Click "Download & Install Precision"
  3. Verify progress indicator shows: Download → Verify → Extract → Installed
  4. Verify "Precision installed" appears in status summary
  5. Verify library appears in "Installed Libraries" list
  6. Verify archive appears in seed cache (check Advanced section)

- [ ] **Test 2: Download Efficiency (Network Disabled → Auto-Enable)**
  1. Disable "Allow network downloads" in Advanced section
  2. Click "Download & Install Efficiency"
  3. Verify button shows "(Enable Network)" suffix
  4. Click button - should automatically enable network and download
  5. Verify download proceeds normally
  6. Verify "Efficiency installed" appears in status summary

- [ ] **Test 3: Download All**
  1. Click "Download & Install All"
  2. Verify both Precision and Efficiency download
  3. Verify status shows "Both Precision and Efficiency installed"
  4. Verify both appear in installed libraries list

### Seed Cache Functionality
- [ ] **Test 4: Automatic Seed Cache Population**
  1. Delete seed_dir contents (if any)
  2. Download a library (Precision or Efficiency)
  3. Expand Advanced section
  4. Verify archive appears in "Cached Archives" list
  5. Verify archive has correct filename format: `SSSP_1.3.0_{flavor}_{sha256_prefix}.tar.gz`
  6. Verify archive shows size and SHA256 prefix

- [ ] **Test 5: Import Seed Archives**
  1. Have a tar.gz archive file ready (e.g., from previous download)
  2. Expand Advanced section
  3. Click "Import Seed Archives…"
  4. Select one or more tar.gz/zip files
  5. Verify success message shows imported count
  6. Verify archives appear in cached archives list
  7. Try importing the same file again - should show "skipped (duplicate)" message

- [ ] **Test 6: Install from Seed (Disaster Recovery)**
  1. Delete store_dir contents (or specific library directory)
  2. Expand Advanced section
  3. Verify archives are listed in cached archives
  4. Click "Install from Seed"
  5. Verify library is re-extracted to store_dir
  6. Verify library appears in installed libraries list
  7. Verify status summary updates

### Directory Management
- [ ] **Test 7: Store Directory**
  1. Verify store directory path is visible
  2. Click "Open" button next to store directory
  3. Verify Finder opens to correct directory
  4. Change store directory path and click "Apply"
  5. Verify path updates
  6. Verify "Open" button works with new path

- [ ] **Test 8: Seed Directory (Advanced)**
  1. Expand Advanced section
  2. Verify seed directory path is visible (labeled "Seed Directory (Advanced Cache)")
  3. Click "Open" button
  4. Verify Finder opens to correct directory
  5. Verify directory structure: `sssp/1.3.0/{flavor}/`

### Validation/Diagnostics
- [ ] **Test 9: Validate Configuration**
  1. Expand Advanced section
  2. Click "Validate Configuration"
  3. Verify status table shows:
     - ✓ Repo Pseudos: Found
     - ✓ Store Dir: Exists
     - ✓ Store Writable: Yes
     - ✓ Seed Dir: Exists (if configured)
     - ✓ Seed SSSP: Found (if archives exist)
  4. Delete store_dir and validate again - should show warnings
  5. Restore store_dir and validate - should show all green

### Edge Cases
- [ ] **Test 10: Concurrent Downloads**
  1. Click "Download & Install Precision"
  2. Immediately try to click "Download & Install Efficiency"
  3. Verify second click is disabled or shows error
  4. Wait for first download to complete
  5. Verify second download can proceed

- [ ] **Test 11: Network Error Handling**
  1. Disconnect network (or block GitHub)
  2. Click "Download & Install Precision"
  3. Verify error message appears
  4. Verify download stage shows "error"
  5. Reconnect network and retry - should work

- [ ] **Test 12: Already Installed**
  1. Install a library (e.g., Precision)
  2. Click "Download & Install Precision" again
  3. Verify warning message: "Library already installed"
  4. Verify no duplicate installation

## Visual/UX Verification
- [ ] Buttons are visually prominent (primary actions)
- [ ] Advanced actions are secondary styled
- [ ] Progress indicator is clear and browser-like
- [ ] No empty white areas
- [ ] Dark theme consistency maintained
- [ ] Disabled states are clear
- [ ] Status summary is easy to read
- [ ] Directory paths are accessible but not intrusive

## Notes
- The "Initialize Dirs" button has been removed - directories are created automatically when needed
- Seed cache is populated automatically during downloads
- Network toggle is optional - download buttons handle enabling automatically
- All advanced features are hidden by default but fully functional

