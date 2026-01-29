# Contract Drift Triage - 0873ebf → HEAD

**Generated:** 2026-01-29
**Baseline:** 0873ebf
**HEAD:** Current (v2-python branch)
**Method Universe:** 116 total, 111 covered, 5 exempt

## Executive Summary

| Status | Count | Description |
|--------|-------|-------------|
| Golden OK, HEAD PASS | 45 | Contract stable |
| Golden OK, HEAD FAIL | 30 | Response drift - needs compat shaper |
| Golden FAIL | 38 | Recipe needs 0873ebf-compat payload |
| EXEMPT | 5 | Approved exemptions |

## Category Definitions

- **A)** API signature drift - Payload field changes (required→optional, renamed, etc.)
- **B)** Response contract drift - Output schema/field changes
- **C)** Environment/noise - Paths, ULIDs, timestamps (handled by normalization)
- **D)** Service dependency - QE engine, network, file state required
- **E)** Exempt - 5 approved: cancel_job, get_job_status, get_job_logs, compile_fixture_volume, shutdown

---

## Part 1: Golden Generation Failures (38 methods)

These recipes failed when running in 0873ebf worktree. **Fix required**: Update recipes to send 0873ebf-compatible payloads.

### A) Missing Required Field (21 methods)

Recipe sends HEAD-style payload, but 0873ebf requires additional fields.

| Method | GUI | Missing Field | Fix |
|--------|-----|---------------|-----|
| can_delete_structure | | selector | Add selector to recipe |
| can_pin_to_run | | step_id | Add step_id to recipe |
| change_calculation_structure | Y | new_structure | Add new_structure to recipe |
| create_demo_project | Y | target_dir | Add target_dir to recipe |
| delete_structure | Y | selector | Add selector to recipe |
| detect_workflow | Y | calculation_path | Add calculation_path to recipe |
| download_pseudo_by_filename | | project_root | Add project_root to recipe |
| download_pseudo_candidate | | project_root | Add project_root to recipe |
| ensure_calculation_analysis | Y | analysis_type | Add analysis_type to recipe |
| get_latest_run_for_step | Y | step_id | Add step_id to recipe |
| get_pin_data | | run_id | Add run_id to recipe |
| get_step_detail | Y | step | Add step to recipe |
| get_structure_vis | Y | selector | Add selector to recipe |
| import_pseudo_files | | project_root | Add project_root to recipe |
| instantiate_workflow | Y | workflow_id | Add workflow_id to recipe |
| materialize_pseudo_file | | sha256 | Add sha256 to recipe |
| pin_analysis_to_history | Y | run_id | Add run_id to recipe |
| rename_structure | Y | selector | Add selector to recipe |
| run_single_step | | step_ulid | Add step_ulid to recipe |
| save_relax_final_structure | | parent_structure_ulid | Add parent_structure_ulid to recipe |
| set_common_card | | card_name | Add card_name to recipe |
| structure_get_online_candidate | Y | candidate_id | Add candidate_id to recipe |
| structure_import_online_candidate | Y | candidate_id | Add candidate_id to recipe |

### A) Unexpected Keyword Argument (2 methods)

Recipe sends HEAD-style field that 0873ebf doesn't accept.

| Method | GUI | Unexpected Field | Fix |
|--------|-----|------------------|-----|
| reset_step_params | Y | calculation_ulid | Remove from recipe payload |
| list_qe_ui_parameters | | step_type (should be module) | Use correct field name |

### D) Service/Engine Dependencies (8 methods)

Recipe fails due to missing engine, files, or incorrect state.

| Method | GUI | Issue | Fix |
|--------|-----|-------|-----|
| apply_presets_to_calculation | Y | No QE engine | Mock QE or skip if no engine |
| apply_presets_to_step | | ResolvedResource error | Fix recipe world setup |
| detect_presets | Y | No QE engine | Mock QE or skip if no engine |
| get_band_structure_data | Y | Missing bands file | Provide fixture bands file |
| get_dos_data | Y | Missing DOS file | Provide fixture DOS file |
| get_reference_analysis | Y | NoneType error | Fix recipe world setup |
| get_relax_final_structure_preview | | Not a relax step | Use relax step in recipe |
| promote_relax_structure | | Not a relax step | Use relax step in recipe |

### D) Recipe Logic Errors (5 methods)

| Method | GUI | Issue | Fix |
|--------|-----|-------|-----|
| get_pseudo_options_for_calculation | | dict has no attribute store_dir | Fix recipe world setup |
| import_structure | Y | Is a directory error | Fix file path in recipe |
| rename_calculation | Y | Need calculation_ulid or selector | Add selector to recipe |
| reorder_calculation_steps | Y | New order missing steps | Fix step ID handling |
| resolve_project_pseudo_provenance | | Need pseudo_abspath or both paths | Add correct paths |

---

## Part 2: HEAD Drift Detection (73 methods with golden OK)

### PASS - No Drift (45 methods)

These methods have stable contracts between 0873ebf and HEAD:

| Method | GUI | Notes |
|--------|-----|-------|
| analyze_project_pseudo_effects | | Stable |
| can_delete_calculation | | Stable |
| compute_store_size | Y | Stable |
| create_project | Y | Stable |
| delete_calculation | Y | Stable |
| delete_project_history | Y | Stable |
| delete_step | Y | Stable |
| detect_workflow_for_calculation | Y | Stable |
| download_all_sssp | | Stable |
| download_sssp_library | | Stable |
| get_calculation_pseudo_mapping | | Stable |
| get_common_cards | | Stable |
| get_debug_resolution | Y | Stable |
| get_env_info | Y | Stable |
| get_journal_entry | | Stable |
| get_library_status | | Stable |
| get_preset_catalog | Y | Stable |
| get_pseudo_mapping | | Stable |
| get_run_revision | | Stable |
| get_step_preset_footprints | Y | Stable |
| import_seed_archives | | Stable |
| init_pseudo_dirs | | Stable |
| install_library | | Stable |
| install_pseudo_archive | | Stable |
| install_seed_to_store | | Stable |
| job_counts | Y | Stable |
| list_calculations | | Stable |
| list_installed_sssp | | Stable |
| list_jobs | | Stable |
| list_libraries | Y | Stable |
| list_project_runs | | Stable |
| list_seed_archives | | Stable |
| list_step_artifacts | Y | Stable |
| list_workflow_templates | Y | Stable |
| ping | Y | Stable |
| remove_library | | Stable |
| repair_library | | Stable |
| search_legacy_pseudos | | Stable |
| set_debug_resolution | Y | Stable |
| set_log_level | Y | Stable |
| set_pseudo_config | | Stable |
| set_qe_engine | Y | Stable |
| validate_pseudo_config | | Stable |

### FAIL - Response Drift (30 methods)

These need compat response shapers:

| Method | GUI | Category | Drift Summary |
|--------|-----|----------|---------------|
| add_step_to_calculation | Y | B | Missing: id, steps[].input, steps[].reference; Extra: steps[].status |
| create_calculation | Y | B | n_steps: int→None |
| detect_qe | Y | C | found: diff (env), list lengths |
| discover_qe_engines | | C | cached_at timestamp, counts |
| find_project_root | Y | C | found: env-dependent |
| get_calculation_detail | Y | B | Extra: calculation_id, structure_name, steps[].status; step types |
| get_project_history | Y | C | ULIDs in nested arrays |
| get_project_summary | Y | C | Paths differ |
| get_pseudo_config | Y | B | Missing: default_store_dir, repo_pseudo_dir, default_seed_dir; Extra: legacy_tables_base_url, network_pseudo_base_url |
| get_scf_convergence | Y | C | Paths differ |
| import_step_from_qe_input | Y | B | Same as get_calculation_detail |
| list_calculation_templates | Y | C | Paths differ |
| list_demo_projects | Y | B | Missing: subtitle, difficulty, recommended_use, recommended_analysis, tags |
| list_journal_entries | Y | B | step types: qe_scf→scf, qe_nscf→nscf; missing meta.path |
| list_pseudo_archives_status | | C | archives list (env-dependent) |
| list_qe_engines | Y | C | internal_engines count (env) |
| list_qe_parameter_metadata | Y | B | Response structure changed |
| list_structures | Y | B | Missing: n_species; Extra: lattice_abc, space_group |
| list_wannier_3d_fixtures | Y | C | Paths differ |
| preflight_check | Y | C/B | ok: env, errors: env |
| read_step_artifact_text | Y | C | Paths differ |
| rebuild_project_registry | Y | B | Registry structure differs |
| reload_qe_parameter_metadata | Y | C | Paths differ |
| run_calculation | Y | C | ULIDs |
| run_step | Y | C | ULIDs |
| set_pseudo_mapping | | D | Service error |
| structure_search_online | Y | D | CandidateSummary import error |
| update_calculation_species_map | | B | Major structure change |
| update_step_params | Y | B | Missing: structure, species_overrides |

---

## Part 3: Exempt Methods (5)

| Method | GUI | Reason |
|--------|-----|--------|
| cancel_job | Y | Requires active running job; ephemeral state |
| compile_fixture_volume | Y | Dev-only; requires specific Wannier90 fixtures |
| get_job_logs | Y | Requires active job with log file; ephemeral state |
| get_job_status | Y | Requires active job in JobManager; ephemeral state |
| shutdown | | Terminates daemon; cannot test |

---

## Part 4: P0 GUI-Critical Fixes

### Response Shapers Needed (Category B)

These methods have successful goldens but HEAD responses differ. Compat layer must shape responses:

1. **create_calculation** - `n_steps` should be 0 not None
2. **get_pseudo_config** - Add: default_store_dir, repo_pseudo_dir, default_seed_dir
3. **list_journal_entries** - Map step types: scf→qe_scf, nscf→qe_nscf
4. **list_demo_projects** - Add: subtitle, difficulty, recommended_use, etc.
5. **add_step_to_calculation** - Add: id, steps[].input, steps[].reference
6. **list_structures** - Add: n_species
7. **update_step_params** - Add: structure, species_overrides
8. **get_calculation_detail** - Map step types, fix structure
9. **import_step_from_qe_input** - Same as get_calculation_detail

### Recipe Fixes Needed

These recipes must be updated to send 0873ebf-compatible payloads:

1. **change_calculation_structure** - Add `new_structure` field
2. **delete_structure** - Add `selector` field
3. **create_demo_project** - Add `target_dir` field
4. **detect_workflow** - Add `calculation_path` field
5. **get_step_detail** - Add `step` field
6. **get_structure_vis** - Add `selector` field
7. **instantiate_workflow** - Add `workflow_id` field
8. **reset_step_params** - Remove `calculation_ulid` field
9. **rename_structure** - Add `selector` field

---

## Implementation Priority

### Phase 1: Response Shapers (P0)
Fix the 9 GUI-critical response shapers in `daemon/compat.py`

### Phase 2: Recipe Fixes (P1)
Fix 21 recipes with missing required fields

### Phase 3: Service Dependencies (P2)
Add QE mocks or fixture files for engine-dependent methods

### Phase 4: Remaining Drift (P3)
Handle environment-dependent differences via normalization
