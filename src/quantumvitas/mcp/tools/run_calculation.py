"""run_calculation tool — execute a calculation synchronously."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def run_calculation(calc_ulid: str) -> dict:
    """Run a calculation synchronously.

    Blocks until the engine finishes and returns the final status
    (completed or failed).  The calculation must already have steps
    configured via create_calculation + set_parameters / apply_preset.

    On failure, returns structured diagnostics and knowledge-backed
    suggested_fixes so the agent can diagnose and recover.

    Args:
        calc_ulid: ULID of the calculation to run.
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

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

    # --- run ---
    try:
        result_dto = svc.run.run_calculation(calc_ulid)
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

    # --- Resolve engine/workflow for enrichment ---
    engine = detail.get("engine_family", "")
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

        return make_response(
            payload,
            context_hint=(
                f"Use get_results_summary(calc_ulid='{result_dto.calc_ulid}') "
                "to see results."
            ),
        )

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


def _try_parse_digest(detail: dict) -> dict | None:
    """Attempt to parse QE output for the first step's digest."""
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
                from quantumvitas.drivers.qe.parsers.output import QEOutputParser

                parser = QEOutputParser()
                if parser.can_parse(candidate):
                    return parser.parse(candidate).to_dict()
            except Exception:
                pass

    return None
