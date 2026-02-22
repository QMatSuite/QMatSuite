# Pseudo System Unification — Worklog

## Goal
Unify three incompatible pseudo install/resolve systems into ONE pipeline (`src/qmatsuite/pseudo/`). Delete OLD systems. Fix MCP agent flow `download_pseudo_library -> auto_resolve_species_map`.

## Status: COMPLETE

---

## Phase 1: Delete root head.json from pipeline.py — DONE
- **File**: `src/qmatsuite/pseudo/pipeline.py`
- Deleted root head.json write block (lines 247-253)
- Install-level head.json at `SSSP/precision/1.3.0/head.json` retained (SSOT)

## Phase 2: Rewrite resolution in pseudo_config.py — DONE
- **File**: `src/qmatsuite/core/pseudo_config.py`
- Renamed `flavor` -> `variant` in PseudoResolutionRequest, default `"precision"`
- Replaced `_find_qmatsuite_root()` with `importlib.resources` + dev fallback
- Rewrote `resolve_project_pseudos()` with three-level directory walk
- Deleted ~800 lines of OLD system functions (get_sssp_library_path, install_sssp_from_seed, download_sssp_library, list_installed_sssp, etc.)
- Kept: PseudoConfig, load_pseudo_config, validate_pseudo_config, PseudoResolutionRequest/Result, resolve_project_pseudos, compute_sha256, download_github_release_asset

## Phase 3: Rewrite library_manager.py — DONE
- **File**: `src/qmatsuite/core/library_manager.py`
- Removed all OLD imports
- Rewrote `_get_sssp_status()` with three-level walk
- `install_library()` / `remove_library()` / `repair_library()` use `pipeline.download_and_install()`

## Phase 4: Delete pseudo_installs.py + update consumers — DONE
- **DELETED**: `src/qmatsuite/core/pseudo_installs.py`
- Updated `pseudo_materialization.py`: archive extraction -> three-level library walk
- Updated `pseudo_runtime.py`: archive extraction -> three-level library walk with case-insensitive matching
- Updated `pseudo_options.py`: added `_find_upf_in_libraries()` and `_find_upf_by_sha256_in_libraries()` helpers; replaced all `check_archive_status()` calls

## Phase 5: Rewrite api/service.py Pseudo class — DONE
- Replaced `get_sssp_library_path` references (lines 5507, 6010) with `home_pseudo_libraries_dir()` + three-level walk
- Replaced 7 OLD Pseudo class methods with single `download_and_install()` method
- Updated `api/utils.py`: `get_pseudo_status_bundle()` uses `library_manager.get_library_status()`

## Phase 6: Rewrite daemon/server.py handlers — DONE
- `_handle_install_sssp_from_seed`: uses `QMSService.Pseudo.download_and_install()`
- `_handle_download_sssp_library`: simplified, uses `download_and_install()`
- `_handle_download_all_sssp`: loops precision/efficiency
- `_handle_import_seed_archives`: returns deprecation message
- `_handle_install_pseudo_archive`: rewritten to use `download_and_install()` (was calling deleted methods)

## Phase 7: Fix MCP tools — DONE
- `resolve_species_map.py`: `flavor` -> `variant` (param + response key)
- `_resource_utils.py`: `flavor` -> `variant`, added `version` to request
- `download_pseudo_library.py`: fixed docstring Args section
- `list_resources.py`: root head.json scan -> three-level install-level walk

## Phase 8: Tests — DONE
- **DELETED**: `tests/integration/test_pseudo_download.py` (tested OLD functions)
- Updated `test_pseudo_resolution.py`: `flavor` -> `variant` (6 occurrences)
- Updated `test_pseudo_download_pipeline.py`: root head.json -> install-level assertion; `flavor` -> `variant`
- Updated `test_pseudo_options.py`: replaced `load_manifest_archives`, `is_archive_installed`, `check_archive_status` patches with `_find_upf_in_libraries` patches
- Updated `tests/api/test_p4_hardening.py`: `flavor` -> `variant`; `download_sssp_library` signature test -> `download_and_install` signature test
- Updated `tests/mcp/test_stage_p2.py`: `data["flavor"]` -> `data["variant"]`

## Phase 9: Dead code scan + regression — DONE
- `pseudo_installs` references: 0 in src/, 0 in tests/
- OLD function names: 0 references (only handler names in daemon router)
- `"flavor"` references: 2 backward-compat fallbacks in daemon (acceptable)
- **Python tests**: 6304 passed, 0 failed, 4 skipped
- **GUI e2e tests**: 16 passed, 0 failed

## Additional Fixes
- **runner.py**: Fixed `UnboundLocalError: cannot access local variable 'e'` at line 244 — warnings from Step0 pseudo prep now log and continue instead of using unbound exception variable
- **StepDetailPanel.tsx**: Fixed `dos` step type mapping from module `'pw'` to `'dos'` — `fildos` parameter was invisible in AddParameter search because DOS step was incorrectly mapped to the `pw` module

---

## Files Summary

### DELETED:
- `src/qmatsuite/core/pseudo_installs.py`
- `tests/integration/test_pseudo_download.py`

### Major rewrites:
- `src/qmatsuite/core/pseudo_config.py` (~800 lines deleted, resolution rewritten)
- `src/qmatsuite/core/library_manager.py` (all OLD imports -> NEW pipeline)
- `src/qmatsuite/core/pseudo_options.py` (archive checks -> NEW layout)
- `src/qmatsuite/core/pseudo_materialization.py` (archive extraction -> library walk)
- `src/qmatsuite/core/pseudo_runtime.py` (archive extraction -> library walk)
- `src/qmatsuite/api/service.py` (Pseudo class: 7 methods -> 1 method)
- `src/qmatsuite/api/utils.py` (get_pseudo_status_bundle rewritten)
- `src/qmatsuite/daemon/server.py` (SSSP handlers, flavor->variant, install_pseudo_archive)

### Minor fixes:
- `src/qmatsuite/pseudo/pipeline.py` (deleted root head.json write)
- `src/qmatsuite/mcp/tools/resolve_species_map.py` (flavor->variant)
- `src/qmatsuite/mcp/tools/_resource_utils.py` (flavor->variant, add version)
- `src/qmatsuite/mcp/tools/download_pseudo_library.py` (fix docstring)
- `src/qmatsuite/mcp/tools/list_resources.py` (install-level scan)
- `src/qmatsuite/calculation/runner.py` (fix unbound variable + warning handling)
- `gui/src/components/panels/StepDetailPanel.tsx` (fix dos module mapping)

### Tests updated:
- `tests/api/test_p4_hardening.py`
- `tests/integration/test_pseudo_download_pipeline.py`
- `tests/integration/test_pseudo_resolution.py`
- `tests/mcp/test_stage_p2.py`
- `tests/unit/test_pseudo_options.py`

---

## Patch: Shared Utility + Missing Tests + Cleanup

### Part 1: Shared three-level walk utility — DONE
- **Created**: `src/qmatsuite/pseudo/layout.py`
  - `InstalledLibrary` dataclass (frozen, install_dir + library_key + variant + version + head)
  - `iter_installed_libraries(libraries_root)` — single canonical three-level walk
  - `find_installed_library(libraries_root, library_key, variant, version)` — targeted lookup
  - `find_upf_in_libraries(libraries_root, filename)` — exact filename search
  - `find_upf_in_libraries_casefold(libraries_root, filename)` — case-insensitive fallback
- **Updated**: `src/qmatsuite/pseudo/__init__.py` — exports all 5 new symbols
- **Replaced 9 inline walks in 7 files**:
  - `core/pseudo_config.py` — `_scan_installed_libraries()` now delegates
  - `core/library_manager.py` — `_scan_installed_for_library()` now delegates
  - `core/pseudo_options.py` — `_find_upf_in_libraries()` and `_find_upf_by_sha256_in_libraries()` now delegate
  - `core/pseudo_materialization.py` — step 3 inline walk replaced
  - `core/pseudo_runtime.py` — `_resolve_lib_source_path()` now delegates
  - `mcp/tools/list_resources.py` — `_list_qe_resources()` inline walk replaced
  - `api/service.py` — two SSSP-specific inline walks replaced (lines ~5562, ~6057)
- **Verification**: three-level walk exists in EXACTLY ONE place (`pseudo/layout.py`)

### Part 2: Delete remaining `flavor` fallbacks — DONE
- Deleted 3 backward-compat fallbacks in `daemon/server.py` (lines 852, 906, 1199)
- Fixed 3 stale `flavor` references in daemon docstrings
- **Verification**: `grep -rn "flavor" src/qmatsuite/ --include="*.py"` returns 0 pseudo-related hits (only CP2K binary flavors remain, which are legitimate)

### Part 3: Fix cutoffs loading — DONE
- **BUG FOUND**: SSSP cutoffs JSON is a dict keyed by element (`{"Ac": {...}, "Ag": {...}}`), but parser at `pseudo_config.py:555` used `isinstance(cutoffs_data, list)` which always evaluated to empty `[]` for dicts. **Cutoffs were NEVER loaded.**
- **FIX**: Added dict branch that iterates `cutoffs_data.items()` with `isinstance(elem_data, dict)` guard. List branch preserved for backward compatibility.

### Part 4: Confirm diago_full_acc — DONE
- Confirmed `diago_full_acc=True` at `step_defaults.py:105` in `qe_bandspw` defaults.

### Part 5: Integration tests — DONE
- **Created**: `tests/integration/test_pseudo_unification.py` (23 tests in 7 classes)
  - `TestNoRootHeadJson` (3 tests) — root head.json NOT created, install-level exists with library_key
  - `TestTwoVariantsCoexist` (4 tests) — both precision + efficiency discoverable, separate dirs
  - `TestNoOldLayoutReferences` (8 tests) — deleted modules/functions, no flavor field, variant default=precision, no flavor in src/
  - `TestSeedFallback` (1 test) — resolution succeeds with installed SSSP
  - `TestListResourcesShowsInstalled` (2 tests) — MCP list_resources shows installed lib with elements
  - `TestRealSCFSmoke` (3 tests) — Tl (rare element) preconditions + full QE SCF pipeline
  - `TestGaAsEndToEnd` (2 tests) — GaAs bands auto_resolve + cutoffs dict-vs-list fix verification

### Results
- **Python tests**: 6327 passed, 0 failed, 4 skipped (+23 new tests)
- **GUI e2e tests**: 16 passed, 0 failed
