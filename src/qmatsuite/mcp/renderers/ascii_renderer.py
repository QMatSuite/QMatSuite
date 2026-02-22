"""Builtin unicode-block ASCII renderer for CanonicalPrimitiveBundle.

Pure stdlib — no external dependencies. Renders 80-column fixed-width text.

Series1D-bearing analysis types (convergence, dos, bands, trajectory) are
rendered as 2D terminal charts via :class:`TerminalChart`.  Other types
(scf_digest, field3d) use their own bespoke formatters.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle

# Block characters for bar charts (5 levels: empty → full)
_BLOCKS = " ░▒▓█"

# Object types that carry Series1D data and should be rendered as 2D charts
_CHART_TYPES = {"convergence", "dos", "bands", "trajectory"}


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


def render_bundle_to_ascii(bundle: CanonicalPrimitiveBundle,
                           width: int = 78, height: int = 16) -> str:
    """Render any bundle with Series1D data to a 2D terminal chart string.

    Uses plotext as the primary renderer (higher quality braille/block output).
    Falls back to the built-in TerminalChart if plotext is unavailable.
    """
    if not bundle.series:
        return f"=== {bundle.object_type.upper()} ===\n\n(no data)"

    # Try plotext first (primary renderer)
    try:
        from qmatsuite.mcp.renderers.plotext_renderer import (
            render_bundle_with_plotext,
        )
        return render_bundle_with_plotext(bundle, width=width, height=height + 2)
    except Exception:
        pass

    # Fallback: built-in TerminalChart
    return _render_with_terminal_chart(bundle, width=width, height=height)


def _render_with_terminal_chart(bundle: CanonicalPrimitiveBundle,
                                width: int = 78, height: int = 16) -> str:
    """Fallback renderer using the built-in TerminalChart (pure stdlib)."""
    from qmatsuite.mcp.renderers.terminal_chart import TerminalChart

    chart = TerminalChart(width=width, height=height,
                          title=bundle.object_type.upper())

    for series in bundle.series:
        xy = [
            (xi, yi)
            for xi, yi in zip(series.x.tolist(), series.y.tolist())
            if math.isfinite(xi) and math.isfinite(yi)
        ]
        if xy:
            xs, ys = zip(*xy)
            chart.add_series(list(xs), list(ys), label=series.name or "")

    if bundle.render_meta:
        xl = bundle.render_meta.axis_labels.get("x", "")
        yl = bundle.render_meta.axis_labels.get("y", "")
        if xl:
            chart.set_xlabel(xl)
        if yl:
            chart.set_ylabel(yl)
        for marker in bundle.render_meta.markers:
            if marker.axis == "y":
                chart.add_hline(marker.position, label=marker.label)
            else:
                chart.add_vline(marker.position, label=marker.label)
        if bundle.render_meta.reference_energy is not None:
            chart.add_hline(bundle.render_meta.reference_energy, label="E_ref")

    return chart.render()


def render_bundle_ascii(bundle: CanonicalPrimitiveBundle) -> str:
    """Render a CanonicalPrimitiveBundle as 80-column ASCII text.

    Series1D-bearing types (convergence, dos, bands, trajectory) are rendered
    as 2D terminal charts.  Other types use bespoke formatters.
    """
    obj_type = bundle.object_type.lower()

    if obj_type in _CHART_TYPES:
        return render_bundle_to_ascii(bundle)

    dispatch = {
        "scf_digest": _render_scf_digest,
        "field3d": _render_field3d,
    }
    return dispatch.get(obj_type, _render_generic)(bundle)


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
