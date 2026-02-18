"""preview_compilation tool — stateless preset compilation preview."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def preview_compilation(engine: str, workflow: str, presets: dict) -> dict:
    """Preview what parameters preset compilation would produce.

    This is a **stateless** tool — no calculation is created or modified.
    It shows the compiled QE-style namelist parameters that result from the
    given preset dimension choices.

    Args:
        engine: Engine family identifier (e.g. 'qe', 'vasp').
        workflow: Workflow template id (e.g. 'scf', 'dos', 'bands').
        presets: Dict of dimension → selected option value
            (e.g. ``{"magnetism": "COL", "occupations_scheme": "SMEARING_GAUSSIAN"}``).
    """
    import quantumvitas.drivers  # noqa: F401 — trigger registration
    from quantumvitas.core.driver_registry import DriverRegistry
    from quantumvitas.workflow.templates import get_workflow_service

    # --- validate engine ---
    known_engines = sorted(DriverRegistry.get_all_engines())
    if engine not in known_engines:
        return make_error(
            "unknown_engine",
            f"Engine '{engine}' is not registered.",
            suggestions=known_engines,
        )

    # --- validate workflow ---
    wf_service = get_workflow_service()
    template = wf_service.get_template(workflow)
    if template is None:
        known_workflows = [t.id for t in wf_service.list_templates()]
        return make_error(
            "unknown_workflow",
            f"Workflow '{workflow}' not found.",
            suggestions=known_workflows,
        )

    # --- compile presets per step ---
    from quantumvitas.presets.compiler import compile_presets_for_step

    steps_out: list[dict] = []
    for gen_step in template.step_sequence:
        try:
            compiled = compile_presets_for_step(gen_step, presets)
        except Exception:
            compiled = {}
        steps_out.append({
            "step_type_gen": gen_step,
            "parameters": compiled,
        })

    return make_response(
        {
            "engine": engine,
            "workflow": workflow,
            "presets": presets,
            "steps": steps_out,
        },
        context_hint="To commit, call create_calculation + apply_preset.",
    )
