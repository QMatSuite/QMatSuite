# API Surface Map

**Date**: 2026-01-21  
**Purpose**: Complete inventory of API entrypoints used by CLI and daemon

---

## Subservice Methods (Instance-Style API)

### `svc.project` Subservice (`api/service.py:5011`)

| Method | File:Line | Requires project_root | Has Capability Logic | CLI Callsites | Daemon Callsites |
|--------|-----------|----------------------|---------------------|---------------|------------------|
| `get_config()` | `api/service.py:5017` | ✅ Yes | ✅ Yes (loads config) | `cli/main.py:798, 1052, 1487, 2005, 2280, 2351, 2385, 2459, 2593, 2797, 2862, 3313, 3611, 3680, 3720, 3934, 4131, 4250, 4272, 4559, 5319` (21) | `daemon/server.py:159, 181` (2) |
| `update_config(patch)` | `api/service.py:5035` | ✅ Yes | ✅ Yes (saves config) | `cli/main.py:881, 943, 1521, 2291, 2362, 2428, 2733, 2828, 3378, 3793` (10) | None |
| `get_species_map()` | `api/service.py:5066` | ✅ Yes | ✅ Yes (reads config) | None | None |
| `get_potential_map()` | `api/service.py:5090` | ✅ Yes | ✅ Yes (reads config) | None | None |
| `build_resource_index()` | `api/service.py:5112` | ✅ Yes | ✅ Yes (builds index) | `cli/main.py:1694, 2166, 2284, 3438, 3501, 3937` (6) | `daemon/server.py:160, 182` (2) |
| `list_calculations()` | `api/service.py:5130` | ✅ Yes | ⚠️ Delegates to `svc.calculation.list()` | None | None |
| `collect_slugs(entries, ...)` | `api/service.py:5148` | ✅ Yes | ✅ Yes (calls kernel) | `cli/main.py:1489` (1) | None |
| `apply_structure_rename(...)` | `api/service.py:5167` | ✅ Yes | ✅ Yes (calls kernel) | `cli/main.py:2284` (1) | None |
| `apply_calculation_rename(...)` | `api/service.py:5198` | ✅ Yes | ✅ Yes (calls kernel) | `cli/main.py:2355, 3371` (2) | None |
| `import_pseudo_files(file_paths)` | `api/service.py:5229` | ✅ Yes | ✅ Yes (imports files) | None | `daemon/server.py:3407` (1) |

**Total CLI callsites**: 41  
**Total Daemon callsites**: 5

### `svc.structure` Subservice (`api/service.py:1571`)

| Method | File:Line | Requires project_root | Has Capability Logic | CLI Callsites | Daemon Callsites |
|--------|-----------|----------------------|---------------------|---------------|------------------|
| `get(selector)` | `api/service.py:1577` | ✅ Yes | ✅ Yes (resolves, loads) | `cli/main.py:235, 3437, 3724, 4148` (4) | None |
| `list()` | `api/service.py:1624` | ✅ Yes | ✅ Yes (lists, loads) | `cli/main.py:2019` (1) | None (TODO at `daemon/server.py:2008`) |
| `get_atoms(selector)` | `api/service.py:1673` | ✅ Yes | ✅ Yes (loads coords) | None | None |
| `require_ref(selector, ...)` | `api/service.py:1725` | ✅ Yes | ✅ Yes (resolves) | `cli/main.py:654, 892, 1205, 1324, 2109, 2274, 2587, 2718, 3476, 5391` (10) | `daemon/server.py:5633` (1) |
| `import_file(source, name, format)` | `api/service.py:1807` | ✅ Yes | ✅ Yes (imports, writes) | None | None (static `import_structure()` used instead) |
| `get_vis_data(selector, ...)` | `api/service.py:1911` | ✅ Yes | ✅ Yes (visualizes) | None | `daemon/server.py:4741` (1) |

**Total CLI callsites**: 15  
**Total Daemon callsites**: 2

### `svc.calculation` Subservice (`api/service.py:2119`)

| Method | File:Line | Requires project_root | Has Capability Logic | CLI Callsites | Daemon Callsites |
|--------|-----------|----------------------|---------------------|---------------|------------------|
| `get(selector)` | `api/service.py:2125` | ✅ Yes | ✅ Yes (resolves, loads) | `cli/main.py:2352, 2460, 2801, 3317, 3681, 4133, 4251, 5331` (8) | None |
| `list()` | `api/service.py:2179` | ✅ Yes | ✅ Yes (lists, loads) | `cli/main.py:2050` (1) | None (TODO at `daemon/server.py:2021`) |
| `get_step(calc_selector, step_selector)` | `api/service.py:2364` | ✅ Yes | ✅ Yes (resolves, loads) | None | `daemon/server.py:3095` (1) |
| `list_steps(calc_selector)` | `api/service.py:2429` | ✅ Yes | ✅ Yes (lists steps) | None | `daemon/server.py:4207` (1) |
| `get_effective_params(calc_selector)` | `api/service.py:2492` | ✅ Yes | ✅ Yes (computes params) | None | None |
| `get_detail(selector)` | `api/service.py:3124` | ✅ Yes | ✅ Yes (loads detail) | None | `daemon/server.py:4103, 4553` (2) |
| `set_structure(calc_selector, structure_selector)` | `api/service.py:3229` | ✅ Yes | ✅ Yes (sets structure) | None | `daemon/server.py:4323` (1) |
| `get_common_cards(calc_selector)` | `api/service.py:3318` | ✅ Yes | ✅ Yes (reads cards) | None | `daemon/server.py:3294` (1) |
| `remove_step(calc_selector, step_selector)` | `api/service.py:3559` | ✅ Yes | ✅ Yes (removes step) | None | `daemon/server.py:3649` (1) |
| `set_common_card(calc_selector, card_name, card_data)` | `api/service.py:3684` | ✅ Yes | ✅ Yes (writes card) | None | `daemon/server.py:3294` (1) |
| `get_step_pseudo_mapping(calc_selector, step_selector)` | `api/service.py:3756` | ✅ Yes | ✅ Yes (reads mapping) | None | `daemon/server.py:3333` (1) |
| `set_step_pseudo_mapping(calc_selector, step_selector, mapping)` | `api/service.py:3887` | ✅ Yes | ✅ Yes (writes mapping) | None | `daemon/server.py:3376` (1) |
| `import_step_from_qe_input(calc_selector, input_file, ...)` | `api/service.py:4082` | ✅ Yes | ✅ Yes (imports step) | None | `daemon/server.py:4207` (1) |
| `get_pseudo_mapping(calc_selector)` | `api/service.py:4166` | ✅ Yes | ✅ Yes (reads mapping) | None | `daemon/server.py:4385` (1) |
| `require_ref(selector, ...)` | `api/service.py:2241` | ✅ Yes | ✅ Yes (resolves) | `cli/main.py:1069, 1079, 1090, 1160, 1682, 1707, 1732, 2057, 2464, 2587, 2697, 2805, 2820, 2869, 2902, 3352, 3385, 3394, 3685, 3962, 3986, 4255, 4282, 4568, 5339` (25) | `daemon/server.py:5611` (1) |
| `require_step_ref(calc_selector, step_selector, ...)` | `api/service.py:2263` | ✅ Yes | ✅ Yes (resolves) | `cli/main.py:1686, 1709, 1732, 2193, 2893, 3462` (6) | `daemon/server.py:5656` (1) |
| `resolve_enclosing_path(path)` | `api/service.py:2291` | ✅ Yes | ✅ Yes (finds enclosing) | `cli/main.py:1079, 2805, 2869, 3320, 3612, 3969, 4273, 4560, 5331` (9) | None |
| `rename(...)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:2815` (1) |
| `can_delete(calculation_ulid)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:2886, 2992` (2) |
| `delete(calc_id)` | Not found (may be missing) | ✅ Yes | ✅ Yes | `cli/main.py:2695, 2820` (2) | `daemon/server.py:3004` (1) |
| `update_step_params(...)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:3181` (1) |
| `reset_step_params(...)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:3535` (1) |
| `reorder_steps(...)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:4127` (1) |
| `add_step(...)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:4157` (1) |
| `update_species_map(...)` | `api/service.py:4269` | ✅ Yes | ✅ Yes (updates map) | None | `daemon/server.py:4424` (1) |

**Total CLI callsites**: 51  
**Total Daemon callsites**: 20

### `svc.run` Subservice (`api/service.py:4322`)

| Method | File:Line | Requires project_root | Has Capability Logic | CLI Callsites | Daemon Callsites |
|--------|-----------|----------------------|---------------------|---------------|------------------|
| `run_calculation(calc_selector, steps)` | `api/service.py:4328` | ✅ Yes | ✅ Yes (runs calc) | None | None (static `run_calculation()` used instead) |
| `run_step(calc_selector, step_selector)` | `api/service.py:4422` | ✅ Yes | ✅ Yes (runs step) | None | None (static `run_step()` used instead) |
| `get_status(run_id)` | `api/service.py:4551` | ✅ Yes | ⚠️ Stub (not implemented) | None | None |
| `list()` | `api/service.py:4743` | ✅ Yes | ⚠️ Stub (not implemented) | None | None |
| `preflight(...)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:4611` (1) |

**Total CLI callsites**: 0  
**Total Daemon callsites**: 1

### `svc.analysis` Subservice (`api/service.py:47`)

| Method | File:Line | Requires project_root | Has Capability Logic | CLI Callsites | Daemon Callsites |
|--------|-----------|----------------------|---------------------|---------------|------------------|
| `get_summary(calc_selector, step_selector)` | `api/service.py:53` | ✅ Yes | ✅ Yes (reads artifacts) | None | None |
| `list_properties(calc_selector, step_selector)` | `api/service.py:104` | ✅ Yes | ✅ Yes (checks artifacts) | None | None |
| `get_property_ref(calc_selector, step_selector, property_name)` | `api/service.py:152` | ✅ Yes | ✅ Yes (reads artifact) | None | None |
| `analyze_band(...)` | `api/service.py:361` | ✅ Yes | ✅ Yes (parses, plots) | `cli/main.py:4585` (1) | None |
| `analyze_dos(...)` | `api/service.py:535` | ✅ Yes | ✅ Yes (parses, plots) | `cli/main.py:4672` (1) | None |
| `analyze_scf(...)` | `api/service.py:1152` | ✅ Yes | ✅ Yes (parses SCF) | `cli/main.py:4738` (1) | None |
| `get_relax_final_structure_preview(...)` | `api/service.py:1470` | ✅ Yes | ✅ Yes (reads structure) | None | `daemon/server.py:3568` (1) |
| `get_scf_convergence_data(...)` | `api/service.py:763` | ✅ Yes | ✅ Yes (parses SCF) | None | `daemon/server.py:4766` (1) |
| `get_dos_data(...)` | `api/service.py:1285` | ✅ Yes | ✅ Yes (parses DOS) | None | `daemon/server.py:4790` (1) |
| `get_band_structure_data(...)` | `api/service.py:663` | ✅ Yes | ✅ Yes (parses bands) | None | `daemon/server.py:4815` (1) |
| `get_reference_analysis(...)` | `api/service.py:1372` | ✅ Yes | ✅ Yes (reads reference) | None | `daemon/server.py:4857` (1) |
| `list_step_artifacts(calc_selector, step_selector)` | `api/service.py:853` | ✅ Yes | ✅ Yes (scans artifacts) | None | `daemon/server.py:4960` (1) |
| `ensure_analysis(...)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:4706` (1) |
| `read_step_artifact_text(...)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:4988` (1) |

**Total CLI callsites**: 3  
**Total Daemon callsites**: 9

### `svc.engine` Subservice (`api/service.py:5338`)

| Method | File:Line | Requires project_root | Has Capability Logic | CLI Callsites | Daemon Callsites |
|--------|-----------|----------------------|---------------------|---------------|------------------|
| `list()` | `api/service.py:5344` | ❌ No (global) | ✅ Yes (lists engines) | None | None |
| `get_info(engine_name)` | `api/service.py:5370` | ❌ No (global) | ✅ Yes (gets info) | None | None |
| `list_step_types(engine_name)` | `api/service.py:5419` | ❌ No (global) | ✅ Yes (lists types) | None | None |

**Total CLI callsites**: 0  
**Total Daemon callsites**: 0

### `svc.history` Subservice (`api/service.py:5591`)

| Method | File:Line | Requires project_root | Has Capability Logic | CLI Callsites | Daemon Callsites |
|--------|-----------|----------------------|---------------------|---------------|------------------|
| `get_timeline(limit, calc_id)` | `api/service.py:5597` | ✅ Yes | ✅ Yes (reads history) | None | `daemon/server.py:6114` (1) |
| `get_run_revision(run_id)` | `api/service.py:5699` | ✅ Yes | ✅ Yes (loads revision) | None | `daemon/server.py:6132` (1) |
| `list_runs(calc_id, limit)` | `api/service.py:5729` | ✅ Yes | ✅ Yes (lists runs) | None | `daemon/server.py:6152` (1) |
| `get_pin_data(run_id, step_id, analysis_kind)` | `api/service.py:5834` | ✅ Yes | ✅ Yes (reads pin) | None | `daemon/server.py:6240` (1) |
| `get_latest_run_for_step(step_id)` | `api/service.py:5861` | ✅ Yes | ✅ Yes (finds run) | None | `daemon/server.py:6262` (1) |
| `pin_analysis(...)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:6189` (1) |
| `can_pin(run_id, step_id)` | Not found (may be missing) | ✅ Yes | ✅ Yes | None | `daemon/server.py:6216` (1) |
| `delete(confirm)` | `api/service.py:5904` | ✅ Yes | ✅ Yes (deletes history) | None | `daemon/server.py:6287` (1) |

**Total CLI callsites**: 0  
**Total Daemon callsites**: 8

---

## api.utils Functions (Transparent Re-exports)

**File**: `src/quantumvitas/api/utils.py`

### Pure Utilities (No project_root, Transparent Re-exports)

| Function | File:Line | Re-exports From | CLI Callsites | Daemon Callsites |
|----------|-----------|----------------|---------------|------------------|
| `slugify(value, fallback)` | `api/utils.py:14` | `core.resources.slugify` | None | None |
| `meta_from_name(kind, name, path)` | `api/utils.py:29` | `core.resources.meta_from_name` | None | None |
| `generate_resource_id()` | `api/utils.py:112` | `core.resources.generate_resource_id` | None | None |
| `generate_unique_name_and_slug(...)` | `api/utils.py:123` | `core.resources.generate_unique_name_and_slug` | None | `daemon/server.py:66` (1) |
| `read_structure(filepath, format)` | `api/utils.py:64` | `io.structure_io.read_structure` | None | None |
| `write_structure(structure, filepath, ...)` | `api/utils.py:79` | `io.structure_io.write_structure` | None | None |
| `get_default_step_params(step_type)` | `api/utils.py:7046` (via static) | `calculation.step_defaults.get_default_step_params` | `cli/main.py:1276` (1) | None |
| `generate_kpath(structure, ...)` | `api/utils.py:7063` (via static) | `analysis.kpath.generate_kpath` | `cli/main.py:1257` (1) | None |
| `get_settings()` | `api/utils.py:6049` (via static) | `core.settings.load_settings` | None | `daemon/server.py:237, 1424, 3046, 4347` (4) |
| `get_workflow_service()` | `api/utils.py:6093` (via static) | `workflow.templates.get_workflow_service` | None | `daemon/server.py:6300, 6334, 6417, 6488` (4) |

### Project-Scoped Utilities (Require project_root, Have Logic)

| Function | File:Line | Requires project_root | Has Capability Logic | CLI Callsites | Daemon Callsites |
|----------|-----------|----------------------|---------------------|---------------|------------------|
| `find_path_context_ref(cwd, max_depth)` | `api/utils.py:387` | ✅ Yes | ✅ Yes (scans paths) | `cli/main.py:42` (1) | None |
| `find_project_root(start)` | `api/utils.py:443` | ❌ No (finds root) | ✅ Yes (scans paths) | `cli/main.py:44` (1) | None |
| `can_delete_structure(project_root, selector)` | `api/utils.py:521` | ✅ Yes | ✅ Yes (checks usage) | None | None |
| `delete_structure(project_root, selector, force)` | `api/utils.py:556` | ✅ Yes | ✅ Yes (deletes) | None | None |
| `rename_structure(project_root, selector, new_name)` | `api/utils.py:578` | ✅ Yes | ✅ Yes (renames) | None | None |
| `calculations_using_structure(project_root, config, struct_entry)` | `api/utils.py:503` | ✅ Yes | ✅ Yes (finds usage) | `cli/main.py:49` (1) | None |

**Note**: Some functions in `api.utils` have capability logic but are kept there for backwards compatibility. They should ideally be moved to subservices.

---

## QVService Static Methods (TEMP SHIMs)

### Project-Scoped Static Methods (MUST DELEGATE)

| Static Method | File:Line | Is Pure Delegator? | CLI Callsites | Daemon Callsites | Target Home |
|---------------|-----------|-------------------|---------------|------------------|-------------|
| `get_project_summary(project_root)` | `api/service.py:6104` | ❌ **NO** (has logic) | None | `daemon/server.py:1998, 2089` (2) | `svc.project.get_summary()` |
| `list_structures_data(project_root)` | `api/service.py:6167` | ❌ **NO** (has logic) | None | `daemon/server.py:2010, 2124` (2) | `svc.structure.list()` |
| `list_calculations_data(project_root)` | `api/service.py:6227` | ❌ **NO** (has logic) | None | `daemon/server.py:2023, 2776` (2) | `svc.calculation.list()` |
| `init_calculation(project_root, ...)` | `api/service.py:6310` | ❌ **NO** (has logic) | None | `daemon/server.py:2766` (1) | `svc.project.init_calculation()` (missing) |
| `run_calculation(project_root, ...)` | `api/service.py:6552` | ❌ **NO** (has logic) | `cli/main.py:4010` (1) | `daemon/server.py:5320` (1) | `svc.run.calculation()` (exists) |
| `run_step(project_root, ...)` | `api/service.py:6649` | ❌ **NO** (has logic) | `cli/main.py:1753` (1) | `daemon/server.py:5391` (1) | `svc.run.step()` (exists) |
| `import_structure(project_root, ...)` | `api/service.py:6779` | ❌ **NO** (has logic) | None | `daemon/server.py:2116` (1) | `svc.structure.import_file()` (exists) |
| `promote_relax_structure(project_root, ...)` | `api/service.py:6898` | ❌ **NO** (has logic) | None | `daemon/server.py:3209` (1) | `svc.structure.promote_relax()` (missing) |
| `save_relax_final_structure(project_root, ...)` | `api/service.py:7206` | ❌ **NO** (has logic) | None | `daemon/server.py:3600` (1) | `svc.structure.save_relax_final()` (missing) |
| `configure_species_map(project_root, ...)` | `api/service.py:6977` | ⚠️ **PARTIAL** (delegates to kernel) | `cli/main.py:3656` (1) | None | `svc.calculation.configure_species_map()` (missing) |
| `analyze_project_pseudo_effects(project_root, ...)` | `api/service.py:7693` | ❌ **NO** (has logic) | None | `daemon/server.py:4461` (1) | `svc.project.analyze_pseudo_effects()` (missing) |
| `materialize_pseudo_file(project_root, ...)` | `api/service.py:7748` | ❌ **NO** (has logic) | None | `daemon/server.py:4486` (1) | `svc.project.materialize_pseudo_file()` (missing) |
| `get_pseudo_options_for_elements(project_root, ...)` | `api/service.py:7775` | ❌ **NO** (has logic) | None | `daemon/server.py:4576` (1) | `svc.project.get_pseudo_options()` (missing) |

**Total violations**: 13 project-scoped static methods that are NOT pure delegators

### Global Static Methods (ACCEPTABLE)

| Static Method | File:Line | Is Pure Delegator? | CLI Callsites | Daemon Callsites | Notes |
|---------------|-----------|-------------------|---------------|------------------|-------|
| `init_project(target_dir, ...)` | `api/service.py:5973` | ⚠️ Has logic | None | `daemon/server.py:2077` (1) | Acceptable (no project_root yet) |
| `get_settings()` | `api/service.py:6049` | ⚠️ Has logic | None | `daemon/server.py:237, 1424, 3046, 4347` (4) | Acceptable (global settings) |
| `get_workflow_service()` | `api/service.py:6093` | ✅ **YES** | None | `daemon/server.py:6300, 6334, 6417, 6488` (4) | Pure delegator |
| `get_default_step_params(step_type)` | `api/service.py:7046` | ✅ **YES** | `cli/main.py:1276` (1) | None | Pure delegator |
| `generate_kpath(structure, ...)` | `api/service.py:7063` | ✅ **YES** | `cli/main.py:1257` (1) | None | Pure delegator |
| `create_demo_project(...)` | `api/service.py:7093` | ⚠️ Has logic | None | `daemon/server.py:4634` (1) | Acceptable (no project_root yet) |
| `list_demo_projects()` | `api/service.py:7167` | ⚠️ Has logic | None | `daemon/server.py:4657` (1) | Acceptable (no project_root needed) |
| All pseudo management statics | `api/service.py:7381+` | ⚠️ Have logic | None | Many (15+) | Acceptable (global operations) |

**Total acceptable**: ~15 global static methods

---

## Summary

### Instance Subservice Usage
- **CLI**: 110+ callsites using instance methods
- **Daemon**: 45+ callsites using instance methods
- **Total**: 155+ callsites correctly using instance-style API

### Static Method Violations
- **CLI**: 3 project-scoped static calls (violations)
- **Daemon**: 15 project-scoped static calls (violations)
- **Total**: 18 violations that bypass instance subservices

### Missing Instance Methods
1. `svc.project.get_summary()` - needed for `get_project_summary()` static
2. `svc.project.init_calculation()` - needed for `init_calculation()` static
3. `svc.structure.promote_relax_structure()` - needed for `promote_relax_structure()` static
4. `svc.structure.save_relax_final_structure()` - needed for `save_relax_final_structure()` static
5. `svc.calculation.configure_species_map()` - needed for `configure_species_map()` static
6. `svc.project.analyze_pseudo_effects()` - needed for `analyze_project_pseudo_effects()` static
7. `svc.project.materialize_pseudo_file()` - needed for `materialize_pseudo_file()` static
8. `svc.project.get_pseudo_options()` - needed for `get_pseudo_options_for_elements()` static

---

**End of API Surface Map**

