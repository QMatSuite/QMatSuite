"""Matplotlib-based PNG renderer for CanonicalPrimitiveBundle.

Uses ``matplotlib.use('Agg')`` for headless operation.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle


def render_bundle_png(
    bundle: CanonicalPrimitiveBundle,
    output_path: Path,
) -> Path | None:
    """Render a CanonicalPrimitiveBundle to a PNG file.

    Returns the output path on success, None if the object_type has no
    visual representation (e.g. scf_digest, field3d).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    obj_type = bundle.object_type.lower()

    dispatch = {
        "convergence": _plot_convergence,
        "dos": _plot_dos,
        "bands": _plot_bands,
        "trajectory": _plot_trajectory,
    }

    plotter = dispatch.get(obj_type)
    if plotter is None:
        return None

    fig = plotter(bundle)
    if fig is None:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _plot_convergence(bundle: CanonicalPrimitiveBundle):
    """Line plot: iteration vs energy."""
    import matplotlib.pyplot as plt

    if not bundle.series:
        return None

    s = bundle.series[0]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(s.x, s.y, "o-", markersize=4)

    x_label = s.x_label or "Iteration"
    y_label = s.y_label or "Energy"
    if s.y_unit:
        y_label += f" ({s.y_unit})"

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title("SCF Convergence")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_dos(bundle: CanonicalPrimitiveBundle):
    """Line plot: energy vs DOS with optional Fermi marker."""
    import matplotlib.pyplot as plt

    if not bundle.series:
        return None

    fig, ax = plt.subplots(figsize=(8, 6))

    for s in bundle.series:
        label = s.name or s.y_label or "DOS"
        ax.plot(s.x, s.y, label=label)

    x_label = bundle.series[0].x_label or "Energy"
    if bundle.series[0].x_unit:
        x_label += f" ({bundle.series[0].x_unit})"
    y_label = bundle.series[0].y_label or "DOS"
    if bundle.series[0].y_unit:
        y_label += f" ({bundle.series[0].y_unit})"

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title("Density of States")

    for marker in bundle.render_meta.markers:
        if "fermi" in marker.label.lower():
            ax.axvline(marker.position, color="red", linestyle="--", label=marker.label)

    if len(bundle.series) > 1 or bundle.render_meta.markers:
        ax.legend()

    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_bands(bundle: CanonicalPrimitiveBundle):
    """Multi-line plot: k-distance vs energy for each band."""
    import matplotlib.pyplot as plt

    if not bundle.series:
        return None

    fig, ax = plt.subplots(figsize=(8, 6))

    for s in bundle.series:
        ax.plot(s.x, s.y, color="steelblue", linewidth=0.8)

    x_label = bundle.series[0].x_label or "k-distance"
    y_label = bundle.series[0].y_label or "Energy"
    if bundle.series[0].y_unit:
        y_label += f" ({bundle.series[0].y_unit})"

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title("Band Structure")

    for marker in bundle.render_meta.markers:
        if "fermi" in marker.label.lower():
            ax.axhline(marker.position, color="red", linestyle="--", label=marker.label)

    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_trajectory(bundle: CanonicalPrimitiveBundle):
    """Energy vs frame plot for trajectory data."""
    import matplotlib.pyplot as plt

    if not bundle.series:
        return None

    s = bundle.series[0]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(s.x, s.y, "o-", markersize=3)

    x_label = s.x_label or "Frame"
    y_label = s.y_label or "Energy"
    if s.y_unit:
        y_label += f" ({s.y_unit})"

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title("Trajectory")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig
