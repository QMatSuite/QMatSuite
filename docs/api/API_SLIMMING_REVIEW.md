# API Slimming Review

**Date**: 2026-02-02 (v3: Phase 3 High-Impact Consolidation)
**Scope**: Full `quantumvitas.api` traversal
**Status**: Phase 2 complete, Phase 3 opportunities identified

---

## 1. Current State (Post-Phase 2)

| Category | Count |
|----------|-------|
| `api/__init__.py` exports | 2 |
| QVService static methods | 23 |
| QVService nested service methods | 88 |
| Utils exports (functions + classes) | 79 |
| DTOs | 11 |
| Errors | 10 |
| **TOTAL ENTRYPOINTS** | **213** |

**Reduction from baseline**: 243 → 213 (-30, -12.3%)

---

## 2. Phase 3 High-Impact Consolidation Summary

### 2.1 Bundle-Based Consolidation

The key insight: daemon handlers often call multiple related utils functions in sequence. Bundling them into single responses reduces entrypoints.

| Cluster | Current | Proposed | Delta |
|---------|---------|----------|-------|
| QE Metadata | 11 | 3 | -8 |
| Pseudo Config | 7 | 2 | -5 |
| QE Engine | 5 | 2 | -3 |
| Presets Detection | 5 | 2 | -3 |
| **Subtotal** | 28 | 9 | **-19** |

### 2.2 Service Capability Migration

Per Constitution Law H3, online search should be a domain capability, not utils.

| Cluster | Current (utils) | Proposed (service) | Delta |
|---------|-----------------|-------------------|-------|
| Online Search | 6 | 1 nested class | -5 |

### 2.3 Unused Method Removal

| Cluster | Current | Proposed | Delta |
|---------|---------|----------|-------|
| Unused Service Methods | 3 | 0 | -3 |

### 2.4 Total Phase 3 Opportunity

| Category | Delta |
|----------|-------|
| Bundle consolidation | -19 |
| Service capability | -5 |
| Unused removal | -3 |
| **Total** | **-27** |

**Projected post-Phase 3**: 213 - 27 = **186 entrypoints**

---

## 3. Cluster Details

### 3.1 QE Metadata Cluster

**Pattern**: Daemon calls 5-6 functions per QE parameter panel render.

**Current call pattern** (daemon/server.py):
```python
modules = list_supported_modules()
for module in modules:
    doc_url = get_module_doc_url(module)
    ui_params = get_ui_parameters(module, step_type_gen)
    sections = get_module_param_sections(module)
    cards = get_module_card_sections(module)
```

**Proposed bundle pattern**:
```python
modules = list_qe_modules()
for module in modules:
    bundle = get_qe_module_metadata(module, step_type_gen)
    # bundle.ui_parameters, bundle.doc_url, bundle.sections, bundle.cards
```

**Entrypoint reduction**: 11 → 3 = **-8**

### 3.2 Pseudo Config Cluster

**Pattern**: Daemon calls 4-5 functions to render pseudo management UI.

**Current**: `get_pseudo_config`, `list_installed_sssp`, `list_seed_archives`, `check_archives_status`, `load_manifest_archives`

**Proposed**: Single `get_pseudo_status_bundle()` returning all data.

**Entrypoint reduction**: 7 → 2 = **-5**

### 3.3 QE Engine Cluster

**Pattern**: Daemon calls 3-4 functions to render engine selection UI.

**Current**: `detect_qe`, `list_qe_engines`, `discover_qe_engines`, `get_environment_info`

**Proposed**: Single `get_qe_engine_status()` returning all data.

**Entrypoint reduction**: 5 → 2 = **-3**

### 3.4 Online Search Cluster

**Pattern**: Daemon orchestrates multi-step search flow through utils.

**Current**: 6 utils functions + class

**Proposed**: `QVService.OnlineSearch` static nested class with `search()`, `fetch()`, `create_cache()` methods.

**Entrypoint reduction**: 6 → 1 = **-5** (nested class counts as 1 domain, not 3 methods)

### 3.5 Presets Detection Cluster

**Pattern**: Daemon calls 3-4 functions when loading calculation preset panel.

**Current**: `detect_engine_for_calculation`, `detect_presets_from_calculation`, `detect_workflow_type`, `get_step_preset_footprints`

**Proposed**: Single `get_calculation_preset_bundle(calc_dir)` returning all data.

**Entrypoint reduction**: 5 → 2 = **-3**

---

## 4. Execution Priority

### 4.1 Ranked by Ease + Impact

| Rank | Cluster | Delta | Complexity | Why |
|------|---------|-------|------------|-----|
| 1 | Unused Service Methods | -3 | LOW | Pure deletion, trivial test migration |
| 2 | Pseudo Config Bundle | -5 | LOW | Single daemon domain, no CLI usage |
| 3 | QE Engine Bundle | -3 | MEDIUM | Small CLI migration needed |
| 4 | Presets Detection Bundle | -3 | MEDIUM | Multiple daemon handlers |
| 5 | QE Metadata Bundle | -8 | MEDIUM | Complex daemon migration |
| 6 | Online Search → Service | -5 | HIGH | New service class + handler refactor |

### 4.2 Not Recommended

| Item | Reason |
|------|--------|
| Static method grouping | Would add facade layer (net 0 or worse) |
| Engine/Analysis accessor removal | Future capability scaffolding |
| DTO explosion | Doesn't reduce surface |

---

## 5. Migration Guidelines

### 5.1 Bundle Function Pattern

```python
# Before (multiple calls)
config = get_pseudo_config()
installed = list_installed_sssp()
archives = list_seed_archives()

# After (single bundle call)
bundle = get_pseudo_status_bundle()
config = bundle["config"]
installed = bundle["installed_sssp"]
archives = bundle["seed_archives"]
```

### 5.2 Service Capability Pattern

```python
# Before (utils function)
from quantumvitas.api.utils import search_online_structures
results = search_online_structures(query, max_results=50)

# After (service capability)
from quantumvitas.api import QVService
results = QVService.OnlineSearch.search(query, max_results=50)
```

---

## 6. Verification

### 6.1 Gate Rules

All batches must follow worklog gate rules:
1. Run `python tools/api_surface_audit.py` before and after
2. Full test suite must pass: `pytest tests/ -v --tb=short -n auto --dist=loadfile`
3. Document delta in worklog

### 6.2 Expected Final State

| Category | Current | After Phase 3 |
|----------|---------|---------------|
| utils | 79 | 54 |
| service_nested | 88 | 89* |
| service_static | 23 | 23 |
| errors | 10 | 10 |
| dtos | 11 | 11 |
| api_init | 2 | 2 |
| **TOTAL** | **213** | **186** |

*+1 from OnlineSearch nested class, -3 from unused method removal

---

## Appendix A: Utils Export Categorization (79 total)

### A.1 High-Consolidation Potential (37 exports → 10)

**QE Metadata** (11):
- `get_ui_parameters`, `list_supported_modules`, `get_module_param_sections`
- `get_module_card_sections`, `get_module_doc_url`, `get_metadata_file_info`
- `get_qe_metadata_debug_info`, `safe_load_metadata`, `reload_metadata`
- `_iter_params`, `QEUIParam`

**Pseudo Config** (7):
- `get_pseudo_config`, `set_pseudo_config`, `validate_pseudo_config_dict`
- `list_installed_sssp`, `list_seed_archives`, `check_archives_status`
- `load_manifest_archives`

**QE Engine** (5):
- `detect_qe`, `get_environment_info`, `list_qe_engines`
- `discover_qe_engines`, `set_qe_engine`

**Online Search** (6):
- `search_online_structures`, `fetch_structure_from_optimade`
- `score_candidate`, `extract_provenance`, `reduce_formula`
- `OnlineStructureCache`

**Presets Detection** (5):
- `detect_engine_for_calculation`, `detect_presets_from_calculation`
- `detect_workflow_type`, `get_step_preset_footprints`
- `resolve_precision_context`

### A.2 Keep As-Is (42 exports)

**Core Utilities** (legitimate helpers):
- `slugify`, `meta_from_name`, `ensure_relative_path`
- `generate_unique_name_and_slug`, `is_ulid_like`, `validate_ulid`
- `read_structure`, `write_structure`, `DisplayModeParams`
- `build_structure_vis_payload`, `find_path_context_from_pwd`
- `ContextNotFoundError`

**Template Operations**:
- `list_calculation_templates`, `copy_calculation_template`, `copy_structure_template`

**Preset Application** (write operations):
- `apply_presets_to_step`, `get_preset_catalog`, `create_precision_advisor`

**CLI-specific**:
- `run_input_step`, `apply_card_overrides_to_qe_input`, `apply_species_overrides_to_qe_input`
- `find_calculation_raw_dir`, `find_calculation_results_dir`, `find_band_analysis_files`
- `parse_scf_output`, `plot_scf_convergence`, `save_figure`, `visualize_structure`
- `export_project_to_snapshot`, `materialize_project_from_snapshot`, `get_project_snapshot_class`
- `create_default_registry`, `get_qe_home`, `calculations_using_structure`

**Pseudo Download**:
- `download_pseudo_by_filename`, `download_pseudo_from_url`
- `resolve_pseudo_provenance`, `search_legacy_pseudos`

**Internal Model Access** (consider for Phase 4):
- `load_calculation`, `save_calculation` - expose internal CalculationModel
- `get_journal`, `create_blob_store` - expose internal types

---

## Appendix B: Service Nested Methods (88 total)

### B.1 To Remove (3)

- `Analysis.find_band_files` - UNUSED
- `Project.get_species_map` - tests-only helper
- `Project.get_potential_map` - tests-only helper

### B.2 Future Capability (7) - KEEP

- `Analysis.list_properties`, `Analysis.get_property_ref`, `Analysis.load_artifact`, `Analysis.get_summary`
- `Engine.get_info`, `Engine.list_step_types`, `Engine.validate_installation`

### B.3 Production Use (78) - KEEP

All other nested methods are actively used by daemon/CLI.

---

**End of Review**
