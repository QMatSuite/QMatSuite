"""get_results_summary tool — compact results after a run."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response

# Ry -> eV conversion factor
_RY_TO_EV = 13.605693123


@mcp.tool
def get_results_summary(calc_ulid: str, step: int = -1) -> dict:
    """Get a compact results summary for a completed calculation step.

    Returns key quantities (energy, convergence, timing) from the most
    recent run.  With the default ``step=-1`` the last step is used.

    Args:
        calc_ulid: ULID of the target calculation.
        step: Zero-based step index (-1 = last step).
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- resolve step ---
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception as exc:
        return make_error(
            "not_found",
            f"Calculation '{calc_ulid}' not found: {exc}",
        )

    steps_raw = detail.get("steps", [])
    if not steps_raw:
        return make_error("no_steps", "Calculation has no steps.")

    # Resolve step index
    if step == -1:
        step_idx = len(steps_raw) - 1
    else:
        step_idx = step

    if step_idx < 0 or step_idx >= len(steps_raw):
        return make_error(
            "invalid_step_index",
            f"Step index {step} out of range (calculation has {len(steps_raw)} step(s)).",
        )

    step_info = steps_raw[step_idx]
    step_ulid = step_info.get("step_ulid") or step_info.get("ulid", "")
    step_type_gen = step_info.get("step_type_gen")

    # --- Strategy A: provenance digest ---
    digest_data = None
    run_ulid = None

    if step_ulid:
        try:
            run_info = svc.history.get_latest_run_for_step(step_ulid)
            run_ulid = run_info.get("run_ulid")
        except Exception:
            pass

    if run_ulid and step_ulid:
        try:
            digest_result = svc.analysis.get_step_digest(run_ulid, step_ulid)
            if digest_result.get("available"):
                digest_data = digest_result.get("digest", {})
        except Exception:
            pass

    # --- Strategy B: direct parser fallback ---
    if digest_data is None:
        raw_dir = _find_raw_dir(detail, step_idx)
        if raw_dir is not None:
            digest_data = _parse_direct(raw_dir)

    if digest_data is None:
        return make_error(
            "no_results",
            f"No results found for step {step_idx}. Has the calculation been run?",
            context_hint="Use run_calculation to execute first.",
        )

    # --- build compact summary ---
    summary = _build_summary(digest_data, step_idx, step_type_gen, run_ulid)

    hint = f"Use inspect_calculation(calc_ulid='{calc_ulid}') for parameter details."
    if step_type_gen in {"relax", "vc-relax", "vc_relax"}:
        hint += (
            f" Use promote_structure(calc_ulid='{calc_ulid}') to extract "
            "the relaxed geometry as a new structure."
        )
    return make_response(summary, context_hint=hint)


def _find_raw_dir(detail: dict, step_idx: int):
    """Try to locate the raw output directory for a step."""
    from pathlib import Path

    calc_dir = detail.get("absolute_path")
    if not calc_dir:
        return None

    calc_path = Path(calc_dir)

    # Look in the step's raw directory
    steps = detail.get("steps", [])
    if step_idx < len(steps):
        step_info = steps[step_idx]
        step_slug = step_info.get("slug") or step_info.get("name", "")

        # Try common patterns
        candidates = [
            calc_path / "raw" / step_slug,
            calc_path / "raw",
        ]
        for candidate in candidates:
            if candidate.is_dir():
                return candidate

    return None


def _parse_direct(raw_dir):
    """Direct parse via QEOutputParser."""
    try:
        from quantumvitas.drivers.qe.parsers.output import QEOutputParser

        parser = QEOutputParser()
        if parser.can_parse(raw_dir):
            digest = parser.parse(raw_dir)
            return digest.to_dict()
    except Exception:
        pass
    return None


def _build_summary(
    digest: dict,
    step_idx: int,
    step_type_gen: str | None,
    run_ulid: str | None,
) -> dict:
    """Build the compact MCP-friendly results dict."""
    total_energy_ry = digest.get("total_energy_ry")
    total_energy_ev = None
    if total_energy_ry is not None:
        total_energy_ev = total_energy_ry * _RY_TO_EV

    return {
        "step_index": step_idx,
        "step_type_gen": step_type_gen,
        "run_ulid": run_ulid,
        "converged": digest.get("converged", False),
        "total_energy_eV": total_energy_ev,
        "total_energy_ry": total_energy_ry,
        "fermi_energy_eV": digest.get("fermi_energy_ev"),
        "band_gap_eV": digest.get("band_gap_ev"),
        "n_iterations": digest.get("n_iterations", 0),
        "wall_time_seconds": digest.get("total_wall_time_s"),
    }
