# API Slimming Review

**Date**: 2026-02-02 (v2: Case-by-Case Philosophy)
**Scope**: Full `quantumvitas.api` traversal
**Methodology**: grep-based usage counting in daemon/*.py and cli/*.py

---

## 1. Governing Principle

Per API Constitution v2.0:

> **The API MUST be a THIN layer.**
>
> Core/runtime functions are NOT automatically "reasonable to reexport." Default is NO reexport. Every utils function requires individual justification.

This review audits every public entrypoint against this principle.

---

## 2. Hard Totals (Full API Traversal)

### 2.1 Summary

| Category | Count |
|----------|-------|
| **api/__init__.py exports** | 24 |
| **QVService static methods** | 38 |
| **QVService nested service methods** | ~100 |
| **Utils exports (functions)** | 88 |
| **Utils class re-exports** | 3 |
| **DTOs** | 13 |
| **Errors** | 9 |
| **TOTAL PUBLIC ENTRYPOINTS** | **~275** |

### 2.2 By Module

| Module | Entrypoints | Notes |
|--------|-------------|-------|
| `api/__init__.py` | 24 | 1 class, 2 functions, 9 errors, 12 DTOs |
| `api/service.py` | ~138 | 38 static + ~100 nested methods |
| `api/utils.py` | 91 | 88 functions + 3 class re-exports |
| `api/errors.py` | 9 | Error classes |
| `api/types/*.py` | 13 | DTO classes |

---

## 3. Coverage Analysis (Daemon & CLI Usage)

### 3.1 Overall Coverage

| Metric | Count | Percentage |
|--------|-------|------------|
| Utils functions used by daemon | ~35 | 40% |
| Utils functions used by CLI | ~20 | 23% |
| Utils functions used by both | ~10 | 11% |
| Utils functions used by neither | ~45 | 51% |

### 3.2 Top 10 Most Used Utils (Daemon)

| Function | Daemon Uses | Violation Type |
|----------|-------------|----------------|
| `is_ulid_like` | 29 | PROXY_OK (needs justification) |
| `validate_ulid` | 6 | PROXY_OK (needs justification) |
| `OnlineStructureCache` | 6 | CLASS_EXPORT |
| `load_project_config` | 6 | PROXY_OK (needs justification) |
| `get_pseudo_config` | 6 | PROXY_OK (needs justification) |
| `build_resource_index` | 6 | PROXY_OK (needs justification) |
| `delete_structure` | 4 | SERVICE_DELEGATION |
| `detect_presets_from_calculation` | 4 | DOMAIN_REEXPORT |
| `create_blob_store` | 4 | DOMAIN_REEXPORT |
| `apply_presets_to_step` | 4 | DOMAIN_REEXPORT |

### 3.3 Top 10 Most Used Utils (CLI)

Based on grep analysis of `src/quantumvitas/cli/*.py`:

| Function | CLI Uses | Violation Type |
|----------|----------|----------------|
| `slugify` | ~11 | PROXY_OK (needs justification) |
| `ensure_relative_path` | ~11 | PROXY_OK (needs justification) |
| `meta_from_name` | ~6 | PROXY_OK (needs justification) |
| `read_structure` | ~4 | PROXY_OK (needs justification) |
| `write_structure` | ~3 | PROXY_OK (needs justification) |
| `run_input_step` | ~3 | DOMAIN_REEXPORT |
| `create_default_registry` | ~2 | DOMAIN_REEXPORT |
| `extract_calculation_selector_from_entry` | ~2 | PROXY_OK |
| `parse_scf_output` | ~1 | DOMAIN_REEXPORT |
| `visualize_structure` | ~1 | DOMAIN_REEXPORT |

---

## 4. Utils Classification (New Rules)

Under the new constitution, utils exports are classified as:

| Category | Definition | Count |
|----------|------------|-------|
| **UTILS_PURE** | No runtime imports, stdlib-only | 0 |
| **UTILS_PROXY_REEXPORT** | Transparent proxy WITH docstring justification | 0 (none have justification) |
| **NO_JUSTIFICATION** | Proxy but lacks required docstring | ~30 |
| **DOMAIN_REEXPORT** | Imports from non-core packages | ~40 |
| **SERVICE_DELEGATION** | Calls get_service() internally | 2 |
| **CLASS_EXPORT** | Exposes internal class | 3 |
| **ONLINE_SEARCH** | Should be QVService capability | 5 |
| **ORCHESTRATION** | Multi-step logic, not transparent | ~8 |

**Key finding**: Under the new rules, ALL 88 utils functions are violations because none have the required docstring justification.

---

## 5. Complete Utils Audit (Case-by-Case)

### 5.1 Potentially Legitimate Proxies (Need Justification)

These functions are simple pass-throughs to core.* and MAY be legitimate if justified:

| Function | Source | Daemon | CLI | Verdict |
|----------|--------|--------|-----|---------|
| `slugify` | `core.resources` | 0 | 11 | KEEP: CLI needs for resource naming |
| `meta_from_name` | `core.resources` | 4 | 6 | KEEP: Resource creation helper |
| `ensure_relative_path` | `core.resources` | 0 | 11 | KEEP: Path normalization at boundary |
| `generate_resource_id` | `core.resources` | 0 | 0 | REVIEW: Unused, may delete |
| `generate_unique_name_and_slug` | `core.resources` | 4 | 1 | KEEP: Collision avoidance |
| `is_ulid_like` | `core.resolution` | 29 | 0 | KEEP: Request validation before service |
| `validate_ulid` | `core.resolution` | 6 | 0 | KEEP: Input validation |
| `load_project_config` | `core.project_utils` | 6 | 0 | KEEP: Config loading before service |
| `build_resource_index` | `core.resolution` | 6 | 0 | REVIEW: Should be service method? |
| `read_structure` | `io.structure_io` | 4 | 3 | KEEP: File I/O at boundary |
| `write_structure` | `io.structure_io` | 3 | 2 | KEEP: File I/O at boundary |

**Action**: Add docstring justifications to functions marked KEEP.

### 5.2 Service Delegation (VIOLATION - Must Remove)

| Function | What It Does | Daemon | CLI |
|----------|--------------|--------|-----|
| `delete_structure` | Calls `get_service().structure.delete()` | 4 | 0 |
| `rename_structure` | Calls `get_service().structure.update_meta()` | 3 | 0 |

**Action**: Delete these. Daemon should call `svc.structure.delete()` directly.

### 5.3 Online Search (VIOLATION - Move to Capability)

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `search_online_structures` | 2 | 0 | Move to `QVService.OnlineSearch.search()` |
| `fetch_structure_from_optimade` | 2 | 0 | Move to `QVService.OnlineSearch.fetch()` |
| `score_candidate` | 2 | 0 | Make internal to capability |
| `extract_provenance` | 2 | 0 | Make internal to capability |
| `reduce_formula` | 2 | 0 | Make internal or pure helper |

**Action**: Create `QVService.OnlineSearch` nested class.

### 5.4 Class Exports (VIOLATION - Return Dicts Instead)

| Class | Daemon | CLI | Action |
|-------|--------|-----|--------|
| `OnlineStructureCache` | 6 | 0 | Factory method returning opaque handle |
| `DisplayModeParams` | 2 | 0 | Accept dict, validate internally |
| `QEUIParam` | daemon | 0 | Return dict from metadata methods |

**Action**: Remove class exports; use factory methods or dict parameters.

### 5.5 Domain Reexports (VIOLATION - Largest Category)

#### From `presets.*`:

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `detect_engine_for_calculation` | 4 | 0 | `svc.Calculation.detect_engine()` |
| `detect_presets_from_calculation` | 4 | 0 | `svc.Calculation.detect_presets()` |
| `apply_presets_to_step` | 4 | 0 | `svc.Calculation.apply_presets()` |
| `get_preset_catalog` | 3 | 0 | `QVService.get_preset_catalog()` static |
| `detect_workflow_type` | 0 | 0 | Delete (unused) |
| `get_step_preset_footprints` | 0 | 0 | Delete or internal |
| `resolve_precision_context` | 0 | 0 | Delete (unused) |
| `create_precision_advisor` | 2 | 0 | `svc.Calculation.get_precision_advisor()` |

#### From `analysis.*`:

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `create_blob_store` | 4 | 0 | `svc.Analysis.get_blob_store()` |
| `build_structure_vis_payload` | 2 | 0 | `svc.Structure.get_vis_payload()` |
| `canonicalize_structure` | 0 | 0 | Delete (unused) |
| `parse_scf_output` | 0 | 1 | CLI-only, keep or move to Analysis |
| `plot_scf_convergence` | 0 | 1 | CLI-only plotting |
| `save_figure` | 0 | 1 | CLI-only plotting |
| `visualize_structure` | 0 | 1 | CLI-only, `svc.Structure.visualize()` |

#### From `calculation.*`:

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `compute_io_dir_from_calculation_model` | 3 | 0 | `svc.Calculation.get_io_dir()` |
| `run_input_step` | 0 | 3 | CLI-only, keep for now |
| `apply_card_overrides_to_qe_input` | 0 | 1 | CLI-only, keep for now |
| `apply_species_overrides_to_qe_input` | 0 | 1 | CLI-only, keep for now |
| `find_calculation_raw_dir` | 0 | 1 | CLI-only, keep or internal |
| `find_calculation_results_dir` | 0 | 1 | CLI-only, keep or internal |
| `find_band_analysis_files` | 0 | 1 | CLI-only, keep or internal |
| `detect_runtime_control_keys` | 0 | 0 | Delete (unused) |
| `needs_alat_preservation` | 0 | 0 | Delete (unused) |
| `extract_alat_bohr` | 0 | 0 | Delete (unused) |
| `write_qe_input_file` | 0 | 0 | Delete (unused) |
| `build_step_spec_from_qe_input` | 0 | 0 | Delete (unused) |

#### From `drivers.*`:

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `get_ui_parameters` | daemon | 0 | Keep (QE metadata for UI) |
| `list_supported_modules` | daemon | 0 | Keep (QE metadata for UI) |
| `get_module_param_sections` | daemon | 0 | Keep (QE metadata for UI) |
| `get_module_card_sections` | daemon | 0 | Keep (QE metadata for UI) |
| `get_module_doc_url` | daemon | 0 | Keep (QE metadata for UI) |
| `get_metadata_file_info` | daemon | 0 | Keep (debug) |
| `get_qe_metadata_debug_info` | daemon | 0 | Delete (debug-only) |
| `safe_load_metadata` | daemon | 0 | Internal, not for daemon |
| `reload_metadata` | daemon | 0 | Delete (debug-only) |
| `_iter_params` | daemon | 0 | Delete (private helper) |

### 5.6 Orchestration/Logic (VIOLATION)

| Function | Issue | Daemon | CLI | Action |
|----------|-------|--------|-----|--------|
| `find_path_context_ref` | try/except + dict transform | 0 | 0 | Delete (unused) |
| `find_project_root` | try/except + null return | 0 | 0 | Delete (unused) |
| `can_delete_structure` | Multi-kernel composition | 0 | 0 | Delete (unused) |
| `set_pseudo_config` | Load-modify-save workflow | 3 | 0 | KEEP: Need for daemon |
| `set_settings` | Load-modify-save workflow | 0 | 0 | Review usage |
| `set_qe_engine` | Settings + resolver | 0 | 0 | Review usage |
| `get_display_mode_params_class` | Returns class reference | 0 | 0 | Delete (unused) |

### 5.7 Pseudo Management (Special Category)

These are global operations without project context:

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `get_pseudo_config` | 6 | 0 | KEEP: Global config |
| `set_pseudo_config` | 3 | 0 | KEEP: Global config |
| `validate_pseudo_config_dict` | 0 | 0 | Review |
| `load_pseudo_config_raw` | 0 | 0 | Review |
| `list_installed_sssp` | 0 | 0 | Static method? |
| `list_seed_archives` | 0 | 0 | Static method? |
| `check_archives_status` | 0 | 0 | Static method? |
| `load_manifest_archives` | 0 | 0 | Static method? |
| `download_pseudo_by_filename` | 0 | 0 | Static method? |
| `download_pseudo_from_url` | 0 | 0 | Static method? |
| `resolve_pseudo_provenance` | 0 | 0 | Static method? |
| `search_legacy_pseudos` | 3 | 0 | KEEP: Daemon needs |

### 5.8 QE Engine Discovery (Special Category)

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `detect_qe` | 3 | 0 | KEEP: No project context |
| `get_environment_info` | 0 | 0 | Review |
| `list_qe_engines` | 3 | 0 | KEEP: No project context |
| `discover_qe_engines` | 3 | 0 | KEEP: No project context |
| `set_qe_engine` | 0 | 0 | Review |
| `get_qe_home` | 0 | 1 | CLI-only |
| `create_default_registry` | 0 | 2 | CLI-only |

### 5.9 Template Utilities

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `list_calculation_templates` | 0 | 1 | KEEP: Project init |
| `copy_calculation_template` | 0 | 1 | KEEP: Project init |
| `copy_structure_template` | 0 | 1 | KEEP: Project init |

### 5.10 Selector Extraction

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `extract_calculation_selector_from_entry` | 0 | 2 | KEEP: CLI parsing |
| `extract_structure_selector_from_entry` | 0 | 1 | KEEP: CLI parsing |
| `extract_step_selector_from_entry` | 0 | 0 | Delete (unused) |

### 5.11 Model I/O

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `load_calculation` | 0 | 1 | KEEP: CLI needs |
| `save_calculation` | 0 | 1 | KEEP: CLI needs |

### 5.12 Project Utilities

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `entry_display_name` | 0 | 0 | Delete (unused) |
| `move_to_trash` | 0 | 0 | Delete (unused) |
| `entry_matches` | 0 | 0 | Delete (unused) |
| `calculations_using_structure` | 0 | 1 | KEEP: CLI dependency check |
| `find_path_context_from_pwd` | 0 | 0 | Review |
| `materialize_project_from_snapshot` | 0 | 1 | KEEP: CLI |
| `export_project_to_snapshot` | 0 | 1 | KEEP: CLI |
| `get_project_snapshot_class` | 0 | 1 | KEEP: CLI |

### 5.13 Journal/Misc

| Function | Daemon | CLI | Action |
|----------|--------|-----|--------|
| `get_journal` | 0 | 0 | Review |
| `parse_volume_artifact` | 0 | 0 | Delete (unused) |

---

## 6. Deletion Candidates (Zero Usage)

Functions with 0 daemon AND 0 CLI usage:

| Function | Action | Surface Reduction |
|----------|--------|-------------------|
| `entry_display_name` | DELETE | -1 |
| `move_to_trash` | DELETE | -1 |
| `entry_matches` | DELETE | -1 |
| `extract_step_selector_from_entry` | DELETE | -1 |
| `detect_runtime_control_keys` | DELETE | -1 |
| `needs_alat_preservation` | DELETE | -1 |
| `extract_alat_bohr` | DELETE | -1 |
| `write_qe_input_file` | DELETE | -1 |
| `build_step_spec_from_qe_input` | DELETE | -1 |
| `find_path_context_ref` | DELETE | -1 |
| `find_project_root` | DELETE | -1 |
| `can_delete_structure` | DELETE | -1 |
| `get_display_mode_params_class` | DELETE | -1 |
| `detect_workflow_type` | DELETE | -1 |
| `get_step_preset_footprints` | DELETE | -1 |
| `resolve_precision_context` | DELETE | -1 |
| `canonicalize_structure` | DELETE | -1 |
| `get_qe_metadata_debug_info` | DELETE | -1 |
| `reload_metadata` | DELETE | -1 |
| `_iter_params` | DELETE | -1 |
| `parse_volume_artifact` | DELETE | -1 |
| `generate_resource_id` | REVIEW | -1? |

**Total immediate deletions: 21 functions = -21 surface**

---

## 7. Consolidation Proposals

### Proposal 1: Delete Unused Functions (Real Slimming)

**Surface reduction: -21**

Delete the 21 functions listed above with zero usage.

**Risk**: VERY LOW (zero external usage)

---

### Proposal 2: Remove Service Delegation Functions (Real Slimming)

**Surface reduction: -2**

| Delete | Replacement |
|--------|-------------|
| `delete_structure` | `svc.structure.delete()` |
| `rename_structure` | `svc.structure.update_meta()` |

**Risk**: LOW (4 + 3 call sites to update)

---

### Proposal 3: Create OnlineSearch Capability (Structure Correction)

**Surface change: -5 utils, +1 nested class with ~4 methods = net -1**

Move online search to `QVService.OnlineSearch`:
- `search()` - replaces `search_online_structures`
- `fetch()` - replaces `fetch_structure_from_optimade`
- Internal: `score_candidate`, `extract_provenance`, `reduce_formula`

**Risk**: MEDIUM (daemon handler refactoring)

---

### Proposal 4: Add Docstring Justifications (Compliance Only)

**Surface change: 0**

Add required docstring justifications to ~20 legitimate utils proxies.

This is compliance work, not slimming.

---

### Proposal 5: Consolidate QE Metadata (Real Slimming)

**Surface reduction: -8**

Replace 11 individual QE metadata exports with 1 method:
- Keep: `get_ui_parameters`, `list_supported_modules`, `get_module_param_sections`
- Delete: Debug functions, internal helpers

**Risk**: LOW (daemon-only)

---

## 8. Summary

### 8.1 Current State

| Metric | Value |
|--------|-------|
| Total API surface | ~275 entrypoints |
| Utils functions | 88 |
| Utils with docstring justification | 0 |
| Utils violations | 88 (100%) |
| Unused utils (delete candidates) | 21 |

### 8.2 After Phase 1 (Deletions Only)

| Metric | Current | After |
|--------|---------|-------|
| Utils functions | 88 | 67 |
| Total API surface | ~275 | ~254 |

**Real slimming: -21 entrypoints**

### 8.3 Target State

| Metric | Current | Target |
|--------|---------|--------|
| Utils functions | 88 | <20 |
| Utils violations | 88 | 0 |
| Total API surface | ~275 | <180 |

---

## Appendix: Methodology

### Usage Counting

```bash
# Daemon usage
grep -roh "function_name" src/quantumvitas/daemon/*.py | wc -l

# CLI usage
grep -roh "function_name" src/quantumvitas/cli/*.py | wc -l
```

### Function Listing

```bash
grep -E "^def [a-z_]+\(" src/quantumvitas/api/utils.py
```

### Import Verification

```bash
# Verify daemon imports only from api
grep -E "from quantumvitas\.(core|io|analysis|...)" src/quantumvitas/daemon/*.py
```

---

**End of API Slimming Review v2**
