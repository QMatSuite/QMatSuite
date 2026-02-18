"""get_presets tool — discover quality presets for engine + workflow."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response

# Static dimension descriptions (not stored in ParamSpace objects).
_DIMENSION_META: dict[str, dict] = {
    "magnetism": {
        "description": "Spin treatment for magnetic calculations",
        "options_meta": {
            "NM": "Non-magnetic",
            "COL": "Collinear (LSDA)",
            "NC_CANONICAL": "Non-collinear",
            "SOC_CANONICAL": "Non-collinear + spin-orbit coupling",
        },
        "default": "NM",
    },
    "occupations_scheme": {
        "description": "Electronic occupation scheme",
        "options_meta": {
            "FIXED": "Fixed occupations (insulator)",
            "TETRAHEDRA": "Tetrahedron method",
            "SMEARING_GAUSSIAN": "Gaussian smearing (metal)",
        },
        "default": "FIXED",
    },
    "precision": {
        "description": "Basis-set / k-mesh quality level",
        "options_meta": {
            "LOW": "Low precision (fast screening)",
            "MED": "Medium precision (production)",
            "HIGH": "High precision (publication quality)",
        },
        "default": "MED",
    },
    "convergence": {
        "description": "SCF convergence stringency",
        "options_meta": {
            "FAST": "Fast (loose threshold)",
            "NORMAL": "Normal",
            "ROBUST": "Robust (tight threshold)",
            "VERY_ROBUST": "Very robust (ultra-tight)",
        },
        "default": "NORMAL",
    },
    "qc_precision": {
        "description": "Quantum chemistry precision level",
        "options_meta": {
            "LOW": "Low precision (fast screening)",
            "MED": "Medium precision (production)",
            "HIGH": "High precision (publication quality)",
        },
        "default": "MED",
    },
}


@mcp.tool
def get_presets(engine: str, workflow: str) -> dict:
    """Get available quality presets for a given engine and workflow.

    Returns the preset dimensions (e.g. precision, magnetism) and their
    selectable options. Presets are currently QE-focused; most other engines
    will report ``presets_available: false``.

    Args:
        engine: Engine family identifier (e.g. 'qe', 'vasp').
        workflow: Workflow template id (e.g. 'scf', 'dos', 'bands').
    """
    import quantumvitas.drivers  # noqa: F401 — trigger registration
    from quantumvitas.core.driver_registry import DriverRegistry
    from quantumvitas.presets.variants_registry import (
        PROFILE_TO_ENUM,
        list_dimensions_for_gen_step,
    )
    from quantumvitas.workflow.templates import get_workflow_service

    # Validate engine
    known_engines = sorted(DriverRegistry.get_all_engines())
    if engine not in known_engines:
        return make_error(
            "unknown_engine",
            f"Engine '{engine}' is not registered.",
            suggestions=known_engines,
        )

    # Validate workflow
    service = get_workflow_service()
    template = service.get_template(workflow)
    if template is None:
        known_workflows = [t.id for t in service.list_templates()]
        return make_error(
            "unknown_workflow",
            f"Workflow '{workflow}' not found.",
            suggestions=known_workflows,
        )

    # Collect union of dimensions across all gen steps in the workflow
    all_dimensions: set[str] = set()
    for gen_step in template.step_sequence:
        dims = list_dimensions_for_gen_step(gen_step)
        all_dimensions.update(dims)

    if not all_dimensions:
        return make_response(
            {
                "engine": engine,
                "workflow": workflow,
                "presets_available": False,
                "dimensions": [],
            },
            context_hint="This engine/workflow combination does not have configurable presets.",
        )

    # Build dimension details
    dimensions_out: list[dict] = []
    for dim_name in sorted(all_dimensions):
        meta = _DIMENSION_META.get(dim_name, {})
        profiles = PROFILE_TO_ENUM.get(dim_name, {})
        options_meta = meta.get("options_meta", {})

        options = []
        for profile_name in profiles:
            options.append({
                "value": profile_name,
                "label": options_meta.get(profile_name, profile_name),
            })

        dimensions_out.append({
            "name": dim_name,
            "description": meta.get("description", ""),
            "default": meta.get("default"),
            "options": options,
        })

    return make_response(
        {
            "engine": engine,
            "workflow": workflow,
            "presets_available": True,
            "dimensions": dimensions_out,
        },
        context_hint="Use search_parameters(query='...', engine='...') to find specific parameters to customize.",
    )
