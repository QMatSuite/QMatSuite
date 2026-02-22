# SSSP/Pseudopotential Settings UX Analysis

## Task A — Code Reading & Current Behavior

### 1. Frontend Files Responsible for Settings → Pseudopotentials Panel

**Primary Component:**
- **File:** `gui/src/components/panels/SettingsPanel.tsx`
- **Component:** `PseudopotentialsSection()` (lines 701-1156)
- **Key State:**
  - `localStoreDir`, `localSeedDir` - local edits before applying
  - `actionResult` - success/error messages
  - `confirmDownload` - modal state for download confirmation
  - Uses `usePseudoConfig()` hook for all operations

**Hook/State Management:**
- **File:** `gui/src/hooks/usePseudoConfig.ts`
- **Hook:** `usePseudoConfig()` (lines 79-390)
- **Provides:**
  - `config` - current PseudoConfig state
  - `installedLibraries` - list of installed SSSP libraries
  - `isLoading`, `isDownloading`, `isValidating` - async operation states
  - Actions: `updateConfig`, `validate`, `initDirs`, `installFromSeed`, `downloadLibrary`, `downloadAll`, `listInstalledLibraries`

**Key UI Elements:**
- Store Directory input (line 887-902)
- Seed Directory input (line 906-921)
- "Allow Network Downloads" toggle (line 925-944)
- Action buttons: Apply Changes, Reset to Default, Validate, Initialize Dirs, Install from Seed (line 948-990)
- Download buttons: Efficiency, Precision, Download All (line 1006-1036)
- Installed Libraries display (line 1118-1137)
- Validation results display (line 1066-1115)

### 2. Backend/RPC Endpoints

**RPC Handlers in `src/qmatsuite/daemon/server.py`:**

| Handler Method | RPC Name | Payload | Key Function Called |
|----------------|----------|---------|---------------------|
| `_handle_get_pseudo_config` (line 654) | `get_pseudo_config` | `{}` | `load_pseudo_config()` |
| `_handle_set_pseudo_config` (line 687) | `set_pseudo_config` | `{store_dir?, seed_dir?, allow_download?}` | `save_pseudo_config()` |
| `_handle_validate_pseudo_config` (line 730) | `validate_pseudo_config` | `{}` | `validate_pseudo_config()` |
| `_handle_init_pseudo_dirs` (line 756) | `init_pseudo_dirs` | `{}` | `init_pseudo_dirs()` |
| `_handle_install_seed_to_store` (line 776) | `install_seed_to_store` | `{version?, flavor?}` | `install_sssp_from_seed()` or `install_all_sssp_from_seed()` |
| `_handle_list_installed_sssp` (line 828) | `list_installed_sssp` | `{}` | `list_installed_sssp()` |
| `_handle_download_sssp_library` (line 855) | `download_sssp_library` | `{flavor, version?, force?}` | `download_sssp_library()` |
| `_handle_download_all_sssp` (line 912) | `download_all_sssp` | `{force?}` | `download_all_sssp()` |

**Core Functions in `src/qmatsuite/core/pseudo_config.py`:**
- `load_pseudo_config()` (line 154) - loads from user config file
- `save_pseudo_config()` (line 174) - saves to user config file
- `validate_pseudo_config()` (line 216) - validates config and directories
- `init_pseudo_dirs()` (line 299) - creates store_dir and seed_dir if missing
- `install_sssp_from_seed()` (line 404) - extracts tar.gz from seed to store
- `download_sssp_library()` (line 778) - downloads from GitHub, verifies, extracts
- `list_installed_sssp()` (line 374) - scans store_dir for installed libraries

### 3. State Machine Explanation

#### 3.1 "Allow Network Downloads" Storage

**Location:** User config file (platform-specific)
- **macOS:** `~/Library/Application Support/QMatSuite/config.json`
- **Linux:** `~/.config/qmatsuite/config.json`
- **Windows:** `%APPDATA%/QMatSuite/config.json`

**Structure:**
```json
{
  "pseudo": {
    "store_dir": "/path/to/temp/pseudo",
    "seed_dir": "/path/to/temp/assets/pseudo_seed",
    "allow_download": false,
    "network_pseudo_base_url": "...",
    "legacy_tables_base_url": "..."
  }
}
```

**In-Memory:** `PseudoConfig` dataclass (line 63-125 in `pseudo_config.py`)
- Field: `allow_download: bool = False` (default: False, opt-in)
- Persisted via `save_pseudo_config()` when toggle changes
- Loaded via `load_pseudo_config()` on Settings panel mount

**UI Behavior:**
- Toggle immediately saves via `updateConfig({ allow_download: checked })` (line 761-763 in SettingsPanel.tsx)
- Download buttons are **disabled** when `allow_download === false` (line 1009, 1019, 1029)
- If user somehow clicks download with toggle off, shows confirmation modal (line 1040-1063)

#### 3.2 "Initialize Dirs" Action

**Function:** `init_pseudo_dirs()` in `pseudo_config.py` (line 299-330)

**What it does:**
1. Creates `store_dir` if missing (with `parents=True, exist_ok=True`)
2. Creates `seed_dir` if missing (with `parents=True, exist_ok=True`)
3. Returns `{store_dir_created: bool, seed_dir_created: bool, messages: [], errors: []}`

**Directory Structure Created:**
- `store_dir` → e.g., `/path/to/temp/pseudo/` (empty initially)
- `seed_dir` → e.g., `/path/to/temp/assets/pseudo_seed/` (empty initially)

**Note:** This only creates the **base directories**, NOT the SSSP subdirectories (`sssp/1.3.0/efficiency/`, etc.). Those are created automatically by `download_sssp_library()` or `install_sssp_from_seed()` when needed.

**UI Trigger:** Button "Initialize Dirs" (line 976-982 in SettingsPanel.tsx)
- Calls `initDirs()` hook function
- Shows success/error message for 5 seconds
- Refreshes validation after init

#### 3.3 "Download SSSP Libraries" Action

**Function:** `download_sssp_library()` in `pseudo_config.py` (line 778-998)

**What it does:**
1. **Checks allow_download:** If `allow_download=False` and `force=False`, returns error (line 819-821)
2. **Validates flavor:** Must be "efficiency" or "precision" (line 824-826)
3. **Checks if already installed:** If `store_dir/sssp/{version}/{flavor}/library/` exists and has `.UPF` files, returns success with warning (line 831-835)
4. **Creates directories:** `store_path.mkdir(parents=True, exist_ok=True)` and `library_path.mkdir(parents=True, exist_ok=True)` (line 838-843)
   - **This is automatic** - no need to call "Initialize Dirs" first
5. **Fetches manifest:** Downloads `MANIFEST_PSEUDO_SEED.json` from GitHub release (line 848-853)
6. **Selects entries:** Finds tar.gz and json files for version/flavor (line 856-883)
7. **Downloads files:** Downloads tar.gz and cutoffs.json to temp directory with SHA256 verification (line 888-931)
8. **Extracts archive:** Extracts only `.UPF` files from tar.gz to `library_path/` (line 933-961)
   - **Extraction happens automatically** - no separate "extract" step
9. **Copies cutoffs:** Copies `cutoffs.json` to `store_path/cutoffs.json` (line 963-969)
10. **Creates manifest:** Writes `manifest.json` with installation metadata (line 971-992)

**Final Layout After Download:**
```
${store_dir}/sssp/1.3.0/efficiency/
  ├── library/
  │   ├── Si.pbe-n-rrkjus_psl.1.0.0.UPF
  │   ├── O.pbe-n-rrkjus_psl.1.0.0.UPF
  │   └── ... (all UPF files, flat structure)
  ├── cutoffs.json
  └── manifest.json
```

**UI Trigger:** Download buttons (Efficiency, Precision, Download All) (line 1006-1036)
- Disabled when `allow_download === false`
- Calls `downloadLibrary(flavor, false)` or `downloadAll(false)`
- Shows loading state (`isDownloading`)
- Refreshes `installedLibraries` list after success
- Shows success/error message for 8 seconds

#### 3.4 "Install from Seed" Action

**Function:** `install_sssp_from_seed()` in `pseudo_config.py` (line 404-507)

**What it does:**
1. **Checks seed exists:** Validates `seed_dir/sssp/{version}/{flavor}/` exists (line 439-441)
2. **Finds archive:** Looks for `*.tar.gz` or `*.tgz` in seed directory (line 444-447)
3. **Creates store directory:** `library_path.mkdir(parents=True, exist_ok=True)` (line 453-457)
   - **This is automatic** - no need to call "Initialize Dirs" first
4. **Extracts archive:** Extracts only `.UPF` files from tar.gz to `library_path/` (line 460-478)
   - **Extraction happens automatically** - same as download
5. **Copies cutoffs:** Copies `*cutoff*.json` or `*cutoffs*.json` to `store_path/cutoffs.json` (line 480-487)
6. **Creates manifest:** Writes `manifest.json` with source="seed" (line 489-504)

**Seed Layout Expected:**
```
${seed_dir}/sssp/1.3.0/efficiency/
  ├── SSSP_1.3.0_PBE_efficiency.tar.gz  (or similar name)
  └── cutoffs.json  (optional)
```

**Store Layout After Install (same as download):**
```
${store_dir}/sssp/1.3.0/efficiency/
  ├── library/
  │   └── ... (extracted UPF files)
  ├── cutoffs.json
  └── manifest.json
```

**UI Trigger:** Button "Install from Seed" (line 983-989)
- Calls `installFromSeed()` (no version/flavor specified = installs all available)
- Shows loading state
- Refreshes `installedLibraries` list after success
- Shows success/error message for 5 seconds

**When is it needed?**
- **Offline installation:** When user has pre-downloaded SSSP archives in seed_dir but no network access
- **Pre-bundled setup:** For air-gapped systems or CI/CD environments
- **NOT redundant with download:** Download requires network; Install from Seed is offline-only

### 4. Installed Status Detection

**Function:** `list_installed_sssp()` in `pseudo_config.py` (line 374-401)

**Detection Logic:**
1. Scans `store_dir/sssp/{version}/{flavor}/library/` for each version/flavor combination
2. Checks if `library/` directory exists
3. Counts `.UPF` and `.upf` files in `library/`
4. **Installed = true** if `library_path.exists()` AND `len(upf_files) > 0`
5. Also checks for `cutoffs.json` and `manifest.json` presence

**Exact Checks:**
```python
library_path = store_dir / "sssp" / version / flavor / "library"
if library_path.exists():
    upf_files = list(library_path.glob("*.UPF")) + list(library_path.glob("*.upf"))
    if len(upf_files) > 0:
        installed = True
        file_count = len(upf_files)
        has_cutoffs = (lib_path / "cutoffs.json").exists()
        has_manifest = (lib_path / "manifest.json").exists()
```

**UI Display:**
- Shows in "Installed SSSP Libraries" section (line 1118-1137)
- Only displays libraries where `installed === true`
- Shows version, flavor, file count, and cutoffs status

**Refresh Triggers:**
- On Settings panel mount (line 734-736)
- After successful download (line 820)
- After successful install from seed (line 217 in usePseudoConfig.ts)

---

## Task B — UX Simplification Proposal

### Pain Points

1. **Redundant "Initialize Dirs" step:**
   - Both `download_sssp_library()` and `install_sssp_from_seed()` automatically create directories with `mkdir(parents=True, exist_ok=True)`
   - User must click "Initialize Dirs" before download/install, but it's not actually required
   - Creates confusion: "Do I need to initialize first?"

2. **Multi-step network download flow:**
   - Step 1: Toggle "Allow Network Downloads" ON
   - Step 2: Click "Initialize Dirs" (feels required but isn't)
   - Step 3: Click "Download" button
   - Step 4: Wait for download + auto-extraction
   - **Problem:** Steps 1-3 feel like prerequisites, but only step 1 and 3 are actually needed

3. **"Install from Seed" feels redundant:**
   - After download, libraries are immediately usable (auto-extracted)
   - "Install from Seed" does the same extraction, but from local archives
   - **Confusion:** "Why do I need this if download already installed it?"
   - **Reality:** It's for offline-only scenarios, but this isn't clear

4. **Download buttons disabled when toggle is off:**
   - User must toggle first, then click download
   - Could be combined into one action: "Download (enable network access)"

5. **No clear distinction between online vs offline workflows:**
   - Both paths lead to the same result (extracted library in store)
   - UI doesn't clearly separate "I have network" vs "I have seed archives"

### Simplified UX Proposal

#### 1. New User Flow

**Online (Network) Path:**
1. User clicks "Download SSSP Library" button (Efficiency/Precision/All)
2. If `allow_download === false`, show inline prompt: "Enable network downloads to proceed?" with "Yes, Enable & Download" button
3. If user confirms, toggle `allow_download` to `true` AND start download in one action
4. Download automatically creates directories, downloads, verifies, extracts
5. Library immediately usable (shown in "Installed Libraries" section)

**Offline (Seed) Path:**
1. User places SSSP archives in `seed_dir/sssp/{version}/{flavor}/`
2. User clicks "Install from Local Archives" button (or "Install from Seed" with clearer label)
3. System scans seed_dir, shows available libraries, user selects which to install
4. Installation automatically creates directories, extracts archives
5. Library immediately usable

**Key Changes:**
- Remove "Initialize Dirs" button (or hide it, make it automatic on first download/install)
- Combine "Enable Downloads" + "Download" into single action when toggle is off
- Rename "Install from Seed" to "Install from Local Archives" with description: "For offline installation from pre-downloaded archives"
- Auto-create directories silently (no user action needed)

#### 2. Minimal UI Changes Required

**Remove/Hide:**
- "Initialize Dirs" button - make it automatic/background operation
  - **Alternative:** Keep button but move to "Advanced" section, or show only if validation shows directory creation failed

**Modify Download Buttons:**
- When `allow_download === false`:
  - Change button text to "Download (Enable Network Access)"
  - On click, show inline confirmation: "This will enable network downloads and start downloading. Continue?"
  - If confirmed, call `updateConfig({ allow_download: true })` THEN `downloadLibrary(flavor, false)` in sequence
- When `allow_download === true`:
  - Keep current behavior (direct download)

**Rename/Clarify "Install from Seed":**
- Button text: "Install from Local Archives"
- Description: "Install SSSP libraries from pre-downloaded archives in the seed directory. Use this for offline installation."
- Show available libraries in seed_dir before install (scan and display list)

**Add Smart Defaults:**
- On first Settings panel load, if `store_dir` doesn't exist, auto-create it silently
- Show validation status inline (green checkmark if directories exist and writable)

**UI Layout Suggestion:**
```
Pseudopotentials Section
├── Store Directory [input] [✓/⚠️ status icon]
├── Seed Directory [input] [✓/⚠️ status icon]
├── Allow Network Downloads [toggle] [description]
│
├── Download SSSP Libraries
│   ├── [⬇️ Efficiency] [⬇️ Precision] [⬇️ Download All]
│   └── (buttons enable/disable based on toggle, or show "Enable & Download" if off)
│
├── Install from Local Archives
│   ├── [📦 Install from Seed] button
│   └── (shows available libraries in seed_dir if any)
│
└── Installed Libraries
    └── (list of installed libraries)
```

#### 3. Minimal Backend Changes Required

**No changes needed to core functions** - they already auto-create directories.

**Optional Enhancement:**
- Add `auto_init_dirs: bool = True` parameter to `download_sssp_library()` and `install_sssp_from_seed()`
  - Currently always `True` (implicit), but could be explicit for clarity
  - **Not required** - current behavior is correct

**RPC Handler Changes:**
- `_handle_download_sssp_library`: No changes needed
- **Optional:** Add `auto_init: bool = True` parameter (default True) to allow frontend to skip init if already done
  - **Not required** - `mkdir(parents=True, exist_ok=True)` is idempotent

**Frontend Hook Changes:**
- `usePseudoConfig.downloadLibrary()`: Add optional `enableIfDisabled: boolean = false` parameter
  - If `true` and `allow_download === false`, call `updateConfig({ allow_download: true })` first, then download
- `usePseudoConfig.downloadAll()`: Same enhancement

#### 4. Edge Cases

**Offline Mode:**
- If network unavailable and `allow_download === true`, show error: "Network unavailable. Use 'Install from Local Archives' instead."
- Guide user to seed_dir workflow

**Directories Missing:**
- Auto-create on first download/install attempt
- If creation fails (permissions), show error: "Cannot create store directory. Check permissions or set a different path."
- Validation should check writability proactively

**Partial Installs:**
- If download fails mid-way, `library/` may exist but be incomplete
- `list_installed_sssp()` only reports installed if `len(upf_files) > 0`, so partial installs won't show as "installed"
- On retry, `download_sssp_library()` checks `if library_path.exists() and len(upf_files) > 0`, returns success with warning
- **Enhancement:** Add "Repair" or "Re-download" option for partial installs

**Corrupted Archives:**
- Download verifies SHA256 before extraction (line 896-902, 917-923 in `pseudo_config.py`)
- If verification fails, download stops, no extraction
- Seed install doesn't verify checksums (could add optional verification)
- **Enhancement:** Add checksum verification to `install_sssp_from_seed()` if manifest.json available in seed

**Permission Errors:**
- `mkdir()` and file writes will raise exceptions
- Caught in try/except blocks, returned as errors in result dict
- UI shows error message
- **No changes needed** - error handling is adequate

**Seed Directory Empty:**
- "Install from Local Archives" button should be disabled or show "No archives found in seed directory"
- Scan seed_dir on Settings panel load, show available libraries
- **Enhancement:** Add `list_available_seed_libraries()` function to scan seed_dir

#### 5. Test Checklist

**Online Download Flow:**
- [ ] Toggle OFF → Click Download → Shows "Enable & Download" prompt → Confirms → Toggle becomes ON, download starts
- [ ] Toggle ON → Click Download → Direct download starts
- [ ] Download with store_dir missing → Auto-creates directories → Downloads successfully
- [ ] Download with network error → Shows error, suggests offline install
- [ ] Download already-installed library → Shows warning "Already installed", no re-download
- [ ] Download completes → Library appears in "Installed Libraries" immediately
- [ ] Download partial (interrupt) → Retry shows "Already installed" (if any UPF files exist)

**Offline Install Flow:**
- [ ] Seed dir empty → "Install from Local Archives" button disabled or shows "No archives found"
- [ ] Seed dir has archives → Button enabled, shows available libraries
- [ ] Install with store_dir missing → Auto-creates directories → Extracts successfully
- [ ] Install already-installed library → Shows warning or skips
- [ ] Install completes → Library appears in "Installed Libraries" immediately
- [ ] Install with corrupted archive → Shows error, doesn't create partial install

**Directory Management:**
- [ ] Settings panel load with store_dir missing → Auto-creates silently (or shows validation warning)
- [ ] Validation shows directory not writable → Error message, suggests fix
- [ ] User changes store_dir path → Validation runs, shows status
- [ ] "Initialize Dirs" removed/hidden → No user action needed, directories created automatically

**State Persistence:**
- [ ] Toggle "Allow Network Downloads" → Saves to config.json immediately
- [ ] Change store_dir/seed_dir → "Apply Changes" saves, or auto-save on blur
- [ ] Restart app → Settings restored from config.json

**UI Responsiveness:**
- [ ] Download in progress → Buttons disabled, shows "Downloading..." message
- [ ] Multiple download clicks → Prevented by `downloadInFlightRef` guard
- [ ] Install in progress → Buttons disabled, shows "Installing..." message

---

## Summary

**Current Flow Issues:**
1. "Initialize Dirs" is redundant (directories auto-created by download/install)
2. Multi-step process: Toggle → Init → Download (only Toggle → Download needed)
3. "Install from Seed" purpose unclear (offline vs online distinction not obvious)

**Proposed Simplification:**
1. Remove/hide "Initialize Dirs" (auto-create on demand)
2. Combine "Enable Downloads" + "Download" into single action when toggle is off
3. Rename/clarify "Install from Seed" as "Install from Local Archives" with clear offline purpose
4. Auto-create directories silently (no user action required)

**Backend Changes:** None required (already auto-creates directories)

**Frontend Changes:** 
- Modify download button behavior when toggle is off
- Rename "Install from Seed" button
- Hide/remove "Initialize Dirs" or move to advanced section
- Add seed library scanning/display

**Architecture Preserved:**
- PseudoConfig structure unchanged
- allow_download flag unchanged
- Directory layout unchanged
- Resolution flow unchanged

