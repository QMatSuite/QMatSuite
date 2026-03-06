"""create_calculation tool — create a new calculation with workflow steps."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def create_calculation(
    engine: str,
    workflow: str,
    structure_selector: str,
    name: str = "",
) -> dict:
    """Create a new calculation for a given engine, workflow, and structure.

    Initialises the calculation directory, sets the engine family, and adds
    the workflow's step sequence (e.g. scf, nscf, bands).

    Args:
        engine: Engine family identifier (e.g. 'qe', 'vasp', 'orca').
        workflow: Workflow template id (e.g. 'scf', 'dos', 'bands').
        structure_selector: Name or ULID of an already-imported structure.
        name: Optional human-readable name for the calculation.
    """
    import qmatsuite.drivers  # noqa: F401 — trigger registration
    from qmatsuite.core.driver_registry import DriverRegistry
    from qmatsuite.workflow.templates import get_workflow_service

    # --- validate engine ---
    known_engines = sorted(DriverRegistry.get_all_engines())
    if engine not in known_engines:
        return make_error(
            "unknown_engine",
            f"Engine '{engine}' is not registered.",
            suggestions=known_engines,
            context_hint="Use list_engines() to see all available engines.",
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
            context_hint=f"Use list_workflows(engine='{engine}') to see available workflows.",
        )

    # --- get project service ---
    from qmatsuite.mcp.project import ProjectNotFoundError, get_service

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
                suggestions=["Import a structure first, then retry."],
                context_hint="Use import_structure() to import a structure, or list_structures() to see existing ones.",
            )
        return make_error("creation_failed", msg)

    calc_ulid = calc_resolved.ulid

    # --- add workflow steps ---
    steps_out: list[dict] = []
    for idx, gen_step in enumerate(template.step_sequence):
        try:
            step_dto = svc.calculation.add_step(
                calc_selector=calc_ulid,
                step_type_gen=gen_step,
            )
            steps_out.append({
                "step_index": idx,
                "step_type_gen": gen_step,
                "step_type_spec": step_dto.step_type_spec,
                "step_ulid": step_dto.step_ulid,
            })
        except Exception:
            # Step not supported by this engine — skip silently
            pass

    # --- auto-resolve species_map for pseudo engines ---
    species_map_resolved = False
    if engine in ("qe", "abinit", "siesta"):
        try:
            from qmatsuite.mcp.tools._resource_utils import auto_resolve_species_map_internal

            resolved = auto_resolve_species_map_internal(calc_ulid, svc)
            if resolved:
                svc.calculation.update_species_map(calc_ulid, resolved)
                species_map_resolved = True
        except Exception:
            pass

    search_tip = (
        f"Tip: use search_knowledge(query='{workflow}') to check for "
        f"known issues before configuring. "
    )
    if species_map_resolved:
        hint = (
            search_tip
            + f"Species map auto-resolved. "
            f"Use apply_preset or set_parameters to configure, "
            f"then inspect_calculation(calc_ulid='{calc_ulid}') to review, "
            f"then run_calculation(calc_ulid='{calc_ulid}') to execute."
        )
    else:
        hint = (
            search_tip
            + f"IMPORTANT: For engines using pseudopotentials (QE, ABINIT, Siesta, VASP), "
            f"call auto_resolve_species_map(calc_ulid='{calc_ulid}') or "
            f"set_species_map(calc_ulid='{calc_ulid}', species_map=...) first. "
            f"Then use apply_preset or set_parameters to configure, "
            f"then inspect_calculation(calc_ulid='{calc_ulid}') to review."
        )

    return make_response(
        {
            "calc_ulid": calc_ulid,
            "name": calc_name,
            "engine": engine,
            "workflow": workflow,
            "steps": steps_out,
            "species_map_resolved": species_map_resolved,
        },
        context_hint=hint,
    )
