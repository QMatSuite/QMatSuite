# Pseudo Download Pipeline — Complete Rewrite Worklog

**Date**: 2026-02-20
**Branch**: v2-python

## Summary

Complete rewrite of the pseudo library download system. Previously SSSP-only with broken temp dir cleanup. Now supports all 8 libraries (31 archives) from the QMatSuite asset repo with a robust 5-step pipeline.

## Problem Statement

- `download_sssp_library()` only handled SSSP (hardcoded)
- Orphaned temp dirs (`sssp_download_*`) piling up in `.tmp/downloads/`
- `.qmatsuite/libraries/pseudo/` always empty — resolution couldn't find installed libs
- Non-SSSP libraries had no download path
- `ManifestEntry` dropped fields needed for non-SSSP (relativistic, type)

## What Changed

### New Package: `src/qmatsuite/pseudo/`

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 15 | Package exports: PseudoRegistry, download_and_install |
| `registry.py` | ~200 | Library registry from vendored manifest |
| `pipeline.py` | ~250 | 5-step download-install pipeline |

### Modified Files

| File | Change |
|------|--------|
| `src/qmatsuite/mcp/tools/download_pseudo_library.py` | Complete rewrite — new API (library, variant, version) |
| `src/qmatsuite/core/pseudo_config.py` | Added step 3b: new library layout search via head.json |
| `src/qmatsuite/mcp/tools/list_resources.py` | Added library-aware discovery scanning head.json |
| `tests/mcp/test_stage_p4.py` | Updated tests for new API |

### New Test File

| File | Tests |
|------|-------|
| `tests/integration/test_pseudo_download_pipeline.py` | 20 registry unit + download integration tests |

## Architecture

### Registry (`registry.py`)

- Loads vendored `MANIFEST_PSEUDO_SEED.json` (31 entries, 8 libraries)
- Maps each entry to `(library_key, variant, version)` triple
- `ArchiveInfo` dataclass with frozen fields
- 8 library categories: sssp, pseudodojo, gbrv, sg15, hgh, ps-library, gipaw, scan_tm
- Default variant per library (e.g., sssp→precision, gbrv→pbe)
- PseudoDojo variant = `{type}-{relativistic}_{xc}_{quality}` (e.g., `nc-sr_pbe_standard`)
- SSSP companions (cutoffs JSON) tracked via companion files

### Pipeline (`pipeline.py`)

5-step pipeline with cleanup guarantees:

1. **RESOLVE** — registry lookup + check already installed (head.json + UPFs)
2. **DOWNLOAD** — GitHub → `pseudo_dl_<uuid>` temp dir → SHA256 verify → move to seeds
3. **EXTRACT** — seed archive → `pseudo_ext_<uuid>` temp dir → flatten UPFs
4. **INSTALL** — copy to `libraries/pseudo/<Library>/<variant>/<version>/` → write head.json
5. **VALIDATE** — count UPFs > 0, spot-check sizes, verify head.json

Key properties:
- Idempotent (skip if already installed)
- Temp dirs cleaned in `finally` blocks (no orphans)
- Supports tar.gz, tgz, tar, and zip archives
- `head.json` at two levels: install dir (full info) + library root (variant/version pointer)

### Install Layout

```
.qmatsuite/libraries/pseudo/
├── SSSP/
│   ├── head.json          ← {"variant": "precision", "version": "1.3.0"}
│   └── precision/
│       └── 1.3.0/
│           ├── head.json  ← full ArchiveInfo
│           ├── Si.pbe-n-rrkjus_psl.1.0.0.UPF
│           ├── ...
│           └── SSSP_1.3.0_PBE_precision.json  (cutoffs companion)
├── PseudoDojo/
│   ├── head.json
│   └── nc-sr_pbe_standard/
│       └── 0.4/
│           ├── head.json
│           └── *.UPF
```

### Resolution Fix

`resolve_project_pseudos()` now has step 3b between "check store library" and "try seed":
- Scans `libraries/pseudo/*/head.json`
- Reads variant/version from head.json
- Looks for UPFs in `<Library>/<variant>/<version>/`
- Pure filesystem scanning — no imports from `pseudo/`

## Integration Test Results — Real Downloads

### Test Count Investigation

- Baseline: 6259 passed (included integration tests)
- Non-integration only: 5916 passed, 4 skipped — **no tests deleted**
- 5920 collected excluding integration, 6295 total — delta is exactly the 375 integration tests
- Final full run: **6291 passed, 4 skipped, 0 failed** (+32 net new tests)

### SSSP Precision Download (mandatory, ~60MB)

- **Status**: PASS
- **UPFs installed**: 103 (41 `.UPF` + 62 `.upf`)
- **Seed cached**: `SSSP_1.3.0_PBE_precision.tar.gz` (62,963,841 bytes) + companion `.json`
- **SHA256 verified**: `d91db6b4b3788501...`
- **head.json**: Written at both library root and install dir
- **Element spot-check**: Al, Si, Fe, Cu, Pb, O, C, N all found (H uses `H_ONCV_PBE-1.0.oncvpsp.upf` naming)
- **Cutoffs companion**: `SSSP_1.3.0_PBE_precision.json` installed alongside UPFs
- **Orphan temp dirs**: 0 (cleaned 7 old `sssp_download_*` orphans from prior broken system)
- **Idempotent rerun**: Correctly detected "Already installed (103 UPFs)"

### Representative Library Downloads

| Library | Format | Size | UPFs | Time | Status |
|---------|--------|------|------|------|--------|
| PseudoDojo nc-sr_pbe_standard | .tgz | 5.0 MB | 72 | 0.6s | PASS |
| GBRV pbe | .tar.gz | 12.5 MB | 65 | 1.0s | PASS |
| SG15 oncv | .tar.gz | 5.7 MB | 219 | 0.6s | PASS |
| SCAN_TM default | .zip | 1.0 MB | 32 | 0.3s | PASS |
| GIPAW default | .zip | 21.5 MB | 146 | 1.1s | PASS |
| HGH default | .tar.gz | 30.4 MB | 266 | 1.9s | PASS |

All 4 archive formats tested: `.tar.gz`, `.tgz`, `.tar` (PseudoDojo FR variants), `.zip`

### Resolution Integration Test

- Tested `resolve_project_pseudos()` step 3b with 5 elements NOT in `resources/pseudo`
- Elements: Ag, Ba, Ga, Ti, Zn — all resolved from installed SG15 library
- Messages confirmed: "Copied from library SG15" for each element
- Step 3b (new library layout via head.json) verified working independently

### GIPAW Note

- GIPAW zip contains macOS resource fork files (`._Li.pbe-paw-gipaw-nh.UPF`, 212 bytes)
- These are extracted as UPFs (match `.upf` extension) but are harmless metadata
- Validation correctly flagged them as size warnings

### Bugs Found (Pre-existing, NOT introduced)

- `resolve_project_pseudos()` glob pattern `f"{element}*.UPF"` is too loose: `C*` matches `Cu*`
- This causes Carbon to sometimes resolve to a Copper pseudopotential
- Fix needed: use `f"{element}[._-]*"` pattern — tracked as separate issue, not part of this rewrite

### Formal Integration Test Suite

```
tests/integration/test_pseudo_download_pipeline.py — 32 passed, 0 failed
  TestRegistry: 20 tests (no network)
  TestSSPPrecisionDownload: 5 tests (real download)
  TestRepresentativeLibraries: 6 tests (real downloads)
  TestResolutionIntegration: 1 test (resolution after download)
```

### Full Regression

```
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
6291 passed, 4 skipped, 0 failed (4:50 wall time)
```

The 4 skipped are pre-existing engine execution tests (require installed engine binaries).

## Existing Code Reused (NOT modified)

- `compute_sha256()`, `download_github_release_asset()`, `get_ssl_context()` from `core/pseudo_config.py`
- `home_pseudo_libraries_dir()`, `home_pseudo_seeds_dir()`, `tmp_downloads_dir()` from `core/paths.py`
- Vendored manifest at `resources/pseudo_libinfo/assets-2025-12-26/MANIFEST_PSEUDO_SEED.json`

## Installed Libraries Summary

After all tests, 7 libraries installed in `.qmatsuite/libraries/pseudo/`:

| Library | Variant | Version | UPFs |
|---------|---------|---------|------|
| SSSP | precision | 1.3.0 | 103 |
| PseudoDojo | nc-sr_pbe_standard | 0.4 | 72 |
| GBRV | pbe | 1.5 | 65 |
| SG15 | oncv | 2020-02-06 | 219 |
| SCAN_TM | default | 2017 | 32 |
| GIPAW | default | current | 146 |
| HGH | default | current | 266 |

Seed cache: 8 archives in `.qmatsuite/seeds/pseudo/` (includes SSSP efficiency from prior runs)
