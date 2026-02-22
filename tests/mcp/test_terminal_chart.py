"""Unit and integration tests for TerminalChart and render_bundle_to_ascii."""
from __future__ import annotations

import math

import numpy as np
import pytest

from qmatsuite.mcp.renderers.terminal_chart import TerminalChart
from qmatsuite.mcp.renderers.ascii_renderer import render_bundle_to_ascii

# ---------------------------------------------------------------------------
# Bundle helpers (duplicated from test_phase2a to keep this file self-contained)
# ---------------------------------------------------------------------------

from qmatsuite.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
)
from qmatsuite.core.analysis.primitives import Marker, Series1D


def _make_convergence_bundle() -> CanonicalPrimitiveBundle:
    iters = np.arange(1, 11, dtype=float)
    energies = -100.0 + 5.0 * np.exp(-0.5 * iters)
    return CanonicalPrimitiveBundle(
        object_type="convergence",
        series=[
            Series1D(
                x=iters, y=energies,
                x_label="Iteration", y_label="Energy",
                x_unit="", y_unit="Ry",
                name="scf_convergence",
            )
        ],
        render_meta=RenderMeta(
            axis_labels={"x": "Iteration", "y": "Energy (Ry)"},
            units={"energy": "Ry"},
        ),
        provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="convergence"),
    )


def _make_dos_bundle() -> CanonicalPrimitiveBundle:
    energies = np.linspace(-10.0, 5.0, 100)
    dos_vals = np.exp(-0.5 * (energies + 2.0) ** 2) + 0.5 * np.exp(
        -0.5 * (energies - 1.0) ** 2
    )
    return CanonicalPrimitiveBundle(
        object_type="dos",
        series=[
            Series1D(
                x=energies, y=dos_vals,
                x_label="Energy", y_label="DOS",
                x_unit="eV", y_unit="states/eV",
                name="total_dos",
            )
        ],
        render_meta=RenderMeta(
            axis_labels={"x": "Energy (eV)", "y": "DOS (states/eV)"},
            units={"energy": "eV"},
            markers=[Marker(position=0.0, label="Fermi energy", axis="x")],
        ),
        provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="dos"),
    )


def _make_bands_bundle() -> CanonicalPrimitiveBundle:
    k_dist = np.linspace(0.0, 1.0, 20)
    series = []
    for i in range(5):
        energies = -5.0 + i * 2.0 + 0.5 * np.sin(2 * np.pi * k_dist)
        series.append(
            Series1D(
                x=k_dist, y=energies,
                x_label="k-distance", y_label="Energy",
                x_unit="1/A", y_unit="eV",
                name=f"band_{i}",
            )
        )
    return CanonicalPrimitiveBundle(
        object_type="bands",
        series=series,
        render_meta=RenderMeta(
            axis_labels={"x": "k-distance (1/A)", "y": "Energy (eV)"},
            units={"energy": "eV"},
            markers=[Marker(position=0.0, label="Fermi energy", axis="y")],
        ),
        provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="bands"),
    )


# ===========================================================================
# TerminalChart unit tests
# ===========================================================================

class TestTerminalChart:
    def test_single_series_renders(self):
        chart = TerminalChart()
        chart.add_series([1, 2, 3, 4, 5], [1, 4, 9, 16, 25])
        text = chart.render()
        assert text
        lines = text.strip().split("\n")
        assert len(lines) >= 12  # multi-row chart

    def test_output_dimensions(self):
        chart = TerminalChart(width=78, height=18)
        xs = [i / 10 for i in range(100)]
        ys = [math.sin(x) for x in xs]
        chart.add_series(xs, ys)
        text = chart.render()
        lines = text.strip().split("\n")
        assert all(len(line) <= 80 for line in lines)

    def test_multiple_series(self):
        chart = TerminalChart(title="Two Series")
        chart.add_series([1, 2, 3], [1, 2, 3], label="A")
        chart.add_series([1, 2, 3], [3, 2, 1], label="B")
        text = chart.render()
        assert text
        # Both markers should appear
        assert "●" in text or "○" in text

    def test_hline_present(self):
        chart = TerminalChart()
        chart.add_series([0, 1, 2], [0, 0.5, 1])
        chart.add_hline(0.5, label="midpoint")
        text = chart.render()
        # Horizontal line character should appear
        assert "─" in text

    def test_vline_present(self):
        chart = TerminalChart()
        chart.add_series([0, 1, 2], [0, 1, 0])
        chart.add_vline(1.0, label="peak")
        text = chart.render()
        assert text

    def test_flat_line_no_crash(self):
        chart = TerminalChart()
        chart.add_series([1, 2, 3, 4, 5], [7.5, 7.5, 7.5, 7.5, 7.5])
        text = chart.render()
        assert text
        assert "No data" not in text

    def test_single_point_no_crash(self):
        chart = TerminalChart()
        chart.add_series([3.14], [2.71])
        text = chart.render()
        assert text
        assert "No data" not in text

    def test_nan_inf_filtered(self):
        chart = TerminalChart()
        chart.add_series(
            [1, 2, float("nan"), 4, float("inf")],
            [1, float("nan"), 3, 4, 5],
        )
        text = chart.render()
        # Only finite pairs survive: (1,1) and (4,4)
        assert "No data" not in text

    def test_all_nan_returns_no_data(self):
        chart = TerminalChart()
        chart.add_series([float("nan"), float("nan")], [float("nan"), float("nan")])
        text = chart.render()
        assert "No data" in text

    def test_negative_values(self):
        chart = TerminalChart()
        chart.add_series([-3, -2, -1, 0, 1], [-10, -5, 0, 5, 10])
        text = chart.render()
        assert text
        assert "No data" not in text

    def test_large_dataset_downsampled(self):
        chart = TerminalChart(width=78, height=16)
        xs = list(range(10000))
        ys = [math.sin(x * 0.01) for x in xs]
        chart.add_series(xs, ys)
        text = chart.render()
        lines = text.strip().split("\n")
        assert all(len(line) <= 80 for line in lines)

    def test_scientific_notation_ticks(self):
        chart = TerminalChart()
        xs = list(range(5))
        ys = [1e-8 + i * 1e-9 for i in range(5)]
        chart.add_series(xs, ys)
        text = chart.render()
        assert "e" in text  # scientific notation

    def test_axis_labels_present(self):
        chart = TerminalChart()
        chart.add_series([1, 2, 3], [4, 5, 6])
        chart.set_xlabel("X Axis")
        chart.set_ylabel("Y Axis")
        text = chart.render()
        assert "X Axis" in text
        assert "Y Axis" in text

    def test_empty_data_no_crash(self):
        chart = TerminalChart()
        text = chart.render()
        assert text  # returns "No data" string


# ===========================================================================
# Integration tests: render_bundle_to_ascii
# ===========================================================================

class TestRenderBundleToAscii:
    def test_convergence_bundle(self):
        bundle = _make_convergence_bundle()
        text = render_bundle_to_ascii(bundle)
        lines = text.strip().split("\n")
        assert len(lines) >= 8
        assert "CONVERGENCE" in text

    def test_dos_bundle(self):
        bundle = _make_dos_bundle()
        text = render_bundle_to_ascii(bundle)
        lines = text.strip().split("\n")
        assert len(lines) >= 8
        assert "DOS" in text

    def test_bands_bundle(self):
        bundle = _make_bands_bundle()
        text = render_bundle_to_ascii(bundle)
        lines = text.strip().split("\n")
        assert len(lines) >= 8
        assert "BANDS" in text

    def test_render_meta_used(self):
        """Axis labels from render_meta appear in chart output."""
        bundle = _make_convergence_bundle()
        text = render_bundle_to_ascii(bundle)
        # xlabel comes from render_meta.axis_labels["x"] = "Iteration"
        assert "Iteration" in text


# ===========================================================================
# plotext renderer tests
# ===========================================================================

class TestPlotextRenderer:
    def test_plotext_available(self):
        """plotext is installed and importable."""
        import plotext
        assert plotext is not None

    def test_convergence_renders(self):
        """Convergence bundle renders via plotext."""
        from qmatsuite.mcp.renderers.plotext_renderer import (
            render_bundle_with_plotext,
        )
        bundle = _make_convergence_bundle()
        result = render_bundle_with_plotext(bundle)
        assert result is not None
        lines = result.strip().split("\n")
        assert len(lines) >= 5
        assert "CONVERGENCE" in result

    def test_dos_renders(self):
        """DOS bundle renders via plotext."""
        from qmatsuite.mcp.renderers.plotext_renderer import (
            render_bundle_with_plotext,
        )
        bundle = _make_dos_bundle()
        result = render_bundle_with_plotext(bundle)
        assert result is not None
        lines = result.strip().split("\n")
        assert len(lines) >= 5
        assert "DOS" in result

    def test_bands_renders(self):
        """Bands bundle with 5 series renders without error."""
        from qmatsuite.mcp.renderers.plotext_renderer import (
            render_bundle_with_plotext,
        )
        bundle = _make_bands_bundle()
        result = render_bundle_with_plotext(bundle)
        assert result is not None
        lines = result.strip().split("\n")
        assert len(lines) >= 5
        assert "BANDS" in result

    def test_bands_with_fermi_shift(self):
        """Bands with reference_energy shifts y-axis label."""
        from qmatsuite.mcp.renderers.plotext_renderer import (
            render_bundle_with_plotext,
        )
        k_dist = np.linspace(0.0, 1.0, 20)
        series = [
            Series1D(
                x=k_dist, y=-5.0 + 2.0 * k_dist,
                x_label="k-path", y_label="Energy",
                x_unit="1/A", y_unit="eV",
                name="band_0",
            )
        ]
        bundle = CanonicalPrimitiveBundle(
            object_type="bands",
            series=series,
            render_meta=RenderMeta(
                axis_labels={"x": "k-path", "y": "Energy"},
                units={"energy": "eV"},
                reference_energy=2.0,
                markers=[
                    Marker(position=0.0, label="Γ", axis="x"),
                    Marker(position=1.0, label="X", axis="x"),
                ],
            ),
            provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="bands"),
        )
        result = render_bundle_with_plotext(bundle)
        assert "E_F" in result or "E - E_F" in result

    def test_no_ansi_codes(self):
        """Output should be free of ANSI escape codes."""
        from qmatsuite.mcp.renderers.plotext_renderer import (
            render_bundle_with_plotext,
        )
        bundle = _make_convergence_bundle()
        result = render_bundle_with_plotext(bundle)
        assert "\x1b" not in result

    def test_render_bundle_to_ascii_uses_plotext(self):
        """render_bundle_to_ascii should use plotext when available."""
        bundle = _make_convergence_bundle()
        text = render_bundle_to_ascii(bundle)
        # plotext produces box-drawing border characters
        assert "┌" in text or "┐" in text or "└" in text or "┘" in text
