"""list_workflows tool — discover workflows available for a given engine."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def list_workflows(engine: str) -> dict:
    """List workflows available for a specific engine.

    Shows which workflow templates the engine supports, along with the
    materialized (engine-specific) step sequence for each.

    Args:
        engine: Engine family identifier (e.g. 'qe', 'vasp', 'orca').
    """
    import qmatsuite.drivers  # noqa: F401 — trigger registration
    from qmatsuite.core.driver_registry import DriverRegistry
    from qmatsuite.workflow.generalized_steps import materialize_workflow
    from qmatsuite.workflow.templates import get_workflow_service

    # Validate engine
    known = sorted(DriverRegistry.get_all_engines())
    if engine not in known:
        return make_error(
            "unknown_engine",
            f"Engine '{engine}' is not registered.",
            suggestions=known,
        )

    driver = DriverRegistry.get_driver(engine)
    gen_steps = driver.SUPPORTED_GEN_STEPS if hasattr(driver, "SUPPORTED_GEN_STEPS") else set()
    service = get_workflow_service()

    workflows_out: list[dict] = []
    for template in service.list_templates():
        # Check if ALL required gen steps are supported by the engine
        # (through base engine or companions)
        try:
            spec_steps = materialize_workflow(list(template.step_sequence), engine)
        except ValueError:
            # Engine doesn't support one or more steps
            continue

        workflows_out.append({
            "workflow_id": template.id,
            "name": template.name,
            "description": template.description,
            "gen_steps": list(template.step_sequence),
            "spec_steps": spec_steps,
        })

    return make_response(
        {"engine": engine, "workflows": workflows_out, "total": len(workflows_out)},
        context_hint="Use get_presets(engine='...', workflow='...') to check for available quality presets.",
    )
