"""list_analyses tool — enumerate available analysis types for a calculation step."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def list_analyses(calc_ulid: str, step: int = -1) -> dict:
    """List available analysis types for a calculation step.

    Enumerates what analysis types (convergence, dos, bands, etc.) are
    available for a given step WITHOUT doing full parsing.  Evidence file
    existence is checked to indicate whether data is present.

    Args:
        calc_ulid: ULID of the target calculation.
        step: Zero-based step index (-1 = last step).
    """
    from pathlib import Path

    from qmatsuite.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- resolve calc + step ---
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception as exc:
        return make_error("not_found", f"Calculation '{calc_ulid}' not found: {exc}")

    steps_raw = detail.get("steps", [])
    if not steps_raw:
        return make_error("no_steps", "Calculation has no steps.")

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

    engine = detail.get("engine_family", "")
    if not engine:
        return make_error(
            "no_engine",
            "Calculation has no engine_family set.",
        )

    # --- get driver + capabilities ---
    try:
        import qmatsuite.drivers  # noqa: F401 — trigger registration
        from qmatsuite.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver(engine)
        capabilities = getattr(driver, "ANALYSIS_CAPABILITIES", []) or []
    except Exception as exc:
        return make_error("driver_error", f"Cannot load driver for '{engine}': {exc}")

    if not capabilities:
        return make_response(
            {"analyses": [], "step_index": step_idx, "step_ulid": step_ulid, "engine": engine},
            context_hint=f"Engine '{engine}' has no declared analysis capabilities.",
        )

    # --- build ordered_gen_steps from calc detail ---
    from qmatsuite.core.analysis.capability import enumerate_all_matches

    ordered_gen_steps: list[tuple[str, str, Path]] = []
    calc_dir = Path(detail.get("absolute_path", ""))

    for s in steps_raw:
        s_ulid = s.get("step_ulid") or s.get("ulid", "")
        s_gen = s.get("step_type_gen", "")
        if not s_ulid or not s_gen:
            continue
        # Best-effort evidence dir resolution
        evidence_dir = _resolve_evidence_dir(calc_dir, s_ulid, s_gen)
        ordered_gen_steps.append((s_ulid, s_gen, evidence_dir))

    matches = enumerate_all_matches(capabilities, ordered_gen_steps)
    relevant = [m for m in matches if step_ulid in m.step_ulids]

    # --- check evidence file existence ---
    analyses = []
    for match in relevant:
        evidence_available = False
        if match.evidence_dirs:
            primary_dir = match.evidence_dirs[0]
            if primary_dir.is_dir():
                # Find matching capability for evidence_files list
                cap = _find_capability(capabilities, match.object_type, match.gen_steps)
                if cap and cap.evidence_files:
                    import fnmatch
                    try:
                        files = [f.name for f in primary_dir.iterdir() if f.is_file()]
                        evidence_available = any(
                            any(fnmatch.fnmatch(f, pat) for f in files)
                            for pat in cap.evidence_files
                        )
                    except OSError:
                        pass
                else:
                    # No specific evidence_files — just check dir is non-empty
                    try:
                        evidence_available = any(primary_dir.iterdir())
                    except OSError:
                        pass

        analyses.append({
            "object_type": match.object_type,
            "gen_steps": match.gen_steps,
            "evidence_available": evidence_available,
        })

    hint = (
        f"Use plot_analysis(calc_ulid='{calc_ulid}', object_type='<type>') "
        "to parse and render an analysis."
    )
    return make_response(
        {
            "analyses": analyses,
            "step_index": step_idx,
            "step_ulid": step_ulid,
            "engine": engine,
        },
        context_hint=hint,
    )


def _resolve_evidence_dir(calc_dir, step_ulid: str, gen_step: str):
    """Best-effort evidence dir resolution mirroring QMSService._find_step_evidence_dir."""
    from pathlib import Path

    raw_dir = calc_dir / "raw"
    if not raw_dir.is_dir():
        return raw_dir

    # Priority: raw/<step_ulid>/ → raw/step_artifacts/<step_ulid>/ → raw/
    step_raw = raw_dir / step_ulid
    if step_raw.is_dir():
        try:
            if any(step_raw.iterdir()):
                return step_raw
        except OSError:
            pass

    artifacts = raw_dir / "step_artifacts" / step_ulid
    if artifacts.is_dir():
        try:
            if any(artifacts.iterdir()):
                return artifacts
        except OSError:
            pass

    return raw_dir


def _find_capability(capabilities, object_type: str, gen_steps: list[str]):
    """Find the matching AnalysisCapability for a given match."""
    for cap in capabilities:
        if cap.object_type == object_type and list(cap.gen_step_sequence) == gen_steps:
            return cap
    # Fallback: match just object_type
    for cap in capabilities:
        if cap.object_type == object_type:
            return cap
    return None
