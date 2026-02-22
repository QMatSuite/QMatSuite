# Pseudo Selection v2 - Phase 1 Implementation Plan

## Phase A: Code Mapping Summary

### Current Implementation Analysis

#### 1. UI Component: `CommonCardPseudo.tsx`
- **Location**: `gui/src/components/common_cards/CommonCardPseudo.tsx`
- **Current Structure**:
  - **Lines 383-412**: Library dropdown selector
    - Options: "internal", "precision", "efficiency"
    - Shows installation status for SSSP variants
  - **Lines 420-528**: Pseudopotential File dropdown per element
    - Groups candidates by source (internal, sssp_precision, sssp_efficiency, project)
    - Shows filename only (no SHA256 deduplication)
    - Displays source badge after selection
- **Data Model**:
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

#### 2. Backend API: `get_calculation_pseudo_mapping()`
- **Location**: `src/qmatsuite/api.py` lines 4963-5246
- **Current Logic**:
  - Builds candidates by scanning filesystem:
    1. Internal: `resources/pseudo/*.UPF`
    2. SSSP Precision: `store_dir/sssp/1.3.0/precision/library/*.UPF` (hardcoded)
    3. SSSP Efficiency: `store_dir/sssp/1.3.0/efficiency/library/*.UPF` (hardcoded)
    4. Project: `project_root/pseudo/*.UPF`
  - **Lines 5101-5172**: Candidate building
    - Matches by filename prefix (element symbol)
    - Deduplicates by filename (NOT SHA256)
    - No provenance information
    - Hardcoded SSSP paths

#### 3. Backend API: `update_calculation_species_map()`
- **Location**: `src/qmatsuite/api.py` lines 5259-5299
- **Current Logic**:
  - Accepts `species_map: Dict[str, Dict[str, Any]]`
  - Stores `{pseudopot: filename, mass?: float}` per element
  - No SHA256 support yet

#### 4. RPC Handlers
- **Location**: `src/qmatsuite/daemon/server.py`
- **Registration**: Lines 209-322 in `_handlers` dict
- **Current Handlers**:
  - `get_calculation_pseudo_mapping` (line 293) → `_handle_get_calculation_pseudo_mapping` (line 3330)
  - `update_calculation_species_map` (line 294) → `_handle_update_calculation_species_map` (line 3356)

#### 5. Provenance System (Already Exists)
- **Location**: `src/qmatsuite/core/pseudo_provenance.py`
- **Functions**:
  - `resolve_pseudo_provenance(path)` - resolves single file by SHA256/sha_token
  - `_build_occurrences_index(bundle)` - builds sha256 → occurrences mapping
  - Uses vendored `pseudo_libinfo` bundle
- **Not Currently Used**: For selection UI (only used for individual file resolution)

#### 6. Archive Management (New - Already Created)
- **Location**: `src/qmatsuite/core/pseudo_installs.py`
- **Functions Available**:
  - `load_manifest_archives()` - loads from vendored manifest
  - `check_archives_status()` - checks install status
  - `install_archive()` - downloads and installs archive
  - `is_archive_installed()` - verifies by SHA256

## Design Mapping

### Phase B: Generic Archive Status RPC + Settings UI

**RPC Handlers to Add**:
1. `list_pseudo_archives_status`
   - Returns: `List[ArchiveStatus]` with install status
   - Uses: `pseudo_installs.load_manifest_archives()` + `check_archives_status()`

2. `install_pseudo_archive`
   - Input: `asset_name: str`
   - Uses: `pseudo_installs.load_manifest_archives()` to find archive
   - Calls: `pseudo_installs.install_archive()` with upstream_url, sha256, size_bytes
   - Returns: `{success, messages[], errors[], archive_status?}`

**Settings UI Changes**:
- Replace SSSP-only UI in `SettingsPanel.tsx` (or subcomponent)
- Show generic "Pseudopotential Archives" table:
  - Group by `library_name` + `library_version` (collapsible)
  - Each row: name, metadata (xc/quality/type/relativistic), size, installed flag
  - Actions: Install, Verify (optional), Reveal (optional)

### Phase C: Pseudo Options API

**New Backend Method**: `get_pseudo_options_for_elements()`
- **Location**: `src/qmatsuite/api.py`
- **Input**: `project_root, elements: List[str]`
- **Output**: `Dict[str, List[PseudoOption]]` (element → options)

**PseudoOption Structure**:
```python
{
  "sha256": str,  # Primary identity
  "sha_token": str,
  "element": str,
  "display_basename": str,  # Primary basename
  "all_basenames": List[str],
  "sources": List[{
    "kind": "project" | "internal" | "library",
    "label": str,  # e.g., "SSSP 1.3.0 PBE efficiency"
    "installed": bool,
    "archive_asset": Optional[str],  # For library sources
  }],
  "availability": {"any_installed": bool}
}
```

**Data Sources**:
1. **Library chips**: From `PSEUDO_FILE_INDEX.json` occurrences (by sha256)
   - Use `_build_occurrences_index()` from `pseudo_provenance.py`
   - For each occurrence, check if archive is installed via `pseudo_installs.is_archive_installed()`
2. **Project pseudos**: Scan `project_root/pseudo/*.UPF`
   - Compute sha256 + sha_token
   - Parse element
   - If sha256 matches index → add "Project" chip to existing option
   - Otherwise → create "Project-only" option
3. **Internal pseudos**: Scan `resources/pseudo/*.UPF`
   - Similar to project pseudos
   - Always "installed" (in repo)

**RPC Handler**: `get_pseudo_options_for_calculation`
- Input: `project_root, calculation` (derives elements from structure)
- Returns: Options grouped by element

### Phase D: UI Replacement

**CommonCardPseudo.tsx Changes**:
1. **Remove**: Library dropdown (lines 383-412)
2. **Replace**: Pseudopotential File dropdown (lines 452-498)
   - Single dropdown per element
   - Options from new RPC
   - Left: `display_basename`
   - Right: Source chips (blue=installed, gray=not installed)
3. **Sorting**:
   - Options with Project chip first
   - Then options with any installed chip
   - Then the rest
4. **Collision Handling**:
   - If same `display_basename` appears multiple times, append `· <sha256[:8]>` in dropdown
5. **Selection Payload**:
   - Update `updateCalculationSpeciesMap` to send sha256 + basename
   - Backward compatible: keep filename for now

### Phase E: Tests

**Unit Tests to Add**:
1. `test_get_pseudo_options_for_elements`:
   - Dedup by sha256
   - Same sha256 produces multiple library chips
   - Installed chip reflects archive status
   - Name collision: two distinct sha256 with same basename → two options
   - Project/internal injection: project pseudo matching library sha256 adds chip (not new option)
   - RPC roundtrip returns stable JSON schema

## Implementation Order

1. **Phase B**: RPC handlers + Settings UI (generic archives)
2. **Phase C**: Pseudo options API (sha256-dedup + chips)
3. **Phase D**: UI replacement (single dropdown)
4. **Phase E**: Tests

## Key Constraints

- **No runtime network**: All manifest/index data from vendored bundle
- **SHA256 verification**: All "installed" status must verify SHA256
- **No hardcoded SSSP paths**: Use manifest-driven approach
- **Backward compatibility**: Keep filename mapping for now, add sha256 alongside

