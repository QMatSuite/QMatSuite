# Multi-Frontend Refactor Compliance Audit (Stop-the-Bleeding Scope)

**Date**: 2026-01-21  
**Auditor**: Independent Adversarial Reviewer  
**Reference Commit**: 0873ebf (Implementation Plan: Multi-Frontend Refactor v2)  
**Scope**: Stop-the-bleeding compliance check

---

## A) Import Isolation Audit

### Commands Executed

```bash
# Check for forbidden kernel imports in CLI
rg -n "^from qmatsuite\.(core|calculation|analysis|engine|project|execution|presets|workflow|ir|drivers|io|parsers|viz|legacy|data|history)" src/qmatsuite/cli/ src/qmatsuite/daemon/

# Check for forbidden kernel imports (import statement style)
rg -n "^import qmatsuite\.(core|calculation|analysis|engine|project|execution|presets|workflow|ir|drivers|io|parsers|viz|legacy|data|history)" src/qmatsuite/cli/ src/qmatsuite/daemon/
```

### Results

**CLI (`src/qmatsuite/cli/main.py`)**:
- ✅ **PASS**: Zero forbidden imports found
- All imports are from `qmatsuite.api.*` or `qmatsuite.api.utils.*` or `qmatsuite.api.qe_io.*`
- Lines 26-33: Imports from `qmatsuite.api` only
- Lines 34-54: Imports from `qmatsuite.api.utils` only
- Line 63: Imports from `qmatsuite.api.qe_io` only

**Daemon (`src/qmatsuite/daemon/server.py`)**:
- ✅ **PASS**: Zero forbidden imports found
- All imports are from `qmatsuite.api.*` or `qmatsuite.api.utils.*` or `qmatsuite.daemon.jobs.*`
- Line 31: `from qmatsuite.api import QMSService, APIError, get_service`
- Lines 32-78: Imports from `qmatsuite.api.utils` only
- Line 79: `from qmatsuite.daemon.jobs import JobManager, JobStatus`

### Conclusion

**✅ GOAL 1 PASS**: CLI and daemon do NOT import any kernel modules directly. They import ONLY from `qmatsuite.api.*` (plus stdlib/third-party).

---

## B) Dual Channel Audit

### Static Method Callsites Analysis

#### CLI Static Method Calls (6 instances)

| File:Line | Call | Classification | Analysis |
|-----------|------|----------------|----------|
| `cli/main.py:1257` | `QMSService.generate_kpath(...)` | **GLOBAL OK** | Pure utility, no project_root needed |
| `cli/main.py:1276` | `QMSService.get_default_step_params(step_type)` | **GLOBAL OK** | Pure utility, no project_root needed |
| `cli/main.py:1753` | `QMSService.run_step(...)` | **PROJECT-SCOPED (VIOLATION)** | Takes `project_root`, has logic, calls kernel directly |
| `cli/main.py:3656` | `QMSService.configure_species_map(...)` | **PROJECT-SCOPED (VIOLATION)** | Takes `project_root`, delegates to kernel but not to instance method |
| `cli/main.py:4010` | `QMSService.run_calculation(...)` | **PROJECT-SCOPED (VIOLATION)** | Takes `project_root`, has logic, calls kernel directly |
| `cli/main.py:57` | Comment only | N/A | Documentation reference |

**CLI Violations**: 3 project-scoped static calls that should use instance methods.

#### Daemon Static Method Calls (40 instances)

| File:Line | Call | Classification | Analysis |
|-----------|------|----------------|----------|
| `daemon/server.py:237` | `QMSService.get_settings()` | **GLOBAL OK** | Global user settings, no project_root |
| `daemon/server.py:1424` | `QMSService.get_settings()` | **GLOBAL OK** | Global user settings |
| `daemon/server.py:3046` | `QMSService.get_settings()` | **GLOBAL OK** | Global user settings |
| `daemon/server.py:4347` | `QMSService.get_settings()` | **GLOBAL OK** | Global user settings |
| `daemon/server.py:845` | `QMSService.init_pseudo_dirs()` | **GLOBAL OK** | Global pseudo config, no project_root |
| `daemon/server.py:1073` | `QMSService.list_pseudo_libraries()` | **GLOBAL OK** | Global pseudo libraries |
| `daemon/server.py:1096` | `QMSService.get_library_status(...)` | **GLOBAL OK** | Global pseudo library status |
| `daemon/server.py:1135` | `QMSService.install_pseudo_library(...)` | **GLOBAL OK** | Global pseudo library install |
| `daemon/server.py:1164` | `QMSService.remove_pseudo_library(...)` | **GLOBAL OK** | Global pseudo library removal |
| `daemon/server.py:1187` | `QMSService.repair_pseudo_library(...)` | **GLOBAL OK** | Global pseudo library repair |
| `daemon/server.py:1198` | `QMSService.compute_store_size()` | **GLOBAL OK** | Global pseudo store size |
| `daemon/server.py:1331` | `QMSService.is_pseudo_archive_installed(...)` | **GLOBAL OK** | Global pseudo archive check |
| `daemon/server.py:1354` | `QMSService.install_pseudo_archive(...)` | **GLOBAL OK** | Global pseudo archive install |
| `daemon/server.py:889` | `QMSService.install_sssp_from_seed(...)` | **GLOBAL OK** | Global SSSP install |
| `daemon/server.py:893` | `QMSService.install_all_sssp_from_seed(...)` | **GLOBAL OK** | Global SSSP install |
| `daemon/server.py:974` | `QMSService.download_sssp_library(...)` | **GLOBAL OK** | Global SSSP download |
| `daemon/server.py:1018` | `QMSService.download_all_sssp(...)` | **GLOBAL OK** | Global SSSP download |
| `daemon/server.py:1062` | `QMSService.import_seed_archives(...)` | **GLOBAL OK** | Global seed import |
| `daemon/server.py:2077` | `QMSService.init_project(...)` | **GLOBAL OK** | Creates new project (no project_root yet) |
| `daemon/server.py:4634` | `QMSService.create_demo_project(...)` | **GLOBAL OK** | Creates new project |
| `daemon/server.py:4657` | `QMSService.list_demo_projects()` | **GLOBAL OK** | Lists demos (no project_root needed) |
| `daemon/server.py:6300` | `QMSService.get_workflow_service()` | **GLOBAL OK** | Returns service object |
| `daemon/server.py:6334` | `QMSService.get_workflow_service()` | **GLOBAL OK** | Returns service object |
| `daemon/server.py:6417` | `QMSService.get_workflow_service()` | **GLOBAL OK** | Returns service object |
| `daemon/server.py:6488` | `QMSService.get_workflow_service()` | **GLOBAL OK** | Returns service object |
| `daemon/server.py:1998` | `QMSService.get_project_summary(project_root)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:2089` | `QMSService.get_project_summary(project_root)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic |
| `daemon/server.py:2010` | `QMSService.list_structures_data(project_root)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:2124` | `QMSService.list_structures_data(project_root)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic |
| `daemon/server.py:2023` | `QMSService.list_calculations_data(project_root)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:2776` | `QMSService.list_calculations_data(project_root)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic |
| `daemon/server.py:2116` | `QMSService.import_structure(...)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:2766` | `QMSService.init_calculation(...)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:3209` | `QMSService.promote_relax_structure(...)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:3600` | `QMSService.save_relax_final_structure(...)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:4461` | `QMSService.analyze_project_pseudo_effects(...)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:4486` | `QMSService.materialize_pseudo_file(...)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:4576` | `QMSService.get_pseudo_options_for_elements(...)` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:5320` | `func=QMSService.run_calculation` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:5391` | `func=QMSService.run_step` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |
| `daemon/server.py:5446` | `func=QMSService.run_single_step` | **PROJECT-SCOPED (VIOLATION)** | Takes project_root, has logic, calls kernel directly |

**Daemon Violations**: 15 project-scoped static calls that should use instance methods.

### Static Method Implementation Analysis

#### Project-Scoped Static Methods (MUST DELEGATE)

| Static Method | File:Line | Is Pure Delegator? | Analysis |
|---------------|-----------|-------------------|----------|
| `get_project_summary(project_root)` | `api/service.py:6104` | ❌ **NO** | Has logic: calls `load_project_config`, `list_structures`, `list_calculations` directly |
| `list_structures_data(project_root)` | `api/service.py:6167` | ❌ **NO** | Has logic: calls `list_structures`, `read_structure` directly |
| `list_calculations_data(project_root)` | `api/service.py:6227` | ❌ **NO** | Has logic: calls `list_calculations`, `Project.open`, `Calculation.from_yaml` directly |
| `init_calculation(project_root, ...)` | `api/service.py:6310` | ❌ **NO** | Has logic: calls kernel modules directly, creates files |
| `init_step(project_root, ...)` | `api/service.py:6430` | ❌ **NO** | Has logic: calls kernel modules directly |
| `run_calculation(project_root, ...)` | `api/service.py:6552` | ❌ **NO** | Has logic: calls `Project.open`, `Calculation.from_yaml`, `CalculationRunner` directly |
| `run_step(project_root, ...)` | `api/service.py:6649` | ❌ **NO** | Has logic: calls `Project.open`, `Calculation.from_yaml`, `CalculationRunner` directly |
| `import_structure(project_root, ...)` | `api/service.py:6779` | ❌ **NO** | Has logic: calls kernel modules directly, creates files |
| `promote_relax_structure(project_root, ...)` | `api/service.py:6898` | ❌ **NO** | Has logic: calls kernel modules directly |
| `save_relax_final_structure(project_root, ...)` | `api/service.py:7206` | ❌ **NO** | Has logic: calls kernel modules directly, creates files |
| `configure_species_map(project_root, ...)` | `api/service.py:6977` | ⚠️ **PARTIAL** | Delegates to `qmatsuite.calculation.species_config.configure_species_map` but not to instance method |
| `analyze_project_pseudo_effects(project_root, ...)` | `api/service.py:7693` | ❌ **NO** | Has logic: calls kernel modules directly |
| `materialize_pseudo_file(project_root, ...)` | `api/service.py:7748` | ❌ **NO** | Has logic: calls kernel modules directly |
| `get_pseudo_options_for_elements(project_root, ...)` | `api/service.py:7775` | ❌ **NO** | Has logic: calls kernel modules directly |

**Violation Count**: 13 project-scoped static methods that are NOT pure delegators.

#### Global Static Methods (ACCEPTABLE)

| Static Method | File:Line | Is Pure Delegator? | Analysis |
|---------------|-----------|-------------------|----------|
| `init_project(target_dir, ...)` | `api/service.py:5973` | ⚠️ **PARTIAL** | Has logic but no project_root yet (acceptable) |
| `get_settings()` | `api/service.py:6049` | ⚠️ **PARTIAL** | Calls `load_settings()` directly (global operation, acceptable) |
| `get_workflow_service()` | `api/service.py:6093` | ✅ **YES** | Pure delegator: `return _get_workflow_service()` |
| `get_default_step_params(step_type)` | `api/service.py:7046` | ✅ **YES** | Pure delegator: `return _get_default_step_params(step_type)` |
| `generate_kpath(structure, ...)` | `api/service.py:7063` | ✅ **YES** | Pure delegator: `return _generate_kpath(...)` |
| `create_demo_project(...)` | `api/service.py:7093` | ⚠️ **PARTIAL** | Has logic but no project_root yet (acceptable) |
| `list_demo_projects()` | `api/service.py:7167` | ⚠️ **PARTIAL** | Has logic but no project_root needed (acceptable) |
| All pseudo management statics | `api/service.py:7381+` | ⚠️ **PARTIAL** | Global operations, call kernel directly (acceptable for global ops) |

### Conclusion

**❌ GOAL 3 FAIL**: 13 project-scoped static methods are NOT pure delegators. They contain logic and call kernel modules directly instead of delegating to `get_service(project_root).<subservice>.<method>()`.

---

## C) API Surface Inventory

### Subservice Methods Inventory

#### `svc.project` Subservice (`api/service.py:5011`)

| Method | File:Line | Callsites (CLI) | Callsites (Daemon) | Callsites (Tests) |
|--------|-----------|-----------------|-------------------|-------------------|
| `get_config()` | `api/service.py:5017` | `cli/main.py:798, 1052, 1487, 2005, 2280, 2351, 2385, 2459, 2593, 2797, 2862, 3313, 3611, 3680, 3720, 3934, 4131, 4250, 4272, 4559, 5319` (21) | `daemon/server.py:159, 181` (2) | Unknown |
| `update_config(patch)` | `api/service.py:5035` | `cli/main.py:881, 943, 1521, 2291, 2362, 2428, 2733, 2828, 3378, 3793` (10) | None | Unknown |
| `get_species_map()` | `api/service.py:5066` | None | None | Unknown |
| `get_potential_map()` | `api/service.py:5090` | None | None | Unknown |
| `build_resource_index()` | `api/service.py:5112` | `cli/main.py:1694, 2166, 2284, 3438, 3501, 3937` (6) | `daemon/server.py:160, 182` (2) | Unknown |
| `list_calculations()` | `api/service.py:5130` | None | None | Unknown |
| `collect_slugs(entries, ...)` | `api/service.py:5148` | `cli/main.py:1489` (1) | None | Unknown |
| `apply_structure_rename(...)` | `api/service.py:5167` | `cli/main.py:2284` (1) | None | Unknown |
| `apply_calculation_rename(...)` | `api/service.py:5198` | `cli/main.py:2355, 3371` (2) | None | Unknown |
| `import_pseudo_files(file_paths)` | `api/service.py:5229` | None | `daemon/server.py:3407` (1) | Unknown |

**Total CLI callsites**: 41  
**Total Daemon callsites**: 5

#### `svc.structure` Subservice (`api/service.py:1571`)

| Method | File:Line | Callsites (CLI) | Callsites (Daemon) | Callsites (Tests) |
|--------|-----------|-----------------|-------------------|-------------------|
| `get(selector)` | `api/service.py:1577` | `cli/main.py:235, 3437, 3724, 4148` (4) | None | Unknown |
| `list()` | `api/service.py:1624` | `cli/main.py:2019` (1) | None (TODO comment at line 2008) | Unknown |
| `import_file(file_path, ...)` | `api/service.py:1807` | None | None | Unknown |
| `get_vis_data(selector, params)` | `api/service.py:1911` | None | `daemon/server.py:4741` (1) | Unknown |
| `require_ref(selector, ...)` | Not found in search | `cli/main.py:654, 892, 1205, 1324, 2109, 2274, 2587, 2718, 3476, 5391` (10) | `daemon/server.py:5633` (1) | Unknown |

**Total CLI callsites**: 15  
**Total Daemon callsites**: 2

#### `svc.calculation` Subservice (`api/service.py:2119`)

| Method | File:Line | Callsites (CLI) | Callsites (Daemon) | Callsites (Tests) |
|--------|-----------|-----------------|-------------------|-------------------|
| `get(selector)` | `api/service.py:2364` | `cli/main.py:2352, 2460, 2801, 3317, 3681, 4133, 4251, 5331` (8) | None | Unknown |
| `list()` | `api/service.py:2179` | `cli/main.py:2050` (1) | None (TODO comment at line 2021) | Unknown |
| `get_step(calc_selector, step_selector)` | `api/service.py:2364` | None | `daemon/server.py:3095` (1) | Unknown |
| `list_steps(calc_selector)` | `api/service.py:2429` | None | `daemon/server.py:4207` (1) | Unknown |
| `get_effective_params(calc_selector)` | `api/service.py:2492` | None | None | Unknown |
| `get_detail(selector)` | `api/service.py:3124` | None | `daemon/server.py:4103, 4553` (2) | Unknown |
| `set_structure(calc_selector, structure_selector)` | `api/service.py:3229` | None | `daemon/server.py:4323` (1) | Unknown |
| `get_common_cards(calc_selector)` | `api/service.py:3318` | None | `daemon/server.py:3294` (1) | Unknown |
| `remove_step(calc_selector, step_selector)` | `api/service.py:3559` | None | `daemon/server.py:3649` (1) | Unknown |
| `set_common_card(calc_selector, card_name, card_data)` | `api/service.py:3684` | None | `daemon/server.py:3294` (1) | Unknown |
| `get_step_pseudo_mapping(calc_selector, step_selector)` | `api/service.py:3756` | None | `daemon/server.py:3333` (1) | Unknown |
| `set_step_pseudo_mapping(calc_selector, step_selector, mapping)` | `api/service.py:3887` | None | `daemon/server.py:3376` (1) | Unknown |
| `import_step_from_qe_input(calc_selector, input_file, ...)` | `api/service.py:4082` | None | `daemon/server.py:4207` (1) | Unknown |
| `get_pseudo_mapping(calc_selector)` | `api/service.py:4166` | None | `daemon/server.py:4385` (1) | Unknown |
| `require_ref(selector, ...)` | Not found in search | `cli/main.py:1069, 1079, 1090, 1160, 1682, 1707, 1732, 2057, 2464, 2587, 2697, 2805, 2820, 2869, 2902, 3352, 3385, 3394, 3685, 3962, 3986, 4255, 4282, 4568, 5339` (25) | `daemon/server.py:5611` (1) | Unknown |
| `require_step_ref(calc_selector, step_selector, ...)` | Not found in search | `cli/main.py:1686, 1709, 1732, 2193, 2893, 3462` (6) | `daemon/server.py:5656` (1) | Unknown |
| `rename(...)` | Not found in search | None | `daemon/server.py:2815` (1) | Unknown |
| `can_delete(calculation_ulid)` | Not found in search | None | `daemon/server.py:2886, 2992` (2) | Unknown |
| `delete(calc_id)` | Not found in search | `cli/main.py:2695, 2820` (2) | `daemon/server.py:3004` (1) | Unknown |
| `update_step_params(...)` | Not found in search | None | `daemon/server.py:3181` (1) | Unknown |
| `reset_step_params(...)` | Not found in search | None | `daemon/server.py:3535` (1) | Unknown |
| `reorder_steps(...)` | Not found in search | None | `daemon/server.py:4127` (1) | Unknown |
| `add_step(...)` | Not found in search | None | `daemon/server.py:4157` (1) | Unknown |
| `update_species_map(...)` | Not found in search | None | `daemon/server.py:4424` (1) | Unknown |
| `resolve_enclosing_path()` | Not found in search | `cli/main.py:1079, 2805, 2869, 3320, 3612, 3969, 4273, 4560, 5331` (9) | None | Unknown |

**Total CLI callsites**: 51  
**Total Daemon callsites**: 20

#### `svc.run` Subservice (`api/service.py:4322`)

| Method | File:Line | Callsites (CLI) | Callsites (Daemon) | Callsites (Tests) |
|--------|-----------|-----------------|-------------------|-------------------|
| `run_calculation(calc_selector, steps)` | `api/service.py:4328` | None | None | Unknown |
| `run_step(calc_selector, step_selector)` | `api/service.py:4422` | None | None | Unknown |
| `get_status(run_id)` | `api/service.py:4551` | None | None | Unknown |
| `list()` | `api/service.py:4743` | None | None | Unknown |
| `preflight(...)` | Not found in search | None | `daemon/server.py:4611` (1) | Unknown |

**Total CLI callsites**: 0  
**Total Daemon callsites**: 1

#### `svc.analysis` Subservice (`api/service.py:47`)

| Method | File:Line | Callsites (CLI) | Callsites (Daemon) | Callsites (Tests) |
|--------|-----------|-----------------|-------------------|-------------------|
| `get_summary(calc_selector, step_selector)` | `api/service.py:53` | None | None | Unknown |
| `list_properties(calc_selector, step_selector)` | `api/service.py:104` | None | None | Unknown |
| `get_property_ref(calc_selector, step_selector, property_name)` | `api/service.py:152` | None | None | Unknown |
| `analyze_band(...)` | `api/service.py:361` | `cli/main.py:4585` (1) | None | Unknown |
| `analyze_dos(...)` | `api/service.py:535` | `cli/main.py:4672` (1) | None | Unknown |
| `analyze_scf(...)` | `api/service.py:1152` | `cli/main.py:4738` (1) | None | Unknown |
| `get_relax_final_structure_preview(...)` | `api/service.py:1470` | None | `daemon/server.py:3568` (1) | Unknown |
| `ensure_analysis(...)` | Not found in search | None | `daemon/server.py:4706` (1) | Unknown |
| `get_scf_convergence_data(...)` | `api/service.py:763` | None | `daemon/server.py:4766` (1) | Unknown |
| `get_dos_data(...)` | `api/service.py:1285` | None | `daemon/server.py:4790` (1) | Unknown |
| `get_band_structure_data(...)` | `api/service.py:663` | None | `daemon/server.py:4815` (1) | Unknown |
| `get_reference_analysis(...)` | `api/service.py:1372` | None | `daemon/server.py:4857` (1) | Unknown |
| `list_step_artifacts(calc_selector, step_selector)` | `api/service.py:853` | None | `daemon/server.py:4960` (1) | Unknown |
| `read_step_artifact_text(...)` | Not found in search | None | `daemon/server.py:4988` (1) | Unknown |

**Total CLI callsites**: 3  
**Total Daemon callsites**: 9

#### `svc.engine` Subservice (`api/service.py:5338`)

| Method | File:Line | Callsites (CLI) | Callsites (Daemon) | Callsites (Tests) |
|--------|-----------|-----------------|-------------------|-------------------|
| `list()` | `api/service.py:5344` | None | None | Unknown |
| `get_info(engine_name)` | `api/service.py:5370` | None | None | Unknown |
| `list_step_types(engine_name)` | `api/service.py:5419` | None | None | Unknown |

**Total CLI callsites**: 0  
**Total Daemon callsites**: 0

#### `svc.history` Subservice (`api/service.py:5591`)

| Method | File:Line | Callsites (CLI) | Callsites (Daemon) | Callsites (Tests) |
|--------|-----------|-----------------|-------------------|-------------------|
| `get_timeline(calc_id, limit)` | `api/service.py:5597` | None | `daemon/server.py:6114` (1) | Unknown |
| `get_run_revision(run_id)` | `api/service.py:5699` | None | `daemon/server.py:6132` (1) | Unknown |
| `list_runs(calc_id, limit)` | `api/service.py:5729` | None | `daemon/server.py:6152` (1) | Unknown |
| `pin_analysis(...)` | Not found in search | None | `daemon/server.py:6189` (1) | Unknown |
| `can_pin(run_id, step_id)` | Not found in search | None | `daemon/server.py:6216` (1) | Unknown |
| `get_pin_data(run_id, step_id, analysis_kind)` | `api/service.py:5834` | None | `daemon/server.py:6240` (1) | Unknown |
| `get_latest_run_for_step(step_id)` | `api/service.py:5861` | None | `daemon/server.py:6262` (1) | Unknown |
| `delete(confirm)` | `api/service.py:5904` | None | `daemon/server.py:6287` (1) | Unknown |

**Total CLI callsites**: 0  
**Total Daemon callsites**: 8

### Static Methods Inventory

See Section B for detailed analysis. Summary:
- **13 project-scoped static methods** that are NOT pure delegators (VIOLATIONS)
- **~15 global static methods** that are acceptable (GLOBAL OK)

### Conclusion

**⚠️ GOAL 2 PARTIAL**: Instance subservices exist and are used in many places (110+ CLI callsites, 45+ daemon callsites), but 18 project-scoped static method calls still bypass the subservice architecture.

---

## D) Gold Standard Parity

### Daemon Handler Analysis

**Total Handlers**: 119 (from `def _handle_` pattern in `daemon/server.py`)

#### Handlers Using Instance Methods (CORRECT)

| Handler | Implementation | Status |
|---------|----------------|--------|
| Cache building | `svc = get_service(project_root); svc.project.get_config(); svc.project.build_resource_index()` | ✅ Correct |
| `_handle_rename_calculation` | `svc.calculation.rename(...)` | ✅ Correct |
| `_handle_can_delete_calculation` | `svc.calculation.can_delete(...)` | ✅ Correct |
| `_handle_delete_calculation` | `svc.calculation.delete(...)` | ✅ Correct |
| `_handle_get_step_detail` | `svc.calculation.get_step(...)` | ✅ Correct |
| `_handle_update_step_params` | `svc.calculation.update_step_params(...)` | ✅ Correct |
| `_handle_get_common_cards` | `svc.calculation.get_common_cards(...)` | ✅ Correct |
| `_handle_set_common_card` | `svc.calculation.set_common_card(...)` | ✅ Correct |
| `_handle_get_step_pseudo_mapping` | `svc.calculation.get_step_pseudo_mapping(...)` | ✅ Correct |
| `_handle_set_step_pseudo_mapping` | `svc.calculation.set_step_pseudo_mapping(...)` | ✅ Correct |
| `_handle_import_pseudo_files` | `svc.project.import_pseudo_files(...)` | ✅ Correct |
| `_handle_reset_step_params` | `svc.calculation.reset_step_params(...)` | ✅ Correct |
| `_handle_get_relax_final_structure_preview` | `svc.analysis.get_relax_final_structure_preview(...)` | ✅ Correct |
| `_handle_remove_step` | `svc.calculation.remove_step(...)` | ✅ Correct |
| `_handle_get_calculation_detail` | `svc.calculation.get_detail(...)` | ✅ Correct |
| `_handle_reorder_steps` | `svc.calculation.reorder_steps(...)` | ✅ Correct |
| `_handle_add_step` | `svc.calculation.add_step(...)` | ✅ Correct |
| `_handle_list_steps` | `svc.calculation.list_steps(...)` | ✅ Correct |
| `_handle_import_step_from_qe_input` | `svc.calculation.import_step_from_qe_input(...)` | ✅ Correct |
| `_handle_set_calculation_structure` | `svc.calculation.set_structure(...)` | ✅ Correct |
| `_handle_get_calculation_pseudo_mapping` | `svc.calculation.get_pseudo_mapping(...)` | ✅ Correct |
| `_handle_update_calculation_species_map` | `svc.calculation.update_species_map(...)` | ✅ Correct |
| `_handle_preflight_calculation` | `svc.run.preflight(...)` | ✅ Correct |
| `_handle_ensure_analysis` | `svc.analysis.ensure_analysis(...)` | ✅ Correct |
| `_handle_get_structure_vis_data` | `svc.structure.get_vis_data(...)` | ✅ Correct |
| `_handle_get_scf_convergence_data` | `svc.analysis.get_scf_convergence_data(...)` | ✅ Correct |
| `_handle_get_dos_data` | `svc.analysis.get_dos_data(...)` | ✅ Correct |
| `_handle_get_band_structure_data` | `svc.analysis.get_band_structure_data(...)` | ✅ Correct |
| `_handle_get_reference_analysis` | `svc.analysis.get_reference_analysis(...)` | ✅ Correct |
| `_handle_list_step_artifacts` | `svc.analysis.list_step_artifacts(...)` | ✅ Correct |
| `_handle_read_step_artifact_text` | `svc.analysis.read_step_artifact_text(...)` | ✅ Correct |
| `_handle_get_timeline` | `svc.history.get_timeline(...)` | ✅ Correct |
| `_handle_get_run_revision` | `svc.history.get_run_revision(...)` | ✅ Correct |
| `_handle_list_runs` | `svc.history.list_runs(...)` | ✅ Correct |
| `_handle_pin_analysis` | `svc.history.pin_analysis(...)` | ✅ Correct |
| `_handle_can_pin` | `svc.history.can_pin(...)` | ✅ Correct |
| `_handle_get_pin_data` | `svc.history.get_pin_data(...)` | ✅ Correct |
| `_handle_get_latest_run_for_step` | `svc.history.get_latest_run_for_step(...)` | ✅ Correct |
| `_handle_delete_history` | `svc.history.delete(...)` | ✅ Correct |

**Count**: ~38 handlers use instance methods correctly.

#### Handlers Using Static Methods (VIOLATIONS)

| Handler | Current Implementation | Should Use | Status |
|---------|----------------------|------------|--------|
| `_handle_get_project_summary` | `QMSService.get_project_summary(project_root)` | `get_service(project_root).project.get_summary()` | ❌ VIOLATION |
| `_handle_list_structures` | `QMSService.list_structures_data(project_root)` | `get_service(project_root).structure.list()` | ❌ VIOLATION |
| `_handle_list_calculations` | `QMSService.list_calculations_data(project_root)` | `get_service(project_root).calculation.list()` | ❌ VIOLATION |
| `_handle_import_structure` | `QMSService.import_structure(...)` | `get_service(project_root).structure.import_file(...)` | ❌ VIOLATION |
| `_handle_init_calculation` | `QMSService.init_calculation(...)` | `get_service(project_root).calculation.init(...)` | ❌ VIOLATION |
| `_handle_run_calculation` | `func=QMSService.run_calculation` | `get_service(project_root).run.calculation(...)` | ❌ VIOLATION |
| `_handle_run_step` | `func=QMSService.run_step` | `get_service(project_root).run.step(...)` | ❌ VIOLATION |
| `_handle_run_single_step` | `func=QMSService.run_single_step` | Instance method (TBD) | ❌ VIOLATION |
| `_handle_promote_relax_structure` | `QMSService.promote_relax_structure(...)` | Instance method (TBD) | ❌ VIOLATION |
| `_handle_save_relax_final_structure` | `QMSService.save_relax_final_structure(...)` | Instance method (TBD) | ❌ VIOLATION |
| `_handle_analyze_project_pseudo_effects` | `QMSService.analyze_project_pseudo_effects(...)` | Instance method (TBD) | ❌ VIOLATION |
| `_handle_materialize_pseudo_file` | `QMSService.materialize_pseudo_file(...)` | Instance method (TBD) | ❌ VIOLATION |
| `_handle_get_pseudo_options_for_elements` | `QMSService.get_pseudo_options_for_elements(...)` | Instance method (TBD) | ❌ VIOLATION |

**Count**: 13 handlers use static methods (violations).

### Parity Gaps vs 0873ebf

**Missing Instance Methods** (cannot route through subservices):

1. **Project subservice**:
   - `get_summary()` - Missing (static `get_project_summary()` exists but not as instance method)

2. **Structure subservice**:
   - `import_file()` - EXISTS but not used (daemon uses static `import_structure()`)

3. **Calculation subservice**:
   - `init()` - Missing (static `init_calculation()` exists but not as instance method)

4. **Run subservice**:
   - `run_calculation()` - EXISTS but not used (daemon uses static)
   - `run_step()` - EXISTS but not used (daemon uses static)
   - `run_single_step()` - Missing (static exists but not as instance method)

5. **Structure/Calculation subservices**:
   - `promote_relax_structure()` - Missing (no instance method)
   - `save_relax_final_structure()` - Missing (no instance method)

6. **Project subservice**:
   - `analyze_pseudo_effects()` - Missing (no instance method)
   - `materialize_pseudo_file()` - Missing (no instance method)
   - `get_pseudo_options()` - Missing (no instance method)

### Concrete Repro Steps for Broken Functionality

**None identified**: All daemon handlers appear to work, but they use static methods instead of instance methods, violating the architecture.

### Conclusion

**⚠️ GOAL 4 PARTIAL**: Most daemon handlers work, but 13 handlers use static methods instead of instance methods. Some instance methods exist but are not used (e.g., `svc.run.calculation()`, `svc.run.step()`, `svc.structure.import_file()`).

---

## E) Recommendations

### Batch 1: Convert Static Methods to Pure Delegators (High Priority)

**Goal**: Make all project-scoped static methods pure delegators that call instance methods.

**Changes**:

1. **`get_project_summary(project_root)`** → Delegate to `get_service(project_root).project.get_summary()`
   - **File**: `src/qmatsuite/api/service.py:6104`
   - **Action**: Add `get_summary()` to `Project` subservice, make static delegate to it
   - **Test**: `pytest tests/unit/test_api_service.py::test_project_get_summary`

2. **`list_structures_data(project_root)`** → Delegate to `get_service(project_root).structure.list()`
   - **File**: `src/qmatsuite/api/service.py:6167`
   - **Action**: Make static delegate to `svc.structure.list()` (method already exists)
   - **Test**: `pytest tests/unit/test_api_service.py::test_structure_list`

3. **`list_calculations_data(project_root)`** → Delegate to `get_service(project_root).calculation.list()`
   - **File**: `src/qmatsuite/api/service.py:6227`
   - **Action**: Make static delegate to `svc.calculation.list()` (method already exists)
   - **Test**: `pytest tests/unit/test_api_service.py::test_calculation_list`

4. **`import_structure(project_root, ...)`** → Delegate to `get_service(project_root).structure.import_file(...)`
   - **File**: `src/qmatsuite/api/service.py:6779`
   - **Action**: Make static delegate to `svc.structure.import_file()` (method already exists)
   - **Test**: `pytest tests/unit/test_api_service.py::test_structure_import_file`

5. **`run_calculation(project_root, ...)`** → Delegate to `get_service(project_root).run.calculation(...)`
   - **File**: `src/qmatsuite/api/service.py:6552`
   - **Action**: Make static delegate to `svc.run.calculation()` (method already exists, may need signature adjustment)
   - **Test**: `pytest tests/unit/test_api_service.py::test_run_calculation`

6. **`run_step(project_root, ...)`** → Delegate to `get_service(project_root).run.step(...)`
   - **File**: `src/qmatsuite/api/service.py:6649`
   - **Action**: Make static delegate to `svc.run.step()` (method already exists, may need signature adjustment)
   - **Test**: `pytest tests/unit/test_api_service.py::test_run_step`

**Estimated Effort**: 6 static methods × 30 min = 3 hours  
**Risk**: LOW (mechanical changes, existing instance methods)

### Batch 2: Add Missing Instance Methods (High Priority)

**Goal**: Add instance method equivalents for static methods that don't have them.

**Changes**:

1. **Add `project.init_calculation(...)`** → Instance method for `init_calculation()`
   - **File**: `src/qmatsuite/api/service.py:5011` (Project subservice)
   - **Action**: Add `init_calculation(name, structure_selector, template)` method
   - **Test**: `pytest tests/unit/test_api_service.py::test_project_init_calculation`

2. **Add `structure.promote_relax_structure(...)`** → Instance method for `promote_relax_structure()`
   - **File**: `src/qmatsuite/api/service.py:1571` (Structure subservice)
   - **Action**: Add method that wraps static logic
   - **Test**: `pytest tests/unit/test_api_service.py::test_structure_promote_relax`

3. **Add `structure.save_relax_final_structure(...)`** → Instance method for `save_relax_final_structure()`
   - **File**: `src/qmatsuite/api/service.py:1571` (Structure subservice)
   - **Action**: Add method that wraps static logic
   - **Test**: `pytest tests/unit/test_api_service.py::test_structure_save_relax_final`

4. **Add `project.analyze_pseudo_effects(...)`** → Instance method for `analyze_project_pseudo_effects()`
   - **File**: `src/qmatsuite/api/service.py:5011` (Project subservice)
   - **Action**: Add method that wraps static logic
   - **Test**: `pytest tests/unit/test_api_service.py::test_project_analyze_pseudo_effects`

5. **Add `project.materialize_pseudo_file(...)`** → Instance method for `materialize_pseudo_file()`
   - **File**: `src/qmatsuite/api/service.py:5011` (Project subservice)
   - **Action**: Add method that wraps static logic
   - **Test**: `pytest tests/unit/test_api_service.py::test_project_materialize_pseudo_file`

6. **Add `project.get_pseudo_options(...)`** → Instance method for `get_pseudo_options_for_elements()`
   - **File**: `src/qmatsuite/api/service.py:5011` (Project subservice)
   - **Action**: Add method that wraps static logic
   - **Test**: `pytest tests/unit/test_api_service.py::test_project_get_pseudo_options`

7. **Add `run.run_single_step(...)`** → Instance method for `run_single_step()`
   - **File**: `src/qmatsuite/api/service.py:4322` (Run subservice)
   - **Action**: Add method (may be same as `run_step()`)
   - **Test**: `pytest tests/unit/test_api_service.py::test_run_single_step`

**Estimated Effort**: 7 methods × 1 hour = 7 hours  
**Risk**: MEDIUM (new methods, need to ensure compatibility)

### Batch 3: Migrate Daemon Handlers (Medium Priority)

**Goal**: Update daemon handlers to use instance methods instead of static methods.

**Changes**:

1. **`_handle_get_project_summary`** → Use `svc.project.get_summary()`
   - **File**: `src/qmatsuite/daemon/server.py:1998, 2089`
   - **Action**: Replace `QMSService.get_project_summary(project_root)` with `get_service(project_root).project.get_summary()`
   - **Test**: `pytest tests/integration/test_daemon.py::test_get_project_summary`

2. **`_handle_list_structures`** → Use `svc.structure.list()`
   - **File**: `src/qmatsuite/daemon/server.py:2010, 2124`
   - **Action**: Replace `QMSService.list_structures_data(project_root)` with `get_service(project_root).structure.list()`
   - **Test**: `pytest tests/integration/test_daemon.py::test_list_structures`

3. **`_handle_list_calculations`** → Use `svc.calculation.list()`
   - **File**: `src/qmatsuite/daemon/server.py:2023, 2776`
   - **Action**: Replace `QMSService.list_calculations_data(project_root)` with `get_service(project_root).calculation.list()`
   - **Test**: `pytest tests/integration/test_daemon.py::test_list_calculations`

4. **`_handle_import_structure`** → Use `svc.structure.import_file()`
   - **File**: `src/qmatsuite/daemon/server.py:2116`
   - **Action**: Replace `QMSService.import_structure(...)` with `get_service(project_root).structure.import_file(...)`
   - **Test**: `pytest tests/integration/test_daemon.py::test_import_structure`

5. **`_handle_init_calculation`** → Use `svc.project.init_calculation()` (after Batch 2)
   - **File**: `src/qmatsuite/daemon/server.py:2766`
   - **Action**: Replace `QMSService.init_calculation(...)` with `get_service(project_root).project.init_calculation(...)`
   - **Test**: `pytest tests/integration/test_daemon.py::test_init_calculation`

6. **`_handle_run_calculation`** → Use `svc.run.calculation()` (after Batch 1)
   - **File**: `src/qmatsuite/daemon/server.py:5320`
   - **Action**: Replace `func=QMSService.run_calculation` with `get_service(project_root).run.calculation(...)`
   - **Test**: `pytest tests/integration/test_daemon.py::test_run_calculation`

7. **`_handle_run_step`** → Use `svc.run.step()` (after Batch 1)
   - **File**: `src/qmatsuite/daemon/server.py:5391`
   - **Action**: Replace `func=QMSService.run_step` with `get_service(project_root).run.step(...)`
   - **Test**: `pytest tests/integration/test_daemon.py::test_run_step`

8. **Remaining 6 handlers** → Migrate after Batch 2 adds missing instance methods
   - Files: `daemon/server.py:3209, 3600, 4461, 4486, 4576, 5446`
   - Action: Replace static calls with instance method calls

**Estimated Effort**: 13 handlers × 20 min = 4.5 hours  
**Risk**: LOW (mechanical changes, tests exist)

### Batch 4: Migrate CLI Handlers (Medium Priority)

**Goal**: Update CLI to use instance methods instead of static methods.

**Changes**:

1. **`run_step` command** → Use `svc.run.step()` (after Batch 1)
   - **File**: `src/qmatsuite/cli/main.py:1753`
   - **Action**: Replace `QMSService.run_step(...)` with `get_service(project_root).run.step(...)`
   - **Test**: `pytest tests/integration/test_cli.py::test_run_step`

2. **`configure_species_map` command** → Use instance method (after adding to Calculation subservice)
   - **File**: `src/qmatsuite/cli/main.py:3656`
   - **Action**: Replace `QMSService.configure_species_map(...)` with `get_service(project_root).calculation.configure_species_map(...)`
   - **Test**: `pytest tests/integration/test_cli.py::test_configure_species_map`

3. **`run_calculation` command** → Use `svc.run.calculation()` (after Batch 1)
   - **File**: `src/qmatsuite/cli/main.py:4010`
   - **Action**: Replace `QMSService.run_calculation(...)` with `get_service(project_root).run.calculation(...)`
   - **Test**: `pytest tests/integration/test_cli.py::test_run_calculation`

**Estimated Effort**: 3 handlers × 20 min = 1 hour  
**Risk**: LOW (mechanical changes)

### Batch 5: Mark Static Methods as DEPRECATED (Low Priority)

**Goal**: Add deprecation warnings to static methods that have instance equivalents.

**Changes**:

1. Add `@deprecated` decorator or docstring warnings to all project-scoped static methods
2. Update docstrings to indicate they are "TEMP SHIM / DEPRECATED"
3. Keep static methods for backwards compatibility but discourage new usage

**Estimated Effort**: 13 methods × 5 min = 1 hour  
**Risk**: LOW (documentation only)

### Summary

**Total Estimated Effort**: ~16.5 hours  
**Total Batches**: 5  
**Dependencies**: Batch 2 must complete before Batch 3 (some handlers), Batch 1 must complete before Batch 3/4 (run methods)

**Each batch is runnable with pytest** and can be tested independently.

---

## Conclusion

### Compliance Status

| Goal | Status | Notes |
|------|--------|-------|
| 1. Import isolation | ✅ **PASS** | Zero forbidden imports in CLI/daemon |
| 2. API SSOT | ⚠️ **PARTIAL** | Instance subservices exist and are used, but 18 static calls bypass them |
| 3. Static method delegators | ❌ **FAIL** | 13 project-scoped static methods are NOT pure delegators |
| 4. Daemon parity | ⚠️ **PARTIAL** | Most handlers work, but 13 use static methods instead of instance methods |

### Critical Violations

1. **13 project-scoped static methods** contain logic and call kernel modules directly
2. **18 static method callsites** (3 CLI + 15 daemon) bypass the instance subservice architecture
3. **7 missing instance methods** prevent full routing through subservices

### Recommended Action

**Proceed with Batches 1-4** to achieve full compliance. Batch 5 is optional cleanup.

---

**End of Audit Report**

