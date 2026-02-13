# Library Manager UX Documentation

## Overview
The Library Manager provides a generic, package-manager-like interface for managing pseudopotential libraries (SSSP, PseudoDojo, etc.) in QuantumVITAS.

## Architecture

### Backend
- **Generic Layer**: `src/quantumvitas/core/library_manager.py`
  - Provides generic functions: `get_supported_libraries()`, `get_library_status()`, `install_library()`, `remove_library()`, `repair_library()`
  - Wraps existing SSSP-specific functions without rewriting them
  - Designed to be extensible for future libraries (PseudoDojo, etc.)

- **RPC Handlers**: `src/quantumvitas/daemon/server.py`
  - `list_libraries`: Returns metadata for all supported libraries
  - `get_library_status`: Returns status of a specific library
  - `install_library`: Installs library variants from various sources
  - `remove_library`: Removes library variants from store
  - `repair_library`: Re-extracts from seed cache
  - `compute_store_size`: Computes total disk usage

### Frontend
- **Hook**: `gui/src/hooks/useLibraryManager.ts`
  - Provides state management and actions for library operations
  - Handles progress tracking and error management

- **Component**: `gui/src/components/panels/LibrariesPanel.tsx`
  - Main library manager UI
  - Includes modals for install/remove operations

## UI Structure

### Overview Header
- **Installed Count**: Shows number of libraries with installed variants
- **Disk Usage**: Optional display of total store size
- **Store Directory**: Read-only path with "Open" button
- **Seed Cache**: Advanced section with path and "Open" button

### Library List
Each library card shows:
- **Name & Description**: Library identifier and description
- **Status Badge**: Installed / Partial / Not Installed
- **Variants**: Chips showing which variants are installed
- **Actions**:
  - **Install…**: Opens installer modal
  - **Remove…**: Opens remove modal (only if variants installed)
  - **Repair**: Re-extract from seed (advanced, only if seed exists)

### Install Modal
- **Variant Selection**: Checkboxes for each supported variant
  - Default variants marked as "recommended"
- **Source Selection**: Radio buttons
  - GitHub Online (auto-enables network if disabled)
  - Seed Cache (offline)
  - Local Archive (user-provided files)
- **Progress Indicator**: Browser-like 4-stage progress
  - Download → Verify → Extract → Installed
- **File Selection**: For local archive source, multi-select file picker

### Remove Modal
- **Variant Selection**: Checkboxes for installed variants
- **Estimated Freed Space**: Shows disk space that will be freed
- **Confirmation**: Remove button with confirmation

## Library-Specific Implementation (SSSP)

### Library ID
- `library_id = "sssp"`

### Variants
- `variants = ["precision", "efficiency"]`
- Default: `["precision"]` (recommended)

### Sources
- **github_release**: Downloads from GitHub release, saves to seed, extracts to store
- **seed**: Re-extracts from seed cache
- **local_archive**: Imports user-provided archives into seed, then extracts

### Storage Layout
- **Store**: `${store_dir}/sssp/1.3.0/{variant}/library/*.UPF`
- **Seed**: `${seed_dir}/sssp/1.3.0/{variant}/SSSP_1.3.0_{variant}_{sha256_prefix}.tar.gz`

## Manual Test Checklist

### Basic Installation
- [ ] **Test 1: Install Precision (GitHub Online)**
  1. Open Settings → Libraries
  2. Find SSSP library card
  3. Click "Install…"
  4. Select "precision" variant
  5. Select "GitHub Online" source
  6. Click "Install"
  7. Verify progress: Download → Verify → Extract → Installed
  8. Verify SSSP card shows "✓ Installed" status
  9. Verify "precision" variant chip shows "✓"
  10. Verify archive appears in seed cache (check Advanced)

- [ ] **Test 2: Install Efficiency (Network Auto-Enable)**
  1. Disable "Allow network downloads" in Advanced (if available)
  2. Click "Install…" on SSSP
  3. Select "efficiency" variant
  4. Select "GitHub Online" source
  5. Verify button shows "(Enable Network)" or similar
  6. Click "Install"
  7. Verify network is automatically enabled
  8. Verify download proceeds normally
  9. Verify both variants now show as installed

- [ ] **Test 3: Install All Variants**
  1. Remove all SSSP variants (if installed)
  2. Click "Install…"
  3. Select both "precision" and "efficiency"
  4. Select "GitHub Online"
  5. Click "Install"
  6. Verify both variants install
  7. Verify status shows "Installed" (not "Partial")

### Removal
- [ ] **Test 4: Remove One Variant**
  1. Ensure both precision and efficiency are installed
  2. Click "Remove…" on SSSP
  3. Select only "precision" variant
  4. Verify estimated freed space is shown
  5. Click "Remove"
  6. Verify precision is removed
  7. Verify efficiency remains installed
  8. Verify status shows "Partial"

- [ ] **Test 5: Remove All Variants**
  1. Click "Remove…" on SSSP
  2. Select all installed variants
  3. Click "Remove"
  4. Verify all variants removed
  5. Verify status shows "Not Installed"
  6. Verify library card shows no installed variants

### Offline/Seed Operations
- [ ] **Test 6: Install from Seed Cache**
  1. Ensure seed cache has archives (from previous download)
  2. Remove store_dir contents for SSSP
  3. Click "Install…" on SSSP
  4. Select variants to install
  5. Select "Seed Cache" source
  6. Click "Install"
  7. Verify installation proceeds without network
  8. Verify variants are extracted from seed
  9. Verify status updates correctly

- [ ] **Test 7: Install from Local Archive**
  1. Have a tar.gz archive file ready (e.g., SSSP archive)
  2. Click "Install…" on SSSP
  3. Select variants
  4. Select "Local Archive" source
  5. Click "Select Files…"
  6. Select one or more archive files
  7. Click "Install"
  8. Verify archives are imported to seed cache
  9. Verify variants are extracted to store
  10. Verify status updates correctly

- [ ] **Test 8: Repair from Seed**
  1. Ensure seed cache has archives
  2. Delete store_dir contents for one variant (e.g., precision)
  3. Click "Repair" button on SSSP card
  4. Verify variant is re-extracted from seed
  5. Verify status updates to show variant installed
  6. Verify file count matches original

### Advanced Features
- [ ] **Test 9: Store Size Display**
  1. Install some libraries
  2. Verify "Disk usage" shows in overview header
  3. Verify size is formatted correctly (KB/MB/GB)
  4. Remove a library
  5. Verify disk usage decreases

- [ ] **Test 10: Seed Cache Management**
  1. Expand Advanced section
  2. Verify seed directory path is shown
  3. Click "Open" button
  4. Verify Finder opens to seed directory
  5. Verify archive files are visible

### Edge Cases
- [ ] **Test 11: Concurrent Operations**
  1. Start an installation
  2. Try to start another installation
  3. Verify second operation is blocked or shows error
  4. Wait for first to complete
  5. Verify second can proceed

- [ ] **Test 12: Network Error Handling**
  1. Disconnect network (or block GitHub)
  2. Try to install from GitHub Online
  3. Verify error message appears
  4. Verify progress shows "error" stage
  5. Reconnect network and retry - should work

- [ ] **Test 13: Already Installed**
  1. Install a variant
  2. Try to install the same variant again
  3. Verify warning message appears
  4. Verify no duplicate installation

- [ ] **Test 14: Invalid Archive**
  1. Try to install from local archive with invalid file
  2. Verify error message appears
  3. Verify no partial installation

## Extensibility Notes

### Adding New Libraries
To add a new library (e.g., PseudoDojo):

1. **Backend** (`library_manager.py`):
   - Add library metadata to `get_supported_libraries()`
   - Implement library-specific functions:
     - `_get_pseudodojo_status()`
     - `_install_pseudodojo()`
     - `_remove_pseudodojo()`
     - `_repair_pseudodojo()`
   - Update `get_library_status()`, `install_library()`, etc. to handle new library_id

2. **Frontend**:
   - No changes needed - UI is generic and will automatically show new library

3. **Storage Layout**:
   - Follow pattern: `${store_dir}/{library_id}/{version}/{variant}/library/*.UPF`
   - Seed: `${seed_dir}/{library_id}/{version}/{variant}/archives`

## Files Modified

### Backend
- `src/quantumvitas/core/library_manager.py` (new)
- `src/quantumvitas/daemon/server.py` (added generic RPC handlers)

### Frontend
- `gui/src/hooks/useLibraryManager.ts` (new)
- `gui/src/components/panels/LibrariesPanel.tsx` (new)
- `gui/src/components/panels/SettingsPanel.tsx` (updated to use LibrariesPanel)
- `gui/src/components/panels/SettingsPanel.css` (added library manager styles)

## Migration Notes

The old `PseudopotentialsSection` component is still in `SettingsPanel.tsx` but is replaced by `LibrariesPanel`. The old SSSP-specific RPC handlers remain for backward compatibility but new code should use the generic library manager RPCs.

