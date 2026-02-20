# Pseudo Resolution — Deterministic Lookup + Pipeline Hardening

**Date**: 2026-02-20
**Branch**: v2-python
**Predecessor**: PSEUDO_DOWNLOAD_PIPELINE_WORKLOG.md

## Summary

Replaced glob-based pseudo resolution (`f"{element}*.UPF"`) with deterministic index-based lookup using the vendored `PSEUDO_FILE_INDEX.json`. This fixes the C→Cu resolution bug and unifies install path computation into a single function.

## Problem Statement

- `resolve_project_pseudos()` used `glob(f"{element}*.UPF")` which is non-deterministic
- Searching for Carbon (`C`) matched Copper (`Cu`) files (`C*.UPF` matches `Cu_*.UPF`)
- Install path computation duplicated between `pipeline.py` and resolution code
- Band structure calculations missing `diago_full_acc` best practice

## What Changed

### New Functions in `src/quantumvitas/pseudo/registry.py`

| Function | Purpose |
|----------|---------|
| `archive_install_relpath(info)` | Single source of truth for install path: `<dir_name>/<variant>/<version>` |
| `resolve_element_from_index(library_key, variant, version, element)` | Deterministic element→filename lookup from PSEUDO_FILE_INDEX.json |
| `_load_file_index()` | Lazy-load and cache the file index (3083 files, 3623 occurrences) |
| `_find_file_index_path()` | Locate vendored PSEUDO_FILE_INDEX.json |

### Index Join Logic

For each occurrence in PSEUDO_FILE_INDEX.json:
1. Look up `files[sha256]` → get `element`
2. Compute `(library_key, variant, version)` from `occurrence.library.*` using existing `_compute_variant()` / `_compute_version()` / `_CATEGORY_MAP`
3. Use `Path(occurrence.path_in_archive).name` as the filename
4. Store: `_element_index[(library_key, variant, version, element)] = filename`

### Modified Files

| File | Change |
|------|--------|
| `src/quantumvitas/pseudo/registry.py` | Added `archive_install_relpath()`, `resolve_element_from_index()`, `_load_file_index()` |
| `src/quantumvitas/pseudo/__init__.py` | Exported new functions |
| `src/quantumvitas/pseudo/pipeline.py` | Use `archive_install_relpath()` for install path |
| `src/quantumvitas/core/pseudo_config.py` | Rewrote `resolve_project_pseudos()` with deterministic lookup + `_find_file_in_dir()` helper |
| `src/quantumvitas/calculation/step_defaults.py` | Added `diago_full_acc: True` to qe_bandspw ELECTRONS |
| `src/quantumvitas/mcp/tools/list_resources.py` | Added element-level availability via index lookup |

### New Files

| File | Description |
|------|-------------|
| `tests/integration/test_pseudo_resolution.py` | 4 test classes (A-D), ~25 tests |
| `docs/history/worklogs/PSEUDO_RESOLUTION_FIX_WORKLOG.md` | This worklog |

## Resolution Chain (New)

For each element in `resolve_project_pseudos()`:

1. **Get exact filename** from `resolve_element_from_index()` for requested library
2. **Project pseudo dir** — check exact filename, then tight glob fallback
3. **Bundled resources** — check exact filename, then tight glob fallback
4. **Installed libraries** — scan head.json, use index for each library, tight glob fallback
5. **Seed auto-install** — install from seed, retry with deterministic lookup
6. **Not found** — error

### Tight Glob Pattern

Replaced broken `f"{element}*.UPF"` with `f"{element}[._-]*.[Uu][Pp][Ff]"`:
- Matches: `Si.pbe-n-rrkjus_psl.1.0.0.UPF`, `Si_ONCV_PBE-1.0.oncvpsp.upf`
- Rejects: `Si` matching `Siesta`, `C` matching `Cu`, `Ca`, `Cl`, etc.

### Key Properties

- **Zero globs in primary path** — exact dict lookup from index
- **C vs Cu impossible** — lookup key includes full element symbol
- **Deterministic** — same input always gives same output
- **Lazy** — index only loaded when first resolution call happens
- **Backward compatible** — tight glob fallback handles files not in index

## diago_full_acc for Band Structure

Added `"diago_full_acc": True` to `qe_bandspw` ELECTRONS defaults. This is standard best practice — ensures all eigenvalues (not just below Fermi level) are converged in band structure calculations.

## Test Plan

### Class A: TestIndexLookup (unit, no network) — 11 tests
- Si, C, Cu individual resolution
- C vs Cu different filenames (core bug fix)
- Nonexistent element/library → None
- Common elements coverage (H through Bi)
- Deterministic (same call twice)
- Cross-library: SG15, GBRV, SSSP efficiency

### Class B: TestArchiveInstallRelpath (unit) — 5 tests
- SSSP, PseudoDojo, GBRV, SG15 path computation
- Pipeline module has the function

### Class C: TestResolutionChain (integration) — 5 tests
- Si from SSSP installed library
- C not Cu (integration-level bug fix verification)
- 5 elements from SG15
- Project pseudo dir populated after resolution
- Project-local preference (no re-copy)

### Class D: TestBandspwDefaults (unit) — 3 tests
- diago_full_acc True in bandspw
- Not in SCF
- Not in bands.x post-processing
