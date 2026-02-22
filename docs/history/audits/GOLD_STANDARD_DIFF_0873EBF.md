# Gold Standard Comparison vs Commit 0873ebf

**Date**: 2026-01-21  
**Reference**: Commit 0873ebf (Implementation Plan: Multi-Frontend Refactor v2)

---

## Gold Standard Properties (from 0873ebf)

### 1. Frontend Import Isolation
**Requirement**: CLI and daemon must NOT import kernel modules directly. They may import ONLY from `qmatsuite.api.*` (plus stdlib/third-party).

**Current Status**: ✅ **PASS**
- Zero forbidden imports found in CLI
- Zero forbidden imports found in daemon
- All imports are from `qmatsuite.api.*` or `qmatsuite.api.utils.*`

### 2. API Single Source of Truth (SSOT)
**Requirement**: For any capability used by cli/daemon, there must be exactly ONE canonical entrypoint in the API layer (either instance-style method or pure transparent re-export).

**Current Status**: ⚠️ **PARTIAL**
- Instance subservices exist and are used (155+ callsites)
- BUT: 18 static method calls bypass instance subservices
- Dual-channel exists: static methods + instance methods both used

### 3. No Dual-Channel Architecture
**Requirement**: No "both exist and both are used" situations. Legacy static methods must be removed OR made unreachable from frontends.

**Current Status**: ❌ **FAIL**
- 13 project-scoped static methods are actively used by frontends
- Static methods contain logic instead of delegating to instance methods
- Creates confusion about which path is "canonical"

### 4. Static Methods as Pure Delegators
**Requirement**: If a static takes `project_root`, it must immediately delegate to `get_service(project_root).<subservice>.<method>(...)` and contain no independent logic.

**Current Status**: ❌ **FAIL**
- 13 project-scoped static methods contain logic and call kernel modules directly
- They do NOT delegate to instance methods

---

## Functionality Path Comparison

### Daemon Handlers

**Total Handlers**: 119

#### Handlers Using Instance Methods (CORRECT)
- ✅ ~38 handlers correctly use `get_service(project_root).<subservice>.<method>()`
- Examples: `_handle_get_step_detail`, `_handle_update_step_params`, `_handle_get_calculation_detail`, etc.

#### Handlers Using Static Methods (VIOLATIONS)
- ❌ 13 handlers use static methods instead of instance methods:
  - `_handle_get_project_summary` → `QMSService.get_project_summary(project_root)`
  - `_handle_list_structures` → `QMSService.list_structures_data(project_root)`
  - `_handle_list_calculations` → `QMSService.list_calculations_data(project_root)`
  - `_handle_import_structure` → `QMSService.import_structure(...)`
  - `_handle_init_calculation` → `QMSService.init_calculation(...)`
  - `_handle_run_calculation` → `func=QMSService.run_calculation`
  - `_handle_run_step` → `func=QMSService.run_step`
  - `_handle_promote_relax_structure` → `QMSService.promote_relax_structure(...)`
  - `_handle_save_relax_final_structure` → `QMSService.save_relax_final_structure(...)`
  - `_handle_analyze_project_pseudo_effects` → `QMSService.analyze_project_pseudo_effects(...)`
  - `_handle_materialize_pseudo_file` → `QMSService.materialize_pseudo_file(...)`
  - `_handle_get_pseudo_options_for_elements` → `QMSService.get_pseudo_options_for_elements(...)`

### CLI Commands

**Total Commands**: ~50+ (estimated)

#### Commands Using Instance Methods (CORRECT)
- ✅ Most commands correctly use `get_service(project_root).<subservice>.<method>()`
- Examples: `list structures`, `list calculations`, `show structure`, etc.

#### Commands Using Static Methods (VIOLATIONS)
- ❌ 3 commands use static methods:
  - `run step` → `QMSService.run_step(...)`
  - `configure species-map` → `QMSService.configure_species_map(...)`
  - `run calculation` → `QMSService.run_calculation(...)`

---

## Missing Functionality vs 0873ebf

### Missing Instance Methods

The following capabilities exist as static methods but lack instance method equivalents:

1. **`svc.project.get_summary()`** - Missing (static `get_project_summary()` exists)
2. **`svc.project.init_calculation()`** - Missing (static `init_calculation()` exists)
3. **`svc.structure.promote_relax_structure()`** - Missing (static exists)
4. **`svc.structure.save_relax_final_structure()`** - Missing (static exists)
5. **`svc.calculation.configure_species_map()`** - Missing (static exists)
6. **`svc.project.analyze_pseudo_effects()`** - Missing (static exists)
7. **`svc.project.materialize_pseudo_file()`** - Missing (static exists)
8. **`svc.project.get_pseudo_options()`** - Missing (static exists)

### Existing Instance Methods Not Used

The following instance methods exist but are NOT used (static methods used instead):

1. **`svc.structure.list()`** - Exists but daemon uses `list_structures_data()` static
2. **`svc.calculation.list()`** - Exists but daemon uses `list_calculations_data()` static
3. **`svc.structure.import_file()`** - Exists but daemon uses `import_structure()` static
4. **`svc.run.calculation()`** - Exists but CLI/daemon use `run_calculation()` static
5. **`svc.run.step()`** - Exists but CLI/daemon use `run_step()` static

---

## Divergences from Gold Standard

### Critical Divergences

1. **Dual-Channel Architecture**: Static methods and instance methods both used for same capabilities
2. **Static Methods Not Delegators**: 13 project-scoped static methods contain logic instead of delegating
3. **Missing Instance Methods**: 8 instance methods missing, causing static method usage

### Acceptable Divergences

1. **Global Operations**: Static methods for global operations (pseudo management, settings) are acceptable
2. **Bootstrap Operations**: Static methods for operations without project_root yet (`init_project`, `create_demo_project`) are acceptable

---

## Restoration Plan

### Required Changes

1. **Add 8 missing instance methods** to subservices
2. **Migrate 18 static method callsites** to use instance methods
3. **Convert 13 static methods** to pure delegators (or remove if unused)
4. **Verify zero frontend kernel imports** (already passing)

### Expected Outcome

After restoration:
- ✅ All project-scoped operations use instance methods
- ✅ Static methods are pure delegators (or removed)
- ✅ Zero dual-channel architecture
- ✅ All functionality routable through API layer

---

**End of Gold Standard Comparison**

