"""quick_run tool — create, configure, and run a calculation in one shot."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


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
            )
        return make_error("creation_failed", msg)

    calc_ulid = calc_resolved.ulid

    # --- set species_map ---
    if species_map:
        try:
            svc.calculation.update_species_map(calc_ulid, species_map)
        except Exception as exc:
            return make_error("species_map_failed", f"Failed to set species_map: {exc}")

    # --- auto-resolve species_map for pseudo engines ---
    if not species_map:
        try:
            from qmatsuite.mcp.tools._resource_utils import auto_resolve_species_map_internal

            resolved = auto_resolve_species_map_internal(calc_ulid, svc)
            if resolved:
                svc.calculation.update_species_map(calc_ulid, resolved)
        except Exception:
            pass  # Best-effort: agent can set manually if auto-resolve fails

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
        # Attempt error enrichment like run_calculation.py
        try:
            detail = svc.calculation.get_detail(calc_ulid)
            digest = _try_parse_digest(detail)
            from qmatsuite.mcp.error_enrichment import enrich_run_error

            # Build a minimal result_dto-like object for enrichment
            enriched = enrich_run_error(
                calc_ulid=calc_ulid,
                result_dto=type("_", (), {
                    "steps": [],
                    "exit_code": getattr(exc, "exit_code", None),
                })(),
                digest=digest,
                engine=engine,
                workflow=workflow,
            )
            return enriched
        except Exception:
            pass
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
            "message": s.message,
        })

    status = result_dto.status
    payload: dict = {
        "calc_ulid": result_dto.calc_ulid,
        "run_ulid": result_dto.run_ulid,
        "status": status,
        "engine": engine,
        "workflow": workflow,
        "steps": steps_out,
    }

    # --- Parse digest for convergence check ---
    try:
        detail = svc.calculation.get_detail(calc_ulid)
        digest = _try_parse_digest(detail)
    except Exception:
        digest = None

    if status == "completed":
        # Check for "completed but not converged"
        if digest and digest.get("total_energy_ry") is None and digest.get("n_iterations", 0) > 0:
            try:
                from qmatsuite.mcp.error_enrichment import enrich_run_error

                digest["converged"] = False
                enriched = enrich_run_error(
                    calc_ulid=calc_ulid,
                    result_dto=result_dto,
                    digest=digest,
                    engine=engine,
                    workflow=workflow,
                )
                enriched["data"] = payload
                return enriched
            except Exception:
                pass

        hint = (
            f"Use get_results_summary(calc_ulid='{result_dto.calc_ulid}') "
            "to see results."
        )
        if workflow in {"relax", "minimize"}:
            hint += (
                f" For the relaxed geometry, use promote_structure(calc_ulid='{result_dto.calc_ulid}') "
                "to extract and register it as a new structure."
            )
        return make_response(payload, context_hint=hint)

    # --- Failed: enrich with diagnostics + suggested_fixes ---
    try:
        from qmatsuite.mcp.error_enrichment import enrich_run_error

        enriched = enrich_run_error(
            calc_ulid=calc_ulid,
            result_dto=result_dto,
            digest=digest,
            engine=engine,
            workflow=workflow,
        )
        enriched["data"] = payload
        return enriched
    except Exception:
        return make_response(
            payload,
            context_hint="Check step messages for failure details.",
            warnings=["Calculation did not complete successfully."],
            status="error",
        )


def _try_parse_digest(detail: dict) -> dict | None:
    """Attempt to parse engine output for the first step's digest."""
    from pathlib import Path

    calc_dir = detail.get("absolute_path")
    if not calc_dir:
        return None

    calc_path = Path(calc_dir)
    steps = detail.get("steps", [])
    if not steps:
        return None

    step_info = steps[0]
    step_slug = step_info.get("slug") or step_info.get("name", "")

    candidates = [
        calc_path / "raw" / step_slug,
        calc_path / "raw",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            try:
                import qmatsuite.drivers  # noqa: F401
                from qmatsuite.parsers.registry import find_parser_for_raw

                parser_cls = find_parser_for_raw(candidate, "scf_digest")
                if parser_cls is not None:
                    parser = parser_cls()
                    digest = parser.parse(candidate)
                    return digest.to_dict() if hasattr(digest, "to_dict") else digest
            except Exception:
                pass

            try:
                from qmatsuite.drivers.qe.parsers.output import QEOutputParser

                parser = QEOutputParser()
                if parser.can_parse(candidate):
                    return parser.parse(candidate).to_dict()
            except Exception:
                pass

    return None
