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

### Batch 3: [PENDING]
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

---

## Current State (After Batch 2)

| Category | Count |
|----------|-------|
| utils | 88 |
| service_static | 38 |
| service_nested | 91 |
| errors | 10 |
| dtos | 11 |
| api_init | 2 |
| **TOTAL** | **240** |

| Usage Status | Count |
|--------------|-------|
| Daemon only | 115 |
| CLI only | 51 |
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
