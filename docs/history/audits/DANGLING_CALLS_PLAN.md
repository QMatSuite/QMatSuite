# Dangling Calls Execution Plan

**Date**: 2026-01-21  
**Purpose**: Track dangling API calls and migration status

---

## Baseline (Batch 0)

**Command**: `python tools/api_dangling_calls_scanner.py --json`

**Result**:
```json
{
  "canonical_methods_count": 51,
  "dangling_calls_count": 0,
  "dangling_calls": []
}
```

**Status**: ✅ **PASS** - Zero dangling calls found

**Pytest Result**: 2554 passed, 2 skipped, 197 warnings in 80.06s

---

## Migration Plan

### Static Method Calls to Migrate

| Method | Callsite | Target Home | Action | Status |
|--------|----------|-------------|--------|--------|
| `QMSService.get_project_summary(project_root)` | `daemon/server.py:1998, 2089` | `svc.project.get_summary()` | Add instance method, migrate callsites | ⏳ Pending |
| `QMSService.list_structures_data(project_root)` | `daemon/server.py:2010, 2124` | `svc.structure.list()` | Migrate callsites (method exists) | ⏳ Pending |
| `QMSService.list_calculations_data(project_root)` | `daemon/server.py:2023, 2776` | `svc.calculation.list()` | Migrate callsites (method exists) | ⏳ Pending |
| `QMSService.init_calculation(project_root, ...)` | `daemon/server.py:2766` | `svc.project.init_calculation()` | Add instance method, migrate callsite | ⏳ Pending |
| `QMSService.run_calculation(project_root, ...)` | `cli/main.py:4010`, `daemon/server.py:5320` | `svc.run.calculation()` | Migrate callsites (method exists) | ⏳ Pending |
| `QMSService.run_step(project_root, ...)` | `cli/main.py:1753`, `daemon/server.py:5391` | `svc.run.step()` | Migrate callsites (method exists) | ⏳ Pending |
| `QMSService.import_structure(project_root, ...)` | `daemon/server.py:2116` | `svc.structure.import_file()` | Migrate callsite (method exists) | ⏳ Pending |
| `QMSService.promote_relax_structure(project_root, ...)` | `daemon/server.py:3209` | `svc.structure.promote_relax()` | Add instance method, migrate callsite | ⏳ Pending |
| `QMSService.save_relax_final_structure(project_root, ...)` | `daemon/server.py:3600` | `svc.structure.save_relax_final()` | Add instance method, migrate callsite | ⏳ Pending |
| `QMSService.configure_species_map(project_root, ...)` | `cli/main.py:3656` | `svc.calculation.configure_species_map()` | Add instance method, migrate callsite | ⏳ Pending |
| `QMSService.analyze_project_pseudo_effects(project_root, ...)` | `daemon/server.py:4461` | `svc.project.analyze_pseudo_effects()` | Add instance method, migrate callsite | ⏳ Pending |
| `QMSService.materialize_pseudo_file(project_root, ...)` | `daemon/server.py:4486` | `svc.project.materialize_pseudo_file()` | Add instance method, migrate callsite | ⏳ Pending |
| `QMSService.get_pseudo_options_for_elements(project_root, ...)` | `daemon/server.py:4576` | `svc.project.get_pseudo_options()` | Add instance method, migrate callsite | ⏳ Pending |

**Total to migrate**: 13 static method calls (18 callsites)

---

## Batch 1: Fill Missing Instance Methods

**Goal**: Add missing instance methods to subservices

### Methods to Add

1. **`svc.project.get_summary()`** → `api/service.py:5011` (Project subservice)
   - **Action**: Add method that wraps static `get_project_summary()` logic
   - **Status**: ⏳ Pending

2. **`svc.project.init_calculation(name, structure_selector, template)`** → `api/service.py:5011` (Project subservice)
   - **Action**: Add method that wraps static `init_calculation()` logic
   - **Status**: ⏳ Pending

3. **`svc.structure.promote_relax_structure(calc_selector, step_selector, name)`** → `api/service.py:1571` (Structure subservice)
   - **Action**: Add method that wraps static `promote_relax_structure()` logic
   - **Status**: ⏳ Pending

4. **`svc.structure.save_relax_final_structure(calc_selector, step_selector, parent_structure_ulid, slug_hint)`** → `api/service.py:1571` (Structure subservice)
   - **Action**: Add method that wraps static `save_relax_final_structure()` logic
   - **Status**: ⏳ Pending

5. **`svc.calculation.configure_species_map(calculation, from_qe_input, set_entries, merge)`** → `api/service.py:2119` (Calculation subservice)
   - **Action**: Add method that wraps static `configure_species_map()` logic
   - **Status**: ⏳ Pending

6. **`svc.project.analyze_pseudo_effects(selections)`** → `api/service.py:5011` (Project subservice)
   - **Action**: Add method that wraps static `analyze_project_pseudo_effects()` logic
   - **Status**: ⏳ Pending

7. **`svc.project.materialize_pseudo_file(element, sha256, preferred_basename)`** → `api/service.py:5011` (Project subservice)
   - **Action**: Add method that wraps static `materialize_pseudo_file()` logic
   - **Status**: ⏳ Pending

8. **`svc.project.get_pseudo_options(elements, config)`** → `api/service.py:5011` (Project subservice)
   - **Action**: Add method that wraps static `get_pseudo_options_for_elements()` logic
   - **Status**: ⏳ Pending

**After Batch 1**:
- Dangling count: 0 (no change, methods exist but not used)
- Pytest: Must pass

---

## Batch 2: Migrate Daemon Callsites

**Goal**: Replace static method calls with instance method calls in daemon

### Migrations

1. `daemon/server.py:1998, 2089` → `QMSService.get_project_summary(project_root)` → `get_service(project_root).project.get_summary()`
2. `daemon/server.py:2010, 2124` → `QMSService.list_structures_data(project_root)` → `get_service(project_root).structure.list()`
3. `daemon/server.py:2023, 2776` → `QMSService.list_calculations_data(project_root)` → `get_service(project_root).calculation.list()`
4. `daemon/server.py:2116` → `QMSService.import_structure(...)` → `get_service(project_root).structure.import_file(...)`
5. `daemon/server.py:2766` → `QMSService.init_calculation(...)` → `get_service(project_root).project.init_calculation(...)`
6. `daemon/server.py:3209` → `QMSService.promote_relax_structure(...)` → `get_service(project_root).structure.promote_relax_structure(...)`
7. `daemon/server.py:3600` → `QMSService.save_relax_final_structure(...)` → `get_service(project_root).structure.save_relax_final_structure(...)`
8. `daemon/server.py:4461` → `QMSService.analyze_project_pseudo_effects(...)` → `get_service(project_root).project.analyze_pseudo_effects(...)`
9. `daemon/server.py:4486` → `QMSService.materialize_pseudo_file(...)` → `get_service(project_root).project.materialize_pseudo_file(...)`
10. `daemon/server.py:4576` → `QMSService.get_pseudo_options_for_elements(...)` → `get_service(project_root).project.get_pseudo_options(...)`
11. `daemon/server.py:5320` → `func=QMSService.run_calculation` → `get_service(project_root).run.calculation(...)`
12. `daemon/server.py:5391` → `func=QMSService.run_step` → `get_service(project_root).run.step(...)`

**After Batch 2**:
- Dangling count: 0 (should remain)
- Pytest: Must pass

---

## Batch 3: Migrate CLI Callsites

**Goal**: Replace static method calls with instance method calls in CLI

### Migrations

1. `cli/main.py:1753` → `QMSService.run_step(...)` → `get_service(project_root).run.step(...)`
2. `cli/main.py:3656` → `QMSService.configure_species_map(...)` → `get_service(project_root).calculation.configure_species_map(...)`
3. `cli/main.py:4010` → `QMSService.run_calculation(...)` → `get_service(project_root).run.calculation(...)`

**After Batch 3**:
- Dangling count: 0 (should remain)
- Pytest: Must pass

---

## Batch 4: Remove Legacy Dual-Channel Access

**Goal**: Ensure no frontend calls legacy static methods for project-scoped operations

### Verification

1. Check for remaining static calls:
   ```bash
   grep -r "QMSService\.\(get_project_summary\|list_structures_data\|list_calculations_data\|init_calculation\|run_calculation\|run_step\|import_structure\|promote_relax_structure\|save_relax_final_structure\|configure_species_map\|analyze_project_pseudo_effects\|materialize_pseudo_file\|get_pseudo_options_for_elements\)" src/qmatsuite/cli src/qmatsuite/daemon
   ```
   - Expected: Zero matches (or only in comments)

2. Mark remaining static methods as TEMP SHIM:
   - Add `# TEMP SHIM for PR; TODO relocate to <Subservice>` comment
   - Ensure they are NOT called by frontends

**After Batch 4**:
- Dangling count: 0 (should remain)
- Pytest: Must pass
- No frontend calls to project-scoped static methods

---

## Final Status

**Target**: All project-scoped operations use instance methods, zero dangling calls, zero frontend kernel imports.

**Final Results**:
- ✅ Dangling calls: **0** (unchanged from baseline)
- ✅ Frontend kernel imports: **0** (only comment in daemon/server.py)
- ✅ All project-scoped static methods marked as **TEMP SHIM**
- ✅ All frontend callsites migrated to instance methods:
  - CLI: 3 callsites migrated
  - Daemon: 12 callsites migrated (including job manager wrappers)

**End of Execution Plan**

