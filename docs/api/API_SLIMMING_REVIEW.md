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

## Appendix C: Bundle QA (Phase 3 Quality Audit)

**Date**: 2026-02-02
**Status**: DTO-first schema recommendations

### C.1 Overview

Batches 33-35 created bundle functions to consolidate multiple utils calls into single responses.
Current state: These return `dict` which creates stringly-typed surface.

**Goal**: Define stable DTO schemas for each bundle WITHOUT increasing API surface.

### C.2 Bundle Schemas

#### C.2.1 get_pseudo_status_bundle()

**Location**: `api/utils.py:463`

**Current return type**: `dict`

**Actual schema** (from implementation):
```python
{
    "config": dict,           # PseudoConfig.to_dict()
    "validation": dict,       # ValidationResult.to_dict()
    "installed_sssp": list,   # List of installed SSSP library dicts
    "seed_archives": list,    # List of seed archive dicts
    "manifest_archives": list,# List of manifest archive dicts
    "archive_statuses": list  # List of archive status dicts
}
```

**Recommended DTO**:
```python
@dataclass
class PseudoStatusBundle(BaseDTO):
    """Comprehensive pseudo configuration status."""
    config: dict               # STABLE: pseudo config as dict
    validation: dict           # STABLE: validation result
    installed_sssp: list[dict] # STABLE: installed libraries
    seed_archives: list[dict]  # STABLE: available seed archives
    manifest_archives: list[dict]  # STABLE: manifest archives
    archive_statuses: list[dict]   # STABLE: installation status per archive
```

**Call-site audit**:
- `daemon/server.py:_handle_get_pseudo_config` - uses `bundle["config"]`
- `daemon/server.py:_handle_get_pseudo_validation` - uses `bundle["validation"]`
- `daemon/server.py:_handle_list_installed_sssp` - uses `bundle["installed_sssp"]`

**Error semantics**: Currently raises exceptions. Should wrap in ErrorDTO? NO - bundle is read-only data, exceptions are appropriate.

**Migration path**:
1. Create `PseudoStatusBundle` DTO (inherits BaseDTO)
2. Change return type from `dict` to `PseudoStatusBundle`
3. Callers use `bundle.config` instead of `bundle["config"]`
4. No new exports needed (DTO goes in dtos.py, function name unchanged)

---

#### C.2.2 get_qe_engine_status()

**Location**: `api/utils.py:779`

**Current return type**: `dict`

**Actual schema** (from implementation):
```python
{
    "detection": {
        "found": bool,
        "qe_home": str | None,
        "qe_bin_dir": str | None,
        "version": str | None,
        "executables": list[str],
        "mode": str,  # "external" | "internal"
        "error": str | None  # Only if found=False
    },
    "environment": {
        "python_version": str,
        "python_executable": str,
        "qv_version": str,
        "qe_home": str | None,
        "qe_found": bool
    },
    "available_engines": list[dict],  # Internal QE installations
    "discovered": list[dict]          # Auto-discovered engines
}
```

**Recommended DTO**:
```python
@dataclass
class QEDetectionInfo:
    """QE detection result."""
    found: bool
    qe_home: str | None
    qe_bin_dir: str | None
    version: str | None
    executables: list[str]
    mode: str  # "external" | "internal"
    error: str | None = None

@dataclass
class QEEnvironmentInfo:
    """Environment info."""
    python_version: str
    python_executable: str
    qv_version: str
    qe_home: str | None
    qe_found: bool

@dataclass
class QEEngineStatusBundle(BaseDTO):
    """Comprehensive QE engine status."""
    detection: QEDetectionInfo    # STABLE: detection result
    environment: QEEnvironmentInfo  # STABLE: environment info
    available_engines: list[dict]   # DEBUG: internal installations
    discovered: list[dict]          # DEBUG: auto-discovered engines
```

**Note**: `available_engines` and `discovered` are DEBUG fields - useful for troubleshooting but not part of stable contract.

**Call-site audit**:
- `daemon/server.py:_handle_detect_qe` - uses `bundle["detection"]`
- `daemon/server.py:_handle_get_env_info` - uses `bundle["environment"]`

**Migration path**: Same as C.2.1 - create DTO, change return type, update callers.

---

#### C.2.3 get_calculation_preset_bundle()

**Location**: `api/utils.py:633`

**Current return type**: `dict`

**Actual schema** (from implementation):
```python
{
    "detected_engine": str | None,  # e.g., "qe", "pyscf"
    "dimension_states": dict,       # Preset dimension values
    "workflow_type": str | None,    # e.g., "SCF", "DOS", "BANDS"
    "step_footprints": list[dict]   # Per-step preset footprints
}
```

**Recommended DTO**:
```python
@dataclass
class CalculationPresetBundle(BaseDTO):
    """Comprehensive preset detection for calculation."""
    detected_engine: str | None   # STABLE: detected engine family
    dimension_states: dict        # STABLE: detected preset dimensions
    workflow_type: str | None     # STABLE: detected workflow type
    step_footprints: list[dict]   # STABLE: per-step footprints
```

**Call-site audit**:
- `daemon/server.py:_handle_detect_presets` - uses `bundle["dimension_states"]`
- `daemon/server.py:_handle_detect_workflow` - uses `bundle["workflow_type"]`
- `daemon/server.py:_handle_get_step_preset_footprints` - uses `bundle["step_footprints"]`

**Migration path**: Same pattern.

---

### C.3 DTO Migration Rules

1. **No surface increase**: DTO classes go in `api/dtos.py` (already counted)
2. **Function name unchanged**: `get_pseudo_status_bundle()` stays
3. **Backwards compatible**: Callers can still use `bundle["key"]` if needed (DTOs support dict-like access via `to_dict()`)
4. **Type annotations**: Update function signatures to return DTOs
5. **Validation**: DTOs can validate fields on construction

### C.4 Risks

| Risk | Mitigation |
|------|------------|
| Breaking daemon/CLI that uses dict access | DTOs implement `to_dict()` for compatibility |
| Type errors in tests | Update test assertions to use DTO attributes |
| Serialization changes | DTOs use same `to_dict()` → JSON path |

### C.5 Implementation Priority

| Bundle | Priority | Reason |
|--------|----------|--------|
| PseudoStatusBundle | MEDIUM | Most complex, most fields |
| QEEngineStatusBundle | LOW | Nested structure adds complexity |
| CalculationPresetBundle | HIGH | Simple, clean schema |

**Recommendation**: Start with `CalculationPresetBundle` as it has simplest schema.

---

**End of Review**
