"""RPC method introspection utilities."""

import inspect
from dataclasses import dataclass
from io import StringIO
from typing import Any

from quantumvitas.daemon.server import QVDaemon


@dataclass
class RPCMethodInfo:
    """Metadata about an RPC method."""
    name: str
    handler_name: str
    signature: inspect.Signature
    docstring: str | None
    required_params: list[str]
    optional_params: list[str]


def get_all_rpc_methods() -> list[RPCMethodInfo]:
    """
    Enumerate all RPC methods from daemon handler registry.

    Returns:
        List of RPCMethodInfo objects sorted by name.
    """
    daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    methods = []

    for name, handler in daemon._handlers.items():
        sig = inspect.signature(handler)
        doc = inspect.getdoc(handler)

        # Parse handler docstrings for payload requirements
        required_params = []
        optional_params = []

        if doc:
            # Extract from "Payload:" section in docstring
            lines = doc.split('\n')
            in_payload = False
            for line in lines:
                stripped = line.strip()
                if stripped.lower().startswith('payload:'):
                    in_payload = True
                    continue
                if in_payload:
                    if stripped.startswith('-') or stripped.startswith('*'):
                        # Parse "- param_name: type - description"
                        if ':' in stripped:
                            param_part = stripped.lstrip('-* ').split(':')[0].strip()
                            if '(optional)' in stripped.lower():
                                optional_params.append(param_part)
                            else:
                                required_params.append(param_part)
                    elif stripped and not stripped.startswith(' '):
                        # End of Payload section
                        in_payload = False

        methods.append(RPCMethodInfo(
            name=name,
            handler_name=handler.__name__,
            signature=sig,
            docstring=doc,
            required_params=required_params,
            optional_params=optional_params,
        ))

    return sorted(methods, key=lambda m: m.name)


def get_method_categories() -> dict[str, list[str]]:
    """
    Categorize RPC methods by functional area.

    Returns:
        Dict mapping category name to list of method names.
    """
    # Categories derived from server.py comments
    return {
        "system": ["ping", "shutdown"],
        "environment": [
            "detect_qe", "get_env_info", "list_qe_engines",
            "set_qe_engine", "set_log_level", "set_debug_resolution", "get_debug_resolution",
            # Generic engine RPCs (replace former QE-specific RPCs)
            "list_engine_families", "list_step_palette", "list_engine_ui_parameters",
            "list_engine_parameter_metadata", "set_engine_family",
        ],
        "pseudo_config": [
            "get_pseudo_config", "set_pseudo_config", "validate_pseudo_config",
            "init_pseudo_dirs", "install_seed_to_store", "list_installed_sssp",
            "list_seed_archives", "download_sssp_library", "download_all_sssp",
            "resolve_project_pseudo_provenance", "import_seed_archives",
            "list_pseudo_archives_status", "install_pseudo_archive",
            "analyze_project_pseudo_effects",
        ],
        "library_manager": [
            "list_libraries", "get_library_status", "install_library",
            "remove_library", "repair_library", "compute_store_size",
        ],
        "project": [
            "get_project_summary", "list_structures", "list_calculations",
            "find_project_root", "rebuild_project_registry", "create_project",
        ],
        "structure": [
            "import_structure", "structure_search_online",
            "structure_get_online_candidate", "structure_import_online_candidate",
            "rename_structure", "delete_structure", "can_delete_structure",
        ],
        "calculation": [
            "list_calculation_templates", "create_calculation", "rename_calculation",
            "delete_calculation", "can_delete_calculation", "get_calculation_detail",
            "reorder_calculation_steps", "add_step_to_calculation",
            "change_calculation_structure",
            "get_calculation_pseudo_mapping", "update_calculation_species_map",
            "get_pseudo_options_for_calculation", "materialize_pseudo_file",
        ],
        "step": [
            "get_step_detail", "update_step_params", "reset_step_params",
            "get_common_cards", "set_common_card", "get_pseudo_mapping",
            "set_pseudo_mapping", "import_pseudo_files", "search_legacy_pseudos",
            "download_pseudo_by_filename", "download_pseudo_candidate",
            "get_relax_final_structure_preview", "save_relax_final_structure",
            "promote_relax_structure", "delete_step",
        ],
        "presets": [
            "get_preset_catalog", "detect_presets", "detect_workflow",
            "detect_workflow_for_calculation", "apply_presets_to_step",
            "apply_presets_to_calculation", "get_step_preset_footprints",
        ],
        "preflight": ["preflight_check"],
        "demo": ["create_demo_project", "list_demo_projects"],
        "analysis": [
            "get_structure_vis", "get_reference_analysis",
            "list_step_artifacts", "read_step_artifact_text",
            "list_raw_files", "read_raw_file",
            "get_step_digest", "get_analysis", "get_analysis_snapshot",
        ],
        "visualization_dev": ["list_wannier_3d_fixtures", "compile_fixture_volume"],
        "jobs": [
            "run_calculation", "run_step", "run_single_step", "get_job_status",
            "get_job_logs", "list_jobs", "job_counts", "cancel_job",
        ],
        "journal": ["list_journal_entries", "get_journal_entry"],
        "history": [
            "get_project_history", "get_run_revision", "list_project_runs",
            "pin_analysis_to_history", "can_pin_to_run", "get_pin_data",
            "get_latest_run_for_step", "delete_project_history",
        ],
        "workflow": ["list_workflow_templates", "instantiate_workflow"],
    }


def print_method_inventory():
    """Print formatted inventory of all RPC methods."""
    methods = get_all_rpc_methods()
    categories = get_method_categories()

    print(f"Total RPC methods: {len(methods)}")
    print("\n## By Category:\n")

    covered = set()
    for cat, names in categories.items():
        print(f"### {cat} ({len(names)} methods)")
        for name in names:
            print(f"  - {name}")
            covered.add(name)
        print()

    # Find uncategorized
    all_names = {m.name for m in methods}
    uncategorized = all_names - covered
    if uncategorized:
        print(f"### UNCATEGORIZED ({len(uncategorized)} methods)")
        for name in sorted(uncategorized):
            print(f"  - {name}")


if __name__ == "__main__":
    print_method_inventory()
