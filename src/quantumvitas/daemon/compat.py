"""
Backward compatibility layer for RPC methods.

Implements v0 (0873ebf) compatibility at the daemon RPC boundary:
- adapt_payload(): Transform old payloads to new format
- shape_response(): Transform new responses to old format

This ensures UI (unchanged since 0873ebf) works with current HEAD.
"""

from typing import Any, Dict, Optional
import copy


# -----------------------------------------------------------------------------
# Payload Adapters - Transform old payloads to new format
# -----------------------------------------------------------------------------

def _adapt_change_calculation_structure(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Accept 'structure' for 'new_structure'."""
    if "structure" in payload and "new_structure" not in payload:
        payload = dict(payload)
        payload["new_structure"] = payload.pop("structure")
    return payload


def _adapt_delete_structure(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Add selector from structure_id if missing."""
    if "selector" not in payload and "structure_id" in payload:
        payload = dict(payload)
        payload["selector"] = {"id": payload["structure_id"]}
    return payload


def _adapt_get_structure_vis(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Add selector from structure_id if missing."""
    if "selector" not in payload:
        payload = dict(payload)
        if "structure_id" in payload:
            payload["selector"] = {"id": payload["structure_id"]}
        elif "structure_name" in payload:
            payload["selector"] = {"name": payload["structure_name"]}
    return payload


def _adapt_instantiate_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Accept 'workflow' for 'workflow_id'."""
    if "workflow" in payload and "workflow_id" not in payload:
        payload = dict(payload)
        payload["workflow_id"] = payload.pop("workflow")
    return payload


def _adapt_detect_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Add calculation_path from project_root and calculation if missing."""
    if "calculation_path" not in payload:
        payload = dict(payload)
        project_root = payload.get("project_root", "")
        calculation = payload.get("calculation", "")
        if project_root and calculation:
            payload["calculation_path"] = f"{project_root}/calculations/{calculation}"
    return payload


def _adapt_reset_step_params(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove calculation_ulid if present (no longer accepted)."""
    if "calculation_ulid" in payload:
        payload = dict(payload)
        payload.pop("calculation_ulid")
    return payload


def _adapt_create_demo_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Provide default target_dir if missing."""
    if "target_dir" not in payload:
        payload = dict(payload)
        # Default to temp directory if not specified
        import tempfile
        payload["target_dir"] = tempfile.gettempdir()
    return payload


def _adapt_list_qe_ui_parameters(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Provide default module if missing."""
    if "module" not in payload:
        payload = dict(payload)
        payload["module"] = "pw.x"  # Default to pw.x
    return payload


def _adapt_get_step_detail(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Add step field from step_slug if missing."""
    if "step" not in payload:
        payload = dict(payload)
        if "step_slug" in payload:
            payload["step"] = payload["step_slug"]
        elif "step_id" in payload:
            payload["step"] = payload["step_id"]
    return payload


def _adapt_rename_calculation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Add selector or calculation_ulid if missing."""
    if "calculation_ulid" not in payload and "selector" not in payload:
        payload = dict(payload)
        if "calculation_id" in payload:
            payload["calculation_ulid"] = payload["calculation_id"]
        elif "calculation_name" in payload or "calculation_slug" in payload:
            payload["selector"] = {
                "name": payload.get("calculation_name"),
                "slug": payload.get("calculation_slug"),
            }
    return payload


def _adapt_rename_structure(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Add selector if missing."""
    if "selector" not in payload:
        payload = dict(payload)
        if "structure_id" in payload:
            payload["selector"] = {"id": payload["structure_id"]}
        elif "structure_name" in payload:
            payload["selector"] = {"name": payload["structure_name"]}
        elif "structure_slug" in payload:
            payload["selector"] = {"slug": payload["structure_slug"]}
    return payload


def _adapt_find_project_root(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Map v0 'cwd' key to v1 'start_dir' key."""
    if "cwd" in payload and "start_dir" not in payload:
        payload = dict(payload)
        payload["start_dir"] = payload.pop("cwd")
    return payload


PAYLOAD_ADAPTERS: Dict[str, callable] = {
    "change_calculation_structure": _adapt_change_calculation_structure,
    "delete_structure": _adapt_delete_structure,
    "get_structure_vis": _adapt_get_structure_vis,
    "instantiate_workflow": _adapt_instantiate_workflow,
    "detect_workflow": _adapt_detect_workflow,
    "reset_step_params": _adapt_reset_step_params,
    "create_demo_project": _adapt_create_demo_project,
    "list_qe_ui_parameters": _adapt_list_qe_ui_parameters,
    "get_step_detail": _adapt_get_step_detail,
    "rename_calculation": _adapt_rename_calculation,
    "rename_structure": _adapt_rename_structure,
    "find_project_root": _adapt_find_project_root,
}


def adapt_payload(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform old (v0) payloads to new format.

    Args:
        method: RPC method name
        payload: Original payload dict

    Returns:
        Adapted payload dict (may be same object if no changes)
    """
    adapter = PAYLOAD_ADAPTERS.get(method)
    if adapter:
        return adapter(payload)
    return payload


# -----------------------------------------------------------------------------
# Response Shapers - Transform new responses to old format
# -----------------------------------------------------------------------------

def _shape_create_calculation(response: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure n_steps is int (0 if None)."""
    if response.get("n_steps") is None:
        response = dict(response)
        response["n_steps"] = 0
    return response


def _shape_get_pseudo_config(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add compat fields for v0."""
    response = dict(response)
    # Add v0 fields from v1 equivalents or defaults
    if "default_store_dir" not in response:
        response["default_store_dir"] = response.get("store_dir", "")
    if "repo_pseudo_dir" not in response:
        # Derive from context or use empty
        response["repo_pseudo_dir"] = ""
    if "default_seed_dir" not in response:
        response["default_seed_dir"] = response.get("seed_dir", "")
    # Remove v1-only fields that v0 didn't have
    response.pop("legacy_tables_base_url", None)
    response.pop("network_pseudo_base_url", None)
    return response


def _map_step_type_to_v0(step_type: str) -> str:
    """Map new step types to v0 format (qe_ prefix)."""
    # Map short types to qe_ prefixed types
    TYPE_MAP = {
        "scf": "qe_scf",
        "nscf": "qe_nscf",
        "bands": "qe_bands",
        "dos": "qe_dos",
        "relax": "qe_relax",
        "vc-relax": "qe_vc_relax",
        "ph": "qe_ph",
        "q2r": "qe_q2r",
        "matdyn": "qe_matdyn",
        "projwfc": "qe_projwfc",
    }
    return TYPE_MAP.get(step_type, step_type)


def _shape_list_journal_entries(response: Dict[str, Any]) -> Dict[str, Any]:
    """Map step types to v0 format."""
    if "entries" not in response:
        return response

    response = copy.deepcopy(response)
    for entry in response.get("entries", []):
        for key in ["before", "after"]:
            if key in entry and "steps" in entry[key]:
                for step in entry[key]["steps"]:
                    if "type" in step:
                        step["type"] = _map_step_type_to_v0(step["type"])
    return response


def _shape_list_demo_projects(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add default fields for v0."""
    if "demos" not in response:
        return response

    response = copy.deepcopy(response)
    for demo in response.get("demos", []):
        # Ensure subtitle has a value (service now returns it, but provide fallback)
        if not demo.get("subtitle"):
            demo["subtitle"] = ""
        if "difficulty" not in demo:
            demo["difficulty"] = "beginner"
        if "recommended_use" not in demo:
            demo["recommended_use"] = "General"
        # Try to derive recommended_analysis from title/name/subtitle/id
        if demo.get("recommended_analysis") is None:
            # Check multiple fields for analysis type hints
            title = demo.get("title", "").lower()
            name = demo.get("name", "").lower()
            subtitle = demo.get("subtitle", "").lower()
            demo_id = demo.get("id", "").lower()
            check_text = f"{title} {name} {subtitle} {demo_id}"
            if "dos" in check_text:
                demo["recommended_analysis"] = "dos"
            elif "band" in check_text:
                demo["recommended_analysis"] = "bands"
            elif "scf" in check_text and "nscf" not in check_text:
                demo["recommended_analysis"] = "scf"
            elif "phonon" in check_text:
                demo["recommended_analysis"] = "scf"
            # Keep None for others (e.g., vc-relax, wannier)
        if not demo.get("description"):
            demo["description"] = f"Demo project: {demo.get('title') or demo.get('name', '')}"
        # v0 required fields (service now returns these, but provide fallback)
        if not demo.get("title"):
            demo["title"] = demo.get("name", demo.get("id", ""))
        if "tags" not in demo:
            demo["tags"] = []
        if "estimated_runtime_scf" not in demo:
            demo["estimated_runtime_scf"] = None
    return response


def _is_ulid(value: str) -> bool:
    """Check if a string looks like a ULID (26 alphanumeric chars starting with 01)."""
    if not value or len(value) != 26:
        return False
    return value.startswith("01") and value.isalnum()


def _derive_step_name_from_type(step_type: str) -> str:
    """Derive semantic step name from step type."""
    # Map qe_ prefixed types back to semantic names
    TYPE_TO_NAME = {
        "qe_scf": "scf",
        "qe_nscf": "nscf",
        "qe_bands": "bands",
        "qe_dos": "dos",
        "qe_relax": "relax",
        "qe_vc_relax": "vc-relax",
        "qe_ph": "ph",
        "qe_q2r": "q2r",
        "qe_matdyn": "matdyn",
        "qe_projwfc": "projwfc",
        "bands_pw": "bands",
    }
    return TYPE_TO_NAME.get(step_type, step_type.replace("qe_", ""))


def _should_derive_step_name(name: str) -> bool:
    """Check if step name should be derived from type (empty or ULID-like)."""
    if not name:
        return True
    return _is_ulid(name)


def _shape_add_step_to_calculation(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add v0 fields to steps."""
    response = copy.deepcopy(response)

    # Add id if missing
    if "id" not in response and "calculation_id" in response:
        response["id"] = response["calculation_id"]
    # v0 required fields at top level
    if "name" not in response:
        response["name"] = response.get("calculation_name", "")
    if "slug" not in response:
        response["slug"] = response.get("calculation_slug", response.get("name", ""))
    if "structure_id" not in response:
        response["structure_id"] = response.get("structure", "")

    # Remove intermediate keys that v0 didn't have
    response.pop("calculation_id", None)
    response.pop("calculation_name", None)
    response.pop("calculation_slug", None)
    response.pop("structure", None)

    # Shape steps - v0 add_step_to_calculation only had: step_id, type, input, reference
    for step in response.get("steps", []):
        if "input" not in step:
            step["input"] = None
        if "reference" not in step:
            step["reference"] = None
        # Normalize step type to v0 format (qe_scf -> scf)
        if "type" in step:
            step["type"] = _derive_step_name_from_type(step["type"])
        # Remove v1-only fields - v0 didn't have name/slug/missing on steps for this method
        step.pop("status", None)
        step.pop("name", None)
        step.pop("slug", None)
        step.pop("missing", None)
        step.pop("step_file", None)
        step.pop("id", None)  # v0 only had step_id, not id
        # Rename step_id to match v0 if needed
        if "step_id" not in step and "id" in step:
            step["step_id"] = step["id"]

    return response


def _shape_list_structures(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add v0 fields to structures."""
    if "structures" not in response:
        return response

    response = copy.deepcopy(response)
    for struct in response.get("structures", []):
        # Add n_species if missing
        if "n_species" not in struct:
            # Derive from formula or elements
            elements = struct.get("structure_elements", [])
            if elements:
                struct["n_species"] = len(set(elements))
            else:
                # Parse from formula
                formula = struct.get("formula", "")
                struct["n_species"] = len(set(c for c in formula if c.isupper()))

        # v0 required fields
        if "absolute_path" not in struct:
            struct["absolute_path"] = struct.get("path", "")
        if "lattice_type" not in struct:
            struct["lattice_type"] = "tuple"
        if "lattice_params" not in struct:
            # Provide default lattice params structure
            struct["lattice_params"] = {
                "a": 0.0, "b": 0.0, "c": 0.0,
                "alpha": 90.0, "beta": 90.0, "gamma": 90.0,
                "volume": 0.0
            }

    return response


def _shape_update_step_params(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape update_step_params for v0 compat - step detail response."""
    # First apply common step detail shaping
    response = _shape_step_detail(response)

    # Add v0-only fields with defaults
    if "warnings" not in response:
        response["warnings"] = []

    return response


def _shape_set_pseudo_config(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add v0 fields for set_pseudo_config."""
    response = dict(response)
    if "default_store_dir" not in response:
        response["default_store_dir"] = response.get("store_dir", "")
    if "repo_pseudo_dir" not in response:
        response["repo_pseudo_dir"] = ""
    if "default_seed_dir" not in response:
        response["default_seed_dir"] = response.get("seed_dir", "")
    # Remove v1-only fields that v0 didn't have
    response.pop("legacy_tables_base_url", None)
    response.pop("network_pseudo_base_url", None)
    return response


def _shape_change_calculation_structure(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape change_calculation_structure for v0 compat."""
    response = copy.deepcopy(response)

    # v0 required fields
    if "path" not in response:
        response["path"] = ""
    if "absolute_path" not in response:
        response["absolute_path"] = ""
    if "species_map" not in response:
        response["species_map"] = None

    # Shape steps
    for step in response.get("steps", []):
        step_type = step.get("type", "")
        # Derive name from type if missing
        if _should_derive_step_name(step.get("name", "")):
            step["name"] = _derive_step_name_from_type(step_type)
        if "type" in step:
            step["type"] = _map_step_type_to_v0(step["type"])
        if _should_derive_step_name(step.get("slug", "")):
            step["slug"] = step.get("name", "")
        # Regenerate step_file if missing or contains ULID
        step_file = step.get("step_file", "")
        if not step_file or any(_is_ulid(part.replace(".step.yaml", "").replace(".in", ""))
                                for part in step_file.split("/")):
            step["step_file"] = f"steps/{step.get('name', '')}.step.yaml"
        if "missing" not in step:
            step["missing"] = False

    return response


def _shape_list_pseudo_archives_status(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add grouped_by_library field for v0 compat."""
    if "archives" not in response:
        return response

    response = copy.deepcopy(response)

    # Build grouped_by_library if missing
    if "grouped_by_library" not in response:
        grouped = {}
        for archive in response.get("archives", []):
            lib_name = archive.get("library_name", "Unknown")
            lib_version = archive.get("library_version")
            key = f"{lib_name} {lib_version}" if lib_version else f"{lib_name} None"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(archive)
        response["grouped_by_library"] = grouped

    return response


def _shape_list_calculations(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add v0 fields to calculations."""
    if "calculations" not in response:
        return response

    response = copy.deepcopy(response)
    for calc in response.get("calculations", []):
        if "path" not in calc:
            calc["path"] = ""
        if "absolute_path" not in calc:
            calc["absolute_path"] = ""
        if "mode" not in calc:
            calc["mode"] = "normal"
        # structure field - try multiple sources
        if not calc.get("structure"):
            calc["structure"] = (
                calc.get("structure_name") or
                calc.get("structure_slug") or
                calc.get("structure_id", "")
            )
        if "steps" not in calc:
            calc["steps"] = []
        # Shape steps
        for step in calc.get("steps", []):
            step_type = step.get("type", "")
            # Derive name from type if missing
            if _should_derive_step_name(step.get("name", "")):
                step["name"] = _derive_step_name_from_type(step_type)
            if "type" in step:
                step["type"] = _map_step_type_to_v0(step["type"])
            if _should_derive_step_name(step.get("slug", "")):
                step["slug"] = step.get("name", "")

    return response


def _shape_get_project_history(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape get_project_history for v0 compat."""
    if "timeline" not in response:
        return response

    response = copy.deepcopy(response)
    for entry in response.get("timeline", []):
        # v0 expected these as strings, not None
        if entry.get("calc_id") is None:
            entry["calc_id"] = ""
        if entry.get("step_id") is None:
            entry["step_id"] = ""
        # v0 expected structure_ids as string, not list
        if isinstance(entry.get("structure_ids"), list):
            entry["structure_ids"] = ",".join(entry["structure_ids"]) if entry["structure_ids"] else ""

    return response


def _shape_get_calculation_pseudo_mapping(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add v0 fields to get_calculation_pseudo_mapping."""
    response = copy.deepcopy(response)

    # v0 required fields
    if "installed_sources" not in response:
        response["installed_sources"] = {
            "internal": True,
            "sssp_precision": False,
            "sssp_efficiency": False
        }
    if "candidates_by_element" not in response:
        response["candidates_by_element"] = {}
    if "resolved_by_element" not in response:
        response["resolved_by_element"] = {}

    return response


def _shape_discover_qe_engines(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape discover_qe_engines for v0 compat."""
    response = copy.deepcopy(response)

    # v0 expected cached_at as string timestamp, not float
    if "cached_at" in response and isinstance(response["cached_at"], (int, float)):
        from datetime import datetime
        response["cached_at"] = datetime.fromtimestamp(response["cached_at"]).isoformat()

    return response


def _shape_get_latest_run_for_step(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape get_latest_run_for_step for v0 compat."""
    response = dict(response)

    # v0 expected run_id as string, not None
    if response.get("run_id") is None:
        response["run_id"] = ""

    return response


def _shape_detect_qe(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape detect_qe for v0 compat."""
    response = dict(response)

    # Remove HEAD-only keys (v0 didn't have 'mode')
    response.pop("mode", None)

    # v0 expected error field as string (empty or error message)
    if "error" not in response:
        if not response.get("found"):
            response["error"] = "No internal QE found"
        else:
            response["error"] = ""  # Empty string, not None, for v0 compat

    # Ensure error is always a string
    if response.get("error") is None:
        response["error"] = ""

    return response


def _shape_search_legacy_pseudos(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape search_legacy_pseudos for v0 compat."""
    if "candidates" not in response:
        return response

    response = copy.deepcopy(response)
    for candidate in response.get("candidates", []):
        # v0 expected xc field
        if "xc" not in candidate:
            # Try to derive from filename
            filename = candidate.get("filename", "")
            if "pbe" in filename.lower():
                candidate["xc"] = "pbe"
            elif "pz" in filename.lower() or "lda" in filename.lower():
                candidate["xc"] = "lda"
            else:
                candidate["xc"] = "unknown"

    return response


def _shape_calculation_detail(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape calculation detail for v0 compat."""
    response = copy.deepcopy(response)

    # Ensure id field
    if "id" not in response and "calculation_id" in response:
        response["id"] = response["calculation_id"]

    # v0 required fields
    if "path" not in response:
        response["path"] = ""
    if "absolute_path" not in response:
        response["absolute_path"] = ""
    if "species_map" not in response:
        response["species_map"] = None

    # Shape steps
    for step in response.get("steps", []):
        step_type = step.get("type", "")
        # Derive name from type if missing
        if _should_derive_step_name(step.get("name", "")):
            step["name"] = _derive_step_name_from_type(step_type)
        # Map step type to v0 format
        if "type" in step:
            step["type"] = _map_step_type_to_v0(step["type"])
        # v0 required step fields
        if _should_derive_step_name(step.get("slug", "")):
            step["slug"] = step.get("name", "")
        # Regenerate step_file if missing or contains ULID
        step_file = step.get("step_file", "")
        if not step_file or any(_is_ulid(part.replace(".step.yaml", "").replace(".in", ""))
                                for part in step_file.split("/")):
            step["step_file"] = f"steps/{step.get('name', '')}.step.yaml"
        # Remove v1-only fields (not in v0 baseline response)
        step.pop("status", None)
        step.pop("step_type", None)
        step.pop("step_id", None)  # v0 uses "id", not "step_id"
        # Ensure missing is boolean
        if "missing" in step:
            step["missing"] = bool(step["missing"])
        else:
            step["missing"] = False

    # Remove v1-only top-level fields
    response.pop("calculation_id", None)
    response.pop("structure_name", None)

    return response


def _shape_import_step_from_qe_input(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape import step response for v0 compat."""
    return _shape_calculation_detail(response)


def _shape_get_calculation_detail(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape get_calculation_detail for v0 compat."""
    return _shape_calculation_detail(response)


def _shape_update_calculation_species_map(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape update_calculation_species_map response."""
    response = copy.deepcopy(response)

    # Add missing fields
    if "species_map" not in response:
        response["species_map"] = {}
    if "absolute_path" not in response:
        response["absolute_path"] = ""
    if "path" not in response:
        response["path"] = ""

    # Shape steps
    for step in response.get("steps", []):
        step_type = step.get("type", "")
        # Derive name from type if missing
        if _should_derive_step_name(step.get("name", "")):
            step["name"] = _derive_step_name_from_type(step_type)
        if "type" in step:
            step["type"] = _map_step_type_to_v0(step["type"])
        if _should_derive_step_name(step.get("slug", "")):
            step["slug"] = step.get("name", "")
        # Regenerate step_file if missing or contains ULID
        step_file = step.get("step_file", "")
        if not step_file or any(_is_ulid(part.replace(".step.yaml", "").replace(".in", ""))
                                for part in step_file.split("/")):
            step["step_file"] = f"steps/{step.get('name', '')}.step.yaml"
        step.pop("status", None)
        step.pop("step_type", None)
        step.pop("step_id", None)
        if "missing" in step:
            step["missing"] = bool(step["missing"])
        else:
            step["missing"] = False

    # Remove v1-only fields
    response.pop("calculation_id", None)
    response.pop("structure_name", None)

    return response


def _shape_reorder_calculation_steps(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape reorder_calculation_steps for v0 compat."""
    return _shape_calculation_detail(response)


def _shape_create_demo_project(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape create_demo_project for v0 compat.

    v0 expects: project_root, project_id, project_name, structure, calculation, ready_to_run
    HEAD returns: project_root, demo_id
    """
    response = copy.deepcopy(response)

    # Read project info from created project if needed
    project_root = response.get("project_root")
    if project_root:
        from pathlib import Path
        from quantumvitas.api import QVService
        try:
            project_path = Path(project_root)
            if project_path.exists():
                # Get project summary to fill in missing fields
                summary = QVService.get_project_summary(project_path)

                # Add v0 expected fields
                if "project_id" not in response:
                    response["project_id"] = summary.get("id", "")
                if "project_name" not in response:
                    response["project_name"] = summary.get("name", "demo-si-project")

                # Get first structure
                structures = QVService.list_structures_data(project_path)
                if structures and "structure" not in response:
                    first_struct = structures[0]
                    response["structure"] = {
                        "id": first_struct.get("id", ""),
                        "name": first_struct.get("name", ""),
                    }

                # Get first calculation
                calcs = QVService.list_calculations_data(project_path)
                if calcs and "calculation" not in response:
                    response["calculation"] = calcs[0].get("id", "")

                if "ready_to_run" not in response:
                    response["ready_to_run"] = True
        except Exception:
            # If we can't read the project, provide defaults
            pass

    # Ensure required fields have defaults
    if "project_id" not in response:
        response["project_id"] = ""
    if "project_name" not in response:
        response["project_name"] = "demo-si-project"
    if "structure" not in response:
        response["structure"] = {"id": "", "name": ""}
    if "calculation" not in response:
        response["calculation"] = ""
    if "ready_to_run" not in response:
        response["ready_to_run"] = True

    # Remove HEAD-only fields
    response.pop("demo_id", None)

    return response


def _shape_get_structure_vis(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape get_structure_vis for v0 compat."""
    response = copy.deepcopy(response)

    # Ensure atoms list has required fields
    for atom in response.get("atoms", []):
        if "color" not in atom:
            atom["color"] = "#888888"
        if "radius" not in atom:
            atom["radius"] = 1.0

    # v0 required fields
    if "n_boundary_atoms" not in response:
        response["n_boundary_atoms"] = len(response.get("boundary_atoms", []))

    # v0 had performance metrics
    if "perf" not in response:
        response["perf"] = {
            "trace_id": "",
            "prep_ms": 0.0,
            "bonds_ms": 0.0,
            "ser_ms": 0.0,
            "total_ms": 0.0,
            "atoms": response.get("n_atoms", 0),
            "bonds": response.get("n_bonds", 0),
            "bytes": 0,
        }

    return response


def _shape_structure_get_online_candidate(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape structure_get_online_candidate for v0 compat."""
    response = copy.deepcopy(response)

    # v0 expected structure_data, not structure_dict
    if "structure_dict" in response and "structure_data" not in response:
        response["structure_data"] = response.pop("structure_dict")

    return response


def _shape_step_detail(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape step detail response for v0 compat.

    v0 response only has: id, name, slug, path, absolute_path, step_type,
    structure, parent_calculation_id, parameters, cards, species_overrides,
    prefix_outdir_injection

    HEAD adds extra: meta, status, step_id, calc_id - remove them.
    """
    response = copy.deepcopy(response)

    # Remove HEAD-only keys
    response.pop("meta", None)
    response.pop("status", None)
    response.pop("step_id", None)
    response.pop("calc_id", None)

    return response


def _shape_set_pseudo_mapping(response: Dict[str, Any]) -> Dict[str, Any]:
    """Shape set_pseudo_mapping response for v0 compat."""
    return _shape_step_detail(response)


RESPONSE_SHAPERS: Dict[str, callable] = {
    "create_calculation": _shape_create_calculation,
    "get_step_detail": _shape_step_detail,
    "set_pseudo_mapping": _shape_set_pseudo_mapping,
    "get_pseudo_config": _shape_get_pseudo_config,
    "set_pseudo_config": _shape_set_pseudo_config,
    "list_journal_entries": _shape_list_journal_entries,
    "list_demo_projects": _shape_list_demo_projects,
    "add_step_to_calculation": _shape_add_step_to_calculation,
    "list_structures": _shape_list_structures,
    "update_step_params": _shape_update_step_params,
    "import_step_from_qe_input": _shape_import_step_from_qe_input,
    "get_calculation_detail": _shape_get_calculation_detail,
    "update_calculation_species_map": _shape_update_calculation_species_map,
    "change_calculation_structure": _shape_change_calculation_structure,
    "list_pseudo_archives_status": _shape_list_pseudo_archives_status,
    "list_calculations": _shape_list_calculations,
    "get_project_history": _shape_get_project_history,
    "get_calculation_pseudo_mapping": _shape_get_calculation_pseudo_mapping,
    "discover_qe_engines": _shape_discover_qe_engines,
    "get_latest_run_for_step": _shape_get_latest_run_for_step,
    "detect_qe": _shape_detect_qe,
    "search_legacy_pseudos": _shape_search_legacy_pseudos,
    "reorder_calculation_steps": _shape_reorder_calculation_steps,
    "create_demo_project": _shape_create_demo_project,
    "get_structure_vis": _shape_get_structure_vis,
    "structure_get_online_candidate": _shape_structure_get_online_candidate,
}


def shape_response(method: str, response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform new responses to v0 format.

    Args:
        method: RPC method name
        response: New response dict

    Returns:
        Shaped response dict (may be same object if no changes)
    """
    if response is None:
        return response

    shaper = RESPONSE_SHAPERS.get(method)
    if shaper:
        return shaper(response)
    return response
