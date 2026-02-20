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

### New Package: `src/quantumvitas/pseudo/`

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 15 | Package exports: PseudoRegistry, download_and_install |
| `registry.py` | ~200 | Library registry from vendored manifest |
| `pipeline.py` | ~250 | 5-step download-install pipeline |

### Modified Files

| File | Change |
|------|--------|
| `src/quantumvitas/mcp/tools/download_pseudo_library.py` | Complete rewrite — new API (library, variant, version) |
| `src/quantumvitas/core/pseudo_config.py` | Added step 3b: new library layout search via head.json |
| `src/quantumvitas/mcp/tools/list_resources.py` | Added library-aware discovery scanning head.json |
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

## Test Results

- 5916 passed, 0 failed, 4 skipped (non-integration suite)
- 20 registry unit tests pass (no network)
- Integration tests available for SSSP + representative libraries (network required)

## Existing Code Reused (NOT modified)

- `compute_sha256()`, `download_github_release_asset()`, `get_ssl_context()` from `core/pseudo_config.py`
- `home_pseudo_libraries_dir()`, `home_pseudo_seeds_dir()`, `tmp_downloads_dir()` from `core/paths.py`
- Vendored manifest at `resources/pseudo_libinfo/assets-2025-12-26/MANIFEST_PSEUDO_SEED.json`
