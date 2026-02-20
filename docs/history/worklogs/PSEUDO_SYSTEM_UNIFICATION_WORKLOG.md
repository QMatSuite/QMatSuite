# Pseudo System Unification — Worklog

## Goal
Unify three incompatible pseudo install/resolve systems into ONE pipeline (`src/quantumvitas/pseudo/`). Delete OLD systems. Fix MCP agent flow `download_pseudo_library -> auto_resolve_species_map`.

## Status: COMPLETE

---

## Phase 1: Delete root head.json from pipeline.py — DONE
- **File**: `src/quantumvitas/pseudo/pipeline.py`
- Deleted root head.json write block (lines 247-253)
- Install-level head.json at `SSSP/precision/1.3.0/head.json` retained (SSOT)

## Phase 2: Rewrite resolution in pseudo_config.py — DONE
- **File**: `src/quantumvitas/core/pseudo_config.py`
- Renamed `flavor` -> `variant` in PseudoResolutionRequest, default `"precision"`
- Replaced `_find_quantumvitas_root()` with `importlib.resources` + dev fallback
- Rewrote `resolve_project_pseudos()` with three-level directory walk
- Deleted ~800 lines of OLD system functions (get_sssp_library_path, install_sssp_from_seed, download_sssp_library, list_installed_sssp, etc.)
- Kept: PseudoConfig, load_pseudo_config, validate_pseudo_config, PseudoResolutionRequest/Result, resolve_project_pseudos, compute_sha256, download_github_release_asset

## Phase 3: Rewrite library_manager.py — DONE
- **File**: `src/quantumvitas/core/library_manager.py`
- Removed all OLD imports
- Rewrote `_get_sssp_status()` with three-level walk
- `install_library()` / `remove_library()` / `repair_library()` use `pipeline.download_and_install()`

## Phase 4: Delete pseudo_installs.py + update consumers — DONE
- **DELETED**: `src/quantumvitas/core/pseudo_installs.py`
- Updated `pseudo_materialization.py`: archive extraction -> three-level library walk
- Updated `pseudo_runtime.py`: archive extraction -> three-level library walk with case-insensitive matching
- Updated `pseudo_options.py`: added `_find_upf_in_libraries()` and `_find_upf_by_sha256_in_libraries()` helpers; replaced all `check_archive_status()` calls

## Phase 5: Rewrite api/service.py Pseudo class — DONE
- Replaced `get_sssp_library_path` references (lines 5507, 6010) with `home_pseudo_libraries_dir()` + three-level walk
- Replaced 7 OLD Pseudo class methods with single `download_and_install()` method
- Updated `api/utils.py`: `get_pseudo_status_bundle()` uses `library_manager.get_library_status()`

## Phase 6: Rewrite daemon/server.py handlers — DONE
- `_handle_install_sssp_from_seed`: uses `QVService.Pseudo.download_and_install()`
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
- `src/quantumvitas/core/pseudo_installs.py`
- `tests/integration/test_pseudo_download.py`

### Major rewrites:
- `src/quantumvitas/core/pseudo_config.py` (~800 lines deleted, resolution rewritten)
- `src/quantumvitas/core/library_manager.py` (all OLD imports -> NEW pipeline)
- `src/quantumvitas/core/pseudo_options.py` (archive checks -> NEW layout)
- `src/quantumvitas/core/pseudo_materialization.py` (archive extraction -> library walk)
- `src/quantumvitas/core/pseudo_runtime.py` (archive extraction -> library walk)
- `src/quantumvitas/api/service.py` (Pseudo class: 7 methods -> 1 method)
- `src/quantumvitas/api/utils.py` (get_pseudo_status_bundle rewritten)
- `src/quantumvitas/daemon/server.py` (SSSP handlers, flavor->variant, install_pseudo_archive)

### Minor fixes:
- `src/quantumvitas/pseudo/pipeline.py` (deleted root head.json write)
- `src/quantumvitas/mcp/tools/resolve_species_map.py` (flavor->variant)
- `src/quantumvitas/mcp/tools/_resource_utils.py` (flavor->variant, add version)
- `src/quantumvitas/mcp/tools/download_pseudo_library.py` (fix docstring)
- `src/quantumvitas/mcp/tools/list_resources.py` (install-level scan)
- `src/quantumvitas/calculation/runner.py` (fix unbound variable + warning handling)
- `gui/src/components/panels/StepDetailPanel.tsx` (fix dos module mapping)

### Tests updated:
- `tests/api/test_p4_hardening.py`
- `tests/integration/test_pseudo_download_pipeline.py`
- `tests/integration/test_pseudo_resolution.py`
- `tests/mcp/test_stage_p2.py`
- `tests/unit/test_pseudo_options.py`
