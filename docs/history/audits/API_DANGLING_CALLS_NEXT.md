# API Dangling Calls and Legacy Usage Audit Report

**Generated:** Automated AST-based scan
**Repository:** QMatSuite

---

## Executive Summary

### Top 10 Offenders by Dangling Call Count

| Rank | Class::Method | Count | Files | Notes |
|------|---------------|-------|-------|-------|
| 1 | `qmatsuite.api.QMSService::init_project` | 97 | 39 | Static method - exists but scanner missed it |
| 2 | `qmatsuite.api.QMSService::init_calculation` | 78 | 36 | Static method - exists but scanner missed it |
| 3 | `qmatsuite.api.QMSService::import_structure` | 67 | 29 | Static method - exists but scanner missed it |
| 4 | `qmatsuite.api.QMSService::init_step` | 43 | 13 | Static method - exists but scanner missed it |
| 5 | `qmatsuite.api.QMSService::add_step` | 31 | 11 | Likely `svc.calculation.add_step()` - nested class method |
| 6 | `qmatsuite.api.QMSService::update_step_params` | 25 | 14 | Likely `svc.calculation.update_step_params()` - nested class method |
| 7 | `qmatsuite.api.QMSService::is_ulid_like` | 22 | 1 | Utility function - should move to utils |
| 8 | `qmatsuite.api.QMSService::run_step` | 20 | 8 | Static method - exists but scanner missed it |
| 9 | `qmatsuite.api.QMSService::get_pseudo_config` | 15 | 2 | Static method - exists but scanner missed it |
| 10 | `qmatsuite.api_legacy.QMSService::_build_structure_vis_payload` | 13 | 5 | Private method in legacy - test-only usage |

**Total dangling calls:** 773 (Note: Many are false positives due to static method detection limitations)
**Total legacy imports:** 8
**Critical legacy imports in new API:** 0 (good - no legacy dependencies in `src/qmatsuite/api/*`)

---

## 1. Inventory of API-like Classes

### qmatsuite.api.service.QMSService

- **Module:** `api.service`
- **Public methods:** 27
- **Nested classes:** 7

**Top method examples:** `__init__`, `analysis`, `structure`, `calculation`, `run`, `project`, `engine`, `history`, `init_project`, `get_settings`
*... and 17 more*

**Nested classes:**
- `Analysis` (11 methods)
- `Structure` (10 methods)
- `Calculation` (21 methods)
- `Run` (7 methods)
- `Project` (10 methods)
- `Engine` (5 methods)
- `History` (9 methods)

### qmatsuite._api_legacy.QMSService

- **Module:** `_api_legacy`
- **Public methods:** 236
- **Nested classes:** 0

**Top method examples:** `__init__`, `detect_context`, `find_path_context_ref`, `load_project_config`, `build_resource_index`, `resolve_calculation_ref`, `resolve_step_ref`, `resolve_structure_ref`, `require_calculation_ref`, `require_structure_ref`
*... and 226 more*


### qmatsuite.api_legacy.QMSService

- **Module:** `api_legacy`
- **Public methods:** 112
- **Nested classes:** 0

**Top method examples:** `__init__`, `__init__`, `resolve_calculation`, `resolve_step`, `resolve_structure`, `detect_context`, `build_resource_index`, `load_project_config`, `is_ulid_like`, `validate_ulid`
*... and 102 more*


---

## 2. Callsites Summary

---

## 3. Dangling Calls

Methods called but not defined on the resolved class.

**Note:** Many entries in this section are false positives due to static method detection limitations. Methods like `init_project`, `init_calculation`, `import_structure`, etc. are static methods that DO exist in `qmatsuite.api.service.QMSService` but were not properly detected by the AST scanner. These should be verified manually.

**Also note:** Some calls may be to nested class methods (e.g., `svc.calculation.add_step()` appears as `QMSService::add_step`). These are legitimate calls that need better resolution in the scanner.

### `qmatsuite.api.QMSService::init_project`

- **Count:** 97
- **Files:** 39

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:2027` (in _handle_create_project)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2083` (in _handle_create_project)
- `<HOME>/QMatSuite/tests/cli/test_calculation_structure_kind_engine_family.py:20` (in test_project)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:42` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_gui_job_and_step_flows.py:55` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_online_candidate_handler.py:24` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:43` (in test_promote_creates_new_resource)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:98` (in test_promote_requires_current_json)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:127` (in test_promote_requires_relax_step)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:162` (in test_daemon_promote_rpc)
*... and 87 more callsites*

### `qmatsuite.api.QMSService::init_calculation`

- **Count:** 78
- **Files:** 36

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:2716` (in _handle_create_calculation)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2801` (in _handle_create_calculation)
- `<HOME>/QMatSuite/tests/daemon/test_delete_calculation_daemon.py:30` (in test_delete_calculation_handler_accepts_slug_and_resolves)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:70` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_gui_job_and_step_flows.py:76` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:56` (in test_promote_creates_new_resource)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:111` (in test_promote_requires_current_json)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:140` (in test_promote_requires_relax_step)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:175` (in test_daemon_promote_rpc)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:194` (in calculation_with_steps)
*... and 68 more callsites*

### `qmatsuite.api.QMSService::import_structure`

- **Count:** 67
- **Files:** 29

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:2066` (in _handle_import_structure)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2122` (in _handle_import_structure)
- `<HOME>/QMatSuite/tests/cli/test_calculation_structure_kind_engine_family.py:35` (in test_project)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:50` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:58` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_gui_job_and_step_flows.py:62` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:53` (in test_promote_creates_new_resource)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:108` (in test_promote_requires_current_json)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:137` (in test_promote_requires_relax_step)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:172` (in test_daemon_promote_rpc)
*... and 57 more callsites*

### `qmatsuite.api.QMSService::init_step`

- **Count:** 43
- **Files:** 13

**Callsites:**
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:60` (in test_promote_creates_new_resource)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:112` (in test_promote_requires_current_json)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:141` (in test_promote_requires_relax_step)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:176` (in test_daemon_promote_rpc)
- `<HOME>/QMatSuite/tests/integration/orca/test_orca_project_level.py:99` (in orca_project)
- `<HOME>/QMatSuite/tests/integration/test_cp2k_integration.py:90` (in test_cp2k_scf_silicon)
- `<HOME>/QMatSuite/tests/integration/test_cp2k_integration.py:150` (in test_cp2k_relax_silicon_with_cell)
- `<HOME>/QMatSuite/tests/integration/test_cp2k_integration.py:235` (in test_cp2k_md_incremental_skip_disabled)
- `<HOME>/QMatSuite/tests/integration/test_lammps_long_smoke.py:149` (in lj_relax_project)
- `<HOME>/QMatSuite/tests/integration/test_lammps_long_smoke.py:284` (in eam_md_project)
*... and 33 more callsites*

### `qmatsuite.api.QMSService::add_step`

- **Count:** 31
- **Files:** 11

**Callsites:**
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:81` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:85` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:172` (in test_multi_step_calculation_ulid_only_selectors)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:176` (in test_multi_step_calculation_ulid_only_selectors)
- `<HOME>/QMatSuite/tests/daemon/test_gui_job_and_step_flows.py:87` (in temp_project)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:210` (in calculation_with_steps)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:246` (in calculation_with_steps)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:283` (in calculation_with_steps)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:328` (in calculation_with_steps)
- `<HOME>/QMatSuite/tests/daemon/test_update_step_params_persistence.py:68` (in temp_project)
*... and 21 more callsites*

### `qmatsuite.api.QMSService::update_step_params`

- **Count:** 25
- **Files:** 14

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3187` (in _handle_update_step_params)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:217` (in calculation_with_steps)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:253` (in calculation_with_steps)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:299` (in calculation_with_steps)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:334` (in calculation_with_steps)
- `<HOME>/QMatSuite/tests/integration/test_cp2k_integration.py:99` (in test_cp2k_scf_silicon)
- `<HOME>/QMatSuite/tests/integration/test_cp2k_integration.py:159` (in test_cp2k_relax_silicon_with_cell)
- `<HOME>/QMatSuite/tests/integration/test_cp2k_integration.py:244` (in test_cp2k_md_incremental_skip_disabled)
- `<HOME>/QMatSuite/tests/integration/test_lammps_chain.py:108` (in chain_project)
- `<HOME>/QMatSuite/tests/integration/test_lammps_chain.py:132` (in chain_project)
*... and 15 more callsites*

### `qmatsuite.api.QMSService::is_ulid_like`

- **Count:** 22
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2905` (in _handle_can_delete_calculation)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2986` (in _handle_delete_calculation)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2989` (in _handle_delete_calculation)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3098` (in _handle_get_step_detail)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3179` (in _handle_update_step_params)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3258` (in _handle_get_common_cards)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3302` (in _handle_set_common_card)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3342` (in _handle_get_pseudo_mapping)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3386` (in _handle_set_pseudo_mapping)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3545` (in _handle_reset_step_params)
*... and 12 more callsites*

### `qmatsuite.api.QMSService::run_step`

- **Count:** 20
- **Files:** 8

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:1744` (in run_step_command)
- `<HOME>/QMatSuite/tests/integration/orca/test_orca_project_level.py:151` (in test_run_step_uses_unified_pipeline)
- `<HOME>/QMatSuite/tests/integration/test_orca_relax_real.py:119` (in test_orca_relax_creates_current_json)
- `<HOME>/QMatSuite/tests/integration/test_orca_relax_real.py:141` (in test_orca_relax_structure_changes)
- `<HOME>/QMatSuite/tests/integration/test_orca_relax_real.py:174` (in test_orca_relax_molecule_composition)
- `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py:229` (in test_t3_runstep_scf_forbids_chkfile)
- `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py:311` (in test_t4_runstep_mp2_chain_execution)
- `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py:389` (in test_t5_missing_dependency_error)
- `<HOME>/QMatSuite/tests/integration/test_pyscf_relax_real.py:158` (in test_pyscf_relax_execution_creates_current_json)
- `<HOME>/QMatSuite/tests/integration/test_pyscf_relax_real.py:210` (in test_pyscf_relax_structure_changes)
*... and 10 more callsites*

### `qmatsuite.api.QMSService::get_pseudo_config`

- **Count:** 15
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:748` (in _handle_get_pseudo_config)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:1198` (in _handle_list_pseudo_archives_status)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:1252` (in _handle_install_pseudo_archive)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:748` (in _handle_get_pseudo_config)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:788` (in _handle_validate_pseudo_config)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:807` (in _handle_init_pseudo_dirs)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:829` (in _handle_install_seed_to_store)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:872` (in _handle_list_installed_sssp)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:897` (in _handle_list_seed_archives)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:940` (in _handle_download_sssp_library)
*... and 5 more callsites*

### `qmatsuite.api_legacy.QMSService::_build_structure_vis_payload`

- **Count:** 13
- **Files:** 5

**Callsites:**
- `<HOME>/QMatSuite/tests/integration/test_optimade_live.py:507` (in test_optimade_live_viewer_payload_builder)
- `<HOME>/QMatSuite/tests/integration/test_pipeline_alignment.py:90` (in test_online_vs_project_pipeline_bit_aligned)
- `<HOME>/QMatSuite/tests/integration/test_pipeline_alignment.py:111` (in test_online_vs_project_pipeline_bit_aligned)
- `<HOME>/QMatSuite/tests/unit/test_online_project_payload_contract.py:53` (in test_online_project_payload_contract_identical)
- `<HOME>/QMatSuite/tests/unit/test_online_project_payload_contract.py:61` (in test_online_project_payload_contract_identical)
- `<HOME>/QMatSuite/tests/unit/test_online_project_payload_contract.py:170` (in test_payload_contract_atoms_contains_all_display_atoms)
- `<HOME>/QMatSuite/tests/unit/test_online_structure_supercell.py:432` (in test_online_project_shared_pipeline)
- `<HOME>/QMatSuite/tests/unit/test_online_structure_supercell.py:440` (in test_online_project_shared_pipeline)
- `<HOME>/QMatSuite/tests/unit/test_online_structure_supercell.py:616` (in test_online_vs_project_pipeline_identical)
- `<HOME>/QMatSuite/tests/unit/test_online_structure_supercell.py:624` (in test_online_vs_project_pipeline_identical)
*... and 3 more callsites*

### `qmatsuite.api.QMSService::run_calculation`

- **Count:** 12
- **Files:** 5

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:3997` (in run_calculation_command)
- `<HOME>/QMatSuite/tests/integration/orca/test_orca_project_level.py:135` (in test_run_calculation_uses_jobgraph_pipeline)
- `<HOME>/QMatSuite/tests/integration/test_incremental_run.py:810` (in test_pseudo_preflight_warning_and_update)
- `<HOME>/QMatSuite/tests/integration/test_incremental_run.py:924` (in test_crash_recovery_incremental_rerun_from_failed_step)
- `<HOME>/QMatSuite/tests/integration/test_incremental_run.py:1008` (in test_pseudo_preflight_update_failure_non_blocking)
- `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py:145` (in test_t1_runcalc_incremental_uses_chkfile)
- `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py:166` (in test_t1_runcalc_incremental_uses_chkfile)
- `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py:182` (in test_t2_runcalc_full_forbids_chkfile)
- `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py:197` (in test_t2_runcalc_full_forbids_chkfile)
- `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py:214` (in test_t3_runstep_scf_forbids_chkfile)
*... and 2 more callsites*

### `qmatsuite.api.QMSService::promote_relax_structure`

- **Count:** 12
- **Files:** 5

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:3159` (in _handle_promote_relax_structure)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3218` (in _handle_promote_relax_structure)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:78` (in test_promote_creates_new_resource)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:116` (in test_promote_requires_current_json)
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:145` (in test_promote_requires_relax_step)
- `<HOME>/QMatSuite/tests/integration/test_relax_e2e.py:133` (in test_promote_relax_structure_e2e)
- `<HOME>/QMatSuite/tests/integration/test_relax_e2e.py:170` (in test_promote_requires_current_json)
- `<HOME>/QMatSuite/tests/integration/test_relax_e2e.py:198` (in test_promote_requires_relax_step_type)
- `<HOME>/QMatSuite/tests/integration/test_relax_promote_e2e.py:190` (in test_promote_creates_new_structure_resource)
- `<HOME>/QMatSuite/tests/integration/test_relax_promote_e2e.py:229` (in test_promote_requires_current_json)
*... and 2 more callsites*

### `qmatsuite.api.QMSService::list_calculations_data`

- **Count:** 11
- **Files:** 4

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:1973` (in _handle_list_calculations)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:2726` (in _handle_create_calculation)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2030` (in _handle_list_calculations)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2811` (in _handle_create_calculation)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:108` (in test_get_calculation_detail_has_steps)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:164` (in test_multi_step_calculation_ulid_only_selectors)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:279` (in test_change_calculation_structure_via_daemon)
- `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py:325` (in test_change_calculation_structure_rejects_project_root_as_selector)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:92` (in test_returns_list)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:102` (in test_calculation_entry_schema)
*... and 1 more callsites*

### `qmatsuite.api.QMSService::list_structures_data`

- **Count:** 9
- **Files:** 4

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:1960` (in _handle_list_structures)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:2074` (in _handle_import_structure)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2016` (in _handle_list_structures)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2130` (in _handle_import_structure)
- `<HOME>/QMatSuite/tests/integration/test_relax_promote_e2e.py:171` (in test_promote_creates_new_structure_resource)
- `<HOME>/QMatSuite/tests/integration/test_relax_promote_e2e.py:198` (in test_promote_creates_new_structure_resource)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:55` (in test_returns_list)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:67` (in test_structure_entry_schema)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:258` (in test_structures_list_serializable)

### `qmatsuite.api.QMSService::get_project_summary`

- **Count:** 8
- **Files:** 4

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:1948` (in _handle_get_project_summary)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:2039` (in _handle_create_project)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2006` (in _handle_get_project_summary)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2095` (in _handle_create_project)
- `<HOME>/QMatSuite/tests/unit/test_demo_snapshot_restore.py:140` (in test_create_demo_project_via_api)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:22` (in test_returns_project_info)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:41` (in test_counts_resources)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:247` (in test_project_summary_serializable)

### `qmatsuite.api.QMSService::validate_ulid`

- **Count:** 7
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:2911` (in _handle_delete_calculation)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:4328` (in _handle_get_calculation_pseudo_mapping)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3003` (in _handle_delete_calculation)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3115` (in _handle_get_step_detail)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:4125` (in _handle_get_calculation_detail)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:4403` (in _handle_get_calculation_pseudo_mapping)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:4577` (in _handle_get_pseudo_options_for_calculation)

### `qmatsuite.api.QMSService::create_demo_project`

- **Count:** 7
- **Files:** 5

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:4582` (in _handle_create_demo_project)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:4678` (in _handle_create_demo_project)
- `<HOME>/QMatSuite/tests/unit/test_api_service.py:81` (in test_create_demo_project_prevents_nested_project)
- `<HOME>/QMatSuite/tests/unit/test_demo_snapshot_restore.py:112` (in test_create_demo_project_via_api)
- `<HOME>/QMatSuite/tests/unit/test_demo_snapshot_restore.py:149` (in test_create_demo_project_with_invalid_demo_id)
- `<HOME>/QMatSuite/tests/unit/test_project_snapshot.py:471` (in test_create_demo_project_defaults_to_bands)
- `<HOME>/QMatSuite/tests/unit/test_project_snapshot.py:501` (in test_create_demo_project_with_explicit_demo_id)

### `qmatsuite.api.QMSService::get_vis_data`

- **Count:** 7
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:129` (in test_returns_visualization_data)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:172` (in test_supercell_increases_atoms)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:173` (in test_supercell_increases_atoms)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:184` (in test_boundary_repeat_adds_image_atoms)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:190` (in test_boundary_repeat_adds_image_atoms)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:236` (in test_not_found_raises_error)
- `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py:280` (in test_structure_vis_serializable)

### `qmatsuite.api.QMSService::configure_step`

- **Count:** 7
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/tools/run_lammps_long_smoke.py:143` (in run_workflow_a_lj_relax)
- `<HOME>/QMatSuite/tools/run_lammps_long_smoke.py:339` (in run_workflow_b_eam_md)
- `<HOME>/QMatSuite/tools/run_lammps_long_smoke.py:538` (in run_workflow_c_chain)
- `<HOME>/QMatSuite/tools/run_lammps_long_smoke.py:562` (in run_workflow_c_chain)
- `<HOME>/QMatSuite/tools/run_lammps_long_smoke.py:746` (in run_workflow_d_restart)
- `<HOME>/QMatSuite/tools/run_lammps_long_smoke.py:770` (in run_workflow_d_restart)
- `<HOME>/QMatSuite/tools/run_lammps_long_smoke.py:796` (in run_workflow_d_restart)

### `qmatsuite.api.service.QMSService::load_artifact`

- **Count:** 6
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/tests/api/test_analysis_capabilities.py:158` (in test_load_artifact_json)
- `<HOME>/QMatSuite/tests/api/test_analysis_capabilities.py:203` (in test_load_artifact_npz)
- `<HOME>/QMatSuite/tests/api/test_analysis_capabilities.py:238` (in test_load_artifact_not_found)
- `<HOME>/QMatSuite/tests/api/test_analysis_capabilities.py:256` (in test_load_artifact_invalid_ref_none)
- `<HOME>/QMatSuite/tests/api/test_analysis_capabilities.py:285` (in test_load_artifact_invalid_ref_missing_path)
- `<HOME>/QMatSuite/tests/api/test_analysis_capabilities.py:320` (in test_load_artifact_unsupported_format)

### `qmatsuite.api.QMSService::get_workflow_service`

- **Count:** 5
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:6248` (in _handle_list_workflow_templates)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:6282` (in _handle_detect_workflow)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:6365` (in _handle_detect_workflow_for_calculation)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:6436` (in _handle_instantiate_workflow)
- `<HOME>/QMatSuite/tests/unit/test_api_service_facade.py:178` (in test_get_workflow_service_wrapper)

### `qmatsuite.api.QMSService::get_band_structure_data`

- **Count:** 5
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:4859` (in _handle_get_band_structure_data)
- `<HOME>/QMatSuite/tests/unit/test_api_get_band_structure_data.py:156` (in test_get_band_structure_data_success)
- `<HOME>/QMatSuite/tests/unit/test_api_get_band_structure_data.py:220` (in test_get_band_structure_data_graceful_missing_stdout)
- `<HOME>/QMatSuite/tests/unit/test_api_get_band_structure_data.py:253` (in test_get_band_structure_data_missing_gnu)
- `<HOME>/QMatSuite/tests/unit/test_api_get_band_structure_data.py:270` (in test_get_band_structure_data_without_step_selector)

### `qmatsuite.api.service.QMSService::validate_installation`

- **Count:** 5
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/tests/api/test_engine_capabilities.py:83` (in test_engine_validate_installation_returns_dict)
- `<HOME>/QMatSuite/tests/api/test_engine_capabilities.py:106` (in test_validate_installation_known_engine)
- `<HOME>/QMatSuite/tests/api/test_engine_capabilities.py:140` (in test_validate_installation_unknown_engine)
- `<HOME>/QMatSuite/tests/api/test_engine_capabilities.py:161` (in test_validate_installation_qe_not_found)
- `<HOME>/QMatSuite/tests/api/test_engine_capabilities.py:181` (in test_validate_installation_engine_without_hook)

### `qmatsuite.api.QMSService::configure_species_map`

- **Count:** 4
- **Files:** 4

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:3643` (in configure_species_command)
- `<HOME>/QMatSuite/tests/daemon/test_gui_job_and_step_flows.py:652` (in test_calculation_stops_after_step_failure)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:200` (in calculation_with_steps)
- `<HOME>/QMatSuite/tests/integration/test_qe_relax_real.py:119` (in qe_calculation_with_relax)

### `qmatsuite.api.QMSService::get`

- **Count:** 4
- **Files:** 3

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:5293` (in _validate_step_structure_consistency)
- `<HOME>/QMatSuite/tests/unit/test_api_service_facade.py:95` (in test_structure_get_not_found)
- `<HOME>/QMatSuite/tests/unit/test_api_service_facade.py:118` (in test_calculation_get_not_found)
- `<HOME>/QMatSuite/tests/unit/test_calculation_ulid_contracts.py:75` (in test_get_calculation_detail_rejects_non_ulid)

### `qmatsuite.api.QMSService::require_ref`

- **Count:** 4
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:5301` (in _validate_step_structure_consistency)
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:5353` (in _execute_step_spec)
- `<HOME>/QMatSuite/tests/unit/test_api_service_facade.py:101` (in test_structure_require_ref_not_found)
- `<HOME>/QMatSuite/tests/unit/test_api_service_facade.py:124` (in test_calculation_require_ref_not_found)

### `qmatsuite.api.QMSService::get_settings`

- **Count:** 4
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:191` (in __init__)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:1374` (in _handle_get_debug_resolution)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:2996` (in _handle_get_step_detail)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:4295` (in _handle_get_calculation_pseudo_mapping)

### `qmatsuite.api.QMSService::load_pseudo_config`

- **Count:** 4
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:815` (in _handle_install_seed_to_store)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:871` (in _handle_list_seed_archives)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:957` (in _handle_download_all_sssp)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:1001` (in _handle_import_seed_archives)

### `qmatsuite.api.QMSService::can_delete_structure`

- **Count:** 4
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:2647` (in _handle_can_delete_structure)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:2666` (in _handle_delete_structure)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2721` (in _handle_can_delete_structure)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:2740` (in _handle_delete_structure)

### `qmatsuite.api.QMSService::download_pseudo_by_filename`

- **Count:** 4
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:3408` (in _handle_download_pseudo_by_filename)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:3448` (in _handle_download_pseudo_candidate)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3477` (in _handle_download_pseudo_by_filename)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3517` (in _handle_download_pseudo_candidate)

### `qmatsuite.api.QMSService::save_relax_final_structure`

- **Count:** 4
- **Files:** 3

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:3549` (in _handle_save_relax_final_structure)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:3619` (in _handle_save_relax_final_structure)
- `<HOME>/QMatSuite/tests/integration/test_relax_structure_save.py:132` (in test_save_relax_structure_idempotency)
- `<HOME>/QMatSuite/tests/integration/test_relax_structure_save.py:160` (in test_save_relax_structure_idempotency)

### `qmatsuite.api.service.QMSService::duplicate`

- **Count:** 4
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/tests/api/test_calculation_write.py:116` (in test_duplicate_calculation_happy_path)
- `<HOME>/QMatSuite/tests/api/test_calculation_write.py:157` (in test_duplicate_unknown_selector_raises_not_found)
- `<HOME>/QMatSuite/tests/api/test_calculation_write.py:189` (in test_duplicate_slug_conflict_raises_conflict)
- `<HOME>/QMatSuite/tests/api/test_calculation_write.py:220` (in test_duplicate_with_custom_slug)

### `QMSService.init_calculation::is_dir`

- **Count:** 4
- **Files:** 4

**Callsites:**
- `<HOME>/QMatSuite/tests/integration/test_pyscf_relax_real.py:95` (in pyscf_calculation_with_relax)
- `<HOME>/QMatSuite/tests/integration/test_qe_relax_real.py:113` (in qe_calculation_with_relax)
- `<HOME>/QMatSuite/tests/integration/test_relax_promote_e2e.py:112` (in promote_test_calculation_with_relax)
- `<HOME>/QMatSuite/tests/unit/test_api_service.py:203` (in test_init_calculation)

### `qmatsuite.api.QMSService::get_default_step_params`

- **Count:** 3
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:1270` (in init_step_command)
- `<HOME>/QMatSuite/tests/unit/test_api_service_facade.py:144` (in test_get_default_step_params_wrapper)
- `<HOME>/QMatSuite/tests/unit/test_api_service_facade.py:156` (in test_get_default_step_params_wrapper)

### `qmatsuite.api.QMSService::run_input_step`

- **Count:** 3
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:1881` (in _run_standalone_step)
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:1959` (in run_structure_command)
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:5383` (in _execute_step_spec)

### `qmatsuite.api.QMSService::list_installed_sssp`

- **Count:** 3
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:854` (in _handle_list_installed_sssp)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:934` (in _handle_download_sssp_library)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:976` (in _handle_download_all_sssp)

### `qmatsuite.api.QMSService::check_archives_status`

- **Count:** 3
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:1200` (in _handle_list_pseudo_archives_status)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:1287` (in _handle_install_pseudo_archive)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:1313` (in _handle_install_pseudo_archive)

### `qmatsuite.api.QMSService::detect_engine_for_calculation`

- **Count:** 3
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:3677` (in _handle_detect_presets)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:3787` (in _handle_apply_presets_to_step)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:3946` (in _handle_apply_presets_to_calculation)

### `qmatsuite.api.QMSService::detect_presets_from_calculation`

- **Count:** 3
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:3682` (in _handle_detect_presets)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:3788` (in _handle_apply_presets_to_step)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:3947` (in _handle_apply_presets_to_calculation)

### `qmatsuite.api.QMSService::import_step_from_qe_input`

- **Count:** 3
- **Files:** 3

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:4154` (in _handle_import_step_from_qe_input)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:4232` (in _handle_import_step_from_qe_input)
- `<HOME>/QMatSuite/tools/import_tutorial_datasets.py:562` (in _materialize_project_from_input_folder_legacy)

### `qmatsuite.api.QMSService::get_calculation_pseudo_mapping`

- **Count:** 3
- **Files:** 3

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:4332` (in _handle_get_calculation_pseudo_mapping)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:4407` (in _handle_get_calculation_pseudo_mapping)
- `<HOME>/QMatSuite/tools/test_silicon_wannier90_demo_logging.py:85` 

### `qmatsuite.api.QMSService::create_blob_store`

- **Count:** 3
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:5119` (in _handle_compile_fixture_volume)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:5142` (in _handle_compile_fixture_volume)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:5163` (in _handle_compile_fixture_volume)

### `qmatsuite.api.QMSService::load_calculation`

- **Count:** 3
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:5235` (in _handle_run_calculation)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:5323` (in _handle_run_step)
- `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py:5863` (in _snapshot_dag)

### `qmatsuite.api.QMSService::get_calculation_detail`

- **Count:** 3
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:4130` (in _handle_get_calculation_detail)
- `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py:4589` (in _handle_get_pseudo_options_for_calculation)
- `<HOME>/QMatSuite/tools/import_tutorial_datasets.py:944` (in validate_roundtrip_regeneration)

### `qmatsuite.api.service.QMSService::list`

- **Count:** 3
- **Files:** 3

**Callsites:**
- `<HOME>/QMatSuite/tests/api/test_calculation_read.py:45` (in test_calculation_list_returns_dtos)
- `<HOME>/QMatSuite/tests/api/test_engine_capabilities.py:27` (in test_engine_list_returns_list)
- `<HOME>/QMatSuite/tests/api/test_structure_capabilities.py:84` (in test_structure_list_returns_dtos)

### `qmatsuite.api.service.QMSService::cancel`

- **Count:** 3
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/tests/api/test_run_capabilities.py:105` (in test_cancel_happy_path)
- `<HOME>/QMatSuite/tests/api/test_run_capabilities.py:133` (in test_cancel_not_found)
- `<HOME>/QMatSuite/tests/api/test_run_capabilities.py:169` (in test_cancel_json_serializable)

### `QMSService.promote_relax_structure::exists`

- **Count:** 3
- **Files:** 3

**Callsites:**
- `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py:88` (in test_promote_creates_new_resource)
- `<HOME>/QMatSuite/tests/integration/test_relax_e2e.py:143` (in test_promote_relax_structure_e2e)
- `<HOME>/QMatSuite/tests/integration/test_relax_promote_e2e.py:204` (in test_promote_creates_new_structure_resource)

### `qmatsuite.api.QMSService::create_default_registry`

- **Count:** 2
- **Files:** 1

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:1536` (in detect_qe)
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:1927` (in run_structure_command)

### `qmatsuite.api.QMSService::analyze_band`

- **Count:** 2
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:4569` (in analyze_band_command)
- `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py:459` (in test_analyze_bands_and_generate_plot)

### `qmatsuite.api.QMSService::get_config`

- **Count:** 2
- **Files:** 2

**Callsites:**
- `<HOME>/QMatSuite/src/qmatsuite/cli/main.py:5281` (in _validate_step_structure_consistency)
- `<HOME>/QMatSuite/tests/unit/test_api_service_facade.py:70` (in test_load_project_config)

*... and 133 more dangling call groups*

---

## 4. Legacy Dependency Analysis

### Critical: Legacy imports in new API implementation

**Status:** ✅ **No critical legacy imports found in `src/qmatsuite/api/*`**

The new API implementation does not depend on legacy modules. This is correct.

### Other Legacy Imports (Test Files Only)

All legacy imports are in test files, which is acceptable for temporary compatibility during migration.

#### `tests/integration/test_pipeline_alignment.py`
- Line 24: `from qmatsuite.api_legacy import QMSService`

#### `tests/integration/test_optimade_live.py`
- Line 496: `from qmatsuite.api_legacy import QMSService` (inside function)

#### `tests/unit/test_online_project_payload_contract.py`
- Line 14: `from qmatsuite.api_legacy import QMSService`

#### `tests/unit/test_online_structure_supercell.py`
- Line 403: `from qmatsuite.api_legacy import QMSService` (inside function)
- Line 542: `from qmatsuite.api_legacy import QMSService` (inside function)

#### `tests/unit/test_optimade_offline.py`
- Line 21: `from qmatsuite.api_legacy import QMSService`

**Summary:**
- **Total legacy imports:** 8 (all in test files)
- **Critical imports in new API:** 0 ✅
- **Action:** These test files should be migrated to use `qmatsuite.api.QMSService` instead of `qmatsuite.api_legacy.QMSService`

---

## 5. Migration Decision Table

### Category A: Should migrate to new QMSService domain accessor

#### `qmatsuite.api.QMSService::get_pseudo_config`

- **Count:** 15
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::get_settings`

- **Count:** 4
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::list_installed_sssp`

- **Count:** 3
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::create_blob_store`

- **Count:** 3
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::get_calculation_detail`

- **Count:** 3
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tools/import_tutorial_datasets.py`, `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`

#### `qmatsuite.api.QMSService::create_default_registry`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/cli/main.py`

#### `qmatsuite.api.QMSService::get_environment_info`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::list_qe_engines`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::delete_structure`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::get_pseudo_mapping`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::get_relax_final_structure_preview`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::update_calculation_species_map`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::list_demo_projects`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::get_dos_data`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::get_reference_analysis`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::list_step_artifacts`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::get_journal`

- **Count:** 2
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::create_project_from_snapshot`

- **Count:** 1
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/cli/main.py`

#### `QMSService.create_default_registry::get`

- **Count:** 1
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/cli/main.py`

#### `qmatsuite.api.QMSService::get_qe_home`

- **Count:** 1
- **Rationale:** Should migrate to new QMSService domain accessor
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/cli/main.py`

*... and 18 more items in this category*

### Category B: Legit capability gap → consider adding API capability

#### `qmatsuite.api.QMSService::configure_step`

- **Count:** 7
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tools/run_lammps_long_smoke.py`

#### `qmatsuite.api.QMSService::load_pseudo_config`

- **Count:** 4
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::can_delete_structure`

- **Count:** 4
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::download_pseudo_by_filename`

- **Count:** 4
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::run_input_step`

- **Count:** 3
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/cli/main.py`

#### `qmatsuite.api.QMSService::check_archives_status`

- **Count:** 3
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::detect_engine_for_calculation`

- **Count:** 3
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::detect_presets_from_calculation`

- **Count:** 3
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::import_step_from_qe_input`

- **Count:** 3
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tools/import_tutorial_datasets.py`, `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::load_calculation`

- **Count:** 3
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::detect_qe`

- **Count:** 2
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::discover_qe_engines`

- **Count:** 2
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::set_qe_engine`

- **Count:** 2
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::set_pseudo_config`

- **Count:** 2
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::resolve_pseudo_provenance`

- **Count:** 2
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::load_manifest_archives`

- **Count:** 2
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::rename_structure`

- **Count:** 2
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::rename_calculation`

- **Count:** 2
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `QMSService.promote_relax_structure::relative_to`

- **Count:** 2
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::set_common_card`

- **Count:** 2
- **Rationale:** Legit capability gap
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

*... and 53 more items in this category*

### Category C: Pure util → consider moving to utils and re-exporting

#### `qmatsuite.api.QMSService::is_ulid_like`

- **Count:** 22
- **Rationale:** Pure utility function
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`

#### `qmatsuite.api.QMSService::validate_ulid`

- **Count:** 7
- **Rationale:** Pure utility function
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::parse_volume_artifact`

- **Count:** 2
- **Rationale:** Pure utility function
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::generate_kpath`

- **Count:** 1
- **Rationale:** Pure utility function
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/cli/main.py`

#### `qmatsuite.api.QMSService::generate_unique_name_and_slug`

- **Count:** 1
- **Rationale:** Pure utility function
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::meta_from_name`

- **Count:** 1
- **Rationale:** Pure utility function
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

### Category D: Tests-only / temporary compatibility → document sunset plan

#### `qmatsuite.api.QMSService::init_project`

- **Count:** 97
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/unit/test_api_service.py`, `<HOME>/QMatSuite/tests/daemon/test_update_step_params_persistence.py`, `<HOME>/QMatSuite/tests/integration/test_qe_relax_real.py`, `<HOME>/QMatSuite/tests/unit/test_resource_rename_safety.py`, `<HOME>/QMatSuite/tests/daemon/test_online_candidate_handler.py`

#### `qmatsuite.api.QMSService::init_calculation`

- **Count:** 78
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/unit/test_api_service.py`, `<HOME>/QMatSuite/tests/daemon/test_update_step_params_persistence.py`, `<HOME>/QMatSuite/tests/integration/test_qe_relax_real.py`, `<HOME>/QMatSuite/tests/unit/test_resource_rename_safety.py`, `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py`

#### `qmatsuite.api.QMSService::import_structure`

- **Count:** 67
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/unit/test_api_service.py`, `<HOME>/QMatSuite/tests/daemon/test_update_step_params_persistence.py`, `<HOME>/QMatSuite/tests/integration/test_qe_relax_real.py`, `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py`, `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py`

#### `qmatsuite.api.QMSService::init_step`

- **Count:** 43
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/integration/test_qe_relax_real.py`, `<HOME>/QMatSuite/tests/integration/vasp/test_vasp_project_e2e.py`, `<HOME>/QMatSuite/tests/integration/orca/test_orca_project_level.py`, `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py`, `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py`

#### `qmatsuite.api.QMSService::add_step`

- **Count:** 31
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/daemon/test_update_step_params_persistence.py`, `<HOME>/QMatSuite/tests/integration/test_incremental_run.py`, `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py`, `<HOME>/QMatSuite/tests/integration/test_step_slug_consistency.py`, `<HOME>/QMatSuite/tests/integration/test_lammps_incremental_skip.py`

#### `qmatsuite.api.QMSService::update_step_params`

- **Count:** 25
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/integration/test_qe_relax_real.py`, `<HOME>/QMatSuite/tests/integration/test_relax_promote_e2e.py`, `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py`, `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py`, `<HOME>/QMatSuite/tests/integration/test_cp2k_integration.py`

#### `qmatsuite.api.QMSService::run_step`

- **Count:** 20
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/integration/test_qe_relax_real.py`, `<HOME>/QMatSuite/src/qmatsuite/cli/main.py`, `<HOME>/QMatSuite/tests/integration/vasp/test_vasp_project_e2e.py`, `<HOME>/QMatSuite/tests/integration/orca/test_orca_project_level.py`, `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py`

#### `qmatsuite.api_legacy.QMSService::_build_structure_vis_payload`

- **Count:** 13
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/unit/test_optimade_offline.py`, `<HOME>/QMatSuite/tests/integration/test_optimade_live.py`, `<HOME>/QMatSuite/tests/unit/test_online_project_payload_contract.py`, `<HOME>/QMatSuite/tests/unit/test_online_structure_supercell.py`, `<HOME>/QMatSuite/tests/integration/test_pipeline_alignment.py`

#### `qmatsuite.api.QMSService::run_calculation`

- **Count:** 12
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/cli/main.py`, `<HOME>/QMatSuite/tests/integration/vasp/test_vasp_project_e2e.py`, `<HOME>/QMatSuite/tests/integration/orca/test_orca_project_level.py`, `<HOME>/QMatSuite/tests/integration/test_incremental_run.py`, `<HOME>/QMatSuite/tests/integration/test_pyscf_phase3c.py`

#### `qmatsuite.api.QMSService::promote_relax_structure`

- **Count:** 12
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`, `<HOME>/QMatSuite/tests/daemon/test_promote_relax_structure.py`, `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/tests/integration/test_relax_e2e.py`, `<HOME>/QMatSuite/tests/integration/test_relax_promote_e2e.py`

#### `qmatsuite.api.QMSService::list_calculations_data`

- **Count:** 11
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/daemon/test_gui_calculation_detail.py`, `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py`, `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::list_structures_data`

- **Count:** 9
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py`, `<HOME>/QMatSuite/tests/integration/test_relax_promote_e2e.py`, `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::get_project_summary`

- **Count:** 8
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py`, `<HOME>/QMatSuite/tests/unit/test_demo_snapshot_restore.py`, `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::create_demo_project`

- **Count:** 7
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/unit/test_api_service.py`, `<HOME>/QMatSuite/tests/unit/test_demo_snapshot_restore.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`, `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`, `<HOME>/QMatSuite/tests/unit/test_project_snapshot.py`

#### `qmatsuite.api.QMSService::get_vis_data`

- **Count:** 7
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/unit/test_qmsservice_gui.py`

#### `qmatsuite.api.service.QMSService::load_artifact`

- **Count:** 6
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/api/test_analysis_capabilities.py`

#### `qmatsuite.api.QMSService::get_workflow_service`

- **Count:** 5
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/unit/test_api_service_facade.py`, `<HOME>/QMatSuite/src/qmatsuite/daemon/server.py`

#### `qmatsuite.api.QMSService::get_band_structure_data`

- **Count:** 5
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/unit/test_api_get_band_structure_data.py`, `<HOME>/QMatSuite/src/qmatsuite/frontends/daemon/server.py`

#### `qmatsuite.api.service.QMSService::validate_installation`

- **Count:** 5
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/api/test_engine_capabilities.py`

#### `qmatsuite.api.QMSService::configure_species_map`

- **Count:** 4
- **Rationale:** Tests-only usage
- **Proposed action:** See rationale above

- **Sample files:** `<HOME>/QMatSuite/tests/daemon/test_gui_job_and_step_flows.py`, `<HOME>/QMatSuite/tests/integration/test_qe_relax_real.py`, `<HOME>/QMatSuite/tests/daemon/test_si_bands_calculation_daemon.py`, `<HOME>/QMatSuite/src/qmatsuite/cli/main.py`

*... and 46 more items in this category*
