# API & Daemon/RPC Layer Architecture Review

**Date**: 2026-02-14
**Purpose**: Final closeout review before API surface freeze and comprehensive test addition.
**Scope**: API layer (`qmatsuite.api`), Daemon/RPC layer (`qmatsuite.daemon`), CLI layer (`qmatsuite.cli`).
**Status**: READ-ONLY AUDIT — no code modifications.

---

## 1. Executive Summary

### Key Metrics

| Metric | Count |
|--------|-------|
| **Total API methods (QMSService, all depths)** | **117** |
| API methods at depth 0 (directly on QMSService) | 23 |
| API methods at depth 1 (on sub-objects) | 94 |
| API utility functions (api.utils) | ~65 |
| DTO types | 18 |
| Error classes | 9 |
| **Grand total public API surface** | **~200** |
| **Total RPC endpoints (daemon dispatch table)** | **120** (118 unique after 1 duplicate key) |
| Total daemon internal functions | ~35 |
| Compat layer functions (daemon/compat.py) | ~36 |
| CLI commands/subcommands | 35 |
| **Constitutional violations (daemon→kernel)** | **0 direct imports** (gate-enforced) |
| **Business logic leaks (daemon doing API work)** | **8 significant** |
| **Identified consolidation opportunities** | **22** |
| **Estimated method count after consolidations** | **~155** (from ~200) |

### Architecture Health Summary

**Good:**
- Zero kernel imports from daemon or CLI (gate-tested)
- Clean DTO boundary — kernel objects never leaked
- Exception mapping centralized in `_mapping/exc_mapping.py`
- CLI properly uses only `qmatsuite.api.*` imports
- 65 gate tests enforce architectural invariants

**Concerning:**
- Daemon contains ~770 lines of business logic that should be in API (online structure handling: ~370 lines, QE metadata browser: ~400 lines)
- `api.utils` at 2,262 lines is a grab-bag — many functions are kernel re-exports with thin wrappers
- CLI reads YAML files directly in ~20 places instead of API calls
- Some API sub-objects have overlapping methods (e.g., `svc.project.list_calculations()` vs `svc.calculation.list()`)
- Compat layer (`daemon/compat.py`) is 1,011 lines of v0 GUI format translation

---

## 2. Complete API Method Enumeration (Phase 1, Step 1.1)

### 2.1 QMSService Direct Methods (Depth 0) — 23 methods

| # | Method | Signature | Purpose | Called by |
|---|--------|-----------|---------|----------|
| 1 | `__init__` | `(project_root: Path)` | Initialize service with project root | CLI, daemon |
| 2 | `init_project` | `(target_dir, name, ...)` (static) | Initialize a new project | CLI, daemon |
| 3 | `get_settings` | `()` (static) | Get user settings | daemon |
| 4 | `get_workflow_service` | `()` (static) | Get WorkflowService instance | daemon |
| 5 | `run_single_step` | `(step_type_spec, params, ...)` (static) | Run a single step standalone | daemon |
| 6 | `get_default_step_params` | `(step_type_spec)` (static) | Get default params for step type | CLI |
| 7 | `resolve_step_type_spec` | `(step_type_gen, engine_family)` (static) | Resolve GEN→SPEC step type | CLI |
| 8 | `generate_kpath` | `(structure, ...)` (static) | Generate k-path for band structure | CLI |
| 9 | `create_demo_project` | `(demo_name, target_dir, ...)` (static) | Create demo project | CLI, daemon |
| 10 | `list_demo_projects` | `()` (static) | List available demos | daemon |
| 11 | `init_pseudo_dirs` | `()` (static) | Initialize pseudo directories | daemon |
| 12 | `list_pseudo_libraries` | `()` (static) | List pseudo libraries | daemon |
| 13 | `get_library_status` | `(library_id)` (static) | Get library status | daemon |
| 14 | `install_pseudo_library` | `(library_id, ...)` (static) | Install pseudo library | daemon |
| 15 | `remove_pseudo_library` | `(library_id, ...)` (static) | Remove pseudo library | daemon |
| 16 | `repair_pseudo_library` | `(library_id, ...)` (static) | Repair pseudo library | daemon |
| 17 | `compute_store_size` | `()` (static) | Compute pseudo store size | daemon |
| 18 | `is_pseudo_archive_installed` | `(asset_name, sha256)` (static) | Check if archive installed | daemon |
| 19 | `install_pseudo_archive` | `(asset_name, ...)` (static) | Install pseudo archive | daemon |
| 20 | `install_sssp_from_seed` | `(seed_dir, library)` (static) | Install SSSP from seed | daemon |
| 21 | `install_all_sssp_from_seed` | `(seed_dir)` (static) | Install all SSSP from seed | daemon |
| 22 | `download_sssp_library` | `(store_dir, library, ...)` (static) | Download SSSP library | daemon |
| 23 | `download_all_sssp` | `(store_dir, ...)` (static) | Download all SSSP | daemon |
| 24 | `import_seed_archives` | `(seed_dir, archive_paths)` (static) | Import seed archives | daemon |

> Note: Most depth-0 static methods relate to pseudo/library management and project-less operations.

### 2.2 svc.analysis (Depth 1) — 12 methods

| # | Method | Signature | Purpose | Called by |
|---|--------|-----------|---------|----------|
| 25 | `list_step_artifacts` | `(calc_sel, step_sel)` | List output files for step | daemon |
| 26 | `read_step_artifact_text` | `(calc_sel, step_sel, artifact_path, ...)` | Read text artifact content | daemon |
| 27 | `analyze_scf` | `(scf_file, plot, ...)` | Analyze SCF output | CLI |
| 28 | `list_raw_files` | `(calc_sel, step_sel)` | List raw text artifacts (Surface A) | daemon |
| 29 | `read_raw_file` | `(calc_sel, step_sel, filename, ...)` | Read one raw artifact (Surface A) | daemon |
| 30 | `get_step_digest` | `(run_ulid, step_ulid)` | Return post-run digest (Surface B) | daemon |
| 31 | `get_analysis` | `(run_ulid, object_type, transforms)` | Derive analysis from evidence (Surface C) | daemon |
| 32 | `get_analysis_snapshot` | `(run_ulid, object_type)` | Replay from SQLite+CAS | daemon |
| 33 | `get_analysis_instances_for_step` | `(calc_sel, step_ulid)` | Step-scoped analysis enumeration | daemon |
| 34 | `get_field3d_grid` | `(run_ulid)` | Materialize Field3D data to .scratch/ | daemon |
| 35 | `get_reference_analysis` | `(calc_sel, analysis_type)` | Reference analysis for demos | daemon |
| 36 | `get_relax_final_structure_preview` | `(calc_sel, step_sel, ...)` | Preview final relax structure | daemon |

### 2.3 svc.structure (Depth 1) — 12 methods

| # | Method | Signature | Purpose | Called by |
|---|--------|-----------|---------|----------|
| 37 | `get` | `(selector)` | Get structure by selector | CLI, daemon |
| 38 | `list` | `(project_selector)` | List structures in project | CLI, daemon |
| 39 | `get_atoms` | `(selector)` | Get full atomic coordinates | Jupyter |
| 40 | `require_ref` | `(selector, config)` | Resolve to ResolvedResource | CLI, internal |
| 41 | `visualize` | `(selector, format)` | Get visualization data | internal only |
| 42 | `import_file` | `(source, name, format, ...)` | Import structure file | daemon |
| 43 | `get_vis_data` | `(selector, supercell, ...)` | Pure vis data for 3D rendering | daemon |
| 44 | `update_meta` | `(selector, new_name, new_slug)` | Rename structure | daemon |
| 45 | `can_delete` | `(selector)` | Check if deletable | daemon |
| 46 | `delete` | `(selector, force)` | Delete structure | CLI, daemon |
| 47 | `promote_relax_structure` | `(calc_sel, step_sel, name, ...)` | Promote relax output to resource | daemon |
| 48 | `save_relax_final_structure` | `(calc_sel, step_sel, parent_ulid, ...)` | Save relax structure (idempotent) | daemon |

### 2.4 svc.online_search (Depth 1) — 4 methods (all static)

| # | Method | Signature | Purpose | Called by |
|---|--------|-----------|---------|----------|
| 49 | `search_structures` | `(query, mode, sources, ...)` | Search online (OPTIMADE+PubChem) | daemon |
| 50 | `fetch_structure` | `(ref)` | Fetch full structure | daemon |
| 51 | `list_providers` | `(refresh_registry)` | List online providers | daemon |
| 52 | `update_online_sources` | `(patch)` | Update source settings | daemon |

### 2.5 svc.calculation (Depth 1) — 35 methods

| # | Method | Signature | Purpose | Called by |
|---|--------|-----------|---------|----------|
| 53 | `get` | `(selector)` | Get calculation by selector | CLI, daemon |
| 54 | `list` | `(project_selector, status)` | List calculations | CLI, daemon |
| 55 | `require_ref` | `(selector, config)` | Resolve to ResolvedResource | CLI, internal |
| 56 | `require_step_ref` | `(calc_sel, step_sel, config)` | Resolve step | CLI, internal |
| 57 | `resolve_enclosing_path` | `(path)` | Find calculation enclosing path | CLI |
| 58 | `require_enclosing` | `(path)` | Require enclosing calculation | internal |
| 59 | `get_step` | `(calc_sel, step_sel)` | Get step by selectors | CLI |
| 60 | `get_step_detail` | `(calc_sel, step_sel)` | Detailed step info (params, cards) | daemon |
| 61 | `list_steps` | `(calc_sel)` | List steps in calculation | CLI, daemon |
| 62 | `create` | `(engine, name, structure_sel, ...)` | Create new calculation | internal |
| 63 | `update_meta` | `(selector, **meta_kwargs)` | Update calculation metadata | CLI |
| 64 | `update_step_params` | `(calc_sel, step_sel, params)` | Update step parameters | CLI, daemon |
| 65 | `duplicate` | `(selector, new_name, new_slug)` | Duplicate calculation | internal |
| 66 | `can_delete` | `(selector)` | Check if deletable | daemon |
| 67 | `delete` | `(selector, force)` | Delete calculation | CLI, daemon |
| 68 | `get_detail` | `(selector)` | Detailed info for GUI | daemon |
| 69 | `set_structure` | `(calc_sel, structure_sel, update_steps)` | Change calculation structure | daemon |
| 70 | `get_common_cards` | `(calc_sel, step_sel)` | Get K_POINTS etc. view models | daemon |
| 71 | `set_engine_family` | `(calc_sel, engine_family)` | Set engine on calculation | daemon |
| 72 | `apply_presets` | `(calc_sel, presets, validate_physics)` | Broadcast presets to all steps | daemon |
| 73 | `add_step` | `(calc_sel, step_type_gen, ...)` | Add step to calculation | daemon |
| 74 | `add_step_from_spec` | `(calc_sel, step_spec, index)` | Add step from pre-built spec | CLI |
| 75 | `remove_step` | `(calc_sel, step_sel)` | Remove step | CLI, daemon |
| 76 | `rename_step` | `(calc_sel, step_sel, new_name, ...)` | Rename step | CLI, daemon |
| 77 | `rename` | `(selector, new_name, ...)` | Rename calculation | CLI, daemon |
| 78 | `set_common_card` | `(calc_sel, step_sel, card_name, view_model, ...)` | Set K_POINTS etc. | daemon |
| 79 | `get_step_pseudo_mapping` | `(calc_sel, step_sel, ...)` | Get step pseudo mapping | daemon |
| 80 | `set_step_pseudo_mapping` | `(calc_sel, step_sel, mapping, ...)` | Set step pseudo mapping | daemon |
| 81 | `reset_step_params` | `(calc_sel, step_sel, ...)` | Reset step params to defaults | daemon |
| 82 | `reorder_steps` | `(calc_sel, new_order, ...)` | Reorder steps | CLI, daemon |
| 83 | `update_steps_structure` | `(calc_sel, structure_sel, ...)` | Update structure in all steps | CLI |
| 84 | `import_step_from_qe_input` | `(calc_sel, input_file, ...)` | Import QE input as step | internal |
| 85 | `get_pseudo_mapping` | `(calc_sel, ...)` | Calc-level pseudo mapping | daemon |
| 86 | `update_species_map` | `(calc_sel, species_map, ...)` | Update species map | daemon |
| 87 | `configure_species_map` | `(calculation, from_qe_input, set_entries, merge)` | Configure species map | CLI |

### 2.6 svc.run (Depth 1) — 5 methods

| # | Method | Signature | Purpose | Called by |
|---|--------|-----------|---------|----------|
| 88 | `run_calculation` | `(calc_sel, steps, run_mode, run_ulid)` | Run calculation | CLI, daemon |
| 89 | `run_step` | `(calc_sel, step_sel, run_ulid)` | Run single step | CLI, daemon |
| 90 | `cancel` | `(run_ulid)` | Cancel running job | internal |
| 91 | `list_runs` | `(calc_sel, status)` | List runs | internal |
| 92 | `preflight` | `(calc_sel, step_sel)` | Pre-flight checks | daemon |

### 2.7 svc.project (Depth 1) — 13 methods

| # | Method | Signature | Purpose | Called by |
|---|--------|-----------|---------|----------|
| 93 | `get_config` | `()` | Get project config | CLI, daemon |
| 94 | `update_config` | `(patch)` | Update project config | CLI |
| 95 | `build_resource_index` | `()` | Build resource index | CLI, daemon |
| 96 | `list_calculations` | `()` | List calculations in project | internal |
| 97 | `collect_slugs` | `(entries, exclude)` | Collect all slugs | CLI |
| 98 | `apply_structure_rename` | `(entry, new_name, ...)` | Apply structure rename | CLI |
| 99 | `apply_calculation_rename` | `(entry, new_name, ...)` | Apply calculation rename | CLI |
| 100 | `import_pseudo_files` | `(file_paths)` | Import pseudo files | daemon |
| 101 | `get_summary` | `()` | Project summary | daemon |
| 102 | `init_calculation` | `(name, structure_sel, template, ...)` | Create calculation | CLI, daemon |
| 103 | `analyze_pseudo_effects` | `(selections)` | Analyze pseudo effects (read-only) | daemon |
| 104 | `materialize_pseudo_file` | `(element, sha256, ...)` | Materialize pseudo from selection | daemon |
| 105 | `get_pseudo_options` | `(elements, config)` | Get deduped pseudo options | daemon |

### 2.8 svc.engine (Depth 1) — 4 methods

| # | Method | Signature | Purpose | Called by |
|---|--------|-----------|---------|----------|
| 106 | `list` | `()` | List all engines | internal |
| 107 | `get_info` | `(engine_name)` | Engine info | internal |
| 108 | `list_step_types` | `(engine_name)` | List step types | internal |
| 109 | `validate_installation` | `(engine_name)` | Validate engine install | internal |

### 2.9 svc.history (Depth 1) — 9 methods

| # | Method | Signature | Purpose | Called by |
|---|--------|-----------|---------|----------|
| 110 | `get_timeline` | `(limit, calc_ulid)` | Get project timeline | CLI, daemon |
| 111 | `get_run_revision` | `(run_ulid)` | Get run revision details | CLI, daemon |
| 112 | `get_storage_summary` | `()` | Storage summary | CLI, daemon |
| 113 | `list_runs` | `(calc_ulid, limit)` | List all runs | daemon |
| 114 | `pin_analysis` | `(run_ulid, step_ulid, analysis_kind, ...)` | Pin analysis to history | daemon |
| 115 | `can_pin` | `(run_ulid, step_ulid)` | Check if pinning allowed | daemon |
| 116 | `get_pin_data` | `(run_ulid, step_ulid, analysis_kind)` | Get pinned data | daemon |
| 117 | `get_latest_run_for_step` | `(step_ulid)` | Latest run for step | daemon |
| 118 | `delete` | `(confirm)` | Delete .provenance/ | CLI, daemon |

### 2.10 api.utils Standalone Functions — ~65 functions

These are not on QMSService but are importable from `qmatsuite.api.utils`:

**Resource utilities (20):** `slugify`, `meta_from_name`, `ensure_relative_path`, `read_structure`, `write_structure`, `generate_unique_name_and_slug`, `list_calculation_templates`, `copy_calculation_template`, `copy_structure_template`, `extract_selector_from_entry`, `entry_display_name`, `move_to_trash`, `entry_matches`, `detect_runtime_control_keys`, `needs_alat_preservation`, `extract_alat_bohr`, `is_ulid_like`, `validate_ulid`, `calculations_using_structure`, `load_calculation`, `save_calculation`

**Pseudo utilities (7):** `get_pseudo_status_bundle`, `set_pseudo_config`, `search_legacy_pseudos`, `create_precision_advisor`, `download_pseudo_by_filename`, `download_pseudo_from_url`, `resolve_pseudo_provenance`

**Visualization (4):** `build_structure_vis_payload`, `visualize_structure`, `canonicalize_structure`, `reduce_formula`

**Engine/registry (5):** `list_engine_families`, `get_step_palette`, `validate_engine_family`, `get_engine_ui_parameters`, `get_engine_parameter_metadata`

**Analysis (7):** `parse_scf_output`, `parse_dos_data`, `parse_bands_gnu`, `plot_scf_convergence`, `plot_dos`, `plot_bands`, `save_figure`, `parse_volume_artifact`

**Presets (4):** `apply_presets_to_step`, `get_preset_catalog`, `resolve_precision_context`, `get_calculation_preset_bundle`

**QE-specific (5):** `write_qe_input_file`, `build_step_spec_from_qe_input`, `get_qe_engine_status`, `set_qe_engine`, `get_qe_home`

**QE metadata re-exports (9):** `get_ui_parameters`, `list_supported_modules`, `get_module_param_sections`, `get_module_card_sections`, `get_module_doc_url`, `get_metadata_file_info`, `get_qe_metadata_debug_info`, `safe_load_metadata`, `reload_metadata`

**Project utilities (10):** `run_input_step`, `apply_card_overrides_to_qe_input`, `apply_species_overrides_to_qe_input`, `find_calculation_raw_dir`, `find_calculation_results_dir`, `find_band_analysis_files`, `materialize_project_from_snapshot`, `export_project_to_snapshot`, `get_project_snapshot_class`, `find_path_context_from_pwd`, `compute_io_dir_from_calculation_model`, `get_journal`, `create_blob_store`, `score_candidate`, `extract_provenance`, `set_settings`, `create_default_registry`

---

## 3. Capability Grouping Analysis (Phase 1, Step 1.2)

### Group 1: Project Lifecycle (7 methods)

**Methods:** #2 `init_project`, #93 `get_config`, #94 `update_config`, #95 `build_resource_index`, #101 `get_summary`, + utils `find_path_context_from_pwd`, `export_project_to_snapshot`

**Assessment:**
- 1 overlapping method: `svc.project.list_calculations()` (#96) duplicates `svc.calculation.list()` (#54). **Merge candidate.**
- Missing: No `delete_project` API method — CLI does `shutil.rmtree` directly. **Gap.**
- `build_resource_index()` (#95) is internal bookkeeping exposed as API — should it be internal-only?

### Group 2: Calculation Lifecycle (14 methods)

**Methods:** #53 `get`, #54 `list`, #55 `require_ref`, #58 `require_enclosing`, #62 `create`, #63 `update_meta`, #65 `duplicate`, #66 `can_delete`, #67 `delete`, #68 `get_detail`, #77 `rename`, #102 `init_calculation`

**Assessment:**
- 2 creation paths: `svc.calculation.create()` (#62) and `svc.project.init_calculation()` (#102). **Merge candidate** — should be one method.
- `get` vs `get_detail`: #53 returns CalculationDTO, #68 returns rich dict with steps/structure info. The difference is justified (lightweight vs full), but naming is confusing. Consider `get` vs `get_full`.
- `require_ref` (#55) and `require_enclosing` (#58) are resolution helpers, not CRUD. Consider if these should be internal-only.

### Group 3: Step Management (17 methods)

**Methods:** #56 `require_step_ref`, #59 `get_step`, #60 `get_step_detail`, #61 `list_steps`, #64 `update_step_params`, #73 `add_step`, #74 `add_step_from_spec`, #75 `remove_step`, #76 `rename_step`, #78 `set_common_card`, #70 `get_common_cards`, #81 `reset_step_params`, #82 `reorder_steps`, #84 `import_step_from_qe_input`

**Assessment:**
- `add_step` (#73) vs `add_step_from_spec` (#74): The former takes individual parameters, the latter a spec dict. **Merge candidate** — could be one method with overloaded input.
- `get_step` (#59) vs `get_step_detail` (#60): Similar to get/get_detail above. Justified but confusing naming.
- `import_step_from_qe_input` (#84) is QE-specific and should eventually be generalized.

### Group 4: Structure Management (12 methods)

**Methods:** #37-48 (all svc.structure methods)

**Assessment:**
- `promote_relax_structure` (#47) vs `save_relax_final_structure` (#48): Both promote relax output to project structure. #48 is idempotent, #47 is not. **Merge candidate** — should be one method with idempotency option.
- `visualize` (#41) is only called internally and may be dead code. **Remove candidate.**
- `get_vis_data` (#43) is the active visualization method for the GUI.

### Group 5: Pseudo/Library Management (24 methods + 7 utils)

**Methods:** #11-24 (static), #79-80, #85-86, #100, #103-105 + 7 utility functions

**Assessment:**
- This is the largest capability group and the most scattered. Methods are split across:
  - Depth 0 statics: 14 methods (#11-24) — library/archive operations
  - `svc.calculation`: 4 methods (#79, #80, #85, #86) — step/calc-level pseudo mapping
  - `svc.project`: 3 methods (#100, #103-105) — project-level pseudo operations
  - `api.utils`: 7 functions
- **Major consolidation opportunity**: The 14 depth-0 pseudo statics could be grouped under a `svc.pseudo` sub-object.
- `get_step_pseudo_mapping` (#79) vs `get_pseudo_mapping` (#85): step-level vs calc-level, but confusing naming.

### Group 6: Run/Execution (8 methods)

**Methods:** #5 `run_single_step`, #88-92 (svc.run)

**Assessment:**
- `run_single_step` (#5) is a static method for standalone execution. `svc.run.run_step` (#89) is for project-based execution. Both are justified but the name collision is confusing.
- `cancel` (#90) and `list_runs` (#91) are marked internal-only but should be daemon-accessible for job management.

### Group 7: Analysis (12 methods + 7 utils)

**Methods:** #25-36 (svc.analysis) + analysis utility functions

**Assessment:**
- `list_step_artifacts` (#25) vs `list_raw_files` (#28): Both list files for a step. #28 is a "Surface A wrapper" that calls #25. **Merge candidate** — keep one, add a parameter for filtering.
- `read_step_artifact_text` (#26) vs `read_raw_file` (#29): Same pattern. **Merge candidate.**
- `analyze_scf` (#27) is CLI-only and uses different approach (file path) vs the rest (selectors). Could be consolidated.

### Group 8: Online Search (4 methods)

**Methods:** #49-52 (svc.online_search)

**Assessment:** Clean and minimal. No consolidation needed.

### Group 9: History (9 methods)

**Methods:** #110-118 (svc.history)

**Assessment:** Clean. The `list_runs` here (#113) vs `svc.run.list_runs` (#91) could be confusing — different domains but similar names.

### Group 10: Engine Info (4 methods + 5 utils)

**Methods:** #106-109 (svc.engine) + engine registry utils

**Assessment:**
- `svc.engine.list()` (#106) is never directly called by daemon/CLI — daemon uses `list_engine_families()` utility. **Check if needed.**
- `svc.engine.validate_installation()` (#109) appears unused. **Remove candidate.**

### Group 11: Configuration/Presets (5 methods + 4 utils)

**Methods:** #71 `set_engine_family`, #72 `apply_presets`, #87 `configure_species_map` + preset utils

**Assessment:** Reasonably clean. `apply_presets` is calc-level broadcast. `apply_presets_to_step` is step-level via utils.

---

## 4. Consolidation Opportunities (Phase 1, Step 1.3)

### Opportunity 1: Merge duplicate calculation listing

- **Methods involved:** #54 `svc.calculation.list()`, #96 `svc.project.list_calculations()`
- **Current state:** Both return `list[CalculationDTO]`. Project's version delegates internally.
- **Proposed change:** Remove `svc.project.list_calculations()`. Use `svc.calculation.list()` everywhere.
- **Rationale:** Identical result type. Having both is confusing — callers must choose which to call.
- **Risk/complexity:** Low. Find-and-replace in internal callers.
- **Blocked by:** Nothing.

### Opportunity 2: Unify calculation creation

- **Methods involved:** #62 `svc.calculation.create()`, #102 `svc.project.init_calculation()`
- **Current state:** `create()` takes `engine` + kwargs; `init_calculation()` takes `name` + `template` + `engine_family`. Both create calculations. CLI uses `init_calculation()`, daemon uses `create_calculation` RPC which calls `init_calculation()`.
- **Proposed change:** Merge into a single `svc.calculation.create()` that accepts optional `template` and `engine_family` parameters.
- **Rationale:** Two methods for the same conceptual operation. Jupyter users must guess which to call.
- **Risk/complexity:** Medium. CLI and daemon call sites need updating. Template logic needs porting.
- **Blocked by:** Nothing.

### Opportunity 3: Merge add_step variants

- **Methods involved:** #73 `add_step()`, #74 `add_step_from_spec()`
- **Current state:** `add_step()` takes individual params; `add_step_from_spec()` takes a dict.
- **Proposed change:** Make `add_step()` accept an optional `spec` dict parameter. If provided, use it; otherwise build from individual params.
- **Rationale:** Reduces decision surface for callers.
- **Risk/complexity:** Low. The spec-based path is a subset.
- **Blocked by:** Nothing.

### Opportunity 4: Merge relax structure promotion

- **Methods involved:** #47 `promote_relax_structure()`, #48 `save_relax_final_structure()`
- **Current state:** `promote` is non-idempotent, `save` is idempotent. Both do essentially the same thing.
- **Proposed change:** Keep `save_relax_final_structure()` (idempotent is always better), deprecate `promote_relax_structure()`.
- **Rationale:** Idempotency is a property, not a separate operation.
- **Risk/complexity:** Low. Deprecate with thin wrapper.
- **Blocked by:** Nothing.

### Opportunity 5: Merge artifact listing methods

- **Methods involved:** #25 `list_step_artifacts()`, #28 `list_raw_files()`
- **Current state:** `list_raw_files` is documented as "Surface A wrapper" calling `list_step_artifacts`.
- **Proposed change:** Remove `list_raw_files()`. Add `filter` parameter to `list_step_artifacts()`.
- **Rationale:** `list_raw_files` is a thin filter over `list_step_artifacts`. One method with a filter is cleaner.
- **Risk/complexity:** Low. Update daemon call sites.
- **Blocked by:** Nothing.

### Opportunity 6: Merge artifact reading methods

- **Methods involved:** #26 `read_step_artifact_text()`, #29 `read_raw_file()`
- **Current state:** Same pattern as above. `read_raw_file` is "Surface A wrapper".
- **Proposed change:** Remove `read_raw_file()`. Use `read_step_artifact_text()` with appropriate defaults.
- **Rationale:** Same operation, different defaults.
- **Risk/complexity:** Low.
- **Blocked by:** Nothing.

### Opportunity 7: Remove dead visualization method

- **Methods involved:** #41 `svc.structure.visualize()`
- **Current state:** Not called by daemon or CLI. `get_vis_data()` (#43) is the active method.
- **Proposed change:** Verify no external callers exist, then remove.
- **Rationale:** Dead code.
- **Risk/complexity:** Low. Verify before removing.
- **Blocked by:** Verify that no Jupyter notebooks or external code calls it.

### Opportunity 8: Group pseudo statics under sub-object

- **Methods involved:** #11-24 (14 depth-0 static methods for pseudo/library management)
- **Current state:** 14 static methods directly on QMSService.
- **Proposed change:** Create `QMSService.Pseudo` sub-object (like Structure, Calculation, etc.). Move all 14 methods there.
- **Rationale:** These are a coherent capability group. Having them at depth 0 clutters the top-level API.
- **Risk/complexity:** Medium. Many daemon and CLI call sites to update.
- **Blocked by:** Nothing, but coordination needed.

### Opportunity 9: Flatten resolution helpers or make internal

- **Methods involved:** #40 `require_ref` (structure), #55 `require_ref` (calculation), #56 `require_step_ref`, #57 `resolve_enclosing_path`, #58 `require_enclosing`
- **Current state:** Used by CLI for selector resolution. Internal API plumbing exposed as public.
- **Proposed change:** Either (a) make these internal (`_require_ref`), or (b) provide higher-level methods that don't need them.
- **Rationale:** These are implementation details. Jupyter users shouldn't need to call `require_ref()`.
- **Risk/complexity:** High. CLI uses them extensively. Would require new high-level CLI helper.
- **Blocked by:** CLI refactoring needed first.

### Opportunity 10: Consolidate pseudo mapping methods

- **Methods involved:** #79 `get_step_pseudo_mapping`, #80 `set_step_pseudo_mapping`, #85 `get_pseudo_mapping`, #86 `update_species_map`, #87 `configure_species_map`
- **Current state:** 5 methods for pseudo/species configuration at different scopes (step vs calc).
- **Proposed change:** Rename for clarity: `get_step_pseudo_mapping` → keep, `get_pseudo_mapping` → `get_calc_pseudo_mapping`. Consider merging `update_species_map` and `configure_species_map`.
- **Rationale:** `configure_species_map` and `update_species_map` do overlapping things.
- **Risk/complexity:** Medium.
- **Blocked by:** Need to verify behavioral differences.

### Opportunity 11: Merge `get` and `get_detail` naming

- **Methods involved:** #53/68 (calculation get/get_detail), #59/60 (step get/get_step_detail)
- **Current state:** `get` returns DTO, `get_detail` returns rich dict with embedded data.
- **Proposed change:** Rename `get_detail` to `get_full` or add `detail=True` parameter to `get`.
- **Rationale:** Clearer intent. "detail" is vague.
- **Risk/complexity:** Low if renaming, medium if merging.
- **Blocked by:** Nothing.

### Opportunity 12: Remove QE metadata re-exports from api.utils

- **Methods involved:** 9 QE metadata re-exports (`get_ui_parameters`, `list_supported_modules`, etc.)
- **Current state:** `api.utils` re-exports 9 QE-specific metadata functions from `drivers.qe.data`.
- **Proposed change:** These should be accessed via `svc.engine.get_parameter_metadata()` or the generic `get_engine_parameter_metadata()` util.
- **Rationale:** QE-specific re-exports violate engine-agnostic API principle.
- **Risk/complexity:** Medium. Daemon's `_qe_parameter_metadata_internal` uses these directly.
- **Blocked by:** Need generic engine parameter metadata API first.

### Opportunity 13: Move `build_resource_index()` to internal-only

- **Methods involved:** #95 `svc.project.build_resource_index()`
- **Current state:** Called by CLI and daemon to force-rebuild index.
- **Proposed change:** Make internal. Trigger automatically when needed (after mutations).
- **Rationale:** Callers shouldn't need to manually trigger index rebuilds — that's internal bookkeeping.
- **Risk/complexity:** High. Need to ensure all mutation paths trigger rebuild.
- **Blocked by:** Registry rebuild needs to be auto-triggered.

### Opportunity 14: Remove `svc.engine` sub-object methods called only internally

- **Methods involved:** #106-109 (all svc.engine methods)
- **Current state:** `list`, `get_info`, `list_step_types`, `validate_installation` — none called by daemon or CLI directly (daemon uses utils).
- **Proposed change:** Verify usage. If truly internal-only, deprecate the sub-object.
- **Rationale:** Unused public surface.
- **Risk/complexity:** Low if truly unused.
- **Blocked by:** Verify no Jupyter or external usage.

### Opportunity 15: Consolidate project rename utilities

- **Methods involved:** #97 `collect_slugs`, #98 `apply_structure_rename`, #99 `apply_calculation_rename`
- **Current state:** CLI calls these individually to implement rename. Low-level plumbing exposed as API.
- **Proposed change:** Absorb into `svc.structure.update_meta()` and `svc.calculation.rename()`.
- **Rationale:** Rename should be one API call, not 3-4 calls.
- **Risk/complexity:** Medium. CLI needs refactoring.
- **Blocked by:** CLI rename refactoring.

### Opportunity 16: Move `analyze_scf` from svc.analysis to utils-only

- **Methods involved:** #27 `svc.analysis.analyze_scf()`
- **Current state:** Takes a file path (not selectors), CLI-only. Other analysis methods use selectors.
- **Proposed change:** Keep only the `parse_scf_output` + `plot_scf_convergence` utils for CLI. Remove from svc.analysis or refactor to use selectors.
- **Rationale:** Inconsistent with other analysis methods that use selectors.
- **Risk/complexity:** Low.
- **Blocked by:** Nothing.

### Opportunity 17: Merge list_runs across domains

- **Methods involved:** #91 `svc.run.list_runs()`, #113 `svc.history.list_runs()`
- **Current state:** `svc.run.list_runs()` returns RunResultDTO list. `svc.history.list_runs()` returns dict with richer history data.
- **Proposed change:** Rename `svc.history.list_runs()` to `svc.history.list_run_history()` for clarity.
- **Rationale:** Prevent name confusion.
- **Risk/complexity:** Low.
- **Blocked by:** Nothing.

### Opportunity 18: Move online structure import logic from daemon to API

- **Methods involved:** RPC `structure_import_online_candidate` (daemon business logic)
- **Current state:** ~100 lines of structure import logic in daemon including file writes, slug generation, config mutation.
- **Proposed change:** Create `svc.structure.import_online(session_id, candidate_id)` that encapsulates all this logic.
- **Rationale:** Jupyter users cannot import online structures without the daemon.
- **Risk/complexity:** Medium. Moving daemon code to API.
- **Blocked by:** Nothing.

### Opportunity 19: Move online candidate fetching logic from daemon to API

- **Methods involved:** RPC `structure_get_online_candidate` (daemon business logic, ~370 lines)
- **Current state:** Massive business logic in daemon: SQLite access, pymatgen construction, primitive cell conversion, visualization pipeline, bond computation.
- **Proposed change:** Create `svc.online_search.get_candidate_detail(session_id, candidate_id)` that returns complete candidate with visualization data.
- **Rationale:** This is the single largest business logic leak. Jupyter users cannot preview online structures without the daemon.
- **Risk/complexity:** High. 370 lines to move and refactor.
- **Blocked by:** Nothing.

### Opportunity 20: Move QE metadata browser from daemon to API

- **Methods involved:** Daemon's `_qe_parameter_metadata_internal` (~400 lines)
- **Current state:** Full QE/engine parameter metadata browser implemented in daemon.
- **Proposed change:** Move to `get_engine_parameter_metadata()` in api.utils (already partially exists) or a new `svc.engine.browse_parameters()` method.
- **Rationale:** Jupyter users cannot browse engine parameters without daemon.
- **Risk/complexity:** Medium. Logic needs to be generalized for all engines.
- **Blocked by:** Generic engine metadata API (partially exists).

### Opportunity 21: Remove `svc.run.cancel()` and `svc.run.list_runs()` if truly internal

- **Methods involved:** #90 `cancel`, #91 `list_runs`
- **Current state:** Marked internal-only. Daemon uses JobManager directly for job management.
- **Proposed change:** Either make these the canonical job management path (daemon should use them too), or remove them.
- **Rationale:** If daemon bypasses these, they're dead code.
- **Risk/complexity:** Medium. Need to decide canonical job management path.
- **Blocked by:** Job management architecture decision.

### Opportunity 22: Consolidate `write_qe_input_file` and `build_step_spec_from_qe_input`

- **Methods involved:** utils `write_qe_input_file`, `build_step_spec_from_qe_input`, `apply_card_overrides_to_qe_input`, `apply_species_overrides_to_qe_input`
- **Current state:** 4 QE-specific functions in the engine-agnostic API utils.
- **Proposed change:** Move to `qmatsuite.api.qe_io` module (already exists for QECardType/QEInputParser).
- **Rationale:** QE-specific code should not be in generic utils.
- **Risk/complexity:** Low. Already have the module.
- **Blocked by:** Nothing.

---

## 5. Justification for Non-Mergeable Methods (Phase 1, Step 1.4)

### svc.analysis
| Method | Justification |
|--------|---------------|
| `list_step_artifacts` | Core artifact enumeration — unique capability |
| `read_step_artifact_text` | Text content retrieval with security sandbox — unique |
| `analyze_scf` | *Consolidation target (#16)* |
| `get_step_digest` | Surface B: post-run digest — structurally different from analysis objects |
| `get_analysis` | Surface C: on-demand derivation from evidence — unique computation path |
| `get_analysis_snapshot` | Replay from CAS/SQLite — different data source than get_analysis |
| `get_analysis_instances_for_step` | Enumeration of analysis instances — different from single analysis retrieval |
| `get_field3d_grid` | Specialized 3D grid materialization — unique data format |
| `get_reference_analysis` | Demo-only reference data — unique source (bundled references, not runs) |
| `get_relax_final_structure_preview` | Read-only preview with no side effects — distinct from promote/save |

### svc.structure
| Method | Justification |
|--------|---------------|
| `get` | Core CRUD — returns lightweight DTO |
| `list` | Core CRUD enumeration |
| `get_atoms` | Full coordinate data — heavyweight, Jupyter-specific |
| `import_file` | File import with format detection — unique capability |
| `get_vis_data` | 3D rendering payload — unique data shape |
| `update_meta` | Rename — distinct from CRUD get/set |
| `can_delete` | Pre-check before destructive action — separate from delete |
| `delete` | Destructive CRUD — must be separate |
| `save_relax_final_structure` | Promotes run output to project resource — unique data flow |

### svc.calculation (after consolidations)
| Method | Justification |
|--------|---------------|
| `get` | Core CRUD lightweight |
| `list` | Core CRUD enumeration |
| `create` | Core CRUD creation *(will merge init_calculation)* |
| `update_meta` | Metadata update — different from parameter update |
| `get_step` | Step retrieval — different scope from calculation get |
| `get_step_detail` | Rich step detail with params/cards — heavyweight |
| `list_steps` | Step enumeration — calculation-scoped |
| `update_step_params` | Parameter mutation — distinct from metadata |
| `duplicate` | Deep copy — unique operation |
| `get_detail` | Rich calculation detail — heavyweight |
| `set_structure` | Structure binding — changes calculation's structure reference |
| `get_common_cards` | K_POINTS view model — specialized data shape |
| `set_engine_family` | Engine selection — state transition (UNDECIDED→DECIDED) |
| `apply_presets` | Broadcast operation across all steps — unique scope |
| `add_step` | Step creation *(will merge add_step_from_spec)* |
| `remove_step` | Step deletion |
| `rename_step` | Step rename |
| `rename` | Calculation rename |
| `set_common_card` | K_POINTS mutation — specialized |
| `get_step_pseudo_mapping` | Step-scoped pseudo info |
| `set_step_pseudo_mapping` | Step-scoped pseudo mutation |
| `reset_step_params` | Reset to defaults — distinct from update |
| `reorder_steps` | Step ordering — unique operation |
| `update_steps_structure` | Structure propagation to all steps |
| `import_step_from_qe_input` | QE import — specialized ingestion |
| `get_pseudo_mapping` | Calc-scoped pseudo info |
| `configure_species_map` | Species configuration — distinct from pseudo mapping |

---

## 6. Nesting Flattening Opportunities (Phase 1, Step 1.5)

The current API uses 8 depth-1 sub-objects accessed via properties:

```python
svc.analysis.method()
svc.structure.method()
svc.online_search.method()
svc.calculation.method()
svc.run.method()
svc.project.method()
svc.engine.method()
svc.history.method()
```

### Flattening Assessment

| Current | Flat alternative | Recommendation |
|---------|-----------------|----------------|
| `svc.analysis.get_analysis(...)` | `svc.get_analysis(...)` | **Keep nested** — 12 methods per sub-object keeps it organized |
| `svc.calculation.add_step(...)` | `svc.add_step(...)` | **Keep nested** — 35 methods would overwhelm flat namespace |
| `svc.structure.get(...)` | `svc.get_structure(...)` | **Could flatten** — only 12 methods |
| `svc.run.run_calculation(...)` | `svc.run_calculation(...)` | **Could flatten** — only 5 methods |
| `svc.project.get_config(...)` | `svc.get_project_config(...)` | **Could flatten** — only 13 methods |
| `svc.engine.list(...)` | `svc.list_engines(...)` | **Could flatten** — only 4 methods, mostly unused |
| `svc.history.get_timeline(...)` | `svc.get_history_timeline(...)` | **Could flatten** — 9 methods |
| `svc.online_search.search(...)` | `svc.search_online(...)` | **Could flatten** — only 4 methods |

**Recommendation:** Keep the current nesting. With 117 methods, a flat namespace would be overwhelming. The sub-object grouping provides clear domain boundaries. The 8 sub-objects match the 8 logical domains well. The cost of nesting (one extra `.`) is far outweighed by the organization benefit.

**One exception:** The 14 depth-0 pseudo statics (#11-24) should move INTO a sub-object (`svc.pseudo`), not out of nesting.

---

## 7. User Workflow Coverage (Phase 1, Step 1.6)

### Workflow 1: Load demo → run → analyze → plot

```python
# Step 1: Load demo
project = QMSService.create_demo_project("si_scf", target_dir)  # API ✓

# Step 2: Open project
svc = QMSService(project_root)  # API ✓

# Step 3: List calculations
calcs = svc.calculation.list()  # API ✓

# Step 4: Run calculation
result = svc.run.run_calculation(calc_selector)  # API ✓

# Step 5: Get analysis
analysis = svc.analysis.get_analysis(run_ulid, "scf_convergence")  # API ✓

# Step 6: Plot (via utils)
from qmatsuite.api.utils import parse_scf_output, plot_scf_convergence, save_figure
scf = parse_scf_output(output_file)  # API utils ✓
fig = plot_scf_convergence(scf)  # API utils ✓
save_figure(fig, "convergence.png")  # API utils ✓
```

**Verdict: FULLY COVERED.** All steps have API methods.

### Workflow 2: Empty project → create calc → import structure → add steps → configure → run → analyze

```python
# Step 1: Create project
QMSService.init_project(target_dir, "my_project")  # API ✓

# Step 2: Open project
svc = QMSService(project_root)  # API ✓

# Step 3: Import structure (local file)
struct = svc.structure.import_file("POSCAR")  # API ✓

# Step 3b: Import structure (online)
results = svc.online_search.search_structures("silicon")  # API ✓
candidate = svc.online_search.fetch_structure(ref)  # API ✓
# !! CRITICAL GAP: No API method to save fetched structure to project!
# The daemon's structure_import_online_candidate does this, but API doesn't expose it.
# Jupyter users CANNOT import online structures.

# Step 4: Create calculation
calc = svc.project.init_calculation("Si SCF", structure_selector=struct.meta.slug)  # API ✓

# Step 5: Set engine
calc = svc.calculation.set_engine_family(calc_selector, "qe")  # API ✓

# Step 6: Add steps
step = svc.calculation.add_step(calc_selector, "scf")  # API ✓

# Step 7: Configure step parameters
svc.calculation.update_step_params(calc_selector, step_selector, {"ecutwfc": 60})  # API ✓

# Step 8: Apply presets
svc.calculation.apply_presets(calc_selector, {"precision": "high"})  # API ✓

# Step 9: Run
result = svc.run.run_calculation(calc_selector)  # API ✓

# Step 10: Analyze
analysis = svc.analysis.get_analysis(run_ulid, "scf_convergence")  # API ✓
```

**Verdict: ONE CRITICAL GAP.** Online structure import is daemon-only. All other steps have API methods.

### Gap Summary

| Gap | Severity | Impact |
|-----|----------|--------|
| No API for importing online structure to project | **CRITICAL** | Jupyter users cannot use online structure search end-to-end |
| No API for previewing online candidate (visualization) | **HIGH** | Jupyter users cannot preview before importing |
| No API for browsing engine parameter metadata (full) | **MEDIUM** | Jupyter users cannot explore available parameters for non-QE engines |
| No `delete_project` API method | **LOW** | CLI uses shutil directly; Jupyter users would too |

---

## 8. Complete RPC Endpoint Enumeration (Phase 2, Step 2.1)

**Total unique RPC endpoints: 120** (dispatch table has 121 entries, 1 duplicate key `detect_workflow`)

### System (2)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 1 | `ping` | Health check | None | Returns `{pong: true}` |
| 2 | `shutdown` | Stop daemon | None | Sets `_running = False` |

### Environment & Settings (7)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 3 | `detect_qe` | QE engine detection | `get_qe_engine_status()["detection"]` | No |
| 4 | `get_env_info` | Environment info | `get_qe_engine_status()["environment"]` | No |
| 5 | `list_qe_engines` | Available QE engines | `get_qe_engine_status()["available_engines"]` | No |
| 6 | `set_qe_engine` | Set QE binary | `set_qe_engine(bin_dir)` | No |
| 7 | `set_log_level` | Set daemon log level | None | Daemon-only config |
| 8 | `set_debug_resolution` | Toggle debug resolution | `set_settings(...)` | Thin wrapper |
| 9 | `get_debug_resolution` | Get debug resolution state | `QMSService.get_settings()` | Thin wrapper |

### Generic Engine (5)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 10 | `list_engine_families` | List engines | `list_engine_families()` | No |
| 11 | `list_step_palette` | Step types for engine | `get_step_palette(engine_family)` | No |
| 12 | `list_engine_ui_parameters` | UI parameter metadata | `get_engine_ui_parameters(...)` | No |
| 13 | `list_engine_parameter_metadata` | Full parameter browser | `get_engine_parameter_metadata()` or `_qe_parameter_metadata_internal()` | **YES: ~400 lines QE special-casing** |
| 14 | `set_engine_family` | Set engine on calc | `svc.calculation.set_engine_family()` | No |

### Pseudopotential Configuration (14)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 15 | `get_pseudo_config` | Get pseudo config | `get_pseudo_status_bundle()["config"]` | No |
| 16 | `set_pseudo_config` | Set pseudo config | `set_pseudo_config(...)` | No |
| 17 | `validate_pseudo_config` | Validate pseudo config | `get_pseudo_status_bundle()["validation"]` | No |
| 18 | `init_pseudo_dirs` | Init pseudo dirs | `QMSService.init_pseudo_dirs()` | No |
| 19 | `install_seed_to_store` | Install SSSP from seed | `QMSService.install_sssp_from_seed()` | Conditional branching |
| 20 | `list_installed_sssp` | List installed SSSP | `get_pseudo_status_bundle()["installed_sssp"]` | Wraps in dict |
| 21 | `list_seed_archives` | List seed archives | `get_pseudo_status_bundle()["seed_archives"]` | Wraps in dict |
| 22 | `download_sssp_library` | Download SSSP | `QMSService.download_sssp_library()` | Config extraction + refresh |
| 23 | `download_all_sssp` | Download all SSSP | `QMSService.download_all_sssp()` | Config extraction + refresh |
| 24 | `resolve_project_pseudo_provenance` | Resolve pseudo provenance | `resolve_pseudo_provenance()` | Path resolution |
| 25 | `import_seed_archives` | Import seed archives | `QMSService.import_seed_archives()` | Path conversion |
| 26 | `list_pseudo_archives_status` | Archive status | `get_pseudo_status_bundle()` | **YES: builds grouped_by_library** |
| 27 | `install_pseudo_archive` | Install archive | `QMSService.install_pseudo_archive()` | **YES: manifest lookup + dedup** |
| 28 | `analyze_project_pseudo_effects` | Analyze pseudo effects | `svc.project.analyze_pseudo_effects()` | Thin wrapper |

### Generic Library Manager (6)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 29 | `list_libraries` | List pseudo libraries | `QMSService.list_pseudo_libraries()` | No |
| 30 | `get_library_status` | Get library status | `QMSService.get_library_status()` | Error handling |
| 31 | `install_library` | Install library | `QMSService.install_pseudo_library()` | Thin wrapper |
| 32 | `remove_library` | Remove library | `QMSService.remove_pseudo_library()` | Thin wrapper |
| 33 | `repair_library` | Repair library | `QMSService.repair_pseudo_library()` | Thin wrapper |
| 34 | `compute_store_size` | Compute store size | `QMSService.compute_store_size()` | Thin wrapper |

### Project/Resource Listing (5)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 35 | `get_project_summary` | Project summary | `svc.project.get_summary()` | No |
| 36 | `list_structures` | List structures | `svc.structure.list()` | DTO-to-dict |
| 37 | `list_calculations` | List calculations | `svc.calculation.list()` | DTO-to-dict + `_project_root` injection |
| 38 | `find_project_root` | Find project root | `find_path_context_from_pwd()` | Error→{found:false} |
| 39 | `rebuild_project_registry` | Rebuild index | `svc.project.build_resource_index()` | **YES: snapshot-diff-rebuild** |

### Project Creation & Import (2)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 40 | `create_project` | Create project | `QMSService.init_project()` + `svc.project.get_summary()` | Post-creation summary |
| 41 | `import_structure` | Import structure file | `svc.structure.import_file()` + `svc.structure.list()` | Post-import lookup |

### Online Structure Search (5)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 42 | `structure_search_online` | Search online | `OnlineSearch.search_structures()` | **YES: cache management** |
| 43 | `structure_get_online_candidate` | Preview candidate | `OnlineSearch.fetch_structure()` + vis pipeline | **CRITICAL: ~370 lines business logic** |
| 44 | `structure_list_providers` | List providers | `OnlineSearch.list_providers()` | No |
| 45 | `structure_update_online_sources` | Update sources | `OnlineSearch.update_online_sources()` | DTO construction |
| 46 | `structure_import_online_candidate` | Import candidate | Cache + file write + config | **CRITICAL: ~100 lines business logic** |

### Structure Management (3)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 47 | `rename_structure` | Rename structure | `svc.structure.update_meta()` | Pre-rename capture |
| 48 | `delete_structure` | Delete structure | `svc.structure.delete()` | Pre-delete capture |
| 49 | `can_delete_structure` | Check deletability | `svc.structure.can_delete()` | No |

### Calculation Management (5)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 50 | `list_calculation_templates` | List templates | `list_calculation_templates()` | No |
| 51 | `create_calculation` | Create calculation | `svc.project.init_calculation()` + list | Cache + post-create detail |
| 52 | `rename_calculation` | Rename | `svc.calculation.rename()` | ULID disambiguation |
| 53 | `delete_calculation` | Delete | `svc.calculation.delete()` | **YES: extensive validation** |
| 54 | `can_delete_calculation` | Check deletability | `svc.calculation.can_delete()` | ULID resolution |

### Step Operations (14)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 55 | `get_step_detail` | Step details | `svc.calculation.get_step_detail()` | ULID resolution + debug |
| 56 | `update_step_params` | Update params | `svc.calculation.update_step_params()` | Re-fetch after update |
| 57 | `reset_step_params` | Reset params | `svc.calculation.reset_step_params()` | Cache |
| 58 | `get_common_cards` | Get K_POINTS etc | `svc.calculation.get_common_cards()` | ULID resolution |
| 59 | `set_common_card` | Set K_POINTS etc | `svc.calculation.set_common_card()` | ULID + cache |
| 60 | `get_pseudo_mapping` | Step pseudo mapping | `svc.calculation.get_step_pseudo_mapping()` | ULID + cache |
| 61 | `set_pseudo_mapping` | Set pseudo mapping | `svc.calculation.set_step_pseudo_mapping()` | ULID + cache |
| 62 | `import_pseudo_files` | Import pseudo files | `svc.project.import_pseudo_files()` | No |
| 63 | `search_legacy_pseudos` | Search QE pseudos | `search_legacy_pseudos()` | Optional config |
| 64 | `download_pseudo_by_filename` | Download pseudo | `download_pseudo_by_filename()` | Cache config |
| 65 | `download_pseudo_candidate` | Download by URL/name | `download_pseudo_from_url()` or `download_pseudo_by_filename()` | URL vs filename dispatch |
| 66 | `promote_relax_structure` | Promote relax output | `svc.structure.promote_relax_structure()` | Cache invalidation |
| 67 | `get_relax_final_structure_preview` | Preview relax output | `svc.analysis.get_relax_final_structure_preview()` | Resolve + cache |
| 68 | `save_relax_final_structure` | Save relax structure | `svc.structure.save_relax_final_structure()` | Registry rebuild |

### Calculation Configuration (9)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 69 | `get_calculation_detail` | Calc detail | `svc.calculation.get_detail()` | ULID resolution |
| 70 | `reorder_calculation_steps` | Reorder steps | `svc.calculation.reorder_steps()` | Resolve + cache |
| 71 | `add_step_to_calculation` | Add step | `svc.calculation.add_step()` + refresh | Post-add list refresh |
| 72 | `change_calculation_structure` | Change structure | `svc.calculation.set_structure()` | **YES: dual ULID resolution + path protection** |
| 73 | `get_calculation_pseudo_mapping` | Calc pseudo mapping | `svc.calculation.get_pseudo_mapping()` | ULID + verbose logging |
| 74 | `update_calculation_species_map` | Update species map | `svc.calculation.update_species_map()` | Resolve + cache |
| 75 | `get_pseudo_options_for_calculation` | Pseudo options | `svc.calculation.get_detail()` + `svc.project.get_pseudo_options()` | **YES: element extraction logic** |
| 76 | `materialize_pseudo_file` | Materialize pseudo | `svc.project.materialize_pseudo_file()` | No |
| 77 | `delete_step` | Delete step | `svc.calculation.remove_step()` | Ghost step handling |

### Preset Detection (6)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 78 | `get_preset_catalog` | Get catalog | `get_preset_catalog()` | No |
| 79 | `detect_presets` | Detect presets | `get_calculation_preset_bundle()` | Path resolution |
| 80 | `detect_workflow` | Detect workflow | `get_calculation_preset_bundle()` | Path resolution |
| 81 | `apply_presets_to_step` | Apply to step | `apply_presets_to_step()` | Step resolution + post-detect |
| 82 | `apply_presets_to_calculation` | Apply to calc | `svc.calculation.apply_presets()` | Thin wrapper |
| 83 | `get_step_preset_footprints` | Preset footprints | `get_calculation_preset_bundle()` | ULID + path resolution |

### Pre-flight & Demo (3)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 84 | `preflight_check` | Pre-run checks | `svc.run.preflight()` | Optional resolution |
| 85 | `create_demo_project` | Create demo | `QMSService.create_demo_project()` | Registry rebuild |
| 86 | `list_demo_projects` | List demos | `QMSService.list_demo_projects()` | Error swallowing |

### Visualization & Analysis (11)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 87 | `get_structure_vis` | Structure vis data | `svc.structure.get_vis_data()` | No |
| 88 | `get_reference_analysis` | Demo reference analysis | `svc.analysis.get_reference_analysis()` | Type validation |
| 89 | `get_analysis` | Get analysis | `svc.analysis.get_analysis()` | Thin wrapper |
| 90 | `get_analysis_instances_for_step` | Analysis instances | `svc.analysis.get_analysis_instances_for_step()` | Thin wrapper |
| 91 | `get_analysis_snapshot` | Replay analysis | `svc.analysis.get_analysis_snapshot()` | Thin wrapper |
| 92 | `get_field3d_grid` | Field3D grid | `svc.analysis.get_field3d_grid()` | Thin wrapper |
| 93 | `get_step_digest` | Step digest | `svc.analysis.get_step_digest()` | Thin wrapper |
| 94 | `list_step_artifacts` | List artifacts | `svc.analysis.list_step_artifacts()` | Resolve + wrapper |
| 95 | `read_step_artifact_text` | Read artifact | `svc.analysis.read_step_artifact_text()` | Resolve + wrapper |
| 96 | `list_raw_files` | List raw files | `svc.analysis.list_raw_files()` | Resolve + wrapper |
| 97 | `read_raw_file` | Read raw file | `svc.analysis.read_raw_file()` | Resolve + wrapper |

### Volume Visualization (2)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 98 | `list_wannier_3d_fixtures` | List 3D fixtures | None | **YES: pure filesystem scanning** |
| 99 | `compile_fixture_volume` | Compile volume data | `parse_volume_artifact()` + `create_blob_store()` | Blob verification |

### Job Management (8)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 100 | `run_calculation` | Run calculation | `svc.run.run_calculation()` via wrapper | **YES: ULID gen, step init, wrapper construction** |
| 101 | `run_step` | Run step | `svc.run.run_step()` via wrapper | Similar to above |
| 102 | `run_single_step` | Run standalone step | `QMSService.run_single_step()` | ULID gen, cache |
| 103 | `get_job_status` | Job status | `job_manager.get_job_status()` | No |
| 104 | `get_job_logs` | Job logs | `job_manager.get_job_logs()` | No |
| 105 | `list_jobs` | List jobs | `job_manager.list_jobs()` | Path normalization |
| 106 | `job_counts` | Job counts | `job_manager.count_by_status()` | Thin wrapper |
| 107 | `cancel_job` | Cancel job | `job_manager.cancel_job()` | No |

### Journal (2)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 108 | `list_journal_entries` | List journal entries | `get_journal().list_entries()` | DTO serialization |
| 109 | `get_journal_entry` | Get journal entry | `get_journal().get_entry()` | Null-safe |

### Project History (9)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 110 | `get_project_history` | Get timeline | `svc.history.get_timeline()` | Thin wrapper |
| 111 | `get_run_revision` | Run details | `svc.history.get_run_revision()` | Thin wrapper |
| 112 | `list_project_runs` | List runs | `svc.history.list_runs()` | Thin wrapper |
| 113 | `pin_analysis_to_history` | Pin analysis | `svc.history.pin_analysis()` | Base64 PNG decode |
| 114 | `can_pin_to_run` | Can pin check | `svc.history.can_pin()` | No |
| 115 | `get_pin_data` | Get pinned data | `svc.history.get_pin_data()` | No |
| 116 | `get_latest_run_for_step` | Latest run for step | `svc.history.get_latest_run_for_step()` | No |
| 117 | `delete_project_history` | Delete history | `svc.history.delete()` | No |
| 118 | `get_storage_summary` | Storage summary | `svc.history.get_storage_summary()` | No |

### Workflow (4)

| # | RPC endpoint | Purpose | API call(s) | Extra logic? |
|---|-------------|---------|-------------|--------------|
| 119 | `list_workflow_templates` | List templates | `QMSService.get_workflow_service().list_templates()` | Serialization + filter |
| 120 | `detect_workflow_for_calculation` | Detect workflow | 3 workflow service calls | **YES: coverage computation** |
| ~~121~~ | ~~`detect_workflow`~~ (duplicate of #80) | ~~Detect workflow~~ | ~~Overridden by second registration~~ | ~~Redundant~~ |
| 122 | `instantiate_workflow` | Instantiate workflow | `service.instantiate_workflow()` | No |

---

## 9. RPC Consolidation Opportunities (Phase 2, Step 2.2)

### RPC-C1: Merge `list_step_artifacts` + `list_raw_files` RPCs

Both call similar API methods. The API methods themselves should merge (Opportunity #5), and the RPC endpoints should follow.

### RPC-C2: Merge `read_step_artifact_text` + `read_raw_file` RPCs

Same as above (Opportunity #6).

### RPC-C3: Remove duplicate `detect_workflow` registration

Lines 344 and 400 both register `detect_workflow`. The second overwrites the first. Remove the dead first registration.

### RPC-C4: Consolidate `detect_presets` and `detect_workflow`

Both call `get_calculation_preset_bundle()` and do path resolution. Could be one RPC with a `what` parameter.

### RPC-C5: Merge `get_pseudo_mapping` and `get_calculation_pseudo_mapping`

Step-level vs calc-level pseudo mapping. The API methods are different but the RPC plumbing is nearly identical. Consider parameterizing scope.

### RPC-C6: Merge `download_pseudo_by_filename` and `download_pseudo_candidate`

`download_pseudo_candidate` already dispatches to `download_pseudo_by_filename` or `download_pseudo_from_url`. The first is redundant.

### RPC-C7: Merge `promote_relax_structure` and `save_relax_final_structure`

API consolidation #4. The RPC endpoints should follow.

### RPC-C8: Consider merging QE-specific RPCs into generic engine RPCs

`detect_qe`, `get_env_info`, `list_qe_engines`, `set_qe_engine` are QE-specific. Long-term, these should be parameterized versions of generic engine RPCs.

---

## 10. Constitutional Violation Check (Phase 2, Step 2.3)

### Direct Kernel Imports from Daemon: **ZERO**

The daemon properly imports only from `qmatsuite.api` and `qmatsuite.api.utils`. Gate tests `test_import_gate.py` and `test_daemon_kernel_ban.py` enforce this continuously.

### Boundary Smells (Not Hard Violations)

| File:Line | What | Concern |
|-----------|------|---------|
| `server.py:70` | `from qmatsuite.api.utils import _iter_params` | Imports private API function (leading underscore). Should be public or accessed indirectly. |
| `compat.py:~531` | `_expand_step_ulids_to_steps` | Reads `calculation.yaml` directly via `yaml.safe_load`. Should use API method. |
| `compat.py:~272` | `_derive_step_name_from_type` | Does `stype_spec.replace("qe_", "")` — borderline prefix inference. Display-only, not dispatch. |
| `server.py:~5713` | `_snapshot_dag(index)` | Accesses `ResourceIndex.by_id`, `.by_path` — kernel type internals via `Any` typing. |
| `compat.py:~827` | `_shape_create_demo_project` | Instantiates `QMSService` directly and calls multiple service methods. |

---

## 11. Misplaced Daemon Logic (Phase 2, Step 2.4)

### Misplaced Logic 1: Online candidate preview (CRITICAL)

- **Location:** `server.py:2176-2547` (~370 lines)
- **What it does:** Fetches online structure candidate, constructs pymatgen Structure/Molecule, converts to primitive cell, computes bonds, formats visualization data, accesses SQLite cache directly, extracts provenance.
- **Why it's misplaced:** This is core structure processing and visualization pipeline. It uses pymatgen APIs, SQLite queries, and coordinate transformations — all domain logic.
- **Where it should go:** New API method `svc.online_search.get_candidate_detail(session_id, candidate_id)` returning complete candidate with vis data.
- **Impact:** Jupyter users cannot preview online structure candidates without the daemon.

### Misplaced Logic 2: Online candidate import (CRITICAL)

- **Location:** `server.py:2613-2711` (~100 lines)
- **What it does:** Retrieves structure from cache, canonicalizes, generates slug, writes structure file, patches JSON provenance, mutates project config, rebuilds registry.
- **Why it's misplaced:** File writes and config mutations MUST go through the API (Law H9).
- **Where it should go:** New API method `svc.structure.import_online(session_id, candidate_id, name=None)`.
- **Impact:** Jupyter users cannot import online structures to their project.

### Misplaced Logic 3: QE parameter metadata browser (SIGNIFICANT)

- **Location:** `server.py:1424-1840` (~400 lines)
- **What it does:** Full metadata browser with 4 operations: list_modules, list_sections, list_parameters, search. Handles schema versions, managed/protected parameter detection.
- **Why it's misplaced:** Parameter metadata browsing is engine capability, not daemon plumbing.
- **Where it should go:** Enhanced `get_engine_parameter_metadata()` in API utils (already partially exists for non-QE engines).
- **Impact:** Jupyter users cannot browse QE parameter metadata in detail.

### Misplaced Logic 4: Online structure search caching (MODERATE)

- **Location:** `server.py:2118-2174` (~55 lines)
- **What it does:** Creates `OnlineStructureCache`, stores session and candidates.
- **Why it's misplaced:** Cache management is infrastructure/API responsibility.
- **Where it should go:** Inside `svc.online_search.search_structures()` or a companion cache manager.
- **Impact:** Jupyter users' search results are not cached for later retrieval.

### Misplaced Logic 5: Wannier 3D fixture scanning (MODERATE)

- **Location:** `server.py:4843-4970` (~130 lines)
- **What it does:** 3-tier fixture root discovery, manifest.json parsing, recursive glob scanning.
- **Why it's misplaced:** No API call at all. Pure filesystem business logic.
- **Where it should go:** New API utility function or svc.analysis method.
- **Impact:** Jupyter users cannot list available 3D visualization fixtures.

### Misplaced Logic 6: Run calculation wrapper construction (MODERATE)

- **Location:** `server.py:5094-5198` (~100 lines)
- **What it does:** Loads calculation.yaml via `load_calculation()`, initializes step list, computes io_dir, generates ULID, constructs wrapper function for JobManager.
- **Why it's misplaced:** Run preparation logic (io_dir computation, step initialization) is domain logic.
- **Where it should go:** `svc.run.run_calculation()` should handle all preparation internally.
- **Impact:** Minor — the API method exists, but daemon adds extra preparation.

### Misplaced Logic 7: Pseudo archive installation (MODERATE)

- **Location:** `server.py:1251-1364` (~110 lines)
- **What it does:** Manifest lookup, dedup check, install, status refresh.
- **Why it's misplaced:** Installation logic with manifest parsing is domain logic.
- **Where it should go:** `QMSService.install_pseudo_archive()` should handle manifest lookup internally.
- **Impact:** Minor — most logic is pre/post validation.

### Misplaced Logic 8: Workflow detection for calculation (MINOR)

- **Location:** `server.py:6220-6339` (~120 lines)
- **What it does:** Calls 3 workflow service methods, computes coverage, formats labels.
- **Why it's misplaced:** Coverage computation and label formatting is presentation-adjacent domain logic.
- **Where it should go:** Enhanced workflow service method that returns formatted results.
- **Impact:** Minor — Jupyter users can call workflow service directly.

---

## 12. Complete Daemon Function Enumeration (Phase 2, Step 2.5)

### QMSDaemon Core Methods

| # | Function | Purpose | Calls API? | Calls kernel? | Should exist here? |
|---|----------|---------|------------|---------------|--------------------|
| 1 | `__init__` | Initialize daemon | No | No | Yes |
| 2 | `log(message, level)` | Write to stderr | No | No | Yes |
| 3 | `_rpc_log_level_for(endpoint)` | Determine log level | No | No | Yes |
| 4 | `logger` (property) | Logger shim | No | No | Yes |
| 5 | `_configure_logging()` | Configure Python logging | No | No | Yes |
| 6 | `run()` | Main stdin/stdout loop | No | No | Yes |
| 7 | `handle_line(line)` | Parse JSON, dispatch | No | No | Yes |
| 8 | `handle_request(request)` | Route to handler | API errors | No | Yes |
| 9 | `_get_svc(project_root)` | Get cached QMSService | API | No | Yes |
| 10 | `_require_calculation_ref(...)` | Resolve calc | API | No | Yes (boundary validation) |
| 11 | `_require_structure_ref(...)` | Resolve structure | API | No | Yes (boundary validation) |
| 12 | `_require_step_ref(...)` | Resolve step | API | No | Yes (boundary validation) |
| 13 | `_resolve_calculation_with_fallback(...)` | Resolve from cache | API | No | Yes |
| 14 | `_resolve_step_with_fallback(...)` | Resolve from cache | API | No | Yes |
| 15 | `_rebuild_registry_after_write(...)` | Force rebuild | API | No | Yes (but should be auto) |
| 16 | `_snapshot_dag(index)` | Snapshot for diffing | No | **Accesses internals** | **No — uses kernel types** |
| 17 | `_diff_dag(old, new)` | Compute DAG diff | No | No | Marginal — pure dict logic |
| 18 | `_update_logging_level(level)` | Update log level | No | No | Yes |
| 19 | `_qe_parameter_metadata_internal(...)` | QE metadata browser | API utils | No | **No — 400 lines of domain logic** |
| 20 | `_require_path(payload, key)` | Validate Path from payload | No | No | Yes |
| 21 | `_require_str(payload, key)` | Validate string from payload | No | No | Yes |

### DaemonState Methods

| # | Function | Purpose | Should exist? |
|---|----------|---------|---------------|
| 22 | `get_cache(project_root)` | Get/create ProjectCache | Yes |
| 23 | `rebuild_cache(project_root)` | Force rebuild | Yes |
| 24 | `invalidate_cache(project_root)` | Evict cache | Yes |

### compat.py Functions

| # | Function | Purpose | Should exist? |
|---|----------|---------|---------------|
| 25 | `adapt_payload(method, payload)` | v0→current payload adapter | Yes (compat) |
| 26 | `shape_response(method, response)` | Current→v0 response shaper | Yes (compat) |
| 27-38 | 12 payload adapters (`_adapt_*`) | Per-method transforms | Yes (compat) |
| 39-60 | 22 response shapers (`_shape_*`) | Per-method transforms | Yes (compat) |
| 61 | `_is_ulid(value)` | ULID check | Yes |
| 62 | `_derive_step_name_from_type(spec)` | Step name from spec | **Borderline** — prefix stripping |
| 63 | `_should_derive_step_name(name)` | Name check | Yes |
| 64 | `_expand_step_ulids_to_steps(...)` | ULID→step info | **No — reads YAML directly** |

### jobs.py

| # | Function | Purpose | Should exist? |
|---|----------|---------|---------------|
| 65 | `JobStatus` (enum) | Job states | Yes |
| 66 | `Job` (dataclass) | Job representation | Yes |
| 67 | `Job.to_dict()` | Serialization | Yes |
| 68 | `Job.to_summary_dict()` | Summary serialization | Yes |
| 69 | `JobManager.__init__` | Create executor | Yes |
| 70 | `JobManager.submit(...)` | Submit job | Yes |
| 71 | `JobManager.submit_with_id(...)` | Submit with ULID | Yes |
| 72 | `JobManager._update_last_log_line(...)` | Read log tail | Yes |
| 73 | `JobManager.get_job(id)` | Get job | Yes |
| 74 | `JobManager.get_job_status(id)` | Get status | Yes |
| 75 | `JobManager.get_job_logs(id, ...)` | Read logs | Yes |
| 76 | `JobManager.list_jobs(...)` | Filter/list jobs | Yes |
| 77 | `JobManager.count_by_status()` | Count by status | Yes |
| 78 | `JobManager.cancel_job(id)` | Cancel job | Yes |
| 79 | `JobManager.cleanup_completed(...)` | Evict old jobs | Yes |
| 80 | `JobManager.shutdown(wait)` | Shutdown executor | Yes |

---

## 13. Unnecessary Daemon Work (Phase 2, Step 2.6)

### UW-1: ULID resolution at every RPC boundary

Nearly every RPC handler that takes a calculation/step selector performs ULID resolution (`is_ulid_like()`, `validate_ulid()`) before calling the API. The API itself also does selector resolution internally. This is **double resolution** — the daemon resolves ULIDs to validate them, then the API resolves them again.

**Recommendation:** Let the API handle all resolution. The daemon should pass selectors through unchanged. ULID validation belongs in the API, not the daemon.

### UW-2: Post-write registry rebuilds

Multiple RPC handlers call `_rebuild_registry_after_write()` after mutations. The API should trigger rebuilds automatically after mutations.

**Recommendation:** Make registry rebuild automatic in the API layer after any state mutation.

### UW-3: Cache invalidation scattered across handlers

Many handlers manually call `cache.invalidate()` or `_rebuild_registry_after_write()` after mutations. This is error-prone — miss one and the cache is stale.

**Recommendation:** Centralize cache invalidation. The API could emit "mutation events" that the daemon listens to.

### UW-4: DTO-to-dict conversion

RPC handlers like `list_structures` and `list_calculations` convert DTOs to dicts with `dto.to_dict()`. This is necessary for JSON serialization but could be handled by a generic response serializer.

**Recommendation:** Add a `serialize_response()` helper that automatically converts DTOs and other typed objects to JSON-serializable dicts. Not critical but reduces boilerplate.

### UW-5: Re-fetching after mutations

Several handlers (e.g., `update_step_params`, `add_step_to_calculation`) call the API to mutate, then immediately re-fetch the same data for the response. The API mutation methods could return the updated data.

**Recommendation:** Have API mutation methods return the updated object (many already do). Remove redundant re-fetches.

---

## 14. Cross-Layer Analysis (Phase 3)

### 14.1 API Methods Only Called by Daemon

These API methods are ONLY used by the daemon (never by CLI or internal API code):

| Method | Assessment |
|--------|------------|
| `svc.online_search.*` (all 4) | Daemon-only. **Should be available to Jupyter.** Legitimate API methods. |
| `svc.analysis.get_field3d_grid()` | Daemon-only. Legitimate for GUI. Jupyter could use it. |
| `svc.analysis.get_analysis_snapshot()` | Daemon-only. History replay. Jupyter could use it. |
| `svc.analysis.get_analysis_instances_for_step()` | Daemon-only. Legitimate. |
| `svc.history.pin_analysis()` | Daemon-only. Legitimate for GUI history. |
| `svc.history.can_pin()` | Daemon-only. Pre-check for pinning. |
| `svc.history.get_pin_data()` | Daemon-only. Pin retrieval. |
| `svc.structure.get_vis_data()` | Daemon-only. Could be useful for Jupyter notebooks. |
| `svc.calculation.get_detail()` | Daemon-only. Rich detail view. CLI uses `get` + manual enrichment. |
| `svc.calculation.set_structure()` | Daemon-only. CLI uses `update_steps_structure`. |
| `QMSService.get_settings()` | Daemon-only. |
| `QMSService.get_workflow_service()` | Daemon-only. |

**Assessment:** These are all legitimate API methods that the daemon needs and that Jupyter users should also be able to call. No methods should be removed — the CLI should consider using more of them.

### 14.2 Capability Gaps (Daemon can do, API cannot)

| # | Capability | Daemon implementation | API gap | Severity |
|---|-----------|----------------------|---------|----------|
| 1 | **Preview online structure candidate** | `_handle_structure_get_online_candidate` (~370 lines) | No API method for full candidate preview with visualization | **CRITICAL** |
| 2 | **Import online structure to project** | `_handle_structure_import_online_candidate` (~100 lines) | No API method to save online structure as project resource | **CRITICAL** |
| 3 | **Browse QE parameter metadata** | `_qe_parameter_metadata_internal` (~400 lines) | Partial: `get_engine_parameter_metadata()` exists for generic but QE detail is daemon-only | **HIGH** |
| 4 | **List 3D visualization fixtures** | `_handle_list_wannier_3d_fixtures` (~130 lines) | No API method | **MEDIUM** |
| 5 | **Job management** (status, logs, cancel) | `job_manager.*` calls | `svc.run.cancel()` exists but `list_runs()`/`get_status()`/`get_logs()` don't have daemon-independent equivalents | **MEDIUM** |
| 6 | **Online search session caching** | `OnlineStructureCache` in daemon | Cache management not in API | **LOW** |
| 7 | **DAG diff after registry rebuild** | `_snapshot_dag` + `_diff_dag` | GUI convenience, not needed for Jupyter | **LOW** |

### 14.3 Redundant Conversions / Transformations

| Data path | Redundancy | Location |
|-----------|------------|----------|
| ULID resolution | Daemon validates ULID → API resolves ULID again | Every RPC handler + `svc.calculation.get()` etc. |
| DTO→dict→DTO | Daemon converts DTO to dict for response; compat layer may reshape; GUI deserializes | `list_structures`, `list_calculations` + compat.py shapers |
| Registry rebuild | Daemon triggers rebuild → API operation may also trigger | Multiple mutation handlers |
| Step type gen extraction | compat.py `_derive_step_name_from_type` does prefix stripping; API's `_safe_step_type_gen` uses proper conversion | `compat.py:272` + `service.py:46` |
| Calculation detail | daemon `_handle_get_calculation_detail` resolves ULID → API `get_detail()` resolves again internally | Every get_detail RPC |

---

## 15. Priority-Ordered Recommendations

### P0 — CRITICAL (Do before API freeze)

1. **Create `svc.structure.import_online()` API method** (Gap #2, Misplaced Logic #2)
   - Move daemon's structure import logic to API
   - Without this, Jupyter users cannot complete the online import workflow

2. **Create `svc.online_search.get_candidate_detail()` API method** (Gap #1, Misplaced Logic #1)
   - Move daemon's 370-line candidate preview logic to API
   - Without this, Jupyter users cannot preview online structures

### P1 — HIGH (Do during API freeze sprint)

3. **Move QE metadata browser to API** (Gap #3, Misplaced Logic #3)
   - Enhance `get_engine_parameter_metadata()` to handle QE's full metadata browsing
   - ~400 lines to relocate

4. **Merge duplicate calculation creation** (Opportunity #2)
   - `svc.project.init_calculation()` + `svc.calculation.create()` → single method

5. **Merge duplicate listing** (Opportunity #1)
   - Remove `svc.project.list_calculations()` in favor of `svc.calculation.list()`

6. **Merge Surface A artifact methods** (Opportunities #5 + #6)
   - `list_raw_files` → `list_step_artifacts` with filter
   - `read_raw_file` → `read_step_artifact_text` with defaults

### P2 — MEDIUM (Do during cleanup)

7. **Group pseudo statics into `svc.pseudo`** (Opportunity #8)
8. **Merge add_step variants** (Opportunity #3)
9. **Merge relax structure promotion** (Opportunity #4)
10. **Move QE-specific utils to `api.qe_io`** (Opportunity #22)
11. **Fix compat.py YAML read** (#64 `_expand_step_ulids_to_steps`)
12. **Remove `svc.structure.visualize()` if dead** (Opportunity #7)
13. **Rename `list_runs` for clarity** (Opportunity #17)

### P3 — LOW (Nice-to-have)

14. **Remove QE metadata re-exports from utils** (Opportunity #12)
15. **Flatten resolution helpers** (Opportunity #9)
16. **Auto-trigger registry rebuilds** (UW-2)
17. **Centralize daemon cache invalidation** (UW-3)
18. **Remove double ULID resolution** (UW-1)
19. **Consolidate preset detection RPCs** (RPC-C4)
20. **Plan compat.py sunset** — 1,011 lines of v0 translation that should shrink as GUI catches up

---

## Appendix A: File Size Summary

| File | Lines | Role |
|------|-------|------|
| `src/qmatsuite/api/service.py` | 8,610 | API service class |
| `src/qmatsuite/api/utils.py` | 2,262 | API utility functions |
| `src/qmatsuite/daemon/server.py` | 6,409 | Daemon RPC server |
| `src/qmatsuite/daemon/compat.py` | 1,011 | v0 GUI compat layer |
| `src/qmatsuite/daemon/jobs.py` | 707 | Job manager |
| `src/qmatsuite/cli/main.py` | 5,374 | CLI commands |
| **Total** | **24,373** | |

## Appendix B: Gate Tests Enforcing Architecture

| Gate | What it enforces |
|------|-----------------|
| `test_import_gate.py` | CLI/daemon import only from `qmatsuite.api.*` |
| `test_daemon_kernel_ban.py` | Daemon zero kernel imports (comprehensive) |
| `test_kernel_no_api_import.py` | Kernel does not import from API (Law K0) |
| `test_kernel_no_frontend_import.py` | Kernel does not import from CLI/daemon |
| `test_engine_no_ssot_import.py` | Engines don't import SSOT (Law K6) |
| `test_yaml_write_single_entry.py` | yaml.safe_dump only in yaml_io.py (Law K3) |
| `test_yaml_read_single_entry.py` | YAML reads centralized (Law K7) |
| `test_frontend_no_yaml_write.py` | No direct YAML writes in frontends (Law H9) |
| `test_no_deep_domain_import.py` | Cross-domain via public.py only (Law K2) |
| `test_no_bare_step_type.py` | No bare `step_type` field |
| `test_no_manual_join_split.py` | No manual underscore parsing |
| `test_no_fallbacks.py` | No silent engine fallbacks |
