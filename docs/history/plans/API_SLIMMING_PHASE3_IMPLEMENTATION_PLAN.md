# API Slimming Phase 3 Implementation Plan

**Created**: 2026-02-02
**Target**: 213 → 186 entrypoints (-27)
**Approach**: Bundle-based consolidation + unused removal

---

## Overview

Phase 3 focuses on high-impact consolidation through:
1. **Bundle functions**: Combine multiple related utils into single response
2. **Service capability**: Move online search to QMSService per Constitution H3
3. **Unused removal**: Delete methods with zero production usage

---

## Gate Rules (From Worklog)

**MANDATORY for every batch**:

1. **AUDIT BEFORE/AFTER**: Run `python tools/api_surface_audit.py`
2. **FULL TEST SUITE**:
   ```bash
   source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
   ```
3. **DOCUMENT DELTA**: Update worklog with raw audit output
4. **NET NEGATIVE**: Each batch must reduce total entrypoints

---

## Batch 32: Delete Unused Service Methods

**Complexity**: LOW
**Expected Delta**: -3

### Entrypoints to Delete

| Method | Location | Usage | Migration |
|--------|----------|-------|-----------|
| `Analysis.find_band_files` | service.py:1447 | d=0, c=0, t=0 | None (no callers) |
| `Project.get_species_map` | service.py:5592 | d=0, c=0, t=3 | Tests → `get_config().get("species_map", {})` |
| `Project.get_potential_map` | service.py:5616 | d=0, c=0, t=3 | Tests → `get_config().get("potential_map", {})` |

### Migration Steps

1. Update `tests/api/test_project_capabilities.py`:
   - Replace `svc.project.get_species_map()` → `svc.project.get_config().get("species_map", {})`
   - Replace `svc.project.get_potential_map()` → `svc.project.get_config().get("potential_map", {})`

2. Delete methods from `src/qmatsuite/api/service.py`:
   - `Analysis.find_band_files` (lines ~1447-1460)
   - `Project.get_species_map` (lines ~5592-5606)
   - `Project.get_potential_map` (lines ~5616-5630)

### Audit Checks

```bash
# Before
python tools/api_surface_audit.py | grep -E "service_nested|TOTAL"

# After
python tools/api_surface_audit.py | grep -E "service_nested|TOTAL"
# Expected: service_nested 88 → 85, TOTAL 213 → 210
```

---

## Batch 33: Pseudo Config Bundle

**Complexity**: LOW
**Expected Delta**: -5

### Current Entrypoints (7)

| Function | Daemon Refs | Action |
|----------|-------------|--------|
| `get_pseudo_config` | 26 | Fold into bundle |
| `set_pseudo_config` | 17 | **KEEP** (write) |
| `validate_pseudo_config_dict` | 4 | Fold into bundle |
| `list_installed_sssp` | 12 | Fold into bundle |
| `list_seed_archives` | 11 | Fold into bundle |
| `check_archives_status` | 6 | Fold into bundle |
| `load_manifest_archives` | 5 | Fold into bundle |

### Proposed Entrypoints (2)

1. `get_pseudo_status_bundle() -> dict`
2. `set_pseudo_config(...)` (keep existing)

### Implementation Steps

1. **Add bundle function** to `utils.py`:
   ```python
   def get_pseudo_status_bundle() -> dict:
       """
       Get comprehensive pseudo configuration status.

       Returns bundled response with:
       - config: Current pseudo configuration
       - validation: Validation result
       - installed_sssp: List of installed SSSP libraries
       - seed_archives: List of available seed archives
       - archive_statuses: Installation status of archives
       - manifest_archives: List of manifest archives
       """
       config = get_pseudo_config()
       return {
           "config": config,
           "validation": validate_pseudo_config_dict(config),
           "installed_sssp": list_installed_sssp(),
           "seed_archives": list_seed_archives(Path(config.get("seed_dir", ""))),
           "archive_statuses": check_archives_status(load_manifest_archives(), config),
           "manifest_archives": load_manifest_archives(),
       }
   ```

2. **Migrate daemon handlers** in `server.py`:
   - Find all call sites using individual functions
   - Replace with bundle + key extraction
   - Example: `config = get_pseudo_config()` → `bundle = get_pseudo_status_bundle(); config = bundle["config"]`

3. **Delete individual functions** from `utils.py`:
   - `get_pseudo_config` (keep internal, remove from `__all__`)
   - `validate_pseudo_config_dict`
   - `list_installed_sssp`
   - `list_seed_archives`
   - `check_archives_status`
   - `load_manifest_archives`

### Audit Checks

```bash
# Expected: utils 79 → 74, TOTAL 210 → 205
```

---

## Batch 34: QE Engine Bundle

**Complexity**: MEDIUM
**Expected Delta**: -3

### Current Entrypoints (5)

| Function | Daemon Refs | CLI Refs | Action |
|----------|-------------|----------|--------|
| `detect_qe` | 17 | 3 | Fold into bundle |
| `get_environment_info` | 4 | 0 | Fold into bundle |
| `list_qe_engines` | 10 | 0 | Fold into bundle |
| `discover_qe_engines` | 17 | 0 | Fold into bundle |
| `set_qe_engine` | 10 | 0 | **KEEP** (write) |

### Proposed Entrypoints (2)

1. `get_qe_engine_status() -> dict`
2. `set_qe_engine(...)` (keep existing)

### Implementation Steps

1. **Add bundle function** to `utils.py`:
   ```python
   def get_qe_engine_status() -> dict:
       """
       Get comprehensive QE engine status.

       Returns bundled response with:
       - detection: QE detection result
       - environment: Environment info
       - available_engines: List of available QE engines
       - discovered: Auto-discovered engines (cached)
       """
       return {
           "detection": detect_qe(),
           "environment": get_environment_info(),
           "available_engines": list_qe_engines(),
           "discovered": discover_qe_engines(),
       }
   ```

2. **Migrate daemon + CLI handlers**

3. **Delete individual functions** (keep internal, remove exports)

### Audit Checks

```bash
# Expected: utils 74 → 71, TOTAL 205 → 202
```

---

## Batch 35: Presets Detection Bundle

**Complexity**: MEDIUM
**Expected Delta**: -3

### Current Entrypoints (5)

| Function | Daemon Refs | Action |
|----------|-------------|--------|
| `detect_engine_for_calculation` | 6 | Fold into bundle |
| `detect_presets_from_calculation` | 6 | Fold into bundle |
| `detect_workflow_type` | 4 | Fold into bundle |
| `get_step_preset_footprints` | 10 | Fold into bundle |
| `resolve_precision_context` | 4 | **KEEP** (precision advisor) |

### Proposed Entrypoints (2)

1. `get_calculation_preset_bundle(calculation_dir: Path) -> dict`
2. `resolve_precision_context(...)` (keep existing)

### Implementation Steps

1. **Add bundle function** to `utils.py`:
   ```python
   def get_calculation_preset_bundle(calculation_dir: Path) -> dict:
       """
       Get comprehensive preset detection for a calculation.

       Returns bundled response with:
       - detected_engine: Engine detected from steps
       - dimension_states: Detected preset dimension values
       - workflow_type: Detected workflow type
       - step_footprints: Preset footprints per step
       """
       engine = detect_engine_for_calculation(calculation_dir)
       return {
           "detected_engine": engine,
           "dimension_states": detect_presets_from_calculation(calculation_dir, engine_filter=engine),
           "workflow_type": detect_workflow_type(calculation_dir),
           "step_footprints": get_step_preset_footprints(calculation_dir),
       }
   ```

2. **Migrate daemon handlers**

3. **Delete individual functions** (keep internal, remove exports)

### Audit Checks

```bash
# Expected: utils 71 → 68, TOTAL 202 → 199
```

---

## Batch 36-37: QE Metadata Bundle

**Complexity**: MEDIUM
**Expected Delta**: -8

### Batch 36: Add Bundle + Migrate

1. Add `get_qe_module_metadata(module, step_type_gen)` bundle function
2. Add `list_qe_modules()` convenience function
3. Migrate daemon handlers to use bundle
4. Keep all old functions temporarily

### Batch 37: Delete Old Functions

Delete from exports (keep internal):
- `get_ui_parameters`
- `list_supported_modules`
- `get_module_param_sections`
- `get_module_card_sections`
- `get_module_doc_url`
- `get_metadata_file_info`
- `get_qe_metadata_debug_info`
- `safe_load_metadata`
- `reload_metadata`
- `_iter_params`

Keep: `QEUIParam` (class for type hints)

### Audit Checks

```bash
# Expected: utils 68 → 60, TOTAL 199 → 191
```

---

## Batch 38-39: Online Search → Service (DEFER)

**Complexity**: HIGH
**Expected Delta**: -5

This is the most complex batch requiring:
- New `QMSService.OnlineSearch` static nested class
- Major daemon handler refactoring
- Cache factory pattern

**Recommendation**: Defer to Phase 4 if Phase 3 targets are met with batches 32-37.

---

## Summary

| Batch | Cluster | Delta | Running Total |
|-------|---------|-------|---------------|
| 32 | Unused Service Methods | -3 | 210 |
| 33 | Pseudo Config Bundle | -5 | 205 |
| 34 | QE Engine Bundle | -3 | 202 |
| 35 | Presets Detection Bundle | -3 | 199 |
| 36-37 | QE Metadata Bundle | -8 | 191 |
| 38-39 | Online Search (defer) | -5 | 186 |

**Phase 3 Target**: 191 entrypoints (without Online Search)
**Full Target**: 186 entrypoints (with Online Search)

---

## Risk Mitigation

### Backward Compatibility

For bundle functions, keep individual functions available internally:
- Mark as `@deprecated` in docstring
- Remove from `__all__` but don't delete code
- Daemon/CLI updated; tests can import directly if needed

### Rollback Plan

Each batch is atomic:
- If tests fail, revert batch entirely
- Each batch has independent migration
- No cross-batch dependencies

---

**End of Implementation Plan**
