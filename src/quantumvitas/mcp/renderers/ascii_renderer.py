"""Builtin unicode-block ASCII renderer for CanonicalPrimitiveBundle.

Pure stdlib — no external dependencies. Renders 80-column fixed-width text.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle

# Block characters for bar charts (5 levels: empty → full)
_BLOCKS = " ░▒▓█"


def _sparkline(values: list[float], width: int = 40) -> str:
    """Render a sparkline string using Unicode block characters."""
    if not values:
        return ""
    v_min = min(values)
    v_max = max(values)
    span = v_max - v_min
    if span == 0:
        return "▄" * min(len(values), width)

    # Resample to width if needed
    if len(values) > width:
        step = len(values) / width
        resampled = [values[int(i * step)] for i in range(width)]
    else:
        resampled = list(values)

    chars = " ▁▂▃▄▅▆▇█"
    result = []
    for v in resampled:
        idx = int((v - v_min) / span * (len(chars) - 1))
        idx = max(0, min(idx, len(chars) - 1))
        result.append(chars[idx])
    return "".join(result)


def _unicode_bar(value: float, max_val: float, width: int = 40) -> str:
    """Render a horizontal bar using Unicode block characters."""
    if max_val <= 0 or value <= 0:
        return ""
    ratio = min(value / max_val, 1.0)
    full_blocks = int(ratio * width)
    remainder = (ratio * width) - full_blocks
    bar = "█" * full_blocks
    if remainder > 0.0 and full_blocks < width:
        frac_idx = int(remainder * (len(_BLOCKS) - 1))
        bar += _BLOCKS[max(1, frac_idx)]
    return bar


def render_bundle_ascii(bundle: CanonicalPrimitiveBundle) -> str:
    """Render a CanonicalPrimitiveBundle as 80-column ASCII text.

    Dispatches on ``bundle.object_type`` to specialized formatters.
    """
    obj_type = bundle.object_type.lower()

    dispatch = {
        "convergence": _render_convergence,
        "dos": _render_dos,
        "bands": _render_bands,
        "scf_digest": _render_scf_digest,
        "trajectory": _render_trajectory,
        "field3d": _render_field3d,
    }

    renderer = dispatch.get(obj_type, _render_generic)
    return renderer(bundle)


def _render_convergence(bundle: CanonicalPrimitiveBundle) -> str:
    """Convergence: iteration vs energy table + sparkline."""
    lines = ["=== Convergence ===", ""]

    if not bundle.series:
        lines.append("(no data)")
        return "\n".join(lines)

    s = bundle.series[0]
    x_vals = s.x.tolist()
    y_vals = s.y.tolist()

    x_label = s.x_label or "Iteration"
    y_label = s.y_label or "Energy"
    y_unit = f" ({s.y_unit})" if s.y_unit else ""

    lines.append(f"  {x_label:<12s}  {y_label}{y_unit}")
    lines.append("  " + "-" * 40)

    for x, y in zip(x_vals, y_vals):
        x_str = f"{int(x)}" if x == int(x) else f"{x:.2f}"
        lines.append(f"  {x_str:<12s}  {y:.8f}")

    lines.append("")
    lines.append("Sparkline: " + _sparkline(y_vals))
    lines.append(f"  range: {min(y_vals):.6f} .. {max(y_vals):.6f}")

    return "\n".join(lines)


def _render_dos(bundle: CanonicalPrimitiveBundle) -> str:
    """DOS: horizontal bar chart."""
    lines = ["=== Density of States ===", ""]

    if not bundle.series:
        lines.append("(no data)")
        return "\n".join(lines)

    s = bundle.series[0]
    energies = s.x.tolist()
    dos_vals = s.y.tolist()

    y_unit = f" ({s.y_unit})" if s.y_unit else ""
    lines.append(f"  Energy ({s.x_unit or 'eV'}) vs DOS{y_unit}")
    lines.append("")

    # Sample ~20 rows for display
    n = len(energies)
    step = max(1, n // 20)
    max_dos = max(abs(v) for v in dos_vals) if dos_vals else 1.0

    for i in range(0, n, step):
        e = energies[i]
        d = dos_vals[i]
        bar = _unicode_bar(abs(d), max_dos, width=30)
        lines.append(f"  {e:8.3f} | {bar} {d:.3f}")

    # Fermi marker
    for marker in bundle.render_meta.markers:
        if "fermi" in marker.label.lower():
            lines.append(f"\n  Fermi energy: {marker.position:.4f}")

    return "\n".join(lines)


def _render_bands(bundle: CanonicalPrimitiveBundle) -> str:
    """Bands: summary text (not renderable as ASCII chart)."""
    lines = ["=== Band Structure ===", ""]

    n_bands = len(bundle.series)
    if n_bands == 0:
        lines.append("(no data)")
        return "\n".join(lines)

    n_kpoints = len(bundle.series[0].x) if bundle.series else 0

    all_energies = []
    for s in bundle.series:
        all_energies.extend(s.y.tolist())

    e_min = min(all_energies) if all_energies else 0.0
    e_max = max(all_energies) if all_energies else 0.0

    lines.append(f"  Bands:    {n_bands}")
    lines.append(f"  K-points: {n_kpoints}")
    lines.append(f"  Energy range: {e_min:.4f} .. {e_max:.4f}")

    if bundle.series[0].y_unit:
        lines.append(f"  Energy unit: {bundle.series[0].y_unit}")

    for marker in bundle.render_meta.markers:
        if "fermi" in marker.label.lower():
            lines.append(f"  Fermi energy: {marker.position:.4f}")

    return "\n".join(lines)


def _render_scf_digest(bundle: CanonicalPrimitiveBundle) -> str:
    """SCF digest: key-value summary table."""
    lines = ["=== SCF Digest ===", ""]

    extra = bundle.render_meta.extra or {}
    if extra:
        max_key_len = max(len(str(k)) for k in extra)
        for k, v in extra.items():
            lines.append(f"  {str(k):<{max_key_len}s}  {v}")
    elif bundle.series:
        s = bundle.series[0]
        lines.append(f"  {s.y_label or 'Value'}: {s.y.tolist()[-1]:.8f} {s.y_unit or ''}")
    else:
        lines.append("(no data)")

    return "\n".join(lines)


def _render_trajectory(bundle: CanonicalPrimitiveBundle) -> str:
    """Trajectory: frame count + energy sparkline."""
    lines = ["=== Trajectory ===", ""]

    if bundle.geometry_frames is not None:
        n_frames = len(bundle.geometry_frames.frames)
        lines.append(f"  Frames: {n_frames}")
        if bundle.geometry_frames.frames:
            n_atoms = bundle.geometry_frames.frames[0].n_atoms
            lines.append(f"  Atoms:  {n_atoms}")

    if bundle.series:
        s = bundle.series[0]
        y_vals = s.y.tolist()
        lines.append(f"  {s.y_label or 'Energy'} ({s.y_unit or 'eV'}):")
        lines.append(f"    first: {y_vals[0]:.6f}")
        lines.append(f"    last:  {y_vals[-1]:.6f}")
        lines.append(f"    min:   {min(y_vals):.6f}")
        lines.append(f"    max:   {max(y_vals):.6f}")
        lines.append("")
        lines.append("  Sparkline: " + _sparkline(y_vals))

    if not bundle.series and bundle.geometry_frames is None:
        lines.append("(no data)")

    return "\n".join(lines)


def _render_field3d(bundle: CanonicalPrimitiveBundle) -> str:
    """Field3D: grid dimensions + value range summary."""
    lines = ["=== Field3D ===", ""]

    extra = bundle.render_meta.extra or {}
    grid = extra.get("grid_dims") or extra.get("grid_shape")
    if grid:
        lines.append(f"  Grid: {grid}")

    val_range = extra.get("value_range")
    if val_range:
        lines.append(f"  Value range: {val_range}")

    if bundle.arrays:
        for key, arr in bundle.arrays.items():
            if hasattr(arr, "shape"):
                lines.append(f"  Array '{key}': shape {arr.shape}")
            elif isinstance(arr, list):
                lines.append(f"  Array '{key}': {len(arr)} elements")

    if len(lines) == 2:
        lines.append("(3D volumetric data — not renderable in ASCII)")

    return "\n".join(lines)


def _render_generic(bundle: CanonicalPrimitiveBundle) -> str:
    """Fallback for unknown object types."""
    lines = [f"=== {bundle.object_type} ===", ""]
    lines.append(f"  Series: {len(bundle.series)}")
    for i, s in enumerate(bundle.series):
        name = s.name or f"series_{i}"
        lines.append(f"    [{i}] {name}: {len(s.x)} points")
    if bundle.geometry_frames:
        lines.append(f"  Geometry frames: {len(bundle.geometry_frames.frames)}")
    if bundle.arrays:
        lines.append(f"  Arrays: {list(bundle.arrays.keys())}")
    return "\n".join(lines)
