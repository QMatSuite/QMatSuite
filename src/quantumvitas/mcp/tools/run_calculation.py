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

    if status == "completed":
        return make_response(
            payload,
            context_hint=(
                f"Use get_results_summary(calc_ulid='{result_dto.calc_ulid}') "
                "to see results."
            ),
        )

    # Failed — include error info
    return make_response(
        payload,
        context_hint="Check step messages for failure details.",
        warnings=["Calculation did not complete successfully."],
        status="error",
    )
