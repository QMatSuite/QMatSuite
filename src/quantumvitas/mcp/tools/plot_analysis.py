"""plot_analysis tool — full parse + render for a calculation analysis."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def plot_analysis(calc_ulid: str, object_type: str, step: int = -1) -> dict:
    """Parse and visualize an analysis result for a calculation step.

    Produces ASCII text rendering (always) and a PNG plot (when the
    object type is plottable). Uses the Mode B analysis path to parse
    output files directly from the calculation directory.

    Returns a compact response (~200-300 tokens) with:
    - ascii_plot: fixed-size ASCII rendering
    - plot_files: paths to generated PNG files
    - summary: key scalar values extracted from the analysis
    - primitive_meta: series metadata (names, ranges) without raw data
    - evidence_files: source file info with mtime for staleness detection

    Raw array data (series x/y, eigenvalue matrices, DOS grids) is NEVER
    included in the response to protect the agent's context window.

    Args:
        calc_ulid: ULID of the target calculation.
        object_type: Analysis type to render (e.g. 'convergence', 'dos', 'bands').
        step: Zero-based step index (-1 = last step).
    """
    import os
    from datetime import datetime, timezone
    from pathlib import Path

    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

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
        return make_error("no_engine", "Calculation has no engine_family set.")

    # --- Mode B: get analysis instances for the step ---
    try:
        result = svc.analysis.get_analysis_instances_for_step(calc_ulid, step_ulid)
    except Exception as exc:
        return make_error(
            "analysis_error",
            f"Analysis retrieval failed: {exc}",
        )

    instances = result.get("instances", [])

    # Find matching instance by object_type
    match = None
    for inst in instances:
        if inst.get("object_type", "").lower() == object_type.lower():
            match = inst
            break

    if match is None:
        available = [inst.get("object_type", "") for inst in instances]
        hint = (
            f"Use list_analyses(calc_ulid='{calc_ulid}', step={step_idx}) "
            "to see available types."
        )
        return make_error(
            "not_available",
            f"Analysis type '{object_type}' not available for this step. "
            f"Available: {available}",
            context_hint=hint,
        )

    state = match.get("state", "")
    if state != "ok":
        return make_error(
            "parse_failed",
            f"Analysis '{object_type}' parse state: {state}. "
            "Evidence files may be missing or output format unsupported.",
            context_hint="Ensure the calculation has been run successfully.",
        )

    # --- reconstruct bundle (lives only in this function scope) ---
    from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle

    bundle_dict = match.get("bundle")
    if not bundle_dict:
        return make_error(
            "no_bundle",
            f"Analysis '{object_type}' returned ok state but no bundle data.",
        )

    bundle = CanonicalPrimitiveBundle.from_dict(bundle_dict)

    # --- render ASCII (fixed size, ~70x18 chars) ---
    from quantumvitas.mcp.renderers.ascii_renderer import render_bundle_ascii

    ascii_text = render_bundle_ascii(bundle)

    # --- render PNG (best-effort) ---
    calc_dir = Path(detail.get("absolute_path", ""))
    plot_files = []
    try:
        from quantumvitas.mcp.renderers.matplotlib_renderer import render_bundle_png

        scratch_dir = calc_dir / ".scratch"
        png_output = scratch_dir / f"{object_type}_step{step_idx}.png"
        png_result = render_bundle_png(bundle, png_output)
        if png_result is not None:
            plot_files.append(str(png_result))
    except Exception:
        pass  # Best-effort: PNG rendering is optional

    # --- extract summary scalars (no raw arrays) ---
    summary = _extract_summary(bundle, object_type)

    # --- primitive_meta: series metadata without raw data ---
    primitive_meta = _extract_primitive_meta(bundle)

    # --- evidence_files: source file info for staleness detection ---
    evidence_files = _collect_evidence_files(bundle, calc_dir, step_ulid, step_info)

    # Bundle is consumed — let GC reclaim array memory
    del bundle, bundle_dict

    hint = (
        f"Use list_analyses(calc_ulid='{calc_ulid}') to see other available analyses."
    )
    return make_response(
        {
            "object_type": object_type,
            "step_index": step_idx,
            "engine": engine,
            "summary": summary,
            "ascii_plot": ascii_text,
            "plot_files": plot_files,
            "evidence_files": evidence_files,
            "primitive_meta": primitive_meta,
        },
        context_hint=hint,
    )


def _extract_summary(bundle, object_type: str) -> dict:
    """Extract key scalar values from a bundle — no raw arrays."""
    summary: dict = {}

    extra = bundle.render_meta.extra or {}
    # Pull scalar values from render_meta.extra (scf_digest stores data here)
    for key in ("converged", "total_energy_eV", "fermi_energy_eV",
                "n_iterations", "band_gap_eV"):
        if key in extra:
            summary[key] = extra[key]

    if bundle.series:
        s0 = bundle.series[0]
        y_vals = s0.y
        if len(y_vals) > 0:
            summary["final_value"] = float(y_vals[-1])
            summary["n_points"] = len(y_vals)

    if bundle.geometry_frames is not None:
        summary["n_frames"] = len(bundle.geometry_frames.frames)

    # Markers (Fermi energy etc.)
    for marker in bundle.render_meta.markers:
        key = marker.label.lower().replace(" ", "_")
        summary[key] = marker.position

    return summary


def _extract_primitive_meta(bundle) -> dict:
    """Series metadata (names, ranges) without raw data."""
    meta: dict = {
        "n_series": len(bundle.series),
        "series_names": [],
        "has_geometry_frames": bundle.geometry_frames is not None,
    }

    for i, s in enumerate(bundle.series):
        name = s.name or f"series_{i}"
        meta["series_names"].append(name)

    # x/y ranges from first series (compact)
    if bundle.series:
        s0 = bundle.series[0]
        if len(s0.x) > 0:
            meta["x_range"] = [float(s0.x.min()), float(s0.x.max())]
            meta["y_range"] = [float(s0.y.min()), float(s0.y.max())]

    meta["axis_labels"] = bundle.render_meta.axis_labels
    meta["units"] = bundle.render_meta.units
    meta["n_markers"] = len(bundle.render_meta.markers)

    return meta


def _collect_evidence_files(bundle, calc_dir, step_ulid: str, step_info: dict) -> list:
    """Collect mtime/size of evidence files the parser consumed."""
    import os
    from datetime import datetime, timezone

    evidence = []

    # Try provenance source_files first (SourceFileStat dataclass)
    if bundle.provenance_meta and bundle.provenance_meta.source_files:
        for sf in bundle.provenance_meta.source_files:
            sf_path = getattr(sf, "path", "")
            sf_mtime = getattr(sf, "mtime", None)
            sf_size = getattr(sf, "size_bytes", None)
            entry = {"name": os.path.basename(sf_path) if sf_path else str(sf)}
            if sf_mtime is not None:
                entry["mtime"] = datetime.fromtimestamp(
                    sf_mtime, tz=timezone.utc
                ).isoformat()
            if sf_size is not None:
                entry["size_bytes"] = sf_size
            evidence.append(entry)

    # Fallback: scan raw directory for output files
    if not evidence:
        from quantumvitas.mcp.tools.list_analyses import _resolve_evidence_dir
        gen_step = step_info.get("step_type_gen", "")
        edir = _resolve_evidence_dir(calc_dir, step_ulid, gen_step)
        if edir.is_dir():
            try:
                for f in sorted(edir.iterdir()):
                    if f.is_file() and f.suffix in (".out", ".dat", ".xml", ".gnu"):
                        stat = os.stat(f)
                        evidence.append({
                            "name": f.name,
                            "mtime": datetime.fromtimestamp(
                                stat.st_mtime, tz=timezone.utc
                            ).isoformat(),
                            "size_bytes": stat.st_size,
                        })
            except OSError:
                pass

    return evidence
