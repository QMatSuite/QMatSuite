# API Slimming Audit - Final Report

**From**: Opus 4.5 (Architecture Executor)
**Re**: API Constitution Compliance
**Date**: 2026-01-27
**Status**: FULL PASS

---

## Executive Summary

### Verdict: **FULL PASS**

**All LegacyService references eliminated:**
- Daemon/server.py: **ZERO LegacyService** imports (was 8)
- Daemon/server.py: **ZERO history.* kernel bypass** imports (was 11)
- api/service.py: **ZERO LegacyService** imports (was 22)
- CLI: Compliant (no LegacyService)

**Test Results:**
- 2502 passed, 2 skipped, 0 failed (all tests passing)

---

## A) Violations Fixed

### A.1 LegacyService Eliminated from Daemon (8 methods)

| Handler | Line | Replacement |
|---------|------|-------------|
| `_handle_can_delete_calculation` | 2837 | `svc.calculation.can_delete()` |
| `_handle_delete_calculation` | 2949 | `svc.calculation.can_delete()` |
| `_handle_update_step_params` | 3137 | `svc.calculation.update_step_params()` |
| `_handle_get_common_cards` | 3228 | `svc.calculation.get_common_cards()` |
| `_handle_get_calculation_detail` | 4080 | `svc.calculation.get_detail()` |
| `_handle_change_calculation_structure` | 4305 | `svc.calculation.set_structure()` |
| `_handle_get_pseudo_options` | 4538 | `svc.calculation.get_detail()` |
| `_handle_preflight_check` | 4602 | `svc.run.preflight()` |

### A.2 History Kernel Bypass Eliminated from Daemon (11 imports)

| Handler | Original Import | Replacement |
|---------|-----------------|-------------|
| `_handle_get_project_history` | `history.storage`, `history.events`, `history.run_revision` | `svc.history.get_timeline()` |
| `_handle_get_run_revision` | `history.storage`, `history.run_revision` | `svc.history.get_run_revision()` |
| `_handle_list_project_runs` | `history.storage`, `history.run_revision` | `svc.history.list_runs()` |
| `_handle_pin_analysis_to_history` | `history.pins` | `svc.history.pin_analysis()` |
| `_handle_can_pin_to_run` | `history.pins` | `svc.history.can_pin()` |
| `_handle_get_pin_data` | `history.pins` | `svc.history.get_pin_data()` |
| `_handle_get_latest_run_for_step` | `history.storage`, `history.events` | `svc.history.get_latest_run_for_step()` |
| `_handle_delete_project_history` | `history.storage` | `svc.history.delete()` |

### A.3 LegacyService Eliminated from service.py (22 methods)

All 22 LegacyService delegations replaced with direct kernel calls:

| Location | Count | Methods |
|----------|-------|---------|
| Analysis accessor | 6 | analyze_band, analyze_dos, get_band_structure_data, get_scf_convergence_data, list_step_artifacts, read_step_artifact_text |
| Structure accessor | 3 | import_file, get_vis_data, update_meta |
| Calculation accessor | 1 | create |
| Run accessor | 2 | run_calculation, run_step |
| Static methods | 10 | init_step, run_calculation, run_step, import_structure, promote_relax_structure |

---

## B) New Domain Capabilities Added

### B.1 Calculation Accessor (4 new methods)

| Method | Purpose |
|--------|---------|
| `can_delete(selector)` | Check if calculation can be deleted (dependencies) |
| `get_detail(selector)` | Get full calculation detail for GUI display |
| `set_structure(calc_selector, structure_selector, update_steps)` | Change calculation structure |
| `get_common_cards(calc_selector, step_selector)` | Get card view models (K_POINTS, etc.) |

### B.2 Run Accessor (1 new method)

| Method | Purpose |
|--------|---------|
| `preflight(calc_selector, step_selector)` | Pre-flight checks before running |

### B.3 History Accessor (8 new methods)

| Method | Purpose |
|--------|---------|
| `get_timeline(limit, calc_id)` | Get project timeline events |
| `get_run_revision(run_id)` | Get run revision details |
| `list_runs(calc_id, limit)` | List all runs |
| `pin_analysis(run_id, step_id, analysis_kind, png_data, json_payload)` | Pin analysis to history |
| `can_pin(run_id, step_id)` | Check if pinning is allowed |
| `get_pin_data(run_id, step_id, analysis_kind)` | Get pinned data |
| `get_latest_run_for_step(step_id)` | Get latest run containing step |
| `delete(confirm)` | Delete history directory |

---

## C) Domain Accessor Method Counts

### Summary Table

| Accessor | Methods | Classification |
|----------|---------|----------------|
| Analysis | 10 | User-facing capabilities |
| Structure | 10 | User-facing capabilities |
| Calculation | 16 | User-facing capabilities |
| Run | 6 | User-facing capabilities |
| Project | 9 | User-facing capabilities |
| Engine | 4 | User-facing capabilities |
| **History** | **8** | **User-facing capabilities (NEW)** |
| **Total** | **63** | |

### Detailed Method List

#### Analysis (10 methods)
- `get_summary`, `list_properties`, `get_property_ref`, `load_artifact`
- `analyze_band`, `analyze_dos`
- `get_band_structure_data`, `get_scf_convergence_data`
- `list_step_artifacts`, `read_step_artifact_text`

#### Structure (10 methods)
- `get`, `list`, `get_atoms`, `require_ref`, `visualize`
- `import_file`, `get_vis_data`, `update_meta`
- `delete`, `get_composition`

#### Calculation (16 methods)
- `get`, `list`, `require_ref`, `require_step_ref`
- `resolve_enclosing_path`, `require_enclosing`, `get_step`, `list_steps`
- `get_effective_params`, `create`, `update_meta`, `update_step_params`
- `duplicate`, `delete`, `add_step`, `remove_step`
- **NEW:** `can_delete`, `get_detail`, `set_structure`, `get_common_cards`

#### Run (6 methods)
- `run_calculation`, `run_step`, `get_status`, `cancel`, `list_runs`
- **NEW:** `preflight`

#### Project (9 methods)
- `get_config`, `update_config`, `get_species_map`, `get_potential_map`
- `build_resource_index`, `list_calculations`, `collect_slugs`
- `apply_structure_rename`, `apply_calculation_rename`

#### Engine (4 methods)
- `list`, `get_info`, `list_step_types`, `validate_installation`

#### History (8 methods - NEW)
- `get_timeline`, `get_run_revision`, `list_runs`, `pin_analysis`
- `can_pin`, `get_pin_data`, `get_latest_run_for_step`, `delete`

---

## D) Test Results

### Test Summary
- **2502 passed** (all tests passing)
- **2 skipped** (expected)
- **0 failed** (no failures)

---

## E) Compliance Status

### Layer Compliance

| Layer | LegacyService | Kernel Bypass | Status |
|-------|---------------|---------------|--------|
| CLI | 0 | 0 | **COMPLIANT** |
| Daemon | 0 | 0 | **COMPLIANT** |
| api/__init__.py | 0 | 0 | **COMPLIANT** |
| api/utils.py | 0 | 0 | **COMPLIANT** |
| api/service.py | **0** | 0 | **COMPLIANT** |

### Architecture Gate

```
CLI imports only: quantumvitas.api.*, quantumvitas.api.utils
Daemon imports only: quantumvitas.api.*, quantumvitas.api.utils
No kernel modules imported by frontends
service.py uses direct kernel calls (no LegacyService layer)
```

---

## F) Bugs Fixed During Migration

### F.1 import_structure Registry Update Order

**Issue:** `require_structure` was called with stale `index` before `update_registry_add_structure`

**Fix:** Call `update_registry_add_structure` BEFORE `require_structure` when index is provided

**Location:** `QVService.import_structure()` static method

### F.2 promote_relax_structure Import Path

**Issue:** Import referenced non-existent `find_generated_structure_path` from `calculation.naming`

**Fix:** Import `get_generated_structure_path` from `execution.relax_artifacts` and use step ULID

**Location:** `QVService.promote_relax_structure()` static method

### F.3 analyze_band/analyze_dos Output Directory Auto-Detection

**Issue:** Missing auto-detection logic for output directory when analyzing files without explicit `output_dir` parameter. Plots were not being saved when called via CLI without `--output` flag.

**Root Cause:** During LegacyService elimination, the auto-detection code that finds the calculation's results directory from the input file path was not copied over.

**Fix:** Added auto-detection logic using ResourceIndex to find the enclosing calculation directory and set `output_dir` to `{calculation_dir}/results`

**Location:** `Analysis.analyze_band()` and `Analysis.analyze_dos()` methods

**Impact:** This was a regression that broke 4 CLI tests (bands/DOS analysis tests)

---

## G) Final Verdict

### **FULL PASS**

**All Conditions Met:**
1. ✅ Daemon has ZERO LegacyService imports
2. ✅ Daemon has ZERO kernel bypass imports
3. ✅ CLI has ZERO LegacyService/kernel bypass imports
4. ✅ api/service.py has ZERO LegacyService imports
5. ✅ api/utils.py is transparent re-exports only
6. ✅ New History accessor added with minimal surface
7. ✅ All tests pass (2502 passed, 0 failed)

### Migration Completed

| Phase | Status | Items |
|-------|--------|-------|
| Phase 1 | **COMPLETE** | Daemon LegacyService elimination (8 methods) |
| Phase 2 | **COMPLETE** | Daemon history.* elimination (11 imports) |
| Phase 3 | **COMPLETE** | service.py LegacyService elimination (22 methods) |

---

**End of Report**
