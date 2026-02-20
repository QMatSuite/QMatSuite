"""Tests for MCP Phase 2A: list_analyses + plot_analysis + renderers.

Uses synthetic CanonicalPrimitiveBundle objects — no real engine runs needed.
"""
from __future__ import annotations

import numpy as np
import pytest

from quantumvitas.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
)
from quantumvitas.core.analysis.primitives import Marker, Series1D


# ---------------------------------------------------------------------------
# Helpers: build synthetic bundles
# ---------------------------------------------------------------------------

def _make_convergence_bundle() -> CanonicalPrimitiveBundle:
    """Convergence bundle: 10 SCF iterations."""
    iters = np.arange(1, 11, dtype=float)
    energies = -100.0 + 5.0 * np.exp(-0.5 * iters)
    return CanonicalPrimitiveBundle(
        object_type="convergence",
        series=[
            Series1D(
                x=iters,
                y=energies,
                x_label="Iteration",
                y_label="Energy",
                x_unit="",
                y_unit="Ry",
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
    """DOS bundle: energy vs DOS with Fermi marker."""
    energies = np.linspace(-10.0, 5.0, 100)
    dos_vals = np.exp(-0.5 * (energies + 2.0) ** 2) + 0.5 * np.exp(
        -0.5 * (energies - 1.0) ** 2
    )
    return CanonicalPrimitiveBundle(
        object_type="dos",
        series=[
            Series1D(
                x=energies,
                y=dos_vals,
                x_label="Energy",
                y_label="DOS",
                x_unit="eV",
                y_unit="states/eV",
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
    """Bands bundle: 5 bands, 20 k-points each."""
    k_dist = np.linspace(0.0, 1.0, 20)
    series = []
    for i in range(5):
        energies = -5.0 + i * 2.0 + 0.5 * np.sin(2 * np.pi * k_dist)
        series.append(
            Series1D(
                x=k_dist,
                y=energies,
                x_label="k-distance",
                y_label="Energy",
                x_unit="1/A",
                y_unit="eV",
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


def _make_scf_digest_bundle() -> CanonicalPrimitiveBundle:
    """SCF digest bundle with key-value data in render_meta.extra."""
    return CanonicalPrimitiveBundle(
        object_type="scf_digest",
        render_meta=RenderMeta(
            extra={
                "converged": True,
                "total_energy_eV": -135.42,
                "fermi_energy_eV": 6.34,
                "n_iterations": 8,
            }
        ),
        provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="scf_digest"),
    )


def _make_trajectory_bundle() -> CanonicalPrimitiveBundle:
    """Trajectory bundle: 5 frames of energy data."""
    frames = np.arange(1, 6, dtype=float)
    energies = -100.0 + np.array([0.5, 0.3, 0.15, 0.08, 0.02])
    return CanonicalPrimitiveBundle(
        object_type="trajectory",
        series=[
            Series1D(
                x=frames,
                y=energies,
                x_label="Frame",
                y_label="Energy",
                x_unit="",
                y_unit="eV",
                name="trajectory_energy",
            )
        ],
        render_meta=RenderMeta(
            axis_labels={"x": "Frame", "y": "Energy (eV)"},
            units={"energy": "eV"},
        ),
        provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="trajectory"),
    )


# ---------------------------------------------------------------------------
# Test helper: patch analysis service at the right level
# ---------------------------------------------------------------------------

def _patch_analysis_instances(monkeypatch, mock_return):
    """Patch get_service so analysis.get_analysis_instances_for_step returns mock_return.

    Since ``QVService.analysis`` is a property that creates a fresh
    ``Analysis`` instance each call, we must patch at the class level.
    """
    from quantumvitas.api import QVService

    original_analysis_class = QVService.Analysis

    class PatchedAnalysis(original_analysis_class):
        def get_analysis_instances_for_step(self, *args, **kwargs):
            return mock_return

    monkeypatch.setattr(QVService, "analysis", property(lambda self: PatchedAnalysis(self)))


# ===========================================================================
# ASCII Renderer Tests
# ===========================================================================

class TestAsciiRenderer:
    def test_convergence(self):
        from quantumvitas.mcp.renderers.ascii_renderer import render_bundle_ascii

        bundle = _make_convergence_bundle()
        text = render_bundle_ascii(bundle)
        lines = text.strip().split("\n")
        assert len(lines) >= 8  # 2D chart, not a one-line sparkline
        assert "CONVERGENCE" in text or "Iteration" in text

    def test_dos(self):
        from quantumvitas.mcp.renderers.ascii_renderer import render_bundle_ascii

        bundle = _make_dos_bundle()
        text = render_bundle_ascii(bundle)
        lines = text.strip().split("\n")
        assert len(lines) >= 8

    def test_bands_summary(self):
        from quantumvitas.mcp.renderers.ascii_renderer import render_bundle_ascii

        bundle = _make_bands_bundle()
        text = render_bundle_ascii(bundle)
        lines = text.strip().split("\n")
        assert len(lines) >= 8

    def test_scf_digest(self):
        from quantumvitas.mcp.renderers.ascii_renderer import render_bundle_ascii

        bundle = _make_scf_digest_bundle()
        text = render_bundle_ascii(bundle)
        assert "=== SCF Digest ===" in text
        assert "converged" in text
        assert "total_energy_eV" in text

    def test_trajectory(self):
        from quantumvitas.mcp.renderers.ascii_renderer import render_bundle_ascii

        bundle = _make_trajectory_bundle()
        text = render_bundle_ascii(bundle)
        lines = text.strip().split("\n")
        assert len(lines) >= 8  # 2D chart, not a one-line sparkline

    def test_empty_series(self):
        from quantumvitas.mcp.renderers.ascii_renderer import render_bundle_ascii

        bundle = CanonicalPrimitiveBundle(
            object_type="convergence",
            provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="convergence"),
        )
        text = render_bundle_ascii(bundle)
        assert "(no data)" in text

    def test_generic_fallback(self):
        from quantumvitas.mcp.renderers.ascii_renderer import render_bundle_ascii

        bundle = CanonicalPrimitiveBundle(
            object_type="unknown_type",
            series=[
                Series1D(
                    x=np.array([1.0, 2.0]),
                    y=np.array([3.0, 4.0]),
                    x_label="x",
                    y_label="y",
                    x_unit="",
                    y_unit="",
                )
            ],
            provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="unknown_type"),
        )
        text = render_bundle_ascii(bundle)
        assert "=== unknown_type ===" in text
        assert "Series: 1" in text
        assert "2 points" in text

    def test_field3d(self):
        from quantumvitas.mcp.renderers.ascii_renderer import render_bundle_ascii

        bundle = CanonicalPrimitiveBundle(
            object_type="field3d",
            render_meta=RenderMeta(extra={"grid_dims": [40, 40, 40]}),
            provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="field3d"),
        )
        text = render_bundle_ascii(bundle)
        assert "=== Field3D ===" in text
        assert "Grid:" in text


class TestSparklineHelper:
    def test_sparkline_basic(self):
        from quantumvitas.mcp.renderers.ascii_renderer import _sparkline

        result = _sparkline([1.0, 2.0, 3.0, 4.0, 5.0], width=10)
        assert len(result) == 5  # fewer values than width → no resampling
        assert result[0] == " "  # min value
        assert result[-1] == "█"  # max value

    def test_sparkline_empty(self):
        from quantumvitas.mcp.renderers.ascii_renderer import _sparkline

        assert _sparkline([]) == ""

    def test_sparkline_constant(self):
        from quantumvitas.mcp.renderers.ascii_renderer import _sparkline

        result = _sparkline([5.0, 5.0, 5.0], width=10)
        assert len(result) == 3
        # All same value → all same char
        assert len(set(result)) == 1

    def test_sparkline_resampling(self):
        from quantumvitas.mcp.renderers.ascii_renderer import _sparkline

        values = list(range(100))
        result = _sparkline(values, width=20)
        assert len(result) == 20


class TestUnicodeBarHelper:
    def test_bar_basic(self):
        from quantumvitas.mcp.renderers.ascii_renderer import _unicode_bar

        result = _unicode_bar(10.0, 10.0, width=10)
        assert "█" in result
        assert len(result) <= 11  # up to width + 1 fractional char

    def test_bar_zero(self):
        from quantumvitas.mcp.renderers.ascii_renderer import _unicode_bar

        assert _unicode_bar(0.0, 10.0) == ""

    def test_bar_half(self):
        from quantumvitas.mcp.renderers.ascii_renderer import _unicode_bar

        result = _unicode_bar(5.0, 10.0, width=20)
        # ~10 full blocks
        assert len(result) >= 10
        assert len(result) <= 12


# ===========================================================================
# Matplotlib Renderer Tests
# ===========================================================================

class TestMatplotlibRenderer:
    def test_convergence_png(self, tmp_path):
        from quantumvitas.mcp.renderers.matplotlib_renderer import render_bundle_png

        bundle = _make_convergence_bundle()
        out = tmp_path / "conv.png"
        result = render_bundle_png(bundle, out)
        assert result is not None
        assert result.exists()
        assert result.stat().st_size > 0

    def test_dos_png(self, tmp_path):
        from quantumvitas.mcp.renderers.matplotlib_renderer import render_bundle_png

        bundle = _make_dos_bundle()
        out = tmp_path / "dos.png"
        result = render_bundle_png(bundle, out)
        assert result is not None
        assert result.exists()

    def test_bands_png(self, tmp_path):
        from quantumvitas.mcp.renderers.matplotlib_renderer import render_bundle_png

        bundle = _make_bands_bundle()
        out = tmp_path / "bands.png"
        result = render_bundle_png(bundle, out)
        assert result is not None
        assert result.exists()

    def test_trajectory_png(self, tmp_path):
        from quantumvitas.mcp.renderers.matplotlib_renderer import render_bundle_png

        bundle = _make_trajectory_bundle()
        out = tmp_path / "traj.png"
        result = render_bundle_png(bundle, out)
        assert result is not None
        assert result.exists()

    def test_not_plottable_scf_digest(self, tmp_path):
        from quantumvitas.mcp.renderers.matplotlib_renderer import render_bundle_png

        bundle = _make_scf_digest_bundle()
        out = tmp_path / "digest.png"
        result = render_bundle_png(bundle, out)
        assert result is None
        assert not out.exists()

    def test_not_plottable_field3d(self, tmp_path):
        from quantumvitas.mcp.renderers.matplotlib_renderer import render_bundle_png

        bundle = CanonicalPrimitiveBundle(
            object_type="field3d",
            provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="field3d"),
        )
        out = tmp_path / "field3d.png"
        result = render_bundle_png(bundle, out)
        assert result is None

    def test_creates_parent_dirs(self, tmp_path):
        from quantumvitas.mcp.renderers.matplotlib_renderer import render_bundle_png

        bundle = _make_convergence_bundle()
        out = tmp_path / "nested" / "dir" / "conv.png"
        result = render_bundle_png(bundle, out)
        assert result is not None
        assert result.exists()

    def test_empty_series_returns_none(self, tmp_path):
        from quantumvitas.mcp.renderers.matplotlib_renderer import render_bundle_png

        bundle = CanonicalPrimitiveBundle(
            object_type="convergence",
            provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="convergence"),
        )
        out = tmp_path / "empty.png"
        result = render_bundle_png(bundle, out)
        assert result is None


# ===========================================================================
# list_analyses Tool Tests
# ===========================================================================

class TestListAnalyses:
    def test_no_project(self, monkeypatch):
        from quantumvitas.mcp import project as mcp_project
        from quantumvitas.mcp.tools.list_analyses import list_analyses

        monkeypatch.setattr(mcp_project, "_project_root_override", None)
        monkeypatch.delenv("QMATSUITE_PROJECT", raising=False)

        result = list_analyses.fn(calc_ulid="FAKE_ULID")
        assert result["status"] == "error"
        assert result["error_type"] == "no_project"

    def test_not_found(self, qv_project):
        from quantumvitas.mcp.tools.list_analyses import list_analyses

        result = list_analyses.fn(calc_ulid="NONEXISTENT_ULID_12345")
        assert result["status"] == "error"
        assert result["error_type"] == "not_found"

    def test_happy_path(self, qv_project):
        """Create a QE SCF calc and list analyses — should find convergence."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.list_analyses import list_analyses

        # Create a QE SCF calculation
        cr = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        assert cr["status"] == "success"
        calc_ulid = cr["data"]["calc_ulid"]

        result = list_analyses.fn(calc_ulid=calc_ulid, step=0)
        assert result["status"] == "success"
        data = result["data"]
        assert "analyses" in data
        assert data["engine"] == "qe"
        assert data["step_index"] == 0
        # QE SCF should declare convergence + field3d capabilities
        obj_types = [a["object_type"] for a in data["analyses"]]
        assert "convergence" in obj_types

    def test_no_steps(self, qv_project, monkeypatch):
        """Calc with empty steps list returns no_steps error."""
        from quantumvitas.mcp.tools.list_analyses import list_analyses
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.api import QVService

        cr = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = cr["data"]["calc_ulid"]

        # QVService.calculation is a property → must patch at class level
        original_calc_class = QVService.Calculation

        class PatchedCalculation(original_calc_class):
            def get_detail(self, selector):
                d = super().get_detail(selector)
                d["steps"] = []
                return d

        monkeypatch.setattr(
            QVService, "calculation",
            property(lambda self: PatchedCalculation(self)),
        )

        result = list_analyses.fn(calc_ulid=calc_ulid)
        assert result["status"] == "error"
        assert result["error_type"] == "no_steps"

    def test_invalid_step_index(self, qv_project):
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.list_analyses import list_analyses

        cr = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = cr["data"]["calc_ulid"]

        result = list_analyses.fn(calc_ulid=calc_ulid, step=99)
        assert result["status"] == "error"
        assert result["error_type"] == "invalid_step_index"

    def test_default_step_minus_one(self, qv_project):
        """step=-1 should resolve to last step."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.list_analyses import list_analyses

        cr = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = cr["data"]["calc_ulid"]

        result = list_analyses.fn(calc_ulid=calc_ulid)  # default step=-1
        assert result["status"] == "success"
        # For single-step SCF, step_index should be 0
        assert result["data"]["step_index"] == 0


# ===========================================================================
# plot_analysis Tool Tests
# ===========================================================================

class TestPlotAnalysis:
    def test_no_project(self, monkeypatch):
        from quantumvitas.mcp import project as mcp_project
        from quantumvitas.mcp.tools.plot_analysis import plot_analysis

        monkeypatch.setattr(mcp_project, "_project_root_override", None)
        monkeypatch.delenv("QMATSUITE_PROJECT", raising=False)

        result = plot_analysis.fn(calc_ulid="FAKE", object_type="convergence")
        assert result["status"] == "error"
        assert result["error_type"] == "no_project"

    def test_not_found(self, qv_project):
        from quantumvitas.mcp.tools.plot_analysis import plot_analysis

        result = plot_analysis.fn(calc_ulid="NONEXISTENT_ULID", object_type="convergence")
        assert result["status"] == "error"
        assert result["error_type"] == "not_found"

    def test_not_available(self, qv_project, monkeypatch):
        """Request an object_type that doesn't exist for the step."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.plot_analysis import plot_analysis

        cr = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = cr["data"]["calc_ulid"]

        _patch_analysis_instances(monkeypatch, {"instances": []})

        result = plot_analysis.fn(
            calc_ulid=calc_ulid, object_type="nonexistent_type",
        )
        assert result["status"] == "error"
        assert result["error_type"] == "not_available"

    def test_convergence_happy_path(self, qv_project, monkeypatch):
        """Mock analysis API to return a convergence bundle, verify render."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.plot_analysis import plot_analysis

        cr = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = cr["data"]["calc_ulid"]

        bundle = _make_convergence_bundle()
        _patch_analysis_instances(monkeypatch, {
            "instances": [{
                "object_type": "convergence",
                "step_ulids": ["fake_ulid"],
                "gen_steps": ["scf"],
                "state": "ok",
                "bundle": bundle.to_dict(),
            }]
        })

        result = plot_analysis.fn(
            calc_ulid=calc_ulid, object_type="convergence",
        )
        assert result["status"] == "success"
        data = result["data"]
        assert data["object_type"] == "convergence"
        assert "ascii_plot" in data
        assert len(data["ascii_plot"].strip().split("\n")) >= 8  # 2D chart
        # Context-window safe: no raw arrays, only metadata
        assert "primitive_meta" in data
        assert data["primitive_meta"]["n_series"] == 1
        assert "summary" in data
        assert "final_value" in data["summary"]
        assert "plot_files" in data
        assert "evidence_files" in data
        # Must NOT contain raw bundle data
        assert "bundle" not in data

    def test_dos_happy_path(self, qv_project, monkeypatch):
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.plot_analysis import plot_analysis

        cr = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = cr["data"]["calc_ulid"]

        bundle = _make_dos_bundle()
        _patch_analysis_instances(monkeypatch, {
            "instances": [{
                "object_type": "dos",
                "step_ulids": ["fake"],
                "gen_steps": ["dos"],
                "state": "ok",
                "bundle": bundle.to_dict(),
            }]
        })

        result = plot_analysis.fn(calc_ulid=calc_ulid, object_type="dos")
        assert result["status"] == "success"
        data = result["data"]
        assert len(data["ascii_plot"].strip().split("\n")) >= 8  # 2D chart
        assert data["primitive_meta"]["n_series"] == 1
        # DOS summary should have Fermi marker
        assert "fermi_energy" in data["summary"]

    def test_bands_happy_path(self, qv_project, monkeypatch):
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.plot_analysis import plot_analysis

        cr = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = cr["data"]["calc_ulid"]

        bundle = _make_bands_bundle()
        _patch_analysis_instances(monkeypatch, {
            "instances": [{
                "object_type": "bands",
                "step_ulids": ["fake"],
                "gen_steps": ["bandspw"],
                "state": "ok",
                "bundle": bundle.to_dict(),
            }]
        })

        result = plot_analysis.fn(calc_ulid=calc_ulid, object_type="bands")
        assert result["status"] == "success"
        data = result["data"]
        assert len(data["ascii_plot"].strip().split("\n")) >= 8  # 2D chart
        assert data["primitive_meta"]["n_series"] == 5
        assert "x_range" in data["primitive_meta"]
        assert "y_range" in data["primitive_meta"]

    def test_scf_digest_no_png(self, qv_project, monkeypatch):
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.plot_analysis import plot_analysis

        cr = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = cr["data"]["calc_ulid"]

        bundle = _make_scf_digest_bundle()
        _patch_analysis_instances(monkeypatch, {
            "instances": [{
                "object_type": "scf_digest",
                "step_ulids": ["fake"],
                "gen_steps": ["scf"],
                "state": "ok",
                "bundle": bundle.to_dict(),
            }]
        })

        result = plot_analysis.fn(calc_ulid=calc_ulid, object_type="scf_digest")
        assert result["status"] == "success"
        data = result["data"]
        assert "SCF Digest" in data["ascii_plot"]
        assert data["plot_files"] == []  # not plottable
        # Summary should have extracted scalars from render_meta.extra
        assert data["summary"].get("converged") is True
        assert data["summary"].get("total_energy_eV") == -135.42

    def test_parse_failed_state(self, qv_project, monkeypatch):
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.plot_analysis import plot_analysis

        cr = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="Silicon",
        )
        calc_ulid = cr["data"]["calc_ulid"]

        _patch_analysis_instances(monkeypatch, {
            "instances": [{
                "object_type": "convergence",
                "step_ulids": ["fake"],
                "gen_steps": ["scf"],
                "state": "missing_evidence",
                "bundle": None,
            }]
        })

        result = plot_analysis.fn(calc_ulid=calc_ulid, object_type="convergence")
        assert result["status"] == "error"
        assert result["error_type"] == "parse_failed"


# ===========================================================================
# Server Registration Test
# ===========================================================================

class TestServerRegistration:
    def test_tools_registered(self):
        """Verify list_analyses and plot_analysis are registered in the MCP server."""
        from quantumvitas.mcp.server import mcp

        tool_names = set(mcp._tool_manager._tools.keys())
        assert "list_analyses" in tool_names
        assert "plot_analysis" in tool_names

    def test_tool_count_at_least_29(self):
        """Should have at least 29 tools (27 existing + 2 new)."""
        from quantumvitas.mcp.server import mcp

        assert len(mcp._tool_manager._tools) >= 29
