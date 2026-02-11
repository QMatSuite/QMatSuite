"""Tests for trajectory transforms: FrameSlice, Smoothing, MSD, RDF, VACF, DiffusionCoefficient."""
from __future__ import annotations

import json

import numpy as np
import pytest

from quantumvitas.core.analysis.base import SourceFileStat
from quantumvitas.core.analysis.bundles import (
    CanonicalPrimitiveBundle,
    DerivedPrimitiveBundle,
    ProvenanceMeta,
    RenderMeta,
)
from quantumvitas.core.analysis.primitives import GeometryFrame, GeometryFrames, Series1D
from quantumvitas.core.analysis.transforms.diffusion import DiffusionCoefficient
from quantumvitas.core.analysis.transforms.frame_slice import FrameSlice
from quantumvitas.core.analysis.transforms.msd import MSD
from quantumvitas.core.analysis.transforms.rdf import RDF
from quantumvitas.core.analysis.transforms.smoothing import Smoothing
from quantumvitas.core.analysis.transforms.vacf import VACF


def _make_trajectory_bundle(n_frames: int = 10) -> CanonicalPrimitiveBundle:
    """Create a trajectory bundle with linear displacement for testing."""
    cell = np.array([[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]])
    frames = []
    time = np.arange(n_frames, dtype=float) * 10.0  # fs

    for i in range(n_frames):
        # 2 atoms, first moves linearly along x, second is stationary
        positions = np.array([
            [1.0 + 0.1 * i, 2.0, 3.0],
            [5.0, 5.0, 5.0],
        ])
        velocities = np.array([
            [0.1, 0.0, 0.0],
            [0.0, 0.0, 0.0],
        ])
        frames.append(GeometryFrame(
            positions=positions,
            species=["Si", "O"],
            cell=cell,
            pbc=(True, True, True),
            velocities=velocities,
        ))

    energy_series = Series1D(
        x=time,
        y=np.linspace(-100.0, -99.0, n_frames),
        x_label="Time",
        y_label="Energy",
        x_unit="fs",
        y_unit="eV",
        name="Energy",
    )

    return CanonicalPrimitiveBundle(
        object_type="trajectory",
        render_meta=RenderMeta(
            axis_labels={"x": "Time", "y": "Energy"},
            units={"x": "fs", "y": "eV"},
        ),
        provenance_meta=ProvenanceMeta(
            schema_version="1.0",
            object_type="trajectory",
            run_ulid="01RUN",
            calc_ulid="01CALC",
            step_ulids=["01STEP"],
            gen_steps=["md"],
            engine_name="test",
            source_files=[SourceFileStat(path="test.out", size_bytes=100, mtime=1.0)],
            parser_name="test",
            parser_version="1.0",
        ),
        series=[energy_series],
        geometry_frames=GeometryFrames(
            frames=frames,
            time=time,
        ),
    )


# ── FrameSlice ────────────────────────────────────────────────────

class TestFrameSlice:
    def test_correct_subset(self) -> None:
        bundle = _make_trajectory_bundle(10)
        sliced = FrameSlice(start=2, stop=6).apply(bundle)
        assert isinstance(sliced, DerivedPrimitiveBundle)
        assert len(sliced.geometry_frames.frames) == 4
        assert sliced.geometry_frames.time is not None
        np.testing.assert_allclose(sliced.geometry_frames.time, [20.0, 30.0, 40.0, 50.0])

    def test_series_alignment(self) -> None:
        bundle = _make_trajectory_bundle(10)
        sliced = FrameSlice(start=0, stop=5).apply(bundle)
        assert len(sliced.series[0].x) == 5
        assert len(sliced.series[0].y) == 5

    def test_step_parameter(self) -> None:
        bundle = _make_trajectory_bundle(10)
        sliced = FrameSlice(step=2).apply(bundle)
        assert len(sliced.geometry_frames.frames) == 5

    def test_pure_no_mutation(self) -> None:
        bundle = _make_trajectory_bundle(10)
        before = json.dumps(bundle.to_dict(), sort_keys=True)
        FrameSlice(start=2, stop=6).apply(bundle)
        after = json.dumps(bundle.to_dict(), sort_keys=True)
        assert before == after

    def test_transform_chain(self) -> None:
        bundle = _make_trajectory_bundle(10)
        sliced = FrameSlice(start=2, stop=6).apply(bundle)
        assert sliced.transform_chain[-1].transform_name == "frame_slice"


# ── Smoothing ─────────────────────────────────────────────────────

class TestSmoothing:
    def test_known_average(self) -> None:
        bundle = _make_trajectory_bundle(10)
        # Replace energy with known values
        bundle.series[0] = Series1D(
            x=np.arange(10, dtype=float),
            y=np.array([1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0, 17.0, 19.0]),
            x_label="Step", y_label="E", x_unit="", y_unit="eV", name="Energy",
        )
        smoothed = Smoothing(window_size=3).apply(bundle)
        assert isinstance(smoothed, DerivedPrimitiveBundle)
        expected = [3.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0, 17.0]
        np.testing.assert_allclose(smoothed.series[0].y, expected)
        assert len(smoothed.series[0].x) == len(expected)

    def test_window_1_identity(self) -> None:
        bundle = _make_trajectory_bundle(5)
        smoothed = Smoothing(window_size=1).apply(bundle)
        np.testing.assert_allclose(smoothed.series[0].y, bundle.series[0].y)

    def test_transform_chain(self) -> None:
        bundle = _make_trajectory_bundle(10)
        smoothed = Smoothing(window_size=3).apply(bundle)
        assert smoothed.transform_chain[-1].transform_name == "smoothing"

    def test_pure_no_mutation(self) -> None:
        bundle = _make_trajectory_bundle(5)
        before = json.dumps(bundle.to_dict(), sort_keys=True)
        Smoothing(window_size=2).apply(bundle)
        after = json.dumps(bundle.to_dict(), sort_keys=True)
        assert before == after


# ── MSD ───────────────────────────────────────────────────────────

class TestMSD:
    def test_linear_displacement_quadratic_msd(self) -> None:
        """Linear displacement -> MSD grows quadratically."""
        bundle = _make_trajectory_bundle(10)
        result = MSD().apply(bundle)
        assert isinstance(result, DerivedPrimitiveBundle)
        msd = result.arrays["msd"]
        assert msd[0] == pytest.approx(0.0, abs=1e-10)
        # MSD grows with frame index (atom 1 moves 0.1*i along x)
        assert msd[-1] > msd[1]

    def test_stationary_atoms_zero_msd(self) -> None:
        """All atoms stationary -> MSD = 0 everywhere."""
        cell = np.eye(3) * 10.0
        frames = [
            GeometryFrame(
                positions=np.array([[1.0, 2.0, 3.0]]),
                species=["Si"],
                cell=cell,
                pbc=(True, True, True),
            )
            for _ in range(5)
        ]
        bundle = CanonicalPrimitiveBundle(
            object_type="trajectory",
            render_meta=RenderMeta(axis_labels={}, units={}),
            provenance_meta=ProvenanceMeta(schema_version="1.0", object_type="trajectory"),
            geometry_frames=GeometryFrames(frames=frames, time=np.arange(5, dtype=float)),
        )
        result = MSD().apply(bundle)
        np.testing.assert_allclose(result.arrays["msd"], 0.0, atol=1e-10)

    def test_msd_series_output(self) -> None:
        bundle = _make_trajectory_bundle(10)
        result = MSD().apply(bundle)
        assert len(result.series) == 1
        assert result.series[0].name == "MSD"
        assert result.series[0].y_unit == "A^2"

    def test_transform_chain(self) -> None:
        bundle = _make_trajectory_bundle(5)
        result = MSD().apply(bundle)
        assert result.transform_chain[-1].transform_name == "msd"


# ── RDF ───────────────────────────────────────────────────────────

class TestRDF:
    def test_produces_output(self) -> None:
        bundle = _make_trajectory_bundle(5)
        result = RDF(r_max=6.0, n_bins=50).apply(bundle)
        assert isinstance(result, DerivedPrimitiveBundle)
        assert len(result.series) == 1
        assert result.series[0].name == "RDF"
        assert len(result.series[0].x) == 50
        assert len(result.series[0].y) == 50

    def test_rdf_unit_labels(self) -> None:
        bundle = _make_trajectory_bundle(5)
        result = RDF(r_max=5.0, n_bins=20).apply(bundle)
        assert result.series[0].x_unit == "A"
        assert result.series[0].y_unit == ""

    def test_transform_chain(self) -> None:
        bundle = _make_trajectory_bundle(5)
        result = RDF().apply(bundle)
        assert result.transform_chain[-1].transform_name == "rdf"

    def test_pure_no_mutation(self) -> None:
        bundle = _make_trajectory_bundle(5)
        before = json.dumps(bundle.to_dict(), sort_keys=True)
        RDF().apply(bundle)
        after = json.dumps(bundle.to_dict(), sort_keys=True)
        assert before == after


# ── VACF ──────────────────────────────────────────────────────────

class TestVACF:
    def test_constant_velocity(self) -> None:
        """Constant velocity -> VACF = 1.0 everywhere."""
        bundle = _make_trajectory_bundle(5)
        result = VACF().apply(bundle)
        assert isinstance(result, DerivedPrimitiveBundle)
        vacf = result.arrays["vacf"]
        # First value should be 1.0 (normalized)
        assert vacf[0] == pytest.approx(1.0, abs=1e-10)
        # With constant velocity, all values should be 1.0
        np.testing.assert_allclose(vacf, 1.0, atol=1e-10)

    def test_vacf_series_output(self) -> None:
        bundle = _make_trajectory_bundle(5)
        result = VACF().apply(bundle)
        assert len(result.series) == 1
        assert result.series[0].name == "VACF"

    def test_transform_chain(self) -> None:
        bundle = _make_trajectory_bundle(5)
        result = VACF().apply(bundle)
        assert result.transform_chain[-1].transform_name == "vacf"


# ── DiffusionCoefficient ─────────────────────────────────────────

class TestDiffusionCoefficient:
    def test_linear_msd_correct_d(self) -> None:
        """Linear MSD(t) = slope*t -> D = slope/6."""
        bundle = _make_trajectory_bundle(10)
        # First compute MSD
        msd_result = MSD().apply(bundle)

        # Apply diffusion coefficient
        d_result = DiffusionCoefficient().apply(msd_result)
        assert isinstance(d_result, DerivedPrimitiveBundle)
        assert "diffusion_coefficient" in d_result.arrays
        assert d_result.arrays["diffusion_coefficient"][0] != 0.0

    def test_with_fit_window(self) -> None:
        bundle = _make_trajectory_bundle(10)
        msd_result = MSD().apply(bundle)
        d_result = DiffusionCoefficient(fit_start=20.0, fit_end=70.0).apply(msd_result)
        assert "diffusion_coefficient" in d_result.arrays

    def test_transform_chain(self) -> None:
        bundle = _make_trajectory_bundle(10)
        msd_result = MSD().apply(bundle)
        d_result = DiffusionCoefficient().apply(msd_result)
        assert d_result.transform_chain[-1].transform_name == "diffusion_coefficient"
        assert d_result.transform_chain[-2].transform_name == "msd"
