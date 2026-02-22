# Library Manager Unit-Based Architecture - Design Document

## 1. Variant Key Derivation Rules

### SSSP
**Fields available**: `library_name`, `library_version`, `xc`, `quality`, `type`, `relativistic`

**Variant Key Formula**:
```
variant_key = f"{xc.lower()}-{quality}"
```

**Examples**:
- `pbe-precision` (xc="pbe", quality="precision")
- `pbe-efficiency` (xc="pbe", quality="efficiency")
- `lda-precision` (xc="lda", quality="precision")

**Rationale**: 
- SSSP uses `quality` as the primary differentiator (precision vs efficiency)
- `xc` is typically "pbe" but could vary
- `type` and `relativistic` are usually consistent for SSSP, so not needed in variant_key
- Lowercase for filesystem compatibility

### PseudoDojo
**Fields available**: `library_name`, `library_version`, `xc`, `type`, `relativistic`, `quality` (may be optional)

**Variant Key Formula**:
```
parts = []
if xc: parts.append(xc.lower())
if type: parts.append(type.lower())
if relativistic: parts.append(relativistic.lower())
if quality: parts.append(quality.lower())
variant_key = "-".join(parts) if parts else "default"
```

**Examples**:
- `pbe-nc-fr-04` (xc="pbe", type="nc", relativistic="fr", quality="04")
- `pbe-nc-sr` (xc="pbe", type="nc", relativistic="sr")
- `pbe-standard` (xc="pbe", quality="standard")

**Rationale**:
- PseudoDojo has more variable metadata
- Combine all relevant fields
- Use "default" if no distinguishing fields

### GIPAW
**Fields available**: `library_name`, `library_version`, `xc`, `type`, `relativistic`

**Variant Key Formula**:
```
parts = []
if xc: parts.append(xc.lower())
if type: parts.append(type.lower())
variant_key = "-".join(parts) if parts else "default"
```

**Examples**:
- `pbe-default` (xc="pbe")
- `lda-standard` (xc="lda", type="standard")

**Rationale**:
- GIPAW typically has simpler structure
- Use xc and type if available

### Generic Fallback
For any library not explicitly handled:
```
parts = []
if xc: parts.append(xc.lower())
if quality: parts.append(quality.lower())
if type: parts.append(type.lower())
variant_key = "-".join(parts) if parts else "default"
```

## 2. MANIFEST_PSEUDO_SEED.json → InstallableUnit Mapping

### Manifest Structure (from pseudo_provenance.py and pseudo_config.py)
Each entry in `manifest["files"]` has:
```json
{
  "relative_path": "SSSP_1.3.0_PBE_precision.tar.gz",
  "size_bytes": 12345678,
  "sha256": "abc123...",
  "category": "sssp",
  "library_name": "sssp",
  "library_version": "1.3.0",
  "xc": "pbe",
  "quality": "precision",
  "type": "nc",  // optional
  "relativistic": "sr"  // optional
}
```

### InstallableUnit Mapping
```python
InstallableUnit(
    unit_id=entry["sha256"],  # Use sha256 as unique identifier
    library_name=entry["library_name"].lower(),  # Normalize to lowercase
    version=entry["library_version"],
    variant_key=derive_variant_key(entry),  # See derivation rules above
    archive_filename=Path(entry["relative_path"]).name,  # Extract filename
    archive_sha256=entry["sha256"],
    size_bytes=entry.get("size_bytes", 0),
    metadata={
        "category": entry.get("category"),
        "xc": entry.get("xc"),
        "quality": entry.get("quality"),
        "type": entry.get("type"),
        "relativistic": entry.get("relativistic"),
        "relative_path": entry["relative_path"],
    }
)
```

### Filtering Rules
- **Only archive files**: Include entries where `relative_path` ends with `.tar.gz`, `.tgz`, `.tar`, or `.zip`
- **Exclude JSON files**: Skip entries ending with `.json` (these are cutoffs/metadata, not installable units)

## 3. Canonical Install Path

### Path Formula
```
<store_dir>/<library_name>/<version>/<variant_key>/library/*.upf
```

### Examples
- SSSP: `temp/pseudo/sssp/1.3.0/pbe-precision/library/*.upf`
- SSSP: `temp/pseudo/sssp/1.3.0/pbe-efficiency/library/*.upf`
- PseudoDojo: `temp/pseudo/pseudo-dojo/nc-fr-04/pbe-nc-fr-04/library/*.upf`
- GIPAW: `temp/pseudo/gipaw/2017/pbe-default/library/*.upf`

### Implementation
```python
def get_unit_install_path(unit: InstallableUnit, store_dir: Path) -> Path:
    """Compute canonical install path for a unit."""
    return store_dir / unit.library_name / unit.version / unit.variant_key / "library"
```

## 4. Files to Modify

### Backend Core
1. **`src/qmatsuite/core/library_manager.py`** (Complete rewrite)
   - Remove: `LibraryMetadata`, `LibraryVariantStatus`, `LibraryStatus`
   - Add: `InstallableUnit`, `UnitStatus`, `LibraryGroup`
   - Add: `load_installable_units()` - parse vendored manifest
   - Add: `derive_variant_key()` - library-specific variant key derivation
   - Add: `get_unit_install_path()` - compute canonical path
   - Add: `is_unit_installed()` - filesystem detection
   - Add: `get_supported_libraries()` - group units by library_name
   - Add: `get_library_status()` - return LibraryGroup with unit statuses
   - Rewrite: `install_units(unit_ids, source)` - unit-based install
   - Rewrite: `remove_units(unit_ids)` - unit-based remove
   - Rewrite: `repair_units(unit_ids)` - unit-based repair
   - Remove: All variant-based logic

2. **`src/qmatsuite/core/pseudo_config.py`** (Keep for download helpers)
   - Keep: `download_github_release_asset()` - used by install_units
   - Keep: `compute_sha256()` - used for verification
   - Remove/Deprecate: `download_sssp_library()`, `download_all_sssp()` - no longer used
   - Remove/Deprecate: `install_sssp_from_seed()`, `install_all_sssp_from_seed()` - no longer used
   - Keep: `import_seed_archives()` - may be used for local archive import

3. **`src/qmatsuite/core/pseudo_libinfo.py`** (No changes)
   - Already loads vendored manifest correctly
   - Just needs to be imported and used

### RPC Layer
4. **`src/qmatsuite/daemon/server.py`** (RPC handler updates)
   - Update: `_handle_list_libraries()` - return LibraryGroup[]
   - Update: `_handle_get_library_status()` - return LibraryGroup
   - Rewrite: `_handle_install_library()` → `_handle_install_units()` - take unit_ids
   - Rewrite: `_handle_remove_library()` → `_handle_remove_units()` - take unit_ids
   - Rewrite: `_handle_repair_library()` → `_handle_repair_units()` - take unit_ids
   - Remove: All variant-based RPC handlers

### Frontend Hook
5. **`gui/src/hooks/useLibraryManager.ts`** (Complete rewrite)
   - Remove: `LibraryMetadata`, `LibraryStatus`, `LibraryVariantStatus` types
   - Add: `InstallableUnit`, `UnitStatus`, `LibraryGroup` types
   - Rewrite: `loadLibraries()` - load LibraryGroup[] with units
   - Rewrite: `loadLibraryStatus()` - return LibraryGroup with unit statuses
   - Rewrite: `installLibrary()` → `installUnits(unitIds, source)`
   - Rewrite: `removeLibrary()` → `removeUnits(unitIds)`
   - Rewrite: `repairLibrary()` → `repairUnits(unitIds)`
   - Update: State management to work with LibraryGroup[]

### Frontend UI
6. **`gui/src/components/panels/LibrariesPanel.tsx`** (Major refactor)
   - Remove: Variant chips display
   - Add: Unit list under each library
   - Update: Install modal to show units, not variants
   - Update: Filter tabs to work with units
   - Update: Visual states for units (installed/available/broken)
   - Add: Unit row display with metadata (xc, quality, type, size)
   - Update: Summary bar to show "Installed X / Y units"

7. **`gui/src/components/panels/SettingsPanel.css`** (Style updates)
   - Add: `.library-unit-row` styles
   - Add: `.unit-status-badge` styles
   - Update: Filter tab styles if needed
   - Add: Unit metadata display styles

## 5. Implementation Order

### Phase 1: Backend Model + Detection
1. Define `InstallableUnit`, `UnitStatus`, `LibraryGroup` dataclasses
2. Implement `load_installable_units()` - parse vendored manifest
3. Implement `derive_variant_key()` - library-specific rules
4. Implement `get_unit_install_path()` - canonical path computation
5. Implement `is_unit_installed()` - filesystem detection
6. Implement `get_supported_libraries()` - group units by library_name
7. Implement `get_library_status()` - return LibraryGroup with statuses

### Phase 2: Install/Remove/Repair
8. Implement `install_units()` - download, verify, extract
9. Implement `remove_units()` - delete canonical directories
10. Implement `repair_units()` - re-extract from seed cache
11. Implement seed cache management (save archives, never extract)

### Phase 3: RPC Layer
12. Update RPC handlers to use unit-based APIs
13. Update RPC payloads (unit_ids instead of variants)

### Phase 4: Frontend Hook
14. Rewrite TypeScript types
15. Rewrite hook to work with LibraryGroup[]
16. Update state management

### Phase 5: Frontend UI
17. Refactor LibrariesPanel to show units
18. Update install modal
19. Update visual states and filtering
20. Add unit metadata display

## 6. Open Questions / Clarifications Needed

1. **Manifest Structure**: Confirm that manifest entries have all fields (type, relativistic) or if some are optional
2. **Unit ID**: Confirm sha256 is sufficient as unit_id, or if we need composite key
3. **Seed Cache Structure**: Confirm `<seed_dir>/<library_name>/<version>/<archive_filename>` is correct
4. **Archive Extraction**: Confirm archives extract directly to `library/` subdirectory, or if they have internal structure
5. **Cutoffs JSON**: How should cutoffs.json be handled? Same unit or separate?

## 7. Testing Strategy

1. **Unit Tests**:
   - Variant key derivation for SSSP, PseudoDojo, GIPAW
   - Path computation correctness
   - Install detection logic
   - Manifest parsing

2. **Integration Tests**:
   - Install unit from GitHub
   - Install unit from seed cache
   - Remove unit
   - Repair unit
   - Status detection after operations

3. **Manual Tests**:
   - UI displays units correctly
   - Install/remove/repair work end-to-end
   - Filter tabs work
   - Visual states are correct

