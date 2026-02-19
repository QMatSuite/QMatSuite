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

    If the engine has a preflight checker, the compiled parameters are also
    validated and any issues are returned in ``preflight_issues``.

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

    gen_steps = list(template.step_sequence)
    steps_out: list[dict] = []
    for gen_step in gen_steps:
        try:
            compiled = compile_presets_for_step(gen_step, presets)
        except Exception:
            compiled = {}
        entry: dict = {
            "step_type_gen": gen_step,
            "parameters": compiled,
        }
        if not compiled:
            entry["note"] = (
                "No parameters compiled for this step. "
                "Use set_parameters() after creating the calculation to configure manually."
            )
        steps_out.append(entry)

    result_data: dict = {
        "engine": engine,
        "workflow": workflow,
        "presets": presets,
        "steps": steps_out,
    }

    if all(not s["parameters"] for s in steps_out):
        result_data["hint"] = (
            "No parameters compiled. This may mean the presets don't apply to "
            "these step types. Use set_parameters() to configure manually."
        )

    # --- preflight (best-effort) ---
    try:
        driver = DriverRegistry.get_driver(engine)
        checker = driver.get_preflight_checker()
        if checker is not None:
            all_issues: list[dict] = []
            for idx, step_entry in enumerate(steps_out):
                workflow_context = {
                    "gen_steps": gen_steps,
                    "current_step_index": idx,
                    "current_step_gen": step_entry["step_type_gen"],
                    "other_steps_params": {},
                }
                issues = checker.check(
                    step_entry["parameters"], None, workflow_context,
                )
                for iss in issues:
                    all_issues.append({
                        "step_index": idx,
                        "step_type_gen": step_entry["step_type_gen"],
                        "code": iss.code,
                        "severity": iss.severity,
                        "message": iss.message,
                        "parameter": iss.parameter,
                        "suggestion": iss.suggestion,
                    })
            if all_issues:
                result_data["preflight_issues"] = all_issues
    except Exception:
        pass  # Best-effort: never cause tool failure

    return make_response(
        result_data,
        context_hint="To commit, call create_calculation + apply_preset.",
    )
