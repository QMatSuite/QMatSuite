# SHA Family Migration Hardening Report

**Date**: Post-migration hardening pass  
**Scope**: Ensure zero remaining `sha_token` usage, strict schema validation, and regression-proof contracts  
**Status**: Complete

---

## Summary

This document summarizes the hardening pass performed after migrating from `sha_token` to `sha_family` for pseudopotential physical identity. The migration is intentionally **not backward compatible** - we do not support reading `pseudo_sha_token` anymore.

## Step 0: Repo Audit Results

### SHA Token References

**Code/Test/Tools**: ✅ **Zero occurrences** (except cleanup code)
- `src/quantumvitas/project/snapshot.py`: Only contains cleanup code (removes `pseudo_sha_token` during materialization)
- `tests/unit/test_demo_snapshot_pseudo_family.py`: Test file that verifies absence of `sha_token` (correct)

**Documentation**: Historical references only (acceptable if marked as historical)
- Multiple docs mention `sha_token` in historical context
- No active code references

### Token Match Warnings

**Result**: ✅ **Zero occurrences** in `src/` and `gui/`

### Family Match Warnings

**Result**: ✅ **Present and correct**
- `src/quantumvitas/core/pseudo_options.py`: 4 occurrences (correct)
- `gui/src/components/common_cards/CommonCardPseudo.tsx`: 5 occurrences (correct)
- `gui/src/types/qv.ts`: 1 occurrence (correct)

---

## Step 1: Demo/Snapshot Generator Fixes

### Identified Scripts

1. **`tools/generate_demo_snapshots.py`**
   - Generates `si_bands_demo.yml` and `si_dos_demo.yml` from test projects
   - **Status**: ✅ Fixed - uses `export_project_to_snapshot()` which computes `sha_family`

2. **`tools/regenerate_si_bands_demo.py`**
   - Regenerates `si_bands_demo.yml` only
   - **Status**: ✅ Fixed - uses `export_project_to_snapshot()` which computes `sha_family`

3. **`tools/import_tutorial_datasets.py`**
   - Generates demos from `tests/data/0_*` through `19_*` folders
   - **Status**: ✅ Fixed - uses `materialize_project_from_qe_input_folder()` → `export_project_to_snapshot()`

### Fixes Applied

**File**: `src/quantumvitas/project/snapshot.py`

1. **`export_project_to_snapshot()`** (lines 393-442):
   - Enhanced to compute `pseudo_sha256` and `pseudo_sha_family` from files if missing
   - Searches `project_root/pseudo/` first, then `resources/pseudo/` as fallback
   - Uses `get_resources_dir()` for reliable path resolution
   - Ensures complete triplet: `pseudo_basename`, `pseudo_sha256`, `pseudo_sha_family`

2. **`materialize_project_from_snapshot()`** (lines 725-736):
   - Removes legacy `pseudo_sha_token` field if present during materialization
   - Ensures clean output without legacy fields

### Verification

**Before Fix**:
- Generated demos had only `pseudopot` field
- Missing `pseudo_sha256` and `pseudo_sha_family`

**After Fix**:
- All generated demos include complete triplet
- Zero occurrences of `pseudo_sha_token` in generated files
- Verified with `grep -r "pseudo_sha_token" resources/demo_projects/` → 0 matches

### How to Reproduce

```bash
# Generate all demos
python tools/generate_demo_snapshots.py
python tools/regenerate_si_bands_demo.py
python tools/import_tutorial_datasets.py --clean

# Verify
grep -r "pseudo_sha_family" resources/demo_projects/*.yml
grep -r "pseudo_sha_token" resources/demo_projects/*.yml  # Should be empty
```

---

## Step 2: Strict Bundle Schema Validation

### Changes Applied

**File**: `src/quantumvitas/core/pseudo_libinfo.py`

**Function**: `load_pseudo_libinfo_bundle()` (lines 261-308)

**New Validation**:
1. **Index entries must have `sha_family`**:
   - Checks every file entry in `index["files"]`
   - Raises `RuntimeError` if `sha_family` is missing
   - Validates `sha_family` is a non-empty string

2. **Index entries must NOT have `sha_token`**:
   - Checks for `sha_token` or `pseudo_sha_token` in file entries
   - Raises `RuntimeError` if found

3. **Manifest validation**:
   - Checks top-level keys for legacy `sha_token` fields
   - Checks manifest entries (if present) for legacy fields

### Existing Checks (Preserved)

- ✅ SHA256SUMS.txt verification (strict)
- ✅ Manifest SHA256 cross-check (strict)
- ✅ File existence checks

### Tests Added

**File**: `tests/unit/test_pseudo_libinfo_loader.py`

1. **`test_load_pseudo_libinfo_bundle_validates_sha_family()`**:
   - Verifies all bundle entries have `sha_family`
   - Verifies no legacy `sha_token` fields
   - Validates `sha_family` is non-empty string

### Failure Cases (Hard Errors)

The loader will raise `RuntimeError` if:
- Any index entry is missing `sha_family` → "missing required 'sha_family' field"
- Any index entry contains `sha_token` → "contains legacy sha_token field"
- Any manifest entry contains `sha_token` → "contains legacy sha_token field"

---

## Step 3: Contract Tests

### Backend Contract Tests

**File**: `tests/unit/test_pseudo_contracts.py`

**Class**: `TestPseudoOptionsContract`

1. **`test_options_include_required_fields()`**:
   - Verifies `get_pseudo_options_for_elements()` returns variants with:
     - `sha256`, `sha_family`, `basename`, `element`, `sources`
     - `family_match_warnings` (can be empty list)
   - Verifies NO legacy fields: `sha_token`, `pseudo_sha_token`, `token_match_warnings`

2. **`test_options_sha256_matches_file()`**:
   - Verifies `sha256` and `sha_family` in variant match actual file hashes

### UI Writeback Contract Tests

**Class**: `TestUIWritebackContract`

1. **`test_update_writes_complete_triplet()`**:
   - Verifies `update_calculation_species_map()` writes complete triplet:
     - `pseudo_basename`, `pseudo_sha256`, `pseudo_sha_family`
   - Verifies NO legacy fields written

2. **`test_update_rejects_incomplete_triplet()`**:
   - Tests behavior when incomplete triplet is provided
   - Verifies legacy fields are never written

### No Legacy Fields Tests

**Class**: `TestNoLegacyFields`

1. **`test_options_no_sha_token()`**:
   - Verifies options never contain `sha_token` in any form
   - Checks serialized JSON to catch hidden fields

---

## Step 4: Test Execution

### Running Tests

```bash
# Install dependencies
pip install -e '.[dev]'

# Run all tests
python -m pytest tests/ -v --tb=short

# Run specific test suites
python -m pytest tests/unit/test_pseudo_libinfo_loader.py -v
python -m pytest tests/unit/test_pseudo_contracts.py -v
python -m pytest tests/unit/test_demo_snapshot_pseudo_family.py -v
```

### Expected Results

- ✅ All tests pass
- ✅ No skipped tests (except network tests in CI)
- ✅ Zero `sha_token` references in code/tests/tools
- ✅ All generated demos have `pseudo_sha_family`

---

## Files Modified

### Core Implementation

1. **`src/quantumvitas/project/snapshot.py`**:
   - Enhanced `export_project_to_snapshot()` to compute `sha_family` from files
   - Added cleanup of `pseudo_sha_token` in `materialize_project_from_snapshot()`

2. **`src/quantumvitas/core/pseudo_libinfo.py`**:
   - Added strict schema validation in `load_pseudo_libinfo_bundle()`
   - Validates `sha_family` presence and `sha_token` absence

### Tests

1. **`tests/unit/test_pseudo_libinfo_loader.py`**:
   - Added `test_load_pseudo_libinfo_bundle_validates_sha_family()`

2. **`tests/unit/test_pseudo_contracts.py`** (new):
   - Backend contract tests for `get_pseudo_options_for_elements()`
   - UI writeback contract tests for `update_calculation_species_map()`
   - No legacy fields tests

3. **`tests/unit/test_demo_snapshot_pseudo_family.py`** (existing):
   - Already verifies demo generation produces `sha_family` (not `sha_token`)

### Documentation

1. **`docs/DEMO_GENERATION.md`** (new):
   - Comprehensive guide for generating demo projects
   - Documents all three demo generation scripts
   - Explains pseudopotential field requirements

2. **`docs/SHA_FAMILY_MIGRATION_HARDENING.md`** (this file):
   - Complete hardening report

---

## Behavior Verification

### Non-Negotiable Laws (Verified Unchanged)

✅ **Three pseudo sources only**: `internal`, `lib`, `project` - No 4th source  
✅ **QE runtime reads only `project/pseudo`** - Always by filename  
✅ **UI does not touch filesystem** - Only Step0 mutates `project/pseudo`  
✅ **UI selection key is `sha256`** - Not `sha_family`  
✅ **User selection writes triplet together** - `pseudo_filename + pseudo_sha256 + pseudo_sha_family`  
✅ **Restore/default selection is read-only** - Does not write `calc.yml`  
✅ **Step0 semantics unchanged** - Project source → noop+refresh, external → collision resolution

### Migration Status

✅ **Zero `sha_token` producers** - All generators fixed  
✅ **Strict bundle schema** - Loader validates `sha_family` presence and `sha_token` absence  
✅ **Contract tests** - Backend and UI writeback contracts verified  
✅ **Regression protection** - Tests guard against future `sha_token` reintroduction

---

## Verification Commands

```bash
# Check for sha_token in code
grep -r "sha_token\|pseudo_sha_token\|__tok-" src gui tests tools

# Check for sha_family usage
grep -r "pseudo_sha_family\|sha_family" src gui tests tools | wc -l

# Verify demo files
grep -r "pseudo_sha_family" resources/demo_projects/*.yml
grep -r "pseudo_sha_token" resources/demo_projects/*.yml  # Should be empty

# Run tests
python -m pytest tests/unit/test_pseudo_libinfo_loader.py -v
python -m pytest tests/unit/test_pseudo_contracts.py -v
python -m pytest tests/unit/test_demo_snapshot_pseudo_family.py -v
```

---

## PR Title Suggestion

"Hardening sha_family migration: strict bundle schema + producer cleanup + contract tests"

