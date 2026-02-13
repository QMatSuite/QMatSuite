# API Dangling Calls Audit Report

**Generated:** Automated AST-based scan  
**Repository HEAD:** `2f0b076791c2348cb5669138c1dba215ccab2a3d`

---

## A. Inventory: API-like Classes Discovered

### QVService (`quantumvitas._api_legacy.QVService`)

- **Module:** `quantumvitas._api_legacy`
- **Defined at:** `quantumvitas/_api_legacy/QVService.py:229`
- **Public methods:** 215

Methods:
  - `add_step_to_calculation()`
  - `analyze_band()`
  - `analyze_dos()`
  - `analyze_project_pseudo_effects()`
  - `analyze_scf()`
  - `apply_calculation_rename()`
  - `apply_card_overrides_to_qe_input()`
  - `apply_presets_to_step()`
  - `apply_species_overrides_to_qe_input()`
  - `apply_structure_rename()`
  - `build_bonds()`
  - `build_display_atoms()`
  - `build_resource_index()`
  - `build_step_spec_from_qe_input()`
  - `calc_add_step()`
  - `calc_remove_step()`
  - `calc_set_steps()`
  - `calculation_directory()`
  - `calculations_using_structure()`
  - `can_delete_calculation()`
  - `can_delete_structure()`
  - `canonicalize_structure()`
  - `change_calculation_structure()`
  - `check_archives_status()`
  - `collect_slugs()`
  - `compute_io_dir_from_calculation_model()`
  - `compute_store_size()`
  - `configure_calculation()`
  - `configure_project()`
  - `configure_species_map()`
  - `configure_step()`
  - `configure_structure()`
  - `copy_calculation_template()`
  - `copy_structure_template()`
  - `create_blob_store()`
  - `create_default_registry()`
  - `create_demo_project()`
  - `create_online_structure_cache()`
  - `create_precision_advisor()`
  - `create_project_from_snapshot()`
  - `delete_calculation()`
  - `delete_calculation_entry()`
  - `delete_project()`
  - `delete_step()`
  - `delete_step_from_calculation()`
  - `delete_structure()`
  - `detect_context()`
  - `detect_engine_for_calculation()`
  - `detect_presets_from_calculation()`
  - `detect_project_root()`
  - `detect_qe()`
  - `detect_runtime_control_keys()`
  - `detect_workflow_type()`
  - `discover_qe_engines()`
  - `download_all_sssp()`
  - `download_pseudo_by_filename()`
  - `download_pseudo_from_url()`
  - `download_sssp_library()`
  - `ensure_calculation_analysis()`
  - `ensure_relative_path()`
  - `entry_display_name()`
  - `entry_matches()`
  - `export_project_snapshot()`
  - `extract_alat_bohr()`
  - `extract_calculation_selector_from_entry()`
  - `extract_provenance()`
  - `extract_step_selector_from_entry()`
  - `fetch_structure_from_optimade()`
  - `find_band_analysis_files()`
  - `find_calculation_entry()`
  - `find_calculation_raw_dir()`
  - `find_calculation_results_dir()`
  - `find_enclosing_calculation()`
  - `find_path_context_from_pwd()`
  - `find_path_context_ref()`
  - `find_project_root()`
  - `find_quantumvitas_root()`
  - `find_structure_entry()`
  - `generate_kpath()`
  - `generate_qe_input_from_spec()`
  - `generate_qe_input_from_structure()`
  - `generate_resource_id()`
  - `generate_unique_name_and_slug()`
  - `get_band_structure_data()`
  - `get_calculation()`
  - `get_calculation_detail()`
  - `get_calculation_pseudo_mapping()`
  - `get_common_cards()`
  - `get_default_step_params()`
  - `get_display_mode_params_type()`
  - `get_dos_data()`
  - `get_element_color()`
  - `get_element_radius()`
  - `get_environment_info()`
  - `get_journal()`
  - `get_library_status()`
  - `get_preset_catalog()`
  - `get_project_summary()`
  - `get_pseudo_config()`
  - `get_pseudo_default_paths()`
  - `get_pseudo_mapping()`
  - `get_pseudo_options_for_elements()`
  - `get_qe_home()`
  - `get_reference_analysis()`
  - `get_relax_final_structure_preview()`
  - `get_scf_convergence_data()`
  - `get_settings()`
  - `get_step()`
  - `get_step_detail()`
  - `get_step_preset_footprints()`
  - `get_structure()`
  - `get_structure_vis_data()`
  - `get_workflow_service()`
  - `import_pseudo_files()`
  - `import_seed_archives()`
  - `import_step_from_qe_input()`
  - `import_structure()`
  - `import_structure_from_template()`
  - `init_calculation()`
  - `init_project()`
  - `init_pseudo_dirs()`
  - `init_step()`
  - `install_all_sssp_from_seed()`
  - `install_pseudo_archive()`
  - `install_pseudo_library()`
  - `install_sssp_from_seed()`
  - `is_path_like()`
  - `is_pseudo_archive_installed()`
  - `is_resolution_debug_enabled()`
  - `is_ulid_like()`
  - `list_available_gen_steps()`
  - `list_calculation_templates()`
  - `list_calculations()`
  - `list_calculations_data()`
  - `list_demo_projects()`
  - `list_installed_sssp()`
  - `list_pseudo_libraries()`
  - `list_qe_engines()`
  - `list_seed_archives()`
  - `list_step_artifacts()`
  - `list_steps()`
  - `list_structures()`
  - `list_structures_data()`
  - `load_calculation()`
  - `load_calculation_model()`
  - `load_manifest_archives()`
  - `load_project_config()`
  - `load_project_context()`
  - `load_pseudo_config()`
  - `make_structure_selector_resolver_ref()`
  - `match_step_selector()`
  - `materialize_pseudo_file()`
  - `materialize_step_spec()`
  - `meta_from_name()`
  - `move_to_trash()`
  - `needs_alat_preservation()`
  - `parse_bands_gnu()`
  - `parse_bxsf_bandgrid_3d()`
  - `parse_dos_data()`
  - `parse_scf_output()`
  - `parse_volume_artifact()`
  - `parse_xsf_datagrid_3d()`
  - `plot_bands()`
  - `plot_dos()`
  - `plot_scf_convergence()`
  - `preflight_check()`
  - `promote_relax_structure()`
  - `read_step_artifact_text()`
  - `read_structure()`
  - `reduce_formula()`
  - `remove_pseudo_library()`
  - `rename_calculation()`
  - `rename_structure()`
  - `reorder_calculation_steps()`
  - `repair_pseudo_library()`
  - `require_calculation_ref()`
  - `require_project_root()`
  - `require_step_ref()`
  - `require_structure_ref()`
  - `reset_step_params()`
  - `resolve_calculation_for_cli()`
  - `resolve_calculation_ref()`
  - `resolve_precision_context()`
  - `resolve_pseudo_provenance()`
  - `resolve_resource()`
  - `resolve_step_for_cli()`
  - `resolve_step_ref()`
  - `resolve_structure_ref()`
  - `run_calculation()`
  - `run_input_step()`
  - `run_single_step()`
  - `run_step()`
  - `save_calculation()`
  - `save_figure()`
  - `save_project_config()`
  - `save_project_snapshot()`
  - `save_relax_final_structure()`
  - `score_candidate()`
  - `search_legacy_pseudos()`
  - `search_online_structures()`
  - `set_common_card()`
  - `set_pseudo_config()`
  - `set_pseudo_mapping()`
  - `set_qe_engine()`
  - `set_settings()`
  - `slugify()`
  - `update_calculation_species_map()`
  - `update_registry_add_structure()`
  - `update_step_params()`
  - `validate_pseudo_config()`
  - `validate_ulid()`
  - `visualize_structure()`
  - `visualize_structure_direct()`
  - `write_qe_input_file()`
  - `write_structure()`

### QVService (`quantumvitas.api.service.QVService`)

- **Module:** `quantumvitas.api.service`
- **Defined at:** `quantumvitas/api/service/QVService.py:27`
- **Public methods:** 26

Methods:
  - `analysis()`
  - `calculation()`
  - `configure_species_map()`
  - `create_demo_project()`
  - `engine()`
  - `extract_calculation_selector_from_entry()`
  - `generate_kpath()`
  - `get_default_step_params()`
  - `get_project_summary()`
  - `get_settings()`
  - `get_workflow_service()`
  - `history()`
  - `import_structure()`
  - `init_calculation()`
  - `init_project()`
  - `init_step()`
  - `list_calculations_data()`
  - `list_demo_projects()`
  - `list_structures_data()`
  - `project()`
  - `promote_relax_structure()`
  - `run()`
  - `run_calculation()`
  - `run_step()`
  - `save_relax_final_structure()`
  - `structure()`

### QVService (`quantumvitas.api_legacy.QVService`)

- **Module:** `quantumvitas.api_legacy`
- **Defined at:** `quantumvitas/api_legacy/QVService.py:148`
- **Public methods:** 101

Methods:
  - `add_step_to_calculation()`
  - `analyze_band()`
  - `analyze_dos()`
  - `analyze_scf()`
  - `build_resource_index()`
  - `calc_add_step()`
  - `calc_remove_step()`
  - `calc_set_steps()`
  - `can_delete_calculation()`
  - `can_delete_structure()`
  - `change_calculation_structure()`
  - `configure_calculation()`
  - `configure_project()`
  - `configure_species_map()`
  - `configure_step()`
  - `configure_structure()`
  - `create_demo_project()`
  - `create_project_from_snapshot()`
  - `delete_calculation()`
  - `delete_project()`
  - `delete_step()`
  - `delete_step_from_calculation()`
  - `delete_structure()`
  - `detect_context()`
  - `detect_qe()`
  - `discover_qe_engines()`
  - `download_pseudo_by_filename()`
  - `download_pseudo_from_url()`
  - `ensure_calculation_analysis()`
  - `ensure_relative_path()`
  - `export_project_snapshot()`
  - `generate_unique_name_and_slug()`
  - `get_band_structure_data()`
  - `get_calculation()`
  - `get_calculation_detail()`
  - `get_calculation_for_cli()`
  - `get_calculation_pseudo_mapping()`
  - `get_common_cards()`
  - `get_dos_data()`
  - `get_environment_info()`
  - `get_project_summary()`
  - `get_pseudo_config()`
  - `get_pseudo_mapping()`
  - `get_pseudo_options_for_elements()`
  - `get_reference_analysis()`
  - `get_relax_final_structure_preview()`
  - `get_scf_convergence_data()`
  - `get_step()`
  - `get_step_detail()`
  - `get_step_for_cli()`
  - `get_structure()`
  - `get_structure_vis_data()`
  - `import_pseudo_files()`
  - `import_step_from_qe_input()`
  - `import_structure()`
  - `import_structure_from_template()`
  - `init_calculation()`
  - `init_project()`
  - `init_pseudo_dirs()`
  - `init_step()`
  - `is_ulid_like()`
  - `list_available_gen_steps()`
  - `list_calculations()`
  - `list_calculations_data()`
  - `list_demo_projects()`
  - `list_qe_engines()`
  - `list_step_artifacts()`
  - `list_steps()`
  - `list_structures()`
  - `list_structures_data()`
  - `load_project_config()`
  - `load_project_context()`
  - `meta_from_name()`
  - `preflight_check()`
  - `promote_relax_structure()`
  - `read_step_artifact_text()`
  - `rename_calculation()`
  - `rename_structure()`
  - `reorder_calculation_steps()`
  - `require_structure()`
  - `reset_step_params()`
  - `resolve_calculation()`
  - `resolve_pseudo_provenance()`
  - `resolve_step()`
  - `resolve_structure()`
  - `run_calculation()`
  - `run_single_step()`
  - `run_step()`
  - `save_project_snapshot()`
  - `save_relax_final_structure()`
  - `search_legacy_pseudos()`
  - `set_common_card()`
  - `set_pseudo_config()`
  - `set_pseudo_mapping()`
  - `set_qe_engine()`
  - `slugify()`
  - `update_calculation_species_map()`
  - `update_step_params()`
  - `validate_pseudo_config()`
  - `validate_ulid()`
  - `visualize_structure()`

### WorkflowService (`quantumvitas.workflow.templates.WorkflowService`)

- **Module:** `quantumvitas.workflow.templates`
- **Defined at:** `quantumvitas/workflow/templates/WorkflowService.py:141`
- **Public methods:** 5

Methods:
  - `detect_workflow()`
  - `get_template()`
  - `instantiate_workflow()`
  - `list_templates()`
  - `validate_workflow()`

### TestIntegrationWithQVService (`test_analysis_artifacts.TestIntegrationWithQVService`)

- **Module:** `test_analysis_artifacts`
- **Defined at:** `test_analysis_artifacts/TestIntegrationWithQVService.py:356`
- **Public methods:** 1

Methods:
  - `test_get_scf_uses_artifact()`

### FakeWorkflowService (`test_api_service_facade.FakeWorkflowService`)

- **Module:** `test_api_service_facade`
- **Defined at:** `test_api_service_facade/FakeWorkflowService.py:166`
- **Public methods:** 0

Methods:

### TestAPIServiceFacade (`test_api_service_facade.TestAPIServiceFacade`)

- **Module:** `test_api_service_facade`
- **Defined at:** `test_api_service_facade/TestAPIServiceFacade.py:20`
- **Public methods:** 16

Methods:
  - `demo_project()`
  - `test_api_importable()`
  - `test_calculation_get_not_found()`
  - `test_calculation_list_empty()`
  - `test_calculation_list_steps_not_found()`
  - `test_calculation_require_ref_not_found()`
  - `test_calculation_resolve_enclosing_returns_none()`
  - `test_domain_accessors_exist()`
  - `test_get_default_step_params_wrapper()`
  - `test_get_workflow_service_wrapper()`
  - `test_load_project_config()`
  - `test_service_initialization()`
  - `test_service_initialization_fails_for_non_project()`
  - `test_structure_get_not_found()`
  - `test_structure_list_empty()`
  - `test_structure_require_ref_not_found()`

### TestWorkflowService (`test_workflow.TestWorkflowService`)

- **Module:** `test_workflow`
- **Defined at:** `test_workflow/TestWorkflowService.py:156`
- **Public methods:** 7

Methods:
  - `service()`
  - `test_get_template_bands()`
  - `test_get_template_dos()`
  - `test_get_template_scf()`
  - `test_get_template_unknown_returns_none()`
  - `test_list_templates_contains_v0_workflows()`
  - `test_list_templates_not_empty()`

---

## B. Call-site Inventory

### Static Calls (ClassName.method())

#### QVService (`quantumvitas._api_legacy.QVService`)

**Total callsites:** 62

- `Analysis()`: 1 callsite(s)
  - `src/quantumvitas/api/service.py:1155`
- `Calculation()`: 1 callsite(s)
  - `src/quantumvitas/api/service.py:3228`
- `Engine()`: 1 callsite(s)
  - `src/quantumvitas/api/service.py:4394`
- `History()`: 1 callsite(s)
  - `src/quantumvitas/api/service.py:4772`
- `Project()`: 1 callsite(s)
  - `src/quantumvitas/api/service.py:4141`
- `Run()`: 1 callsite(s)
  - `src/quantumvitas/api/service.py:3917`
- `Structure()`: 1 callsite(s)
  - `src/quantumvitas/api/service.py:1703`
- `_build_structure_vis_payload()`: 2 callsite(s)
  - `src/quantumvitas/_api_legacy.py:3894`
  - `src/quantumvitas/api_legacy.py:3439`
- `_detect_calculation_results_dir()`: 6 callsite(s)
  - `src/quantumvitas/_api_legacy.py:2881`
  - `src/quantumvitas/_api_legacy.py:2961`
  - `src/quantumvitas/_api_legacy.py:3090`
  - `src/quantumvitas/api_legacy.py:2426`
  - `src/quantumvitas/api_legacy.py:2506`
  - `src/quantumvitas/api_legacy.py:2635`
- `_detect_prefix_outdir_injection()`: 2 callsite(s)
  - `src/quantumvitas/_api_legacy.py:5474`
  - `src/quantumvitas/api_legacy.py:5019`
- `_preflight_check_and_seed_pseudos()`: 2 callsite(s)
  - `src/quantumvitas/_api_legacy.py:8560`
  - `src/quantumvitas/api_legacy.py:8105`
- `_update_calculation_steps()`: 4 callsite(s)
  - `src/quantumvitas/_api_legacy.py:7148`
  - `src/quantumvitas/_api_legacy.py:7174`
  - `src/quantumvitas/api_legacy.py:6693`
  - `src/quantumvitas/api_legacy.py:6719`
- `calc_add_step()`: 2 callsite(s)
  - `src/quantumvitas/_api_legacy.py:1798`
  - `src/quantumvitas/api_legacy.py:1388`
- `calc_remove_step()`: 2 callsite(s)
  - `src/quantumvitas/_api_legacy.py:1945`
  - `src/quantumvitas/api_legacy.py:1535`
- `calc_set_steps()`: 2 callsite(s)
  - `src/quantumvitas/_api_legacy.py:7323`
  - `src/quantumvitas/api_legacy.py:6868`
- `configure_calculation()`: 2 callsite(s)
  - `src/quantumvitas/_api_legacy.py:5122`
  - `src/quantumvitas/api_legacy.py:4667`
- `configure_structure()`: 2 callsite(s)
  - `src/quantumvitas/_api_legacy.py:5026`
  - `src/quantumvitas/api_legacy.py:4571`
- `export_project_snapshot()`: 2 callsite(s)
  - `src/quantumvitas/_api_legacy.py:1143`
  - `src/quantumvitas/api_legacy.py:733`
- `get_calculation_detail()`: 8 callsite(s)
  - `src/quantumvitas/_api_legacy.py:6997`
  - `src/quantumvitas/_api_legacy.py:7332`
  - `src/quantumvitas/_api_legacy.py:7683`
  - `src/quantumvitas/_api_legacy.py:8100`
  - `src/quantumvitas/api_legacy.py:6542`
  - `src/quantumvitas/api_legacy.py:6877`
  - `src/quantumvitas/api_legacy.py:7228`
  - `src/quantumvitas/api_legacy.py:7645`
- `get_project_summary()`: 2 callsite(s)
  - `src/quantumvitas/_api_legacy.py:8716`
  - `src/quantumvitas/api_legacy.py:8261`
- `get_step_detail()`: 12 callsite(s)
  - `src/quantumvitas/_api_legacy.py:5644`
  - `src/quantumvitas/_api_legacy.py:5781`
  - `src/quantumvitas/_api_legacy.py:5904`
  - `src/quantumvitas/_api_legacy.py:5944`
  - `src/quantumvitas/_api_legacy.py:6170`
  - `src/quantumvitas/_api_legacy.py:7055`
  - `src/quantumvitas/api_legacy.py:5189`
  - `src/quantumvitas/api_legacy.py:5326`
  - `src/quantumvitas/api_legacy.py:5449`
  - `src/quantumvitas/api_legacy.py:5489`
  - ... and 2 more
- `import_structure()`: 5 callsite(s)
  - `src/quantumvitas/_api_legacy.py:5742`
  - `src/quantumvitas/_api_legacy.py:8863`
  - `src/quantumvitas/api/service.py:5771`
  - `src/quantumvitas/api_legacy.py:5287`
  - `src/quantumvitas/api_legacy.py:8408`

#### QVService (`quantumvitas.api_legacy.QVService`)

**Total callsites:** 615

- `_build_structure_vis_payload()`: 14 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:2453`
  - `tests/integration/test_optimade_live.py:507`
  - `tests/integration/test_pipeline_alignment.py:90`
  - `tests/integration/test_pipeline_alignment.py:111`
  - `tests/unit/test_online_project_payload_contract.py:53`
  - `tests/unit/test_online_project_payload_contract.py:61`
  - `tests/unit/test_online_project_payload_contract.py:170`
  - `tests/unit/test_online_structure_supercell.py:432`
  - `tests/unit/test_online_structure_supercell.py:440`
  - `tests/unit/test_online_structure_supercell.py:616`
  - ... and 4 more
- `add_step_to_calculation()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:4190`
- `analyze_project_pseudo_effects()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:4409`
- `analyze_scf()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:4719`
- `apply_card_overrides_to_qe_input()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:1952`
- `apply_presets_to_step()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:3770`
  - `src/quantumvitas/daemon/server.py:3894`
- `apply_species_overrides_to_qe_input()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:1953`
- `can_delete_calculation()`: 2 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:2921`
  - `src/quantumvitas/frontends/daemon/server.py:3033`
- `can_delete_structure()`: 4 callsite(s)
  - `src/quantumvitas/daemon/server.py:2647`
  - `src/quantumvitas/daemon/server.py:2666`
  - `src/quantumvitas/frontends/daemon/server.py:2721`
  - `src/quantumvitas/frontends/daemon/server.py:2740`
- `canonicalize_structure()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:2540`
- `change_calculation_structure()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:4344`
- `check_archives_status()`: 3 callsite(s)
  - `src/quantumvitas/daemon/server.py:1200`
  - `src/quantumvitas/daemon/server.py:1287`
  - `src/quantumvitas/daemon/server.py:1313`
- `compute_io_dir_from_calculation_model()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:5253`
  - `src/quantumvitas/daemon/server.py:5325`
- `compute_store_size()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1148`
- `configure_species_map()`: 4 callsite(s)
  - `src/quantumvitas/cli/main.py:3643`
  - `tests/daemon/test_gui_job_and_step_flows.py:652`
  - `tests/daemon/test_si_bands_calculation_daemon.py:200`
  - `tests/integration/test_qe_relax_real.py:119`
- `configure_step()`: 7 callsite(s)
  - `tools/run_lammps_long_smoke.py:143`
  - `tools/run_lammps_long_smoke.py:339`
  - `tools/run_lammps_long_smoke.py:538`
  - `tools/run_lammps_long_smoke.py:562`
  - `tools/run_lammps_long_smoke.py:746`
  - `tools/run_lammps_long_smoke.py:770`
  - `tools/run_lammps_long_smoke.py:796`
- `create_blob_store()`: 3 callsite(s)
  - `src/quantumvitas/daemon/server.py:5119`
  - `src/quantumvitas/daemon/server.py:5142`
  - `src/quantumvitas/daemon/server.py:5163`
- `create_default_registry()`: 2 callsite(s)
  - `src/quantumvitas/cli/main.py:1536`
  - `src/quantumvitas/cli/main.py:1927`
- `create_demo_project()`: 7 callsite(s)
  - `src/quantumvitas/daemon/server.py:4582`
  - `src/quantumvitas/frontends/daemon/server.py:4678`
  - `tests/unit/test_api_service.py:81`
  - `tests/unit/test_demo_snapshot_restore.py:112`
  - `tests/unit/test_demo_snapshot_restore.py:149`
  - `tests/unit/test_project_snapshot.py:471`
  - `tests/unit/test_project_snapshot.py:501`
- `create_precision_advisor()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:3852`
- `create_project_from_snapshot()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:703`
- `delete_calculation()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:3044`
- `delete_step_from_calculation()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:3667`
- `delete_structure()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:2672`
  - `src/quantumvitas/frontends/daemon/server.py:2746`
- `detect_engine_for_calculation()`: 3 callsite(s)
  - `src/quantumvitas/daemon/server.py:3677`
  - `src/quantumvitas/daemon/server.py:3787`
  - `src/quantumvitas/daemon/server.py:3946`
- `detect_presets_from_calculation()`: 3 callsite(s)
  - `src/quantumvitas/daemon/server.py:3682`
  - `src/quantumvitas/daemon/server.py:3788`
  - `src/quantumvitas/daemon/server.py:3947`
- `detect_qe()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:686`
  - `src/quantumvitas/frontends/daemon/server.py:685`
- `detect_workflow_type()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:3729`
- `discover_qe_engines()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:716`
  - `src/quantumvitas/frontends/daemon/server.py:715`
- `download_all_sssp()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:968`
- `download_pseudo_by_filename()`: 4 callsite(s)
  - `src/quantumvitas/daemon/server.py:3408`
  - `src/quantumvitas/daemon/server.py:3448`
  - `src/quantumvitas/frontends/daemon/server.py:3477`
  - `src/quantumvitas/frontends/daemon/server.py:3517`
- `download_pseudo_from_url()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:3439`
  - `src/quantumvitas/frontends/daemon/server.py:3508`
- `download_sssp_library()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:924`
- `ensure_calculation_analysis()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:4653`
  - `src/quantumvitas/frontends/daemon/server.py:4749`
- `extract_provenance()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:2342`
- `fetch_structure_from_optimade()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:2216`
- `find_band_analysis_files()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:4291`
- `find_calculation_raw_dir()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:4282`
- `find_calculation_results_dir()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:4327`
- `find_path_context_from_pwd()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1997`
- `generate_kpath()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:1251`
- `generate_unique_name_and_slug()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:2549`
- `get_band_structure_data()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:4859`
- `get_calculation_detail()`: 3 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:4130`
  - `src/quantumvitas/frontends/daemon/server.py:4589`
  - `tools/import_tutorial_datasets.py:944`
- `get_calculation_pseudo_mapping()`: 3 callsite(s)
  - `src/quantumvitas/daemon/server.py:4332`
  - `src/quantumvitas/frontends/daemon/server.py:4407`
  - `tools/test_silicon_wannier90_demo_logging.py:85`
- `get_common_cards()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:3266`
- `get_default_step_params()`: 3 callsite(s)
  - `src/quantumvitas/cli/main.py:1270`
  - `tests/unit/test_api_service_facade.py:144`
  - `tests/unit/test_api_service_facade.py:156`
- `get_dos_data()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:4737`
  - `src/quantumvitas/frontends/daemon/server.py:4834`
- `get_environment_info()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:696`
  - `src/quantumvitas/frontends/daemon/server.py:695`
- `get_journal()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:6005`
  - `src/quantumvitas/daemon/server.py:6031`
- `get_library_status()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1046`
- `get_preset_catalog()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:3644`
- `get_project_summary()`: 8 callsite(s)
  - `src/quantumvitas/daemon/server.py:1948`
  - `src/quantumvitas/daemon/server.py:2039`
  - `src/quantumvitas/frontends/daemon/server.py:2006`
  - `src/quantumvitas/frontends/daemon/server.py:2095`
  - `tests/unit/test_demo_snapshot_restore.py:140`
  - `tests/unit/test_qvservice_gui.py:22`
  - `tests/unit/test_qvservice_gui.py:41`
  - `tests/unit/test_qvservice_gui.py:247`
- `get_pseudo_config()`: 15 callsite(s)
  - `src/quantumvitas/daemon/server.py:748`
  - `src/quantumvitas/daemon/server.py:1198`
  - `src/quantumvitas/daemon/server.py:1252`
  - `src/quantumvitas/frontends/daemon/server.py:748`
  - `src/quantumvitas/frontends/daemon/server.py:788`
  - `src/quantumvitas/frontends/daemon/server.py:807`
  - `src/quantumvitas/frontends/daemon/server.py:829`
  - `src/quantumvitas/frontends/daemon/server.py:872`
  - `src/quantumvitas/frontends/daemon/server.py:897`
  - `src/quantumvitas/frontends/daemon/server.py:940`
  - ... and 5 more
- `get_pseudo_mapping()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:3282`
  - `src/quantumvitas/frontends/daemon/server.py:3350`
- `get_pseudo_options_for_elements()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:4524`
- `get_qe_home()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:5188`
- `get_reference_analysis()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:4804`
  - `src/quantumvitas/frontends/daemon/server.py:4901`
- `get_relax_final_structure_preview()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:3516`
  - `src/quantumvitas/frontends/daemon/server.py:3586`
- `get_scf_convergence_data()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:4810`
- `get_settings()`: 4 callsite(s)
  - `src/quantumvitas/daemon/server.py:191`
  - `src/quantumvitas/daemon/server.py:1374`
  - `src/quantumvitas/daemon/server.py:2996`
  - `src/quantumvitas/daemon/server.py:4295`
- `get_step_detail()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:3142`
- `get_step_preset_footprints()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:4004`
- `get_structure_vis_data()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:4784`
- `get_workflow_service()`: 5 callsite(s)
  - `src/quantumvitas/daemon/server.py:6248`
  - `src/quantumvitas/daemon/server.py:6282`
  - `src/quantumvitas/daemon/server.py:6365`
  - `src/quantumvitas/daemon/server.py:6436`
  - `tests/unit/test_api_service_facade.py:178`
- `import_pseudo_files()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:3356`
  - `src/quantumvitas/frontends/daemon/server.py:3425`
- `import_seed_archives()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1012`
- `import_step_from_qe_input()`: 3 callsite(s)
  - `src/quantumvitas/daemon/server.py:4154`
  - `src/quantumvitas/frontends/daemon/server.py:4232`
  - `tools/import_tutorial_datasets.py:562`
- `import_structure()`: 67 callsite(s)
  - `src/quantumvitas/daemon/server.py:2066`
  - `src/quantumvitas/frontends/daemon/server.py:2122`
  - `tests/cli/test_calculation_structure_kind_engine_family.py:35`
  - `tests/daemon/test_gui_calculation_detail.py:50`
  - `tests/daemon/test_gui_calculation_detail.py:58`
  - `tests/daemon/test_gui_job_and_step_flows.py:62`
  - `tests/daemon/test_promote_relax_structure.py:53`
  - `tests/daemon/test_promote_relax_structure.py:108`
  - `tests/daemon/test_promote_relax_structure.py:137`
  - `tests/daemon/test_promote_relax_structure.py:172`
  - ... and 57 more
- `init_calculation()`: 78 callsite(s)
  - `src/quantumvitas/daemon/server.py:2716`
  - `src/quantumvitas/frontends/daemon/server.py:2801`
  - `tests/daemon/test_delete_calculation_daemon.py:30`
  - `tests/daemon/test_gui_calculation_detail.py:70`
  - `tests/daemon/test_gui_job_and_step_flows.py:76`
  - `tests/daemon/test_promote_relax_structure.py:56`
  - `tests/daemon/test_promote_relax_structure.py:111`
  - `tests/daemon/test_promote_relax_structure.py:140`
  - `tests/daemon/test_promote_relax_structure.py:175`
  - `tests/daemon/test_si_bands_calculation_daemon.py:194`
  - ... and 68 more
- `init_project()`: 97 callsite(s)
  - `src/quantumvitas/daemon/server.py:2027`
  - `src/quantumvitas/frontends/daemon/server.py:2083`
  - `tests/cli/test_calculation_structure_kind_engine_family.py:20`
  - `tests/daemon/test_gui_calculation_detail.py:42`
  - `tests/daemon/test_gui_job_and_step_flows.py:55`
  - `tests/daemon/test_online_candidate_handler.py:24`
  - `tests/daemon/test_promote_relax_structure.py:43`
  - `tests/daemon/test_promote_relax_structure.py:98`
  - `tests/daemon/test_promote_relax_structure.py:127`
  - `tests/daemon/test_promote_relax_structure.py:162`
  - ... and 87 more
- `init_pseudo_dirs()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:795`
- `init_step()`: 43 callsite(s)
  - `tests/daemon/test_promote_relax_structure.py:60`
  - `tests/daemon/test_promote_relax_structure.py:112`
  - `tests/daemon/test_promote_relax_structure.py:141`
  - `tests/daemon/test_promote_relax_structure.py:176`
  - `tests/integration/orca/test_orca_project_level.py:99`
  - `tests/integration/test_cp2k_integration.py:90`
  - `tests/integration/test_cp2k_integration.py:150`
  - `tests/integration/test_cp2k_integration.py:235`
  - `tests/integration/test_lammps_long_smoke.py:149`
  - `tests/integration/test_lammps_long_smoke.py:284`
  - ... and 33 more
- `install_all_sssp_from_seed()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:843`
- `install_pseudo_archive()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1304`
- `install_pseudo_library()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1085`
- `install_sssp_from_seed()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:839`
- `is_pseudo_archive_installed()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1281`
- `is_ulid_like()`: 22 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:2905`
  - `src/quantumvitas/frontends/daemon/server.py:2986`
  - `src/quantumvitas/frontends/daemon/server.py:2989`
  - `src/quantumvitas/frontends/daemon/server.py:3098`
  - `src/quantumvitas/frontends/daemon/server.py:3179`
  - `src/quantumvitas/frontends/daemon/server.py:3258`
  - `src/quantumvitas/frontends/daemon/server.py:3302`
  - `src/quantumvitas/frontends/daemon/server.py:3342`
  - `src/quantumvitas/frontends/daemon/server.py:3386`
  - `src/quantumvitas/frontends/daemon/server.py:3545`
  - ... and 12 more
- `list_calculation_templates()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:2692`
- `list_calculations_data()`: 11 callsite(s)
  - `src/quantumvitas/daemon/server.py:1973`
  - `src/quantumvitas/daemon/server.py:2726`
  - `src/quantumvitas/frontends/daemon/server.py:2030`
  - `src/quantumvitas/frontends/daemon/server.py:2811`
  - `tests/daemon/test_gui_calculation_detail.py:108`
  - `tests/daemon/test_gui_calculation_detail.py:164`
  - `tests/daemon/test_gui_calculation_detail.py:279`
  - `tests/daemon/test_gui_calculation_detail.py:325`
  - `tests/unit/test_qvservice_gui.py:92`
  - `tests/unit/test_qvservice_gui.py:102`
  - ... and 1 more
- `list_demo_projects()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:4605`
  - `src/quantumvitas/frontends/daemon/server.py:4701`
- `list_installed_sssp()`: 3 callsite(s)
  - `src/quantumvitas/daemon/server.py:854`
  - `src/quantumvitas/daemon/server.py:934`
  - `src/quantumvitas/daemon/server.py:976`
- `list_pseudo_libraries()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1023`
- `list_qe_engines()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:706`
  - `src/quantumvitas/frontends/daemon/server.py:705`
- `list_seed_archives()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:877`
- `list_step_artifacts()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:4907`
  - `src/quantumvitas/frontends/daemon/server.py:5026`
- `list_structures_data()`: 9 callsite(s)
  - `src/quantumvitas/daemon/server.py:1960`
  - `src/quantumvitas/daemon/server.py:2074`
  - `src/quantumvitas/frontends/daemon/server.py:2016`
  - `src/quantumvitas/frontends/daemon/server.py:2130`
  - `tests/integration/test_relax_promote_e2e.py:171`
  - `tests/integration/test_relax_promote_e2e.py:198`
  - `tests/unit/test_qvservice_gui.py:55`
  - `tests/unit/test_qvservice_gui.py:67`
  - `tests/unit/test_qvservice_gui.py:258`
- `load_calculation()`: 3 callsite(s)
  - `src/quantumvitas/daemon/server.py:5235`
  - `src/quantumvitas/daemon/server.py:5323`
  - `src/quantumvitas/daemon/server.py:5863`
- `load_manifest_archives()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:1199`
  - `src/quantumvitas/daemon/server.py:1264`
- `load_pseudo_config()`: 4 callsite(s)
  - `src/quantumvitas/daemon/server.py:815`
  - `src/quantumvitas/daemon/server.py:871`
  - `src/quantumvitas/daemon/server.py:957`
  - `src/quantumvitas/daemon/server.py:1001`
- `materialize_pseudo_file()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:4434`
- `meta_from_name()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:2559`
- `parse_volume_artifact()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:4884`
  - `src/quantumvitas/daemon/server.py:5105`
- `preflight_check()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:4652`
- `promote_relax_structure()`: 12 callsite(s)
  - `src/quantumvitas/daemon/server.py:3159`
  - `src/quantumvitas/frontends/daemon/server.py:3218`
  - `tests/daemon/test_promote_relax_structure.py:78`
  - `tests/daemon/test_promote_relax_structure.py:116`
  - `tests/daemon/test_promote_relax_structure.py:145`
  - `tests/integration/test_relax_e2e.py:133`
  - `tests/integration/test_relax_e2e.py:170`
  - `tests/integration/test_relax_e2e.py:198`
  - `tests/integration/test_relax_promote_e2e.py:190`
  - `tests/integration/test_relax_promote_e2e.py:229`
  - ... and 2 more
- `read_step_artifact_text()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:4935`
  - `src/quantumvitas/frontends/daemon/server.py:5054`
- `read_structure()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:4512`
- `reduce_formula()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:2223`
- `remove_pseudo_library()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1114`
- `rename_calculation()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:2764`
  - `src/quantumvitas/frontends/daemon/server.py:2849`
- `rename_structure()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:2626`
  - `src/quantumvitas/frontends/daemon/server.py:2700`
- `reorder_calculation_steps()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:4074`
  - `src/quantumvitas/frontends/daemon/server.py:4158`
- `repair_pseudo_library()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1137`
- `reset_step_params()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:3483`
  - `src/quantumvitas/frontends/daemon/server.py:3553`
- `resolve_precision_context()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:3848`
- `resolve_pseudo_provenance()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:1181`
  - `src/quantumvitas/frontends/daemon/server.py:1238`
- `run_calculation()`: 12 callsite(s)
  - `src/quantumvitas/cli/main.py:3997`
  - `tests/integration/orca/test_orca_project_level.py:135`
  - `tests/integration/test_incremental_run.py:810`
  - `tests/integration/test_incremental_run.py:924`
  - `tests/integration/test_incremental_run.py:1008`
  - `tests/integration/test_pyscf_phase3c.py:145`
  - `tests/integration/test_pyscf_phase3c.py:166`
  - `tests/integration/test_pyscf_phase3c.py:182`
  - `tests/integration/test_pyscf_phase3c.py:197`
  - `tests/integration/test_pyscf_phase3c.py:214`
  - ... and 2 more
- `run_input_step()`: 3 callsite(s)
  - `src/quantumvitas/cli/main.py:1881`
  - `src/quantumvitas/cli/main.py:1959`
  - `src/quantumvitas/cli/main.py:5383`
- `run_step()`: 20 callsite(s)
  - `src/quantumvitas/cli/main.py:1744`
  - `tests/integration/orca/test_orca_project_level.py:151`
  - `tests/integration/test_orca_relax_real.py:119`
  - `tests/integration/test_orca_relax_real.py:141`
  - `tests/integration/test_orca_relax_real.py:174`
  - `tests/integration/test_pyscf_phase3c.py:229`
  - `tests/integration/test_pyscf_phase3c.py:311`
  - `tests/integration/test_pyscf_phase3c.py:389`
  - `tests/integration/test_pyscf_relax_real.py:158`
  - `tests/integration/test_pyscf_relax_real.py:210`
  - ... and 10 more
- `save_project_snapshot()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:1421`
- `save_relax_final_structure()`: 4 callsite(s)
  - `src/quantumvitas/daemon/server.py:3549`
  - `src/quantumvitas/frontends/daemon/server.py:3619`
  - `tests/integration/test_relax_structure_save.py:132`
  - `tests/integration/test_relax_structure_save.py:160`
- `score_candidate()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:2224`
- `search_legacy_pseudos()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:3381`
  - `src/quantumvitas/frontends/daemon/server.py:3450`
- `search_online_structures()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:2104`
- `set_common_card()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:3243`
  - `src/quantumvitas/frontends/daemon/server.py:3310`
- `set_pseudo_config()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:762`
  - `src/quantumvitas/frontends/daemon/server.py:763`
- `set_pseudo_mapping()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:3325`
  - `src/quantumvitas/frontends/daemon/server.py:3394`
- `set_qe_engine()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:728`
  - `src/quantumvitas/frontends/daemon/server.py:727`
- `set_settings()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:1363`
- `update_calculation_species_map()`: 2 callsite(s)
  - `src/quantumvitas/daemon/server.py:4371`
  - `src/quantumvitas/frontends/daemon/server.py:4446`
- `update_step_params()`: 1 callsite(s)
  - `src/quantumvitas/frontends/daemon/server.py:3187`
- `validate_pseudo_config()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:781`
- `validate_ulid()`: 7 callsite(s)
  - `src/quantumvitas/daemon/server.py:2911`
  - `src/quantumvitas/daemon/server.py:4328`
  - `src/quantumvitas/frontends/daemon/server.py:3003`
  - `src/quantumvitas/frontends/daemon/server.py:3115`
  - `src/quantumvitas/frontends/daemon/server.py:4125`
  - `src/quantumvitas/frontends/daemon/server.py:4403`
  - `src/quantumvitas/frontends/daemon/server.py:4577`
- `visualize_structure_direct()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:4862`

### Instance Calls (var.method())

#### QVService (`quantumvitas.api.service.QVService`)

**Total callsites:** 48

- `add_step()`: 2 callsite(s)
  - `tests/api/test_calculation_write.py:276` (via `svc`)
  - `tests/api/test_calculation_write.py:387` (via `svc`)
- `cancel()`: 3 callsite(s)
  - `tests/api/test_run_capabilities.py:105` (via `svc`)
  - `tests/api/test_run_capabilities.py:133` (via `svc`)
  - `tests/api/test_run_capabilities.py:169` (via `svc`)
- `create()`: 1 callsite(s)
  - `tests/api/test_calculation_write.py:25` (via `svc`)
- `delete()`: 1 callsite(s)
  - `tests/api/test_calculation_write.py:240` (via `svc`)
- `duplicate()`: 4 callsite(s)
  - `tests/api/test_calculation_write.py:116` (via `svc`)
  - `tests/api/test_calculation_write.py:157` (via `svc`)
  - `tests/api/test_calculation_write.py:189` (via `svc`)
  - `tests/api/test_calculation_write.py:220` (via `svc`)
- `get()`: 2 callsite(s)
  - `tests/api/test_calculation_read.py:25` (via `svc`)
  - `tests/api/test_structure_capabilities.py:61` (via `svc`)
- `get_atoms()`: 1 callsite(s)
  - `tests/api/test_structure_capabilities.py:102` (via `svc`)
- `get_config()`: 1 callsite(s)
  - `tests/api/test_project_capabilities.py:23` (via `svc`)
- `get_effective_params()`: 1 callsite(s)
  - `tests/api/test_calculation_read.py:102` (via `svc`)
- `get_info()`: 1 callsite(s)
  - `tests/api/test_engine_capabilities.py:46` (via `svc`)
- `get_potential_map()`: 1 callsite(s)
  - `tests/api/test_project_capabilities.py:76` (via `svc`)
- `get_property_ref()`: 1 callsite(s)
  - `tests/api/test_analysis_capabilities.py:88` (via `svc`)
- `get_species_map()`: 1 callsite(s)
  - `tests/api/test_project_capabilities.py:59` (via `svc`)
- `get_step()`: 1 callsite(s)
  - `tests/api/test_calculation_read.py:63` (via `svc`)
- `get_summary()`: 1 callsite(s)
  - `tests/api/test_analysis_capabilities.py:45` (via `svc`)
- `list()`: 3 callsite(s)
  - `tests/api/test_calculation_read.py:45` (via `svc`)
  - `tests/api/test_engine_capabilities.py:27` (via `svc`)
  - `tests/api/test_structure_capabilities.py:84` (via `svc`)
- `list_calculations()`: 1 callsite(s)
  - `tests/api/test_project_capabilities.py:93` (via `svc`)
- `list_properties()`: 1 callsite(s)
  - `tests/api/test_analysis_capabilities.py:112` (via `svc`)
- `list_runs()`: 1 callsite(s)
  - `tests/api/test_run_capabilities.py:68` (via `svc`)
- `list_step_types()`: 1 callsite(s)
  - `tests/api/test_engine_capabilities.py:65` (via `svc`)
- `list_steps()`: 1 callsite(s)
  - `tests/api/test_calculation_read.py:84` (via `svc`)
- `load_artifact()`: 6 callsite(s)
  - `tests/api/test_analysis_capabilities.py:158` (via `svc`)
  - `tests/api/test_analysis_capabilities.py:203` (via `svc`)
  - `tests/api/test_analysis_capabilities.py:238` (via `svc`)
  - `tests/api/test_analysis_capabilities.py:256` (via `svc`)
  - `tests/api/test_analysis_capabilities.py:285` (via `svc`)
  - `tests/api/test_analysis_capabilities.py:320` (via `svc`)
- `remove_step()`: 2 callsite(s)
  - `tests/api/test_calculation_write.py:362` (via `svc`)
  - `tests/api/test_calculation_write.py:418` (via `svc`)
- `run_calculation()`: 1 callsite(s)
  - `tests/api/test_run_capabilities.py:30` (via `svc`)
- `run_step()`: 1 callsite(s)
  - `tests/api/test_run_capabilities.py:50` (via `svc`)
- `update_config()`: 1 callsite(s)
  - `tests/api/test_project_capabilities.py:41` (via `svc`)
- `update_meta()`: 1 callsite(s)
  - `tests/api/test_calculation_write.py:44` (via `svc`)
- `update_step_params()`: 1 callsite(s)
  - `tests/api/test_calculation_write.py:62` (via `svc`)
- `validate_installation()`: 5 callsite(s)
  - `tests/api/test_engine_capabilities.py:83` (via `svc`)
  - `tests/api/test_engine_capabilities.py:106` (via `svc`)
  - `tests/api/test_engine_capabilities.py:140` (via `svc`)
  - `tests/api/test_engine_capabilities.py:161` (via `svc`)
  - `tests/api/test_engine_capabilities.py:181` (via `svc`)

#### QVService (`quantumvitas.api_legacy.QVService`)

**Total callsites:** 97

- `add_step()`: 31 callsite(s)
  - `tests/daemon/test_gui_calculation_detail.py:81` (via `svc`)
  - `tests/daemon/test_gui_calculation_detail.py:85` (via `svc`)
  - `tests/daemon/test_gui_calculation_detail.py:172` (via `svc`)
  - `tests/daemon/test_gui_calculation_detail.py:176` (via `svc`)
  - `tests/daemon/test_gui_job_and_step_flows.py:87` (via `svc`)
  - `tests/daemon/test_si_bands_calculation_daemon.py:210` (via `svc`)
  - `tests/daemon/test_si_bands_calculation_daemon.py:246` (via `svc`)
  - `tests/daemon/test_si_bands_calculation_daemon.py:283` (via `svc`)
  - `tests/daemon/test_si_bands_calculation_daemon.py:328` (via `svc`)
  - `tests/daemon/test_update_step_params_persistence.py:68` (via `svc`)
  - ... and 21 more
- `analyze_band()`: 2 callsite(s)
  - `src/quantumvitas/cli/main.py:4569` (via `svc`)
  - `tests/daemon/test_si_bands_calculation_daemon.py:459` (via `svc`)
- `analyze_dos()`: 1 callsite(s)
  - `src/quantumvitas/cli/main.py:4656` (via `svc`)
- `can_pin()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:6164` (via `svc`)
- `delete()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:6235` (via `svc`)
- `get()`: 4 callsite(s)
  - `src/quantumvitas/cli/main.py:5293` (via `svc`)
  - `tests/unit/test_api_service_facade.py:95` (via `svc`)
  - `tests/unit/test_api_service_facade.py:118` (via `svc`)
  - `tests/unit/test_calculation_ulid_contracts.py:75` (via `svc`)
- `get_band_structure_data()`: 4 callsite(s)
  - `tests/unit/test_api_get_band_structure_data.py:156` (via `svc`)
  - `tests/unit/test_api_get_band_structure_data.py:220` (via `svc`)
  - `tests/unit/test_api_get_band_structure_data.py:253` (via `svc`)
  - `tests/unit/test_api_get_band_structure_data.py:270` (via `svc`)
- `get_common_cards()`: 1 callsite(s)
  - `tests/daemon/test_get_common_cards.py:123` (via `svc`)
- `get_config()`: 2 callsite(s)
  - `src/quantumvitas/cli/main.py:5281` (via `svc`)
  - `tests/unit/test_api_service_facade.py:70` (via `svc`)
- `get_detail()`: 1 callsite(s)
  - `tests/daemon/test_gui_calculation_detail.py:143` (via `svc`)
- `get_latest_run_for_step()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:6210` (via `svc`)
- `get_pin_data()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:6188` (via `svc`)
- `get_run_revision()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:6080` (via `svc`)
- `get_scf_convergence_data()`: 1 callsite(s)
  - `tests/unit/test_analysis_artifacts.py:395` (via `svc`)
- `get_step()`: 1 callsite(s)
  - `tests/unit/test_calculation_ulid_contracts.py:138` (via `svc`)
- `get_timeline()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:6062` (via `svc`)
- `get_vis_data()`: 7 callsite(s)
  - `tests/unit/test_qvservice_gui.py:129` (via `svc`)
  - `tests/unit/test_qvservice_gui.py:172` (via `svc`)
  - `tests/unit/test_qvservice_gui.py:173` (via `svc`)
  - `tests/unit/test_qvservice_gui.py:184` (via `svc`)
  - `tests/unit/test_qvservice_gui.py:190` (via `svc`)
  - `tests/unit/test_qvservice_gui.py:236` (via `svc`)
  - `tests/unit/test_qvservice_gui.py:280` (via `svc`)
- `list()`: 2 callsite(s)
  - `tests/unit/test_api_service_facade.py:87` (via `svc`)
  - `tests/unit/test_api_service_facade.py:110` (via `svc`)
- `list_runs()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:6100` (via `svc`)
- `list_steps()`: 1 callsite(s)
  - `tests/unit/test_api_service_facade.py:130` (via `svc`)
- `pin_analysis()`: 1 callsite(s)
  - `src/quantumvitas/daemon/server.py:6137` (via `svc`)
- `preflight()`: 2 callsite(s)
  - `tests/daemon/test_qe_detection.py:68` (via `svc`)
  - `tests/daemon/test_qe_detection.py:121` (via `svc`)
- `require_ref()`: 4 callsite(s)
  - `src/quantumvitas/cli/main.py:5301` (via `svc`)
  - `src/quantumvitas/cli/main.py:5353` (via `svc`)
  - `tests/unit/test_api_service_facade.py:101` (via `svc`)
  - `tests/unit/test_api_service_facade.py:124` (via `svc`)
- `resolve_enclosing_path()`: 1 callsite(s)
  - `tests/unit/test_api_service_facade.py:135` (via `svc`)
- `update_step_params()`: 24 callsite(s)
  - `tests/daemon/test_si_bands_calculation_daemon.py:217` (via `svc`)
  - `tests/daemon/test_si_bands_calculation_daemon.py:253` (via `svc`)
  - `tests/daemon/test_si_bands_calculation_daemon.py:299` (via `svc`)
  - `tests/daemon/test_si_bands_calculation_daemon.py:334` (via `svc`)
  - `tests/integration/test_cp2k_integration.py:99` (via `svc`)
  - `tests/integration/test_cp2k_integration.py:159` (via `svc`)
  - `tests/integration/test_cp2k_integration.py:244` (via `svc`)
  - `tests/integration/test_lammps_chain.py:108` (via `svc`)
  - `tests/integration/test_lammps_chain.py:132` (via `svc`)
  - `tests/integration/test_lammps_chain.py:174` (via `svc`)
  - ... and 14 more

---

## C. Dangling Calls

A call is 'dangling' if the method is not defined on the resolved class.

### Dangling Static Calls

#### `quantumvitas._api_legacy.QVService.Analysis()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `Analysis`
**Callsites:** 1

File:line references:
- `src/quantumvitas/api/service.py:1155` (in `analysis`)

**Note:** Similar methods exist: `ensure_calculation_analysis()`, `find_band_analysis_files()`, `get_reference_analysis()`

#### `quantumvitas._api_legacy.QVService.Calculation()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `Calculation`
**Callsites:** 1

File:line references:
- `src/quantumvitas/api/service.py:3228` (in `calculation`)

**Note:** Similar methods exist: `add_step_to_calculation()`, `apply_calculation_rename()`, `calculation_directory()`, `calculations_using_structure()`, `can_delete_calculation()`

#### `quantumvitas._api_legacy.QVService.Engine()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `Engine`
**Callsites:** 1

File:line references:
- `src/quantumvitas/api/service.py:4394` (in `engine`)

**Note:** Similar methods exist: `detect_engine_for_calculation()`, `discover_qe_engines()`, `list_qe_engines()`, `set_qe_engine()`

#### `quantumvitas._api_legacy.QVService.History()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `History`
**Callsites:** 1

File:line references:
- `src/quantumvitas/api/service.py:4772` (in `history`)


#### `quantumvitas._api_legacy.QVService.Project()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `Project`
**Callsites:** 1

File:line references:
- `src/quantumvitas/api/service.py:4141` (in `project`)

**Note:** Similar methods exist: `analyze_project_pseudo_effects()`, `configure_project()`, `create_demo_project()`, `create_project_from_snapshot()`, `delete_project()`

#### `quantumvitas._api_legacy.QVService.Run()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `Run`
**Callsites:** 1

File:line references:
- `src/quantumvitas/api/service.py:3917` (in `run`)

**Note:** Similar methods exist: `detect_runtime_control_keys()`, `run_calculation()`, `run_input_step()`, `run_single_step()`, `run_step()`

#### `quantumvitas._api_legacy.QVService.Structure()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `Structure`
**Callsites:** 1

File:line references:
- `src/quantumvitas/api/service.py:1703` (in `structure`)

**Note:** Similar methods exist: `apply_structure_rename()`, `calculations_using_structure()`, `can_delete_structure()`, `canonicalize_structure()`, `change_calculation_structure()`

#### `quantumvitas._api_legacy.QVService._build_structure_vis_payload()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `_build_structure_vis_payload`
**Callsites:** 2

File:line references:
- `src/quantumvitas/_api_legacy.py:3894` (in `get_structure_vis_data`)
- `src/quantumvitas/api_legacy.py:3439` (in `get_structure_vis_data`)


#### `quantumvitas._api_legacy.QVService._detect_calculation_results_dir()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `_detect_calculation_results_dir`
**Callsites:** 6

File:line references:
- `src/quantumvitas/_api_legacy.py:2881` (in `analyze_scf`)
- `src/quantumvitas/_api_legacy.py:2961` (in `analyze_dos`)
- `src/quantumvitas/_api_legacy.py:3090` (in `analyze_band`)
- `src/quantumvitas/api_legacy.py:2426` (in `analyze_scf`)
- `src/quantumvitas/api_legacy.py:2506` (in `analyze_dos`)
- `src/quantumvitas/api_legacy.py:2635` (in `analyze_band`)


#### `quantumvitas._api_legacy.QVService._detect_prefix_outdir_injection()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `_detect_prefix_outdir_injection`
**Callsites:** 2

File:line references:
- `src/quantumvitas/_api_legacy.py:5474` (in `get_step_detail`)
- `src/quantumvitas/api_legacy.py:5019` (in `get_step_detail`)


#### `quantumvitas._api_legacy.QVService._preflight_check_and_seed_pseudos()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `_preflight_check_and_seed_pseudos`
**Callsites:** 2

File:line references:
- `src/quantumvitas/_api_legacy.py:8560` (in `preflight_check`)
- `src/quantumvitas/api_legacy.py:8105` (in `preflight_check`)

**Note:** Similar methods exist: `preflight_check()`

#### `quantumvitas._api_legacy.QVService._update_calculation_steps()`

**Class:** `quantumvitas._api_legacy.QVService`
**Method:** `_update_calculation_steps`
**Callsites:** 4

File:line references:
- `src/quantumvitas/_api_legacy.py:7148` (in `calc_add_step`)
- `src/quantumvitas/_api_legacy.py:7174` (in `calc_remove_step`)
- `src/quantumvitas/api_legacy.py:6693` (in `calc_add_step`)
- `src/quantumvitas/api_legacy.py:6719` (in `calc_remove_step`)


#### `quantumvitas.api_legacy.QVService._build_structure_vis_payload()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `_build_structure_vis_payload`
**Callsites:** 14

File:line references:
- `src/quantumvitas/frontends/daemon/server.py:2453` (in `_handle_structure_get_online_candidate`)
- `tests/integration/test_optimade_live.py:507` (in `test_optimade_live_viewer_payload_builder`)
- `tests/integration/test_pipeline_alignment.py:90` (in `test_online_vs_project_pipeline_bit_aligned`)
- `tests/integration/test_pipeline_alignment.py:111` (in `test_online_vs_project_pipeline_bit_aligned`)
- `tests/unit/test_online_project_payload_contract.py:53` (in `test_online_project_payload_contract_identical`)
- `tests/unit/test_online_project_payload_contract.py:61` (in `test_online_project_payload_contract_identical`)
- `tests/unit/test_online_project_payload_contract.py:170` (in `test_payload_contract_atoms_contains_all_display_atoms`)
- `tests/unit/test_online_structure_supercell.py:432` (in `test_online_project_shared_pipeline`)
- `tests/unit/test_online_structure_supercell.py:440` (in `test_online_project_shared_pipeline`)
- `tests/unit/test_online_structure_supercell.py:616` (in `test_online_vs_project_pipeline_identical`)
- `tests/unit/test_online_structure_supercell.py:624` (in `test_online_vs_project_pipeline_identical`)
- `tests/unit/test_optimade_offline.py:100` (in `test_optimade_online_pipeline_payload_contract`)
- `tests/unit/test_optimade_offline.py:160` (in `test_optimade_vs_project_same_structure_identical_payload`)
- `tests/unit/test_optimade_offline.py:168` (in `test_optimade_vs_project_same_structure_identical_payload`)


#### `quantumvitas.api_legacy.QVService.analyze_project_pseudo_effects()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `analyze_project_pseudo_effects`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:4409` (in `_handle_analyze_project_pseudo_effects`)


#### `quantumvitas.api_legacy.QVService.apply_card_overrides_to_qe_input()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `apply_card_overrides_to_qe_input`
**Callsites:** 1

File:line references:
- `src/quantumvitas/cli/main.py:1952` (in `run_structure_command`)


#### `quantumvitas.api_legacy.QVService.apply_presets_to_step()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `apply_presets_to_step`
**Callsites:** 2

File:line references:
- `src/quantumvitas/daemon/server.py:3770` (in `_handle_apply_presets_to_step`)
- `src/quantumvitas/daemon/server.py:3894` (in `_handle_apply_presets_to_calculation`)


#### `quantumvitas.api_legacy.QVService.apply_species_overrides_to_qe_input()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `apply_species_overrides_to_qe_input`
**Callsites:** 1

File:line references:
- `src/quantumvitas/cli/main.py:1953` (in `run_structure_command`)


#### `quantumvitas.api_legacy.QVService.canonicalize_structure()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `canonicalize_structure`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:2540` (in `_handle_structure_import_online_candidate`)


#### `quantumvitas.api_legacy.QVService.check_archives_status()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `check_archives_status`
**Callsites:** 3

File:line references:
- `src/quantumvitas/daemon/server.py:1200` (in `_handle_list_pseudo_archives_status`)
- `src/quantumvitas/daemon/server.py:1287` (in `_handle_install_pseudo_archive`)
- `src/quantumvitas/daemon/server.py:1313` (in `_handle_install_pseudo_archive`)


#### `quantumvitas.api_legacy.QVService.compute_io_dir_from_calculation_model()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `compute_io_dir_from_calculation_model`
**Callsites:** 2

File:line references:
- `src/quantumvitas/daemon/server.py:5253` (in `_handle_run_calculation`)
- `src/quantumvitas/daemon/server.py:5325` (in `_handle_run_step`)


#### `quantumvitas.api_legacy.QVService.compute_store_size()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `compute_store_size`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1148` (in `_handle_compute_store_size`)


#### `quantumvitas.api_legacy.QVService.create_blob_store()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `create_blob_store`
**Callsites:** 3

File:line references:
- `src/quantumvitas/daemon/server.py:5119` (in `_handle_compile_fixture_volume`)
- `src/quantumvitas/daemon/server.py:5142` (in `_handle_compile_fixture_volume`)
- `src/quantumvitas/daemon/server.py:5163` (in `_handle_compile_fixture_volume`)


#### `quantumvitas.api_legacy.QVService.create_default_registry()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `create_default_registry`
**Callsites:** 2

File:line references:
- `src/quantumvitas/cli/main.py:1536` (in `detect_qe`)
- `src/quantumvitas/cli/main.py:1927` (in `run_structure_command`)


#### `quantumvitas.api_legacy.QVService.create_precision_advisor()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `create_precision_advisor`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:3852` (in `_handle_apply_presets_to_calculation`)


#### `quantumvitas.api_legacy.QVService.detect_engine_for_calculation()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `detect_engine_for_calculation`
**Callsites:** 3

File:line references:
- `src/quantumvitas/daemon/server.py:3677` (in `_handle_detect_presets`)
- `src/quantumvitas/daemon/server.py:3787` (in `_handle_apply_presets_to_step`)
- `src/quantumvitas/daemon/server.py:3946` (in `_handle_apply_presets_to_calculation`)


#### `quantumvitas.api_legacy.QVService.detect_presets_from_calculation()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `detect_presets_from_calculation`
**Callsites:** 3

File:line references:
- `src/quantumvitas/daemon/server.py:3682` (in `_handle_detect_presets`)
- `src/quantumvitas/daemon/server.py:3788` (in `_handle_apply_presets_to_step`)
- `src/quantumvitas/daemon/server.py:3947` (in `_handle_apply_presets_to_calculation`)


#### `quantumvitas.api_legacy.QVService.detect_workflow_type()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `detect_workflow_type`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:3729` (in `_handle_detect_workflow`)


#### `quantumvitas.api_legacy.QVService.download_all_sssp()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `download_all_sssp`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:968` (in `_handle_download_all_sssp`)


#### `quantumvitas.api_legacy.QVService.download_sssp_library()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `download_sssp_library`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:924` (in `_handle_download_sssp_library`)


#### `quantumvitas.api_legacy.QVService.extract_provenance()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `extract_provenance`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:2342` (in `_handle_structure_get_online_candidate`)


#### `quantumvitas.api_legacy.QVService.fetch_structure_from_optimade()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `fetch_structure_from_optimade`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:2216` (in `_handle_structure_get_online_candidate`)


#### `quantumvitas.api_legacy.QVService.find_band_analysis_files()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `find_band_analysis_files`
**Callsites:** 1

File:line references:
- `src/quantumvitas/cli/main.py:4291` (in `analyze_output_command`)


#### `quantumvitas.api_legacy.QVService.find_calculation_raw_dir()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `find_calculation_raw_dir`
**Callsites:** 1

File:line references:
- `src/quantumvitas/cli/main.py:4282` (in `analyze_output_command`)


#### `quantumvitas.api_legacy.QVService.find_calculation_results_dir()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `find_calculation_results_dir`
**Callsites:** 1

File:line references:
- `src/quantumvitas/cli/main.py:4327` (in `analyze_output_command`)


#### `quantumvitas.api_legacy.QVService.find_path_context_from_pwd()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `find_path_context_from_pwd`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1997` (in `_handle_find_project_root`)


#### `quantumvitas.api_legacy.QVService.generate_kpath()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `generate_kpath`
**Callsites:** 1

File:line references:
- `src/quantumvitas/cli/main.py:1251` (in `init_step_command`)


#### `quantumvitas.api_legacy.QVService.get_default_step_params()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_default_step_params`
**Callsites:** 3

File:line references:
- `src/quantumvitas/cli/main.py:1270` (in `init_step_command`)
- `tests/unit/test_api_service_facade.py:144` (in `test_get_default_step_params_wrapper`)
- `tests/unit/test_api_service_facade.py:156` (in `test_get_default_step_params_wrapper`)


#### `quantumvitas.api_legacy.QVService.get_journal()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_journal`
**Callsites:** 2

File:line references:
- `src/quantumvitas/daemon/server.py:6005` (in `_handle_list_journal_entries`)
- `src/quantumvitas/daemon/server.py:6031` (in `_handle_get_journal_entry`)


#### `quantumvitas.api_legacy.QVService.get_library_status()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_library_status`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1046` (in `_handle_get_library_status`)


#### `quantumvitas.api_legacy.QVService.get_preset_catalog()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_preset_catalog`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:3644` (in `_handle_get_preset_catalog`)


#### `quantumvitas.api_legacy.QVService.get_qe_home()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_qe_home`
**Callsites:** 1

File:line references:
- `src/quantumvitas/cli/main.py:5188` (in `_collect_qe_detection_info`)


#### `quantumvitas.api_legacy.QVService.get_settings()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_settings`
**Callsites:** 4

File:line references:
- `src/quantumvitas/daemon/server.py:191` (in `__init__`)
- `src/quantumvitas/daemon/server.py:1374` (in `_handle_get_debug_resolution`)
- `src/quantumvitas/daemon/server.py:2996` (in `_handle_get_step_detail`)
- `src/quantumvitas/daemon/server.py:4295` (in `_handle_get_calculation_pseudo_mapping`)


#### `quantumvitas.api_legacy.QVService.get_step_preset_footprints()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_step_preset_footprints`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:4004` (in `_handle_get_step_preset_footprints`)

**Note:** Similar methods exist: `get_step()`

#### `quantumvitas.api_legacy.QVService.get_workflow_service()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_workflow_service`
**Callsites:** 5

File:line references:
- `src/quantumvitas/daemon/server.py:6248` (in `_handle_list_workflow_templates`)
- `src/quantumvitas/daemon/server.py:6282` (in `_handle_detect_workflow`)
- `src/quantumvitas/daemon/server.py:6365` (in `_handle_detect_workflow_for_calculation`)
- `src/quantumvitas/daemon/server.py:6436` (in `_handle_instantiate_workflow`)
- `tests/unit/test_api_service_facade.py:178` (in `test_get_workflow_service_wrapper`)


#### `quantumvitas.api_legacy.QVService.import_seed_archives()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `import_seed_archives`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1012` (in `_handle_import_seed_archives`)


#### `quantumvitas.api_legacy.QVService.install_all_sssp_from_seed()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `install_all_sssp_from_seed`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:843` (in `_handle_install_seed_to_store`)


#### `quantumvitas.api_legacy.QVService.install_pseudo_archive()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `install_pseudo_archive`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1304` (in `_handle_install_pseudo_archive`)


#### `quantumvitas.api_legacy.QVService.install_pseudo_library()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `install_pseudo_library`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1085` (in `_handle_install_library`)


#### `quantumvitas.api_legacy.QVService.install_sssp_from_seed()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `install_sssp_from_seed`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:839` (in `_handle_install_seed_to_store`)


#### `quantumvitas.api_legacy.QVService.is_pseudo_archive_installed()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `is_pseudo_archive_installed`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1281` (in `_handle_install_pseudo_archive`)


#### `quantumvitas.api_legacy.QVService.list_calculation_templates()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `list_calculation_templates`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:2692` (in `_handle_list_calculation_templates`)


#### `quantumvitas.api_legacy.QVService.list_installed_sssp()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `list_installed_sssp`
**Callsites:** 3

File:line references:
- `src/quantumvitas/daemon/server.py:854` (in `_handle_list_installed_sssp`)
- `src/quantumvitas/daemon/server.py:934` (in `_handle_download_sssp_library`)
- `src/quantumvitas/daemon/server.py:976` (in `_handle_download_all_sssp`)


#### `quantumvitas.api_legacy.QVService.list_pseudo_libraries()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `list_pseudo_libraries`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1023` (in `_handle_list_libraries`)


#### `quantumvitas.api_legacy.QVService.list_seed_archives()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `list_seed_archives`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:877` (in `_handle_list_seed_archives`)


#### `quantumvitas.api_legacy.QVService.load_calculation()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `load_calculation`
**Callsites:** 3

File:line references:
- `src/quantumvitas/daemon/server.py:5235` (in `_handle_run_calculation`)
- `src/quantumvitas/daemon/server.py:5323` (in `_handle_run_step`)
- `src/quantumvitas/daemon/server.py:5863` (in `_snapshot_dag`)


#### `quantumvitas.api_legacy.QVService.load_manifest_archives()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `load_manifest_archives`
**Callsites:** 2

File:line references:
- `src/quantumvitas/daemon/server.py:1199` (in `_handle_list_pseudo_archives_status`)
- `src/quantumvitas/daemon/server.py:1264` (in `_handle_install_pseudo_archive`)


#### `quantumvitas.api_legacy.QVService.load_pseudo_config()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `load_pseudo_config`
**Callsites:** 4

File:line references:
- `src/quantumvitas/daemon/server.py:815` (in `_handle_install_seed_to_store`)
- `src/quantumvitas/daemon/server.py:871` (in `_handle_list_seed_archives`)
- `src/quantumvitas/daemon/server.py:957` (in `_handle_download_all_sssp`)
- `src/quantumvitas/daemon/server.py:1001` (in `_handle_import_seed_archives`)


#### `quantumvitas.api_legacy.QVService.materialize_pseudo_file()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `materialize_pseudo_file`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:4434` (in `_handle_materialize_pseudo_file`)


#### `quantumvitas.api_legacy.QVService.parse_volume_artifact()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `parse_volume_artifact`
**Callsites:** 2

File:line references:
- `src/quantumvitas/daemon/server.py:4884` (in `_handle_compile_fixture_volume`)
- `src/quantumvitas/daemon/server.py:5105` (in `_handle_compile_fixture_volume`)


#### `quantumvitas.api_legacy.QVService.read_structure()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `read_structure`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:4512` (in `_handle_get_pseudo_options_for_calculation`)


#### `quantumvitas.api_legacy.QVService.reduce_formula()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `reduce_formula`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:2223` (in `_handle_structure_get_online_candidate`)


#### `quantumvitas.api_legacy.QVService.remove_pseudo_library()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `remove_pseudo_library`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1114` (in `_handle_remove_library`)


#### `quantumvitas.api_legacy.QVService.repair_pseudo_library()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `repair_pseudo_library`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1137` (in `_handle_repair_library`)


#### `quantumvitas.api_legacy.QVService.resolve_precision_context()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `resolve_precision_context`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:3848` (in `_handle_apply_presets_to_calculation`)


#### `quantumvitas.api_legacy.QVService.run_input_step()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `run_input_step`
**Callsites:** 3

File:line references:
- `src/quantumvitas/cli/main.py:1881` (in `_run_standalone_step`)
- `src/quantumvitas/cli/main.py:1959` (in `run_structure_command`)
- `src/quantumvitas/cli/main.py:5383` (in `_execute_step_spec`)


#### `quantumvitas.api_legacy.QVService.score_candidate()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `score_candidate`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:2224` (in `_handle_structure_get_online_candidate`)


#### `quantumvitas.api_legacy.QVService.search_online_structures()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `search_online_structures`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:2104` (in `_handle_structure_search_online`)


#### `quantumvitas.api_legacy.QVService.set_settings()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `set_settings`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:1363` (in `_handle_set_debug_resolution`)


#### `quantumvitas.api_legacy.QVService.visualize_structure_direct()`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `visualize_structure_direct`
**Callsites:** 1

File:line references:
- `src/quantumvitas/cli/main.py:4862` (in `analyze_structure_command`)

**Note:** Similar methods exist: `visualize_structure()`

### Dangling Instance Calls

#### `add_step()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `add_step`
**Callsites:** 2

File:line references:
- `tests/api/test_calculation_write.py:276` (via `svc`) (in `test_add_step_persists_and_returns_step_dto`)
- `tests/api/test_calculation_write.py:387` (via `svc`) (in `test_add_step_unknown_calc_raises_not_found`)


#### `cancel()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `cancel`
**Callsites:** 3

File:line references:
- `tests/api/test_run_capabilities.py:105` (via `svc`) (in `test_cancel_happy_path`)
- `tests/api/test_run_capabilities.py:133` (via `svc`) (in `test_cancel_not_found`)
- `tests/api/test_run_capabilities.py:169` (via `svc`) (in `test_cancel_json_serializable`)


#### `create()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `create`
**Callsites:** 1

File:line references:
- `tests/api/test_calculation_write.py:25` (via `svc`) (in `test_calculation_create_returns_dto`)

**Note:** Similar methods exist: `create_demo_project()`

#### `delete()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `delete`
**Callsites:** 1

File:line references:
- `tests/api/test_calculation_write.py:240` (via `svc`) (in `test_calculation_delete_returns_none`)


#### `duplicate()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `duplicate`
**Callsites:** 4

File:line references:
- `tests/api/test_calculation_write.py:116` (via `svc`) (in `test_duplicate_calculation_happy_path`)
- `tests/api/test_calculation_write.py:157` (via `svc`) (in `test_duplicate_unknown_selector_raises_not_found`)
- `tests/api/test_calculation_write.py:189` (via `svc`) (in `test_duplicate_slug_conflict_raises_conflict`)
- `tests/api/test_calculation_write.py:220` (via `svc`) (in `test_duplicate_with_custom_slug`)


#### `get()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `get`
**Callsites:** 2

File:line references:
- `tests/api/test_calculation_read.py:25` (via `svc`) (in `test_calculation_get_returns_dto`)
- `tests/api/test_structure_capabilities.py:61` (via `svc`) (in `test_structure_dto_no_positions`)

**Note:** Similar methods exist: `get_default_step_params()`, `get_project_summary()`, `get_settings()`, `get_workflow_service()`

#### `get_atoms()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `get_atoms`
**Callsites:** 1

File:line references:
- `tests/api/test_structure_capabilities.py:102` (via `svc`) (in `test_structure_get_atoms_returns_full_data`)


#### `get_config()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `get_config`
**Callsites:** 1

File:line references:
- `tests/api/test_project_capabilities.py:23` (via `svc`) (in `test_project_get_config_returns_dict`)


#### `get_effective_params()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `get_effective_params`
**Callsites:** 1

File:line references:
- `tests/api/test_calculation_read.py:102` (via `svc`) (in `test_calculation_get_effective_params_returns_dict`)


#### `get_info()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `get_info`
**Callsites:** 1

File:line references:
- `tests/api/test_engine_capabilities.py:46` (via `svc`) (in `test_engine_get_info_returns_dict`)


#### `get_potential_map()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `get_potential_map`
**Callsites:** 1

File:line references:
- `tests/api/test_project_capabilities.py:76` (via `svc`) (in `test_project_get_potential_map_returns_dict`)


#### `get_property_ref()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `get_property_ref`
**Callsites:** 1

File:line references:
- `tests/api/test_analysis_capabilities.py:88` (via `svc`) (in `test_get_property_ref_no_embedded_arrays`)


#### `get_species_map()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `get_species_map`
**Callsites:** 1

File:line references:
- `tests/api/test_project_capabilities.py:59` (via `svc`) (in `test_project_get_species_map_returns_dict`)


#### `get_step()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `get_step`
**Callsites:** 1

File:line references:
- `tests/api/test_calculation_read.py:63` (via `svc`) (in `test_calculation_get_step_returns_dto`)


#### `get_summary()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `get_summary`
**Callsites:** 1

File:line references:
- `tests/api/test_analysis_capabilities.py:45` (via `svc`) (in `test_get_summary_returns_dto`)


#### `list()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `list`
**Callsites:** 3

File:line references:
- `tests/api/test_calculation_read.py:45` (via `svc`) (in `test_calculation_list_returns_dtos`)
- `tests/api/test_engine_capabilities.py:27` (via `svc`) (in `test_engine_list_returns_list`)
- `tests/api/test_structure_capabilities.py:84` (via `svc`) (in `test_structure_list_returns_dtos`)

**Note:** Similar methods exist: `list_calculations_data()`, `list_demo_projects()`, `list_structures_data()`

#### `list_calculations()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `list_calculations`
**Callsites:** 1

File:line references:
- `tests/api/test_project_capabilities.py:93` (via `svc`) (in `test_project_list_calculations_returns_list`)

**Note:** Similar methods exist: `calculation()`, `list_calculations_data()`

#### `list_properties()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `list_properties`
**Callsites:** 1

File:line references:
- `tests/api/test_analysis_capabilities.py:112` (via `svc`) (in `test_list_properties_returns_list`)


#### `list_runs()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `list_runs`
**Callsites:** 1

File:line references:
- `tests/api/test_run_capabilities.py:68` (via `svc`) (in `test_list_runs_returns_list`)

**Note:** Similar methods exist: `run()`

#### `list_step_types()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `list_step_types`
**Callsites:** 1

File:line references:
- `tests/api/test_engine_capabilities.py:65` (via `svc`) (in `test_engine_list_step_types_returns_list`)


#### `list_steps()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `list_steps`
**Callsites:** 1

File:line references:
- `tests/api/test_calculation_read.py:84` (via `svc`) (in `test_calculation_list_steps_returns_dtos`)


#### `load_artifact()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `load_artifact`
**Callsites:** 6

File:line references:
- `tests/api/test_analysis_capabilities.py:158` (via `svc`) (in `test_load_artifact_json`)
- `tests/api/test_analysis_capabilities.py:203` (via `svc`) (in `test_load_artifact_npz`)
- `tests/api/test_analysis_capabilities.py:238` (via `svc`) (in `test_load_artifact_not_found`)
- `tests/api/test_analysis_capabilities.py:256` (via `svc`) (in `test_load_artifact_invalid_ref_none`)
- `tests/api/test_analysis_capabilities.py:285` (via `svc`) (in `test_load_artifact_invalid_ref_missing_path`)
- `tests/api/test_analysis_capabilities.py:320` (via `svc`) (in `test_load_artifact_unsupported_format`)


#### `remove_step()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `remove_step`
**Callsites:** 2

File:line references:
- `tests/api/test_calculation_write.py:362` (via `svc`) (in `test_remove_step_removes_from_step_yaml`)
- `tests/api/test_calculation_write.py:418` (via `svc`) (in `test_remove_step_unknown_step_raises_not_found`)


#### `update_config()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `update_config`
**Callsites:** 1

File:line references:
- `tests/api/test_project_capabilities.py:41` (via `svc`) (in `test_project_update_config_returns_dict`)


#### `update_meta()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `update_meta`
**Callsites:** 1

File:line references:
- `tests/api/test_calculation_write.py:44` (via `svc`) (in `test_calculation_update_meta_returns_dto`)


#### `update_step_params()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `update_step_params`
**Callsites:** 1

File:line references:
- `tests/api/test_calculation_write.py:62` (via `svc`) (in `test_calculation_update_step_params_returns_dto`)


#### `validate_installation()` on `quantumvitas.api.service.QVService`

**Class:** `quantumvitas.api.service.QVService`
**Method:** `validate_installation`
**Callsites:** 5

File:line references:
- `tests/api/test_engine_capabilities.py:83` (via `svc`) (in `test_engine_validate_installation_returns_dict`)
- `tests/api/test_engine_capabilities.py:106` (via `svc`) (in `test_validate_installation_known_engine`)
- `tests/api/test_engine_capabilities.py:140` (via `svc`) (in `test_validate_installation_unknown_engine`)
- `tests/api/test_engine_capabilities.py:161` (via `svc`) (in `test_validate_installation_qe_not_found`)
- `tests/api/test_engine_capabilities.py:181` (via `svc`) (in `test_validate_installation_engine_without_hook`)


#### `add_step()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `add_step`
**Callsites:** 31

File:line references:
- `tests/daemon/test_gui_calculation_detail.py:81` (via `svc`) (in `temp_project`)
- `tests/daemon/test_gui_calculation_detail.py:85` (via `svc`) (in `temp_project`)
- `tests/daemon/test_gui_calculation_detail.py:172` (via `svc`) (in `test_multi_step_calculation_ulid_only_selectors`)
- `tests/daemon/test_gui_calculation_detail.py:176` (via `svc`) (in `test_multi_step_calculation_ulid_only_selectors`)
- `tests/daemon/test_gui_job_and_step_flows.py:87` (via `svc`) (in `temp_project`)
- `tests/daemon/test_si_bands_calculation_daemon.py:210` (via `svc`) (in `calculation_with_steps`)
- `tests/daemon/test_si_bands_calculation_daemon.py:246` (via `svc`) (in `calculation_with_steps`)
- `tests/daemon/test_si_bands_calculation_daemon.py:283` (via `svc`) (in `calculation_with_steps`)
- `tests/daemon/test_si_bands_calculation_daemon.py:328` (via `svc`) (in `calculation_with_steps`)
- `tests/daemon/test_update_step_params_persistence.py:68` (via `svc`) (in `temp_project`)
- `tests/integration/test_incremental_run.py:153` (via `svc`) (in `minimal_calculation`)
- `tests/integration/test_incremental_run.py:159` (via `svc`) (in `minimal_calculation`)
- `tests/integration/test_incremental_run.py:165` (via `svc`) (in `minimal_calculation`)
- `tests/integration/test_incremental_run.py:583` (via `svc`) (in `test_ignore_ulid_for_equivalence`)
- `tests/integration/test_lammps_chain.py:101` (via `svc`) (in `chain_project`)
- `tests/integration/test_lammps_chain.py:126` (via `svc`) (in `chain_project`)
- `tests/integration/test_lammps_chain.py:152` (via `svc`) (in `chain_project`)
- `tests/integration/test_lammps_eam_md.py:99` (via `svc`) (in `eam_md_project`)
- `tests/integration/test_lammps_incremental_skip.py:90` (via `svc`) (in `inline_lj_project`)
- `tests/integration/test_lammps_incremental_skip.py:292` (via `svc`) (in `external_potential_project`)
- `tests/integration/test_lammps_lj_minimize.py:74` (via `svc`) (in `lj_project`)
- `tests/integration/test_step_slug_consistency.py:75` (via `svc`) (in `test_step_slug_uniqueness_and_consistency`)
- `tests/integration/test_step_slug_consistency.py:76` (via `svc`) (in `test_step_slug_uniqueness_and_consistency`)
- `tests/integration/test_step_slug_consistency.py:126` (via `svc`) (in `test_require_step_by_ulid_returns_correct_slug`)
- `tests/integration/test_step_slug_consistency.py:127` (via `svc`) (in `test_require_step_by_ulid_returns_correct_slug`)
- `tests/integration/test_step_slug_consistency.py:149` (via `svc`) (in `test_require_step_by_slug_returns_correct_step`)
- `tests/integration/test_step_slug_consistency.py:150` (via `svc`) (in `test_require_step_by_slug_returns_correct_step`)
- `tests/integration/test_step_slug_consistency.py:176` (via `svc`) (in `test_resource_index_matches_yaml`)
- `tests/integration/test_step_slug_consistency.py:177` (via `svc`) (in `test_resource_index_matches_yaml`)
- `tests/integration/test_step_slug_consistency.py:208` (via `svc`) (in `test_three_steps_same_type`)
- `tests/unit/test_api_get_band_structure_data.py:111` (via `svc`) (in `tmp_project_with_bands`)

**Note:** Similar methods exist: `add_step_to_calculation()`, `calc_add_step()`

#### `can_pin()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `can_pin`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:6164` (via `svc`) (in `_handle_can_pin_to_run`)


#### `delete()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `delete`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:6235` (via `svc`) (in `_handle_delete_project_history`)

**Note:** Similar methods exist: `can_delete_calculation()`, `can_delete_structure()`, `delete_calculation()`, `delete_project()`, `delete_step()`

#### `get()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get`
**Callsites:** 4

File:line references:
- `src/quantumvitas/cli/main.py:5293` (via `svc`) (in `_validate_step_structure_consistency`)
- `tests/unit/test_api_service_facade.py:95` (via `svc`) (in `test_structure_get_not_found`)
- `tests/unit/test_api_service_facade.py:118` (via `svc`) (in `test_calculation_get_not_found`)
- `tests/unit/test_calculation_ulid_contracts.py:75` (via `svc`) (in `test_get_calculation_detail_rejects_non_ulid`)

**Note:** Similar methods exist: `get_band_structure_data()`, `get_calculation()`, `get_calculation_detail()`, `get_calculation_for_cli()`, `get_calculation_pseudo_mapping()`

#### `get_config()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_config`
**Callsites:** 2

File:line references:
- `src/quantumvitas/cli/main.py:5281` (via `svc`) (in `_validate_step_structure_consistency`)
- `tests/unit/test_api_service_facade.py:70` (via `svc`) (in `test_load_project_config`)


#### `get_detail()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_detail`
**Callsites:** 1

File:line references:
- `tests/daemon/test_gui_calculation_detail.py:143` (via `svc`) (in `test_get_calculation_detail_has_steps`)


#### `get_latest_run_for_step()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_latest_run_for_step`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:6210` (via `svc`) (in `_handle_get_latest_run_for_step`)


#### `get_pin_data()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_pin_data`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:6188` (via `svc`) (in `_handle_get_pin_data`)


#### `get_run_revision()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_run_revision`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:6080` (via `svc`) (in `_handle_get_run_revision`)


#### `get_timeline()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_timeline`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:6062` (via `svc`) (in `_handle_get_project_history`)


#### `get_vis_data()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `get_vis_data`
**Callsites:** 7

File:line references:
- `tests/unit/test_qvservice_gui.py:129` (via `svc`) (in `test_returns_visualization_data`)
- `tests/unit/test_qvservice_gui.py:172` (via `svc`) (in `test_supercell_increases_atoms`)
- `tests/unit/test_qvservice_gui.py:173` (via `svc`) (in `test_supercell_increases_atoms`)
- `tests/unit/test_qvservice_gui.py:184` (via `svc`) (in `test_boundary_repeat_adds_image_atoms`)
- `tests/unit/test_qvservice_gui.py:190` (via `svc`) (in `test_boundary_repeat_adds_image_atoms`)
- `tests/unit/test_qvservice_gui.py:236` (via `svc`) (in `test_not_found_raises_error`)
- `tests/unit/test_qvservice_gui.py:280` (via `svc`) (in `test_structure_vis_serializable`)


#### `list()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `list`
**Callsites:** 2

File:line references:
- `tests/unit/test_api_service_facade.py:87` (via `svc`) (in `test_structure_list_empty`)
- `tests/unit/test_api_service_facade.py:110` (via `svc`) (in `test_calculation_list_empty`)

**Note:** Similar methods exist: `list_available_gen_steps()`, `list_calculations()`, `list_calculations_data()`, `list_demo_projects()`, `list_qe_engines()`

#### `list_runs()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `list_runs`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:6100` (via `svc`) (in `_handle_list_project_runs`)


#### `pin_analysis()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `pin_analysis`
**Callsites:** 1

File:line references:
- `src/quantumvitas/daemon/server.py:6137` (via `svc`) (in `_handle_pin_analysis_to_history`)


#### `preflight()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `preflight`
**Callsites:** 2

File:line references:
- `tests/daemon/test_qe_detection.py:68` (via `svc`) (in `test_preflight_check_initializes_qe_from_settings`)
- `tests/daemon/test_qe_detection.py:121` (via `svc`) (in `test_preflight_check_uses_two_state_resolver`)

**Note:** Similar methods exist: `preflight_check()`

#### `require_ref()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `require_ref`
**Callsites:** 4

File:line references:
- `src/quantumvitas/cli/main.py:5301` (via `svc`) (in `_validate_step_structure_consistency`)
- `src/quantumvitas/cli/main.py:5353` (via `svc`) (in `_execute_step_spec`)
- `tests/unit/test_api_service_facade.py:101` (via `svc`) (in `test_structure_require_ref_not_found`)
- `tests/unit/test_api_service_facade.py:124` (via `svc`) (in `test_calculation_require_ref_not_found`)


#### `resolve_enclosing_path()` on `quantumvitas.api_legacy.QVService`

**Class:** `quantumvitas.api_legacy.QVService`
**Method:** `resolve_enclosing_path`
**Callsites:** 1

File:line references:
- `tests/unit/test_api_service_facade.py:135` (via `svc`) (in `test_calculation_resolve_enclosing_returns_none`)


### Ambiguous / Needs Manual Review

**None found.**

---

## D. Summary Counts

- **Total API-like classes:** 8
- **Total static callsites:** 677
- **Total instance callsites:** 145
- **Dangling static calls:** 125
- **Dangling instance calls:** 108
- **Ambiguous calls:** 0

### Top Offending Modules/Files (by dangling call count)

- `src/quantumvitas/daemon/server.py`: 79 dangling call(s)
- `src/quantumvitas/cli/main.py`: 18 dangling call(s)
- `tests/api/test_calculation_write.py`: 12 dangling call(s)
- `tests/unit/test_api_service_facade.py`: 11 dangling call(s)
- `tests/api/test_analysis_capabilities.py`: 9 dangling call(s)
- `tests/integration/test_step_slug_consistency.py`: 9 dangling call(s)
- `src/quantumvitas/_api_legacy.py`: 8 dangling call(s)
- `src/quantumvitas/api_legacy.py`: 8 dangling call(s)
- `tests/api/test_engine_capabilities.py`: 8 dangling call(s)
- `src/quantumvitas/api/service.py`: 7 dangling call(s)
- `tests/unit/test_qvservice_gui.py`: 7 dangling call(s)
- `tests/api/test_calculation_read.py`: 5 dangling call(s)
- `tests/api/test_project_capabilities.py`: 5 dangling call(s)
- `tests/daemon/test_gui_calculation_detail.py`: 5 dangling call(s)
- `tests/unit/test_online_structure_supercell.py`: 4 dangling call(s)
- `tests/api/test_run_capabilities.py`: 4 dangling call(s)
- `tests/daemon/test_si_bands_calculation_daemon.py`: 4 dangling call(s)
- `tests/integration/test_incremental_run.py`: 4 dangling call(s)
- `tests/unit/test_online_project_payload_contract.py`: 3 dangling call(s)
- `tests/unit/test_optimade_offline.py`: 3 dangling call(s)
