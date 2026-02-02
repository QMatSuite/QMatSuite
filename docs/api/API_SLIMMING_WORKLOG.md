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

### Batch 7: [PENDING]
- **Time**:
- **Action**:
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

---

## Current State (After Batch 6)

| Category | Count |
|----------|-------|
| utils | 88 |
| service_static | 35 |
| service_nested | 91 |
| errors | 10 |
| dtos | 11 |
| api_init | 2 |
| **TOTAL** | **237** |

| Usage Status | Count |
|--------------|-------|
| Daemon only | 113 |
| CLI only | 50 |
| Both | 44 |
| **UNUSED** | **30** |

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
