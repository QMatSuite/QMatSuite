"""Minimal payload generators for RPC methods."""

import os
from pathlib import Path
from typing import Any


def get_minimal_payload(method_name: str, project_root: Path | None = None, tmp_path: Path | None = None) -> dict[str, Any] | None:
    """
    Generate minimal payload for an RPC method.

    Returns:
        Payload dict, or None if method requires a recipe (complex prerequisites).
    """
    # Stateless methods (no payload needed)
    STATELESS = {
        "ping": {},
        "get_env_info": {},
        "list_qe_engines": {},
        "get_debug_resolution": {},
        "get_pseudo_config": {},
        "list_seed_archives": {},
        "list_libraries": {},
        "list_pseudo_archives_status": {},
        "compute_store_size": {},
        "list_calculation_templates": {},
        "get_preset_catalog": {},
        "list_demo_projects": {},
        "list_workflow_templates": {},
        "list_wannier_3d_fixtures": {},
        "job_counts": {},
        "list_jobs": {},
        # M4: Generic engine RPCs
        "list_engine_families": {},
        # Additional stateless/near-stateless methods
        "detect_qe": {"search_paths": []},  # Empty list uses default PATH search
    }

    if method_name in STATELESS:
        return STATELESS[method_name]

    # Methods requiring project_root only
    PROJECT_ONLY = {
        "get_project_summary",
        "list_structures",
        "list_calculations",
        "list_journal_entries",
        "get_project_history",
        "list_project_runs",
    }

    if method_name in PROJECT_ONLY:
        if project_root is None:
            return None  # Needs recipe
        return {"project_root": str(project_root)}

    # Methods with simple parameters
    SIMPLE_PARAMS = {
        "set_log_level": {"level": "INFO"},
        "set_debug_resolution": {"enabled": False},
        "set_qe_engine": {"bin_dir": None},  # None means use internal QE
        # M4: Generic engine RPCs
        "list_step_palette": {"engine_family": None},  # UNDECIDED state
        "list_engine_ui_parameters": {"engine_family": "qe", "step_type_gen": "scf"},
        "list_engine_parameter_metadata": {"engine_family": "qe", "operation": "list_categories"},
    }

    if method_name in SIMPLE_PARAMS:
        return SIMPLE_PARAMS[method_name]

    # find_project_root needs isolation: use tmp_path if provided, otherwise skip
    # This ensures deterministic results in parallel test runs
    if method_name == "find_project_root":
        if tmp_path is not None:
            # Use xdist worker ID for extra uniqueness
            worker_id = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
            search_dir = tmp_path / f"find_root_{worker_id}"
            search_dir.mkdir(parents=True, exist_ok=True)
            return {"cwd": str(search_dir)}
        # No tmp_path: return None to indicate this needs a recipe/fixture
        return None

    # Complex methods - require recipes
    return None


def get_methods_needing_recipes() -> set[str]:
    """
    Return set of method names that require explicit recipes.

    These methods have complex prerequisites:
    - Require existing resources (calculations, structures, steps)
    - Perform mutations that need setup/teardown
    - Require external state (QE installed, network access)
    """
    return {
        # Mutations requiring existing resources
        "rename_structure", "delete_structure", "can_delete_structure",
        "rename_calculation", "delete_calculation", "can_delete_calculation",
        "get_calculation_detail", "reorder_calculation_steps",
        "add_step_to_calculation",
        "change_calculation_structure", "get_calculation_pseudo_mapping",
        "update_calculation_species_map", "get_pseudo_options_for_calculation",
        "materialize_pseudo_file", "delete_step",
        
        # Step operations requiring calculation context
        "get_step_detail", "update_step_params", "reset_step_params",
        "get_common_cards", "set_common_card", "get_pseudo_mapping",
        "set_pseudo_mapping", "get_relax_final_structure_preview",
        "save_relax_final_structure", "promote_relax_structure",
        
        # Preset operations requiring step context
        "detect_presets", "detect_workflow_for_calculation",
        "apply_presets_to_step", "apply_presets_to_calculation",
        "get_step_preset_footprints",
        
        # Analysis requiring completed runs
        "get_structure_vis", "get_reference_analysis",
        "list_step_artifacts", "read_step_artifact_text",
        
        # Job operations requiring running jobs
        "run_calculation", "run_step", "run_single_step",
        "get_job_status", "get_job_logs", "cancel_job",
        
        # History operations requiring existing runs
        "get_run_revision", "pin_analysis_to_history",
        "can_pin_to_run", "get_pin_data", "get_latest_run_for_step",
        "delete_project_history", "get_journal_entry",
        
        # Pseudo operations requiring network/files
        "set_pseudo_config", "validate_pseudo_config", "init_pseudo_dirs",
        "install_seed_to_store", "download_sssp_library", "download_all_sssp",
        "resolve_project_pseudo_provenance", "import_seed_archives",
        "install_pseudo_archive", "analyze_project_pseudo_effects",
        "import_pseudo_files", "search_legacy_pseudos",
        "download_pseudo_by_filename", "download_pseudo_candidate",
        
        # Library operations requiring network
        "get_library_status", "install_library", "remove_library", "repair_library",
        
        # Project mutations
        "create_project", "import_structure", "create_calculation",
        "rebuild_project_registry",
        
        # Online search requiring network
        "structure_search_online", "structure_get_online_candidate",
        "structure_import_online_candidate",
        "structure_list_providers", "structure_update_online_sources",
        
        # Preflight requiring calculation context
        "preflight_check",
        
        # Demo requiring write access
        "create_demo_project",
        
        # Dev endpoints
        "compile_fixture_volume",
        
        # System mutations
        "shutdown",

        # Workflow requiring calculation context
        "detect_workflow", "instantiate_workflow",
    }
