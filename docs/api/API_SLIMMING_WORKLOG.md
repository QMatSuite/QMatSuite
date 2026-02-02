# API Slimming Worklog

**Started**: 2026-02-02
**Status**: IN PROGRESS

---

## Reference

| Document | Location |
|----------|----------|
| API Constitution | `docs/api/API_CONSTITUTION.md` |
| Implementation Plan | `docs/api/API_SLIMMING_IMPLEMENTATION_PLAN.md` |
| Slimming Review | `docs/api/API_SLIMMING_REVIEW.md` |
| Audit Script | `tools/api_surface_audit.py` |

---

## Test Command

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Audit Baseline (2026-02-02)

| Category | Count |
|----------|-------|
| utils | 91 |
| service_static | 38 |
| service_nested | 91 |
| errors | 10 |
| dtos | 11 |
| api_init | 2 |
| **TOTAL** | **243** |

| Usage Status | Count |
|--------------|-------|
| Daemon only | 115 |
| CLI only | 51 |
| Both | 44 |
| **UNUSED** | **33** |

---

## Change Log

### Batch 0: Baseline Established
- **Time**: 2026-02-02
- **Action**: Created audit script, ran baseline
- **Total Entrypoints**: 243
- **Unused**: 33
- **Tests**: N/A (no changes)

---

### Batch 1: Delete generate_resource_id from utils
- **Time**: 2026-02-02
- **Action**: Removed `generate_resource_id` from api/utils.py
- **Deleted**: 1 function (utils)
- **Delta**: 243 → 242 entrypoints, utils 91 → 90, unused 33 → 32
- **Tests**: 3018 passed, 18 skipped
- **Notes**: Updated 3 test files to import from core.resources instead

---

### Batch 2: Delete visualization/cache factory functions
- **Time**: 2026-02-02
- **Action**: Removed `get_display_mode_params_class`, `create_online_structure_cache`
- **Deleted**: 2 functions (utils)
- **Delta**: 242 → 240 entrypoints, utils 90 → 88, unused 32 → 30
- **Tests**: 3018 passed, 18 skipped
- **Notes**: Per Law H3, online cache creation is capability, not utils. Kept class re-exports.

---

### Batch 3: Delete unused static method
- **Time**: 2026-02-02
- **Action**: Deleted `QVService.extract_calculation_selector_from_entry` (0 callers, just wrapped utils)
- **Deleted**: 1 static method
- **Delta**: 240 → 239 entrypoints, static 38 → 37
- **Tests**: 3018 passed, 18 skipped

---

### Batch 4: Migrate compat.py to nested service methods
- **Time**: 2026-02-02
- **Action**: Migrated `daemon/compat.py` from static methods to nested service methods
- **Changes**:
  - `QVService.get_project_summary(path)` → `QVService(path).project.get_summary()`
  - `QVService.list_structures_data(path)` → `QVService(path).structure.list()` (DTO)
  - `QVService.list_calculations_data(path)` → `QVService(path).calculation.list()` (DTO)
- **Delta**: No entrypoint change (call site migration only)
- **Tests**: 3018 passed, 18 skipped
- **Notes**: Prepares for static method deletion once test usages are migrated

---

### Batch 5: Migrate consumer tests to nested service methods
- **Time**: 2026-02-02
- **Action**: Migrated test files from static methods to nested DTO methods
- **Files changed**:
  - `tests/daemon/test_gui_calculation_detail.py`: 3 usages migrated (lines 108, 164, 332)
  - `tests/integration/test_relax_promote_e2e.py`: 2 usages migrated (lines 183, 210)
- **Remaining callers**:
  - `test_gui_calculation_detail.py:288`: Needs `structure` name field (DTO has ulid only)
  - `test_qvservice_gui.py`: 6 usages - tests OF the static methods (delete with methods)
- **Delta**: No entrypoint change (call site migration only)
- **Tests**: 3018 passed, 18 skipped

---

### Batch 6: Delete list_structures_data and list_calculations_data
- **Time**: 2026-02-02
- **Action**: Deleted static methods `list_structures_data`, `list_calculations_data`
- **Deleted**: 2 static methods, 6 tests
- **Delta**: 239 → 237 entrypoints, static 37 → 35
- **Tests**: 3012 passed, 18 skipped
- **Notes**: Migrated last consumer test (test_gui_calculation_detail.py) to use `get_detail()`

---

### Batch 7: Inline get_project_summary into nested method
- **Time**: 2026-02-02
- **Action**: Inlined `get_project_summary` static into `project.get_summary()` nested, deleted static
- **Deleted**: 1 static method
- **Delta**: 237 → 236 entrypoints, static 35 → 34
- **Tests**: 3012 passed, 18 skipped
- **Notes**: Migrated 4 test usages to nested method

---

### Batch 8: Inline materialize_pseudo_file into nested method
- **Time**: 2026-02-02
- **Action**: Inlined `materialize_pseudo_file` static into `project.materialize_pseudo_file()` nested, deleted static
- **Deleted**: 1 static method
- **Delta**: 236 → 235 entrypoints, static 34 → 33
- **Tests**: 3012 passed, 18 skipped

---

### Batch 9: Inline get_pseudo_options_for_elements into nested method
- **Time**: 2026-02-02
- **Action**: Inlined `get_pseudo_options_for_elements` static into `project.get_pseudo_options()` nested, deleted static
- **Deleted**: 1 static method
- **Delta**: 235 → 234 entrypoints, static 33 → 32
- **Tests**: 3012 passed, 18 skipped

---

### Batch 10: Inline analyze_project_pseudo_effects into nested method
- **Time**: 2026-02-02
- **Action**: Inlined `analyze_project_pseudo_effects` static into `project.analyze_pseudo_effects()` nested, deleted static
- **Deleted**: 1 static method
- **Delta**: 234 → 233 entrypoints, static 32 → 31
- **Tests**: 3012 passed, 18 skipped
- **Notes**: Daemon caller already migrated in previous session

---

### Batch 11: Inline save_relax_final_structure into nested method
- **Time**: 2026-02-02
- **Action**: Inlined `save_relax_final_structure` static into `structure.save_relax_final_structure()` nested, deleted static
- **Deleted**: 1 static method
- **Delta**: 233 → 232 entrypoints, static 31 → 30
- **Tests**: 3012 passed, 18 skipped
- **Notes**: Migrated 2 test usages in test_relax_structure_save.py to nested method

---

### Batch 12: Inline promote_relax_structure into nested method
- **Time**: 2026-02-02
- **Action**: Inlined `promote_relax_structure` static into `structure.promote_relax_structure()` nested, deleted static
- **Deleted**: 1 static method
- **Delta**: 232 → 231 entrypoints, static 30 → 29
- **Tests**: 3012 passed, 18 skipped
- **Notes**: Migrated 10 test usages across 3 test files to nested method

---

### Batch 13: Inline configure_species_map into nested method
- **Time**: 2026-02-02
- **Action**: Inlined `configure_species_map` static into `calculation.configure_species_map()` nested, deleted static
- **Deleted**: 1 static method
- **Delta**: 231 → 230 entrypoints, static 29 → 28
- **Tests**: 3012 passed, 18 skipped
- **Notes**: Migrated 3 test usages across 3 test files to nested method

---

### Batch 14: Inline run_calculation into nested method
- **Time**: 2026-02-02
- **Action**: Extended `run.run_calculation()` nested method with `run_mode` and `run_ulid` params, deleted static
- **Deleted**: 1 static method
- **Delta**: 230 → 229 entrypoints, static 28 → 27
- **Tests**: 3012 passed, 18 skipped
- **Notes**: Migrated 10+ test usages across 4 test files to nested method. CLI and daemon already used nested method.

---

### Batch 15: Inline run_step into nested method
- **Time**: 2026-02-02
- **Action**: Extended `run.run_step()` nested method with `run_ulid` param, deleted static
- **Deleted**: 1 static method
- **Delta**: 229 → 228 entrypoints, static 27 → 26
- **Tests**: 3012 passed, 18 skipped
- **Notes**:
  - Migrated 19 test usages across 7 test files to nested method
  - Updated `_result_dict_to_dto` to handle `success` boolean and `step_ulid` for run_step results
  - Updated `run_single_step` to delegate to nested method (daemon backward compat)
  - Tests now use DTO attributes (`.status`, `.error.message`) instead of dict `.get()`

---

### Batch 16: Inline init_calculation into nested method
- **Time**: 2026-02-02
- **Action**: Inlined `init_calculation` static into `project.init_calculation()` nested, converted static to thin wrapper
- **Deleted**: 0 (static now delegates to nested - needs caller migration to fully delete)
- **Delta**: No change (228 entrypoints, 26 static)
- **Tests**: 3012 passed, 18 skipped
- **Notes**:
  - Full implementation inlined into `project.init_calculation()`
  - Static method now thin wrapper (~10 lines) pending caller migration (80 callers across 37 files)
  - Constitution requires: migrate callers → delete static for real surface reduction

---

### Batch 17: [PENDING]
- **Time**:
- **Action**: Migrate init_calculation callers and delete static
- **Deleted**:
- **Delta**:
- **Tests**:

---

## Summary Table

| Batch | Date | Action | Deleted | New Total | Tests |
|-------|------|--------|---------|-----------|-------|
| 0 | 2026-02-02 | Baseline | 0 | 243 | N/A |
| 1 | 2026-02-02 | Delete generate_resource_id | 1 | 242 | PASS |
| 2 | 2026-02-02 | Delete viz/cache factory fns | 2 | 240 | PASS |
| 3 | 2026-02-02 | Delete extract_calculation_selector_from_entry | 1 | 239 | PASS |
| 4 | 2026-02-02 | Migrate compat.py to nested methods | 0 | 239 | PASS |
| 5 | 2026-02-02 | Migrate consumer tests to DTO methods | 0 | 239 | PASS |
| 6 | 2026-02-02 | Delete list_structures/calculations_data | 2 | 237 | PASS |
| 7 | 2026-02-02 | Inline get_project_summary | 1 | 236 | PASS |
| 8 | 2026-02-02 | Inline materialize_pseudo_file | 1 | 235 | PASS |
| 9 | 2026-02-02 | Inline get_pseudo_options_for_elements | 1 | 234 | PASS |
| 10 | 2026-02-02 | Inline analyze_project_pseudo_effects | 1 | 233 | PASS |
| 11 | 2026-02-02 | Inline save_relax_final_structure | 1 | 232 | PASS |
| 12 | 2026-02-02 | Inline promote_relax_structure | 1 | 231 | PASS |
| 13 | 2026-02-02 | Inline configure_species_map | 1 | 230 | PASS |
| 14 | 2026-02-02 | Inline run_calculation | 1 | 229 | PASS |
| 15 | 2026-02-02 | Inline run_step | 1 | 228 | PASS |
| 16 | 2026-02-02 | Inline init_calculation | 0* | 228 | PASS |

*Static now delegates to nested - needs caller migration for actual deletion

---

## Current State (After Batch 15)

| Category | Count |
|----------|-------|
| utils | 88 |
| service_static | 26 |
| service_nested | 91 |
| errors | 10 |
| dtos | 11 |
| api_init | 2 |
| **TOTAL** | **228** |

| Usage Status | Count |
|--------------|-------|
| Daemon only | ~108 |
| CLI only | ~50 |
| Both | ~44 |
| **UNUSED** | ~28 |

### Remaining TEMP SHIM Static Methods
- `init_calculation` (73 callers) - next target
- `import_structure` (62 callers) - after init_calculation
- `run_single_step` (daemon) - delegates to nested `run_step`

---

## Notes

### Remaining Unused Entrypoints Analysis

**Cannot delete (part of Constitution or base classes):**
- `ConflictError`, `FilesystemError`: Law H6 error taxonomy - keep
- `BaseDTO`: Base class for all DTOs - keep
- `StructureDTO`, `CalculationDTO`, `MetaDTO`: Core DTOs used in type hints - keep

**F401 entries (noqa imports):**
- `DisplayModeParams`, `OnlineStructureCache`, `QEUIParam`: Class re-exports, needed for type hints

**Service methods (unused nested services):**
- Analysis.*, Structure.*, Calculation.*, Run.*, Project.*, Engine.*: 16 unused methods
- Require service.py changes - future batch

---

**End of Worklog**
