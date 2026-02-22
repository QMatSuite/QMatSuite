"""Tests for LAMMPS trajectory parser."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qmatsuite.core.analysis.bundles import CanonicalPrimitiveBundle, compute_canonical_sha
from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.core.analysis.trajectory.model import Trajectory
from qmatsuite.drivers.lammps.parsers.trajectory import LAMMPSTrajectoryParser

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis_lammps_trajectory"


def _make_evidence(raw_dir: Path, gen_steps: list[str] | None = None) -> EvidenceBundle:
    return EvidenceBundle(
        primary_raw_dir=raw_dir,
        calc_dir=raw_dir.parent,
        run_ulid="01TESTRUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP"],
        gen_steps=gen_steps or ["md"],
        engine_name="lammps",
        evidence_steps=[],
    )


def test_can_parse_true() -> None:
    assert LAMMPSTrajectoryParser().can_parse(FIXTURE_DIR)


def test_can_parse_false(tmp_path: Path) -> None:
    assert not LAMMPSTrajectoryParser().can_parse(tmp_path)


def test_parse_returns_trajectory() -> None:
    result = LAMMPSTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    assert isinstance(result, Trajectory)


def test_parse_frame_count() -> None:
    result = LAMMPSTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    assert result.n_frames == 6  # dump every 2 steps for 10 steps = 6 frames (0,2,4,6,8,10)


def test_parse_positions_shape() -> None:
    result = LAMMPSTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.positions.shape == (108, 3)  # 108 LJ atoms


def test_parse_forces_present() -> None:
    result = LAMMPSTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.forces is not None
        assert frame.forces.shape == (108, 3)


def test_parse_velocities_present() -> None:
    result = LAMMPSTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.velocities is not None
        assert frame.velocities.shape == (108, 3)


def test_parse_cell_present() -> None:
    result = LAMMPSTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    for frame in result.frames:
        assert frame.cell is not None
        assert frame.cell.shape == (3, 3)


def test_parse_thermo_merge() -> None:
    """Thermo data from log.lammps merged with dump frames."""
    result = LAMMPSTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    # First frame (timestep 0) should have thermo
    assert result.frames[0].energy is not None
    assert result.frames[0].temperature is not None


def test_to_primitives() -> None:
    result = LAMMPSTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    canonical = result.to_primitives()
    assert isinstance(canonical, CanonicalPrimitiveBundle)
    assert canonical.object_type == "trajectory"


def test_sha_deterministic() -> None:
    result = LAMMPSTrajectoryParser().parse(_make_evidence(FIXTURE_DIR))
    sha1 = compute_canonical_sha(result.to_primitives())
    sha2 = compute_canonical_sha(result.to_primitives())
    assert len(sha1) == 64
    assert sha1 == sha2
