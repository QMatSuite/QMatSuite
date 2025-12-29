# Pseudo Selection v2 - Phase 0: Code Mapping

## Current Implementation Analysis

### 1. UI Components (Frontend)

**Main Component**: `gui/src/components/common_cards/CommonCardPseudo.tsx`
- **Lines 383-412**: Library dropdown selector
  - Options: "internal", "precision", "efficiency"
  - Shows installation status for SSSP variants
- **Lines 420-528**: Pseudopotential File dropdown per element
  - Groups candidates by source (internal, sssp_precision, sssp_efficiency, project)
  - Shows filename only
  - Displays source badge after selection

**Modal Integration**: `gui/src/components/panels/CalculationListPanel.tsx`
- **Lines 1138-1209**: "Edit Pseudopotentials" modal
  - Wraps `CommonCardPseudo` component
  - Calls `updateCalculationSpeciesMap` on Apply

**Data Model** (from CommonCardPseudo.tsx):
```typescript
interface PseudoMapping {
  species: string[];
  mapping: Record<string, string>;  // element -> filename
  candidates_by_element?: Record<string, Array<{
    filename: string;
    source: 'internal' | 'sssp_precision' | 'sssp_efficiency' | 'project';
    path?: string | null;
  }>>;
  resolved_by_element?: Record<string, {
    filename: string;
    source: 'internal' | 'sssp_precision' | 'sssp_efficiency' | 'project' | null;
    resolved: boolean;
    in_project?: boolean;
  }>;
}
```

### 2. Backend RPC/API

**RPC Handler**: `src/quantumvitas/daemon/server.py`
- **Line 3330**: `_handle_get_calculation_pseudo_mapping()`
  - Returns mapping with candidates_by_element
- **Line 3356**: `_handle_update_calculation_species_map()`
  - Updates species_map in calculation.yaml

**Service Layer**: `src/quantumvitas/api.py`
- **Line 4963**: `get_calculation_pseudo_mapping()`
  - Builds candidates_by_element by scanning:
    1. Internal: `resources/pseudo/*.UPF`
    2. SSSP Precision: `store_dir/sssp/1.3.0/precision/library/*.UPF`
    3. SSSP Efficiency: `store_dir/sssp/1.3.0/efficiency/library/*.UPF`
    4. Project: `project_root/pseudo/*.UPF`
  - **Lines 5101-5172**: Candidate building logic
    - Matches by filename prefix (element symbol)
    - Deduplicates by filename (not SHA256)
    - No provenance information

**Provenance Resolution**: Already exists
- `src/quantumvitas/api.py` line 4099: `resolve_pseudo_provenance()`
- `src/quantumvitas/daemon/server.py` line 1200: `_handle_resolve_project_pseudo_provenance()`
- Uses `pseudo_provenance.py` which loads vendored `pseudo_libinfo` bundle

### 3. Settings Installation Code

**Settings UI**: `gui/src/components/panels/SettingsPanel.tsx`
- **Line 709**: `PseudopotentialsSection` component
- Uses `usePseudoConfig` hook

**Backend Installation**: `src/quantumvitas/core/pseudo_config.py`
- **Line 957**: `download_sssp_library()`
  - Fetches manifest from GitHub at runtime
  - Downloads archives to seed cache
  - Extracts to `store_dir/sssp/1.3.0/{flavor}/library/`
  - Verifies SHA256
- **Line 356**: `get_sssp_library_path()` - hardcoded path structure
- **Line 374**: `list_installed_sssp()` - checks for UPF files in hardcoded paths

**Installation Paths**:
- Store: `<store_dir>/sssp/1.3.0/{flavor}/library/*.UPF`
- Seed: `<seed_dir>/sssp/1.3.0/{flavor}/*.tar.gz`

**Validation**:
- SHA256 verification during download
- File existence check for installed detection

### 4. Pseudo Libinfo Bundle

**Loader**: `src/quantumvitas/core/pseudo_libinfo.py`
- **Line 114**: `load_pseudo_libinfo_bundle()`
  - Loads from `resources/pseudo_libinfo/<tag>/`
  - Verifies SHA256SUMS.txt
  - Returns bundle with `index` and `manifest` dicts
  - Already cached with `@lru_cache(maxsize=1)`

**Provenance**: `src/quantumvitas/core/pseudo_provenance.py`
- **Line 253**: `resolve_pseudo_provenance()`
  - Builds occurrences index from bundle
  - Matches by SHA256 (primary) or sha_token (fallback)
  - Returns `PseudoProvenanceResult` with matches

## Files to Modify

### Phase 1: Backend Archive Management

1. **`src/quantumvitas/core/pseudo_installs.py`** (NEW)
   - `get_pseudo_install_root()` - get install root from config
   - `list_installed_archives()` - scan archives directory
   - `is_archive_installed(asset_name, expected_sha256)` - verify installation
   - `install_archive(asset_url, asset_name, expected_sha256)` - download & verify

2. **`src/quantumvitas/daemon/server.py`**
   - Add `_handle_list_pseudo_archives_status()` RPC
   - Add `_handle_install_pseudo_archive()` RPC

3. **`gui/src/hooks/usePseudoConfig.ts`** (or new hook)
   - Add functions to call new RPCs

4. **`gui/src/components/panels/SettingsPanel.tsx`** (or LibrariesPanel.tsx)
   - Replace SSSP-specific UI with generic archives table
   - Show archives from manifest, grouped by library
   - Show install status per archive

### Phase 2: Provenance Tags

1. **`src/quantumvitas/core/pseudo_libinfo.py`** (or new module)
   - Add `build_provenance_indices()` - build sha256->occurrences mapping
   - Add `get_archive_install_status()` - check if archive is installed

2. **`src/quantumvitas/api.py`**
   - Add `get_pseudo_options_for_element(element)` method
   - Returns deduplicated options with provenance tags

3. **`src/quantumvitas/daemon/server.py`**
   - Add `_handle_get_pseudo_options_for_element()` RPC handler

### Phase 3: UI Replacement

1. **`gui/src/components/common_cards/CommonCardPseudo.tsx`**
   - Remove Library dropdown (lines 383-412)
   - Replace Pseudopotential File dropdown (lines 452-498) with:
     - Custom dropdown showing basename + tags
     - Tags show provenance (blue=installed, gray=not installed)
   - Update data model to use sha256-based selection

2. **`gui/src/components/common_cards/CommonCardPseudo.css`**
   - Add styles for tag chips
   - Add styles for custom dropdown option renderer

3. **`gui/src/hooks/usePseudoConfig.ts`** (or new hook)
   - Add `getPseudoOptionsForElement(element)` function

4. **`src/quantumvitas/api.py`**
   - Update `update_calculation_species_map()` to accept sha256 (backward compatible)

### Phase 4: Tests

1. **`tests/unit/test_pseudo_installs.py`** (NEW)
   - Test archive install/status logic

2. **`tests/unit/test_pseudo_options.py`** (NEW)
   - Test options generation
   - Test deduplication by SHA256
   - Test tag generation

## Key Observations

1. **Current candidate building** (api.py:5101-5172):
   - Only uses filename matching (element prefix)
   - No SHA256 deduplication
   - No provenance information
   - Hardcoded SSSP paths

2. **Provenance system exists** but not used for selection:
   - `resolve_pseudo_provenance()` works on individual files
   - Need to reverse: element -> all options with provenance

3. **Installation detection**:
   - Currently hardcoded SSSP paths
   - Need generic archive-based detection

4. **Data model**:
   - Currently stores filename only
   - Need to store sha256 + basename
   - Backward compatibility: resolve old filename to sha256

## Implementation Strategy

1. **Phase 1**: Build generic archive management (independent of UI)
2. **Phase 2**: Build provenance tag system (independent of UI)
3. **Phase 3**: Replace UI to use new systems
4. **Phase 4**: Add tests

This allows incremental development and testing at each phase.

