"""get_results_summary tool — compact results after a run."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response

# Unit conversion factors
_RY_TO_EV = 13.605693123
_HA_TO_EV = 27.211386245988


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
    if step_type_gen in {"relax", "minimize"}:
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
        step_ulid = step_info.get("step_ulid") or step_info.get("ulid", "")

        # Try common patterns, including ULID-based subdirs (xTB ISOLATED workdir policy)
        candidates = [
            calc_path / "raw" / step_slug,
            calc_path / "raw" / step_ulid,  # xTB: raw/<step_ulid>/
            calc_path / "raw",
        ]
        for candidate in candidates:
            if candidate and candidate.is_dir():
                return candidate

    return None


def _parse_direct(raw_dir):
    """Direct parse via engine-agnostic parser registry."""
    try:
        # Trigger driver registration so all parsers are available
        import quantumvitas.drivers  # noqa: F401

        from quantumvitas.parsers.registry import find_parser_for_raw

        parser_cls = find_parser_for_raw(raw_dir, "scf_digest")
        if parser_cls is not None:
            parser = parser_cls()
            digest = parser.parse(raw_dir)
            return digest.to_dict() if hasattr(digest, "to_dict") else digest
    except Exception:
        pass

    # Fallback: try QE parser directly (in case registry lookup failed)
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
    """Build the compact MCP-friendly results dict.

    Handles multiple energy unit conventions:
    - QE: total_energy_ry (Rydberg)
    - VASP, xTB, LAMMPS: total_energy_ev (eV)
    - ORCA, Gaussian, QMCPACK: total_energy_ha (Hartree)
    """
    # Resolve total energy to eV from whichever unit the digest provides.
    # Handle multiple engine naming conventions:
    #   QE:   total_energy_ry  (Rydberg)
    #   VASP: total_energy_ev  (eV)
    #   ORCA/Gaussian/QMCPACK: total_energy_ha  (Hartree)
    #   xTB:  final_energy_eV or final_energy_Ha  (xTB-specific names from XTBDigest.to_dict())
    total_energy_ev = digest.get("total_energy_ev")
    total_energy_ry = digest.get("total_energy_ry")
    total_energy_ha = digest.get("total_energy_ha")

    if total_energy_ev is None:
        if total_energy_ry is not None:
            total_energy_ev = total_energy_ry * _RY_TO_EV
        elif total_energy_ha is not None:
            total_energy_ev = total_energy_ha * _HA_TO_EV
        else:
            # xTB: final_energy_eV (note capital E, V — exact field name from XTBDigest)
            xtb_ev = digest.get("final_energy_eV")
            if xtb_ev is not None:
                total_energy_ev = xtb_ev
            else:
                xtb_ha = digest.get("final_energy_Ha")
                if xtb_ha is not None:
                    total_energy_ev = xtb_ha * _HA_TO_EV

    # Convergence: xTB uses 'success' (single-point) and 'converged_geometry' (opt)
    converged = digest.get("converged", False)
    if not converged:
        converged = bool(
            digest.get("success", False) or digest.get("converged_geometry", False)
        )

    # Iteration count: xTB uses 'n_opt_cycles' for geometry optimization cycles
    n_iterations = digest.get("n_iterations") or digest.get("n_opt_cycles") or 0

    # Wall time: xTB uses 'wall_time_s'
    wall_time = digest.get("total_wall_time_s") or digest.get("wall_time_s")

    # Fermi energy: xTB uses 'homo_lumo_gap_eV' (not an energy level, but best proxy)
    fermi_ev = digest.get("fermi_energy_ev")

    summary: dict = {
        "step_index": step_idx,
        "step_type_gen": step_type_gen,
        "run_ulid": run_ulid,
        "converged": converged,
        "total_energy_eV": total_energy_ev,
        "total_energy_ry": total_energy_ry,
        "fermi_energy_eV": fermi_ev,
        "band_gap_eV": digest.get("band_gap_ev"),
        "n_iterations": n_iterations,
        "wall_time_seconds": wall_time,
    }

    # Include magnetization if present (GAP-1)
    total_mag = digest.get("total_magnetization")
    abs_mag = digest.get("absolute_magnetization")
    if total_mag is not None:
        summary["total_magnetization"] = total_mag
    if abs_mag is not None:
        summary["absolute_magnetization"] = abs_mag

    return summary
