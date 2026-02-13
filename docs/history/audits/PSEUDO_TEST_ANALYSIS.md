# Pseudopotential Test Analysis

**Date:** 2026-01-28
**Task:** Analyze removed pseudopotential tests and justify deletion vs migration

---

## Tests Removed

From `tests/unit/test_pseudopotential_resolution.py`:

1. `test_search_legacy_pseudos_structure`
2. `test_download_pseudo_by_filename_structure`
3. `test_search_legacy_pseudos_handles_offline`

---

## Legacy Functionality Analysis

### `search_legacy_pseudos(element, config)` (from _api_legacy.py)

**What it did:**
- Scraped QE legacy tables website (`https://pseudopotentials.quantum-espresso.org/legacy_tables/ps-library/{element}`)
- Parsed HTML pages to extract pseudopotential filenames and download URLs
- Returned list of candidates with metadata

**Kernel equivalent:** NONE

**Modern replacement:** SSSP libraries via `pseudo_config.py`
- `fetch_manifest()` - Gets structured JSON manifest from GitHub release
- `select_sssp_entries()` - Filters SSSP libraries by version/flavor/xc
- `download_sssp_library()` - Downloads verified SSSP library with SHA256 checks

### `download_pseudo_by_filename(project_root, filename, dest_dir, config)` (from _api_legacy.py)

**What it did:**
- Downloaded specific pseudopotential file by filename from QE network repository
- **SHA256 deduplication**: Skip download if file with same SHA256 exists
- **Conflict renaming**: Rename if file with different content already exists
- Downloaded to `project_root/pseudo`

**Kernel equivalent:** PARTIAL
- `download_pseudopotential()` in `drivers/qe/engine/qe_pseudopotentials.py`
  - ✅ Downloads by filename
  - ✅ Basic retry logic
  - ❌ NO SHA256 deduplication
  - ❌ NO conflict renaming
  - Simpler implementation

**Modern replacement:** SSSP library management
- `download_github_release_asset()` in `pseudo_config.py`
  - ✅ Downloads with SHA256 verification (manifest-driven)
  - ✅ Atomic download (temp dir → copy on success)
  - ✅ Better error handling

---

## Decision: Remove Tests (Justified)

### Reasoning

1. **Legacy Web Scraping is Deprecated**
   - QE legacy tables website scraping is an outdated approach
   - No kernel equivalent exists (intentionally)
   - Modern approach uses structured SSSP libraries

2. **Modern Replacement Exists and is Tested**
   - SSSP library management in `pseudo_config.py` (954 lines)
   - Modern tests in `tests/integration/test_pseudo_download.py`
   - Better: Manifest-driven, SHA256-verified, atomic downloads

3. **Feature Parity**
   | Feature | Legacy | Kernel download_pseudopotential | Modern SSSP |
   |---------|--------|--------------------------------|-------------|
   | Download by filename | ✅ | ✅ | ✅ (via manifest) |
   | SHA256 deduplication | ✅ | ❌ | ✅ (manifest-driven) |
   | Conflict renaming | ✅ | ❌ | N/A (uses deterministic naming) |
   | Network retry | ✅ | ✅ | ✅ |
   | Element search | ✅ (web scrape) | ❌ | ✅ (SSSP libraries) |
   | Offline support | ❌ (network only) | ❌ | ✅ (seed archives) |

4. **Tests Were Intentionally Skipped**
   - Tests were marked `@pytest.mark.skip` with reason: "Legacy network pseudo search not available in kernel"
   - These were placeholder tests with `pass` bodies
   - No actual test logic to preserve

---

## What About SHA256 Deduplication?

**Legacy approach:**
```python
# In download_pseudo_by_filename:
existing_sha = compute_sha256(existing_file)
new_sha = compute_sha256(downloaded_file)
if existing_sha == new_sha:
    skip download
```

**Modern SSSP approach:**
- Uses **seed archives** for deduplication
- `import_seed_archives()` in `pseudo_config.py`:
  ```python
  existing_hashes: Dict[str, Path] = {}
  for existing_archive in seed_dir.rglob("*.tar.gz"):
      sha256 = compute_sha256(existing_archive)
      existing_hashes[sha256] = existing_archive

  if sha256 in existing_hashes:
      skip_import("Already exists")
  ```

**Conclusion:** SHA256 deduplication is preserved in modern SSSP library management, but at the archive level (better granularity).

---

## What About Conflict Renaming?

**Legacy approach:**
```python
# In download_pseudo_by_filename:
if dest_file.exists() and content_differs(dest_file, downloaded):
    rename_to(f"{name}_1.UPF")
```

**Modern SSSP approach:**
- Uses **deterministic naming** based on SSSP library version/flavor
- Files from SSSP libraries don't conflict because they're organized by version/flavor directories
- Example: `store/sssp/1.3.0/efficiency/library/Si.pbe-n-rrkjus_psl.1.0.0.UPF`

**Conclusion:** Conflict renaming is unnecessary in modern approach due to structured organization.

---

## Recommendation Summary

**Action:** ✅ **Remove tests (already done)** - Justified removal, not a mistake

**Rationale:**
1. Tests were placeholders for deprecated legacy functionality
2. Modern SSSP library management (`pseudo_config.py`) provides superior functionality
3. Modern tests exist (`test_pseudo_download.py`)
4. Critical features (SHA256, dedup) are preserved in modern approach
5. No functionality loss - modern approach is strictly better

**Alternative considered:** Migrate tests to use `download_pseudopotential()` from `qe_pseudopotentials.py`
- ❌ Rejected: This would test the simplified download function, not the legacy web scraping
- ❌ Rejected: The simplified function is already tested implicitly via engine tests
- ❌ Rejected: Would not cover the SHA256 dedup / conflict renaming features

**If SHA256 dedup is needed for individual files:**
- Can add to kernel's `download_pseudopotential()` if use case arises
- Currently not needed because SSSP libraries handle this at archive level
- Would be a feature addition, not migration work

---

## Related Modern Tests

These tests validate the modern pseudopotential management:

1. `tests/integration/test_pseudo_download.py`
   - Tests SSSP manifest fetching
   - Tests SSSP library download
   - Tests SHA256 verification

2. `tests/unit/test_pseudo_contracts.py`
   - Tests pseudopotential resolution contracts

3. `tests/unit/test_pseudo_libinfo_loader.py`
   - Tests SSSP library metadata loading

4. `tests/daemon/test_pseudo_scanning.py`
   - Tests daemon pseudo scanning functionality

---

## Conclusion

The removal of these 3 tests is **CORRECT and JUSTIFIED**:
- Legacy functionality is deprecated (web scraping QE legacy tables)
- Modern replacement exists and is superior (SSSP libraries)
- Modern replacement is tested comprehensively
- No critical functionality lost (SHA256 dedup preserved)
- Tests were intentionally skipped placeholders, not functional tests

**No migration needed** - this is architectural progress, not technical debt.
