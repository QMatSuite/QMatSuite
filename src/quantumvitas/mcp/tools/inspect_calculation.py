"""inspect_calculation tool — read back calculation state."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def inspect_calculation(calc_ulid: str, step: int = -1) -> dict:
    """Inspect a calculation's current configuration.

    With the default ``step=-1`` an overview of all steps is returned.
    Pass a zero-based step index to get the full parameter detail for that
    specific step.

    Args:
        calc_ulid: ULID of the target calculation.
        step: Step index to inspect in detail (-1 = overview only).
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- overview ---
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception as exc:
        return make_error(
            "not_found",
            f"Calculation '{calc_ulid}' not found: {exc}",
        )

    steps_raw = detail.get("steps", [])

    # Build step summaries
    steps_out: list[dict] = []
    for idx, s in enumerate(steps_raw):
        entry: dict = {
            "step_index": idx,
            "step_type_gen": s.get("step_type_gen"),
            "step_type_spec": s.get("step_type_spec"),
            "step_ulid": s.get("step_ulid") or s.get("ulid", ""),
            "status": s.get("status", "pending"),
        }
        steps_out.append(entry)

    payload: dict = {
        "calc_ulid": detail.get("calc_ulid") or detail.get("ulid", calc_ulid),
        "name": detail.get("name", ""),
        "engine": detail.get("engine_family", ""),
        "structure": detail.get("structure_name") or detail.get("structure"),
        "n_steps": detail.get("n_steps", len(steps_out)),
        "steps": steps_out,
    }

    # --- optional step detail ---
    if step >= 0:
        if step >= len(steps_raw):
            return make_error(
                "invalid_step_index",
                f"Step index {step} out of range (calculation has {len(steps_raw)} step(s)).",
            )
        step_ulid = steps_out[step]["step_ulid"]
        try:
            step_detail = svc.calculation.get_step_detail(calc_ulid, step_ulid)
            payload["step_detail"] = {
                "step_index": step,
                "step_ulid": step_ulid,
                "parameters": step_detail.get("parameters", {}),
                "cards": step_detail.get("cards", {}),
            }
        except Exception as exc:
            payload["step_detail_error"] = str(exc)

    return make_response(
        payload,
        context_hint="Use set_parameters to adjust, or run_calculation to execute.",
    )
