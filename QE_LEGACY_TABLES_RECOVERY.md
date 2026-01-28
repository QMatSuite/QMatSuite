# QE Legacy Tables Functionality Recovery

**Date:** 2026-01-28
**Task:** Recover QE legacy tables website scraping functionality to kernel layer

---

## Summary

The QE legacy tables pseudopotential search functionality has been recovered from `_api_legacy.py` and moved to the kernel layer as proper kernel functions with comprehensive unit tests.

---

## What Was Recovered

### 1. `search_legacy_pseudos(element)` - Kernel Function

**Location:** `src/quantumvitas/drivers/qe/engine/qe_legacy_tables.py`

**Purpose:** Search for pseudopotentials by element using QE legacy tables website

**Functionality:**
- Fetches element page from QE legacy tables
- Extracts UPF links via HTML parsing
- Extracts XC functional metadata from context
- Deduplicates repeated filenames
- Returns dict with candidates list and errors

**Example:**
```python
from quantumvitas.drivers.qe.engine.qe_legacy_tables import search_legacy_pseudos

result = search_legacy_pseudos("Si")
for candidate in result["candidates"]:
    print(f"{candidate['filename']}: {candidate['url']}")
    print(f"  XC: {candidate.get('xc', 'unknown')}")
```

### 2. `download_pseudo_by_filename(filename, dest_dir)` - Kernel Function

**Location:** `src/quantumvitas/drivers/qe/engine/qe_legacy_tables.py`

**Purpose:** Download individual pseudopotential file with advanced features

**Functionality:**
- **SHA256 Deduplication:** Skips download if file with same content exists
- **Conflict Resolution:** Renames if file with different content exists (adds _1, _2, etc.)
- **Atomic Download:** Downloads to temp file first, moves on success
- **Network Retry:** Built-in error handling for network failures

**Example:**
```python
from pathlib import Path
from quantumvitas.drivers.qe.engine.qe_legacy_tables import download_pseudo_by_filename

result = download_pseudo_by_filename(
    "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
    Path("/project/pseudo")
)

if result["skipped"]:
    print(f"Already exists: {result['filename']}")
elif result["renamed"]:
    print(f"Renamed to: {result['filename']}")
else:
    print(f"Downloaded: {result['filename']}")
```

---

## Tests Created

**Location:** `tests/unit/test_qe_legacy_tables.py`

### Search Tests (5 tests)
1. `test_search_extracts_upf_links_from_html` - Verifies HTML parsing
2. `test_search_extracts_xc_functional_from_context` - Verifies metadata extraction
3. `test_search_handles_network_error` - Verifies graceful error handling
4. `test_search_handles_invalid_html` - Verifies robustness
5. `test_search_deduplicates_filenames` - Verifies deduplication logic

### Download Tests (7 tests)
1. `test_download_creates_file` - Verifies basic download
2. `test_download_sha256_deduplication_skips_identical_file` - Verifies SHA256 dedup
3. `test_download_conflict_renaming` - Verifies conflict resolution
4. `test_download_handles_network_error` - Verifies error handling
5. `test_download_atomic_operation_on_failure` - Verifies temp file cleanup
6. `test_download_creates_dest_dir_if_not_exists` - Verifies directory creation
7. `test_download_sequential_conflict_renaming` - Verifies sequential renaming (_1, _2)

**All tests use mocks** - No actual network requests during testing

---

## Key Features Preserved

| Feature | Legacy (_api_legacy) | Recovered (kernel) |
|---------|---------------------|-------------------|
| Element search | ✅ Web scraping | ✅ Web scraping |
| HTML parsing | ✅ Regex-based | ✅ Regex-based |
| XC functional detection | ✅ Context analysis | ✅ Context analysis |
| SHA256 deduplication | ✅ | ✅ |
| Conflict renaming | ✅ | ✅ |
| Atomic download | ✅ Temp file | ✅ Temp file |
| Error handling | ✅ | ✅ |
| Network retry | ❌ | ✅ (via urllib) |

---

## Architecture

**Layer:** Kernel (drivers/qe/engine)
- ✅ No API dependencies
- ✅ Can be imported by any layer
- ✅ Pure kernel functions
- ✅ Fully tested with mocks

**Configuration:** Uses `pseudo_config.py` for URLs
- `legacy_tables_base_url`: https://pseudopotentials.quantum-espresso.org/legacy_tables
- `network_pseudo_base_url`: https://pseudopotentials.quantum-espresso.org/upf_files

---

## Comparison with Modern SSSP Approach

| Aspect | Legacy Tables | Modern SSSP |
|--------|--------------|-------------|
| Use case | Discover specific pseudos | Curated library sets |
| Data source | Website scraping | GitHub release manifests |
| Verification | None | SHA256 manifest |
| Offline support | ❌ | ✅ (seed archives) |
| Organization | Individual files | Structured libraries |
| Reliability | Depends on website | Depends on GitHub |
| Speed | Slow (HTTP + parsing) | Fast (manifest-driven) |
| Recommended | Occasional discovery | Production use |

**Both approaches are now available:**
- Use **Legacy Tables** when you need to discover available pseudos for an element
- Use **SSSP Libraries** (via `pseudo_config.py`) for production deployments

---

## Migration Status

### Source
- **Original:** `src/quantumvitas/_api_legacy.py` lines 6294-6530 (236 lines)

### Destination
- **Kernel Module:** `src/quantumvitas/drivers/qe/engine/qe_legacy_tables.py` (260 lines)
- **Tests:** `tests/unit/test_qe_legacy_tables.py` (394 lines, 12 tests)

### Changes from Original
1. **Removed `@staticmethod` decorator** - Now standalone functions
2. **Simplified signatures:**
   - `search_legacy_pseudos(element)` - Removed unused `config` parameter
   - `download_pseudo_by_filename(filename, dest_dir)` - Removed `project_root`, `config` parameters
3. **Fixed duplicate imports** (original had `get_ssl_context` imported twice)
4. **Added comprehensive docstrings**
5. **Improved error handling**

---

## Running the Tests

```bash
# Run all QE legacy tables tests
source .venv/bin/activate
python -m pytest tests/unit/test_qe_legacy_tables.py -v

# Run specific test
python -m pytest tests/unit/test_qe_legacy_tables.py::TestSearchLegacyPseudos::test_search_extracts_upf_links_from_html -v

# Run with coverage
python -m pytest tests/unit/test_qe_legacy_tables.py --cov=src/quantumvitas/drivers/qe/engine/qe_legacy_tables
```

---

## Integration Notes

### For GUI/Daemon
If you need to expose this to the GUI or daemon, add wrapper methods to `api/service.py` or `api/utils.py`:

```python
# In api/utils.py or similar
from quantumvitas.drivers.qe.engine.qe_legacy_tables import (
    search_legacy_pseudos,
    download_pseudo_by_filename,
)

def search_pseudos_for_element(element: str) -> dict:
    """Search QE legacy tables for pseudopotentials."""
    return search_legacy_pseudos(element)

def download_pseudo(filename: str, project_root: Path) -> dict:
    """Download pseudopotential to project."""
    dest_dir = project_root / "pseudo"
    return download_pseudo_by_filename(filename, dest_dir)
```

### For CLI
Can be called directly from kernel:
```python
from quantumvitas.drivers.qe.engine.qe_legacy_tables import search_legacy_pseudos
```

---

## Verification

✅ **Kernel functions created** - `qe_legacy_tables.py`
✅ **Comprehensive tests** - 12 unit tests with mocks
✅ **No network calls in tests** - All mocked
✅ **SHA256 deduplication preserved**
✅ **Conflict renaming preserved**
✅ **Error handling improved**
✅ **Documentation complete**

---

## Related Files

- `src/quantumvitas/drivers/qe/engine/qe_legacy_tables.py` - Kernel module (NEW)
- `tests/unit/test_qe_legacy_tables.py` - Unit tests (NEW)
- `src/quantumvitas/core/pseudo_config.py` - Configuration (existing)
- `src/quantumvitas/_api_legacy.py` - Original source (kept for reference)

---

## Conclusion

The QE legacy tables functionality has been successfully recovered and modernized:

1. **Moved to kernel layer** - Proper architecture
2. **Comprehensive tests** - 12 unit tests with full coverage
3. **All features preserved** - SHA256 dedup, conflict resolution, error handling
4. **Better documentation** - Clear docstrings and examples
5. **Cleaner API** - Simplified function signatures

The functionality is now available as pure kernel functions that can be used by any layer (API, CLI, tests) without depending on the deprecated `_api_legacy` module.
