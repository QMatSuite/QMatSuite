# API Slimming Opportunity Report

**Generated**: 2026-02-02
**Baseline**: 243 entrypoints → **Current**: 213 entrypoints (-30, -12.3%)
**Target**: Further consolidation opportunities

---

## Executive Summary

This report provides an exhaustive catalog of all 213 public API entrypoints and identifies consolidation opportunities beyond the "easy wins" already harvested. The analysis reveals:

1. **79 utils functions** - Many are thin proxies to core; several clusters could merge
2. **23 static methods** - ALL unused by daemon/CLI (test-only); should migrate to nested accessors
3. **88 nested service methods** - Core capabilities; several overlap opportunities
4. **11 DTOs** - Appropriate surface
5. **10 errors** - Appropriate surface
6. **2 api_init exports** - Required

**Key Finding**: The 23 static methods are NOT used by daemon or CLI - they are only called by tests. This is a major architectural smell suggesting these should either become nested accessor methods or be moved to utils.

---

## 1. Full API Catalog

### 1.1 Utils Functions (79 total)

#### Resource Utilities (6)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `slugify` | utils.py:35 | `(value: str, fallback: str)` | `str` | Filesystem-safe slug | 0/23/22 | thin proxy | KEEP |
| `meta_from_name` | utils.py:50 | `(kind: str, *, name: str, path: str)` | `dict` | Generate resource metadata | 2/12/30 | thin proxy | KEEP |
| `ensure_relative_path` | utils.py:70 | `(path, *, base: Path)` | `str` | Make path relative | 0/23/6 | thin proxy | KEEP |
| `generate_unique_name_and_slug` | utils.py:133 | `(kind, preferred_name, existing_slugs)` | `tuple[str, str]` | Unique name/slug pair | 2/2/2 | thin proxy | KEEP |
| `is_ulid_like` | utils.py:374 | `(s: str)` | `bool` | Check ULID format | 29/0/20 | helper | KEEP |
| `validate_ulid` | utils.py:390 | `(ulid_str: str, kind: str)` | `str` | Validate ULID | 6/0/1 | helper | KEEP |

#### Structure I/O (7)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `read_structure` | utils.py:85 | `(filepath, format=None)` | `Structure` | Read atomic structure | 2/9/56 | thin proxy | KEEP |
| `write_structure` | utils.py:100 | `(structure, filepath, format, metadata)` | `None` | Write atomic structure | 3/2/58 | thin proxy | KEEP |
| `canonicalize_structure` | utils.py:1445 | `(structure)` | `None` | Canonicalize in-place | 2/0/88 | thin proxy | KEEP |
| `reduce_formula` | utils.py:1456 | `(formula: str)` | `str` | Reduce chemical formula | 2/0/2 | thin proxy | KEEP |
| `visualize_structure` | utils.py:1751 | `(structure, ...)` | `dict` | Generate vis data | 0/2/18 | thin proxy | MERGE_CANDIDATE |
| `build_structure_vis_payload` | utils.py:641 | `(structure, params)` | `dict` | Build vis payload | 3/0/23 | thin proxy | MERGE_CANDIDATE |
| `DisplayModeParams` | utils.py:638 | class re-export | class | Visualization params | 0/0/0 | class re-export | KEEP |

#### Template Operations (3)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `list_calculation_templates` | utils.py:155 | `()` | `list[dict]` | List available templates | 4/2/8 | thin proxy | MOVE_TO_SERVICE |
| `copy_calculation_template` | utils.py:166 | `(template_name, target_dir, ...)` | `Path` | Copy template to dir | 0/2/0 | thin proxy | MOVE_TO_SERVICE |
| `copy_structure_template` | utils.py:199 | `(template_name, target_dir, ...)` | `Path` | Copy structure template | 0/2/0 | thin proxy | MOVE_TO_SERVICE |

#### Selector/Entry Utilities (4)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `extract_selector_from_entry` | utils.py:223 | `(entry: dict, kind: str)` | `str\|None` | Extract selector from entry | 0/26/0 | helper | KEEP |
| `entry_display_name` | utils.py:254 | `(entry: dict)` | `str` | Human-readable name | 0/8/0 | helper | KEEP |
| `entry_matches` | utils.py:285 | `(entry: dict, identifier: str)` | `bool` | Match entry to identifier | 0/2/13 | helper | KEEP |
| `move_to_trash` | utils.py:270 | `(path, trash_dir)` | `Path` | Move file to trash | 0/5/0 | helper | KEEP |

#### QE Input Utilities (6)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `detect_runtime_control_keys` | utils.py:300 | `(parameters: dict)` | `list[str]` | Detect runtime keys | 0/2/10 | helper | BUNDLE_CANDIDATE |
| `needs_alat_preservation` | utils.py:314 | `(qe_input)` | `bool` | Check alat preservation | 0/2/0 | helper | BUNDLE_CANDIDATE |
| `extract_alat_bohr` | utils.py:328 | `(qe_input)` | `float\|None` | Extract alat value | 0/2/0 | helper | BUNDLE_CANDIDATE |
| `write_qe_input_file` | utils.py:342 | `(qe_input, filepath)` | `None` | Write QE input file | 0/3/0 | thin proxy | KEEP |
| `build_step_spec_from_qe_input` | utils.py:354 | `(qe_input, step_type_spec)` | `dict` | Build step spec | 0/2/16 | helper | KEEP |
| `apply_card_overrides_to_qe_input` | utils.py:1634 | `(qe_input, card_overrides)` | `None` | Apply card overrides | 0/2/0 | helper | BUNDLE_CANDIDATE |
| `apply_species_overrides_to_qe_input` | utils.py:1646 | `(qe_input, species_overrides)` | `None` | Apply species overrides | 0/2/3 | helper | BUNDLE_CANDIDATE |

#### Calculation Model I/O (3)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `load_calculation` | utils.py:428 | `(path, project_root)` | `CalculationModel` | Load calculation model | 4/2/121 | internal-model-leak | REPLACE |
| `save_calculation` | utils.py:445 | `(model, path)` | `None` | Save calculation model | 0/2/21 | internal-model-leak | REPLACE |
| `calculations_using_structure` | utils.py:410 | `(project_root, config, struct_entry)` | `list` | Find calcs using struct | 0/4/0 | helper | MOVE_TO_SERVICE |

#### Pseudo Config Cluster (8)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `get_pseudo_config` | utils.py:463 | `()` | `dict` | Get pseudo config | 14/0/11 | capability | BUNDLE_CANDIDATE |
| `set_pseudo_config` | utils.py:477 | `(seed_dir, store_dir, ...)` | `dict` | Set pseudo config | 7/0/10 | capability | BUNDLE_CANDIDATE |
| `validate_pseudo_config_dict` | utils.py:513 | `(config_dict)` | `dict` | Validate config | 2/0/0 | helper | BUNDLE_CANDIDATE |
| `list_installed_sssp` | utils.py:540 | `(store_dir)` | `list[dict]` | List SSSP libraries | 6/0/17 | capability | BUNDLE_CANDIDATE |
| `list_seed_archives` | utils.py:566 | `(seed_dir)` | `list[dict]` | List seed archives | 5/0/10 | capability | BUNDLE_CANDIDATE |
| `check_archives_status` | utils.py:584 | `(archives, config)` | `list[dict]` | Check archive status | 4/0/0 | capability | BUNDLE_CANDIDATE |
| `load_manifest_archives` | utils.py:618 | `()` | `list[dict]` | Load manifest | 3/0/21 | capability | BUNDLE_CANDIDATE |
| `search_legacy_pseudos` | utils.py:1842 | `(element, config)` | `dict` | Search legacy pseudos | 7/0/11 | capability | BUNDLE_CANDIDATE |

#### QE Engine Detection Cluster (7)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `detect_qe` | utils.py:839 | `()` | `dict` | Detect QE installation | 7/1/11 | capability | BUNDLE_CANDIDATE |
| `list_qe_engines` | utils.py:912 | `()` | `dict` | List QE engines | 4/0/8 | capability | BUNDLE_CANDIDATE |
| `discover_qe_engines` | utils.py:962 | `()` | `dict` | Discover QE engines | 7/0/8 | capability | BUNDLE_CANDIDATE |
| `set_qe_engine` | utils.py:1052 | `(bin_dir)` | `dict` | Set active QE engine | 4/0/8 | capability | BUNDLE_CANDIDATE |
| `get_qe_home` | utils.py:1577 | `()` | `Path\|None` | Get QE home dir | 0/2/4 | helper | BUNDLE_CANDIDATE |
| `get_environment_info` | utils.py:891 | `()` | `dict` | Get env info | 2/0/0 | helper | BUNDLE_CANDIDATE |
| `create_default_registry` | utils.py:1563 | `(config_dict)` | `EngineRegistry` | Create engine registry | 0/4/45 | internal-model-leak | REPLACE |

#### Pseudo Download Cluster (3)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `download_pseudo_by_filename` | utils.py:734 | `(filename, element, ...)` | `dict` | Download pseudo file | 6/0/12 | capability | BUNDLE_CANDIDATE |
| `download_pseudo_from_url` | utils.py:1133 | `(url, dest_dir, ...)` | `dict` | Download from URL | 3/0/0 | capability | BUNDLE_CANDIDATE |
| `resolve_pseudo_provenance` | utils.py:1083 | `(filename, element)` | `dict` | Resolve provenance | 2/0/6 | helper | BUNDLE_CANDIDATE |

#### Presets/Precision Cluster (7)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `apply_presets_to_step` | utils.py:1320 | `(step_spec, presets, ...)` | `dict` | Apply presets to step | 5/0/72 | capability | KEEP |
| `get_preset_catalog` | utils.py:1354 | `()` | `dict` | Get preset catalog | 4/0/9 | capability | BUNDLE_CANDIDATE |
| `detect_workflow_type` | utils.py:1365 | `(calculation_dir)` | `str` | Detect workflow type | 2/0/12 | helper | BUNDLE_CANDIDATE |
| `get_step_preset_footprints` | utils.py:1382 | `(calculation_dir)` | `dict` | Get preset footprints | 4/0/12 | helper | BUNDLE_CANDIDATE |
| `resolve_precision_context` | utils.py:1399 | `(project_root, ...)` | `PrecisionContext` | Resolve precision ctx | 2/0/0 | helper | BUNDLE_CANDIDATE |
| `create_precision_advisor` | utils.py:1909 | `(calculation_dir)` | `PrecisionAdvisor` | Create advisor | 2/0/0 | internal-model-leak | REPLACE |
| `detect_presets_from_calculation` | utils.py:712 | `(calculation_dir)` | `dict` | Detect presets | 4/0/33 | helper | BUNDLE_CANDIDATE |

#### Calculation Discovery (4)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `detect_engine_for_calculation` | utils.py:696 | `(calculation_dir)` | `str\|None` | Detect engine | 4/0/0 | helper | MOVE_TO_SERVICE |
| `find_calculation_raw_dir` | utils.py:1662 | `(calculation_dir, working_dir_name)` | `Path` | Find raw dir | 0/2/0 | helper | MOVE_TO_SERVICE |
| `find_calculation_results_dir` | utils.py:1677 | `(calculation_dir)` | `Path` | Find results dir | 0/2/0 | helper | MOVE_TO_SERVICE |
| `compute_io_dir_from_calculation_model` | utils.py:1272 | `(model, project_root)` | `Path` | Compute IO dir | 3/0/0 | helper | MOVE_TO_SERVICE |

#### Online Search Cluster (5)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `search_online_structures` | utils.py:1474 | `(query, sources, ...)` | `list[CandidateSummary]` | Search online | 2/0/0 | capability | KEEP |
| `fetch_structure_from_optimade` | utils.py:1492 | `(optimade_base, source_id)` | `Structure` | Fetch from OPTIMADE | 2/0/19 | capability | MERGE_CANDIDATE |
| `score_candidate` | utils.py:1507 | `(structure, source, query_reduced, raw_data)` | `tuple` | Score candidate | 2/0/0 | helper | MERGE_CANDIDATE |
| `extract_provenance` | utils.py:1524 | `(structure, source, raw_data)` | `dict` | Extract provenance | 2/0/3 | helper | MERGE_CANDIDATE |
| `OnlineStructureCache` | utils.py:669 | class re-export | class | Cache class | 0/0/0 | class re-export | KEEP |

#### Analysis/Plotting Cluster (5)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `find_band_analysis_files` | utils.py:1691 | `(search_dir)` | `BandFiles` | Find band files | 0/2/0 | helper | MOVE_TO_SERVICE |
| `parse_scf_output` | utils.py:1709 | `(output_file)` | `SCFResult` | Parse SCF output | 0/4/30 | thin proxy | KEEP |
| `plot_scf_convergence` | utils.py:1723 | `(scf_result, ax)` | `Axes` | Plot SCF conv | 0/3/5 | thin proxy | KEEP |
| `save_figure` | utils.py:1738 | `(fig, output_path, **kwargs)` | `None` | Save matplotlib fig | 0/5/19 | thin proxy | KEEP |

#### Snapshot Operations (3)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `materialize_project_from_snapshot` | utils.py:1788 | `(snapshot, parent_dir, new_project_name)` | `Path` | Create project from snapshot | 0/2/20 | thin proxy | KEEP |
| `export_project_to_snapshot` | utils.py:1812 | `(project_root)` | `ProjectSnapshot` | Export to snapshot | 0/2/23 | thin proxy | KEEP |
| `get_project_snapshot_class` | utils.py:1827 | `()` | `type` | Get snapshot class | 0/2/0 | class factory | KEEP |

#### Context/Path Utilities (2)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `find_path_context_from_pwd` | utils.py:1427 | `(start_dir, max_depth)` | `PathContext` | Find path context | 2/8/11 | capability | KEEP |
| `ContextNotFoundError` | utils.py:1424 | class re-export | exception | Context error | 0/0/0 | class re-export | KEEP |

#### QE Metadata Cluster (5)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `get_ui_parameters` | (re-export) | `(module_name)` | `list` | Get UI params | daemon | capability | BUNDLE_CANDIDATE |
| `list_supported_modules` | (re-export) | `()` | `list` | List modules | daemon | capability | BUNDLE_CANDIDATE |
| `get_module_param_sections` | (re-export) | `(module_name)` | `dict` | Get param sections | daemon | capability | BUNDLE_CANDIDATE |
| `get_module_card_sections` | (re-export) | `(module_name)` | `dict` | Get card sections | daemon | capability | BUNDLE_CANDIDATE |
| `QEUIParam` | utils.py:677 | class re-export | class | UI param class | 0/0/0 | class re-export | KEEP |

#### Miscellaneous (9)

| Name | File:Line | Signature | Returns | Behavior | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|----------|-------|----------------|----------|
| `get_journal` | utils.py:1247 | `()` | `Journal` | Get journal | 5/0/11 | internal-model-leak | REPLACE |
| `create_blob_store` | utils.py:1258 | `(calc_dir)` | `BlobStore` | Create blob store | 4/0/0 | internal-model-leak | REPLACE |
| `parse_volume_artifact` | utils.py:1294 | `(path)` | `dict` | Parse volume data | 3/0/0 | capability | KEEP |
| `run_input_step` | utils.py:1592 | `(input_file, engine, ...)` | `dict` | Run single input | 0/6/4 | capability | MOVE_TO_SERVICE |
| `set_settings` | utils.py:1544 | `(settings_dict)` | `None` | Set global settings | 2/0/0 | capability | KEEP |

---

### 1.2 Static Methods (23 total) - ALL UNUSED BY DAEMON/CLI

**Critical Finding**: None of these static methods are called by daemon or CLI. They exist only for test convenience.

| Name | File:Line | Signature | Returns | D/C/T | Classification | Slimming |
|------|-----------|-----------|---------|-------|----------------|----------|
| `init_project` | service.py:6775 | `(parent_dir, project_name, ...)` | `Path` | 0/0/112 | capability | MOVE_TO_UTILS |
| `get_settings` | service.py:6851 | `()` | `dict` | 0/0/9 | capability | DELETE_UNUSED |
| `get_workflow_service` | service.py:6895 | `()` | `WorkflowService` | 0/0/26 | internal-model-leak | DELETE_UNUSED |
| `run_single_step` | service.py:6906 | `(project_root, calc_selector, ...)` | `RunResultDTO` | 0/0/18 | capability | MERGE_CANDIDATE |
| `get_default_step_params` | service.py:6956 | `(step_type_gen)` | `dict` | 0/0/4 | capability | MERGE_CANDIDATE |
| `resolve_step_type_spec` | service.py:6973 | `(step_type_gen, engine_family)` | `str` | 0/0/0 | helper | DELETE_UNUSED |
| `generate_kpath` | service.py:6995 | `(structure, path_type, ...)` | `dict` | 0/0/6 | capability | MOVE_TO_SERVICE |
| `create_demo_project` | service.py:7025 | `(demo_name, parent_dir)` | `Path` | 0/0/32 | capability | KEEP |
| `list_demo_projects` | service.py:7099 | `()` | `list[dict]` | 0/0/13 | capability | KEEP |
| `init_pseudo_dirs` | service.py:7157 | `()` | `dict` | 0/0/11 | capability | BUNDLE_CANDIDATE |
| `list_pseudo_libraries` | service.py:7171 | `()` | `list[dict]` | 0/0/0 | capability | BUNDLE_CANDIDATE |
| `get_library_status` | service.py:7184 | `(library_id)` | `dict` | 0/0/11 | capability | BUNDLE_CANDIDATE |
| `install_pseudo_library` | service.py:7200 | `(library_id, variants, ...)` | `dict` | 0/0/0 | capability | BUNDLE_CANDIDATE |
| `remove_pseudo_library` | service.py:7247 | `(library_id, variants)` | `dict` | 0/0/0 | capability | BUNDLE_CANDIDATE |
| `repair_pseudo_library` | service.py:7264 | `(library_id, variants)` | `dict` | 0/0/1 | capability | BUNDLE_CANDIDATE |
| `compute_store_size` | service.py:7281 | `()` | `dict` | 0/0/8 | capability | BUNDLE_CANDIDATE |
| `is_pseudo_archive_installed` | service.py:7293 | `(asset_name, expected_sha256)` | `bool` | 0/0/0 | helper | BUNDLE_CANDIDATE |
| `install_pseudo_archive` | service.py:7309 | `(asset_url, asset_name, ...)` | `dict` | 0/0/10 | capability | BUNDLE_CANDIDATE |
| `install_sssp_from_seed` | service.py:7347 | `(library_id, seed_dir)` | `dict` | 0/0/0 | capability | BUNDLE_CANDIDATE |
| `install_all_sssp_from_seed` | service.py:7370 | `(seed_dir)` | `dict` | 0/0/0 | capability | BUNDLE_CANDIDATE |
| `download_sssp_library` | service.py:7389 | `(library_id, variants)` | `dict` | 0/0/21 | capability | BUNDLE_CANDIDATE |
| `download_all_sssp` | service.py:7423 | `()` | `dict` | 0/0/15 | capability | BUNDLE_CANDIDATE |
| `import_seed_archives` | service.py:7451 | `(archives)` | `dict` | 0/0/10 | capability | BUNDLE_CANDIDATE |

**Recommendation**: 14 of these 23 static methods relate to pseudo library management. They should be consolidated into a single `PseudoLibrary` nested accessor.

---

### 1.3 Nested Service Methods (88 total)

#### Analysis Domain (17)

| Name | Accessor | D/C/T | Classification | Slimming |
|------|----------|-------|----------------|----------|
| `get_summary` | analysis | 0/0/14 | capability | KEEP (future) |
| `list_properties` | analysis | 0/0/4 | capability | KEEP (future) |
| `get_property_ref` | analysis | 0/0/2 | capability | KEEP (future) |
| `load_artifact` | analysis | 0/0/18 | capability | KEEP (future) |
| `analyze_band` | analysis | 0/1/4 | capability | KEEP |
| `analyze_dos` | analysis | 0/1/0 | capability | KEEP |
| `get_band_structure_data` | analysis | 1/0/26 | capability | KEEP |
| `get_scf_convergence_data` | analysis | 1/0/4 | capability | KEEP |
| `list_step_artifacts` | analysis | 1/0/23 | capability | KEEP |
| `read_step_artifact_text` | analysis | 1/0/28 | capability | KEEP |
| `analyze_scf` | analysis | 0/1/0 | capability | KEEP |
| `ensure_analysis` | analysis | 1/0/5 | capability | KEEP |
| `get_dos_data` | analysis | 1/0/15 | capability | KEEP |
| `get_reference_analysis` | analysis | 1/0/17 | capability | KEEP |
| `find_band_files` | analysis | 0/0/0 | helper | DELETE_UNUSED |
| `get_relax_final_structure_preview` | analysis | 1/0/12 | capability | KEEP |

#### Structure Domain (12)

| Name | Accessor | D/C/T | Classification | Slimming |
|------|----------|-------|----------------|----------|
| `get` | structure | 2/4/- | capability | KEEP |
| `list` | structure | 2/1/- | capability | KEEP |
| `get_atoms` | structure | 0/0/3 | capability | KEEP (Jupyter) |
| `require_ref` | structure | 1/12/- | capability | KEEP |
| `visualize` | structure | 0/0/21 | capability | KEEP |
| `import_file` | structure | 1/0/62 | capability | KEEP |
| `get_vis_data` | structure | 1/0/7 | capability | KEEP |
| `update_meta` | structure | 1/0/14 | capability | KEEP |
| `can_delete` | structure | 1/0/28 | capability | KEEP |
| `delete` | structure | 1/0/225 | capability | KEEP |
| `promote_relax_structure` | structure | 1/0/30 | capability | KEEP |
| `save_relax_final_structure` | structure | 1/0/15 | capability | KEEP |

#### Calculation Domain (26)

| Name | Accessor | D/C/T | Classification | Slimming |
|------|----------|-------|----------------|----------|
| `get` | calculation | 2/8/- | capability | KEEP |
| `list` | calculation | 2/1/- | capability | KEEP |
| `require_ref` | calculation | 1/20/- | capability | KEEP |
| `require_step_ref` | calculation | 1/10/- | capability | KEEP |
| `resolve_enclosing_path` | calculation | 0/6/- | capability | KEEP |
| `get_step` | calculation | 0/0/98 | capability | KEEP |
| `get_step_detail` | calculation | 2/0/43 | capability | KEEP |
| `list_steps` | calculation | 1/0/9 | capability | KEEP |
| `get_effective_params` | calculation | 0/0/3 | capability | KEEP (future) |
| `create` | calculation | 0/0/701 | capability | KEEP |
| `update_meta` | calculation | 0/0/- | capability | KEEP |
| `update_step_params` | calculation | 1/0/69 | capability | KEEP |
| `duplicate` | calculation | 0/0/43 | capability | KEEP |
| `can_delete` | calculation | 2/0/- | capability | KEEP |
| `delete` | calculation | 1/2/- | capability | KEEP |
| `get_detail` | calculation | 2/0/2 | capability | KEEP |
| `set_structure` | calculation | 1/0/2 | capability | KEEP |
| `get_common_cards` | calculation | 1/0/19 | capability | KEEP |
| `add_step` | calculation | 1/0/135 | capability | KEEP |
| `remove_step` | calculation | 1/0/8 | capability | KEEP |
| `rename` | calculation | 1/0/125 | capability | KEEP |
| `set_common_card` | calculation | 1/0/21 | capability | KEEP |
| `get_step_pseudo_mapping` | calculation | 1/0/- | capability | KEEP |
| `set_step_pseudo_mapping` | calculation | 1/0/- | capability | KEEP |
| `reset_step_params` | calculation | 1/0/- | capability | KEEP |
| `reorder_steps` | calculation | 1/0/- | capability | KEEP |
| `import_step_from_qe_input` | calculation | 1/0/- | capability | KEEP |
| `get_pseudo_mapping` | calculation | 1/0/- | capability | KEEP |
| `update_species_map` | calculation | 1/0/- | capability | KEEP |
| `configure_species_map` | calculation | 0/1/- | capability | KEEP |

#### Run Domain (4)

| Name | Accessor | D/C/T | Classification | Slimming |
|------|----------|-------|----------------|----------|
| `run_calculation` | run | 1/1/- | capability | KEEP |
| `run_step` | run | 1/1/- | capability | KEEP |
| `cancel` | run | 0/0/- | capability | KEEP (future) |
| `preflight` | run | 1/0/- | capability | KEEP |

#### Project Domain (16)

| Name | Accessor | D/C/T | Classification | Slimming |
|------|----------|-------|----------------|----------|
| `get_config` | project | 6/18/- | capability | KEEP |
| `update_config` | project | 0/10/- | capability | KEEP |
| `get_species_map` | project | 0/0/- | capability | DELETE_UNUSED |
| `get_potential_map` | project | 0/0/- | capability | DELETE_UNUSED |
| `build_resource_index` | project | 3/5/- | capability | KEEP |
| `collect_slugs` | project | 0/1/- | capability | KEEP |
| `apply_structure_rename` | project | 0/2/- | capability | KEEP |
| `apply_calculation_rename` | project | 0/2/- | capability | KEEP |
| `import_pseudo_files` | project | 1/0/- | capability | KEEP |
| `get_summary` | project | 2/0/- | capability | KEEP |
| `init_calculation` | project | 1/0/- | capability | KEEP |
| `analyze_pseudo_effects` | project | 1/0/- | capability | KEEP |
| `materialize_pseudo_file` | project | 1/0/- | capability | KEEP |
| `get_pseudo_options` | project | 1/0/- | capability | KEEP |

#### Engine Domain (4)

| Name | Accessor | D/C/T | Classification | Slimming |
|------|----------|-------|----------------|----------|
| `list` | engine | 0/0/- | capability | KEEP (future) |
| `get_info` | engine | 0/0/- | capability | KEEP (future) |
| `list_step_types` | engine | 0/0/- | capability | KEEP (future) |
| `validate_installation` | engine | 0/0/- | capability | KEEP (future) |

#### History Domain (9)

| Name | Accessor | D/C/T | Classification | Slimming |
|------|----------|-------|----------------|----------|
| `get_timeline` | history | 1/0/- | capability | KEEP |
| `get_run_revision` | history | 1/0/- | capability | KEEP |
| `list_runs` | history | 1/0/- | capability | KEEP |
| `pin_analysis` | history | 1/0/- | capability | KEEP |
| `can_pin` | history | 1/0/- | capability | KEEP |
| `get_pin_data` | history | 1/0/- | capability | KEEP |
| `get_latest_run_for_step` | history | 1/0/- | capability | KEEP |
| `delete` | history | 1/0/- | capability | KEEP |

---

### 1.4 DTOs (11 total)

| Name | File | Classification | Slimming |
|------|------|----------------|----------|
| `BaseDTO` | types/base.py | base class | KEEP |
| `MetaDTO` | types/common.py | helper | KEEP |
| `CandidateSummary` | types/common.py | data | KEEP |
| `ErrorDTO` | types/error.py | error | KEEP |
| `StructureDTO` | types/structure.py | data | KEEP |
| `CalculationDTO` | types/calculation.py | data | KEEP |
| `CalculationRefDTO` | types/calculation.py | reference | KEEP |
| `StepDTO` | types/calculation.py | data | KEEP |
| `RunResultDTO` | types/run.py | data | KEEP |
| `AnalysisRefDTO` | types/analysis.py | reference | KEEP |
| `AnalysisSummaryDTO` | types/analysis.py | data | KEEP |

---

### 1.5 Errors (10 total)

| Name | File:Line | Classification | Slimming |
|------|-----------|----------------|----------|
| `APIError` | errors.py:15 | base | KEEP |
| `NotFoundError` | errors.py:74 | common | KEEP |
| `AmbiguousError` | errors.py:80 | common | KEEP |
| `ValidationError` | errors.py:88 | common | KEEP |
| `ConflictError` | errors.py:123 | common | KEEP |
| `EngineError` | errors.py:158 | common | KEEP |
| `ConfigError` | errors.py:200 | common | KEEP |
| `FilesystemError` | errors.py:237 | common | KEEP |
| `InternalError` | errors.py:266 | common | KEEP |

---

## 2. Unused Entrypoints Review

### 2.1 Service Methods Marked UNUSED (but tested)

| Entrypoint | Refs | Justification | Risk |
|------------|------|---------------|------|
| `Analysis.get_summary` | t=14 | Scaffolding for analysis summary UI | LOW - tested |
| `Analysis.list_properties` | t=4 | Scaffolding for property browser | LOW - tested |
| `Analysis.get_property_ref` | t=2 | Scaffolding for lazy loading | LOW - tested |
| `Analysis.load_artifact` | t=18 | Scaffolding for lazy loading | LOW - tested |
| `Analysis.find_band_files` | t=0 | **NO TESTS, no daemon/CLI usage** | HIGH - DELETE |
| `Structure.get_atoms` | t=3 | Jupyter-only feature (documented) | LOW - tested |
| `Calculation.get_effective_params` | t=3 | Scaffolding for params inspector | LOW - tested |
| `Project.get_species_map` | t=0 | **NO TESTS, redundant with get_config** | HIGH - DELETE |
| `Project.get_potential_map` | t=0 | **NO TESTS, redundant with get_config** | HIGH - DELETE |
| `Engine.list` | t=0 | **NO TESTS** (but `list_step_types` tested) | MEDIUM |
| `Engine.get_info` | t=0 | **NO TESTS** | MEDIUM |
| `Engine.list_step_types` | t=varies | Tested via capability tests | LOW - tested |
| `Engine.validate_installation` | t=varies | Tested via capability tests | LOW - tested |
| `Run.cancel` | t=0 | **NO TESTS**, daemon-only future | MEDIUM |

**Immediate deletion candidates** (no tests, no daemon/CLI):
- `Analysis.find_band_files` (use `find_band_analysis_files` from utils instead)
- `Project.get_species_map` (use `get_config().get("species_map", {})`)
- `Project.get_potential_map` (use `get_config().get("potential_map", {})`)

**Expected delta**: -3

---

### 2.2 Static Methods - ALL Unused by Daemon/CLI

**Evidence**: Zero grep matches for `QVService.` in daemon/ or cli/ directories.

All 23 static methods are only used in tests. This is an architectural issue:

1. **Project-agnostic operations** (like `init_project`, `create_demo_project`) don't need a project root, so static makes sense BUT should be utils functions.

2. **Pseudo library operations** (14 methods) are project-agnostic BUT should be a dedicated `PseudoLibrary` service or consolidated into fewer methods.

3. **Step/workflow utilities** (like `get_default_step_params`, `resolve_step_type_spec`) should be in utils or merged into calculation accessor.

---

## 3. Static Methods Review (23)

| Method | Why Static? | Better Location | Action |
|--------|-------------|-----------------|--------|
| `init_project` | No project exists yet | utils or standalone | MOVE_TO_UTILS |
| `get_settings` | Global settings | utils | DELETE or MOVE |
| `get_workflow_service` | Internal | DELETE | DELETE |
| `run_single_step` | Standalone run | `run.run_step` | MERGE |
| `get_default_step_params` | No project needed | utils or calculation accessor | MERGE |
| `resolve_step_type_spec` | No project needed | utils | DELETE (unused) |
| `generate_kpath` | Structure-only | `structure.generate_kpath` | MOVE |
| `create_demo_project` | No project exists | KEEP static | KEEP |
| `list_demo_projects` | No project exists | KEEP static | KEEP |
| `init_pseudo_dirs` | Global operation | `PseudoLibrary` accessor | BUNDLE |
| `list_pseudo_libraries` | Global operation | `PseudoLibrary.list` | BUNDLE |
| `get_library_status` | Global operation | `PseudoLibrary.get_status` | BUNDLE |
| `install_pseudo_library` | Global operation | `PseudoLibrary.install` | BUNDLE |
| `remove_pseudo_library` | Global operation | `PseudoLibrary.remove` | BUNDLE |
| `repair_pseudo_library` | Global operation | `PseudoLibrary.repair` | BUNDLE |
| `compute_store_size` | Global operation | `PseudoLibrary.compute_size` | BUNDLE |
| `is_pseudo_archive_installed` | Global operation | DELETE (internal) | DELETE |
| `install_pseudo_archive` | Global operation | `PseudoLibrary.install_archive` | BUNDLE |
| `install_sssp_from_seed` | Global operation | `PseudoLibrary.install_from_seed` | BUNDLE |
| `install_all_sssp_from_seed` | Global operation | `PseudoLibrary.install_all_from_seed` | BUNDLE |
| `download_sssp_library` | Global operation | `PseudoLibrary.download` | BUNDLE |
| `download_all_sssp` | Global operation | `PseudoLibrary.download_all` | BUNDLE |
| `import_seed_archives` | Global operation | `PseudoLibrary.import_archives` | BUNDLE |

---

## 4. Consolidation Opportunities

### 4.1 Pseudo Library Cluster (HIGH IMPACT)

**Current entrypoints (14 static + 8 utils = 22)**:

Static methods:
- `init_pseudo_dirs`, `list_pseudo_libraries`, `get_library_status`
- `install_pseudo_library`, `remove_pseudo_library`, `repair_pseudo_library`
- `compute_store_size`, `is_pseudo_archive_installed`, `install_pseudo_archive`
- `install_sssp_from_seed`, `install_all_sssp_from_seed`
- `download_sssp_library`, `download_all_sssp`, `import_seed_archives`

Utils functions:
- `get_pseudo_config`, `set_pseudo_config`, `validate_pseudo_config_dict`
- `list_installed_sssp`, `list_seed_archives`, `check_archives_status`
- `load_manifest_archives`, `search_legacy_pseudos`

**Proposed minimal API (1 static accessor)**:

```python
class QVService:
    @staticmethod
    def pseudo_library() -> PseudoLibraryService:
        """Get pseudo library service (project-agnostic)."""

class PseudoLibraryService:
    def get_status() -> PseudoLibraryStatusDTO  # replaces 8+ getters
    def install(library_id, variants=None) -> dict
    def remove(library_id, variants=None) -> dict
    def repair(library_id, variants=None) -> dict
    def download(library_id, variants=None) -> dict
    def import_archives(archives) -> dict
    def search_legacy(element) -> dict
```

**Expected delta**: 22 → 7 = **-15 entrypoints**

**Migration scope**: ~30 daemon calls, ~0 CLI calls, ~100 test calls

**Risks**: Significant refactor; need new DTO for status

---

### 4.2 QE Engine Detection Cluster (MEDIUM IMPACT)

**Current entrypoints (7 utils)**:
- `detect_qe`, `list_qe_engines`, `discover_qe_engines`, `set_qe_engine`
- `get_qe_home`, `get_environment_info`, `create_default_registry`

**Proposed minimal API (2)**:

```python
# utils
def get_qe_status() -> QEStatusDTO  # replaces detect_qe, list_qe_engines, discover_qe_engines, get_environment_info
def set_qe_engine(bin_dir: str | None) -> QEStatusDTO  # keep
```

**Expected delta**: 7 → 2 = **-5 entrypoints**

**Migration scope**: ~20 daemon calls

**Risks**: Need new `QEStatusDTO`; callers need to access status fields

---

### 4.3 Presets/Precision Cluster (MEDIUM IMPACT)

**Current entrypoints (7 utils)**:
- `apply_presets_to_step`, `get_preset_catalog`, `detect_workflow_type`
- `get_step_preset_footprints`, `resolve_precision_context`
- `create_precision_advisor`, `detect_presets_from_calculation`

**Proposed minimal API (2)**:

```python
def apply_presets_to_step(step_spec, presets, ...) -> dict  # keep
def get_preset_context(calculation_dir) -> PresetContextDTO  # replaces 5 getters
```

Where `PresetContextDTO` contains:
- `catalog: dict`
- `workflow_type: str`
- `footprints: dict`
- `precision_context: dict`
- `detected_presets: dict`

**Expected delta**: 7 → 2 = **-5 entrypoints**

**Migration scope**: ~15 daemon calls

---

### 4.4 Online Search Cluster (LOW IMPACT)

**Current entrypoints (5 utils)**:
- `search_online_structures`, `fetch_structure_from_optimade`
- `score_candidate`, `extract_provenance`, `OnlineStructureCache`

**Proposed minimal API (2)**:

```python
def search_online_structures(query, sources, ...) -> list[CandidateSummary]  # keep
# score_candidate, extract_provenance are internal - DELETE from API
# OnlineStructureCache stays as class re-export
```

**Expected delta**: 5 → 2 = **-3 entrypoints** (move internals out of API)

---

### 4.5 QE Input Utilities Cluster (LOW IMPACT)

**Current entrypoints (6 utils)**:
- `detect_runtime_control_keys`, `needs_alat_preservation`, `extract_alat_bohr`
- `write_qe_input_file`, `apply_card_overrides_to_qe_input`, `apply_species_overrides_to_qe_input`

These are CLI-only helpers for QE input manipulation. Could bundle into:

```python
def get_qe_input_info(qe_input) -> QEInputInfoDTO  # replaces 3 inspection functions
def apply_qe_input_overrides(qe_input, card_overrides, species_overrides) -> None  # replaces 2
```

**Expected delta**: 6 → 3 = **-3 entrypoints**

---

### 4.6 Structure Visualization Cluster (LOW IMPACT)

**Current entrypoints (2 utils)**:
- `visualize_structure`, `build_structure_vis_payload`

Both do similar things. Keep only one.

**Expected delta**: 2 → 1 = **-1 entrypoint**

---

### 4.7 Calculation Discovery Helpers (LOW IMPACT)

**Current entrypoints (4 utils)**:
- `detect_engine_for_calculation`, `find_calculation_raw_dir`
- `find_calculation_results_dir`, `compute_io_dir_from_calculation_model`

These should be service methods or embedded in CalculationDTO.

**Expected delta**: 4 → 0 = **-4 entrypoints** (embed in DTO/service)

---

### 4.8 Template Operations (LOW IMPACT)

**Current entrypoints (3 utils)**:
- `list_calculation_templates`, `copy_calculation_template`, `copy_structure_template`

Should be project accessor methods.

**Expected delta**: 3 → 0 as utils = **-3 entrypoints** (move to `project.templates.*`)

---

### 4.9 Internal Model Leaks (HIGH PRIORITY)

These functions return internal kernel types, violating API isolation:

| Function | Returns | Action |
|----------|---------|--------|
| `load_calculation` | `CalculationModel` | DELETE (use `svc.calculation.get`) |
| `save_calculation` | via `CalculationModel` | DELETE (use `svc.calculation.update_*`) |
| `create_default_registry` | `EngineRegistry` | DELETE or MOVE to internal |
| `get_journal` | `Journal` | DELETE (use history accessor) |
| `create_blob_store` | `BlobStore` | DELETE or MOVE to internal |
| `create_precision_advisor` | `PrecisionAdvisor` | DELETE (embed in presets) |
| `get_workflow_service` | `WorkflowService` | DELETE |

**Expected delta**: -7 entrypoints

---

## 5. Prioritized Top-10 Slimming Backlog

| Priority | Action | Expected Delta | Rationale |
|----------|--------|----------------|-----------|
| **1** | Delete unused no-test service methods (`find_band_files`, `get_species_map`, `get_potential_map`) | **-3** | Zero usage, zero tests, immediate deletion |
| **2** | Delete internal model leak functions (`load_calculation`, `save_calculation`, `get_journal`, `create_blob_store`, `create_default_registry`, `create_precision_advisor`, `get_workflow_service`) | **-7** | Violate API isolation, have DTO/service equivalents |
| **3** | Bundle pseudo library static methods into `PseudoLibrary` accessor | **-12** | 14 statics → 6 methods on accessor |
| **4** | Bundle pseudo config utils into pseudo library service | **-6** | 8 utils → 2 methods |
| **5** | Consolidate QE engine detection utils | **-5** | 7 → 2 with status DTO |
| **6** | Consolidate presets/precision utils | **-5** | 7 → 2 with context DTO |
| **7** | Move template operations to project accessor | **-3** | 3 utils → project.templates |
| **8** | Embed calculation discovery in DTO/service | **-4** | 4 utils → embedded |
| **9** | Delete unused static methods (`get_settings`, `resolve_step_type_spec`, `is_pseudo_archive_installed`) | **-3** | Zero usage |
| **10** | Merge online search internals | **-2** | Hide score_candidate, extract_provenance |

**Total potential reduction**: ~50 entrypoints (213 → ~163)

---

## Appendix: Audit Tool Output

```
============================================================
API SURFACE AUDIT SUMMARY
============================================================

TOTAL ENTRYPOINTS: 213

BY CATEGORY:
  api_init            :    2
  dtos                :   11
  errors              :   10
  service_nested      :   88
  service_static      :   23
  utils               :   79

USAGE COVERAGE:
  Daemon only:        108
  CLI only:            45
  Both daemon+CLI:     36
  UNUSED (0 refs):     24
============================================================
```

---

**End of Report**
