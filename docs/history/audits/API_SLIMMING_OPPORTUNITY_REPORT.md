# API Slimming Opportunity Report

**Generated**: 2026-02-02
**Revised**: 2026-02-02 (Final Closeout)
**Baseline**: 243 entrypoints → **Final**: 204 entrypoints (-39, -16.0%)

---

## Executive Summary

### Phase 3: High-Impact Consolidation Targets

| Priority | Cluster | Current | Proposed | Delta | Complexity |
|----------|---------|---------|----------|-------|------------|
| 1 | QE Metadata Bundle | 11 utils | 3 | **-8** | MEDIUM |
| 2 | Pseudo Config Bundle | 7 utils | 2 | **-5** | LOW |
| 3 | QE Engine Bundle | 5 utils | 2 | **-3** | LOW |
| 4 | Online Search → Service | 6 utils | 1 nested | **-5** | HIGH |
| 5 | Presets Detection Bundle | 5 utils | 2 | **-3** | MEDIUM |
| 6 | Unused Service Methods | 3 nested | 0 | **-3** | LOW |
| **Total** | | 37 | 10 | **-27** | |

**Projected surface after Phase 3**: 213 - 27 = **186 entrypoints**

---

## High-Impact, High-Complexity Consolidation Opportunities

### Cluster 1: QE Metadata Bundle (SLIMMING: -8)

**Current entrypoints (11 utils)**:

| Entrypoint | Location | Daemon Refs | CLI Refs |
|------------|----------|-------------|----------|
| `get_ui_parameters` | utils.py:678 | 4 | 0 |
| `list_supported_modules` | utils.py:679 | 8 | 4 |
| `get_module_param_sections` | utils.py:680 | 4 | 4 |
| `get_module_card_sections` | utils.py:681 | 5 | 0 |
| `get_module_doc_url` | utils.py:682 | 5 | 4 |
| `get_metadata_file_info` | utils.py:683 | 6 | 0 |
| `get_qe_metadata_debug_info` | utils.py:684 | 4 | 0 |
| `safe_load_metadata` | utils.py:685 | 7 | 0 |
| `reload_metadata` | utils.py:686 | 4 | 0 |
| `_iter_params` | utils.py:688 | 6 | 0 |
| `QEUIParam` (class) | utils.py:687 | 1 | 0 |

**Total usage**: daemon=54, cli=12

**Proposed minimal public API (3 entrypoints)**:

1. `get_qe_module_metadata(module: str, step_type_gen: str | None = None) -> dict`
   - Returns bundled response:
   ```python
   {
       "ui_parameters": [...],      # was get_ui_parameters
       "param_sections": {...},     # was get_module_param_sections
       "card_sections": {...},      # was get_module_card_sections
       "doc_url": "...",            # was get_module_doc_url
       "supported_modules": [...],  # was list_supported_modules
   }
   ```
2. `list_qe_modules() -> list[str]` - Convenience for module discovery
3. `QEUIParam` (class) - Keep for type hints in daemon

**What gets deleted (8)**:
- `get_ui_parameters` → folded into bundle
- `list_supported_modules` → folded into bundle (also standalone `list_qe_modules`)
- `get_module_param_sections` → folded into bundle
- `get_module_card_sections` → folded into bundle
- `get_module_doc_url` → folded into bundle
- `get_metadata_file_info` → internal only (debug)
- `get_qe_metadata_debug_info` → DELETE (debug-only, daemon can import directly)
- `safe_load_metadata` → internal only
- `reload_metadata` → DELETE (debug-only)
- `_iter_params` → internal only (daemon imports if needed)

**Expected delta**: **-8** utils

**Migration impact**:
- Daemon: 54 refs → update to use bundle
- CLI: 12 refs → update to use bundle or `list_qe_modules()`

**Risk level**: MEDIUM - multiple daemon handlers use these individually

**Prerequisites**:
- New `get_qe_module_metadata()` function must be added first
- Daemon handlers migrated to use bundle pattern
- CLI migrated to use bundle or list helper

---

### Cluster 2: Pseudo Config Bundle (SLIMMING: -5)

**Current entrypoints (7 utils)**:

| Entrypoint | Location | Daemon Refs | CLI Refs |
|------------|----------|-------------|----------|
| `get_pseudo_config` | utils.py:463 | 26 | 0 |
| `set_pseudo_config` | utils.py:477 | 17 | 0 |
| `validate_pseudo_config_dict` | utils.py:513 | 4 | 0 |
| `list_installed_sssp` | utils.py:540 | 12 | 0 |
| `list_seed_archives` | utils.py:566 | 11 | 0 |
| `check_archives_status` | utils.py:584 | 6 | 0 |
| `load_manifest_archives` | utils.py:618 | 5 | 0 |

**Total usage**: daemon=81, cli=0

**Proposed minimal public API (2 entrypoints)**:

1. `get_pseudo_status_bundle() -> dict`
   - Returns bundled response:
   ```python
   {
       "config": {...},            # was get_pseudo_config
       "validation": {...},        # was validate_pseudo_config_dict
       "installed_sssp": [...],    # was list_installed_sssp
       "seed_archives": [...],     # was list_seed_archives
       "archive_statuses": [...],  # was check_archives_status
       "manifest_archives": [...], # was load_manifest_archives
   }
   ```
2. `set_pseudo_config(...)` - Keep (write operation)

**What gets deleted (5)**:
- `get_pseudo_config` → folded into bundle (config key)
- `validate_pseudo_config_dict` → folded into bundle (validation key)
- `list_installed_sssp` → folded into bundle
- `list_seed_archives` → folded into bundle
- `check_archives_status` → folded into bundle
- `load_manifest_archives` → folded into bundle

**Expected delta**: **-5** utils

**Migration impact**:
- Daemon: 81 refs → update to use bundle
- Call sites extract needed keys from bundle response

**Risk level**: LOW - all daemon-only, straightforward migration

**Prerequisites**:
- New `get_pseudo_status_bundle()` function
- Daemon handlers migrate to bundle pattern

---

### Cluster 3: QE Engine Bundle (SLIMMING: -3)

**Current entrypoints (5 utils)**:

| Entrypoint | Location | Daemon Refs | CLI Refs |
|------------|----------|-------------|----------|
| `detect_qe` | utils.py:839 | 17 | 3 |
| `get_environment_info` | utils.py:891 | 4 | 0 |
| `list_qe_engines` | utils.py:912 | 10 | 0 |
| `discover_qe_engines` | utils.py:962 | 17 | 0 |
| `set_qe_engine` | utils.py:1052 | 10 | 0 |

**Total usage**: daemon=58, cli=3

**Proposed minimal public API (2 entrypoints)**:

1. `get_qe_engine_status() -> dict`
   - Returns bundled response:
   ```python
   {
       "detection": {...},         # was detect_qe
       "environment": {...},       # was get_environment_info
       "available_engines": [...], # was list_qe_engines
       "discovered": {...},        # was discover_qe_engines (cached)
   }
   ```
2. `set_qe_engine(bin_dir)` - Keep (write operation)

**What gets deleted (3)**:
- `detect_qe` → folded into bundle (detection key)
- `get_environment_info` → folded into bundle (environment key)
- `list_qe_engines` → folded into bundle (available_engines key)
- `discover_qe_engines` → folded into bundle (discovered key)

**Expected delta**: **-3** utils

**Migration impact**:
- Daemon: 58 refs → update to use bundle
- CLI: 3 refs → update to use bundle

**Risk level**: LOW - straightforward bundle pattern

---

### Cluster 4: Online Search → Service Capability (SLIMMING: -5)

**Current entrypoints (6 utils)**:

| Entrypoint | Location | Daemon Refs | CLI Refs |
|------------|----------|-------------|----------|
| `search_online_structures` | utils.py:1474 | 4 | 0 |
| `fetch_structure_from_optimade` | utils.py:1492 | 4 | 0 |
| `score_candidate` | utils.py:1507 | 4 | 0 |
| `extract_provenance` | utils.py:1524 | 4 | 0 |
| `reduce_formula` | utils.py:1456 | 4 | 0 |
| `OnlineStructureCache` (class) | utils.py:669 | 8 | 0 |

**Total usage**: daemon=28, cli=0

**Per Constitution Law H3**: Online search is domain capability, NOT utils.

**Proposed minimal public API (1 nested service class)**:

New nested class: `QVService.OnlineSearch` (no project context required - static accessor)

```python
class OnlineSearch:
    """Online structure search capability."""

    @staticmethod
    def search(query: str, max_results: int = 50) -> dict:
        """Search online databases. Returns summary + candidates."""

    @staticmethod
    def fetch(optimade_base: str, source_id: str) -> dict:
        """Fetch structure from OPTIMADE. Returns structure DTO."""

    @staticmethod
    def create_cache(cache_dir: Path | None = None) -> "OnlineStructureCache":
        """Create cache instance for session."""
```

Internal (not exported): `score_candidate`, `extract_provenance`, `reduce_formula`

**What gets deleted (5 utils)**:
- `search_online_structures` → `QVService.OnlineSearch.search()`
- `fetch_structure_from_optimade` → `QVService.OnlineSearch.fetch()`
- `score_candidate` → internal to search capability
- `extract_provenance` → internal to search capability
- `reduce_formula` → internal to search capability (pure helper)
- `OnlineStructureCache` → `QVService.OnlineSearch.create_cache()`

**Expected delta**: **-5** utils, +1 nested class = **-5** net (nested class has 3 methods but counts as domain, not individual entrypoints)

**Migration impact**:
- Daemon: 28 refs → update to use service capability
- Create `QVService.OnlineSearch` static nested class

**Risk level**: HIGH - requires new nested class, daemon handler refactoring

**Prerequisites**:
- New `OnlineSearch` nested class implementation
- Daemon handlers migrated
- Cache factory pattern for `OnlineStructureCache`

---

### Cluster 5: Presets Detection Bundle (SLIMMING: -3)

**Current entrypoints (5 utils)**:

| Entrypoint | Location | Daemon Refs | CLI Refs |
|------------|----------|-------------|----------|
| `detect_engine_for_calculation` | utils.py:696 | 6 | 0 |
| `detect_presets_from_calculation` | utils.py:712 | 6 | 0 |
| `detect_workflow_type` | utils.py:1365 | 4 | 0 |
| `get_step_preset_footprints` | utils.py:1382 | 10 | 0 |
| `resolve_precision_context` | utils.py:1399 | 4 | 0 |

**Total usage**: daemon=30, cli=0

**Proposed minimal public API (2 entrypoints)**:

1. `get_calculation_preset_bundle(calculation_dir: Path) -> dict`
   - Returns bundled response:
   ```python
   {
       "detected_engine": "...",       # was detect_engine_for_calculation
       "dimension_states": {...},      # was detect_presets_from_calculation
       "workflow_type": "...",         # was detect_workflow_type
       "step_footprints": {...},       # was get_step_preset_footprints
   }
   ```
2. Keep separate: `apply_presets_to_step` (write operation), `get_preset_catalog` (reference data), `create_precision_advisor` (factory)

**What gets deleted (3)**:
- `detect_engine_for_calculation` → folded into bundle
- `detect_presets_from_calculation` → folded into bundle
- `detect_workflow_type` → folded into bundle
- `get_step_preset_footprints` → folded into bundle
- `resolve_precision_context` → keep (needed for precision advisor creation)

**Expected delta**: **-3** utils

**Migration impact**:
- Daemon: 30 refs → update to use bundle

**Risk level**: MEDIUM - must maintain separate write operations

---

### Cluster 6: Unused Service Methods (SLIMMING: -3)

**Current entrypoints (3 nested methods)**:

| Entrypoint | Location | Daemon | CLI | Tests |
|------------|----------|--------|-----|-------|
| `Analysis.find_band_files` | service.py:1447 | 0 | 0 | 0 |
| `Project.get_species_map` | service.py:5592 | 0 | 0 | 3 |
| `Project.get_potential_map` | service.py:5616 | 0 | 0 | 3 |

**Proposed**: DELETE all three

**Migration**:
- `Analysis.find_band_files`: None (no callers)
- `Project.get_species_map`: Tests use `svc.project.get_config().get("species_map", {})`
- `Project.get_potential_map`: Tests use `svc.project.get_config().get("potential_map", {})`

**Expected delta**: **-3** service_nested

**Risk level**: LOW - trivial test migration

---

## DTO Expansion Opportunities (Clarity, NOT Slimming)

These do not reduce surface count but improve API ergonomics:

### CalculationDTO Expansion

**Current**: `CalculationDTO` lacks preset/workflow info, requiring separate utils calls.

**Proposal**: Add optional fields to `CalculationDTO`:
```python
@dataclass
class CalculationDTO:
    # ... existing fields ...
    detected_engine: str | None = None      # populate if requested
    workflow_type: str | None = None        # populate if requested
    dimension_states: dict | None = None    # populate if requested
```

**Impact**: Daemon can request full calculation detail in one call instead of multiple.

**Surface change**: 0 (fields added to existing DTO)

---

## Summary: Phase 3 Consolidation Plan

### Ranked by Ease + Impact

| Rank | Cluster | Delta | Complexity | Batch |
|------|---------|-------|------------|-------|
| 1 | Unused Service Methods | -3 | LOW | 32 |
| 2 | Pseudo Config Bundle | -5 | LOW | 33 |
| 3 | QE Engine Bundle | -3 | MEDIUM | 34 |
| 4 | Presets Detection Bundle | -3 | MEDIUM | 35 |
| 5 | QE Metadata Bundle | -8 | MEDIUM | 36-37 |
| 6 | Online Search → Service | -5 | HIGH | 38-39 |

**Total**: **-27 entrypoints**

### What's NOT an Opportunity

1. **Static methods** (23) - All production-used, correctly designed
2. **Engine/Analysis accessor methods** - Future capability scaffolding (keep)
3. **Adding facade layers** - Violates "no multi-layer facade" constraint
4. **Relocating tests-only A-class methods** - Represent planned future API

---

## Appendix: Methodology

### Usage Counting

```bash
# Count daemon usage
grep -r -c "function_name" src/quantumvitas/daemon/

# Count CLI usage
grep -r -c "function_name" src/quantumvitas/cli/
```

### Cluster Analysis

Grouped functions by:
1. Semantic similarity (same domain)
2. Call-site co-occurrence (daemon handlers that use multiple related functions)
3. Bundle potential (can be combined into single response)

---

## Final Closeout Status

**Status**: CLOSED — All actionable slimming completed.

### Final Numbers

| Category | Count |
|----------|-------|
| api_init | 2 |
| service_static | 23 |
| service_nested | 90 |
| utils | 68 |
| dtos | 11 |
| errors | 10 |
| **TOTAL** | **204** |

### Remaining Surface is Post-Slimming Stable

The opportunities documented above have been partially executed (Phases 1-3 bundles, unused removal, H9 migration). The remaining 204 entrypoints represent the intentional stable API surface.

### Disallowed Patterns (Gated)

- **Service-delegating wrappers in utils**: Gate B prevents re-introduction
- **Stub/placeholder service methods**: Gate C prevents half-baked capabilities
- **Direct YAML writes in frontends**: Gate H9 enforces kernel-only filesystem access

Future slimming (if desired) would target the remaining Phase 3 opportunities (online search migration, further QE metadata bundling). These are tracked here for reference but not scheduled.

---

**End of Report**
