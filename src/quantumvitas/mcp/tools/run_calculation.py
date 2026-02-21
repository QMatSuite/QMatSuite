"""run_calculation tool — execute a calculation synchronously."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def run_calculation(calc_ulid: str, run_mode: str = "incremental") -> dict:
    """Run a calculation synchronously.

    Blocks until the engine finishes and returns the final status
    (completed or failed).  The calculation must already have steps
    configured via create_calculation + set_parameters / apply_preset.

    On failure, returns structured diagnostics and knowledge-backed
    suggested_fixes so the agent can diagnose and recover.

    Args:
        calc_ulid: ULID of the calculation to run.
        run_mode: Run mode — "incremental" (default) skips unchanged steps,
            "full" reruns everything from step 0.
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    if run_mode not in ("incremental", "full"):
        return make_error(
            "invalid_run_mode",
            f"run_mode must be 'incremental' or 'full', got '{run_mode}'",
        )

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- validate calc exists ---
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception as exc:
        return make_error(
            "not_found",
            f"Calculation '{calc_ulid}' not found: {exc}",
        )

    # --- validate species_map for pseudo engines ---
    engine = detail.get("engine_family", "")
    species_map = detail.get("species_map") or {}
    if engine in ("qe", "abinit", "siesta") and not species_map:
        return make_error(
            "missing_species_map",
            "No species_map configured. Pseudopotential engines require species_map.",
            context_hint=(
                f"Call auto_resolve_species_map(calc_ulid='{calc_ulid}') or "
                f"set_species_map(calc_ulid='{calc_ulid}', ...) first."
            ),
        )

    # --- run ---
    try:
        result_dto = svc.run.run_calculation(calc_ulid, run_mode=run_mode)
    except Exception as exc:
        return make_error(
            "execution_failed",
            f"Calculation run failed: {exc}",
            context_hint="Check engine installation and calculation parameters.",
        )

    # Build step summaries from the DTO
    steps_out: list[dict] = []
    for s in result_dto.steps:
        steps_out.append({
            "step_ulid": s.step_ulid,
            "step_type_gen": s.step_type_gen,
            "step_type_spec": s.step_type_spec,
            "status": s.status or "unknown",
            "message": s.message,
        })

    status = result_dto.status  # "completed" or "failed"

    payload: dict = {
        "calc_ulid": result_dto.calc_ulid,
        "run_ulid": result_dto.run_ulid,
        "status": status,
        "steps": steps_out,
        "io_dir": result_dto.io_dir,
    }

    # --- Resolve workflow for enrichment ---
    workflow = ""
    steps_raw = detail.get("steps", [])
    if steps_raw:
        workflow = steps_raw[0].get("step_type_gen", "")

    # --- Parse digest (needed for both success and failure analysis) ---
    digest = _try_parse_digest(detail)

    if status == "completed":
        # Check for "completed but not converged": QE exits normally
        # but SCF didn't actually converge (no '!' total energy line).
        if digest and digest.get("total_energy_ry") is None and digest.get("n_iterations", 0) > 0:
            # QE ran to electron_maxstep but didn't converge
            try:
                from quantumvitas.mcp.error_enrichment import enrich_run_error

                # Override the digest converged flag — QE said "JOB DONE"
                # but there's no converged energy.
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
        if _is_relax_workflow(workflow):
            hint += (
                f" For the relaxed geometry, use promote_structure(calc_ulid='{result_dto.calc_ulid}') "
                "to extract and register it as a new structure."
            )
        return make_response(payload, context_hint=hint)

    # --- Failed: enrich with diagnostics + suggested_fixes ---
    try:
        from quantumvitas.mcp.error_enrichment import enrich_run_error

        enriched = enrich_run_error(
            calc_ulid=calc_ulid,
            result_dto=result_dto,
            digest=digest,
            engine=engine,
            workflow=workflow,
        )
        # Merge run payload into the enriched error for completeness
        enriched["data"] = payload
        return enriched
    except Exception:
        # Fallback to basic error if enrichment fails
        return make_response(
            payload,
            context_hint="Check step messages for failure details.",
            warnings=["Calculation did not complete successfully."],
            status="error",
        )


def _is_relax_workflow(workflow: str) -> bool:
    """Check if the workflow involves structural relaxation."""
    return workflow in {"relax", "minimize"}


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
            # Try engine-agnostic parser registry first
            try:
                import quantumvitas.drivers  # noqa: F401
                from quantumvitas.parsers.registry import find_parser_for_raw

                parser_cls = find_parser_for_raw(candidate, "scf_digest")
                if parser_cls is not None:
                    parser = parser_cls()
                    digest = parser.parse(candidate)
                    return digest.to_dict() if hasattr(digest, "to_dict") else digest
            except Exception:
                pass

            # Fallback: QE parser directly
            try:
                from quantumvitas.drivers.qe.parsers.output import QEOutputParser

                parser = QEOutputParser()
                if parser.can_parse(candidate):
                    return parser.parse(candidate).to_dict()
            except Exception:
                pass

    return None
