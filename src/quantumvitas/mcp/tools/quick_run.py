"""quick_run tool — create, configure, and run a calculation in one shot."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def quick_run(
    engine: str,
    workflow: str,
    structure_selector: str,
    species_map: dict | None = None,
    presets: dict | None = None,
    overrides: dict | None = None,
    name: str = "",
) -> dict:
    """Create and run a calculation in a single call.

    Combines create_calculation + (optional) set_species_map +
    (optional) apply_preset + (optional) set_parameters +
    run_calculation into one tool.  Blocks until the engine finishes.

    Args:
        engine: Engine family identifier (e.g. 'qe', 'vasp', 'orca').
        workflow: Workflow template id (e.g. 'scf', 'dos', 'bands').
        structure_selector: Name or ULID of an already-imported structure.
        species_map: Optional element-to-pseudopotential mapping.
            Required for QE, ABINIT, Siesta, VASP.
            Example: {"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}}
        presets: Optional dict of dimension -> value for preset compilation.
        overrides: Optional engine-native parameter overrides (applied to step 0).
        name: Optional human-readable name for the calculation.
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

    # --- get service ---
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- init calculation ---
    calc_name = name or f"{engine}_{workflow}"
    try:
        calc_resolved = svc.project.init_calculation(
            name=calc_name,
            structure_selector=structure_selector,
            engine_family=engine,
        )
    except Exception as exc:
        msg = str(exc)
        if "structure" in msg.lower() or "not found" in msg.lower():
            return make_error(
                "structure_not_found",
                f"Structure '{structure_selector}' not found: {msg}",
            )
        return make_error("creation_failed", msg)

    calc_ulid = calc_resolved.ulid

    # --- set species_map ---
    if species_map:
        try:
            svc.calculation.update_species_map(calc_ulid, species_map)
        except Exception as exc:
            return make_error("species_map_failed", f"Failed to set species_map: {exc}")

    # --- add workflow steps ---
    step_ulids: list[str] = []
    for gen_step in template.step_sequence:
        try:
            step_dto = svc.calculation.add_step(
                calc_selector=calc_ulid,
                step_type_gen=gen_step,
            )
            step_ulids.append(step_dto.step_ulid)
        except Exception:
            pass

    # --- apply presets ---
    if presets:
        try:
            svc.calculation.apply_presets(calc_ulid, presets)
        except Exception as exc:
            return make_error("preset_failed", f"Preset application failed: {exc}")

    # --- apply overrides to step 0 ---
    if overrides and step_ulids:
        try:
            svc.calculation.update_step_params(
                calc_selector=calc_ulid,
                step_selector=step_ulids[0],
                params={"parameters": overrides},
            )
        except Exception as exc:
            return make_error("override_failed", f"Parameter override failed: {exc}")

    # --- run ---
    try:
        result_dto = svc.run.run_calculation(calc_ulid)
    except Exception as exc:
        return make_error(
            "execution_failed",
            f"Calculation run failed: {exc}",
            context_hint=(
                "Check engine installation and calculation parameters. "
                "For pseudopotential engines (QE, ABINIT, Siesta, VASP), "
                "ensure species_map is set."
            ),
        )

    # Build step summaries
    steps_out: list[dict] = []
    for s in result_dto.steps:
        steps_out.append({
            "step_ulid": s.step_ulid,
            "step_type_gen": s.step_type_gen,
            "step_type_spec": s.step_type_spec,
            "status": s.status or "unknown",
        })

    hint = (
        f"Use get_results_summary(calc_ulid='{result_dto.calc_ulid}') "
        "to see results."
    )
    if workflow in {"relax", "vc-relax", "vc_relax"}:
        hint += (
            f" For the relaxed geometry, use promote_structure(calc_ulid='{result_dto.calc_ulid}') "
            "to extract and register it as a new structure."
        )
    return make_response(
        {
            "calc_ulid": result_dto.calc_ulid,
            "run_ulid": result_dto.run_ulid,
            "status": result_dto.status,
            "engine": engine,
            "workflow": workflow,
            "steps": steps_out,
        },
        context_hint=hint,
    )
