"""Matplotlib-based PNG renderer for CanonicalPrimitiveBundle.

Uses ``matplotlib.use('Agg')`` for headless operation.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle


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

    # Fermi energy: prefer reference_energy, fall back to markers
    fermi_drawn = False
    if bundle.render_meta.reference_energy is not None:
        ax.axvline(
            bundle.render_meta.reference_energy,
            color="red", linestyle="--", linewidth=1.0,
            label=f"E_F = {bundle.render_meta.reference_energy:.4f}",
        )
        fermi_drawn = True

    if not fermi_drawn:
        for marker in bundle.render_meta.markers:
            if "fermi" in marker.label.lower():
                ax.axvline(marker.position, color="red", linestyle="--", label=marker.label)
                fermi_drawn = True
                break

    if len(bundle.series) > 1 or fermi_drawn:
        ax.legend()

    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def _plot_bands(bundle: CanonicalPrimitiveBundle):
    """Band structure plot with Fermi level, k-point labels, and E-shift."""
    import matplotlib.pyplot as plt

    if not bundle.series:
        return None

    fig, ax = plt.subplots(figsize=(8, 6))

    # Determine Fermi energy for shifting
    e_fermi = bundle.render_meta.reference_energy  # may be None

    # Separate k-point markers (axis="x") from other markers
    kpoint_markers = []
    other_markers = []
    for marker in bundle.render_meta.markers:
        if marker.axis == "x":
            kpoint_markers.append(marker)
        else:
            other_markers.append(marker)

    # Plot bands — shift by Fermi energy if available
    for s in bundle.series:
        y_data = s.y
        if e_fermi is not None:
            y_data = s.y - e_fermi
        ax.plot(s.x, y_data, color="steelblue", linewidth=0.8)

    # Y-axis label
    if e_fermi is not None:
        y_label = "E \u2212 E\u2082 (eV)"  # E − E_F (eV) — use subscript F
        y_label = "E \u2212 E_F (eV)"
    else:
        y_label = bundle.series[0].y_label or "Energy"
        if bundle.series[0].y_unit:
            y_label += f" ({bundle.series[0].y_unit})"

    ax.set_ylabel(y_label)
    ax.set_title("Band Structure")

    # Fermi level reference line (at 0 after shift, or at E_F if no shift)
    if e_fermi is not None:
        ax.axhline(0.0, color="red", linestyle="--", linewidth=0.8, label="E_F")

    # High-symmetry k-point labels on x-axis
    if kpoint_markers:
        tick_positions = [m.position for m in kpoint_markers]
        tick_labels = [m.label for m in kpoint_markers]

        # Draw vertical lines at high-symmetry points
        for pos in tick_positions:
            ax.axvline(pos, color="gray", linewidth=0.5, alpha=0.7)

        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels)
        ax.set_xlim(tick_positions[0], tick_positions[-1])
    else:
        ax.set_xlabel(bundle.series[0].x_label or "k-path")

    ax.grid(True, axis="y", alpha=0.3)
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
