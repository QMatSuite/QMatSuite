"""get_status tool — query historical run state for a calculation."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def get_status(calc_ulid: str) -> dict:
    """Check the run state of all steps in a calculation.

    Use after run_calculation to verify completion or diagnose failure.
    Reports whether each step has been executed and what the outcome was.

    Args:
        calc_ulid: ULID of the target calculation.
    """
    from qmatsuite.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- get calc detail ---
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception as exc:
        return make_error(
            "not_found",
            f"Calculation '{calc_ulid}' not found: {exc}",
        )

    steps_raw = detail.get("steps", [])

    # --- query provenance for each step ---
    steps_out: list[dict] = []
    has_completed = False
    has_failed = False
    all_not_run = True

    # Resolve calc dir for output file checks
    calc_dir = detail.get("absolute_path")

    for idx, s in enumerate(steps_raw):
        step_ulid = s.get("step_ulid") or s.get("ulid", "")
        step_type_gen = s.get("step_type_gen")
        step_status = "not_run"
        run_ulid = None

        if step_ulid:
            try:
                run_info = svc.history.get_latest_run_for_step(step_ulid)
                if run_info.get("run_ulid"):
                    run_ulid = run_info["run_ulid"]
                    step_status = "completed"
                    has_completed = True
                    all_not_run = False
            except Exception:
                pass

        # If no successful run recorded, check for output files that
        # indicate a run happened but failed (exit code != 0, not
        # recorded as success in provenance).
        if step_status == "not_run" and calc_dir:
            from pathlib import Path

            step_slug = s.get("slug") or s.get("name", "")
            raw_dir = Path(calc_dir) / "raw" / step_slug
            if not raw_dir.is_dir():
                raw_dir = Path(calc_dir) / "raw"
            if raw_dir.is_dir():
                out_files = list(raw_dir.glob("*.out")) + list(raw_dir.glob("*.log"))
                if out_files:
                    step_status = "failed"
                    has_failed = True
                    all_not_run = False

        steps_out.append({
            "step_index": idx,
            "step_ulid": step_ulid,
            "step_type_gen": step_type_gen,
            "status": step_status,
            "run_ulid": run_ulid,
        })

    # Determine overall status
    if all_not_run:
        overall_status = "not_run"
    elif has_failed:
        overall_status = "failed"
    elif has_completed:
        overall_status = "completed"
    else:
        overall_status = "partial"

    # Detect relax workflow from step types
    gen_types = {s.get("step_type_gen", "") for s in steps_raw}
    is_relax = bool(gen_types & {"relax", "minimize"})

    # Context hint depends on status
    resolved_ulid = detail.get("calc_ulid") or detail.get("ulid", calc_ulid)
    if overall_status == "not_run":
        hint = f"Use run_calculation(calc_ulid='{resolved_ulid}') to execute this calculation."
    elif overall_status == "failed":
        hint = (
            f"One or more steps failed. Use get_results_summary(calc_ulid='{resolved_ulid}') "
            "for diagnostics, or inspect_calculation(dry_run=True) to check parameters."
        )
    elif overall_status == "completed":
        hint = (
            f"Use get_results_summary(calc_ulid='{resolved_ulid}') "
            "to see results."
        )
        if is_relax:
            hint += (
                f" Use promote_structure(calc_ulid='{resolved_ulid}') to extract "
                "the relaxed geometry as a new structure."
            )
    else:
        hint = f"Some steps have not been run. Use run_calculation(calc_ulid='{resolved_ulid}') to execute."

    return make_response(
        {
            "calc_ulid": detail.get("calc_ulid") or detail.get("ulid", calc_ulid),
            "overall_status": overall_status,
            "n_steps": len(steps_out),
            "steps": steps_out,
        },
        context_hint=hint,
    )
