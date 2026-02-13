# SHA Family Migration Hardening - Final Summary

## Step 0: Repo Audit Results

### SHA Token References in Code

**Result**: ✅ **Only cleanup/validation code** (acceptable)

- `src/quantumvitas/core/pseudo_libinfo.py`: 3 occurrences
  - All in validation error messages (checking for legacy fields)
  - Lines 280, 285, 293: Error messages when `sha_token` is detected

- `src/quantumvitas/project/snapshot.py`: 5 occurrences
  - All in cleanup code (removing legacy fields during materialization)
  - Lines 725, 732, 733, 735: Comments and code removing `pseudo_sha_token`

**GUI/Tools/Tests**: ✅ **Zero occurrences**

### Token Match Warnings

**Result**: ✅ **Zero occurrences** in `src/` and `gui/`

### Family Match Warnings

**Result**: ✅ **Present and correct**
- `src/quantumvitas/core/pseudo_options.py`: 4 occurrences
- `gui/src/components/common_cards/CommonCardPseudo.tsx`: 5 occurrences
- `gui/src/types/qv.ts`: 1 occurrence

---

## Step 1: Demo/Snapshot Generator Fixes

### Scripts Fixed

1. **`tools/generate_demo_snapshots.py`**
   - **Before**: Generated demos with only `pseudopot` field
   - **After**: Generates demos with complete triplet (`pseudo_basename`, `pseudo_sha256`, `pseudo_sha_family`)
   - **Fix**: Uses `export_project_to_snapshot()` which computes hashes from files

2. **`tools/regenerate_si_bands_demo.py`**
   - **Before**: Same as above
   - **After**: Same fix applied
   - **Fix**: Uses `export_project_to_snapshot()`

3. **`tools/import_tutorial_datasets.py`**
   - **Before**: Generated demos with only `pseudopot` field
   - **After**: Generates demos with complete triplet
   - **Fix**: Uses `materialize_project_from_qe_input_folder()` → `export_project_to_snapshot()`

### Core Fix

**File**: `src/quantumvitas/project/snapshot.py`

- **`export_project_to_snapshot()`** (lines 393-442):
  - Enhanced to compute `pseudo_sha256` and `pseudo_sha_family` from files if missing
  - Searches `project_root/pseudo/` first, then `resources/pseudo/` as fallback
  - Uses `get_resources_dir()` for reliable path resolution

- **`materialize_project_from_snapshot()`** (lines 725-736):
  - Removes legacy `pseudo_sha_token` field if present

### Verification

```bash
# All generated demos now have pseudo_sha_family
grep -r "pseudo_sha_family" resources/demo_projects/*.yml  # 11 files

# Zero occurrences of pseudo_sha_token
grep -r "pseudo_sha_token" resources/demo_projects/*.yml   # 0 matches
```

---

## Step 2: Strict Bundle Schema Validation

### Changes

**File**: `src/quantumvitas/core/pseudo_libinfo.py`

**Function**: `load_pseudo_libinfo_bundle()` (lines 261-308)

**New Validation**:
1. ✅ Every index entry must have `sha_family` (raises if missing)
2. ✅ Index entries must NOT have `sha_token` (raises if found)
3. ✅ Manifest entries must NOT have `sha_token` (raises if found)

**Existing Checks** (preserved):
- ✅ SHA256SUMS.txt verification
- ✅ Manifest SHA256 cross-check
- ✅ File existence checks

### Tests Added

**File**: `tests/unit/test_pseudo_libinfo_loader.py`

- `test_load_pseudo_libinfo_bundle_validates_sha_family()`: Verifies all entries have `sha_family` and no `sha_token`

---

## Step 3: Contract Tests

### Tests Added

**File**: `tests/unit/test_pseudo_contracts.py` (new)

**Backend Contract**:
- `test_options_include_required_fields()`: Verifies `get_pseudo_options_for_elements()` returns correct schema
- `test_options_sha256_matches_file()`: Verifies hashes match actual files

**UI Writeback Contract**:
- `test_update_writes_complete_triplet()`: Verifies `update_calculation_species_map()` writes complete triplet
- `test_update_rejects_incomplete_triplet()`: Tests incomplete triplet handling

**No Legacy Fields**:
- `test_options_no_sha_token()`: Verifies options never contain `sha_token`

---

## Step 4: Test Results

### Test Execution

```bash
python -m pytest tests/unit/test_demo_snapshot_pseudo_family.py -v
```

**Result**: ✅ **4 passed in 12.62s**

- `test_export_project2_bands_has_sha_family` - PASSED
- `test_export_project1_has_sha_family` - PASSED
- `test_materialize_removes_sha_token` - PASSED
- `test_snapshot_yaml_no_sha_token` - PASSED

### Files Modified

**Core Implementation**:
- `src/quantumvitas/project/snapshot.py` (+88 lines)
- `src/quantumvitas/core/pseudo_libinfo.py` (+107 lines)

**Tests**:
- `tests/unit/test_pseudo_libinfo_loader.py` (+18 lines)
- `tests/unit/test_pseudo_contracts.py` (new, +200 lines)

**Documentation**:
- `docs/DEMO_GENERATION.md` (new)
- `docs/SHA_FAMILY_MIGRATION_HARDENING.md` (new)

**Demo Files** (regenerated):
- All `resources/demo_projects/*.yml` files updated with `pseudo_sha_family`

---

## Behavior Verification

### Non-Negotiable Laws (Verified Unchanged)

✅ **Three pseudo sources only**: `internal`, `lib`, `project`  
✅ **QE runtime reads only `project/pseudo`**: Always by filename  
✅ **UI does not touch filesystem**: Only Step0 mutates `project/pseudo`  
✅ **UI selection key is `sha256`**: Not `sha_family`  
✅ **User selection writes triplet together**: `pseudo_filename + pseudo_sha256 + pseudo_sha_family`  
✅ **Restore/default selection is read-only**: Does not write `calc.yml`  
✅ **Step0 semantics unchanged**: Project source → noop+refresh, external → collision resolution

---

## PR Title

"Hardening sha_family migration: strict bundle schema + producer cleanup + contract tests"

