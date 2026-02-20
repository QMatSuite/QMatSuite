"""plotext-based ASCII renderer for MCP analysis output.

Uses plotext for high-quality terminal charts with braille/block characters
and proper axis rendering.  Falls back gracefully if plotext is unavailable.
"""
from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle

import plotext as plt

# Regex to strip ANSI escape codes from plotext output
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def render_bundle_with_plotext(
    bundle: CanonicalPrimitiveBundle,
    width: int = 78,
    height: int = 20,
) -> str:
    """Render a primitive bundle using plotext.

    Returns a clean ASCII string (no ANSI codes) containing the chart.
    """
    obj_type = bundle.object_type.lower()

    if obj_type == "bands":
        return _render_bands_plotext(bundle, width, height)

    return _render_generic_plotext(bundle, width, height)


def _render_generic_plotext(
    bundle: CanonicalPrimitiveBundle,
    width: int,
    height: int,
) -> str:
    """Generic plotext rendering for convergence, DOS, trajectory, etc."""
    plt.clear_figure()
    plt.plotsize(width, height)
    plt.theme("clear")

    for i, series in enumerate(bundle.series):
        x = series.x.tolist() if hasattr(series.x, "tolist") else list(series.x)
        y = series.y.tolist() if hasattr(series.y, "tolist") else list(series.y)
        # Filter non-finite values
        pairs = [(xi, yi) for xi, yi in zip(x, y)
                 if math.isfinite(xi) and math.isfinite(yi)]
        if not pairs:
            continue
        xs, ys = zip(*pairs)
        label = series.name or f"series_{i}"
        plt.plot(list(xs), list(ys), label=label)

    # Title
    plt.title(bundle.object_type.upper())

    # Axis labels from render_meta
    if bundle.render_meta:
        xl = bundle.render_meta.axis_labels.get("x", "")
        yl = bundle.render_meta.axis_labels.get("y", "")
        if xl:
            plt.xlabel(xl)
        if yl:
            plt.ylabel(yl)

        # Horizontal reference lines (Fermi level, etc.)
        if bundle.render_meta.reference_energy is not None:
            plt.hline(bundle.render_meta.reference_energy)

        # Markers: vertical lines for axis="x", horizontal for axis="y"
        for marker in bundle.render_meta.markers:
            if marker.axis == "y":
                plt.hline(marker.position)
            elif marker.axis == "x":
                plt.vline(marker.position)

    return _ANSI_RE.sub("", plt.build())


def _render_bands_plotext(
    bundle: CanonicalPrimitiveBundle,
    width: int,
    height: int,
) -> str:
    """Specialized bands rendering: E-shift, Fermi line, k-point labels."""
    plt.clear_figure()
    plt.plotsize(width, height)
    plt.theme("clear")

    e_fermi = bundle.render_meta.reference_energy  # may be None

    # Separate k-point markers from other markers
    kpoint_markers = []
    for marker in bundle.render_meta.markers:
        if marker.axis == "x":
            kpoint_markers.append(marker)

    # Plot all bands with same marker style
    for series in bundle.series:
        x = series.x.tolist() if hasattr(series.x, "tolist") else list(series.x)
        y = series.y.tolist() if hasattr(series.y, "tolist") else list(series.y)
        if e_fermi is not None:
            y = [yi - e_fermi for yi in y]
        plt.plot(x, y)

    plt.title("BANDS")

    # Fermi level at 0 after shift
    if e_fermi is not None:
        plt.hline(0.0)
        plt.ylabel("E - E_F (eV)")
    else:
        plt.ylabel("Energy (eV)")

    # K-point labels on x-axis
    if kpoint_markers:
        tick_positions = [m.position for m in kpoint_markers]
        tick_labels = [m.label for m in kpoint_markers]
        plt.xticks(tick_positions, tick_labels)
        for pos in tick_positions:
            plt.vline(pos)

    return _ANSI_RE.sub("", plt.build())
