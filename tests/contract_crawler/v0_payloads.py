"""
v0 Payload Schema Definitions for 0873ebf baseline.

This is the SINGLE SOURCE OF TRUTH for v0 payload schemas.
All recipes MUST call build_v0_payload() instead of constructing payloads directly.

Schema was determined by reading 0873ebf server.py handler implementations.
Once defined here, DO NOT change without verifying against 0873ebf source.

If a method fails with the v0 payload:
- Fix the recipe world/setup
- OR fix the compat adapter/shaper on HEAD
- DO NOT change this file unless 0873ebf source actually differs
"""

from pathlib import Path
from typing import Any, Dict, Optional


# =============================================================================
# V0 PAYLOAD SCHEMAS (verified from 0873ebf server.py handlers)
# =============================================================================

def build_v0_payload(method_name: str, world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    Build a v0-compatible payload for the given method.

    Args:
        method_name: RPC method name
        world: World dict from build_demo_world() containing project state
        **extra: Additional method-specific parameters

    Returns:
        v0-compatible payload dict

    Raises:
        KeyError: If method has no registered schema
    """
    builder = V0_PAYLOAD_BUILDERS.get(method_name)
    if builder is None:
        raise KeyError(f"No v0 payload schema defined for method: {method_name}")
    return builder(world, **extra)


# -----------------------------------------------------------------------------
# Structure Methods (selector is a STRING in v0, not a dict)
# -----------------------------------------------------------------------------

def _build_delete_structure(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 delete_structure payload.
    Source: 0873ebf server.py _handle_delete_structure

    Fields:
        project_root: str
        selector: str (structure ID as plain string)
        force: bool (optional)
    """
    return {
        "project_root": world["project_root"],
        "selector": world["structure_ulid"],  # PLAIN STRING, not dict
        "force": extra.get("force", False),
    }


def _build_rename_structure(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 rename_structure payload.
    Source: 0873ebf server.py _handle_rename_structure

    Fields:
        project_root: str
        selector: str (structure ID as plain string)
        new_name: str
    """
    return {
        "project_root": world["project_root"],
        "selector": world["structure_ulid"],  # PLAIN STRING
        "new_name": extra.get("new_name", "renamed_structure"),
    }


def _build_can_delete_structure(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 can_delete_structure payload.
    Source: 0873ebf server.py _handle_can_delete_structure

    Fields:
        project_root: str
        selector: str (structure ID as plain string)
    """
    return {
        "project_root": world["project_root"],
        "selector": world["structure_ulid"],  # PLAIN STRING
    }


def _build_get_structure_vis(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 get_structure_vis payload.
    Source: 0873ebf server.py _handle_get_structure_vis

    Fields:
        project_root: str
        selector: str (structure ID as plain string)
        supercell: [int, int, int] (optional)
        repeat_boundary: bool (optional)
        display_mode: str (optional)
    """
    return {
        "project_root": world["project_root"],
        "selector": world["structure_ulid"],  # PLAIN STRING
    }


def _build_import_structure(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 import_structure payload.
    Source: 0873ebf server.py _handle_import_structure

    Fields:
        project_root: str
        source_file: str (path to structure file - NOTE: NOT "source")
        name: str (optional)
    """
    return {
        "project_root": world["project_root"],
        "source_file": extra.get("source_file", ""),  # NOTE: key is "source_file"
        "name": extra.get("name", "imported_structure"),
    }


# -----------------------------------------------------------------------------
# QE Parameter Methods
# -----------------------------------------------------------------------------

def _build_list_qe_ui_parameters(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 list_qe_ui_parameters payload.
    Source: 0873ebf server.py _handle_list_qe_ui_parameters

    Fields:
        module: str (required) - e.g., "pw", "bands", "dos"
        step_type: str (required) - e.g., "scf", "nscf", "bands"
    """
    return {
        "module": extra.get("module", "pw"),
        "step_type_gen": extra.get("step_type_gen", "scf"),  # Canonical: step_type_gen for UI parameters
    }


# -----------------------------------------------------------------------------
# Calculation/Step Methods
# -----------------------------------------------------------------------------

def _build_run_single_step(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 run_single_step payload.
    Source: 0873ebf server.py _handle_run_single_step

    Fields:
        project_root: str
        calculation: str (calculation selector)
        step_ulid: str (step ULID)
        verbose: bool (optional)
    """
    return {
        "project_root": world["project_root"],
        "calculation": world["calculation_selector"],
        "step_ulid": world["step_selector"],
        "verbose": extra.get("verbose", False),
    }


def _build_reorder_calculation_steps(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 reorder_calculation_steps payload.
    Source: 0873ebf server.py _handle_reorder_calculation_steps

    Fields:
        project_root: str
        calculation: str
        new_order: List[str] (step IDs in new order)
    """
    return {
        "project_root": world["project_root"],
        "calculation": world["calculation_selector"],
        "new_order": extra.get("new_order", list(reversed(world.get("step_ids", [])))),
    }


def _build_reset_step_params(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 reset_step_params payload.
    Source: 0873ebf server.py _handle_reset_step_params

    NOTE: This method is BROKEN in 0873ebf - the handler internally passes
    calculation_ulid to QVService.reset_step_params() but the service method
    doesn't accept it. Should be EXEMPT.

    Fields:
        project_root: str
        calculation: str
        step: str
    """
    return {
        "project_root": world["project_root"],
        "calculation": world["calculation_selector"],
        "step": world["step_selector"],
    }


def _build_set_common_card(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 set_common_card payload.
    Source: 0873ebf server.py _handle_set_common_card

    Fields:
        project_root: str
        calculation: str
        step: str
        card_name: str (e.g., "K_POINTS")
        view_model: dict (UI view model, NOT card_value)
    """
    return {
        "project_root": world["project_root"],
        "calculation": world["calculation_selector"],
        "step": world["step_selector"],
        "card_name": extra.get("card_name", "K_POINTS"),
        "view_model": extra.get("view_model", {"grid": [4, 4, 4], "shift": [0, 0, 0]}),
    }


# -----------------------------------------------------------------------------
# Workflow Methods
# -----------------------------------------------------------------------------

def _build_instantiate_workflow(world: Dict[str, Any], **extra) -> Dict[str, Any]:
    """
    v0 instantiate_workflow payload.
    Source: 0873ebf server.py _handle_instantiate_workflow

    Fields:
        workflow_id: str
        calculation_path: str (path to calculation directory)
        structure_ulid: str
        calculation_id: str (parent calculation ULID)
    """
    calc_path = f"{world['project_root']}/calculations/{world['calc_slug']}"
    return {
        "workflow_id": extra.get("workflow_id", "scf"),
        "calculation_path": calc_path,
        "structure_ulid": world["structure_ulid"],
        "calculation_id": world["calculation_selector"],  # calc_id ULID
    }


# =============================================================================
# PAYLOAD BUILDER REGISTRY
# =============================================================================

V0_PAYLOAD_BUILDERS: Dict[str, callable] = {
    # Structure methods
    "delete_structure": _build_delete_structure,
    "rename_structure": _build_rename_structure,
    "can_delete_structure": _build_can_delete_structure,
    "get_structure_vis": _build_get_structure_vis,
    "import_structure": _build_import_structure,

    # QE parameter methods
    "list_qe_ui_parameters": _build_list_qe_ui_parameters,

    # Calculation/step methods
    "run_single_step": _build_run_single_step,
    "reorder_calculation_steps": _build_reorder_calculation_steps,
    "reset_step_params": _build_reset_step_params,
    "set_common_card": _build_set_common_card,

    # Workflow methods
    "instantiate_workflow": _build_instantiate_workflow,
}


# =============================================================================
# EXEMPT METHODS (known broken in 0873ebf baseline)
# =============================================================================

V0_EXEMPT_METHODS = {
    # These are broken IN the 0873ebf baseline itself (handler bugs)
    "reset_step_params",  # Handler passes calculation_ulid but service doesn't accept it
    "apply_presets_to_step",  # 'ResolvedResource' object has no attribute 'path'
    "get_pseudo_options_for_calculation",  # 'dict' object has no attribute 'store_dir'
    "set_common_card",  # Cannot set() a dict at path 'cards.K_POINTS'

    # These require ephemeral job state that can't be recreated
    "cancel_job",
    "get_job_status",
    "get_job_logs",

    # These require specific fixture files not available in test env
    "compile_fixture_volume",

    # This terminates the daemon process
    "shutdown",
}


def get_v0_payload_methods() -> set:
    """Get set of methods that have v0 payload definitions."""
    return set(V0_PAYLOAD_BUILDERS.keys())


def is_v0_exempt(method_name: str) -> bool:
    """Check if method is exempt from v0 testing."""
    return method_name in V0_EXEMPT_METHODS
