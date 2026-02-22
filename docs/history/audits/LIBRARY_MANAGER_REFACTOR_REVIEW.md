# Library Manager Refactor - Code Review Summary

## Current Implementation vs Proposed Model

### 1. Core Model Differences

#### Current Model (Library-Centric)
- **Abstraction Level**: Library → Variants
  - `LibraryMetadata`: Hardcoded list with `id="sssp"`, `supported_variants=["precision", "efficiency"]`
  - `LibraryStatus`: Tracks which variants are installed
  - `LibraryVariantStatus`: Status per variant (precision/efficiency)

- **Installable Unit**: Treated as "SSSP precision" or "SSSP efficiency" (conceptual, not explicit)
- **Hardcoded Assumptions**:
  - Only SSSP library
  - Only version "1.3.0"
  - Only variants "precision" and "efficiency"
  - Fixed path structure: `<store_dir>/sssp/1.3.0/{variant}/library`

#### Proposed Model (Unit-Centric)
- **Abstraction Level**: Library → InstallableUnits
  - `InstallableUnit`: Each entry in MANIFEST_PSEUDO_SEED.json is a unit
  - Units grouped by `library_name` for display
  - Each unit has: `library_name`, `library_version`, `xc`, `quality`, `type`, `relativistic`, `sha256`, etc.
  - `unit_id`: Unique identifier (sha256 or composite)

- **Installable Unit**: Explicit - one archive file = one unit
- **Dynamic**: No hardcoded assumptions; all metadata comes from manifest

### 2. Source of Truth

#### Current Implementation
- **Status Detection**: Hardcoded filesystem checks
  - `_get_sssp_status()`: Directly checks `<store_dir>/sssp/1.3.0/{variant}/library/*.UPF`
  - Doesn't reference MANIFEST_PSEUDO_SEED.json for detection

- **Install Logic**: Fetches manifest from GitHub at runtime
  - `download_sssp_library()` calls `fetch_manifest()` from GitHub
  - Uses `select_sssp_entries()` to filter entries
  - Downloads and extracts selected entries

- **Vendored Manifest**: Exists but not used
  - `pseudo_libinfo.py` loads vendored `MANIFEST_PSEUDO_SEED.json`
  - But `library_manager.py` doesn't use it - fetches from GitHub instead

#### Proposed Model
- **Source of Truth**: Vendored `MANIFEST_PSEUDO_SEED.json`
  - Load from `pseudo_libinfo.load_pseudo_libinfo_bundle().manifest`
  - All available units come from this manifest
  - No runtime GitHub fetch for unit discovery

- **Status Detection**: Filesystem-based, but path computed from unit metadata
  - `get_unit_install_path(unit, store_dir)`: Computes path from unit fields
  - `is_unit_installed(unit, store_dir)`: Checks computed path for UPF files
  - No reliance on `manifest.json` in install directory

- **Install Logic**: Install by `unit_id`
  - `install_library(unit_ids, source)`: Takes list of unit IDs
  - Each unit installed independently
  - Path computed from unit metadata

### 3. Path Computation

#### Current Implementation
```python
# Hardcoded in get_sssp_library_path()
store_dir / "sssp" / version / flavor / "library"
# Example: <store_dir>/sssp/1.3.0/precision/library
```

#### Proposed Model
```python
# Dynamic from unit metadata
def get_unit_install_path(unit: InstallableUnit, store_dir: Path) -> Path:
    if unit.library_name.upper() == "SSSP":
        return store_dir / "sssp" / unit.library_version / unit.quality / "library"
    else:
        # Other libraries: <store_dir>/{library_name}/{version}/library
        return store_dir / unit.library_name.lower() / unit.library_version / "library"
```

**Key Difference**: Path derived from unit metadata, not hardcoded

### 4. Install/Remove/Repair Operations

#### Current Implementation
- **Install**: `install_library(library_id, variants, source)`
  - Takes `variants=["precision", "efficiency"]`
  - Routes to `_install_sssp()` which calls `download_sssp_library(flavor=variant)`
  - Each variant is a separate download/install operation

- **Remove**: `remove_library(library_id, variants)`
  - Takes `variants=["precision"]`
  - Deletes `<store_dir>/sssp/1.3.0/{variant}/` directory

- **Repair**: `repair_library(library_id, variants)`
  - Re-extracts from seed cache for specified variants

#### Proposed Model
- **Install**: `install_library(unit_ids, source)`
  - Takes `unit_ids=["sha256_1", "sha256_2"]`
  - Each unit installed independently
  - Can install individual units, not just "all variants"

- **Remove**: `remove_library(unit_ids)`
  - Takes `unit_ids=["sha256_1"]`
  - Removes only those units' directories
  - More granular control

- **Repair**: `repair_library(unit_ids)`
  - Re-extracts specific units from seed cache

**Key Difference**: Operations work on individual units, not variants

### 5. UI Model

#### Current Implementation
- **Display**: Library cards with variant chips
  - Shows "SSSP" library
  - Variant chips: "precision ✓", "efficiency"
  - Install modal: Checkboxes for variants

- **Filter Tabs**: All | Installed | Available
  - Filters by library status (installed/partial/not_installed)

#### Proposed Model
- **Display**: Libraries grouped by `library_name`
  - Under each library, list `InstallableUnit` objects
  - Each unit shows: installed/available status, size, metadata (xc, quality, type, relativistic)
  - Install modal: Lists individual units, not just variants

- **Filter Tabs**: All | Installed | Available
  - Filters by unit status (installed/not_installed)

**Key Difference**: UI shows individual units, not just variants

### 6. Files That Will Need Changes

#### Backend (`src/qmatsuite/core/`)

1. **`library_manager.py`** (Major Refactor)
   - Replace `LibraryMetadata`, `LibraryVariantStatus`, `LibraryStatus` with `InstallableUnit`, `UnitStatus`, `LibraryGroup`
   - Add `load_installable_units()` to parse vendored manifest
   - Add `get_unit_install_path()` to compute paths from metadata
   - Add `is_unit_installed()` for filesystem detection
   - Rewrite `get_supported_libraries()` to group units by `library_name`
   - Rewrite `get_library_status()` to check unit status
   - Rewrite `install_library()` to take `unit_ids` instead of `variants`
   - Rewrite `remove_library()` to take `unit_ids`
   - Rewrite `repair_library()` to take `unit_ids`
   - Remove hardcoded SSSP logic

2. **`pseudo_config.py`** (Minor Changes)
   - Keep existing `download_sssp_library()` for backward compatibility
   - May need adapter functions to map unit_ids to existing install logic
   - `fetch_manifest()` and `select_sssp_entries()` may still be used for backward compat

3. **`pseudo_libinfo.py`** (No Changes)
   - Already loads vendored manifest
   - Just needs to be used by `library_manager.py`

#### Frontend (`gui/src/`)

1. **`hooks/useLibraryManager.ts`** (Major Refactor)
   - Change `LibraryMetadata` → `LibraryGroup` (with units)
   - Change `LibraryStatus` → `LibraryGroup` (with unit statuses)
   - Change `installLibrary(libraryId, variants)` → `installLibrary(unitIds)`
   - Change `removeLibrary(libraryId, variants)` → `removeLibrary(unitIds)`
   - Change `repairLibrary(libraryId, variants)` → `repairLibrary(unitIds)`

2. **`components/panels/LibrariesPanel.tsx`** (Major Refactor)
   - Change library cards to show units under each library
   - Change install modal to list units instead of variants
   - Update filtering logic to work with units
   - Update visual states (installed/available) for units

3. **`components/panels/SettingsPanel.css`** (Minor Changes)
   - May need styles for unit lists
   - Unit status indicators

#### RPC Handlers (`src/qmatsuite/daemon/server.py`)

1. **RPC Changes**
   - `list_libraries`: Return `LibraryGroup[]` instead of `LibraryMetadata[]`
   - `get_library_status`: Return `LibraryGroup` with unit statuses
   - `install_library`: Change payload from `{library_id, variants}` to `{unit_ids}`
   - `remove_library`: Change payload from `{library_id, variants}` to `{unit_ids}`
   - `repair_library`: Change payload from `{library_id, variants}` to `{unit_ids}`

### 7. Backward Compatibility Strategy

#### Current SSSP Install Logic
- `download_sssp_library()` in `pseudo_config.py` will remain
- Need adapter: Map unit_ids to variant-based install
  - For SSSP units: Extract `quality` field → use as `flavor`
  - Call existing `download_sssp_library(flavor=quality)`

#### Migration Path
1. Keep existing functions as internal helpers
2. New unit-based API wraps old variant-based API
3. Gradually migrate UI to unit-based model
4. Eventually deprecate variant-based API

### 8. Key Architectural Changes

#### Current: Variant-Based
```
Library (SSSP)
  ├── Variant (precision) → Install/Remove
  └── Variant (efficiency) → Install/Remove
```

#### Proposed: Unit-Based
```
Library (SSSP)
  ├── Unit (sha256_1: SSSP 1.3.0 PBE precision) → Install/Remove
  ├── Unit (sha256_2: SSSP 1.3.0 PBE efficiency) → Install/Remove
  └── Unit (sha256_3: SSSP 1.2.1 PBE precision) → Install/Remove
```

### 9. Benefits of Proposed Model

1. **Extensibility**: Easy to add new libraries (PseudoDojo, GIPAW, etc.) - just add to manifest
2. **Granularity**: Install individual units, not just "all variants"
3. **Version Support**: Can handle multiple versions (1.3.0, 1.2.1, etc.)
4. **Metadata Rich**: UI can show xc, type, relativistic info per unit
5. **Single Source of Truth**: Vendored manifest is authoritative
6. **No Hardcoding**: All paths and metadata come from manifest

### 10. Challenges

1. **Breaking Changes**: UI and RPC API changes
2. **Migration**: Need to map existing installs to unit_ids
3. **Complexity**: More granular model = more UI complexity
4. **Backward Compatibility**: Must keep existing SSSP install working

### 11. Detection Logic Comparison

#### Current Detection
```python
# Hardcoded check
lib_path = get_sssp_library_path(store_dir, "1.3.0", "precision")
library_path = lib_path / "library"
if library_path.exists() and has_upf_files(library_path):
    installed = True
```

#### Proposed Detection
```python
# Dynamic check from unit metadata
install_path = get_unit_install_path(unit, store_dir)
if install_path.exists() and has_upf_files(install_path):
    installed = True
```

**Key Difference**: Path computed from unit, not hardcoded

### 12. Summary of Refactor Scope

**High Impact Areas:**
- `library_manager.py`: Complete rewrite of core model
- `useLibraryManager.ts`: API changes
- `LibrariesPanel.tsx`: UI restructure
- RPC handlers: Payload changes

**Medium Impact Areas:**
- `pseudo_config.py`: Adapter functions for backward compat
- CSS: New unit list styles

**Low Impact Areas:**
- `pseudo_libinfo.py`: Already loads manifest, just needs to be used
- Other components: Minimal changes

**Estimated Complexity**: High - This is a significant architectural change that touches core data models, API contracts, and UI.

